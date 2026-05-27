"""Layer 4 — Per-phase synthesizer for Pattern A orchestration.

Implements `Layer4_Spec.md` §5.2 step 3 (per-phase synthesis loop) + the
`Layer4_PerPhase_v2.md` prompt body (v1 → v2 surgical amendment per Step 4f
bringing the tool schema up to D1 typed IntensityTarget union + the PR-C-followon
2D AccommodationModality input contract + the D-66 RaceEventPayload field).

Driver-level orchestration of Pattern A (per-phase synth loop + seam review
loop + final cross-phase validator pass + Layer4Payload composition) lives in
`layer4/plan_create.py`. This module owns one slice: build the
`record_phase_sessions` tool schema, render the per-phase user prompt, invoke
the synthesizer LLM, parse the output into typed `PlanSession` rows with
`phase_metadata` populated from the `PhaseSpec`, run the §5.4 validator
scoped to the phase, and capped-retry per §5.5.

Validator-driven retries and seam-driven re-syntheses share the per-phase
retry counter per §5.5 — the caller passes `seam_issues` (constraint deltas
from the seam reviewer) into `synthesize_phase()` for the seam-driven path;
the function increments the retry counter regardless of the trigger.

**Coaching-flag enum (per Layer4_PerPhase_v1.md D5):** 6 LLM-emitted flags
covering the §8.2–§8.6 closed set excluding `intensity_modulated` (which is
emitted on refresh paths per §8.6/§8.7 broadening but NOT on plan_create
where there is no athlete-intent surface to deviate from) and spec-auto
flags (which the orchestrator stamps post-synthesis per §8.1).
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import date as _date_type, datetime, timedelta
from typing import Any, Callable, Literal

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
from layer4.errors import Layer4OutputError
from layer4.payload import (
    CardioBlock,
    Layer4Payload,
    Observation,
    PhaseSpec,
    PhaseStructure,
    PlanSession,
    RuleFailure,
    SessionPhaseMetadata,
    StrengthExercise,
    SynthesisMetadata,
    ValidatorResult,
)
from layer4.validator import ValidatorContext, validate_layer4_payload


# ─── Constants per Layer4_PerPhase_v2.md §7 + §3.4 ───────────────────────────


DEFAULT_MAX_TOKENS = 4000
"""Per `Layer4_Spec.md` §3.1 default `max_tokens_per_phase`."""

DEFAULT_EXTENDED_THINKING_BUDGET = 5000
"""Per `Layer4_PerPhase_v1.md` D2 (max-defensive — synthesizer is judgment-heavy
AND combinatorial)."""

_MAX_SESSIONS_PER_PHASE = 56
"""Bounded-collection ceiling for the `sessions` array. Kept lock-step with the
`maxItems` passed to `build_record_phase_sessions_tool` (the tool default); the
schema bound is only an Anthropic API hint, so the driver clamps over-emit
pre-validation (same over-emit-vs-cap guard applied to Layer 3A/3B)."""

_MAX_SESSIONS_PER_WEEK = 14
"""Per-week session ceiling (D-77 §4.2): a worst-case high-frequency week — 6
disciplines + strength with occasional doubles. The per-block `maxItems` +
over-emit clamp scale from this × the block's week count."""

_PER_BLOCK_BUDGET_MS = 120_000
"""D-77 §6 per-block synthesis budget (accumulated LLM latency). A block's
capped-retry stack runs multiple sequential extended-thinking calls in ONE
non-resumable function invocation; if the stack exceeds the immovable 300s
Vercel cap it 504-kills mid-loop, caches nothing, and the next pass restarts it
from attempt 1 — an infinite loop the wall-clock backstop only converts into a
loud failure after ~900s. This bound stops the loop from STARTING another
attempt once the block has spent its LLM-time budget, so a block always RETURNS
within the function cap: it caches the best parseable attempt as best-effort
(§5.5 cap-hit) or fails terminally fast. 120s leaves headroom for one more
in-flight attempt under the 300s cap. The first attempt is never gated."""

_BLOCK_OUTPUT_TOKENS_PER_SESSION = 600
"""D-77 §6 follow-on. A dense PlanSession (cardio_blocks with per-block intensity
targets + strength_exercises arrays + 240-char notes/instructions) serializes to
~400-600 output tokens; budget the worst case so a full high-frequency week-block
fits its `max_tokens` without truncating mid-`sessions`."""

_BLOCK_OUTPUT_TOKENS_OVERHEAD = 800
"""Fixed block output budget on top of the per-session estimate: covers
`phase_synthesis_notes` (≤600 chars), `opportunities` (3×≤240 chars), and the
JSON envelope/scaffolding."""


# Per `Layer4_PerPhase_v1.md` D5: closed set of 6 LLM-emitted coaching flags.
# Spec-auto flags (`recovery_week`, `peak_volume_marker`, `race_rehearsal`,
# `fueling_practice`, `kit_check`, `pacing_lock`, `pre_race_taper`) are
# orchestrator-stamped post-synthesis per §8.1 + §8.5; not in this enum.
_PHASE_COACHING_FLAGS = [
    "technique_emphasis",
    "long_slow_distance",
    "weak_link_targeted",
    "overreach_test",
    "discipline_specific_intensity",
    "race_pace_specific",
]


# Per-mode deload-cadence anchor — per `Layer4_PerPhase_v1.md` D6.
_DELOAD_CADENCE: dict[
    Literal["standard", "compressed", "extended", "custom"], int | None
] = {
    "standard": 4,
    "compressed": 3,
    "extended": 5,
    "custom": None,
}


# Per `Layer4_PerPhase_v1.md` D7: Taper-length anchor table per race format.
# Information-only — the prompt surfaces these to the model, which picks
# within the §6.1 proportion budget.
_TAPER_ANCHOR_BY_FORMAT: dict[str, str] = {
    "single_day": "1–2 weeks (sub-marathon to half-marathon)",
    "marathon": "2–3 weeks (marathon / Olympic-distance)",
    "ironman_70_3": "2–3 weeks (IM 70.3)",
    "ironman_full": "3 weeks (full IM)",
    "continuous_multi_day": "3 weeks (continuous multi-day: expedition AR / multi-day ultra, 24–72h+)",
    "stage_race": "3 weeks (stage race)",
}


SYSTEM_PROMPT = """You are AIDSTATION's Layer 4 per-phase synthesizer.

You are called once per periodization phase (Base / Build / Peak / Taper) inside Pattern A orchestration (plan_create + plan_refresh T3 cross-phase). Your job is to produce a complete day-by-day `list[PlanSession]` for ONE phase — typically 3–10 weeks — given the athlete's full upstream context plus the prior phase's accepted output (when this is not the first phase synthesized) and the phase's intended exit/entry state.

# What you produce

Exactly one tool call to `record_phase_sessions` with:

- `sessions`: list of PlanSession rows covering `phase_start_date` through `phase_end_date` inclusive. One row per (date, session_index_in_day). Maximum 2 sessions per day per `Layer4_Spec.md` §7.12. Athletes pick their own schedule per Layer 1 §K — respect available days + per-day windows; do not prescribe on `available=False` days unless explicitly flagged `athlete_self_scheduled`.
- `phase_synthesis_notes`: ≤600 chars rationale for the phase shape — deload placement, key-session anchor placement, the connection to prior phase, any judgment calls. This persists into `plan_versions.notes` JSONB.
- `opportunities`: optional, up to 3 entries; each is an athlete-facing observation about something the plan could capitalize on (e.g., "athlete reports new climbing access — added technique block in Build wk 3"). Per `Layer4_Spec.md` §8.7 LLM-emitted exception.

# Coaching voice (apply to session_notes, coaching_intent, instructions, phase_synthesis_notes)

- Direct. Factual. Evidence-grounded.
- No platitudes ("great workout!"), no hype ("crush it!"), no cheerleading ("you've got this!").
- Tone matches a real endurance coach talking to a serious athlete.
- Short sentences. Plain English. No emoji.

# Phase intent — the spine of your output

Each phase has an intended volume band per discipline (from 2A `phase_load_bands`) and an intended intensity distribution (Base ≈ 80/15/5 Z1-Z2/Z3/Z4-Z5; Build ≈ 70/20/10; Peak ≈ 70/20/10 — shares Build's shape; race-pace differentiation surfaces via the `race_pace_specific` per-session flag rather than zone-distribution; Taper ≈ 75/15/10). Per-week volume should land inside the band ±10%; per-phase intensity distribution within ±10pp of intended.

Volume shape across the phase typically ramps with one deload week per mode anchor. The deload week reduces volume to the lower edge of the band and biases intensity toward Z1-Z2; the orchestrator stamps `recovery_week` spec-auto.

# Coaching-flag emission (closed-set; 6 flags LLM-emitted)

These six flags are the only flags you emit. Other flags (`recovery_week`, `peak_volume_marker`, `race_rehearsal`, `fueling_practice`, `kit_check`, `pacing_lock`, `pre_race_taper`) are spec-auto stamped by the orchestrator from phase + scheduling context — DO NOT emit them.

- `technique_emphasis` — session is built around a skill-development focus (e.g., swim drill set; running-form work). Phase-appropriate in any phase but most natural in Base / early Build.
- `long_slow_distance` — the week's LSD cornerstone session per discipline. Exactly one per (week, discipline) in Base + Build typically; Peak retains LSD on the primary discipline; Taper drops LSD.
- `weak_link_targeted` — session is built around a Layer 3A `weak_links` accessory or skill block.
- `overreach_test` — deliberate intentional-overload session to test ceiling (typically Peak — paired with extra recovery before + after).
- `discipline_specific_intensity` — hard session whose intensity targets a specific race-format demand (e.g., long climbing intervals for skimo; sustained tempo for marathon).
- `race_pace_specific` — session prescribes race-pace work. Peak-only (per `Layer4_Spec.md` §8.4); never emit in Base / Build / Taper. Open-ended mode (no `race_format`) never emits this flag.

# Injury exclusions (hard constraints; never overridable)

2D `excluded_exercises` are hard constraints. Never prescribe an excluded exercise. 2D `accommodated_exercises` carry per-modality accommodations (volume / intensity / tempo / loading-type / frequency reduction) — when prescribing one, honor the modality per `Layer2D_Spec.md` §5.3.6. The validator's `injury_violation_*` rule is a defensive set-membership check; the prompt's job is to NOT propose excluded exercises in the first place.

# Equipment respect

Layer 2C per-locale `effective_pool` + `exercises_resolved` (Tier 1 direct / Tier 2 athlete-listed substitute / Tier 3 nearest-neighbor proxy) is your equipment surface for strength prescriptions. Prefer Tier 1 when present; Tier 2 acceptable; Tier 3 fallback only. Each session has one `locale_id` — all blocks within a session must resolve at that locale (single-locale-per-session invariant per `Layer4_Spec.md` §5.4 rule 6b).

# Schedule respect

Layer 1 §K `daily_availability_windows` per-day windows: prescribe on `available=True` days only; session `duration_min` must fit within the day's window minutes (validator: `daily_window_fit_*`). Sessions on `available=False` days raise unless explicitly flagged `athlete_self_scheduled` (not in this flag enum — orchestrator path only). The athlete's **long-session day** is the day carrying the longest enabled window — FormRefresh Slice C retired the standalone long-session input, so the longest window now *is* the long-session capacity. Anchor the primary discipline's weekly `long_slow_distance` cornerstone (flag list above) on that day; secondary-discipline LSDs fit their own longest available day. The `=== Schedule ===` block names the computed long-session day.

# Race-event context (D-66)

When `race_event_payload` is non-None, the plan is targeting a real race event:
- `race_format`: structural axis driving the Taper anchor (single_day ≈ 1–2 wks; marathon-IM-class ≈ 2–3 wks; continuous_multi_day / stage_race ≈ 3+ wks). Sport/discipline specifics live on `framework_sport` + the discipline set, not here.
- `route_locales[]` (multi-day): D-66 structured graph — sequenced anchor locales (start / transition_area / aid_station / drop_bag_point / bivvy / finish). The synthesizer reads but is not the primary consumer (that's the race-week brief).
- Open-ended mode (race_event_payload is None): use the open-ended 12-week horizon default; do not emit `race_pace_specific`.

# Continuity context (prior-phase + carryover)

When `phase_index_in_plan > 0`, the prior phase's accepted output is the seam-in: aim to land the first week of THIS phase at the prior phase's exit state. Specifically, the prior week's last session shapes the rest day decision; the prior week's weekly aggregate informs the first week's volume target.

When `start_phase != 'Base'` (athlete starts partway through), the prior phase's "exit state" is synthetic — derived from 2A `phase_load_bands` for the immediately-skipped phase. The synthesizer reads this synthetic context but should NOT flag missing earlier-phase preparation (the athlete is starting partway).

# Output discipline

- One tool call per invocation. No prose outside the tool call.
- Each cardio_block requires an `intensity_zone` (Z1-Z5 or mixed) and an `intensity_target` matching the sport (HRTarget endurance / PowerTarget bike-run-skimo-row / PaceTarget run-hike-paddle-ski / SwimPaceTarget swim / RPETarget universal-fallback / VerticalRateTarget skimo-hiking / StrokeRateTarget swim-paddle-row / CadenceTarget cycling / ClimbingGradeTarget outdoor-rock).
- `interval_set` cardio_blocks emit `repetitions` + `rest_between_min` + `rest_intensity_zone`. Other block_kinds leave those three null.
- Strength `exercise_id` references Layer 0B canonical IDs; populate `exercise_name`. `resolution_tier` 1 / 2 / 3 maps to 2C's substitution metadata; `substitute_text` set for tier 2; `proxy_origin_id` set for tier 3.
- All athlete-facing text fields are bounded by `maxLength` in the schema — be concise. `session_notes` 1–3 sentences; `coaching_intent` one line.
"""


# ─── Tool schema (record_phase_sessions) ─────────────────────────────────────


def _intensity_target_schema() -> dict[str, Any]:
    """9-shape discriminated `IntensityTarget` `oneOf` union per
    `layer4/payload.py` §7.3. Mirrors single_session.py + plan_refresh.py."""
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


def _session_schema() -> dict[str, Any]:
    """One element of `sessions[]`. Full PlanSession contract mirror per the
    Step 4a Option 2 precedent. Includes `rest` kind (Pattern A produces full
    schedules including rest days; differs from refresh/single_session which
    only emit working sessions)."""
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
            "kind": {"type": "string", "enum": ["cardio", "strength", "rest"]},
            "discipline_id": {"type": ["string", "null"]},
            "discipline_name": {"type": ["string", "null"]},
            "locale_id": {"type": ["string", "null"]},
            "locale_name": {"type": ["string", "null"]},
            "duration_min": {"type": "integer", "minimum": 0, "maximum": 480},
            "intensity_summary": {
                "type": "string",
                "enum": ["easy", "moderate", "hard", "mixed", "rest"],
            },
            "session_notes": {"type": "string", "maxLength": 240},
            "coaching_intent": {"type": "string", "maxLength": 200},
            "coaching_flags": {
                "type": "array",
                "items": {"type": "string", "enum": _PHASE_COACHING_FLAGS},
                "maxItems": 6,
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
                        "exercise_id": {"type": "string"},
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


def build_record_phase_sessions_tool(max_sessions: int = 56) -> dict[str, Any]:
    """Anthropic tool definition for `record_phase_sessions`. Sessions array
    `maxItems` accommodates up to 4 weeks × 7 days × 2/day = 56 for the
    longest typical phase (Base in standard mode 12 wks would split across
    multiple synthesizer calls in v2 if budget pressure surfaces; v1 single
    call per phase). Caller can override `max_sessions` for tighter caps."""
    return {
        "name": "record_phase_sessions",
        "description": (
            "Record the synthesized PlanSession list for one periodization phase. "
            "Output covers `phase_start_date` through `phase_end_date` inclusive. "
            "Emit exactly one tool call per invocation."
        ),
        "input_schema": {
            "type": "object",
            "additionalProperties": False,
            "required": ["sessions", "phase_synthesis_notes"],
            "properties": {
                "sessions": {
                    "type": "array",
                    "minItems": 0,
                    "maxItems": max_sessions,
                    "items": _session_schema(),
                },
                "phase_synthesis_notes": {
                    "type": "string",
                    "maxLength": 600,
                },
                "opportunities": {
                    "type": ["array", "null"],
                    "maxItems": 3,
                    "items": {"type": "string", "maxLength": 240},
                },
            },
        },
    }


# ─── Prompt rendering (Layer4_PerPhase_v2.md §6) ─────────────────────────────


def _format_active_injuries(layer2d: Layer2DPayload | None) -> list[str]:
    """Render 2D excluded + accommodated exercises for the active-injury
    block per the PR-C-followon v2 amendment (replaces the v1 prompt's
    reference to 3A `active_injuries.restriction_text` which never existed
    in 3A's typed contract — canonical injury source is 2D)."""
    if layer2d is None:
        return ["- (Layer 2D payload not supplied; no injury exclusions in scope.)"]
    out: list[str] = []
    if not layer2d.excluded_exercises and not layer2d.accommodated_exercises:
        out.append("- None on file.")
        return out
    for er in layer2d.excluded_exercises:
        out.append(f"- EXCLUDE {er.exercise_id} ({er.exercise_name})")
    for er in layer2d.accommodated_exercises:
        mod_list = ", ".join(m.modality_type for m in er.accommodations)
        out.append(
            f"- ACCOMMODATE {er.exercise_id} ({er.exercise_name}): {mod_list}"
        )
    return out


def _format_phase_load_bands(
    layer2a: Layer2APayload | None, phase_name: str
) -> list[str]:
    """Per-discipline volume bands for the phase per 2A `phase_load_bands`."""
    if layer2a is None:
        return ["- (Layer 2A payload not supplied; using open-ended bands.)"]
    out: list[str] = []
    for d in layer2a.disciplines:
        if d.inclusion != "included":
            continue
        pl = d.phase_load
        if phase_name == "Base":
            low, high = pl.base_low, pl.base_high
        elif phase_name == "Build":
            low, high = pl.build_low, pl.build_high
        elif phase_name == "Peak":
            low, high = pl.peak_low, pl.peak_high
        elif phase_name == "Taper":
            low, high = pl.taper_low, pl.taper_high
        else:
            continue
        out.append(
            f"- {d.discipline_name} ({d.discipline_id}): {low:.1f}–{high:.1f} hr/wk"
        )
    if not out:
        out.append("- (No included disciplines on file.)")
    return out


def _format_weekly_rollup_for_prior_phase(sessions: list[PlanSession]) -> list[str]:
    """Compute a weekly rollup table from prior-phase accepted sessions.
    Per-week (week_in_phase, discipline) — total volume hours, zone breakdown,
    session count, key per-session flag list.

    The prior phase's sessions carry `phase_metadata` non-None (Pattern A
    output) so `week_in_phase` is read directly. When a session lacks
    phase_metadata (defensive — shouldn't happen for Pattern A output), it's
    skipped from the rollup."""
    if not sessions:
        return ["- (No prior-phase sessions to roll up.)"]

    @dataclass
    class _WeekBucket:
        total_hours: float = 0.0
        z12_hours: float = 0.0
        z3_hours: float = 0.0
        z45_hours: float = 0.0
        session_count: int = 0
        flags: list[str] = field(default_factory=list)

    buckets: dict[tuple[int, str], _WeekBucket] = {}
    for s in sessions:
        if s.phase_metadata is None:
            continue
        key = (s.phase_metadata.week_in_phase, s.discipline_id or "(none)")
        bucket = buckets.setdefault(key, _WeekBucket())
        hours = s.duration_min / 60.0
        bucket.total_hours += hours
        bucket.session_count += 1
        for f in s.coaching_flags:
            if f not in bucket.flags:
                bucket.flags.append(f)
        # Zone bucketing: walk cardio_blocks, sum by zone family.
        if s.cardio_blocks:
            for cb in s.cardio_blocks:
                z = cb.intensity_zone
                cb_h = cb.duration_min / 60.0
                if z in ("Z1", "Z2"):
                    bucket.z12_hours += cb_h
                elif z == "Z3" or z == "mixed":
                    bucket.z3_hours += cb_h
                elif z in ("Z4", "Z5"):
                    bucket.z45_hours += cb_h

    out: list[str] = ["| Week | Discipline | Total hrs | Z1-Z2 hrs | Z3 hrs | Z4-Z5 hrs | Sessions | Flags |"]
    out.append("|---|---|---|---|---|---|---|---|")
    for (wk, disc), b in sorted(buckets.items()):
        flags_str = ", ".join(b.flags) if b.flags else "—"
        out.append(
            f"| {wk} | {disc} | {b.total_hours:.1f} | {b.z12_hours:.1f} | "
            f"{b.z3_hours:.1f} | {b.z45_hours:.1f} | {b.session_count} | {flags_str} |"
        )
    return out


def _format_prior_phase_last_week(sessions: list[PlanSession]) -> list[str]:
    """Render the last week of the prior phase's sessions verbatim (the
    seam-in). Per Layer4_PerPhase_v1.md D4 hybrid rendering."""
    if not sessions:
        return ["- (No prior-phase sessions.)"]
    last_date = max(s.date for s in sessions)
    week_start = last_date - timedelta(days=6)
    last_week = [s for s in sessions if s.date >= week_start]
    last_week.sort(key=lambda s: (s.date, s.session_index_in_day))
    out: list[str] = ["| Date | Day | Idx | Kind | Sport | Duration | Intensity | Flags |"]
    out.append("|---|---|---|---|---|---|---|---|")
    for s in last_week:
        flags_str = ", ".join(s.coaching_flags) if s.coaching_flags else "—"
        out.append(
            f"| {s.date.isoformat()} | {s.day_of_week} | {s.session_index_in_day} | "
            f"{s.kind} | {s.discipline_id or '—'} | {s.duration_min} min | "
            f"{s.intensity_summary} | {flags_str} |"
        )
    return out


def _format_route_locales(race_event: RaceEventPayload | None) -> list[str]:
    """Per the v2 D-66 amendment: render the structured `route_locales[]`
    graph when present. Multi-day events only; single_day events have None
    or empty route_locales."""
    if race_event is None:
        return []
    out: list[str] = []
    out.append("")
    out.append(
        f"=== Race event (D-66) — {race_event.race_format} ==="
    )
    out.append(f"Event date: {race_event.event_date.isoformat()}")
    out.append(f"Event name: {race_event.name}")
    if race_event.distance_km is not None:
        out.append(f"Distance: {race_event.distance_km} km")
    if race_event.estimated_duration_hr is not None:
        out.append(f"Estimated duration: {race_event.estimated_duration_hr} hr")
    if race_event.total_elevation_gain_m is not None:
        out.append(f"Elevation gain: {race_event.total_elevation_gain_m} m")
    if race_event.route_locales:
        out.append("Route locales (sequenced):")
        for rl in race_event.route_locales:
            entry = (
                f"- [{rl.sequence_idx}] {rl.role}: {rl.name}"
            )
            if rl.mile_marker is not None:
                entry += f" (mile {rl.mile_marker})"
            if rl.notes:
                entry += f" — {rl.notes}"
            out.append(entry)
    return out


def _format_training_substitution_per_phase(
    payload: TrainingSubstitutionPayload,
) -> list[str]:
    """Render the training-substitution brief for the per-phase prompt.

    Convention: `=== Section ===` header + one compact line per discipline to
    match per_phase.py's `=== Race + locale + equipment ===` idiom. Per
    discipline: the race craft + the craft candidate set (the LLM picks the
    closest trainable craft), the terrain training emphasis ranked by
    `pct × fidelity`, and the terrain that can't be trained locally. Empty
    payload renders an explanatory line so the LLM doesn't infer a silent
    omission.
    """
    lines: list[str] = ["=== Best-fit training substitution (per discipline) ==="]
    lines.append(
        "Surfaced from the Layer 2 training-substitution resolver (race terrain "
        "× local trainability). Bias each phase's sessions toward the "
        "highest-emphasis trainable terrain; name compensation work for terrain "
        "that can't be trained locally. Peak biases the highest-fidelity proxies "
        "+ race-craft specificity; Taper biases lower-stimulus trainable terrain."
    )
    if not payload.recommendations and not payload.coaching_flags:
        lines.append("(No training-substitution recommendations for this discipline set.)")
        lines.append("")
        return lines
    for rec in payload.recommendations:
        crafts = ", ".join(rec.candidate_training_crafts) or "(none logged)"
        label = (
            f"{rec.discipline_id} {rec.discipline_name} (race craft: "
            f"{rec.race_craft}; candidate crafts: {crafts})"
        )
        emph = "; ".join(
            f"{e.terrain_name or e.race_terrain_id} {e.pct:g}% "
            f"(proxy {e.proxy_terrain_name or e.proxy_terrain_id} @{e.fidelity:.2f})"
            for e in rec.terrain_emphasis
        ) or "(none)"
        untr = "; ".join(
            f"{g.terrain_name or g.race_terrain_id} {g.pct:g}% ({g.reason})"
            for g in rec.untrainable_terrain
        )
        line = f"{label}: emphasis={emph}"
        if untr:
            line += f"; untrainable={untr}"
        lines.append(line)
    if payload.coaching_flags:
        lines.append("")
        lines.append("Substitution coaching flags:")
        for fl in payload.coaching_flags:
            scope_bits = [b for b in (fl.discipline_id, fl.race_terrain_id) if b]
            scope = f" ({' / '.join(scope_bits)})" if scope_bits else ""
            lines.append(f"- {fl.flag_type}{scope}: {fl.message}")
    lines.append("")
    lines.append(
        "Cite crafts + terrain in `coaching_intent` / `session_notes` using "
        "natural language — never the internal `discipline_id` / `TRN-xxx` "
        "strings."
    )
    lines.append("")
    return lines


def _format_daily_windows_schedule(layer1_payload: dict[str, Any]) -> list[str]:
    """Render the `=== Schedule ===` section: per-day availability windows +
    the derived long-session day. Shared by per_phase + plan_refresh T2/T3.

    `layer1_payload` is `Layer1Payload.model_dump()`; `daily_availability_windows`
    is a list of dicts (day_of_week / enabled / window_start / window_duration /
    second_window_* / doubles_feasible). FormRefresh Slice C (2026-05-25) retired
    the standalone long-session picker: the weekly long session IS the longest
    enabled primary window and rest days ARE the disabled days — derived here by
    the consumer, not denormalized (Layer1_Spec §5.4). Ties among equal-duration
    enabled windows resolve to the earliest listed day.
    """
    lines: list[str] = ["=== Schedule ==="]
    avail = layer1_payload.get("available_days_per_week")
    if avail is not None:
        lines.append(f"Available days per week (Layer 1 §K): {avail}")

    windows = layer1_payload.get("daily_availability_windows") or []
    if not windows:
        lines.append("(No per-day availability windows on file.)")
        lines.append("")
        return lines

    longest_idx: int | None = None
    longest_dur = 0
    for i, w in enumerate(windows):
        if not w.get("enabled"):
            continue
        dur = w.get("window_duration") or 0
        if dur > longest_dur:
            longest_dur = dur
            longest_idx = i

    for i, w in enumerate(windows):
        dow = w.get("day_of_week", "?")
        if not w.get("enabled"):
            lines.append(f"- {dow}: rest (unavailable)")
            continue
        seg = f"- {dow}: available, {w.get('window_duration')} min"
        sec = w.get("second_window_duration")
        if sec:
            seg += f" (+ {sec} min second window)"
        if i == longest_idx:
            seg += "  ← longest enabled window"
        lines.append(seg)

    doubles = windows[0].get("doubles_feasible")
    if doubles:
        lines.append(f"Doubles feasible: {doubles}")

    if longest_idx is not None:
        long_dow = windows[longest_idx].get("day_of_week", "?")
        lines.append(
            f"Long-session day = {long_dow} ({longest_dur} min, the longest enabled "
            "window). Anchor the primary discipline's weekly `long_slow_distance` "
            "cornerstone here; secondary-discipline LSDs fit their own longest "
            "available day."
        )
    else:
        lines.append(
            "No enabled windows — the whole period is rest; prescribe no sessions."
        )
    lines.append(
        "Disabled days are rest days. Do not exceed any day's window minutes "
        "(validator: `daily_window_fit`)."
    )
    lines.append("")
    return lines


def render_user_prompt(
    *,
    phase_spec: PhaseSpec,
    phase_structure: PhaseStructure,
    phase_index_in_plan: int,
    is_first_phase_in_plan: bool,
    layer1_payload: dict[str, Any],
    layer2a_payload: Layer2APayload | None,
    layer2b_payload: Layer2BPayload | None,
    layer2c_payloads: dict[str, Layer2CPayload],
    layer2d_payload: Layer2DPayload | None,
    layer2e_payload: Layer2EPayload | None,
    layer3a_payload: Layer3APayload,
    layer3b_payload: Layer3BPayload,
    race_event_payload: RaceEventPayload | None,
    prior_block_sessions: list[PlanSession],
    retries_used: int,
    rule_failures: list[RuleFailure],
    seam_issues: list[str],
    seam_direction: Literal["re_prompt_prior", "re_prompt_next"] | None,
    training_substitution_payload: TrainingSubstitutionPayload | None = None,
    week_range: tuple[int, int] | None = None,
) -> str:
    """Render the §6 user prompt for one synthesis unit. Inline Python
    rendering replaces Mustache; the structure matches `Layer4_PerPhase_v2.md`
    §6.

    `week_range` (D-77) scopes the unit to an inclusive `week_in_phase` range
    when set — the prompt then asks the model to fill only those weeks. When
    None the unit is the whole phase (legacy / seam-driven re-synthesis path).

    `prior_block_sessions` is the accepted output of the immediately-preceding
    synthesis unit (the prior week-block in block mode, same phase or the prior
    phase's last block at a phase boundary; the whole prior phase in whole-phase
    mode). Empty for the very first unit of the plan (or synthetic-prior when
    `start_phase != 'Base'` and no real prior exists)."""
    parts: list[str] = []
    mode = layer3b_payload.periodization_shape.mode
    start_phase = layer3b_payload.periodization_shape.start_phase
    block_mode = week_range is not None
    is_first_block_of_phase = (week_range is None) or (week_range[0] == 1)
    is_first_unit_of_plan = is_first_phase_in_plan and is_first_block_of_phase

    # === Phase + plan context ===
    parts.append("=== Phase + plan context ===")
    parts.append(
        f"Phase: {phase_spec.phase_name} ({phase_spec.weeks} weeks, "
        f"{phase_spec.start_date.isoformat()} through "
        f"{phase_spec.end_date.isoformat()})"
    )
    if block_mode:
        ws, we = week_range  # type: ignore[misc]
        block_start, block_end = _block_date_window(phase_spec, week_range)  # type: ignore[arg-type]
        wk_label = f"week {ws}" if ws == we else f"weeks {ws}–{we}"
        parts.append(
            f"THIS CALL synthesizes ONLY {wk_label} of {phase_spec.weeks} in "
            f"this phase ({block_start.isoformat()} through "
            f"{block_end.isoformat()}, inclusive). Do NOT emit sessions for any "
            "other week — later weeks are generated in their own calls and "
            "stitched at the seams."
        )
    parts.append(
        f"Phase index in plan: {phase_index_in_plan} of "
        f"{len(phase_structure.phases)}"
    )
    parts.append(f"Is first phase in this plan: {is_first_phase_in_plan}")
    parts.append(
        f"Periodization mode: {mode} (athlete start_phase = {start_phase})"
    )
    parts.append(f"Plan total weeks: {phase_structure.total_weeks}")
    parts.append(
        f"Deload cadence anchor: "
        f"{_DELOAD_CADENCE.get(mode, 'judgment')}"  # type: ignore[arg-type]
        f" (mode={mode})"
    )
    parts.append("")
    parts.append("Phase volume bands per discipline (per 2A `phase_load_bands`):")
    parts.extend(_format_phase_load_bands(layer2a_payload, phase_spec.phase_name))
    parts.append("")
    parts.append(
        "Intended intensity distribution (Z1-Z2 / Z3 / Z4-Z5) — within ±10pp tolerance:"
    )
    iid = phase_spec.intended_intensity_distribution
    parts.append(
        f"- Z1-Z2: {iid.get('Z1-Z2', 0.0) * 100:.0f}% | "
        f"Z3: {iid.get('Z3', 0.0) * 100:.0f}% | "
        f"Z4-Z5: {iid.get('Z4-Z5', 0.0) * 100:.0f}%"
    )
    parts.append("")

    # === Prior continuity ===
    if not block_mode:
        parts.append("=== Prior-phase continuity ===")
        if is_first_phase_in_plan and start_phase == "Base":
            parts.append("(First phase of plan; no prior context.)")
        elif is_first_phase_in_plan and start_phase != "Base":
            parts.append(
                f"(Athlete starts at {start_phase}; no real prior sessions. "
                "Assume the immediately-prior skipped phase landed at its 2A "
                "exit state. Do NOT flag missing earlier-phase preparation.)"
            )
        elif phase_index_in_plan > 0 and prior_block_sessions:
            prior = phase_structure.phases[phase_index_in_plan - 1]
            parts.append(
                f"Prior phase: {prior.phase_name} ({prior.weeks} wks, "
                f"{prior.start_date.isoformat()} → {prior.end_date.isoformat()})"
            )
            parts.append("")
            parts.append("Prior phase weekly rollup:")
            parts.extend(_format_weekly_rollup_for_prior_phase(prior_block_sessions))
            parts.append("")
            parts.append("Prior phase last week (verbatim — the seam-in):")
            parts.extend(_format_prior_phase_last_week(prior_block_sessions))
        else:
            parts.append("(No prior-phase sessions supplied.)")
    else:
        # D-77 block mode: continuity threads the immediately-preceding week.
        parts.append("=== Prior-week continuity ===")
        if is_first_unit_of_plan and start_phase == "Base":
            parts.append("(First week of plan; no prior context.)")
        elif is_first_unit_of_plan and start_phase != "Base":
            parts.append(
                f"(Athlete starts at {start_phase}; no real prior sessions. "
                "Assume the immediately-prior skipped phase landed at its 2A "
                "exit state. Do NOT flag missing earlier-phase preparation.)"
            )
        elif prior_block_sessions:
            if is_first_block_of_phase:
                parts.append(
                    "This is the FIRST week of a NEW phase — a DELIBERATE phase "
                    "transition. Expect a planned step in emphasis/volume vs. the "
                    "prior phase's close, NOT a smooth ramp. Continue from where "
                    "the prior phase ended (below)."
                )
            else:
                parts.append(
                    f"Preceding week(s) of this same {phase_spec.phase_name} phase "
                    "below. Progress GENTLY and continuously from here — no abrupt "
                    "week-over-week jump; honor any planned recovery/down week in "
                    "the phase's intended progression."
                )
            parts.append("")
            parts.append("Preceding week rollup:")
            parts.extend(_format_weekly_rollup_for_prior_phase(prior_block_sessions))
            parts.append("")
            parts.append("Preceding week (verbatim — the seam-in):")
            parts.extend(_format_prior_phase_last_week(prior_block_sessions))
        else:
            parts.append("(No preceding-week sessions supplied.)")
    parts.append("")

    # === Athlete context (Layer 1 + 3A) ===
    parts.append("=== Athlete context ===")
    parts.append(
        f"Experience level: {layer1_payload.get('experience_level', 'unknown')}"
    )
    voice = layer1_payload.get("coaching_voice_preferences")
    if voice:
        parts.append(f"Voice notes: {voice}")
    parts.append("")
    parts.append("Active injuries (hard constraints; never overridable):")
    parts.extend(_format_active_injuries(layer2d_payload))
    parts.append("")
    cs = layer3a_payload.current_state
    parts.append(
        f"Aerobic state: {cs.aerobic_capacity.level} ({cs.aerobic_capacity.confidence})"
    )
    parts.append(
        f"Strength state: {cs.strength.level} ({cs.strength.confidence})"
    )
    if cs.weak_links:
        parts.append(f"Weak links (target via `weak_link_targeted` flag): {cs.weak_links}")
    rt = layer3a_payload.recent_trajectory
    parts.append(f"Short-term trajectory: {rt.short_term.direction}")
    parts.append(f"Medium-term trajectory: {rt.medium_term.direction}")
    parts.append(
        f"Data density: {layer3a_payload.data_density.recent_workouts_count} "
        f"recent workouts, "
        f"{layer3a_payload.data_density.integration_data_days} days of "
        f"integration data"
    )
    parts.append("")

    # === Race + locale + equipment ===
    parts.append("=== Race + locale + equipment ===")
    if layer2a_payload:
        included_disciplines = [
            d for d in layer2a_payload.disciplines if d.inclusion == "included"
        ]
        parts.append(
            f"Disciplines: {[d.discipline_id for d in included_disciplines]}"
        )
        parts.append("Discipline load weights:")
        for d in included_disciplines:
            parts.append(
                f"- {d.discipline_id}: {d.load_weight.value:.2f}"
            )
    if race_event_payload is not None:
        race_format_label = race_event_payload.race_format
        parts.append(f"Race format: {race_format_label}")
        anchor = _TAPER_ANCHOR_BY_FORMAT.get(race_format_label, "(no anchor)")
        parts.append(f"Taper-length anchor (for this race format): {anchor}")
        parts.extend(_format_route_locales(race_event_payload))
    else:
        parts.append("Race format: open_ended (no event_date)")
        parts.append("Do NOT emit `race_pace_specific` (open-ended mode).")
    parts.append("")

    if layer2c_payloads:
        parts.append("Locales + equipment views:")
        for locale_id, l2c in layer2c_payloads.items():
            parts.append(
                f"- {locale_id}: effective_pool size={len(l2c.effective_pool)}; "
                f"discipline_coverage={[d.discipline_id for d in l2c.discipline_coverage]}"
            )
    parts.append("")

    # === Best-fit training substitution ===
    if training_substitution_payload is not None:
        parts.extend(_format_training_substitution_per_phase(training_substitution_payload))

    # === Schedule ===
    parts.extend(_format_daily_windows_schedule(layer1_payload))

    # === Retry context ===
    if retries_used > 0 and rule_failures:
        parts.append(
            f"=== Retry context — validator failure (pass {retries_used} of cap=2) ==="
        )
        parts.append(
            "Prior pass failed deterministic validator with these rule failures. "
            "Repair while preserving as much of the phase shape as possible."
        )
        for rf in rule_failures:
            parts.append(
                f"- [{rf.severity}] `{rf.rule_name}` on session(s) "
                f"{rf.affected_session_ids}: {rf.detail}"
            )
        parts.append("")

    # === Seam-driven retry context ===
    if seam_issues:
        parts.append(
            "=== Seam-driven re-prompt — propose-patch authority (per §6.2) ==="
        )
        dir_str = seam_direction or "(unspecified)"
        parts.append(
            f"Seam reviewer flagged this phase's boundary ({dir_str}) and "
            "supplied constraint statements. Honor each as a hard constraint."
        )
        for issue in seam_issues:
            parts.append(f"- {issue}")
        parts.append("")

    # === Output instruction ===
    parts.append("=== Output ===")
    if block_mode:
        out_start, out_end = _block_date_window(phase_spec, week_range)  # type: ignore[arg-type]
    else:
        out_start, out_end = phase_spec.start_date, phase_spec.end_date
    parts.append(
        f"Emit one tool call to `record_phase_sessions` with your list of "
        f"PlanSession records covering {out_start.isoformat()} "
        f"through {out_end.isoformat()} (inclusive) plus a "
        "phase_synthesis_notes rationale (≤600 chars) and optional "
        "opportunities (up to 3 entries)."
    )

    return "\n".join(parts)


# ─── Anthropic SDK adapter ───────────────────────────────────────────────────


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
"""Adapter signature: `(system_prompt, user_prompt, tool_schema, model,
temperature, max_tokens, extended_thinking_budget) -> _SynthesizerOutput`.
Default implementation calls Anthropic SDK; tests pass a stub."""


def _default_llm_caller(
    system_prompt: str,
    user_prompt: str,
    tool_schema: dict[str, Any],
    model: str,
    temperature: float,
    max_tokens: int,
    extended_thinking_budget: int,
) -> _SynthesizerOutput:
    """Production caller — delegates to the shared thinking-aware invocation
    (`llm_invocation.invoke_tool_call`), which holds the one correct
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


# ─── Tool output → PlanSession (with phase_metadata filled) ──────────────────


def _parse_date(s: str) -> _date_type:
    return datetime.fromisoformat(s).date() if "T" in s else _date_type.fromisoformat(s)


def _clamp_sessions_over_emit(
    raw_sessions: list[Any],
    phase_name: str,
    max_sessions: int = _MAX_SESSIONS_PER_PHASE,
) -> list[Any]:
    """Trim an over-emitted `sessions` array to `max_sessions` (default
    `_MAX_SESSIONS_PER_PHASE`; the per-block ceiling in D-77 block mode).

    The tool-schema `maxItems` is only an Anthropic API hint, so the model can
    over-run it; this is the driver-side backstop (the Layer 4 twin of the
    Layer 3A/3B bounded-collection clamps). Passes through unchanged at or under
    the ceiling; logs when it fires."""
    if len(raw_sessions) > max_sessions:
        print(
            f"synthesize_phase: {phase_name} clamping sessions "
            f"from {len(raw_sessions)} to {max_sessions}"
        )
        return raw_sessions[:max_sessions]
    return raw_sessions


def _block_date_window(
    phase_spec: PhaseSpec, week_range: tuple[int, int]
) -> tuple[_date_type, _date_type]:
    """Map an inclusive `week_in_phase` range (1-indexed) to its date window.

    Week 1 = the first 7 days of the phase. The window end is clamped to the
    phase's `end_date` so a final short block (phase weeks not a multiple of
    `_BLOCK_WEEKS`) doesn't run past the phase."""
    week_start, week_end = week_range
    block_start = phase_spec.start_date + timedelta(days=(week_start - 1) * 7)
    block_end = phase_spec.start_date + timedelta(days=week_end * 7 - 1)
    if block_end > phase_spec.end_date:
        block_end = phase_spec.end_date
    return block_start, block_end


def _filter_raw_sessions_to_window(
    raw_sessions: list[Any],
    window_start: _date_type,
    window_end: _date_type,
    phase_name: str,
) -> list[Any]:
    """Drop raw session dicts whose date falls outside the block's window
    (D-77 §4.2). A deterministic block-boundary enforcement: the prompt asks
    the model to fill only this block's weeks, but `tool_choice: auto` can let
    it spill into adjacent weeks — trimming here keeps each cached block
    disjoint so concatenation across blocks never double-counts a date. Rows
    with an unparseable/absent date are kept (the PlanSession parse step below
    surfaces them as a schema_violation rather than silently dropping)."""
    kept: list[Any] = []
    dropped = 0
    for s in raw_sessions:
        raw_date = s.get("date") if isinstance(s, dict) else None
        if raw_date is None:
            kept.append(s)
            continue
        try:
            d = _parse_date(raw_date)
        except (ValueError, TypeError):
            kept.append(s)
            continue
        if window_start <= d <= window_end:
            kept.append(s)
        else:
            dropped += 1
    if dropped:
        print(
            f"synthesize_phase: {phase_name} dropped {dropped} session(s) "
            f"outside block window [{window_start}, {window_end}]"
        )
    return kept


def _build_session_phase_metadata(
    phase_spec: PhaseSpec, session_date: _date_type
) -> SessionPhaseMetadata:
    """Orchestrator fills `phase_metadata` from the `PhaseSpec` per §7.5.

    `week_in_phase` is 1-indexed (week 1 = first 7 days of the phase).
    Sessions falling outside `[phase_start, phase_end]` get week_in_phase
    clamped to 1 / total_weeks_in_phase — the validator's
    `phase_date_out_of_range_*` rule will catch out-of-window dates as
    blockers; this defensive clamp ensures pydantic construction doesn't
    trip on negative/oversize week values."""
    days_in = (session_date - phase_spec.start_date).days
    week = max(1, min(phase_spec.weeks, days_in // 7 + 1))
    return SessionPhaseMetadata(
        phase_name=phase_spec.phase_name,
        week_in_phase=week,
        total_weeks_in_phase=phase_spec.weeks,
        intended_volume_band=phase_spec.intended_volume_band,
        intended_intensity_distribution=phase_spec.intended_intensity_distribution,
    )


def _build_plan_session(
    session_data: dict[str, Any],
    *,
    session_id: str,
    plan_version_id: int,
    phase_spec: PhaseSpec,
) -> PlanSession:
    """Wrap a session dict from the synthesizer tool output into a PlanSession.
    Pattern A output requires `phase_metadata` non-None (per §7.12); fills
    from `phase_spec`."""
    raw_blocks = session_data.get("cardio_blocks")
    blocks: list[CardioBlock] | None = None
    if raw_blocks:
        blocks = [CardioBlock(**b) for b in raw_blocks]

    raw_exercises = session_data.get("strength_exercises")
    exercises: list[StrengthExercise] | None = None
    if raw_exercises:
        exercises = [StrengthExercise(**e) for e in raw_exercises]

    session_date = _parse_date(session_data["date"])

    return PlanSession(
        session_id=session_id,
        plan_version_id=plan_version_id,
        date=session_date,
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
        rest_reason=session_data.get("rest_reason"),
        phase_metadata=_build_session_phase_metadata(phase_spec, session_date),
        session_notes=session_data["session_notes"],
        coaching_intent=session_data["coaching_intent"],
        coaching_flags=list(session_data.get("coaching_flags", [])),
        is_ad_hoc=False,
        ad_hoc_request_payload=None,
    )


# ─── Per-phase synthesis result + driver ─────────────────────────────────────


@dataclass
class PhaseSynthesisResult:
    """Output of `synthesize_phase()` — one phase's accepted (or best-effort)
    sessions + the metadata the orchestrator accumulates into the
    Layer4Payload."""

    phase_name: str
    sessions: list[PlanSession]
    phase_synthesis_notes: str
    opportunities: list[str]
    validator_results: list[ValidatorResult]
    cap_hit: bool
    retries_used: int
    input_tokens: int
    output_tokens: int
    latency_ms: int
    llm_call_count: int


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
    phase_structure: PhaseStructure,
    mode: Literal["plan_create", "plan_refresh"],
) -> Layer4Payload:
    """Build a Layer4Payload for validator-input purposes with a placeholder
    accepted ValidatorResult. The real validator pass runs against this
    payload. Pattern A payloads require `phase_structure` non-None +
    `seam_reviews` non-None (empty list passes); each session
    `phase_metadata` non-None (already filled by `_build_plan_session`)."""
    return Layer4Payload(
        user_id=user_id,
        mode=mode,
        plan_version_id=plan_version_id,
        scope_start_date=scope_start,
        scope_end_date=scope_end,
        model_synthesizer=model,
        model_seam_reviewer=None,
        temperature=temperature,
        pattern="A",
        latency_ms_total=0,
        input_tokens_total=0,
        output_tokens_total=0,
        llm_call_count=0,
        etl_version_set=etl_version_set,
        sessions=sessions,
        phase_structure=phase_structure,
        seam_reviews=[],
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


def synthesize_phase(
    *,
    user_id: int,
    phase_spec: PhaseSpec,
    phase_structure: PhaseStructure,
    phase_index_in_plan: int,
    layer1_payload: dict[str, Any],
    layer2a_payload: Layer2APayload | None,
    layer2b_payload: Layer2BPayload | None,
    layer2c_payloads: dict[str, Layer2CPayload],
    layer2d_payload: Layer2DPayload | None,
    layer2e_payload: Layer2EPayload | None,
    layer3a_payload: Layer3APayload,
    layer3b_payload: Layer3BPayload,
    race_event_payload: RaceEventPayload | None,
    prior_block_sessions: list[PlanSession],
    plan_version_id: int,
    etl_version_set: dict[str, str],
    mode: Literal["plan_create", "plan_refresh"],
    model: str = "claude-sonnet-4-6",
    temperature: float = 0.2,
    max_tokens: int = DEFAULT_MAX_TOKENS,
    extended_thinking_budget: int = DEFAULT_EXTENDED_THINKING_BUDGET,
    capped_retries: int = 2,
    seam_issues: list[str] | None = None,
    seam_direction: Literal["re_prompt_prior", "re_prompt_next"] | None = None,
    retries_already_used: int = 0,
    llm_caller: LLMCaller | None = None,
    session_id_prefix: str | None = None,
    # Training-substitution resolver payload rendered into the per-phase
    # prompt via `_format_training_substitution_per_phase`. Default None
    # preserves legacy call sites that don't surface the cone.
    training_substitution_payload: TrainingSubstitutionPayload | None = None,
    # D-77: when set, scope this call to an inclusive `week_in_phase` range
    # (the per-week synthesis unit). None = whole phase (seam re-synth path).
    week_range: tuple[int, int] | None = None,
) -> PhaseSynthesisResult:
    """Synthesize one synthesis unit's PlanSession list per `Layer4_Spec.md`
    §5.2 step 3. The unit is one week-block (D-77 `week_range`) or, when
    `week_range` is None, a whole phase (the seam-driven re-synthesis path).

    Algorithm:
    1. Render `Layer4_PerPhase_v2.md` §6 user prompt against the full upstream
       payload set + the phase's intended state + prior phase context.
    2. Invoke synthesizer LLM via `record_phase_sessions` tool.
    3. Parse tool output into typed PlanSession rows with `phase_metadata`
       filled from `phase_spec`.
    4. Run §5.4 deterministic validator scoped to this phase.
    5. On validator failure: capped retry with `RuleFailure` context merged
       into the next pass's user prompt. Counter shared across validator-
       driven AND seam-driven retries (per §5.5 + §6.2).
    6. On cap-hit with unresolved blockers: best-effort acceptance per §5.5.

    `seam_issues` + `seam_direction` populate the seam-driven retry context
    when this is a seam-reviewer-triggered re-synthesis. `retries_already_used`
    propagates the per-phase counter across the seam-driven trigger boundary
    (the caller in `plan_create.py` tracks the running count per phase).

    `session_id_prefix` enables deterministic session_id generation across
    retries (so the validator can reliably identify "the same session"
    across passes). Defaults to a fresh 8-char hex prefix.
    """
    if session_id_prefix is None:
        session_id_prefix = uuid.uuid4().hex[:8]

    caller: LLMCaller = llm_caller or _default_llm_caller

    # D-77: scope the unit to a week-block when `week_range` is set, else the
    # whole phase. The per-unit session ceiling scales from the per-week cap, and
    # the block's output budget (`effective_max_tokens`) scales with it. NOTE:
    # under extended thinking the request ceiling is `max_tokens +
    # extended_thinking_budget`; the thinking attempt that exhausts the budget on
    # reasoning and emits an empty tool call is caught in `invoke_tool_call` (the
    # forced-tool retry fires with thinking off → all of `max_tokens` is output
    # room). The forced retry then needs `max_tokens` itself to be large enough
    # for a dense week's `sessions` — the original per-phase 4000 was not, which
    # truncated the retry mid-output → `schema_violation` — so block mode sizes
    # the budget to its session ceiling below.
    if week_range is not None:
        ws, we = week_range
        block_weeks = max(1, we - ws + 1)
        max_sessions_this_unit = min(
            _MAX_SESSIONS_PER_WEEK * block_weeks, _MAX_SESSIONS_PER_PHASE
        )
        unit_scope_start, unit_scope_end = _block_date_window(phase_spec, week_range)
        unit_tag = f"{phase_spec.phase_name}:w{ws}" + (f"-{we}" if we != ws else "")
        # D-77 §6 follow-on: size the block output budget to its session ceiling.
        # The per-phase default `max_tokens` (4000) predates the dense session
        # schema, so a full high-frequency week serialized well past it: the
        # forced-tool retry (thinking off → `max_tokens` IS the entire output
        # budget) truncated mid-`sessions` → empty/partial tool args →
        # `schema_violation`. That is the bounded terminal failure the post-fix
        # re-run surfaced in place of the prior 504-loop (the per-block budget
        # guard + empty-tool escalation stopped the loop but left the unit too
        # small). Raise it to fit a worst-case dense block; never below the
        # caller's value. Higher `max_tokens` is only a ceiling — billed/latency
        # cost tracks tokens actually emitted, and the per-block budget guard
        # still bounds total synthesis time.
        effective_max_tokens = max(
            max_tokens,
            max_sessions_this_unit * _BLOCK_OUTPUT_TOKENS_PER_SESSION
            + _BLOCK_OUTPUT_TOKENS_OVERHEAD,
        )
    else:
        max_sessions_this_unit = _MAX_SESSIONS_PER_PHASE
        unit_scope_start, unit_scope_end = phase_spec.start_date, phase_spec.end_date
        unit_tag = f"{phase_spec.phase_name}:full-phase"
        # Whole-phase mode (seam-driven re-synth) keeps the caller's budget — a
        # 56-session single call is the unit D-77 decomposition replaced; the
        # week-seam stitcher (Slice 3), not a token bump, is its scaling path.
        effective_max_tokens = max_tokens
    tool_schema = build_record_phase_sessions_tool(max_sessions_this_unit)

    rule_failures: list[RuleFailure] = []
    validator_results: list[ValidatorResult] = []

    total_input_tokens = 0
    total_output_tokens = 0
    total_latency_ms = 0
    llm_call_count = 0
    cap_hit = False
    final_retries_used = retries_already_used

    latest_sessions: list[PlanSession] | None = None
    latest_notes: str = ""
    latest_opportunities: list[str] = []
    latest_validator: ValidatorResult | None = None

    # The retry loop runs from `retries_already_used` to `capped_retries`
    # inclusive. When seam-driven, retries_already_used > 0 and we may have
    # fewer attempts remaining; when validator-driven from a fresh phase,
    # retries_already_used == 0.
    remaining_budget = capped_retries - retries_already_used
    if remaining_budget < 0:
        # Per §6.2: if cap is exhausted, accept current (no further synthesis).
        # Shouldn't be invoked in this state but defensive.
        return PhaseSynthesisResult(
            phase_name=phase_spec.phase_name,
            sessions=[],
            phase_synthesis_notes="(cap exhausted; no synthesis attempted)",
            opportunities=[],
            validator_results=[],
            cap_hit=True,
            retries_used=retries_already_used,
            input_tokens=0,
            output_tokens=0,
            latency_ms=0,
            llm_call_count=0,
        )

    for pass_offset in range(remaining_budget + 1):
        current_pass = retries_already_used + pass_offset
        # D-77 §6 per-block budget guard: don't START another extended-thinking
        # attempt once the block has spent its LLM-time budget — the block must
        # RETURN within the 300s function cap so it caches (or fails terminally
        # fast) rather than 504-looping forever. The first attempt always runs;
        # later retries are gated on accumulated latency.
        if pass_offset > 0 and total_latency_ms >= _PER_BLOCK_BUDGET_MS:
            if latest_sessions is not None:
                # Accept the best parseable attempt so far as best-effort
                # (§5.5 cap-hit) so the block caches and the plan makes
                # monotonic progress instead of re-synthesizing it next pass.
                print(
                    f"synthesize_phase: {unit_tag} per-block budget spent "
                    f"({total_latency_ms}ms over {llm_call_count} call(s)) — "
                    f"accepting best-effort attempt (cap_hit)"
                )
                cap_hit = True
                break
            # No parseable attempt within budget — the block can't be salvaged;
            # fail terminally fast (the row flips to a coded failure) instead of
            # starting another attempt that would 504.
            print(
                f"synthesize_phase: {unit_tag} per-block budget spent "
                f"({total_latency_ms}ms over {llm_call_count} call(s)) with no "
                f"parseable attempt — terminal"
            )
            raise Layer4OutputError(
                "synthesis_budget_exhausted",
                detail=(
                    f"{unit_tag}: no parseable attempt within "
                    f"{_PER_BLOCK_BUDGET_MS}ms ({llm_call_count} call(s))"
                ),
            )
        user_prompt = render_user_prompt(
            phase_spec=phase_spec,
            phase_structure=phase_structure,
            phase_index_in_plan=phase_index_in_plan,
            is_first_phase_in_plan=(phase_index_in_plan == 0),
            layer1_payload=layer1_payload,
            layer2a_payload=layer2a_payload,
            layer2b_payload=layer2b_payload,
            layer2c_payloads=layer2c_payloads,
            layer2d_payload=layer2d_payload,
            layer2e_payload=layer2e_payload,
            layer3a_payload=layer3a_payload,
            layer3b_payload=layer3b_payload,
            race_event_payload=race_event_payload,
            prior_block_sessions=prior_block_sessions,
            retries_used=current_pass,
            rule_failures=rule_failures,
            seam_issues=seam_issues or [],
            seam_direction=seam_direction,
            training_substitution_payload=training_substitution_payload,
            week_range=week_range,
        )

        llm_out = caller(
            SYSTEM_PROMPT,
            user_prompt,
            tool_schema,
            model,
            temperature,
            effective_max_tokens,
            extended_thinking_budget,
        )
        llm_call_count += 1
        total_input_tokens += llm_out.input_tokens
        total_output_tokens += llm_out.output_tokens
        total_latency_ms += llm_out.latency_ms

        # D-77 §6 diagnostics — per-attempt LLM latency so a 504-looping block
        # reveals whether a SINGLE call is near the 300s function cap or whether
        # the capped-retry stack (multiple extended-thinking calls in one
        # non-resumable function invocation) is what blows the budget. Diagnostic
        # only; trim once the per-block cost driver is identified.
        print(
            f"synthesize_phase: {unit_tag} attempt {current_pass + 1}/"
            f"{capped_retries + 1} llm call {llm_out.latency_ms}ms "
            f"(in={llm_out.input_tokens} out={llm_out.output_tokens} "
            f"max_tokens={effective_max_tokens})"
        )

        raw_sessions = llm_out.tool_args.get("sessions")
        notes_str = llm_out.tool_args.get("phase_synthesis_notes", "")
        opportunities = llm_out.tool_args.get("opportunities") or []

        if not isinstance(raw_sessions, list):
            # The synthesizer returned a tool_use block whose args carried no
            # 'sessions' array — observed in production under extended-thinking
            # `tool_choice: auto`, where the model can emit a thin/partial tool
            # call. Treat it like the parse-failure path below: retry within the
            # cap with the miss fed back into the next prompt, raising terminal
            # only after the cap is exhausted — rather than hard-failing the
            # whole plan on the first miss while retries were still available.
            # Log the keys the model DID emit so a recurrence is diagnosable
            # from the runtime log (is the dict empty, partial, or wrong-keyed?).
            present_keys = sorted(llm_out.tool_args.keys())
            print(
                f"synthesize_phase: {unit_tag} attempt {current_pass + 1} "
                f"returned no 'sessions' array (tool_args keys={present_keys})"
            )
            if current_pass >= capped_retries:
                raise Layer4OutputError(
                    "schema_violation",
                    detail=(
                        "tool args missing 'sessions' array after "
                        f"{current_pass + 1} attempt(s) (keys={present_keys})"
                    ),
                )
            rule_failures = [
                RuleFailure(
                    rule_name="schema_violation",
                    phase_name=phase_spec.phase_name,
                    severity="blocker",
                    detail="tool output omitted the required 'sessions' array",
                    affected_session_ids=[],
                )
            ]
            final_retries_used = current_pass + 1
            continue

        # D-77: in block mode, drop any session the model placed outside the
        # block's week window FIRST so each cached block stays disjoint
        # (concatenation across blocks never double-counts a date). The window
        # filter is the block boundary; the ceiling clamp below caps what
        # remains in-window.
        if week_range is not None:
            raw_sessions = _filter_raw_sessions_to_window(
                raw_sessions, unit_scope_start, unit_scope_end, phase_spec.phase_name
            )

        # Pre-validation clamp on the bounded `sessions` collection: the tool
        # schema's `maxItems` is only an Anthropic API hint, so the model can
        # over-emit past it. Trim to the declared ceiling before parsing — the
        # same over-emit-vs-cap guard applied to Layer 3A/3B bounded fields.
        raw_sessions = _clamp_sessions_over_emit(
            raw_sessions, phase_spec.phase_name, max_sessions_this_unit
        )

        try:
            sessions = [
                _build_plan_session(
                    s,
                    session_id=f"S-{session_id_prefix}-{phase_spec.phase_name[:3].lower()}-{i:03d}",
                    plan_version_id=plan_version_id,
                    phase_spec=phase_spec,
                )
                for i, s in enumerate(raw_sessions)
            ]
        except (ValidationError, KeyError, ValueError, TypeError) as e:
            print(
                f"synthesize_phase: {unit_tag} attempt {current_pass + 1} "
                f"sessions did not parse ({type(e).__name__}): {str(e)[:240]}"
            )
            if current_pass >= capped_retries:
                raise Layer4OutputError(
                    "schema_violation",
                    detail=f"tool output did not parse as PlanSession list: {e}",
                )
            rule_failures = [
                RuleFailure(
                    rule_name="schema_violation",
                    phase_name=phase_spec.phase_name,
                    severity="blocker",
                    detail=str(e)[:240],
                    affected_session_ids=[],
                )
            ]
            final_retries_used = current_pass + 1
            continue

        latest_sessions = sessions
        latest_notes = notes_str
        latest_opportunities = [str(o) for o in opportunities][:3]

        if not sessions:
            empty_result = ValidatorResult(
                pass_index=current_pass,
                accepted=True,
                rule_failures=[],
                retried_phase_names=[],
            )
            validator_results.append(empty_result)
            latest_validator = empty_result
            final_retries_used = current_pass
            break

        payload_attempt = _build_payload_for_validation(
            user_id=user_id,
            sessions=sessions,
            plan_version_id=plan_version_id,
            scope_start=unit_scope_start,
            scope_end=unit_scope_end,
            model=model,
            temperature=temperature,
            etl_version_set=etl_version_set,
            phase_structure=phase_structure,
            mode=mode,
        )
        ctx = ValidatorContext(
            layer2a_payload=layer2a_payload,
            layer2b_payload=layer2b_payload,
            layer2c_payloads=dict(layer2c_payloads),
            layer2d_payload=layer2d_payload,
            layer2e_payload=layer2e_payload,
            layer3a_payload=layer3a_payload,
            layer3b_payload=layer3b_payload,
            race_event=race_event_payload,
        )
        validator_result = validate_layer4_payload(
            payload_attempt, ctx, pass_index=current_pass
        )
        validator_results.append(validator_result)
        latest_validator = validator_result
        final_retries_used = current_pass

        if validator_result.accepted:
            break

        rule_failures = list(validator_result.rule_failures)
        # D-77 §6 diagnostics — the per-block validator rejection was previously
        # silent, so a block that 504-loops by exhausting its retry stack gave no
        # signal as to WHY each attempt was rejected (a fixable rule bug vs. a
        # genuinely-unsatisfiable plan). Log the failing rule_name(severity) set.
        _failed = "; ".join(
            f"{f.rule_name}({f.severity})" for f in validator_result.rule_failures
        )[:240]
        print(
            f"synthesize_phase: {unit_tag} attempt {current_pass + 1} validator "
            f"rejected ({len(validator_result.rule_failures)} failure(s)): {_failed}"
        )
        if current_pass >= capped_retries:
            cap_hit = True
            final_retries_used = current_pass
            break
        # else: continue loop for next retry; counter increments via current_pass.

    if latest_sessions is None:
        # Defensive — at minimum one pass must have completed (the loop runs
        # at least once when remaining_budget >= 0).
        raise Layer4OutputError(
            "schema_violation",
            detail="no synthesizer pass produced parseable sessions",
        )
    assert latest_validator is not None

    # D-77 §6 diagnostics — per-block synthesis summary: call count + total
    # latency expose how close a block runs to the 300s function cap, and
    # cap_hit/retries_used show whether it converged or was best-effort accepted.
    # (Fires only when the block RETURNS — a block 504-killed mid-loop is traced
    # via the per-attempt lines above instead.) Diagnostic only; trim later.
    print(
        f"synthesize_phase: {unit_tag} done — {llm_call_count} llm call(s), "
        f"{total_latency_ms}ms total, accepted={latest_validator.accepted}, "
        f"cap_hit={cap_hit}, retries_used={final_retries_used}, "
        f"sessions={len(latest_sessions)}"
    )

    return PhaseSynthesisResult(
        phase_name=phase_spec.phase_name,
        sessions=latest_sessions,
        phase_synthesis_notes=latest_notes,
        opportunities=latest_opportunities,
        validator_results=validator_results,
        cap_hit=cap_hit,
        retries_used=final_retries_used,
        input_tokens=total_input_tokens,
        output_tokens=total_output_tokens,
        latency_ms=total_latency_ms,
        llm_call_count=llm_call_count,
    )


def build_synthesis_metadata_from_result(
    result: PhaseSynthesisResult,
    *,
    model: str,
    temperature: float,
) -> SynthesisMetadata:
    """Convert a `PhaseSynthesisResult` into the `SynthesisMetadata` row the
    orchestrator overwrites into `PhaseSpec.synthesis_metadata` once the
    phase synthesis call completes (§7.6)."""
    return SynthesisMetadata(
        model=model,
        temperature=temperature,
        input_tokens=result.input_tokens,
        output_tokens=result.output_tokens,
        latency_ms=result.latency_ms,
        retries_used=result.retries_used,
        cap_hit=result.cap_hit,
    )


__all__ = [
    "DEFAULT_MAX_TOKENS",
    "DEFAULT_EXTENDED_THINKING_BUDGET",
    "SYSTEM_PROMPT",
    "LLMCaller",
    "PhaseSynthesisResult",
    "build_record_phase_sessions_tool",
    "build_synthesis_metadata_from_result",
    "render_user_prompt",
    "synthesize_phase",
]
