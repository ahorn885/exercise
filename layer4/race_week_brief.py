"""Layer 4 — `llm_layer4_race_week_brief` race-week brief synthesizer
(D-66 caller integration, Step 4e of `Layer4_Spec.md` §14.3.4).

Implements `Layer4_Spec.md` §3.4 (race-week-brief entry-point signature
including the D-66 amendment `race_event_payload: RaceEventPayload`
positional arg), §4.5 (input validation preconditions including 2 new D-66
rows), §5.3 (Pattern B single-call algorithm), §5.5 (capped retry; cap=2
default), §7.13 (RaceWeekBrief schema), §7.14 (RacePlan schema multi-day
only), §8.5 (spec-auto Taper coaching flags handled orchestrator-side
post-synthesis), §8.6 (`intensity_modulated` + `discipline_specific_intensity`
LLM-emittable), §8.7 (`opportunity` LLM-emitted exception; `data_gap`
orchestrator-emitted on §4.5 soft-fail; `intensity_modulated` orchestrator
bubble).

Pattern B in v1 even for multi-day events: the brief covers the Taper
window only (≤ 14 days = ≤ 1 phase). Pattern A's per-phase machinery is
unnecessary for a single phase.

The race-week-brief synthesizer emits three coordinated artifacts in a
single `record_race_week_brief` tool call:
1. `taper_session_overrides` — modified Taper-phase PlanSessions
   (orchestrator post-stamps the 5 spec-auto Taper flags per §8.5).
2. `race_week_brief` — structured RaceWeekBrief per §7.13 (always emitted).
3. `race_plan` — structured RacePlan per §7.14 (multi-day events only:
   continuous_multi_day / stage_race).

**D-66 contract (2026-05-18):** The `race_event_payload: RaceEventPayload`
arg carries the route-locale graph + the merged free-text race `notes` (race
rules + mandatory gear + context, per #439) + distance/elevation. Layer 3B
continues to expose race_format / event_date / event_locale_id /
time_to_event_weeks for periodization decisions; the race_event_payload arg
carries the brief-rendering-relevant surface. See
`Race_Events_D66_Design_v1.md` §4.

**Layer 1 payload handling (v1).** `Layer1Payload` is opaque `dict[str, Any]`
per the PR-D + Step 4a/b/c/d precedent (Layer 1 typed contract out of v1
scope). The prompt template reads specific keys (`experience_level`,
`travel_constraint`, `sleep_baseline`) and renders missing keys as empty
placeholders.

**Tool-schema fidelity (Step 4a precedent).** The `record_race_week_brief`
tool schema mirrors the full `RaceWeekBrief` + `RacePlan` + Taper-session
override contracts from `layer4/payload.py` rather than the sketch in
`Layer4_RaceWeekBrief_v1.md` §4.1 (which was drafted before the D1
amendment + D-66). Paired with the `Layer4_RaceWeekBrief_v2.md` prompt
body amendment for source-pointer + route-locale rendering updates.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import date as _date_type, datetime
from typing import Any, Callable

from pydantic import ValidationError

from llm_invocation import ThinkingToolCallError, invoke_tool_call
from layer4.context import (
    Layer2APayload,
    Layer2BPayload,
    Layer2CPayload,
    Layer2DPayload,
    Layer2EPayload,
    Layer3APayload,
    Layer3BPayload,
    RaceEventPayload,
    TrainingSubstitutionPayload,
)
from layer4.errors import Layer4InputError, Layer4OutputError
from layer4.recovery_guidance import format_recovery_guidance
from layer4.per_phase import (
    VARIETY_CARVEOUT_PROMPT_SECTION,
    compute_feasible_pool_ids,
    compute_recovery_pool_ids,
    format_upstream_coaching_flags,
    _apply_strength_resolution,
    _format_coaching_memory,
    _recovery_pool_entries,
    _repair_recovery_exercises,
)
from layer4.payload import (
    CardioBlock,
    Contingency,
    FuelingStrategy,
    KitItem,
    Layer4Payload,
    Observation,
    PacingStrategy,
    PlanSession,
    RacePlan,
    RaceSegment,
    RaceWeekBrief,
    RecoveryExercise,
    RuleFailure,
    StrengthExercise,
    TransitionSpec,
    ValidatorResult,
)
from layer4.validator import (
    ValidatorContext,
    validate_layer4_payload,
    weekly_capacity_hours,
)
from weather_client import ExpectedConditions, Fetcher, get_expected_conditions


# ─── Tool-use schema (Layer4_RaceWeekBrief_v2 §4.1) ──────────────────────────


def _intensity_target_schema() -> dict[str, Any]:
    """Discriminated `IntensityTarget` union per `Layer4_Spec.md` §7.3.1
    (D1 amendment 2026-05-17). Same as single_session.py — extracted here
    to keep the schema literal close to the tool builder; `pacing_target`
    on `RaceSegment` uses the same union per §7.14."""
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


def _taper_override_session_schema(
    feasible_pool_ids: list[str] | None = None,
    recovery_pool_ids: list[str] | None = None,
) -> dict[str, Any]:
    """Schema for one Taper-session override per `Layer4_RaceWeekBrief_v2.md`
    §4.1. Mirrors `PlanSession` shape with the closed 2-flag race-week-brief
    enum (`intensity_modulated`, `discipline_specific_intensity`) per
    `Layer4_Spec.md` §8.6 — spec-auto Taper flags (§8.5) are orchestrator-
    stamped post-synthesis.

    Track 2 D1: when `feasible_pool_ids` is non-empty, the
    `strength_exercises.exercise_id` property is bounded by enum, making
    out-of-pool picks structurally impossible at the SDK boundary. #698 Track 1:
    `recovery_pool_ids` does the same for `recovery_exercises`, and `kind` gains
    `recovery` so a prior Taper recovery session can be echoed/trimmed (selection
    only — no D6 placement on this path, which has no grid)."""
    return {
        "type": "object",
        "additionalProperties": False,
        "required": [
            "session_id_to_override",
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
            "session_id_to_override": {"type": "string"},
            "date": {"type": "string", "format": "date"},
            "day_of_week": {
                "type": "string",
                "enum": ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"],
            },
            # #698 Track 1 — max→2 so a prior recovery session occupying the 3rd
            # daily slot (≤2 training + ≤1 recovery) can be echoed as an override
            # (mirrors `payload.PlanSession.session_index_in_day` le=2).
            "session_index_in_day": {"type": "integer", "minimum": 0, "maximum": 2},
            "time_of_day": {
                "type": "string",
                "enum": ["morning", "afternoon", "evening", "unspecified"],
            },
            "kind": {
                "type": "string",
                "enum": ["cardio", "strength", "rest", "recovery"],
            },
            "discipline_id": {"type": ["string", "null"]},
            "discipline_name": {"type": ["string", "null"]},
            "locale_id": {"type": ["string", "null"]},
            "locale_name": {"type": ["string", "null"]},
            "duration_min": {"type": "integer", "minimum": 0, "maximum": 360},
            "intensity_summary": {
                "type": "string",
                "enum": ["easy", "moderate", "hard", "mixed", "rest"],
            },
            "session_notes": {"type": "string", "maxLength": 240},
            "coaching_intent": {"type": "string", "maxLength": 200},
            "coaching_flags": {
                "type": "array",
                "items": {
                    "type": "string",
                    "enum": [
                        "intensity_modulated",
                        "discipline_specific_intensity",
                    ],
                },
                "maxItems": 2,
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
            # #698 Track 1 — structured recovery/mobility block (the analog of
            # strength_exercises). exercise_id is enum-bound to the recovery pool
            # when resolvable, so out-of-pool picks are structurally impossible at
            # the SDK boundary (mirrors `per_phase._session_schema`).
            "recovery_exercises": {
                "type": ["array", "null"],
                "items": {
                    "type": "object",
                    "additionalProperties": False,
                    "required": [
                        "exercise_id",
                        "exercise_name",
                        "prescription",
                        "instructions",
                    ],
                    "properties": {
                        "exercise_id": (
                            {"type": "string", "enum": recovery_pool_ids}
                            if recovery_pool_ids
                            else {"type": "string"}
                        ),
                        "exercise_name": {"type": "string"},
                        "prescription": {"type": "string", "maxLength": 120},
                        "instructions": {"type": "string", "maxLength": 240},
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


def _race_week_brief_schema() -> dict[str, Any]:
    """Schema for the always-emitted `race_week_brief` argument — mirrors
    the full `RaceWeekBrief` contract per `layer4/payload.py` §7.13 (Step 4a
    full-fidelity precedent). Includes the new `layer0_canonical` field on
    `KitItem` per the D-66 paired §7.13 amendment 2026-05-18."""
    return {
        "type": "object",
        "additionalProperties": False,
        "required": [
            "days_to_event",
            "event_name",
            "event_date",
            "event_locale",
            "race_format",
            "goal_outcome",
            "pre_race_logistics",
            "kit_manifest",
            "kit_check_dates",
            "race_day_fueling_plan",
            "pre_race_meal_strategy",
            "pacing_strategy_summary",
            "contingencies",
            "mental_prep_cues",
        ],
        "properties": {
            "days_to_event": {"type": "integer", "minimum": 0, "maximum": 14},
            "event_name": {"type": "string", "maxLength": 200},
            "event_date": {"type": "string", "format": "date"},
            "event_locale": {"type": "string", "maxLength": 200},
            "race_format": {
                "type": "string",
                "enum": [
                    "single_day",
                    "continuous_multi_day",
                    "stage_race",
                ],
            },
            "goal_outcome": {"type": "string", "maxLength": 120},
            "pre_race_logistics": {"type": "string", "maxLength": 300},
            "drop_bag_strategy": {"type": ["string", "null"], "maxLength": 240},
            "course_familiarization_notes": {
                "type": ["string", "null"],
                "maxLength": 280,
            },
            "kit_manifest": {
                "type": "array",
                "maxItems": 30,
                "items": {
                    "type": "object",
                    "additionalProperties": False,
                    "required": ["item", "purpose", "optional"],
                    "properties": {
                        "item": {"type": "string", "maxLength": 80},
                        "purpose": {"type": "string", "maxLength": 120},
                        "optional": {"type": "boolean"},
                        "layer0_canonical": {"type": "boolean"},
                    },
                },
            },
            "kit_check_dates": {
                "type": "array",
                "maxItems": 4,
                "items": {"type": "string", "format": "date"},
            },
            "race_day_fueling_plan": {"type": "string", "maxLength": 320},
            "pre_race_meal_strategy": {"type": "string", "maxLength": 280},
            "pacing_strategy_summary": {"type": "string", "maxLength": 200},
            "contingencies": {
                "type": "array",
                "minItems": 3,
                "maxItems": 8,
                "items": {"type": "string", "maxLength": 180},
            },
            "mental_prep_cues": {
                "type": "array",
                "minItems": 2,
                "maxItems": 5,
                "items": {"type": "string", "maxLength": 120},
            },
        },
    }


def _race_plan_schema() -> dict[str, Any]:
    """Schema for the conditionally-emitted `race_plan` argument — mirrors
    `RacePlan` per `layer4/payload.py` §7.14. Omitted (or null) for
    `race_format == 'single_day'`; required for multi-day events."""
    return {
        "type": ["object", "null"],
        "additionalProperties": False,
        "required": [
            "race_name",
            "race_start_datetime",
            "race_end_estimate_datetime",
            "race_format",
            "locales",
            "segments",
            "transitions",
            "pacing_strategy",
            "fueling_strategy",
            "contingencies",
        ],
        "properties": {
            "race_name": {"type": "string", "maxLength": 200},
            "race_start_datetime": {"type": "string", "format": "date-time"},
            "race_end_estimate_datetime": {"type": "string", "format": "date-time"},
            "race_format": {
                "type": "string",
                "enum": ["continuous_multi_day", "stage_race"],
            },
            "locales": {
                "type": "array",
                "minItems": 1,
                "items": {"type": "string"},
            },
            "segments": {
                "type": "array",
                "minItems": 2,
                "maxItems": 13,
                "items": {
                    "type": "object",
                    "additionalProperties": False,
                    "required": [
                        "segment_id",
                        "segment_index",
                        "sport",
                        "estimated_start_offset_hr",
                        "estimated_duration_min",
                        "terrain_notes",
                        "pacing_target",
                        "coaching_notes",
                    ],
                    "properties": {
                        "segment_id": {"type": "string"},
                        "segment_index": {"type": "integer", "minimum": 0},
                        "sport": {"type": "string"},
                        "estimated_start_offset_hr": {
                            "type": "number",
                            "minimum": 0,
                        },
                        "estimated_duration_min": {
                            "type": "integer",
                            "minimum": 5,
                            "maximum": 1800,
                        },
                        "distance_km": {"type": ["number", "null"], "minimum": 0},
                        "elevation_gain_m": {"type": ["number", "null"], "minimum": 0},
                        "terrain_notes": {"type": "string", "maxLength": 240},
                        "pacing_target": _intensity_target_schema(),
                        "coaching_notes": {"type": "string", "maxLength": 240},
                    },
                },
            },
            "transitions": {
                "type": "array",
                "items": {
                    "type": "object",
                    "additionalProperties": False,
                    "required": [
                        "from_segment_id",
                        "to_segment_id",
                        "estimated_duration_min",
                        "gear_changes",
                        "is_fueling_window",
                        "notes",
                    ],
                    "properties": {
                        "from_segment_id": {"type": "string"},
                        "to_segment_id": {"type": "string"},
                        "estimated_duration_min": {
                            "type": "integer",
                            "minimum": 0,
                            "maximum": 180,
                        },
                        "gear_changes": {
                            "type": "array",
                            "items": {"type": "string", "maxLength": 80},
                            "maxItems": 8,
                        },
                        "is_fueling_window": {"type": "boolean"},
                        "notes": {"type": "string", "maxLength": 200},
                    },
                },
            },
            "pacing_strategy": {
                "type": "object",
                "additionalProperties": False,
                "required": [
                    "overall_intensity_target",
                    "pacing_milestones",
                    "rationale_text",
                ],
                "properties": {
                    "overall_intensity_target": {"type": "string", "maxLength": 160},
                    "night_section_adjustment": {
                        "type": ["string", "null"],
                        "maxLength": 200,
                    },
                    "pacing_milestones": {
                        "type": "array",
                        "items": {"type": "string", "maxLength": 120},
                        "maxItems": 10,
                    },
                    "rationale_text": {"type": "string", "maxLength": 300},
                },
            },
            "fueling_strategy": {
                "type": "object",
                "additionalProperties": False,
                "required": [
                    "cho_g_per_hr_low",
                    "cho_g_per_hr_high",
                    "sodium_mg_per_hr",
                    "fluid_ml_per_hr",
                    "caffeine_strategy",
                    "rationale_text",
                ],
                "properties": {
                    "cho_g_per_hr_low": {
                        "type": "integer",
                        "minimum": 0,
                        "maximum": 200,
                    },
                    "cho_g_per_hr_high": {
                        "type": "integer",
                        "minimum": 0,
                        "maximum": 200,
                    },
                    "sodium_mg_per_hr": {
                        "type": "integer",
                        "minimum": 0,
                        "maximum": 3000,
                    },
                    "fluid_ml_per_hr": {
                        "type": "integer",
                        "minimum": 0,
                        "maximum": 2000,
                    },
                    "caffeine_strategy": {"type": "string", "maxLength": 200},
                    "night_section_strategy": {
                        "type": ["string", "null"],
                        "maxLength": 240,
                    },
                    "rationale_text": {"type": "string", "maxLength": 300},
                },
            },
            "contingencies": {
                "type": "array",
                "minItems": 4,
                "maxItems": 12,
                "items": {
                    "type": "object",
                    "additionalProperties": False,
                    "required": ["trigger", "action_plan", "threshold_to_invoke"],
                    "properties": {
                        "trigger": {"type": "string", "maxLength": 160},
                        "action_plan": {"type": "string", "maxLength": 200},
                        "threshold_to_invoke": {"type": "string", "maxLength": 120},
                    },
                },
            },
        },
    }


def build_record_race_week_brief_tool(
    feasible_pool_ids: list[str] | None = None,
    recovery_pool_ids: list[str] | None = None,
) -> dict[str, Any]:
    """The `record_race_week_brief` Anthropic tool definition per
    `Layer4_RaceWeekBrief_v2.md` §4.1 — mirrors the full `RaceWeekBrief`
    + `RacePlan` + Taper-session override contracts from `layer4/payload.py`.

    Track 2 D1: `feasible_pool_ids` (when non-empty) bounds
    `strength_exercises.exercise_id` via JSON-schema enum. Production callers
    pass `compute_feasible_pool_ids(layer2c_payloads, layer2d_payload)`. #698
    Track 1: `recovery_pool_ids` (when non-empty) bounds
    `recovery_exercises.exercise_id` the same way
    (`compute_recovery_pool_ids(layer2c_payloads, layer2d_payload)`)."""
    return {
        "name": "record_race_week_brief",
        "description": (
            "Record the race-week brief — modified Taper-phase sessions, "
            "the structured RaceWeekBrief, and (for multi-day events only) "
            "the structured RacePlan. Emit exactly one tool call per invocation."
        ),
        "input_schema": {
            "type": "object",
            "additionalProperties": False,
            "required": ["taper_session_overrides", "race_week_brief"],
            "properties": {
                "taper_session_overrides": {
                    "type": "array",
                    "maxItems": 42,
                    "items": _taper_override_session_schema(
                        feasible_pool_ids, recovery_pool_ids
                    ),
                },
                "race_week_brief": _race_week_brief_schema(),
                "race_plan": _race_plan_schema(),
                "opportunities": {
                    "type": "array",
                    "maxItems": 2,
                    "items": {
                        "type": "object",
                        "additionalProperties": False,
                        "required": ["text"],
                        "properties": {
                            "text": {"type": "string", "maxLength": 240},
                            "evidence_basis": {
                                "type": "array",
                                "items": {"type": "string"},
                                "maxItems": 3,
                            },
                        },
                    },
                },
            },
        },
    }


# ─── Input validation (Layer4_Spec.md §4.5) ──────────────────────────────────


_MAX_DAYS_TO_EVENT = 14
_MULTI_DAY_FORMATS = frozenset(
    {"continuous_multi_day", "stage_race"}
)


def _validate_inputs(
    layer2e_payload: Layer2EPayload | None,
    layer3b_payload: Layer3BPayload,
    race_event_payload: RaceEventPayload | None,
    today: _date_type,
) -> int:
    """Apply §4.5 race-week-brief preconditions. Fail-fast — raises
    `Layer4InputError` on first failing rule. Returns `days_to_event`
    (computed once + reused downstream).

    **D-66 amendments:** rows 7 (`race_event_payload_missing`) + 8
    (`race_event_date_mismatch_3b`) are new D-66 rows. Rows 3 (event_date
    in future), 5 (event_locale_unresolved), 6 (race_format_unset) source
    their values from `race_event_payload` per the D-66 design doc §8.2 +
    the paired `Layer3BPayload` extension (Layer3BPayload now carries
    optional event_date / event_locale_id / race_format / time_to_event_weeks
    per the paired `Layer3_3B_Spec.md` §7 amendment 2026-05-18; v1
    implementation prefers race_event_payload as the source-of-truth)."""
    # Row 1: event mode required (per §3.4 declaration)
    if layer3b_payload.mode != "event":
        raise Layer4InputError(
            "race_week_brief_requires_event_mode",
            detail=f"layer3b_payload.mode={layer3b_payload.mode}",
        )

    # Row 7 (D-66): race_event_payload non-None
    if race_event_payload is None:
        raise Layer4InputError(
            "race_event_payload_missing",
            detail="race_event_payload required for race-week-brief mode",
        )

    # Row 6: race_format set (sourced from race_event_payload — D-66)
    valid_formats = {"single_day", "continuous_multi_day", "stage_race"}
    if race_event_payload.race_format not in valid_formats:
        raise Layer4InputError(
            "race_format_unset",
            detail=f"race_event_payload.race_format={race_event_payload.race_format}",
        )

    # Row 3: event_date in future
    event_date = race_event_payload.event_date
    if event_date <= today:
        raise Layer4InputError(
            "event_date_in_past",
            detail=f"event_date={event_date} ≤ today={today}",
        )

    # Row 2: event within 14d window
    days_to_event = (event_date - today).days
    if days_to_event > _MAX_DAYS_TO_EVENT:
        raise Layer4InputError(
            "race_week_brief_too_early",
            detail=f"days_to_event={days_to_event} > {_MAX_DAYS_TO_EVENT}",
        )

    # Row 4: 2E payload required (mandatory for race-day fueling plan)
    if layer2e_payload is None:
        raise Layer4InputError(
            "layer2e_payload_missing",
            detail="layer2e_payload required for race-week-brief mode",
        )

    # Row 8 (D-66): race_event_date_mismatch_3b — defensive consistency check
    # against the typed Layer3BPayload.event_date field (D-66 amendment 2026-05-18).
    # When Layer 3B has not been re-run to populate event_date (legacy plans or
    # caller-side pre-D-66 callers), skip the check defensively.
    if layer3b_payload.event_date is not None:
        if layer3b_payload.event_date != race_event_payload.event_date:
            raise Layer4InputError(
                "race_event_date_mismatch_3b",
                detail=(
                    f"race_event_payload.event_date={race_event_payload.event_date} != "
                    f"layer3b_payload.event_date={layer3b_payload.event_date}"
                ),
            )

    return days_to_event


# ─── System prompt (Layer4_RaceWeekBrief_v2.md §5) ───────────────────────────


_SYSTEM_PROMPT = """You are AIDSTATION's race-week brief synthesizer. The athlete is 14 or fewer days from a target event. Your job is to (1) modify their existing Taper-phase sessions to match race-week emphasis, (2) produce a structured race-week brief covering logistics + kit + fueling + pacing + contingencies + mental prep, and (3) for multi-day events only (expedition AR, stage races, multi-day ultras), produce a structured race plan covering segments + transitions + pacing strategy + fueling strategy + contingencies.

# What you produce

Exactly one tool call to `record_race_week_brief` with three arguments:
- `taper_session_overrides` — list of modified PlanSession records (only sessions you change; pass-throughs stay untouched)
- `race_week_brief` — the structured RaceWeekBrief, always emitted
- `race_plan` — the structured RacePlan, omitted (or null) for single-day events

Spec-auto Taper coaching flags (`race_rehearsal`, `fueling_practice`, `kit_check`, `pacing_lock`, `pre_race_taper`) are stamped by the orchestrator post-synthesis based on session shape + `days_to_event`. You do not emit these. You DO emit `intensity_modulated` (when modulating a Taper session intensity from prior-plan periodization shape due to athlete signal) and `discipline_specific_intensity` (when prescribing race-discipline-specific intensity work in a Taper session).

# Coaching voice (apply to all athlete-facing text fields)

- Direct. Factual. Evidence-grounded.
- No platitudes ("great workout!"), no hype ("crush it!"), no cheerleading ("you've got this!"), no race-day magic, no emoji.
- Tone matches a real endurance coach talking to a serious athlete who has worked hard and earned this race-week.
- Short sentences. Plain English.
- `mental_prep_cues` are evidence-grounded mantras — reference concrete signals (HR, RPE, pace, fueling intake, splits) or concrete cognitive moves ("review your 28-day chronic load if doubt creeps in") rather than emotional framings.

# Taper session modulation

The athlete's Taper sessions are already in `prior_taper_sessions`. Modify only what needs modifying for race-week. Sessions at `days_to_event ≤ 2` go light + easy + no novel stimulus. Sessions at `days_to_event ∈ [3, 5]` include one moderate-or-easy session with ≥30 min at race-target zone. Sessions at `days_to_event == 7` are low-cognitive-load (recovery spin, easy walk) so the athlete can focus on kit checks. One Taper session per week, typically the longest scheduled, structures as a race-rehearsal with full race-day fueling + pacing + kit practice (60–120 min, not race-distance). All Taper cardio sessions ≥ 60 min cue race-day fueling tier from 2E.

When 3A signals (fatigue markers, ACWR elevated, sleep deficit, lingering illness) suggest pulling back further than the prior-plan Taper structure: modulate intensity downward, emit `intensity_modulated`, and explain the modulation in `session_notes` in two short sentences.

Recovery sessions (`kind=recovery`): the prior plan may include a light mobility/breathwork recovery session (its movements are listed under `recovery_exercises:` in the prior-session block). Race-week bias is toward freshness, not added stimulus — keep a recovery session only when it aids recovery without adding fatigue, and never introduce novel recovery stimulus this close to the event. When you keep one, emit `kind=recovery` and echo or trim the prior `recovery_exercises` (each item: `exercise_id`, `exercise_name`, a free-text `prescription`, and `instructions`); pick `exercise_id`s only from those already prescribed in the prior session — never invent one. When the session no longer serves race-week, drop it to full rest instead: `kind=rest`, `intensity_summary=rest`, `rest_reason=planned_recovery`, and a null `recovery_exercises`.

# Race-week brief synthesis

The `race_week_brief` is athlete-facing and consumed by the brief UI surface + Layer 5's clothing/conditions advisor. Coverage requirements: `kit_check_dates` MUST include `event.date - 7` at minimum; `contingencies` MUST cover D6 anchor categories applicable to the race format (any race: GI / hydration / mechanical-or-gear-failure / weather; ultra + multi-day: sleep-dep; stage races: between-stage recovery; multi-day: cumulative fatigue + crew-pacing-mismatch); `mental_prep_cues` must be evidence-grounded.

Weather contingency: every race happens outdoors at a known location on a known date, so a weather contingency is always required. When an `## Expected conditions` block is present in the request, anchor the weather contingency to those climate normals (e.g. heat + electrolyte protocol when typical highs are hot; a lightning/exposure bail plan for storm-prone windows; a layering/hypothermia plan when typical lows are cold or precipitation likelihood is high). When that block is absent, reason from the race location + date yourself (regional seasonal climate) — do not omit the weather contingency.

Kit-manifest synthesis (D-66 active): the athlete's race_event_payload now carries structured route-locale equipment per the D-66 amendment. Render any mandatory-gear lines from the free-text race notes + per-route-locale equipment items into the flat kit_manifest list. Prefer canonical layer0 names (`layer0_canonical=True`); free-text fallback (`layer0_canonical=False`) when no canonical exists.

# Race plan synthesis (multi-day events only)

For `race_format != 'single_day'`, produce `race_plan` covering the race itself. `segments` are chronologically ordered. `segment_id` is a unique stable UUID per segment. `segment_index` starts at 0 and is strictly monotonic. `estimated_start_offset_hr` is strictly monotonic. `pacing_target` per segment uses the typed IntensityTarget union (HRTarget / PowerTarget / PaceTarget / SwimPaceTarget / RPETarget / VerticalRateTarget / StrokeRateTarget / CadenceTarget / ClimbingGradeTarget — pick the shape that best matches the discipline + 3A data density). `transitions[].from_segment_id` references an existing segment's `segment_id`; `to_segment_id` references the next segment. `fueling_strategy.cho_g_per_hr_low/high` MUST fall inside the athlete's 2E race-day fueling tier band.

# Iteration discipline (when retries_used > 0)

On retry, the orchestrator passes `rule_failures` describing what the validator caught. Treat each failure as a hard constraint. Don't argue with the validator; adjust the output to clear the failure while preserving as much of the brief's structural coverage as possible. Severity `blocker` means the brief is unshippable as drafted; severity `warning` means optional adjustment.

# Output discipline

- One tool call per invocation. Do not emit prose outside the tool call.
- All athlete-facing text fields are bounded by `maxLength` in the schema — be concise.
- Numeric durations always integers.
- Exercise IDs reference Layer 0B canonical IDs; populate `exercise_name` with the human-readable name.
- For interval_set cardio_blocks: emit `repetitions`, `rest_between_min`, `rest_intensity_zone`. For other block_kinds: leave those three fields null.
"""


# ─── Prompt rendering (Layer4_RaceWeekBrief_v2.md §6) ────────────────────────


def _render_training_substitution_section(
    payload: TrainingSubstitutionPayload,
) -> list[str]:
    """Render the Slice-5 training-substitution brief for the race-week prompt.

    Per discipline: the race craft + the craft candidate set (the LLM picks the
    closest), the terrain training emphasis ranked by `pct × fidelity`, and the
    terrain that can't be trained locally (so the brief can name compensation
    work). `# Heading` + `**bold:**` matches the race_week_brief markdown idiom.
    """
    lines: list[str] = ["# Best-fit training substitution (Layer 2 substitution resolver)", ""]
    lines.append(
        "**Purpose:** per race discipline, the closest trainable terrain "
        "emphasis (ranked by how much of that leg is on each terrain × how "
        "well the athlete can reproduce it locally), the craft candidate set to "
        "pick the closest trainable craft from, and the terrain that can't be "
        "trained directly. Bias race-week sessions toward the highest-emphasis "
        "trainable terrain; name compensation work for untrainable terrain."
    )
    lines.append("")
    if not payload.recommendations and not payload.coaching_flags:
        lines.append("_No training-substitution recommendations for this discipline set._")
        lines.append("")
        return lines
    for rec in payload.recommendations:
        crafts = ", ".join(rec.candidate_training_crafts) or "(none logged)"
        lines.append(
            f"- **{rec.discipline_id} {rec.discipline_name}** (race craft: "
            f"{rec.race_craft}) — candidate training crafts: {crafts}"
        )
        if rec.terrain_emphasis:
            emph = "; ".join(
                f"{e.terrain_name or e.race_terrain_id} ({e.pct:g}%, proxy "
                f"{e.proxy_terrain_name or e.proxy_terrain_id} @ fidelity "
                f"{e.fidelity:.2f})"
                for e in rec.terrain_emphasis
            )
            lines.append(f"  - Terrain emphasis: {emph}")
        if rec.untrainable_terrain:
            untr = "; ".join(
                f"{g.terrain_name or g.race_terrain_id} ({g.pct:g}%, {g.reason})"
                for g in rec.untrainable_terrain
            )
            lines.append(f"  - Untrainable terrain: {untr}")
    if payload.coaching_flags:
        lines.append("")
        lines.append("**Substitution coaching flags:**")
        for fl in payload.coaching_flags:
            scope_bits = [b for b in (fl.discipline_id, fl.race_terrain_id) if b]
            scope = f" ({' / '.join(scope_bits)})" if scope_bits else ""
            lines.append(f"- `{fl.flag_type}`{scope}: {fl.message}")
    lines.append("")
    return lines


def _render_user_prompt(
    layer1_payload: dict[str, Any],
    layer2a_payload: Layer2APayload,
    layer2b_payload: Layer2BPayload,
    layer2c_payloads: dict[str, Layer2CPayload],
    layer2d_payload: Layer2DPayload,
    layer2e_payload: Layer2EPayload,
    layer3a_payload: Layer3APayload,
    layer3b_payload: Layer3BPayload,
    race_event_payload: RaceEventPayload,
    prior_plan_session_window: list[PlanSession],
    days_to_event: int,
    today: _date_type,
    retries_used: int,
    rule_failures: list[RuleFailure],
    training_substitution_payload: TrainingSubstitutionPayload | None = None,
    expected_conditions: ExpectedConditions | None = None,
) -> str:
    """Render the §6 user prompt template against the typed payloads.
    Inline Python rendering (no Mustache dependency) per the
    `layer4/single_session.py` precedent."""
    parts: list[str] = []
    is_multi_day = race_event_payload.race_format != "single_day"

    # § Event metadata (D-66 sourced)
    parts.append("# Race-week brief request")
    parts.append("")
    parts.append(
        f"**Event:** {race_event_payload.name} on "
        f"{race_event_payload.event_date.isoformat()} "
        f"({race_event_payload.race_format})"
    )
    parts.append(f"**Days to event:** {days_to_event}")
    # D-73 Phase 5.2 walkthrough #1 (2026-05-21) — surface the Mapbox-anchored
    # race location to the LLM so `event_locale` in the brief output is
    # grounded in the athlete-provided anchor instead of inferred from the
    # event name. Legacy slug surfaces too when the Mapbox columns are unset
    # (pre-walkthrough rows).
    locale_name = (
        race_event_payload.event_locale_place_name
        or race_event_payload.event_locale_name
        or race_event_payload.event_locale_id
    )
    if locale_name:
        parts.append(f"**Race location:** {locale_name}")
    if race_event_payload.distance_km is not None:
        parts.append(f"**Race distance:** {race_event_payload.distance_km} km")
    if race_event_payload.estimated_duration_hr is not None:
        parts.append(
            f"**Estimated duration:** {race_event_payload.estimated_duration_hr} hr"
        )
    if race_event_payload.primary_metric is not None:
        parts.append(
            f"**Primary metric:** {race_event_payload.primary_metric} "
            "(how the athlete frames this race — pace/segment language should lead with it)"
        )
    if race_event_payload.total_elevation_gain_m is not None:
        parts.append(
            f"**Elevation gain:** {race_event_payload.total_elevation_gain_m} m"
        )
    # #439 — the prior split "Race rules summary" / "Notes" form fields were
    # merged into the single `notes` field, and the brief now renders it in
    # full. The prior split left `notes` captured but never rendered into the
    # prompt (the #306/#338 root: race rules the athlete typed never reached the
    # synthesizer). Free text covers race rules + mandatory gear + portage + any
    # other context the athlete wants the brief to reason against.
    if race_event_payload.notes:
        parts.append("")
        parts.append("**Race notes & rules (verbatim from athlete):**")
        parts.append("```")
        parts.append(race_event_payload.notes)
        parts.append("```")
    parts.append("")

    # § Expected conditions — climate normals at the race location + date
    # (weather_client). Anchors the required weather contingency. Absent when
    # the race has no coordinates or the climate lookup failed; the synthesizer
    # then reasons about expected weather from the location + date itself.
    if expected_conditions is not None:
        parts.append("## Expected conditions")
        parts.append("")
        parts.append(expected_conditions.summary_line())
        parts.append(
            "Anchor the weather contingency to these normals. They are "
            "historical climate, not a forecast — frame guidance as typical "
            "conditions to prepare for."
        )
        parts.append("")

    # § Route locales (D-66 amendment 2026-05-18 — only for multi-day events
    # OR when route_locales populated for a single-day event)
    if race_event_payload.route_locales:
        parts.append("# Route locales (D-66 structured graph)")
        parts.append("")
        parts.append(
            "Ordered by sequence_idx. Per-locale equipment populated by the athlete via "
            "onboarding §H.4 or the profile race-events tab. Synthesize kit_manifest "
            "items + RacePlan.segments references from this graph."
        )
        # Companion to PR #131 (RaceLocalesValidatorHotfix). When start
        # or finish role is missing, instruct the LLM not to infer the
        # anchor from first/last sequence_idx position.
        roles_present = {rl.role for rl in race_event_payload.route_locales}
        missing_anchors = [
            anchor for anchor in ("start", "finish") if anchor not in roles_present
        ]
        if missing_anchors:
            parts.append("")
            parts.append(
                f"**Note:** no entry has role={' or role='.join(repr(a) for a in missing_anchors)}. "
                "Treat the corresponding anchor(s) as unknown — do not infer from "
                "first/last sequence_idx position."
            )
        parts.append("")
        for rl in race_event_payload.route_locales:
            line = f"- [{rl.sequence_idx}] {rl.role}: {rl.name}"
            if rl.mile_marker is not None:
                line += f" (mile {rl.mile_marker})"
            parts.append(line)
            if rl.notes:
                parts.append(f"    notes: {rl.notes}")
            if rl.equipment:
                parts.append("    equipment:")
                for eq in rl.equipment:
                    eq_line = f"      - {eq.equipment_name}"
                    if eq.quantity_text:
                        eq_line += f" ({eq.quantity_text})"
                    parts.append(eq_line)
                    if eq.notes:
                        parts.append(f"          notes: {eq.notes}")
        parts.append("")

    # § Athlete profile
    parts.append("# Athlete profile")
    parts.append("")
    parts.append(f"User ID {layer3a_payload.user_id}.")
    exp = layer1_payload.get("experience_level") or "unknown"
    parts.append(f"Experience level: {exp}.")
    travel = layer1_payload.get("travel_constraint")
    if travel:
        parts.append(f"Travel constraint: {travel}")
    sleep = layer1_payload.get("sleep_baseline")
    if sleep:
        parts.append(f"Sleep baseline: {sleep}")
    parts.append("")

    # § Active injuries (2D)
    parts.append("## Active injuries (2D — hard constraints)")
    parts.append("")
    excluded = layer2d_payload.excluded_exercises
    accommodated = layer2d_payload.accommodated_exercises
    if not excluded and not accommodated:
        parts.append("- None on file.")
    else:
        for er in excluded:
            parts.append(f"- EXCLUDE {er.exercise_id} ({er.exercise_name})")
        for er in accommodated:
            mod_list = ", ".join(m.modality_type for m in er.accommodations)
            parts.append(
                f"- ACCOMMODATE {er.exercise_id} ({er.exercise_name}): {mod_list}"
            )
    parts.append("")

    # § Current athlete state (3A)
    parts.append("# Current athlete state (3A)")
    parts.append("")
    cs = layer3a_payload.current_state
    parts.append(
        f"- Aerobic capacity: {cs.aerobic_capacity.level} ({cs.aerobic_capacity.confidence})"
    )
    parts.append(f"- Strength: {cs.strength.level} ({cs.strength.confidence})")
    if cs.weak_links:
        parts.append(f"- Weak links: {', '.join(cs.weak_links)}")
    rt = layer3a_payload.recent_trajectory
    parts.append(f"- Short-term trajectory: {rt.short_term.direction}")
    parts.append(f"- Medium-term trajectory: {rt.medium_term.direction}")
    if rt.acwr_status.combined:
        c = rt.acwr_status.combined
        parts.append(
            f"- ACWR (combined): ratio={c.ratio:.2f}, zone={c.zone}, "
            f"acute={c.acute_load:.0f} chronic={c.chronic_load:.0f} {c.units}"
        )
    parts.append(
        f"- Data density: {layer3a_payload.data_density.recent_workouts_count} "
        f"recent workouts, {layer3a_payload.data_density.integration_data_days} "
        "days of integration data"
    )
    parts.append("")

    # === Recovery state (3A wellness) — #196 Phase 4 recovery-aware planning ===
    # Freshness-gated, LLM-soft strong-lean guidance surfaced from the already-
    # hashed 3A digest (no new cache-key input). See layer4/recovery_guidance.py.
    parts.extend(format_recovery_guidance(layer3a_payload))
    parts.append("")

    # § Periodization phase (3B Taper context)
    parts.append("# Periodization phase (3B Taper context)")
    parts.append("")
    parts.append(
        f"- Periodization mode: {layer3b_payload.periodization_shape.mode}"
    )
    parts.append(
        f"- Start phase: {layer3b_payload.periodization_shape.start_phase}"
    )
    parts.append(f"- Goal viability: {layer3b_payload.goal_viability.viability}")
    parts.append(
        f"- Goal viability reasoning: {layer3b_payload.goal_viability.reasoning_text}"
    )
    parts.append("")

    # § Best-fit training substitution (Layer 2 substitution resolver)
    if training_substitution_payload is not None:
        parts.extend(
            _render_training_substitution_section(training_substitution_payload)
        )

    # § Upstream coaching flags — #307 advisory channel (Layer 2A/2B/2C/2D)
    upstream_flag_lines = format_upstream_coaching_flags(
        layer2a=layer2a_payload,
        layer2b=layer2b_payload,
        layer2c_payloads=layer2c_payloads.values(),
        layer2d=layer2d_payload,
    )
    if upstream_flag_lines:
        parts.append("# Upstream coaching flags")
        parts.append("")
        parts.extend(upstream_flag_lines)
        parts.append("")

    # #339 — surface the durable Coaching Memory block (#690 rendered it on
    # plan-create only); suppress-on-empty. The variety carve-out's guard defers
    # to race-week specificity, so this mainly carries non-variety prefs here.
    coaching_memory_lines = _format_coaching_memory(layer1_payload)
    if coaching_memory_lines:
        parts.append("# Coaching memory")
        parts.append("")
        parts.extend(coaching_memory_lines)
        parts.append("")

    # § Race-day fueling tier (2E)
    parts.append("# Race-day fueling tier (2E)")
    parts.append("")
    rdf = (
        layer2e_payload.race_day_fueling[0]
        if layer2e_payload.race_day_fueling
        else None
    )
    if rdf is not None:
        parts.append(f"- Event: {rdf.event_name}")
        parts.append(
            f"- CHO band: {rdf.cho_g_per_hr_low}–{rdf.cho_g_per_hr_high} g/hr"
        )
        parts.append(
            f"- Sodium band: {rdf.na_mg_per_hr_low}–{rdf.na_mg_per_hr_high} mg/hr"
        )
        if rdf.fluid_ml_per_hr_low is not None and rdf.fluid_ml_per_hr_high is not None:
            parts.append(
                f"- Fluid band: {rdf.fluid_ml_per_hr_low}–{rdf.fluid_ml_per_hr_high} ml/hr"
            )
    parts.append("")

    # § Prior plan Taper sessions
    parts.append("# Prior plan Taper sessions (verbatim)")
    parts.append("")
    if not prior_plan_session_window:
        parts.append("- No prior Taper sessions on file.")
    else:
        for s in prior_plan_session_window:
            line = (
                f"- session_id={s.session_id} | {s.date.isoformat()} "
                f"({s.day_of_week}) | {s.kind} | {s.intensity_summary} | "
                f"{s.duration_min} min"
            )
            if s.discipline_name:
                line += f" | {s.discipline_name}"
            if s.locale_name:
                line += f" @ {s.locale_name}"
            parts.append(line)
            if s.coaching_flags:
                parts.append(
                    f"    existing flags: {', '.join(s.coaching_flags)}"
                )
            # #698 Track 1 — surface a prior recovery session's structured
            # movements so the synthesizer can echo or trim them (and only ever
            # picks exercise_ids it has already seen prescribed). Without this the
            # recovery_exercises block is invisible and the LLM can't carry it
            # forward into a recovery override.
            if s.recovery_exercises:
                parts.append("    recovery_exercises:")
                for rx in s.recovery_exercises:
                    parts.append(
                        f"      - {rx.exercise_id} ({rx.exercise_name}): "
                        f"{rx.prescription}"
                    )
            if s.session_notes:
                parts.append(f"    notes: {s.session_notes}")
    parts.append("")

    # § Retry context
    if retries_used > 0:
        parts.append(f"# Validator feedback (retry pass {retries_used} of 2)")
        parts.append("")
        parts.append(
            "You produced output that failed validation. Each failure below is "
            "a hard constraint for this retry:"
        )
        parts.append("")
        for rf in rule_failures:
            parts.append(
                f"- **{rf.rule_name}** ({rf.severity}): {rf.detail}"
            )
        parts.append("")

    # § Task
    parts.append("# Your task")
    parts.append("")
    parts.append(
        "Emit one tool call to `record_race_week_brief` with: "
        "(1) `taper_session_overrides` — modify only Taper sessions that need "
        "race-week adjustment; (2) `race_week_brief` — always emit; cover "
        "logistics + kit + fueling + pacing + contingencies + mental prep; "
        f"(3) `race_plan` — {'emit for this multi-day event' if is_multi_day else 'omit (null) for this single-day event'}."
    )
    parts.append("")
    parts.append(
        f"Coverage: `kit_check_dates` MUST include `event.date - 7` at minimum. "
        f"`contingencies` MUST cover D6 anchor categories applicable to "
        f"race_format={race_event_payload.race_format}. `mental_prep_cues` must "
        f"be evidence-grounded."
    )

    return "\n".join(parts)


# ─── Anthropic SDK call ──────────────────────────────────────────────────────


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
"""Type alias for the LLM-call adapter. Signature:
`(system_prompt, user_prompt, tool_schema, model, temperature, max_tokens,
extended_thinking_budget) -> _SynthesizerOutput`. Default implementation
calls Anthropic's API; tests pass a stub."""


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


# ─── Tool output → typed Layer4Payload ───────────────────────────────────────


def _parse_date(s: str) -> _date_type:
    return datetime.fromisoformat(s).date() if "T" in s else _date_type.fromisoformat(s)


def _parse_datetime(s: str) -> datetime:
    return datetime.fromisoformat(s)


def _build_session_override(
    override_data: dict[str, Any],
    *,
    plan_version_id: int,
    prior_by_id: dict[str, PlanSession],
) -> PlanSession:
    """Convert one taper_session_override dict into a `PlanSession`.

    Synthesizer emits `session_id_to_override` referencing a prior-plan
    session; we reuse the prior `session_id` so the override replaces the
    prior session in plan-view UI. Inherits `phase_metadata` from the
    prior session per `Layer4_Spec.md` §7.12 C2 amendment (race-week-brief
    preserves Taper-phase metadata verbatim from the prior plan)."""
    sid = override_data["session_id_to_override"]
    prior = prior_by_id.get(sid)
    if prior is None:
        raise Layer4OutputError(
            "schema_violation",
            detail=(
                f"taper_session_overrides[].session_id_to_override={sid} "
                "does not match any session in prior_plan_session_window"
            ),
        )

    raw_blocks = override_data.get("cardio_blocks")
    blocks: list[CardioBlock] | None = None
    if raw_blocks:
        blocks = [CardioBlock(**b) for b in raw_blocks]

    raw_exercises = override_data.get("strength_exercises")
    exercises: list[StrengthExercise] | None = None
    if raw_exercises:
        exercises = [StrengthExercise(**e) for e in raw_exercises]

    raw_recovery = override_data.get("recovery_exercises")
    recovery_exercises: list[RecoveryExercise] | None = None
    if raw_recovery:
        recovery_exercises = [RecoveryExercise(**r) for r in raw_recovery]

    return PlanSession(
        session_id=sid,
        plan_version_id=plan_version_id,
        date=_parse_date(override_data["date"]),
        day_of_week=override_data["day_of_week"],
        session_index_in_day=override_data["session_index_in_day"],
        time_of_day=override_data["time_of_day"],
        kind=override_data["kind"],
        discipline_id=override_data.get("discipline_id"),
        discipline_name=override_data.get("discipline_name"),
        locale_id=override_data.get("locale_id"),
        locale_name=override_data.get("locale_name"),
        duration_min=override_data["duration_min"],
        intensity_summary=override_data["intensity_summary"],
        cardio_blocks=blocks,
        strength_exercises=exercises,
        recovery_exercises=recovery_exercises,
        rest_reason=override_data.get("rest_reason"),
        phase_metadata=prior.phase_metadata,
        session_notes=override_data["session_notes"],
        coaching_intent=override_data["coaching_intent"],
        coaching_flags=list(override_data.get("coaching_flags", [])),
        is_ad_hoc=False,
        ad_hoc_request_payload=None,
    )


def _build_race_week_brief(
    brief_data: dict[str, Any],
) -> RaceWeekBrief:
    """Convert the race_week_brief dict into a typed `RaceWeekBrief`."""
    raw_kit = brief_data.get("kit_manifest", [])
    kit_manifest = [KitItem(**ki) for ki in raw_kit]
    raw_dates = brief_data.get("kit_check_dates", [])
    kit_check_dates = [_parse_date(d) for d in raw_dates]
    return RaceWeekBrief(
        days_to_event=brief_data["days_to_event"],
        event_name=brief_data["event_name"],
        event_date=_parse_date(brief_data["event_date"]),
        event_locale=brief_data["event_locale"],
        race_format=brief_data["race_format"],
        goal_outcome=brief_data["goal_outcome"],
        pre_race_logistics=brief_data["pre_race_logistics"],
        drop_bag_strategy=brief_data.get("drop_bag_strategy"),
        course_familiarization_notes=brief_data.get("course_familiarization_notes"),
        kit_manifest=kit_manifest,
        kit_check_dates=kit_check_dates,
        race_day_fueling_plan=brief_data["race_day_fueling_plan"],
        pre_race_meal_strategy=brief_data["pre_race_meal_strategy"],
        pacing_strategy_summary=brief_data["pacing_strategy_summary"],
        contingencies=list(brief_data["contingencies"]),
        mental_prep_cues=list(brief_data["mental_prep_cues"]),
    )


def _build_race_plan(plan_data: dict[str, Any]) -> RacePlan:
    """Convert the race_plan dict into a typed `RacePlan`."""
    segments = [RaceSegment(**s) for s in plan_data["segments"]]
    transitions = [TransitionSpec(**t) for t in plan_data["transitions"]]
    pacing_strategy = PacingStrategy(**plan_data["pacing_strategy"])
    fueling_strategy = FuelingStrategy(**plan_data["fueling_strategy"])
    contingencies = [Contingency(**c) for c in plan_data["contingencies"]]
    return RacePlan(
        race_name=plan_data["race_name"],
        race_start_datetime=_parse_datetime(plan_data["race_start_datetime"]),
        race_end_estimate_datetime=_parse_datetime(plan_data["race_end_estimate_datetime"]),
        race_format=plan_data["race_format"],
        locales=list(plan_data["locales"]),
        segments=segments,
        transitions=transitions,
        pacing_strategy=pacing_strategy,
        fueling_strategy=fueling_strategy,
        contingencies=contingencies,
    )


def _build_layer4_payload(
    *,
    user_id: int,
    sessions: list[PlanSession],
    plan_version_id: int,
    race_event_payload: RaceEventPayload,
    race_week_brief: RaceWeekBrief,
    race_plan: RacePlan | None,
    model: str,
    temperature: float,
    validator_results: list[ValidatorResult],
    notable_observations: list[Observation],
    etl_version_set: dict[str, str],
    input_tokens_total: int,
    output_tokens_total: int,
    latency_ms_total: int,
    llm_call_count: int,
    scope_start_date: _date_type,
    scope_end_date: _date_type,
) -> Layer4Payload:
    """Compose the final Layer4Payload per `Layer4_Spec.md` §3.4:
    `mode='race_week_brief'`, `pattern='B'`, `phase_structure=None`,
    `seam_reviews=None`, `race_week_brief` non-None, `race_plan` non-None
    iff race_format != 'single_day'."""
    return Layer4Payload(
        user_id=user_id,
        mode="race_week_brief",
        plan_version_id=plan_version_id,
        scope_start_date=scope_start_date,
        scope_end_date=scope_end_date,
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
        race_week_brief=race_week_brief,
        race_plan=race_plan,
    )


def _emit_intensity_modulated_observation(
    sessions: list[PlanSession],
) -> Observation | None:
    """Per §8.6/§8.7: when ANY session override carries the
    `intensity_modulated` flag, emit one orchestrator-side
    `Observation(category='intensity_modulated')` referencing the count."""
    affected = [s for s in sessions if "intensity_modulated" in s.coaching_flags]
    if not affected:
        return None
    return Observation(
        category="intensity_modulated",
        text=(
            f"Synthesizer modulated intensity on {len(affected)} race-week "
            "Taper session(s); see session_notes for the rationale."
        ),
        evidence_basis=["Layer4_Spec.md §8.6 + §8.7"],
        elevates_to_hitl=False,
    )


def _emit_opportunity_observations(
    opportunities: list[dict[str, Any]],
) -> list[Observation]:
    """Per §8.7: `opportunity` is the LLM-emitted exception. The synthesizer
    may emit up to 2 opportunities via the tool's `opportunities` arg;
    orchestrator passes them through as `Observation(category='opportunity')`."""
    out: list[Observation] = []
    for op in opportunities:
        out.append(
            Observation(
                category="opportunity",
                text=op["text"],
                evidence_basis=list(op.get("evidence_basis", [])),
                elevates_to_hitl=False,
            )
        )
    return out


def _emit_data_gap_observations(
    validator_result: ValidatorResult,
) -> list[Observation]:
    """Per §8.7: emit `data_gap` observation for §4.5 soft-fail rules
    (`kit_manifest_inputs_incomplete_*`). One observation per failure
    code present in the final accepted validator result."""
    out: list[Observation] = []
    seen: set[str] = set()
    for rf in validator_result.rule_failures:
        if (
            rf.rule_name.startswith("kit_manifest_inputs_incomplete")
            and rf.rule_name not in seen
        ):
            seen.add(rf.rule_name)
            text = f"{rf.rule_name}: kit-manifest synthesis degraded; athlete may complete route-locale equipment via /profile?tab=race-events."
            out.append(
                Observation(
                    category="data_gap",
                    text=text[:240],
                    evidence_basis=["Layer4_Spec.md §4.5 row 9 + §8.7"],
                    elevates_to_hitl=False,
                )
            )
    return out


def _emit_route_locales_anchor_observations(
    race_event_payload: RaceEventPayload,
) -> list[Observation]:
    """Companion to PR #131 (RaceLocalesValidatorHotfix). When the athlete
    captured route_locales but didn't mark an explicit `start` and/or
    `finish` role anywhere in the list, surface a `data_gap` observation
    so the LLM has explicit signal rather than fabricating an anchor
    from first/last position inference. Skipped when route_locales is
    empty (already covered by `kit_manifest_inputs_incomplete_no_route_locales`)."""
    out: list[Observation] = []
    if not race_event_payload.route_locales:
        return out
    roles = {rl.role for rl in race_event_payload.route_locales}
    if "start" not in roles:
        out.append(
            Observation(
                category="data_gap",
                text=(
                    "route_locales_missing_start_anchor: no entry has role='start'. "
                    "Do not infer a start anchor from the first sequence_idx; treat "
                    "the start as unknown for pacing + logistics narration."
                )[:240],
                evidence_basis=[
                    "Race_Events_D66_Design_v1.md §4.2",
                    "PR #131 validator loosen 2026-05-23",
                ],
                elevates_to_hitl=False,
            )
        )
    if "finish" not in roles:
        out.append(
            Observation(
                category="data_gap",
                text=(
                    "route_locales_missing_finish_anchor: no entry has role='finish'. "
                    "Do not infer a finish anchor from the last sequence_idx; treat "
                    "the finish as unknown for pacing + logistics narration."
                )[:240],
                evidence_basis=[
                    "Race_Events_D66_Design_v1.md §4.2",
                    "PR #131 validator loosen 2026-05-23",
                ],
                elevates_to_hitl=False,
            )
        )
    return out


# ─── Entry point ─────────────────────────────────────────────────────────────


def llm_layer4_race_week_brief(
    user_id: int,
    layer1_payload: dict[str, Any],
    layer2a_payload: Layer2APayload,
    layer2b_payload: Layer2BPayload,
    layer2c_payloads: dict[str, Layer2CPayload],
    layer2d_payload: Layer2DPayload,
    layer2e_payload: Layer2EPayload,
    layer3a_payload: Layer3APayload,
    layer3b_payload: Layer3BPayload,
    race_event_payload: RaceEventPayload,
    prior_plan_session_window: list[PlanSession],
    plan_version_id: int,
    etl_version_set: dict[str, str],
    *,
    model: str = "claude-sonnet-4-6",
    temperature: float = 0.2,
    max_tokens: int = 6000,
    capped_retries: int = 2,
    extended_thinking_budget: int = 5500,
    today: _date_type | None = None,
    llm_caller: LLMCaller | None = None,
    # Training-substitution payload rendered into the brief prompt via
    # `_render_training_substitution_section`. Default None preserves existing
    # call sites (notably the test fixtures).
    training_substitution_payload: TrainingSubstitutionPayload | None = None,
    # Injectable climate-normals fetcher (tests pass a fake). Default None
    # uses the live Open-Meteo lookup; a no-op when the race has no coords.
    weather_fetcher: Fetcher | None = None,
) -> Layer4Payload:
    """Pattern B race-week-brief synthesizer per `Layer4_Spec.md` §3.4
    (D-66 amendment 2026-05-18 — new `race_event_payload` positional arg).

    Algorithm (§5.3 Pattern B + §5.5 capped retry):
    1. Validate inputs per §4.5 — raises `Layer4InputError` on precondition
       fail. Returns `days_to_event` (computed once + reused).
    2. Build the user prompt with full payload context (5 Layer 2 + 3A + 3B
       + 1 + race_event_payload + prior Taper sessions).
    3. Invoke synthesizer; parse `record_race_week_brief` tool output into
       (taper_session_overrides, race_week_brief, race_plan); wrap into a
       `Layer4Payload`.
    4. Run §5.4 deterministic validator harness (race-week-brief mode
       rules + `kit_manifest_inputs_incomplete` D-66-active branch).
    5. On validator failure, retry up to `capped_retries` (default 2) with
       `RuleFailure` context merged into the user prompt.
    6. On cap-hit with unresolved blockers: ship the latest synthesis as
       best-effort with an orchestrator-emitted
       `Observation(category='best_effort_plan', elevates_to_hitl=True)`;
       outstanding `blocker`-severity failures demote to `warning` per
       §5.5.

    The `today` param defaults to `date.today()` for orchestrator
    integration; tests inject a fixed date.

    The `llm_caller` param is dependency-injectable for tests; production
    callers leave it as None to use the Anthropic SDK default."""
    if today is None:
        today = _date_type.today()

    days_to_event = _validate_inputs(
        layer2e_payload=layer2e_payload,
        layer3b_payload=layer3b_payload,
        race_event_payload=race_event_payload,
        today=today,
    )

    caller: LLMCaller = llm_caller or _default_llm_caller
    feasible_pool_ids = compute_feasible_pool_ids(layer2c_payloads, layer2d_payload)
    recovery_pool_ids = compute_recovery_pool_ids(layer2c_payloads, layer2d_payload)
    # #698 Track 1 — id->(name,type) for the SAME pool, feeding the
    # `_repair_recovery_exercises` crash-guard on taper recovery overrides
    # (mirrors per_phase; prod plan #74 was the per-phase sibling).
    recovery_pool_entries = _recovery_pool_entries(layer2c_payloads, layer2d_payload)
    tool_schema = build_record_race_week_brief_tool(
        feasible_pool_ids=feasible_pool_ids or None,
        recovery_pool_ids=recovery_pool_ids or None,
    )

    # Climate normals for the weather contingency (best-effort; None when the
    # race has no coordinates or the lookup fails — the prompt then degrades to
    # intrinsic climate reasoning). Fetched once, reused across retries.
    expected_conditions = get_expected_conditions(
        race_event_payload.event_locale_lat,
        race_event_payload.event_locale_lng,
        race_event_payload.event_date,
        today=today,
        fetcher=weather_fetcher,
    )

    prior_by_id = {s.session_id: s for s in prior_plan_session_window}
    is_multi_day = race_event_payload.race_format != "single_day"

    rule_failures: list[RuleFailure] = []
    validator_results: list[ValidatorResult] = []
    total_input_tokens = 0
    total_output_tokens = 0
    total_latency_ms = 0
    llm_call_count = 0
    cap_hit = False

    latest_sessions: list[PlanSession] | None = None
    latest_brief: RaceWeekBrief | None = None
    latest_plan: RacePlan | None = None
    latest_opportunities: list[dict[str, Any]] = []
    latest_validator: ValidatorResult | None = None

    for retries_used in range(capped_retries + 1):
        user_prompt = _render_user_prompt(
            layer1_payload=layer1_payload,
            layer2a_payload=layer2a_payload,
            layer2b_payload=layer2b_payload,
            layer2c_payloads=layer2c_payloads,
            layer2d_payload=layer2d_payload,
            layer2e_payload=layer2e_payload,
            layer3a_payload=layer3a_payload,
            layer3b_payload=layer3b_payload,
            race_event_payload=race_event_payload,
            prior_plan_session_window=prior_plan_session_window,
            days_to_event=days_to_event,
            today=today,
            retries_used=retries_used,
            rule_failures=rule_failures,
            training_substitution_payload=training_substitution_payload,
            expected_conditions=expected_conditions,
        )

        llm_out = caller(
            # #339 — append the variety carve-out (self-limiting: its guard
            # defers to race-week specificity, so it stays inert in taper while
            # honoring non-variety Coaching-memory prefs surfaced above).
            _SYSTEM_PROMPT + "\n\n" + VARIETY_CARVEOUT_PROMPT_SECTION,
            user_prompt,
            tool_schema,
            model,
            temperature,
            max_tokens,
            extended_thinking_budget,
        )

        llm_call_count += 1
        total_input_tokens += llm_out.input_tokens
        total_output_tokens += llm_out.output_tokens
        total_latency_ms += llm_out.latency_ms

        # Parse tool args
        try:
            tool_args = llm_out.tool_args
            override_data_list = tool_args.get("taper_session_overrides", [])
            if not isinstance(override_data_list, list):
                raise Layer4OutputError(
                    "schema_violation",
                    detail="taper_session_overrides not a list",
                )
            # #698 Track 1 — deterministic recovery_exercises crash-guard: fill a
            # recovery override the synthesizer left empty BEFORE pydantic, so the
            # forced recovery day self-heals instead of failing the brief (the
            # taper sibling of the prod plan #74 per-phase failure).
            override_data_list, _recovery_fill_notes = _repair_recovery_exercises(
                override_data_list, recovery_pool_entries
            )
            if _recovery_fill_notes:
                print(
                    "synthesize_race_week_brief: recovery auto-fill — "
                    + "; ".join(_recovery_fill_notes)
                )
            # #803 — set strength resolution metadata deterministically from each
            # pick's 2C resolution before construction (mirrors per_phase). Taper
            # overrides can carry strength blocks.
            _res_notes = _apply_strength_resolution(override_data_list, layer2c_payloads)
            if _res_notes:
                print(
                    "synthesize_race_week_brief: strength resolution defaulted to "
                    f"exact for unresolved picks: {', '.join(_res_notes)}"
                )
            override_sessions = [
                _build_session_override(
                    od, plan_version_id=plan_version_id, prior_by_id=prior_by_id
                )
                for od in override_data_list
            ]
            # Compose the merged Taper-week session list per `Layer4_Spec.md`
            # §3.4 "sessions = modified Taper-phase sessions": overrides
            # replace prior sessions by session_id; non-overridden prior
            # sessions pass through verbatim. This is what the validator
            # operates on (volume_band, intensity_dist, etc. work against
            # the full merged Taper-week view).
            overridden_ids = {s.session_id for s in override_sessions}
            sessions = [
                s for s in prior_plan_session_window if s.session_id not in overridden_ids
            ] + override_sessions
            sessions.sort(key=lambda s: (s.date, s.session_index_in_day))
            brief_data = tool_args.get("race_week_brief")
            if not isinstance(brief_data, dict):
                raise Layer4OutputError(
                    "schema_violation",
                    detail="race_week_brief not an object",
                )
            race_week_brief = _build_race_week_brief(brief_data)
            plan_data = tool_args.get("race_plan")
            if is_multi_day:
                if not isinstance(plan_data, dict):
                    raise Layer4OutputError(
                        "schema_violation",
                        detail=(
                            f"race_format={race_event_payload.race_format} "
                            "requires race_plan non-null"
                        ),
                    )
                race_plan: RacePlan | None = _build_race_plan(plan_data)
            else:
                race_plan = None
            opportunities = list(tool_args.get("opportunities", []))
        except (ValidationError, KeyError, ValueError, Layer4OutputError) as e:
            if retries_used >= capped_retries:
                if isinstance(e, Layer4OutputError):
                    raise
                raise Layer4OutputError(
                    "schema_violation",
                    detail=f"tool output did not parse: {e}",
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

        # Determine scope window (prior Taper window OR today→event_date)
        if sessions:
            scope_start_date = min(s.date for s in sessions)
            scope_end_date = max(
                max(s.date for s in sessions), race_event_payload.event_date
            )
        else:
            scope_start_date = today
            scope_end_date = race_event_payload.event_date

        latest_sessions = sessions
        latest_brief = race_week_brief
        latest_plan = race_plan
        latest_opportunities = opportunities

        payload_attempt = _build_layer4_payload_for_validation(
            user_id=user_id,
            sessions=sessions,
            plan_version_id=plan_version_id,
            race_week_brief=race_week_brief,
            race_plan=race_plan,
            model=model,
            temperature=temperature,
            etl_version_set=etl_version_set,
            scope_start_date=scope_start_date,
            scope_end_date=scope_end_date,
        )

        ctx = ValidatorContext(
            layer2a_payload=layer2a_payload,
            layer2b_payload=layer2b_payload,
            layer2c_payloads=layer2c_payloads,
            layer2d_payload=layer2d_payload,
            layer2e_payload=layer2e_payload,
            layer3a_payload=layer3a_payload,
            layer3b_payload=layer3b_payload,
            race_event=race_event_payload,
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

    assert latest_sessions is not None
    assert latest_brief is not None
    assert latest_validator is not None
    assert validator_results, "validator_results must be non-empty"

    # Best-effort acceptance per §5.5
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
                    "Validator cap hit; latest race-week brief accepted as "
                    "best-effort. Outstanding blocker-severity failures "
                    "demoted to warning."
                ),
                evidence_basis=["Layer4_Spec.md §5.5"],
                elevates_to_hitl=True,
            )
        )

    # §8.6/§8.7 — intensity_modulated bubble
    intensity_obs = _emit_intensity_modulated_observation(latest_sessions)
    if intensity_obs is not None:
        notable_observations.append(intensity_obs)

    # §8.7 — opportunity LLM-emitted exception
    notable_observations.extend(_emit_opportunity_observations(latest_opportunities))

    # §8.7 — data_gap orchestrator-emitted from soft-warning rules
    notable_observations.extend(
        _emit_data_gap_observations(validator_results[-1])
    )

    # Route-locales missing-anchor data_gap (companion to PR #131
    # validator loosen 2026-05-23). Emitted whenever route_locales is
    # captured but explicit start / finish role anchors are missing.
    notable_observations.extend(
        _emit_route_locales_anchor_observations(race_event_payload)
    )

    # Final composition
    if latest_sessions:
        final_scope_start = min(s.date for s in latest_sessions)
        final_scope_end = max(
            max(s.date for s in latest_sessions), race_event_payload.event_date
        )
    else:
        final_scope_start = today
        final_scope_end = race_event_payload.event_date

    return _build_layer4_payload(
        user_id=user_id,
        sessions=latest_sessions,
        plan_version_id=plan_version_id,
        race_event_payload=race_event_payload,
        race_week_brief=latest_brief,
        race_plan=latest_plan,
        model=model,
        temperature=temperature,
        validator_results=validator_results,
        notable_observations=notable_observations,
        etl_version_set=etl_version_set,
        input_tokens_total=total_input_tokens,
        output_tokens_total=total_output_tokens,
        latency_ms_total=total_latency_ms,
        llm_call_count=llm_call_count,
        scope_start_date=final_scope_start,
        scope_end_date=final_scope_end,
    )


def _build_layer4_payload_for_validation(
    *,
    user_id: int,
    sessions: list[PlanSession],
    plan_version_id: int,
    race_week_brief: RaceWeekBrief,
    race_plan: RacePlan | None,
    model: str,
    temperature: float,
    etl_version_set: dict[str, str],
    scope_start_date: _date_type,
    scope_end_date: _date_type,
) -> Layer4Payload:
    """Build a mid-retry Layer4Payload for validator-input purposes. Uses a
    placeholder accepted ValidatorResult so the payload's
    `validator_results[-1].accepted` invariant doesn't trip during
    construction; the real validator pass runs against this payload and the
    final composition uses `_build_layer4_payload`."""
    return Layer4Payload(
        user_id=user_id,
        mode="race_week_brief",
        plan_version_id=plan_version_id,
        scope_start_date=scope_start_date,
        scope_end_date=scope_end_date,
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
        race_week_brief=race_week_brief,
        race_plan=race_plan,
    )


__all__ = [
    "build_record_race_week_brief_tool",
    "llm_layer4_race_week_brief",
]
