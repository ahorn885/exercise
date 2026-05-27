"""Tests for `layer4/validator.py` — Layer 4 §5.4 deterministic validator
harness (Step 3 PR-E of `Layer4_Spec.md` §14.3.4 sequencing).

Coverage:
- ValidatorContext construction × 3
- Per rule (×21): happy-path + at least one blocker/warning case + mode-gate
- Per-modality compliance for injury_accommodation_violation × 6 variants
- Driver-level: aggregation, pass_index, accepted-vs-not, mode-gating

Total target: ~120 tests matching the PR-D handoff §5 projection.
"""

from __future__ import annotations

from datetime import date, datetime, timedelta

import pytest

from layer4 import (
    ACWREntry,
    ACWRStatus,
    Assessment,
    AccommodationModality,
    CardioBlock,
    CurrentState,
    DailyAvailabilityWindow,
    DataDensity,
    DisciplineCoverage,
    Evidence,
    ExerciseRisk,
    ExerciseSubstitutionModality,
    FrequencyReductionModality,
    FuelingStrategy,
    HRTarget,
    IntensityReductionModality,
    Layer2ADiscipline,
    Layer2APayload,
    Layer2CPayload,
    Layer2DPayload,
    Layer4Payload,
    LoadingTypeChangeModality,
    PaceTarget,
    PacingStrategy,
    PerDateRestriction,
    PhaseLoadBands,
    PhaseSpec,
    PhaseStructure,
    PlanSession,
    RPETarget,
    RaceEventPayload,
    RacePlan,
    RaceSegment,
    RaceWeekBrief,
    RationaleMetadata,
    ResolvedExercise,
    SessionPhaseMetadata,
    StrengthExercise,
    SynthesisMetadata,
    TempoModificationModality,
    TrainingGapsSummary,
    ValidatorContext,
    ValidatorResult,
    VolumeReductionModality,
    WeightResult,
    validate_layer4_payload,
)
from layer4.payload import RuleFailure
from layer4.validator import phase_volume_bands_hours
from layer4.context import (
    DailyNutritionBaseline,
    DailyPhaseTargets,
    Layer2EPayload,
    MacroTargets,
    RaceDayFueling,
    SupplementIntegrationPayload,
)


# ─── Fixtures / builders ─────────────────────────────────────────────────────


_SCOPE_START = date(2026, 6, 1)  # Mon


def _cardio_block(
    duration_min: int = 60, zone: str = "Z2", target: object | None = None
) -> CardioBlock:
    return CardioBlock(
        block_kind="main_set",
        duration_min=duration_min,
        intensity_zone=zone,  # type: ignore[arg-type]
        intensity_target=target or HRTarget(hr_bpm_low=130, hr_bpm_high=145),
        instructions="steady",
    )


def _strength_exercise(
    exercise_id: str = "E-squat",
    sets: int = 3,
    reps: int | str = 8,
    load: str = "70% 1RM",
    tempo: str | None = None,
) -> StrengthExercise:
    return StrengthExercise(
        exercise_id=exercise_id,
        exercise_name=exercise_id,
        resolution_tier=1,
        sets=sets,
        reps_per_set=reps,
        load_prescription=load,
        rest_between_sets_sec=120,
        tempo=tempo,
        instructions="execute with control",
        coaching_flags=[],
    )


def _phase_metadata(phase: str = "Base") -> SessionPhaseMetadata:
    return SessionPhaseMetadata(
        phase_name=phase,  # type: ignore[arg-type]
        week_in_phase=1,
        total_weeks_in_phase=8,
        intended_volume_band=(5.0, 8.0),
        intended_intensity_distribution={"Z1-Z2": 0.80, "Z3": 0.15, "Z4-Z5": 0.05},
    )


_UNSET = object()


def _cardio_session(
    *,
    session_id: str = "S-1",
    d: date = _SCOPE_START,
    index: int = 0,
    duration_min: int = 60,
    discipline_id: str = "D-001",
    locale_id: str = "L-home",
    intensity_summary: str = "moderate",
    blocks: list[CardioBlock] | None = None,
    phase_metadata: object = _UNSET,
    coaching_flags: list[str] | None = None,
) -> PlanSession:
    dow_map = {0: "Mon", 1: "Tue", 2: "Wed", 3: "Thu", 4: "Fri", 5: "Sat", 6: "Sun"}
    if phase_metadata is _UNSET:
        phase_metadata = _phase_metadata()
    return PlanSession(
        session_id=session_id,
        plan_version_id=1,
        date=d,
        day_of_week=dow_map[d.weekday()],  # type: ignore[arg-type]
        session_index_in_day=index,
        time_of_day="morning",
        kind="cardio",
        discipline_id=discipline_id,
        discipline_name=discipline_id,
        locale_id=locale_id,
        locale_name=locale_id,
        duration_min=duration_min,
        intensity_summary=intensity_summary,  # type: ignore[arg-type]
        cardio_blocks=blocks or [_cardio_block(duration_min=duration_min)],
        phase_metadata=phase_metadata,  # type: ignore[arg-type]
        session_notes="x",
        coaching_intent="x",
        coaching_flags=coaching_flags or [],
    )


def _strength_session(
    *,
    session_id: str = "S-1",
    d: date = _SCOPE_START,
    index: int = 0,
    locale_id: str = "L-home",
    discipline_id: str = "D-001",
    exercises: list[StrengthExercise] | None = None,
    phase_metadata: object = _UNSET,
    coaching_flags: list[str] | None = None,
    duration_min: int = 45,
    intensity_summary: str = "moderate",
) -> PlanSession:
    dow_map = {0: "Mon", 1: "Tue", 2: "Wed", 3: "Thu", 4: "Fri", 5: "Sat", 6: "Sun"}
    if phase_metadata is _UNSET:
        phase_metadata = _phase_metadata()
    return PlanSession(
        session_id=session_id,
        plan_version_id=1,
        date=d,
        day_of_week=dow_map[d.weekday()],  # type: ignore[arg-type]
        session_index_in_day=index,
        time_of_day="afternoon",
        kind="strength",
        discipline_id=discipline_id,
        discipline_name=discipline_id,
        locale_id=locale_id,
        locale_name=locale_id,
        duration_min=duration_min,
        intensity_summary=intensity_summary,  # type: ignore[arg-type]
        strength_exercises=exercises or [_strength_exercise()],
        phase_metadata=phase_metadata,  # type: ignore[arg-type]
        session_notes="x",
        coaching_intent="x",
        coaching_flags=coaching_flags or [],
    )


def _phase_structure() -> PhaseStructure:
    return PhaseStructure(
        phases=[
            PhaseSpec(
                phase_name="Base",
                start_date=_SCOPE_START,
                end_date=_SCOPE_START + timedelta(days=55),
                weeks=8,
                intended_volume_band=(5.0, 8.0),
                intended_intensity_distribution={"Z1-Z2": 0.80, "Z3": 0.15, "Z4-Z5": 0.05},
                synthesis_metadata=SynthesisMetadata(
                    model="m",
                    temperature=0.0,
                    input_tokens=0,
                    output_tokens=0,
                    latency_ms=0,
                    retries_used=0,
                    cap_hit=False,
                ),
            )
        ],
        total_weeks=8,
        derived_from="3b_standard",
    )


def _minimal_layer4(
    *,
    mode: str = "plan_create",
    pattern: str = "A",
    sessions: list[PlanSession] | None = None,
    suggestion_id: int | None = None,
    race_week_brief: RaceWeekBrief | None = None,
    race_plan: RacePlan | None = None,
) -> Layer4Payload:
    if sessions is None:
        sessions = [_cardio_session()]
    is_pattern_a = pattern == "A" and mode in ("plan_create", "plan_refresh")
    return Layer4Payload(
        user_id=1,
        mode=mode,  # type: ignore[arg-type]
        plan_version_id=1,
        scope_start_date=min(s.date for s in sessions),
        scope_end_date=max(s.date for s in sessions),
        model_synthesizer="m",
        model_seam_reviewer="m" if is_pattern_a else None,
        temperature=0.0,
        pattern=pattern,  # type: ignore[arg-type]
        latency_ms_total=0,
        input_tokens_total=0,
        output_tokens_total=0,
        llm_call_count=1,
        etl_version_set={"layer0": "v7"},
        sessions=sessions,
        phase_structure=_phase_structure() if is_pattern_a else None,
        seam_reviews=[] if is_pattern_a else None,
        validator_results=[
            ValidatorResult(
                pass_index=0, accepted=True, rule_failures=[], retried_phase_names=[]
            )
        ],
        notable_observations=[],
        suggestion_id=suggestion_id,
        race_week_brief=race_week_brief,
        race_plan=race_plan,
    )


def _layer2a_with_band(
    discipline_id: str = "D-001",
    base_low: float = 5.0,
    base_high: float = 8.0,
    inclusion: str = "included",
) -> Layer2APayload:
    disc = Layer2ADiscipline(
        discipline_id=discipline_id,
        discipline_name=discipline_id,
        inclusion=inclusion,  # type: ignore[arg-type]
        role="Primary",
        is_conditional=False,
        load_weight=WeightResult(value=0.5, source="system_default", system_default=0.5),
        sleep_deprivation_relevant=False,
        rationale="r",
        phase_load=PhaseLoadBands(
            base_low=base_low,
            base_high=base_high,
            build_low=base_low + 1,
            build_high=base_high + 1,
            peak_low=base_low + 1.5,
            peak_high=base_high + 1.5,
            taper_low=base_low - 2,
            taper_high=base_high - 2,
            default_inclusion="included",
        ),
    )
    # phase_load values are PERCENTAGES; the weekly totals convert them to
    # hours. Sized at the per-phase band midpoint so the single included
    # discipline (renormalized to 100% of capacity) yields an hour band equal
    # to the raw (low, high) — keeping these boundary tests' numbers intact.
    _base_mid = (base_low + base_high) / 2
    return Layer2APayload(
        framework_sport="AR",
        etl_version_set={"layer0": "v7"},
        disciplines=[disc],
        weekly_total_hours_by_phase={
            "Base": (_base_mid, _base_mid),
            "Build": (_base_mid + 1, _base_mid + 1),
            "Peak": (_base_mid + 1.5, _base_mid + 1.5),
            "Taper": (_base_mid - 2, _base_mid - 2),
        },
        training_gaps_summary=TrainingGapsSummary(
            flagged_count=0, any_no_substitute=False, any_multi_substitute_candidate=False
        ),
        hitl_required=False,
        unresolved_flags=[],
        coaching_flags=[],
        rationale_metadata=RationaleMetadata(
            template_version="v1", generated_at="2026-05-17T10:00:00Z"
        ),
    )


def _layer2c(
    locale_id: str = "L-home",
    exercise_ids: list[str] | None = None,
    discipline_id: str = "D-001",
    coverage_pct: float = 0.9,
    total_exercises: int = 10,
) -> Layer2CPayload:
    exercise_ids = exercise_ids if exercise_ids is not None else ["E-squat"]
    resolved = [
        ResolvedExercise(
            exercise_id=ex,
            exercise_name=ex,
            exercise_type="strength",
            discipline_ids=[discipline_id],
            sport_relevance_notes={discipline_id: "x"},
            priority_per_discipline={discipline_id: "Medium"},
            tier=1,
            terrain_required=[],
            contraindicated_parts=[],
            contraindicated_conditions=[],
            accommodations=[],
        )
        for ex in exercise_ids
    ]
    return Layer2CPayload(
        locale_id=locale_id,
        etl_version_set={"layer0": "v7"},
        effective_pool=list(exercise_ids),
        discipline_coverage=[
            DisciplineCoverage(
                discipline_id=discipline_id,
                discipline_name=discipline_id,
                exercise_db_sport="x",
                total_exercises=total_exercises,
                tier_1_count=total_exercises,
                tier_2_count=0,
                tier_3_count=0,
                unavailable_count=0,
                coverage_pct=coverage_pct,
            )
        ],
        exercises_resolved=resolved,
        coaching_flags=[],
    )


def _layer2d_with_excluded(exercise_ids: list[str]) -> Layer2DPayload:
    return Layer2DPayload(
        etl_version_set={"layer0": "v7"},
        excluded_exercises=[
            ExerciseRisk(
                exercise_id=ex,
                exercise_name=ex,
                discipline_ids=["D-001"],
                verdict="exclude",
                accommodations=[],
                evidence=[],
            )
            for ex in exercise_ids
        ],
        accommodated_exercises=[],
        clean_exercise_ids=[],
        discipline_risk_profiles=[],
        coaching_flags=[],
        hitl_required=False,
        hitl_items=[],
        body_part_vocab_misses=[],
        condition_vocab_misses=[],
    )


def _layer2d_with_accommodated(
    exercise_id: str, modalities: list[AccommodationModality]
) -> Layer2DPayload:
    return Layer2DPayload(
        etl_version_set={"layer0": "v7"},
        excluded_exercises=[],
        accommodated_exercises=[
            ExerciseRisk(
                exercise_id=exercise_id,
                exercise_name=exercise_id,
                discipline_ids=["D-001"],
                verdict="accommodate",
                accommodations=modalities,
                evidence=[],
            )
        ],
        clean_exercise_ids=[],
        discipline_risk_profiles=[],
        coaching_flags=[],
        hitl_required=False,
        hitl_items=[],
        body_part_vocab_misses=[],
        condition_vocab_misses=[],
    )


def _daily_window(
    dow: str = "Mon",
    enabled: bool = True,
    duration: int = 120,
    doubles: str = "no",
) -> DailyAvailabilityWindow:
    if not enabled:
        return DailyAvailabilityWindow(
            day_of_week=dow,  # type: ignore[arg-type]
            enabled=False,
            doubles_feasible=doubles,  # type: ignore[arg-type]
        )
    return DailyAvailabilityWindow(
        day_of_week=dow,  # type: ignore[arg-type]
        enabled=True,
        window_start="06:00",
        window_duration=duration,
        doubles_feasible=doubles,  # type: ignore[arg-type]
    )


_DOW_NAMES = ("Sun", "Mon", "Tue", "Wed", "Thu", "Fri", "Sat")


def _full_week_windows(duration: int = 120) -> list[DailyAvailabilityWindow]:
    return [_daily_window(dow=d, duration=duration) for d in _DOW_NAMES]


def _race_week_brief(
    event_date: date,
    race_format: str = "single_day",
    contingencies: list[str] | None = None,
) -> RaceWeekBrief:
    return RaceWeekBrief(
        days_to_event=(event_date - _SCOPE_START).days,
        event_name="Test Event",
        event_date=event_date,
        event_locale="L-home",
        race_format=race_format,  # type: ignore[arg-type]
        goal_outcome="Finish",
        pre_race_logistics="x",
        kit_manifest=[],
        kit_check_dates=[],
        race_day_fueling_plan="x",
        pre_race_meal_strategy="x",
        pacing_strategy_summary="x",
        contingencies=contingencies or [],
        mental_prep_cues=[],
    )


def _race_plan_multi_day(
    cho_low: int = 60,
    cho_high: int = 90,
    sodium: int = 600,
    fluid: int = 600,
    segments_offsets: list[float] | None = None,
    contingencies: list[str] | None = None,
) -> RacePlan:
    offsets = segments_offsets or [0.0, 6.0]
    segs = [
        RaceSegment(
            segment_id=f"seg-{i}",
            segment_index=i,
            sport="trail_running",
            estimated_start_offset_hr=off,
            estimated_duration_min=180,
            terrain_notes="x",
            pacing_target=RPETarget(rpe_low=6, rpe_high=7),
            coaching_notes="x",
        )
        for i, off in enumerate(offsets)
    ]
    from layer4 import Contingency

    return RacePlan(
        race_name="Test Event",
        race_start_datetime=datetime(2026, 7, 17, 6, 0, 0),
        race_end_estimate_datetime=datetime(2026, 7, 18, 12, 0, 0),
        race_format="continuous_multi_day",
        locales=["L-home"],
        segments=segs,
        transitions=[],
        pacing_strategy=PacingStrategy(
            overall_intensity_target="RPE 5-6",
            pacing_milestones=[],
            rationale_text="x",
        ),
        fueling_strategy=FuelingStrategy(
            cho_g_per_hr_low=cho_low,
            cho_g_per_hr_high=cho_high,
            sodium_mg_per_hr=sodium,
            fluid_ml_per_hr=fluid,
            caffeine_strategy="x",
            rationale_text="x",
        ),
        contingencies=[
            Contingency(trigger=c, action_plan="x", threshold_to_invoke="x")
            for c in (contingencies or [])
        ],
    )


def _layer2e_with_tier(
    event_name: str = "Test Event",
    cho_low: float = 60.0,
    cho_high: float = 90.0,
    na_low: float = 500.0,
    na_high: float = 700.0,
    fluid_low: float = 500.0,
    fluid_high: float = 700.0,
) -> Layer2EPayload:
    targets = DailyPhaseTargets(
        activity_multiplier=1.6,
        activity_multiplier_source={"row": "base"},
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
        race_day_fueling=[
            RaceDayFueling(
                event_id="E-1",
                event_name=event_name,
                duration_tier="tier_long",
                cho_g_per_hr_low=cho_low,
                cho_g_per_hr_high=cho_high,
                na_mg_per_hr_low=na_low,
                na_mg_per_hr_high=na_high,
                fluid_ml_per_hr_low=fluid_low,
                fluid_ml_per_hr_high=fluid_high,
                sport_modifier_applied=1.0,
                salt_tolerance_modifier_applied=1.0,
                heat_acclim_modifier_applied=1.0,
                recommended_formats=[],
                blocked_formats=[],
                sleep_dep_overlay_applies=False,
                notes=[],
            )
        ],
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


def _names_of(failures: list[RuleFailure]) -> list[str]:
    return [f.rule_name for f in failures]


# ─── ValidatorContext construction (×3) ─────────────────────────────────────


def test_validator_context_defaults_empty():
    ctx = ValidatorContext()
    assert ctx.layer2a_payload is None
    assert ctx.layer2c_payloads == {}
    assert ctx.per_date_restrictions == ()
    assert ctx.prior_session_loads_by_date is None


def test_validator_context_with_payloads():
    ctx = ValidatorContext(layer2a_payload=_layer2a_with_band())
    assert ctx.layer2a_payload is not None
    assert ctx.layer2a_payload.framework_sport == "AR"


def test_validator_context_frozen():
    ctx = ValidatorContext()
    with pytest.raises(Exception):  # FrozenInstanceError or AttributeError
        ctx.layer2a_payload = _layer2a_with_band()  # type: ignore[misc]


# ─── Driver-level (×6) ──────────────────────────────────────────────────────


def test_driver_empty_payload_accepted():
    payload = _minimal_layer4()
    result = validate_layer4_payload(payload, ValidatorContext())
    assert result.accepted
    assert result.rule_failures == []
    assert result.pass_index == 0
    assert result.retried_phase_names == []


def test_driver_pass_index_preserved():
    payload = _minimal_layer4()
    result = validate_layer4_payload(payload, ValidatorContext(), pass_index=3)
    assert result.pass_index == 3


def test_driver_accepted_false_on_blocker():
    payload = _minimal_layer4(
        sessions=[
            _strength_session(
                exercises=[_strength_exercise(exercise_id="E-bench")],
            )
        ]
    )
    ctx = ValidatorContext(layer2d_payload=_layer2d_with_excluded(["E-bench"]))
    result = validate_layer4_payload(payload, ctx)
    assert not result.accepted
    assert any(f.severity == "blocker" for f in result.rule_failures)


def test_driver_accepted_true_with_warnings_only():
    payload = _minimal_layer4(
        sessions=[
            _strength_session(
                exercises=[
                    _strength_exercise(
                        exercise_id="E-bench", sets=10, reps=10, load="80% 1RM"
                    )
                ]
            )
        ]
    )
    ctx = ValidatorContext(
        layer2d_payload=_layer2d_with_accommodated(
            "E-bench",
            [
                VolumeReductionModality(
                    factor=0.5, applies_to="sets", rationale="r", evidence_basis=[]
                )
            ],
        )
    )
    result = validate_layer4_payload(payload, ctx)
    # Warnings present but accepted=True.
    assert result.accepted
    assert any(f.severity == "warning" for f in result.rule_failures)


def test_driver_aggregates_multiple_rules():
    payload = _minimal_layer4(
        sessions=[
            _strength_session(
                session_id="S-1",
                exercises=[
                    _strength_exercise(exercise_id="E-bench"),
                    _strength_exercise(exercise_id="E-rdl"),
                ],
            )
        ]
    )
    ctx = ValidatorContext(layer2d_payload=_layer2d_with_excluded(["E-bench", "E-rdl"]))
    result = validate_layer4_payload(payload, ctx)
    assert len([f for f in result.rule_failures if f.rule_name.startswith("injury_violation")]) == 2


def test_driver_retried_phase_names_always_empty():
    payload = _minimal_layer4()
    result = validate_layer4_payload(payload, ValidatorContext(), pass_index=2)
    assert result.retried_phase_names == []


# ─── Rule 1: volume_band ────────────────────────────────────────────────────


def test_volume_band_in_band_no_fire():
    sessions = [
        _cardio_session(
            session_id=f"S-{i}",
            d=_SCOPE_START + timedelta(days=i),
            duration_min=60,  # 1h × 6 = 6h within 5-8h band
        )
        for i in range(6)
    ]
    payload = _minimal_layer4(sessions=sessions)
    ctx = ValidatorContext(
        layer2a_payload=_layer2a_with_band(), capacity_hours=999.0
    )
    failures = validate_layer4_payload(payload, ctx).rule_failures
    assert not any(f.rule_name.startswith("volume_band") for f in failures)


def test_volume_band_above_warning():
    sessions = [
        _cardio_session(
            session_id=f"S-{i}", d=_SCOPE_START + timedelta(days=i), duration_min=90
        )
        for i in range(6)
    ]  # 9h: above 8 × 1.1=8.8 but ≤ 8 × 1.2=9.6 → warning
    payload = _minimal_layer4(sessions=sessions)
    ctx = ValidatorContext(
        layer2a_payload=_layer2a_with_band(), capacity_hours=999.0
    )
    failures = validate_layer4_payload(payload, ctx).rule_failures
    vb = [f for f in failures if f.rule_name.startswith("volume_band")]
    assert vb
    assert all(f.severity == "warning" for f in vb)


def test_volume_band_above_blocker():
    sessions = [
        _cardio_session(
            session_id=f"S-{i}", d=_SCOPE_START + timedelta(days=i), duration_min=120
        )
        for i in range(6)
    ]  # 12h: above 8 × 1.2=9.6 → blocker
    payload = _minimal_layer4(sessions=sessions)
    ctx = ValidatorContext(
        layer2a_payload=_layer2a_with_band(), capacity_hours=999.0
    )
    failures = validate_layer4_payload(payload, ctx).rule_failures
    vb = [f for f in failures if f.rule_name.startswith("volume_band")]
    assert vb
    assert any(f.severity == "blocker" for f in vb)


def test_volume_band_skips_when_no_2a():
    payload = _minimal_layer4()
    failures = validate_layer4_payload(payload, ValidatorContext()).rule_failures
    assert not any(f.rule_name.startswith("volume_band") for f in failures)


def test_volume_band_mode_gated_single_session():
    s = _strength_session(session_id="S-1", phase_metadata=None).model_copy(
        update={"is_ad_hoc": True, "ad_hoc_request_payload": {"x": 1}}
    )
    payload = _minimal_layer4(
        mode="single_session_synthesize",
        pattern="B",
        suggestion_id=99,
        sessions=[s],
    )
    ctx = ValidatorContext(layer2a_payload=_layer2a_with_band())
    failures = validate_layer4_payload(payload, ctx).rule_failures
    assert not any(f.rule_name.startswith("volume_band") for f in failures)


# ─── Rule 2: acwr ───────────────────────────────────────────────────────────


def test_acwr_in_band_no_fire():
    # Acute (last 7d) = 7h via payload Mon-Sun.
    # Chronic window = 28 days; 21 days of 1h prior + 7h payload = 28h; avg 7h/wk → ratio 1.0.
    sessions = [
        _cardio_session(session_id=f"S-{i}", d=_SCOPE_START + timedelta(days=i), duration_min=60)
        for i in range(7)
    ]
    payload = _minimal_layer4(sessions=sessions)
    prior = {
        _SCOPE_START - timedelta(days=i): 1.0
        for i in range(1, 22)  # SCOPE_START-1..-21: 21 days within chronic window
    }
    ctx = ValidatorContext(prior_session_loads_by_date=prior)
    failures = validate_layer4_payload(payload, ctx).rule_failures
    assert not any(f.rule_name.startswith("acwr") for f in failures)


def test_acwr_above_blocker():
    # Acute = 14h (last 7d in payload). Chronic_total = 14h. chronic_avg = 14/4 = 3.5/wk. ratio = 14/3.5 = 4.0.
    sessions = [
        _cardio_session(session_id=f"S-{i}", d=_SCOPE_START + timedelta(days=i), duration_min=120)
        for i in range(7)
    ]
    payload = _minimal_layer4(sessions=sessions)
    ctx = ValidatorContext(prior_session_loads_by_date={})  # no prior data
    failures = validate_layer4_payload(payload, ctx).rule_failures
    acwr = [f for f in failures if f.rule_name.startswith("acwr")]
    assert acwr
    assert acwr[0].severity == "blocker"


def test_acwr_skipped_when_no_prior_data():
    payload = _minimal_layer4()
    ctx = ValidatorContext()  # prior is None
    failures = validate_layer4_payload(payload, ctx).rule_failures
    assert not any(f.rule_name.startswith("acwr") for f in failures)


# ─── Rule 3: rest_spacing ──────────────────────────────────────────────────


def test_rest_spacing_consecutive_hard_blocker():
    sessions = [
        _cardio_session(
            session_id="S-1", d=_SCOPE_START, intensity_summary="hard"
        ),
        _cardio_session(
            session_id="S-2",
            d=_SCOPE_START + timedelta(days=1),
            intensity_summary="hard",
        ),
    ]
    payload = _minimal_layer4(sessions=sessions)
    failures = validate_layer4_payload(payload, ValidatorContext()).rule_failures
    rs = [f for f in failures if f.rule_name.startswith("rest_spacing")]
    assert rs
    assert rs[0].severity == "blocker"


def test_rest_spacing_exempted_by_overreach_test_flag():
    sessions = [
        _cardio_session(
            session_id="S-1", d=_SCOPE_START, intensity_summary="hard"
        ),
        _cardio_session(
            session_id="S-2",
            d=_SCOPE_START + timedelta(days=1),
            intensity_summary="hard",
            coaching_flags=["overreach_test"],
        ),
    ]
    payload = _minimal_layer4(sessions=sessions)
    failures = validate_layer4_payload(payload, ValidatorContext()).rule_failures
    assert not any(f.rule_name.startswith("rest_spacing") for f in failures)


def test_rest_spacing_non_consecutive_no_fire():
    sessions = [
        _cardio_session(
            session_id="S-1", d=_SCOPE_START, intensity_summary="hard"
        ),
        _cardio_session(
            session_id="S-2",
            d=_SCOPE_START + timedelta(days=2),
            intensity_summary="hard",
        ),
    ]
    payload = _minimal_layer4(sessions=sessions)
    failures = validate_layer4_payload(payload, ValidatorContext()).rule_failures
    assert not any(f.rule_name.startswith("rest_spacing") for f in failures)


# ─── Rule 4: intensity_dist ────────────────────────────────────────────────


def test_intensity_dist_within_tolerance_no_fire():
    # 80%/15%/5% target; build a payload that matches.
    sessions = [
        _cardio_session(
            session_id="S-1",
            d=_SCOPE_START,
            duration_min=80,
            blocks=[_cardio_block(duration_min=80, zone="Z2")],
        ),
        _cardio_session(
            session_id="S-2",
            d=_SCOPE_START + timedelta(days=1),
            duration_min=15,
            blocks=[_cardio_block(duration_min=15, zone="Z3")],
        ),
        _cardio_session(
            session_id="S-3",
            d=_SCOPE_START + timedelta(days=2),
            duration_min=5,
            blocks=[_cardio_block(duration_min=5, zone="Z4")],
        ),
    ]
    payload = _minimal_layer4(sessions=sessions)
    failures = validate_layer4_payload(payload, ValidatorContext()).rule_failures
    assert not any(f.rule_name.startswith("intensity_dist") for f in failures)


def test_intensity_dist_drift_warning():
    # All Z4 — way off 80/15/5.
    sessions = [
        _cardio_session(
            session_id=f"S-{i}",
            d=_SCOPE_START + timedelta(days=i),
            duration_min=60,
            blocks=[_cardio_block(duration_min=60, zone="Z4")],
        )
        for i in range(5)
    ]
    payload = _minimal_layer4(sessions=sessions)
    failures = validate_layer4_payload(payload, ValidatorContext()).rule_failures
    iv = [f for f in failures if f.rule_name.startswith("intensity_dist")]
    assert iv
    assert all(f.severity == "warning" for f in iv)


# ─── Rule 5: two_per_day (defensive) ───────────────────────────────────────


def test_two_per_day_defensive_passes_valid_payload():
    sessions = [
        _cardio_session(session_id="S-1", d=_SCOPE_START, index=0),
        _strength_session(session_id="S-2", d=_SCOPE_START, index=1),
    ]
    payload = _minimal_layer4(sessions=sessions)
    failures = validate_layer4_payload(payload, ValidatorContext()).rule_failures
    assert not any(f.rule_name.startswith("two_per_day") for f in failures)


def test_two_per_day_fires_via_model_construct_bypass():
    """Pydantic Layer4Payload rejects invalid two_per_day at construction;
    use model_construct to bypass and verify the §5.4 rule still fires."""
    s1 = _cardio_session(session_id="S-1", d=_SCOPE_START, index=0)
    s2 = _cardio_session(session_id="S-2", d=_SCOPE_START, index=0)  # dup index
    s3 = _cardio_session(session_id="S-3", d=_SCOPE_START, index=1)
    payload = _minimal_layer4(sessions=[_cardio_session()])
    payload = payload.model_copy(update={"sessions": [s1, s2, s3]})  # type: ignore
    # model_copy doesn't re-run validators; construct directly via model_construct to be safe.
    payload = Layer4Payload.model_construct(**{**payload.__dict__, "sessions": [s1, s2, s3]})
    failures = validate_layer4_payload(payload, ValidatorContext()).rule_failures
    tpd = [f for f in failures if f.rule_name.startswith("two_per_day")]
    assert tpd
    assert any("max_exceeded" in f.rule_name for f in tpd)


# ─── Rule 6a: equipment_unavailable ────────────────────────────────────────


def test_equipment_unavailable_in_pool_no_fire():
    sessions = [
        _strength_session(
            session_id="S-1",
            exercises=[_strength_exercise(exercise_id="E-squat")],
        )
    ]
    payload = _minimal_layer4(sessions=sessions)
    ctx = ValidatorContext(layer2c_payloads={"L-home": _layer2c(exercise_ids=["E-squat"])})
    failures = validate_layer4_payload(payload, ctx).rule_failures
    assert not any(f.rule_name.startswith("equipment_unavailable") for f in failures)


def test_equipment_unavailable_missing_blocker():
    sessions = [
        _strength_session(
            session_id="S-1",
            exercises=[_strength_exercise(exercise_id="E-bench")],
        )
    ]
    payload = _minimal_layer4(sessions=sessions)
    ctx = ValidatorContext(layer2c_payloads={"L-home": _layer2c(exercise_ids=["E-squat"])})
    failures = validate_layer4_payload(payload, ctx).rule_failures
    eu = [f for f in failures if f.rule_name.startswith("equipment_unavailable")]
    assert eu
    assert eu[0].severity == "blocker"


def test_equipment_unavailable_skipped_without_2c():
    sessions = [_strength_session(session_id="S-1")]
    payload = _minimal_layer4(sessions=sessions)
    failures = validate_layer4_payload(payload, ValidatorContext()).rule_failures
    assert not any(f.rule_name.startswith("equipment_unavailable") for f in failures)


# ─── Rule 6b: session_multi_locale ─────────────────────────────────────────


def test_session_multi_locale_pass_through_when_all_resolve():
    sessions = [
        _strength_session(
            session_id="S-1",
            exercises=[
                _strength_exercise(exercise_id="E-squat"),
                _strength_exercise(exercise_id="E-rdl"),
            ],
        )
    ]
    payload = _minimal_layer4(sessions=sessions)
    ctx = ValidatorContext(
        layer2c_payloads={"L-home": _layer2c(exercise_ids=["E-squat", "E-rdl"])}
    )
    failures = validate_layer4_payload(payload, ctx).rule_failures
    assert not any(f.rule_name.startswith("session_multi_locale") for f in failures)


def test_session_multi_locale_blocker_when_none_resolve():
    sessions = [
        _strength_session(
            session_id="S-1",
            exercises=[_strength_exercise(exercise_id="E-fake")],
        )
    ]
    payload = _minimal_layer4(sessions=sessions)
    ctx = ValidatorContext(layer2c_payloads={"L-home": _layer2c(exercise_ids=["E-squat"])})
    failures = validate_layer4_payload(payload, ctx).rule_failures
    sml = [f for f in failures if f.rule_name.startswith("session_multi_locale")]
    assert sml
    assert sml[0].severity == "blocker"


# ─── Rule 6c: session_locale_not_in_cluster ────────────────────────────────


def test_session_locale_in_cluster_no_fire():
    payload = _minimal_layer4()
    ctx = ValidatorContext(layer2c_payloads={"L-home": _layer2c()})
    failures = validate_layer4_payload(payload, ctx).rule_failures
    assert not any(f.rule_name.startswith("session_locale_not_in_cluster") for f in failures)


def test_session_locale_not_in_cluster_blocker():
    payload = _minimal_layer4(
        sessions=[_cardio_session(locale_id="L-unknown")]
    )
    ctx = ValidatorContext(layer2c_payloads={"L-home": _layer2c()})
    failures = validate_layer4_payload(payload, ctx).rule_failures
    sl = [f for f in failures if f.rule_name.startswith("session_locale_not_in_cluster")]
    assert sl
    assert sl[0].severity == "blocker"


def test_session_locale_lock_d67_violation():
    payload = _minimal_layer4(
        sessions=[_cardio_session(locale_id="L-home", d=_SCOPE_START)]
    )
    ctx = ValidatorContext(
        layer2c_payloads={
            "L-home": _layer2c("L-home"),
            "L-travel": _layer2c("L-travel"),
        },
        per_date_restrictions=(
            PerDateRestriction(date=datetime(2026, 6, 1), locale_lock="L-travel"),
        ),
    )
    failures = validate_layer4_payload(payload, ctx).rule_failures
    sl = [f for f in failures if f.rule_name.startswith("session_locale_lock_violation")]
    assert sl
    assert sl[0].severity == "blocker"


def test_session_locale_lock_d67_empty_no_fire():
    payload = _minimal_layer4()
    ctx = ValidatorContext(
        layer2c_payloads={"L-home": _layer2c()},
        per_date_restrictions=(),  # v1 always-empty
    )
    failures = validate_layer4_payload(payload, ctx).rule_failures
    assert not any(f.rule_name.startswith("session_locale_lock") for f in failures)


# ─── Rule 9: injury_violation ──────────────────────────────────────────────


def test_injury_violation_clean_no_fire():
    sessions = [_strength_session(exercises=[_strength_exercise(exercise_id="E-squat")])]
    payload = _minimal_layer4(sessions=sessions)
    ctx = ValidatorContext(layer2d_payload=_layer2d_with_excluded(["E-bench"]))
    failures = validate_layer4_payload(payload, ctx).rule_failures
    assert not any(f.rule_name.startswith("injury_violation") for f in failures)


def test_injury_violation_excluded_exercise_blocker():
    sessions = [_strength_session(exercises=[_strength_exercise(exercise_id="E-bench")])]
    payload = _minimal_layer4(sessions=sessions)
    ctx = ValidatorContext(layer2d_payload=_layer2d_with_excluded(["E-bench"]))
    failures = validate_layer4_payload(payload, ctx).rule_failures
    iv = [f for f in failures if f.rule_name.startswith("injury_violation")]
    assert iv
    assert iv[0].severity == "blocker"


def test_injury_violation_skipped_without_2d():
    sessions = [_strength_session()]
    payload = _minimal_layer4(sessions=sessions)
    failures = validate_layer4_payload(payload, ValidatorContext()).rule_failures
    assert not any(f.rule_name.startswith("injury_violation") for f in failures)


# ─── Rule 10: injury_accommodation_violation ───────────────────────────────


def test_accommodation_volume_reduction_compliant_no_fire():
    sessions = [
        _strength_session(
            exercises=[
                _strength_exercise(exercise_id="E-squat", sets=2, reps=5, load="60% 1RM")
            ]
        )
    ]
    payload = _minimal_layer4(sessions=sessions)
    ctx = ValidatorContext(
        layer2d_payload=_layer2d_with_accommodated(
            "E-squat",
            [VolumeReductionModality(factor=0.5, applies_to="sets", rationale="r", evidence_basis=[])],
        )
    )
    failures = validate_layer4_payload(payload, ctx).rule_failures
    assert not any(
        f.rule_name.startswith("injury_accommodation_violation_volume") for f in failures
    )


def test_accommodation_volume_reduction_exceeds_warning():
    # baseline 40 × 0.5 × 1.1 = 22 reps threshold. 10×10 = 100 reps → fires.
    sessions = [
        _strength_session(
            exercises=[
                _strength_exercise(exercise_id="E-squat", sets=10, reps=10, load="60% 1RM")
            ]
        )
    ]
    payload = _minimal_layer4(sessions=sessions)
    ctx = ValidatorContext(
        layer2d_payload=_layer2d_with_accommodated(
            "E-squat",
            [VolumeReductionModality(factor=0.5, applies_to="sets", rationale="r", evidence_basis=[])],
        )
    )
    failures = validate_layer4_payload(payload, ctx).rule_failures
    iav = [f for f in failures if f.rule_name.startswith("injury_accommodation_violation_volume")]
    assert iav
    assert iav[0].severity == "warning"


def test_accommodation_intensity_reduction_compliant_no_fire():
    sessions = [
        _strength_session(
            exercises=[_strength_exercise(exercise_id="E-squat", load="40% 1RM")]
        )
    ]
    payload = _minimal_layer4(sessions=sessions)
    ctx = ValidatorContext(
        layer2d_payload=_layer2d_with_accommodated(
            "E-squat",
            [
                IntensityReductionModality(
                    factor=0.6, target_metric="percent_1rm", rationale="r", evidence_basis=[]
                )
            ],
        )
    )
    failures = validate_layer4_payload(payload, ctx).rule_failures
    assert not any(
        f.rule_name.startswith("injury_accommodation_violation_intensity") for f in failures
    )


def test_accommodation_intensity_reduction_exceeds_warning():
    # baseline 80 × 0.6 × 1.1 = 52.8. Prescribed 80% > 52.8 → fires.
    sessions = [
        _strength_session(
            exercises=[_strength_exercise(exercise_id="E-squat", load="80% 1RM")]
        )
    ]
    payload = _minimal_layer4(sessions=sessions)
    ctx = ValidatorContext(
        layer2d_payload=_layer2d_with_accommodated(
            "E-squat",
            [
                IntensityReductionModality(
                    factor=0.6, target_metric="percent_1rm", rationale="r", evidence_basis=[]
                )
            ],
        )
    )
    failures = validate_layer4_payload(payload, ctx).rule_failures
    iav = [
        f for f in failures if f.rule_name.startswith("injury_accommodation_violation_intensity")
    ]
    assert iav
    assert iav[0].severity == "warning"


def test_accommodation_tempo_isometric_compliant():
    sessions = [
        _strength_session(
            exercises=[
                _strength_exercise(exercise_id="E-squat", tempo="iso-45s", load="bodyweight")
            ]
        )
    ]
    payload = _minimal_layer4(sessions=sessions)
    ctx = ValidatorContext(
        layer2d_payload=_layer2d_with_accommodated(
            "E-squat",
            [
                TempoModificationModality(
                    tempo_pattern="isometric_only",
                    hold_s=45,
                    sets=5,
                    intensity_pct_mvc=70,
                    rationale="r",
                    evidence_basis=[],
                )
            ],
        )
    )
    failures = validate_layer4_payload(payload, ctx).rule_failures
    assert not any(
        f.rule_name.startswith("injury_accommodation_violation_tempo") for f in failures
    )


def test_accommodation_tempo_isometric_missing_notation_warns():
    sessions = [
        _strength_session(
            exercises=[_strength_exercise(exercise_id="E-squat", tempo="3-1-1-0")]
        )
    ]
    payload = _minimal_layer4(sessions=sessions)
    ctx = ValidatorContext(
        layer2d_payload=_layer2d_with_accommodated(
            "E-squat",
            [
                TempoModificationModality(
                    tempo_pattern="isometric_only",
                    hold_s=45,
                    sets=5,
                    intensity_pct_mvc=70,
                    rationale="r",
                    evidence_basis=[],
                )
            ],
        )
    )
    failures = validate_layer4_payload(payload, ctx).rule_failures
    iav = [f for f in failures if f.rule_name.startswith("injury_accommodation_violation_tempo")]
    assert iav
    assert iav[0].severity == "warning"


def test_accommodation_tempo_eccentric_match():
    sessions = [
        _strength_session(
            exercises=[_strength_exercise(exercise_id="E-squat", tempo="3-1-1-0")]
        )
    ]
    payload = _minimal_layer4(sessions=sessions)
    ctx = ValidatorContext(
        layer2d_payload=_layer2d_with_accommodated(
            "E-squat",
            [
                TempoModificationModality(
                    tempo_pattern="eccentric_focus",
                    eccentric_s=3,
                    concentric_s=1,
                    rationale="r",
                    evidence_basis=[],
                )
            ],
        )
    )
    failures = validate_layer4_payload(payload, ctx).rule_failures
    assert not any(
        f.rule_name.startswith("injury_accommodation_violation_tempo") for f in failures
    )


def test_accommodation_tempo_eccentric_mismatch():
    # Modality wants eccentric=4; prescribed=1 → mismatch.
    sessions = [
        _strength_session(
            exercises=[_strength_exercise(exercise_id="E-squat", tempo="1-0-1-0")]
        )
    ]
    payload = _minimal_layer4(sessions=sessions)
    ctx = ValidatorContext(
        layer2d_payload=_layer2d_with_accommodated(
            "E-squat",
            [
                TempoModificationModality(
                    tempo_pattern="eccentric_focus",
                    eccentric_s=4,
                    rationale="r",
                    evidence_basis=[],
                )
            ],
        )
    )
    failures = validate_layer4_payload(payload, ctx).rule_failures
    iav = [f for f in failures if f.rule_name.startswith("injury_accommodation_violation_tempo")]
    assert iav
    assert iav[0].severity == "warning"


def test_accommodation_loading_type_change_skipped_silently_in_v1():
    sessions = [_strength_session(exercises=[_strength_exercise(exercise_id="E-squat")])]
    payload = _minimal_layer4(sessions=sessions)
    ctx = ValidatorContext(
        layer2d_payload=_layer2d_with_accommodated(
            "E-squat",
            [
                LoadingTypeChangeModality(
                    from_type="bilateral",
                    to_type="unilateral_contralateral",
                    rationale="r",
                    evidence_basis=[],
                )
            ],
        )
    )
    failures = validate_layer4_payload(payload, ctx).rule_failures
    # v1 skips loading_type_change enforcement silently.
    assert not any(
        f.rule_name.startswith("injury_accommodation_violation") for f in failures
    )


def test_accommodation_frequency_cap_compliant_no_fire():
    sessions = [
        _strength_session(
            session_id=f"S-{i}",
            d=_SCOPE_START + timedelta(days=i),
            discipline_id="D-001",
            exercises=[_strength_exercise(exercise_id="E-squat")],
        )
        for i in range(2)
    ]
    payload = _minimal_layer4(sessions=sessions)
    ctx = ValidatorContext(
        layer2d_payload=_layer2d_with_accommodated(
            "E-squat",
            [
                FrequencyReductionModality(
                    sessions_per_week_cap=2,
                    discipline_id="D-001",
                    rationale="r",
                    evidence_basis=[],
                )
            ],
        )
    )
    failures = validate_layer4_payload(payload, ctx).rule_failures
    assert not any(
        f.rule_name.startswith("injury_accommodation_violation_frequency") for f in failures
    )


def test_accommodation_frequency_cap_exceeded_warning():
    sessions = [
        _strength_session(
            session_id=f"S-{i}",
            d=_SCOPE_START + timedelta(days=i),
            discipline_id="D-001",
            exercises=[_strength_exercise(exercise_id="E-squat")],
        )
        for i in range(4)
    ]
    payload = _minimal_layer4(sessions=sessions)
    ctx = ValidatorContext(
        layer2d_payload=_layer2d_with_accommodated(
            "E-squat",
            [
                FrequencyReductionModality(
                    sessions_per_week_cap=2,
                    discipline_id="D-001",
                    rationale="r",
                    evidence_basis=[],
                )
            ],
        )
    )
    failures = validate_layer4_payload(payload, ctx).rule_failures
    iav = [
        f for f in failures if f.rule_name.startswith("injury_accommodation_violation_frequency")
    ]
    assert iav
    assert iav[0].severity == "warning"


def test_accommodation_exercise_substitution_skipped():
    sessions = [_strength_session(exercises=[_strength_exercise(exercise_id="E-squat")])]
    payload = _minimal_layer4(sessions=sessions)
    ctx = ValidatorContext(
        layer2d_payload=_layer2d_with_accommodated(
            "E-squat",
            [ExerciseSubstitutionModality(rationale="r", evidence_basis=[])],
        )
    )
    failures = validate_layer4_payload(payload, ctx).rule_failures
    # exercise_substitution is covered by injury_violation_*; no accommodation rule fires.
    assert not any(
        f.rule_name.startswith("injury_accommodation_violation") for f in failures
    )


def test_accommodation_skipped_without_2d():
    sessions = [_strength_session()]
    payload = _minimal_layer4(sessions=sessions)
    failures = validate_layer4_payload(payload, ValidatorContext()).rule_failures
    assert not any(
        f.rule_name.startswith("injury_accommodation_violation") for f in failures
    )


# ─── Rule 11: schedule_violation ───────────────────────────────────────────


def test_schedule_violation_enabled_day_no_fire():
    windows = _full_week_windows()
    payload = _minimal_layer4()
    ctx = ValidatorContext(daily_availability_windows=tuple(windows))
    failures = validate_layer4_payload(payload, ctx).rule_failures
    assert not any(f.rule_name.startswith("schedule_violation") for f in failures)


def test_schedule_violation_disabled_day_blocker():
    # Disable Mon — session falls on Mon.
    windows = [_daily_window(dow=d, enabled=(d != "Mon")) for d in _DOW_NAMES]
    payload = _minimal_layer4()
    ctx = ValidatorContext(daily_availability_windows=tuple(windows))
    failures = validate_layer4_payload(payload, ctx).rule_failures
    sv = [f for f in failures if f.rule_name.startswith("schedule_violation")]
    assert sv
    assert sv[0].severity == "blocker"


def test_schedule_violation_athlete_self_scheduled_exempts():
    windows = [_daily_window(dow=d, enabled=(d != "Mon")) for d in _DOW_NAMES]
    payload = _minimal_layer4(
        sessions=[_cardio_session(coaching_flags=["athlete_self_scheduled"])]
    )
    ctx = ValidatorContext(daily_availability_windows=tuple(windows))
    failures = validate_layer4_payload(payload, ctx).rule_failures
    assert not any(f.rule_name.startswith("schedule_violation") for f in failures)


# ─── Rule 12: discipline_excluded ──────────────────────────────────────────


def test_discipline_included_no_fire():
    payload = _minimal_layer4()
    ctx = ValidatorContext(layer2a_payload=_layer2a_with_band(discipline_id="D-001"))
    failures = validate_layer4_payload(payload, ctx).rule_failures
    assert not any(f.rule_name.startswith("discipline_excluded") for f in failures)


def test_discipline_excluded_by_2a_blocker():
    payload = _minimal_layer4(sessions=[_cardio_session(discipline_id="D-002")])
    ctx = ValidatorContext(layer2a_payload=_layer2a_with_band(discipline_id="D-001"))
    failures = validate_layer4_payload(payload, ctx).rule_failures
    de = [f for f in failures if f.rule_name.startswith("discipline_excluded")]
    assert de
    assert de[0].severity == "blocker"


def test_discipline_excluded_d67_per_date_blocker():
    payload = _minimal_layer4()
    ctx = ValidatorContext(
        layer2a_payload=_layer2a_with_band(),
        per_date_restrictions=(
            PerDateRestriction(date=datetime(2026, 6, 1), discipline_exclusions=["D-001"]),
        ),
    )
    failures = validate_layer4_payload(payload, ctx).rule_failures
    de = [f for f in failures if f.rule_name.startswith("discipline_excluded_per_date")]
    assert de
    assert de[0].severity == "blocker"


# ─── Rule 13: sport_locale_incompatible ────────────────────────────────────


def test_sport_locale_compatible_no_fire():
    payload = _minimal_layer4()
    ctx = ValidatorContext(layer2c_payloads={"L-home": _layer2c()})
    failures = validate_layer4_payload(payload, ctx).rule_failures
    assert not any(f.rule_name.startswith("sport_locale_incompatible") for f in failures)


def test_sport_locale_incompatible_blocker():
    payload = _minimal_layer4(sessions=[_cardio_session(discipline_id="D-MTB")])
    ctx = ValidatorContext(
        layer2c_payloads={
            "L-home": _layer2c(coverage_pct=0.0, total_exercises=0, discipline_id="D-MTB")
        }
    )
    failures = validate_layer4_payload(payload, ctx).rule_failures
    sl = [f for f in failures if f.rule_name.startswith("sport_locale_incompatible")]
    assert sl
    assert sl[0].severity == "blocker"


# ─── Rule 14: taper_phase_intent_violation ─────────────────────────────────


def test_taper_phase_intent_violation_skipped_for_non_race_week_brief():
    payload = _minimal_layer4()
    failures = validate_layer4_payload(payload, ValidatorContext()).rule_failures
    assert not any(f.rule_name.startswith("taper_phase_intent_violation") for f in failures)


def test_taper_phase_intent_violation_hard_within_2d_blocker():
    event_date = _SCOPE_START + timedelta(days=1)
    sessions = [
        _cardio_session(
            session_id="S-1",
            d=_SCOPE_START,  # 1d to event
            intensity_summary="hard",
            phase_metadata=_phase_metadata(phase="Taper"),
        )
    ]
    payload = _minimal_layer4(
        mode="race_week_brief",
        pattern="B",
        sessions=sessions,
        race_week_brief=_race_week_brief(event_date=event_date),
    )
    failures = validate_layer4_payload(payload, ValidatorContext()).rule_failures
    tv = [f for f in failures if f.rule_name.startswith("taper_phase_intent_violation_hard")]
    assert tv
    assert tv[0].severity == "blocker"


def test_taper_phase_intent_long_session_within_2d_blocker():
    event_date = _SCOPE_START + timedelta(days=1)
    sessions = [
        _cardio_session(
            session_id="S-1",
            d=_SCOPE_START,
            duration_min=180,  # 3h long-duration
            intensity_summary="easy",
            phase_metadata=_phase_metadata(phase="Taper"),
        )
    ]
    payload = _minimal_layer4(
        mode="race_week_brief",
        pattern="B",
        sessions=sessions,
        race_week_brief=_race_week_brief(event_date=event_date),
    )
    failures = validate_layer4_payload(payload, ValidatorContext()).rule_failures
    tv = [f for f in failures if f.rule_name.startswith("taper_phase_intent_violation_long")]
    assert tv
    assert tv[0].severity == "blocker"


# ─── Rule 15: kit_manifest_inputs_incomplete ───────────────────────────────


def test_kit_manifest_inputs_incomplete_skipped_for_single_day():
    event_date = _SCOPE_START + timedelta(days=5)
    payload = _minimal_layer4(
        mode="race_week_brief",
        pattern="B",
        sessions=[
            _cardio_session(phase_metadata=_phase_metadata(phase="Taper"))
        ],
        race_week_brief=_race_week_brief(event_date=event_date, race_format="single_day"),
    )
    failures = validate_layer4_payload(payload, ValidatorContext()).rule_failures
    assert not any(f.rule_name == "kit_manifest_inputs_incomplete" for f in failures)


def test_kit_manifest_inputs_incomplete_skipped_when_race_event_none():
    """D-66 active branch (Layer4_Spec.md §5.4 line 912): rule skips when
    `ctx.race_event is None`. Replaces the pre-D-66 always-warn behavior."""
    event_date = _SCOPE_START + timedelta(days=5)
    payload = _minimal_layer4(
        mode="race_week_brief",
        pattern="B",
        sessions=[
            _cardio_session(phase_metadata=_phase_metadata(phase="Taper"))
        ],
        race_week_brief=_race_week_brief(
            event_date=event_date,
            race_format="continuous_multi_day",
            contingencies=["gi", "hydration", "mechanical", "nav", "sleep_dep", "weather"],
        ),
        race_plan=_race_plan_multi_day(),
    )
    failures = validate_layer4_payload(payload, ValidatorContext()).rule_failures
    assert not any(
        f.rule_name.startswith("kit_manifest_inputs_incomplete") for f in failures
    )


def test_kit_manifest_inputs_incomplete_no_route_locales_warns():
    """D-66 active branch: emit `kit_manifest_inputs_incomplete_no_route_locales`
    when route_locales empty."""
    event_date = _SCOPE_START + timedelta(days=5)
    payload = _minimal_layer4(
        mode="race_week_brief",
        pattern="B",
        sessions=[
            _cardio_session(phase_metadata=_phase_metadata(phase="Taper"))
        ],
        race_week_brief=_race_week_brief(
            event_date=event_date,
            race_format="continuous_multi_day",
            contingencies=["gi", "hydration", "mechanical", "nav", "sleep_dep", "weather"],
        ),
        race_plan=_race_plan_multi_day(),
    )
    race_event = RaceEventPayload(
        race_event_id=1,
        user_id=1,
        name="Test Race",
        event_date=event_date,
        race_format="continuous_multi_day",
        event_locale_mapbox_id="poi.test_anchor",
        is_target_event=True,
        route_locales=[],
    )
    failures = validate_layer4_payload(
        payload, ValidatorContext(race_event=race_event)
    ).rule_failures
    km = [
        f
        for f in failures
        if f.rule_name == "kit_manifest_inputs_incomplete_no_route_locales"
    ]
    assert km
    assert km[0].severity == "warning"


# ─── Rule 16: race_plan_segments_unordered ─────────────────────────────────


def test_race_plan_segments_ordered_no_fire():
    event_date = _SCOPE_START + timedelta(days=5)
    payload = _minimal_layer4(
        mode="race_week_brief",
        pattern="B",
        sessions=[
            _cardio_session(phase_metadata=_phase_metadata(phase="Taper"))
        ],
        race_week_brief=_race_week_brief(
            event_date=event_date,
            race_format="continuous_multi_day",
            contingencies=["gi", "hydration", "mechanical", "cumulative_fatigue"],
        ),
        race_plan=_race_plan_multi_day(segments_offsets=[0.0, 6.0, 12.0]),
    )
    failures = validate_layer4_payload(payload, ValidatorContext()).rule_failures
    assert not any(f.rule_name.startswith("race_plan_segments_unordered") for f in failures)


def test_race_plan_segments_offsets_decreasing_blocker():
    """segment_index is monotonic per pydantic; offset_hr can violate."""
    event_date = _SCOPE_START + timedelta(days=5)
    payload = _minimal_layer4(
        mode="race_week_brief",
        pattern="B",
        sessions=[
            _cardio_session(phase_metadata=_phase_metadata(phase="Taper"))
        ],
        race_week_brief=_race_week_brief(
            event_date=event_date,
            race_format="continuous_multi_day",
            contingencies=["gi", "hydration", "mechanical", "cumulative_fatigue"],
        ),
        race_plan=_race_plan_multi_day(segments_offsets=[0.0, 12.0, 6.0]),
    )
    failures = validate_layer4_payload(payload, ValidatorContext()).rule_failures
    rps = [f for f in failures if f.rule_name.startswith("race_plan_segments_unordered")]
    assert rps
    assert rps[0].severity == "blocker"


# ─── Rule 17: fueling_strategy_2e_tier_mismatch ────────────────────────────


def test_fueling_strategy_within_tier_no_fire():
    event_date = _SCOPE_START + timedelta(days=5)
    payload = _minimal_layer4(
        mode="race_week_brief",
        pattern="B",
        sessions=[
            _cardio_session(phase_metadata=_phase_metadata(phase="Taper"))
        ],
        race_week_brief=_race_week_brief(
            event_date=event_date,
            race_format="continuous_multi_day",
            contingencies=["gi", "hydration", "mechanical", "cumulative_fatigue"],
        ),
        race_plan=_race_plan_multi_day(cho_low=70, cho_high=80, sodium=600, fluid=600),
    )
    ctx = ValidatorContext(layer2e_payload=_layer2e_with_tier())
    failures = validate_layer4_payload(payload, ctx).rule_failures
    assert not any(
        f.rule_name.startswith("fueling_strategy_2e_tier_mismatch") for f in failures
    )


def test_fueling_strategy_cho_high_outside_blocker():
    event_date = _SCOPE_START + timedelta(days=5)
    payload = _minimal_layer4(
        mode="race_week_brief",
        pattern="B",
        sessions=[
            _cardio_session(phase_metadata=_phase_metadata(phase="Taper"))
        ],
        race_week_brief=_race_week_brief(
            event_date=event_date,
            race_format="continuous_multi_day",
            contingencies=["gi", "hydration", "mechanical", "cumulative_fatigue"],
        ),
        race_plan=_race_plan_multi_day(cho_low=70, cho_high=150),  # 150 > 90 tier high
    )
    ctx = ValidatorContext(layer2e_payload=_layer2e_with_tier())
    failures = validate_layer4_payload(payload, ctx).rule_failures
    fs = [f for f in failures if f.rule_name.startswith("fueling_strategy_2e_tier_mismatch")]
    assert fs
    assert fs[0].severity == "blocker"


def test_fueling_strategy_sodium_below_blocker():
    event_date = _SCOPE_START + timedelta(days=5)
    payload = _minimal_layer4(
        mode="race_week_brief",
        pattern="B",
        sessions=[
            _cardio_session(phase_metadata=_phase_metadata(phase="Taper"))
        ],
        race_week_brief=_race_week_brief(
            event_date=event_date,
            race_format="continuous_multi_day",
            contingencies=["gi", "hydration", "mechanical", "cumulative_fatigue"],
        ),
        race_plan=_race_plan_multi_day(sodium=100),  # below 500 tier low
    )
    ctx = ValidatorContext(layer2e_payload=_layer2e_with_tier())
    failures = validate_layer4_payload(payload, ctx).rule_failures
    fs = [
        f
        for f in failures
        if f.rule_name == "fueling_strategy_2e_tier_mismatch_sodium"
    ]
    assert fs


# ─── Rule 18: contingency_anchor_category_missing ──────────────────────────


def test_contingency_anchors_covered_no_fire():
    event_date = _SCOPE_START + timedelta(days=5)
    payload = _minimal_layer4(
        mode="race_week_brief",
        pattern="B",
        sessions=[
            _cardio_session(phase_metadata=_phase_metadata(phase="Taper"))
        ],
        race_week_brief=_race_week_brief(
            event_date=event_date,
            race_format="continuous_multi_day",
            # continuous_multi_day requires gi / hydration / mechanical /
            # weather (universal) / cumulative_fatigue + sleep_dep. The nav
            # anchor was retired 2026-05-25.
            contingencies=[
                "gi distress",
                "hydration shortfall",
                "mechanical failure",
                "weather window + storm bail plan",
                "cumulative_fatigue",
                "sleep dep management",
            ],
        ),
        race_plan=_race_plan_multi_day(),
    )
    failures = validate_layer4_payload(payload, ValidatorContext()).rule_failures
    assert not any(
        f.rule_name.startswith("contingency_anchor_category_missing") for f in failures
    )


def test_contingency_anchor_weather_universal_warns_when_missing():
    """`weather` is a universal anchor — even a single-day race warns when
    the brief omits it (2026-05-25)."""
    event_date = _SCOPE_START + timedelta(days=5)
    payload = _minimal_layer4(
        mode="race_week_brief",
        pattern="B",
        sessions=[
            _cardio_session(phase_metadata=_phase_metadata(phase="Taper"))
        ],
        race_week_brief=_race_week_brief(
            event_date=event_date,
            race_format="single_day",
            # gi / hydration / mechanical present; weather deliberately absent.
            contingencies=[
                "gi distress",
                "hydration shortfall",
                "mechanical failure",
            ],
        ),
    )
    failures = validate_layer4_payload(payload, ValidatorContext()).rule_failures
    weather = [
        f
        for f in failures
        if f.rule_name == "contingency_anchor_category_missing_weather"
    ]
    assert len(weather) == 1
    assert weather[0].severity == "warning"


def test_contingency_anchor_missing_warns():
    event_date = _SCOPE_START + timedelta(days=5)
    payload = _minimal_layer4(
        mode="race_week_brief",
        pattern="B",
        sessions=[
            _cardio_session(phase_metadata=_phase_metadata(phase="Taper"))
        ],
        race_week_brief=_race_week_brief(
            event_date=event_date,
            race_format="continuous_multi_day",
            contingencies=["gi"],  # missing hydration / mechanical / cumulative_fatigue / sleep_dep
        ),
        race_plan=_race_plan_multi_day(),
    )
    failures = validate_layer4_payload(payload, ValidatorContext()).rule_failures
    cm = [f for f in failures if f.rule_name.startswith("contingency_anchor_category_missing")]
    assert cm
    assert all(f.severity == "warning" for f in cm)


# ─── Rule 19: phase_date_out_of_range ──────────────────────────────────────


def test_phase_date_in_range_no_fire():
    payload = _minimal_layer4()
    failures = validate_layer4_payload(payload, ValidatorContext()).rule_failures
    assert not any(f.rule_name.startswith("phase_date_out_of_range") for f in failures)


def test_phase_date_out_of_range_blocker():
    # Session outside phase bounds (Base ends at +55d, session at +100d).
    sessions = [_cardio_session(d=_SCOPE_START + timedelta(days=100))]
    payload = _minimal_layer4(sessions=sessions)
    failures = validate_layer4_payload(payload, ValidatorContext()).rule_failures
    pdoor = [f for f in failures if f.rule_name.startswith("phase_date_out_of_range")]
    assert pdoor
    assert pdoor[0].severity == "blocker"


def test_phase_date_out_of_range_skipped_without_phase_structure():
    sessions = [
        _strength_session(
            phase_metadata=None,
            session_id="S-1",
        )
    ]
    sessions[0] = sessions[0].model_copy(update={"is_ad_hoc": True, "ad_hoc_request_payload": {}})
    payload = _minimal_layer4(
        mode="single_session_synthesize",
        pattern="B",
        suggestion_id=99,
        sessions=sessions,
    )
    failures = validate_layer4_payload(payload, ValidatorContext()).rule_failures
    assert not any(f.rule_name.startswith("phase_date_out_of_range") for f in failures)


# ─── Rule 20: daily_window_fit ─────────────────────────────────────────────


def test_daily_window_fit_within_no_fire():
    payload = _minimal_layer4(
        sessions=[_cardio_session(duration_min=60)]
    )
    ctx = ValidatorContext(daily_availability_windows=tuple(_full_week_windows(duration=120)))
    failures = validate_layer4_payload(payload, ctx).rule_failures
    assert not any(f.rule_name.startswith("daily_window_fit") for f in failures)


def test_daily_window_fit_exceeds_blocker():
    payload = _minimal_layer4(
        sessions=[_cardio_session(duration_min=180)]
    )
    ctx = ValidatorContext(daily_availability_windows=tuple(_full_week_windows(duration=120)))
    failures = validate_layer4_payload(payload, ctx).rule_failures
    wf = [f for f in failures if f.rule_name.startswith("daily_window_fit_window")]
    assert wf
    assert wf[0].severity == "blocker"


def test_daily_window_fit_d67_max_total_minutes_blocker():
    payload = _minimal_layer4(
        sessions=[_cardio_session(duration_min=60)]
    )
    ctx = ValidatorContext(
        daily_availability_windows=tuple(_full_week_windows(duration=120)),
        per_date_restrictions=(
            PerDateRestriction(date=datetime(2026, 6, 1), max_total_minutes=30),
        ),
    )
    failures = validate_layer4_payload(payload, ctx).rule_failures
    wf = [f for f in failures if f.rule_name.startswith("daily_window_fit_d67_max")]
    assert wf
    assert wf[0].severity == "blocker"


# ─── Rule 21: indoor_only_violation ────────────────────────────────────────


def test_indoor_only_no_restrictions_no_fire():
    payload = _minimal_layer4()
    failures = validate_layer4_payload(payload, ValidatorContext()).rule_failures
    assert not any(f.rule_name.startswith("indoor_only_violation") for f in failures)


def test_indoor_only_violation_outdoor_discipline_blocker():
    payload = _minimal_layer4(
        sessions=[_cardio_session(discipline_id="trail_running")]
    )
    ctx = ValidatorContext(
        per_date_restrictions=(
            PerDateRestriction(date=datetime(2026, 6, 1), indoor_only=True),
        ),
    )
    failures = validate_layer4_payload(payload, ctx).rule_failures
    iv = [f for f in failures if f.rule_name.startswith("indoor_only_violation")]
    assert iv
    assert iv[0].severity == "blocker"


def test_indoor_only_indoor_discipline_no_fire():
    payload = _minimal_layer4(
        sessions=[_cardio_session(discipline_id="indoor_cycling")]
    )
    ctx = ValidatorContext(
        per_date_restrictions=(
            PerDateRestriction(date=datetime(2026, 6, 1), indoor_only=True),
        ),
    )
    failures = validate_layer4_payload(payload, ctx).rule_failures
    assert not any(f.rule_name.startswith("indoor_only_violation") for f in failures)


# ─── Mode-gating per entry point (×4) ───────────────────────────────────────


def test_mode_gate_single_session_skips_volume_acwr_intensity():
    sessions = [
        _strength_session(session_id="S-1", phase_metadata=None).model_copy(
            update={"is_ad_hoc": True, "ad_hoc_request_payload": {"x": 1}}
        )
    ]
    payload = _minimal_layer4(
        mode="single_session_synthesize",
        pattern="B",
        suggestion_id=99,
        sessions=sessions,
    )
    ctx = ValidatorContext(
        layer2a_payload=_layer2a_with_band(),
        prior_session_loads_by_date={},
    )
    failures = validate_layer4_payload(payload, ctx).rule_failures
    assert not any(f.rule_name.startswith("volume_band") for f in failures)
    assert not any(f.rule_name.startswith("acwr") for f in failures)
    assert not any(f.rule_name.startswith("intensity_dist") for f in failures)
    assert not any(f.rule_name.startswith("phase_date_out_of_range") for f in failures)


def test_mode_gate_race_week_brief_runs_taper_rules_only():
    event_date = _SCOPE_START + timedelta(days=5)
    payload = _minimal_layer4(
        mode="race_week_brief",
        pattern="B",
        sessions=[
            _cardio_session(phase_metadata=_phase_metadata(phase="Taper"))
        ],
        race_week_brief=_race_week_brief(event_date=event_date),
    )
    failures = validate_layer4_payload(payload, ValidatorContext()).rule_failures
    # taper_phase_intent_violation can fire; kit_manifest_inputs_incomplete only on multi-day.
    assert not any(f.rule_name == "kit_manifest_inputs_incomplete" for f in failures)


def test_mode_gate_plan_refresh_b_no_phase_date_check():
    sessions = [_cardio_session(phase_metadata=None)]
    payload = _minimal_layer4(
        mode="plan_refresh", pattern="B", sessions=sessions
    )
    failures = validate_layer4_payload(payload, ValidatorContext()).rule_failures
    # phase_metadata is None → rule skips automatically.
    assert not any(f.rule_name.startswith("phase_date_out_of_range") for f in failures)


def test_mode_gate_plan_create_runs_phase_date_check():
    sessions = [_cardio_session(d=_SCOPE_START + timedelta(days=500))]
    payload = _minimal_layer4(sessions=sessions)  # default mode plan_create + pattern A
    failures = validate_layer4_payload(payload, ValidatorContext()).rule_failures
    assert any(f.rule_name.startswith("phase_date_out_of_range") for f in failures)


# ─── Parametrized boundary tests ────────────────────────────────────────────


@pytest.mark.parametrize(
    "actual_hours,expected_severity",
    [
        # Band: low=5, high=8. warning ±10% → 4.5/8.8; blocker ±20% → 4.0/9.6.
        (6.0, None),  # in band
        (8.5, None),  # within ±10% (warning_high=8.8)
        (9.0, "warning"),
        (9.7, "blocker"),
        (12.0, "blocker"),
        (4.6, None),  # 4.6 > 4.5 warning_low → in band
        (4.4, "warning"),  # below 4.5 warning_low
        (3.9, "blocker"),  # below 4.0 blocker_low
    ],
)
def test_volume_band_boundaries(actual_hours: float, expected_severity: str | None):
    # Build sessions totalling actual_hours on a single ISO week.
    minutes = int(actual_hours * 60)
    sessions = [
        _cardio_session(
            session_id="S-1",
            d=_SCOPE_START,
            duration_min=minutes,
        )
    ]
    payload = _minimal_layer4(sessions=sessions)
    ctx = ValidatorContext(
        layer2a_payload=_layer2a_with_band(), capacity_hours=999.0
    )
    failures = validate_layer4_payload(payload, ctx).rule_failures
    vb = [f for f in failures if f.rule_name.startswith("volume_band")]
    if expected_severity is None:
        assert not vb, f"unexpected volume_band failures for {actual_hours}h: {_names_of(vb)}"
    else:
        assert vb, f"expected volume_band {expected_severity} for {actual_hours}h"
        assert vb[0].severity == expected_severity


# ─── Rule 1: volume_band — pct→hours conversion (unit-bug regression) ─────────


def _layer2a_multi(
    disc_pcts: dict[str, tuple[float, float]],
    weekly_total: tuple[float, float],
) -> Layer2APayload:
    """Layer2APayload with several INCLUDED disciplines carrying identical
    Base/Build/Peak/Taper PERCENTAGE bands + a per-phase weekly-total hour
    range. Mirrors the real catalog shape (phase_load is %, hours are separate)."""
    disciplines = [
        Layer2ADiscipline(
            discipline_id=did,
            discipline_name=did,
            inclusion="included",
            role="Primary",
            is_conditional=False,
            load_weight=WeightResult(
                value=None, source="system_default", system_default=None
            ),
            sleep_deprivation_relevant=False,
            rationale="r",
            phase_load=PhaseLoadBands(
                base_low=lo, base_high=hi,
                build_low=lo, build_high=hi,
                peak_low=lo, peak_high=hi,
                taper_low=lo, taper_high=hi,
                default_inclusion="included",
            ),
        )
        for did, (lo, hi) in disc_pcts.items()
    ]
    return Layer2APayload(
        framework_sport="AR",
        etl_version_set={"layer0": "v7"},
        disciplines=disciplines,
        weekly_total_hours_by_phase={
            p: weekly_total for p in ("Base", "Build", "Peak", "Taper")
        },
        training_gaps_summary=TrainingGapsSummary(
            flagged_count=0,
            any_no_substitute=False,
            any_multi_substitute_candidate=False,
        ),
        hitl_required=False,
        unresolved_flags=[],
        coaching_flags=[],
        rationale_metadata=RationaleMetadata(
            template_version="v1", generated_at="2026-05-17T10:00:00Z"
        ),
    )


def test_volume_band_uses_hours_not_raw_percentages():
    """`phase_load` values are PERCENTAGES. Compared raw against actual hours
    they flagged `volume_band_below` on every discipline (the real bug). The
    band must be the capacity-bounded HOUR conversion instead."""
    disc_pcts = {
        "D-trail": (10.0, 20.0),  # mid 15
        "D-bike": (30.0, 50.0),   # mid 40
        "D-hike": (40.0, 50.0),   # mid 45  → Σ mids = 100 (renorm factor 1)
    }
    layer2a = _layer2a_multi(disc_pcts, weekly_total=(16.0, 18.0))
    capacity = 10.0  # athlete has 10h/wk (< 18h framework) → effective 10h

    bands = phase_volume_bands_hours(layer2a, "Base", capacity)
    # Converted to HOURS (pct/100 × 10h), NOT the raw percentages.
    assert bands["D-trail"] == pytest.approx((1.0, 2.0))
    assert bands["D-bike"] == pytest.approx((3.0, 5.0))
    assert bands["D-trail"][0] < 5.0  # hours, not the raw "10"

    # Realistic trail (1.5h) + bike (4h) week — inside the hour bands. The old
    # raw-% comparison would have flagged both below (1.5 < 10×0.8).
    sessions = [
        _cardio_session(
            session_id="S-t", d=_SCOPE_START, duration_min=90, discipline_id="D-trail"
        ),
        _cardio_session(
            session_id="S-b",
            d=_SCOPE_START + timedelta(days=1),
            duration_min=240,
            discipline_id="D-bike",
        ),
    ]
    payload = _minimal_layer4(sessions=sessions)
    ctx = ValidatorContext(layer2a_payload=layer2a, capacity_hours=capacity)
    failures = validate_layer4_payload(payload, ctx).rule_failures
    assert not [f for f in failures if f.rule_name.startswith("volume_band")]


def test_volume_band_below_fires_on_genuine_hour_shortfall():
    """The rule still catches a real shortfall once the band is in hours."""
    disc_pcts = {
        "D-trail": (10.0, 20.0),
        "D-bike": (30.0, 50.0),
        "D-hike": (40.0, 50.0),
    }
    layer2a = _layer2a_multi(disc_pcts, weekly_total=(16.0, 18.0))
    # trail band 1.0–2.0h; 0.5h is below blocker_low (0.8h).
    sessions = [
        _cardio_session(
            session_id="S-t", d=_SCOPE_START, duration_min=30, discipline_id="D-trail"
        ),
    ]
    payload = _minimal_layer4(sessions=sessions)
    ctx = ValidatorContext(layer2a_payload=layer2a, capacity_hours=10.0)
    failures = validate_layer4_payload(payload, ctx).rule_failures
    vb = [f for f in failures if f.rule_name.startswith("volume_band_below")]
    assert vb and vb[0].severity == "blocker"


def test_volume_band_open_ended_without_capacity():
    """No capacity → open-ended band (rule no-ops), preserving behavior for
    entry points that don't supply the athlete's hours."""
    layer2a = _layer2a_multi({"D-trail": (10.0, 20.0)}, weekly_total=(16.0, 18.0))
    sessions = [
        _cardio_session(
            session_id="S-t", d=_SCOPE_START, duration_min=30, discipline_id="D-trail"
        ),
    ]
    payload = _minimal_layer4(sessions=sessions)
    ctx = ValidatorContext(layer2a_payload=layer2a, capacity_hours=None)
    failures = validate_layer4_payload(payload, ctx).rule_failures
    assert not [f for f in failures if f.rule_name.startswith("volume_band")]


@pytest.mark.parametrize(
    "factor,reps,expected_fire",
    [
        (0.5, 5, False),  # 3 sets × 5 = 15 ≤ 40 × 0.5 × 1.10 = 22
        (0.5, 10, True),  # 30 > 22
        (0.7, 5, False),  # 15 ≤ 40 × 0.7 × 1.10 = 30.8
        (0.7, 12, True),  # 36 > 30.8
        (1.0, 14, False),  # 3×14=42 ≤ 40 × 1.0 × 1.10 = 44 → in tolerance
        (1.0, 15, True),  # 3×15=45 > 44 threshold → fires (factor=1 + 10% tolerance)
    ],
)
def test_accommodation_volume_boundaries(factor: float, reps: int, expected_fire: bool):
    sessions = [
        _strength_session(
            exercises=[
                _strength_exercise(exercise_id="E-squat", sets=3, reps=reps, load="60% 1RM")
            ]
        )
    ]
    payload = _minimal_layer4(sessions=sessions)
    ctx = ValidatorContext(
        layer2d_payload=_layer2d_with_accommodated(
            "E-squat",
            [
                VolumeReductionModality(
                    factor=factor, applies_to="sets", rationale="r", evidence_basis=[]
                )
            ],
        )
    )
    failures = validate_layer4_payload(payload, ctx).rule_failures
    iav = [f for f in failures if f.rule_name.startswith("injury_accommodation_violation_volume")]
    if expected_fire:
        assert iav, f"expected volume violation for factor={factor} reps={reps}"
    else:
        assert not iav, f"unexpected volume violation for factor={factor} reps={reps}"
