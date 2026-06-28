"""Layer 4 — `llm_layer4_plan_refresh` D-64 caller integration (T1 + T2).

Implements `Layer4_Spec.md` §3.2 (plan-refresh entry-point function
signature), §4.3 (input validation preconditions), §5.1 (pattern routing —
T1/T2 → B always), §5.3 (Pattern B algorithm), §5.5 (capped retry; cap=2
default), §8.6/§8.7 (`intensity_modulated` observation emission — broadened
to plan_refresh per the 2026-05-17 §8.6/§8.7 amendment).

T1 and T2 share Pattern B's algorithm, the validator harness, the retry
loop, the schema-violation special case, and the best-effort acceptance
fallback. The tier-distinct logic — system prompt, user-prompt template,
tool schema's sessions array `maxItems`, sampling defaults (max_tokens +
extended_thinking_budget) — lives in `plan_refresh_t1.py` and
`plan_refresh_t2.py`. This module owns the driver entrypoint that dispatches
on `tier` to the tier file's `synthesize_*` helper.

T3 is queued for Step 4d (intra-phase → Pattern B; cross-phase → Pattern A;
the latter depends on Step 4f's per-phase orchestration). T3 raises
`Layer4InputError('tier_t3_not_yet_implemented')` until Step 4d lands.

**3B required for all tiers (Andy 2026-05-17 §4.3-wins pick).** The
spec contained an internal contradiction: §3.2 signature typed
`layer3b_payload: Layer3BPayload | None` with T1 falling back to prior
sessions' phase_metadata; §4.3 row 1 stated "`layer3b_payload` required even
on T1/T2 — Pattern B's validator still reads phase intent for the
intensity-distribution check." Andy picked §4.3-wins. Per that pick,
`Layer4_Spec.md` §3.2 signature was amended (drop `| None`); D-64's T1
default cascade now includes 3B re-run (per the carry-forward catalogued in
the closing handoff).

**Tool-schema fidelity (Step 4a Option 2 precedent).** The
`record_refresh_sessions` tool mirrors the full `Layer4Payload.PlanSession`
contract — 9-shape `IntensityTarget` `oneOf` union, `intensity_zone` enum,
strength `exercise_name`/`rest_between_sets_sec`/`tempo`, etc. The
prompt-body MD's v1 sketch (smaller schema) is documentation; the runtime
tool schema follows the full payload contract per Step 4a's precedent.

Caching is the orchestrator's concern per §9.4 — this function is invoked
only on cache miss. The per-entry cache key formula lives in
`layer4/hashing.py` `plan_refresh_key`.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import date as _date_type, datetime
from typing import Any, Callable, Literal

from pydantic import ValidationError

from llm_invocation import ThinkingToolCallError, invoke_tool_call
from layer4.context import (
    Layer2Bundle,
    Layer3APayload,
    Layer3BPayload,
    ParsedIntent,
    TrainingSubstitutionPayload,
)
from layer4.errors import Layer4InputError, Layer4OutputError
from layer4.per_phase import (
    CARDIO_DRILLS_PROMPT_SECTION,
    CARDIO_PROGRAMMING_PROMPT_SECTION,
    VARIETY_CARVEOUT_PROMPT_SECTION,
    _apply_strength_resolution,
    _format_cardio_drill_pool,
    _format_coaching_memory,
    block_output_budget,
    compute_cardio_drill_pool_ids,
    compute_feasible_pool_ids,
    format_measured_physiology,
    format_upstream_coaching_flags,
)
from layer4.payload import (
    CardioBlock,
    CardioDrill,
    Layer4Payload,
    Observation,
    PlanSession,
    RuleFailure,
    StrengthExercise,
    ValidatorResult,
)
from layer4.validator import (
    ValidatorContext,
    validate_layer4_payload,
    weekly_capacity_hours,
)


# ─── Shared types ────────────────────────────────────────────────────────────


@dataclass
class _SynthesizerOutput:
    """Raw output from one synthesizer LLM call before payload construction."""

    tool_args: dict[str, Any]
    input_tokens: int
    output_tokens: int
    latency_ms: int


LLMCaller = Callable[
    [str, str, dict[str, Any], str, float, int, int],
    _SynthesizerOutput,
]
"""Adapter signature:
`(system_prompt, user_prompt, tool_schema, model, temperature, max_tokens,
extended_thinking_budget) -> _SynthesizerOutput`. Default implementation
calls Anthropic SDK; tests pass a stub."""


# ─── Tool schema (full PlanSession contract mirror per Step 4a precedent) ────


def _intensity_target_schema() -> dict[str, Any]:
    """9-shape discriminated `IntensityTarget` `oneOf` union per
    `layer4/payload.py` §7.3. Identical to single_session.py's schema."""
    return {
        "oneOf": [
            {
                "type": "object",
                "additionalProperties": False,
                "required": ["hr_bpm_low", "hr_bpm_high"],
                "properties": {
                    "hr_bpm_low": {"type": "integer", "minimum": 30, "maximum": 230},
                    "hr_bpm_high": {"type": "integer", "minimum": 30, "maximum": 230},
                },
            },
            {
                "type": "object",
                "additionalProperties": False,
                "required": ["power_w_low", "power_w_high"],
                "properties": {
                    "power_w_low": {"type": "integer", "minimum": 0, "maximum": 2000},
                    "power_w_high": {"type": "integer", "minimum": 0, "maximum": 2000},
                },
            },
            {
                "type": "object",
                "additionalProperties": False,
                "required": ["pace_per_km_low", "pace_per_km_high"],
                "properties": {
                    "pace_per_km_low": {"type": "string", "pattern": r"^\d{1,2}:[0-5]\d$"},
                    "pace_per_km_high": {"type": "string", "pattern": r"^\d{1,2}:[0-5]\d$"},
                },
            },
            {
                "type": "object",
                "additionalProperties": False,
                "required": ["pace_per_100m_low", "pace_per_100m_high"],
                "properties": {
                    "pace_per_100m_low": {"type": "string", "pattern": r"^\d{1,2}:[0-5]\d$"},
                    "pace_per_100m_high": {"type": "string", "pattern": r"^\d{1,2}:[0-5]\d$"},
                },
            },
            {
                "type": "object",
                "additionalProperties": False,
                "required": ["rpe_low", "rpe_high"],
                "properties": {
                    "rpe_low": {"type": "integer", "minimum": 1, "maximum": 10},
                    "rpe_high": {"type": "integer", "minimum": 1, "maximum": 10},
                },
            },
            {
                "type": "object",
                "additionalProperties": False,
                "required": ["vert_m_per_hr_low", "vert_m_per_hr_high"],
                "properties": {
                    "vert_m_per_hr_low": {"type": "integer", "minimum": 0, "maximum": 3000},
                    "vert_m_per_hr_high": {"type": "integer", "minimum": 0, "maximum": 3000},
                },
            },
            {
                "type": "object",
                "additionalProperties": False,
                "required": ["strokes_per_min_low", "strokes_per_min_high"],
                "properties": {
                    "strokes_per_min_low": {"type": "integer", "minimum": 0, "maximum": 200},
                    "strokes_per_min_high": {"type": "integer", "minimum": 0, "maximum": 200},
                },
            },
            {
                "type": "object",
                "additionalProperties": False,
                "required": ["rpm_low", "rpm_high"],
                "properties": {
                    "rpm_low": {"type": "integer", "minimum": 0, "maximum": 250},
                    "rpm_high": {"type": "integer", "minimum": 0, "maximum": 250},
                },
            },
            {
                "type": "object",
                "additionalProperties": False,
                "required": ["grade_system", "grade_min", "grade_max"],
                "properties": {
                    "grade_system": {
                        "type": "string",
                        "enum": ["yosemite_decimal", "french_sport", "uiaa"],
                    },
                    "grade_min": {"type": "string"},
                    "grade_max": {"type": "string"},
                },
            },
        ]
    }


# Closed coaching-flag enum per `Layer4_RefreshT1_v1.md` D6 + `_v1.md` line 217:
# 7 LLM-emittable flags (technique_emphasis, long_slow_distance,
# weak_link_targeted, overreach_test, discipline_specific_intensity,
# race_pace_specific, intensity_modulated). Phase-tied spec-auto flags
# (recovery_week, deload, race_rehearsal, etc.) are orchestrator-stamped, not
# LLM-emitted.
_REFRESH_COACHING_FLAGS = [
    "technique_emphasis",
    "long_slow_distance",
    "weak_link_targeted",
    "overreach_test",
    "discipline_specific_intensity",
    "race_pace_specific",
    "intensity_modulated",
]


def _session_schema(
    feasible_pool_ids: list[str] | None = None,
    cardio_drill_pool_ids: list[str] | None = None,
) -> dict[str, Any]:
    """One element of the `sessions` array — the full PlanSession contract
    mirror per Step 4a precedent. Differs from single_session.py only in the
    closed coaching_flags enum (7 refresh flags vs 3 single-session flags)
    and the absence of `is_ad_hoc`-related sentinel fields.

    Track 2 D1: when `feasible_pool_ids` is non-empty, the
    `strength_exercises.exercise_id` property is bounded by enum, making
    out-of-pool picks structurally impossible at the SDK boundary."""
    return {
        "type": "object",
        "additionalProperties": False,
        "required": [
            "date",
            "day_of_week",
            "session_index_in_day",
            "time_of_day",
            "kind",
            "duration_min",
            "intensity_summary",
            "session_notes",
            "coaching_intent",
            "coaching_flags",
        ],
        "properties": {
            "date": {"type": "string", "format": "date"},
            "day_of_week": {
                "type": "string",
                "enum": ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"],
            },
            "session_index_in_day": {"type": "integer", "minimum": 0, "maximum": 1},
            "time_of_day": {
                "type": "string",
                "enum": ["morning", "afternoon", "evening", "unspecified"],
            },
            "kind": {"type": "string", "enum": ["cardio", "strength"]},
            "discipline_id": {"type": ["string", "null"]},
            "discipline_name": {"type": ["string", "null"]},
            "locale_id": {"type": ["string", "null"]},
            "locale_name": {"type": ["string", "null"]},
            "duration_min": {"type": "integer", "minimum": 30, "maximum": 360},
            "intensity_summary": {
                "type": "string",
                "enum": ["easy", "moderate", "hard", "mixed"],
            },
            "session_notes": {"type": "string", "maxLength": 240},
            "coaching_intent": {"type": "string", "maxLength": 200},
            "coaching_flags": {
                "type": "array",
                "items": {"type": "string", "enum": _REFRESH_COACHING_FLAGS},
                "maxItems": 7,
                "uniqueItems": True,
            },
            "cardio_blocks": {
                "type": ["array", "null"],
                "items": {
                    "type": "object",
                    "additionalProperties": False,
                    "required": [
                        "block_kind",
                        "duration_min",
                        "intensity_zone",
                        "intensity_target",
                        "instructions",
                    ],
                    "properties": {
                        "block_kind": {
                            "type": "string",
                            "enum": [
                                "warmup",
                                "main_set",
                                "cooldown",
                                "interval_set",
                                "transition",
                            ],
                        },
                        "duration_min": {"type": "integer", "minimum": 1, "maximum": 300},
                        "intensity_zone": {
                            "type": "string",
                            "enum": ["Z1", "Z2", "Z3", "Z4", "Z5", "mixed"],
                        },
                        "intensity_target": _intensity_target_schema(),
                        "instructions": {"type": "string", "maxLength": 240},
                        "repetitions": {
                            "type": ["integer", "null"],
                            "minimum": 1,
                            "maximum": 50,
                        },
                        "rest_between_min": {
                            "type": ["integer", "null"],
                            "minimum": 0,
                        },
                        "rest_intensity_zone": {
                            "type": ["string", "null"],
                            "enum": ["Z1", "Z2", None],
                        },
                    },
                },
            },
            "strength_exercises": {
                "type": ["array", "null"],
                "items": {
                    "type": "object",
                    "additionalProperties": False,
                    "required": [
                        "exercise_id",
                        "exercise_name",
                        "resolution_tier",
                        "sets",
                        "reps_per_set",
                        "load_prescription",
                        "rest_between_sets_sec",
                        "instructions",
                        "coaching_flags",
                    ],
                    "properties": {
                        "exercise_id": (
                            {"type": "string", "enum": feasible_pool_ids}
                            if feasible_pool_ids
                            else {"type": "string"}
                        ),
                        "exercise_name": {"type": "string"},
                        "resolution_tier": {"type": "integer", "enum": [1, 2, 3]},
                        "substitute_text": {"type": ["string", "null"]},
                        "proxy_origin_id": {"type": ["string", "null"]},
                        "sets": {"type": "integer", "minimum": 1, "maximum": 10},
                        "reps_per_set": {
                            "oneOf": [
                                {"type": "integer", "minimum": 1, "maximum": 100},
                                {"type": "string"},
                            ]
                        },
                        "load_prescription": {"type": "string", "maxLength": 120},
                        "rest_between_sets_sec": {
                            "type": "integer",
                            "minimum": 0,
                            "maximum": 600,
                        },
                        "tempo": {"type": ["string", "null"]},
                        "instructions": {"type": "string", "maxLength": 240},
                        "coaching_flags": {
                            "type": "array",
                            "items": {"type": "string"},
                            "maxItems": 4,
                            "uniqueItems": True,
                        },
                    },
                },
            },
            # #698 Track 2 (Slice C2) — structured cardio drill block, the
            # analog of the plan-create cardio_drills (same fidelity as plan
            # generation). HARD CAP maxItems:1; exercise_id enum-bound to the
            # drill pool when resolvable, so out-of-pool picks are structurally
            # impossible at the SDK boundary.
            "cardio_drills": {
                "type": ["array", "null"],
                "maxItems": 1,
                "items": {
                    "type": "object",
                    "additionalProperties": False,
                    "required": [
                        "exercise_id",
                        "exercise_name",
                        "prescription",
                    ],
                    "properties": {
                        "exercise_id": (
                            {"type": "string", "enum": cardio_drill_pool_ids}
                            if cardio_drill_pool_ids
                            else {"type": "string"}
                        ),
                        "exercise_name": {"type": "string"},
                        "prescription": {"type": "string", "maxLength": 120},
                        "instructions": {"type": ["string", "null"], "maxLength": 240},
                    },
                },
            },
            "rest_reason": {
                "type": ["string", "null"],
                "enum": [
                    "planned_recovery",
                    "overreach_protection",
                    "travel_day",
                    "athlete_unavailable",
                    "taper_drop",
                    None,
                ],
            },
        },
    }


def build_record_refresh_sessions_tool(
    tier: Literal["T1", "T2", "T3"],
    feasible_pool_ids: list[str] | None = None,
    cardio_drill_pool_ids: list[str] | None = None,
) -> dict[str, Any]:
    """Anthropic tool definition for `record_refresh_sessions`. Sessions
    array `maxItems` is tier-specific: T1=4 (2-day window × max 2/day);
    T2=14 (7-day window × max 2/day); T3=56 (28-day window × max 2/day).
    Per-session shape is the full PlanSession contract mirror per the
    Step 4a Option 2 precedent.

    Track 2 D1: `feasible_pool_ids` (when non-empty) bounds
    `strength_exercises.exercise_id` via JSON-schema enum. Production callers
    pass `compute_feasible_pool_ids(layer2c_payloads, layer2d_payload)`."""
    max_items = _TIER_MAX_SESSIONS[tier]
    description = (
        f"Record the synthesized {tier} refresh sessions covering "
        f"[refresh_scope_start, refresh_scope_end]. Output is a list of 0-"
        f"{max_items} PlanSession objects. Empty list is allowed when the "
        f"refresh window is entirely rest by athlete schedule + coaching "
        f"choice. Emit exactly one tool call per invocation."
    )
    return {
        "name": "record_refresh_sessions",
        "description": description,
        "input_schema": {
            "type": "object",
            "additionalProperties": False,
            "required": ["sessions"],
            "properties": {
                "sessions": {
                    "type": "array",
                    "minItems": 0,
                    "maxItems": max_items,
                    "items": _session_schema(feasible_pool_ids, cardio_drill_pool_ids),
                }
            },
        },
    }


# ─── Input validation (Layer4_Spec.md §4.3) ──────────────────────────────────


_T1_MAX_SCOPE_DAYS = 3
_T2_MAX_SCOPE_DAYS = 9
_T3_MAX_SCOPE_DAYS = 32

# Per-tier `sessions` array ceiling: 2-day/7-day/28-day window × max 2/day.
# Drives both the tool schema's `maxItems` and the output-token budget the driver
# sizes per `per_phase.block_output_budget` (so a dense block doesn't truncate).
_TIER_MAX_SESSIONS = {"T1": 4, "T2": 14, "T3": 56}


def _validate_inputs(
    tier: str,
    refresh_scope_start: _date_type,
    refresh_scope_end: _date_type,
    layer1_payload: dict[str, Any] | None,
    layer2_bundle: Layer2Bundle | None,
    layer3a_payload: Layer3APayload | None,
    layer3b_payload: Layer3BPayload | None,
    prior_plan_session_window: list[PlanSession],
    plan_version_id_parent: int,
    plan_start_date: _date_type | None = None,
) -> None:
    """Apply §4.3 plan-refresh preconditions. Fail-fast — raises
    `Layer4InputError` on first failing rule.

    `plan_start_date` is required when `tier == 'T3'` per the Step 4d §3.2
    amendment (orchestrator-supplied; used by `phase_structure_from_3b()`
    for phase-boundary detection). T1/T2 ignore."""
    # Row 2: tier in enum
    if tier not in ("T1", "T2", "T3"):
        raise Layer4InputError("tier_invalid", detail=f"tier={tier!r}")

    # Row 3: scope_start <= scope_end
    if refresh_scope_start > refresh_scope_end:
        raise Layer4InputError(
            "refresh_scope_inverted",
            detail=(
                f"refresh_scope_start={refresh_scope_start.isoformat()} > "
                f"refresh_scope_end={refresh_scope_end.isoformat()}"
            ),
        )

    # Row 4: tier matches scope length
    scope_days = (refresh_scope_end - refresh_scope_start).days + 1
    if tier == "T1" and scope_days > _T1_MAX_SCOPE_DAYS:
        raise Layer4InputError(
            "tier_scope_mismatch",
            detail=f"tier=T1 requires scope <= 3 days (got {scope_days})",
        )
    if tier == "T2" and scope_days > _T2_MAX_SCOPE_DAYS:
        raise Layer4InputError(
            "tier_scope_mismatch",
            detail=f"tier=T2 requires scope <= 9 days (got {scope_days})",
        )
    if tier == "T3" and scope_days > _T3_MAX_SCOPE_DAYS:
        raise Layer4InputError(
            "tier_scope_mismatch",
            detail=f"tier=T3 requires scope <= 32 days (got {scope_days})",
        )

    # Step 4d amendment: plan_start_date required when tier=='T3' for
    # phase-boundary detection via phase_structure_from_3b().
    if tier == "T3" and plan_start_date is None:
        raise Layer4InputError(
            "plan_start_date_missing",
            detail=(
                "tier='T3' requires plan_start_date non-None per Layer4_Spec.md "
                "§3.2 (Step 4d amendment) — phase_structure_from_3b() needs the "
                "parent plan's start date to compute phase boundaries"
            ),
        )

    # Row 1: upstream payloads non-None. Per Andy 2026-05-17 §4.3-wins pick,
    # `layer3b_payload` is required for T1 and T2 (the validator reads
    # phase intent for the intensity-distribution check; falling back to
    # prior session phase_metadata was the §3.2-narrative path, rejected by
    # the §4.3-wins resolution).
    if layer1_payload is None:
        raise Layer4InputError(
            "missing_upstream_payload", detail="layer1_payload is None"
        )
    if layer2_bundle is None:
        raise Layer4InputError(
            "missing_upstream_payload", detail="layer2_bundle is None"
        )
    if layer3a_payload is None:
        raise Layer4InputError(
            "missing_upstream_payload", detail="layer3a_payload is None"
        )
    if layer3b_payload is None:
        raise Layer4InputError(
            "missing_upstream_payload",
            detail=(
                "layer3b_payload is required for all tiers per §4.3 row 1 "
                "(2026-05-17 §4.3-wins amendment)"
            ),
        )

    # Row 5: prior_plan_session_window non-empty
    if not prior_plan_session_window:
        raise Layer4InputError(
            "prior_plan_window_empty",
            detail="prior_plan_session_window must be non-empty for plan_refresh",
        )

    # Row 6: plan_version_id_parent must be a positive int (FK to plan_versions;
    # actual FK check is orchestrator-side — defensive shape check here).
    if plan_version_id_parent <= 0:
        raise Layer4InputError(
            "plan_version_id_parent_missing",
            detail=(
                f"plan_version_id_parent={plan_version_id_parent} is not a valid "
                "plan_versions FK"
            ),
        )

    # Row 7 (parsed_intent_schema_invalid) is pydantic-enforced at
    # ParsedIntent construction; if a caller bypasses pydantic that's their
    # contract violation, not Layer 4's defensive concern.


# ─── Anthropic SDK call ──────────────────────────────────────────────────────


def _default_llm_caller(
    system_prompt: str,
    user_prompt: str,
    tool_schema: dict[str, Any],
    model: str,
    temperature: float,
    max_tokens: int,
    extended_thinking_budget: int,
) -> _SynthesizerOutput:
    """Production LLM caller — delegates to the shared thinking-aware
    invocation (`llm_invocation.invoke_tool_call`), which holds the one correct
    extended-thinking request shape (tool_choice `auto` + temperature 1 +
    max_tokens > budget_tokens) AND the forced-tool retry that fires when a
    thinking attempt declines the tool. Failures map to `Layer4OutputError` so
    the existing error contract is preserved. Tests inject a stub instead."""
    try:
        result = invoke_tool_call(
            system_prompt=system_prompt,
            user_prompt=user_prompt,
            tool_schema=tool_schema,
            model=model,
            temperature=temperature,
            max_tokens=max_tokens,
            extended_thinking_budget=extended_thinking_budget,
        )
    except ThinkingToolCallError as exc:
        raise Layer4OutputError(exc.code, detail=exc.detail) from exc

    return _SynthesizerOutput(
        tool_args=result.tool_args,
        input_tokens=result.input_tokens,
        output_tokens=result.output_tokens,
        latency_ms=result.latency_ms,
    )


# ─── Tool-output parsing → PlanSession ───────────────────────────────────────


def _parse_date(s: str) -> _date_type:
    return datetime.fromisoformat(s).date() if "T" in s else _date_type.fromisoformat(s)


def _build_plan_session(
    session_data: dict[str, Any],
    *,
    session_id: str,
    plan_version_id: int,
) -> PlanSession:
    """Wrap a session dict from the synthesizer tool output into a
    PlanSession. Pattern B plan_refresh requires `phase_metadata=None` per
    §7.12 + `is_ad_hoc=False` (refresh outputs aren't ad-hoc)."""
    raw_blocks = session_data.get("cardio_blocks")
    blocks: list[CardioBlock] | None = None
    if raw_blocks:
        blocks = [CardioBlock(**b) for b in raw_blocks]

    raw_exercises = session_data.get("strength_exercises")
    exercises: list[StrengthExercise] | None = None
    if raw_exercises:
        exercises = [StrengthExercise(**e) for e in raw_exercises]

    raw_drills = session_data.get("cardio_drills")
    drills: list[CardioDrill] | None = None
    if raw_drills:
        drills = [CardioDrill(**d) for d in raw_drills]

    return PlanSession(
        session_id=session_id,
        plan_version_id=plan_version_id,
        date=_parse_date(session_data["date"]),
        day_of_week=session_data["day_of_week"],
        session_index_in_day=session_data["session_index_in_day"],
        time_of_day=session_data["time_of_day"],
        kind=session_data["kind"],
        discipline_id=session_data.get("discipline_id"),
        discipline_name=session_data.get("discipline_name"),
        locale_id=session_data.get("locale_id"),
        locale_name=session_data.get("locale_name"),
        duration_min=session_data["duration_min"],
        intensity_summary=session_data["intensity_summary"],
        cardio_blocks=blocks,
        strength_exercises=exercises,
        cardio_drills=drills,
        rest_reason=session_data.get("rest_reason"),
        phase_metadata=None,
        session_notes=session_data["session_notes"],
        coaching_intent=session_data["coaching_intent"],
        coaching_flags=list(session_data.get("coaching_flags", [])),
        is_ad_hoc=False,
        ad_hoc_request_payload=None,
    )


# ─── Layer4Payload composition (Pattern B plan_refresh) ──────────────────────


def _build_layer4_payload(
    *,
    user_id: int,
    sessions: list[PlanSession],
    plan_version_id: int,
    scope_start: _date_type,
    scope_end: _date_type,
    model: str,
    temperature: float,
    validator_results: list[ValidatorResult],
    notable_observations: list[Observation],
    etl_version_set: dict[str, str],
    input_tokens_total: int,
    output_tokens_total: int,
    latency_ms_total: int,
    llm_call_count: int,
) -> Layer4Payload:
    """Compose the final Layer4Payload per `Layer4_Spec.md` §3.2:
    `mode='plan_refresh'`, `pattern='B'` for T1/T2, `phase_structure=None`,
    `seam_reviews=None`, each session has `phase_metadata=None`."""
    return Layer4Payload(
        user_id=user_id,
        mode="plan_refresh",
        plan_version_id=plan_version_id,
        scope_start_date=scope_start,
        scope_end_date=scope_end,
        model_synthesizer=model,
        model_seam_reviewer=None,
        temperature=temperature,
        pattern="B",
        latency_ms_total=latency_ms_total,
        input_tokens_total=input_tokens_total,
        output_tokens_total=output_tokens_total,
        llm_call_count=llm_call_count,
        etl_version_set=etl_version_set,
        sessions=sessions,
        phase_structure=None,
        seam_reviews=None,
        shape_override=None,
        validator_results=validator_results,
        notable_observations=notable_observations,
        suggestion_id=None,
        race_week_brief=None,
        race_plan=None,
    )


def _build_payload_for_validation(
    *,
    user_id: int,
    sessions: list[PlanSession],
    plan_version_id: int,
    scope_start: _date_type,
    scope_end: _date_type,
    model: str,
    temperature: float,
    etl_version_set: dict[str, str],
) -> Layer4Payload:
    """Build a Layer4Payload mid-retry for validator-input purposes with a
    placeholder accepted ValidatorResult so the payload's
    `validator_results[-1].accepted` invariant doesn't trip during
    construction. The real validator pass runs against this payload."""
    return Layer4Payload(
        user_id=user_id,
        mode="plan_refresh",
        plan_version_id=plan_version_id,
        scope_start_date=scope_start,
        scope_end_date=scope_end,
        model_synthesizer=model,
        model_seam_reviewer=None,
        temperature=temperature,
        pattern="B",
        latency_ms_total=0,
        input_tokens_total=0,
        output_tokens_total=0,
        llm_call_count=0,
        etl_version_set=etl_version_set,
        sessions=sessions,
        phase_structure=None,
        seam_reviews=None,
        shape_override=None,
        validator_results=[
            ValidatorResult(
                pass_index=0,
                accepted=True,
                rule_failures=[],
                retried_phase_names=[],
            )
        ],
        notable_observations=[],
        suggestion_id=None,
        race_week_brief=None,
        race_plan=None,
    )


def _emit_intensity_modulated_observation(
    sessions: list[PlanSession],
) -> Observation | None:
    """Per §8.6/§8.7 (2026-05-17 broadening to plan_refresh): when the
    synthesizer emitted the `intensity_modulated` session coaching_flag on
    any session in the refresh output, the orchestrator side emits a single
    paired `Observation(category='intensity_modulated')`. Returns None when
    no session carries the flag."""
    affected = [
        s.session_id for s in sessions if "intensity_modulated" in s.coaching_flags
    ]
    if not affected:
        return None
    return Observation(
        category="intensity_modulated",
        text=(
            "Synthesizer modulated the prescribed intensity on "
            f"{len(affected)} session(s); see session_notes for the rationale."
        ),
        evidence_basis=["Layer4_Spec.md §8.6 + §8.7"],
        elevates_to_hitl=False,
    )


def _build_validator_context(
    layer2_bundle: Layer2Bundle,
    layer3a_payload: Layer3APayload,
    layer3b_payload: Layer3BPayload,
    capacity_hours: float | None = None,
    owned_gear: frozenset[str] = frozenset(),
) -> ValidatorContext:
    """Bundle Layer2Bundle + 3A + 3B into a ValidatorContext for the §5.4
    rule harness. Per `Layer4_RefreshT1_v1.md` §6 + `Layer4_RefreshT2_v1.md`
    §6: the validator reads 2A (volume bands), 2C (locale equipment views),
    2D (injury exclusions + accommodations), 3A (ACWR / recent load), 3B
    (periodization shape + intensity-distribution targets). `capacity_hours`
    (the athlete's bounded weekly hours) converts 2A's percentage bands into
    the hour targets `volume_band` checks against."""
    return ValidatorContext(
        layer2a_payload=layer2_bundle.a,
        layer2b_payload=layer2_bundle.b,
        layer2c_payloads=dict(layer2_bundle.c),
        layer2d_payload=layer2_bundle.d,
        layer2e_payload=layer2_bundle.e,
        layer3a_payload=layer3a_payload,
        layer3b_payload=layer3b_payload,
        capacity_hours=capacity_hours,
        owned_gear=owned_gear,
    )


# ─── Entry point: llm_layer4_plan_refresh ────────────────────────────────────


def llm_layer4_plan_refresh(
    user_id: int,
    tier: Literal["T1", "T2", "T3"],
    refresh_scope_start: _date_type,
    refresh_scope_end: _date_type,
    layer1_payload: dict[str, Any],
    layer2_bundle: Layer2Bundle,
    layer3a_payload: Layer3APayload,
    layer3b_payload: Layer3BPayload,
    prior_plan_session_window: list[PlanSession],
    parsed_intent: ParsedIntent | None,
    plan_version_id: int,
    plan_version_id_parent: int,
    etl_version_set: dict[str, str],
    *,
    plan_start_date: _date_type | None = None,
    training_substitution_payload: TrainingSubstitutionPayload | None = None,
    terrain_feasibility: dict[str, Any] | None = None,
    event_window_segments: list[Any] | None = None,
    model_synthesizer: str = "claude-sonnet-4-6",
    model_seam_reviewer: str | None = None,
    temperature: float = 0.4,
    max_tokens: int | None = None,
    capped_retries: int = 2,
    extended_thinking_budget: int | None = None,
    llm_caller: LLMCaller | None = None,
    phase_caller: Any | None = None,
    seam_caller: Any | None = None,
    cache: Any | None = None,
    call_cache_key: str | None = None,
    executor: Any | None = None,
) -> Layer4Payload:
    """Pattern B plan-refresh entrypoint per `Layer4_Spec.md` §3.2.

    Dispatches on `tier` to the tier-specific synthesizer plumbing in
    `plan_refresh_t1.py` (T1), `plan_refresh_t2.py` (T2), or
    `plan_refresh_t3.py` (T3 intra-phase). T3 cross-phase raises
    `Layer4InputError('tier_t3_cross_phase_requires_pattern_a')` until
    Step 4f lands Pattern A orchestration for refresh.

    Algorithm (§5.3 Pattern B + §5.5 capped retry):
    1. Validate inputs per §4.3 — raises `Layer4InputError` on precondition
       fail. `layer3b_payload` required for all tiers (Andy 2026-05-17
       §4.3-wins pick). `plan_start_date` required when tier='T3' (Step 4d
       amendment).
    2. For T3: compute `phase_structure_from_3b()`; route intra-phase scope
       to Pattern B; raise on cross-phase scope.
    3. Build tier-specific user prompt + tool schema.
    4. Invoke synthesizer; parse `record_refresh_sessions` tool output into
       `list[PlanSession]`; wrap into a Layer4Payload.
    5. Run §5.4 deterministic validator harness with the 21-rule set;
       weekly-aggregate rules (volume_band + intensity_dist) are
       load-bearing at T2 + T3 scope; ACWR forward projection is
       load-bearing at T3 scope.
    6. On validator failure, retry up to `capped_retries` (default 2) with
       `RuleFailure` context merged into the user prompt per D8.
    7. On cap-hit with unresolved blockers: ship the latest synthesis as
       best-effort with an orchestrator-emitted
       `Observation(category='best_effort_plan', elevates_to_hitl=True)`;
       outstanding `blocker`-severity failures demote to `warning`.
    8. Emit `Observation(category='intensity_modulated', elevates_to_hitl=
       False)` per §8.6/§8.7 when any session carries the
       `intensity_modulated` coaching flag.

    `model_seam_reviewer` is reserved for T3 cross-phase Pattern A routing
    (Step 4f); ignored on T1/T2/T3-intra-phase Pattern B. `parsed_intent=None`
    is permitted — D-64 degrades gracefully when the NL parser is
    unavailable (per `Plan_Refresh_D64_Design_v1.md` §5.4).
    """
    _validate_inputs(
        tier,
        refresh_scope_start,
        refresh_scope_end,
        layer1_payload,
        layer2_bundle,
        layer3a_payload,
        layer3b_payload,
        prior_plan_session_window,
        plan_version_id_parent,
        plan_start_date,
    )

    # T3 dispatch: compute phase structure; route intra-phase to Pattern B;
    # delegate cross-phase to Pattern A engine per §6.3 (Step 4f closed the
    # `tier_t3_cross_phase_requires_pattern_a` raise path 2026-05-18).
    dominant_phase_name: str | None = None
    dominant_phase_start_date: _date_type | None = None
    dominant_phase_end_date: _date_type | None = None
    if tier == "T3":
        from layer4.phase_structure import (
            phase_for_date,
            phase_structure_from_3b,
            scope_spans_phase_boundary,
        )

        assert plan_start_date is not None  # _validate_inputs guards this
        phase_structure = phase_structure_from_3b(layer3b_payload, plan_start_date)
        if scope_spans_phase_boundary(
            phase_structure, refresh_scope_start, refresh_scope_end
        ):
            # Cross-phase T3 routes to Pattern A engine in plan_create.py.
            # Phases overlapping the refresh scope get re-synthesized; phases
            # outside the scope carry their prior-plan sessions over as
            # boundary context per §6.3.
            return _route_t3_cross_phase_to_pattern_a(
                user_id=user_id,
                phase_structure=phase_structure,
                refresh_scope_start=refresh_scope_start,
                refresh_scope_end=refresh_scope_end,
                layer1_payload=layer1_payload,
                layer2_bundle=layer2_bundle,
                layer3a_payload=layer3a_payload,
                layer3b_payload=layer3b_payload,
                prior_plan_session_window=prior_plan_session_window,
                plan_version_id=plan_version_id,
                etl_version_set=etl_version_set,
                terrain_feasibility=terrain_feasibility,
                event_window_segments=event_window_segments,
                model_synthesizer=model_synthesizer,
                model_seam_reviewer=(
                    model_seam_reviewer or "claude-sonnet-4-6"
                ),
                temperature=temperature,
                capped_retries=capped_retries,
                phase_caller=phase_caller,
                seam_caller=seam_caller,
                cache=cache,
                call_cache_key=call_cache_key,
                executor=executor,
            )
        phase_at_start = phase_for_date(phase_structure, refresh_scope_start)
        assert phase_at_start is not None  # scope_spans_phase_boundary already verified
        dominant_phase_name = phase_at_start.phase_name
        dominant_phase_start_date = phase_at_start.start_date
        dominant_phase_end_date = phase_at_start.end_date

    # Lazy-import the tier module to keep cross-imports clean.
    if tier == "T1":
        from layer4 import plan_refresh_t1 as tier_module
    elif tier == "T2":
        from layer4 import plan_refresh_t2 as tier_module
    else:
        from layer4 import plan_refresh_t3 as tier_module

    # Size the output budget to the tier's session ceiling, reusing the create
    # path's per-block sizing (`per_phase.block_output_budget`) instead of a flat
    # per-tier constant. A T3 cross-phase block emits up to 56 sessions and
    # truncated `record_refresh_sessions` against the old flat 10000 ceiling
    # (`schema_violation` at `stop_reason=max_tokens` → cron retry loop, never
    # `ready`). The tier `DEFAULT_MAX_TOKENS` is the floor; the helper raises it to
    # fit the block and clamps to the model's 64K output ceiling. T3 runs thinking
    # off (its `DEFAULT_EXTENDED_THINKING_BUDGET`) so the 64K output budget isn't
    # pushed past the model ceiling by a stacked thinking budget.
    floor = max_tokens if max_tokens is not None else tier_module.DEFAULT_MAX_TOKENS
    effective_max_tokens = block_output_budget(_TIER_MAX_SESSIONS[tier], floor=floor)
    effective_thinking = (
        extended_thinking_budget
        if extended_thinking_budget is not None
        else tier_module.DEFAULT_EXTENDED_THINKING_BUDGET
    )
    system_prompt = tier_module.SYSTEM_PROMPT
    # #337 — structured cardio prescription: append the shared `# Cardio
    # programming` section (warm-up/work/cool-down structure + ground intensity
    # targets in the athlete's measured physiology) so refresh has the same
    # fidelity as plan generation. Unconditional (general cardio guidance, not
    # pool-gated); centralized here so the three tier modules stay untouched.
    system_prompt = system_prompt + "\n\n" + CARDIO_PROGRAMMING_PROMPT_SECTION
    # #339 — equivalent-discipline variety carve-out (easy foot-based sessions
    # only; gated on the athlete's `Coaching memory` block, appended below).
    # Centralized here so the three tier modules stay untouched, mirroring the
    # cardio-section append above.
    system_prompt = system_prompt + "\n\n" + VARIETY_CARVEOUT_PROMPT_SECTION
    feasible_pool_ids = compute_feasible_pool_ids(
        dict(layer2_bundle.c), layer2_bundle.d
    )
    # #698 Track 2 (Slice C2) — give refresh the SAME cardio-drill fidelity as
    # plan generation: rendered menu + enum-bind + the ratified prompt section,
    # centralized here so the three tier prompt modules stay untouched. The
    # discipline set is the athlete's included disciplines (2A; falls back to the
    # union of the 2C-resolved disciplines if 2A is absent). The phase is the
    # periodization phase covering the refresh window — true plan-create fidelity,
    # so skill/transition drills drop in Peak/Taper — reusing the T3 dominant
    # phase when known, else derived from 3B + plan_start_date, else permissive
    # "Base" (a T1/T2 refresh with no plan_start_date). T3 cross-phase already
    # returned to the Pattern A engine above, which carries its own drill pool.
    drill_disciplines: set[str] = (
        {
            d.discipline_id
            for d in layer2_bundle.a.disciplines
            if d.inclusion == "included"
        }
        if layer2_bundle.a is not None
        else {
            disc
            for l2c in layer2_bundle.c.values()
            for rx in l2c.exercises_resolved
            for disc in rx.discipline_ids
        }
    )
    drill_phase = dominant_phase_name or "Base"
    if dominant_phase_name is None and plan_start_date is not None:
        from layer4.phase_structure import phase_for_date, phase_structure_from_3b

        _drill_ps = phase_structure_from_3b(layer3b_payload, plan_start_date)
        _drill_phase_obj = phase_for_date(_drill_ps, refresh_scope_start)
        if _drill_phase_obj is not None:
            drill_phase = _drill_phase_obj.phase_name
    owned_gear = frozenset((layer1_payload or {}).get("owned_gear") or [])
    cardio_drill_pool_ids = compute_cardio_drill_pool_ids(
        dict(layer2_bundle.c),
        layer2_bundle.d,
        disciplines=drill_disciplines,
        phase=drill_phase,
        owned_gear=owned_gear,
    )
    cardio_drill_pool_lines = _format_cardio_drill_pool(
        dict(layer2_bundle.c),
        layer2_bundle.a,
        layer2_bundle.d,
        disciplines=drill_disciplines,
        phase=drill_phase,
        owned_gear=owned_gear,
    )
    # Suppress-on-empty: only carry the drill instructions when a menu renders,
    # so the LLM is never handed an unfillable cardio_drills[] (mirrors §6a-G1).
    if cardio_drill_pool_lines:
        system_prompt = system_prompt + "\n\n" + CARDIO_DRILLS_PROMPT_SECTION
    tool_schema = build_record_refresh_sessions_tool(
        tier,
        feasible_pool_ids=feasible_pool_ids or None,
        cardio_drill_pool_ids=cardio_drill_pool_ids or None,
    )
    caller: LLMCaller = llm_caller or _default_llm_caller

    effective_intent = parsed_intent or _default_parsed_intent()

    rule_failures: list[RuleFailure] = []
    validator_results: list[ValidatorResult] = []
    session_id_prefix = uuid.uuid4().hex[:8]

    total_input_tokens = 0
    total_output_tokens = 0
    total_latency_ms = 0
    llm_call_count = 0
    cap_hit = False

    latest_sessions: list[PlanSession] | None = None
    latest_validator: ValidatorResult | None = None

    for retries_used in range(capped_retries + 1):
        # T3 takes additional dominant-phase kwargs for the §3.5 prompt
        # block; T1/T2 don't accept those — pass conditionally.
        extra_kwargs: dict[str, Any] = {}
        if tier == "T3":
            extra_kwargs = {
                "dominant_phase_name": dominant_phase_name,
                "dominant_phase_start_date": dominant_phase_start_date,
                "dominant_phase_end_date": dominant_phase_end_date,
            }

        user_prompt = tier_module.render_user_prompt(
            refresh_scope_start=refresh_scope_start,
            refresh_scope_end=refresh_scope_end,
            layer1_payload=layer1_payload,
            layer2_bundle=layer2_bundle,
            layer3a_payload=layer3a_payload,
            layer3b_payload=layer3b_payload,
            prior_plan_session_window=prior_plan_session_window,
            parsed_intent=effective_intent,
            retries_used=retries_used,
            rule_failures=rule_failures,
            training_substitution_payload=training_substitution_payload,
            terrain_feasibility=terrain_feasibility,
            event_window_segments=event_window_segments,
            **extra_kwargs,
        )
        # #698 Track 2 (Slice C2) — append the rendered drill menu (grouped by
        # discipline, carrying each row's coaching_cue dose), the same menu the
        # plan-create path renders. Centralized append keeps the tier render
        # functions untouched. Suppressed when the pool resolves empty.
        if cardio_drill_pool_lines:
            user_prompt += (
                "\n\n=== Cardio drill pool (consider these) ===\n"
                "Optionally attach one drill appropriate to the session's "
                "discipline, from the pool below (pick by id only):\n"
                + "\n".join(cardio_drill_pool_lines)
            )
        # #337 — measured physiological anchors so the synthesizer grounds
        # intensity_target numbers in real values (suppress-on-empty);
        # centralized append, the same fidelity as the plan-create path.
        physiology_lines = format_measured_physiology(layer1_payload)
        if physiology_lines:
            user_prompt += "\n\n=== Measured physiology ===\n" + "\n".join(
                physiology_lines
            )
        print(
            "plan_refresh _synthesize_refresh_tier: measured_physiology "
            f"surfaced={bool(physiology_lines)}"
        )
        # #307 — surface the upstream Layer 2A/2B/2C/2D coaching_flags
        # advisory channel (suppress-on-empty).
        upstream_flag_lines = format_upstream_coaching_flags(
            layer2a=layer2_bundle.a,
            layer2b=layer2_bundle.b,
            layer2c_payloads=layer2_bundle.c.values(),
            layer2d=layer2_bundle.d,
        )
        if upstream_flag_lines:
            user_prompt += (
                "\n\n=== Upstream coaching flags ===\n"
                + "\n".join(upstream_flag_lines)
            )
        # #339 — surface the durable Coaching Memory block on the refresh path
        # too (#690 rendered it on plan-create only), so a stated variety
        # preference reaches the carve-out above (suppress-on-empty).
        coaching_memory_lines = _format_coaching_memory(layer1_payload)
        if coaching_memory_lines:
            user_prompt += "\n\n" + "\n".join(coaching_memory_lines)

        llm_out = caller(
            system_prompt,
            user_prompt,
            tool_schema,
            model_synthesizer,
            temperature,
            effective_max_tokens,
            effective_thinking,
        )

        llm_call_count += 1
        total_input_tokens += llm_out.input_tokens
        total_output_tokens += llm_out.output_tokens
        total_latency_ms += llm_out.latency_ms

        raw_sessions = llm_out.tool_args.get("sessions")
        if not isinstance(raw_sessions, list):
            raise Layer4OutputError(
                "schema_violation",
                detail="tool args missing 'sessions' array",
            )

        # #803 — set strength resolution metadata deterministically from each
        # pick's 2C resolution before construction (mirrors per_phase).
        # layer2_bundle.c is the per-locale 2C map.
        _res_notes = _apply_strength_resolution(raw_sessions, dict(layer2_bundle.c))
        if _res_notes:
            print(
                "llm_layer4_plan_refresh: strength resolution defaulted to exact "
                f"for unresolved picks: {', '.join(_res_notes)}"
            )

        try:
            sessions = [
                _build_plan_session(
                    s,
                    session_id=f"S-{session_id_prefix}-{i:03d}",
                    plan_version_id=plan_version_id,
                )
                for i, s in enumerate(raw_sessions)
            ]
        except (ValidationError, KeyError, ValueError, TypeError) as e:
            # Schema-violation special case per §5.5: ONE retry on malformed
            # output that doesn't consume the per-call budget. Bail on the
            # second failure.
            if retries_used >= capped_retries:
                raise Layer4OutputError(
                    "schema_violation",
                    detail=f"tool output did not parse as PlanSession list: {e}",
                )
            rule_failures = [
                RuleFailure(
                    rule_name="schema_violation",
                    phase_name=None,
                    severity="blocker",
                    detail=str(e)[:240],
                    affected_session_ids=[],
                )
            ]
            continue

        latest_sessions = sessions

        # Empty sessions list short-circuits validator (no sessions to validate)
        # — `Layer4Payload._check_validator_results` still requires accepted
        # final pass, which we synthesize manually below.
        if not sessions:
            empty_result = ValidatorResult(
                pass_index=retries_used,
                accepted=True,
                rule_failures=[],
                retried_phase_names=[],
            )
            validator_results.append(empty_result)
            latest_validator = empty_result
            break

        payload_attempt = _build_payload_for_validation(
            user_id=user_id,
            sessions=sessions,
            plan_version_id=plan_version_id,
            scope_start=refresh_scope_start,
            scope_end=refresh_scope_end,
            model=model_synthesizer,
            temperature=temperature,
            etl_version_set=etl_version_set,
        )
        ctx = _build_validator_context(
            layer2_bundle,
            layer3a_payload,
            layer3b_payload,
            capacity_hours=weekly_capacity_hours(layer1_payload),
            owned_gear=frozenset((layer1_payload or {}).get("owned_gear") or []),
        )
        validator_result = validate_layer4_payload(
            payload_attempt, ctx, pass_index=retries_used
        )
        validator_results.append(validator_result)
        latest_validator = validator_result

        if validator_result.accepted:
            break

        rule_failures = list(validator_result.rule_failures)
        if retries_used == capped_retries:
            cap_hit = True

    assert latest_sessions is not None and latest_validator is not None
    assert validator_results, "validator_results must be non-empty"

    notable_observations: list[Observation] = []
    if cap_hit and not latest_validator.accepted:
        demoted = [
            RuleFailure(
                rule_name=f.rule_name,
                phase_name=f.phase_name,
                severity="warning",
                detail=f.detail,
                affected_session_ids=f.affected_session_ids,
            )
            for f in latest_validator.rule_failures
        ]
        best_effort = ValidatorResult(
            pass_index=latest_validator.pass_index + 1,
            accepted=True,
            rule_failures=demoted,
            retried_phase_names=[],
        )
        validator_results.append(best_effort)
        notable_observations.append(
            Observation(
                category="best_effort_plan",
                text=(
                    "Validator cap hit; latest synthesis accepted as best-effort. "
                    "Outstanding blocker-severity failures demoted to warning."
                ),
                evidence_basis=["Layer4_Spec.md §5.5"],
                elevates_to_hitl=True,
            )
        )

    intensity_obs = _emit_intensity_modulated_observation(latest_sessions)
    if intensity_obs is not None:
        notable_observations.append(intensity_obs)

    return _build_layer4_payload(
        user_id=user_id,
        sessions=latest_sessions,
        plan_version_id=plan_version_id,
        scope_start=refresh_scope_start,
        scope_end=refresh_scope_end,
        model=model_synthesizer,
        temperature=temperature,
        validator_results=validator_results,
        notable_observations=notable_observations,
        etl_version_set=etl_version_set,
        input_tokens_total=total_input_tokens,
        output_tokens_total=total_output_tokens,
        latency_ms_total=total_latency_ms,
        llm_call_count=llm_call_count,
    )


def _route_t3_cross_phase_to_pattern_a(
    *,
    user_id: int,
    phase_structure: Any,
    refresh_scope_start: _date_type,
    refresh_scope_end: _date_type,
    layer1_payload: dict[str, Any],
    layer2_bundle: Layer2Bundle,
    layer3a_payload: Layer3APayload,
    layer3b_payload: Layer3BPayload,
    prior_plan_session_window: list[PlanSession],
    plan_version_id: int,
    etl_version_set: dict[str, str],
    terrain_feasibility: dict[str, Any] | None = None,
    event_window_segments: list[Any] | None = None,
    model_synthesizer: str,
    model_seam_reviewer: str,
    temperature: float,
    capped_retries: int,
    phase_caller: Any | None,
    seam_caller: Any | None,
    cache: Any | None = None,
    call_cache_key: str | None = None,
    executor: Any | None = None,
) -> Layer4Payload:
    """Delegate T3 cross-phase refresh to the Pattern A engine in
    plan_create.py per `Layer4_Spec.md` §6.3 (Step 4f).

    Identifies which phase indices overlap [refresh_scope_start,
    refresh_scope_end] and synthesizes those; phases outside the scope keep
    their prior-plan sessions (read from `prior_plan_session_window`) as
    boundary context for seam reviews.
    """
    from layer4.plan_create import synthesize_pattern_a_for_refresh

    # Determine which phase indices overlap the refresh scope.
    phase_indices_to_synthesize: list[int] = []
    for i, phase in enumerate(phase_structure.phases):
        # Phase overlaps refresh scope iff their date ranges intersect.
        if (
            phase.end_date >= refresh_scope_start
            and phase.start_date <= refresh_scope_end
        ):
            phase_indices_to_synthesize.append(i)

    # Bucket prior_plan_session_window sessions into the non-synthesized
    # phases (carryover for seam-review boundary context).
    carryover_sessions: dict[int, list[PlanSession]] = {}
    for i, phase in enumerate(phase_structure.phases):
        if i in phase_indices_to_synthesize:
            continue
        in_phase = [
            s
            for s in prior_plan_session_window
            if phase.start_date <= s.date <= phase.end_date
        ]
        if in_phase:
            carryover_sessions[i] = in_phase

    return synthesize_pattern_a_for_refresh(
        user_id=user_id,
        layer1_payload=layer1_payload,
        layer2a_payload=layer2_bundle.a,
        layer2b_payload=layer2_bundle.b,
        layer2c_payloads=dict(layer2_bundle.c),
        layer2d_payload=layer2_bundle.d,
        layer2e_payload=layer2_bundle.e,
        layer3a_payload=layer3a_payload,
        layer3b_payload=layer3b_payload,
        race_event_payload=None,
        phase_structure=phase_structure,
        phase_indices_to_synthesize=phase_indices_to_synthesize,
        carryover_sessions_by_phase_index=carryover_sessions,
        refresh_scope_start=refresh_scope_start,
        refresh_scope_end=refresh_scope_end,
        plan_version_id=plan_version_id,
        etl_version_set=etl_version_set,
        terrain_feasibility=terrain_feasibility,
        event_window_segments=event_window_segments,
        model_synthesizer=model_synthesizer,
        model_seam_reviewer=model_seam_reviewer,
        temperature=temperature,
        capped_retries_per_phase=capped_retries,
        phase_caller=phase_caller,
        seam_caller=seam_caller,
        cache=cache,
        call_cache_key=call_cache_key,
        executor=executor,
    )


def _default_parsed_intent() -> ParsedIntent:
    """Per `Plan_Refresh_D64_Design_v1.md` §5.4: when the parser is
    unavailable, D-64 returns a degraded ParsedIntent with all flags FALSE,
    signals at default, parser_confidence='low'. Layer 4 mirrors that
    default when the caller passes parsed_intent=None."""
    return ParsedIntent(
        parser_confidence="low",
        ambiguity_notes="Parser unavailable; running default cascade only.",
    )


__all__ = [
    "LLMCaller",
    "build_record_refresh_sessions_tool",
    "llm_layer4_plan_refresh",
]
