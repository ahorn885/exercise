"""Layer 2C builder — equipment mapper query node.

Per `Layer2C_Spec.md` §3 (function signature) + §5 (algorithm). Pure
query node: deterministic given inputs, no LLM involvement. Two SQL
queries per call — (1) the toggle-definition lookup against
`layer0.sport_specific_gear_toggles` (§5.1 DP1 = (A) Runtime lookup),
and (2) the discipline-bridged exercise enumeration joining
`sport_discipline_bridge`, `sport_exercise_map`, and `exercises` per
§5.2. Plus one tiny supplemental sdb-only query (3) so zero-exercise
disciplines still surface a `DisciplineCoverage` row.

Function signature mirrors `q_layer2b_terrain_classifier_payload` and
`q_layer2d_injury_risk_payload` — `db` first positional, the §5.6
amendment's optional `layer2d_payload` and `etl_version_set` keyword-only.

Decision Points pinned by D-73 Phase 2.4-Prep (Andy 2026-05-19):
  DP1 (§5.1) = (A) Runtime lookup — `_load_toggle_defs` reads the table
    at call time; no Layer 1 disturbance.
  DP2 (§8.3) = (b) Structured column — toggle-OFF-for-discipline flag
    reads `gated_discipline_ids` from the toggle row directly; no
    hard-coded mapping in 2C code.

§5.1 vs §6 reconciliation: §5.1's pseudo-code adds `toggle_def.also_satisfies`
items straight into the equipment pool, but the deployed data shape
(per `migrate_toggles_v3_columns.sql` + `Vocabulary_Audit_v2.md §4.2`)
treats `also_satisfies` as a list of TOGGLE NAMES, not equipment names.
§6's prose is the canonical reading: an `also_satisfies` entry expands
to the referenced toggle's `paired_equipment_categories` (one hop, no
cascade per §6 paragraph 3). This builder implements §6 semantics.
"""

from __future__ import annotations

import re
from collections import Counter
from typing import Any

from layer4.context import (
    DisciplineCoverage,
    Layer2CCoachingFlag,
    Layer2CPayload,
    Layer2DPayload,
    ResolutionDetail,
    ResolvedExercise,
)


# ─── Constants ───────────────────────────────────────────────────────────────


_REQUIRED_ETL_KEYS: frozenset[str] = frozenset({"0A", "0B", "0C"})

# §8.1 low-coverage threshold per spec — flags any discipline where
# fewer than half of its mapped exercises resolve to a usable tier.
_LOW_COVERAGE_THRESHOLD: float = 0.50

# §8.2 critical-priority sentinel. `sport_exercise_map.priority` is a
# free-text column; the canonical value is the string "Critical".
_CRITICAL_PRIORITY: str = "Critical"

# Discipline-id regex matches the D-### convention used across Layer 2
# specs. Validation is shape-only (UI-side does canonical lookups).
_DISCIPLINE_ID_PATTERN = re.compile(r"^D-\d{3}[a-z]?$")


# ─── Errors ──────────────────────────────────────────────────────────────────


class Layer2CInputError(ValueError):
    """Raised by `q_layer2c_equipment_mapper_payload` on §4 validation
    failure. Plan-gen catches and surfaces a user-facing error. This is
    NOT a HITL gate — HITL is for ambiguous content, not malformed inputs."""


# ─── Validation (spec §4) ────────────────────────────────────────────────────


def _validate_inputs(
    locale_id: str,
    locale_equipment_pool: list[str],
    cluster_locale_ids: list[str],
    cluster_gear_toggle_states: dict[str, bool],
    included_discipline_ids: list[str],
    etl_version_set: dict[str, str],
) -> None:
    if not isinstance(locale_id, str) or not locale_id:
        raise Layer2CInputError("locale_id must be a non-empty string")

    if not isinstance(locale_equipment_pool, list):
        raise Layer2CInputError(
            "locale_equipment_pool must be a list (may be empty)"
        )
    for idx, token in enumerate(locale_equipment_pool):
        if not isinstance(token, str):
            raise Layer2CInputError(
                f"locale_equipment_pool[{idx}] must be a string (got {type(token).__name__})"
            )

    if not isinstance(cluster_locale_ids, list) or not cluster_locale_ids:
        raise Layer2CInputError(
            "cluster_locale_ids must be a non-empty list"
        )
    if locale_id not in cluster_locale_ids:
        raise Layer2CInputError(
            f"locale_id {locale_id!r} must be in cluster_locale_ids"
        )

    if not isinstance(cluster_gear_toggle_states, dict):
        raise Layer2CInputError(
            "cluster_gear_toggle_states must be a dict"
        )
    for k, v in cluster_gear_toggle_states.items():
        if not isinstance(k, str):
            raise Layer2CInputError(
                f"cluster_gear_toggle_states key {k!r} must be a string"
            )
        if not isinstance(v, bool):
            raise Layer2CInputError(
                f"cluster_gear_toggle_states[{k!r}] must be a bool (got {type(v).__name__})"
            )

    if not isinstance(included_discipline_ids, list) or not included_discipline_ids:
        raise Layer2CInputError(
            "included_discipline_ids must be a non-empty list"
        )
    for idx, d_id in enumerate(included_discipline_ids):
        if not isinstance(d_id, str) or not _DISCIPLINE_ID_PATTERN.match(d_id):
            raise Layer2CInputError(
                f"included_discipline_ids[{idx}] {d_id!r} must match pattern D-\\d{{3}}[a-z]?"
            )

    if not isinstance(etl_version_set, dict) or not _REQUIRED_ETL_KEYS.issubset(
        etl_version_set.keys()
    ):
        raise Layer2CInputError(
            f"etl_version_set must contain keys {sorted(_REQUIRED_ETL_KEYS)}; "
            f"got {sorted(etl_version_set.keys()) if isinstance(etl_version_set, dict) else etl_version_set!r}"
        )


# ─── DB loaders ──────────────────────────────────────────────────────────────


def _load_toggle_defs(
    db,
    version_0c: str,
) -> dict[str, dict[str, Any]]:
    """§5.1 DP1 (A) — Runtime lookup of toggle definitions for the active
    0C version. Returns a dict keyed by toggle_name carrying the four
    fields 2C reads (paired_equipment_categories, also_satisfies,
    gated_discipline_ids, display_label). Single query against the
    11-row table; indexed by UNIQUE (toggle_name, etl_version).
    """
    cur = db.execute(
        """
        SELECT
          toggle_name,
          display_label,
          paired_equipment_categories,
          also_satisfies,
          gated_discipline_ids
        FROM layer0.sport_specific_gear_toggles
         WHERE etl_version = ?
           AND superseded_at IS NULL
        """,
        (version_0c,),
    )
    return {
        r["toggle_name"]: {
            "toggle_name": r["toggle_name"],
            "display_label": r.get("display_label"),
            "paired_equipment_categories": list(
                r.get("paired_equipment_categories") or []
            ),
            "also_satisfies": list(r.get("also_satisfies") or []),
            "gated_discipline_ids": list(r.get("gated_discipline_ids") or []),
        }
        for r in cur.fetchall()
    }


def _load_skill_capability_toggle_defs(
    db,
    version_0c: str,
) -> dict[str, dict[str, list[str]]]:
    """D-73 Phase 5.2 Bucket C (l) — read the skill-capability toggle
    vocab from `layer0.skill_capability_toggles` (5 active rows at
    canonical 0C version per
    `etl/sources/populate_skill_capability_toggles.sql`). Returns a
    dict keyed by toggle_name carrying `gated_discipline_ids` (2C reads
    the discipline side; 2B has its own copy that reads the terrain
    side). Empty dict when the table has no active rows.
    """
    cur = db.execute(
        """
        SELECT toggle_name, gated_terrain_ids, gated_discipline_ids
          FROM layer0.skill_capability_toggles
         WHERE etl_version = ?
           AND superseded_at IS NULL
        """,
        (version_0c,),
    )
    return {
        r["toggle_name"]: {
            "gated_terrain_ids": list(r.get("gated_terrain_ids") or []),
            "gated_discipline_ids": list(r.get("gated_discipline_ids") or []),
        }
        for r in cur.fetchall()
    }


def _load_discipline_info(
    db,
    discipline_ids: list[str],
    version_0a: str,
) -> dict[str, dict[str, str]]:
    """Pull discipline_name + exercise_db_sport from sport_discipline_bridge
    for every included discipline. Standalone so zero-exercise disciplines
    still surface a `DisciplineCoverage` row + a `low_coverage` flag per
    §10 ("Discipline in `included_discipline_ids` has zero exercises").

    A discipline may appear under multiple framework_sports in sdb (e.g.,
    Trail Running under both AR and Triathlon). exercise_db_sport should
    be stable across them — we take the first row deterministically.
    """
    cur = db.execute(
        """
        SELECT discipline_id, discipline_name, exercise_db_sport
          FROM layer0.sport_discipline_bridge
         WHERE discipline_id = ANY(?)
           AND etl_version = ?
           AND superseded_at IS NULL
        """,
        (list(discipline_ids), version_0a),
    )
    info: dict[str, dict[str, str]] = {}
    for r in cur.fetchall():
        d_id = r["discipline_id"]
        if d_id not in info:
            info[d_id] = {
                "discipline_name": r["discipline_name"],
                "exercise_db_sport": r["exercise_db_sport"],
            }
    return info


def _load_exercises(
    db,
    included_discipline_ids: list[str],
    version_0a: str,
    versions_0b: list[str],
) -> list[dict[str, Any]]:
    """Spec §5.2 — exercise universe across the included disciplines.

    JOINs sport_discipline_bridge → sport_exercise_map → exercises.
    Returns raw rows (one per (discipline, exercise) pair); the caller
    deduplicates by exercise_id and tracks discipline attribution.
    """
    cur = db.execute(
        """
        SELECT
          sxm.exercise_id,
          sxm.exercise_name,
          sxm.exercise_type,
          sxm.sport_name,
          sxm.sport_relevance_note,
          sxm.priority,
          e.equipment_required,
          e.equipment_substitutes_structured,
          e.physical_proxies,
          e.terrain_required,
          e.contraindicated_parts,
          e.contraindicated_conditions,
          sdb.discipline_id,
          sdb.discipline_name,
          sdb.exercise_db_sport
        FROM layer0.sport_discipline_bridge sdb
        JOIN layer0.sport_exercise_map sxm
          ON sxm.sport_name = sdb.exercise_db_sport
        JOIN layer0.exercises e
          ON e.exercise_id = sxm.exercise_id
        WHERE sdb.discipline_id = ANY(?)
          AND sdb.etl_version = ?
          AND sxm.etl_version = ANY(?)
          AND e.etl_version = ANY(?)
          AND sdb.superseded_at IS NULL
          AND sxm.superseded_at IS NULL
          AND e.superseded_at IS NULL
        """,
        (list(included_discipline_ids), version_0a, versions_0b, versions_0b),
    )
    return [dict(r) for r in cur.fetchall()]


# ─── §5.1 + §6 effective pool ────────────────────────────────────────────────


def _build_effective_pool(
    locale_equipment_pool: list[str],
    cluster_gear_toggle_states: dict[str, bool],
    toggle_defs: dict[str, dict[str, Any]],
) -> set[str]:
    """Per spec §5.1 + §6. `also_satisfies` carries TOGGLE NAMES; §6
    clarifies one-hop expansion (no cascade). Implementation expands
    each enabled toggle's paired_equipment_categories AND the
    paired_equipment_categories of every toggle in its also_satisfies
    list — but does NOT recurse further. Unknown toggle names (not in
    the active 0C row set) are skipped silently; the input dict can
    carry stale keys without failing the call.
    """
    pool: set[str] = set(locale_equipment_pool)
    for toggle_name, enabled in cluster_gear_toggle_states.items():
        if not enabled:
            continue
        td = toggle_defs.get(toggle_name)
        if td is None:
            continue
        pool.update(td["paired_equipment_categories"])
        for also_toggle in td["also_satisfies"]:
            also_def = toggle_defs.get(also_toggle)
            if also_def is None:
                continue
            pool.update(also_def["paired_equipment_categories"])
    return pool


# ─── §5.3/5.4/5.5 tier resolution ────────────────────────────────────────────


def _tier_1(equipment_required: list[str], effective_pool: set[str]) -> bool:
    """§5.3 — flat TEXT[] AND semantics. Empty list is bodyweight =
    always available."""
    return set(equipment_required or []).issubset(effective_pool)


def _tier_2(
    substitutes_structured: list[dict[str, Any]] | None,
    effective_pool: set[str],
) -> ResolutionDetail | None:
    """§5.4 — iterate `equipment_substitutes_structured` in array order
    (Batch C 3-bucket sort preserved). First match wins.

    Per spec rules:
    - `is_improvised: true` always resolves (no equipment check).
    - CNF semantics: `equipment_required: [[a,b],[c]]` means `(a AND b) OR (c)`.
    - Empty `equipment_required` on a non-improvised sub = no extra
      equipment needed; auto-resolves.
    - Returned `substitute_equipment` is the matching AND-group (flat
      list[str] per `ResolutionDetail` typed shape).
    """
    for sub in substitutes_structured or []:
        text = sub.get("substitute_text") or ""
        groups = sub.get("equipment_required") or []
        if sub.get("is_improvised", False):
            # Improvised substitutes assume household items; pool check
            # skipped per spec §5.4 bullet 3. Flatten unique tokens
            # across all CNF groups so downstream sees the kit, not the
            # nested shape.
            flat: list[str] = []
            seen: set[str] = set()
            for group in groups:
                for token in group:
                    if token not in seen:
                        seen.add(token)
                        flat.append(token)
            return ResolutionDetail(
                substitute_text=text,
                substitute_equipment=flat,
                is_improvised=True,
            )
        if not groups:
            # K-parser shape: bodyweight-variant subs ship with empty
            # equipment_required and is_improvised=False. Auto-resolve.
            return ResolutionDetail(
                substitute_text=text,
                substitute_equipment=[],
                is_improvised=False,
            )
        for group in groups:
            if set(group).issubset(effective_pool):
                return ResolutionDetail(
                    substitute_text=text,
                    substitute_equipment=list(group),
                    is_improvised=False,
                )
    return None


def _tier_3(
    physical_proxies: list[dict[str, Any]] | None,
    effective_pool: set[str],
    exercise_index: dict[str, dict[str, Any]],
) -> ResolutionDetail | None:
    """§5.5 — iterate `physical_proxies` in array order; only Tier 1 is
    checked on the proxy (no cascading per spec §5.5 bullet 1). Proxies
    referencing exercises absent from the per-discipline query result
    are skipped silently — proxies can point to any exercise in Layer 0
    but we don't fetch on the fly per spec §5.5 bullet 3 (performance).
    """
    for proxy in physical_proxies or []:
        proxy_id = proxy.get("exercise_id")
        if not proxy_id or proxy_id not in exercise_index:
            continue
        proxy_ex = exercise_index[proxy_id]
        if _tier_1(proxy_ex.get("equipment_required") or [], effective_pool):
            return ResolutionDetail(
                proxy_exercise_id=proxy_id,
                proxy_exercise_name=(
                    proxy.get("exercise_name")
                    or proxy_ex.get("exercise_name")
                    or proxy_id
                ),
            )
    return None


# ─── §5.2 + §5.7 row dedupe + coverage ───────────────────────────────────────


def _dedupe_by_exercise(
    raw_rows: list[dict[str, Any]],
) -> dict[str, dict[str, Any]]:
    """Collapse the JOIN result by exercise_id. Tracks the set of
    discipline_ids the exercise covers + per-discipline sport_relevance_note
    and priority so the ResolvedExercise can carry both dicts.

    Per spec §5.2 last bullet: an exercise may appear under multiple
    disciplines; tier resolution runs once per exercise, not per pair.
    """
    by_id: dict[str, dict[str, Any]] = {}
    for r in raw_rows:
        eid = r["exercise_id"]
        if eid not in by_id:
            by_id[eid] = {
                "exercise_id": eid,
                "exercise_name": r["exercise_name"],
                "exercise_type": r["exercise_type"],
                "equipment_required": list(r.get("equipment_required") or []),
                "equipment_substitutes_structured": (
                    list(r.get("equipment_substitutes_structured") or [])
                ),
                "physical_proxies": list(r.get("physical_proxies") or []),
                "terrain_required": list(r.get("terrain_required") or []),
                "contraindicated_parts": list(
                    r.get("contraindicated_parts") or []
                ),
                "contraindicated_conditions": list(
                    r.get("contraindicated_conditions") or []
                ),
                "discipline_ids": [],
                "sport_relevance_notes": {},
                "priority_per_discipline": {},
            }
        entry = by_id[eid]
        d_id = r["discipline_id"]
        if d_id not in entry["discipline_ids"]:
            entry["discipline_ids"].append(d_id)
            entry["sport_relevance_notes"][d_id] = r.get("sport_relevance_note") or ""
            entry["priority_per_discipline"][d_id] = r.get("priority") or ""
    return by_id


def _resolve_exercise(
    ex: dict[str, Any],
    effective_pool: set[str],
    exercise_index: dict[str, dict[str, Any]],
) -> tuple[int, ResolutionDetail | None]:
    """Apply §5.3 → §5.4 → §5.5 cascade. Returns (tier, detail)."""
    if _tier_1(ex["equipment_required"], effective_pool):
        return 1, None
    detail_2 = _tier_2(ex["equipment_substitutes_structured"], effective_pool)
    if detail_2 is not None:
        return 2, detail_2
    detail_3 = _tier_3(ex["physical_proxies"], effective_pool, exercise_index)
    if detail_3 is not None:
        return 3, detail_3
    return 0, None


def _build_coverage(
    included_discipline_ids: list[str],
    discipline_info: dict[str, dict[str, str]],
    resolved: list[ResolvedExercise],
) -> list[DisciplineCoverage]:
    """§5.7 — per-discipline coverage rollup. Order matches the input
    `included_discipline_ids` so callers get stable output. Disciplines
    missing from `discipline_info` (no sdb row for the active 0A
    version) are skipped per §10 — they're surfaced via the
    `low_coverage` flag path on a synthetic zero-row aggregate.
    """
    out: list[DisciplineCoverage] = []
    for d_id in included_discipline_ids:
        info = discipline_info.get(d_id)
        if info is None:
            continue
        exs = [r for r in resolved if d_id in r.discipline_ids]
        total = len(exs)
        by_tier = Counter(r.tier for r in exs)
        coverage_pct = (
            (by_tier[1] + by_tier[2] + by_tier[3]) / total if total else 0.0
        )
        out.append(
            DisciplineCoverage(
                discipline_id=d_id,
                discipline_name=info["discipline_name"],
                exercise_db_sport=info["exercise_db_sport"],
                total_exercises=total,
                tier_1_count=by_tier[1],
                tier_2_count=by_tier[2],
                tier_3_count=by_tier[3],
                unavailable_count=by_tier[0],
                coverage_pct=coverage_pct,
            )
        )
    return out


# ─── §5.6 accommodation pass-through ─────────────────────────────────────────


def _attach_accommodations(
    resolved: list[ResolvedExercise],
    layer2d_payload: Layer2DPayload | None,
) -> None:
    """§5.6 amendment (2026-05-17) — copy `AccommodationModality` lists
    onto Tier-1/2/3 resolved exercises. 2D's excluded set isn't passed
    here (callers strip excluded exercises before invoking 2C per spec
    §5.6 parenthetical). Tier-0 entries keep their empty default — they
    aren't prescribable so no modality applies.
    """
    if layer2d_payload is None:
        return
    accom_map = {
        er.exercise_id: list(er.accommodations)
        for er in layer2d_payload.accommodated_exercises
    }
    for r in resolved:
        if r.tier > 0:
            r.accommodations = accom_map.get(r.exercise_id, [])


# ─── §8 Coaching flags ───────────────────────────────────────────────────────


def _emit_coaching_flags(
    coverage: list[DisciplineCoverage],
    resolved: list[ResolvedExercise],
    discipline_info: dict[str, dict[str, str]],
    toggle_defs: dict[str, dict[str, Any]],
    cluster_gear_toggle_states: dict[str, bool],
    included_discipline_ids: list[str],
    skill_toggle_defs: dict[str, dict[str, list[str]]],
    skill_toggle_states: dict[str, bool],
) -> list[Layer2CCoachingFlag]:
    flags: list[Layer2CCoachingFlag] = []

    # §8.3 first — emit BEFORE 5.2 query semantically per spec
    # (deterministic regardless of resolution outcome). DP2 = (b): we
    # read `gated_discipline_ids` from the toggle row directly. A
    # toggle whose row carries gated_discipline_ids = ['D-012'] fires
    # this flag for D-012 whenever the toggle is OFF in the cluster
    # state. Toggles absent from `cluster_gear_toggle_states` are
    # treated as OFF (matches the spec semantics — UI carries 12
    # canonical toggles).
    included_set = set(included_discipline_ids)
    for toggle_name, td in toggle_defs.items():
        gated_ids = td["gated_discipline_ids"]
        if not gated_ids:
            continue
        if cluster_gear_toggle_states.get(toggle_name, False):
            continue
        for d_id in gated_ids:
            if d_id not in included_set:
                continue
            d_info = discipline_info.get(d_id)
            d_name = d_info["discipline_name"] if d_info else d_id
            flags.append(
                Layer2CCoachingFlag(
                    flag_type="toggle_off_for_discipline",
                    discipline_id=d_id,
                    discipline_name=d_name,
                    affected_exercise_ids=[],
                    message=(
                        f"You included {d_name} but '{toggle_name}' is off. "
                        "No gear means no equipment-based exercises for this discipline."
                    ),
                    metadata={"toggle_name": toggle_name},
                )
            )

    # D-73 Phase 5.2 Bucket C (l) skill-capability flag — parallel to
    # the §8.3 toggle-OFF-for-discipline gate above but keyed off the
    # athlete's skill capability state rather than gear availability.
    # Same default-OFF semantics: missing keys in `skill_toggle_states`
    # are treated as OFF so the flag fires for every included gated
    # discipline until the athlete enables the matching skill toggle.
    # Affected_exercise_ids stays empty — capability gating is about
    # whether to include the discipline at all in race-relevant work,
    # not about which exercises in the discipline are blocked.
    for toggle_name, td in skill_toggle_defs.items():
        gated_ids = td["gated_discipline_ids"]
        if not gated_ids:
            continue
        if skill_toggle_states.get(toggle_name, False):
            continue
        for d_id in gated_ids:
            if d_id not in included_set:
                continue
            d_info = discipline_info.get(d_id)
            d_name = d_info["discipline_name"] if d_info else d_id
            flags.append(
                Layer2CCoachingFlag(
                    flag_type="requires_skill_capability",
                    discipline_id=d_id,
                    discipline_name=d_name,
                    affected_exercise_ids=[],
                    message=(
                        f"You included {d_name} but the '{toggle_name}' "
                        "skill capability is not enabled. Treat as a "
                        "capability gap until the skill is acquired."
                    ),
                    metadata={"toggle_name": toggle_name},
                )
            )

    # §8.1 low_coverage
    for cov in coverage:
        if cov.coverage_pct >= _LOW_COVERAGE_THRESHOLD:
            continue
        unavailable_ids = [
            r.exercise_id
            for r in resolved
            if cov.discipline_id in r.discipline_ids and r.tier == 0
        ]
        flags.append(
            Layer2CCoachingFlag(
                flag_type="low_coverage",
                discipline_id=cov.discipline_id,
                discipline_name=cov.discipline_name,
                affected_exercise_ids=unavailable_ids,
                message=(
                    f"Only {cov.coverage_pct:.0%} of {cov.discipline_name} "
                    f"exercises are available at this locale."
                ),
                metadata={
                    "coverage_pct": cov.coverage_pct,
                    "tier_1": cov.tier_1_count,
                    "tier_2": cov.tier_2_count,
                    "tier_3": cov.tier_3_count,
                    "unavailable": cov.unavailable_count,
                },
            )
        )

    # §8.2 critical_dropped — one flag per dropped exercise; uses the
    # exercise's primary discipline (first listed) for the
    # discipline_name field per spec §8.2 example.
    for r in resolved:
        if r.tier != 0:
            continue
        is_critical = any(
            (priority or "").strip() == _CRITICAL_PRIORITY
            for priority in r.priority_per_discipline.values()
        )
        if not is_critical:
            continue
        primary_d = r.discipline_ids[0] if r.discipline_ids else None
        d_info = discipline_info.get(primary_d) if primary_d else None
        d_name = d_info["discipline_name"] if d_info else (primary_d or "")
        flags.append(
            Layer2CCoachingFlag(
                flag_type="critical_dropped",
                discipline_id=primary_d,
                discipline_name=d_name,
                affected_exercise_ids=[r.exercise_id],
                message=(
                    f"Critical exercise '{r.exercise_name}' for {d_name} "
                    "cannot be performed at this locale."
                ),
                metadata={
                    "exercise_type": r.exercise_type,
                    "discipline_ids": list(r.discipline_ids),
                },
            )
        )

    return flags


# ─── Public entry point ──────────────────────────────────────────────────────


def q_layer2c_equipment_mapper_payload(
    db,
    locale_id: str,
    locale_equipment_pool: list[str],
    cluster_locale_ids: list[str],
    cluster_gear_toggle_states: dict[str, bool],
    included_discipline_ids: list[str],
    *,
    layer2d_payload: Layer2DPayload | None = None,
    etl_version_set: dict[str, str],
    skill_toggle_states: dict[str, bool] | None = None,
) -> Layer2CPayload:
    """Resolve which Layer 0 exercises are available for a single
    locale, at what tier, with what substitute or proxy detail. Pure
    query node per `Layer2C_Spec.md` §3. Per-locale not per-cluster —
    Layer 4 invokes 2C once per locale in the athlete's cluster.

    `db` is the project's `_PgConn`-shaped connection (sqlite-style `?`
    placeholders auto-translated to psycopg `%s`). `layer2d_payload`
    when supplied drives the §5.6 accommodation pass-through onto
    resolved exercises.

    Validation per §4 raises `Layer2CInputError`.
    """
    _validate_inputs(
        locale_id,
        locale_equipment_pool,
        cluster_locale_ids,
        cluster_gear_toggle_states,
        included_discipline_ids,
        etl_version_set,
    )
    skill_toggle_states = skill_toggle_states or {}

    version_0a = etl_version_set["0A"]
    version_0b = etl_version_set["0B"]
    version_0c = etl_version_set["0C"]
    # 2D precedent for the 0B multi-version note in `Layer2C_Spec.md`
    # §5.2 — single 0B string wrapped into a list to satisfy the `ANY`
    # placeholder. When the etl_version_set evolves to carry a real set,
    # the wrapping is the only code that changes.
    versions_0b = [version_0b]

    toggle_defs = _load_toggle_defs(db, version_0c)
    skill_toggle_defs = _load_skill_capability_toggle_defs(db, version_0c)
    discipline_info = _load_discipline_info(
        db, included_discipline_ids, version_0a
    )
    raw_rows = _load_exercises(
        db, included_discipline_ids, version_0a, versions_0b
    )

    effective_pool = _build_effective_pool(
        locale_equipment_pool, cluster_gear_toggle_states, toggle_defs
    )

    exercise_index = _dedupe_by_exercise(raw_rows)

    resolved: list[ResolvedExercise] = []
    for ex in exercise_index.values():
        tier, detail = _resolve_exercise(ex, effective_pool, exercise_index)
        resolved.append(
            ResolvedExercise(
                exercise_id=ex["exercise_id"],
                exercise_name=ex["exercise_name"],
                exercise_type=ex["exercise_type"],
                discipline_ids=list(ex["discipline_ids"]),
                sport_relevance_notes=dict(ex["sport_relevance_notes"]),
                priority_per_discipline=dict(ex["priority_per_discipline"]),
                tier=tier,
                resolution_detail=detail,
                terrain_required=list(ex["terrain_required"]),
                contraindicated_parts=list(ex["contraindicated_parts"]),
                contraindicated_conditions=list(ex["contraindicated_conditions"]),
                accommodations=[],
            )
        )

    _attach_accommodations(resolved, layer2d_payload)

    coverage = _build_coverage(
        included_discipline_ids, discipline_info, resolved
    )
    coaching_flags = _emit_coaching_flags(
        coverage,
        resolved,
        discipline_info,
        toggle_defs,
        cluster_gear_toggle_states,
        included_discipline_ids,
        skill_toggle_defs,
        skill_toggle_states,
    )

    return Layer2CPayload(
        locale_id=locale_id,
        etl_version_set=dict(etl_version_set),
        effective_pool=sorted(effective_pool),
        discipline_coverage=coverage,
        exercises_resolved=resolved,
        coaching_flags=coaching_flags,
    )
