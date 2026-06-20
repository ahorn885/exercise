"""Layer 4 — T1 (2-day refresh) tier-specific synthesizer plumbing.

Per `Layer4_RefreshT1_v1.md` (prompt body §5 system prompt + §6 user prompt
template + §7 sampling configuration). The driver entrypoint in
`layer4/plan_refresh.py` dispatches here on `tier='T1'` and consumes:

- `SYSTEM_PROMPT` — the inline system prompt matching the prompt body §5.
- `DEFAULT_MAX_TOKENS` / `DEFAULT_EXTENDED_THINKING_BUDGET` — T1 sampling
  defaults per §7 (max_tokens=2000 for up to 4 sessions; thinking ~3000).
- `render_user_prompt(...)` — inline Python rendering of the §6 user prompt
  template (Mustache replaced by f-string + conditional blocks).
"""

from __future__ import annotations

from datetime import date as _date_type
from typing import Any

from layer4.context import (
    Layer2Bundle,
    Layer3APayload,
    Layer3BPayload,
    ParsedIntent,
    TrainingSubstitutionPayload,
)
from layer4.payload import PlanSession, RuleFailure
from layer4.injury_render import format_active_injuries
from layer4.per_phase import (
    _format_event_window_overlay,
    _format_session_feasibility,
    _format_training_substitution_per_phase,
)
from layer4.strength_guidance import STRENGTH_PROGRAMMING_GUIDANCE


DEFAULT_MAX_TOKENS = 2000
DEFAULT_EXTENDED_THINKING_BUDGET = 3000


SYSTEM_PROMPT = (
    """You are AIDSTATION's Layer 4 plan-refresh T1 synthesizer.

You are called when an athlete clicks "Refresh next 2 days" on their training plan. The athlete has typed an optional free-text note explaining why they want the refresh. Your job is to produce 0-4 PlanSession records covering the next 2 calendar days that:

1. Honor the athlete's stated intent (their words are the primary signal — see policy below).
2. Hand off cleanly into the sessions already planned for days 3-9 after the refresh window.
3. Stay inside the periodization phase's intent (volume band + intensity distribution) unless the athlete's intent justifies stepping outside.
4. Never violate hard constraints — active injuries, equipment availability, schedule availability.

VOICE: Direct, focused, evidence-grounded. No platitudes. No cheerleading. No hype. Match a real endurance coach talking to a serious athlete. Short sentences. Plain English. No emoji. Never surface internal identifiers in athlete-facing text — no discipline ids (e.g. "D-012") and no skill/toggle slugs (e.g. "climbing_roped"); use the plain discipline name.

PROCESS:
- Read the athlete's `raw_text` and `parsed_intent` first. These drive WHY you're modulating.
- Read the recent training context (last 7 days summary + 3A state) to ground the modulation in objective signal where possible.
- Read the refresh-window-after sessions (the sessions planned for days 3-9) — these are the continuity constraint. Your output must hand off cleanly to them.
- Decide the shape of the refresh window (1 session per day / 2 per day / rest / mix). Honor the athlete's per-day availability per the orchestrator's locale assignment per day.
- For each session, prescribe sport / duration / intensity + the structured content (cardio_blocks for cardio; strength_exercises for strength).

INTENSITY-MODULATION POLICY:
- The athlete's words and the parsed signals dominate the prescription DIRECTION.
- 3A objective signals (ACWR, recent load, last-hard-session) ground the MAGNITUDE but never override the direction.
- Hard safety constraints (active injuries, equipment availability, schedule availability) are never overridden.
- When sickness_signal='active': prescribe rest-shape sessions only (zero hard work) regardless of other signals.
- Emit `intensity_modulated` on every session where the prescription deviates from what the periodization phase + adjacent sessions would naturally call for, due to athlete intent or a 3A signal. Briefly explain the modulation in `session_notes` (1-2 short sentences).

OUTPUT DISCIPLINE:
- Emit exactly one tool call to `record_refresh_sessions`. The tool's `sessions` argument is your list of 0-4 PlanSession records.
- Every cardio block requires an explicit `intensity_zone` (Z1-Z5 or mixed) and an `intensity_target` shape matching the sport: HRTarget for endurance, PowerTarget for bike/run/skimo/row, PaceTarget for running/paddle/ski, SwimPaceTarget for swim, RPETarget as universal fallback, VerticalRateTarget for skimo/hiking, StrokeRateTarget for swim/paddle/row, CadenceTarget for cycling, ClimbingGradeTarget for outdoor rock. Pick the shape that best matches the sport.
- For interval_set cardio_blocks: emit `repetitions`, `rest_between_min`, `rest_intensity_zone`. For other block_kinds: leave those three fields null.
- Strength exercises reference Layer 0B exercise IDs; populate `exercise_name` with the human-readable name; `reps_per_set` accepts an integer or a string ("8-12", "AMRAP").
- All athlete-facing text fields are bounded by `maxLength` in the schema — be concise.
- Do not emit prose outside the tool call.

# Strength programming

"""
    + STRENGTH_PROGRAMMING_GUIDANCE
    + "\n"
)


def _format_active_injuries(layer2_bundle: Layer2Bundle) -> list[str]:
    """Render the active-injuries block (hard constraints) from 2D
    excluded + accommodated lists.

    Delegates to the shared `layer4.injury_render` renderer (same one the
    create path uses) so the two prompts can't drift; that renderer carries
    each modality's params + rationale (#555), not just the type name.
    """
    return format_active_injuries(
        layer2_bundle.d,
        none_payload_line=(
            "(2D payload not provided this refresh; no injury data available.)"
        ),
        none_on_file_line="(No active injuries.)",
    )


def _format_prior_window_summary(
    sessions: list[PlanSession],
    *,
    start: _date_type,
    end: _date_type,
) -> list[str]:
    """Render a summary-table view of sessions in [start, end] for the
    "Recent training" block (D4 — prior-window-as-summary)."""
    in_window = [s for s in sessions if start <= s.date <= end]
    if not in_window:
        return ["| (no sessions in window) | | | | | |"]
    lines = []
    for s in sorted(in_window, key=lambda x: (x.date, x.session_index_in_day)):
        sport = s.discipline_name or s.discipline_id or s.kind
        lines.append(
            f"| {s.date.isoformat()} | {sport} | {s.kind} | {s.duration_min}min | "
            f"{s.intensity_summary} | (planned) |"
        )
    return lines


def _format_window_verbatim(
    sessions: list[PlanSession],
    *,
    start: _date_type,
    end: _date_type,
    include_flags: bool = False,
) -> list[str]:
    """Render the verbatim view of sessions in [start, end] for the
    refresh-window-during-prior or refresh-window-after blocks."""
    in_window = [s for s in sessions if start <= s.date <= end]
    if not in_window:
        return ["(no sessions in window)"]
    lines = []
    for s in sorted(in_window, key=lambda x: (x.date, x.session_index_in_day)):
        sport = s.discipline_name or s.discipline_id or s.kind
        flags_str = ""
        if include_flags and s.coaching_flags:
            flags_str = " " + " ".join(f"[{f}]" for f in s.coaching_flags)
        lines.append(
            f"- {s.date.isoformat()} ({sport} / {s.kind} / {s.duration_min}min / "
            f"{s.intensity_summary}): {s.coaching_intent}{flags_str}"
        )
    return lines


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
    """Render the §6 user prompt for T1. Inline Python rendering replaces
    Mustache from the prompt body MD."""
    from datetime import timedelta

    parts: list[str] = []

    # === Refresh request ===
    parts.append("=== Refresh request ===")
    parts.append("Tier: T1 (2-day rolling window)")
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
    coach_notes = layer1_payload.get("coach_notes")
    if coach_notes:
        parts.append(f"Coach notes: {coach_notes}")
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

    # === Periodization shape ===
    parts.append("=== Periodization shape (3B — re-run as part of refresh cascade) ===")
    shape = layer3b_payload.periodization_shape
    parts.append(f"Mode: {layer3b_payload.mode}")
    parts.append(f"Start phase: {shape.start_phase}")
    parts.append(f"Periodization mode: {shape.mode}")
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

    # === Recent training (last 7 days summary) ===
    prior_start = refresh_scope_start - timedelta(days=7)
    prior_end = refresh_scope_start - timedelta(days=1)
    parts.append("=== Recent training (last 7 days — summary) ===")
    parts.append("| Date | Sport | Kind | Duration | Intensity | Completed |")
    parts.append("|---|---|---|---|---|---|")
    parts.extend(
        _format_prior_window_summary(
            prior_plan_session_window, start=prior_start, end=prior_end
        )
    )
    parts.append("")

    # === Sessions being replaced ===
    parts.append("=== Sessions previously planned for the refresh window (being replaced) ===")
    parts.extend(
        _format_window_verbatim(
            prior_plan_session_window,
            start=refresh_scope_start,
            end=refresh_scope_end,
        )
    )
    parts.append("")

    # === Sessions planned for days 3-9 (continuity constraint) ===
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
        "Your T1 output must hand off cleanly into these. If any of the planned "
        "post-window sessions is a key workout (long ride, race-pace day, "
        "weak-link strength), the refresh must not compromise it."
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
            "of the prescription intact. Do not regenerate from scratch."
        )
        parts.append("")

    # === Output ===
    parts.append("=== Output ===")
    parts.append(
        "Emit one tool call to `record_refresh_sessions` with your list of 0-4 "
        "PlanSession records."
    )

    return "\n".join(parts)


__all__ = [
    "DEFAULT_MAX_TOKENS",
    "DEFAULT_EXTENDED_THINKING_BUDGET",
    "SYSTEM_PROMPT",
    "render_user_prompt",
]
