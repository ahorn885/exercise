"""Layer 3A — Athlete State Evaluation driver per `Layer3_3A_Spec.md` §3.

Single LLM call orchestrator. Wraps:

1. `_validate_inputs(...)` — §4 preconditions → `Layer3AInputError(code)`.
2. `_render_user_prompt(...)` — §5.1 prep transformations (8 sections).
3. `_default_llm_caller(...)` — Anthropic SDK extended-thinking + forced
   tool-use (`tool_choice={"type": "tool", "name": "record_athlete_state"}`).
4. Single capped retry on schema violation per §5.3 step 1.
5. `_check_evidence_basis(...)` — name-existence warn-log; no fail (§5.3 step 2).
6. `_apply_confidence_floors(...)` — §6.2 floor rules + high-confidence
   gate clamp + §6.3 `confidence_clamped_by_data_density` observation
   append.
7. Metadata stamping → final `Layer3APayload`.

Companion prompt body: `aidstation-sources/prompts/Layer3A_v1.md` (system
prompt rules + tool schema rationale + D1-D10 source decisions).

Integration substrate: `layer3a/integration.py` (5 `q_layer3A_*` accessors
+ `assemble_layer3a_integration_bundle`).
"""

from __future__ import annotations

import hashlib
import warnings
from dataclasses import dataclass
from datetime import date, datetime, timedelta, timezone
from typing import Any, Callable

from pydantic import ValidationError

from llm_invocation import ThinkingToolCallError, invoke_tool_call
from evidence_catalog import render_catalog_block as _render_evidence_catalog_block
from layer4.context import (
    ACWREntry,
    ACWRStatus,
    Assessment,
    CurrentState,
    DailyWellnessRecord,
    DataDensity,
    Layer1Payload,
    Layer2APayload,
    Layer3AIntegrationBundle,
    Layer3APayload,
    Layer3Observation,
    RecentTrajectory,
    TrajectoryWindow,
)

# ─── Errors (inlined per Step 4a + Layer 2C precedent) ───────────────────────


class Layer3AInputError(ValueError):
    """Raised when §4 input preconditions fail."""

    def __init__(self, code: str, *, detail: str | None = None) -> None:
        self.code = code
        self.detail = detail
        msg = f"Layer3A input error: {code}"
        if detail:
            msg = f"{msg} — {detail}"
        super().__init__(msg)


class Layer3AOutputError(RuntimeError):
    """Raised when the LLM output fails schema validation after the single
    capped retry per §5.3 step 1, OR when the SDK adapter cannot extract a
    `record_athlete_state` tool-use block."""

    def __init__(self, code: str, *, detail: str | None = None) -> None:
        self.code = code
        self.detail = detail
        msg = f"Layer3A output error: {code}"
        if detail:
            msg = f"{msg} — {detail}"
        super().__init__(msg)


class Layer3AEvidenceBasisWarning(UserWarning):
    """Surfaced when `evidence_basis` cites a field path not present in the
    rendered prep dict. Telemetry-only per §5.3 step 2."""


# ─── Constants ───────────────────────────────────────────────────────────────


_APPROVED_MODELS = frozenset({
    "claude-sonnet-4-6",
    "claude-sonnet-4-5",  # legacy default per Layer3_3A_Spec.md §3.3 pre-correction; kept for replay
    "claude-opus-4-7",
    "claude-haiku-4-5",
})

_TOOL_NAME = "record_athlete_state"

_CONFIDENCE_RANK = {"low": 0, "medium": 1, "high": 2}

_DEFAULT_MODEL = "claude-sonnet-4-6"
_DEFAULT_TEMPERATURE = 0.2
_DEFAULT_MAX_TOKENS = 4000
_DEFAULT_THINKING_BUDGET = 4000


# ─── LLM caller protocol (matches layer4/single_session.py shape) ────────────


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
    + max_tokens > budget_tokens). Failures map to `Layer3AOutputError` so the
    §5.3 error contract is preserved. Tests inject a stub instead."""
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
        raise Layer3AOutputError(exc.code, detail=exc.detail) from exc

    return _LLMOutput(
        tool_args=result.tool_args,
        input_tokens=result.input_tokens,
        output_tokens=result.output_tokens,
        latency_ms=result.latency_ms,
    )


# ─── Tool schema (full Layer3APayload mirror per D5) ─────────────────────────


# Mirrors `Layer3APayload.current_state.weak_links` `Field(max_length=5)` in
# `layer4/context.py`. Used both as the tool-schema `maxItems` hint and as the
# pre-validation clamp cap (`_clamp_weak_links`) — keep the three in lock-step.
_WEAK_LINKS_MAX_ITEMS = 5

# Mirrors `Layer3Observation.text` `Field(max_length=240)` in `layer4/context.py`
# and the tool-schema `maxLength` on `notable_observations[].text`. The Anthropic
# API treats string bounds as guidance, so a long observation walls the cone on
# `schema_violation` (the per-string twin of the weak_links over-emit); the
# pre-validation clamp (`_clamp_observation_text`) truncates to the cap instead.
_OBSERVATION_TEXT_MAX_CHARS = 240


_ASSESSMENT_SCHEMA = {
    "type": "object",
    "additionalProperties": False,
    "required": ["level", "confidence", "reasoning_text", "evidence_basis"],
    "properties": {
        "level": {
            "type": "string",
            "enum": ["low", "moderate", "good", "strong", "insufficient_data"],
        },
        "confidence": {"type": "string", "enum": ["high", "medium", "low"]},
        "reasoning_text": {"type": "string"},
        "evidence_basis": {"type": "array", "items": {"type": "string"}},
    },
}

_TRAJECTORY_WINDOW_SCHEMA = {
    "type": "object",
    "additionalProperties": False,
    "required": ["direction", "reasoning_text", "evidence_basis"],
    "properties": {
        "direction": {
            "type": "string",
            "enum": [
                "overreached",
                "fatigued",
                "recovered",
                "steady",
                "building",
                "detrained",
                "peaking",
                "insufficient_data",
            ],
        },
        "reasoning_text": {"type": "string"},
        "evidence_basis": {"type": "array", "items": {"type": "string"}},
    },
}

_ACWR_ENTRY_SCHEMA = {
    "type": "object",
    "additionalProperties": False,
    "required": ["acute_load", "chronic_load", "ratio", "zone", "units"],
    "properties": {
        "acute_load": {"type": "number", "minimum": 0},
        "chronic_load": {"type": "number", "minimum": 0},
        "ratio": {"type": "number", "minimum": 0},
        "zone": {
            "type": "string",
            "enum": [
                "undertraining",
                "sweet_spot",
                "functional_overreach",
                "non_functional_overreach",
                "detraining",
            ],
        },
        "units": {"type": "string"},
    },
}


def build_record_athlete_state_tool() -> dict[str, Any]:
    """Tool schema mirroring `Layer3APayload` per D5 (full payload-contract
    mirror, Step 4a Option 2 precedent). Metadata fields (`user_id`, `as_of`,
    `model`, `temperature`, `prompt_hash`, `latency_ms`, `*_tokens`,
    `etl_version_set`) are stamped by the driver post-hoc — NOT in the tool
    schema."""
    return {
        "name": _TOOL_NAME,
        "description": (
            "Emit the structured athlete-state evaluation. Required. The "
            "Layer3APayload contract is mirrored verbatim sans driver-stamped "
            "metadata (user_id, as_of, model, temperature, prompt_hash, "
            "latency_ms, *_tokens, etl_version_set)."
        ),
        "input_schema": {
            "type": "object",
            "additionalProperties": False,
            "required": [
                "current_state",
                "recent_trajectory",
                "data_density",
                "notable_observations",
            ],
            "properties": {
                "current_state": {
                    "type": "object",
                    "additionalProperties": False,
                    "required": [
                        "aerobic_capacity",
                        "strength",
                        "weak_links",
                        "skill_assessments",
                    ],
                    "properties": {
                        "aerobic_capacity": _ASSESSMENT_SCHEMA,
                        "strength": _ASSESSMENT_SCHEMA,
                        "weak_links": {
                            "type": "array",
                            "maxItems": _WEAK_LINKS_MAX_ITEMS,
                            "items": {"type": "string"},
                        },
                        "skill_assessments": {
                            "type": "object",
                            "additionalProperties": _ASSESSMENT_SCHEMA,
                        },
                        "body_composition_notes": {"type": ["string", "null"]},
                    },
                },
                "recent_trajectory": {
                    "type": "object",
                    "additionalProperties": False,
                    "required": ["short_term", "medium_term", "acwr_status", "confidence"],
                    "properties": {
                        "short_term": _TRAJECTORY_WINDOW_SCHEMA,
                        "medium_term": _TRAJECTORY_WINDOW_SCHEMA,
                        "acwr_status": {
                            "type": "object",
                            "additionalProperties": False,
                            "required": ["per_discipline", "combined"],
                            "properties": {
                                "per_discipline": {
                                    "type": "object",
                                    "additionalProperties": _ACWR_ENTRY_SCHEMA,
                                },
                                "combined": {
                                    "anyOf": [_ACWR_ENTRY_SCHEMA, {"type": "null"}],
                                },
                            },
                        },
                        "confidence": {
                            "type": "string",
                            "enum": ["high", "medium", "low"],
                        },
                    },
                },
                "data_density": {
                    "type": "object",
                    "additionalProperties": False,
                    "required": [
                        "connected_providers",
                        "integration_data_days",
                        "recent_workouts_count",
                        "recent_sleep_count",
                        "recent_hrv_count",
                        "self_report_freshness_days",
                        "section_completeness",
                    ],
                    "properties": {
                        "connected_providers": {
                            "type": "array",
                            "items": {"type": "string"},
                        },
                        "integration_data_days": {"type": "integer", "minimum": 0},
                        "recent_workouts_count": {"type": "integer", "minimum": 0},
                        "recent_sleep_count": {"type": "integer", "minimum": 0},
                        "recent_hrv_count": {"type": "integer", "minimum": 0},
                        "self_report_freshness_days": {"type": "integer", "minimum": 0},
                        "section_completeness": {
                            "type": "object",
                            "additionalProperties": {
                                "type": "number",
                                "minimum": 0,
                                "maximum": 1,
                            },
                        },
                    },
                },
                "notable_observations": {
                    "type": "array",
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
                # #826 — curated research/coaching sources the state assessment
                # rests on. Slugs from the provided research-source catalog
                # ONLY (constrained-citation). Optional: omit / empty when no
                # catalog source applies.
                "source_citations": {
                    "type": "array",
                    "items": {"type": "string"},
                },
            },
        },
    }


# ─── Input validation (§4) ───────────────────────────────────────────────────


def _validate_inputs(
    layer1_payload: Layer1Payload | None,
    layer2a_payload: Layer2APayload | None,
    integration_bundle: Layer3AIntegrationBundle | None,
    as_of: datetime | None,
    etl_version_set: dict[str, str] | None,
    model: str,
    temperature: float,
) -> None:
    """Per `Layer3_3A_Spec.md` §4. Raises `Layer3AInputError(code)` on the
    first failure with a spec-named error code."""
    if layer1_payload is None:
        raise Layer3AInputError("missing_layer1")
    if layer1_payload.identity is None:
        raise Layer3AInputError(
            "incomplete_onboarding", detail="Layer1Payload.identity is None"
        )
    # #447 — do NOT require a profile `primary_sport`. The planning sport now
    # comes from the target race (PlanGen_Planning_Sport_Spec_v1 §3), so a
    # race-tier plan must build even when the athlete left primary_sport blank.
    # The real "do we have a sport to plan" gate is the non-empty 2A discipline
    # set below; `primary_sport` is only home-discipline context downstream and
    # renders as "unspecified" when None.
    if layer2a_payload is None:
        raise Layer3AInputError("missing_2a")
    if not layer2a_payload.disciplines:
        raise Layer3AInputError(
            "missing_2a", detail="layer2a_payload.disciplines is empty"
        )
    if integration_bundle is None:
        raise Layer3AInputError("missing_integration_bundle")
    if as_of is None:
        raise Layer3AInputError("invalid_as_of", detail="as_of is None")
    now = datetime.now(timezone.utc) if as_of.tzinfo else datetime.now()
    if as_of > now + timedelta(hours=1):
        raise Layer3AInputError(
            "invalid_as_of",
            detail=f"as_of={as_of.isoformat()} is more than 1h in the future",
        )
    if not etl_version_set:
        raise Layer3AInputError("missing_etl_pin")
    if model not in _APPROVED_MODELS:
        raise Layer3AInputError("unapproved_model", detail=f"model={model!r}")
    if not (0.0 <= temperature <= 1.0):
        raise Layer3AInputError("invalid_temp", detail=f"temperature={temperature!r}")


# ─── Prep dict + user-prompt rendering (§5.1) ────────────────────────────────


def _compute_age(
    dob: date | None, as_of: datetime | None
) -> int | None:
    if dob is None or as_of is None:
        return None
    anchor = as_of.date() if isinstance(as_of, datetime) else as_of
    years = anchor.year - dob.year - (
        (anchor.month, anchor.day) < (dob.month, dob.day)
    )
    return max(years, 0)


def _render_demographics(layer1_payload: Layer1Payload, as_of: datetime) -> str:
    identity = layer1_payload.identity
    perf = layer1_payload.performance
    age = _compute_age(identity.date_of_birth, as_of)
    parts = [
        f"age {age if age is not None else 'unknown'}",
        f"sex {identity.sex or 'unspecified'}",
    ]
    if identity.height_cm is not None:
        parts.append(f"height {identity.height_cm:.0f}cm")
    if perf and perf.body_weight_kg is not None:
        parts.append(f"weight {perf.body_weight_kg:.1f}kg")
    yst = layer1_payload.training_history.years_structured_training
    if yst is not None:
        parts.append(f"{yst}y structured training")
    return ", ".join(parts) + "."


def _render_training_history(layer1_payload: Layer1Payload) -> str:
    th = layer1_payload.training_history
    primary = layer1_payload.identity.primary_sport or "unspecified"
    lines = [f"- primary_sport: {primary}"]
    if th.years_structured_training is not None:
        lines.append(f"- years_structured_training: {th.years_structured_training}")
    if th.peak_weekly_volume_hrs is not None:
        py = f" ({th.peak_weekly_volume_year})" if th.peak_weekly_volume_year else ""
        lines.append(f"- peak_weekly_volume_hrs: {th.peak_weekly_volume_hrs:.1f}{py}")
    if th.longest_event_completed:
        lines.append(f"- longest_event_completed: {th.longest_event_completed}")
    if th.training_consistency_disrupted_weeks is not None:
        cause = f" ({th.training_consistency_cause})" if th.training_consistency_cause else ""
        lines.append(
            f"- training_consistency_disrupted_weeks: {th.training_consistency_disrupted_weeks}{cause}"
        )
    if th.secondary_sports:
        names = ", ".join(f"{s.sport_slug}[{s.experience_tier}]" for s in th.secondary_sports)
        lines.append(f"- secondary_sports: {names}")
    if th.recent_race_results:
        race_lines = []
        for r in sorted(th.recent_race_results, key=lambda x: x.event_date, reverse=True)[:5]:
            race_lines.append(f"  - {r.event_date} {r.event_name}")
        lines.append("- recent_race_results (top 5 by date):")
        lines.extend(race_lines)
    return "\n".join(lines) if len(lines) > 1 else lines[0] + "\n- (no further data)"


def _render_discipline_baselines(
    layer1_payload: Layer1Payload, layer2a_payload: Layer2APayload
) -> str:
    """Per §5.1 step 3 — only disciplines with inclusion='included' from 2A."""
    included = {d.discipline_id for d in layer2a_payload.disciplines if d.inclusion == "included"}
    bl = layer1_payload.discipline_baselines
    if bl is None:
        return "(no discipline baselines reported)"
    blocks: list[str] = []

    def _maybe(name: str, model: Any, when: bool) -> None:
        if not when or model is None:
            return
        populated = {
            k: v
            for k, v in model.model_dump().items()
            if v not in (None, [], "")
        }
        if not populated:
            return
        bullets = "\n".join(f"  - {k}: {v}" for k, v in populated.items())
        blocks.append(f"- {name}:\n{bullets}")

    _maybe("running", bl.running, any("run" in d.lower() for d in included))
    _maybe("cycling", bl.cycling, any("cycl" in d.lower() or "bike" in d.lower() for d in included))
    _maybe("swimming", bl.swimming, any("swim" in d.lower() for d in included))
    _maybe("paddling", bl.paddling, any("paddl" in d.lower() or "kayak" in d.lower() for d in included))
    _maybe("skiing", bl.skiing, any("ski" in d.lower() for d in included))
    _maybe("navigation", bl.navigation, any("nav" in d.lower() or "ar" in d.lower() for d in included))
    _maybe("technical", bl.technical, any("climb" in d.lower() or "tech" in d.lower() for d in included))
    return "\n".join(blocks) if blocks else "(no included-discipline baselines populated)"


def _render_strength(layer1_payload: Layer1Payload) -> str:
    e = layer1_payload.strength_benchmarks
    if e is None:
        return "(no strength benchmarks recorded)"
    lines = []
    for k, v in e.model_dump().items():
        if k == "last_tested_at":
            continue
        label = v if v is not None else "not tested"
        lines.append(f"- {k}: {label}")
    if e.last_tested_at is not None:
        lines.append(f"- last_tested_at: {e.last_tested_at.isoformat()}")
    return "\n".join(lines)


def _render_performance(layer1_payload: Layer1Payload, as_of: datetime) -> str:
    p = layer1_payload.performance
    if p is None:
        return "(no performance baselines recorded)"
    anchor = as_of.date() if isinstance(as_of, datetime) else as_of

    def _age_tag(d: date | None) -> str:
        if d is None:
            return ""
        days = (anchor - d).days
        if days > 365:
            return f" (test_date={d.isoformat()}, stale: {days // 30}mo old)"
        return f" (test_date={d.isoformat()})"

    lines = []
    if p.hrmax_bpm is not None:
        src = f" [source={p.hrmax_source}]" if p.hrmax_source else ""
        lines.append(f"- hrmax_bpm: {p.hrmax_bpm}{src}")
    if p.lactate_threshold_hr_bpm is not None:
        method = f" [method={p.lt_method}]" if p.lt_method else ""
        lines.append(f"- lactate_threshold_hr_bpm: {p.lactate_threshold_hr_bpm}{method}")
    if p.vo2max is not None:
        src = f" [source={p.vo2max_source}]" if p.vo2max_source else ""
        lines.append(f"- vo2max: {p.vo2max}{src}")
    if p.cycling_ftp_w is not None:
        lines.append(f"- cycling_ftp_w: {p.cycling_ftp_w}{_age_tag(p.cycling_ftp_test_date)}")
    if p.running_threshold_pace_sec_per_km is not None:
        lines.append(
            f"- running_threshold_pace_sec_per_km: {p.running_threshold_pace_sec_per_km}"
            f"{_age_tag(p.running_threshold_test_date)}"
        )
    if p.css_swim_sec_per_100m is not None:
        lines.append(
            f"- css_swim_sec_per_100m: {p.css_swim_sec_per_100m}{_age_tag(p.css_test_date)}"
        )
    return "\n".join(lines) if lines else "(no performance baselines populated)"


def _render_lifestyle(layer1_payload: Layer1Payload) -> str:
    li = layer1_payload.lifestyle
    if li is None:
        return "(no lifestyle data recorded)"
    lines = []
    if li.sleep_baseline_hours is not None:
        lines.append(f"- sleep_baseline_hours: {li.sleep_baseline_hours:.1f}")
    if li.work_stress_level:
        lines.append(f"- work_stress_level: {li.work_stress_level}")
    if li.dietary_pattern:
        lines.append(f"- dietary_pattern: {', '.join(li.dietary_pattern)}")
    if li.supplement_protocol_notes:
        lines.append(f"- supplement_protocol_notes: {li.supplement_protocol_notes}")
    if li.caffeine_tolerance:
        strategy = f" [race_day={li.caffeine_race_day_strategy}]" if li.caffeine_race_day_strategy else ""
        lines.append(f"- caffeine_tolerance: {li.caffeine_tolerance}{strategy}")
    if li.altitude_acclimatization_history is not None:
        ah = "yes" if li.altitude_acclimatization_history else "no"
        extras = []
        if li.altitude_max_exposure_m:
            extras.append(f"max_m={li.altitude_max_exposure_m}")
        if li.altitude_exposure_count:
            extras.append(f"exposures={li.altitude_exposure_count}")
        detail = f" ({', '.join(extras)})" if extras else ""
        lines.append(f"- altitude_acclimatization_history: {ah}{detail}")
    if li.salt_electrolyte_tolerance:
        lines.append(f"- salt_electrolyte_tolerance: {li.salt_electrolyte_tolerance}")
    return "\n".join(lines) if lines else "(no lifestyle fields populated)"


def _render_wellness_metric(
    records: list[DailyWellnessRecord],
    label: str,
    value_attr: str,
    source_attr: str,
    num_fmt: str,
    count_label: str,
) -> str | None:
    """One `recent_wellness` metric line: latest value + provenance + window
    average + populated-day count. Returns None when no day carries the metric
    (suppress-on-empty) so a sleep-only provider doesn't print a bare
    `resting_hr` line."""
    populated = sorted(
        (r for r in records if getattr(r, value_attr) is not None),
        key=lambda r: r.date,
    )
    if not populated:
        return None
    latest = populated[-1]
    avg = sum(getattr(r, value_attr) for r in populated) / len(populated)
    return (
        f"  - {label}: latest={num_fmt.format(getattr(latest, value_attr))} "
        f"({getattr(latest, source_attr)}, {latest.date})  "
        f"14d-avg={num_fmt.format(avg)}  {count_label}={len(populated)}"
    )


def _render_integration_summary(bundle: Layer3AIntegrationBundle) -> str:
    lines = []

    # recent_workouts
    rw = bundle.recent_workouts
    if rw:
        sources: dict[str, int] = {}
        for w in rw:
            sources[w.source] = sources.get(w.source, 0) + 1
        breakdown = ", ".join(f"{k}:{v}" for k, v in sorted(sources.items()))
        first, last = min(w.date for w in rw), max(w.date for w in rw)
        lines.append(
            f"- recent_workouts: count={len(rw)} range=[{first}, {last}] sources={{{breakdown}}}"
        )
    else:
        lines.append("- recent_workouts: count=0")

    # recent_wellness — device sources coalesced per-field with provenance.
    rw_well = bundle.recent_wellness
    if rw_well:
        first, last = min(r.date for r in rw_well), max(r.date for r in rw_well)
        lines.append(f"- recent_wellness: count={len(rw_well)} range=[{first}, {last}]")
        lines.append(
            "    (one row/day; device sources coalesced per-field, "
            "freshest-non-null; provenance in parens)"
        )
        for metric_line in (
            _render_wellness_metric(
                rw_well, "sleep_hours", "total_sleep_hours",
                "total_sleep_hours_source", "{:.1f}", "nights",
            ),
            _render_wellness_metric(
                rw_well, "hrv_rmssd_ms", "hrv_rmssd_ms",
                "hrv_rmssd_ms_source", "{:.0f}", "nights",
            ),
            _render_wellness_metric(
                rw_well, "resting_hr", "resting_hr",
                "resting_hr_source", "{:.0f}", "days",
            ),
        ):
            if metric_line is not None:
                lines.append(metric_line)
    else:
        lines.append("- recent_wellness: count=0")

    # self_report_sleep — kept separate from the device coalesce so §6.1 can
    # weigh subjective sleep_quality / self-reported hours against device data.
    sr = bundle.recent_self_report_sleep
    if sr:
        first, last = min(s.date for s in sr), max(s.date for s in sr)
        latest = max(sr, key=lambda s: s.date)
        parts = []
        if latest.total_sleep_hours is not None:
            parts.append(f"latest_hours={latest.total_sleep_hours:.1f}")
        if latest.sleep_quality is not None:
            parts.append(f"latest_quality={latest.sleep_quality}/10")
        detail = ("  " + " ".join(parts)) if parts else ""
        lines.append(
            f"- self_report_sleep: count={len(sr)} range=[{first}, {last}]{detail}"
        )
    else:
        lines.append("- self_report_sleep: count=0")

    # combined_load
    cl = bundle.combined_load
    if cl.combined is not None:
        c = cl.combined
        lines.append(
            f"- combined_load.combined: acute={c.acute_load:.1f} "
            f"chronic={c.chronic_load:.1f} ratio={c.ratio:.2f} "
            f"zone={c.zone} units={cl.units}"
        )
    else:
        lines.append("- combined_load.combined: None (no signal)")
    for disc_id, entry in sorted(cl.per_discipline.items()):
        lines.append(
            f"  - per_discipline[{disc_id}]: acute={entry.acute_load:.1f} "
            f"chronic={entry.chronic_load:.1f} ratio={entry.ratio:.2f} zone={entry.zone}"
        )
    if cl.polar_cross_ref is not None:
        pcr = cl.polar_cross_ref
        lines.append(
            f"- polar_cross_ref: daily_load={pcr.daily_load} acute={pcr.acute_load} "
            f"chronic={pcr.chronic_load} status={pcr.cardio_load_status}"
        )

    # connected_providers
    if bundle.connected_providers:
        for ps in bundle.connected_providers:
            ls = ps.last_sync.isoformat() if ps.last_sync else "never"
            cov = (
                f"w={'Y' if ps.has_recent_workouts else 'N'} "
                f"s={'Y' if ps.has_recent_sleep else 'N'} "
                f"hrv={'Y' if ps.has_recent_hrv else 'N'}"
            )
            lines.append(
                f"- provider[{ps.provider}]: status={ps.status} last_sync={ls} coverage=[{cov}]"
            )
    else:
        lines.append("- connected_providers: none")

    return "\n".join(lines)


def _render_phase_context(layer2a_payload: Layer2APayload) -> str:
    included = [d for d in layer2a_payload.disciplines if d.inclusion == "included"]
    lines = [f"- framework_sport: {layer2a_payload.framework_sport}"]
    if included:
        lines.append("- included disciplines (id, role, load_weight):")
        for d in included:
            lw = d.load_weight.value if d.load_weight else None
            lw_str = f"{lw:.2f}" if isinstance(lw, (int, float)) else "n/a"
            lines.append(f"  - {d.discipline_id} {d.discipline_name} [{d.role}] weight={lw_str}")
    return "\n".join(lines)


def _render_health_context_note(layer1_payload: Layer1Payload) -> str:
    """Per §5.2 — threaded health context for coloring the strength / state
    assessment. Active injuries are the hard constraint; resolved injuries,
    past/active conditions, and medication classes are threaded in as
    background so the assessment accounts for history (return-to-load,
    flare-aware load, HR-affecting meds). Injury-risk *verdicts* remain Layer
    2D's territory. Pregnancy NEVER mentioned (not in the captured vocab)."""
    hs = layer1_payload.health_status
    if hs is None:
        return "(no health context recorded)"

    def _inj(inj) -> str:
        bp = inj.body_part or "unspecified"
        sev = inj.severity or "unspecified"
        mc = (
            "; constraints: " + ", ".join(inj.movement_constraints)
            if inj.movement_constraints
            else ""
        )
        return f"{bp} ({sev}){mc}"

    def _cond(c) -> str:
        nm = c.condition_name or c.system_category
        return f"{nm} (severity {c.severity})" if c.severity else nm

    lines: list[str] = []
    if hs.current_injuries:
        lines.append(
            "Active injuries: "
            + " | ".join(_inj(i) for i in hs.current_injuries[:3])
            + "."
        )
    if hs.injury_history:
        lines.append(
            "Prior (resolved) injuries: "
            + " | ".join(_inj(i) for i in hs.injury_history[:3])
            + "."
        )
    cond_parts: list[str] = []
    if hs.health_conditions_active:
        cond_parts.append(
            "active: " + ", ".join(_cond(c) for c in hs.health_conditions_active[:4])
        )
    if hs.health_conditions_history:
        cond_parts.append(
            "prior: " + ", ".join(_cond(c) for c in hs.health_conditions_history[:4])
        )
    if cond_parts:
        lines.append("Health conditions — " + "; ".join(cond_parts) + ".")
    med_parts: list[str] = []
    if hs.medications_active:
        med_parts.append(
            "current: " + ", ".join(m.medication_class for m in hs.medications_active[:4])
        )
    if hs.medications_history:
        med_parts.append(
            "past: " + ", ".join(m.medication_class for m in hs.medications_history[:4])
        )
    if med_parts:
        lines.append("Medications — " + "; ".join(med_parts) + ".")

    if not lines:
        return "(no health context recorded)"
    lines.append(
        "Color the strength/state assessment accordingly; do not produce "
        "injury-risk judgments (Layer 2D's territory)."
    )
    return " ".join(lines)


def _build_prep_dict(
    layer1_payload: Layer1Payload,
    layer2a_payload: Layer2APayload,
    integration_bundle: Layer3AIntegrationBundle,
    as_of: datetime,
) -> dict[str, Any]:
    """Flat dict keyed by `section.field` paths. Used by the evidence-basis
    cross-check to verify the LLM cites real field names."""
    identity = layer1_payload.identity
    th = layer1_payload.training_history
    perf = layer1_payload.performance
    life = layer1_payload.lifestyle
    se = layer1_payload.strength_benchmarks

    d: dict[str, Any] = {
        "section_a.age": _compute_age(identity.date_of_birth, as_of),
        "section_a.sex": identity.sex,
        "section_a.height_cm": identity.height_cm,
        "section_a.primary_sport": identity.primary_sport,
        "section_b.current_injuries_count": len(
            layer1_payload.health_status.current_injuries
        )
        if layer1_payload.health_status
        else 0,
        "section_b.resting_hr_bpm": (
            layer1_payload.health_status.resting_hr_bpm
            if layer1_payload.health_status
            else None
        ),
        "section_c.years_structured_training": th.years_structured_training,
        "section_c.peak_weekly_volume_hrs": th.peak_weekly_volume_hrs,
        "section_c.longest_event_completed": th.longest_event_completed,
        "section_c.training_consistency_disrupted_weeks": th.training_consistency_disrupted_weeks,
        "section_c.recent_race_results_count": len(th.recent_race_results),
    }
    if perf is not None:
        d["section_f.body_weight_kg"] = perf.body_weight_kg
        d["section_f.hrmax_bpm"] = perf.hrmax_bpm
        d["section_f.hrmax_source"] = perf.hrmax_source
        d["section_f.lactate_threshold_hr_bpm"] = perf.lactate_threshold_hr_bpm
        d["section_f.vo2max"] = perf.vo2max
        d["section_f.cycling_ftp_w"] = perf.cycling_ftp_w
        d["section_f.cycling_ftp_test_date"] = perf.cycling_ftp_test_date
        d["section_f.running_threshold_pace_sec_per_km"] = perf.running_threshold_pace_sec_per_km
        d["section_f.running_threshold_test_date"] = perf.running_threshold_test_date
        d["section_f.css_swim_sec_per_100m"] = perf.css_swim_sec_per_100m
        d["section_f.css_test_date"] = perf.css_test_date
    if se is not None:
        for k, v in se.model_dump().items():
            d[f"section_e.{k}"] = v
    if life is not None:
        for k, v in life.model_dump().items():
            d[f"section_i.{k}"] = v
    d["integration.recent_workouts"] = len(integration_bundle.recent_workouts)
    d["integration.recent_wellness"] = len(integration_bundle.recent_wellness)
    d["integration.recent_self_report_sleep"] = len(
        integration_bundle.recent_self_report_sleep
    )
    d["integration.combined_load"] = integration_bundle.combined_load
    d["integration.connected_providers"] = [
        p.provider for p in integration_bundle.connected_providers
    ]
    d["layer2a.framework_sport"] = layer2a_payload.framework_sport
    d["layer2a.disciplines"] = [dx.discipline_id for dx in layer2a_payload.disciplines]
    return d


# NOTE: editing this prompt body can shift the Layer 3D gate verdict for a plan
# parked at the review screen. Bump `LAYER3_GATE_PROMPT_REVISION` in
# layer4/hashing.py when you change it, so the staleness fingerprint
# (`compute_gate_input_fingerprint`) re-fires a parked plan against the new
# prompt — the raw-input fingerprint can't see a prompt redeploy on its own (#213).
_SYSTEM_PROMPT = """You are evaluating an endurance athlete's current state. Your role is the
internal coaching analyst — direct, evidence-grounded, no platitudes. You
read the athlete's profile and recent training/recovery data, then emit a
structured judgment via the `record_athlete_state` tool. You cannot return
free-form text outside the tool call.

Hard rules:

1. Ground every assessment in specific evidence from the input. Cite the
   field name(s) in `reasoning_text` and list them in `evidence_basis`
   (e.g., "section_c.years_structured_training",
   "integration.recent_workouts").

2. Never invent data. If a field is "not tested" or missing, treat it as
   absent — do not extrapolate from peer fields. Use
   `level: insufficient_data` with `reasoning_text` explaining what was
   missing rather than guessing.

3. Distinguish current_state (where the athlete is RIGHT NOW) from
   recent_trajectory (where they are MOVING). Both are required.
   short_term and medium_term trajectory may differ — "fatigued
   (short-term)" with "building (medium-term)" is a normal hard-block
   signal, not a contradiction.

4. Weighting rules when self-report and integration data disagree:
   - Objective metrics (volume, HR averages, sleep duration, resting HR,
     HRV, vertical): integration data dominates. Self-report is
     sanity-check only. Flag >25% divergence as a `data_hygiene`
     observation. Device wellness (`integration.recent_wellness`) is
     coalesced per-field across providers (freshest-non-null); each metric's
     winning source is tagged in parens — cite it when a value drives an
     assessment.
   - Subjective metrics (perceived stress, motivation, sleep quality
     felt): self-report dominates. Integration may inform agreement but
     cannot override.
   - Hybrid metrics (sleep duration + quality, recovery, readiness):
     synthesize. Disagreement is itself a signal worth flagging.
   - Skill / experience: self-report only, bounded by recency-of-claim.
   - Calibration tests + performance tests: self-report-with-date; stale
     baselines (>12 months) reduce confidence.

5. Confidence calibration:
   - `high` requires ALL of: ≥1 connected provider with active data in
     last 14d, ≥10 logged workouts in last 28d, §C self-report present
     and not in conflict with integration, §F baselines present and not
     stale, §I sleep self-report present, AND for the specific assessment
     field ≥3 evidence_basis citations.
   - `medium` is the safe default.
   - `low` requires explicit data-gap reasoning.
   The validator post-clamps `high` to `medium` when any of the above
   gates fail — be conservative.

6. Emit `notable_observations` only when they would change a downstream
   decision. Do not narrate. Keep each observation's `text` under 240
   characters — one concise flag, not a paragraph (it is hard-capped at
   240 and truncated past that). Required observation triggers:
   - ACWR ratio >1.5 in any discipline OR combined → warning,
     elevates_to_hitl=true.
   - ACWR ratio <0.5 in any discipline AND athlete in build/peak phase
     → warning, elevates_to_hitl=true.
   - Self-report vs integration volume diverges >25% → data_hygiene,
     elevates_to_hitl=true.
   - Sleep self-report <6h AND no integration sleep data → warning,
     elevates_to_hitl=false.
   - connected_providers count == 0 AND athlete in peak phase →
     data_gap, elevates_to_hitl=true.
   - Performance baseline (§F) test date >12 months → data_gap,
     elevates_to_hitl=false.
   - Strength benchmark (§E) entirely absent → data_gap,
     elevates_to_hitl=true.
   - Just-onboarded (years_structured_training=0 AND recent_workouts<5)
     → data_gap, elevates_to_hitl=false.
   - HRV crash (recent 7-day HRV avg <70% of 28-day avg) → warning,
     elevates_to_hitl=true.

7. Forbidden observations (never emit):
   - Generic encouragement ("you're doing great", "keep it up").
   - Goal viability statements ("your sub-3 marathon goal is realistic")
     — that's Layer 3B's territory.
   - Injury-risk statements — that's Layer 2D's territory.
   - Exercise prescriptions — that's Layer 4.
   - Speculation beyond evidence.

8. Observation ordering: return in priority order, highest first —
   (a) warning + elevates_to_hitl=true, (b) data_gap +
   elevates_to_hitl=true, (c) warning + elevates_to_hitl=false,
   (d) data_hygiene + elevates_to_hitl=true, (e) everything else.

9. `weak_links` is bounded to 5 items max, ordered MOST-LIMITING FIRST —
   the list is truncated to the first 5, so lead with the weaknesses that
   most constrain training. Short phrases (e.g., "single-leg balance",
   "shoulder press strength"). Layer 4 consumes these for accessory
   programming.

10. `body_composition_notes` is optional. Emit ONLY when a relevant
    signal exists. Do not pad.

11. ACWR `combined.units` MUST be "hours" (substrate normalizes to hours
    from cardio_log durations).

12. Research-source citations (`source_citations`): a catalog of curated
    training-science sources is provided below. When your state assessment
    rests on the principle in one of them (e.g. citing the aerobic-base or
    detraining literature for an aerobic-capacity call), list its `slug` in
    the top-level `source_citations` array. Cite ONLY slugs that appear in the
    provided catalog — never invent a slug. Cite only what genuinely applies
    (typically 0–3); an empty array is fine. This is separate from
    `evidence_basis` (which cites the athlete's own input fields).

Voice: direct endurance-coaching-analyst voice. Match the cadence of a
real coach scanning a profile. No fluff, no marketing tone. If the data
is sparse, say so; do not perform certainty you don't have."""


def _render_user_prompt(
    layer1_payload: Layer1Payload,
    layer2a_payload: Layer2APayload,
    integration_bundle: Layer3AIntegrationBundle,
    as_of: datetime,
    *,
    retry_error: str | None = None,
) -> str:
    """Per `Layer3_3A_Spec.md` §5.2 — assemble the user prompt from the 8
    §5.1 prep sections + 2A phase block + §B health note + as_of line."""
    blocks = [
        f"Athlete context: {_render_demographics(layer1_payload, as_of)}",
        "",
        "Training history:",
        _render_training_history(layer1_payload),
        "",
        "Discipline baselines (included per 2A):",
        _render_discipline_baselines(layer1_payload, layer2a_payload),
        "",
        "Strength benchmarks:",
        _render_strength(layer1_payload),
        "",
        "Performance testing:",
        _render_performance(layer1_payload, as_of),
        "",
        "Lifestyle and recovery:",
        _render_lifestyle(layer1_payload),
        "",
        "Recent activity bundle (anchored at "
        f"{as_of.isoformat()}, 28-day workout window / 14-day sleep + HRV windows):",
        _render_integration_summary(integration_bundle),
        "",
        "Current phase context (from 2A):",
        _render_phase_context(layer2a_payload),
        "",
        "Health-context note (read-only):",
        _render_health_context_note(layer1_payload),
        "",
        # #826 — research-source allowlist for `source_citations` (rule 12).
        _render_evidence_catalog_block(),
        "",
        f"Today is {as_of.isoformat()}.",
        "",
        "Produce a `Layer3APayload` via the `record_athlete_state` tool. "
        "Ground every assessment in evidence_basis citations, and cite any "
        "applicable research sources in `source_citations` (slugs from the "
        "catalog above only). Apply the confidence calibration rules in the "
        "system prompt — when in doubt, prefer `medium`. Emit observations "
        "only when they would change a downstream decision.",
    ]
    if retry_error:
        blocks.extend([
            "",
            f"Previous attempt failed schema validation: {retry_error}",
            "",
            "Re-emit a valid `record_athlete_state` tool call addressing the "
            "error above. Do not change unrelated fields.",
        ])
    return "\n".join(blocks)


# ─── Evidence-basis cross-check (§5.3 step 2) ────────────────────────────────


def _collect_evidence_basis(payload_dict: dict[str, Any]) -> list[str]:
    """Walk the validated tool args + post-clamp output and surface every
    `evidence_basis` entry across Assessments + TrajectoryWindows +
    Observations. Used by `_check_evidence_basis` for name-existence check."""
    paths: list[str] = []
    cs = payload_dict.get("current_state", {})
    for k in ("aerobic_capacity", "strength"):
        node = cs.get(k)
        if isinstance(node, dict):
            paths.extend(node.get("evidence_basis", []))
    for _, node in cs.get("skill_assessments", {}).items():
        if isinstance(node, dict):
            paths.extend(node.get("evidence_basis", []))
    rt = payload_dict.get("recent_trajectory", {})
    for k in ("short_term", "medium_term"):
        node = rt.get(k)
        if isinstance(node, dict):
            paths.extend(node.get("evidence_basis", []))
    for obs in payload_dict.get("notable_observations", []):
        if isinstance(obs, dict):
            paths.extend(obs.get("evidence_basis", []))
    return paths


def _check_evidence_basis(
    tool_args: dict[str, Any], prep_dict: dict[str, Any]
) -> None:
    """Per §5.3 step 2 — name-existence check. Missing references warn but
    do not fail (per D9 + spec §12 item 3A-1)."""
    cited = _collect_evidence_basis(tool_args)
    valid_keys = set(prep_dict.keys())
    for path in cited:
        if path not in valid_keys:
            warnings.warn(
                f"evidence_basis cites unknown field path: {path!r}",
                Layer3AEvidenceBasisWarning,
                stacklevel=3,
            )


# ─── Confidence-floor clamp (§6.2 + §6.3) ────────────────────────────────────


def _clamp_confidence(current: str, ceiling: str) -> str:
    """Return the lower of current vs ceiling per the high > medium > low
    ordering."""
    if _CONFIDENCE_RANK[current] <= _CONFIDENCE_RANK[ceiling]:
        return current
    return ceiling


def _check_high_confidence_gates(
    bundle: Layer3AIntegrationBundle, layer1_payload: Layer1Payload
) -> bool:
    """Per `Layer3_3A_Spec.md` §6.2 — ALL gates must be true to permit `high`
    confidence anywhere in the payload. If any gate fails, `high` is clamped
    to `medium` everywhere."""
    # Gate 1: ≥1 active provider with any recent data
    active_with_data = any(
        ps.status == "active"
        and (ps.has_recent_workouts or ps.has_recent_sleep or ps.has_recent_hrv)
        for ps in bundle.connected_providers
    )
    if not active_with_data:
        return False
    # Gate 2: ≥10 logged workouts in last 28d
    if len(bundle.recent_workouts) < 10:
        return False
    # Gate 3: §C self-report substantive
    if layer1_payload.training_history.years_structured_training is None:
        return False
    # Gate 4: §F baselines — HRmax + ≥1 threshold metric
    perf = layer1_payload.performance
    if perf is None or perf.hrmax_bpm is None:
        return False
    threshold_present = (
        perf.cycling_ftp_w is not None
        or perf.running_threshold_pace_sec_per_km is not None
        or perf.css_swim_sec_per_100m is not None
    )
    if not threshold_present:
        return False
    # Gate 5: §I sleep self-report
    life = layer1_payload.lifestyle
    if life is None or life.sleep_baseline_hours is None:
        return False
    return True


def _apply_confidence_floors(
    payload: Layer3APayload,
    bundle: Layer3AIntegrationBundle,
    layer1_payload: Layer1Payload,
) -> Layer3APayload:
    """Per `Layer3_3A_Spec.md` §6.2 floor rules + §6.3 auto-append observation.

    Returns a clamped copy. Signals that fire are recorded and surfaced
    via a single appended `confidence_clamped_by_data_density` observation
    (category=data_gap, elevates_to_hitl=False)."""
    signals: list[str] = []
    cs = payload.current_state
    rt = payload.recent_trajectory

    # Floor 1: connected_providers count == 0 → trajectory ≤ medium
    if not bundle.connected_providers:
        if _CONFIDENCE_RANK[rt.confidence] > _CONFIDENCE_RANK["medium"]:
            rt = rt.model_copy(update={"confidence": "medium"})
        signals.append("no_connected_providers")

    # Floor 2: recent_workouts < 5 → trajectory ≤ low
    if len(bundle.recent_workouts) < 5:
        if _CONFIDENCE_RANK[rt.confidence] > _CONFIDENCE_RANK["low"]:
            rt = rt.model_copy(update={"confidence": "low"})
        signals.append("sparse_recent_workouts")

    # Floor 3: no device HRV anywhere in recent_wellness → trajectory ≤ medium
    if not any(r.hrv_rmssd_ms is not None for r in bundle.recent_wellness):
        if _CONFIDENCE_RANK[rt.confidence] > _CONFIDENCE_RANK["medium"]:
            rt = rt.model_copy(update={"confidence": "medium"})
        signals.append("no_recent_hrv")

    # Floor 4: years_structured_training == 0 → current_state assessments ≤ medium
    yst = layer1_payload.training_history.years_structured_training
    if yst is not None and yst == 0:
        if _CONFIDENCE_RANK[cs.aerobic_capacity.confidence] > _CONFIDENCE_RANK["medium"]:
            cs = cs.model_copy(
                update={
                    "aerobic_capacity": cs.aerobic_capacity.model_copy(
                        update={"confidence": "medium"}
                    )
                }
            )
        if _CONFIDENCE_RANK[cs.strength.confidence] > _CONFIDENCE_RANK["medium"]:
            cs = cs.model_copy(
                update={
                    "strength": cs.strength.model_copy(update={"confidence": "medium"})
                }
            )
        signals.append("just_onboarded_training_history")

    # High-confidence gate: if ANY gate fails, clamp every `high` to `medium`
    if not _check_high_confidence_gates(bundle, layer1_payload):
        if _CONFIDENCE_RANK[cs.aerobic_capacity.confidence] > _CONFIDENCE_RANK["medium"]:
            cs = cs.model_copy(
                update={
                    "aerobic_capacity": cs.aerobic_capacity.model_copy(
                        update={"confidence": "medium"}
                    )
                }
            )
            signals.append("high_gate_failed_aerobic")
        if _CONFIDENCE_RANK[cs.strength.confidence] > _CONFIDENCE_RANK["medium"]:
            cs = cs.model_copy(
                update={
                    "strength": cs.strength.model_copy(update={"confidence": "medium"})
                }
            )
            signals.append("high_gate_failed_strength")
        if _CONFIDENCE_RANK[rt.confidence] > _CONFIDENCE_RANK["medium"]:
            rt = rt.model_copy(update={"confidence": "medium"})
            signals.append("high_gate_failed_trajectory")
        clamped_skills: dict[str, Assessment] = {}
        any_skill_clamped = False
        for k, a in cs.skill_assessments.items():
            if _CONFIDENCE_RANK[a.confidence] > _CONFIDENCE_RANK["medium"]:
                clamped_skills[k] = a.model_copy(update={"confidence": "medium"})
                any_skill_clamped = True
            else:
                clamped_skills[k] = a
        if any_skill_clamped:
            cs = cs.model_copy(update={"skill_assessments": clamped_skills})
            signals.append("high_gate_failed_skill_assessments")

    observations = list(payload.notable_observations)
    if signals:
        observations.append(
            Layer3Observation(
                category="data_gap",
                text=f"Confidence clamped by data density: {', '.join(sorted(set(signals)))}.",
                evidence_basis=[
                    "integration.connected_providers",
                    "integration.recent_workouts",
                    "integration.recent_wellness",
                    "section_c.years_structured_training",
                ],
                elevates_to_hitl=False,
            )
        )

    return payload.model_copy(
        update={
            "current_state": cs,
            "recent_trajectory": rt,
            "notable_observations": observations,
        }
    )


# ─── Prompt hash + driver entry point ────────────────────────────────────────


def _clamp_weak_links(
    candidate: dict[str, Any], max_items: int = _WEAK_LINKS_MAX_ITEMS
) -> None:
    """Trim `current_state.weak_links` to the schema cap in place before
    validation. The field is `max_length=5` on `Layer3APayload`, and the tool
    schema carries the matching `maxItems`, but the Anthropic API treats tool-
    schema array bounds as guidance — not a hard limit. A multi-discipline
    athlete legitimately surfaces >5 weak links, and the model holds that line
    even with the schema-violation retry feedback, so the cone walls on
    `schema_violation` (Layer3AOutputError). The prompt instructs the model to
    order weak_links most-limiting first, so keeping the first `max_items` is a
    principled top-N rather than an arbitrary cut. The cap itself is the
    Layer3_3A_Spec §7 contract."""
    current_state = candidate.get("current_state")
    if not isinstance(current_state, dict):
        return
    weak_links = current_state.get("weak_links")
    if isinstance(weak_links, list) and len(weak_links) > max_items:
        print(
            f"llm_layer3a_athlete_state: clamping weak_links from "
            f"{len(weak_links)} to {max_items} (Layer3APayload schema cap)"
        )
        current_state["weak_links"] = weak_links[:max_items]


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
    bounds as guidance — a long observation fails `Layer3APayload` validation on
    both attempts and walls the cone (the per-string twin of the weak_links
    over-emit). Only the human-readable `text` is trimmed; the structured fields
    (category, evidence_basis, elevates_to_hitl) are untouched, so HITL gating is
    unaffected."""
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
                f"llm_layer3a_athlete_state: truncating a notable_observations "
                f"text from {len(text)} to {len(truncated)} chars "
                f"(Layer3Observation max_length={max_chars})"
            )
            item["text"] = truncated


def _strip_unknown_current_state_keys(candidate: dict[str, Any]) -> None:
    """Drop keys the model invents under `current_state` but `CurrentState` does
    not declare, in place before validation. `_Base` sets `extra='forbid'`
    (`layer4/context.py` §7 guardrail), so a stray key walls the cone on
    `schema_violation`. Observed in prod: the model emits a null
    `weak_links_note_internal` sibling beside `weak_links` and holds it through
    the capped schema-violation retry — the weak_links over-emit failure mode,
    normalized the same deterministic way. Only undeclared keys are removed, so
    a misplaced *required* field (e.g. a typo'd `weak_links`) still surfaces as
    `schema_violation` with its real slot unfilled rather than being masked."""
    current_state = candidate.get("current_state")
    if not isinstance(current_state, dict):
        return
    unknown = {
        key: type(value).__name__
        for key, value in current_state.items()
        if key not in CurrentState.model_fields
    }
    if unknown:
        print(
            f"llm_layer3a_athlete_state: stripping unknown current_state keys "
            f"{unknown} (not in CurrentState schema; extra='forbid')"
        )
        for key in unknown:
            del current_state[key]


def _prompt_hash(system_prompt: str, user_prompt: str) -> str:
    return hashlib.sha256(
        (system_prompt + "||" + user_prompt).encode("utf-8")
    ).hexdigest()


def llm_layer3a_athlete_state(
    user_id: int,
    layer1_payload: Layer1Payload,
    layer2a_payload: Layer2APayload,
    integration_bundle: Layer3AIntegrationBundle,
    as_of: datetime,
    etl_version_set: dict[str, str],
    *,
    model: str = _DEFAULT_MODEL,
    temperature: float = _DEFAULT_TEMPERATURE,
    max_tokens: int = _DEFAULT_MAX_TOKENS,
    extended_thinking_budget: int = _DEFAULT_THINKING_BUDGET,
    llm_caller: LLMCaller | None = None,
) -> Layer3APayload:
    """Per `Layer3_3A_Spec.md` §3 + §5 — single-call LLM driver for Layer 3A.

    Algorithm:
    1. `_validate_inputs(...)` — §4 preconditions → `Layer3AInputError`.
    2. `_render_user_prompt(...)` — §5.1 prep transformations.
    3. Single LLM call via `caller` (default: Anthropic SDK extended thinking
       + forced tool-use per D1 + D2).
    4. Schema validation via `Layer3APayload.model_validate`. On failure,
       single capped retry per §5.3 step 1.
    5. `_check_evidence_basis(...)` — name-existence warn-log (§5.3 step 2).
    6. `_apply_confidence_floors(...)` — §6.2 floor rules + high-gate clamp
       + §6.3 `confidence_clamped_by_data_density` observation append.
    7. Stamp metadata + return.

    The `llm_caller` param is dependency-injectable for tests; production
    callers leave it None to use `_default_llm_caller`."""
    _validate_inputs(
        layer1_payload,
        layer2a_payload,
        integration_bundle,
        as_of,
        etl_version_set,
        model,
        temperature,
    )

    caller: LLMCaller = llm_caller or _default_llm_caller
    tool_schema = build_record_athlete_state_tool()
    prep_dict = _build_prep_dict(
        layer1_payload, layer2a_payload, integration_bundle, as_of
    )

    last_validation_error: str | None = None
    llm_out: _LLMOutput | None = None
    validated_args: dict[str, Any] | None = None

    # §5.3 step 1: single capped retry on schema violation (max 2 attempts).
    for attempt in range(2):
        user_prompt = _render_user_prompt(
            layer1_payload,
            layer2a_payload,
            integration_bundle,
            as_of,
            retry_error=last_validation_error,
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
        # Try assembling the full Layer3APayload now to validate the entire
        # contract including driver-stamped metadata; if pydantic complains
        # about a field in tool_args, treat as schema_violation.
        candidate = {
            **llm_out.tool_args,
            "user_id": user_id,
            "as_of": as_of,
            "model": model,
            "temperature": temperature,
            "prompt_hash": _prompt_hash(_SYSTEM_PROMPT, user_prompt),
            "latency_ms": llm_out.latency_ms,
            "input_tokens": llm_out.input_tokens,
            "output_tokens": llm_out.output_tokens,
            "etl_version_set": etl_version_set,
        }
        # Honor the bounded-collection caps and strip model-invented keys
        # deterministically before validation so an over-emit or embellishment
        # degrades gracefully instead of walling the cone.
        _clamp_weak_links(candidate)
        _clamp_observation_text(candidate)
        _strip_unknown_current_state_keys(candidate)
        try:
            Layer3APayload.model_validate(candidate)
            validated_args = candidate
            break
        except ValidationError as exc:
            last_validation_error = str(exc)
            if attempt == 1:
                raise Layer3AOutputError(
                    "schema_violation",
                    detail=last_validation_error,
                ) from exc

    assert validated_args is not None and llm_out is not None
    payload = Layer3APayload.model_validate(validated_args)

    # §5.3 step 2: evidence-basis cross-check (warn only)
    _check_evidence_basis(llm_out.tool_args, prep_dict)

    # §5.3 step 3 + §6.2/6.3: post-LLM confidence-floor clamp
    payload = _apply_confidence_floors(payload, integration_bundle, layer1_payload)

    return payload


__all__ = [
    "Layer3AEvidenceBasisWarning",
    "Layer3AInputError",
    "Layer3AOutputError",
    "LLMCaller",
    "build_record_athlete_state_tool",
    "llm_layer3a_athlete_state",
]
