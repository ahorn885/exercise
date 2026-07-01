"""Tests for `layer4/context.py` — upstream-layer typed pydantic payloads
that Layer 4's validator harness consumes (Step 3 PR-D of `Layer4_Spec.md`
§14.3.4 sequencing).

Coverage per the PR-C-followon closing handoff §5 next-session pointer:
- AccommodationModality smart/tagged-union dispatch × 12
- ExerciseRisk accommodation-on-verdict invariants × 6
- ResolvedExercise accommodation pass-through × 6
- Happy-path per upstream payload × 8
- extra='forbid' rejection per payload × 8
- JSON round-trip × 4
- Cross-field validation × 6

Total: 50 tests.
"""

from __future__ import annotations

from datetime import datetime

import pytest
from pydantic import ValidationError, TypeAdapter

from layer4 import (
    ACWREntry,
    ACWRStatus,
    AccommodationModality,
    Assessment,
    CurrentState,
    DailyAvailabilityWindow,
    DailyNutritionBaseline,
    DailyPhaseTargets,
    DataDensity,
    DisciplineCoverage,
    ExerciseRisk,
    ExerciseSubstitutionModality,
    FrequencyReductionModality,
    GoalViability,
    IntensityReductionModality,
    Layer2ACoachingFlag,
    Layer2ADiscipline,
    Layer2APayload,
    Layer2BPayload,
    Layer2CPayload,
    Layer2DPayload,
    Layer2EPayload,
    Layer3APayload,
    Layer3BHITLItem,
    Layer3BPayload,
    Layer3Observation,
    LoadingTypeChangeModality,
    MacroTargets,
    PeriodizationShape,
    PhaseLoadBands,
    RationaleMetadata,
    RecentTrajectory,
    ResolvedExercise,
    SupplementIntegrationPayload,
    TempoModificationModality,
    TrainingGapsSummary,
    TrajectoryWindow,
    VolumeReductionModality,
    WeightResult,
)


# ─── AccommodationModality dispatch helpers ─────────────────────────────────

_MODALITY_ADAPTER = TypeAdapter(AccommodationModality)


# Reusable factories — keep tests small + focused on the assertion.


def _volume_red(factor: float = 0.7) -> VolumeReductionModality:
    return VolumeReductionModality(
        factor=factor,
        applies_to="sets",
        rationale="reduce sets to manage load",
        evidence_basis=["soligard_2016_bjsm"],
    )


def _intensity_red(factor: float = 0.7) -> IntensityReductionModality:
    return IntensityReductionModality(
        factor=factor,
        target_metric="percent_1rm",
        rationale="reduce load to manage joint stress",
        evidence_basis=["acsm_guidelines_11ed"],
    )


def _tempo_iso() -> TempoModificationModality:
    return TempoModificationModality(
        tempo_pattern="isometric_only",
        hold_s=45,
        sets=5,
        rest_s=120,
        intensity_pct_mvc=70,
        rationale="patellar tendinopathy isometric analgesia",
        evidence_basis=["rio_2015_bjsm"],
    )


def _tempo_eccentric() -> TempoModificationModality:
    return TempoModificationModality(
        tempo_pattern="eccentric_focus",
        eccentric_s=3,
        concentric_s=1,
        rationale="eccentric heel-drop protocol",
        evidence_basis=["alfredson_1998"],
    )


def _loading_change() -> LoadingTypeChangeModality:
    return LoadingTypeChangeModality(
        from_type="bilateral",
        to_type="unilateral_contralateral",
        rationale="cross-education for immobilised limb",
        evidence_basis=["manca_2017_sports_med", "hendy_lamon_2017"],
    )


def _frequency_red() -> FrequencyReductionModality:
    return FrequencyReductionModality(
        factor=0.5,
        discipline_id="D-001",
        rationale="reduce running frequency to manage bone stress",
        evidence_basis=["acsm_guidelines_11ed"],
    )


def _substitution() -> ExerciseSubstitutionModality:
    return ExerciseSubstitutionModality(
        rationale="unified-enum placeholder; 2D emits EXCLUDE; 2C handles substitution",
        evidence_basis=[],
    )


def _accommodate_risk(modality: AccommodationModality | None = None) -> ExerciseRisk:
    return ExerciseRisk(
        exercise_id="E-100",
        exercise_name="Bench Press",
        discipline_ids=["D-001"],
        verdict="accommodate",
        accommodations=[modality or _volume_red()],
        evidence=[],
    )


# ─── AccommodationModality discriminated-union dispatch (×12) ────────────────


def test_volume_reduction_dispatch():
    m = _MODALITY_ADAPTER.validate_python(
        {
            "modality_type": "volume_reduction",
            "factor": 0.7,
            "applies_to": "sets",
            "rationale": "x",
            "evidence_basis": ["e1"],
        }
    )
    assert isinstance(m, VolumeReductionModality)
    assert m.factor == 0.7


def test_intensity_reduction_dispatch():
    m = _MODALITY_ADAPTER.validate_python(
        {
            "modality_type": "intensity_reduction",
            "factor": 0.6,
            "target_metric": "rpe",
            "rationale": "x",
            "evidence_basis": ["e1"],
        }
    )
    assert isinstance(m, IntensityReductionModality)
    assert m.target_metric == "rpe"


def test_tempo_modification_dispatch_isometric():
    m = _MODALITY_ADAPTER.validate_python(
        {
            "modality_type": "tempo_modification",
            "tempo_pattern": "isometric_only",
            "hold_s": 45,
            "sets": 5,
            "rest_s": 120,
            "intensity_pct_mvc": 70,
            "rationale": "x",
            "evidence_basis": ["rio_2015_bjsm"],
        }
    )
    assert isinstance(m, TempoModificationModality)
    assert m.tempo_pattern == "isometric_only"


def test_loading_type_change_dispatch():
    m = _MODALITY_ADAPTER.validate_python(
        {
            "modality_type": "loading_type_change",
            "from_type": "bilateral",
            "to_type": "unilateral_contralateral",
            "rationale": "x",
            "evidence_basis": ["manca_2017"],
        }
    )
    assert isinstance(m, LoadingTypeChangeModality)


def test_frequency_reduction_dispatch():
    m = _MODALITY_ADAPTER.validate_python(
        {
            "modality_type": "frequency_reduction",
            "factor": 0.5,
            "discipline_id": "D-001",
            "rationale": "x",
            "evidence_basis": ["e1"],
        }
    )
    assert isinstance(m, FrequencyReductionModality)


def test_exercise_substitution_dispatch():
    m = _MODALITY_ADAPTER.validate_python(
        {"modality_type": "exercise_substitution", "rationale": "x", "evidence_basis": []}
    )
    assert isinstance(m, ExerciseSubstitutionModality)


def test_modality_unknown_type_rejected():
    with pytest.raises(ValidationError):
        _MODALITY_ADAPTER.validate_python(
            {"modality_type": "rest_more", "rationale": "x", "evidence_basis": []}
        )


def test_volume_reduction_factor_lower_bound():
    with pytest.raises(ValidationError):
        VolumeReductionModality(
            factor=0.1,  # below 0.3 floor
            applies_to="sets",
            rationale="x",
            evidence_basis=[],
        )


def test_intensity_reduction_factor_lower_bound():
    with pytest.raises(ValidationError):
        IntensityReductionModality(
            factor=0.2,  # below 0.4 floor
            target_metric="percent_1rm",
            rationale="x",
            evidence_basis=[],
        )


def test_tempo_isometric_requires_protocol_fields():
    with pytest.raises(ValidationError):
        TempoModificationModality(
            tempo_pattern="isometric_only",
            # Missing hold_s + sets + intensity_pct_mvc.
            rationale="x",
            evidence_basis=[],
        )


def test_tempo_eccentric_requires_tempo_tuple_component():
    with pytest.raises(ValidationError):
        TempoModificationModality(
            tempo_pattern="eccentric_focus",
            # No eccentric_s / concentric_s / isometric_* — fail.
            rationale="x",
            evidence_basis=[],
        )


def test_frequency_reduction_requires_factor_or_cap():
    with pytest.raises(ValidationError):
        FrequencyReductionModality(
            # Both factor + sessions_per_week_cap None → fail.
            rationale="x",
            evidence_basis=[],
        )


# ─── ExerciseRisk accommodation-on-verdict invariants (×6) ───────────────────


def test_exercise_risk_accommodate_with_accommodations_ok():
    er = ExerciseRisk(
        exercise_id="E-1",
        exercise_name="Bench Press",
        discipline_ids=["D-001"],
        verdict="accommodate",
        accommodations=[_volume_red()],
        evidence=[],
    )
    assert er.verdict == "accommodate"
    assert len(er.accommodations) == 1


def test_exercise_risk_accommodate_empty_accommodations_rejected():
    with pytest.raises(ValidationError):
        ExerciseRisk(
            exercise_id="E-1",
            exercise_name="Bench Press",
            discipline_ids=["D-001"],
            verdict="accommodate",
            accommodations=[],
            evidence=[],
        )


def test_exercise_risk_exclude_with_accommodations_rejected():
    with pytest.raises(ValidationError):
        ExerciseRisk(
            exercise_id="E-1",
            exercise_name="Bench Press",
            discipline_ids=["D-001"],
            verdict="exclude",
            accommodations=[_volume_red()],
            evidence=[],
        )


def test_exercise_risk_clean_with_accommodations_rejected():
    with pytest.raises(ValidationError):
        ExerciseRisk(
            exercise_id="E-1",
            exercise_name="Bench Press",
            discipline_ids=["D-001"],
            verdict="clean",
            accommodations=[_volume_red()],
            evidence=[],
        )


def test_exercise_risk_exclude_empty_accommodations_ok():
    er = ExerciseRisk(
        exercise_id="E-1",
        exercise_name="Bench Press",
        discipline_ids=["D-001"],
        verdict="exclude",
        accommodations=[],
        evidence=[],
    )
    assert er.verdict == "exclude"


def test_exercise_risk_clean_empty_accommodations_ok():
    er = ExerciseRisk(
        exercise_id="E-1",
        exercise_name="Squat",
        discipline_ids=["D-001"],
        verdict="clean",
        accommodations=[],
        evidence=[],
    )
    assert er.verdict == "clean"


# ─── ResolvedExercise accommodation pass-through (×6) ────────────────────────


def _resolved_exercise(
    tier: int = 1, accommodations: list[AccommodationModality] | None = None
) -> ResolvedExercise:
    return ResolvedExercise(
        exercise_id="E-1",
        exercise_name="Bench Press",
        exercise_type="strength",
        discipline_ids=["D-001"],
        sport_relevance_notes={"D-001": "primary push"},
        priority_per_discipline={"D-001": "High"},
        tier=tier,  # type: ignore[arg-type]
        resolution_detail=None,
        terrain_required=[],
        contraindicated_parts=[],
        contraindicated_conditions=[],
        accommodations=accommodations or [],
    )


def test_resolved_exercise_tier1_with_accommodations():
    rx = _resolved_exercise(tier=1, accommodations=[_volume_red()])
    assert rx.tier == 1
    assert isinstance(rx.accommodations[0], VolumeReductionModality)


def test_resolved_exercise_tier2_with_accommodations():
    rx = _resolved_exercise(tier=2, accommodations=[_intensity_red()])
    assert rx.tier == 2
    assert isinstance(rx.accommodations[0], IntensityReductionModality)


def test_resolved_exercise_tier3_with_accommodations():
    rx = _resolved_exercise(tier=3, accommodations=[_tempo_iso()])
    assert rx.tier == 3
    assert isinstance(rx.accommodations[0], TempoModificationModality)


def test_resolved_exercise_tier0_empty_accommodations():
    rx = _resolved_exercise(tier=0, accommodations=[])
    assert rx.tier == 0
    assert rx.accommodations == []


def test_resolved_exercise_multi_modality_pass_through():
    rx = _resolved_exercise(
        tier=2,
        accommodations=[_volume_red(0.6), _intensity_red(0.7), _loading_change()],
    )
    assert len(rx.accommodations) == 3
    assert isinstance(rx.accommodations[0], VolumeReductionModality)
    assert isinstance(rx.accommodations[1], IntensityReductionModality)
    assert isinstance(rx.accommodations[2], LoadingTypeChangeModality)


def test_resolved_exercise_dict_form_round_trip_accommodations():
    rx = ResolvedExercise.model_validate(
        {
            "exercise_id": "E-1",
            "exercise_name": "Patellar Iso Hold",
            "exercise_type": "strength",
            "discipline_ids": ["D-001"],
            "sport_relevance_notes": {"D-001": "tendon analgesia"},
            "priority_per_discipline": {"D-001": "High"},
            "tier": 1,
            "resolution_detail": None,
            "terrain_required": [],
            "contraindicated_parts": [],
            "contraindicated_conditions": [],
            "accommodations": [
                {
                    "modality_type": "tempo_modification",
                    "tempo_pattern": "isometric_only",
                    "hold_s": 45,
                    "sets": 5,
                    "rest_s": 120,
                    "intensity_pct_mvc": 70,
                    "rationale": "patellar tendinopathy",
                    "evidence_basis": ["rio_2015_bjsm"],
                }
            ],
        }
    )
    assert isinstance(rx.accommodations[0], TempoModificationModality)
    assert rx.accommodations[0].hold_s == 45


# ─── Happy-path per upstream payload (×8) ────────────────────────────────────


def _layer2a_payload() -> Layer2APayload:
    disc = Layer2ADiscipline(
        discipline_id="D-001",
        discipline_name="Trail Running",
        inclusion="included",
        role="Primary",
        load_weight=WeightResult(value=0.4, source="system_default", system_default=0.4),
        rationale="primary endurance discipline for the target event",
        phase_load=PhaseLoadBands(
            base_low=0.3,
            base_high=0.5,
            build_low=0.4,
            build_high=0.6,
            peak_low=0.5,
            peak_high=0.7,
            taper_low=0.2,
            taper_high=0.4,
            notes_conditions=None,
            default_inclusion="included",
        ),
    )
    return Layer2APayload(
        framework_sport="Adventure Racing",
        etl_version_set={"layer0": "v7", "vocab": "v3"},
        disciplines=[disc],
        training_gaps_summary=TrainingGapsSummary(
            flagged_count=0,
        ),
        hitl_required=False,
        unresolved_flags=[],
        coaching_flags=[],
        rationale_metadata=RationaleMetadata(
            generated_at="2026-05-17T10:00:00Z"
        ),
    )


def test_layer2a_payload_happy_path():
    p = _layer2a_payload()
    assert p.framework_sport == "Adventure Racing"
    assert p.disciplines[0].inclusion == "included"
    assert p.disciplines[0].phase_load.peak_high == 0.7


def _layer2c_payload() -> Layer2CPayload:
    rx = _resolved_exercise(tier=1, accommodations=[])
    return Layer2CPayload(
        locale_id="L-home",
        etl_version_set={"layer0": "v7"},
        effective_pool=["E-1"],
        discipline_coverage=[
            DisciplineCoverage(
                discipline_id="D-001",
                discipline_name="Trail Running",
                exercise_db_sport="trail_running",
                total_exercises=10,
                tier_1_count=8,
                tier_2_count=1,
                tier_3_count=0,
                unavailable_count=1,
                coverage_pct=0.9,
            )
        ],
        exercises_resolved=[rx],
        coaching_flags=[],
    )


def test_layer2c_payload_happy_path():
    p = _layer2c_payload()
    assert p.locale_id == "L-home"
    assert p.exercises_resolved[0].tier == 1
    assert p.discipline_coverage[0].coverage_pct == 0.9


def _layer2d_payload() -> Layer2DPayload:
    return Layer2DPayload(
        etl_version_set={"layer0": "v7"},
        excluded_exercises=[
            ExerciseRisk(
                exercise_id="E-bench",
                exercise_name="Bench Press",
                discipline_ids=["D-001"],
                verdict="exclude",
                accommodations=[],
                evidence=[],
            )
        ],
        accommodated_exercises=[
            ExerciseRisk(
                exercise_id="E-squat",
                exercise_name="Squat",
                discipline_ids=["D-001"],
                verdict="accommodate",
                accommodations=[_volume_red(0.7)],
                evidence=[],
            )
        ],
        clean_exercise_ids=["E-deadlift"],
        discipline_risk_profiles=[],
        coaching_flags=[],
        hitl_required=False,
        hitl_items=[],
    )


def test_layer2d_payload_happy_path():
    p = _layer2d_payload()
    assert p.excluded_exercises[0].verdict == "exclude"
    assert p.accommodated_exercises[0].verdict == "accommodate"
    assert isinstance(p.accommodated_exercises[0].accommodations[0], VolumeReductionModality)


def _layer2e_payload() -> Layer2EPayload:
    targets = DailyPhaseTargets(
        activity_multiplier=1.6,
        activity_multiplier_source={"row": "base_endurance"},
        daily_calorie_target_kcal=2800,
        macros=MacroTargets(
            cho_g=400,
            cho_g_per_kg=5.7,
            cho_kcal=1600,
            protein_g=140,
            protein_g_per_kg=2.0,
            protein_kcal=560,
            fat_g=70,
            fat_kcal=630,
            fat_floor_constrained=False,
        ),
    )
    return Layer2EPayload(
        athlete_id="A-1",
        etl_version_set={"layer0": "v7"},
        computed_at=datetime(2026, 5, 17, 10, 0, 0),
        bmr_method="mifflin_st_jeor",
        bmr_kcal=1750.0,
        daily_nutrition_baseline=DailyNutritionBaseline(
            per_phase={"Base": targets, "Build": targets, "Peak": targets, "Taper": targets}
        ),
        race_day_fueling=[],
        supplement_integration=SupplementIntegrationPayload(
            integrated=[],
            race_day_suggestions=[],
            contraindication_flags=[],
            contraindication_hitl_items=[],
        ),
        dietary_pattern_adjustments=[],
        sleep_dep_overlay=None,
        heat_acclim_adjustments=[],
        coaching_flags=[],
        hitl_items=[],
        hitl_required=False,
    )


def test_layer2e_payload_happy_path():
    p = _layer2e_payload()
    assert p.bmr_method == "mifflin_st_jeor"
    assert p.daily_nutrition_baseline.per_phase["Base"].daily_calorie_target_kcal == 2800


def _layer3a_payload() -> Layer3APayload:
    return Layer3APayload(
        user_id=1,
        as_of=datetime(2026, 5, 17, 10, 0, 0),
        model="claude-opus-4-7",
        temperature=0.0,
        prompt_hash="abc123",
        latency_ms=2500,
        input_tokens=8000,
        output_tokens=1500,
        etl_version_set={"layer0": "v7"},
        current_state=CurrentState(
            aerobic_capacity=Assessment(
                level="good", confidence="high", reasoning_text="r", evidence_basis=["e1"]
            ),
            strength=Assessment(
                level="moderate", confidence="medium", reasoning_text="r", evidence_basis=["e1"]
            ),
            weak_links=["shoulder press strength"],
            skill_assessments={},
            body_composition_notes=None,
        ),
        recent_trajectory=RecentTrajectory(
            short_term=TrajectoryWindow(
                direction="steady", reasoning_text="r", evidence_basis=["e1"]
            ),
            medium_term=TrajectoryWindow(
                direction="building", reasoning_text="r", evidence_basis=["e1"]
            ),
            acwr_status=ACWRStatus(
                per_discipline={
                    "D-001": ACWREntry(
                        acute_load=8.0,
                        chronic_load=10.0,
                        ratio=0.8,
                        zone="sweet_spot",
                        units="hours",
                    )
                },
                combined=None,
            ),
            confidence="medium",
        ),
        data_density=DataDensity(
            connected_providers=["coros"],
            integration_data_days=28,
            recent_workouts_count=20,
            recent_sleep_count=14,
            recent_hrv_count=14,
            self_report_freshness_days=2,
            section_completeness={"C": 1.0, "D": 1.0, "E": 0.8, "F": 0.9, "I": 0.7},
        ),
        notable_observations=[],
    )


def test_layer3a_payload_happy_path():
    p = _layer3a_payload()
    assert p.current_state.aerobic_capacity.level == "good"
    assert p.recent_trajectory.acwr_status.per_discipline["D-001"].zone == "sweet_spot"


def _layer3b_payload() -> Layer3BPayload:
    return Layer3BPayload(
        user_id=1,
        as_of=datetime(2026, 5, 17, 10, 0, 0),
        mode="event",
        model="claude-opus-4-7",
        temperature=0.0,
        prompt_hash="def456",
        latency_ms=3000,
        input_tokens=9000,
        output_tokens=1800,
        etl_version_set={"layer0": "v7"},
        goal_viability=GoalViability(
            viability="achievable",
            confidence="high",
            reasoning_text="r",
            evidence_basis=["h2.goal_outcome"],
            suggested_adjustments=[],
        ),
        periodization_shape=PeriodizationShape(
            mode="standard",
            start_phase="Base",
            reasoning_text="r",
            evidence_basis=["e1"],
        ),
        hitl_surface=[],
        notable_observations=[],
    )


def test_layer3b_payload_happy_path():
    p = _layer3b_payload()
    assert p.goal_viability.viability == "achievable"
    assert p.periodization_shape.mode == "standard"


def test_daily_availability_window_happy_path():
    w = DailyAvailabilityWindow(
        day_of_week="Mon",
        enabled=True,
        window_start="06:00",
        window_duration=60,
        doubles_feasible="no",
    )
    assert w.day_of_week == "Mon"
    assert w.window_duration == 60


# ─── extra='forbid' rejection per payload (×8) ────────────────────────────────


def test_layer2a_payload_forbids_extra():
    with pytest.raises(ValidationError):
        Layer2APayload.model_validate(
            {
                "framework_sport": "AR",
                "etl_version_set": {},
                "disciplines": [],
                "training_gaps_summary": {
                    "flagged_count": 0,
                    "any_no_substitute": False,
                    "any_multi_substitute_candidate": False,
                },
                "hitl_required": False,
                "unresolved_flags": [],
                "coaching_flags": [],
                "rationale_metadata": {"template_version": "v1", "generated_at": "now"},
                "extra_garbage": True,  # extra='forbid' must reject.
            }
        )


def test_layer2b_payload_forbids_extra():
    with pytest.raises(ValidationError):
        Layer2BPayload.model_validate(
            {
                "coaching_flags": [],
                "etl_version_set": {},
                "extra": "junk",
            }
        )


def test_layer2c_payload_forbids_extra():
    with pytest.raises(ValidationError):
        p = _layer2c_payload().model_dump(mode="python")
        p["extra"] = "junk"
        Layer2CPayload.model_validate(p)


def test_layer2d_payload_forbids_extra():
    with pytest.raises(ValidationError):
        p = _layer2d_payload().model_dump(mode="python")
        p["extra"] = "junk"
        Layer2DPayload.model_validate(p)


def test_layer2e_payload_forbids_extra():
    with pytest.raises(ValidationError):
        p = _layer2e_payload().model_dump(mode="json")
        p["extra"] = "junk"
        Layer2EPayload.model_validate(p)


def test_layer3a_payload_forbids_extra():
    with pytest.raises(ValidationError):
        p = _layer3a_payload().model_dump(mode="json")
        p["extra"] = "junk"
        Layer3APayload.model_validate(p)


def test_layer3b_payload_forbids_extra():
    with pytest.raises(ValidationError):
        p = _layer3b_payload().model_dump(mode="json")
        p["extra"] = "junk"
        Layer3BPayload.model_validate(p)


def test_daily_availability_window_forbids_extra():
    with pytest.raises(ValidationError):
        DailyAvailabilityWindow.model_validate(
            {
                "day_of_week": "Mon",
                "enabled": True,
                "window_start": "06:00",
                "window_duration": 60,
                "doubles_feasible": "no",
                "extra": "junk",
            }
        )


# ─── JSON round-trip (×4) ─────────────────────────────────────────────────────


def test_layer2d_payload_json_round_trip():
    p1 = _layer2d_payload()
    blob = p1.model_dump_json()
    p2 = Layer2DPayload.model_validate_json(blob)
    assert p1 == p2
    # AccommodationModality survives the round-trip with correct discriminator.
    assert isinstance(p2.accommodated_exercises[0].accommodations[0], VolumeReductionModality)


def test_layer2c_payload_json_round_trip_with_multi_modality():
    rx = _resolved_exercise(
        tier=2,
        accommodations=[_volume_red(0.7), _tempo_iso(), _loading_change()],
    )
    p1 = Layer2CPayload(
        locale_id="L-home",
        etl_version_set={"layer0": "v7"},
        effective_pool=["E-1"],
        discipline_coverage=[],
        exercises_resolved=[rx],
        coaching_flags=[],
    )
    blob = p1.model_dump_json()
    p2 = Layer2CPayload.model_validate_json(blob)
    assert p1 == p2
    assert isinstance(p2.exercises_resolved[0].accommodations[0], VolumeReductionModality)
    assert isinstance(p2.exercises_resolved[0].accommodations[1], TempoModificationModality)
    assert isinstance(p2.exercises_resolved[0].accommodations[2], LoadingTypeChangeModality)


def test_layer3a_payload_json_round_trip():
    p1 = _layer3a_payload()
    blob = p1.model_dump_json()
    p2 = Layer3APayload.model_validate_json(blob)
    assert p1 == p2


def test_layer3b_payload_json_round_trip():
    p1 = _layer3b_payload()
    blob = p1.model_dump_json()
    p2 = Layer3BPayload.model_validate_json(blob)
    assert p1 == p2


# ─── Cross-field validation (×6) ──────────────────────────────────────────────


def test_layer2d_excluded_with_wrong_verdict_rejected():
    # An ExerciseRisk with verdict='accommodate' parked in excluded_exercises is wrong.
    with pytest.raises(ValidationError):
        Layer2DPayload(
            etl_version_set={},
            excluded_exercises=[
                ExerciseRisk(
                    exercise_id="E-1",
                    exercise_name="X",
                    discipline_ids=[],
                    verdict="accommodate",
                    accommodations=[_volume_red()],
                    evidence=[],
                )
            ],
            accommodated_exercises=[],
            clean_exercise_ids=[],
            discipline_risk_profiles=[],
            coaching_flags=[],
            hitl_required=False,
            hitl_items=[],
        )


def test_layer2d_accommodated_with_wrong_verdict_rejected():
    with pytest.raises(ValidationError):
        Layer2DPayload(
            etl_version_set={},
            excluded_exercises=[],
            accommodated_exercises=[
                ExerciseRisk(
                    exercise_id="E-1",
                    exercise_name="X",
                    discipline_ids=[],
                    verdict="clean",
                    accommodations=[],
                    evidence=[],
                )
            ],
            clean_exercise_ids=[],
            discipline_risk_profiles=[],
            coaching_flags=[],
            hitl_required=False,
            hitl_items=[],
        )


def test_goal_viability_achievable_with_adjustments_rejected():
    with pytest.raises(ValidationError):
        GoalViability(
            viability="achievable",
            confidence="high",
            reasoning_text="r",
            evidence_basis=["e1"],
            suggested_adjustments=["stretch goal"],  # achievable + non-empty → fail
        )


def test_goal_viability_adjustment_requires_suggestions():
    with pytest.raises(ValidationError):
        GoalViability(
            viability="achievable-with-adjustment",
            confidence="high",
            reasoning_text="r",
            evidence_basis=["e1"],
            suggested_adjustments=[],  # adjustment + empty → fail
        )


def test_periodization_shape_custom_requires_phase_weeks():
    with pytest.raises(ValidationError):
        PeriodizationShape(
            mode="custom",
            start_phase="Base",
            phase_weeks=None,  # custom + None → fail
            reasoning_text="r",
            evidence_basis=["e1"],
        )


def test_layer3b_hitl_unique_labels_enforced():
    duplicate = Layer3BHITLItem(
        source="3B",
        item_label="3B.unrealistic_goal",
        severity="warning",
        description="d",
        recommended_action="a",
        acknowledge_option="ack",
        revise_option="r",
        revise_target="h2.goal_outcome",
    )
    with pytest.raises(ValidationError):
        Layer3BPayload(
            user_id=1,
            as_of=datetime(2026, 5, 17, 10, 0, 0),
            mode="event",
            model="claude-opus-4-7",
            temperature=0.0,
            prompt_hash="x",
            latency_ms=0,
            input_tokens=0,
            output_tokens=0,
            etl_version_set={},
            goal_viability=GoalViability(
                viability="achievable",
                confidence="high",
                reasoning_text="r",
                evidence_basis=["e1"],
                suggested_adjustments=[],
            ),
            periodization_shape=PeriodizationShape(
                mode="standard",
                start_phase="Base",
                reasoning_text="r",
                evidence_basis=["e1"],
            ),
            hitl_surface=[duplicate, duplicate],  # same item_label twice → fail
            notable_observations=[],
        )
