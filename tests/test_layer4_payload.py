"""Tests for Layer 4 payload schemas — §7.12 invariants + JSON round-trip + extra-forbid.

Test scope is Layer4_Spec.md §7.12 SCHEMA rules only. Domain rules
(§5.4 validator harness — volume bands, ACWR, injury exclusions, etc.)
land in their own test module with the Step 3 validator harness.
"""

from __future__ import annotations

from datetime import date, datetime, timezone
from typing import Any

import pytest
from pydantic import ValidationError

from layer4.payload import (
    CadenceTarget,
    CardioBlock,
    ClimbingGradeTarget,
    Contingency,
    FuelingStrategy,
    HRTarget,
    KitItem,
    Layer4Payload,
    Observation,
    PaceTarget,
    PacingStrategy,
    PhaseSpec,
    PhaseStructure,
    PlanSession,
    PowerTarget,
    RPETarget,
    RacePlan,
    RaceSegment,
    RaceWeekBrief,
    RuleFailure,
    SeamReview,
    SessionPhaseMetadata,
    ShapeOverride,
    StrengthExercise,
    StrokeRateTarget,
    SwimPaceTarget,
    SynthesisMetadata,
    TransitionSpec,
    ValidatorResult,
    VerticalRateTarget,
)


# ─── builders ───────────────────────────────────────────────────────────────


def _accepted_validator_result() -> ValidatorResult:
    return ValidatorResult(
        pass_index=0, accepted=True, rule_failures=[], retried_phase_names=[]
    )


def _phase_metadata() -> SessionPhaseMetadata:
    return SessionPhaseMetadata(
        phase_name="Base",
        week_in_phase=1,
        total_weeks_in_phase=4,
        intended_volume_band=(6.0, 8.0),
        intended_intensity_distribution={"Z1-Z2": 0.8, "Z3": 0.15, "Z4-Z5": 0.05},
    )


def _cardio_block(block_kind: str = "main_set") -> CardioBlock:
    base: dict[str, Any] = {
        "block_kind": block_kind,
        "duration_min": 30,
        "intensity_zone": "Z2",
        "intensity_target": HRTarget(hr_bpm_low=140, hr_bpm_high=155),
        "instructions": "Steady Z2 effort.",
    }
    if block_kind == "interval_set":
        base.update({"repetitions": 4, "rest_between_min": 2, "rest_intensity_zone": "Z1"})
    return CardioBlock(**base)


def _cardio_session(
    *,
    session_id: str = "s-cardio-1",
    date_: date = date(2026, 6, 1),
    day_of_week: str = "Mon",
    session_index_in_day: int = 0,
    intensity_summary: str = "moderate",
    with_phase_metadata: bool = True,
) -> PlanSession:
    return PlanSession(
        session_id=session_id,
        plan_version_id=42,
        date=date_,
        day_of_week=day_of_week,
        session_index_in_day=session_index_in_day,
        time_of_day="morning",
        kind="cardio",
        discipline_id="run",
        discipline_name="Run",
        locale_id="loc-home",
        locale_name="Home",
        duration_min=45,
        intensity_summary=intensity_summary,
        cardio_blocks=[_cardio_block()],
        phase_metadata=_phase_metadata() if with_phase_metadata else None,
        session_notes="Z2 run; steady pace.",
        coaching_intent="Aerobic base.",
        coaching_flags=[],
    )


def _strength_exercise(tier: int = 1) -> StrengthExercise:
    base: dict[str, Any] = {
        "exercise_id": "ex-1",
        "exercise_name": "Goblet squat",
        "resolution_tier": tier,
        "sets": 3,
        "reps_per_set": 10,
        "load_prescription": "20 kg dumbbell",
        "rest_between_sets_sec": 90,
        "instructions": "Controlled descent; drive through midfoot.",
        "coaching_flags": [],
    }
    if tier == 2:
        base["substitute_text"] = "DB substitute for barbell back squat (no rack)"
    if tier == 3:
        base["proxy_origin_id"] = "ex-back-squat"
    return StrengthExercise(**base)


def _strength_session(
    *,
    session_id: str = "s-strength-1",
    date_: date = date(2026, 6, 2),
    day_of_week: str = "Tue",
    session_index_in_day: int = 0,
    intensity_summary: str = "moderate",
    with_phase_metadata: bool = True,
) -> PlanSession:
    return PlanSession(
        session_id=session_id,
        plan_version_id=42,
        date=date_,
        day_of_week=day_of_week,
        session_index_in_day=session_index_in_day,
        time_of_day="evening",
        kind="strength",
        discipline_id="strength",
        discipline_name="Strength",
        locale_id="loc-home",
        locale_name="Home",
        duration_min=45,
        intensity_summary=intensity_summary,
        strength_exercises=[_strength_exercise()],
        phase_metadata=_phase_metadata() if with_phase_metadata else None,
        session_notes="Lower-body strength.",
        coaching_intent="General prep.",
        coaching_flags=[],
    )


def _rest_session(
    *,
    session_id: str = "s-rest-1",
    date_: date = date(2026, 6, 3),
    day_of_week: str = "Wed",
    with_phase_metadata: bool = True,
) -> PlanSession:
    return PlanSession(
        session_id=session_id,
        plan_version_id=42,
        date=date_,
        day_of_week=day_of_week,
        session_index_in_day=0,
        time_of_day="unspecified",
        kind="rest",
        duration_min=0,
        intensity_summary="rest",
        rest_reason="planned_recovery",
        phase_metadata=_phase_metadata() if with_phase_metadata else None,
        session_notes="Rest day.",
        coaching_intent="Recovery.",
        coaching_flags=[],
    )


def _phase_structure() -> PhaseStructure:
    sm = SynthesisMetadata(
        model="claude-sonnet-4-6",
        temperature=0.5,
        input_tokens=1000,
        output_tokens=500,
        latency_ms=5000,
        retries_used=0,
        cap_hit=False,
    )
    return PhaseStructure(
        phases=[
            PhaseSpec(
                phase_name="Base",
                start_date=date(2026, 6, 1),
                end_date=date(2026, 6, 28),
                weeks=4,
                intended_volume_band=(6.0, 8.0),
                intended_intensity_distribution={"Z1-Z2": 0.8, "Z3": 0.15, "Z4-Z5": 0.05},
                synthesis_metadata=sm,
            )
        ],
        total_weeks=4,
        derived_from="3b_standard",
    )


def _plan_create_payload(**overrides: Any) -> Layer4Payload:
    defaults: dict[str, Any] = dict(
        user_id=1,
        mode="plan_create",
        plan_version_id=42,
        scope_start_date=date(2026, 6, 1),
        scope_end_date=date(2026, 6, 3),
        model_synthesizer="claude-sonnet-4-6",
        model_seam_reviewer="claude-sonnet-4-6",
        temperature=0.5,
        pattern="A",
        latency_ms_total=10000,
        input_tokens_total=2000,
        output_tokens_total=1000,
        llm_call_count=1,
        etl_version_set={"layer1": "v1", "layer2a": "v1"},
        sessions=[_cardio_session(), _strength_session(), _rest_session()],
        phase_structure=_phase_structure(),
        seam_reviews=[],
        validator_results=[_accepted_validator_result()],
        notable_observations=[],
    )
    defaults.update(overrides)
    return Layer4Payload(**defaults)


def _race_week_brief(race_format: str = "single_day") -> RaceWeekBrief:
    return RaceWeekBrief(
        days_to_event=7,
        event_name="Pocket Gopher Extreme",
        event_date=date(2026, 7, 17),
        event_locale="loc-pge",
        race_format=race_format,
        goal_outcome="Finish",
        pre_race_logistics="Drive Friday; sleep Friday + Saturday onsite.",
        kit_manifest=[KitItem(item="trail shoes", purpose="primary footwear", optional=False)],
        kit_check_dates=[date(2026, 7, 10), date(2026, 7, 14), date(2026, 7, 16)],
        race_day_fueling_plan="60g CHO/hr from gels; sodium ~700mg/hr.",
        pre_race_meal_strategy="Carb-load 36h prior; race-morning oats + banana 3h pre.",
        pacing_strategy_summary="Z2 dominant; conserve through hour 24.",
        contingencies=["GI distress: switch to liquid CHO + Pepto"],
        mental_prep_cues=["Stay on plan through low points; expect them at hours 16 + 32."],
    )


def _race_plan() -> RacePlan:
    seg0 = RaceSegment(
        segment_id="seg-0",
        segment_index=0,
        sport="Trail Run",
        estimated_start_offset_hr=0.0,
        estimated_duration_min=240,
        distance_km=30.0,
        elevation_gain_m=500.0,
        terrain_notes="Mixed singletrack, mostly runnable.",
        pacing_target=HRTarget(hr_bpm_low=130, hr_bpm_high=150),
        coaching_notes="Hold back; this is the easy leg.",
    )
    seg1 = RaceSegment(
        segment_id="seg-1",
        segment_index=1,
        sport="MTB",
        estimated_start_offset_hr=4.5,
        estimated_duration_min=300,
        distance_km=60.0,
        elevation_gain_m=800.0,
        terrain_notes="Forest road + singletrack.",
        pacing_target=RPETarget(rpe_low=4, rpe_high=5),
        coaching_notes="Eat early; this is the longest leg.",
    )
    return RacePlan(
        race_name="Pocket Gopher Extreme",
        race_start_datetime=datetime(2026, 7, 17, 8, 0, tzinfo=timezone.utc),
        race_end_estimate_datetime=datetime(2026, 7, 19, 16, 0, tzinfo=timezone.utc),
        race_format="expedition_ar",
        locales=["loc-pge"],
        segments=[seg0, seg1],
        transitions=[
            TransitionSpec(
                from_segment_id="seg-0",
                to_segment_id="seg-1",
                estimated_duration_min=20,
                gear_changes=["swap to MTB shoes", "swap pack to MTB pack"],
                is_fueling_window=True,
                notes="Substantial eat — 400 kcal.",
            )
        ],
        pacing_strategy=PacingStrategy(
            overall_intensity_target="Z2 dominant; no Z4 unless emergency",
            pacing_milestones=["seg-0 done by H4.5"],
            rationale_text="Long-event durability over speed.",
        ),
        fueling_strategy=FuelingStrategy(
            cho_g_per_hr_low=50,
            cho_g_per_hr_high=80,
            sodium_mg_per_hr=700,
            fluid_ml_per_hr=500,
            caffeine_strategy="100mg every 4h after hour 12",
            rationale_text="Match 2E race-day tier.",
        ),
        contingencies=[
            Contingency(
                trigger="GI distress past hour 12",
                action_plan="Liquid CHO only; Pepto 2-tab; reassess in 30min",
                threshold_to_invoke="Persists >30min and 1st Pepto fails",
            )
        ],
    )


# ─── happy paths per mode ───────────────────────────────────────────────────


def test_plan_create_happy_path():
    p = _plan_create_payload()
    assert p.mode == "plan_create"
    assert p.pattern == "A"
    assert len(p.sessions) == 3


def test_plan_refresh_pattern_b_happy_path():
    p = _plan_create_payload(
        mode="plan_refresh",
        pattern="B",
        phase_structure=None,
        seam_reviews=None,
        model_seam_reviewer=None,
        sessions=[
            _cardio_session(with_phase_metadata=False),
            _strength_session(with_phase_metadata=False),
        ],
    )
    assert p.mode == "plan_refresh"


def test_single_session_synthesize_happy_path():
    cardio = _cardio_session(with_phase_metadata=False)
    cardio = cardio.model_copy(
        update={"is_ad_hoc": True, "ad_hoc_request_payload": {"sport": "Run"}}
    )
    p = _plan_create_payload(
        mode="single_session_synthesize",
        pattern="B",
        phase_structure=None,
        seam_reviews=None,
        model_seam_reviewer=None,
        sessions=[cardio],
        suggestion_id=999,
    )
    assert p.suggestion_id == 999


def test_race_week_brief_single_day_happy_path():
    p = _plan_create_payload(
        mode="race_week_brief",
        pattern="B",
        phase_structure=None,
        seam_reviews=None,
        model_seam_reviewer=None,
        race_week_brief=_race_week_brief("single_day"),
        race_plan=None,
    )
    assert p.race_plan is None


def test_race_week_brief_multi_day_happy_path():
    p = _plan_create_payload(
        mode="race_week_brief",
        pattern="B",
        phase_structure=None,
        seam_reviews=None,
        model_seam_reviewer=None,
        race_week_brief=_race_week_brief("expedition_ar"),
        race_plan=_race_plan(),
    )
    assert p.race_plan is not None
    assert p.race_plan.race_format == "expedition_ar"


# ─── §7.2 + §7.12 PlanSession kind invariants ───────────────────────────────


def test_cardio_requires_cardio_blocks():
    with pytest.raises(ValidationError, match="cardio_blocks non-None and non-empty"):
        _cardio_session().model_copy(update={"cardio_blocks": None}, deep=True)
        # model_copy doesn't re-validate by default; build fresh to trigger validator:
        PlanSession(
            **{**_cardio_session().model_dump(), "cardio_blocks": None}
        )


def test_cardio_forbids_strength_exercises():
    with pytest.raises(ValidationError, match="strength_exercises is None"):
        PlanSession(
            **{
                **_cardio_session().model_dump(),
                "strength_exercises": [_strength_exercise().model_dump()],
            }
        )


def test_strength_requires_strength_exercises():
    with pytest.raises(ValidationError, match="strength_exercises non-None"):
        PlanSession(
            **{**_strength_session().model_dump(), "strength_exercises": None}
        )


def test_strength_forbids_cardio_blocks():
    with pytest.raises(ValidationError, match="cardio_blocks is None"):
        PlanSession(
            **{
                **_strength_session().model_dump(),
                "cardio_blocks": [_cardio_block().model_dump()],
            }
        )


def test_rest_requires_rest_reason():
    with pytest.raises(ValidationError, match="rest_reason non-None"):
        PlanSession(**{**_rest_session().model_dump(), "rest_reason": None})


def test_rest_requires_duration_zero():
    with pytest.raises(ValidationError, match="duration_min == 0"):
        PlanSession(**{**_rest_session().model_dump(), "duration_min": 30})


def test_rest_forbids_discipline_id():
    with pytest.raises(ValidationError, match="discipline_id is None"):
        PlanSession(**{**_rest_session().model_dump(), "discipline_id": "run"})


def test_ad_hoc_requires_request_payload():
    cardio = _cardio_session(with_phase_metadata=False).model_dump()
    cardio["is_ad_hoc"] = True
    cardio["ad_hoc_request_payload"] = None
    with pytest.raises(ValidationError, match="ad_hoc_request_payload non-None"):
        PlanSession(**cardio)


# ─── §7.3 CardioBlock interval rules ────────────────────────────────────────


def test_interval_set_requires_interval_fields():
    with pytest.raises(ValidationError, match="repetitions, rest_between_min"):
        CardioBlock(
            block_kind="interval_set",
            duration_min=20,
            intensity_zone="Z4",
            intensity_target=RPETarget(rpe_low=8, rpe_high=8),
            instructions="6x3min hard",
        )


def test_non_interval_forbids_interval_fields():
    with pytest.raises(ValidationError, match="repetitions is None"):
        CardioBlock(
            block_kind="main_set",
            duration_min=20,
            intensity_zone="Z2",
            intensity_target=RPETarget(rpe_low=4, rpe_high=4),
            instructions="Steady",
            repetitions=4,
        )


# ─── §7.4 StrengthExercise resolution_tier rules ────────────────────────────


def test_tier1_forbids_substitute_or_proxy():
    with pytest.raises(ValidationError, match="substitute_text is None and proxy_origin_id is None"):
        _strength_exercise(1).model_copy()
        StrengthExercise(
            **{**_strength_exercise(1).model_dump(), "substitute_text": "foo"}
        )


def test_tier2_requires_substitute_text():
    with pytest.raises(ValidationError, match="substitute_text non-None"):
        StrengthExercise(
            **{**_strength_exercise(2).model_dump(), "substitute_text": None}
        )


def test_tier3_requires_proxy_origin_id():
    with pytest.raises(ValidationError, match="proxy_origin_id non-None"):
        StrengthExercise(
            **{**_strength_exercise(3).model_dump(), "proxy_origin_id": None}
        )


# ─── §7.12 Layer4Payload mode invariants ────────────────────────────────────


def test_plan_create_requires_phase_structure():
    with pytest.raises(ValidationError, match="phase_structure non-None"):
        _plan_create_payload(phase_structure=None)


def test_plan_create_requires_seam_reviews():
    with pytest.raises(ValidationError, match="seam_reviews non-None"):
        _plan_create_payload(seam_reviews=None)


def test_plan_refresh_pattern_b_forbids_phase_structure():
    with pytest.raises(ValidationError, match="phase_structure is None"):
        _plan_create_payload(
            mode="plan_refresh",
            pattern="B",
            phase_structure=_phase_structure(),
            seam_reviews=None,
            sessions=[_cardio_session(with_phase_metadata=False)],
        )


def test_single_session_requires_len_one():
    with pytest.raises(ValidationError, match=r"len\(sessions\)==1"):
        cardio = _cardio_session(with_phase_metadata=False).model_dump()
        cardio["is_ad_hoc"] = True
        cardio["ad_hoc_request_payload"] = {"sport": "Run"}
        _plan_create_payload(
            mode="single_session_synthesize",
            pattern="B",
            phase_structure=None,
            seam_reviews=None,
            sessions=[PlanSession(**cardio), _rest_session(with_phase_metadata=False)],
            suggestion_id=1,
        )


def test_single_session_requires_is_ad_hoc():
    with pytest.raises(ValidationError, match="is_ad_hoc==True"):
        _plan_create_payload(
            mode="single_session_synthesize",
            pattern="B",
            phase_structure=None,
            seam_reviews=None,
            sessions=[_cardio_session(with_phase_metadata=False)],
            suggestion_id=1,
        )


def test_single_session_requires_suggestion_id():
    cardio = _cardio_session(with_phase_metadata=False).model_dump()
    cardio["is_ad_hoc"] = True
    cardio["ad_hoc_request_payload"] = {"sport": "Run"}
    with pytest.raises(ValidationError, match="suggestion_id non-None"):
        _plan_create_payload(
            mode="single_session_synthesize",
            pattern="B",
            phase_structure=None,
            seam_reviews=None,
            sessions=[PlanSession(**cardio)],
            suggestion_id=None,
        )


def test_race_week_brief_single_day_forbids_race_plan():
    with pytest.raises(ValidationError, match="race_plan is None"):
        _plan_create_payload(
            mode="race_week_brief",
            pattern="B",
            phase_structure=None,
            seam_reviews=None,
            race_week_brief=_race_week_brief("single_day"),
            race_plan=_race_plan(),
        )


def test_race_week_brief_multi_day_requires_race_plan():
    with pytest.raises(ValidationError, match="race_plan non-None"):
        _plan_create_payload(
            mode="race_week_brief",
            pattern="B",
            phase_structure=None,
            seam_reviews=None,
            race_week_brief=_race_week_brief("expedition_ar"),
            race_plan=None,
        )


# ─── §7.12 two-sessions-per-day rules ───────────────────────────────────────


def test_two_strength_same_day_rejected():
    with pytest.raises(ValidationError, match="strength\\+strength"):
        _plan_create_payload(
            sessions=[
                _strength_session(
                    session_id="a",
                    date_=date(2026, 6, 5),
                    day_of_week="Fri",
                    session_index_in_day=0,
                ),
                _strength_session(
                    session_id="b",
                    date_=date(2026, 6, 5),
                    day_of_week="Fri",
                    session_index_in_day=1,
                ),
            ]
        )


def test_two_hard_same_day_rejected():
    with pytest.raises(ValidationError, match="two hard sessions"):
        _plan_create_payload(
            sessions=[
                _cardio_session(
                    session_id="a",
                    date_=date(2026, 6, 5),
                    day_of_week="Fri",
                    session_index_in_day=0,
                    intensity_summary="hard",
                ),
                _cardio_session(
                    session_id="b",
                    date_=date(2026, 6, 5),
                    day_of_week="Fri",
                    session_index_in_day=1,
                    intensity_summary="hard",
                ),
            ]
        )


def test_more_than_two_per_day_rejected():
    with pytest.raises(ValidationError, match="max 2 sessions per day"):
        _plan_create_payload(
            sessions=[
                _cardio_session(
                    session_id=f"s{i}",
                    date_=date(2026, 6, 5),
                    day_of_week="Fri",
                    session_index_in_day=0,
                )
                for i in range(3)
            ]
        )


# ─── §7.12 ValidatorResult + ShapeOverride rules ────────────────────────────


def test_empty_validator_results_rejected():
    with pytest.raises(ValidationError, match="validator_results must be non-empty"):
        _plan_create_payload(validator_results=[])


def test_unaccepted_final_pass_rejected():
    rule_failure = RuleFailure(
        rule_name="volume_band_exceeded_week_3",
        phase_name="Base",
        severity="blocker",
        detail="Week 3 exceeds upper band",
        affected_session_ids=["s-cardio-1"],
    )
    with pytest.raises(ValidationError, match=r"validator_results\[-1\].accepted must be True"):
        _plan_create_payload(
            validator_results=[
                ValidatorResult(
                    pass_index=0,
                    accepted=False,
                    rule_failures=[rule_failure],
                    retried_phase_names=["Base"],
                )
            ]
        )


def test_shape_override_requires_observation():
    override = ShapeOverride(
        original_shape_mode="standard",
        original_start_phase="Base",
        overridden_mode="compressed",
        overridden_start_phase="Build",
        rationale_text="Athlete onboarded 6 weeks out from event.",
        evidence_basis=["3b_payload.time_to_event_weeks"],
    )
    with pytest.raises(ValidationError, match="shape_override non-None requires"):
        _plan_create_payload(shape_override=override, notable_observations=[])


def test_shape_override_with_observation_ok():
    override = ShapeOverride(
        original_shape_mode="standard",
        original_start_phase="Base",
        overridden_mode="compressed",
        overridden_start_phase="Build",
        rationale_text="Athlete onboarded 6 weeks out from event.",
        evidence_basis=["3b_payload.time_to_event_weeks"],
    )
    obs = Observation(
        category="shape_override",
        text="Layer 4 overrode 3B shape mode.",
        evidence_basis=["3b_payload.time_to_event_weeks"],
        elevates_to_hitl=False,
    )
    p = _plan_create_payload(shape_override=override, notable_observations=[obs])
    assert p.shape_override is not None


# ─── §7.12 phase_metadata-per-mode rule ─────────────────────────────────────


def test_plan_create_requires_phase_metadata_on_sessions():
    with pytest.raises(ValidationError, match="phase_metadata non-None"):
        _plan_create_payload(sessions=[_cardio_session(with_phase_metadata=False)])


def test_plan_refresh_pattern_b_forbids_phase_metadata():
    with pytest.raises(ValidationError, match="phase_metadata is None"):
        _plan_create_payload(
            mode="plan_refresh",
            pattern="B",
            phase_structure=None,
            seam_reviews=None,
            model_seam_reviewer=None,
            sessions=[_cardio_session(with_phase_metadata=True)],
        )


def test_single_session_forbids_phase_metadata():
    cardio = _cardio_session(with_phase_metadata=True).model_dump()
    cardio["is_ad_hoc"] = True
    cardio["ad_hoc_request_payload"] = {"sport": "Run"}
    with pytest.raises(ValidationError, match="phase_metadata is None"):
        _plan_create_payload(
            mode="single_session_synthesize",
            pattern="B",
            phase_structure=None,
            seam_reviews=None,
            sessions=[PlanSession(**cardio)],
            suggestion_id=1,
        )


# ─── extra='forbid' (untrusted-input boundary) ──────────────────────────────


def test_extra_keys_rejected_on_payload():
    p = _plan_create_payload()
    raw = p.model_dump()
    raw["unexpected_key"] = "drift"
    with pytest.raises(ValidationError, match="unexpected_key"):
        Layer4Payload(**raw)


def test_extra_keys_rejected_on_session():
    s = _cardio_session()
    raw = s.model_dump()
    raw["spurious"] = "x"
    with pytest.raises(ValidationError, match="spurious"):
        PlanSession(**raw)


# ─── JSON round-trip (cache + tool-use ingress) ─────────────────────────────


def test_json_round_trip_plan_create():
    p = _plan_create_payload()
    serialized = p.model_dump_json()
    reconstructed = Layer4Payload.model_validate_json(serialized)
    assert reconstructed.model_dump() == p.model_dump()


def test_json_round_trip_race_week_brief_multi_day():
    p = _plan_create_payload(
        mode="race_week_brief",
        pattern="B",
        phase_structure=None,
        seam_reviews=None,
        model_seam_reviewer=None,
        race_week_brief=_race_week_brief("expedition_ar"),
        race_plan=_race_plan(),
    )
    serialized = p.model_dump_json()
    reconstructed = Layer4Payload.model_validate_json(serialized)
    assert reconstructed.model_dump() == p.model_dump()


# ─── §7.14 RacePlan chronological ordering ──────────────────────────────────


def test_race_plan_segments_unordered_rejected():
    rp = _race_plan()
    raw = rp.model_dump()
    raw["segments"][0]["segment_index"] = 5
    raw["segments"][1]["segment_index"] = 1
    with pytest.raises(ValidationError, match="chronologically ordered"):
        RacePlan(**raw)


# ─── §7.3 IntensityTarget union — happy paths per shape ────────────────────


def _block_with_target(target: Any) -> CardioBlock:
    return CardioBlock(
        block_kind="main_set",
        duration_min=30,
        intensity_zone="Z2",
        intensity_target=target,
        instructions="x",
    )


def test_target_hr_happy_path():
    b = _block_with_target(HRTarget(hr_bpm_low=140, hr_bpm_high=155))
    assert isinstance(b.intensity_target, HRTarget)


def test_target_power_happy_path():
    b = _block_with_target(PowerTarget(power_w_low=200, power_w_high=240))
    assert isinstance(b.intensity_target, PowerTarget)


def test_target_pace_happy_path():
    b = _block_with_target(PaceTarget(pace_per_km_low="5:30", pace_per_km_high="5:00"))
    assert isinstance(b.intensity_target, PaceTarget)


def test_target_swim_pace_happy_path():
    b = _block_with_target(
        SwimPaceTarget(pace_per_100m_low="1:50", pace_per_100m_high="1:35")
    )
    assert isinstance(b.intensity_target, SwimPaceTarget)


def test_target_rpe_happy_path():
    b = _block_with_target(RPETarget(rpe_low=4, rpe_high=6))
    assert isinstance(b.intensity_target, RPETarget)


def test_target_vertical_rate_happy_path():
    b = _block_with_target(VerticalRateTarget(vert_m_per_hr_low=800, vert_m_per_hr_high=1200))
    assert isinstance(b.intensity_target, VerticalRateTarget)


def test_target_stroke_rate_happy_path():
    b = _block_with_target(StrokeRateTarget(strokes_per_min_low=50, strokes_per_min_high=70))
    assert isinstance(b.intensity_target, StrokeRateTarget)


def test_target_cadence_happy_path():
    b = _block_with_target(CadenceTarget(rpm_low=85, rpm_high=95))
    assert isinstance(b.intensity_target, CadenceTarget)


def test_target_climbing_grade_yosemite_happy_path():
    b = _block_with_target(
        ClimbingGradeTarget(grade_system="yosemite_decimal", grade_min="5.10a", grade_max="5.11b")
    )
    assert isinstance(b.intensity_target, ClimbingGradeTarget)


def test_target_climbing_grade_french_sport_happy_path():
    b = _block_with_target(
        ClimbingGradeTarget(grade_system="french_sport", grade_min="6a", grade_max="7c")
    )
    assert b.intensity_target.grade_system == "french_sport"


def test_target_climbing_grade_uiaa_happy_path():
    b = _block_with_target(
        ClimbingGradeTarget(grade_system="uiaa", grade_min="V", grade_max="VIII+")
    )
    assert b.intensity_target.grade_system == "uiaa"


# ─── §7.3 IntensityTarget — type + bounds rejection ────────────────────────


def test_target_hr_string_value_rejected():
    with pytest.raises(ValidationError):
        CardioBlock(
            block_kind="main_set",
            duration_min=30,
            intensity_zone="Z2",
            intensity_target={"hr_bpm_low": "easy", "hr_bpm_high": 155},
            instructions="x",
        )


def test_target_rpe_out_of_bounds_rejected():
    with pytest.raises(ValidationError):
        RPETarget(rpe_low=1, rpe_high=99)


def test_target_hr_low_above_high_rejected():
    with pytest.raises(ValidationError, match="hr_bpm_low must be <= hr_bpm_high"):
        HRTarget(hr_bpm_low=200, hr_bpm_high=140)


def test_target_rpe_low_above_high_rejected():
    with pytest.raises(ValidationError, match="rpe_low must be <= rpe_high"):
        RPETarget(rpe_low=8, rpe_high=4)


def test_target_pace_bad_format_rejected():
    with pytest.raises(ValidationError):
        PaceTarget(pace_per_km_low="5:75", pace_per_km_high="5:00")


def test_target_pace_letters_rejected():
    with pytest.raises(ValidationError):
        PaceTarget(pace_per_km_low="fast", pace_per_km_high="slow")


def test_target_climbing_grade_system_unknown_rejected():
    with pytest.raises(ValidationError):
        ClimbingGradeTarget(grade_system="v_grade", grade_min="V4", grade_max="V6")  # type: ignore[arg-type]


def test_target_unknown_keys_rejected():
    # A dict with keys that don't match any shape in the union must reject.
    with pytest.raises(ValidationError):
        CardioBlock(
            block_kind="main_set",
            duration_min=30,
            intensity_zone="Z2",
            intensity_target={"made_up_key": 42},
            instructions="x",
        )


def test_target_mixed_keys_rejected():
    # Mixing keys from two different shapes must reject (extra='forbid' on each shape).
    with pytest.raises(ValidationError):
        CardioBlock(
            block_kind="main_set",
            duration_min=30,
            intensity_zone="Z2",
            intensity_target={"hr_bpm_low": 140, "power_w_high": 220},
            instructions="x",
        )


# ─── IntensityTarget JSON round-trip (LLM tool-use ingress shape) ──────────


def test_target_round_trip_via_dict_hr():
    # Simulates LLM emitting a dict (tool_use input arrives as JSON dict);
    # smart union resolves to HRTarget.
    block = CardioBlock(
        block_kind="main_set",
        duration_min=30,
        intensity_zone="Z2",
        intensity_target={"hr_bpm_low": 140, "hr_bpm_high": 155},  # type: ignore[arg-type]
        instructions="x",
    )
    assert isinstance(block.intensity_target, HRTarget)


def test_target_round_trip_via_dict_climbing():
    block = CardioBlock(
        block_kind="main_set",
        duration_min=30,
        intensity_zone="Z2",
        intensity_target={  # type: ignore[arg-type]
            "grade_system": "yosemite_decimal",
            "grade_min": "5.10a",
            "grade_max": "5.11b",
        },
        instructions="x",
    )
    assert isinstance(block.intensity_target, ClimbingGradeTarget)


def test_payload_with_climbing_target_json_round_trip():
    climbing_block = CardioBlock(
        block_kind="main_set",
        duration_min=60,
        intensity_zone="mixed",
        intensity_target=ClimbingGradeTarget(
            grade_system="yosemite_decimal", grade_min="5.10a", grade_max="5.11b"
        ),
        instructions="6 routes; rest as needed between attempts.",
    )
    climbing_session = _cardio_session().model_copy(update={"cardio_blocks": [climbing_block]})
    p = _plan_create_payload(
        sessions=[climbing_session, _strength_session(), _rest_session()]
    )
    serialized = p.model_dump_json()
    reconstructed = Layer4Payload.model_validate_json(serialized)
    assert isinstance(reconstructed.sessions[0].cardio_blocks[0].intensity_target, ClimbingGradeTarget)


# ─── §7.12 race_week_brief strict phase_metadata (v1 override-pass-through) ─


def test_race_week_brief_requires_phase_metadata():
    # Per the §7.12 C2 amendment + v1 strict invariant: race_week_brief only
    # modifies existing Pattern-A-produced Taper sessions, so phase_metadata
    # must be non-None on every session.
    with pytest.raises(ValidationError, match="race_week_brief.*phase_metadata non-None"):
        _plan_create_payload(
            mode="race_week_brief",
            pattern="B",
            phase_structure=None,
            seam_reviews=None,
            model_seam_reviewer=None,
            race_week_brief=_race_week_brief("single_day"),
            race_plan=None,
            sessions=[_cardio_session(with_phase_metadata=False)],
        )
