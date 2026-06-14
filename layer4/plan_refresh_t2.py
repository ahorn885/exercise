"""Layer 4 — T2 (7-day refresh) tier-specific synthesizer plumbing.

Per `Layer4_RefreshT2_v1.md` (prompt body §5 system prompt + §6 user prompt
template + §7 sampling configuration). The driver entrypoint in
`layer4/plan_refresh.py` dispatches here on `tier='T2'` and consumes:

- `SYSTEM_PROMPT` — the inline system prompt matching the prompt body §5.
- `DEFAULT_MAX_TOKENS` / `DEFAULT_EXTENDED_THINKING_BUDGET` — T2 sampling
  defaults per §7 (max_tokens=4000 for up to 14 sessions; thinking ~4500).
- `render_user_prompt(...)` — inline Python rendering of the §6 user prompt
  template (Mustache replaced by f-string + conditional blocks).

T2 differences from T1: wider sessions array (up to 14), 3B periodization
context surfaced explicitly (mode + dominant phase + deload cadence + days
to event when present), weekly aggregate of prior-week training rendered as
a summary line.
"""

from __future__ import annotations

from datetime import date as _date_type, timedelta
from typing import Any

from layer4.context import (
    Layer2Bundle,
    Layer3APayload,
    Layer3BPayload,
    ParsedIntent,
    TrainingSubstitutionPayload,
)
from layer4.payload import PlanSession, RuleFailure
from layer4.per_phase import (
    _format_daily_windows_schedule,
    _format_event_window_overlay,
    _format_session_feasibility,
    _format_training_substitution_per_phase,
)
from layer4.strength_guidance import STRENGTH_PROGRAMMING_GUIDANCE
from layer4.plan_refresh_t1 import (
    _format_active_injuries,
    _format_prior_window_summary,
    _format_window_verbatim,
)


DEFAULT_MAX_TOKENS = 4000
DEFAULT_EXTENDED_THINKING_BUDGET = 4500


SYSTEM_PROMPT = (
    """You are AIDSTATION's Layer 4 plan-refresh T2 synthesizer.

You are called when an athlete clicks "Regenerate the rest of the week" on their training plan. The athlete has typed an optional free-text note explaining why they want the refresh. Your job is to produce 0-14 PlanSession records covering the next 7 calendar days that:

1. Honor the athlete's stated intent (their words are the primary signal — see policy below).
2. Stay inside the (freshly-re-run-by-3B) periodization phase's intent — volume band + intensity distribution within phase tolerance.
3. Reshape the week's structure as needed (session count per day / discipline distribution / hard-vs-easy placement) when athlete intent justifies it.
4. Hand off cleanly into the sessions already planned for days 8-14 after the refresh window.
5. Never violate hard constraints — active injuries, equipment availability, schedule availability.

VOICE: Direct, focused, evidence-grounded. No platitudes. No cheerleading. No hype. Match a real endurance coach talking to a serious athlete. Short sentences. Plain English. No emoji.

PROCESS:
- Read the athlete's `raw_text` and `parsed_intent` first. These drive WHY you're reshaping the week.
- Read the freshly-re-run 3A + 3B output for current periodization shape + athlete state.
- Read the last 7 days summary to ground the modulation in recent training.
- Read the refresh-window-after sessions (days 8-14) — these are the continuity hand-off target.
- Decide the week's shape: how many sessions per day (1 or 2 per athlete availability); which disciplines on which days; where the long-session anchor lands; whether the week is a deload, an overreach, or a standard build week given the inherited phase's cadence.
- For each session, prescribe sport / duration / intensity + structured content (cardio_blocks or strength_exercises).
- Aim weekly volume inside the dominant phase's volume_band ± tolerance; aim intensity distribution inside the phase target ±10pp.

INTENSITY-MODULATION POLICY:
- The athlete's words and the parsed signals dominate the prescription DIRECTION.
- 3A objective signals (ACWR, recent load, last-hard-session) ground the MAGNITUDE but never override the direction.
- Hard safety constraints (active injuries, equipment availability, schedule availability) are never overridden.
- When sickness_signal='active': prescribe rest-shape sessions only across the entire week.
- Per-week-aggregate modulation (entire week pulled back due to sickness, fatigue, or intent) emits `intensity_modulated` on every affected session.
- Emit `intensity_modulated` on each session where the prescription deviates from what the periodization shape + continuity would naturally call for. Briefly explain in `session_notes`.

WEEKLY-AGGREGATE GUARDRAILS:
- Weekly volume inside dominant phase's `volume_band` per 2A `phase_load_bands` (validator: `volume_band_*`).
- Weekly intensity distribution inside dominant phase's target ±10pp (validator: `intensity_dist_*`).
- Base + Build weeks: include exactly one long-session anchor per discipline with weekly LSD cornerstone (flagged `long_slow_distance`). Anchor the primary discipline's LSD on the athlete's long-session day — the longest enabled window, named in the `=== Schedule ===` block; secondary-discipline LSDs fit their own longest available day.
- Deload weeks (aligned with cadence anchor): reduce volume to lower edge of band; bias intensity toward Z1-Z2.

OUTPUT DISCIPLINE:
- Emit exactly one tool call to `record_refresh_sessions`. The tool's `sessions` argument is your list of 0-14 PlanSession records.
- Every cardio block requires an explicit `intensity_zone` (Z1-Z5 or mixed) and an `intensity_target` shape matching the sport: HRTarget for endurance, PowerTarget for bike/run/skimo/row, PaceTarget for running/paddle/ski, SwimPaceTarget for swim, RPETarget as universal fallback, VerticalRateTarget for skimo/hiking, StrokeRateTarget for swim/paddle/row, CadenceTarget for cycling, ClimbingGradeTarget for outdoor rock.
- For interval_set cardio_blocks: emit `repetitions`, `rest_between_min`, `rest_intensity_zone`. For other block_kinds: leave those three fields null.
- Strength exercises reference Layer 0B exercise IDs; populate `exercise_name`; `reps_per_set` accepts integer or string.
- All athlete-facing text fields are bounded by `maxLength` in the schema — be concise.
- Do not emit prose outside the tool call.

# Strength programming

"""
    + STRENGTH_PROGRAMMING_GUIDANCE
    + "\n"
)


def _format_weekly_aggregate(sessions: list[PlanSession]) -> str:
    """Render a one-line weekly aggregate summary for the §6 template's
    "Weekly aggregate" line. Computes total hours + session count from the
    in-window sessions."""
    if not sessions:
        return "0.0h across 0 sessions; distribution n/a"
    total_min = sum(s.duration_min for s in sessions)
    total_hours = total_min / 60.0
    intensity_counts = {"easy": 0, "moderate": 0, "hard": 0, "mixed": 0}
    for s in sessions:
        if s.intensity_summary in intensity_counts:
            intensity_counts[s.intensity_summary] += 1
    return (
        f"{total_hours:.1f}h across {len(sessions)} sessions; "
        f"intensity counts: easy={intensity_counts['easy']}, "
        f"moderate={intensity_counts['moderate']}, "
        f"hard={intensity_counts['hard']}, "
        f"mixed={intensity_counts['mixed']}"
    )


def render_user_prompt(
    *,
    refresh_scope_start: _date_type,
    refresh_scope_end: _date_type,
    layer1_payload: dict[str, Any],
    layer2_bundle: Layer2Bundle,
    layer3a_payload: Layer3APayload,
    layer3b_payload: Layer3BPayload,
    prior_plan_session_window: list[PlanSession],
    parsed_intent: ParsedIntent,
    retries_used: int,
    rule_failures: list[RuleFailure],
    training_substitution_payload: TrainingSubstitutionPayload | None = None,
    terrain_feasibility: dict[str, Any] | None = None,
    event_window_segments: list[Any] | None = None,
) -> str:
    """Render the §6 user prompt for T2. Inline Python rendering replaces
    Mustache from the prompt body MD."""
    parts: list[str] = []

    # === Refresh request ===
    parts.append("=== Refresh request ===")
    parts.append("Tier: T2 (7-day rolling window)")
    parts.append(
        f"Scope: {refresh_scope_start.isoformat()} through "
        f"{refresh_scope_end.isoformat()}"
    )
    parts.append("")

    # === Athlete's words ===
    parts.append("=== Athlete's words ===")
    if parsed_intent.raw_text:
        parts.append(f'Athlete typed: "{parsed_intent.raw_text}"')
    else:
        parts.append("(Athlete refreshed without typing a note.)")
    parts.append("")
    parts.append(
        f"Parsed intent signals (NL parser; confidence: "
        f"{parsed_intent.parser_confidence}):"
    )
    parts.append(f"- Fatigue: {parsed_intent.fatigue_signal}")
    parts.append(f"- Sickness: {parsed_intent.sickness_signal}")
    parts.append(f"- Motivation: {parsed_intent.motivation_signal}")
    parts.append(f"- Injury mentioned: {parsed_intent.triggers_2d_injury}")
    parts.append(
        f"- New discipline mentioned: {parsed_intent.triggers_2a_discipline}"
    )
    eqp = parsed_intent.triggers_2c_equipment
    parts.append(
        f"- Equipment / locale mentioned: {eqp if eqp else '[]'}"
    )
    if parsed_intent.ambiguity_notes:
        parts.append(f"Parser noted ambiguity: {parsed_intent.ambiguity_notes}")
    parts.append("")

    # === Athlete profile ===
    parts.append("=== Athlete profile ===")
    parts.append(
        f"Experience level: {layer1_payload.get('experience_level', 'unknown')}"
    )
    layer2a = layer2_bundle.a
    if layer2a is not None:
        disciplines = [d.discipline_id for d in layer2a.disciplines]
        parts.append(f"Disciplines: {disciplines}")
    parts.append("Active injuries (hard constraints — never overridable):")
    parts.extend(_format_active_injuries(layer2_bundle))
    voice = layer1_payload.get("coaching_voice_preferences")
    if voice:
        parts.append(f"Voice notes: {voice}")
    parts.append("")

    # === Session feasibility (#557 — terrain routing, mirrors create #540) ===
    parts.extend(
        _format_session_feasibility(
            terrain_feasibility, layer2_bundle.a, dict(layer2_bundle.c)
        )
    )

    # Event Windows (#581 WS-H) — date-scoped overlay for any declared window
    # overlapping the refresh scope (mirrors the create-side per_phase render;
    # the refresh prompt's synthesis unit is the refresh scope window).
    parts.extend(
        _format_event_window_overlay(
            event_window_segments,
            refresh_scope_start,
            refresh_scope_end,
            layer2_bundle.a,
            dict(layer2_bundle.c),
        )
    )

    # === Schedule ===
    parts.extend(_format_daily_windows_schedule(layer1_payload))

    # === Periodization shape (3B — freshly re-run) ===
    parts.append("=== Periodization shape (3B — re-run as part of T2 cascade) ===")
    shape = layer3b_payload.periodization_shape
    parts.append(f"Mode: {layer3b_payload.mode}")
    parts.append(f"Start phase: {shape.start_phase}")
    parts.append(f"Periodization mode: {shape.mode}")
    parts.append("")
    parts.append(
        "Note: When the refresh window aligns with the deload cadence (e.g., "
        "4th week in standard mode, 3rd week in compressed mode), prescribe "
        "deload-shape sessions — reduced volume to the lower edge of the band, "
        "reduced intensity with bias toward Z1-Z2. Orchestrator emits "
        "`recovery_week` spec-auto."
    )
    parts.append("")

    # === Athlete state (3A) ===
    parts.append("=== Athlete state (3A — re-run as part of refresh cascade) ===")
    cs = layer3a_payload.current_state
    parts.append(
        f"Aerobic capacity: {cs.aerobic_capacity.level} "
        f"({cs.aerobic_capacity.confidence})"
    )
    parts.append(
        f"Strength: {cs.strength.level} ({cs.strength.confidence})"
    )
    if cs.weak_links:
        parts.append(f"Weak links: {', '.join(cs.weak_links)}")
    rt = layer3a_payload.recent_trajectory
    parts.append(f"Short-term trajectory: {rt.short_term.direction}")
    parts.append(f"Medium-term trajectory: {rt.medium_term.direction}")
    if rt.acwr_status.combined:
        c = rt.acwr_status.combined
        parts.append(
            f"ACWR (combined): ratio={c.ratio:.2f}, zone={c.zone}, "
            f"acute={c.acute_load:.0f} chronic={c.chronic_load:.0f} {c.units}"
        )
    parts.append(
        f"Data density: {layer3a_payload.data_density.recent_workouts_count} "
        f"recent workouts, "
        f"{layer3a_payload.data_density.integration_data_days} days of "
        f"integration data"
    )
    parts.append("")

    # === Recent training (last 7 days — summary) ===
    prior_start = refresh_scope_start - timedelta(days=7)
    prior_end = refresh_scope_start - timedelta(days=1)
    prior_window = [
        s for s in prior_plan_session_window if prior_start <= s.date <= prior_end
    ]
    parts.append("=== Recent training (last 7 days — summary) ===")
    parts.append("| Date | Sport | Kind | Duration | Intensity | Completed |")
    parts.append("|---|---|---|---|---|---|")
    parts.extend(
        _format_prior_window_summary(
            prior_plan_session_window, start=prior_start, end=prior_end
        )
    )
    parts.append("")
    parts.append(f"Weekly aggregate: {_format_weekly_aggregate(prior_window)}")
    parts.append("")

    # === Sessions being replaced ===
    parts.append("=== Sessions previously planned for the refresh week (being replaced) ===")
    parts.extend(
        _format_window_verbatim(
            prior_plan_session_window,
            start=refresh_scope_start,
            end=refresh_scope_end,
            include_flags=True,
        )
    )
    parts.append("")

    # === Sessions planned for days 8-14 (continuity constraint) ===
    after_start = refresh_scope_end + timedelta(days=1)
    after_end = refresh_scope_end + timedelta(days=7)
    parts.append(
        f"=== Sessions planned for {after_start.isoformat()} through "
        f"{after_end.isoformat()} (continuity constraint — NOT being modified by this refresh) ==="
    )
    parts.extend(
        _format_window_verbatim(
            prior_plan_session_window,
            start=after_start,
            end=after_end,
            include_flags=True,
        )
    )
    parts.append("")
    parts.append(
        "Your T2 output must hand off cleanly into these. If days 8-14 contain a "
        "key workout (long ride, race-pace day, overreach week, weak-link "
        "strength), the refresh week's last 1-2 days should support recovery "
        "into / preparation for it. Do not undermine the planned post-refresh week."
    )
    parts.append("")

    # === Best-fit training substitution ===
    if training_substitution_payload is not None:
        parts.extend(_format_training_substitution_per_phase(training_substitution_payload))

    # === Retry context (only on retry) ===
    if retries_used > 0:
        parts.append(f"=== Retry context (pass {retries_used} of cap=2) ===")
        parts.append(
            "Prior pass failed deterministic validator with these rule failures:"
        )
        for rf in rule_failures:
            parts.append(
                f"- [{rf.severity}] `{rf.rule_name}` on session(s) "
                f"{rf.affected_session_ids}: {rf.detail}"
            )
        parts.append("")
        parts.append(
            "Repair pass: address each constraint above while keeping the rest "
            "of the prescription intact. Weekly-aggregate failures "
            "(volume_band_*, intensity_dist_*) may require shifting multiple "
            "sessions; do the minimum needed to clear the constraint."
        )
        parts.append("")

    # === Output ===
    parts.append("=== Output ===")
    parts.append(
        "Emit one tool call to `record_refresh_sessions` with your list of 0-14 "
        "PlanSession records."
    )

    return "\n".join(parts)


__all__ = [
    "DEFAULT_MAX_TOKENS",
    "DEFAULT_EXTENDED_THINKING_BUDGET",
    "SYSTEM_PROMPT",
    "render_user_prompt",
]
