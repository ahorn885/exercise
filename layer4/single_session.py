"""Layer 4 — `llm_layer4_single_session_synthesize` D-63 caller integration.

Implements `Layer4_Spec.md` §3.3 (single-session entry-point function
signature), §4.4 (input validation preconditions), §5.3 (Pattern B
single-call algorithm), §5.5 (capped retry semantics; cap=2 default), §8.7
(call-level observations — `intensity_modulated` orchestrator-side bubble).

Pattern B: one Claude API call via the `record_single_session` tool-use
mechanism; parse the structured output into a `Layer4Payload`; run the §5.4
deterministic validator harness (mode-gated to single-session-relevant
rules); on validator failure, retry the synthesizer with the `RuleFailure`
context merged into the user prompt; cap retries at 2; on cap-hit, ship the
latest synthesis as best-effort with an orchestrator-emitted
`Observation(category='best_effort_plan')`.

Caching is the orchestrator's concern per §9.4 — this function is
invoked only on cache miss. The per-entry cache key formula lives in
`layer4/hashing.py` `single_session_synthesize_key`.

**Layer 1 payload handling (v1).** `Layer1Payload` is not yet a typed
contract in `layer4/context.py` (Layer 1 typed schemas are out of scope for
the current implementation arc). The signature accepts a `dict[str, Any]`
opaque pass-through matching the PR-D precedent for unmapped upstream
shapes; the prompt body's template reads specific keys (e.g.,
`experience_level`, `coach_notes`) and renders missing keys
as empty strings.

**Tool-schema fidelity choice (v1 — Andy 2026-05-17 Option 2).** The
`record_single_session` tool schema mirrors the full `Layer4Payload`
`PlanSession` contract per `layer4/payload.py` rather than the smaller
sketch in `Layer4_SingleSession_v1.md` §4.1. The LLM picks every coaching
field including `intensity_zone` per cardio block and the discriminated
`intensity_target` shape (one of 9 typed targets). Paired with the
`Layer4_SingleSession_v2.md` prompt body amendment.
"""

from __future__ import annotations

import json
import uuid
from dataclasses import dataclass
from datetime import date as _date_type, datetime
from typing import Any, Callable, Literal

from pydantic import BaseModel, ConfigDict, Field, ValidationError, model_validator

from llm_invocation import ThinkingToolCallError, invoke_tool_call
from layer4.context import (
    Layer2CPayload,
    Layer2DPayload,
    Layer3APayload,
)
from layer4.errors import Layer4InputError, Layer4OutputError
from layer4.per_phase import (
    CARDIO_PROGRAMMING_PROMPT_SECTION,
    VARIETY_CARVEOUT_PROMPT_SECTION,
    _apply_strength_resolution,
    _format_cardio_drill_pool,
    _format_coaching_memory,
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
from layer4.validator import ValidatorContext, validate_layer4_payload


# ─── SingleSessionRequest (D-63 §4.3 contract) ───────────────────────────────


class SingleSessionRequest(BaseModel):
    """D-63 on-demand workout request per `OnDemand_Workout_D63_Design_v1.md`
    §4.3. Athlete-supplied via the D-63 frontend; pre-validated by the
    caller before Layer 4 invocation.

    Locale XOR quick_equipment per §4.4 — exactly one populated.

    `intensity` accepts `'race_pace'` per D-63 §4.3 schema; the prompt body
    treats it as `'hard'` with `discipline_specific_intensity` flag per
    `Layer4_SingleSession_v1.md` §11 row 5. Layer 4 stores the raw athlete
    pick in `ad_hoc_request_payload` for downstream observability.
    """

    model_config = ConfigDict(extra="forbid")

    sport: str
    duration_min: int = Field(ge=30, le=360)
    intensity: Literal["easy", "moderate", "hard", "race_pace"]
    locale_slug: str | None = None
    quick_equipment: list[str] = Field(default_factory=list)
    notes_for_synthesizer: str | None = None

    @model_validator(mode="after")
    def _check_locale_xor_quick_equipment(self) -> "SingleSessionRequest":
        has_locale = self.locale_slug is not None
        has_quick = len(self.quick_equipment) > 0
        if has_locale and has_quick:
            raise ValueError(
                "exactly one of locale_slug and quick_equipment must be populated "
                "(both provided)"
            )
        if not has_locale and not has_quick:
            raise ValueError(
                "exactly one of locale_slug and quick_equipment must be populated "
                "(neither provided)"
            )
        return self


# ─── Tool-use schema (Layer4_SingleSession_v2 §4.1) ──────────────────────────


def _intensity_target_schema() -> dict[str, Any]:
    """Discriminated `IntensityTarget` union per `layer4/payload.py` §7.3.
    Smart-union dispatch: the LLM emits the shape's keys, pydantic resolves.
    We surface a `oneOf` with explicit shapes so Anthropic's tool-use
    validator catches malformed targets at JSON-schema time."""
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
                    "grade_system": {"type": "string", "enum": ["yosemite_decimal", "french_sport", "uiaa"]},
                    "grade_min": {"type": "string"},
                    "grade_max": {"type": "string"},
                },
            },
        ]
    }


def build_record_single_session_tool(
    feasible_pool_ids: list[str] | None = None,
    cardio_drill_pool_ids: list[str] | None = None,
) -> dict[str, Any]:
    """The `record_single_session` Anthropic tool definition per
    `Layer4_SingleSession_v2.md` §4.1 — mirrors the full `PlanSession`
    contract from `layer4/payload.py` (minus orchestrator-filled metadata:
    `session_id`, `plan_version_id`, `is_ad_hoc`, `ad_hoc_request_payload`,
    `phase_metadata`).

    Track 2 D1: `feasible_pool_ids` (when non-empty) bounds
    `strength_exercises.exercise_id` via JSON-schema enum, making out-of-pool
    picks structurally impossible at the SDK boundary. Production callers
    pass `compute_feasible_pool_ids({locale_id: layer2c}, layer2d_payload)`.

    #698 Track 2 (Slice C1): `cardio_drill_pool_ids` (when non-empty) bounds
    `cardio_drills.exercise_id` the same way — the on-demand analog of the
    plan-create drill pool (`compute_cardio_drill_pool_ids(...)`)."""
    return {
        "name": "record_single_session",
        "description": (
            "Record the synthesized ad-hoc workout matching the athlete's D-63 "
            "request. Emit exactly one tool call per invocation."
        ),
        "input_schema": {
            "type": "object",
            "additionalProperties": False,
            "required": ["session"],
            "properties": {
                "session": {
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
                            "items": {
                                "type": "string",
                                "enum": [
                                    "intensity_modulated",
                                    "technique_emphasis",
                                    "discipline_specific_intensity",
                                ],
                            },
                            "maxItems": 3,
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
                        # #698 Track 2 (Slice C1) — structured cardio drill block,
                        # the analog of the plan-create cardio_drills. HARD CAP
                        # maxItems:1 (one technical/interval focus per session;
                        # mirrors the PlanSession pydantic invariant). exercise_id
                        # is enum-bound to the drill pool when resolvable, so
                        # out-of-pool picks are structurally impossible at the SDK
                        # boundary (the sole guard here — the validator membership
                        # rule is dormant on this path, phase_metadata=None).
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
                                    "instructions": {
                                        "type": ["string", "null"],
                                        "maxLength": 240,
                                    },
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
            },
        },
    }


# ─── Input validation (Layer4_Spec.md §4.4) ──────────────────────────────────


def _validate_inputs(
    request: SingleSessionRequest,
    layer2c_payload_for_locale: Layer2CPayload | None,
    layer2d_payload: Layer2DPayload | None,
    layer3a_payload: Layer3APayload | None,
) -> None:
    """Apply §4.4 single-session preconditions. Fail-fast — raises
    `Layer4InputError` on first failing rule. Caller is expected to
    pre-validate per D-63 §6.3; Layer 4 raises defensively.

    `sport_not_in_inclusion` (§4.4 row 6) is not checked here because
    `layer2a_payload` is not in the §3.3 signature — caller pre-checks per
    D-63 §6.3."""
    # Row 1: upstream payloads non-None
    if layer2d_payload is None:
        raise Layer4InputError("missing_upstream_payload", detail="layer2d_payload is None")
    if layer3a_payload is None:
        raise Layer4InputError("missing_upstream_payload", detail="layer3a_payload is None")

    # Row 4: locale XOR quick_equipment (pydantic enforces at construction;
    # re-check defensively in case caller bypassed pydantic).
    has_locale = request.locale_slug is not None
    has_quick = len(request.quick_equipment) > 0
    if has_locale and has_quick:
        raise Layer4InputError("locale_and_quick_equipment_both_set")
    if not has_locale and not has_quick:
        raise Layer4InputError("locale_and_quick_equipment_both_unset")

    # Row 5: 2C payload required when locale specified
    if has_locale:
        if layer2c_payload_for_locale is None:
            raise Layer4InputError(
                "layer2c_payload_for_locale_missing",
                detail=f"locale_slug={request.locale_slug} requires layer2c_payload_for_locale",
            )
        if layer2c_payload_for_locale.locale_id != request.locale_slug:
            raise Layer4InputError(
                "layer2c_payload_for_locale_missing",
                detail=(
                    f"layer2c_payload_for_locale.locale_id="
                    f"{layer2c_payload_for_locale.locale_id} does not match "
                    f"request.locale_slug={request.locale_slug}"
                ),
            )


# ─── Prompt rendering (Layer4_SingleSession_v2.md §5 + §6) ───────────────────


_SYSTEM_PROMPT = (
    """You are AIDSTATION's single-session workout synthesizer. The athlete has fired an on-demand workout request through D-63: pick a sport, pick a duration, pick an intensity, pick a location (saved locale or "somewhere else" with quick equipment). Your job is to produce one structured workout matching the request, respecting active injuries and recent training load, in a direct coaching voice.

# What you produce

Exactly one PlanSession via the `record_single_session` tool. The session is athlete-facing and immediately renderable as a workout card. Use:
- `cardio_blocks` for cardio sports (warmup / main_set / cooldown structure; add interval_set blocks for interval work; add transition blocks for sport-transitions like brick workouts). Every cardio_block requires an explicit `intensity_zone` (Z1-Z5 or mixed) and an `intensity_target` shape matching the sport: HRTarget for endurance, PowerTarget for bike/run/skimo/row, PaceTarget for running/paddle/ski, SwimPaceTarget for swim, RPETarget as universal fallback, VerticalRateTarget for skimo/hiking, StrokeRateTarget for swim/paddle/row, CadenceTarget for cycling, ClimbingGradeTarget for outdoor rock. Pick the shape that best matches the sport.
- `strength_exercises` for strength sports (sets / reps_per_set / load_prescription / rest_between_sets_sec / instructions; exercise_id references Layer 0B exercise library; exercise_name is the human-readable name)

`is_ad_hoc=True` is filled by the orchestrator; you do not emit it.

# Coaching voice (apply to all athlete-facing text fields: session_notes, coaching_intent, instructions)

- Direct. Factual. Evidence-grounded.
- No platitudes ("great workout!"), no hype ("crush it!"), no cheerleading ("you've got this!").
- Tone matches a real endurance coach talking to a serious athlete.
- Short sentences. Plain English. No emoji.

# Intensity modulation policy (three-tier)

The athlete's picked intensity is the structural intent. Honor it by default. When recent training load signals push back, apply this three-tier policy:

Tier 1 — Full honor. When recent-load signals are neutral or favorable (ACWR <= 1.10, no hard session in the last 36 hours, no fatigue-marker red flags): prescribe the session at the athlete's picked intensity. No flag emitted.

Tier 2 — Honor with warning. When signals show mild overreach risk (ACWR 1.10-1.25, OR a hard session 24-48 hours ago in the same sport, OR mild fatigue markers): prescribe the session at the athlete's picked intensity, but include an explicit overreach-risk note in `session_notes`. No `intensity_modulated` flag.

Tier 3 — Modulate with explanation. When signals are clear-cut overreach (ACWR > 1.25, OR a hard session in the last 24 hours in the same sport AND elevated 7-day load, OR strong fatigue-marker signals): modulate the prescribed intensity downward by one tier (hard -> moderate; moderate -> easy). Set `intensity_summary` to the modulated value and emit `intensity_modulated` in `coaching_flags`. Explain the modulation in `session_notes` in two sentences max.

The athlete's `notes_for_synthesizer` text is honored as structural intent (Tier 1) UNLESS Tier 3 signals are clear. Safety blockers (injury exclusion, validator hard-constraint) always override the athlete's note regardless of tier.

# Injury exclusions (hard constraints; never overridable)

Active injuries in `layer2d_payload` are hard constraints. Never prescribe exercises that load the affected joint / muscle / movement pattern. Substitute via Layer 2C Tier 2 (athlete-listed substitute) or Tier 3 (Layer 0B exercise-library nearest-neighbor proxy) — populate `substitute_text` or `proxy_origin_id` accordingly. If no safe substitute exists for a critical exercise, change the session structure.

# Equipment respect

When `request.locale_slug` is non-None: prescribe only from `layer2c_payload_for_locale.effective_pool` (with `exercises_resolved` Tier 1/2/3 substitution map). Tier 1 (direct match) preferred; Tier 2 acceptable; Tier 3 fallback only.

When `request.quick_equipment` is non-empty (athlete is "Somewhere else"): prescribe only from `request.quick_equipment` plus bodyweight movements. No Tier 2/3 substitution available. State equipment constraints explicitly in `session_notes`.

"""
    + CARDIO_PROGRAMMING_PROMPT_SECTION
    + """

# Cardio drills

A cardio session may optionally carry **one** drill from the `=== Cardio drill pool (consider these) ===` menu — a discrete, catalog-defined skill, transition, or interval drill that sharpens the requested sport (a single-leg cycling drill, a swim CSS set, a threshold-interval block). Drills are optional and additive to the session's free-composed `cardio_blocks`: they refine *how* this session trains the sport; they do not replace its main work. Most on-demand sessions carry none — reach for one only when it genuinely sharpens today's request.

- **At most one drill.** A session targets one technical or interval focus, not a drill circuit. Never emit more than one `cardio_drills` entry.
- **Pick only from the rendered pool, by id.** Choose an `exercise_id` from the menu only — never invent one, and never name a drill or drill-type that isn't in the menu. If no menu is rendered, prescribe no drill.
- **Match the drill to the requested sport.** The menu is grouped under discipline headers; only attach a drill that trains the sport the athlete asked for (a bike drill on a bike request, a swim set on a swim request). Never attach an unrelated-discipline drill.
- **A form/cadence drill does not replace steady aerobic work.** For a plain easy or steady session, prioritize the requested volume and intensity; reach for a cadence/single-leg/technique drill only when the athlete's note or the sport gives a specific reason, not as default seasoning.
- Give the drill a free-text `prescription` (e.g. "4×50m, focus on catch", "6×30s single-leg, 30s easy between") and brief `instructions`. `cardio_drills` rides `kind='cardio'` sessions only; leave it null on a strength session.

# Output discipline

- One tool call per invocation. Do not emit prose outside the tool call.
- All athlete-facing text fields are bounded by `maxLength` in the schema — be concise.
- `coaching_intent` is a one-line summary of the session's purpose; `session_notes` is 1-3 short sentences of context.
- Numeric durations always integers.
- Exercise IDs reference Layer 0B canonical IDs; populate `exercise_name` with the human-readable name.
- For interval_set cardio_blocks: emit `repetitions`, `rest_between_min`, `rest_intensity_zone`. For other block_kinds: leave those three fields null.
"""
    # #339 — variety carve-out (self-limiting: its guard clause defers to the
    # athlete's explicit on-demand sport pick, so it stays inert here while still
    # honoring non-variety Coaching-memory prefs surfaced in the user prompt).
    + "\n\n"
    + VARIETY_CARVEOUT_PROMPT_SECTION
)


def _render_user_prompt(
    request: SingleSessionRequest,
    layer1_payload: dict[str, Any],
    layer2c_payload_for_locale: Layer2CPayload | None,
    layer2d_payload: Layer2DPayload,
    layer3a_payload: Layer3APayload,
    session_date: _date_type,
    retries_used: int,
    rule_failures: list[RuleFailure],
    cardio_drill_pool_lines: list[str] | None = None,
) -> str:
    """Render the user prompt per `Layer4_SingleSession_v2.md` §6. Inline
    Python rendering instead of Mustache to avoid the dependency."""
    parts: list[str] = []

    # § Athlete request
    parts.append("# Athlete request")
    parts.append("")
    parts.append(f"Sport: {request.sport}")
    parts.append(f"Date: {session_date.isoformat()} ({session_date.strftime('%a')})")
    parts.append(f"Duration: {request.duration_min} min")
    parts.append(f"Intensity: {request.intensity}")
    if request.locale_slug:
        locale_label = (
            layer2c_payload_for_locale.locale_id
            if layer2c_payload_for_locale
            else request.locale_slug
        )
        parts.append(f"Location: {locale_label} (saved locale `{request.locale_slug}`)")
    else:
        parts.append("Location: Somewhere else (athlete-supplied equipment)")
    if request.notes_for_synthesizer:
        parts.append(f'Athlete note: "{request.notes_for_synthesizer}"')
    parts.append("")

    # § Athlete context
    parts.append("# Athlete context")
    parts.append("")
    parts.append(f"User ID: {layer3a_payload.user_id}")
    exp = layer1_payload.get("experience_level") or "unknown"
    parts.append(f"Experience level: {exp}")
    coach_notes = layer1_payload.get("coach_notes")
    if coach_notes:
        parts.append(f"Coach notes: {coach_notes}")
    # #337 — measured physiological anchors so the synthesizer grounds
    # intensity_target numbers in real values (suppress-on-empty).
    physiology_lines = format_measured_physiology(layer1_payload)
    if physiology_lines:
        parts.extend(physiology_lines)
    print(
        "single_session _render_user_prompt: measured_physiology surfaced="
        f"{bool(physiology_lines)}"
    )
    # #307 — surface the upstream coaching_flags advisory channel. Single
    # session only has the locale 2C + 2D payloads in scope (no 2A/2B).
    upstream_flag_lines = format_upstream_coaching_flags(
        layer2c_payloads=(
            [layer2c_payload_for_locale]
            if layer2c_payload_for_locale is not None
            else None
        ),
        layer2d=layer2d_payload,
    )
    if upstream_flag_lines:
        parts.extend(upstream_flag_lines)
    # #339 — surface the durable Coaching Memory block (#690 rendered it on
    # plan-create only); honors non-variety prefs (e.g. avoid-exercise notes)
    # for this ad-hoc session (suppress-on-empty).
    coaching_memory_lines = _format_coaching_memory(layer1_payload)
    if coaching_memory_lines:
        parts.extend(coaching_memory_lines)
    parts.append("")

    # § Active injuries — read from 2D excluded + accommodated lists
    parts.append("## Active injuries (hard constraints)")
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

    # § Equipment
    parts.append("# Equipment")
    parts.append("")
    if request.locale_slug and layer2c_payload_for_locale is not None:
        parts.append(f"## Curated equipment view ({layer2c_payload_for_locale.locale_id})")
        parts.append("")
        parts.append(
            "Effective equipment pool from Layer 2C — Tier 1 direct matches, Tier 2 "
            "athlete-listed substitutes, Tier 3 nearest-neighbor proxies. Prefer "
            "Tier 1 when present; Tier 2 acceptable; Tier 3 fallback only."
        )
        parts.append("")
        parts.append("Effective pool: " + ", ".join(layer2c_payload_for_locale.effective_pool))
        parts.append("")
        parts.append("Resolved exercises (subset):")
        # #691 — exclude tier-0 (equipment-infeasible, no substitute/proxy) so the
        # model never sees an unavailable exercise as a resolved option. Filter
        # before the 50-row cap so the subset is up to 50 *feasible* exercises.
        feasible_resolved = [
            rx for rx in layer2c_payload_for_locale.exercises_resolved if rx.tier != 0
        ]
        for rx in feasible_resolved[:50]:
            note = ""
            if rx.tier != 1 and rx.resolution_detail:
                note = f" (Tier {rx.tier}"
                if rx.resolution_detail.substitute_text:
                    note += f": {rx.resolution_detail.substitute_text}"
                elif rx.resolution_detail.proxy_exercise_id:
                    note += f": proxy {rx.resolution_detail.proxy_exercise_id}"
                note += ")"
            parts.append(f"- {rx.exercise_id} ({rx.exercise_name}){note}")
    else:
        parts.append("## Athlete-supplied equipment (no curated substitutes; exhaustive)")
        parts.append("")
        parts.append(", ".join(request.quick_equipment))
        parts.append("")
        parts.append(
            "There are no Tier 2/3 substitutes available — the athlete has supplied "
            "an exhaustive list. If the sport requires equipment beyond this list, "
            "fall back to bodyweight-doable variants in the same movement pattern "
            "and state the constraint in `session_notes`."
        )
    parts.append("")

    # § Recent training context
    parts.append("# Recent training context (drives intensity-modulation policy)")
    parts.append("")
    parts.append("## Layer 3A summary")
    parts.append("")
    cs = layer3a_payload.current_state
    parts.append(f"- Aerobic capacity: {cs.aerobic_capacity.level} ({cs.aerobic_capacity.confidence})")
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
    for disc_id, entry in rt.acwr_status.per_discipline.items():
        parts.append(
            f"- ACWR ({disc_id}): ratio={entry.ratio:.2f}, zone={entry.zone}"
        )
    parts.append(f"- Data density: {layer3a_payload.data_density.recent_workouts_count} recent workouts, "
                 f"{layer3a_payload.data_density.integration_data_days} days of integration data")
    parts.append("")

    # § Retry context
    if retries_used > 0:
        parts.append(f"# Retry context (retry pass {retries_used} of 2)")
        parts.append("")
        parts.append(
            "The deterministic validator flagged the prior pass. Adjust to clear "
            "these failures while preserving as much of the athlete's request as "
            "possible."
        )
        parts.append("")
        for rf in rule_failures:
            parts.append(
                f"- Rule: `{rf.rule_name}` | Severity: {rf.severity} | "
                f"Detail: {rf.detail}"
            )
        parts.append("")

    # § Cardio drill pool — #698 Track 2 (Slice C1). Grouped by discipline +
    # carrying each row's coaching_cue dose; bound to the tool-schema enum via
    # compute_cardio_drill_pool_ids. Suppress-on-empty: no menu → the LLM is
    # never handed an unfillable cardio_drills[] (mirrors plan-create + §6a-G1).
    if cardio_drill_pool_lines:
        parts.append("=== Cardio drill pool (consider these) ===")
        parts.append(
            "Optionally attach one drill appropriate to the requested sport, from "
            "the pool below (pick by id only):"
        )
        parts.extend(cardio_drill_pool_lines)
        parts.append("")

    # § Task
    parts.append("# Your task")
    parts.append("")
    parts.append(
        "Produce one workout session matching the athlete's request. Apply the "
        "intensity-modulation policy. Respect injury exclusions absolutely. Stay "
        "within the equipment available. Emit via the `record_single_session` "
        "tool. One tool call. No prose outside the tool call."
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


# ─── Tool output → PlanSession + Layer4Payload ───────────────────────────────


def _build_plan_session(
    session_data: dict[str, Any],
    *,
    session_id: str,
    plan_version_id: int,
    request: SingleSessionRequest,
) -> PlanSession:
    """Wrap a session dict from the synthesizer tool output into a
    `PlanSession`. Fills `is_ad_hoc=True`, `ad_hoc_request_payload`,
    `phase_metadata=None`, `session_id`, `plan_version_id`."""
    # Normalize cardio_blocks / strength_exercises from raw dicts into typed
    # models; pydantic smart-union handles the IntensityTarget shape dispatch.
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
        is_ad_hoc=True,
        ad_hoc_request_payload=request.model_dump(mode="json"),
    )


def _parse_date(s: str) -> _date_type:
    return datetime.fromisoformat(s).date() if "T" in s else _date_type.fromisoformat(s)


def _build_layer4_payload(
    *,
    user_id: int,
    session: PlanSession,
    plan_version_id: int,
    suggestion_id: int,
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
    """Compose the final Layer4Payload per `Layer4_Spec.md` §3.3:
    `mode='single_session_synthesize'`, `pattern='B'`,
    `phase_structure=None`, `seam_reviews=None`, `len(sessions)==1`,
    `sessions[0].is_ad_hoc=True`, `suggestion_id` populated."""
    return Layer4Payload(
        user_id=user_id,
        mode="single_session_synthesize",
        plan_version_id=plan_version_id,
        scope_start_date=session.date,
        scope_end_date=session.date,
        model_synthesizer=model,
        model_seam_reviewer=None,
        temperature=temperature,
        pattern="B",
        latency_ms_total=latency_ms_total,
        input_tokens_total=input_tokens_total,
        output_tokens_total=output_tokens_total,
        llm_call_count=llm_call_count,
        etl_version_set=etl_version_set,
        sessions=[session],
        phase_structure=None,
        seam_reviews=None,
        shape_override=None,
        validator_results=validator_results,
        notable_observations=notable_observations,
        suggestion_id=suggestion_id,
        race_week_brief=None,
        race_plan=None,
    )


def _emit_intensity_modulated_observation(session: PlanSession) -> Observation | None:
    """Per §8.7: when the LLM emits the `intensity_modulated` session flag,
    the orchestrator side emits a paired `Observation(category=
    'intensity_modulated')`. Returns None when the flag isn't present."""
    if "intensity_modulated" in session.coaching_flags:
        return Observation(
            category="intensity_modulated",
            text=(
                "Synthesizer modulated the prescribed intensity from the athlete's "
                "picked value; see session_notes for the rationale."
            ),
            evidence_basis=["Layer4_Spec.md §8.6 + §8.7"],
            elevates_to_hitl=False,
        )
    return None


# ─── Entry point: llm_layer4_single_session_synthesize ───────────────────────


def llm_layer4_single_session_synthesize(
    user_id: int,
    request: SingleSessionRequest,
    layer1_payload: dict[str, Any],
    layer2c_payload_for_locale: Layer2CPayload | None,
    layer2d_payload: Layer2DPayload,
    layer3a_payload: Layer3APayload,
    suggestion_id: int,
    etl_version_set: dict[str, str],
    *,
    model: str = "claude-sonnet-4-6",
    temperature: float = 0.3,
    max_tokens: int = 1500,
    capped_retries: int = 2,
    extended_thinking_budget: int = 3500,
    plan_version_id: int = 0,
    session_date: _date_type | None = None,
    llm_caller: LLMCaller | None = None,
) -> Layer4Payload:
    """Pattern B single-call synthesizer for D-63 on-demand workouts per
    `Layer4_Spec.md` §3.3.

    Algorithm (§5.3 Pattern B + §5.5 capped retry):
    1. Validate inputs per §4.4 — raises `Layer4InputError` on precondition
       fail.
    2. Build the user prompt with full payload context.
    3. Invoke synthesizer; parse `record_single_session` tool output into a
       `PlanSession`; wrap into a `Layer4Payload`.
    4. Run §5.4 deterministic validator harness (mode-gated to the
       single-session-relevant rules).
    5. On validator failure, retry up to `capped_retries` (default 2) with
       `RuleFailure` context merged into the user prompt.
    6. On cap-hit with unresolved blockers: ship the latest synthesis as
       best-effort with an orchestrator-emitted
       `Observation(category='best_effort_plan', elevates_to_hitl=True)`;
       outstanding `blocker`-severity failures demote to `warning` per
       §5.5.

    The `plan_version_id` param defaults to 0 because §3.3 specifies
    `plan_version_id=None` for D-63 outputs — but the Layer4Payload schema
    requires non-None int. v1 uses 0 as the sentinel for "ad-hoc, no plan
    pinning"; v2 may revisit. Orchestrator can override via the param.

    The `session_date` param defaults to today() when not specified —
    D-63's typical UX fires for "today's workout."

    The `llm_caller` param is dependency-injectable for tests; production
    callers leave it as None to use the Anthropic SDK default."""
    _validate_inputs(request, layer2c_payload_for_locale, layer2d_payload, layer3a_payload)

    if session_date is None:
        session_date = _date_type.today()

    caller: LLMCaller = llm_caller or _default_llm_caller
    locale_l2c = (
        {layer2c_payload_for_locale.locale_id: layer2c_payload_for_locale}
        if layer2c_payload_for_locale is not None
        else {}
    )
    feasible_pool_ids = (
        compute_feasible_pool_ids(locale_l2c, layer2d_payload)
        if layer2c_payload_for_locale is not None
        else []
    )
    # #698 Track 2 (Slice C1) — on-demand cardio drill pool. single_session is
    # phase-agnostic (no periodization phase → pass permissive "Base" so no
    # character-by-phase drop) and has no layer2a; the discipline set is the
    # union of disciplines trainable at the picked locale (the menu groups by
    # discipline + the prompt tells the LLM to match today's requested sport —
    # G5 discipline-scope-via-prompt). Off-locale ("somewhere else", no 2C) →
    # empty pool → suppressed block + free-string schema.
    cardio_drill_disciplines: set[str] = (
        {
            d
            for rx in layer2c_payload_for_locale.exercises_resolved
            for d in rx.discipline_ids
        }
        if layer2c_payload_for_locale is not None
        else set()
    )
    cardio_drill_pool_ids = compute_cardio_drill_pool_ids(
        locale_l2c,
        layer2d_payload,
        disciplines=cardio_drill_disciplines,
        phase="Base",
    )
    cardio_drill_pool_lines = _format_cardio_drill_pool(
        locale_l2c,
        None,
        layer2d_payload,
        disciplines=cardio_drill_disciplines,
        phase="Base",
    )
    tool_schema = build_record_single_session_tool(
        feasible_pool_ids=feasible_pool_ids or None,
        cardio_drill_pool_ids=cardio_drill_pool_ids or None,
    )

    rule_failures: list[RuleFailure] = []
    validator_results: list[ValidatorResult] = []
    session_id = f"S-{uuid.uuid4().hex[:12]}"

    total_input_tokens = 0
    total_output_tokens = 0
    total_latency_ms = 0
    llm_call_count = 0
    cap_hit = False

    latest_session: PlanSession | None = None
    latest_validator: ValidatorResult | None = None

    for retries_used in range(capped_retries + 1):
        user_prompt = _render_user_prompt(
            request=request,
            layer1_payload=layer1_payload,
            layer2c_payload_for_locale=layer2c_payload_for_locale,
            layer2d_payload=layer2d_payload,
            layer3a_payload=layer3a_payload,
            session_date=session_date,
            retries_used=retries_used,
            rule_failures=rule_failures,
            cardio_drill_pool_lines=cardio_drill_pool_lines,
        )

        try:
            llm_out = caller(
                _SYSTEM_PROMPT,
                user_prompt,
                tool_schema,
                model,
                temperature,
                max_tokens,
                extended_thinking_budget,
            )
        except Layer4OutputError:
            raise

        llm_call_count += 1
        total_input_tokens += llm_out.input_tokens
        total_output_tokens += llm_out.output_tokens
        total_latency_ms += llm_out.latency_ms

        session_data = llm_out.tool_args.get("session")
        if not isinstance(session_data, dict):
            raise Layer4OutputError(
                "schema_violation",
                detail="tool args missing 'session' object",
            )

        # #803 — set strength resolution_tier/substitute_text/proxy_origin_id
        # deterministically from the locale's 2C resolution before construction
        # (mirrors per_phase). Only when a locale surface exists; the
        # locale-agnostic path has no resolution map to derive from.
        if layer2c_payload_for_locale is not None:
            _res_notes = _apply_strength_resolution(
                [session_data],
                {layer2c_payload_for_locale.locale_id: layer2c_payload_for_locale},
            )
            if _res_notes:
                print(
                    "single_session: strength resolution defaulted to exact for "
                    f"unresolved picks: {', '.join(_res_notes)}"
                )

        try:
            session = _build_plan_session(
                session_data,
                session_id=session_id,
                plan_version_id=plan_version_id,
                request=request,
            )
        except (ValidationError, KeyError, ValueError) as e:
            # Schema-violation special case per §5.5: ONE retry on malformed
            # output that doesn't consume the per-call budget. Bail on the
            # second failure.
            if retries_used >= capped_retries:
                raise Layer4OutputError(
                    "schema_violation",
                    detail=f"tool output did not parse as PlanSession: {e}",
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

        latest_session = session
        payload_attempt = _build_layer4_payload_for_validation(
            user_id=user_id,
            session=session,
            plan_version_id=plan_version_id,
            suggestion_id=suggestion_id,
            model=model,
            temperature=temperature,
            etl_version_set=etl_version_set,
        )

        ctx = ValidatorContext(
            layer2c_payloads={
                layer2c_payload_for_locale.locale_id: layer2c_payload_for_locale
            }
            if layer2c_payload_for_locale is not None
            else {},
            layer2d_payload=layer2d_payload,
            layer3a_payload=layer3a_payload,
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

    assert latest_session is not None and latest_validator is not None
    assert validator_results, "validator_results must be non-empty"

    # Best-effort acceptance per §5.5: if cap was hit with blocker failures,
    # demote them to warnings + append an accepted ValidatorResult so the
    # Layer4Payload contract (`validator_results[-1].accepted == True`) is
    # satisfied.
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

    intensity_obs = _emit_intensity_modulated_observation(latest_session)
    if intensity_obs is not None:
        notable_observations.append(intensity_obs)

    return _build_layer4_payload(
        user_id=user_id,
        session=latest_session,
        plan_version_id=plan_version_id,
        suggestion_id=suggestion_id,
        model=model,
        temperature=temperature,
        validator_results=validator_results,
        notable_observations=notable_observations,
        etl_version_set=etl_version_set,
        input_tokens_total=total_input_tokens,
        output_tokens_total=total_output_tokens,
        latency_ms_total=total_latency_ms,
        llm_call_count=llm_call_count,
    )


def _build_layer4_payload_for_validation(
    *,
    user_id: int,
    session: PlanSession,
    plan_version_id: int,
    suggestion_id: int,
    model: str,
    temperature: float,
    etl_version_set: dict[str, str],
) -> Layer4Payload:
    """Build a Layer4Payload mid-retry for validator-input purposes. Uses a
    placeholder accepted ValidatorResult so the payload's
    `validator_results[-1].accepted` invariant doesn't trip during
    construction; the real validator pass runs against this payload and the
    final composition uses `_build_layer4_payload`."""
    return Layer4Payload(
        user_id=user_id,
        mode="single_session_synthesize",
        plan_version_id=plan_version_id,
        scope_start_date=session.date,
        scope_end_date=session.date,
        model_synthesizer=model,
        model_seam_reviewer=None,
        temperature=temperature,
        pattern="B",
        latency_ms_total=0,
        input_tokens_total=0,
        output_tokens_total=0,
        llm_call_count=0,
        etl_version_set=etl_version_set,
        sessions=[session],
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
        suggestion_id=suggestion_id,
        race_week_brief=None,
        race_plan=None,
    )


__all__ = [
    "SingleSessionRequest",
    "build_record_single_session_tool",
    "llm_layer4_single_session_synthesize",
]
