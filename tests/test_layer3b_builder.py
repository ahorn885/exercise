"""Tests for `layer3b.builder.llm_layer3b_goal_timeline_viability` per
`Layer3_3B_Spec.md` §4 + §5 + §6 + §13 — plus the cache wrapper in
`layer3b.cached_wrapper`.

LLM calls are mocked via a stub `llm_caller` dependency (same shape as
`layer3a/builder.py` precedent). No real Anthropic SDK invocation; no
`ANTHROPIC_API_KEY` env requirement. The stubs verify that the round-trip
through input validation + prompt rendering + tool-args parsing + schema
validation + mode-discriminator + evidence-basis cross-check + HITL
auto-emit + post-LLM confidence-floor clamp + periodization-sanity loop
+ metadata stamping + D14 event-metadata population produces the
expected `Layer3BPayload`. Real-LLM regression on §13.x scenarios is
deferred to Step 7/8 telemetry tuning per
`Upstream_Implementation_Plan_v1.md`.
"""

from __future__ import annotations

import warnings
from datetime import date, datetime
from decimal import Decimal
from typing import Any

import pytest

from layer3a.builder import _LLMOutput as _LLMOutput3A  # type alias compatibility
from layer3b.builder import (
    Layer3BEvidenceBasisWarning,
    Layer3BInputError,
    Layer3BOutputError,
    _DEFAULT_DNF_RECOVERY_WINDOW_WEEKS,
    _DNF_RECOVERY_WINDOW_WEEKS,
    _LLMOutput,
    _apply_confidence_floors,
    _build_prep_dict,
    _check_periodization_sanity,
    _clamp_confidence,
    _enforce_hitl_auto_emit,
    _periodization_fallback_to_standard,
    _render_user_prompt,
    _time_to_event_phase_band,
    _time_to_event_weeks,
    build_emit_layer3b_payload_tool,
    llm_layer3b_goal_timeline_viability,
)
from layer3b.cached_wrapper import (
    layer3b_goal_timeline_viability_key,
    llm_layer3b_goal_timeline_viability_cached,
)
from layer4.cache import InMemoryCacheBackend
from layer4.context import (
    ACWREntry,
    ACWRStatus,
    Assessment,
    CurrentState,
    DataDensity,
    DisciplineWeightRecord,
    Layer1Disclosures,
    Layer1DisciplineBaselines,
    Layer1EventGoal,
    Layer1HealthStatus,
    Layer1Identity,
    Layer1Lifestyle,
    Layer1Network,
    Layer1Payload,
    Layer1Performance,
    Layer1StrengthBenchmarks,
    Layer1TrainingHistory,
    Layer2ADiscipline,
    Layer2APayload,
    Layer3APayload,
    Layer3Observation,
    RaceEventPayload,
    RationaleMetadata,
    RecentTrajectory,
    TrainingGapsSummary,
    TrajectoryWindow,
    WeightResult,
)


# ─── Fixtures ────────────────────────────────────────────────────────────────


_DEFAULT_ETL = {"0A": "v1", "0B": "v1", "0C": "v1"}


def _make_layer1(
    *,
    primary_sport: str = "Adventure Racing",
    plan_duration_weeks_no_event: int | None = None,
    non_event_goal_type: str | None = None,
) -> Layer1Payload:
    return Layer1Payload(
        user_id=1,
        as_of=datetime(2026, 5, 20, 0, 0),
        identity=Layer1Identity(
            date_of_birth=date(1980, 6, 1),
            sex="male",
            height_cm=180.0,
            primary_sport=primary_sport,
        ),
        health_status=Layer1HealthStatus(
            current_injuries=[],
            resting_hr_bpm=52,
        ),
        training_history=Layer1TrainingHistory(
            years_structured_training=5,
            peak_weekly_volume_hrs=12.0,
            peak_weekly_volume_year=2024,
            longest_event_completed="50-mile ultra",
            discipline_weighting=[
                DisciplineWeightRecord(discipline_slug="run", weight_pct=40),
                DisciplineWeightRecord(discipline_slug="bike", weight_pct=40),
                DisciplineWeightRecord(discipline_slug="paddle", weight_pct=20),
            ],
        ),
        discipline_baselines=Layer1DisciplineBaselines(),
        strength_benchmarks=Layer1StrengthBenchmarks(),
        performance=Layer1Performance(body_weight_kg=75.0, hrmax_bpm=185),
        event_goal=Layer1EventGoal(
            plan_duration_weeks_no_event=plan_duration_weeks_no_event,
            non_event_goal_type=non_event_goal_type,
        ),
        lifestyle=Layer1Lifestyle(sleep_baseline_hours=7.5),
        network=Layer1Network(),
        disclosures=Layer1Disclosures(),
    )


def _make_layer3a(
    *,
    aerobic_level: str = "good",
    aerobic_confidence: str = "medium",
    strength_level: str = "moderate",
    strength_confidence: str = "medium",
    short_term: str = "building",
    medium_term: str = "building",
    trajectory_confidence: str = "medium",
    connected_providers: list[str] | None = None,
    self_report_freshness_days: int = 0,
    etl_version_set: dict[str, str] | None = None,
) -> Layer3APayload:
    if connected_providers is None:
        connected_providers = ["polar"]
    return Layer3APayload(
        user_id=1,
        as_of=datetime(2026, 5, 20, 0, 0),
        model="claude-sonnet-4-6",
        temperature=0.2,
        prompt_hash="a" * 64,
        latency_ms=4500,
        input_tokens=3200,
        output_tokens=900,
        etl_version_set=etl_version_set or _DEFAULT_ETL,
        current_state=CurrentState(
            aerobic_capacity=Assessment(
                level=aerobic_level,
                confidence=aerobic_confidence,
                reasoning_text="reasoning",
                evidence_basis=["x", "y", "z"],
            ),
            strength=Assessment(
                level=strength_level,
                confidence=strength_confidence,
                reasoning_text="reasoning",
                evidence_basis=["x", "y", "z"],
            ),
            weak_links=["single-leg balance"],
            skill_assessments={},
            body_composition_notes=None,
        ),
        recent_trajectory=RecentTrajectory(
            short_term=TrajectoryWindow(
                direction=short_term,
                reasoning_text="reasoning",
                evidence_basis=["x"],
            ),
            medium_term=TrajectoryWindow(
                direction=medium_term,
                reasoning_text="reasoning",
                evidence_basis=["x"],
            ),
            acwr_status=ACWRStatus(per_discipline={}, combined=None),
            confidence=trajectory_confidence,
        ),
        data_density=DataDensity(
            connected_providers=connected_providers,
            integration_data_days=28,
            recent_workouts_count=12,
            recent_sleep_count=10,
            recent_hrv_count=10,
            self_report_freshness_days=self_report_freshness_days,
            section_completeness={},
        ),
        notable_observations=[],
    )


def _make_layer2a(
    disciplines: int = 3, etl_version_set: dict[str, str] | None = None
) -> Layer2APayload:
    return Layer2APayload(
        framework_sport="Adventure Racing",
        etl_version_set=etl_version_set or _DEFAULT_ETL,
        disciplines=[
            Layer2ADiscipline(
                discipline_id=f"D-{i:03d}",
                discipline_name=f"Discipline {i}",
                inclusion="included",
                role="Primary" if i == 1 else "Secondary",
                is_conditional=False,
                load_weight=WeightResult(
                    value=0.4 if i == 1 else 0.3,
                    source="system_default",
                    system_default=0.4 if i == 1 else 0.3,
                ),
                sleep_deprivation_relevant=False,
                rationale="test fixture rationale",
            )
            for i in range(1, disciplines + 1)
        ],
        training_gaps_summary=TrainingGapsSummary(
            flagged_count=0,
            any_no_substitute=False,
            any_multi_substitute_candidate=False,
        ),
        hitl_required=False,
        unresolved_flags=[],
        coaching_flags=[],
        rationale_metadata=RationaleMetadata(
            template_version="v1",
            generated_at="2026-05-20T12:00:00",
        ),
    )


def _make_race_event(
    *,
    event_date: date = date(2026, 7, 17),
    race_format: str = "continuous_multi_day",
    name: str = "Pocket Gopher Extreme 2026",
    distance_km: float | None = None,
    event_locale_id: str | None = "nerstrand-mn",
) -> RaceEventPayload:
    return RaceEventPayload(
        race_event_id=1,
        user_id=1,
        name=name,
        event_date=event_date,
        race_format=race_format,
        distance_km=Decimal(str(distance_km)) if distance_km is not None else None,
        event_locale_mapbox_id="poi.test_anchor",
        is_target_event=True,
        event_locale_id=event_locale_id,
        route_locales=[],
    )


def _good_tool_args(
    *,
    mode: str = "event",
    viability: str = "achievable",
    confidence: str = "medium",
    periodization_mode: str = "compressed",
    start_phase: str = "Build",
    phase_weeks: dict[str, int] | None = None,
    hitl_surface: list[dict[str, Any]] | None = None,
    observations: list[dict[str, Any]] | None = None,
    evidence_basis_h2: bool = True,
) -> dict[str, Any]:
    """A schema-valid tool args payload mimicking a well-behaved LLM."""
    if evidence_basis_h2:
        gv_evidence = ["h2.goal_outcome", "3a.current_state.aerobic_capacity"] if mode == "event" else ["h3.plan_duration_weeks", "h3.non_event_goal_type"]
    else:
        gv_evidence = ["3a.current_state.aerobic_capacity"]
    suggested = [] if viability == "achievable" else ["Stretch goal to a lower tier"]
    return {
        "mode": mode,
        "goal_viability": {
            "viability": viability,
            "confidence": confidence,
            "reasoning_text": "Reasonable goal given current state and timeline.",
            "evidence_basis": gv_evidence,
            "suggested_adjustments": suggested,
        },
        "periodization_shape": {
            "mode": periodization_mode,
            "start_phase": start_phase,
            "phase_weeks": phase_weeks,
            "reasoning_text": "Phase shape per §5.3 band guidance.",
            "evidence_basis": ["2a.framework_sport"],
        },
        "hitl_surface": hitl_surface or [],
        "notable_observations": observations or [],
    }


def _stub_caller(tool_args: dict[str, Any]):
    def _call(*_args, **_kwargs) -> _LLMOutput:
        return _LLMOutput(
            tool_args=tool_args, input_tokens=2800, output_tokens=600, latency_ms=2200
        )

    return _call


def _sequence_caller(outputs: list[dict[str, Any]]):
    state = {"i": 0}

    def _call(*_args, **_kwargs) -> _LLMOutput:
        i = state["i"]
        state["i"] = i + 1
        return _LLMOutput(
            tool_args=outputs[i], input_tokens=2800, output_tokens=600, latency_ms=2200
        )

    return _call


def _explode_caller(*_args, **_kwargs) -> _LLMOutput:
    raise AssertionError("LLM caller invoked when it should not have been")


# ─── §4 input validation ─────────────────────────────────────────────────────


class TestInputValidation:
    def test_missing_layer1_raises(self):
        with pytest.raises(Layer3BInputError) as exc:
            llm_layer3b_goal_timeline_viability(
                user_id=1,
                layer1_payload=None,  # type: ignore[arg-type]
                layer3a_payload=_make_layer3a(),
                layer2a_payload=_make_layer2a(),
                race_event_payload=_make_race_event(),
                current_date=date(2026, 5, 20),
                etl_version_set=_DEFAULT_ETL,
                goal_outcome="Finish",
                llm_caller=_stub_caller(_good_tool_args()),
            )
        assert exc.value.code == "missing_layer1"

    def test_missing_3a_payload_raises(self):
        with pytest.raises(Layer3BInputError) as exc:
            llm_layer3b_goal_timeline_viability(
                user_id=1,
                layer1_payload=_make_layer1(),
                layer3a_payload=None,  # type: ignore[arg-type]
                layer2a_payload=_make_layer2a(),
                race_event_payload=_make_race_event(),
                current_date=date(2026, 5, 20),
                etl_version_set=_DEFAULT_ETL,
                goal_outcome="Finish",
                llm_caller=_stub_caller(_good_tool_args()),
            )
        assert exc.value.code == "missing_3a_payload"

    def test_missing_2a_payload_raises(self):
        with pytest.raises(Layer3BInputError) as exc:
            llm_layer3b_goal_timeline_viability(
                user_id=1,
                layer1_payload=_make_layer1(),
                layer3a_payload=_make_layer3a(),
                layer2a_payload=None,  # type: ignore[arg-type]
                race_event_payload=_make_race_event(),
                current_date=date(2026, 5, 20),
                etl_version_set=_DEFAULT_ETL,
                goal_outcome="Finish",
                llm_caller=_stub_caller(_good_tool_args()),
            )
        assert exc.value.code == "missing_2a_payload"

    def test_etl_version_mismatch_3a_raises(self):
        with pytest.raises(Layer3BInputError) as exc:
            llm_layer3b_goal_timeline_viability(
                user_id=1,
                layer1_payload=_make_layer1(),
                layer3a_payload=_make_layer3a(etl_version_set={"0A": "vDIFFERENT"}),
                layer2a_payload=_make_layer2a(),
                race_event_payload=_make_race_event(),
                current_date=date(2026, 5, 20),
                etl_version_set=_DEFAULT_ETL,
                goal_outcome="Finish",
                llm_caller=_stub_caller(_good_tool_args()),
            )
        assert exc.value.code == "etl_version_mismatch_3a"

    def test_etl_version_mismatch_2a_raises(self):
        with pytest.raises(Layer3BInputError) as exc:
            llm_layer3b_goal_timeline_viability(
                user_id=1,
                layer1_payload=_make_layer1(),
                layer3a_payload=_make_layer3a(),
                layer2a_payload=_make_layer2a(etl_version_set={"0A": "vDIFFERENT"}),
                race_event_payload=_make_race_event(),
                current_date=date(2026, 5, 20),
                etl_version_set=_DEFAULT_ETL,
                goal_outcome="Finish",
                llm_caller=_stub_caller(_good_tool_args()),
            )
        assert exc.value.code == "etl_version_mismatch_2a"

    def test_no_included_disciplines_raises(self):
        l2a = _make_layer2a()
        for d in l2a.disciplines:
            d.inclusion = "excluded"
        with pytest.raises(Layer3BInputError) as exc:
            llm_layer3b_goal_timeline_viability(
                user_id=1,
                layer1_payload=_make_layer1(),
                layer3a_payload=_make_layer3a(),
                layer2a_payload=l2a,
                race_event_payload=_make_race_event(),
                current_date=date(2026, 5, 20),
                etl_version_set=_DEFAULT_ETL,
                goal_outcome="Finish",
                llm_caller=_stub_caller(_good_tool_args()),
            )
        assert exc.value.code == "no_included_disciplines"

    def test_event_date_in_past_raises_fatal(self):
        with pytest.raises(Layer3BInputError) as exc:
            llm_layer3b_goal_timeline_viability(
                user_id=1,
                layer1_payload=_make_layer1(),
                layer3a_payload=_make_layer3a(),
                layer2a_payload=_make_layer2a(),
                race_event_payload=_make_race_event(event_date=date(2026, 4, 1)),
                current_date=date(2026, 5, 20),
                etl_version_set=_DEFAULT_ETL,
                goal_outcome="Finish",
                llm_caller=_explode_caller,
            )
        assert exc.value.code == "event_date_in_past"

    def test_event_mode_missing_goal_outcome_raises(self):
        with pytest.raises(Layer3BInputError) as exc:
            llm_layer3b_goal_timeline_viability(
                user_id=1,
                layer1_payload=_make_layer1(),
                layer3a_payload=_make_layer3a(),
                layer2a_payload=_make_layer2a(),
                race_event_payload=_make_race_event(),
                current_date=date(2026, 5, 20),
                etl_version_set=_DEFAULT_ETL,
                goal_outcome=None,
                llm_caller=_stub_caller(_good_tool_args()),
            )
        assert exc.value.code == "event_mode_missing_goal_outcome"

    def test_event_mode_invalid_goal_outcome_raises(self):
        with pytest.raises(Layer3BInputError) as exc:
            llm_layer3b_goal_timeline_viability(
                user_id=1,
                layer1_payload=_make_layer1(),
                layer3a_payload=_make_layer3a(),
                layer2a_payload=_make_layer2a(),
                race_event_payload=_make_race_event(),
                current_date=date(2026, 5, 20),
                etl_version_set=_DEFAULT_ETL,
                goal_outcome="Win The Whole Thing",
                llm_caller=_stub_caller(_good_tool_args()),
            )
        assert exc.value.code == "event_mode_invalid_goal_outcome"

    def test_no_event_mode_missing_plan_duration_raises(self):
        with pytest.raises(Layer3BInputError) as exc:
            llm_layer3b_goal_timeline_viability(
                user_id=1,
                layer1_payload=_make_layer1(),
                layer3a_payload=_make_layer3a(),
                layer2a_payload=_make_layer2a(),
                race_event_payload=None,
                current_date=date(2026, 5, 20),
                etl_version_set=_DEFAULT_ETL,
                plan_duration_weeks=None,
                non_event_goal_type="endurance",
                llm_caller=_stub_caller(_good_tool_args(mode="no-event")),
            )
        assert exc.value.code == "no_event_mode_missing_fields"

    def test_no_event_mode_invalid_plan_duration_raises(self):
        with pytest.raises(Layer3BInputError) as exc:
            llm_layer3b_goal_timeline_viability(
                user_id=1,
                layer1_payload=_make_layer1(),
                layer3a_payload=_make_layer3a(),
                layer2a_payload=_make_layer2a(),
                race_event_payload=None,
                current_date=date(2026, 5, 20),
                etl_version_set=_DEFAULT_ETL,
                plan_duration_weeks=99,
                non_event_goal_type="endurance",
                llm_caller=_stub_caller(_good_tool_args(mode="no-event")),
            )
        assert exc.value.code == "no_event_mode_missing_fields"

    def test_no_event_mode_missing_goal_type_raises(self):
        with pytest.raises(Layer3BInputError) as exc:
            llm_layer3b_goal_timeline_viability(
                user_id=1,
                layer1_payload=_make_layer1(),
                layer3a_payload=_make_layer3a(),
                layer2a_payload=_make_layer2a(),
                race_event_payload=None,
                current_date=date(2026, 5, 20),
                etl_version_set=_DEFAULT_ETL,
                plan_duration_weeks=16,
                non_event_goal_type=None,
                llm_caller=_stub_caller(_good_tool_args(mode="no-event")),
            )
        assert exc.value.code == "no_event_mode_missing_fields"

    def test_unapproved_model_raises(self):
        with pytest.raises(Layer3BInputError) as exc:
            llm_layer3b_goal_timeline_viability(
                user_id=1,
                layer1_payload=_make_layer1(),
                layer3a_payload=_make_layer3a(),
                layer2a_payload=_make_layer2a(),
                race_event_payload=_make_race_event(),
                current_date=date(2026, 5, 20),
                etl_version_set=_DEFAULT_ETL,
                goal_outcome="Finish",
                model="gpt-5",
                llm_caller=_stub_caller(_good_tool_args()),
            )
        assert exc.value.code == "unapproved_model"

    def test_invalid_temperature_raises(self):
        with pytest.raises(Layer3BInputError) as exc:
            llm_layer3b_goal_timeline_viability(
                user_id=1,
                layer1_payload=_make_layer1(),
                layer3a_payload=_make_layer3a(),
                layer2a_payload=_make_layer2a(),
                race_event_payload=_make_race_event(),
                current_date=date(2026, 5, 20),
                etl_version_set=_DEFAULT_ETL,
                goal_outcome="Finish",
                temperature=1.5,
                llm_caller=_stub_caller(_good_tool_args()),
            )
        assert exc.value.code == "invalid_temp"


# ─── §4 tool schema ──────────────────────────────────────────────────────────


class TestToolSchema:
    def test_tool_name_is_emit_layer3b_payload(self):
        assert build_emit_layer3b_payload_tool()["name"] == "emit_layer3b_payload"

    def test_required_top_level_fields(self):
        schema = build_emit_layer3b_payload_tool()["input_schema"]
        assert set(schema["required"]) == {
            "mode",
            "goal_viability",
            "periodization_shape",
            "hitl_surface",
            "notable_observations",
        }

    def test_mode_enum(self):
        schema = build_emit_layer3b_payload_tool()["input_schema"]
        assert schema["properties"]["mode"]["enum"] == ["event", "no-event"]

    def test_viability_enum(self):
        schema = build_emit_layer3b_payload_tool()["input_schema"]
        viability_enum = schema["properties"]["goal_viability"]["properties"]["viability"]["enum"]
        assert set(viability_enum) == {
            "achievable",
            "achievable-with-adjustment",
            "unrealistic-as-stated",
        }

    def test_periodization_mode_enum(self):
        schema = build_emit_layer3b_payload_tool()["input_schema"]
        mode_enum = schema["properties"]["periodization_shape"]["properties"]["mode"]["enum"]
        assert set(mode_enum) == {"standard", "compressed", "extended", "custom"}

    def test_start_phase_enum(self):
        schema = build_emit_layer3b_payload_tool()["input_schema"]
        sp_enum = schema["properties"]["periodization_shape"]["properties"]["start_phase"]["enum"]
        assert set(sp_enum) == {"Base", "Build", "Peak", "Taper"}

    def test_hitl_severity_enum(self):
        schema = build_emit_layer3b_payload_tool()["input_schema"]
        sev_enum = schema["properties"]["hitl_surface"]["items"]["properties"]["severity"]["enum"]
        assert set(sev_enum) == {"blocker", "warning", "informational"}

    def test_observation_category_enum(self):
        schema = build_emit_layer3b_payload_tool()["input_schema"]
        cat_enum = schema["properties"]["notable_observations"]["items"]["properties"][
            "category"
        ]["enum"]
        assert set(cat_enum) == {"warning", "opportunity", "data_gap", "data_hygiene"}

    def test_observation_max_items(self):
        schema = build_emit_layer3b_payload_tool()["input_schema"]
        assert schema["properties"]["notable_observations"]["maxItems"] == 10

    def test_additional_properties_false_throughout(self):
        schema = build_emit_layer3b_payload_tool()["input_schema"]
        assert schema["additionalProperties"] is False
        for sub in ("goal_viability", "periodization_shape"):
            assert schema["properties"][sub]["additionalProperties"] is False
        # hitl_surface item-level
        assert (
            schema["properties"]["hitl_surface"]["items"]["additionalProperties"]
            is False
        )


# ─── §13 happy path end-to-end + metadata stamping ───────────────────────────


class TestEntryPointHappyPath:
    def test_event_mode_round_trip_stamps_metadata_and_event_fields(self):
        race = _make_race_event(event_date=date(2026, 7, 17))
        result = llm_layer3b_goal_timeline_viability(
            user_id=42,
            layer1_payload=_make_layer1(),
            layer3a_payload=_make_layer3a(),
            layer2a_payload=_make_layer2a(),
            race_event_payload=race,
            current_date=date(2026, 5, 20),
            etl_version_set=_DEFAULT_ETL,
            goal_outcome="Finish",
            llm_caller=_stub_caller(_good_tool_args()),
        )
        assert result.user_id == 42
        assert result.mode == "event"
        # D14 event-metadata population
        assert result.event_date == date(2026, 7, 17)
        assert result.event_locale_id == "nerstrand-mn"
        assert result.race_format == "continuous_multi_day"
        # #334: (2026-07-17 - 2026-05-20) = 58 days → ceil((58+1)/7) = 9
        assert result.time_to_event_weeks == 9
        # Metadata stamping
        assert result.model == "claude-sonnet-4-6"
        assert len(result.prompt_hash) == 64  # sha256 hex
        assert result.input_tokens == 2800
        assert result.output_tokens == 600

    def test_no_event_mode_round_trip_leaves_event_fields_none(self):
        result = llm_layer3b_goal_timeline_viability(
            user_id=1,
            layer1_payload=_make_layer1(),
            layer3a_payload=_make_layer3a(),
            layer2a_payload=_make_layer2a(),
            race_event_payload=None,
            current_date=date(2026, 5, 20),
            etl_version_set=_DEFAULT_ETL,
            plan_duration_weeks=16,
            non_event_goal_type="endurance",
            llm_caller=_stub_caller(
                _good_tool_args(
                    mode="no-event",
                    periodization_mode="standard",
                    start_phase="Base",
                )
            ),
        )
        assert result.mode == "no-event"
        assert result.event_date is None
        assert result.event_locale_id is None
        assert result.race_format is None
        assert result.time_to_event_weeks is None

    def test_no_event_mode_resolves_from_layer1_when_kwargs_absent(self):
        l1 = _make_layer1(
            plan_duration_weeks_no_event=12, non_event_goal_type="general_fitness"
        )
        result = llm_layer3b_goal_timeline_viability(
            user_id=1,
            layer1_payload=l1,
            layer3a_payload=_make_layer3a(),
            layer2a_payload=_make_layer2a(),
            race_event_payload=None,
            current_date=date(2026, 5, 20),
            etl_version_set=_DEFAULT_ETL,
            # No kwargs — driver resolves from Layer1EventGoal
            llm_caller=_stub_caller(
                _good_tool_args(
                    mode="no-event",
                    periodization_mode="standard",
                    start_phase="Base",
                )
            ),
        )
        assert result.mode == "no-event"


# ─── §5.5 step 2 mode-discriminator enforcement ──────────────────────────────


class TestModeDiscriminator:
    def test_llm_emits_no_event_in_event_mode_raises_schema_violation(self):
        # When LLM emits mode='no-event' in event-mode context, the driver
        # populates event-metadata fields per D14, and the resulting payload
        # fails pydantic's _check_event_mode_consistency (no-event requires
        # all 4 fields None). The error surfaces via schema_violation after
        # retry exhaustion — pydantic catches the inconsistency before the
        # post-LLM mode-discriminator check.
        with pytest.raises(Layer3BOutputError) as exc:
            llm_layer3b_goal_timeline_viability(
                user_id=1,
                layer1_payload=_make_layer1(),
                layer3a_payload=_make_layer3a(),
                layer2a_payload=_make_layer2a(),
                race_event_payload=_make_race_event(),
                current_date=date(2026, 5, 20),
                etl_version_set=_DEFAULT_ETL,
                goal_outcome="Finish",
                llm_caller=_stub_caller(_good_tool_args(mode="no-event")),
            )
        assert exc.value.code == "schema_violation"

    def test_llm_emits_event_in_no_event_mode_raises(self):
        with pytest.raises(Layer3BOutputError) as exc:
            llm_layer3b_goal_timeline_viability(
                user_id=1,
                layer1_payload=_make_layer1(),
                layer3a_payload=_make_layer3a(),
                layer2a_payload=_make_layer2a(),
                race_event_payload=None,
                current_date=date(2026, 5, 20),
                etl_version_set=_DEFAULT_ETL,
                plan_duration_weeks=16,
                non_event_goal_type="endurance",
                llm_caller=_stub_caller(
                    _good_tool_args(mode="event", periodization_mode="standard", start_phase="Base")
                ),
            )
        assert exc.value.code == "mode_mismatch"


# ─── §6.5 confidence-floor clamp ────────────────────────────────────────────


class TestConfidenceFloors:
    def test_clamp_helper_does_not_upgrade(self):
        assert _clamp_confidence("low", "high") == "low"
        assert _clamp_confidence("medium", "high") == "medium"
        assert _clamp_confidence("high", "medium") == "medium"

    def test_floor1_first_time_competitive_clamps_to_medium(self):
        result = llm_layer3b_goal_timeline_viability(
            user_id=1,
            layer1_payload=_make_layer1(),
            layer3a_payload=_make_layer3a(),
            layer2a_payload=_make_layer2a(),
            race_event_payload=_make_race_event(),
            current_date=date(2026, 5, 20),
            etl_version_set=_DEFAULT_ETL,
            goal_outcome="Podium",
            first_time_at_distance=True,
            llm_caller=_stub_caller(
                _good_tool_args(
                    viability="achievable-with-adjustment", confidence="high"
                )
            ),
        )
        assert result.goal_viability.confidence == "medium"
        clamped = [o for o in result.notable_observations if o.text.startswith("Confidence clamped")]
        assert len(clamped) == 1
        assert "first_time_competitive_goal" in clamped[0].text

    def test_floor2_layer3a_low_trajectory_clamps_to_medium(self):
        result = llm_layer3b_goal_timeline_viability(
            user_id=1,
            layer1_payload=_make_layer1(),
            layer3a_payload=_make_layer3a(trajectory_confidence="low"),
            layer2a_payload=_make_layer2a(),
            race_event_payload=_make_race_event(),
            current_date=date(2026, 5, 20),
            etl_version_set=_DEFAULT_ETL,
            goal_outcome="Finish",
            llm_caller=_stub_caller(_good_tool_args(confidence="high")),
        )
        assert result.goal_viability.confidence == "medium"

    def test_floor3_no_event_no_providers_stale_clamps_to_low(self):
        result = llm_layer3b_goal_timeline_viability(
            user_id=1,
            layer1_payload=_make_layer1(),
            layer3a_payload=_make_layer3a(
                connected_providers=[], self_report_freshness_days=45
            ),
            layer2a_payload=_make_layer2a(),
            race_event_payload=None,
            current_date=date(2026, 5, 20),
            etl_version_set=_DEFAULT_ETL,
            plan_duration_weeks=16,
            non_event_goal_type="endurance",
            llm_caller=_stub_caller(
                _good_tool_args(
                    mode="no-event",
                    confidence="high",
                    periodization_mode="standard",
                    start_phase="Base",
                )
            ),
        )
        assert result.goal_viability.confidence == "low"

    def test_floor4_event_no_attempts_first_time_clamps_to_medium(self):
        result = llm_layer3b_goal_timeline_viability(
            user_id=1,
            layer1_payload=_make_layer1(),
            layer3a_payload=_make_layer3a(),
            layer2a_payload=_make_layer2a(),
            race_event_payload=_make_race_event(),
            current_date=date(2026, 5, 20),
            etl_version_set=_DEFAULT_ETL,
            goal_outcome="Finish",
            first_time_at_distance=True,
            previous_attempts=None,
            llm_caller=_stub_caller(_good_tool_args(confidence="high")),
        )
        assert result.goal_viability.confidence == "medium"

    def test_no_clamp_signal_no_observation(self):
        result = llm_layer3b_goal_timeline_viability(
            user_id=1,
            layer1_payload=_make_layer1(),
            layer3a_payload=_make_layer3a(),
            layer2a_payload=_make_layer2a(),
            race_event_payload=_make_race_event(),
            current_date=date(2026, 5, 20),
            etl_version_set=_DEFAULT_ETL,
            goal_outcome="Finish",
            first_time_at_distance=False,
            previous_attempts=[{"outcome": "Finished", "dnf_cause": ""}],
            llm_caller=_stub_caller(_good_tool_args(confidence="medium")),
        )
        assert all(
            "Confidence clamped" not in o.text for o in result.notable_observations
        )

    def test_clamp_does_not_upgrade_low_to_medium(self):
        result = llm_layer3b_goal_timeline_viability(
            user_id=1,
            layer1_payload=_make_layer1(),
            layer3a_payload=_make_layer3a(),
            layer2a_payload=_make_layer2a(),
            race_event_payload=_make_race_event(),
            current_date=date(2026, 5, 20),
            etl_version_set=_DEFAULT_ETL,
            goal_outcome="Podium",
            first_time_at_distance=True,
            llm_caller=_stub_caller(
                _good_tool_args(viability="achievable-with-adjustment", confidence="low")
            ),
        )
        assert result.goal_viability.confidence == "low"


# ─── §6.1 HITL auto-emit ─────────────────────────────────────────────────────


class TestHITLAutoEmit:
    def test_unrealistic_goal_auto_emits_blocker(self):
        result = llm_layer3b_goal_timeline_viability(
            user_id=1,
            layer1_payload=_make_layer1(),
            layer3a_payload=_make_layer3a(),
            layer2a_payload=_make_layer2a(),
            race_event_payload=_make_race_event(event_date=date(2026, 6, 17)),  # 4 weeks
            current_date=date(2026, 5, 20),
            etl_version_set=_DEFAULT_ETL,
            goal_outcome="Podium",
            llm_caller=_stub_caller(
                _good_tool_args(
                    viability="unrealistic-as-stated",
                    confidence="high",
                    periodization_mode="compressed",
                    start_phase="Taper",
                )
            ),
        )
        labels = {h.item_label for h in result.hitl_surface}
        assert "3B.unrealistic_goal" in labels
        unrealistic = next(
            h for h in result.hitl_surface if h.item_label == "3B.unrealistic_goal"
        )
        assert unrealistic.severity == "blocker"
        assert unrealistic.acknowledge_option is None  # §7 schema rule

    def test_first_time_competitive_auto_emits_warning(self):
        result = llm_layer3b_goal_timeline_viability(
            user_id=1,
            layer1_payload=_make_layer1(),
            layer3a_payload=_make_layer3a(),
            layer2a_payload=_make_layer2a(),
            race_event_payload=_make_race_event(),
            current_date=date(2026, 5, 20),
            etl_version_set=_DEFAULT_ETL,
            goal_outcome="Compete mid-pack",
            first_time_at_distance=True,
            llm_caller=_stub_caller(
                _good_tool_args(viability="achievable-with-adjustment")
            ),
        )
        labels = {h.item_label for h in result.hitl_surface}
        assert "3B.first_time_competitive_goal" in labels

    def test_dnf_recurrence_within_window_auto_emits_warning(self):
        result = llm_layer3b_goal_timeline_viability(
            user_id=1,
            layer1_payload=_make_layer1(),
            layer3a_payload=_make_layer3a(),
            layer2a_payload=_make_layer2a(),
            race_event_payload=_make_race_event(event_date=date(2026, 7, 1)),  # ~6wk
            current_date=date(2026, 5, 20),
            etl_version_set=_DEFAULT_ETL,
            goal_outcome="Finish",
            previous_attempts=[{"outcome": "DNF", "dnf_cause": "quad_failure"}],
            llm_caller=_stub_caller(_good_tool_args()),
        )
        labels = {h.item_label for h in result.hitl_surface}
        assert "3B.dnf_recurrence_risk" in labels

    def test_dnf_outside_window_does_not_auto_emit(self):
        # quad_failure window = 12 weeks; event 16 weeks away → safe
        result = llm_layer3b_goal_timeline_viability(
            user_id=1,
            layer1_payload=_make_layer1(),
            layer3a_payload=_make_layer3a(),
            layer2a_payload=_make_layer2a(),
            race_event_payload=_make_race_event(event_date=date(2026, 9, 11)),
            current_date=date(2026, 5, 20),
            etl_version_set=_DEFAULT_ETL,
            goal_outcome="Finish",
            previous_attempts=[{"outcome": "DNF", "dnf_cause": "quad_failure"}],
            llm_caller=_stub_caller(
                _good_tool_args(periodization_mode="standard", start_phase="Base")
            ),
        )
        labels = {h.item_label for h in result.hitl_surface}
        assert "3B.dnf_recurrence_risk" not in labels

    def test_compressed_on_fatigued_auto_emits_warning(self):
        result = llm_layer3b_goal_timeline_viability(
            user_id=1,
            layer1_payload=_make_layer1(),
            layer3a_payload=_make_layer3a(short_term="fatigued"),
            layer2a_payload=_make_layer2a(),
            race_event_payload=_make_race_event(event_date=date(2026, 6, 17)),  # 4wk
            current_date=date(2026, 5, 20),
            etl_version_set=_DEFAULT_ETL,
            goal_outcome="Finish",
            llm_caller=_stub_caller(
                _good_tool_args(periodization_mode="compressed", start_phase="Taper")
            ),
        )
        labels = {h.item_label for h in result.hitl_surface}
        assert "3B.compressed_on_fatigued_athlete" in labels

    def test_dedup_when_llm_already_emitted_item(self):
        pre_emitted = [
            {
                "source": "3B",
                "item_label": "3B.unrealistic_goal",
                "severity": "blocker",
                "description": "LLM-emitted description",
                "recommended_action": "LLM-emitted action",
                "acknowledge_option": None,
                "revise_option": "LLM-emitted revise",
                "revise_target": "h2.goal_outcome",
            }
        ]
        result = llm_layer3b_goal_timeline_viability(
            user_id=1,
            layer1_payload=_make_layer1(),
            layer3a_payload=_make_layer3a(),
            layer2a_payload=_make_layer2a(),
            race_event_payload=_make_race_event(event_date=date(2026, 6, 17)),
            current_date=date(2026, 5, 20),
            etl_version_set=_DEFAULT_ETL,
            goal_outcome="Podium",
            llm_caller=_stub_caller(
                _good_tool_args(
                    viability="unrealistic-as-stated",
                    confidence="high",
                    periodization_mode="compressed",
                    start_phase="Taper",
                    hitl_surface=pre_emitted,
                )
            ),
        )
        labels = [h.item_label for h in result.hitl_surface]
        assert labels.count("3B.unrealistic_goal") == 1
        # LLM-emitted item kept (not replaced)
        kept = next(h for h in result.hitl_surface if h.item_label == "3B.unrealistic_goal")
        assert kept.description == "LLM-emitted description"

    def test_dnf_recovery_window_mapping(self):
        # Defensive: the spec §6.1 mapping must be loaded
        assert _DNF_RECOVERY_WINDOW_WEEKS["quad_failure"] == 12
        assert _DNF_RECOVERY_WINDOW_WEEKS["nutrition_blowup"] == 4
        assert _DNF_RECOVERY_WINDOW_WEEKS["injury_during_event"] == 16
        assert _DEFAULT_DNF_RECOVERY_WINDOW_WEEKS == 8


# ─── §5.5 step 4 periodization sanity loop ───────────────────────────────────


class TestPeriodizationSanity:
    def test_custom_with_correct_sum_passes(self):
        result = llm_layer3b_goal_timeline_viability(
            user_id=1,
            layer1_payload=_make_layer1(),
            layer3a_payload=_make_layer3a(),
            layer2a_payload=_make_layer2a(),
            race_event_payload=_make_race_event(event_date=date(2026, 7, 22)),  # 9wk
            current_date=date(2026, 5, 20),
            etl_version_set=_DEFAULT_ETL,
            goal_outcome="Finish",
            llm_caller=_stub_caller(
                _good_tool_args(
                    periodization_mode="custom",
                    start_phase="Build",
                    phase_weeks={"Base": 0, "Build": 5, "Peak": 3, "Taper": 1},
                )
            ),
        )
        # Sum = 9, target = 9 → passes
        assert result.periodization_shape.mode == "custom"
        assert sum(result.periodization_shape.phase_weeks.values()) == 9

    def test_custom_with_sum_within_one_week_passes(self):
        result = llm_layer3b_goal_timeline_viability(
            user_id=1,
            layer1_payload=_make_layer1(),
            layer3a_payload=_make_layer3a(),
            layer2a_payload=_make_layer2a(),
            race_event_payload=_make_race_event(event_date=date(2026, 7, 22)),
            current_date=date(2026, 5, 20),
            etl_version_set=_DEFAULT_ETL,
            goal_outcome="Finish",
            llm_caller=_stub_caller(
                _good_tool_args(
                    periodization_mode="custom",
                    start_phase="Build",
                    phase_weeks={"Base": 0, "Build": 5, "Peak": 3, "Taper": 2},
                )
            ),
        )
        # Sum = 10, target = 9, deviation = 1 → passes
        assert result.periodization_shape.mode == "custom"

    def test_custom_with_mismatched_sum_retries_then_falls_back(self):
        # Both LLM calls return bad sums → persistent failure → fallback
        bad_args_1 = _good_tool_args(
            periodization_mode="custom",
            start_phase="Build",
            phase_weeks={"Base": 0, "Build": 5, "Peak": 3, "Taper": 5},  # sum=13
        )
        bad_args_2 = _good_tool_args(
            periodization_mode="custom",
            start_phase="Build",
            phase_weeks={"Base": 0, "Build": 5, "Peak": 3, "Taper": 4},  # sum=12
        )
        result = llm_layer3b_goal_timeline_viability(
            user_id=1,
            layer1_payload=_make_layer1(),
            layer3a_payload=_make_layer3a(),
            layer2a_payload=_make_layer2a(),
            race_event_payload=_make_race_event(event_date=date(2026, 7, 22)),  # 9wk
            current_date=date(2026, 5, 20),
            etl_version_set=_DEFAULT_ETL,
            goal_outcome="Finish",
            llm_caller=_sequence_caller([bad_args_1, bad_args_2]),
        )
        # Fallback path: mode flipped to standard, phase_weeks=None
        assert result.periodization_shape.mode == "standard"
        assert result.periodization_shape.phase_weeks is None
        # Auto-appended observation
        fallback_obs = [
            o for o in result.notable_observations
            if "fell back from custom to standard" in o.text
        ]
        assert len(fallback_obs) == 1
        assert fallback_obs[0].category == "data_hygiene"

    def test_custom_with_mismatched_sum_retry_succeeds(self):
        # First call bad sum; retry returns good sum → success without fallback
        bad_args = _good_tool_args(
            periodization_mode="custom",
            start_phase="Build",
            phase_weeks={"Base": 0, "Build": 5, "Peak": 3, "Taper": 5},  # sum=13
        )
        good_args = _good_tool_args(
            periodization_mode="custom",
            start_phase="Build",
            phase_weeks={"Base": 0, "Build": 5, "Peak": 3, "Taper": 1},  # sum=9
        )
        result = llm_layer3b_goal_timeline_viability(
            user_id=1,
            layer1_payload=_make_layer1(),
            layer3a_payload=_make_layer3a(),
            layer2a_payload=_make_layer2a(),
            race_event_payload=_make_race_event(event_date=date(2026, 7, 22)),
            current_date=date(2026, 5, 20),
            etl_version_set=_DEFAULT_ETL,
            goal_outcome="Finish",
            llm_caller=_sequence_caller([bad_args, good_args]),
        )
        # Retry succeeded — mode stays custom
        assert result.periodization_shape.mode == "custom"
        # No fallback observation
        assert not any(
            "fell back" in o.text for o in result.notable_observations
        )

    def test_non_custom_modes_skip_sanity_check(self):
        # Sanity check only applies to custom mode
        result = llm_layer3b_goal_timeline_viability(
            user_id=1,
            layer1_payload=_make_layer1(),
            layer3a_payload=_make_layer3a(),
            layer2a_payload=_make_layer2a(),
            race_event_payload=_make_race_event(event_date=date(2026, 7, 22)),
            current_date=date(2026, 5, 20),
            etl_version_set=_DEFAULT_ETL,
            goal_outcome="Finish",
            llm_caller=_stub_caller(
                _good_tool_args(periodization_mode="compressed", start_phase="Build")
            ),
        )
        assert result.periodization_shape.mode == "compressed"

    def test_check_periodization_sanity_helper(self):
        # Build a payload with valid custom mode + correct sum
        from layer4.context import GoalViability, PeriodizationShape, Layer3BPayload

        payload = Layer3BPayload(
            user_id=1,
            as_of=datetime(2026, 5, 20, 0, 0),
            mode="event",
            model="claude-sonnet-4-6",
            temperature=0.0,
            prompt_hash="x" * 64,
            latency_ms=2000,
            input_tokens=2800,
            output_tokens=600,
            etl_version_set=_DEFAULT_ETL,
            goal_viability=GoalViability(
                viability="achievable",
                confidence="medium",
                reasoning_text="r",
                evidence_basis=["h2.goal_outcome"],
                suggested_adjustments=[],
            ),
            periodization_shape=PeriodizationShape(
                mode="custom",
                start_phase="Build",
                phase_weeks={"Base": 0, "Build": 5, "Peak": 3, "Taper": 1},
                reasoning_text="r",
                evidence_basis=["x"],
            ),
            hitl_surface=[],
            notable_observations=[],
            event_date=date(2026, 7, 22),
            event_locale_id="x",
            race_format="single_day",
            time_to_event_weeks=9,
        )
        passed, actual, _ = _check_periodization_sanity(payload, 9)
        assert passed is True and actual == 9

    def test_check_periodization_sanity_rejects_weeks_before_start_phase(self):
        # Total sum (12) matches target, but all weeks sit BEFORE
        # start_phase=Peak. The old check (total-sum only) passed this; the
        # tightened check rejects it so it can't 500 in Layer 4's
        # _allocate_weeks_custom.
        from layer4.context import GoalViability, PeriodizationShape, Layer3BPayload

        payload = Layer3BPayload(
            user_id=1,
            as_of=datetime(2026, 5, 20, 0, 0),
            mode="event",
            model="claude-sonnet-4-6",
            temperature=0.0,
            prompt_hash="x" * 64,
            latency_ms=2000,
            input_tokens=2800,
            output_tokens=600,
            etl_version_set=_DEFAULT_ETL,
            goal_viability=GoalViability(
                viability="achievable",
                confidence="medium",
                reasoning_text="r",
                evidence_basis=["h2.goal_outcome"],
                suggested_adjustments=[],
            ),
            periodization_shape=PeriodizationShape(
                mode="custom",
                start_phase="Peak",
                phase_weeks={"Base": 8, "Build": 4, "Peak": 0, "Taper": 0},
                reasoning_text="r",
                evidence_basis=["x"],
            ),
            hitl_surface=[],
            notable_observations=[],
            event_date=date(2026, 8, 12),
            event_locale_id="x",
            race_format="single_day",
            time_to_event_weeks=12,
        )
        passed, _, _ = _check_periodization_sanity(payload, 12)
        assert passed is False

    def test_custom_weeks_parked_before_start_phase_falls_back(self):
        # End-to-end: a custom shape whose weeks all sit before start_phase
        # routes through the existing retry+fallback to a standard plan rather
        # than walling Layer 4.
        bad = _good_tool_args(
            periodization_mode="custom",
            start_phase="Peak",
            phase_weeks={"Base": 8, "Build": 4, "Peak": 0, "Taper": 0},
        )
        result = llm_layer3b_goal_timeline_viability(
            user_id=1,
            layer1_payload=_make_layer1(),
            layer3a_payload=_make_layer3a(),
            layer2a_payload=_make_layer2a(),
            race_event_payload=_make_race_event(event_date=date(2026, 8, 12)),  # 12wk
            current_date=date(2026, 5, 20),
            etl_version_set=_DEFAULT_ETL,
            goal_outcome="Finish",
            llm_caller=_stub_caller(bad),
        )
        assert result.periodization_shape.mode == "standard"
        assert result.periodization_shape.phase_weeks is None


# ─── §8.2 notable_observations budget (pre-validation clamp) ──────────────────


class TestNotableObservationsBudget:
    def test_over_budget_observations_clamped_not_schema_violation(self):
        # 12 observations (> the 10 cap). max_length=10 + the API not hard-
        # enforcing maxItems means without the pre-validation clamp this walls
        # on schema_violation (the 3A weak_links twin). Lowest-priority
        # data_hygiene items drop; the 4 warnings survive.
        obs = (
            [
                {
                    "category": "data_hygiene",
                    "text": f"hygiene note {i}",
                    "evidence_basis": ["x"],
                    "elevates_to_hitl": False,
                }
                for i in range(8)
            ]
            + [
                {
                    "category": "warning",
                    "text": f"warning note {i}",
                    "evidence_basis": ["x"],
                    "elevates_to_hitl": False,
                }
                for i in range(4)
            ]
        )
        result = llm_layer3b_goal_timeline_viability(
            user_id=1,
            layer1_payload=_make_layer1(),
            layer3a_payload=_make_layer3a(),
            layer2a_payload=_make_layer2a(),
            race_event_payload=_make_race_event(event_date=date(2026, 7, 22)),
            current_date=date(2026, 5, 20),
            etl_version_set=_DEFAULT_ETL,
            goal_outcome="Finish",
            llm_caller=_stub_caller(_good_tool_args(observations=obs)),
        )
        assert len(result.notable_observations) <= 10
        warns = [o for o in result.notable_observations if o.category == "warning"]
        assert len(warns) == 4

    def test_over_length_observation_text_truncated_not_schema_violation(self):
        # Per-string twin of the budget clamp: Layer3Observation.text is
        # max_length=240 and the tool-schema maxLength is only an API hint, so a
        # long observation walls the cone on schema_violation. The driver
        # truncates to the cap before validation instead of failing.
        long_text = (
            "The requested finish target sits well outside the band the current "
            "fitness trajectory supports given the compressed runway to race day, "
            "and the volume ramp required to close that gap would push acute load "
            "into the non-functional-overreach zone, so the timeline needs an "
            "explicit viability conversation before the plan is generated."
        )
        assert len(long_text) > 240
        result = llm_layer3b_goal_timeline_viability(
            user_id=1,
            layer1_payload=_make_layer1(),
            layer3a_payload=_make_layer3a(),
            layer2a_payload=_make_layer2a(),
            race_event_payload=_make_race_event(event_date=date(2026, 7, 22)),
            current_date=date(2026, 5, 20),
            etl_version_set=_DEFAULT_ETL,
            goal_outcome="Finish",
            llm_caller=_stub_caller(
                _good_tool_args(
                    observations=[
                        {
                            "category": "warning",
                            "text": long_text,
                            "evidence_basis": ["x"],
                            "elevates_to_hitl": True,
                        }
                    ]
                )
            ),
        )
        emitted = [o for o in result.notable_observations if o.text.endswith("…")]
        assert len(emitted) == 1
        assert len(emitted[0].text) <= 240
        assert emitted[0].category == "warning"
        assert emitted[0].elevates_to_hitl is True


# ─── §5.5 step 1 schema violation retry ──────────────────────────────────────


class TestSchemaViolation:
    def test_invalid_then_valid_succeeds_after_retry(self):
        # First call emits a bad enum; second emits valid
        bad = _good_tool_args()
        bad["goal_viability"]["viability"] = "totally-bogus"
        good = _good_tool_args()
        result = llm_layer3b_goal_timeline_viability(
            user_id=1,
            layer1_payload=_make_layer1(),
            layer3a_payload=_make_layer3a(),
            layer2a_payload=_make_layer2a(),
            race_event_payload=_make_race_event(),
            current_date=date(2026, 5, 20),
            etl_version_set=_DEFAULT_ETL,
            goal_outcome="Finish",
            llm_caller=_sequence_caller([bad, good]),
        )
        assert result.goal_viability.viability == "achievable"

    def test_two_invalid_raises_output_error(self):
        bad1 = _good_tool_args()
        bad1["goal_viability"]["viability"] = "nope-1"
        bad2 = _good_tool_args()
        bad2["goal_viability"]["viability"] = "nope-2"
        with pytest.raises(Layer3BOutputError) as exc:
            llm_layer3b_goal_timeline_viability(
                user_id=1,
                layer1_payload=_make_layer1(),
                layer3a_payload=_make_layer3a(),
                layer2a_payload=_make_layer2a(),
                race_event_payload=_make_race_event(),
                current_date=date(2026, 5, 20),
                etl_version_set=_DEFAULT_ETL,
                goal_outcome="Finish",
                llm_caller=_sequence_caller([bad1, bad2]),
            )
        assert exc.value.code == "schema_violation"

    def test_suggested_adjustments_pydantic_rule_enforced(self):
        # achievable + non-empty suggested_adjustments → pydantic fails
        bad = _good_tool_args(viability="achievable")
        bad["goal_viability"]["suggested_adjustments"] = ["should-be-empty"]
        good = _good_tool_args(viability="achievable")  # back to canonical
        result = llm_layer3b_goal_timeline_viability(
            user_id=1,
            layer1_payload=_make_layer1(),
            layer3a_payload=_make_layer3a(),
            layer2a_payload=_make_layer2a(),
            race_event_payload=_make_race_event(),
            current_date=date(2026, 5, 20),
            etl_version_set=_DEFAULT_ETL,
            goal_outcome="Finish",
            llm_caller=_sequence_caller([bad, good]),
        )
        assert result.goal_viability.suggested_adjustments == []


# ─── §5.5 + D9 evidence-basis check ──────────────────────────────────────────


class TestEvidenceBasisCheck:
    def test_unknown_path_warns(self):
        bad_args = _good_tool_args()
        bad_args["goal_viability"]["evidence_basis"] = [
            "h2.goal_outcome",
            "fictional.path",
        ]
        with warnings.catch_warnings(record=True) as caught:
            warnings.simplefilter("always")
            llm_layer3b_goal_timeline_viability(
                user_id=1,
                layer1_payload=_make_layer1(),
                layer3a_payload=_make_layer3a(),
                layer2a_payload=_make_layer2a(),
                race_event_payload=_make_race_event(),
                current_date=date(2026, 5, 20),
                etl_version_set=_DEFAULT_ETL,
                goal_outcome="Finish",
                llm_caller=_stub_caller(bad_args),
            )
        ev_warnings = [
            w for w in caught if issubclass(w.category, Layer3BEvidenceBasisWarning)
        ]
        assert any("fictional.path" in str(w.message) for w in ev_warnings)

    def test_event_mode_missing_h2_reference_warns(self):
        args = _good_tool_args(evidence_basis_h2=False)
        with warnings.catch_warnings(record=True) as caught:
            warnings.simplefilter("always")
            llm_layer3b_goal_timeline_viability(
                user_id=1,
                layer1_payload=_make_layer1(),
                layer3a_payload=_make_layer3a(),
                layer2a_payload=_make_layer2a(),
                race_event_payload=_make_race_event(),
                current_date=date(2026, 5, 20),
                etl_version_set=_DEFAULT_ETL,
                goal_outcome="Finish",
                llm_caller=_stub_caller(args),
            )
        ev_warnings = [
            w for w in caught if issubclass(w.category, Layer3BEvidenceBasisWarning)
        ]
        assert any(
            "must reference at least one h2.*" in str(w.message) for w in ev_warnings
        )

    def test_no_event_mode_with_h2_reference_warns(self):
        args = _good_tool_args(
            mode="no-event",
            periodization_mode="standard",
            start_phase="Base",
        )
        args["goal_viability"]["evidence_basis"] = ["h2.goal_outcome"]  # wrong mode
        with warnings.catch_warnings(record=True) as caught:
            warnings.simplefilter("always")
            llm_layer3b_goal_timeline_viability(
                user_id=1,
                layer1_payload=_make_layer1(),
                layer3a_payload=_make_layer3a(),
                layer2a_payload=_make_layer2a(),
                race_event_payload=None,
                current_date=date(2026, 5, 20),
                etl_version_set=_DEFAULT_ETL,
                plan_duration_weeks=16,
                non_event_goal_type="endurance",
                llm_caller=_stub_caller(args),
            )
        ev_warnings = [
            w for w in caught if issubclass(w.category, Layer3BEvidenceBasisWarning)
        ]
        assert any("must NOT" in str(w.message) for w in ev_warnings)


# ─── §13 test scenarios (TS-1 .. TS-8) ───────────────────────────────────────


class TestS13Scenarios:
    def test_ts1_ar_finisher_compressed(self):
        # 9 weeks, AR Finish, prior expedition AR, 3A good/moderate
        result = llm_layer3b_goal_timeline_viability(
            user_id=1,
            layer1_payload=_make_layer1(),
            layer3a_payload=_make_layer3a(
                aerobic_level="good", strength_level="moderate"
            ),
            layer2a_payload=_make_layer2a(disciplines=4),
            race_event_payload=_make_race_event(event_date=date(2026, 7, 22)),
            current_date=date(2026, 5, 20),
            etl_version_set=_DEFAULT_ETL,
            goal_outcome="Finish",
            first_time_at_distance=False,
            previous_attempts=[
                {"outcome": "Finished", "dnf_cause": ""},
            ],
            llm_caller=_stub_caller(
                _good_tool_args(
                    viability="achievable",
                    confidence="medium",
                    periodization_mode="compressed",
                    start_phase="Build",
                )
            ),
        )
        assert result.goal_viability.viability == "achievable"
        assert result.periodization_shape.mode == "compressed"
        assert not result.hitl_surface  # no blockers/warnings

    def test_ts2_ar_podium_unrealistic_blocker_hitl(self):
        # 4 weeks, Podium → unrealistic + blocker HITL
        result = llm_layer3b_goal_timeline_viability(
            user_id=1,
            layer1_payload=_make_layer1(),
            layer3a_payload=_make_layer3a(),
            layer2a_payload=_make_layer2a(),
            race_event_payload=_make_race_event(event_date=date(2026, 6, 17)),
            current_date=date(2026, 5, 20),
            etl_version_set=_DEFAULT_ETL,
            goal_outcome="Podium",
            llm_caller=_stub_caller(
                _good_tool_args(
                    viability="unrealistic-as-stated",
                    confidence="high",
                    periodization_mode="compressed",
                    start_phase="Taper",
                )
            ),
        )
        assert result.goal_viability.viability == "unrealistic-as-stated"
        blocker = next(
            h for h in result.hitl_surface if h.severity == "blocker"
        )
        assert blocker.item_label == "3B.unrealistic_goal"

    def test_ts3_first_time_competitive_clamps_confidence(self):
        # Trail half, first-time, Compete mid-pack → confidence clamped to medium
        result = llm_layer3b_goal_timeline_viability(
            user_id=1,
            layer1_payload=_make_layer1(primary_sport="Trail Running"),
            layer3a_payload=_make_layer3a(
                aerobic_level="moderate", strength_level="good"
            ),
            layer2a_payload=_make_layer2a(),
            race_event_payload=_make_race_event(
                event_date=date(2026, 8, 12), race_format="single_day"
            ),
            current_date=date(2026, 5, 20),
            etl_version_set=_DEFAULT_ETL,
            goal_outcome="Compete mid-pack",
            first_time_at_distance=True,
            llm_caller=_stub_caller(
                _good_tool_args(
                    viability="achievable-with-adjustment",
                    confidence="high",
                    periodization_mode="standard",
                    start_phase="Base",
                )
            ),
        )
        assert result.goal_viability.confidence == "medium"
        labels = {h.item_label for h in result.hitl_surface}
        assert "3B.first_time_competitive_goal" in labels

    def test_ts4_no_event_endurance_standard(self):
        result = llm_layer3b_goal_timeline_viability(
            user_id=1,
            layer1_payload=_make_layer1(primary_sport="Trail Running"),
            layer3a_payload=_make_layer3a(aerobic_level="low"),
            layer2a_payload=_make_layer2a(),
            race_event_payload=None,
            current_date=date(2026, 5, 20),
            etl_version_set=_DEFAULT_ETL,
            plan_duration_weeks=24,
            non_event_goal_type="endurance",
            llm_caller=_stub_caller(
                _good_tool_args(
                    mode="no-event",
                    viability="achievable",
                    confidence="medium",
                    periodization_mode="standard",
                    start_phase="Base",
                )
            ),
        )
        assert result.mode == "no-event"
        assert result.goal_viability.viability == "achievable"
        assert result.periodization_shape.mode == "standard"

    def test_ts5_no_event_strength_mismatch_observation(self):
        # No-event strength + low strength state — LLM observation, no HITL
        result = llm_layer3b_goal_timeline_viability(
            user_id=1,
            layer1_payload=_make_layer1(primary_sport="Road Cycling"),
            layer3a_payload=_make_layer3a(
                strength_level="low", aerobic_level="good"
            ),
            layer2a_payload=_make_layer2a(),
            race_event_payload=None,
            current_date=date(2026, 5, 20),
            etl_version_set=_DEFAULT_ETL,
            plan_duration_weeks=8,
            non_event_goal_type="strength",
            llm_caller=_stub_caller(
                _good_tool_args(
                    mode="no-event",
                    viability="achievable-with-adjustment",
                    periodization_mode="extended",
                    start_phase="Base",
                    observations=[
                        {
                            "category": "data_hygiene",
                            "text": "Strength goal vs Road Cycling primary — informational",
                            "evidence_basis": ["c.primary_sport", "h3.non_event_goal_type"],
                            "elevates_to_hitl": False,
                        }
                    ],
                )
            ),
        )
        assert result.periodization_shape.mode == "extended"
        # Observation present
        mismatch_obs = [
            o for o in result.notable_observations
            if o.category == "data_hygiene"
        ]
        assert mismatch_obs

    def test_ts6_dnf_recurrence_warning(self):
        # 100-mile ultra, prior DNF (quad_failure), 12 weeks (=window) — emits warning
        result = llm_layer3b_goal_timeline_viability(
            user_id=1,
            layer1_payload=_make_layer1(),
            layer3a_payload=_make_layer3a(),
            layer2a_payload=_make_layer2a(),
            race_event_payload=_make_race_event(
                event_date=date(2026, 8, 5),  # ~11 weeks
                race_format="continuous_multi_day",
            ),
            current_date=date(2026, 5, 20),
            etl_version_set=_DEFAULT_ETL,
            goal_outcome="Finish",
            previous_attempts=[{"outcome": "DNF", "dnf_cause": "quad_failure"}],
            llm_caller=_stub_caller(
                _good_tool_args(
                    viability="achievable-with-adjustment",
                    periodization_mode="standard",
                    start_phase="Base",
                )
            ),
        )
        labels = {h.item_label for h in result.hitl_surface}
        assert "3B.dnf_recurrence_risk" in labels

    def test_ts7_compressed_taper_one_week_out(self):
        result = llm_layer3b_goal_timeline_viability(
            user_id=1,
            layer1_payload=_make_layer1(),
            layer3a_payload=_make_layer3a(),
            layer2a_payload=_make_layer2a(),
            race_event_payload=_make_race_event(event_date=date(2026, 5, 27)),
            current_date=date(2026, 5, 20),
            etl_version_set=_DEFAULT_ETL,
            goal_outcome="Finish",
            llm_caller=_stub_caller(
                _good_tool_args(
                    periodization_mode="compressed", start_phase="Taper"
                )
            ),
        )
        # #334: 7-day gap (2026-05-27 - 2026-05-20) → ceil((7+1)/7) = 2
        assert result.time_to_event_weeks == 2
        assert result.periodization_shape.mode == "compressed"

    def test_ts8_race_date_in_past_fatal_no_llm(self):
        # TS-8: race date in past → fatal validation, no LLM call
        with pytest.raises(Layer3BInputError) as exc:
            llm_layer3b_goal_timeline_viability(
                user_id=1,
                layer1_payload=_make_layer1(),
                layer3a_payload=_make_layer3a(),
                layer2a_payload=_make_layer2a(),
                race_event_payload=_make_race_event(event_date=date(2026, 4, 1)),
                current_date=date(2026, 5, 20),
                etl_version_set=_DEFAULT_ETL,
                goal_outcome="Finish",
                llm_caller=_explode_caller,  # would raise if invoked
            )
        assert exc.value.code == "event_date_in_past"


# ─── Prep dict + prompt rendering ────────────────────────────────────────────


class TestPrepDict:
    def test_event_mode_prep_dict_has_h2_keys(self):
        d = _build_prep_dict(
            mode="event",
            race_event_payload=_make_race_event(),
            layer1_payload=_make_layer1(),
            layer3a_payload=_make_layer3a(),
            layer2a_payload=_make_layer2a(),
            current_date=date(2026, 5, 20),
            plan_duration_weeks=None,
            non_event_goal_type=None,
            goal_outcome="Finish",
            time_goal=None,
            first_time_at_distance=False,
            previous_attempts=None,
            race_distance_km=None,
            race_duration_hr=None,
            race_terrain=None,
            race_pack_weight_kg=None,
        )
        assert "h2.event_date" in d
        assert "h2.goal_outcome" in d
        assert "h2.race_format" in d
        assert "3a.current_state.aerobic_capacity" in d
        assert "2a.framework_sport" in d

    def test_no_event_mode_prep_dict_has_h3_keys(self):
        d = _build_prep_dict(
            mode="no-event",
            race_event_payload=None,
            layer1_payload=_make_layer1(),
            layer3a_payload=_make_layer3a(),
            layer2a_payload=_make_layer2a(),
            current_date=date(2026, 5, 20),
            plan_duration_weeks=16,
            non_event_goal_type="endurance",
            goal_outcome=None,
            time_goal=None,
            first_time_at_distance=None,
            previous_attempts=None,
            race_distance_km=None,
            race_duration_hr=None,
            race_terrain=None,
            race_pack_weight_kg=None,
        )
        assert "h3.plan_duration_weeks" in d
        assert "h3.non_event_goal_type" in d
        assert "h2.event_date" not in d

    def test_render_user_prompt_event_mode(self):
        rendered = _render_user_prompt(
            mode="event",
            race_event_payload=_make_race_event(),
            layer1_payload=_make_layer1(),
            layer3a_payload=_make_layer3a(),
            layer2a_payload=_make_layer2a(),
            current_date=date(2026, 5, 20),
            plan_duration_weeks=None,
            non_event_goal_type=None,
            goal_outcome="Finish",
            time_goal=None,
            first_time_at_distance=False,
            previous_attempts=None,
            race_distance_km=None,
            race_duration_hr=None,
            race_terrain=None,
            race_pack_weight_kg=None,
        )
        assert "mode: event" in rendered
        assert "Today is 2026-05-20" in rendered
        assert "Pocket Gopher Extreme 2026" in rendered

    def test_render_user_prompt_no_event_mode(self):
        rendered = _render_user_prompt(
            mode="no-event",
            race_event_payload=None,
            layer1_payload=_make_layer1(primary_sport="Trail Running"),
            layer3a_payload=_make_layer3a(),
            layer2a_payload=_make_layer2a(),
            current_date=date(2026, 5, 20),
            plan_duration_weeks=16,
            non_event_goal_type="endurance",
            goal_outcome=None,
            time_goal=None,
            first_time_at_distance=None,
            previous_attempts=None,
            race_distance_km=None,
            race_duration_hr=None,
            race_terrain=None,
            race_pack_weight_kg=None,
        )
        assert "mode: no-event" in rendered
        assert "non_event_goal_type: endurance" in rendered
        assert "primary_sport: Trail Running" in rendered

    def test_render_user_prompt_includes_retry_error(self):
        rendered = _render_user_prompt(
            mode="event",
            race_event_payload=_make_race_event(),
            layer1_payload=_make_layer1(),
            layer3a_payload=_make_layer3a(),
            layer2a_payload=_make_layer2a(),
            current_date=date(2026, 5, 20),
            plan_duration_weeks=None,
            non_event_goal_type=None,
            goal_outcome="Finish",
            time_goal=None,
            first_time_at_distance=False,
            previous_attempts=None,
            race_distance_km=None,
            race_duration_hr=None,
            race_terrain=None,
            race_pack_weight_kg=None,
            retry_error="some pydantic error",
        )
        assert "Previous attempt failed schema validation: some pydantic error" in rendered

    def test_time_to_event_weeks_helper(self):
        # #334: race-day-inclusive ceil = ceil((days + 1) / 7), clamped to 0.
        # 58-day gap → ceil(59/7) = 9 (a full week covers the partial remainder
        # so the plan spans through race day).
        assert _time_to_event_weeks(date(2026, 7, 17), date(2026, 5, 20)) == 9
        # Same-day event: 0-day gap → ceil(1/7) = 1 (any today-or-future event
        # gets at least a 1-week plan; a 0-week horizon is degenerate).
        assert _time_to_event_weeks(date(2026, 5, 20), date(2026, 5, 20)) == 1
        # 7-day gap (race = first day of week 2) → ceil(8/7) = 2; the +1 pulls
        # in the week that contains race day.
        assert _time_to_event_weeks(date(2026, 5, 27), date(2026, 5, 20)) == 2
        # Past event clamps to 0.
        assert _time_to_event_weeks(date(2026, 5, 19), date(2026, 5, 20)) == 0

    def test_time_to_event_phase_band_guidance(self):
        assert "compressed" in _time_to_event_phase_band(2)
        assert "compressed" in _time_to_event_phase_band(7)
        assert "standard" in _time_to_event_phase_band(12)
        assert "extended" in _time_to_event_phase_band(30)


# ─── Cache wrapper ───────────────────────────────────────────────────────────


class TestCacheWrapper:
    def test_cache_miss_then_hit_returns_cached(self):
        backend = InMemoryCacheBackend()
        call_count = {"n": 0}

        def _counting_caller(*args, **kwargs):
            call_count["n"] += 1
            return _LLMOutput(
                tool_args=_good_tool_args(),
                input_tokens=2800,
                output_tokens=600,
                latency_ms=2200,
            )

        kwargs = dict(
            user_id=1,
            layer1_payload=_make_layer1(),
            layer3a_payload=_make_layer3a(),
            layer2a_payload=_make_layer2a(),
            race_event_payload=_make_race_event(),
            current_date=date(2026, 5, 20),
            etl_version_set=_DEFAULT_ETL,
            cache_backend=backend,
            goal_outcome="Finish",
            llm_caller=_counting_caller,
        )
        p1 = llm_layer3b_goal_timeline_viability_cached(**kwargs)
        p2 = llm_layer3b_goal_timeline_viability_cached(**kwargs)
        assert call_count["n"] == 1
        assert p1.goal_viability.viability == p2.goal_viability.viability

    def test_cache_key_day_granular_collapses_intraday(self):
        backend = InMemoryCacheBackend()
        call_count = {"n": 0}

        def _counting_caller(*args, **kwargs):
            call_count["n"] += 1
            return _LLMOutput(
                tool_args=_good_tool_args(),
                input_tokens=2800,
                output_tokens=600,
                latency_ms=2200,
            )

        common = dict(
            user_id=1,
            layer1_payload=_make_layer1(),
            layer3a_payload=_make_layer3a(),
            layer2a_payload=_make_layer2a(),
            race_event_payload=_make_race_event(),
            etl_version_set=_DEFAULT_ETL,
            cache_backend=backend,
            goal_outcome="Finish",
            llm_caller=_counting_caller,
        )
        # Same date → 1 call total
        llm_layer3b_goal_timeline_viability_cached(
            current_date=date(2026, 5, 20), **common
        )
        llm_layer3b_goal_timeline_viability_cached(
            current_date=date(2026, 5, 20), **common
        )
        assert call_count["n"] == 1

    def test_cache_key_changes_with_etl_version(self):
        common = dict(
            user_id=1,
            layer1_hash="h1",
            layer3a_hash="h2",
            layer2a_hash="h3",
            race_event_id=1,
            current_date=date(2026, 5, 20),
            non_event_goal_type=None,
            section_h2_kwargs={},
            model="claude-sonnet-4-6",
            temperature=0.0,
            max_tokens=2000,
            extended_thinking_budget=3000,
        )
        k1 = layer3b_goal_timeline_viability_key(
            etl_version_set={"0A": "v1"}, **common
        )
        k2 = layer3b_goal_timeline_viability_key(
            etl_version_set={"0A": "v2"}, **common
        )
        assert k1 != k2

    def test_cache_key_changes_with_target_race_event_id(self):
        common = dict(
            user_id=1,
            layer1_hash="h1",
            layer3a_hash="h2",
            layer2a_hash="h3",
            current_date=date(2026, 5, 20),
            non_event_goal_type=None,
            etl_version_set=_DEFAULT_ETL,
            section_h2_kwargs={},
            model="claude-sonnet-4-6",
            temperature=0.0,
            max_tokens=2000,
            extended_thinking_budget=3000,
        )
        k1 = layer3b_goal_timeline_viability_key(race_event_id=1, **common)
        k2 = layer3b_goal_timeline_viability_key(race_event_id=2, **common)
        k_no = layer3b_goal_timeline_viability_key(race_event_id=None, **common)
        assert k1 != k2
        assert k1 != k_no

    def test_cache_key_changes_with_section_h2_kwargs(self):
        common = dict(
            user_id=1,
            layer1_hash="h1",
            layer3a_hash="h2",
            layer2a_hash="h3",
            race_event_id=1,
            current_date=date(2026, 5, 20),
            non_event_goal_type=None,
            etl_version_set=_DEFAULT_ETL,
            model="claude-sonnet-4-6",
            temperature=0.0,
            max_tokens=2000,
            extended_thinking_budget=3000,
        )
        k1 = layer3b_goal_timeline_viability_key(
            section_h2_kwargs={"goal_outcome": "Finish"}, **common
        )
        k2 = layer3b_goal_timeline_viability_key(
            section_h2_kwargs={"goal_outcome": "Podium"}, **common
        )
        assert k1 != k2

    def test_cache_key_stable_across_same_inputs(self):
        common = dict(
            user_id=1,
            layer1_hash="h1",
            layer3a_hash="h2",
            layer2a_hash="h3",
            race_event_id=1,
            current_date=date(2026, 5, 20),
            non_event_goal_type=None,
            etl_version_set=_DEFAULT_ETL,
            section_h2_kwargs={},
            model="claude-sonnet-4-6",
            temperature=0.0,
            max_tokens=2000,
            extended_thinking_budget=3000,
        )
        k1 = layer3b_goal_timeline_viability_key(**common)
        k2 = layer3b_goal_timeline_viability_key(**common)
        assert k1 == k2 and len(k1) == 64  # sha256 hex

    def test_cache_hit_preserves_payload_round_trip(self):
        backend = InMemoryCacheBackend()
        kwargs = dict(
            user_id=42,
            layer1_payload=_make_layer1(),
            layer3a_payload=_make_layer3a(),
            layer2a_payload=_make_layer2a(),
            race_event_payload=_make_race_event(),
            current_date=date(2026, 5, 20),
            etl_version_set=_DEFAULT_ETL,
            cache_backend=backend,
            goal_outcome="Finish",
            llm_caller=_stub_caller(_good_tool_args()),
        )
        p1 = llm_layer3b_goal_timeline_viability_cached(**kwargs)
        p2 = llm_layer3b_goal_timeline_viability_cached(**kwargs)
        assert p1.model_dump() == p2.model_dump()
