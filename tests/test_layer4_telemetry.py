"""Tests for `layer4/telemetry.py` — per-call observability per §9.6 + §14.3.5.

Coverage:
- `CallMetrics.from_layer4_payload` projection — Pattern A + Pattern B happy
  paths + verdict histogram + cost estimation + retries inference + cap-hit
  + seam_unresolved + intensity_modulated counts + unknown model graceful-fail.
- `TelemetryAggregator` — record + filter by entry_point + total/average
  cost + cap_hit_rate + average_retries + latency_percentile_ms (p50/p95)
  + aggregated seam-verdict histogram + summary() rollup.
"""

from __future__ import annotations

from datetime import date

import pytest

from layer4 import (
    CallMetrics,
    Layer4Payload,
    Observation,
    PhaseSpec,
    PhaseStructure,
    PlanSession,
    RuleFailure,
    SeamReview,
    SessionPhaseMetadata,
    SynthesisMetadata,
    TelemetryAggregator,
    ValidatorResult,
)
from layer4.telemetry import MODEL_PRICING_USD_PER_M


# ─── Fixtures ────────────────────────────────────────────────────────────────


def _rest(
    d: date,
    *,
    idx: int = 0,
    flags: list[str] | None = None,
    with_phase_metadata: bool = True,
) -> PlanSession:
    """Minimal rest session (no cardio/strength) for tests."""
    phase_metadata = (
        SessionPhaseMetadata(
            phase_name="Base",
            week_in_phase=1,
            total_weeks_in_phase=8,
            intended_volume_band=(5.0, 8.0),
            intended_intensity_distribution={"Z1Z2": 0.8, "Z3": 0.15, "Z4Z5": 0.05},
        )
        if with_phase_metadata
        else None
    )
    return PlanSession(
        session_id=f"S-{d.isoformat()}-{idx}",
        plan_version_id=1,
        date=d,
        day_of_week=d.strftime("%a"),
        session_index_in_day=idx,
        time_of_day="morning",
        kind="rest",
        discipline_id=None,
        discipline_name=None,
        locale_id=None,
        locale_name=None,
        duration_min=0,
        intensity_summary="rest",
        rest_reason="planned_recovery",
        session_notes="rest day.",
        coaching_intent="recovery.",
        coaching_flags=flags or [],
        cardio_blocks=None,
        strength_exercises=None,
        is_ad_hoc=False,
        phase_metadata=phase_metadata,
    )


def _meta(retries: int = 0, cap_hit: bool = False) -> SynthesisMetadata:
    return SynthesisMetadata(
        model="claude-sonnet-4-6",
        temperature=0.2,
        input_tokens=8000,
        output_tokens=2500,
        latency_ms=8000,
        retries_used=retries,
        cap_hit=cap_hit,
    )


def _phase(name: str, *, retries: int = 0, cap_hit: bool = False) -> PhaseSpec:
    return PhaseSpec(
        phase_name=name,  # type: ignore[arg-type]
        start_date=date(2026, 6, 1),
        end_date=date(2026, 6, 28),
        weeks=4,
        intended_volume_band=(5.0, 8.0),
        intended_intensity_distribution={"Z1Z2": 0.8, "Z3": 0.15, "Z4Z5": 0.05},
        synthesis_metadata=_meta(retries=retries, cap_hit=cap_hit),
    )


def _seam_review(
    idx: int, prior: str, nxt: str, verdict: str, *, triggered: bool = False
) -> SeamReview:
    return SeamReview(
        seam_index=idx,
        prior_phase_name=prior,  # type: ignore[arg-type]
        next_phase_name=nxt,  # type: ignore[arg-type]
        reviewer_verdict=verdict,  # type: ignore[arg-type]
        seam_issues=[],
        proposed_patch_direction=None,
        triggered_resynthesis=triggered,
        re_prompted_phase_name=None,
        reviewer_model="claude-sonnet-4-6",
        reviewer_input_tokens=2000,
        reviewer_output_tokens=200,
        reviewer_latency_ms=2500,
    )


def _pattern_a_payload(
    *,
    seam_verdicts: list[tuple[str, str, str]] | None = None,
    phase_retries: dict[str, int] | None = None,
    phase_cap_hits: dict[str, bool] | None = None,
    notable_observations: list[Observation] | None = None,
    sessions_with_intensity_mod: int = 0,
    input_tokens_total: int = 24_000,
    output_tokens_total: int = 7_500,
    latency_ms_total: int = 30_000,
    llm_call_count: int = 7,
    model_synthesizer: str = "claude-sonnet-4-6",
) -> Layer4Payload:
    phase_retries = phase_retries or {}
    phase_cap_hits = phase_cap_hits or {}
    phases = [
        _phase(
            name,
            retries=phase_retries.get(name, 0),
            cap_hit=phase_cap_hits.get(name, False),
        )
        for name in ("Base", "Build", "Peak", "Taper")
    ]
    sessions = [
        _rest(date(2026, 6, 1) + ((i,) * 0 and (i,))[0] if False else date(2026, 6, 1))
        for i in range(0)
    ]
    # Real session list — emit `sessions_with_intensity_mod` sessions, one per day.
    sessions = [
        _rest(date(2026, 6, i + 1), flags=["intensity_modulated"])
        for i in range(sessions_with_intensity_mod)
    ]
    seam_reviews = []
    if seam_verdicts:
        for i, (prior, nxt, verdict) in enumerate(seam_verdicts):
            seam_reviews.append(_seam_review(i, prior, nxt, verdict))

    return Layer4Payload(
        user_id=42,
        mode="plan_create",
        plan_version_id=1,
        scope_start_date=date(2026, 6, 1),
        scope_end_date=date(2026, 12, 31),
        model_synthesizer=model_synthesizer,
        model_seam_reviewer="claude-sonnet-4-6",
        temperature=0.2,
        pattern="A",
        latency_ms_total=latency_ms_total,
        input_tokens_total=input_tokens_total,
        output_tokens_total=output_tokens_total,
        llm_call_count=llm_call_count,
        etl_version_set={"layer0": "v7"},
        sessions=sessions,
        phase_structure=PhaseStructure(
            phases=phases, total_weeks=16, derived_from="3b_standard"
        ),
        seam_reviews=seam_reviews,
        shape_override=None,
        validator_results=[
            ValidatorResult(
                pass_index=0,
                accepted=True,
                rule_failures=[],
                retried_phase_names=[],
            )
        ],
        notable_observations=notable_observations or [],
        suggestion_id=None,
        race_week_brief=None,
        race_plan=None,
    )


def _pattern_b_payload(
    *,
    validator_passes: int = 1,
    final_demoted_after_cap_hit: bool = False,
    notable_observations: list[Observation] | None = None,
    input_tokens_total: int = 6_000,
    output_tokens_total: int = 1_500,
    latency_ms_total: int = 7_000,
    llm_call_count: int = 2,
) -> Layer4Payload:
    """Pattern B (plan_refresh T1/T2/T3-intra) payload, refresh mode."""
    notable_observations = notable_observations or []
    validator_results: list[ValidatorResult] = []
    # Build validator_passes-1 failing results + 1 accepted.
    for i in range(validator_passes - 1):
        validator_results.append(
            ValidatorResult(
                pass_index=i,
                accepted=False,
                rule_failures=[
                    RuleFailure(
                        rule_name="volume_band_warning",
                        phase_name=None,
                        severity="warning",
                        detail="under low band",
                        affected_session_ids=[],
                    )
                ],
                retried_phase_names=[],
            )
        )
    if final_demoted_after_cap_hit:
        # Real failing + synthesized accepted with demoted warnings.
        validator_results.append(
            ValidatorResult(
                pass_index=validator_passes - 1,
                accepted=False,
                rule_failures=[
                    RuleFailure(
                        rule_name="volume_band_blocker",
                        phase_name=None,
                        severity="blocker",
                        detail="outside ±20%",
                        affected_session_ids=[],
                    )
                ],
                retried_phase_names=[],
            )
        )
        validator_results.append(
            ValidatorResult(
                pass_index=validator_passes,
                accepted=True,
                rule_failures=[
                    RuleFailure(
                        rule_name="volume_band_blocker",
                        phase_name=None,
                        severity="warning",
                        detail="outside ±20% (demoted)",
                        affected_session_ids=[],
                    )
                ],
                retried_phase_names=[],
            )
        )
    else:
        validator_results.append(
            ValidatorResult(
                pass_index=validator_passes - 1,
                accepted=True,
                rule_failures=[],
                retried_phase_names=[],
            )
        )
    return Layer4Payload(
        user_id=42,
        mode="plan_refresh",
        plan_version_id=2,
        scope_start_date=date(2026, 6, 1),
        scope_end_date=date(2026, 6, 7),
        model_synthesizer="claude-sonnet-4-6",
        model_seam_reviewer=None,
        temperature=0.4,
        pattern="B",
        latency_ms_total=latency_ms_total,
        input_tokens_total=input_tokens_total,
        output_tokens_total=output_tokens_total,
        llm_call_count=llm_call_count,
        etl_version_set={"layer0": "v7"},
        sessions=[],
        phase_structure=None,
        seam_reviews=None,
        shape_override=None,
        validator_results=validator_results,
        notable_observations=notable_observations,
        suggestion_id=None,
        race_week_brief=None,
        race_plan=None,
    )


# ─── CallMetrics.from_layer4_payload ─────────────────────────────────────────


class TestCallMetricsPatternA:
    def test_happy_path_extracts_seam_histogram(self):
        payload = _pattern_a_payload(
            seam_verdicts=[
                ("Base", "Build", "approved"),
                ("Build", "Peak", "flagged_minor"),
                ("Peak", "Taper", "approved"),
            ]
        )
        m = CallMetrics.from_layer4_payload(payload, entry_point="plan_create")
        assert m.entry_point == "plan_create"
        assert m.pattern == "A"
        assert m.seam_verdict_histogram == {"approved": 2, "flagged_minor": 1}

    def test_retries_used_total_summed_across_phases(self):
        payload = _pattern_a_payload(
            phase_retries={"Base": 1, "Build": 0, "Peak": 2, "Taper": 1},
        )
        m = CallMetrics.from_layer4_payload(payload, entry_point="plan_create")
        assert m.retries_used_total == 4

    def test_cap_hit_detected_from_best_effort_observation(self):
        obs = Observation(
            category="best_effort_plan",
            text="cap hit",
            evidence_basis=["§5.5"],
            elevates_to_hitl=True,
        )
        payload = _pattern_a_payload(notable_observations=[obs])
        m = CallMetrics.from_layer4_payload(payload, entry_point="plan_create")
        assert m.cap_hit is True
        assert m.best_effort_emitted is True

    def test_seam_unresolved_count_from_observations(self):
        obs1 = Observation(
            category="seam_unresolved",
            text="iter-2 still flagged",
            evidence_basis=["x"],
            elevates_to_hitl=True,
        )
        obs2 = Observation(
            category="seam_unresolved",
            text="budget exhausted",
            evidence_basis=["x"],
            elevates_to_hitl=True,
        )
        payload = _pattern_a_payload(notable_observations=[obs1, obs2])
        m = CallMetrics.from_layer4_payload(payload, entry_point="plan_create")
        assert m.seam_unresolved_count == 2

    def test_intensity_modulated_session_count(self):
        payload = _pattern_a_payload(sessions_with_intensity_mod=3)
        m = CallMetrics.from_layer4_payload(payload, entry_point="plan_create")
        assert m.intensity_modulated_session_count == 3

    def test_cost_estimate_uses_synthesizer_model_pricing(self):
        # claude-sonnet-4-6: input $3/M, output $15/M
        # 24000 input @ 3/1M = $0.072; 7500 output @ 15/1M = $0.1125; total $0.1845
        payload = _pattern_a_payload(
            input_tokens_total=24_000,
            output_tokens_total=7_500,
        )
        m = CallMetrics.from_layer4_payload(payload, entry_point="plan_create")
        assert abs(m.cost_usd_estimate - 0.1845) < 1e-6


class TestCallMetricsPatternB:
    def test_first_pass_accept_zero_retries(self):
        payload = _pattern_b_payload(validator_passes=1)
        m = CallMetrics.from_layer4_payload(payload, entry_point="plan_refresh")
        assert m.pattern == "B"
        assert m.retries_used_total == 0
        assert m.cap_hit is False
        assert m.seam_verdict_histogram == {}

    def test_two_passes_one_retry(self):
        payload = _pattern_b_payload(validator_passes=2)
        m = CallMetrics.from_layer4_payload(payload, entry_point="plan_refresh")
        assert m.retries_used_total == 1
        assert m.validator_pass_count == 2

    def test_cap_hit_demoted_pass_not_counted_as_retry(self):
        """When cap_hit fires, the synthesized accepted pass appears on top
        of the real failing pass. Heuristic backs that out — retries_used
        should reflect only the real synthesizer calls."""
        obs = Observation(
            category="best_effort_plan",
            text="cap hit",
            evidence_basis=["§5.5"],
            elevates_to_hitl=True,
        )
        payload = _pattern_b_payload(
            validator_passes=3,  # → 3 failing passes
            final_demoted_after_cap_hit=True,
            notable_observations=[obs],
        )
        # Real calls = 3 (validator_passes); synthesized accepted on top.
        # Total entries in validator_results = 4 (3 failing + 1 synthesized).
        # retries_used_total heuristic: len(vr) - 1 - 1 = 2 (subtract synthesized).
        m = CallMetrics.from_layer4_payload(payload, entry_point="plan_refresh")
        assert m.cap_hit is True
        assert m.retries_used_total == 2


class TestCallMetricsCostEstimate:
    def test_unknown_model_estimates_zero(self):
        payload = _pattern_a_payload(model_synthesizer="claude-unknown-model")
        m = CallMetrics.from_layer4_payload(payload, entry_point="plan_create")
        assert m.cost_usd_estimate == 0.0

    def test_caller_supplied_pricing_overlay(self):
        payload = _pattern_a_payload(model_synthesizer="claude-opus-4-7")
        custom = {"claude-opus-4-7": {"input": 1.50, "output": 7.50}}  # 50% discount
        m = CallMetrics.from_layer4_payload(
            payload, entry_point="plan_create", model_pricing=custom
        )
        # 24000 * 1.5/1M + 7500 * 7.5/1M = 0.036 + 0.05625 = 0.09225
        assert abs(m.cost_usd_estimate - 0.09225) < 1e-6


class TestCallMetricsValidatorFailures:
    def test_rule_failure_counts(self):
        payload = _pattern_b_payload(
            validator_passes=2,
        )
        # First pass failing has 1 rule_failure (warning); second accepted has 0.
        m = CallMetrics.from_layer4_payload(payload, entry_point="plan_refresh")
        assert m.rule_failure_count == 1
        assert m.blocker_failure_count == 0


# ─── TelemetryAggregator ─────────────────────────────────────────────────────


class TestTelemetryAggregator:
    def test_record_and_call_count(self):
        agg = TelemetryAggregator()
        m1 = CallMetrics.from_layer4_payload(
            _pattern_a_payload(), entry_point="plan_create"
        )
        m2 = CallMetrics.from_layer4_payload(
            _pattern_b_payload(), entry_point="plan_refresh"
        )
        agg.record(m1)
        agg.record(m2)
        assert agg.call_count() == 2
        assert agg.call_count(entry_point="plan_create") == 1
        assert agg.call_count(entry_point="plan_refresh") == 1
        assert agg.call_count(entry_point="single_session_synthesize") == 0

    def test_total_and_average_cost_per_entry_point(self):
        agg = TelemetryAggregator()
        m1 = CallMetrics.from_layer4_payload(
            _pattern_a_payload(input_tokens_total=10_000, output_tokens_total=2_500),
            entry_point="plan_create",
        )
        m2 = CallMetrics.from_layer4_payload(
            _pattern_a_payload(input_tokens_total=20_000, output_tokens_total=5_000),
            entry_point="plan_create",
        )
        agg.record(m1)
        agg.record(m2)
        # m1: 10000*3/1M + 2500*15/1M = 0.03 + 0.0375 = 0.0675
        # m2: 20000*3/1M + 5000*15/1M = 0.06 + 0.075 = 0.135
        # total: 0.2025; avg: 0.10125
        assert abs(agg.total_cost_usd("plan_create") - 0.2025) < 1e-6
        assert abs(agg.average_cost_usd("plan_create") - 0.10125) < 1e-6
        assert agg.average_cost_usd("plan_refresh") == 0.0  # no calls

    def test_cap_hit_rate(self):
        agg = TelemetryAggregator()
        obs_cap = Observation(
            category="best_effort_plan",
            text="x",
            evidence_basis=["x"],
            elevates_to_hitl=True,
        )
        agg.record(
            CallMetrics.from_layer4_payload(
                _pattern_a_payload(notable_observations=[obs_cap]),
                entry_point="plan_create",
            )
        )
        agg.record(
            CallMetrics.from_layer4_payload(
                _pattern_a_payload(), entry_point="plan_create"
            )
        )
        agg.record(
            CallMetrics.from_layer4_payload(
                _pattern_a_payload(), entry_point="plan_create"
            )
        )
        # 1 of 3 cap-hit → 0.333…
        assert abs(agg.cap_hit_rate("plan_create") - (1 / 3)) < 1e-6

    def test_average_retries(self):
        agg = TelemetryAggregator()
        agg.record(
            CallMetrics.from_layer4_payload(
                _pattern_a_payload(phase_retries={"Base": 0, "Build": 0}),
                entry_point="plan_create",
            )
        )
        agg.record(
            CallMetrics.from_layer4_payload(
                _pattern_a_payload(phase_retries={"Base": 1, "Build": 1, "Peak": 2}),
                entry_point="plan_create",
            )
        )
        # call 1: 0 retries; call 2: 4 retries → avg 2.0
        assert agg.average_retries("plan_create") == 2.0

    def test_latency_percentile_p50_p95(self):
        agg = TelemetryAggregator()
        for ms in (1000, 2000, 3000, 4000, 10000):
            agg.record(
                CallMetrics.from_layer4_payload(
                    _pattern_a_payload(latency_ms_total=ms),
                    entry_point="plan_create",
                )
            )
        # Sorted: 1000, 2000, 3000, 4000, 10000
        # p50 = rank ceil(0.5*5)=3 → index 2 → 3000
        # p95 = rank ceil(0.95*5)=5 → index 4 → 10000
        assert agg.latency_percentile_ms(50.0, "plan_create") == 3000
        assert agg.latency_percentile_ms(95.0, "plan_create") == 10000

    def test_latency_percentile_rejects_out_of_range(self):
        agg = TelemetryAggregator()
        with pytest.raises(ValueError):
            agg.latency_percentile_ms(150.0)
        with pytest.raises(ValueError):
            agg.latency_percentile_ms(-1.0)

    def test_latency_percentile_no_calls_returns_zero(self):
        agg = TelemetryAggregator()
        assert agg.latency_percentile_ms(50.0) == 0
        assert agg.latency_percentile_ms(95.0, "plan_create") == 0

    def test_aggregated_seam_verdict_histogram(self):
        agg = TelemetryAggregator()
        agg.record(
            CallMetrics.from_layer4_payload(
                _pattern_a_payload(
                    seam_verdicts=[
                        ("Base", "Build", "approved"),
                        ("Build", "Peak", "approved"),
                    ]
                ),
                entry_point="plan_create",
            )
        )
        agg.record(
            CallMetrics.from_layer4_payload(
                _pattern_a_payload(
                    seam_verdicts=[
                        ("Base", "Build", "flagged_minor"),
                        ("Build", "Peak", "approved"),
                    ]
                ),
                entry_point="plan_create",
            )
        )
        assert agg.aggregated_seam_verdict_histogram("plan_create") == {
            "approved": 3,
            "flagged_minor": 1,
        }

    def test_pattern_b_calls_dont_contribute_seam_verdicts(self):
        agg = TelemetryAggregator()
        agg.record(
            CallMetrics.from_layer4_payload(
                _pattern_b_payload(), entry_point="plan_refresh"
            )
        )
        assert agg.aggregated_seam_verdict_histogram("plan_refresh") == {}

    def test_summary_rollup_shape(self):
        agg = TelemetryAggregator()
        agg.record(
            CallMetrics.from_layer4_payload(
                _pattern_a_payload(
                    seam_verdicts=[("Base", "Build", "approved")],
                    latency_ms_total=5000,
                ),
                entry_point="plan_create",
            )
        )
        agg.record(
            CallMetrics.from_layer4_payload(
                _pattern_a_payload(
                    seam_verdicts=[("Base", "Build", "approved")],
                    latency_ms_total=15000,
                ),
                entry_point="plan_create",
            )
        )
        s = agg.summary("plan_create")
        assert s["entry_point"] == "plan_create"
        assert s["call_count"] == 2
        assert s["seam_verdict_histogram"] == {"approved": 2}
        assert s["p50_latency_ms"] == 5000
        assert s["p95_latency_ms"] == 15000
        assert "total_cost_usd" in s
        assert "average_cost_usd" in s
        assert "cap_hit_rate" in s
        assert "average_retries" in s

    def test_summary_global_no_filter(self):
        agg = TelemetryAggregator()
        agg.record(
            CallMetrics.from_layer4_payload(
                _pattern_a_payload(), entry_point="plan_create"
            )
        )
        agg.record(
            CallMetrics.from_layer4_payload(
                _pattern_b_payload(), entry_point="plan_refresh"
            )
        )
        s = agg.summary()
        assert s["entry_point"] is None
        assert s["call_count"] == 2


# ─── Module pricing table sanity ─────────────────────────────────────────────


class TestModelPricingTable:
    def test_sonnet_4_6_has_known_rates(self):
        assert MODEL_PRICING_USD_PER_M["claude-sonnet-4-6"]["input"] == 3.00
        assert MODEL_PRICING_USD_PER_M["claude-sonnet-4-6"]["output"] == 15.00

    def test_opus_4_7_has_known_rates(self):
        assert MODEL_PRICING_USD_PER_M["claude-opus-4-7"]["input"] == 15.00
        assert MODEL_PRICING_USD_PER_M["claude-opus-4-7"]["output"] == 75.00

    def test_haiku_4_5_has_known_rates(self):
        assert MODEL_PRICING_USD_PER_M["claude-haiku-4-5"]["input"] == 1.00
        assert MODEL_PRICING_USD_PER_M["claude-haiku-4-5"]["output"] == 5.00
