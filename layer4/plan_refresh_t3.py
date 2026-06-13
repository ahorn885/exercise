"""Layer 4 — T3 (28-day refresh) intra-phase tier-specific synthesizer plumbing.

Per `Layer4_RefreshT3_v1.md` (prompt body §5 system prompt + §6 user prompt
template + §7 sampling configuration). The driver entrypoint in
`layer4/plan_refresh.py` dispatches here on `tier='T3'` AFTER verifying
that the refresh scope is intra-phase (per `phase_structure_from_3b()` +
`scope_spans_phase_boundary()` — cross-phase T3 raises
`tier_t3_cross_phase_requires_pattern_a` and is queued for Step 4f).

T3 differences from T2:

- Wider sessions array (up to 56 = 28 days × max 2/day).
- Output budget sized to the 56-session ceiling by the driver via
  `per_phase.block_output_budget` (clamped to the model's 64K ceiling), with
  thinking OFF so the forced tool call gets the whole budget — a flat 10000
  truncated `record_refresh_sessions` mid-output (`stop_reason=max_tokens`).
- Full upstream cascade in payload (all 5 Layer 2 nodes + 3A + 3B + 1).
- Tiered prior-window rendering: week -2 rollup + week -1 verbatim
  (extends T2's single-week prior context).
- Phase-trajectory-aware reshape framing (Andy 2026-05-17 Step 4d Pick 4) —
  the 4 weeks compose a coherent mesocycle toward the dominant phase's
  exit state. Continuity to days 29-35 is soft (summary-table only).
- Deload-cadence reminder is load-bearing (4 weeks typically contains one
  deload).
- Reuses T1's shared `_format_active_injuries` + `_format_window_verbatim`
  helpers; T2's `_format_weekly_aggregate` for the week -2 rollup line.
"""

from __future__ import annotations

from datetime import date as _date_type, timedelta
from typing import Any, Literal

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
    _format_session_feasibility,
    _format_training_substitution_per_phase,
)
from layer4.plan_refresh_t1 import (
    _format_active_injuries,
    _format_prior_window_summary,
    _format_window_verbatim,
)
from layer4.plan_refresh_t2 import _format_weekly_aggregate


DEFAULT_MAX_TOKENS = 10000
"""Floor only — the driver sizes the effective ceiling to the 56-session block via
`per_phase.block_output_budget` (clamped to the model's 64K output ceiling)."""

DEFAULT_EXTENDED_THINKING_BUDGET = 0
"""Thinking OFF (mirrors `per_phase.DEFAULT_EXTENDED_THINKING_BUDGET`): the forced
tool call gets the entire `max_tokens` as output budget. Required here because the
output budget is sized to the model's 64K ceiling — a stacked thinking budget
would make the request `max_tokens + thinking` exceed the model limit (a 400). The
former 6500, paired with a flat 10000 max_tokens, also starved output on the
thinking attempt (the #569 live verify caught the resulting `schema_violation`)."""


# Per-mode deload cadence (which week-in-mesocycle is the deload):
# standard=4th, compressed=3rd, extended=5th, custom=judgment.
_DELOAD_CADENCE: dict[
    Literal["standard", "compressed", "extended", "custom"], int | None
] = {
    "standard": 4,
    "compressed": 3,
    "extended": 5,
    "custom": None,
}


SYSTEM_PROMPT = """You are AIDSTATION's Layer 4 plan-refresh T3 synthesizer.

You are called when an athlete clicks "Refresh the next 4 weeks" on their training plan. The athlete has typed an optional free-text note explaining why they want the refresh. Your job is to produce 0-56 PlanSession records covering the next 28 calendar days that:

1. Honor the athlete's stated intent (their words are the primary signal).
2. Stay inside the freshly-re-run periodization phase's intent — volume band + intensity distribution within phase tolerance, applied per-week (x 4) AND mesocycle-wide.
3. Reshape the mesocycle for phase progress (phase-trajectory-aware reshape) — the 4 weeks should reflect coherent mesocycle progression toward the dominant phase's exit state.
4. Place the deload week when the cadence anchor falls inside the scope.
5. Hand off softly into the sessions already planned for days 29-35 after the refresh window. Continuity to week 5 is secondary to phase progress.
6. Never violate hard constraints — active injuries, equipment availability, schedule availability.

VOICE: Direct, focused, evidence-grounded. No platitudes. No cheerleading. No hype. Match a real endurance coach talking to a serious athlete. Short sentences. Plain English. No emoji.

PROCESS:
- Read the athlete's `raw_text` and `parsed_intent` first. These drive WHY you're reshaping the mesocycle.
- Read the freshly-re-run full upstream cascade (2A + 2B + 2C + 2D + 2E + 3A + 3B) for current state.
- Read the prior 2 weeks of training (week -2 rollup + week -1 verbatim) to ground the modulation in recent training.
- Read the dominant phase's intent + volume band + intensity distribution + deload cadence anchor + days-to-event (when applicable).
- Decide the mesocycle shape: which week is the highest-volume; where the deload lands; whether intent calls for an overreach week; how the 4-week intensity distribution sums to phase target.
- Decide each week's shape: session count per day (1 or 2 per availability); discipline mix; long-session anchor placement; hard-vs-easy day spacing.
- For each session, prescribe sport / duration / intensity + structured content (cardio_blocks or strength_exercises).

INTENSITY-MODULATION POLICY:
- The athlete's words and the parsed signals dominate the prescription DIRECTION (mesocycle reshape direction + per-session modulation).
- 3A objective signals (ACWR, recent load, last-hard-session) ground the MAGNITUDE but never override the direction.
- Hard safety constraints (active injuries, equipment availability, schedule availability) are never overridden.
- When sickness_signal='active': prescribe rest-shape across the entire scope (athlete must clear sickness before resuming load — no T3-scale reshape during active illness).
- Mesocycle-level modulation (entire mesocycle pulled back due to overreach recovery, illness recent-recovery, intent reshape) emits `intensity_modulated` on every affected session.
- Emit `intensity_modulated` on each session where the prescription deviates from what the periodization shape + dominant-phase intent would naturally call for. Briefly explain in `session_notes`.

WEEKLY-AGGREGATE GUARDRAILS (per-week, x 4):
- Each week's volume inside dominant phase's `volume_band` per 2A `phase_load_bands` (validator: `volume_band_*` per-week).
- Mesocycle-wide intensity distribution inside dominant phase's target +/-10pp (validator: `intensity_dist_*` per-phase).
- Base + Build weeks: include exactly one long-session anchor per discipline per week with weekly LSD cornerstone (flagged `long_slow_distance`). Anchor the primary discipline's LSD on the athlete's long-session day — the longest enabled window, named in the `=== Schedule ===` block; secondary-discipline LSDs fit their own longest available day.
- Deload week (cadence-anchor aligned): reduce volume to lower edge of band; bias intensity toward Z1-Z2. Orchestrator emits `recovery_week` spec-auto.

ACWR FORWARD PROJECTION:
- The 28-day window is long enough for ACWR to be load-bearing. Acute (trailing 7d) / chronic (trailing 28d) ratio must stay inside 0.7-1.4 across the scope; aim 0.8-1.3 for warning-clean.
- A ramp from the prior 2-week baseline that pushes ACWR > 1.4 by week 3 will fail validation. Pace the load increase across the mesocycle.

OUTPUT DISCIPLINE:
- Emit exactly one tool call to `record_refresh_sessions`. The tool's `sessions` argument is your list of 0-56 PlanSession records.
- Every cardio block requires an explicit `intensity_zone` (Z1-Z5 or mixed) and an `intensity_target` shape matching the sport: HRTarget for endurance, PowerTarget for bike/run/skimo/row, PaceTarget for running/paddle/ski, SwimPaceTarget for swim, RPETarget as universal fallback, VerticalRateTarget for skimo/hiking, StrokeRateTarget for swim/paddle/row, CadenceTarget for cycling, ClimbingGradeTarget for outdoor rock.
- For interval_set cardio_blocks: emit `repetitions`, `rest_between_min`, `rest_intensity_zone`. For other block_kinds: leave those three fields null.
- Strength exercises reference Layer 0B exercise IDs; populate `exercise_name`; `reps_per_set` accepts integer or string.
- All athlete-facing text fields are bounded by `maxLength` in the schema — be concise.
- Do not emit prose outside the tool call.
"""


def _format_deload_cadence_line(
    mode: Literal["standard", "compressed", "extended", "custom"]
) -> str:
    """Render the deload-cadence reminder line for the §6 template."""
    cadence_n = _DELOAD_CADENCE[mode]
    if cadence_n is None:
        return (
            f"Deload cadence: mode={mode} — coaching judgment. Pick a deload "
            "week aligned with prior mesocycle cadence + athlete state."
        )
    return (
        f"Deload cadence: mode={mode} — deload weeks fall every {cadence_n}th "
        "week. When the cadence anchor falls inside the 28-day scope, prescribe "
        "that week as deload-shape; orchestrator emits `recovery_week` spec-auto."
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
    dominant_phase_name: str | None = None,
    dominant_phase_start_date: _date_type | None = None,
    dominant_phase_end_date: _date_type | None = None,
) -> str:
    """Render the §6 user prompt for T3 intra-phase. Inline Python rendering
    replaces Mustache from the prompt body MD.

    `dominant_phase_*` are driver-supplied per the §3.5 dominant-phase
    context block; when None (intra-phase verification skipped in tests),
    the prompt renders them as placeholder strings."""
    parts: list[str] = []
    scope_days = (refresh_scope_end - refresh_scope_start).days + 1

    # === Refresh request ===
    parts.append("=== Refresh request ===")
    parts.append("Tier: T3 (28-day rolling window — mesocycle)")
    parts.append(
        f"Scope: {refresh_scope_start.isoformat()} through "
        f"{refresh_scope_end.isoformat()} ({scope_days} days)"
    )
    if dominant_phase_name:
        ds = (
            dominant_phase_start_date.isoformat()
            if dominant_phase_start_date
            else "(unknown)"
        )
        de = (
            dominant_phase_end_date.isoformat()
            if dominant_phase_end_date
            else "(unknown)"
        )
        parts.append(
            f"Dominant phase: {dominant_phase_name} ({ds} through {de})"
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
    parts.append(f"- Equipment / locale mentioned: {eqp if eqp else '[]'}")
    if parsed_intent.ambiguity_notes:
        parts.append(f"Parser noted ambiguity: {parsed_intent.ambiguity_notes}")
    parts.append("")

    # === Athlete profile (post-cascade) ===
    parts.append("=== Athlete profile (post-cascade) ===")
    parts.append(
        f"Experience level: {layer1_payload.get('experience_level', 'unknown')}"
    )
    layer2a = layer2_bundle.a
    if layer2a is not None:
        disciplines = [d.discipline_id for d in layer2a.disciplines]
        parts.append(f"Disciplines (from freshly-re-run 2A): {disciplines}")
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

    # === Schedule ===
    parts.extend(_format_daily_windows_schedule(layer1_payload))

    # === Periodization shape (3B — re-run as part of T3 cascade) ===
    parts.append(
        "=== Periodization shape (3B — re-run as part of T3 cascade) ==="
    )
    shape = layer3b_payload.periodization_shape
    parts.append(f"Mode: {shape.mode}")
    parts.append(f"Start phase (athlete's overall plan): {shape.start_phase}")
    if dominant_phase_name:
        parts.append(f"Dominant phase covering this refresh: {dominant_phase_name}")
        if dominant_phase_end_date:
            parts.append(
                f"Dominant phase end date: {dominant_phase_end_date.isoformat()}"
            )
    parts.append("")
    parts.append(_format_deload_cadence_line(shape.mode))
    parts.append("")

    # === Athlete state (3A) ===
    parts.append(
        "=== Athlete state (3A — re-run as part of T3 cascade) ==="
    )
    cs = layer3a_payload.current_state
    parts.append(
        f"Aerobic capacity: {cs.aerobic_capacity.level} "
        f"({cs.aerobic_capacity.confidence})"
    )
    parts.append(f"Strength: {cs.strength.level} ({cs.strength.confidence})")
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

    # === Week -2 rollup ===
    week_minus_2_start = refresh_scope_start - timedelta(days=14)
    week_minus_2_end = refresh_scope_start - timedelta(days=8)
    week_minus_2_sessions = [
        s
        for s in prior_plan_session_window
        if week_minus_2_start <= s.date <= week_minus_2_end
    ]
    parts.append(
        f"=== Recent training — week -2 rollup "
        f"({week_minus_2_start.isoformat()} through "
        f"{week_minus_2_end.isoformat()}) ==="
    )
    parts.append(_format_weekly_aggregate(week_minus_2_sessions))
    parts.append("")

    # === Week -1 verbatim ===
    week_minus_1_start = refresh_scope_start - timedelta(days=7)
    week_minus_1_end = refresh_scope_start - timedelta(days=1)
    parts.append(
        f"=== Recent training — last week verbatim "
        f"({week_minus_1_start.isoformat()} through "
        f"{week_minus_1_end.isoformat()}) ==="
    )
    parts.extend(
        _format_window_verbatim(
            prior_plan_session_window,
            start=week_minus_1_start,
            end=week_minus_1_end,
            include_flags=True,
        )
    )
    parts.append("")

    # === Refresh window during prior (summary) ===
    parts.append(
        "=== Sessions previously planned for the 28-day refresh window "
        "(being replaced) ==="
    )
    parts.append("| Date | Sport | Kind | Duration | Intensity |")
    parts.append("|---|---|---|---|---|")
    parts.extend(
        _format_prior_window_summary(
            prior_plan_session_window,
            start=refresh_scope_start,
            end=refresh_scope_end,
        )
    )
    parts.append("")

    # === Refresh window after (summary; soft continuity) ===
    week_5_start = refresh_scope_end + timedelta(days=1)
    week_5_end = refresh_scope_end + timedelta(days=7)
    parts.append(
        f"=== Sessions planned for week 5 ({week_5_start.isoformat()} through "
        f"{week_5_end.isoformat()}) — SOFT CONTINUITY ONLY ==="
    )
    parts.append("| Date | Sport | Kind | Duration | Intensity |")
    parts.append("|---|---|---|---|---|")
    parts.extend(
        _format_prior_window_summary(
            prior_plan_session_window, start=week_5_start, end=week_5_end
        )
    )
    parts.append("")
    parts.append(
        "This is a phase-trajectory-aware reshape: the 4-week mesocycle should "
        "reflect coherent progression toward the dominant phase's exit state. "
        "Continuity to week 5 is soft (the athlete invited the reshape). If "
        "week 5 contains a planned hard week, the mesocycle's last week may "
        "need to deload or otherwise prepare; if week 5 is uneventful, the "
        "mesocycle has freer rein."
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
            "of the prescription intact. Mesocycle-aggregate failures "
            "(volume_band_*, intensity_dist_*, acwr_*) may require shifting "
            "volume across multiple weeks; do the minimum needed to clear the "
            "constraint."
        )
        parts.append("")

    # === Output ===
    parts.append("=== Output ===")
    parts.append(
        "Emit one tool call to `record_refresh_sessions` with your list of "
        "0-56 PlanSession records covering the 28-day refresh window."
    )

    return "\n".join(parts)


__all__ = [
    "DEFAULT_MAX_TOKENS",
    "DEFAULT_EXTENDED_THINKING_BUDGET",
    "SYSTEM_PROMPT",
    "render_user_prompt",
]
