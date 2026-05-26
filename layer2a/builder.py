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

D-05 standing filter: discipline_name LIKE pattern excluding "WEEKLY TOTAL"
applied on the PLA join (aggregator rows polluting the table per spec §6).
SQL uses `%%` to survive psycopg2's parameter-substitution scan when params
are non-empty (see line 170; Bucket B #1, 2026-05-23 walkthrough).

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
# Kayaking discipline; only the navigation conditional remains.)
_NAV_DISCIPLINE_ID: str = "D-015"

# §8.3 override-divergence flag fires when |ov - default| / default > 0.5
# (relative divergence; matches the spec example where 25 vs default 15
# yields 67% relative divergence and the flag fires).
_DIVERGENCE_RATIO_THRESHOLD: float = 0.5

_VALID_TEAM_FORMATS: frozenset[str] = frozenset({"Solo", "Unified", "Relay"})

_TEMPLATE_VERSION: str = "v1"


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
    version_0a: str,
) -> list[dict[str, Any]]:
    """Issue the spec §5.2 query. Returns one row per included discipline
    in SDM for the sport, with PLA + DTG + discipline-library rows joined
    LEFT (may be NULL).

    Six positional params: top_level_sport, version_0a, framework_sport,
    version_0a, version_0a, version_0a. Trailing three version_0a params
    are for the PLA, DTG, and disciplines joins respectively.
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
              AND sdm.etl_version = ?
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
            dtg.gap_type,
            dtg.notes AS gap_notes,
            dtg.multi_substitute_candidate,
            dl.discipline_category,
            dl.primary_movement
        FROM sport_disciplines sd
        LEFT JOIN layer0.phase_load_allocation pla
            ON pla.sport_name = ?
           AND pla.discipline_id = sd.discipline_id
           AND pla.etl_version = ?
           AND pla.superseded_at IS NULL
           AND pla.discipline_name NOT LIKE '%%WEEKLY TOTAL%%'
        LEFT JOIN layer0.discipline_training_gaps dtg
            ON dtg.discipline_id = sd.discipline_id
           AND dtg.etl_version = ?
           AND dtg.superseded_at IS NULL
        LEFT JOIN layer0.disciplines dl
            ON dl.discipline_id = sd.discipline_id
           AND dl.etl_version = ?
           AND dl.superseded_at IS NULL
        """,
        (top_level_sport, version_0a, framework_sport, version_0a, version_0a, version_0a),
    )
    return [dict(r) for r in cur.fetchall()]


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


def _is_conditional(role: str, notes_conditions: str | None) -> bool:
    """Per spec §5.3: conditional iff role contains `(*Conditional)` OR
    notes_conditions starts with `*CONDITIONAL` (case-insensitive).
    """
    if "*conditional" in role.lower():
        return True
    if notes_conditions and notes_conditions.strip().lower().startswith("*conditional"):
        return True
    return False


def _default_inclusion(notes_conditions: str | None) -> str:
    """Derive `PhaseLoadBands.default_inclusion` from PLA notes_conditions.

    The layer0 schema doesn't carry a separate column for this — it's
    encoded in the free-text `notes_conditions`. Per spec §5.3:
    `*CONDITIONAL`-prefixed notes → `prompt_required`; otherwise → `included`.
    `excluded` is applied downstream during conditional resolution, not
    here.
    """
    if notes_conditions and notes_conditions.strip().lower().startswith("*conditional"):
        return "prompt_required"
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
    if all(row.get(k) is None for k in band_keys) and row.get("notes_conditions") is None:
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
        default_inclusion=_default_inclusion(row.get("notes_conditions")),
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


def _resolve_conditional(
    row: dict[str, Any],
    race_duration_hours: float | None,
    team_format: str | None,
    overrides: dict[str, dict] | None,
) -> tuple[str, str | None]:
    """Apply spec §5.3 conditional rules. Returns
    `(inclusion, conditional_resolution)`.

    - Unconditional → `('included', None)`.
    - Conditional: prompt_required (athlete opt-in) unless overrides
      explicitly include/exclude.
    """
    discipline_id = row["discipline_id"]
    is_cond = _is_conditional(row["role"], row.get("notes_conditions"))

    if not is_cond:
        return ("included", None)

    # Athlete-explicit override wins.
    ov = (overrides or {}).get(discipline_id) or {}
    if "included" in ov:
        return ("included" if ov["included"] else "excluded", "athlete_opt_in")

    # v1 scope: relay-leg filtering deferred (no current consumer sport).
    # Fall through: unresolved conditional → prompt athlete.
    return ("prompt_required", "athlete_opt_in")


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
    conditional_resolution: str | None,
    race_duration_hours: float | None,
) -> str:
    """Render the athlete-facing rationale string. Composed from a small
    template library keyed on role + inclusion + conditional resolution.
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
        if d.training_gap is not None:
            flags.append(
                Layer2ACoachingFlag(
                    flag_type="training_gap",
                    discipline_id=d.discipline_id,
                    message=(
                        f"{d.discipline_name} has a known training gap: "
                        f"{d.training_gap.notes}"
                    ),
                    metadata={
                        "gap_type": d.training_gap.gap_type,
                        "multi_substitute_candidate": d.training_gap.multi_substitute_candidate,
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
) -> TrainingGapsSummary:
    """Roll up DTG entries across included disciplines per spec §7."""
    included = [d for d in disciplines if d.inclusion == "included" and d.training_gap is not None]
    flagged = len(included)
    any_no_sub = any(
        "no" in (d.training_gap.gap_type or "").lower()
        and "substitute" in (d.training_gap.gap_type or "").lower()
        for d in included
    )
    any_multi_sub = any(d.training_gap.multi_substitute_candidate for d in included)
    return TrainingGapsSummary(
        flagged_count=flagged,
        any_no_substitute=any_no_sub,
        any_multi_substitute_candidate=any_multi_sub,
    )


# ─── Public entry point ──────────────────────────────────────────────────────


def q_layer2a_discipline_classifier_payload(
    db,
    framework_sport: str,
    *,
    athlete_discipline_overrides: dict[str, dict] | None = None,
    estimated_race_duration_hours: float | None = None,
    team_format: str | None = None,
    discipline_id_filter: list[str] | None = None,
    etl_version_set: dict[str, str],
) -> Layer2APayload:
    """Resolve canonical disciplines for a framework sport. Spec §3.

    Pure query node. One SELECT against `layer0.{sport_discipline_map,
    phase_load_allocation,discipline_training_gaps}` joined by spec §5.2.
    No JOIN to per-athlete tables — `athlete_discipline_overrides` is
    supplied by the caller (Phase 5 orchestrator unpacks it from
    `Layer1Payload.training_history.discipline_weighting`).

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
    version_0a = etl_version_set["0A"]

    raw_rows = _load_disciplines(db, top_level_sport, framework_sport, version_0a)

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
        inclusion, conditional_resolution = _resolve_conditional(
            row,
            estimated_race_duration_hours,
            team_format,
            athlete_discipline_overrides,
        )
        load_weight = _compute_load_weight(row, athlete_discipline_overrides)
        rationale = _render_rationale(
            row,
            framework_sport,
            inclusion,
            conditional_resolution,
            estimated_race_duration_hours,
        )
        # Sleep-deprivation relevance: D-015 (nav) always. Spec §8 doesn't
        # enumerate a closed list, so v1 keeps the surface narrow — the
        # rationale text covers the athlete-facing message and downstream
        # layers can read the flag.
        sleep_dep_relevant = row["discipline_id"] == _NAV_DISCIPLINE_ID
        disciplines.append(
            Layer2ADiscipline(
                discipline_id=row["discipline_id"],
                discipline_name=row["discipline_name"],
                discipline_category=row.get("discipline_category"),
                primary_movement=row.get("primary_movement"),
                inclusion=inclusion,
                role=row["role"],
                is_conditional=_is_conditional(row["role"], row.get("notes_conditions")),
                conditional_resolution=conditional_resolution,
                load_weight=load_weight,
                race_time_pct_low=(
                    float(row["race_time_pct_low"])
                    if row.get("race_time_pct_low") is not None
                    else None
                ),
                race_time_pct_high=(
                    float(row["race_time_pct_high"])
                    if row.get("race_time_pct_high") is not None
                    else None
                ),
                sport_specific_context=row.get("sport_specific_context"),
                phase_load=_build_phase_load(row),
                sleep_deprivation_relevant=sleep_dep_relevant,
                training_gap=_build_training_gap(row),
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

    # HITL gate per §5.6
    hitl_required = (
        not disciplines
        or any(d.inclusion == "prompt_required" for d in disciplines)
    )

    coaching_flags = _emit_coaching_flags(
        disciplines,
        raw_rows,
        estimated_race_duration_hours,
    )
    training_gaps_summary = _build_training_gaps_summary(disciplines)

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
        training_gaps_summary=training_gaps_summary,
        hitl_required=hitl_required,
        unresolved_flags=unresolved_flags,
        coaching_flags=coaching_flags,
        rationale_metadata=RationaleMetadata(
            template_version=_TEMPLATE_VERSION,
            generated_at=datetime.utcnow().isoformat(),
        ),
    )
