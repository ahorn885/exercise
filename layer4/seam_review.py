"""Layer 4 — Seam-reviewer LLM call for Pattern A orchestration.

Implements `Layer4_Spec.md` §5.2 step 4 + §6.2 (β propose-patch authority) +
the `Layer4_SeamReviewer_v2.md` prompt body (v1 → v2 surgical amendment for
the active_injury_summary source-pointer update — 2D excluded/accommodated
exercises replace the v1 prompt's 3A `active_injuries` reference per the
PR-C-followon ripple).

The seam reviewer runs between adjacent-phase outputs in Pattern A. It
emits a `SeamReview` row (§7.7) with one of four verdicts and a
proposed-patch direction. The Pattern A orchestrator in `plan_create.py`
applies the §6.2 verdict-to-action table:

- `approved` / `flagged_minor`: record-only.
- `flagged_major` / `patched` with `re_prompt_*`: re-synthesize the targeted
  phase if its retry budget is not exhausted; otherwise emit
  `seam_unresolved` observation.
- `flagged_major` with `accept_with_observation`: escalate to HITL via a
  `notable_observation`.

Per-seam iteration cap is 2 (initial review + at most one re-review after
re-synthesis). After cap exhaustion, seam_unresolved.
"""

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass, field
from datetime import date as _date_type, timedelta
from typing import Any, Callable, Literal

from llm_invocation import ThinkingToolCallError, invoke_tool_call
from layer4.context import Layer2APayload, Layer2DPayload
from layer4.errors import Layer4OutputError
from layer4.payload import PhaseSpec, PlanSession, SeamReview


DEFAULT_MAX_TOKENS = 1500
"""Per `Layer4_SeamReviewer_v1.md` §7."""

DEFAULT_EXTENDED_THINKING_BUDGET = 2000
"""Per `Layer4_SeamReviewer_v1.md` D2."""


SYSTEM_PROMPT = """You are AIDSTATION's Layer 4 seam reviewer.

You assess whether the transition between two adjacent periodization phases — produced independently by separate synthesizer calls — fits cleanly as a single coherent training progression.

You read two phases' session outputs plus the boundary state the synthesizer was supposed to land on (the prior phase's intended exit volume and intensity distribution, and the next phase's intended entry). You emit exactly one verdict via the `record_seam_review` tool. No free-form text.

VERDICTS:

- `approved` — the transition is clean. Volume continuity, intensity progression, and race-specificity all track. No issues. `seam_issues` empty; `proposed_patch_direction` null.

- `flagged_minor` — the transition has rough edges within typical periodization variance. The athlete would not notice; adaptation outcomes are not at risk. Record-only; no re-synthesis. `seam_issues` populated (1-4 entries) describing the rough edges; `proposed_patch_direction` null.

- `flagged_major` — the transition is meaningfully wrong. Examples: a volume cliff with no taper rationale; an intensity-zone shift that breaks the phase intent; race-specificity missing from Peak entry where the event format requires it; a deload week where one shouldn't be. Re-synthesis of one side of the seam is warranted. `seam_issues` populated; `proposed_patch_direction` is one of `re_prompt_prior` / `re_prompt_next` / `accept_with_observation`.

- `patched` — same severity as `flagged_major`, plus you are confident the re-synthesis direction you propose will resolve the issue. `seam_issues` populated; `proposed_patch_direction` is `re_prompt_prior` or `re_prompt_next` (NEVER `accept_with_observation` — that is a schema violation).

CALIBRATION ANCHORS (use coaching judgment around these, not as thresholds):

- "Within typical periodization variance" ≈ volume drift ≤10% week-over-week without rationale; zone-distribution drift ≤8pp from intended; race-specificity present where expected.
- A week-over-week volume drop >25% with no taper rationale: `flagged_major`.
- A zone shift breaking the phase intent's stated distribution (e.g., Peak starting Z3-dominant when intended Z2-dominant): `flagged_major`.
- A missing race-pace introduction in the first half of Peak when the event format requires race-pace specificity (marathon, IM-class, ultras): `flagged_major`.
- Two consecutive hard sessions across the boundary (last session of prior phase + first session of next phase both `intensity_summary == 'hard'`): `flagged_minor` if there's a logical reason (race rehearsal, overreach week), `flagged_major` otherwise.
- Intensity restricted by an active injury (see active_injury_summary): treat reduced intensity as expected, NOT as a missing element.

PATCH DIRECTION:

- `re_prompt_prior` — the problem is the prior phase's exit (e.g., prior phase ended too high in volume; should taper down).
- `re_prompt_next` — the problem is the next phase's entry (e.g., next phase opens too aggressive; should ramp in).
- `accept_with_observation` — the seam is meaningfully wrong AND re-synthesis won't help (e.g., both sides are constrained by independent factors that re-prompting can't reconcile). Escalates to HITL gate via the orchestrator.

`seam_issues` WRITING RULES (load-bearing — violations push you outside your authority):

- Each entry is one tight sentence, ≤30 words.
- Constraint-level, not solution-level. Describe the constraint the synthesizer must satisfy, NOT specific sessions to add or remove. Examples:
  - Good: "Peak week 1 must hold ≥60% Z2 with at most one Z3 introduction session; current entry is Z3-dominant."
  - Bad: "Replace Peak week 1 day 2 with a Z2 long ride."
- Cite the boundary observation that prompted the constraint.
- No platitudes. Either there is a constraint to state or there is no issue (use `approved`).
- Max 4 entries. Beyond 4, choose `flagged_major + accept_with_observation` and let the orchestrator escalate.

AUTHORITY BOUNDS — WHAT YOU CANNOT DO:

- Cannot rewrite individual sessions. Your output is constraints, not sessions.
- Cannot change phase boundaries, mode, or start_phase.
- Cannot evaluate phases beyond the two adjacent to this seam.
- Cannot emit coaching flags or observations directly. The orchestrator computes those downstream from your verdict.
- Cannot request changes to phases more than one hop from the seam.

ITERATION 2 BEHAVIOR:

If `seam_iteration == 2`, you are re-evaluating after one re-synthesis triggered by your iteration-1 verdict. The `prior_seam_issues` field contains the issues you raised on iteration 1. Judge:

- Did the re-synthesis address the prior issues? If yes and the seam is now clean: `approved`. If yes but new minor edges appeared: `flagged_minor`.
- If the prior issues remain or new major issues appeared: emit a final verdict. The orchestrator will NOT re-prompt again (per-seam cap is 2). On iteration 2, prefer `flagged_major + accept_with_observation` over `flagged_major + re_prompt_*` when you judge the seam is unfixable.

VOICE: direct, evidence-grounded. No cheerleading. No hedging. Match a real endurance coach reviewing a colleague's plan.
"""


# ─── Tool schema (record_seam_review) ────────────────────────────────────────


def build_record_seam_review_tool() -> dict[str, Any]:
    """Anthropic tool definition for `record_seam_review` per
    `Layer4_SeamReviewer_v2.md` §4. Mirrors the §7.7 SeamReview shape minus
    the orchestrator-filled metadata (seam_index, prior_phase_name,
    next_phase_name, reviewer_model, *_tokens, *_latency_ms,
    triggered_resynthesis, re_prompted_phase_name)."""
    return {
        "name": "record_seam_review",
        "description": (
            "Record your seam review for this adjacent-phase pair. Call this "
            "tool exactly once. Do not emit free-form text outside the tool call."
        ),
        "input_schema": {
            "type": "object",
            "additionalProperties": False,
            "required": ["reviewer_verdict", "seam_issues", "proposed_patch_direction"],
            "properties": {
                "reviewer_verdict": {
                    "type": "string",
                    "enum": [
                        "approved",
                        "flagged_minor",
                        "flagged_major",
                        "patched",
                    ],
                },
                "seam_issues": {
                    "type": "array",
                    "items": {"type": "string", "minLength": 1, "maxLength": 240},
                    "maxItems": 4,
                },
                "proposed_patch_direction": {
                    "type": ["string", "null"],
                    "enum": [
                        "re_prompt_prior",
                        "re_prompt_next",
                        "accept_with_observation",
                        None,
                    ],
                },
            },
        },
    }


# ─── Prompt rendering (Layer4_SeamReviewer_v2.md §6) ─────────────────────────


def _format_active_injury_summary(layer2d: Layer2DPayload | None) -> list[str]:
    """Per v2 amendment: render 2D excluded + accommodated exercises as a
    one-line-per-injury summary. Replaces the v1 prompt's reference to 3A
    `active_injuries` which never existed in 3A's typed contract."""
    if layer2d is None:
        return ["- (Layer 2D payload not supplied.)"]
    out: list[str] = []
    if not layer2d.excluded_exercises and not layer2d.accommodated_exercises:
        out.append("- None on file.")
        return out
    if layer2d.excluded_exercises:
        exc_ids = [er.exercise_id for er in layer2d.excluded_exercises]
        out.append(
            f"- {len(exc_ids)} excluded exercise(s): {', '.join(exc_ids[:5])}"
            + ("..." if len(exc_ids) > 5 else "")
        )
    if layer2d.accommodated_exercises:
        acc_count = len(layer2d.accommodated_exercises)
        out.append(
            f"- {acc_count} accommodated exercise(s) (per 2D modality framework)"
        )
    return out


def _intended_volume_band_from_2a(
    layer2a: Layer2APayload | None, phase_name: str
) -> str:
    """Render the per-discipline volume band table compactly."""
    if layer2a is None:
        return "(2A payload not supplied)"
    rows: list[str] = []
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
        rows.append(f"{d.discipline_id}: {low:.1f}-{high:.1f} hr/wk")
    return "; ".join(rows) if rows else "(no included disciplines)"


def _format_weekly_rollup(sessions: list[PlanSession]) -> list[str]:
    """Compute weekly rollup from a phase's accepted sessions. Per-week
    discipline-bucketed total hours + zone breakdown + flag list."""
    if not sessions:
        return ["- (No sessions in this phase.)"]

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
        b = buckets.setdefault(key, _WeekBucket())
        b.total_hours += s.duration_min / 60.0
        b.session_count += 1
        for f in s.coaching_flags:
            if f not in b.flags:
                b.flags.append(f)
        if s.cardio_blocks:
            for cb in s.cardio_blocks:
                cb_h = cb.duration_min / 60.0
                if cb.intensity_zone in ("Z1", "Z2"):
                    b.z12_hours += cb_h
                elif cb.intensity_zone in ("Z3", "mixed"):
                    b.z3_hours += cb_h
                elif cb.intensity_zone in ("Z4", "Z5"):
                    b.z45_hours += cb_h

    out: list[str] = ["| Wk | Discipline | Total hrs | Z1-Z2 | Z3 | Z4-Z5 | Sessions | Flags |"]
    out.append("|---|---|---|---|---|---|---|---|")
    for (wk, disc), b in sorted(buckets.items()):
        flags_str = ", ".join(b.flags) if b.flags else "—"
        out.append(
            f"| {wk} | {disc} | {b.total_hours:.1f} | {b.z12_hours:.1f} | "
            f"{b.z3_hours:.1f} | {b.z45_hours:.1f} | {b.session_count} | {flags_str} |"
        )
    return out


def _format_week_sessions(sessions: list[PlanSession]) -> list[str]:
    """Render a list of sessions verbatim for the seam-side."""
    if not sessions:
        return ["- (No sessions.)"]
    sessions_sorted = sorted(sessions, key=lambda s: (s.date, s.session_index_in_day))
    out: list[str] = ["| Date | Idx | Kind | Sport | Duration | Intensity | Flags |"]
    out.append("|---|---|---|---|---|---|---|")
    for s in sessions_sorted:
        flags_str = ", ".join(s.coaching_flags) if s.coaching_flags else "—"
        out.append(
            f"| {s.date.isoformat()} | {s.session_index_in_day} | {s.kind} | "
            f"{s.discipline_id or '—'} | {s.duration_min} min | "
            f"{s.intensity_summary} | {flags_str} |"
        )
    return out


def render_seam_review_prompt(
    *,
    seam_index: int,
    prior_phase_spec: PhaseSpec,
    next_phase_spec: PhaseSpec,
    prior_phase_sessions: list[PlanSession],
    next_phase_sessions: list[PlanSession],
    layer2a_payload: Layer2APayload | None,
    layer2d_payload: Layer2DPayload | None,
    discipline_mix: list[str],
    mode: str,
    start_phase: str,
    race_format: str,
    event_date: _date_type | None,
    seam_iteration: Literal[1, 2],
    prior_seam_issues: list[str],
) -> str:
    """Render the §6 user prompt for one seam review. Inline Python rendering
    replaces Mustache."""
    parts: list[str] = []
    seam_date = next_phase_spec.start_date
    days_to_event = (
        (event_date - seam_date).days if event_date is not None else None
    )

    parts.append(f"SEAM REVIEW REQUEST — iteration {seam_iteration}")
    parts.append("")
    parts.append(
        f"Adjacent phases: {prior_phase_spec.phase_name} → "
        f"{next_phase_spec.phase_name} (seam at {seam_date.isoformat()})"
    )
    parts.append(f"3B periodization mode: {mode} (start_phase: {start_phase})")
    parts.append(f"Discipline mix: {discipline_mix}")
    race_ctx = race_format
    if event_date is not None:
        race_ctx += f", event {event_date.isoformat()} ({days_to_event} days from seam)"
    parts.append(f"Race context: {race_ctx}")
    parts.append("")

    parts.append("ACTIVE INJURY CONSTRAINTS:")
    parts.extend(_format_active_injury_summary(layer2d_payload))
    parts.append("")

    parts.append("INTENDED BOUNDARY STATE:")
    parts.append("")
    parts.append(
        f"{prior_phase_spec.phase_name} intended exit (per 2A phase_load_bands):"
    )
    parts.append(
        f"- Volume per discipline (hr/wk range): "
        f"{_intended_volume_band_from_2a(layer2a_payload, prior_phase_spec.phase_name)}"
    )
    pid = prior_phase_spec.intended_intensity_distribution
    parts.append(
        f"- Intensity distribution (Z1-Z2 / Z3 / Z4-Z5): "
        f"{pid.get('Z1-Z2', 0) * 100:.0f}% / "
        f"{pid.get('Z3', 0) * 100:.0f}% / {pid.get('Z4-Z5', 0) * 100:.0f}%"
    )
    parts.append("")
    parts.append(
        f"{next_phase_spec.phase_name} intended entry (per 2A phase_load_bands):"
    )
    parts.append(
        f"- Volume per discipline (hr/wk range): "
        f"{_intended_volume_band_from_2a(layer2a_payload, next_phase_spec.phase_name)}"
    )
    nid = next_phase_spec.intended_intensity_distribution
    parts.append(
        f"- Intensity distribution (Z1-Z2 / Z3 / Z4-Z5): "
        f"{nid.get('Z1-Z2', 0) * 100:.0f}% / "
        f"{nid.get('Z3', 0) * 100:.0f}% / {nid.get('Z4-Z5', 0) * 100:.0f}%"
    )
    parts.append("")

    parts.append(
        f"PRIOR PHASE — {prior_phase_spec.phase_name} ({prior_phase_spec.weeks} weeks, "
        f"{prior_phase_spec.start_date.isoformat()} through "
        f"{prior_phase_spec.end_date.isoformat()})"
    )
    parts.append("")
    parts.append("Weekly rollup:")
    parts.extend(_format_weekly_rollup(prior_phase_sessions))
    parts.append("")
    last_week_start = prior_phase_spec.end_date - timedelta(days=6)
    last_week_sessions = [
        s for s in prior_phase_sessions if s.date >= last_week_start
    ]
    parts.append("Last week sessions (full detail — this is the seam):")
    parts.extend(_format_week_sessions(last_week_sessions))
    parts.append("")

    parts.append(
        f"NEXT PHASE — {next_phase_spec.phase_name} ({next_phase_spec.weeks} weeks, "
        f"{next_phase_spec.start_date.isoformat()} through "
        f"{next_phase_spec.end_date.isoformat()})"
    )
    parts.append("")
    parts.append("Weekly rollup:")
    parts.extend(_format_weekly_rollup(next_phase_sessions))
    parts.append("")
    first_week_end = next_phase_spec.start_date + timedelta(days=6)
    first_week_sessions = [
        s for s in next_phase_sessions if s.date <= first_week_end
    ]
    parts.append("First week sessions (full detail — this is the seam):")
    parts.extend(_format_week_sessions(first_week_sessions))
    parts.append("")

    if prior_seam_issues:
        parts.append(
            "ITERATION 1 ISSUES (these triggered the re-synthesis you are now reviewing):"
        )
        for issue in prior_seam_issues:
            parts.append(f"- {issue}")
        parts.append("")

    parts.append("Review this seam. Call `record_seam_review` with your verdict.")

    return "\n".join(parts)


# ─── Anthropic SDK adapter ───────────────────────────────────────────────────


@dataclass
class _SeamReviewerOutput:
    tool_args: dict[str, Any]
    input_tokens: int
    output_tokens: int
    latency_ms: int


SeamReviewerCaller = Callable[
    [str, str, dict[str, Any], str, float, int, int],
    _SeamReviewerOutput,
]
"""Adapter signature: `(system_prompt, user_prompt, tool_schema, model,
temperature, max_tokens, extended_thinking_budget) -> _SeamReviewerOutput`."""


def _default_seam_reviewer_caller(
    system_prompt: str,
    user_prompt: str,
    tool_schema: dict[str, Any],
    model: str,
    temperature: float,
    max_tokens: int,
    extended_thinking_budget: int,
) -> _SeamReviewerOutput:
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

    return _SeamReviewerOutput(
        tool_args=result.tool_args,
        input_tokens=result.input_tokens,
        output_tokens=result.output_tokens,
        latency_ms=result.latency_ms,
    )


# ─── Validation of invalid verdict-direction combinations per §4 / §6.2 ──────


def _validate_verdict_combination(
    verdict: str,
    direction: str | None,
    seam_issues: list[str],
) -> None:
    """Raise `Layer4OutputError('seam_reviewer_invalid_verdict_combination')`
    on the invalid combinations from `Layer4_SeamReviewer_v2.md` §4 / spec
    §6.2 verdict table. Caller treats as schema-violation per §5.5 (one
    schema retry; bail on second)."""
    code = "seam_reviewer_invalid_verdict_combination"
    if verdict == "patched" and direction == "accept_with_observation":
        raise Layer4OutputError(
            code,
            detail="`patched` verdict implies a re-prompt direction; cannot be `accept_with_observation`",
        )
    if verdict == "flagged_major" and direction is None:
        raise Layer4OutputError(
            code,
            detail="`flagged_major` requires a non-null `proposed_patch_direction`",
        )
    if verdict == "patched" and direction is None:
        raise Layer4OutputError(
            code,
            detail="`patched` requires a non-null `proposed_patch_direction`",
        )
    if verdict == "approved" and seam_issues:
        raise Layer4OutputError(
            code,
            detail="`approved` requires empty `seam_issues`",
        )
    if verdict == "approved" and direction is not None:
        raise Layer4OutputError(
            code,
            detail="`approved` requires null `proposed_patch_direction`",
        )
    if verdict == "flagged_minor" and direction is not None:
        raise Layer4OutputError(
            code,
            detail="`flagged_minor` is record-only; `proposed_patch_direction` must be null",
        )


# ─── Single seam-review call ─────────────────────────────────────────────────


@dataclass
class SeamReviewCallResult:
    """Output of `review_seam()` — the parsed SeamReview row + token /
    latency accounting for orchestrator aggregation. `triggered_resynthesis`
    is set by the orchestrator after applying §6.2 authority semantics
    (here we surface verdict + direction; the orchestrator decides whether
    re-synthesis actually fires given the per-phase retry budget)."""

    verdict: Literal["approved", "flagged_minor", "flagged_major", "patched"]
    seam_issues: list[str]
    proposed_patch_direction: (
        Literal["re_prompt_prior", "re_prompt_next", "accept_with_observation"] | None
    )
    input_tokens: int
    output_tokens: int
    latency_ms: int


def review_seam(
    *,
    seam_index: int,
    prior_phase_spec: PhaseSpec,
    next_phase_spec: PhaseSpec,
    prior_phase_sessions: list[PlanSession],
    next_phase_sessions: list[PlanSession],
    layer2a_payload: Layer2APayload | None,
    layer2d_payload: Layer2DPayload | None,
    discipline_mix: list[str],
    mode: str,
    start_phase: str,
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
    """Issue one seam-review LLM call and return the parsed verdict +
    direction + seam_issues + token/latency accounting. The orchestrator in
    `plan_create.py` calls this; applies §6.2 authority semantics (decides
    whether to re-synthesize); records SeamReview rows.

    Schema-violation special case per §5.5 + §6.2: invalid verdict/direction
    combinations raise `Layer4OutputError('seam_reviewer_invalid_verdict_combination')`.
    Orchestrator treats as schema-violation (one schema retry; bail on second)."""
    eff_caller = caller or _default_seam_reviewer_caller
    tool_schema = build_record_seam_review_tool()
    user_prompt = render_seam_review_prompt(
        seam_index=seam_index,
        prior_phase_spec=prior_phase_spec,
        next_phase_spec=next_phase_spec,
        prior_phase_sessions=prior_phase_sessions,
        next_phase_sessions=next_phase_sessions,
        layer2a_payload=layer2a_payload,
        layer2d_payload=layer2d_payload,
        discipline_mix=discipline_mix,
        mode=mode,
        start_phase=start_phase,
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

    _validate_verdict_combination(verdict, direction, seam_issues)

    return SeamReviewCallResult(
        verdict=verdict,  # type: ignore[arg-type]
        seam_issues=seam_issues,
        proposed_patch_direction=direction,  # type: ignore[arg-type]
        input_tokens=llm_out.input_tokens,
        output_tokens=llm_out.output_tokens,
        latency_ms=llm_out.latency_ms,
    )


# ─── SeamReview row composition (after orchestrator decides re-synthesis) ────


def compose_seam_review_row(
    *,
    seam_index: int,
    prior_phase_name: Literal["Base", "Build", "Peak"],
    next_phase_name: Literal["Build", "Peak", "Taper"],
    call_result: SeamReviewCallResult,
    reviewer_model: str,
    triggered_resynthesis: bool,
    re_prompted_phase_name: Literal["Base", "Build", "Peak", "Taper"] | None,
) -> SeamReview:
    """Compose the `SeamReview` row to attach to Layer4Payload.seam_reviews.
    The orchestrator fills `triggered_resynthesis` + `re_prompted_phase_name`
    after applying §6.2 verdict-to-action authority semantics."""
    return SeamReview(
        seam_index=seam_index,
        prior_phase_name=prior_phase_name,
        next_phase_name=next_phase_name,
        reviewer_verdict=call_result.verdict,
        seam_issues=call_result.seam_issues,
        proposed_patch_direction=call_result.proposed_patch_direction,
        triggered_resynthesis=triggered_resynthesis,
        re_prompted_phase_name=re_prompted_phase_name,
        reviewer_model=reviewer_model,
        reviewer_input_tokens=call_result.input_tokens,
        reviewer_output_tokens=call_result.output_tokens,
        reviewer_latency_ms=call_result.latency_ms,
    )


__all__ = [
    "DEFAULT_MAX_TOKENS",
    "DEFAULT_EXTENDED_THINKING_BUDGET",
    "SYSTEM_PROMPT",
    "SeamReviewerCaller",
    "SeamReviewCallResult",
    "build_record_seam_review_tool",
    "compose_seam_review_row",
    "render_seam_review_prompt",
    "review_seam",
]
