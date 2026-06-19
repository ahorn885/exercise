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

import os
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
from layer4 import periodization
from layer4.injury_render import format_active_injuries
from layer4.strength_guidance import STRENGTH_PROGRAMMING_GUIDANCE
from layer4.session_feasibility import (
    EventWindowSegment,
    TerrainResolution,
    feasibility_line,
    grid_annotation,
)
from layer4.session_grid import (
    _RECOVERY_SESSIONS_PER_WEEK,
    build_session_grid,
    classify_recovery_load_band,
    compute_recovery_dose,
    compute_recovery_placement,
    derive_enabled_days,
    derive_long_session_dow,
    placeable_days_in_week,
    resolve_available_days,
)
from layer4.validator import (
    ValidatorContext,
    daily_windows_from_layer1,
    phase_volume_bands_hours,
    skill_gated_disciplines,
    validate_layer4_payload,
    weekly_capacity_hours,
)


# ─── Constants per Layer4_PerPhase_v2.md §7 + §3.4 ───────────────────────────


DEFAULT_MAX_TOKENS = 4000
"""Per `Layer4_Spec.md` §3.1 default `max_tokens_per_phase`."""

DEFAULT_EXTENDED_THINKING_BUDGET = 0
"""0 = go straight to the forced-tool call (one ~110s invocation), skipping the
extended-thinking attempt. The thinking-first attempt (the former max-defensive
5000 per `Layer4_PerPhase_v1.md` D2) repeatedly burned the full
`max_tokens + budget` ceiling on reasoning and returned NO tool block
(`stop_reason=max_tokens`, ~430s of dead time) on dense Build/Peak weeks, then
the forced retry did the real work in ~110s anyway — so the thinking attempt was
pure overhead that consumed the per-block budget and starved the validator
correction loop (pv=58 Build:w2, pv=59 Build:w1). With 0 the forced tool gets
all of `max_tokens` as output budget. The seam reviewer keeps its own
`seam_thinking_budget` (independent constant), so this change is scoped to
block/phase synthesis."""

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
non-resumable function invocation; if the stack exceeds the function cap
(`PLAN_GEN_FUNCTION_CAP_S` — 300s default, raised to 800s on Pro) it 504-kills
mid-loop, caches nothing, and the next pass restarts it from attempt 1 — an
infinite loop the wall-clock backstop only converts into a loud failure after
~900s. This bound stops the loop from STARTING another attempt once the block
has spent its LLM-time budget, so a block always RETURNS within the function
cap: it caches the best parseable attempt as best-effort (§5.5 cap-hit) or fails
terminally fast. NOTE the gate is on retries ONLY — the first attempt is never
gated and is itself uninterruptible, so a single long attempt (e.g. an
extended-thinking call that exhausts `max_tokens` before emitting the tool) can
alone approach the cap; 120s only bounds how much ADDITIONAL retry latency the
loop will start, not the worst-case first attempt."""

_BLOCK_OUTPUT_TOKENS_PER_SESSION = 1400
"""D-77 §6 follow-on (raised 600→900 after pv=38, then 900→1400 after pv=40).
A dense PlanSession (cardio_blocks with per-block intensity targets +
strength_exercises arrays + 240-char notes/instructions) serializes to ~400-600
output tokens when written compactly — but the rendered output runs much larger,
and prod telemetry (pv=39) measured blocks emitting 10-16k output tokens. The
sizing must clear the worst case at the FORCED-TOOL RETRY, whose ceiling is
`effective_max_tokens` ALONE (thinking off → no +thinking_budget headroom; see
`llm_invocation.py`). The prior 900×14+1200=13800 floor sat *below* the observed
16k: pv=40's first block's stochastic thinking attempt (temp=1.0) emitted no
usable tool call, fell through to the forced retry, and the retry truncated
mid-`sessions` against 13800 (`stop_reason=max_tokens`, no usable tool_use
block) → `schema_violation` every pass → #324/#325 retried it into the ~900s
stall backstop (0 blocks cached, generic "stalled" failure). 1400×14+2000=21600
clears the 16k worst case with ~35% headroom so the forced retry is a RELIABLE
floor, not a coin-flip. `max_tokens` is only a ceiling — billed/latency cost
tracks tokens actually emitted, and the per-block budget guard still bounds
total synthesis time — so the headroom is effectively free."""

_BLOCK_OUTPUT_TOKENS_OVERHEAD = 2000
"""Fixed block output budget on top of the per-session estimate: covers
`phase_synthesis_notes` (≤600 chars), `opportunities` (3×≤240 chars), and the
JSON envelope/scaffolding. Raised 800→1200→2000 alongside the per-session bumps
for the same anti-truncation headroom (pv=40 forced-retry truncation; see
`_BLOCK_OUTPUT_TOKENS_PER_SESSION`)."""

_MODEL_MAX_OUTPUT_TOKENS = 64000
"""Per-request output-token ceiling of the synthesizer model
(`claude-sonnet-4-6` = 64K). `block_output_budget` clamps to this: a `max_tokens`
above the model's limit is a 400. The create path's per-week blocks (≤14 sessions
→ ≤21,600) never reach it, so the clamp is a no-op there; it binds only for a
single-call refresh sized to its full session ceiling (T3 = 56 → 80,400 raw).
Under extended thinking the request ceiling is `max_tokens + thinking_budget`, so
a caller sizing to this ceiling must run thinking off (the refresh T3 path does)."""


def block_output_budget(max_sessions: int, floor: int = 0) -> int:
    """Output-token budget for one synthesis block (D-77 §6): size to the unit's
    session ceiling at `_BLOCK_OUTPUT_TOKENS_PER_SESSION` + fixed overhead, never
    below `floor` (the caller's own value), clamped to the model's max output
    ceiling. Shared by the create per-phase synthesizer and the refresh driver so
    both scale output room with the sessions they ask the model to emit — a flat
    per-call constant truncates a dense block (`schema_violation` at
    `stop_reason=max_tokens`)."""
    return min(
        _MODEL_MAX_OUTPUT_TOKENS,
        max(
            floor,
            max_sessions * _BLOCK_OUTPUT_TOKENS_PER_SESSION
            + _BLOCK_OUTPUT_TOKENS_OVERHEAD,
        ),
    )


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


SYSTEM_PROMPT = (
    """You are AIDSTATION's Layer 4 per-phase synthesizer.

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
- Never surface internal identifiers in athlete-facing text — no discipline ids (e.g. "D-012") and no skill/toggle slugs (e.g. "climbing_roped"). Use the plain discipline name ("rock climbing", "roped climbing").

# Phase intent — the spine of your output

Each phase has a per-discipline weekly hour band (from 2A `phase_load_bands`) that the deterministic session grid converts into per-week session counts (see `=== Session grid ===` block in the user prompt). The orchestrator stamps `recovery_week` spec-auto on deload weeks; you do not need to identify them.

# Session grid — deterministic counts + intensity mix

The user prompt's `=== Session grid ===` block is computed deterministically from the athlete's capacity + the phase's intended load + (when applicable) the race format's race-sim anchor. It is **authoritative** for:

- Per-discipline session counts each week (including maintenance-cadence rotations for small-share disciplines — a discipline at e.g. 3% of phase_load gets ~1 session every 3–4 weeks rather than once weekly).
- The cardio polarized intensity mix (easy vs hard session count at the week level — no Z3/moderate; polarized training avoids it).
- The per-discipline session typing — each cardio discipline's count is typed into `long` / `easy` / `quality` slots (these sum to the week-level mix). Honor each discipline's typed counts.
- Race-sim long day slot (present only when the race format is `continuous_multi_day`; multi-discipline, weekend-anchored).

Your job: PLACE these sessions across the week — pick the day, the time-of-day, the exercise/discipline content within the constraints, and the coaching intent. Do NOT deviate from the counts, the intensity mix, the per-discipline typing, or the maintenance cadence. If a discipline shows 0 sessions for this week (maintenance-week skip), honor that. If the grid is genuinely wrong (e.g. an excluded discipline shows allocation), call it out in `phase_synthesis_notes` and produce the best plan you can within the grid.

Session typing is prescribed **per discipline** (long / easy / quality), not just the week-level mix. The `long` session is the LSD aerobic cornerstone and `easy` sessions are aerobic — place BOTH on the discipline's **aerobic** surface from the feasibility surface routing. The `quality` sessions are the hard sessions — place them on the discipline's **vert or technical** surface, matching each quality session's intent to the surface its purpose calls for (hill/vert work on the elevation surface; skill/technical work on the technical surface). Do not collapse every session onto one surface. The race-sim long day (when present) counts as one quality session. When a discipline has no surface routing (single-surface, or all surfaces at one locale), the typing still governs the effort distribution.

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

# Strength programming

"""
    + STRENGTH_PROGRAMMING_GUIDANCE
    + """

Pick exercises from the rendered `=== Strength exercise pool ===` for the session's locale (never invent `exercise_id`s). Keep a stable core of 2–3 compound lifts across the phase for progression; rotate accessory exercises week-to-week. If the athlete has no logged history for an exercise, prescribe the reps and tell them to use a load they can complete for that many reps with ~2 reps in reserve, and log it — they set their own baseline; do not withhold an exercise for lack of history.

Attribute each strength session's `discipline_id` to the discipline it most supports. Place strength as the second session on an easy/moderate cardio day, not on the same day as a key intensity/long session. Do not prescribe a time of day; if strength shares a day with a hard session, add a `session_notes` cue to separate them by a few hours and avoid heavy legs right before the quality session. Honor 2D injury exclusions/accommodations.

# Recovery programming

`kind='recovery'` is a small mobility / soft-tissue / breathwork session — sub-threshold, low-cost, distinct from a training session. The `=== Recovery programming ===` block in the user prompt is **authoritative** for how many recovery sessions to place each week and their duration (deterministic, off the training cap); honor the per-week count.

Recovery sessions are ADDITIVE and do **not** count toward the ≤2/day training cap: a day may carry ≤2 training (cardio/strength) PLUS ≤1 recovery, and the recovery session takes the last `session_index_in_day` slot of its day. Place them on or after hard days, or on lighter / rest-adjacent days; never stack two recovery sessions on one day. Keep `intensity_summary` at `easy` or `rest`. A `recovery` session sets `discipline_id` and `locale_id` to null — it is not a discipline and is not locale-routed; the framing goes in `coaching_intent` / `session_notes`.

Prescribe the movements as a `recovery_exercises[]` block (the structural analog of `strength_exercises`): pick `exercise_id`s from the rendered `=== Recovery exercise pool ===` only (never invent them), and give each a free-text `prescription` (e.g. "2×30s/side", "5 min @ ~6 breaths/min") plus brief `instructions`. Leave `cardio_blocks` / `strength_exercises` / `rest_reason` null.

Load-adaptive rest: full rest is the protective floor and recovery sessions are the active-recovery mechanism — the two are adaptation-neutral, so under high load (Peak phase or a deload week) prefer genuine full rest over active recovery and keep any recovery minimal and short.

# Cardio drills

A cardio session may optionally carry **one** drill from the `=== Cardio drill pool (consider these) ===` menu — a discrete, catalog-defined skill, transition, or interval drill that sharpens a discipline (a brick run, a single-leg cycling drill, a swim CSS set). Drills are optional and additive to the session's free-composed `cardio_blocks`: they refine *how* a session trains a discipline; they do not add sessions or volume. Most cardio sessions carry none.

- **At most one drill per session.** A session targets one technical focus, not a drill circuit. Never emit more than one `cardio_drills` entry.
- **Pick only from the rendered pool, by id.** Choose `exercise_id`s from the menu only — never invent one, and never name a drill or drill-type that isn't in the menu. If no menu is rendered, prescribe no drills.
- **Attach a drill only to a session of its own discipline.** The menu is grouped under each discipline header; a drill belongs on a session training that discipline (a bike over-under on a bike session, a swim set on a swim session), never on an unrelated one.
- **Emphasis follows the drill's character, noted inline per row.** Skill/transition/form drills are a Base-phase tool — build technique early and let them fade toward the race. Interval and endurance drills follow the session's normal phase intent (threshold/VO2 work belongs in Build/Peak).
- **Two cautions:** (a) a form/cadence drill does **not** move steady road economy — for a pure road run or ride, prioritize volume and strength, and reach for a cadence/single-leg cue only for a specific biomechanics or injury reason, not as default seasoning; (b) a brick or transition drill belongs **only** on a day that actually pairs the two sports — a brick run goes on a day with a bike session immediately before it, not on a standalone run.
- Give each drill a free-text `prescription` (e.g. "4×50m, focus on catch", "15 min off the bike at goal pace") and brief `instructions`. `cardio_drills` rides `kind='cardio'` sessions only; leave it null on strength / recovery / rest.

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
)


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


_FEASIBLE_POOL_ENUM_WARN_THRESHOLD = 200

# #698 Finding 2 — the strength pool (both the SDK enum bounding
# `strength_exercises[*].exercise_id` and the rendered pool the synthesizer
# reads) must only contain strength-session `exercise_type`s. Without this,
# every `sport_exercise_map`-mapped 0B row leaked in regardless of type, so a
# cardio/skill drill (e.g. EX073 "Threshold Intervals (Bike)", a Interval/Tempo
# row) was a structurally-valid strength-exercise pick the model could
# mis-prescribe as a lift. The allowlist is the resistance + athletic-development
# modalities (Andy-ratified 2026-06-17: resistance set + agility/activation/
# balance count as strength-session work). Excluded: cardio (Interval/Tempo,
# Aerobic/Endurance), pure skill (Technical/Skill), and recovery/mobility
# (Mobility, Flexibility/Stretching, Recovery/Soft Tissue, Breathwork) — the
# recovery/mobility types are destined for their own session kind (see #698).
# Stored lowercased + matched case-insensitively (mirrors _strength_pattern_match
# against the 0B vocab): prod values are title-case ("Strength"), but the compare
# tolerates casing/whitespace drift.
_STRENGTH_POOL_EXERCISE_TYPES = frozenset(
    {
        "strength", "power", "loaded carry", "plyometric", "isometric",
        "agility", "activation / primer", "balance / proprioception",
    }
)


def _is_strength_pool_type(exercise_type: str) -> bool:
    return (exercise_type or "").strip().lower() in _STRENGTH_POOL_EXERCISE_TYPES


def compute_feasible_pool_ids(
    layer2c_payloads: dict[str, Layer2CPayload],
    layer2d_payload: Layer2DPayload | None,
) -> list[str]:
    """Track 2 D1: cluster-union of resolved strength `exercise_id`s across
    every locale in `layer2c_payloads`, minus 2D-excluded ids. Sorted+deduped
    for deterministic enum ordering across calls (cache-key stability + diff
    legibility). Empty result means no resolvable strength surface (caller
    typically reverts to free-string schema rather than passing an empty enum)."""
    if not layer2c_payloads:
        return []
    excluded: set[str] = (
        {er.exercise_id for er in layer2d_payload.excluded_exercises}
        if layer2d_payload is not None
        else set()
    )
    pool: set[str] = set()
    dropped_by_type: dict[str, int] = {}
    for l2c in layer2c_payloads.values():
        for rx in l2c.exercises_resolved:
            if rx.exercise_id in excluded:
                continue
            # #698 Finding 2 — keep only resistance-training types in the
            # strength enum so cardio/skill rows can't be picked as lifts.
            if not _is_strength_pool_type(rx.exercise_type):
                dropped_by_type[rx.exercise_type] = (
                    dropped_by_type.get(rx.exercise_type, 0) + 1
                )
                continue
            pool.add(rx.exercise_id)
    # Rule #15 — log the non-strength rows the type filter excluded (by type),
    # so a "missing exercise" in a strength session is attributable in prod.
    if dropped_by_type:
        _dbg = ", ".join(f"{t}={n}" for t, n in sorted(dropped_by_type.items()))
        print(f"compute_feasible_pool_ids: non-strength-type dropped [{_dbg}]")
    return sorted(pool)


# #698 Track 1 (Slice 2) — the recovery/mobility analog of
# `_STRENGTH_POOL_EXERCISE_TYPES`. The recovery session pool (the enum bounding
# `recovery_exercises[*].exercise_id` + the rendered pool) must only contain the
# soft-tissue / mobility / breathwork `exercise_type`s — the orphaned 0B catalog
# this session kind gives a home (#698). Lowercased + matched case-insensitively
# (prod values are title-case, e.g. "Mobility"), mirroring `_is_strength_pool_type`.
# These types are exactly the complement excluded from the strength allowlist.
_RECOVERY_POOL_EXERCISE_TYPES = frozenset(
    {
        "mobility", "flexibility / stretching", "recovery / soft tissue",
        "breathwork",
    }
)


def _is_recovery_pool_type(exercise_type: str) -> bool:
    return (exercise_type or "").strip().lower() in _RECOVERY_POOL_EXERCISE_TYPES


def compute_recovery_pool_ids(
    layer2c_payloads: dict[str, Layer2CPayload],
    layer2d_payload: Layer2DPayload | None,
) -> list[str]:
    """#698 Track 1 (Slice 2, D1) — cluster-union of resolved recovery/mobility
    `exercise_id`s across every locale, minus 2D-excluded ids (wrist/injury
    contraindications honored). Mirrors `compute_feasible_pool_ids` but with the
    recovery type allowlist; filters the SAME `l2c.exercises_resolved` surface.
    Sorted+deduped for deterministic enum ordering (cache-key stability). Empty
    result → caller passes no enum (the schema falls back to a free string)."""
    if not layer2c_payloads:
        return []
    excluded: set[str] = (
        {er.exercise_id for er in layer2d_payload.excluded_exercises}
        if layer2d_payload is not None
        else set()
    )
    pool: set[str] = set()
    dropped_by_type: dict[str, int] = {}
    for l2c in layer2c_payloads.values():
        for rx in l2c.exercises_resolved:
            if rx.exercise_id in excluded:
                continue
            if not _is_recovery_pool_type(rx.exercise_type):
                dropped_by_type[rx.exercise_type] = (
                    dropped_by_type.get(rx.exercise_type, 0) + 1
                )
                continue
            pool.add(rx.exercise_id)
    # Rule #15 — log the non-recovery rows the type filter excluded (by type),
    # so a "missing exercise" in a recovery session is attributable in prod.
    if dropped_by_type:
        _dbg = ", ".join(f"{t}={n}" for t, n in sorted(dropped_by_type.items()))
        print(f"compute_recovery_pool_ids: non-recovery-type dropped [{_dbg}]")
    return sorted(pool)


# #698 Track 2 (A2) — the cardio drill pool exercise types: Part B's 24-row
# surviving 0B catalog (Technical/Skill transition+form drills, Interval/Tempo
# structured intervals, Aerobic/Endurance). The `_RECOVERY_POOL_EXERCISE_TYPES`
# analog. Lowercased + matched case-insensitively (prod values are title-case,
# e.g. "Interval / Tempo"), mirroring `_is_recovery_pool_type`.
_CARDIO_DRILL_POOL_EXERCISE_TYPES = frozenset(
    {"technical / skill", "interval / tempo", "aerobic / endurance"}
)
# Character periodization (design §5): skill/transition/form drills (Technical/
# Skill) are a Base-phase tool — kept in Base/Build, dropped in Peak/Taper.
# Interval/endurance (Interval/Tempo + Aerobic/Endurance) follow normal phase
# emphasis → never phase-suppressed (gating VO2/threshold out of Build/Peak would
# hide the pool's most useful rows).
_CARDIO_DRILL_SKILL_TYPE = "technical / skill"
_CARDIO_DRILL_SKILL_DROP_PHASES = frozenset({"Peak", "Taper"})
# The constituent-sport gate (design §5/§3a): EX175 Brick Run + EX176 Tri
# Transition SEM-match the composite "Multi-Sport Race"/Triathlon/Duathlon
# sports — broad enough to match a paddle/climb-only AR athlete with no bike/run
# leg. Include them ONLY when the athlete trains BOTH a cycling AND a running
# discipline. The cycling/running discipline-id sets are the live
# `layer0.disciplines` rows whose `primary_movement` is 'cycling'/'running'
# (read-only neon-query run 27828748291, 2026-06-19); hardcoded by stable D-id
# (canon is locked Layer 0 — re-derive from that query if a discipline is added).
# The other 3 transition keeps (EX144/EX163/EX170) are intra-discipline → the
# plain discipline-match gates them, no extra check.
_CYCLING_DISCIPLINE_IDS = frozenset({"D-006", "D-007", "D-008", "D-030", "D-031"})
_RUNNING_DISCIPLINE_IDS = frozenset({"D-001", "D-002", "D-024", "D-027"})
_CONSTITUENT_SPORT_GATED_DRILLS = frozenset({"EX175", "EX176"})


def _is_cardio_drill_pool_type(exercise_type: str) -> bool:
    return (
        (exercise_type or "").strip().lower() in _CARDIO_DRILL_POOL_EXERCISE_TYPES
    )


def _cardio_drill_phase_allows(exercise_type: str, phase: str) -> bool:
    """Skill/transition drills drop in Peak/Taper; interval/endurance always keep."""
    if (exercise_type or "").strip().lower() == _CARDIO_DRILL_SKILL_TYPE:
        return phase not in _CARDIO_DRILL_SKILL_DROP_PHASES
    return True


def _constituent_sport_gate_ok(exercise_id: str, disciplines: set[str]) -> bool:
    """EX175/EX176 require the athlete to hold both a cycling AND a running
    discipline; every other drill passes (its plain SEM-match already gates it)."""
    if exercise_id not in _CONSTITUENT_SPORT_GATED_DRILLS:
        return True
    return bool(disciplines & _CYCLING_DISCIPLINE_IDS) and bool(
        disciplines & _RUNNING_DISCIPLINE_IDS
    )


def compute_cardio_drill_pool_ids(
    layer2c_payloads: dict[str, Layer2CPayload],
    layer2d_payload: Layer2DPayload | None,
    *,
    disciplines: set[str],
    phase: str,
) -> list[str]:
    """#698 Track 2 (A2) — the cardio drill pool: the union of resolved drill-type
    `exercise_id`s across every locale whose `discipline_ids` intersect the
    athlete's included disciplines, minus 2D-excluded ids, minus the
    constituent-sport-gated transition drills (EX175/EX176) when the athlete lacks
    both a cycling and a running discipline, minus skill/transition drills in
    Peak/Taper. Mirrors `compute_recovery_pool_ids` (reads the SAME
    `exercises_resolved` surface). Sorted+deduped for deterministic enum ordering
    (cache-key stability). Empty → caller passes no enum (the schema falls back to
    a free string) and the prompt block is suppressed."""
    if not layer2c_payloads:
        return []
    excluded: set[str] = (
        {er.exercise_id for er in layer2d_payload.excluded_exercises}
        if layer2d_payload is not None
        else set()
    )
    pool: set[str] = set()
    dropped = {"excluded": 0, "discipline": 0, "gate": 0, "phase": 0}
    for l2c in layer2c_payloads.values():
        for rx in l2c.exercises_resolved:
            if not _is_cardio_drill_pool_type(rx.exercise_type):
                continue  # non-drill types are the silent majority
            if rx.exercise_id in excluded:
                dropped["excluded"] += 1
                continue
            if not (set(rx.discipline_ids) & disciplines):
                dropped["discipline"] += 1
                continue
            if not _constituent_sport_gate_ok(rx.exercise_id, disciplines):
                dropped["gate"] += 1
                continue
            if not _cardio_drill_phase_allows(rx.exercise_type, phase):
                dropped["phase"] += 1
                continue
            pool.add(rx.exercise_id)
    # Rule #15 — log the inputs + the chosen pool + why drill-type rows dropped,
    # so a missing/surprising cardio drill is a one-read /admin/logs diagnosis.
    print(
        f"compute_cardio_drill_pool_ids: phase={phase} "
        f"athlete_disciplines={sorted(disciplines)} pool={sorted(pool)} "
        f"dropped(excluded={dropped['excluded']},discipline={dropped['discipline']},"
        f"gate={dropped['gate']},phase={dropped['phase']})"
    )
    return sorted(pool)


def _session_schema(
    feasible_pool_ids: list[str] | None = None,
    recovery_pool_ids: list[str] | None = None,
    cardio_drill_pool_ids: list[str] | None = None,
) -> dict[str, Any]:
    """One element of `sessions[]`. Full PlanSession contract mirror per the
    Step 4a Option 2 precedent. Includes `rest` kind (Pattern A produces full
    schedules including rest days; differs from refresh/single_session which
    only emit working sessions).

    Track 2 D1: when `feasible_pool_ids` is non-empty, the
    `strength_exercises.exercise_id` property is bounded by enum, making
    out-of-pool picks structurally impossible at the SDK boundary. #698 Track 1
    (Slice 2): `recovery_pool_ids` does the same for `recovery_exercises`."""
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
            # #698 Track 1 — max→2 so a recovery session can take the 3rd daily
            # slot (≤2 training + ≤1 recovery; mirrors PlanSession.session_index_in_day).
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
            # #698 Track 1 (Slice 2, D1) — structured recovery/mobility block,
            # the analog of strength_exercises. exercise_id is enum-bound to the
            # recovery pool when resolvable, so out-of-pool picks are structurally
            # impossible at the SDK boundary (mirrors strength_exercises).
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
            # #698 Track 2 (A2) — structured cardio drill block, the analog of
            # recovery_exercises. HARD CAP maxItems:1 (a session targets one
            # technical/interval focus, not a drill circuit; mirrors the
            # PlanSession pydantic invariant). exercise_id is enum-bound to the
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
        },
    }


def build_record_phase_sessions_tool(
    max_sessions: int = 56,
    feasible_pool_ids: list[str] | None = None,
    recovery_pool_ids: list[str] | None = None,
    cardio_drill_pool_ids: list[str] | None = None,
) -> dict[str, Any]:
    """Anthropic tool definition for `record_phase_sessions`. Sessions array
    `maxItems` accommodates up to 4 weeks × 7 days × 2/day = 56 for the
    longest typical phase (Base in standard mode 12 wks would split across
    multiple synthesizer calls in v2 if budget pressure surfaces; v1 single
    call per phase). Caller can override `max_sessions` for tighter caps.

    Track 2 D1: `feasible_pool_ids` (when non-empty) bounds
    `strength_exercises.exercise_id` via JSON-schema enum. Production callers
    pass `compute_feasible_pool_ids(layer2c_payloads, layer2d_payload)`. #698
    Track 1: `recovery_pool_ids` bounds `recovery_exercises.exercise_id` the
    same way (`compute_recovery_pool_ids(...)`)."""
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
                    "items": _session_schema(
                        feasible_pool_ids, recovery_pool_ids, cardio_drill_pool_ids
                    ),
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
    in 3A's typed contract — canonical injury source is 2D).

    Delegates to the shared `layer4.injury_render` renderer so the create +
    refresh prompts can't drift; that renderer also carries each modality's
    params + rationale (#555), not just the type name.
    """
    return format_active_injuries(
        layer2d,
        none_payload_line=(
            "- (Layer 2D payload not supplied; no injury exclusions in scope.)"
        ),
        none_on_file_line="- None on file.",
    )


# #335 Phase 2 §8 — strength exercise-surface rendering. The per-discipline cap
# (N≈8–12 in the design) balances grounding the synthesizer in real resolved
# exercise_ids against input-token cost (#316).
_STRENGTH_POOL_CAP_PER_DISCIPLINE = 10
_STRENGTH_PRIORITY_RANK = {"Critical": 0, "High": 1, "Medium": 2, "Low": 3}
# §8 ranking bias + §5 integrated-stability bias (movement_patterns, lowercased
# for case-insensitive match against the 0B vocab e.g. "Single-Leg"/"Hinge").
_STRENGTH_PREFERRED_PATTERNS = {
    "single-leg", "hinge", "squat", "lunge", "carry", "anti-rotation",
}
# Core-eligible = big compound multi-joint lifts (the §5 "2–3 progressed
# compound lifts" stable core); the rest are rotating accessory.
_STRENGTH_COMPOUND_PATTERNS = {"hinge", "squat", "lunge", "single-leg"}
_STRENGTH_CORE_CAP = 3


def _strength_pattern_match(rx, vocab: set[str]) -> bool:
    return any(
        (p or "").strip().lower() in vocab for p in (rx.movement_patterns or [])
    )


def _format_strength_exercise_pool(
    layer2c_payloads: dict[str, Layer2CPayload],
    layer2a_payload: Layer2APayload | None,
    layer2d_payload: Layer2DPayload | None,
) -> list[str]:
    """#335 Phase 2 §8 — render the resolved strength-exercise surface so the
    synthesizer prescribes real, locale-available `exercise_id`s instead of
    inventing them. Without this the prompt rendered only `effective_pool
    size=N` (a count), so the model guessed ids and Rule 6a rejected every guess
    as `equipment_unavailable` — even when the athlete owns the gear; the id
    simply was never in the resolved set.

    Per locale, per included discipline (2A load-weight order), the resolved
    exercises ranked Critical→High→Medium then Tier-1-first, 2D-excluded
    dropped, deduped across disciplines (listed under the first/highest-weight
    discipline that surfaces them), capped per discipline. A discipline with no
    resolved exercises (e.g. zero-0B disciplines like MTB/Climbing) renders
    nothing — no blocker; sport sessions cover those (Phase 1).

    Two §8 deviations, both compensated by the §9 prompt text: movement-pattern
    ranking (Single-Leg/Hinge/…) is omitted because `ResolvedExercise` carries
    no `movement_patterns`, so the unilateral/offset bias rides on the prompt;
    core-vs-accessory marking is likewise left to the prompt (no data signal)."""
    if not layer2c_payloads:
        return []
    excluded_ids = (
        {er.exercise_id for er in layer2d_payload.excluded_exercises}
        if layer2d_payload is not None
        else set()
    )
    weight_order: list[str] = []
    if layer2a_payload is not None:
        included = [
            d for d in layer2a_payload.disciplines if d.inclusion == "included"
        ]
        included.sort(key=lambda d: d.load_weight.value, reverse=True)
        weight_order = [d.discipline_id for d in included]

    out: list[str] = []
    for locale_id, l2c in layer2c_payloads.items():
        present = {d for rx in l2c.exercises_resolved for d in rx.discipline_ids}
        ordered = [d for d in weight_order if d in present] + sorted(
            present - set(weight_order)
        )
        seen: set[str] = set()
        locale_lines: list[str] = []
        for d_id in ordered:
            cands = [
                rx
                for rx in l2c.exercises_resolved
                if d_id in rx.discipline_ids
                and rx.exercise_id not in excluded_ids
                and rx.exercise_id not in seen
                # #698 Finding 2 — render only resistance-training types; this
                # mirrors the compute_feasible_pool_ids enum so the rendered
                # pool and the structural enum stay in lockstep.
                and _is_strength_pool_type(rx.exercise_type)
            ]
            cands.sort(
                key=lambda rx: (
                    _STRENGTH_PRIORITY_RANK.get(
                        rx.priority_per_discipline.get(d_id, ""), 4
                    ),
                    0 if _strength_pattern_match(
                        rx, _STRENGTH_PREFERRED_PATTERNS
                    ) else 1,
                    rx.tier,
                )
            )
            cands = cands[:_STRENGTH_POOL_CAP_PER_DISCIPLINE]
            if not cands:
                continue
            locale_lines.append(f"  {d_id}:")
            core_count = 0
            for rx in cands:
                seen.add(rx.exercise_id)
                # Core = a high-relevance compound lift to progress consistently
                # (priority Critical/High AND a compound pattern), capped; the
                # rest rotate as accessory (§5 hybrid core+accessory).
                is_core = (
                    core_count < _STRENGTH_CORE_CAP
                    and _STRENGTH_PRIORITY_RANK.get(
                        rx.priority_per_discipline.get(d_id, ""), 4
                    ) <= 1
                    and _strength_pattern_match(rx, _STRENGTH_COMPOUND_PATTERNS)
                )
                if is_core:
                    core_count += 1
                attrs = ["core" if is_core else "accessory", f"Tier {rx.tier}"]
                prio = rx.priority_per_discipline.get(d_id, "")
                if prio:
                    attrs.append(prio)
                if rx.movement_patterns:
                    attrs.append(",".join(rx.movement_patterns))
                if rx.tier != 1 and rx.resolution_detail is not None:
                    if rx.resolution_detail.substitute_text:
                        attrs.append(
                            f"substitute: {rx.resolution_detail.substitute_text}"
                        )
                    elif rx.resolution_detail.proxy_exercise_id:
                        attrs.append(
                            f"proxy: {rx.resolution_detail.proxy_exercise_id}"
                        )
                locale_lines.append(
                    f"  - {rx.exercise_id} ({rx.exercise_name}) [{'; '.join(attrs)}]"
                )
        if locale_lines:
            out.append(f"- Locale {locale_id}:")
            out.extend(locale_lines)
    return out


# #698 Track 1 (Slice 2) — cap the rendered recovery pool. Recovery dose is
# small (the evidence: benefit plateaus at ~10 min/wk per muscle group), so a
# short menu is plenty; this also bounds input-token cost (#316).
_RECOVERY_POOL_CAP = 12


def _format_recovery_exercise_pool(
    layer2c_payloads: dict[str, Layer2CPayload],
    layer2d_payload: Layer2DPayload | None,
) -> list[str]:
    """#698 Track 1 (Slice 2, D1) — render the resolved recovery/mobility surface
    so the synthesizer prescribes real, locale-available `exercise_id`s for
    `recovery_exercises` instead of inventing them (the structural analog of
    `_format_strength_exercise_pool`, bound to the same enum via
    `compute_recovery_pool_ids`). Recovery is NOT discipline- or locale-routed
    (the kind carries `discipline_id`/`locale_id` = None), so this is a single
    flat, deduped, capped menu across all locales — no per-discipline ranking or
    core/accessory split (recovery has no progression model). 2D-excluded ids
    dropped (injury contraindications honored). Empty when nothing resolves."""
    if not layer2c_payloads:
        return []
    excluded_ids = (
        {er.exercise_id for er in layer2d_payload.excluded_exercises}
        if layer2d_payload is not None
        else set()
    )
    seen: set[str] = set()
    items: list[tuple[str, str, str]] = []  # (id, name, type) for stable sort
    for l2c in layer2c_payloads.values():
        for rx in l2c.exercises_resolved:
            if (
                rx.exercise_id in excluded_ids
                or rx.exercise_id in seen
                or not _is_recovery_pool_type(rx.exercise_type)
            ):
                continue
            seen.add(rx.exercise_id)
            items.append((rx.exercise_id, rx.exercise_name, rx.exercise_type))
    if not items:
        return []
    items.sort(key=lambda it: it[0])  # deterministic id order
    items = items[:_RECOVERY_POOL_CAP]
    out = ["- Recovery / mobility menu (pick from these ids only):"]
    for ex_id, name, ex_type in items:
        out.append(f"  - {ex_id} ({name}) [{ex_type}]")
    return out


# #698 Track 2 (A2) — cap the rendered cardio drill pool (design §6). A
# multisport athlete's union can exceed this; keep the highest-SEM-priority rows
# per discipline (the render is weight-ordered + priority-sorted, so the cap
# naturally retains them) and bound input-token cost.
_CARDIO_DRILL_POOL_CAP = 12
_CARDIO_DRILL_PRIORITY_RANK = {"Critical": 0, "High": 1, "Medium": 2}


def _cardio_drill_character_tag(exercise_type: str) -> str:
    """The inline phase-emphasis annotation, keyed on drill character (§6)."""
    t = (exercise_type or "").strip().lower()
    if t == _CARDIO_DRILL_SKILL_TYPE:
        return "transition/skill — Base tool, fades to race"
    if t == "interval / tempo":
        return "interval — follow phase intent"
    return "endurance — follow phase intent"


def _format_cardio_drill_pool(
    layer2c_payloads: dict[str, Layer2CPayload],
    layer2a_payload: Layer2APayload | None,
    layer2d_payload: Layer2DPayload | None,
    *,
    disciplines: set[str],
    phase: str,
) -> list[str]:
    """#698 Track 2 (A2) — render the cardio drill pool grouped under the
    athlete's discipline headers, each row carrying its catalog `coaching_cue`
    (the interval dose, threaded via A1.5) + a phase-emphasis-by-character tag, so
    the synthesizer matches a drill to today's discipline by reading, not guessing
    (the `_format_recovery_exercise_pool` analog, bound to the same enum via
    `compute_cardio_drill_pool_ids`). Same filters as the compute fn (type / 2D /
    discipline / constituent-sport gate / phase-by-character). Deduped across
    disciplines (under the highest-load-weight discipline that surfaces it),
    highest-SEM-priority first, capped at `_CARDIO_DRILL_POOL_CAP` rows total.
    Empty when nothing resolves → the caller suppresses the block."""
    if not layer2c_payloads:
        return []
    excluded_ids = (
        {er.exercise_id for er in layer2d_payload.excluded_exercises}
        if layer2d_payload is not None
        else set()
    )
    names: dict[str, str] = {}
    weight_order: list[str] = []
    if layer2a_payload is not None:
        included = [
            d for d in layer2a_payload.disciplines if d.inclusion == "included"
        ]
        included.sort(key=lambda d: d.load_weight.value, reverse=True)
        weight_order = [d.discipline_id for d in included]
        names = {
            d.discipline_id: d.discipline_name for d in layer2a_payload.disciplines
        }
    # Collect drill-type rows passing the compute filters, deduped by id.
    by_id: dict[str, ResolvedExercise] = {}
    for l2c in layer2c_payloads.values():
        for rx in l2c.exercises_resolved:
            if (
                _is_cardio_drill_pool_type(rx.exercise_type)
                and rx.exercise_id not in excluded_ids
                and (set(rx.discipline_ids) & disciplines)
                and _constituent_sport_gate_ok(rx.exercise_id, disciplines)
                and _cardio_drill_phase_allows(rx.exercise_type, phase)
            ):
                by_id.setdefault(rx.exercise_id, rx)
    if not by_id:
        return []
    present = {
        d for rx in by_id.values() for d in rx.discipline_ids if d in disciplines
    }
    ordered = [d for d in weight_order if d in present] + sorted(
        present - set(weight_order)
    )
    seen: set[str] = set()
    rendered = 0
    out: list[str] = []
    for d_id in ordered:
        if rendered >= _CARDIO_DRILL_POOL_CAP:
            break
        cands = [
            rx
            for rx in by_id.values()
            if d_id in rx.discipline_ids and rx.exercise_id not in seen
        ]
        cands.sort(
            key=lambda rx: (
                _CARDIO_DRILL_PRIORITY_RANK.get(
                    rx.priority_per_discipline.get(d_id, ""), 3
                ),
                rx.exercise_id,
            )
        )
        disc_lines: list[str] = []
        for rx in cands:
            if rendered >= _CARDIO_DRILL_POOL_CAP:
                break
            seen.add(rx.exercise_id)
            rendered += 1
            cue = (rx.coaching_cue or "").strip()
            cue_seg = f" — {cue}" if cue else ""
            tag = _cardio_drill_character_tag(rx.exercise_type)
            disc_lines.append(
                f"  - {rx.exercise_id} ({rx.exercise_name}){cue_seg} [{tag}]"
            )
        if disc_lines:
            out.append(f"- {names.get(d_id, d_id)}:")
            out.extend(disc_lines)
    return out


def _format_skill_capability_gates(
    layer2c_payloads: dict[str, Layer2CPayload],
    layer2a_payload: Layer2APayload | None,
) -> list[str]:
    """#336 — render the skill-capability substitution directive.

    For each included discipline whose required skill-capability toggle is OFF
    (sourced from the Layer 2C `requires_skill_capability` flags — the signal
    that was computed-but-unconsumed, #298), instruct the synthesizer to
    substitute strength-and-conditioning work for the skill-specific session
    rather than prescribing training the athlete isn't cleared for. The
    deterministic validator (`_rule_skill_capability_gate`) blocks any
    surviving `kind == 'cardio'` session tagged to a gated discipline, so this
    guidance and the gate agree. Empty when nothing is gated."""
    gated = skill_gated_disciplines(layer2c_payloads)
    if not gated:
        return []
    names: dict[str, str] = {}
    if layer2a_payload is not None:
        names = {d.discipline_id: d.discipline_name for d in layer2a_payload.disciplines}
    out: list[str] = [
        "=== Skill-capability gates (#336 — SAFETY; deterministic) ===",
        "The athlete has NOT been cleared for the skill(s) these disciplines "
        "require. Do NOT prescribe skill-specific (kind='cardio') sessions for "
        "them — the validator will reject those. Instead substitute strength-"
        "and-conditioning work (kind='strength') that builds the underlying "
        "capacity (e.g. grip + upper-body strength in place of a climbing "
        "session), and state the substitution in coaching_intent — "
        "\"prescribing strength until you're cleared on <skill>\":",
    ]
    for d_id in sorted(gated):
        toggle = gated[d_id]
        d_name = names.get(d_id, d_id)
        out.append(
            f"  - {d_name} ({d_id}): not cleared for '{toggle}' — substitute "
            "strength-and-conditioning; no skill-specific session."
        )
    out.append("")
    return out


def _format_session_feasibility(
    terrain_feasibility: dict[str, TerrainResolution] | None,
    layer2a_payload: Layer2APayload | None,
    layer2c_payloads: dict[str, Layer2CPayload],
) -> list[str]:
    """#540 slice 2c.2 — render the deterministic per-discipline terrain-
    feasibility directive (the companion to the inline session-grid tag).

    For each discipline the cascade resolved (EXACT/PROXY/INDOOR/STRENGTH/
    REALLOCATE), state where + how its sessions are actually doable across the
    athlete's locale cluster, so the synthesizer composes a session that works
    rather than one the athlete can't physically do. Skill-gated disciplines
    are absent here by construction (handled by the #336 substitution directive
    — the orchestrator partitions the two). Empty when nothing was resolved."""
    if not terrain_feasibility:
        return []
    names: dict[str, str] = {}
    if layer2a_payload is not None:
        names = {d.discipline_id: d.discipline_name for d in layer2a_payload.disciplines}
    # Exercise id → display name for the STRENGTH tier's substitute pool, from
    # the already-threaded 2C resolved set (no extra plumbing).
    exercise_names: dict[str, str] = {}
    for l2c in layer2c_payloads.values():
        for ex in l2c.exercises_resolved:
            exercise_names.setdefault(ex.exercise_id, ex.exercise_name)
    out: list[str] = [
        "=== Session feasibility (deterministic — terrain routing, #540) ===",
        "Per discipline, where + how its sessions are actually doable across your "
        "locale cluster (home + nearby). The session grid above is authoritative "
        "for counts; this is authoritative for WHERE + as WHAT to compose each "
        "one. Honor it — do not prescribe a session the athlete can't physically "
        "do. Cite locales / surfaces in natural language; never the internal "
        "`TRN-xxx` / `discipline_id` strings:",
    ]
    for d_id in sorted(terrain_feasibility):
        out.append(
            feasibility_line(
                terrain_feasibility[d_id],
                discipline_name=names.get(d_id, d_id),
                exercise_names=exercise_names,
            )
        )
    out.append("")
    return out


def _event_window_label(segment: "EventWindowSegment") -> str:
    """Human-readable label for a date-segment's active subtractive overrides
    (Event Windows Slice 1). Joined with ' + ' when a segment carries more than
    one (overlapping windows)."""
    parts: list[str] = []
    for ov in segment.overrides:
        if ov.override_type == "indoor_only":
            parts.append("indoor-only (no outdoor terrain available)")
        elif ov.override_type == "locale_unavailable":
            parts.append(f"\"{ov.unavailable_locale}\" unavailable (closed this window)")
        elif ov.override_type == "away":
            # Trigger-#1 wording APPROVED (Andy 2026-06-14). Slice 4 dropped the
            # hard-coded "no brought craft" clause — it became false once a craft
            # can be brought (c) or kept at the destination (b); the actual craft
            # availability shows in the per-discipline resolutions this overlay
            # renders (D-009 exact when the boat travelled, etc.), so the label
            # states the environment without asserting an absent-craft claim.
            parts.append(
                f"away at \"{ov.away_locale}\" (training environment: that "
                f"location's terrain/equipment + any craft you have there)"
            )
        else:  # defensive
            parts.append(ov.override_type)
    label = " + ".join(parts)
    # Slice 3 (F8): the destination was cold, so its equipment/terrain came from
    # the category baseline — tell the athlete to log actuals on arrival so the
    # window re-plans on real gear (Trigger-#1 wording, Andy 2026-06-14).
    if segment.assumed_baseline_category:
        away_loc = next(
            (ov.away_locale for ov in segment.overrides
             if ov.override_type == "away" and ov.away_locale),
            "the destination",
        )
        label += (
            f' [Equipment/terrain at "{away_loc}" is assumed from the standard '
            f"{segment.assumed_baseline_category} baseline — log the gym's actual "
            f"equipment on arrival to refine the plan for this window.]"
        )
    return label


def _format_event_window_overlay(
    event_window_segments: list["EventWindowSegment"] | None,
    unit_start: _date_type | None,
    unit_end: _date_type | None,
    layer2a_payload: Layer2APayload | None,
    layer2c_payloads: dict[str, Layer2CPayload],
) -> list[str]:
    """Event Windows Slice 1 (#581 WS-H) — render the date-scoped overlay for any
    event-window segment overlapping THIS synthesis unit's date window.

    Each segment's environment is a subtraction of the home cluster (Slice 1:
    `indoor_only` / `locale_unavailable`); its `resolutions` already hold only
    the disciplines whose routing the window CHANGES, resolved by the existing
    cascade against the reduced environment. The displayed date range is clipped
    to the unit window so the synthesizer knows which of THIS block's dates are
    affected. Empty when no segment overlaps (the common case → no overlay).

    Wording sign-off: Andy 2026-06-14 (Trigger #1)."""
    if not event_window_segments or unit_start is None or unit_end is None:
        return []
    overlapping = [
        s for s in event_window_segments
        if s.end_date >= unit_start and s.start_date <= unit_end
    ]
    if not overlapping:
        return []
    names: dict[str, str] = {}
    if layer2a_payload is not None:
        names = {d.discipline_id: d.discipline_name for d in layer2a_payload.disciplines}
    exercise_names: dict[str, str] = {}
    for l2c in layer2c_payloads.values():
        for ex in l2c.exercises_resolved:
            exercise_names.setdefault(ex.exercise_id, ex.exercise_name)

    out: list[str] = [
        "=== Event-window overlay (deterministic — date-scoped routing) ===",
        # Trigger-#1 wording APPROVED (Andy 2026-06-14) — away-aware (Slice 2).
        "Part of this block falls inside a declared event window where the "
        "training environment differs — either reduced (home, indoor-only or a "
        "locale closed) or replaced (training away at another location). On the "
        "dates below, routing differs from the default feasibility block above. "
        "Compose any session dated within a window against THAT window's routing; "
        "sessions outside the windows use the default. A session that lands on a "
        "window day is composed at that day's environment, never dropped.",
    ]
    for seg in sorted(overlapping, key=lambda s: (s.start_date, s.end_date)):
        disp_start = max(seg.start_date, unit_start)
        disp_end = min(seg.end_date, unit_end)
        out.append(
            f"- {disp_start.isoformat()}–{disp_end.isoformat()} · "
            f"{_event_window_label(seg)}:"
        )
        for d_id in sorted(seg.resolutions):
            out.append(
                "  " + feasibility_line(
                    seg.resolutions[d_id],
                    discipline_name=names.get(d_id, d_id),
                    exercise_names=exercise_names,
                )
            )
    out.append(
        "Placement preference (soft): where a discipline's weekly count leaves a "
        "choice of days, prefer scheduling its outdoor-dependent sessions on the "
        "unconstrained days; let indoor/strength-appropriate work fall on the "
        "window days."
    )
    out.append("")
    return out


def _format_session_grid(
    layer1_payload: dict[str, Any],
    layer2a_payload: Layer2APayload | None,
    phase_structure: PhaseStructure | None,
    phase_name: str,
    race_event_payload: RaceEventPayload | None,
    *,
    week_range: tuple[int, int] | None = None,
    skill_gated: dict[str, str] | None = None,
    terrain_feasibility: dict[str, TerrainResolution] | None = None,
    event_window_segments: list["EventWindowSegment"] | None = None,
) -> list[str]:
    """Track 2 slice 2b: render the deterministic per-week session grid that
    replaces the prior `_format_phase_load_bands` block. The grid is
    authoritative for per-discipline session counts (including maintenance
    cadence for small-share disciplines), the polarized intensity mix, and the
    race-sim long-day slot for `continuous_multi_day` race formats.

    Returns an open-ended-bands fallback line when 2A or phase_structure is
    unavailable (preserves the graceful-degradation contract of the function
    this replaces)."""
    if layer2a_payload is None or phase_structure is None:
        return ["- (Layer 2A / phase_structure unavailable; using open-ended bands.)"]

    capacity = weekly_capacity_hours(layer1_payload)
    # §5.1.1 ceiling inputs — resolve available days from §K availability;
    # two_a_day_preference / peak_sessions_max are the §G availability scalars
    # (slice 2b.2b). Both default to None when the athlete hasn't set them, so
    # the grid falls back to its spec defaults (occasionally / derive-from-pref).
    available_days = resolve_available_days(layer1_payload)
    _availability = (layer1_payload or {}).get("availability") or {}
    two_a_day_preference = _availability.get("two_a_day_preference")
    peak_sessions_max = _availability.get("peak_sessions_max")

    race_format: str | None = None
    race_duration_h: float | None = None
    if race_event_payload is not None:
        race_format = race_event_payload.race_format
        if race_event_payload.estimated_duration_hr is not None:
            race_duration_h = float(race_event_payload.estimated_duration_hr)

    if week_range is not None:
        weeks: range = range(week_range[0], week_range[1] + 1)
    else:
        phase_weeks_n = next(
            (p.weeks for p in phase_structure.phases if p.phase_name == phase_name),
            0,
        )
        weeks = range(1, phase_weeks_n + 1)

    # Counts-follow-away (Event Windows Slice 2, spec §4.1): a plan week FULLY
    # inside an `away` window is counted against the destination, not home — so
    # WS-E2's per-week reallocation shifts the weekly counts toward what the
    # destination supports. A partial/mixed week keeps home counts (its away days
    # are handled by per-day composition / the overlay). Resolve the phase span
    # once for the per-week date math (week w spans start_date+(w-1)*7 .. +6d).
    _phase_spec = next(
        (p for p in phase_structure.phases if p.phase_name == phase_name), None
    )
    _away_segments = [
        s for s in (event_window_segments or []) if s.away_feasibility is not None
    ]
    # plan-72 root fix: the race truncates the final taper week, but `available_days`
    # is the athlete's nominal weekly figure — so the session ceiling (2×days) lets
    # the grid emit more sessions than there are placeable days, the synthesizer
    # can't lay them out at ≤2/day, every validation pass fails, and the block
    # stalls out its budget. Anchor a per-week placeable-day cutoff at the last
    # trainable day before the race: race day and the immediate pre-race day (rest)
    # are both excluded → cutoff = event_date − 2. Open-ended plans → no cutoff.
    _race_cutoff: _date_type | None = (
        race_event_payload.event_date - timedelta(days=2)
        if race_event_payload is not None and race_event_payload.event_date is not None
        else None
    )

    out: list[str] = []
    for w in weeks:
        week_feasibility = terrain_feasibility
        week_available_days = available_days
        if _phase_spec is not None:
            wk_start = _phase_spec.start_date + timedelta(days=(w - 1) * 7)
            wk_end = wk_start + timedelta(days=6)
            week_available_days = placeable_days_in_week(
                available_days, layer1_payload, wk_start, wk_end, _race_cutoff
            )
            if week_available_days != available_days:
                # Rule #15: the race-week truncation that shrinks the ceiling.
                print(
                    f"placeable_days: {phase_name}:w{w} "
                    f"dates={wk_start.isoformat()}..{wk_end.isoformat()} "
                    f"race_cutoff={_race_cutoff.isoformat() if _race_cutoff else None} "
                    f"available_days {available_days}→{week_available_days} "
                    f"(ceiling now ≤2×{week_available_days})"
                )
        if _phase_spec is not None and _away_segments:
            away_seg = next(
                (
                    s for s in _away_segments
                    if s.start_date <= wk_start and s.end_date >= wk_end
                ),
                None,
            )
            if away_seg is not None:
                week_feasibility = away_seg.away_feasibility
                print(
                    f"counts_follow_away: {phase_name}:w{w} "
                    f"dates={wk_start.isoformat()}..{wk_end.isoformat()} "
                    f"fully-away → grid counted against the away env "
                    f"tiers={ {d: r.tier for d, r in sorted(away_seg.away_feasibility.items())} }"
                )
        grid = build_session_grid(
            layer2a_payload,
            phase_structure,
            phase_name,
            w,
            capacity_hours=capacity,
            race_format=race_format,
            race_duration_h=race_duration_h,
            available_days=week_available_days,
            two_a_day_preference=two_a_day_preference,
            peak_sessions_max=peak_sessions_max,
            strength_feasibility_tiers=(
                {d: r.tier for d, r in week_feasibility.items()}
                if week_feasibility else None
            ),
            skill_gated_ids=frozenset(skill_gated or {}),
        )
        # Rule #15 observability: the deterministic grid decides sessions/week
        # per discipline BEFORE feasibility runs — the upstream half of a
        # strength-saturated week (too many sessions across disciplines that
        # then resolve to failover strength). Log the allocation so saturation
        # is attributable to the grid vs. the failover substitution.
        _alloc_dbg = ", ".join(
            f"{a.discipline_id}:{a.sessions_this_week}x{a.typical_session_minutes}m"
            + (
                f"(L{a.session_types.long}/E{a.session_types.easy}/Q{a.session_types.quality})"
                if a.session_types is not None
                else ""
            )
            for a in grid.discipline_allocations
        )
        print(
            f"build_session_grid: {phase_name}:w{w} "
            f"capacity={grid.weekly_capacity_hours:.1f}h allocations=[{_alloc_dbg}]"
        )
        # Rule #15 — the WS-E2 strength-saturation cap's decision (which failover
        # strength was trimmed + where its volume was reallocated), so an
        # over-constrained week's final strength count is attributable in prod.
        if grid.saturation_note:
            print(f"strength_saturation_cap: {phase_name}:w{w} {grid.saturation_note}")
        out.append(
            f"Week {w} — weekly capacity {grid.weekly_capacity_hours:.1f} hours:"
        )
        if not grid.discipline_allocations:
            out.append("  (No allocations resolved — open-ended bands.)")
            continue
        out.append(
            "  Per-discipline session counts (deterministic — do not deviate):"
        )
        for a in grid.discipline_allocations:
            cadence = f" — {a.cadence_note}" if a.cadence_note else ""
            # #336 — flag skill-gated disciplines inline in the authoritative
            # grid so the count is read as a STRENGTH substitution, not a
            # skill-specific session (the validator blocks the latter).
            gate = ""
            if skill_gated and a.discipline_id in skill_gated:
                gate = (
                    " [SKILL-GATED: athlete not cleared for this skill "
                    "— prescribe as a strength substitution, NOT a skill session]"
                )
            # #540 — inline terrain-feasibility tag for the tiers that change the
            # session KIND (strength) or drop it (reallocate). Composes with the
            # skill-gate tag (both append; the orchestrator partitions which
            # disciplines each owns, so they never describe the same one twice).
            terrain_tag = ""
            if terrain_feasibility and a.discipline_id in terrain_feasibility:
                terrain_tag = grid_annotation(terrain_feasibility[a.discipline_id])
            out.append(
                f"  - {a.discipline_name} ({a.discipline_id}): "
                f"{a.sessions_this_week} session(s) × ~{a.typical_session_minutes} min, "
                f"target {a.target_hours_this_week:.1f} hours{cadence}.{gate}{terrain_tag}"
            )
            # #624 Slice 2 — the deterministic long/easy/quality typing that binds
            # to the feasibility surface routing (long + easy → aerobic surface;
            # quality → vert/technical surface).
            st = a.session_types
            if st is not None and st.total > 0:
                parts = []
                if st.long:
                    parts.append(f"{st.long}× long (LSD, aerobic)")
                if st.easy:
                    parts.append(f"{st.easy}× easy (aerobic)")
                if st.quality:
                    parts.append(f"{st.quality}× quality (vert/technical)")
                out.append(f"    Session types (deterministic): {' + '.join(parts)}.")
        if grid.intensity_mix.total > 0:
            out.append(
                f"  Cardio intensity mix (polarized, week-level aggregate — the "
                f"per-discipline quality counts above sum to it): "
                f"{grid.intensity_mix.easy_count} easy + "
                f"{grid.intensity_mix.hard_count} hard."
            )
        if grid.race_sim_long_day is not None:
            sim = grid.race_sim_long_day
            out.append(
                f"  Race-sim long day ({sim.phase_position}): "
                f"1 × {sim.duration_min} min, multi-discipline, weekend-anchored."
            )
    return out


def _format_recovery_programming(
    phase_structure: PhaseStructure | None,
    phase_spec: PhaseSpec,
    week_range: tuple[int, int] | None,
    layer1_payload: dict[str, Any],
    layer2a_payload: Layer2APayload | None,
    pool_is_empty: bool,
) -> list[str]:
    """#698 Track 1 (Slice 3b, D6) — render the deterministic per-week recovery
    dose AND its EXACT placement dates, allocated OFF the training session
    ceiling (not in the grid's discipline allocations; does not count toward the
    daily cap). Placement is deterministic (`compute_recovery_placement`, §6a):
    the LLM is told the recovery days are *assigned*, not chosen — its only job
    is filling `recovery_exercises` from the pool. The same pure function backs
    the validator placement-match rule, so render and enforcement can't drift.

    `high_load` per week is a planned deload week (D4 — bias to full rest);
    `compute_recovery_dose` trims one session toward genuine rest there, and the
    `extreme` band keeps recovery off the long day + the pre-key day.

    Suppress-on-empty (§6.3): when the recovery pool resolves empty, NO block is
    rendered — the LLM is never asked to fill an unfillable `recovery_exercises`
    (a guaranteed-invalid payload + a wasted correction-loop retry). Empty for
    any phase without a defined dose (unknown phase) too. A deload week that
    zeros a KNOWN recovery phase still renders an explicit full-rest line."""
    phase_name = phase_spec.phase_name
    if phase_name not in _RECOVERY_SESSIONS_PER_WEEK:
        return []
    if pool_is_empty:
        # Rule #15 — suppress-on-empty: attributable, not a silent drop.
        print(
            f"compute_recovery_placement: {phase_name} recovery pool empty — "
            "suppressing the recovery block (no recovery prescribed)"
        )
        return []
    if week_range is not None:
        weeks: range = range(week_range[0], week_range[1] + 1)
    else:
        weeks = range(1, phase_spec.weeks + 1)

    capacity = weekly_capacity_hours(layer1_payload)
    windows = layer1_payload.get("daily_availability_windows") or []
    enabled_days = derive_enabled_days(windows)
    long_dow = derive_long_session_dow(windows)
    phase_band = (
        (layer2a_payload.weekly_total_hours_by_phase or {}).get(phase_name)
        if layer2a_payload is not None
        else None
    )

    week_lines: list[str] = []
    any_high_load = False
    for w in weeks:
        high_load = periodization.is_deload_week_for(phase_structure, phase_name, w)
        any_high_load = any_high_load or high_load
        dose = compute_recovery_dose(phase_name, high_load)
        # The week's calendar dates (week 1 = the first 7 days of the phase),
        # clamped to the phase end — mirrors `_block_date_window`.
        wk_start = phase_spec.start_date + timedelta(days=(w - 1) * 7)
        wk_end = min(phase_spec.start_date + timedelta(days=w * 7 - 1), phase_spec.end_date)
        week_dates = [
            wk_start + timedelta(days=i) for i in range((wk_end - wk_start).days + 1)
        ]
        band = classify_recovery_load_band(capacity, phase_band, phase_name, high_load)
        placed = compute_recovery_placement(
            week_dates, enabled_days, long_dow, dose.sessions_this_week, band, pool_is_empty
        )
        if len(placed) < dose.sessions_this_week:
            # Rule #15 — fewer feasible candidate days than the dose requested
            # (clamp), or a zeroed deload week. Either way, attributable.
            print(
                f"compute_recovery_placement: {phase_name}:w{w} dose="
                f"{dose.sessions_this_week} placed={len(placed)} band={band} "
                f"high_load={high_load} (clamped to feasible days)"
            )
        if not placed:
            week_lines.append(
                f"  Week {w}: 0 recovery sessions — full rest "
                f"({'deload — ' if high_load else ''}prefer genuine rest)."
            )
            continue
        dates_txt = ", ".join(d.isoformat() for d in placed)
        week_lines.append(
            f"  Week {w}: place a recovery session on {dates_txt} "
            f"(~{dose.session_minutes} min each) — mobility / soft-tissue / "
            "breathwork. These dates are ASSIGNED; do not add, drop, or move them."
        )

    # Defensive: an empty week range (e.g. 0-week phase) → nothing to render.
    if not week_lines:
        return []

    out = [
        "=== Recovery programming (deterministic — off the training cap) ===",
        "Recovery/mobility sessions (kind='recovery') are ADDITIVE and do NOT "
        "count toward the ≤2/day training cap — a day may carry ≤2 training "
        "(cardio/strength) PLUS ≤1 recovery (the recovery takes the last daily "
        "slot). Recovery PLACEMENT is assigned below (deterministic) — emit a "
        "recovery session on exactly the listed dates, no more and no fewer; "
        "keep them sub-threshold (intensity easy/rest). Your only job on a "
        "recovery session is choosing its `recovery_exercises` from the "
        "`=== Recovery exercise pool ===` ids.",
    ]
    out.extend(week_lines)
    if phase_name == "Peak" or any_high_load:
        # D4 — load-adaptive rest directive (belt-and-suspenders to the assigned
        # dates, which already encode the high-load bias): under high load, full
        # rest is the protective default (adaptation-neutral vs active recovery).
        out.append(
            "  Under high load (Peak phase or a deload week), full rest is the "
            "protective default; the assigned recovery dates already reflect this."
        )
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

    # Single-source the long-session day with `session_grid.derive_long_session_dow`
    # (used by deterministic recovery placement) so the rendered `=== Schedule ===`
    # long day and the recovery placement anchor can never disagree (#698 Slice 3b).
    long_dow = derive_long_session_dow(windows)
    longest_idx: int | None = next(
        (
            i
            for i, w in enumerate(windows)
            if w.get("enabled") and w.get("day_of_week") == long_dow
        ),
        None,
    )
    longest_dur = (
        (windows[longest_idx].get("window_duration") or 0)
        if longest_idx is not None
        else 0
    )

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

    if long_dow is not None:
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
    terrain_feasibility: dict[str, TerrainResolution] | None = None,
    event_window_segments: list[EventWindowSegment] | None = None,
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
    # #336 — skill-capability gate set (discipline_id → toggle_name), derived
    # once from the Layer 2C `requires_skill_capability` flags and threaded into
    # both the grid annotation and the dedicated substitution directive below.
    skill_gated = skill_gated_disciplines(layer2c_payloads or {})
    parts.append("=== Session grid (deterministic — Track 2 §5.1/§5.2/§5.3) ===")
    parts.extend(
        _format_session_grid(
            layer1_payload,
            layer2a_payload,
            phase_structure,
            phase_spec.phase_name,
            race_event_payload,
            week_range=week_range,
            skill_gated=skill_gated,
            terrain_feasibility=terrain_feasibility,
            event_window_segments=event_window_segments,
        )
    )
    parts.append("")
    # #698 Track 1 (Slice 3b) — the deterministic recovery dose + its assigned
    # placement DATES, rendered right after the training grid but allocated OFF
    # its ceiling (additive; see `_format_recovery_programming`). Suppressed when
    # the recovery pool resolves empty (no unfillable payload); empty for
    # zero-dose phases too → no block.
    recovery_pool_is_empty = not compute_recovery_pool_ids(
        layer2c_payloads or {}, layer2d_payload
    )
    recovery_lines = _format_recovery_programming(
        phase_structure,
        phase_spec,
        week_range,
        layer1_payload,
        layer2a_payload,
        recovery_pool_is_empty,
    )
    if recovery_lines:
        parts.extend(recovery_lines)
        parts.append("")
    parts.extend(
        _format_skill_capability_gates(layer2c_payloads or {}, layer2a_payload)
    )
    # #540 — terrain-feasibility directive (companion to the inline grid tag).
    parts.extend(
        _format_session_feasibility(
            terrain_feasibility, layer2a_payload, layer2c_payloads or {}
        )
    )
    # Event Windows Slice 1 (#581 WS-H) — date-scoped overlay for any declared
    # window overlapping THIS synthesis unit. Block mode scopes to the block's
    # date window; whole-phase mode (seam re-synth) scopes to the phase span.
    if block_mode:
        _unit_start, _unit_end = _block_date_window(phase_spec, week_range)  # type: ignore[arg-type]
    else:
        _unit_start, _unit_end = phase_spec.start_date, phase_spec.end_date
    parts.extend(
        _format_event_window_overlay(
            event_window_segments,
            _unit_start,
            _unit_end,
            layer2a_payload,
            layer2c_payloads or {},
        )
    )

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

    # #335 Phase 2 §8 — the resolved strength-exercise pool, rendered for the
    # synthesizer's reading. Track 2 D1 also binds the tool-schema enum to the
    # cluster-union of these ids (see `compute_feasible_pool_ids` +
    # `build_record_phase_sessions_tool(..., feasible_pool_ids=...)`), making
    # out-of-pool picks structurally impossible at the SDK boundary.
    pool_lines = _format_strength_exercise_pool(
        layer2c_payloads, layer2a_payload, layer2d_payload
    )
    if pool_lines:
        parts.append("=== Strength exercise pool ===")
        parts.extend(pool_lines)
        parts.append("")

    # #698 Track 1 (Slice 2) — the resolved recovery/mobility pool. Track 1 D1
    # binds the tool-schema enum to these ids (see `compute_recovery_pool_ids` +
    # `build_record_phase_sessions_tool(..., recovery_pool_ids=...)`). Rendered
    # only when the recovery dose is in play (a recovery block was emitted above)
    # AND the pool resolves — no menu when there's nothing to prescribe.
    if recovery_lines:
        recovery_pool_lines = _format_recovery_exercise_pool(
            layer2c_payloads, layer2d_payload
        )
        if recovery_pool_lines:
            parts.append("=== Recovery exercise pool ===")
            parts.extend(recovery_pool_lines)
            parts.append("")

    # #698 Track 2 (A2) — the cardio drill pool, grouped by discipline + carrying
    # each row's coaching_cue dose. Bound to the tool-schema enum the same way
    # (compute_cardio_drill_pool_ids + build_record_phase_sessions_tool(...,
    # cardio_drill_pool_ids=...)). Suppress-on-empty: no menu → the LLM is never
    # handed an unfillable cardio_drills[] (mirrors recovery + §6a-G1).
    cardio_drill_disciplines = (
        {
            d.discipline_id
            for d in layer2a_payload.disciplines
            if d.inclusion == "included"
        }
        if layer2a_payload is not None
        else set()
    )
    cardio_drill_pool_lines = _format_cardio_drill_pool(
        layer2c_payloads or {},
        layer2a_payload,
        layer2d_payload,
        disciplines=cardio_drill_disciplines,
        phase=phase_spec.phase_name,
    )
    if cardio_drill_pool_lines:
        parts.append("=== Cardio drill pool (consider these) ===")
        parts.append(
            "Optionally attach one drill appropriate to today's discipline, from "
            "the pool below (pick by id only):"
        )
        parts.extend(cardio_drill_pool_lines)
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


def _repair_strength_collisions(
    sessions: list[PlanSession],
) -> tuple[list[PlanSession], list[str]]:
    """WS-E deterministic crash-guard: resolve any day carrying two `strength`
    sessions — which `Layer4Payload._check_two_per_day` hard-rejects — BEFORE
    validation, so the collision self-heals in code instead of forcing a model
    re-synthesis (the pv=69 / plan-70 stall class). Code decides placement; the
    LLM is left to compose session content.

    For each offending day, the later (`session_index_in_day==1`) strength is
    relocated onto the nearest in-list day holding a single non-hard CARDIO
    session — becoming that day's 2nd session (valid: a cardio is present, not
    two-strength, not two-hard) — and that target is consumed so a second
    collision can't reuse it. If no such day exists, the extra strength is
    dropped. Conservative: only relocates onto days the model already populated,
    so it never invents an unavailable training day. Pure. Returns
    (repaired_sessions, notes); empty notes == unchanged. Scoped to
    strength+strength; other `_check_two_per_day` cases keep the existing retry.
    """
    by_day: dict = {}
    for s in sessions:
        by_day.setdefault(s.date, []).append(s)

    consumed: set = set()
    updates: dict = {}  # session_id -> replacement PlanSession
    drops: set = set()  # session_ids to drop
    notes: list[str] = []

    def _find_target(exclude_date):
        for td in sorted(by_day):
            if td == exclude_date or td in consumed:
                continue
            ds = by_day[td]
            if (
                len(ds) == 1
                and ds[0].kind == "cardio"
                and ds[0].intensity_summary != "hard"
            ):
                return td, ds[0]
        return None

    for d in sorted(by_day):
        ss = by_day[d]
        strengths = [s for s in ss if s.kind == "strength"]
        if len(ss) != 2 or len(strengths) != 2:
            continue
        mover = max(strengths, key=lambda s: s.session_index_in_day)
        keeper = min(strengths, key=lambda s: s.session_index_in_day)
        updates[keeper.session_id] = keeper.model_copy(
            update={"session_index_in_day": 0}
        )
        target = _find_target(d)
        if target is not None:
            td, cardio = target
            consumed.add(td)
            updates[cardio.session_id] = cardio.model_copy(
                update={"session_index_in_day": 0}
            )
            updates[mover.session_id] = mover.model_copy(
                update={
                    "date": td,
                    "day_of_week": cardio.day_of_week,
                    "session_index_in_day": 1,
                }
            )
            notes.append(f"{d}: relocated 2nd strength -> {td}")
        else:
            drops.add(mover.session_id)
            notes.append(f"{d}: dropped 2nd strength (no relocation day)")

    if not notes:
        return sessions, []
    out: list[PlanSession] = []
    for s in sessions:
        if s.session_id in drops:
            continue
        out.append(updates.get(s.session_id, s))
    return out, notes


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
    # #540 — per-discipline terrain-feasibility resolutions rendered into the
    # session-grid block. Default None preserves legacy call sites.
    terrain_feasibility: dict[str, TerrainResolution] | None = None,
    # Event Windows Slice 1 (#581 WS-H) — date-scoped reduced-environment
    # segments rendered into the per-phase overlay. Default None preserves
    # legacy call sites + athletes with no windows.
    event_window_segments: list[EventWindowSegment] | None = None,
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
        effective_max_tokens = block_output_budget(
            max_sessions_this_unit, floor=max_tokens
        )
    else:
        max_sessions_this_unit = _MAX_SESSIONS_PER_PHASE
        unit_scope_start, unit_scope_end = phase_spec.start_date, phase_spec.end_date
        unit_tag = f"{phase_spec.phase_name}:full-phase"
        # Whole-phase mode (seam-driven re-synth) keeps the caller's budget — a
        # 56-session single call is the unit D-77 decomposition replaced; the
        # week-seam stitcher (Slice 3), not a token bump, is its scaling path.
        effective_max_tokens = max_tokens
    feasible_pool_ids = compute_feasible_pool_ids(layer2c_payloads, layer2d_payload)
    if len(feasible_pool_ids) > _FEASIBLE_POOL_ENUM_WARN_THRESHOLD:
        import logging
        logging.getLogger(__name__).warning(
            "feasible_pool_ids=%d exceeds threshold %d for %s; "
            "investigate 2C/2D filtering",
            len(feasible_pool_ids),
            _FEASIBLE_POOL_ENUM_WARN_THRESHOLD,
            unit_tag,
        )
    recovery_pool_ids = compute_recovery_pool_ids(layer2c_payloads, layer2d_payload)
    # #698 Track 2 (A2) — bind cardio_drills.exercise_id to the discipline/phase-
    # scoped drill pool (same enum the prompt renders). Empty → no enum (free
    # string) + suppressed prompt block, so an unfillable cardio_drills[] is
    # impossible (§6a-G1).
    cardio_drill_disciplines = (
        {
            d.discipline_id
            for d in layer2a_payload.disciplines
            if d.inclusion == "included"
        }
        if layer2a_payload is not None
        else set()
    )
    cardio_drill_pool_ids = compute_cardio_drill_pool_ids(
        layer2c_payloads,
        layer2d_payload,
        disciplines=cardio_drill_disciplines,
        phase=phase_spec.phase_name,
    )
    tool_schema = build_record_phase_sessions_tool(
        max_sessions_this_unit,
        feasible_pool_ids=feasible_pool_ids or None,
        recovery_pool_ids=recovery_pool_ids or None,
        cardio_drill_pool_ids=cardio_drill_pool_ids or None,
    )

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
        # RETURN within the function cap (`PLAN_GEN_FUNCTION_CAP_S`, 300s default
        # / 800s Pro) so it caches (or fails terminally fast) rather than
        # 504-looping forever. The first attempt always runs; later retries are
        # gated on accumulated latency.
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
            terrain_feasibility=terrain_feasibility,
            event_window_segments=event_window_segments,
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
        # reveals whether a SINGLE call is near the function cap
        # (`PLAN_GEN_FUNCTION_CAP_S`, 300s default / 800s Pro) or whether
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

        # WS-E deterministic crash-guard: resolve any strength+strength day in
        # code BEFORE validation so a collision self-heals instead of forcing a
        # retry/fumble (the pv=69 / plan-70 stall class). Runs every pass.
        sessions, _collision_notes = _repair_strength_collisions(sessions)
        if _collision_notes:
            print(
                f"synthesize_phase: {unit_tag} strength-collision repair — "
                + "; ".join(_collision_notes)
            )

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

        try:
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
        except ValidationError as e:
            # The per-row parse above only catches PlanSession-level faults. The
            # top-level Layer4Payload @model_validators (e.g. `_check_two_per_day`:
            # >2 sessions/day, strength+strength, two-hard, neither-cardio,
            # session_index ordering) fire only HERE, at payload construction. A
            # raw pydantic ValidationError used to escape the layer's typed-error
            # contract -> the route catch-all marked the WHOLE plan 'failed
            # unexpectedly' over one bad block (prod plan #47, 2026-05-31: "max 2
            # sessions per day (got 3)"). Convert it to a retryable
            # `schema_violation` -- same treatment as the parse step above -- so
            # the block re-synthesizes next pass (schema_violation is in the
            # route's `_RETRYABLE_BLOCK_CODES`) instead of discarding the plan.
            print(
                f"synthesize_phase: {unit_tag} attempt {current_pass + 1} "
                f"payload validation failed ({type(e).__name__}): {str(e)[:240]}"
            )
            # Rule #15 observability: the pydantic error truncates the offending
            # sessions, so a `_check_two_per_day` reject (strength+strength,
            # two-hard, >2/day, neither-cardio) was opaque in the log. Dump each
            # multi-session day's kind/discipline/index so the collision is
            # diagnosable from the log alone (Rule #14) rather than the discarded
            # draft. pv=69 (2026-06-13) burned a long triage on exactly this gap.
            _days_dbg: dict = {}
            for _s in sessions:
                _days_dbg.setdefault(_s.date, []).append(_s)
            _multi_dbg = sorted((d, ss) for d, ss in _days_dbg.items() if len(ss) > 1)
            if _multi_dbg:
                _detail_dbg = "; ".join(
                    f"{d}: "
                    + ", ".join(
                        f"{x.kind}/{x.discipline_id or '-'}/idx{x.session_index_in_day}"
                        for x in sorted(ss, key=lambda y: y.session_index_in_day)
                    )
                    for d, ss in _multi_dbg
                )
                print(
                    f"synthesize_phase: {unit_tag} multi-session days — {_detail_dbg}"
                )
            if current_pass >= capped_retries:
                raise Layer4OutputError(
                    "schema_violation",
                    detail=f"Layer4Payload invariant violated: {e}",
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

        ctx = ValidatorContext(
            layer2a_payload=layer2a_payload,
            layer2b_payload=layer2b_payload,
            layer2c_payloads=dict(layer2c_payloads),
            layer2d_payload=layer2d_payload,
            layer2e_payload=layer2e_payload,
            layer3a_payload=layer3a_payload,
            layer3b_payload=layer3b_payload,
            race_event=race_event_payload,
            capacity_hours=weekly_capacity_hours(layer1_payload),
            daily_availability_windows=daily_windows_from_layer1(layer1_payload),
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
        # Rule #15 — the rule_name set above is the WHAT; the `detail` is the WHY
        # (which day overran its window, actual-vs-assigned recovery dates). Surface
        # blocker details so a rejection is diagnosable from logs alone — esp. the
        # #698 Slice-3b availability rules (daily_window_fit / schedule_violation /
        # recovery_placement_match) newly active in prod, where a placement-vs-
        # window-fit deadlock would show both rule_names with their dates here.
        for _f in validator_result.rule_failures:
            if _f.severity == "blocker":
                print(
                    f"synthesize_phase: {unit_tag}   blocker {_f.rule_name}: {_f.detail}"
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
    if latest_validator is None:
        # The per-block budget guard's best-effort-accept path (line ~1544) can
        # `break` with parseable `latest_sessions` set but `latest_validator`
        # still None: every completed pass raised a top-level Layer4Payload
        # ValidationError, whose handler assigns `latest_sessions` at parse time
        # (line ~1709) but `continue`s WITHOUT ever running the validator (so
        # `latest_validator` is never set), and the budget guard then accepts the
        # last parseable attempt. A bare `assert latest_validator is not None`
        # here raised a raw AssertionError that escaped the layer's typed-error
        # contract -> the route catch-all discarded the WHOLE plan over one
        # unconverged block (prod plan #52, 2026-05-31 — a sibling of #47). Raise
        # a RETRYABLE coded error instead (synthesis_budget_exhausted is in the
        # route's `_RETRYABLE_BLOCK_CODES`) so the block re-synthesizes on the
        # next resumable pass like any other unconverged block, rather than
        # killing a near-complete plan.
        raise Layer4OutputError(
            "synthesis_budget_exhausted",
            detail=(
                f"{unit_tag}: per-block budget spent before any validation pass "
                "completed (every attempt raised a payload invariant violation)"
            ),
        )

    # D-77 §6 diagnostics — per-block synthesis summary: call count + total
    # latency expose how close a block runs to the function cap
    # (`PLAN_GEN_FUNCTION_CAP_S`, 300s default / 800s Pro), and
    # cap_hit/retries_used show whether it converged or was best-effort accepted.
    # (Fires only when the block RETURNS — a block 504-killed mid-loop is traced
    # via the per-attempt lines above instead.) Diagnostic only; trim later.
    # #321 observability — the ACCEPTED path was previously silent on which
    # rules the block still trips (warnings, or blockers demoted on a best-effort
    # cap_hit accept). Surface them on the summary line so an accepted-but-flagged
    # block (e.g. a taper week riding `volume_band_below` as a warning) is visible
    # without re-deriving it from the validator.
    _accepted_flags = "; ".join(
        f"{f.rule_name}({f.severity})" for f in latest_validator.rule_failures
    )[:240]
    print(
        f"synthesize_phase: {unit_tag} done — {llm_call_count} llm call(s), "
        f"{total_latency_ms}ms total, accepted={latest_validator.accepted}, "
        f"cap_hit={cap_hit}, retries_used={final_retries_used}, "
        f"sessions={len(latest_sessions)}"
        + (f", flags: {_accepted_flags}" if latest_validator.rule_failures else "")
    )

    # #321 observability — opt-in per-session content dump
    # (`PLAN_GEN_LOG_BLOCK_CONTENT=1`). Off by default so prod logs aren't
    # flooded; on, it dumps one compact line per session in the accepted block —
    # the synthesized content, which is otherwise never logged (only the count).
    if os.getenv("PLAN_GEN_LOG_BLOCK_CONTENT") == "1":
        for s in latest_sessions:
            print(
                f"  block-content {unit_tag}: {s.date} "
                f"{s.discipline_name or s.kind} {s.duration_min}min "
                f"{s.intensity_summary}"
            )

    # §8.1 orchestrator stamp: mark planned-deload weeks `recovery_week` (the
    # same cadence the volume grid uses, so the flag and the bent band agree).
    # Done here — before the block is returned/snapshotted/cached — so the flag
    # rides every persistence path. Closes the documented-but-unimplemented gap.
    periodization.stamp_recovery_week(latest_sessions, phase_structure)

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
    "block_output_budget",
    "build_record_phase_sessions_tool",
    "build_synthesis_metadata_from_result",
    "render_user_prompt",
    "synthesize_phase",
]
