"""Layer 3B — Goal-Timeline-Viability driver per `Layer3_3B_Spec.md` §3.

Single LLM call orchestrator. Wraps:

1. `_validate_inputs(...)` — §4 preconditions → `Layer3BInputError(code)`.
2. `_render_user_prompt(...)` — §5.1 4-block transformations.
3. `_default_llm_caller(...)` — Anthropic SDK extended-thinking + forced
   tool-use (`tool_choice={"type": "tool", "name": "emit_layer3b_payload"}`).
4. Single capped retry on schema violation per §5.5 step 1.
5. Mode-discriminator enforcement per §5.5 step 2.
6. `_check_evidence_basis(...)` — name-existence + mode-discriminator
   warn-log; no fail (§5.5 + D9).
7. `_enforce_hitl_auto_emit(...)` — validator appends missing-but-required
   §6.1 items (§5.5 step 3 + D12).
8. `_apply_confidence_floors(...)` — §6.5 4 floor rules + auto-append
   `confidence_clamped_by_data_signal` observation.
9. `_enforce_periodization_sanity_loop(...)` — §5.5 step 4 (custom-mode
   phase_weeks sum ±1 of timeline; single retry; fallback to standard +
   `periodization_shape_fallback` observation).
10. Metadata stamping + D14 event-metadata population → `Layer3BPayload`.

Companion prompt body: `aidstation-sources/prompts/Layer3B_v1.md` (system
prompt rules + tool schema rationale + D1-D14 source decisions).
"""

from __future__ import annotations

import hashlib
import warnings
from dataclasses import dataclass
from datetime import date, datetime, time as time_cls
from typing import Any, Callable

from pydantic import ValidationError

from llm_invocation import ThinkingToolCallError, invoke_tool_call
from layer4.context import (
    GoalViability,
    Layer1Payload,
    Layer2APayload,
    Layer3APayload,
    Layer3BHITLItem,
    Layer3BPayload,
    Layer3Observation,
    PeriodizationShape,
    RaceEventPayload,
)


# ─── Errors (inlined per Step 4a + Layer 2C + Layer 3A precedent) ────────────


class Layer3BInputError(ValueError):
    """Raised when §4 input preconditions fail."""

    def __init__(self, code: str, *, detail: str | None = None) -> None:
        self.code = code
        self.detail = detail
        msg = f"Layer3B input error: {code}"
        if detail:
            msg = f"{msg} — {detail}"
        super().__init__(msg)


class Layer3BOutputError(RuntimeError):
    """Raised when the LLM output fails schema validation after the single
    capped retry per §5.5 step 1, OR when the SDK adapter cannot extract an
    `emit_layer3b_payload` tool-use block, OR when the mode-discriminator
    fails per §5.5 step 2."""

    def __init__(self, code: str, *, detail: str | None = None) -> None:
        self.code = code
        self.detail = detail
        msg = f"Layer3B output error: {code}"
        if detail:
            msg = f"{msg} — {detail}"
        super().__init__(msg)


class Layer3BEvidenceBasisWarning(UserWarning):
    """Surfaced when `evidence_basis` cites an unknown path OR violates the
    §7 mode-discriminator (event-mode references must include ≥1 `h2.*`;
    no-event-mode must NOT include any `h2.*`). Telemetry-only per D9."""


# ─── Constants ───────────────────────────────────────────────────────────────


_APPROVED_MODELS = frozenset({
    "claude-sonnet-4-6",
    "claude-sonnet-4-5",  # kept for replay parity with 3A
    "claude-opus-4-7",
    "claude-haiku-4-5",
})

_TOOL_NAME = "emit_layer3b_payload"

_CONFIDENCE_RANK = {"low": 0, "medium": 1, "high": 2}

_DEFAULT_MODEL = "claude-sonnet-4-6"
_DEFAULT_TEMPERATURE = 0.0
_DEFAULT_MAX_TOKENS = 2000
_DEFAULT_THINKING_BUDGET = 3000

_VALID_GOAL_OUTCOMES = frozenset({"Finish", "Compete mid-pack", "Podium"})
_COMPETITIVE_GOAL_OUTCOMES = frozenset({"Compete mid-pack", "Podium"})
_VALID_NON_EVENT_GOAL_TYPES = frozenset({"endurance", "general_fitness", "strength", "mixed"})
_VALID_PLAN_DURATION_WEEKS = frozenset({8, 12, 16, 20, 24})

# `notable_observations` budget cap (Layer3_3B_Spec §8.2). Lock-step with
# `Layer3BPayload.notable_observations` `max_length` in `layer4/context.py`:
# used as the tool-schema `maxItems` hint, the `_trim_observations_to_budget`
# default, and the pre-validation `_clamp_notable_observations` cap.
_NOTABLE_OBSERVATIONS_MAX = 10
# Mirrors `Layer3Observation.text` `Field(max_length=240)` in `layer4/context.py`
# and the tool-schema `maxLength` on `notable_observations[].text`. The Anthropic
# API treats string bounds as guidance, so a long observation walls the cone on
# `schema_violation`; the pre-validation `_clamp_observation_text` truncates to
# the cap instead.
_OBSERVATION_TEXT_MAX_CHARS = 240
# §8.2 drop order when over budget: warning > opportunity > data_gap >
# data_hygiene. Lower rank = higher priority = kept first.
_OBSERVATION_CATEGORY_PRIORITY = {
    "warning": 0,
    "opportunity": 1,
    "data_gap": 2,
    "data_hygiene": 3,
}
# Canonical periodization phase order (matches the Literal in
# `PeriodizationShape.phase_weeks`); used by `_check_periodization_sanity` to
# test the allocation at/after `start_phase`.
_PERIODIZATION_PHASE_ORDER = ("Base", "Build", "Peak", "Taper")

# §6.1 DNF recovery window (weeks) per dnf_cause label.
_DNF_RECOVERY_WINDOW_WEEKS = {
    "quad_failure": 12,
    "nutrition_blowup": 4,
    "injury_during_event": 16,
    "weather": 4,
    "timeout": 4,
    "other": 8,
}
_DEFAULT_DNF_RECOVERY_WINDOW_WEEKS = 8

_PURE_ENDURANCE_PRIMARY_SPORTS = frozenset({
    "Trail Running",
    "Road Running",
    "Road Cycling",
    "Swimming",
    "Triathlon",
    "Marathon",
    "Ultramarathon",
})


# ─── LLM caller protocol (matches layer4/single_session.py + layer3a) ────────


@dataclass
class _LLMOutput:
    """Raw output from the LLM call before payload assembly."""

    tool_args: dict[str, Any]
    input_tokens: int
    output_tokens: int
    latency_ms: int


LLMCaller = Callable[
    [str, str, dict[str, Any], str, float, int, int],
    _LLMOutput,
]
"""Signature: `(system_prompt, user_prompt, tool_schema, model, temperature,
max_tokens, extended_thinking_budget) -> _LLMOutput`. Production default is
`_default_llm_caller` (Anthropic SDK); tests inject a stub."""


def _default_llm_caller(
    system_prompt: str,
    user_prompt: str,
    tool_schema: dict[str, Any],
    model: str,
    temperature: float,
    max_tokens: int,
    extended_thinking_budget: int,
) -> _LLMOutput:
    """Production LLM caller — delegates to the shared thinking-aware
    invocation (`llm_invocation.invoke_tool_call`), which holds the one
    correct extended-thinking request shape (tool_choice `auto` + temperature 1
    + max_tokens > budget_tokens). Failures map to `Layer3BOutputError` so the
    §5.5 error contract is preserved. Tests inject a stub instead."""
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
        raise Layer3BOutputError(exc.code, detail=exc.detail) from exc

    return _LLMOutput(
        tool_args=result.tool_args,
        input_tokens=result.input_tokens,
        output_tokens=result.output_tokens,
        latency_ms=result.latency_ms,
    )


# ─── Tool schema (full Layer3BPayload mirror per D5) ─────────────────────────


_GOAL_VIABILITY_SCHEMA = {
    "type": "object",
    "additionalProperties": False,
    "required": [
        "viability",
        "confidence",
        "reasoning_text",
        "evidence_basis",
        "suggested_adjustments",
    ],
    "properties": {
        "viability": {
            "type": "string",
            "enum": ["achievable", "achievable-with-adjustment", "unrealistic-as-stated"],
        },
        "confidence": {"type": "string", "enum": ["high", "medium", "low"]},
        "reasoning_text": {"type": "string"},
        "evidence_basis": {"type": "array", "items": {"type": "string"}},
        "suggested_adjustments": {"type": "array", "items": {"type": "string"}},
    },
}

_PERIODIZATION_SHAPE_SCHEMA = {
    "type": "object",
    "additionalProperties": False,
    "required": ["mode", "start_phase", "reasoning_text", "evidence_basis"],
    "properties": {
        "mode": {
            "type": "string",
            "enum": ["standard", "compressed", "extended", "custom"],
        },
        "start_phase": {
            "type": "string",
            "enum": ["Base", "Build", "Peak", "Taper"],
        },
        "phase_weeks": {
            "anyOf": [
                {
                    "type": "object",
                    "additionalProperties": False,
                    "properties": {
                        "Base": {"type": "integer", "minimum": 0},
                        "Build": {"type": "integer", "minimum": 0},
                        "Peak": {"type": "integer", "minimum": 0},
                        "Taper": {"type": "integer", "minimum": 0},
                    },
                },
                {"type": "null"},
            ]
        },
        "reasoning_text": {"type": "string"},
        "evidence_basis": {"type": "array", "items": {"type": "string"}},
    },
}

_HITL_ITEM_SCHEMA = {
    "type": "object",
    "additionalProperties": False,
    "required": [
        "source",
        "item_label",
        "severity",
        "description",
        "recommended_action",
        "revise_option",
        "revise_target",
    ],
    "properties": {
        "source": {"type": "string", "enum": ["3B"]},
        "item_label": {"type": "string"},
        "severity": {
            "type": "string",
            "enum": ["blocker", "warning", "informational"],
        },
        "description": {"type": "string"},
        "recommended_action": {"type": "string"},
        "acknowledge_option": {"type": ["string", "null"]},
        "revise_option": {"type": "string"},
        "revise_target": {"type": "string"},
    },
}


def build_emit_layer3b_payload_tool() -> dict[str, Any]:
    """Tool schema mirroring `Layer3BPayload` per D5 (full payload-contract
    mirror, Step 4a Option 2 precedent). Metadata fields (`user_id`, `as_of`,
    `model`, `temperature`, `prompt_hash`, `latency_ms`, `*_tokens`,
    `etl_version_set`) + D-66 event-metadata fields (event_date,
    event_locale_id, race_format, time_to_event_weeks) are stamped by the
    driver post-hoc per D14 — NOT in the tool schema."""
    return {
        "name": _TOOL_NAME,
        "description": (
            "Emit the structured goal-timeline-viability evaluation. Required. "
            "The Layer3BPayload contract is mirrored sans driver-stamped "
            "metadata (user_id, as_of, model, temperature, prompt_hash, "
            "latency_ms, *_tokens, etl_version_set) + sans D-66 "
            "event-metadata fields (event_date, event_locale_id, race_format, "
            "time_to_event_weeks) which are populated post-LLM from the "
            "orchestrator-joined target race_events row."
        ),
        "input_schema": {
            "type": "object",
            "additionalProperties": False,
            "required": [
                "mode",
                "goal_viability",
                "periodization_shape",
                "hitl_surface",
                "notable_observations",
            ],
            "properties": {
                "mode": {"type": "string", "enum": ["event", "no-event"]},
                "goal_viability": _GOAL_VIABILITY_SCHEMA,
                "periodization_shape": _PERIODIZATION_SHAPE_SCHEMA,
                "hitl_surface": {
                    "type": "array",
                    "items": _HITL_ITEM_SCHEMA,
                },
                "notable_observations": {
                    "type": "array",
                    "maxItems": _NOTABLE_OBSERVATIONS_MAX,
                    "items": {
                        "type": "object",
                        "additionalProperties": False,
                        "required": ["category", "text", "evidence_basis", "elevates_to_hitl"],
                        "properties": {
                            "category": {
                                "type": "string",
                                "enum": ["warning", "opportunity", "data_gap", "data_hygiene"],
                            },
                            "text": {"type": "string", "maxLength": 240},
                            "evidence_basis": {
                                "type": "array",
                                "items": {"type": "string"},
                            },
                            "elevates_to_hitl": {"type": "boolean"},
                        },
                    },
                },
            },
        },
    }


# ─── Input validation (§4) ───────────────────────────────────────────────────


def _validate_inputs(
    layer1_payload: Layer1Payload | None,
    layer3a_payload: Layer3APayload | None,
    layer2a_payload: Layer2APayload | None,
    race_event_payload: RaceEventPayload | None,
    current_date: date | None,
    etl_version_set: dict[str, str] | None,
    model: str,
    temperature: float,
    *,
    goal_outcome: str | None,
    plan_duration_weeks: int | None,
    non_event_goal_type: str | None,
) -> None:
    """Per `Layer3_3B_Spec.md` §4. Raises `Layer3BInputError(code)` on the
    first failure with a spec-named error code."""
    if layer1_payload is None:
        raise Layer3BInputError("missing_layer1")
    if layer3a_payload is None:
        raise Layer3BInputError("missing_3a_payload")
    if layer2a_payload is None:
        raise Layer3BInputError("missing_2a_payload")
    if current_date is None:
        raise Layer3BInputError("invalid_current_date", detail="current_date is None")
    if not etl_version_set:
        raise Layer3BInputError("missing_etl_pin")

    # §4 rule 5: 3A payload etl_version_set matches caller's pin
    if layer3a_payload.etl_version_set != etl_version_set:
        raise Layer3BInputError(
            "etl_version_mismatch_3a",
            detail=(
                f"3A pin={layer3a_payload.etl_version_set!r} vs "
                f"caller pin={etl_version_set!r}"
            ),
        )
    # §4 rule 6: 2A payload etl_version_set matches caller's pin
    if layer2a_payload.etl_version_set != etl_version_set:
        raise Layer3BInputError(
            "etl_version_mismatch_2a",
            detail=(
                f"2A pin={layer2a_payload.etl_version_set!r} vs "
                f"caller pin={etl_version_set!r}"
            ),
        )

    # §4 rule 7: ≥1 included discipline
    if not any(d.inclusion == "included" for d in layer2a_payload.disciplines):
        raise Layer3BInputError(
            "no_included_disciplines",
            detail="2A produced zero disciplines with inclusion='included'",
        )

    if model not in _APPROVED_MODELS:
        raise Layer3BInputError("unapproved_model", detail=f"model={model!r}")
    if not (0.0 <= temperature <= 1.0):
        raise Layer3BInputError(
            "invalid_temp", detail=f"temperature={temperature!r}"
        )

    # §4 rules 1+2: event-mode requires future event_date + goal_outcome
    if race_event_payload is not None:
        # rule 1: event_date in past
        if race_event_payload.event_date < current_date:
            raise Layer3BInputError(
                "event_date_in_past",
                detail=(
                    f"event_date={race_event_payload.event_date.isoformat()} "
                    f"< current_date={current_date.isoformat()}"
                ),
            )
        # rule 2: event-mode requires goal_outcome populated (caller kwarg)
        if goal_outcome is None:
            raise Layer3BInputError(
                "event_mode_missing_goal_outcome",
                detail=(
                    "event-mode requires goal_outcome kwarg "
                    "(one of Finish / Compete mid-pack / Podium)"
                ),
            )
        if goal_outcome not in _VALID_GOAL_OUTCOMES:
            raise Layer3BInputError(
                "event_mode_invalid_goal_outcome",
                detail=(
                    f"goal_outcome={goal_outcome!r} not in "
                    f"{sorted(_VALID_GOAL_OUTCOMES)!r}"
                ),
            )
    else:
        # §4 rule 3: no-event-mode requires plan_duration_weeks ∈ {8,12,16,20,24}
        # AND non_event_goal_type ∈ enum
        if plan_duration_weeks is None or plan_duration_weeks not in _VALID_PLAN_DURATION_WEEKS:
            raise Layer3BInputError(
                "no_event_mode_missing_fields",
                detail=(
                    f"plan_duration_weeks={plan_duration_weeks!r} not in "
                    f"{sorted(_VALID_PLAN_DURATION_WEEKS)!r}"
                ),
            )
        if non_event_goal_type is None or non_event_goal_type not in _VALID_NON_EVENT_GOAL_TYPES:
            raise Layer3BInputError(
                "no_event_mode_missing_fields",
                detail=(
                    f"non_event_goal_type={non_event_goal_type!r} not in "
                    f"{sorted(_VALID_NON_EVENT_GOAL_TYPES)!r}"
                ),
            )


# ─── Prep dict + user-prompt rendering (§5.1) ────────────────────────────────


def _time_to_event_weeks(event_date: date, current_date: date) -> int:
    """Per spec §5.1 Block 1. Floor-divides days by 7; clamps to 0."""
    return max(0, (event_date - current_date).days // 7)


def _time_to_event_phase_band(weeks: int) -> str:
    """Per spec §5.3 — guidance band the LLM is told."""
    if weeks < 4:
        return "compressed (Peak + Taper only; skip Base/Build)"
    if weeks < 8:
        return "compressed (truncated Build + Peak + Taper)"
    if weeks < 16:
        return "standard (Base + Build + Peak + Taper at typical proportions)"
    if weeks <= 24:
        return "standard or extended (depending on 3A current state)"
    return "extended (double-Base + Build + Peak + Taper)"


def _resolve_plan_duration(
    layer1_payload: Layer1Payload, override: int | None
) -> int | None:
    """No-event-mode duration: caller override takes precedence, else
    Layer1EventGoal.plan_duration_weeks_no_event."""
    if override is not None:
        return override
    return layer1_payload.event_goal.plan_duration_weeks_no_event


def _resolve_non_event_goal_type(
    layer1_payload: Layer1Payload, override: str | None
) -> str | None:
    """No-event-mode goal type: caller override takes precedence, else
    Layer1EventGoal.non_event_goal_type."""
    if override is not None:
        return override
    return layer1_payload.event_goal.non_event_goal_type


def _render_block_1_timeline(
    *,
    mode: str,
    race_event_payload: RaceEventPayload | None,
    current_date: date,
    plan_duration_weeks: int | None,
    non_event_goal_type: str | None,
) -> str:
    """Spec §5.1 Block 1 — Mode + timeline."""
    if mode == "event":
        assert race_event_payload is not None
        weeks = _time_to_event_weeks(race_event_payload.event_date, current_date)
        band = _time_to_event_phase_band(weeks)
        lines = [
            "- mode: event",
            f"- event_date: {race_event_payload.event_date.isoformat()}",
            f"- time_to_event_weeks: {weeks}",
            f"- time_to_event_phase_band guidance: {band}",
            f"- race_format: {race_event_payload.race_format}",
        ]
        return "\n".join(lines)
    lines = [
        "- mode: no-event",
        f"- plan_duration_weeks: {plan_duration_weeks}",
        f"- non_event_goal_type: {non_event_goal_type}",
    ]
    return "\n".join(lines)


def _render_block_2_goal_context(
    *,
    mode: str,
    race_event_payload: RaceEventPayload | None,
    layer1_payload: Layer1Payload,
    goal_outcome: str | None,
    time_goal: str | None,
    first_time_at_distance: bool | None,
    previous_attempts: list[dict[str, Any]] | None,
    race_distance_km: float | None,
    race_duration_hr: float | None,
    race_terrain: list[str] | None,
    race_pack_weight_kg: float | None,
) -> str:
    """Spec §5.1 Block 2 — Goal context. Event-mode reads §H.2 fields (driver
    kwargs for v1 deployed-shape gap per D11); no-event-mode reads §C from
    Layer1Payload."""
    if mode == "event":
        assert race_event_payload is not None
        lines = [
            f"- race_event_name: {race_event_payload.name}",
            f"- goal_outcome: {goal_outcome or 'unknown'}",
        ]
        if time_goal:
            lines.append(f"- time_goal: {time_goal}")
        lines.append(
            f"- first_time_at_distance: "
            f"{first_time_at_distance if first_time_at_distance is not None else 'unknown'}"
        )
        if previous_attempts:
            attempts_summary = [
                f"  - outcome={a.get('outcome', '?')}; dnf_cause={a.get('dnf_cause', '')}"
                for a in previous_attempts
            ]
            lines.append("- previous_attempts:")
            lines.extend(attempts_summary)
        else:
            lines.append("- previous_attempts: (none)")
        # race_distance_km: prefer kwarg, else RaceEventPayload.distance_km
        dist = race_distance_km
        if dist is None and race_event_payload.distance_km is not None:
            dist = float(race_event_payload.distance_km)
        if dist is not None:
            lines.append(f"- race_distance_km: {dist:.1f}")
        if race_duration_hr is not None:
            lines.append(f"- race_duration_hr: {race_duration_hr:.1f}")
        if race_terrain:
            lines.append(f"- race_terrain: {', '.join(race_terrain)}")
        if race_pack_weight_kg is not None:
            lines.append(f"- race_pack_weight_kg: {race_pack_weight_kg:.1f}")
        return "\n".join(lines)

    # No-event mode
    primary = layer1_payload.identity.primary_sport or "unspecified"
    secondary = layer1_payload.training_history.secondary_sports
    sec_str = (
        ", ".join(f"{s.sport_slug}[{s.experience_tier}]" for s in secondary)
        if secondary
        else "(none)"
    )
    return (
        f"- primary_sport: {primary}\n"
        f"- secondary_sports: {sec_str}"
    )


def _render_block_3_state_excerpt(layer3a_payload: Layer3APayload) -> str:
    """Spec §5.1 Block 3 — Current state excerpt from 3A."""
    cs = layer3a_payload.current_state
    rt = layer3a_payload.recent_trajectory
    weak = (
        ", ".join(cs.weak_links) if cs.weak_links else "(none)"
    )
    skills = (
        ", ".join(f"{k}={v.level}({v.confidence})" for k, v in cs.skill_assessments.items())
        if cs.skill_assessments
        else "(none)"
    )
    providers = (
        ", ".join(layer3a_payload.data_density.connected_providers)
        if layer3a_payload.data_density.connected_providers
        else "(none)"
    )
    return (
        f"- aerobic_capacity: level={cs.aerobic_capacity.level}, "
        f"confidence={cs.aerobic_capacity.confidence}; "
        f"reasoning={cs.aerobic_capacity.reasoning_text}\n"
        f"- strength: level={cs.strength.level}, "
        f"confidence={cs.strength.confidence}; "
        f"reasoning={cs.strength.reasoning_text}\n"
        f"- weak_links: {weak}\n"
        f"- skill_assessments: {skills}\n"
        f"- short_term_trajectory: {rt.short_term.direction}; "
        f"reasoning={rt.short_term.reasoning_text}\n"
        f"- medium_term_trajectory: {rt.medium_term.direction}; "
        f"reasoning={rt.medium_term.reasoning_text}\n"
        f"- trajectory_confidence: {rt.confidence}\n"
        f"- data_density.connected_providers: {providers}\n"
        f"- data_density.self_report_freshness_days: "
        f"{layer3a_payload.data_density.self_report_freshness_days}"
    )


def _render_block_4_discipline_load(layer2a_payload: Layer2APayload) -> str:
    """Spec §5.1 Block 4 — Discipline + load context from 2A."""
    included = [d for d in layer2a_payload.disciplines if d.inclusion == "included"]
    lines = [f"- framework_sport: {layer2a_payload.framework_sport}"]
    if not included:
        lines.append("- (no included disciplines)")
    else:
        lines.append("- included_disciplines:")
        for d in included:
            lines.append(
                f"  - {d.discipline_id} ({d.discipline_name}); "
                f"role={d.role}; load_weight={d.load_weight.value:.2f}"
            )
    lines.append(
        f"- training_gaps_flagged_count: "
        f"{layer2a_payload.training_gaps_summary.flagged_count}"
    )
    return "\n".join(lines)


def _build_prep_dict(
    *,
    mode: str,
    race_event_payload: RaceEventPayload | None,
    layer1_payload: Layer1Payload,
    layer3a_payload: Layer3APayload,
    layer2a_payload: Layer2APayload,
    current_date: date,
    plan_duration_weeks: int | None,
    non_event_goal_type: str | None,
    goal_outcome: str | None,
    time_goal: str | None,
    first_time_at_distance: bool | None,
    previous_attempts: list[dict[str, Any]] | None,
    race_distance_km: float | None,
    race_duration_hr: float | None,
    race_terrain: list[str] | None,
    race_pack_weight_kg: float | None,
) -> dict[str, Any]:
    """Flat dict keyed by `section.field` paths. Used by the evidence-basis
    cross-check to verify the LLM cites real field names. Per spec §7 +
    Layer3B_v1.md §3, the key prefixes are h1.* (Layer 1 fields), h2.*
    (event-mode §H.2 fields), h3.* (no-event-mode §H.3 fields), 3a.*
    (Layer 3A excerpt), 2a.* (Layer 2A excerpt), c.* (§C primary/secondary)."""
    th = layer1_payload.training_history
    d: dict[str, Any] = {
        "c.primary_sport": layer1_payload.identity.primary_sport,
        "c.secondary_sports": [s.sport_slug for s in th.secondary_sports],
        "c.discipline_weighting": [
            (w.discipline_slug, w.weight_pct) for w in th.discipline_weighting
        ],
        "3a.current_state.aerobic_capacity": layer3a_payload.current_state.aerobic_capacity.level,
        "3a.current_state.aerobic_capacity.confidence": layer3a_payload.current_state.aerobic_capacity.confidence,
        "3a.current_state.strength": layer3a_payload.current_state.strength.level,
        "3a.current_state.strength.confidence": layer3a_payload.current_state.strength.confidence,
        "3a.current_state.weak_links": layer3a_payload.current_state.weak_links,
        "3a.current_state.skill_assessments": list(
            layer3a_payload.current_state.skill_assessments.keys()
        ),
        "3a.recent_trajectory.short_term.direction": layer3a_payload.recent_trajectory.short_term.direction,
        "3a.recent_trajectory.medium_term.direction": layer3a_payload.recent_trajectory.medium_term.direction,
        "3a.recent_trajectory.confidence": layer3a_payload.recent_trajectory.confidence,
        "3a.data_density.connected_providers": layer3a_payload.data_density.connected_providers,
        "3a.data_density.self_report_freshness_days": layer3a_payload.data_density.self_report_freshness_days,
        "2a.framework_sport": layer2a_payload.framework_sport,
        "2a.training_gaps_summary.flagged_count": layer2a_payload.training_gaps_summary.flagged_count,
    }
    for disc in layer2a_payload.disciplines:
        d[f"2a.discipline.{disc.discipline_id}.role"] = disc.role
        d[f"2a.discipline.{disc.discipline_id}.load_weight"] = disc.load_weight.value

    if mode == "event":
        assert race_event_payload is not None
        d["h2.event_date"] = race_event_payload.event_date
        d["h2.race_format"] = race_event_payload.race_format
        d["h2.race_event_name"] = race_event_payload.name
        d["h2.time_to_event_weeks"] = _time_to_event_weeks(
            race_event_payload.event_date, current_date
        )
        d["h2.goal_outcome"] = goal_outcome
        d["h2.time_goal"] = time_goal
        d["h2.first_time_at_distance"] = first_time_at_distance
        d["h2.previous_attempts"] = previous_attempts or []
        d["h2.race_distance_km"] = (
            race_distance_km
            if race_distance_km is not None
            else (
                float(race_event_payload.distance_km)
                if race_event_payload.distance_km is not None
                else None
            )
        )
        d["h2.race_duration_hr"] = race_duration_hr
        d["h2.race_terrain"] = race_terrain or []
        d["h2.race_pack_weight_kg"] = race_pack_weight_kg
    else:
        d["h3.plan_duration_weeks"] = plan_duration_weeks
        d["h3.non_event_goal_type"] = non_event_goal_type

    return d


_SYSTEM_PROMPT = """You are AIDSTATION's goal-timeline-viability evaluator (Layer 3 Node 3B).

Your job: judge whether the athlete's stated goal is achievable in the
time available, and produce a periodization shape that Layer 4 will use
to size and order training phases.

You will receive (in the user prompt):
  - Mode (event vs no-event) + timeline
  - Goal context (event details OR plan duration + goal type)
  - Athlete current state and recent trajectory (from Layer 3A)
  - Included disciplines + load weights (from Layer 2A)

You will produce a structured Layer3BPayload via the `emit_layer3b_payload`
tool. You cannot return free-form text outside the tool call.

Hard rules:

1. Ground every viability + periodization judgment in specific evidence
   from the input. Cite the field name(s) in `reasoning_text` and list
   them in `evidence_basis` (e.g., "h2.goal_outcome", "3a.current_state.
   aerobic_capacity", "2a.discipline.D-001.load_weight").

2. Mode-discriminator on evidence_basis paths: in event-mode, at least
   one `goal_viability.evidence_basis` entry must reference an h2.*
   field; in no-event-mode, references must use h3.* prefix only — no
   h2.* references.

3. Periodization-shape vocabulary:
   - standard — use 2A's phase load bands as-is. Default for most cases.
   - compressed — shorter phases or skipped Base. For event-mode
     time_to_event_weeks < 8, or no-event mode when Goal Type strongly
     mismatches current state and Plan Duration is short.
   - extended — lengthened phases. May include double-Base for
     time_to_event_weeks > 20 with athlete starting from low aerobic
     state.
   - custom — explicit phase_weeks dict override. phase_weeks MUST sum
     to time_to_event_weeks (event) or plan_duration_weeks (no-event)
     within ±1.

   start_phase ∈ {Base, Build, Peak, Taper}. If 3A shows
   aerobic_capacity ∈ {good, strong} and short-term trajectory is
   building/steady, start_phase = Build is appropriate (skip Base).
   Compressed timelines (<4 weeks) typically start at Peak or Taper.

   phase_weeks MUST be null unless mode == 'custom'.

4. Time-to-event phase band guidance (event-mode only; advisory):
   - < 4 weeks → compressed, Peak + Taper only.
   - 4–8 weeks → compressed, truncated Build + Peak + Taper.
   - 8–16 weeks → standard, Base + Build + Peak + Taper at typical
     proportions.
   - 16–24 weeks → standard or extended depending on 3A state.
   - > 24 weeks → extended, double-Base + Build + Peak + Taper.

5. HITL trigger thresholds — emit a hitl_surface item with the exact
   item_label when ANY of these conditions hold:
   - goal_viability.viability == 'unrealistic-as-stated' →
     3B.unrealistic_goal, severity=blocker. acknowledge_option MUST be
     null (blocker items cannot be acknowledged — athlete must revise).
   - viability == 'achievable-with-adjustment' AND
     first_time_at_distance == True AND goal_outcome ∈
     {Compete mid-pack, Podium} → 3B.first_time_competitive_goal,
     severity=warning.
   - event-mode AND previous_attempts contains DNF AND
     time_to_event_weeks < dnf_recovery_window_weeks →
     3B.dnf_recurrence_risk, severity=warning. Window per dnf_cause:
     quad_failure=12, nutrition_blowup=4, injury_during_event=16,
     weather/timeout=4, other=8.
   - periodization_shape.mode == 'compressed' AND 3A
     recent_trajectory.short_term.direction ∈ {overreached, fatigued} →
     3B.compressed_on_fatigued_athlete, severity=warning.

   viability == 'achievable' with no qualifiers → no HITL.

6. Confidence calibration — the validator post-clamps
   goal_viability.confidence down when any signal fires:
   - first_time_at_distance == True AND goal_outcome ∈
     {Compete mid-pack, Podium} → ≤ medium.
   - 3A recent_trajectory.confidence == 'low' → ≤ medium.
   - no-event mode AND 3A data_density.connected_providers empty AND
     self_report_freshness_days > 30 → ≤ low.
   - event-mode AND previous_attempts empty AND
     first_time_at_distance == True → ≤ medium.
   Prefer medium when in doubt.

7. No-event-mode heuristics — guidance, not hard rules:
   - non_event_goal_type == 'strength' AND 3A current_state.strength.
     level == 'low' AND plan_duration_weeks <= 12 → likely
     achievable-with-adjustment, periodization extended.
   - non_event_goal_type == 'endurance' AND 3A
     current_state.aerobic_capacity.level ∈ {low, moderate} AND
     plan_duration_weeks >= 16 → typically achievable, standard.
   - non_event_goal_type == 'mixed' → shape based on weaker capacity.
   - non_event_goal_type == 'general_fitness' → almost always
     achievable, standard, minimal HITL.
   - Cross-check Goal Type vs §C primary_sport: if 'strength' goal +
     pure-endurance primary (Trail Running, Road Cycling, Swimming,
     etc.), auto-emit observation goal_type_primary_sport_mismatch
     (category=data_hygiene, elevates_to_hitl=False).

8. Required observation auto-emit triggers:
   - first_time_at_distance == True (event-mode) → category=warning;
     elevates_to_hitl=True only when paired with §6.1 row 2 condition.
   - previous_attempts contains DNF in same event → category=warning;
     elevates_to_hitl per §6.1 row 3.
   - event-mode AND time_to_event_weeks > 30 → category=opportunity;
     elevates_to_hitl=False. Suggest intermediate-test-race scheduling.
   - periodization_shape.mode == 'compressed' → category=warning;
     elevates_to_hitl=False unless §6.1 row 4 condition.
   - no-event mode AND Goal Type vs §C primary_sport mismatch →
     category=data_hygiene; elevates_to_hitl=False.

9. Observation budget: notable_observations is capped at 6 items.
   Priority: warning > opportunity > data_gap > data_hygiene. Keep each
   observation's `text` under 240 characters — one concise flag, not a
   paragraph (it is hard-capped at 240 and truncated past that).

10. Forbidden observations (never emit):
    - Generic encouragement.
    - State-assessment claims ("your aerobic capacity is low") —
      Layer 3A's territory.
    - Injury-risk statements — Layer 2D's territory.
    - Exercise prescriptions / session designs / plan dates — Layer 4.
    - Speculation beyond evidence.

11. Race-date-in-past is fatal — validation catches before you see the
    prompt; do NOT pivot to post-race-results mode.

12. Plan duration cap: §H.3 caps no-event Plan Duration at 24 weeks.
    Event-mode can exceed (use 'extended' mode).

Voice: direct, evidence-grounded, no platitudes. Match the cadence of a
real endurance coach evaluating a goal. No hedging ("might possibly"). If
a goal is unrealistic, say so and explain why."""


def _render_user_prompt(
    *,
    mode: str,
    race_event_payload: RaceEventPayload | None,
    layer1_payload: Layer1Payload,
    layer3a_payload: Layer3APayload,
    layer2a_payload: Layer2APayload,
    current_date: date,
    plan_duration_weeks: int | None,
    non_event_goal_type: str | None,
    goal_outcome: str | None,
    time_goal: str | None,
    first_time_at_distance: bool | None,
    previous_attempts: list[dict[str, Any]] | None,
    race_distance_km: float | None,
    race_duration_hr: float | None,
    race_terrain: list[str] | None,
    race_pack_weight_kg: float | None,
    retry_error: str | None = None,
    periodization_error: str | None = None,
) -> str:
    """Per `Layer3_3B_Spec.md` §5.1 — assemble the 4-block user prompt."""
    blocks = [
        "Mode + timeline:",
        _render_block_1_timeline(
            mode=mode,
            race_event_payload=race_event_payload,
            current_date=current_date,
            plan_duration_weeks=plan_duration_weeks,
            non_event_goal_type=non_event_goal_type,
        ),
        "",
        "Goal context:",
        _render_block_2_goal_context(
            mode=mode,
            race_event_payload=race_event_payload,
            layer1_payload=layer1_payload,
            goal_outcome=goal_outcome,
            time_goal=time_goal,
            first_time_at_distance=first_time_at_distance,
            previous_attempts=previous_attempts,
            race_distance_km=race_distance_km,
            race_duration_hr=race_duration_hr,
            race_terrain=race_terrain,
            race_pack_weight_kg=race_pack_weight_kg,
        ),
        "",
        "Current state (from Layer 3A):",
        _render_block_3_state_excerpt(layer3a_payload),
        "",
        "Discipline + load context (from Layer 2A):",
        _render_block_4_discipline_load(layer2a_payload),
        "",
        f"Today is {current_date.isoformat()}.",
        "",
        "Produce a `Layer3BPayload` via the `emit_layer3b_payload` tool. "
        "Ground every viability + periodization judgment in evidence_basis "
        "citations. Apply the §6 guardrails — be conservative on confidence; "
        "emit HITL items when conditions trigger; pick periodization mode "
        "per §5.3 phase bands plus 3A state.",
    ]
    if retry_error:
        blocks.extend([
            "",
            f"Previous attempt failed schema validation: {retry_error}",
            "",
            "Re-emit a valid `emit_layer3b_payload` tool call addressing the "
            "error above. Do not change unrelated fields.",
        ])
    if periodization_error:
        blocks.extend([
            "",
            periodization_error,
        ])
    return "\n".join(blocks)


# ─── Evidence-basis cross-check (§5.5 + D9) ──────────────────────────────────


def _collect_evidence_basis_paths(payload_dict: dict[str, Any]) -> list[str]:
    """Walk the tool args + collect every `evidence_basis` entry across
    goal_viability + periodization_shape + observations."""
    paths: list[str] = []
    gv = payload_dict.get("goal_viability", {})
    if isinstance(gv, dict):
        paths.extend(gv.get("evidence_basis", []))
    ps = payload_dict.get("periodization_shape", {})
    if isinstance(ps, dict):
        paths.extend(ps.get("evidence_basis", []))
    for obs in payload_dict.get("notable_observations", []):
        if isinstance(obs, dict):
            paths.extend(obs.get("evidence_basis", []))
    return paths


def _check_evidence_basis(
    tool_args: dict[str, Any], prep_dict: dict[str, Any], mode: str
) -> None:
    """Per §5.5 + D9 — name-existence check + mode-discriminator on path
    prefixes (§7 schema rule). Missing references warn but do not fail."""
    cited = _collect_evidence_basis_paths(tool_args)
    valid_keys = set(prep_dict.keys())
    for path in cited:
        if path not in valid_keys:
            warnings.warn(
                f"evidence_basis cites unknown field path: {path!r}",
                Layer3BEvidenceBasisWarning,
                stacklevel=3,
            )

    # Mode-discriminator on goal_viability.evidence_basis (§7 schema rule)
    gv = tool_args.get("goal_viability", {})
    if isinstance(gv, dict):
        gv_paths = gv.get("evidence_basis", [])
        h2_refs = [p for p in gv_paths if p.startswith("h2.")]
        if mode == "event" and not h2_refs:
            warnings.warn(
                "event-mode goal_viability.evidence_basis must reference at "
                "least one h2.* field per §7 schema rule (got "
                f"{gv_paths!r})",
                Layer3BEvidenceBasisWarning,
                stacklevel=3,
            )
        elif mode == "no-event" and h2_refs:
            warnings.warn(
                "no-event-mode goal_viability.evidence_basis must NOT "
                f"reference h2.* fields per §7 schema rule (got {h2_refs!r})",
                Layer3BEvidenceBasisWarning,
                stacklevel=3,
            )


# ─── HITL auto-emit enforcement (§5.5 step 3 + §6.1 + D12) ───────────────────


def _has_dnf_attempt(previous_attempts: list[dict[str, Any]] | None) -> bool:
    if not previous_attempts:
        return False
    return any(
        str(a.get("outcome", "")).upper() == "DNF" for a in previous_attempts
    )


def _dnf_recovery_window(previous_attempts: list[dict[str, Any]] | None) -> int:
    """Maximum recovery window across DNF attempts (worst-case)."""
    if not previous_attempts:
        return 0
    max_window = 0
    for a in previous_attempts:
        if str(a.get("outcome", "")).upper() != "DNF":
            continue
        cause = str(a.get("dnf_cause", "other")).lower()
        window = _DNF_RECOVERY_WINDOW_WEEKS.get(cause, _DEFAULT_DNF_RECOVERY_WINDOW_WEEKS)
        max_window = max(max_window, window)
    return max_window


def _enforce_hitl_auto_emit(
    payload: Layer3BPayload,
    *,
    mode: str,
    race_event_payload: RaceEventPayload | None,
    layer3a_payload: Layer3APayload,
    current_date: date,
    goal_outcome: str | None,
    first_time_at_distance: bool | None,
    previous_attempts: list[dict[str, Any]] | None,
) -> Layer3BPayload:
    """Per spec §5.5 step 3 + §6.1 + D12 — append missing-but-required HITL
    items. Dedup by item_label. LLM-emitted items kept; auto-emits append at
    the end."""
    existing_labels = {item.item_label for item in payload.hitl_surface}
    new_items: list[Layer3BHITLItem] = list(payload.hitl_surface)

    # §6.1 row 1: viability == 'unrealistic-as-stated' → blocker
    if payload.goal_viability.viability == "unrealistic-as-stated":
        if "3B.unrealistic_goal" not in existing_labels:
            new_items.append(
                Layer3BHITLItem(
                    source="3B",
                    item_label="3B.unrealistic_goal",
                    severity="blocker",
                    description=(
                        "Stated goal is not achievable in the available "
                        "timeline given current state."
                    ),
                    recommended_action=(
                        "Revise the goal (stretch to a lower tier) or extend "
                        "the timeline."
                    ),
                    acknowledge_option=None,
                    revise_option=(
                        "Edit §H.2 goal_outcome to a lower tier (e.g., Finish "
                        "instead of Podium), or extend the event timeline."
                    ),
                    revise_target=(
                        "h2.goal_outcome" if mode == "event" else "h3.plan_duration_weeks"
                    ),
                )
            )
            existing_labels.add("3B.unrealistic_goal")

    # §6.1 row 2: first_time + competitive goal + achievable-with-adjustment → warning
    if (
        mode == "event"
        and first_time_at_distance is True
        and goal_outcome in _COMPETITIVE_GOAL_OUTCOMES
        and payload.goal_viability.viability == "achievable-with-adjustment"
    ):
        if "3B.first_time_competitive_goal" not in existing_labels:
            new_items.append(
                Layer3BHITLItem(
                    source="3B",
                    item_label="3B.first_time_competitive_goal",
                    severity="warning",
                    description=(
                        "First time at this distance + competitive outcome "
                        "goal. Pacing calibration is the dominant risk."
                    ),
                    recommended_action=(
                        "Consider an intermediate test event or revise to "
                        "Finish-tier goal."
                    ),
                    acknowledge_option=(
                        "I accept the pacing risk and want to attempt the "
                        "competitive goal anyway."
                    ),
                    revise_option=(
                        "Stretch goal to Finish given first-time-at-distance "
                        "context."
                    ),
                    revise_target="h2.goal_outcome",
                )
            )
            existing_labels.add("3B.first_time_competitive_goal")

    # §6.1 row 3: event-mode + prior DNF + within recovery window → warning
    if (
        mode == "event"
        and race_event_payload is not None
        and _has_dnf_attempt(previous_attempts)
    ):
        weeks_to_event = _time_to_event_weeks(
            race_event_payload.event_date, current_date
        )
        window = _dnf_recovery_window(previous_attempts)
        if weeks_to_event < window:
            if "3B.dnf_recurrence_risk" not in existing_labels:
                new_items.append(
                    Layer3BHITLItem(
                        source="3B",
                        item_label="3B.dnf_recurrence_risk",
                        severity="warning",
                        description=(
                            f"Prior DNF recovery window ({window}wk) exceeds "
                            f"time to event ({weeks_to_event}wk). DNF cause "
                            "may recur without targeted preparation."
                        ),
                        recommended_action=(
                            "Address documented DNF cause in early phases "
                            "(e.g., eccentric loading for quad_failure)."
                        ),
                        acknowledge_option=(
                            "I accept the recurrence risk and want to "
                            "proceed with the current timeline."
                        ),
                        revise_option=(
                            "Postpone event by sufficient weeks for full "
                            "recovery + targeted prep."
                        ),
                        revise_target="h2.event_date",
                    )
                )
                existing_labels.add("3B.dnf_recurrence_risk")

    # §6.1 row 4: compressed + 3A overreached/fatigued → warning
    if payload.periodization_shape.mode == "compressed" and (
        layer3a_payload.recent_trajectory.short_term.direction
        in ("overreached", "fatigued")
    ):
        if "3B.compressed_on_fatigued_athlete" not in existing_labels:
            new_items.append(
                Layer3BHITLItem(
                    source="3B",
                    item_label="3B.compressed_on_fatigued_athlete",
                    severity="warning",
                    description=(
                        "Compressed periodization on an athlete showing "
                        f"short-term {layer3a_payload.recent_trajectory.short_term.direction}. "
                        "Recovery time is structurally constrained."
                    ),
                    recommended_action=(
                        "Layer 4 will apply load caps; consider extending "
                        "the timeline if possible."
                    ),
                    acknowledge_option=(
                        "I accept the adherence/injury risk under compressed "
                        "periodization."
                    ),
                    revise_option=(
                        "Extend the event timeline to relieve compression."
                    ),
                    revise_target=(
                        "h2.event_date" if mode == "event" else "h3.plan_duration_weeks"
                    ),
                )
            )
            existing_labels.add("3B.compressed_on_fatigued_athlete")

    return payload.model_copy(update={"hitl_surface": new_items})


# ─── Confidence-floor clamp (§6.5 + D8) ──────────────────────────────────────


def _clamp_confidence(current: str, ceiling: str) -> str:
    """Return the lower of current vs ceiling per the high > medium > low
    ordering."""
    if _CONFIDENCE_RANK[current] <= _CONFIDENCE_RANK[ceiling]:
        return current
    return ceiling


def _apply_confidence_floors(
    payload: Layer3BPayload,
    *,
    mode: str,
    layer3a_payload: Layer3APayload,
    goal_outcome: str | None,
    first_time_at_distance: bool | None,
    previous_attempts: list[dict[str, Any]] | None,
) -> Layer3BPayload:
    """Per `Layer3_3B_Spec.md` §6.5 + D8 — 4 floor rules. Returns a clamped
    copy. Signals that fire are recorded + surfaced via a single appended
    `confidence_clamped_by_data_signal` observation (category=data_gap,
    elevates_to_hitl=False)."""
    signals: list[str] = []
    gv = payload.goal_viability

    # Floor 1: first_time + competitive goal → ≤ medium
    if (
        first_time_at_distance is True
        and goal_outcome in _COMPETITIVE_GOAL_OUTCOMES
    ):
        if _CONFIDENCE_RANK[gv.confidence] > _CONFIDENCE_RANK["medium"]:
            gv = gv.model_copy(update={"confidence": "medium"})
        signals.append("first_time_competitive_goal")

    # Floor 2: 3A recent_trajectory.confidence == 'low' → ≤ medium
    if layer3a_payload.recent_trajectory.confidence == "low":
        if _CONFIDENCE_RANK[gv.confidence] > _CONFIDENCE_RANK["medium"]:
            gv = gv.model_copy(update={"confidence": "medium"})
        signals.append("layer3a_trajectory_confidence_low")

    # Floor 3: no-event + no providers + stale self-report → ≤ low
    if (
        mode == "no-event"
        and not layer3a_payload.data_density.connected_providers
        and layer3a_payload.data_density.self_report_freshness_days > 30
    ):
        if _CONFIDENCE_RANK[gv.confidence] > _CONFIDENCE_RANK["low"]:
            gv = gv.model_copy(update={"confidence": "low"})
        signals.append("no_providers_stale_self_report")

    # Floor 4: event-mode + no previous_attempts + first_time → ≤ medium
    if (
        mode == "event"
        and not previous_attempts
        and first_time_at_distance is True
    ):
        if _CONFIDENCE_RANK[gv.confidence] > _CONFIDENCE_RANK["medium"]:
            gv = gv.model_copy(update={"confidence": "medium"})
        signals.append("first_time_no_previous_attempts")

    observations = list(payload.notable_observations)
    if signals:
        # Dedup signals while preserving stable order
        unique_signals = sorted(set(signals))
        observations.append(
            Layer3Observation(
                category="data_gap",
                text=(
                    f"Confidence clamped by data signal: "
                    f"{', '.join(unique_signals)}."
                ),
                evidence_basis=[
                    "h2.first_time_at_distance",
                    "h2.previous_attempts",
                    "3a.recent_trajectory.confidence",
                    "3a.data_density.connected_providers",
                ],
                elevates_to_hitl=False,
            )
        )
        # Honor §8.2 observation budget cap (max_length=6) — keep highest priority
        observations = _trim_observations_to_budget(observations)

    return payload.model_copy(
        update={
            "goal_viability": gv,
            "notable_observations": observations,
        }
    )


def _trim_observations_to_budget(
    observations: list[Layer3Observation], max_items: int = _NOTABLE_OBSERVATIONS_MAX
) -> list[Layer3Observation]:
    """Per §8.2 — bound notable_observations to max_items via priority:
    warning > opportunity > data_gap > data_hygiene. Preserves order within
    category. Runs POST-validation (auto-emit additions); the pre-validation
    `_clamp_notable_observations` guards the raw-over-emit path."""
    if len(observations) <= max_items:
        return observations
    sorted_obs = sorted(
        enumerate(observations),
        key=lambda x: (_OBSERVATION_CATEGORY_PRIORITY.get(x[1].category, 9), x[0]),
    )
    kept = sorted([item[0] for item in sorted_obs[:max_items]])
    return [observations[i] for i in kept]


def _clamp_notable_observations(
    candidate: dict[str, Any], max_items: int = _NOTABLE_OBSERVATIONS_MAX
) -> None:
    """Trim `notable_observations` to the §8.2 budget in place BEFORE schema
    validation. The model field is `max_length`-bounded and the tool schema
    carries the matching `maxItems`, but the Anthropic API treats array bounds
    as guidance — an over-emit fails `Layer3BPayload` validation on both capped
    attempts and walls the cone (the twin of the 3A weak_links wall). The
    post-validation `_trim_observations_to_budget` cannot help — it never runs.
    Drop lowest-priority items (warning > opportunity > data_gap >
    data_hygiene; ties by emission order) so the surface degrades to the
    budget instead of walling."""
    obs = candidate.get("notable_observations")
    if not isinstance(obs, list) or len(obs) <= max_items:
        return
    ranked = sorted(
        enumerate(obs),
        key=lambda x: (
            _OBSERVATION_CATEGORY_PRIORITY.get(
                (x[1] or {}).get("category") if isinstance(x[1], dict) else None, 9
            ),
            x[0],
        ),
    )
    kept_idx = sorted(i for i, _ in ranked[:max_items])
    print(
        f"llm_layer3b_goal_timeline_viability: clamping notable_observations "
        f"from {len(obs)} to {max_items} (Layer3BPayload §8.2 budget)"
    )
    candidate["notable_observations"] = [obs[i] for i in kept_idx]


def _truncate_to_word_boundary(text: str, max_chars: int) -> str:
    """Cut `text` to <= `max_chars`, snapping to the last word boundary near the
    limit and appending a single-char ellipsis so it does not break mid-word."""
    cut = text[: max_chars - 1].rstrip()
    space = cut.rfind(" ")
    if space >= max_chars - 40:
        cut = cut[:space].rstrip()
    return cut + "…"


def _clamp_observation_text(
    candidate: dict[str, Any], max_chars: int = _OBSERVATION_TEXT_MAX_CHARS
) -> None:
    """Truncate each `notable_observations[i].text` to the schema cap in place
    before validation. `Layer3Observation.text` is `max_length=240` and the tool
    schema carries the matching `maxLength`, but the Anthropic API treats string
    bounds as guidance — a long observation fails `Layer3BPayload` validation and
    walls the cone (same per-string class as the 3A fix). Only the human-readable
    `text` is trimmed; category/evidence_basis/elevates_to_hitl are untouched, so
    HITL gating is unaffected."""
    obs = candidate.get("notable_observations")
    if not isinstance(obs, list):
        return
    for item in obs:
        if not isinstance(item, dict):
            continue
        text = item.get("text")
        if isinstance(text, str) and len(text) > max_chars:
            truncated = _truncate_to_word_boundary(text, max_chars)
            print(
                f"llm_layer3b_goal_timeline_viability: truncating a "
                f"notable_observations text from {len(text)} to "
                f"{len(truncated)} chars (Layer3Observation max_length={max_chars})"
            )
            item["text"] = truncated


# ─── Periodization-sanity loop (§5.5 step 4 + D13) ───────────────────────────


def _periodization_sum_target(
    *,
    mode: str,
    race_event_payload: RaceEventPayload | None,
    current_date: date,
    plan_duration_weeks: int | None,
) -> int | None:
    """Target sum for custom-mode phase_weeks. None when no comparable
    timeline exists (defensive — shouldn't fire under v1 validation)."""
    if mode == "event" and race_event_payload is not None:
        return _time_to_event_weeks(race_event_payload.event_date, current_date)
    if mode == "no-event" and plan_duration_weeks is not None:
        return plan_duration_weeks
    return None


def _check_periodization_sanity(
    payload: Layer3BPayload, target_weeks: int | None
) -> tuple[bool, int | None, str | None]:
    """Returns (passed, actual_sum, sum_kind). passed=False indicates a
    sanity violation requiring retry/fallback."""
    ps = payload.periodization_shape
    if ps.mode != "custom":
        return True, None, None
    if ps.phase_weeks is None:
        # Defense in depth — pydantic catches this earlier
        return False, 0, None
    # Custom weeks must put something in the phases at/after start_phase.
    # Layer 4's `_allocate_weeks_custom` drops earlier phases and raises if
    # nothing positive remains — and the total-sum check below can pass while
    # the post-start allocation is empty (weeks parked only in skipped
    # phases). Catch it here so the existing retry+fallback machinery rescues
    # it to a standard shape instead of letting it 500 in Layer 4.
    start_idx = _PERIODIZATION_PHASE_ORDER.index(ps.start_phase)
    weeks_at_or_after_start = sum(
        ps.phase_weeks.get(p, 0) for p in _PERIODIZATION_PHASE_ORDER[start_idx:]
    )
    if weeks_at_or_after_start <= 0:
        return False, weeks_at_or_after_start, None
    actual = sum(ps.phase_weeks.values())
    if target_weeks is None:
        return False, actual, None
    sum_kind = (
        "time_to_event_weeks" if target_weeks else "plan_duration_weeks"
    )
    if abs(actual - target_weeks) > 1:
        return False, actual, sum_kind
    return True, actual, sum_kind


def _periodization_fallback_to_standard(
    payload: Layer3BPayload, actual_sum: int, target_weeks: int | None
) -> Layer3BPayload:
    """Per §5.5 step 4 — rebuild payload with mode='standard' + phase_weeks=None.
    Preserves start_phase + reasoning_text. Appends `periodization_shape_fallback`
    observation (category=data_hygiene, elevates_to_hitl=False)."""
    ps = payload.periodization_shape
    new_ps = ps.model_copy(
        update={
            "mode": "standard",
            "phase_weeks": None,
            "reasoning_text": (
                ps.reasoning_text
                + " [Validator fallback: custom phase_weeks sum "
                + f"({actual_sum}) outside ±1 of "
                + f"{target_weeks if target_weeks is not None else 'target'} weeks]"
            ),
        }
    )
    observations = list(payload.notable_observations) + [
        Layer3Observation(
            category="data_hygiene",
            text=(
                f"Periodization shape fell back from custom to standard: "
                f"phase_weeks sum {actual_sum} vs target "
                f"{target_weeks if target_weeks is not None else '?'} weeks "
                "(±1 tolerance)."
            ),
            evidence_basis=["validator.periodization_sanity"],
            elevates_to_hitl=False,
        )
    ]
    observations = _trim_observations_to_budget(observations)
    return payload.model_copy(
        update={
            "periodization_shape": new_ps,
            "notable_observations": observations,
        }
    )


# ─── Prompt hash + driver entry point ────────────────────────────────────────


def _prompt_hash(system_prompt: str, user_prompt: str) -> str:
    return hashlib.sha256(
        (system_prompt + "||" + user_prompt).encode("utf-8")
    ).hexdigest()


def _assemble_payload_candidate(
    *,
    tool_args: dict[str, Any],
    user_id: int,
    current_date: date,
    model: str,
    temperature: float,
    prompt_hash: str,
    llm_out: _LLMOutput,
    etl_version_set: dict[str, str],
    race_event_payload: RaceEventPayload | None,
) -> dict[str, Any]:
    """Per D14 — driver populates D-66 event-metadata fields from
    race_event_payload (event-mode) or leaves all None (no-event-mode)."""
    candidate: dict[str, Any] = {
        **tool_args,
        "user_id": user_id,
        "as_of": datetime.combine(current_date, time_cls.min),
        "model": model,
        "temperature": temperature,
        "prompt_hash": prompt_hash,
        "latency_ms": llm_out.latency_ms,
        "input_tokens": llm_out.input_tokens,
        "output_tokens": llm_out.output_tokens,
        "etl_version_set": etl_version_set,
    }
    if race_event_payload is not None:
        candidate["event_date"] = race_event_payload.event_date
        candidate["event_locale_id"] = race_event_payload.event_locale_id
        candidate["race_format"] = race_event_payload.race_format
        candidate["time_to_event_weeks"] = _time_to_event_weeks(
            race_event_payload.event_date, current_date
        )
    return candidate


def llm_layer3b_goal_timeline_viability(
    user_id: int,
    layer1_payload: Layer1Payload,
    layer3a_payload: Layer3APayload,
    layer2a_payload: Layer2APayload,
    race_event_payload: RaceEventPayload | None,
    current_date: date,
    etl_version_set: dict[str, str],
    *,
    # §H.2 deployed-shape gap kwargs (D11 + L3B-P-2) — None-tolerant in v1
    goal_outcome: str | None = None,
    time_goal: str | None = None,
    first_time_at_distance: bool | None = None,
    previous_attempts: list[dict[str, Any]] | None = None,
    race_distance_km: float | None = None,
    race_duration_hr: float | None = None,
    race_terrain: list[str] | None = None,
    race_pack_weight_kg: float | None = None,
    # §H.3 (no-event-mode) — caller override; else from Layer1EventGoal
    plan_duration_weeks: int | None = None,
    non_event_goal_type: str | None = None,
    # Sampling knobs
    model: str = _DEFAULT_MODEL,
    temperature: float = _DEFAULT_TEMPERATURE,
    max_tokens: int = _DEFAULT_MAX_TOKENS,
    extended_thinking_budget: int = _DEFAULT_THINKING_BUDGET,
    llm_caller: LLMCaller | None = None,
) -> Layer3BPayload:
    """Per `Layer3_3B_Spec.md` §3 + §5 — single-call LLM driver for Layer 3B.

    Algorithm:
    1. `_validate_inputs(...)` — §4 preconditions → `Layer3BInputError`.
    2. `_render_user_prompt(...)` — §5.1 4-block prep.
    3. Up to 2 attempts on schema violation (§5.5 step 1).
    4. Schema validation via `Layer3BPayload.model_validate`.
    5. Mode-discriminator enforcement (§5.5 step 2).
    6. `_check_evidence_basis(...)` — name-existence + mode-discriminator
       warn-log (§5.5 + D9).
    7. `_enforce_hitl_auto_emit(...)` — §6.1 missing-but-required items.
    8. `_apply_confidence_floors(...)` — §6.5 4 floor rules + auto-append.
    9. `_enforce_periodization_sanity_loop(...)` — §5.5 step 4 (single
       retry + fallback-to-standard on persistent failure).
    10. Stamp metadata + D14 event-metadata population + return.

    The `llm_caller` param is dependency-injectable for tests; production
    callers leave it None to use `_default_llm_caller`."""
    # Resolve no-event-mode fields from Layer1EventGoal if caller didn't override
    if race_event_payload is None:
        plan_duration_weeks = _resolve_plan_duration(layer1_payload, plan_duration_weeks)
        non_event_goal_type = _resolve_non_event_goal_type(
            layer1_payload, non_event_goal_type
        )

    _validate_inputs(
        layer1_payload,
        layer3a_payload,
        layer2a_payload,
        race_event_payload,
        current_date,
        etl_version_set,
        model,
        temperature,
        goal_outcome=goal_outcome,
        plan_duration_weeks=plan_duration_weeks,
        non_event_goal_type=non_event_goal_type,
    )

    mode = "event" if race_event_payload is not None else "no-event"
    caller: LLMCaller = llm_caller or _default_llm_caller
    tool_schema = build_emit_layer3b_payload_tool()
    prep_dict = _build_prep_dict(
        mode=mode,
        race_event_payload=race_event_payload,
        layer1_payload=layer1_payload,
        layer3a_payload=layer3a_payload,
        layer2a_payload=layer2a_payload,
        current_date=current_date,
        plan_duration_weeks=plan_duration_weeks,
        non_event_goal_type=non_event_goal_type,
        goal_outcome=goal_outcome,
        time_goal=time_goal,
        first_time_at_distance=first_time_at_distance,
        previous_attempts=previous_attempts,
        race_distance_km=race_distance_km,
        race_duration_hr=race_duration_hr,
        race_terrain=race_terrain,
        race_pack_weight_kg=race_pack_weight_kg,
    )

    last_validation_error: str | None = None
    llm_out: _LLMOutput | None = None
    validated_candidate: dict[str, Any] | None = None

    render_kwargs: dict[str, Any] = dict(
        mode=mode,
        race_event_payload=race_event_payload,
        layer1_payload=layer1_payload,
        layer3a_payload=layer3a_payload,
        layer2a_payload=layer2a_payload,
        current_date=current_date,
        plan_duration_weeks=plan_duration_weeks,
        non_event_goal_type=non_event_goal_type,
        goal_outcome=goal_outcome,
        time_goal=time_goal,
        first_time_at_distance=first_time_at_distance,
        previous_attempts=previous_attempts,
        race_distance_km=race_distance_km,
        race_duration_hr=race_duration_hr,
        race_terrain=race_terrain,
        race_pack_weight_kg=race_pack_weight_kg,
    )

    # §5.5 step 1: single capped retry on schema violation (max 2 attempts)
    for attempt in range(2):
        user_prompt = _render_user_prompt(
            **render_kwargs, retry_error=last_validation_error
        )
        llm_out = caller(
            _SYSTEM_PROMPT,
            user_prompt,
            tool_schema,
            model,
            temperature,
            max_tokens,
            extended_thinking_budget,
        )
        candidate = _assemble_payload_candidate(
            tool_args=llm_out.tool_args,
            user_id=user_id,
            current_date=current_date,
            model=model,
            temperature=temperature,
            prompt_hash=_prompt_hash(_SYSTEM_PROMPT, user_prompt),
            llm_out=llm_out,
            etl_version_set=etl_version_set,
            race_event_payload=race_event_payload,
        )
        # Honor the §8.2 budget + per-string cap deterministically before
        # validation so an over-emit degrades gracefully instead of walling on
        # schema_violation.
        _clamp_notable_observations(candidate)
        _clamp_observation_text(candidate)
        try:
            Layer3BPayload.model_validate(candidate)
            validated_candidate = candidate
            break
        except ValidationError as exc:
            last_validation_error = str(exc)
            if attempt == 1:
                raise Layer3BOutputError(
                    "schema_violation",
                    detail=last_validation_error,
                ) from exc

    assert validated_candidate is not None and llm_out is not None
    payload = Layer3BPayload.model_validate(validated_candidate)

    # §5.5 step 2: mode-discriminator enforcement (fail-hard, no retry)
    if payload.mode != mode:
        raise Layer3BOutputError(
            "mode_mismatch",
            detail=(
                f"LLM emitted mode={payload.mode!r} but caller is "
                f"mode={mode!r}"
            ),
        )

    # §5.5 step 5 / D9: evidence-basis cross-check (warn only)
    _check_evidence_basis(llm_out.tool_args, prep_dict, mode)

    # §5.5 step 3 / D12: HITL auto-emit
    payload = _enforce_hitl_auto_emit(
        payload,
        mode=mode,
        race_event_payload=race_event_payload,
        layer3a_payload=layer3a_payload,
        current_date=current_date,
        goal_outcome=goal_outcome,
        first_time_at_distance=first_time_at_distance,
        previous_attempts=previous_attempts,
    )

    # §6.5 / D8: confidence-floor clamp
    payload = _apply_confidence_floors(
        payload,
        mode=mode,
        layer3a_payload=layer3a_payload,
        goal_outcome=goal_outcome,
        first_time_at_distance=first_time_at_distance,
        previous_attempts=previous_attempts,
    )

    # §5.5 step 4 / D13: periodization-sanity loop (single retry + fallback)
    target_weeks = _periodization_sum_target(
        mode=mode,
        race_event_payload=race_event_payload,
        current_date=current_date,
        plan_duration_weeks=plan_duration_weeks,
    )
    passed, actual_sum, sum_kind = _check_periodization_sanity(payload, target_weeks)
    if not passed:
        # Single retry with the periodization deviation error in the prompt
        deviation_msg = (
            f"Previous attempt's periodization_shape.mode=='custom' but "
            f"phase_weeks sums to {actual_sum} which is outside ±1 of "
            f"{target_weeks} ({sum_kind}). Re-emit with either (a) "
            f"mode=='custom' AND phase_weeks summing within ±1 of "
            f"{target_weeks}, OR (b) a non-custom mode "
            "('standard' / 'compressed' / 'extended') with phase_weeks=null."
        )
        try:
            retry_user_prompt = _render_user_prompt(
                **render_kwargs,
                retry_error=None,
                periodization_error=deviation_msg,
            )
            retry_out = caller(
                _SYSTEM_PROMPT,
                retry_user_prompt,
                tool_schema,
                model,
                temperature,
                max_tokens,
                extended_thinking_budget,
            )
            retry_candidate = _assemble_payload_candidate(
                tool_args=retry_out.tool_args,
                user_id=user_id,
                current_date=current_date,
                model=model,
                temperature=temperature,
                prompt_hash=_prompt_hash(_SYSTEM_PROMPT, retry_user_prompt),
                llm_out=retry_out,
                etl_version_set=etl_version_set,
                race_event_payload=race_event_payload,
            )
            _clamp_notable_observations(retry_candidate)
            _clamp_observation_text(retry_candidate)
            retry_payload = Layer3BPayload.model_validate(retry_candidate)
        except (ValidationError, Layer3BOutputError):
            retry_payload = None
        if retry_payload is not None and retry_payload.mode == mode:
            # Re-run downstream transforms on the retry payload
            retry_payload = _enforce_hitl_auto_emit(
                retry_payload,
                mode=mode,
                race_event_payload=race_event_payload,
                layer3a_payload=layer3a_payload,
                current_date=current_date,
                goal_outcome=goal_outcome,
                first_time_at_distance=first_time_at_distance,
                previous_attempts=previous_attempts,
            )
            retry_payload = _apply_confidence_floors(
                retry_payload,
                mode=mode,
                layer3a_payload=layer3a_payload,
                goal_outcome=goal_outcome,
                first_time_at_distance=first_time_at_distance,
                previous_attempts=previous_attempts,
            )
            r_passed, r_actual, _ = _check_periodization_sanity(
                retry_payload, target_weeks
            )
            if r_passed:
                payload = retry_payload
            else:
                payload = _periodization_fallback_to_standard(
                    retry_payload, r_actual or 0, target_weeks
                )
        else:
            # Persistent failure: fallback-to-standard
            payload = _periodization_fallback_to_standard(
                payload, actual_sum or 0, target_weeks
            )

    return payload


__all__ = [
    "Layer3BEvidenceBasisWarning",
    "Layer3BInputError",
    "Layer3BOutputError",
    "LLMCaller",
    "build_emit_layer3b_payload_tool",
    "llm_layer3b_goal_timeline_viability",
]
