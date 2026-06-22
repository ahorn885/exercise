"""Layer 4 — Week-seam reviewer LLM call (D-77 Slice 3).

The **intra-phase** seam reviewer. Where `layer4/seam_review.py` blends two
adjacent *phases* (Pattern A), this blends two adjacent *weeks within the same
phase* — the per-week-block decomposition (D-77 Slices 1+2) generates each week
independently, so weeks within a phase can show abrupt week-to-week cliffs. This
reviewer judges whether the move from one week to the next tracks the
progression the periodization already fixed (a gentle loading ramp interrupted
by planned recovery weeks).

It REUSES the phase-seam machinery — the 4-verdict enum, the `record_seam_review`
tool, the invalid-combination coercion, the thinking-aware caller adapter, and
`SeamReviewCallResult` (all imported from `seam_review.py`) — but carries a NEW
prompt body with **intra-phase calibration** that inverts the phase-seam anchors:
a planned deload week's volume drop is CORRECT here, not a cliff. Per the
ratified design (`designs/Layer4_PerWeekDecomposition_D77_Design_v1.md` §5.2 +
`prompts/Layer4_WeekSeamReviewer_v1.md`) the anchor is **deviation from the
deterministic per-week multiplier grid** (`layer4/periodization.py`), not the
raw size of the week-over-week change.

The orchestrator in `plan_create.py` supplies the planned per-week multiplier +
planned-recovery flag (the same grid the synthesizer prompt and the volume-band
validator use) so the reviewer never has to guess whether a down-week was
intended.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date as _date_type
from typing import Any, Literal

from layer4.context import Layer2DPayload
from layer4.payload import PlanSession
from layer4.seam_review import (
    DEFAULT_EXTENDED_THINKING_BUDGET,
    DEFAULT_MAX_TOKENS,
    SeamReviewCallResult,
    SeamReviewerCaller,
    _coerce_verdict_combination,
    _default_seam_reviewer_caller,
    _format_active_injury_summary,
    build_record_seam_review_tool,
)
from layer4.errors import Layer4OutputError


SYSTEM_PROMPT = """You are AIDSTATION's Layer 4 week-seam reviewer.

You assess whether the transition between two ADJACENT WEEKS WITHIN THE SAME periodization phase — produced independently by separate synthesizer calls — progresses as one continuous block.

Within a phase, week-over-week should be PROGRESSIVE and CONTINUOUS: a gentle loading ramp interrupted by planned recovery (deload) weeks. This is NOT the deliberate step a phase-to-phase transition carries. Do NOT import phase-seam intuitions: a large volume drop is a CLIFF at a phase boundary but is the CORRECT shape of a planned recovery week here.

For each of the two weeks you are given the INTENDED weekly shape the plan periodization already fixed — a planned volume multiplier (relative to the phase's mean week) and whether the week is a PLANNED RECOVERY week — alongside the ACTUAL synthesized volume + intensity. Judge the actual week-over-week change against the PLANNED change, NEVER against the raw size of the jump.

You emit exactly one verdict via the `record_seam_review` tool. No free-form text.

VERDICTS:

- `approved` — the week-over-week move tracks the planned progression. A planned recovery week's volume dip is CORRECT. `seam_issues` empty; `proposed_patch_direction` null.

- `flagged_minor` — rough edges within normal week-to-week variance; the athlete would not notice and adaptation is not at risk. Record-only. `seam_issues` populated (1-4); `proposed_patch_direction` null.

- `flagged_major` — the progression is meaningfully broken relative to the plan. Examples: volume that HOLDS or CLIMBS through a planned recovery week (the deload didn't happen); a week that FLATTENS or DROPS where the grid plans a loading ramp, with no rationale; an intensity-zone inversion that breaks the week's intended distribution. Re-synthesis of one week-block is warranted. `seam_issues` populated; `proposed_patch_direction` is `re_prompt_prior` / `re_prompt_next` / `accept_with_observation`.

- `patched` — same severity as `flagged_major`, plus you are confident the re-synthesis direction you propose resolves it. `seam_issues` populated; `proposed_patch_direction` is `re_prompt_prior` or `re_prompt_next` (NEVER `accept_with_observation` — that is a schema violation).

CALIBRATION ANCHORS (use coaching judgment around these, not as thresholds):

- The GRID is the reference. "Continuous" ≈ the actual week-over-week volume ratio tracks the planned multiplier ratio (planned_next / planned_prior) within ~15 percentage points.
- PLANNED RECOVERY week: a volume drop of ~30-60% INTO the recovery week is expected → `approved`. Volume that holds or climbs INTO a planned recovery week → `flagged_major` (the recovery week didn't happen).
- Coming OUT of a recovery week, volume returns TOWARD baseline, not straight to peak; a rebound that overshoots the planned ramp → `flagged_minor` / `flagged_major` by magnitude.
- LOADING week (not recovery): actual volume should rise roughly with the planned ramp step (~8%/week). Flat or falling where the grid ramps, with no stated reason → `flagged_major`.
- Intensity: the week's actual Z1-Z2 / Z3 / Z4-Z5 split should track its intended distribution; unexplained drift >~8pp → `flagged_minor`; a zone inversion breaking the phase intent → `flagged_major`.
- Two consecutive hard weeks across the seam, neither a planned overreach → `flagged_minor` if there's a logical reason, `flagged_major` otherwise.
- Intensity restricted by an active injury (see active_injury_summary): treat reduced intensity as expected, NOT as a missing element.

PATCH DIRECTION (re-synthesizes ONE WEEK-BLOCK, not a phase):

- `re_prompt_prior` — the prior week is wrong (e.g. its ramp overshot; it ended too high).
- `re_prompt_next` — the next week is wrong (e.g. it failed to deload, or failed to ramp).
- `accept_with_observation` — the seam is meaningfully wrong AND re-synthesis won't reconcile it. Escalates to HITL via the orchestrator.

`seam_issues` WRITING RULES (load-bearing — violations push you outside your authority):

- Each entry is one tight sentence, ≤30 words.
- Constraint-level, not solution-level. Describe the constraint the synthesizer must satisfy relative to the planned grid, NOT specific sessions to add or remove. Examples:
  - Good: "Build week 4 is a planned recovery week (planned ×0.55) but holds 96% of week-3 volume; must drop toward the planned deload."
  - Bad: "Delete two sessions from Build week 4."
- Cite the planned-vs-actual observation that prompted the constraint.
- No platitudes. Either there is a constraint to state or there is no issue (use `approved`).
- Max 4 entries. Beyond 4, choose `flagged_major + accept_with_observation` and let the orchestrator escalate.

AUTHORITY BOUNDS — WHAT YOU CANNOT DO:

- Cannot rewrite individual sessions. Your output is constraints, not sessions.
- Cannot change phase boundaries, mode, or start_phase.
- Cannot evaluate weeks beyond the two adjacent to this seam.
- Cannot emit coaching flags or observations directly. The orchestrator computes those downstream from your verdict.
- Cannot request changes more than one week-hop from the seam.

ITERATION 2 BEHAVIOR:

If `seam_iteration == 2`, you are re-evaluating after one re-synthesis triggered by your iteration-1 verdict. `prior_seam_issues` contains the issues you raised on iteration 1. Judge: did the re-synthesis address them? If yes and the seam is now clean: `approved`. If yes but new minor edges appeared: `flagged_minor`. If the prior issues remain or new major issues appeared, emit a final verdict — the orchestrator will NOT re-prompt again (per-seam cap is 2); prefer `flagged_major + accept_with_observation` over `re_prompt_*` when you judge the seam unfixable.

VOICE: direct, evidence-grounded. No cheerleading. No hedging. Match a real endurance coach reviewing a colleague's plan.
"""


# ─── Per-week rollup (the ACTUAL side of the planned-vs-actual comparison) ────


@dataclass
class _WeekRollup:
    total_hours: float = 0.0
    z12_hours: float = 0.0
    z3_hours: float = 0.0
    z45_hours: float = 0.0
    session_count: int = 0


def compute_week_rollup(sessions: list[PlanSession]) -> _WeekRollup:
    """Aggregate one week's sessions into total hours + zone split. Mirrors the
    zone bucketing in `seam_review._format_weekly_rollup` but collapses the
    per-(week, discipline) table to a single per-week total — the unit the
    week-seam reviewer compares across the seam."""
    r = _WeekRollup()
    for s in sessions:
        r.total_hours += s.duration_min / 60.0
        r.session_count += 1
        if s.cardio_blocks:
            for cb in s.cardio_blocks:
                cb_h = cb.duration_min / 60.0
                if cb.intensity_zone in ("Z1", "Z2"):
                    r.z12_hours += cb_h
                elif cb.intensity_zone in ("Z3", "mixed"):
                    r.z3_hours += cb_h
                elif cb.intensity_zone in ("Z4", "Z5"):
                    r.z45_hours += cb_h
    return r


def _format_week_block(
    *,
    label: str,
    week_in_phase: int,
    planned_multiplier: float,
    is_recovery_week: bool,
    phase_volume_band: tuple[float, float],
    intended_intensity: dict[str, float],
    sessions: list[PlanSession],
) -> list[str]:
    """Render one side of the seam: the planned shape (multiplier + recovery
    flag + planned hours band) next to the actual synthesized volume + zones."""
    roll = compute_week_rollup(sessions)
    plan_low = phase_volume_band[0] * planned_multiplier
    plan_high = phase_volume_band[1] * planned_multiplier
    recovery_tag = "PLANNED RECOVERY (deload) week" if is_recovery_week else "loading week"
    out = [
        f"{label} — week {week_in_phase} in phase — {recovery_tag}",
        f"- Planned volume multiplier: ×{planned_multiplier:.2f} "
        f"(planned phase-total band this week: {plan_low:.1f}-{plan_high:.1f} hr)",
        f"- Actual synthesized volume: {roll.total_hours:.1f} hr "
        f"across {roll.session_count} session(s)",
        f"- Actual intensity (Z1-Z2 / Z3 / Z4-Z5 hr): "
        f"{roll.z12_hours:.1f} / {roll.z3_hours:.1f} / {roll.z45_hours:.1f}",
        f"- Intended intensity distribution (Z1-Z2 / Z3 / Z4-Z5): "
        f"{intended_intensity.get('Z1-Z2', 0) * 100:.0f}% / "
        f"{intended_intensity.get('Z3', 0) * 100:.0f}% / "
        f"{intended_intensity.get('Z4-Z5', 0) * 100:.0f}%",
    ]
    return out


def render_week_seam_prompt(
    *,
    phase_name: str,
    prior_week_in_phase: int,
    next_week_in_phase: int,
    prior_week_sessions: list[PlanSession],
    next_week_sessions: list[PlanSession],
    prior_planned_multiplier: float,
    next_planned_multiplier: float,
    prior_is_recovery: bool,
    next_is_recovery: bool,
    phase_volume_band: tuple[float, float],
    prior_intended_intensity: dict[str, float],
    next_intended_intensity: dict[str, float],
    layer2d_payload: Layer2DPayload | None,
    discipline_mix: list[str],
    mode: str,
    race_format: str,
    event_date: _date_type | None,
    seam_iteration: Literal[1, 2],
    prior_seam_issues: list[str],
) -> str:
    """Render the user prompt for one intra-phase week seam. Presents the
    planned per-week shape (the grid) beside the actual synthesized volume for
    both weeks, so the reviewer judges divergence-from-plan, not raw delta."""
    parts: list[str] = []
    parts.append(f"WEEK-SEAM REVIEW REQUEST — iteration {seam_iteration}")
    parts.append("")
    parts.append(
        f"Adjacent weeks within the {phase_name} phase: "
        f"week {prior_week_in_phase} → week {next_week_in_phase}"
    )
    parts.append(f"3B periodization mode: {mode}")
    parts.append(f"Discipline mix: {discipline_mix}")
    race_ctx = race_format
    if event_date is not None:
        race_ctx += f", event {event_date.isoformat()}"
    parts.append(f"Race context: {race_ctx}")
    parts.append("")

    # The planned week-over-week move — the reference the reviewer judges against.
    if prior_planned_multiplier > 0:
        planned_ratio = next_planned_multiplier / prior_planned_multiplier
        parts.append(
            f"PLANNED week-over-week volume change (the reference): "
            f"×{planned_ratio:.2f} "
            f"(week {prior_week_in_phase} planned ×{prior_planned_multiplier:.2f} → "
            f"week {next_week_in_phase} planned ×{next_planned_multiplier:.2f}). "
            f"Judge the ACTUAL change against THIS, not against the raw drop/rise."
        )
        parts.append("")

    parts.append("ACTIVE INJURY CONSTRAINTS:")
    parts.extend(_format_active_injury_summary(layer2d_payload))
    parts.append("")

    parts.extend(
        _format_week_block(
            label="PRIOR WEEK",
            week_in_phase=prior_week_in_phase,
            planned_multiplier=prior_planned_multiplier,
            is_recovery_week=prior_is_recovery,
            phase_volume_band=phase_volume_band,
            intended_intensity=prior_intended_intensity,
            sessions=prior_week_sessions,
        )
    )
    parts.append("")
    parts.extend(
        _format_week_block(
            label="NEXT WEEK",
            week_in_phase=next_week_in_phase,
            planned_multiplier=next_planned_multiplier,
            is_recovery_week=next_is_recovery,
            phase_volume_band=phase_volume_band,
            intended_intensity=next_intended_intensity,
            sessions=next_week_sessions,
        )
    )
    parts.append("")

    if prior_seam_issues:
        parts.append(
            "ITERATION 1 ISSUES (these triggered the re-synthesis you are now reviewing):"
        )
        for issue in prior_seam_issues:
            parts.append(f"- {issue}")
        parts.append("")

    parts.append("Review this week seam. Call `record_seam_review` with your verdict.")
    return "\n".join(parts)


# ─── Single week-seam-review call ────────────────────────────────────────────


def review_week_seam(
    *,
    phase_name: str,
    prior_week_in_phase: int,
    next_week_in_phase: int,
    prior_week_sessions: list[PlanSession],
    next_week_sessions: list[PlanSession],
    prior_planned_multiplier: float,
    next_planned_multiplier: float,
    prior_is_recovery: bool,
    next_is_recovery: bool,
    phase_volume_band: tuple[float, float],
    prior_intended_intensity: dict[str, float],
    next_intended_intensity: dict[str, float],
    layer2d_payload: Layer2DPayload | None,
    discipline_mix: list[str],
    mode: str,
    race_format: str,
    event_date: _date_type | None,
    seam_iteration: Literal[1, 2],
    prior_seam_issues: list[str],
    model: str = "claude-sonnet-4-6",
    temperature: float = 0.15,
    max_tokens: int = DEFAULT_MAX_TOKENS,
    extended_thinking_budget: int = DEFAULT_EXTENDED_THINKING_BUDGET,
    caller: SeamReviewerCaller | None = None,
) -> SeamReviewCallResult:
    """Issue one week-seam-review LLM call. Returns the same
    `SeamReviewCallResult` shape the phase reviewer returns, so the orchestrator
    reuses `compose_seam_review_row` / the verdict-to-action table unchanged.

    Invalid verdict/direction combinations are COERCED (not raised) via the
    shared `_coerce_verdict_combination` — a seam review is advisory and must
    never discard valid synthesis (the pv=55 lesson, inherited). Only an
    unparseable `reviewer_verdict` enum raises `schema_violation`."""
    eff_caller = caller or _default_seam_reviewer_caller
    tool_schema = build_record_seam_review_tool()
    user_prompt = render_week_seam_prompt(
        phase_name=phase_name,
        prior_week_in_phase=prior_week_in_phase,
        next_week_in_phase=next_week_in_phase,
        prior_week_sessions=prior_week_sessions,
        next_week_sessions=next_week_sessions,
        prior_planned_multiplier=prior_planned_multiplier,
        next_planned_multiplier=next_planned_multiplier,
        prior_is_recovery=prior_is_recovery,
        next_is_recovery=next_is_recovery,
        phase_volume_band=phase_volume_band,
        prior_intended_intensity=prior_intended_intensity,
        next_intended_intensity=next_intended_intensity,
        layer2d_payload=layer2d_payload,
        discipline_mix=discipline_mix,
        mode=mode,
        race_format=race_format,
        event_date=event_date,
        seam_iteration=seam_iteration,
        prior_seam_issues=prior_seam_issues,
    )
    llm_out = eff_caller(
        SYSTEM_PROMPT,
        user_prompt,
        tool_schema,
        model,
        temperature,
        max_tokens,
        extended_thinking_budget,
    )

    verdict = llm_out.tool_args.get("reviewer_verdict")
    seam_issues = list(llm_out.tool_args.get("seam_issues", []) or [])
    direction = llm_out.tool_args.get("proposed_patch_direction")

    if verdict not in ("approved", "flagged_minor", "flagged_major", "patched"):
        raise Layer4OutputError(
            "schema_violation",
            detail=f"reviewer_verdict={verdict!r} not in allowed enum",
        )

    verdict, direction = _coerce_verdict_combination(verdict, direction, seam_issues)

    return SeamReviewCallResult(
        verdict=verdict,  # type: ignore[arg-type]
        seam_issues=seam_issues,
        proposed_patch_direction=direction,  # type: ignore[arg-type]
        input_tokens=llm_out.input_tokens,
        output_tokens=llm_out.output_tokens,
        latency_ms=llm_out.latency_ms,
    )


__all__ = [
    "SYSTEM_PROMPT",
    "compute_week_rollup",
    "render_week_seam_prompt",
    "review_week_seam",
]
