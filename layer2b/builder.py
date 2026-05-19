"""Layer 2B builder — terrain classifier query node.

Per `Layer2B_Spec.md` §3 (function signature) + §5 (algorithm). Pure query
node: deterministic given inputs, no LLM involvement. Two SQL queries
per call — (1) name lookup against `layer0.terrain_types` for the race's
terrain IDs; (2) per-gap proxy resolution against `layer0.terrain_gap_rules`.

The function signature mirrors `q_layer2a_discipline_classifier_payload` —
`db` first positional, `etl_version_set` keyword-only — per Phase 2.2
decision #2. Spec §3 signature is the formal contract; the `db` parameter
is implicit because §5 requires SQL access.

Gap-severity values returned reflect the spec-canonical 4-band enum
({critical, high, medium, low}) for bridgeable gaps + 'unbridgeable' for
NULL-proxy rules + 'undefined' for unknown terrain IDs. The deployed
`layer0.terrain_gap_rules` schema was reclassified from the legacy
'partial' single-value via `etl/sources/migrate_terrain_gap_rules_severity.sql`
(D-73 Phase 2.3 paired migration).
"""

from __future__ import annotations

import re
from typing import Any

from layer4.context import (
    Layer2BCoachingFlag,
    Layer2BPayload,
    Layer2BSummaryBlock,
    RaceTerrainEntry,
    RaceTerrainOutput,
    TerrainGap,
)


# ─── Constants ───────────────────────────────────────────────────────────────


_REQUIRED_ETL_KEYS: frozenset[str] = frozenset({"0C"})

_TRN_PATTERN = re.compile(r"^TRN-\d{3}$")

# §4 precondition 4: lenient pct-sum band — race breakdowns are estimates.
_PCT_SUM_LOW: float = 80.0
_PCT_SUM_HIGH: float = 120.0

# §8.2 coached-intro trigger — fidelity threshold + keyword substring match
# against `prescription_note`. The deployed whitewater rule (TRN-011 →
# TRN-009) is the only current consumer; tokens chosen to match its note
# verbatim plus near-paraphrases the populate script may use.
_COACHED_INTRO_FIDELITY_MIN: float = 0.5
_COACHED_INTRO_KEYWORDS: tuple[str, ...] = (
    "coached introduction",
    "supervised instruction",
    "requires coached",
    "requiring coached",
    "coached intro",
)


# ─── Errors ──────────────────────────────────────────────────────────────────


class Layer2BInputError(ValueError):
    """Raised by `q_layer2b_terrain_classifier_payload` on §4 validation
    failure. Plan-gen catches and surfaces a user-facing error."""


# ─── Helpers ─────────────────────────────────────────────────────────────────


def _validate_inputs(
    race_terrain: list[RaceTerrainEntry],
    locale_terrain_ids: list[str],
    included_discipline_ids: list[str],
    etl_version_set: dict[str, str],
) -> None:
    if not isinstance(race_terrain, list) or not race_terrain:
        raise Layer2BInputError(
            "race_terrain must be a non-empty list of RaceTerrainEntry"
        )
    for idx, entry in enumerate(race_terrain):
        if not isinstance(entry, RaceTerrainEntry):
            raise Layer2BInputError(
                f"race_terrain[{idx}] must be a RaceTerrainEntry instance"
            )
        if not _TRN_PATTERN.match(entry.terrain_id):
            raise Layer2BInputError(
                f"race_terrain[{idx}].terrain_id {entry.terrain_id!r} "
                "must match pattern TRN-\\d{3}"
            )
        if not (0.0 <= entry.pct_of_race <= 100.0):
            raise Layer2BInputError(
                f"race_terrain[{idx}].pct_of_race {entry.pct_of_race} "
                "must be in [0.0, 100.0]"
            )

    pct_sum = sum(e.pct_of_race for e in race_terrain)
    if not (_PCT_SUM_LOW <= pct_sum <= _PCT_SUM_HIGH):
        raise Layer2BInputError(
            f"sum of race_terrain pct_of_race ({pct_sum}) must be in "
            f"[{_PCT_SUM_LOW}, {_PCT_SUM_HIGH}]"
        )

    if not isinstance(locale_terrain_ids, list):
        raise Layer2BInputError(
            "locale_terrain_ids must be a list (may be empty)"
        )
    for idx, lid in enumerate(locale_terrain_ids):
        if not isinstance(lid, str) or not _TRN_PATTERN.match(lid):
            raise Layer2BInputError(
                f"locale_terrain_ids[{idx}] {lid!r} must match pattern TRN-\\d{{3}}"
            )

    if not isinstance(included_discipline_ids, list) or not included_discipline_ids:
        raise Layer2BInputError(
            "included_discipline_ids must be a non-empty list"
        )

    if not isinstance(etl_version_set, dict) or not _REQUIRED_ETL_KEYS.issubset(
        etl_version_set.keys()
    ):
        raise Layer2BInputError(
            f"etl_version_set must contain keys {sorted(_REQUIRED_ETL_KEYS)}; "
            f"got {sorted(etl_version_set.keys()) if isinstance(etl_version_set, dict) else etl_version_set!r}"
        )


def _load_terrain_names(
    db,
    terrain_ids: list[str],
    version_0c: str,
) -> dict[str, str]:
    if not terrain_ids:
        return {}
    cur = db.execute(
        """
        SELECT terrain_id, canonical_name
          FROM layer0.terrain_types
         WHERE terrain_id = ANY(?)
           AND etl_version = ?
           AND superseded_at IS NULL
        """,
        (list(terrain_ids), version_0c),
    )
    return {r["terrain_id"]: r["canonical_name"] for r in cur.fetchall()}


def _load_best_proxy(
    db,
    target_terrain_id: str,
    locale_terrain_ids: list[str],
    version_0c: str,
) -> dict[str, Any] | None:
    # Per spec §5.2 — best-proxy ORDER BY: highest fidelity wins, ties
    # broken by lowest severity. Severity ordering encodes
    # low < medium < high < critical < unbridgeable so the bridgeable
    # rules outrank the NULL-proxy unbridgeable row at equal fidelity.
    cur = db.execute(
        """
        SELECT
          gap.target_terrain_id,
          gap.target_terrain_name,
          gap.proxy_terrain_id,
          gap.proxy_terrain_name,
          gap.gap_severity,
          gap.adaptation_weeks_low,
          gap.adaptation_weeks_high,
          gap.proxy_fidelity,
          gap.proxy_methods,
          gap.uncoverable_stimulus,
          gap.prescription_note
        FROM layer0.terrain_gap_rules gap
        WHERE gap.target_terrain_id = ?
          AND gap.etl_version = ?
          AND gap.superseded_at IS NULL
          AND (
            gap.proxy_terrain_id IS NULL
            OR gap.proxy_terrain_id = ANY(?)
          )
        ORDER BY
          gap.proxy_fidelity DESC NULLS LAST,
          CASE gap.gap_severity
            WHEN 'low' THEN 0
            WHEN 'medium' THEN 1
            WHEN 'high' THEN 2
            WHEN 'critical' THEN 3
            WHEN 'unbridgeable' THEN 4
            ELSE 5
          END
        LIMIT 1
        """,
        (target_terrain_id, version_0c, list(locale_terrain_ids)),
    )
    row = cur.fetchone()
    return dict(row) if row else None


def _build_terrain_gap(row: dict[str, Any]) -> TerrainGap:
    return TerrainGap(
        target_terrain_id=row["target_terrain_id"],
        target_terrain_name=row["target_terrain_name"],
        proxy_terrain_id=row.get("proxy_terrain_id"),
        proxy_terrain_name=row.get("proxy_terrain_name"),
        gap_severity=row["gap_severity"],
        adaptation_weeks_low=row.get("adaptation_weeks_low"),
        adaptation_weeks_high=row.get("adaptation_weeks_high"),
        proxy_fidelity=(
            float(row["proxy_fidelity"])
            if row.get("proxy_fidelity") is not None
            else None
        ),
        proxy_methods=list(row.get("proxy_methods") or []),
        uncoverable_stimulus=list(row.get("uncoverable_stimulus") or []),
        prescription_note=row.get("prescription_note") or "",
        discipline_relevance_assessed=False,
    )


def _build_undefined_gap(
    target_terrain_id: str,
    target_terrain_name: str | None,
) -> TerrainGap:
    return TerrainGap(
        target_terrain_id=target_terrain_id,
        target_terrain_name=target_terrain_name or target_terrain_id,
        proxy_terrain_id=None,
        proxy_terrain_name=None,
        gap_severity="undefined",
        adaptation_weeks_low=None,
        adaptation_weeks_high=None,
        proxy_fidelity=None,
        proxy_methods=[],
        uncoverable_stimulus=[],
        prescription_note=(
            "No gap-rule data exists for this terrain. "
            "Plan-gen treats as unbridgeable by default until a rule is authored."
        ),
        discipline_relevance_assessed=False,
    )


def _mentions_coached_intro(prescription_note: str) -> bool:
    lower = prescription_note.lower()
    return any(kw in lower for kw in _COACHED_INTRO_KEYWORDS)


def _emit_coaching_flags(
    gaps_by_target: dict[str, TerrainGap],
    pct_by_target: dict[str, float],
) -> list[Layer2BCoachingFlag]:
    flags: list[Layer2BCoachingFlag] = []
    for target_id, gap in gaps_by_target.items():
        pct = pct_by_target.get(target_id, 0.0)
        if gap.gap_severity == "undefined":
            flags.append(Layer2BCoachingFlag(
                flag_type="undefined_gap",
                target_terrain_id=target_id,
                message=(
                    f"Terrain '{gap.target_terrain_name}' has no gap rule data "
                    "— plan-gen will treat as unbridgeable by default."
                ),
                metadata={"severity_assumed": "unbridgeable", "pct_of_race": pct},
            ))
            continue
        if gap.proxy_terrain_id is None:
            flags.append(Layer2BCoachingFlag(
                flag_type="unbridgeable_terrain",
                target_terrain_id=target_id,
                message=(
                    f"{gap.target_terrain_name} cannot be replicated with your "
                    f"current locale terrain. {gap.prescription_note}"
                ),
                metadata={
                    "pct_of_race": pct,
                    "uncoverable_stimulus": list(gap.uncoverable_stimulus),
                },
            ))
            continue
        if (
            gap.proxy_fidelity is not None
            and gap.proxy_fidelity >= _COACHED_INTRO_FIDELITY_MIN
            and _mentions_coached_intro(gap.prescription_note)
        ):
            flags.append(Layer2BCoachingFlag(
                flag_type="requires_coached_introduction",
                target_terrain_id=target_id,
                message=gap.prescription_note,
                metadata={
                    "fidelity": gap.proxy_fidelity,
                    "adaptation_weeks_high": gap.adaptation_weeks_high,
                },
            ))
    return flags


def _build_summary(
    race_terrain: list[RaceTerrainEntry],
    covered_ids: set[str],
    gap_ids: set[str],
    gaps_by_target: dict[str, TerrainGap],
) -> Layer2BSummaryBlock:
    # Per spec §5.5: `gaps_only` excludes 'undefined' gaps because they
    # have no rule-driven proxy_terrain_id or unbridgeable classification
    # to count toward bridgeable/unbridgeable splits. The `gap_count` and
    # `pct_of_race_uncovered` totals still include undefined entries.
    gaps_only = [
        g for g in gaps_by_target.values()
        if g.proxy_terrain_id is not None or g.gap_severity == "unbridgeable"
    ]
    bridgeable = [g for g in gaps_only if g.proxy_terrain_id is not None]
    unbridgeable = [g for g in gaps_only if g.proxy_terrain_id is None]

    adapt_highs = [
        g.adaptation_weeks_high
        for g in gaps_only
        if g.adaptation_weeks_high is not None
    ]
    fidelities = [
        g.proxy_fidelity
        for g in gaps_only
        if g.proxy_fidelity is not None
    ]

    has_undefined = any(
        g.gap_severity == "undefined" for g in gaps_by_target.values()
    )

    return Layer2BSummaryBlock(
        total_race_terrain_count=len(race_terrain),
        covered_count=len(covered_ids),
        gap_count=len(gap_ids),
        bridgeable_count=len(bridgeable),
        unbridgeable_count=len(unbridgeable),
        min_adaptation_weeks_needed=max(adapt_highs) if adapt_highs else 0,
        worst_fidelity=min(fidelities) if fidelities else 1.0,
        pct_of_race_uncovered=sum(
            e.pct_of_race for e in race_terrain if e.terrain_id in gap_ids
        ),
        any_unbridgeable=len(unbridgeable) > 0,
        any_undefined=has_undefined,
    )


# ─── Public entry point ──────────────────────────────────────────────────────


def q_layer2b_terrain_classifier_payload(
    db,
    race_terrain: list[RaceTerrainEntry],
    locale_terrain_ids: list[str],
    included_discipline_ids: list[str],
    *,
    etl_version_set: dict[str, str],
) -> Layer2BPayload:
    """Resolve race-vs-locale terrain coverage for the athlete's training plan.

    Pure query node per `Layer2B_Spec.md` §3. Set difference identifies
    terrain gaps; per-gap proxy resolution picks the best available
    (highest fidelity) proxy that's in the athlete's locale set, falling
    back to the rule's unbridgeable row when no real proxy is reachable,
    or to a synthetic 'undefined' gap when the target has no rule rows at
    all. `included_discipline_ids` is required input but not currently
    used for relevance scoping (v1 ships with `discipline_relevance_assessed=False`
    per §5.3 — full structured relevance is queued as open item 2B-1).

    Validation per §4 raises `Layer2BInputError`.
    """
    _validate_inputs(
        race_terrain,
        locale_terrain_ids,
        included_discipline_ids,
        etl_version_set,
    )

    version_0c = etl_version_set["0C"]
    race_id_set = {e.terrain_id for e in race_terrain}
    locale_id_set = set(locale_terrain_ids)
    pct_by_target = {e.terrain_id: e.pct_of_race for e in race_terrain}

    covered_ids = race_id_set & locale_id_set
    gap_ids = race_id_set - locale_id_set

    name_map = _load_terrain_names(db, sorted(race_id_set), version_0c)

    gaps_by_target: dict[str, TerrainGap] = {}
    for gap_id in sorted(gap_ids):
        proxy_row = _load_best_proxy(
            db, gap_id, sorted(locale_id_set), version_0c
        )
        if proxy_row is None:
            gaps_by_target[gap_id] = _build_undefined_gap(
                gap_id, name_map.get(gap_id)
            )
        else:
            if proxy_row.get("target_terrain_name") is None:
                proxy_row["target_terrain_name"] = (
                    name_map.get(gap_id) or gap_id
                )
            gaps_by_target[gap_id] = _build_terrain_gap(proxy_row)

    race_outputs: list[RaceTerrainOutput] = []
    for entry in race_terrain:
        race_outputs.append(RaceTerrainOutput(
            terrain_id=entry.terrain_id,
            terrain_name=name_map.get(entry.terrain_id),
            pct_of_race=entry.pct_of_race,
            available_locally=entry.terrain_id in covered_ids,
            gap=gaps_by_target.get(entry.terrain_id),
        ))

    coaching_flags = _emit_coaching_flags(gaps_by_target, pct_by_target)
    summary = _build_summary(
        race_terrain, covered_ids, gap_ids, gaps_by_target
    )

    return Layer2BPayload(
        race_terrain=race_outputs,
        terrain_gaps=list(gaps_by_target.values()),
        coaching_flags=coaching_flags,
        summary=summary,
        etl_version_set=dict(etl_version_set),
    )
