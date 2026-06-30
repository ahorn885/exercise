"""Layer 2A builder — discipline classifier query node.

Per `Layer2A_Spec.md` §3 (function signature) + §5 (algorithm). Pure query
node: deterministic given inputs, no LLM involvement. Reads three Layer 0
catalog tables (`layer0.sport_discipline_map`, `layer0.phase_load_allocation`,
`layer0.discipline_training_gaps`) via a single CTE+LEFT JOIN query, then
applies code-side conditional resolution + weight computation + rationale
generation.

D-52 sub-decision: these three tables exist only under `layer0.*` (no
`public.*` counterparts in `init_db.py`), so the spec §5.2 SQL targets
`layer0.*` directly — no migration coupling.

#269 (closed 2026-06-30): the PLA `WEEKLY TOTAL TARGET` aggregator rows are
retired at the source — migration
`etl/migrations/layer0/0034_supersede_phase_load_allocation_aggregators.sql`
supersedes them (applied to live prod; nightly `layer0-validate-live` green),
and the `phase_load_allocation_aggregators` check in `validate_layer0` fails
the gate if any ever come back. The former D-05 belt-and-suspenders
`discipline_name NOT LIKE '%WEEKLY TOTAL%'` filter on the PLA join — and the
matching `default_inclusion` aggregator exemption — are therefore removed.

D-17 sub-format naming: `_SUB_FORMAT_SPORTS` whitelist drives the
`top_level_sport` strip — only sports known to use sub-format naming
(Triathlon, Skimo, LDC, OWMS, Canoe/Kayak Marathon) get the parenthetical
stripped for the SDM lookup; the full name is used for the PLA lookup.
AR (no parens) bypasses this entirely.
"""

from __future__ import annotations

import re
from datetime import datetime
from typing import Any

from layer4.context import (
    Layer2ACoachingFlag,
    Layer2ADiscipline,
    Layer2APayload,
    ModalityGroupAllocation,
    PhaseLoadBands,
    RationaleMetadata,
    TrainingGap,
    TrainingGapsSummary,
    UnresolvedFlag,
    WeightResult,
)


# ─── Constants ───────────────────────────────────────────────────────────────


# Code-side whitelist per Layer2A_Spec.md §5.1 + §14 gut-check mitigation.
# Sports here use top-level naming in SDM and sub-format naming in PLA.
_SUB_FORMAT_SPORTS: frozenset[str] = frozenset({
    "Triathlon",
    "Skimo",
    "Long Distance / Endurance Cycling",
    "Canoe / Kayak Marathon",
    "Open Water Marathon Swimming",
})

_REQUIRED_ETL_KEYS: frozenset[str] = frozenset({"0A", "0B", "0C"})

# Conditional-rule constants per spec §5.3. (The R6 collapse retired the
# whitewater-kayak conditional — D-008a/b merged into the ordinary D-010
# Kayaking discipline. The navigation conditional was retired May 2026 when
# D-015 Orienteering folded into D-003 Trekking — Trekking carries no
# navigation/sleep-dep conditional. No discipline-level sleep-dep trigger
# remains; the Layer 2E sleep-dep fueling overlay is event-duration-driven.)

# §8.3 override-divergence flag fires when |ov - default| / default > 0.5
# (relative divergence; matches the spec example where 25 vs default 15
# yields 67% relative divergence and the flag fires).
_DIVERGENCE_RATIO_THRESHOLD: float = 0.5

_VALID_TEAM_FORMATS: frozenset[str] = frozenset({"Solo", "Unified", "Relay"})

# #447 §5 — cross-training fold. A folded home-discipline gets a raw weight of
# this fraction of the SMALLEST included race discipline, guaranteeing every
# cross-training discipline sits strictly below every race discipline (Andy
# 2026-06-21: "fixed low cap below race"). `_normalize_load_weights` then
# rescales the whole set to sum 1.0, preserving the strict ordering.
_CROSS_TRAINING_WEIGHT_FACTOR: float = 0.5


# Pattern matches `"<base> (<suffix>)"` — used to strip sub-format
# parentheticals (e.g. "Triathlon (Standard / Olympic)" → "Triathlon")
# only when the base is in `_SUB_FORMAT_SPORTS`.
_SUB_FORMAT_PATTERN = re.compile(r"^(.+?)\s*\(.+\)\s*$")


# ─── Errors ──────────────────────────────────────────────────────────────────


class Layer2AInputError(ValueError):
    """Raised by `q_layer2a_discipline_classifier_payload` on §4 validation
    failure. Plan-gen catches and surfaces a user-facing error."""


# ─── Helpers ─────────────────────────────────────────────────────────────────


def _strip_sub_format(framework_sport: str) -> str:
    """Return the SDM-side top-level sport name.

    Per spec §5.1: sub-format-using sports (Triathlon, Skimo, etc.) carry
    the parenthetical in PLA but the top-level name in SDM. Strip the
    parenthetical only when the base name is in the whitelist — this
    avoids false-positive strips on sports that legitimately contain
    parentheses for other reasons (none known today, but the gut-check
    risk is real per spec §14).

    AR ("Adventure Racing", no parens) returns unchanged.
    """
    match = _SUB_FORMAT_PATTERN.match(framework_sport)
    if not match:
        return framework_sport
    base = match.group(1).strip()
    if base in _SUB_FORMAT_SPORTS:
        return base
    return framework_sport


def _load_disciplines(
    db,
    top_level_sport: str,
    framework_sport: str,
) -> list[dict[str, Any]]:
    """Issue the spec §5.2 query. Returns one row per included discipline
    in SDM for the sport, with PLA + DTG + discipline-library rows joined
    LEFT (may be NULL).

    Reads the active row set (`superseded_at IS NULL`); the active version is
    resolved per-table at serving time, so no `etl_version` predicate (slice
    3b). Two positional params: top_level_sport (SDM), framework_sport (PLA).
    """
    cur = db.execute(
        """
        WITH sport_disciplines AS (
            SELECT
                sdm.discipline_id,
                sdm.discipline_name,
                sdm.applicability,
                sdm.role,
                sdm.race_time_pct_low,
                sdm.race_time_pct_high,
                sdm.sport_specific_context,
                sdm.phase_load_text
            FROM layer0.sport_discipline_map sdm
            WHERE sdm.sport_name = ?
              AND sdm.applicability = 'INCLUDED'
              AND sdm.superseded_at IS NULL
        )
        SELECT
            sd.discipline_id,
            sd.discipline_name,
            sd.applicability,
            sd.role,
            sd.race_time_pct_low,
            sd.race_time_pct_high,
            sd.sport_specific_context,
            sd.phase_load_text,
            pla.base_pct_low,
            pla.base_pct_high,
            pla.build_pct_low,
            pla.build_pct_high,
            pla.peak_pct_low,
            pla.peak_pct_high,
            pla.taper_pct_low,
            pla.taper_pct_high,
            pla.role AS pla_role,
            pla.notes_conditions,
            pla.default_inclusion,
            dtg.gap_type,
            dtg.notes AS gap_notes,
            dtg.multi_substitute_candidate,
            dl.endurance_profile,
            dl.primary_movement
        FROM sport_disciplines sd
        LEFT JOIN layer0.phase_load_allocation pla
            ON pla.sport_name = ?
           AND pla.discipline_id = sd.discipline_id
           AND pla.superseded_at IS NULL
        LEFT JOIN layer0.discipline_training_gaps dtg
            ON dtg.discipline_id = sd.discipline_id
           AND dtg.superseded_at IS NULL
        LEFT JOIN layer0.disciplines dl
            ON dl.discipline_id = sd.discipline_id
           AND dl.superseded_at IS NULL
        """,
        (top_level_sport, framework_sport),
    )
    return [dict(r) for r in cur.fetchall()]


def _load_weekly_total_hours(
    db, framework_sport: str
) -> dict[str, tuple[float, float]]:
    """Per-phase whole-sport weekly HOUR totals from the spreadsheet's
    `WEEKLY TOTAL TARGET` row (extracted to `layer0.phase_load_weekly_totals`).

    Keyed "Base"/"Build"/"Peak"/"Taper" → (low_hours, high_hours). The
    per-discipline `phase_load` percentages are shares of this total. Phases
    with NULL bounds are omitted (consumer falls back to open-ended bands).
    Keyed on `framework_sport` (the sub-format) like `phase_load_allocation`.
    """
    cur = db.execute(
        """
        SELECT phase, weekly_low_hours, weekly_high_hours
          FROM layer0.phase_load_weekly_totals
         WHERE sport_name = ?
           AND superseded_at IS NULL
        """,
        (framework_sport,),
    )
    out: dict[str, tuple[float, float]] = {}
    for r in cur.fetchall():
        row = dict(r)
        low, high = row.get("weekly_low_hours"), row.get("weekly_high_hours")
        if low is not None and high is not None:
            out[row["phase"]] = (float(low), float(high))
    return out


def _role_modifier(role: str) -> str:
    """Map SDM role (possibly with `(*Conditional)` suffix) to the
    rationale-template modifier per spec §5.5.
    """
    base = role.split("(")[0].strip().lower()
    if base.startswith("primary"):
        return "core"
    if base.startswith("secondary"):
        return "supporting"
    if base.startswith("minor"):
        return "minor"
    if base.startswith("technical"):
        return "technical"
    return base or "supporting"


_INCLUSION_VALUES = {"included", "excluded", "prompt_required"}


def _curator_default_inclusion(row: dict[str, Any]) -> str:
    """The curator's authored base inclusion for a discipline, read from the
    authoritative `layer0.phase_load_allocation.default_inclusion` column (#509).

    Replaces the retired notes-text heuristic, which derived only from
    `notes_conditions` and so could express `included`/`prompt_required` but
    never `excluded` — letting curator-excluded disciplines (e.g. AR
    Canoeing/Snowshoeing/Mountaineering) leak through as `prompt_required`.

    NULL / unpopulated (e.g. a discipline with no PLA row joined) → `included`,
    matching the historical non-conditional default. The Slice 1
    `validate_layer0` gate enforces a populated closed-enum value on every
    real PLA row, so this fallback only catches no-PLA-row disciplines."""
    val = (row.get("default_inclusion") or "").strip().lower()
    if val in _INCLUSION_VALUES:
        return val
    return "included"


def _build_phase_load(row: dict[str, Any]) -> PhaseLoadBands | None:
    """Build `PhaseLoadBands` from PLA columns; return None if no PLA row
    joined (all band columns NULL).
    """
    band_keys = (
        "base_pct_low", "base_pct_high",
        "build_pct_low", "build_pct_high",
        "peak_pct_low", "peak_pct_high",
        "taper_pct_low", "taper_pct_high",
    )
    if (
        all(row.get(k) is None for k in band_keys)
        and row.get("notes_conditions") is None
        and row.get("default_inclusion") is None
    ):
        return None
    return PhaseLoadBands(
        base_low=row.get("base_pct_low"),
        base_high=row.get("base_pct_high"),
        build_low=row.get("build_pct_low"),
        build_high=row.get("build_pct_high"),
        peak_low=row.get("peak_pct_low"),
        peak_high=row.get("peak_pct_high"),
        taper_low=row.get("taper_pct_low"),
        taper_high=row.get("taper_pct_high"),
        notes_conditions=row.get("notes_conditions"),
        default_inclusion=_curator_default_inclusion(row),
    )


def _build_training_gap(row: dict[str, Any]) -> TrainingGap | None:
    """Build `TrainingGap` from DTG columns; return None if no DTG row
    joined (`gap_type` NULL).
    """
    gap_type = row.get("gap_type")
    if gap_type is None:
        return None
    return TrainingGap(
        gap_type=gap_type,
        notes=row.get("gap_notes") or "",
        multi_substitute_candidate=bool(row.get("multi_substitute_candidate")),
    )


def _resolve_inclusion(
    row: dict[str, Any],
    race_overrides: dict[str, float] | None,
    athlete_overrides: dict[str, dict] | None,
) -> str:
    """Resolve a discipline's inclusion via the #509 precedence chain
    `race > athlete > curator-default`.

    1. **Race demand** — the race terrain mix names this discipline
       (`race_discipline_overrides`, derived from per-row `discipline_id` by
       the X3 orchestrator helper) → `included`. Race wins over athlete.
    2. **Athlete weighting** — a non-empty `athlete_discipline_overrides` is the
       athlete's complete, all-or-nothing (sum-to-100, X2) discipline list:
       a listed discipline → `included`, an unlisted one → `excluded`. An empty
       set is no signal (the athlete deferred) → fall through to the curator.
    3. **Curator default** — the authoritative
       `phase_load_allocation.default_inclusion` column
       (`included` / `excluded` / `prompt_required`; NULL → `included`).

    Race provenance rides on `load_weight.source == "race_override"`."""
    discipline_id = row["discipline_id"]

    # 1. Race demand wins (X3 terrain-derived mix).
    if race_overrides and discipline_id in race_overrides:
        return "included"

    # 2. Athlete weighting is the complete membership list when set (#509 Option A).
    if athlete_overrides:
        return "included" if discipline_id in athlete_overrides else "excluded"

    # 3. Curator default_inclusion column (authoritative base).
    return _curator_default_inclusion(row)


def _compute_load_weight(
    row: dict[str, Any],
    overrides: dict[str, dict] | None,
) -> WeightResult:
    """Per spec §5.4: midpoint of `race_time_pct_low`/`high` is the
    system default; athlete override wins when present.
    """
    low = row.get("race_time_pct_low")
    high = row.get("race_time_pct_high")
    default_weight: float | None = None
    if low is not None and high is not None:
        default_weight = float((float(low) + float(high)) / 2.0)
    elif low is not None:
        default_weight = float(low)

    discipline_id = row["discipline_id"]
    ov = (overrides or {}).get(discipline_id) or {}
    if "weight" in ov:
        return WeightResult(
            value=float(ov["weight"]),
            source="athlete_override",
            system_default=default_weight,
        )
    return WeightResult(
        value=default_weight,
        source="system_default",
        system_default=default_weight,
    )


def _load_modality_groups(
    db,
) -> dict[str, list[str]]:
    """X1b.2 — load `layer0.discipline_modality_membership` (active rows).

    Returns `{discipline_id: [group_id, ...]}`. Empty dict (no rows) is
    treated by the caller as the pre-v1.5.0 state — every discipline is
    its own singleton, behavior identical to pre-X1b.
    """
    cur = db.execute(
        "SELECT discipline_id, group_id "
        "FROM layer0.discipline_modality_membership "
        "WHERE superseded_at IS NULL"
    )
    out: dict[str, list[str]] = {}
    for row in cur.fetchall():
        did = row["discipline_id"]
        gid = row["group_id"]
        out.setdefault(did, []).append(gid)
    return out


def _apply_modality_group_pooling(
    disciplines: list["Layer2ADiscipline"],
    membership: dict[str, list[str]],
    race_overrides: dict[str, float] | None,
    athlete_overrides: dict[str, dict] | None,
) -> list[ModalityGroupAllocation]:
    """X1b.2 — Per `Modality_Group_Spec_v1.md` §5.1.

    Pools per-discipline load_weight by modality group, then redistributes
    per the precedence rule (race > athlete > bridge) within the pool.
    Singleton groups (one included member) are no-ops; pooling only
    matters when 2+ included members share a group.

    Mutates `disciplines[i].load_weight.value` in place. Returns the
    per-group diagnostic for emission in the payload.

    Sums and redistributes use the RAW (pre-normalize) load_weight value.
    The final `_normalize_load_weights` pass downstream rescales the set
    to sum to 1.0 — unchanged behavior. Race/athlete-tagged members win
    per-member; untagged members in a group with any race signal fall
    back to the athlete signal, then to bridge midpoints.

    REDIRECT semantics (§5.3): if a race tag names a member that's
    excluded from `disciplines` (i.e. athlete doesn't own that craft),
    the tag is applied to the FIRST included member of the same group
    instead, and a `craft_substitution_via_group` flag is recorded on
    the allocation. The simpler in-set case (race tags an included
    member directly) is handled by the per-member-wins path.
    """
    if not membership:
        # Pre-v1.5.0 substrate: skip pooling, behavior identical to pre-X1b.
        return []

    # Pool only over INCLUDED members — #509's race/athlete/curator inclusion
    # resolution can now exclude many disciplines (Option A: a non-empty athlete
    # weighting is the complete list), and an excluded discipline must not
    # contribute its bridge midpoint to a group pool.
    included_ids = {d.discipline_id for d in disciplines if d.inclusion == "included"}
    by_id = {d.discipline_id: d for d in disciplines}

    # Reverse map: group_id → included members
    group_to_members: dict[str, list[str]] = {}
    for did in included_ids:
        for gid in membership.get(did, []):
            group_to_members.setdefault(gid, []).append(did)

    # REDIRECT: race tags pointing at non-included disciplines need to be
    # re-attributed to an included same-group member.
    effective_race: dict[str, float] = dict(race_overrides or {})
    redirect_flags: dict[str, list[str]] = {}  # group_id → flag list
    for tagged_did in list(effective_race.keys()):
        if tagged_did in included_ids:
            continue
        # tagged but not in included set — redirect within shared groups
        for gid in membership.get(tagged_did, []):
            members = group_to_members.get(gid, [])
            if not members:
                continue
            # Redirect to the first included member of this group
            target = members[0]
            pct = effective_race.pop(tagged_did)
            effective_race[target] = effective_race.get(target, 0.0) + pct
            redirect_flags.setdefault(gid, []).append(
                f"craft_substitution_via_group: race tag {tagged_did} → {target}"
            )
            break

    diagnostics: list[ModalityGroupAllocation] = []

    for gid, members in sorted(group_to_members.items()):
        if len(members) < 2:
            # Singleton — no pooling to do. Race/athlete-on-the-one-member
            # is handled by per-member override below for ALL groups.
            continue

        # Per-member original midpoint base
        bases = {
            did: float(by_id[did].load_weight.value or 0.0)
            for did in members
        }

        # Pool sums
        pool_race = sum(effective_race.get(did, 0.0) for did in members)
        pool_athlete = sum(
            float((athlete_overrides or {}).get(did, {}).get("weight", 0.0))
            for did in members
        )
        pool_base = sum(bases.values())

        # Per-member final assignment per precedence rule
        finals: dict[str, float] = {}
        for did in members:
            if did in effective_race:
                finals[did] = effective_race[did]
            elif did in (athlete_overrides or {}) and "weight" in athlete_overrides[did]:
                finals[did] = float(athlete_overrides[did]["weight"])
            else:
                # Untagged: keep its bridge midpoint share
                finals[did] = bases[did]

        # Apply finals to disciplines
        for did, weight in finals.items():
            d = by_id[did]
            d.load_weight = WeightResult(
                value=float(weight),
                source=(
                    "race_override" if did in effective_race
                    else (
                        "athlete_override"
                        if did in (athlete_overrides or {})
                            and "weight" in athlete_overrides[did]
                        else d.load_weight.source
                    )
                ),
                system_default=d.load_weight.system_default,
            )

        diagnostics.append(
            ModalityGroupAllocation(
                group_id=gid,
                members=sorted(members),
                pool_race=pool_race,
                pool_athlete=pool_athlete,
                pool_base=pool_base,
                per_member_final=finals,
                flags=redirect_flags.get(gid, []),
            )
        )

    # Handle race tags for singleton-group disciplines too (precedence still applies
    # outside of pooling — race overrides win even with no group pooling).
    for did, pct in effective_race.items():
        if did not in by_id:
            continue
        if any(did in alloc.members for alloc in diagnostics):
            continue  # already handled in a multi-member pool
        d = by_id[did]
        d.load_weight = WeightResult(
            value=float(pct),
            source="race_override",
            system_default=d.load_weight.system_default,
        )

    return diagnostics


def _phase_load_midpoints(pl: "PhaseLoadBands") -> list[float]:
    """The per-phase midpoints of a `PhaseLoadBands` (base/build/peak/taper).

    These are the percentages the volume engine (`validator.
    phase_volume_bands_hours` → `session_grid`) renormalizes into weekly HOURS —
    so they, not `load_weight`, govern how much volume a discipline actually
    gets. Used by the cross-training fold to cap the folded volume below the
    smallest race discipline.
    """
    pairs = (
        ("base_low", "base_high"),
        ("build_low", "build_high"),
        ("peak_low", "peak_high"),
        ("taper_low", "taper_high"),
    )
    mids: list[float] = []
    for lo_attr, hi_attr in pairs:
        lo = getattr(pl, lo_attr)
        hi = getattr(pl, hi_attr)
        if lo is not None and hi is not None:
            mids.append((float(lo) + float(hi)) / 2.0)
        elif lo is not None:
            mids.append(float(lo))
    return mids


def _fold_cross_training_disciplines(
    db,
    disciplines: list["Layer2ADiscipline"],
    cross_training_sport: str,
) -> None:
    """#447 §5 — fold the athlete's home-discipline sport in as cross-training.

    Called only when the target race's sport differs from the profile primary
    sport (an off-discipline race, e.g. a trail runner doing an AR). Loads the
    home sport's disciplines, **de-dupes** against the race set (no double-count
    for a discipline the race already covers — Andy 2026-06-21), and appends the
    remainder as `included` cross-training disciplines, capped on **both**
    weighting axes strictly below the smallest included race discipline so race
    specificity always dominates (Andy 2026-06-21):

    - `load_weight` (priority axis) → governs ceiling-shed order + absorber
      reallocation. Capped at `factor × smallest race load_weight`.
    - `phase_load` (volume axis) → the percentages `validator.
      phase_volume_bands_hours`/`session_grid` (#338/#433) renormalize into
      weekly HOURS, i.e. what actually drives how much you train. Capped at
      `factor × smallest race phase-load midpoint`, flat across all phases, so
      the folded volume sits below every race discipline in every phase and
      typically trips the maintenance-cadence rule (a sub-0.5-session/week
      discipline runs intermittently, not weekly). The home sport's own
      phase-load shape is deliberately discarded — its percentages are sized to
      a home-sport plan, not a cross-training dose.

    Runs AFTER `_apply_modality_group_pooling` (so the cap reads the final race
    weights and cross-training never perturbs the race modality pools) and
    BEFORE `_normalize_load_weights` (which rescales the whole set to sum 1.0).
    The folded disciplines therefore do not participate in race coaching-flag /
    training-gap / HITL computation, which run on the race set upstream — by
    design, those stay race-specific.
    """
    race_weights = [
        d.load_weight.value
        for d in disciplines
        if d.inclusion == "included"
        and d.load_weight.value is not None
        and d.load_weight.value > 0
    ]
    if not race_weights:
        # Degenerate: no weighted race disciplines to cap against. Skip rather
        # than inject an unbounded cross-training share.
        print(
            "_fold_cross_training_disciplines: no weighted race disciplines; "
            f"skipping fold for cross_training_sport={cross_training_sport!r}"
        )
        return

    cap = min(race_weights) * _CROSS_TRAINING_WEIGHT_FACTOR

    # Volume-axis cap: smallest per-phase phase-load midpoint across the race
    # set. None when no race discipline carries phase_load (the volume engine
    # then no-ops for everyone, so the folded value is moot → leave phase_load
    # off rather than fabricate a band).
    race_phase_mids = [
        m
        for d in disciplines
        if d.inclusion == "included" and d.phase_load is not None
        for m in _phase_load_midpoints(d.phase_load)
        if m > 0
    ]
    phase_cap = (
        min(race_phase_mids) * _CROSS_TRAINING_WEIGHT_FACTOR
        if race_phase_mids
        else None
    )
    folded_phase_load = (
        PhaseLoadBands(
            base_low=phase_cap, base_high=phase_cap,
            build_low=phase_cap, build_high=phase_cap,
            peak_low=phase_cap, peak_high=phase_cap,
            taper_low=phase_cap, taper_high=phase_cap,
            notes_conditions=None,
            default_inclusion="included",
        )
        if phase_cap is not None
        else None
    )

    existing_ids = {d.discipline_id for d in disciplines}
    xt_rows = _load_disciplines(
        db, _strip_sub_format(cross_training_sport), cross_training_sport
    )
    folded = 0
    for row in xt_rows:
        did = row["discipline_id"]
        if did in existing_ids:
            continue  # de-dupe — the race set already covers this discipline
        existing_ids.add(did)
        disciplines.append(
            Layer2ADiscipline(
                discipline_id=did,
                discipline_name=row["discipline_name"],
                endurance_profile=row.get("endurance_profile"),
                primary_movement=row.get("primary_movement"),
                inclusion="included",
                role="Cross-training",
                load_weight=WeightResult(
                    value=cap, source="system_default", system_default=cap
                ),
                phase_load=folded_phase_load,
                rationale=(
                    f"Cross-training from your primary sport "
                    f"({cross_training_sport}) — folded in at a minority weight to "
                    f"maintain home-discipline fitness while the plan targets the "
                    f"race sport. Race specificity stays on the race disciplines."
                ),
            )
        )
        folded += 1
    # Rule #15 — log the fold decision (sport, both caps, injected vs deduped).
    phase_cap_str = f"{phase_cap:.4f}" if phase_cap is not None else "none"
    print(
        f"_fold_cross_training_disciplines: cross_training_sport="
        f"{cross_training_sport!r} weight_cap={cap:.4f} phase_cap={phase_cap_str} "
        f"folded={folded} deduped={len(xt_rows) - folded}"
    )


def _normalize_load_weights(disciplines: list["Layer2ADiscipline"]) -> None:
    """Rescale `load_weight` in place so the included disciplines' `value`s
    sum to ≈1.0 (Layer4_Spec §4.2). `value` is the midpoint of the 0–100
    `race_time_pct` band (or an athlete override on the same scale); dividing
    every discipline's `value` and `system_default` by the included-set total
    yields a normalized distribution while preserving each discipline's
    value/system_default ratio. No-op when the included total is non-positive
    (degenerate data — e.g. no included disciplines, or all bands unset)."""
    total = sum(
        d.load_weight.value
        for d in disciplines
        if d.inclusion == "included" and d.load_weight.value is not None
    )
    if total <= 0:
        return
    for d in disciplines:
        lw = d.load_weight
        if lw.value is not None:
            lw.value = lw.value / total
        if lw.system_default is not None:
            lw.system_default = lw.system_default / total


# ─── Rationale templates (athlete-facing, per spec §5.5 + Open Item 2A-1) ────


def _render_rationale(
    row: dict[str, Any],
    framework_sport: str,
    inclusion: str,
    race_duration_hours: float | None,
) -> str:
    """Render the athlete-facing rationale string. Composed from a small
    template library keyed on role + inclusion.
    `sport_specific_context` from SDM is appended verbatim when non-NULL.

    Voice per CLAUDE.md: direct, evidence-grounded, no platitudes or hype.
    """
    name = row["discipline_name"]
    role = row["role"]
    modifier = _role_modifier(role)
    low = row.get("race_time_pct_low")
    high = row.get("race_time_pct_high")
    has_pct = low is not None and high is not None

    # Excluded → athlete preference (race-rule auto-resolution retired).
    if inclusion == "excluded":
        text = f"{name} is not included for this event based on athlete preference."
        return _append_sport_context(text, row)

    # Prompt-required → ask the athlete.
    if inclusion == "prompt_required":
        text = (
            f"{name} appears in {framework_sport} only under specific conditions. "
            f"Confirm whether it applies to this event before the plan includes it."
        )
        return _append_sport_context(text, row)

    # Included — main template by role.
    if has_pct:
        pct_clause = f"Race-time share runs {_fmt_pct(low)}–{_fmt_pct(high)}%. "
    else:
        pct_clause = ""

    if modifier == "core":
        body = (
            f"{pct_clause}It carries the bulk of the cardiovascular load "
            f"and drives base-phase volume."
        )
    elif modifier == "supporting":
        body = (
            f"{pct_clause}Volume is sized to maintain the specific stimulus "
            f"without crowding primary work."
        )
    elif modifier == "minor":
        body = (
            f"{pct_clause}Sessions stay infrequent and skill-focused — "
            f"not a base-volume driver."
        )
    elif modifier == "technical":
        body = (
            f"{pct_clause}Practice cadence is skill-driven; load comes from "
            f"the disciplines it supports."
        )
    else:
        body = pct_clause.strip() or "Role-specific stimulus retained."

    text = f"{name} is a {modifier} discipline of {framework_sport}. {body}".strip()

    return _append_sport_context(text, row)


def _append_sport_context(text: str, row: dict[str, Any]) -> str:
    """Append `sport_specific_context` verbatim when non-NULL. Spec §5.5
    requirement; keeps SDM-curated context visible to the athlete."""
    ctx = row.get("sport_specific_context")
    if ctx and ctx.strip():
        return f"{text} {ctx.strip()}"
    return text


def _fmt_pct(value: Any) -> str:
    """Format a numeric pct as a trimmed int/float string for rationale text."""
    f = float(value)
    if f == int(f):
        return str(int(f))
    return f"{f:.1f}".rstrip("0").rstrip(".")


def _fmt_hours(value: float) -> str:
    """Format a numeric hour value (trim trailing zero on integers)."""
    if value == int(value):
        return str(int(value))
    return f"{value:.1f}".rstrip("0").rstrip(".")


# ─── Coaching flags + summary ────────────────────────────────────────────────


def _emit_coaching_flags(
    disciplines: list[Layer2ADiscipline],
    raw_rows: list[dict[str, Any]],
    race_duration_hours: float | None,
) -> list[Layer2ACoachingFlag]:
    """Emit the spec §8 flag types (training_gap + weight_override_divergence)."""
    flags: list[Layer2ACoachingFlag] = []
    rows_by_id = {r["discipline_id"]: r for r in raw_rows}

    for d in disciplines:
        # §8.1 — training gap surfaced on any discipline with a DTG entry
        # (regardless of inclusion — the gap is informational).
        gap = _build_training_gap(rows_by_id[d.discipline_id])
        if gap is not None:
            flags.append(
                Layer2ACoachingFlag(
                    flag_type="training_gap",
                    discipline_id=d.discipline_id,
                    message=(
                        f"{d.discipline_name} has a known training gap: "
                        f"{gap.notes}"
                    ),
                    metadata={
                        "gap_type": gap.gap_type,
                        "multi_substitute_candidate": gap.multi_substitute_candidate,
                    },
                )
            )

        # §8.3 — override divergence (relative > 50%)
        if (
            d.load_weight.source == "athlete_override"
            and d.load_weight.value is not None
            and d.load_weight.system_default is not None
            and d.load_weight.system_default > 0
        ):
            ov = float(d.load_weight.value)
            default = float(d.load_weight.system_default)
            divergence = abs(ov - default)
            divergence_relative = divergence / default
            if divergence_relative > _DIVERGENCE_RATIO_THRESHOLD:
                direction = "higher" if ov > default else "lower"
                flags.append(
                    Layer2ACoachingFlag(
                        flag_type="weight_override_divergence",
                        discipline_id=d.discipline_id,
                        message=(
                            f"Your {d.discipline_name} weight of "
                            f"{_fmt_pct(ov)}% is significantly {direction} than "
                            f"system default of {_fmt_pct(default)}%."
                        ),
                        metadata={
                            "override_pct": ov,
                            "default_pct": default,
                            "divergence": divergence,
                            "divergence_relative": divergence_relative,
                        },
                    )
                )

    return flags


def _build_training_gaps_summary(
    disciplines: list[Layer2ADiscipline],
    raw_rows: list[dict[str, Any]],
) -> TrainingGapsSummary:
    """Roll up DTG entries across included disciplines per spec §7."""
    rows_by_id = {r["discipline_id"]: r for r in raw_rows}
    flagged = sum(
        1
        for d in disciplines
        if d.inclusion == "included"
        and _build_training_gap(rows_by_id[d.discipline_id]) is not None
    )
    return TrainingGapsSummary(flagged_count=flagged)


# ─── Public entry point ──────────────────────────────────────────────────────


def q_layer2a_discipline_classifier_payload(
    db,
    framework_sport: str,
    *,
    athlete_discipline_overrides: dict[str, dict] | None = None,
    race_discipline_overrides: dict[str, float] | None = None,
    estimated_race_duration_hours: float | None = None,
    team_format: str | None = None,
    discipline_id_filter: list[str] | None = None,
    cross_training_sport: str | None = None,
    etl_version_set: dict[str, str],
) -> Layer2APayload:
    """Resolve canonical disciplines for a framework sport. Spec §3.

    Pure query node. One SELECT against `layer0.{sport_discipline_map,
    phase_load_allocation,discipline_training_gaps}` joined by spec §5.2,
    plus a second SELECT against `layer0.phase_load_weekly_totals` for the
    per-phase whole-sport weekly HOUR totals (the percentage `phase_load`
    bands are shares of these). No JOIN to per-athlete tables —
    `athlete_discipline_overrides` is supplied by the caller (Phase 5
    orchestrator unpacks it from `Layer1Payload.training_history.discipline_weighting`).

    Validation per §4 raises `Layer2AInputError`. Empty sport (no SDM
    rows) returns an empty discipline list with `hitl_required=True` and
    a `no_disciplines_for_sport` unresolved flag per §10.
    """
    # §4 input validation
    if not framework_sport or not isinstance(framework_sport, str):
        raise Layer2AInputError("framework_sport must be a non-empty string")
    if not isinstance(etl_version_set, dict) or not _REQUIRED_ETL_KEYS.issubset(
        etl_version_set.keys()
    ):
        raise Layer2AInputError(
            f"etl_version_set must contain keys {sorted(_REQUIRED_ETL_KEYS)}; "
            f"got {sorted(etl_version_set.keys()) if isinstance(etl_version_set, dict) else etl_version_set!r}"
        )
    if estimated_race_duration_hours is not None and estimated_race_duration_hours <= 0:
        raise Layer2AInputError(
            f"estimated_race_duration_hours must be positive (got {estimated_race_duration_hours})"
        )
    if team_format is not None and team_format not in _VALID_TEAM_FORMATS:
        raise Layer2AInputError(
            f"team_format must be one of {sorted(_VALID_TEAM_FORMATS)} (got {team_format!r})"
        )

    top_level_sport = _strip_sub_format(framework_sport)

    raw_rows = _load_disciplines(db, top_level_sport, framework_sport)

    # D-73 Phase 5.2 Bucket E.(b)-B2 (2026-05-24) — when a race-level
    # `discipline_id_filter` is supplied, prune the bridge-derived rows to
    # only the explicit IDs. Preserves the bridge SELECT (rationale +
    # phase_load + training_gap stay intact for surviving rows) but narrows
    # the output set. None = use full bridge defaults (pre-B2 behavior).
    # Empty list = explicit "no disciplines" (matches None semantically —
    # the route layer treats an empty form selection as None, so this path
    # is only reached from direct caller use, e.g. tests).
    if discipline_id_filter is not None:
        allowed = set(discipline_id_filter)
        raw_rows = [r for r in raw_rows if r["discipline_id"] in allowed]

    disciplines: list[Layer2ADiscipline] = []
    for row in raw_rows:
        inclusion = _resolve_inclusion(
            row,
            race_discipline_overrides,
            athlete_discipline_overrides,
        )
        load_weight = _compute_load_weight(row, athlete_discipline_overrides)
        rationale = _render_rationale(
            row,
            framework_sport,
            inclusion,
            estimated_race_duration_hours,
        )
        disciplines.append(
            Layer2ADiscipline(
                discipline_id=row["discipline_id"],
                discipline_name=row["discipline_name"],
                endurance_profile=row.get("endurance_profile"),
                primary_movement=row.get("primary_movement"),
                inclusion=inclusion,
                role=row["role"],
                load_weight=load_weight,
                phase_load=_build_phase_load(row),
                rationale=rationale,
            )
        )

    # Unresolved-sport edge case per §10
    unresolved_flags: list[UnresolvedFlag] = []
    if not disciplines:
        unresolved_flags.append(
            UnresolvedFlag(
                raw_input=framework_sport,
                suggested_match=None,
                severity="error",
            )
        )

    # D-17 guard (#254): a *bare* sub-format parent (e.g. "Triathlon", exactly
    # the whitelist key) reaching 2A means onboarding never resolved a
    # sub-format. SDM is top-level-keyed so disciplines DO load, but PLA +
    # weekly-totals are sub-format-keyed ("Triathlon (Standard / Olympic)" etc.)
    # — every phase-load band joins NULL and the plan would silently get zero
    # training volume. A correctly-resolved input carries the parenthetical and
    # is NOT in `_SUB_FORMAT_SPORTS`, so this fires only on the unresolved bug
    # case. Surface it loudly (unresolved flag + HITL + Rule-#15 log) instead of
    # emitting a no-volume plan. The capture-side fix
    # (`Onboarding_SportSubFormat_D17_254_Design_v1.md`) prevents this path;
    # the guard catches legacy rows + any capture regression.
    sub_format_unresolved = (
        framework_sport in _SUB_FORMAT_SPORTS
        and bool(raw_rows)
        and all(r.get("base_pct_low") is None for r in raw_rows)
    )
    if sub_format_unresolved:
        print(
            f"q_layer2a: framework_sport={framework_sport!r} is a sub-format "
            f"parent with zero phase_load rows — onboarding did not resolve a "
            f"sub-format (D-17/#254). Flagging unresolved + forcing HITL."
        )
        unresolved_flags.append(
            UnresolvedFlag(
                raw_input=framework_sport,
                suggested_match=None,
                severity="error",
            )
        )

    # HITL gate per §5.6
    hitl_required = (
        not disciplines
        or sub_format_unresolved
        or any(d.inclusion == "prompt_required" for d in disciplines)
    )

    coaching_flags = _emit_coaching_flags(
        disciplines,
        raw_rows,
        estimated_race_duration_hours,
    )
    training_gaps_summary = _build_training_gaps_summary(disciplines, raw_rows)

    # X1b.2 — Modality-group pool/redistribute per Modality_Group_Spec_v1 §5.1.
    # Loads layer0.discipline_modality_membership for the current 0A version
    # and mutates per-discipline load_weight values per precedence (race >
    # athlete > bridge). REDIRECT semantics apply when race tags a craft the
    # athlete doesn't own — weight redirects to a same-group included member.
    # Returns the per-group diagnostic for the payload. Empty membership table
    # (pre-v1.5.0) is a no-op — every discipline stays its own singleton.
    membership = _load_modality_groups(db)
    modality_group_allocations = _apply_modality_group_pooling(
        disciplines,
        membership,
        race_discipline_overrides,
        athlete_discipline_overrides,
    )

    # #447 §5 — fold the athlete's home sport in as cross-training when the
    # caller flags it (race sport != profile primary sport). Injects after
    # pooling so the low cap reads the final race weights and cross-training
    # never perturbs the race modality pools; before normalize so the folded
    # disciplines share in the sum-to-1.0 rescale.
    if cross_training_sport:
        _fold_cross_training_disciplines(db, disciplines, cross_training_sport)

    # Normalize load_weight onto a 0–1 distribution over the included set so
    # the Layer 4 plan_create precondition holds (Layer4_Spec §4.2:
    # `discipline_weights` sum to ≈1.0). The raw value is the midpoint of the
    # 0–100 `race_time_pct` band; dividing every discipline's `value` AND
    # `system_default` by the included-set total makes the included weights
    # sum to 1.0 while preserving each discipline's value/system_default ratio.
    # Run AFTER `_emit_coaching_flags` so the athlete-override divergence flag
    # still reads the raw 0–100 override percent (its `override_pct` metadata).
    _normalize_load_weights(disciplines)

    return Layer2APayload(
        framework_sport=framework_sport,
        etl_version_set=dict(etl_version_set),
        disciplines=disciplines,
        weekly_total_hours_by_phase=_load_weekly_total_hours(
            db, framework_sport
        ),
        training_gaps_summary=training_gaps_summary,
        hitl_required=hitl_required,
        unresolved_flags=unresolved_flags,
        coaching_flags=coaching_flags,
        modality_group_allocations=modality_group_allocations,
        rationale_metadata=RationaleMetadata(
            # Day-anchored: `generated_at` is hashed into `layer2a_hash`, which
            # keys plan_create / per-block / race_week_brief cache entries. A
            # full-precision timestamp made those keys vary on every invocation
            # (the cone never cached → D-77 non-convergence). Pure build
            # provenance — no consumer reads it; day-granular keeps it stable
            # within a calendar day.
            generated_at=datetime.utcnow()
            .replace(hour=0, minute=0, second=0, microsecond=0)
            .isoformat(),
        ),
    )
