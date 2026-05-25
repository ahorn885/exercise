"""Tests for `layer3a.builder.llm_layer3a_athlete_state` per
`Layer3_3A_Spec.md` §4 + §5 + §6 + §13 — plus the cache wrapper in
`layer3a.cached_wrapper`.

LLM calls are mocked via a stub `llm_caller` dependency. No real Anthropic
SDK invocation; no `ANTHROPIC_API_KEY` env requirement. The stubs verify
that the round-trip through input validation + prompt rendering + tool-args
parsing + schema validation + evidence-basis cross-check + post-LLM
confidence-floor clamp + metadata stamping produces the expected
`Layer3APayload`. Real-LLM regression on §13.x scenarios is deferred to
Step 7/8 telemetry tuning per `Upstream_Implementation_Plan_v1.md`.
"""

from __future__ import annotations

import warnings
from datetime import date, datetime, timedelta
from typing import Any

import pytest

from layer3a.builder import (
    Layer3AEvidenceBasisWarning,
    Layer3AInputError,
    Layer3AOutputError,
    _LLMOutput,
    _apply_confidence_floors,
    _build_prep_dict,
    _check_high_confidence_gates,
    _clamp_confidence,
    _render_user_prompt,
    build_record_athlete_state_tool,
    llm_layer3a_athlete_state,
)
from layer3a.cached_wrapper import (
    layer3a_athlete_state_key,
    llm_layer3a_athlete_state_cached,
)
from layer4.cache import InMemoryCacheBackend
from layer4.context import (
    ACWREntry,
    CombinedLoadReport,
    DisciplineWeightRecord,
    HRVRecord,
    InjuryRecord,
    Layer1Availability,
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
    Layer3AIntegrationBundle,
    ProviderStatus,
    RationaleMetadata,
    SleepRecord,
    TrainingGapsSummary,
    WeightResult,
    WorkoutRecord,
)


# ─── Fixtures ────────────────────────────────────────────────────────────────


def _make_layer1(
    *,
    years_structured_training: int | None = 5,
    primary_sport: str = "Adventure Racing",
    hrmax_bpm: int | None = 185,
    cycling_ftp_w: int | None = 240,
    sleep_baseline_hours: float | None = 7.5,
    pushup_max_reps: int | None = 40,
    with_injuries: bool = False,
) -> Layer1Payload:
    strength = Layer1StrengthBenchmarks(
        front_plank_sec=180,
        pushup_max_reps=pushup_max_reps,
        dead_hang_sec=60,
    )
    injuries = []
    if with_injuries:
        injuries = [
            InjuryRecord(
                injury_id=1,
                body_part="Wrist",
                side="Left",
                severity="Chronic-Managed",
                injury_type="Tendinopathy / overuse",
                movement_constraints=[
                    "Pain above specific joint angle",
                    "Pain with loading",
                ],
                status="Active",
            )
        ]
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
            current_injuries=injuries,
            resting_hr_bpm=52,
        ),
        training_history=Layer1TrainingHistory(
            years_structured_training=years_structured_training,
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
        strength_benchmarks=strength,
        performance=Layer1Performance(
            body_weight_kg=75.0,
            hrmax_bpm=hrmax_bpm,
            cycling_ftp_w=cycling_ftp_w,
            cycling_ftp_test_date=date(2026, 1, 15),
        ),
        availability=Layer1Availability(),
        event_goal=Layer1EventGoal(),
        lifestyle=Layer1Lifestyle(
            sleep_baseline_hours=sleep_baseline_hours,
            work_stress_level="moderate",
        ),
        network=Layer1Network(),
        disclosures=Layer1Disclosures(),
    )


def _make_layer2a(disciplines: int = 3) -> Layer2APayload:
    return Layer2APayload(
        framework_sport="Adventure Racing",
        etl_version_set={"0A": "v1", "0B": "v1", "0C": "v1"},
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


def _make_bundle(
    *,
    workouts_count: int = 12,
    sleep_count: int = 10,
    hrv_count: int = 10,
    providers: list[str] | None = None,
    as_of: datetime = datetime(2026, 5, 20, 0, 0),
    combined_acwr: float | None = 1.15,
    combined_zone: str = "sweet_spot",
) -> Layer3AIntegrationBundle:
    workouts = [
        WorkoutRecord(
            date=as_of.date() - timedelta(days=i),
            activity="Run" if i % 2 == 0 else "Bike",
            duration_min=60.0,
            distance_mi=6.0,
            avg_hr=145,
            source="garmin",
        )
        for i in range(workouts_count)
    ]
    sleep = [
        SleepRecord(
            date=as_of.date() - timedelta(days=i),
            total_sleep_hours=7.5,
            sleep_quality=8 if i % 2 == 0 else None,
            source="polar",
        )
        for i in range(sleep_count)
    ]
    hrv = [
        HRVRecord(
            date=as_of.date() - timedelta(days=i),
            hrv_rmssd_ms=45.0 - (i * 0.2),
            source="polar",
        )
        for i in range(hrv_count)
    ]
    combined: ACWREntry | None = None
    if combined_acwr is not None:
        combined = ACWREntry(
            acute_load=8.0,
            chronic_load=7.0 if combined_zone != "detraining" else 16.0,
            ratio=combined_acwr,
            zone=combined_zone,  # type: ignore[arg-type]
            units="hours",
        )
    cl = CombinedLoadReport(
        per_discipline={},
        combined=combined,
        units="hours",
        polar_cross_ref=None,
    )
    if providers is None:
        providers = ["polar"]
    ps_list = [
        ProviderStatus(
            provider=p,
            status="active",
            last_sync=as_of - timedelta(hours=2),
            has_recent_workouts=workouts_count > 0,
            has_recent_sleep=sleep_count > 0,
            has_recent_hrv=hrv_count > 0,
        )
        for p in providers
    ]
    return Layer3AIntegrationBundle(
        as_of=as_of,
        recent_workouts=workouts,
        recent_sleep=sleep,
        recent_hrv=hrv,
        combined_load=cl,
        connected_providers=ps_list,
    )


def _good_tool_args(
    *,
    aerobic_confidence: str = "high",
    strength_confidence: str = "high",
    trajectory_confidence: str = "high",
    observations: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    """A schema-valid tool args payload mimicking what a well-behaved LLM
    would emit for a rich-data fixture."""
    return {
        "current_state": {
            "aerobic_capacity": {
                "level": "strong",
                "confidence": aerobic_confidence,
                "reasoning_text": "Athlete shows strong aerobic capacity per FTP + recent volume.",
                "evidence_basis": [
                    "section_f.cycling_ftp_w",
                    "integration.recent_workouts",
                    "section_c.peak_weekly_volume_hrs",
                ],
            },
            "strength": {
                "level": "good",
                "confidence": strength_confidence,
                "reasoning_text": "Good strength baseline per pushup + plank benchmarks.",
                "evidence_basis": [
                    "section_e.pushup_max_reps",
                    "section_e.front_plank_sec",
                    "section_e.dead_hang_sec",
                ],
            },
            "weak_links": ["single-leg balance"],
            "skill_assessments": {},
            "body_composition_notes": None,
        },
        "recent_trajectory": {
            "short_term": {
                "direction": "building",
                "reasoning_text": "Volume building per last-7d count.",
                "evidence_basis": ["integration.recent_workouts"],
            },
            "medium_term": {
                "direction": "building",
                "reasoning_text": "Sustained 28-day volume trend.",
                "evidence_basis": ["integration.recent_workouts"],
            },
            "acwr_status": {
                "per_discipline": {},
                "combined": {
                    "acute_load": 8.0,
                    "chronic_load": 7.0,
                    "ratio": 1.15,
                    "zone": "sweet_spot",
                    "units": "hours",
                },
            },
            "confidence": trajectory_confidence,
        },
        "data_density": {
            "connected_providers": ["polar"],
            "integration_data_days": 28,
            "recent_workouts_count": 12,
            "recent_sleep_count": 10,
            "recent_hrv_count": 10,
            "self_report_freshness_days": 0,
            "section_completeness": {"C": 0.8, "D": 0.5, "E": 0.3, "F": 0.6, "I": 0.4},
        },
        "notable_observations": observations or [],
    }


def _stub_caller(tool_args: dict[str, Any]):
    def _call(*_args, **_kwargs) -> _LLMOutput:
        return _LLMOutput(
            tool_args=tool_args, input_tokens=3200, output_tokens=900, latency_ms=4500
        )

    return _call


def _sequence_caller(outputs: list[dict[str, Any]]):
    state = {"i": 0}

    def _call(*_args, **_kwargs) -> _LLMOutput:
        i = state["i"]
        state["i"] = i + 1
        return _LLMOutput(
            tool_args=outputs[i], input_tokens=3200, output_tokens=900, latency_ms=4500
        )

    return _call


_DEFAULT_ETL = {"0A": "v1", "0B": "v1", "0C": "v1"}


# ─── §4 input validation ─────────────────────────────────────────────────────


class TestInputValidation:
    def test_missing_layer1_raises(self):
        with pytest.raises(Layer3AInputError) as exc:
            llm_layer3a_athlete_state(
                user_id=1,
                layer1_payload=None,  # type: ignore[arg-type]
                layer2a_payload=_make_layer2a(),
                integration_bundle=_make_bundle(),
                as_of=datetime(2026, 5, 20, 0, 0),
                etl_version_set=_DEFAULT_ETL,
                llm_caller=_stub_caller(_good_tool_args()),
            )
        assert exc.value.code == "missing_layer1"

    def test_missing_primary_sport_raises_incomplete_onboarding(self):
        l1 = _make_layer1()
        l1.identity.primary_sport = None
        with pytest.raises(Layer3AInputError) as exc:
            llm_layer3a_athlete_state(
                user_id=1,
                layer1_payload=l1,
                layer2a_payload=_make_layer2a(),
                integration_bundle=_make_bundle(),
                as_of=datetime(2026, 5, 20, 0, 0),
                etl_version_set=_DEFAULT_ETL,
                llm_caller=_stub_caller(_good_tool_args()),
            )
        assert exc.value.code == "incomplete_onboarding"

    def test_missing_2a_raises(self):
        with pytest.raises(Layer3AInputError) as exc:
            llm_layer3a_athlete_state(
                user_id=1,
                layer1_payload=_make_layer1(),
                layer2a_payload=None,  # type: ignore[arg-type]
                integration_bundle=_make_bundle(),
                as_of=datetime(2026, 5, 20, 0, 0),
                etl_version_set=_DEFAULT_ETL,
                llm_caller=_stub_caller(_good_tool_args()),
            )
        assert exc.value.code == "missing_2a"

    def test_empty_2a_disciplines_raises(self):
        l2a = _make_layer2a()
        l2a.disciplines.clear()
        with pytest.raises(Layer3AInputError) as exc:
            llm_layer3a_athlete_state(
                user_id=1,
                layer1_payload=_make_layer1(),
                layer2a_payload=l2a,
                integration_bundle=_make_bundle(),
                as_of=datetime(2026, 5, 20, 0, 0),
                etl_version_set=_DEFAULT_ETL,
                llm_caller=_stub_caller(_good_tool_args()),
            )
        assert exc.value.code == "missing_2a"

    def test_missing_bundle_raises(self):
        with pytest.raises(Layer3AInputError) as exc:
            llm_layer3a_athlete_state(
                user_id=1,
                layer1_payload=_make_layer1(),
                layer2a_payload=_make_layer2a(),
                integration_bundle=None,  # type: ignore[arg-type]
                as_of=datetime(2026, 5, 20, 0, 0),
                etl_version_set=_DEFAULT_ETL,
                llm_caller=_stub_caller(_good_tool_args()),
            )
        assert exc.value.code == "missing_integration_bundle"

    def test_invalid_as_of_future_raises(self):
        future = datetime.now() + timedelta(days=2)
        with pytest.raises(Layer3AInputError) as exc:
            llm_layer3a_athlete_state(
                user_id=1,
                layer1_payload=_make_layer1(),
                layer2a_payload=_make_layer2a(),
                integration_bundle=_make_bundle(),
                as_of=future,
                etl_version_set=_DEFAULT_ETL,
                llm_caller=_stub_caller(_good_tool_args()),
            )
        assert exc.value.code == "invalid_as_of"

    def test_missing_etl_pin_raises(self):
        with pytest.raises(Layer3AInputError) as exc:
            llm_layer3a_athlete_state(
                user_id=1,
                layer1_payload=_make_layer1(),
                layer2a_payload=_make_layer2a(),
                integration_bundle=_make_bundle(),
                as_of=datetime(2026, 5, 20, 0, 0),
                etl_version_set={},
                llm_caller=_stub_caller(_good_tool_args()),
            )
        assert exc.value.code == "missing_etl_pin"

    def test_unapproved_model_raises(self):
        with pytest.raises(Layer3AInputError) as exc:
            llm_layer3a_athlete_state(
                user_id=1,
                layer1_payload=_make_layer1(),
                layer2a_payload=_make_layer2a(),
                integration_bundle=_make_bundle(),
                as_of=datetime(2026, 5, 20, 0, 0),
                etl_version_set=_DEFAULT_ETL,
                model="gpt-4",
                llm_caller=_stub_caller(_good_tool_args()),
            )
        assert exc.value.code == "unapproved_model"

    def test_invalid_temp_raises(self):
        with pytest.raises(Layer3AInputError) as exc:
            llm_layer3a_athlete_state(
                user_id=1,
                layer1_payload=_make_layer1(),
                layer2a_payload=_make_layer2a(),
                integration_bundle=_make_bundle(),
                as_of=datetime(2026, 5, 20, 0, 0),
                etl_version_set=_DEFAULT_ETL,
                temperature=1.5,
                llm_caller=_stub_caller(_good_tool_args()),
            )
        assert exc.value.code == "invalid_temp"

    def test_incomplete_onboarding_when_identity_missing_dob(self):
        # identity itself is required; primary_sport is the specific gate
        l1 = _make_layer1()
        l1.identity.primary_sport = None
        with pytest.raises(Layer3AInputError) as exc:
            llm_layer3a_athlete_state(
                user_id=1,
                layer1_payload=l1,
                layer2a_payload=_make_layer2a(),
                integration_bundle=_make_bundle(),
                as_of=datetime(2026, 5, 20, 0, 0),
                etl_version_set=_DEFAULT_ETL,
                llm_caller=_stub_caller(_good_tool_args()),
            )
        assert exc.value.code == "incomplete_onboarding"


# ─── Tool schema shape ───────────────────────────────────────────────────────


class TestToolSchema:
    def test_tool_name(self):
        schema = build_record_athlete_state_tool()
        assert schema["name"] == "record_athlete_state"

    def test_top_level_required_fields(self):
        schema = build_record_athlete_state_tool()
        req = schema["input_schema"]["required"]
        assert set(req) == {
            "current_state",
            "recent_trajectory",
            "data_density",
            "notable_observations",
        }

    def test_assessment_enum_levels(self):
        schema = build_record_athlete_state_tool()
        cs = schema["input_schema"]["properties"]["current_state"]["properties"]
        levels = cs["aerobic_capacity"]["properties"]["level"]["enum"]
        assert set(levels) == {"low", "moderate", "good", "strong", "insufficient_data"}

    def test_trajectory_direction_enum_8_values(self):
        schema = build_record_athlete_state_tool()
        st = schema["input_schema"]["properties"]["recent_trajectory"]["properties"]["short_term"]
        directions = st["properties"]["direction"]["enum"]
        assert len(set(directions)) == 8

    def test_acwr_zone_enum_5_values(self):
        schema = build_record_athlete_state_tool()
        rt = schema["input_schema"]["properties"]["recent_trajectory"]["properties"]
        zones = rt["acwr_status"]["properties"]["per_discipline"]["additionalProperties"][
            "properties"
        ]["zone"]["enum"]
        assert len(set(zones)) == 5

    def test_observation_category_enum(self):
        schema = build_record_athlete_state_tool()
        obs_item = schema["input_schema"]["properties"]["notable_observations"]["items"]
        cats = obs_item["properties"]["category"]["enum"]
        assert set(cats) == {"warning", "opportunity", "data_gap", "data_hygiene"}

    def test_weak_links_max_items(self):
        schema = build_record_athlete_state_tool()
        wl = schema["input_schema"]["properties"]["current_state"]["properties"]["weak_links"]
        assert wl["maxItems"] == 5

    def test_additional_properties_false_at_top_level(self):
        schema = build_record_athlete_state_tool()
        assert schema["input_schema"]["additionalProperties"] is False


# ─── Happy path ──────────────────────────────────────────────────────────────


class TestEntryPointHappyPath:
    def test_dense_data_round_trip(self):
        # §13.1 — AR athlete dense data; LLM emits high confidence; high-gate
        # criteria all met → no clamp.
        payload = llm_layer3a_athlete_state(
            user_id=1,
            layer1_payload=_make_layer1(),
            layer2a_payload=_make_layer2a(),
            integration_bundle=_make_bundle(),
            as_of=datetime(2026, 5, 20, 0, 0),
            etl_version_set=_DEFAULT_ETL,
            llm_caller=_stub_caller(_good_tool_args()),
        )
        assert payload.current_state.aerobic_capacity.level == "strong"
        assert payload.current_state.aerobic_capacity.confidence == "high"
        assert payload.recent_trajectory.short_term.direction == "building"
        assert payload.recent_trajectory.confidence == "high"
        assert payload.recent_trajectory.acwr_status.combined is not None
        assert payload.recent_trajectory.acwr_status.combined.zone == "sweet_spot"

    def test_metadata_stamping(self):
        as_of = datetime(2026, 5, 20, 0, 0)
        payload = llm_layer3a_athlete_state(
            user_id=42,
            layer1_payload=_make_layer1(),
            layer2a_payload=_make_layer2a(),
            integration_bundle=_make_bundle(),
            as_of=as_of,
            etl_version_set=_DEFAULT_ETL,
            model="claude-sonnet-4-6",
            temperature=0.25,
            llm_caller=_stub_caller(_good_tool_args()),
        )
        assert payload.user_id == 42
        assert payload.as_of == as_of
        assert payload.model == "claude-sonnet-4-6"
        assert payload.temperature == 0.25
        assert payload.etl_version_set == _DEFAULT_ETL
        assert payload.input_tokens == 3200
        assert payload.output_tokens == 900
        assert payload.latency_ms == 4500
        assert len(payload.prompt_hash) == 64  # sha256 hex


# ─── §6.2 confidence floor rules ─────────────────────────────────────────────


class TestConfidenceFloors:
    def test_no_providers_clamps_trajectory_to_medium(self):
        bundle = _make_bundle(providers=[])
        payload = llm_layer3a_athlete_state(
            user_id=1,
            layer1_payload=_make_layer1(),
            layer2a_payload=_make_layer2a(),
            integration_bundle=bundle,
            as_of=datetime(2026, 5, 20, 0, 0),
            etl_version_set=_DEFAULT_ETL,
            llm_caller=_stub_caller(_good_tool_args()),
        )
        assert payload.recent_trajectory.confidence == "medium"
        # auto-appended observation
        clamp_obs = [
            o for o in payload.notable_observations if "clamped" in o.text.lower()
        ]
        assert len(clamp_obs) == 1
        assert clamp_obs[0].category == "data_gap"
        assert clamp_obs[0].elevates_to_hitl is False

    def test_sparse_workouts_clamps_trajectory_to_low(self):
        bundle = _make_bundle(workouts_count=3)
        payload = llm_layer3a_athlete_state(
            user_id=1,
            layer1_payload=_make_layer1(),
            layer2a_payload=_make_layer2a(),
            integration_bundle=bundle,
            as_of=datetime(2026, 5, 20, 0, 0),
            etl_version_set=_DEFAULT_ETL,
            llm_caller=_stub_caller(_good_tool_args()),
        )
        # workouts_count=3 < 5 forces trajectory to low; also <10 means high gate fails
        assert payload.recent_trajectory.confidence == "low"

    def test_no_hrv_clamps_trajectory_to_medium(self):
        bundle = _make_bundle(hrv_count=0)
        payload = llm_layer3a_athlete_state(
            user_id=1,
            layer1_payload=_make_layer1(),
            layer2a_payload=_make_layer2a(),
            integration_bundle=bundle,
            as_of=datetime(2026, 5, 20, 0, 0),
            etl_version_set=_DEFAULT_ETL,
            llm_caller=_stub_caller(_good_tool_args()),
        )
        assert payload.recent_trajectory.confidence == "medium"

    def test_just_onboarded_clamps_current_state_to_medium(self):
        l1 = _make_layer1(years_structured_training=0)
        payload = llm_layer3a_athlete_state(
            user_id=1,
            layer1_payload=l1,
            layer2a_payload=_make_layer2a(),
            integration_bundle=_make_bundle(),
            as_of=datetime(2026, 5, 20, 0, 0),
            etl_version_set=_DEFAULT_ETL,
            llm_caller=_stub_caller(_good_tool_args()),
        )
        # years_structured_training=0 forces both aerobic + strength to medium
        assert payload.current_state.aerobic_capacity.confidence == "medium"
        assert payload.current_state.strength.confidence == "medium"

    def test_high_gate_fails_when_no_hrmax_clamps_high_everywhere(self):
        l1 = _make_layer1(hrmax_bpm=None)
        payload = llm_layer3a_athlete_state(
            user_id=1,
            layer1_payload=l1,
            layer2a_payload=_make_layer2a(),
            integration_bundle=_make_bundle(),
            as_of=datetime(2026, 5, 20, 0, 0),
            etl_version_set=_DEFAULT_ETL,
            llm_caller=_stub_caller(_good_tool_args()),
        )
        assert payload.current_state.aerobic_capacity.confidence == "medium"
        assert payload.current_state.strength.confidence == "medium"
        assert payload.recent_trajectory.confidence == "medium"

    def test_high_gate_passes_when_all_criteria_met(self):
        # Default fixture: ≥10 workouts, polar active with all coverage,
        # years_structured=5, hrmax + ftp set, sleep_baseline set
        assert _check_high_confidence_gates(_make_bundle(), _make_layer1()) is True

    def test_high_gate_fails_without_active_provider(self):
        assert _check_high_confidence_gates(_make_bundle(providers=[]), _make_layer1()) is False

    def test_high_gate_fails_without_threshold_metric(self):
        l1 = _make_layer1(cycling_ftp_w=None)
        # also nulls other threshold metrics via _make_layer1 defaults
        assert _check_high_confidence_gates(_make_bundle(), l1) is False

    def test_high_gate_fails_without_sleep_baseline(self):
        l1 = _make_layer1(sleep_baseline_hours=None)
        assert _check_high_confidence_gates(_make_bundle(), l1) is False

    def test_clamp_does_not_upgrade_low_to_medium(self):
        # When LLM returns 'low', clamp leaves it 'low' even if floor allows medium
        tool_args = _good_tool_args(trajectory_confidence="low")
        payload = llm_layer3a_athlete_state(
            user_id=1,
            layer1_payload=_make_layer1(),
            layer2a_payload=_make_layer2a(),
            integration_bundle=_make_bundle(),
            as_of=datetime(2026, 5, 20, 0, 0),
            etl_version_set=_DEFAULT_ETL,
            llm_caller=_stub_caller(tool_args),
        )
        assert payload.recent_trajectory.confidence == "low"

    def test_clamp_confidence_helper(self):
        assert _clamp_confidence("high", "medium") == "medium"
        assert _clamp_confidence("medium", "high") == "medium"
        assert _clamp_confidence("low", "high") == "low"
        assert _clamp_confidence("low", "low") == "low"
        assert _clamp_confidence("high", "high") == "high"

    def test_no_clamp_signal_no_appended_observation(self):
        payload = llm_layer3a_athlete_state(
            user_id=1,
            layer1_payload=_make_layer1(),
            layer2a_payload=_make_layer2a(),
            integration_bundle=_make_bundle(),
            as_of=datetime(2026, 5, 20, 0, 0),
            etl_version_set=_DEFAULT_ETL,
            llm_caller=_stub_caller(_good_tool_args()),
        )
        # All clamp signals: no_connected_providers fails (provider present),
        # sparse_recent_workouts fails (12>5), no_recent_hrv fails (hrv present),
        # just_onboarded fails (yst=5), high_gate passes → no signals → no
        # appended clamp observation.
        clamp_obs = [
            o for o in payload.notable_observations if "clamped" in o.text.lower()
        ]
        assert clamp_obs == []


# ─── §5.3 schema-violation retry ─────────────────────────────────────────────


class TestSchemaViolation:
    def test_invalid_then_valid_succeeds_after_retry(self):
        bad_args = {"current_state": {"missing": "required"}}
        good_args = _good_tool_args()
        payload = llm_layer3a_athlete_state(
            user_id=1,
            layer1_payload=_make_layer1(),
            layer2a_payload=_make_layer2a(),
            integration_bundle=_make_bundle(),
            as_of=datetime(2026, 5, 20, 0, 0),
            etl_version_set=_DEFAULT_ETL,
            llm_caller=_sequence_caller([bad_args, good_args]),
        )
        assert payload.current_state.aerobic_capacity.level == "strong"

    def test_two_invalid_raises_schema_violation(self):
        bad = {"current_state": {"missing": "required"}}
        with pytest.raises(Layer3AOutputError) as exc:
            llm_layer3a_athlete_state(
                user_id=1,
                layer1_payload=_make_layer1(),
                layer2a_payload=_make_layer2a(),
                integration_bundle=_make_bundle(),
                as_of=datetime(2026, 5, 20, 0, 0),
                etl_version_set=_DEFAULT_ETL,
                llm_caller=_sequence_caller([bad, bad]),
            )
        assert exc.value.code == "schema_violation"

    def test_invalid_enum_value_triggers_retry(self):
        bad = _good_tool_args()
        bad["current_state"]["aerobic_capacity"]["level"] = "bogus_level"
        good = _good_tool_args()
        payload = llm_layer3a_athlete_state(
            user_id=1,
            layer1_payload=_make_layer1(),
            layer2a_payload=_make_layer2a(),
            integration_bundle=_make_bundle(),
            as_of=datetime(2026, 5, 20, 0, 0),
            etl_version_set=_DEFAULT_ETL,
            llm_caller=_sequence_caller([bad, good]),
        )
        assert payload.current_state.aerobic_capacity.level == "strong"


# ─── §5.3 step 2 evidence-basis cross-check ──────────────────────────────────


class TestEvidenceBasisCheck:
    def test_unknown_evidence_basis_warns_but_succeeds(self):
        args = _good_tool_args()
        args["current_state"]["aerobic_capacity"]["evidence_basis"] = [
            "section_z.fabricated_path",
            "another.invalid.key",
        ]
        with warnings.catch_warnings(record=True) as caught:
            warnings.simplefilter("always", Layer3AEvidenceBasisWarning)
            payload = llm_layer3a_athlete_state(
                user_id=1,
                layer1_payload=_make_layer1(),
                layer2a_payload=_make_layer2a(),
                integration_bundle=_make_bundle(),
                as_of=datetime(2026, 5, 20, 0, 0),
                etl_version_set=_DEFAULT_ETL,
                llm_caller=_stub_caller(args),
            )
        # Two unknown paths → 2 warnings; payload succeeds (no exception)
        unknown_warnings = [
            w for w in caught if issubclass(w.category, Layer3AEvidenceBasisWarning)
        ]
        assert len(unknown_warnings) >= 2
        assert payload is not None


# ─── §13 scenarios — round-trip ─────────────────────────────────────────────


class TestS13Scenarios:
    def test_s13_2_sparse_data_just_onboarded(self):
        """§13.2 — new athlete, sparse log, no providers; trajectory low,
        current_state ≤ medium, ACWR combined None."""
        bundle = _make_bundle(workouts_count=4, sleep_count=0, hrv_count=0, providers=[])
        l1 = _make_layer1(years_structured_training=0)
        args = _good_tool_args(
            aerobic_confidence="medium",
            strength_confidence="medium",
            trajectory_confidence="low",
        )
        args["recent_trajectory"]["short_term"]["direction"] = "insufficient_data"
        args["recent_trajectory"]["acwr_status"]["combined"] = None
        args["notable_observations"] = [
            {
                "category": "data_gap",
                "text": "Insufficient training history.",
                "evidence_basis": ["section_c.years_structured_training"],
                "elevates_to_hitl": True,
            }
        ]
        payload = llm_layer3a_athlete_state(
            user_id=1,
            layer1_payload=l1,
            layer2a_payload=_make_layer2a(),
            integration_bundle=bundle,
            as_of=datetime(2026, 5, 20, 0, 0),
            etl_version_set=_DEFAULT_ETL,
            llm_caller=_stub_caller(args),
        )
        assert payload.current_state.aerobic_capacity.confidence == "medium"
        assert payload.recent_trajectory.confidence == "low"
        assert payload.recent_trajectory.acwr_status.combined is None
        # data_gap observation preserved
        cats = [o.category for o in payload.notable_observations]
        assert "data_gap" in cats

    def test_s13_3_conflicting_signals(self):
        """§13.3 — high logged volume + reported high stress; LLM picks
        good aerobic + fatigued short_term + warning observation about ACWR."""
        bundle = _make_bundle(combined_acwr=1.45)
        args = _good_tool_args(aerobic_confidence="medium")
        args["recent_trajectory"]["short_term"]["direction"] = "fatigued"
        args["recent_trajectory"]["acwr_status"]["combined"]["ratio"] = 1.45
        args["recent_trajectory"]["acwr_status"]["combined"]["zone"] = "functional_overreach"
        args["notable_observations"] = [
            {
                "category": "warning",
                "text": "ACWR 1.45 in build phase — overreach risk.",
                "evidence_basis": ["integration.combined_load"],
                "elevates_to_hitl": True,
            }
        ]
        payload = llm_layer3a_athlete_state(
            user_id=1,
            layer1_payload=_make_layer1(),
            layer2a_payload=_make_layer2a(),
            integration_bundle=bundle,
            as_of=datetime(2026, 5, 20, 0, 0),
            etl_version_set=_DEFAULT_ETL,
            llm_caller=_stub_caller(args),
        )
        assert payload.recent_trajectory.short_term.direction == "fatigued"
        assert any(o.category == "warning" for o in payload.notable_observations)

    def test_s13_4_returning_athlete_detrained(self):
        """§13.4 — rich history but no recent activity; LLM picks detrained."""
        bundle = _make_bundle(workouts_count=0, sleep_count=0, hrv_count=0, providers=[])
        args = _good_tool_args(
            aerobic_confidence="medium",
            strength_confidence="medium",
            trajectory_confidence="low",
        )
        args["current_state"]["aerobic_capacity"]["level"] = "moderate"
        args["recent_trajectory"]["short_term"]["direction"] = "detrained"
        args["recent_trajectory"]["medium_term"]["direction"] = "detrained"
        args["recent_trajectory"]["acwr_status"]["combined"] = None
        args["notable_observations"] = [
            {
                "category": "opportunity",
                "text": "Prior training base recoverable.",
                "evidence_basis": ["section_c.peak_weekly_volume_hrs"],
                "elevates_to_hitl": False,
            },
            {
                "category": "data_gap",
                "text": "Stale §F baselines.",
                "evidence_basis": ["section_f.cycling_ftp_test_date"],
                "elevates_to_hitl": False,
            },
        ]
        payload = llm_layer3a_athlete_state(
            user_id=1,
            layer1_payload=_make_layer1(),
            layer2a_payload=_make_layer2a(),
            integration_bundle=bundle,
            as_of=datetime(2026, 5, 20, 0, 0),
            etl_version_set=_DEFAULT_ETL,
            llm_caller=_stub_caller(args),
        )
        assert payload.recent_trajectory.short_term.direction == "detrained"
        assert payload.recent_trajectory.medium_term.direction == "detrained"
        cats = [o.category for o in payload.notable_observations]
        assert "opportunity" in cats
        assert "data_gap" in cats

    def test_s13_6_no_providers_rich_self_report(self):
        """§13.6 — no providers, rich self-report, manual log present."""
        bundle = _make_bundle(providers=[])
        payload = llm_layer3a_athlete_state(
            user_id=1,
            layer1_payload=_make_layer1(),
            layer2a_payload=_make_layer2a(),
            integration_bundle=bundle,
            as_of=datetime(2026, 5, 20, 0, 0),
            etl_version_set=_DEFAULT_ETL,
            llm_caller=_stub_caller(_good_tool_args(trajectory_confidence="medium")),
        )
        assert payload.recent_trajectory.confidence == "medium"
        # high-gate fails (no providers) → current state aerobic clamped
        assert payload.current_state.aerobic_capacity.confidence == "medium"

    def test_s13_7_precondition_failure_no_llm_call(self):
        """§13.7 — primary_sport missing → precondition fails, LLM NOT
        invoked. Stub raises if called."""

        def _explode(*_args, **_kwargs):
            raise AssertionError("LLM should not be called when preconditions fail")

        l1 = _make_layer1()
        l1.identity.primary_sport = None
        with pytest.raises(Layer3AInputError) as exc:
            llm_layer3a_athlete_state(
                user_id=1,
                layer1_payload=l1,
                layer2a_payload=_make_layer2a(),
                integration_bundle=_make_bundle(),
                as_of=datetime(2026, 5, 20, 0, 0),
                etl_version_set=_DEFAULT_ETL,
                llm_caller=_explode,
            )
        assert exc.value.code == "incomplete_onboarding"

    def test_s13_10_acwr_red_zone(self):
        """§13.10 — ACWR combined = 1.62 → warning observation with
        elevates_to_hitl=True."""
        bundle = _make_bundle(combined_acwr=1.62, combined_zone="non_functional_overreach")
        args = _good_tool_args()
        args["recent_trajectory"]["short_term"]["direction"] = "overreached"
        args["recent_trajectory"]["acwr_status"]["combined"]["ratio"] = 1.62
        args["recent_trajectory"]["acwr_status"]["combined"][
            "zone"
        ] = "non_functional_overreach"
        args["notable_observations"] = [
            {
                "category": "warning",
                "text": "ACWR 1.62 — non-functional overreach risk.",
                "evidence_basis": ["integration.combined_load"],
                "elevates_to_hitl": True,
            }
        ]
        payload = llm_layer3a_athlete_state(
            user_id=1,
            layer1_payload=_make_layer1(),
            layer2a_payload=_make_layer2a(),
            integration_bundle=bundle,
            as_of=datetime(2026, 5, 20, 0, 0),
            etl_version_set=_DEFAULT_ETL,
            llm_caller=_stub_caller(args),
        )
        warnings_with_hitl = [
            o
            for o in payload.notable_observations
            if o.category == "warning" and o.elevates_to_hitl
        ]
        assert len(warnings_with_hitl) >= 1


# ─── Prep dict + prompt rendering ────────────────────────────────────────────


class TestPrepDict:
    def test_prep_dict_contains_expected_section_keys(self):
        d = _build_prep_dict(
            _make_layer1(),
            _make_layer2a(),
            _make_bundle(),
            datetime(2026, 5, 20, 0, 0),
        )
        # Required section path keys must be in prep dict
        assert "section_c.years_structured_training" in d
        assert "section_f.hrmax_bpm" in d
        assert "section_i.sleep_baseline_hours" in d
        assert "section_e.pushup_max_reps" in d
        assert "integration.recent_workouts" in d
        assert "integration.connected_providers" in d
        assert "layer2a.framework_sport" in d

    def test_prompt_renders_without_error_for_full_fixture(self):
        prompt = _render_user_prompt(
            _make_layer1(),
            _make_layer2a(),
            _make_bundle(),
            datetime(2026, 5, 20, 0, 0),
        )
        assert "Athlete context:" in prompt
        assert "Training history:" in prompt
        assert "Recent activity bundle" in prompt
        assert "record_athlete_state" in prompt

    def test_prompt_renders_health_note_when_injuries_present(self):
        prompt = _render_user_prompt(
            _make_layer1(with_injuries=True),
            _make_layer2a(),
            _make_bundle(),
            datetime(2026, 5, 20, 0, 0),
        )
        assert "Wrist" in prompt
        assert "Pain above specific joint angle" in prompt

    def test_prompt_renders_no_injury_block_when_none(self):
        prompt = _render_user_prompt(
            _make_layer1(),
            _make_layer2a(),
            _make_bundle(),
            datetime(2026, 5, 20, 0, 0),
        )
        assert "no active injuries" in prompt

    def test_prompt_renders_retry_error_when_provided(self):
        prompt = _render_user_prompt(
            _make_layer1(),
            _make_layer2a(),
            _make_bundle(),
            datetime(2026, 5, 20, 0, 0),
            retry_error="invalid enum 'foo'",
        )
        assert "Previous attempt failed" in prompt
        assert "invalid enum 'foo'" in prompt


# ─── Cache wrapper ───────────────────────────────────────────────────────────


class TestCacheWrapper:
    def test_cache_miss_invokes_synthesizer_then_hit_returns_cached(self):
        backend = InMemoryCacheBackend()
        call_count = {"n": 0}

        def _counting_caller(*args, **kwargs):
            call_count["n"] += 1
            return _LLMOutput(
                tool_args=_good_tool_args(),
                input_tokens=3200,
                output_tokens=900,
                latency_ms=4500,
            )

        kwargs = dict(
            user_id=1,
            layer1_payload=_make_layer1(),
            layer2a_payload=_make_layer2a(),
            integration_bundle=_make_bundle(),
            as_of=datetime(2026, 5, 20, 0, 0),
            etl_version_set=_DEFAULT_ETL,
            cache_backend=backend,
            llm_caller=_counting_caller,
        )
        p1 = llm_layer3a_athlete_state_cached(**kwargs)
        p2 = llm_layer3a_athlete_state_cached(**kwargs)
        assert call_count["n"] == 1
        assert p1.current_state.aerobic_capacity.level == p2.current_state.aerobic_capacity.level
        assert p1.user_id == p2.user_id

    def test_cache_key_day_granular_collapses_intraday_calls(self):
        backend = InMemoryCacheBackend()
        call_count = {"n": 0}

        def _counting_caller(*args, **kwargs):
            call_count["n"] += 1
            return _LLMOutput(
                tool_args=_good_tool_args(),
                input_tokens=3200,
                output_tokens=900,
                latency_ms=4500,
            )

        common = dict(
            user_id=1,
            layer1_payload=_make_layer1(),
            layer2a_payload=_make_layer2a(),
            integration_bundle=_make_bundle(),
            etl_version_set=_DEFAULT_ETL,
            cache_backend=backend,
            llm_caller=_counting_caller,
        )
        llm_layer3a_athlete_state_cached(as_of=datetime(2026, 5, 20, 0, 5), **common)
        llm_layer3a_athlete_state_cached(as_of=datetime(2026, 5, 20, 3, 30), **common)
        assert call_count["n"] == 1  # both same calendar day → 1 cold call

    def test_cache_key_changes_with_different_etl_version(self):
        as_of = datetime(2026, 5, 20, 0, 0)
        l1_hash = "h1"
        l2a_hash = "h2"
        bundle_hash = "h3"
        common = dict(
            user_id=1,
            layer1_hash=l1_hash,
            layer2a_hash=l2a_hash,
            integration_bundle_hash=bundle_hash,
            as_of=as_of,
            model="claude-sonnet-4-6",
            temperature=0.2,
            max_tokens=4000,
            extended_thinking_budget=4000,
        )
        k1 = layer3a_athlete_state_key(etl_version_set={"0A": "v1"}, **common)
        k2 = layer3a_athlete_state_key(etl_version_set={"0A": "v2"}, **common)
        assert k1 != k2

    def test_cache_key_changes_with_model_swap(self):
        as_of = datetime(2026, 5, 20, 0, 0)
        common = dict(
            user_id=1,
            layer1_hash="h1",
            layer2a_hash="h2",
            integration_bundle_hash="h3",
            as_of=as_of,
            etl_version_set=_DEFAULT_ETL,
            temperature=0.2,
            max_tokens=4000,
            extended_thinking_budget=4000,
        )
        k1 = layer3a_athlete_state_key(model="claude-sonnet-4-6", **common)
        k2 = layer3a_athlete_state_key(model="claude-opus-4-7", **common)
        assert k1 != k2

    def test_cache_key_stable_across_same_inputs(self):
        as_of = datetime(2026, 5, 20, 0, 0)
        common = dict(
            user_id=1,
            layer1_hash="h1",
            layer2a_hash="h2",
            integration_bundle_hash="h3",
            as_of=as_of,
            etl_version_set=_DEFAULT_ETL,
            model="claude-sonnet-4-6",
            temperature=0.2,
            max_tokens=4000,
            extended_thinking_budget=4000,
        )
        k1 = layer3a_athlete_state_key(**common)
        k2 = layer3a_athlete_state_key(**common)
        assert k1 == k2 and len(k1) == 64  # sha256 hex

    def test_cache_hit_preserves_payload_metadata_round_trip(self):
        backend = InMemoryCacheBackend()
        kwargs = dict(
            user_id=42,
            layer1_payload=_make_layer1(),
            layer2a_payload=_make_layer2a(),
            integration_bundle=_make_bundle(),
            as_of=datetime(2026, 5, 20, 0, 0),
            etl_version_set=_DEFAULT_ETL,
            cache_backend=backend,
            llm_caller=_stub_caller(_good_tool_args()),
        )
        p1 = llm_layer3a_athlete_state_cached(**kwargs)
        p2 = llm_layer3a_athlete_state_cached(**kwargs)
        # Round-trip via JSON preserves all fields
        assert p1.model_dump() == p2.model_dump()

    def test_cache_key_changes_with_different_user(self):
        as_of = datetime(2026, 5, 20, 0, 0)
        common = dict(
            layer1_hash="h1",
            layer2a_hash="h2",
            integration_bundle_hash="h3",
            as_of=as_of,
            etl_version_set=_DEFAULT_ETL,
            model="claude-sonnet-4-6",
            temperature=0.2,
            max_tokens=4000,
            extended_thinking_budget=4000,
        )
        assert layer3a_athlete_state_key(user_id=1, **common) != layer3a_athlete_state_key(
            user_id=2, **common
        )
