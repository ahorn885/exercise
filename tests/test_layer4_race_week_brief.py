"""Tests for `layer4/race_week_brief.py` — Step 4e integration: D-66
`llm_layer4_race_week_brief` per `Layer4_Spec.md` §3.4 + the D-66 amendment
(`race_event_payload: RaceEventPayload` positional arg).

Coverage:
- `RaceEventPayload` pydantic validation (route-locale invariants + bounds +
  JSON round-trip + extra='forbid')
- Tool schema shape (full fidelity per Step 4a precedent: typed
  IntensityTarget union + KitItem.layer0_canonical + closed coaching_flags
  enum + race_plan oneOf null)
- §4.5 input validation preconditions (including 2 new D-66 rows:
  `race_event_payload_missing` + `race_event_date_mismatch_3b`)
- Entry-point happy path × single-day + multi-day
- Observation emission (intensity_modulated bubble + opportunity LLM-emitted
  exception + data_gap from soft-warning kit_manifest rules)
- Capped retry (validator fail-then-pass + cap-hit best-effort)
- Schema violation (missing tool args + multi-day without race_plan)
- Layer4Payload composition invariants (mode + pattern + race_week_brief +
  race_plan null/non-null + phase_metadata pass-through per §7.12 C2)
- Prompt rendering (race_rules_summary verbatim + mandatory_gear_text
  verbatim + route_locales structured rendering + retry context conditional)

LLM calls mocked via a stub `llm_caller` dependency. No real Anthropic SDK
invocations.
"""

from __future__ import annotations

from datetime import date, datetime, timedelta
from decimal import Decimal
from typing import Any

import pytest

from layer4 import (
    ACWREntry,
    ACWRStatus,
    Assessment,
    CurrentState,
    DailyNutritionBaseline,
    DailyPhaseTargets,
    DataDensity,
    DisciplineCoverage,
    ExerciseRisk,
    GoalViability,
    Layer2APayload,
    Layer2ADiscipline,
    Layer2BPayload,
    Layer2BSummaryBlock,
    Layer2CPayload,
    Layer2DPayload,
    Layer2EPayload,
    Layer3APayload,
    Layer3BPayload,
    Layer4InputError,
    Layer4OutputError,
    Layer4Payload,
    MacroTargets,
    PeriodizationShape,
    PhaseLoadBands,
    RaceDayFueling,
    RaceEventPayload,
    RaceTerrainOutput,
    RationaleMetadata,
    RecentTrajectory,
    ResolvedExercise,
    RouteLocale,
    RouteLocaleEquipment,
    SupplementIntegrationPayload,
    TrainingGapsSummary,
    TrajectoryWindow,
    WeightResult,
    build_record_race_week_brief_tool,
    llm_layer4_race_week_brief,
)
from layer4.race_week_brief import (
    _SynthesizerOutput,
    _emit_route_locales_anchor_observations,
    _render_training_substitution_section,
    _render_user_prompt,
)
from layer4.context import (
    TerrainEmphasis,
    TerrainGapRef,
    TrainingSubstitution,
    TrainingSubstitutionFlag,
    TrainingSubstitutionPayload,
)


_TODAY = date(2026, 6, 1)
_EVENT_DATE = date(2026, 6, 8)  # 7 days out


# ─── Upstream-payload fixtures ───────────────────────────────────────────────


def _layer1() -> dict[str, Any]:
    return {
        "experience_level": "advanced",
        "coaching_voice_preferences": None,
        "travel_constraint": None,
        "sleep_baseline": None,
    }


def _layer2a() -> Layer2APayload:
    disc = Layer2ADiscipline(
        discipline_id="D-trail",
        discipline_name="trail_running",
        inclusion="included",
        role="Primary",
        is_conditional=False,
        load_weight=WeightResult(value=0.5, source="system_default", system_default=0.5),
        sleep_deprivation_relevant=False,
        rationale="r",
        phase_load=PhaseLoadBands(
            base_low=5.0,
            base_high=8.0,
            build_low=6.0,
            build_high=9.0,
            peak_low=6.5,
            peak_high=9.5,
            taper_low=3.0,
            taper_high=6.0,
            default_inclusion="included",
        ),
    )
    return Layer2APayload(
        framework_sport="AR",
        etl_version_set={"layer0": "v7"},
        disciplines=[disc],
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


def _layer2b() -> Layer2BPayload:
    return Layer2BPayload(
        etl_version_set={"layer0": "v7"},
        race_terrain=[
            RaceTerrainOutput(
                terrain_id="T-trail",
                terrain_name="trail",
                pct_of_race=1.0,
                available_locally=True,
                gap=None,
            )
        ],
        terrain_gaps=[],
        coaching_flags=[],
        summary=Layer2BSummaryBlock(
            total_race_terrain_count=1,
            covered_count=1,
            gap_count=0,
            bridgeable_count=0,
            unbridgeable_count=0,
            min_adaptation_weeks_needed=0,
            worst_fidelity=1.0,
            pct_of_race_uncovered=0.0,
            any_unbridgeable=False,
            any_undefined=False,
        ),
    )


def _layer2c(locale_id: str = "home_gym") -> Layer2CPayload:
    return Layer2CPayload(
        locale_id=locale_id,
        etl_version_set={"layer0": "v7"},
        effective_pool=["E-squat"],
        discipline_coverage=[
            DisciplineCoverage(
                discipline_id="D-trail",
                discipline_name="trail_running",
                exercise_db_sport="x",
                total_exercises=1,
                tier_1_count=1,
                tier_2_count=0,
                tier_3_count=0,
                unavailable_count=0,
                coverage_pct=1.0,
            )
        ],
        exercises_resolved=[
            ResolvedExercise(
                exercise_id="E-squat",
                exercise_name="Squat",
                exercise_type="strength",
                discipline_ids=["D-trail"],
                sport_relevance_notes={"D-trail": "x"},
                priority_per_discipline={"D-trail": "Medium"},
                tier=1,
                terrain_required=[],
                contraindicated_parts=[],
                contraindicated_conditions=[],
                accommodations=[],
            )
        ],
        coaching_flags=[],
    )


def _layer2d(excluded: tuple[str, ...] = ()) -> Layer2DPayload:
    return Layer2DPayload(
        etl_version_set={"layer0": "v7"},
        excluded_exercises=[
            ExerciseRisk(
                exercise_id=ex,
                exercise_name=ex,
                discipline_ids=["D-trail"],
                verdict="exclude",
                accommodations=[],
                evidence=[],
            )
            for ex in excluded
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


def _layer2e(
    event_name: str = "Test Race",
    cho_low: float = 60.0,
    cho_high: float = 90.0,
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
                na_mg_per_hr_low=500.0,
                na_mg_per_hr_high=700.0,
                fluid_ml_per_hr_low=500.0,
                fluid_ml_per_hr_high=700.0,
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


def _layer3a() -> Layer3APayload:
    return Layer3APayload(
        user_id=42,
        as_of=datetime(2026, 5, 31, 10, 0, 0),
        model="claude-opus-4-7",
        temperature=0.0,
        prompt_hash="abc",
        latency_ms=1000,
        input_tokens=2000,
        output_tokens=500,
        etl_version_set={"layer0": "v7"},
        current_state=CurrentState(
            aerobic_capacity=Assessment(
                level="good", confidence="high", reasoning_text="r", evidence_basis=["e"]
            ),
            strength=Assessment(
                level="moderate", confidence="medium", reasoning_text="r", evidence_basis=["e"]
            ),
            weak_links=[],
            skill_assessments={},
        ),
        recent_trajectory=RecentTrajectory(
            short_term=TrajectoryWindow(
                direction="steady", reasoning_text="r", evidence_basis=["e"]
            ),
            medium_term=TrajectoryWindow(
                direction="building", reasoning_text="r", evidence_basis=["e"]
            ),
            acwr_status=ACWRStatus(per_discipline={}, combined=None),
            confidence="medium",
        ),
        data_density=DataDensity(
            connected_providers=["coros"],
            integration_data_days=28,
            recent_workouts_count=20,
            recent_sleep_count=14,
            recent_hrv_count=14,
            self_report_freshness_days=2,
            section_completeness={"C": 1.0},
        ),
        notable_observations=[],
    )


def _layer3b(
    mode: str = "event",
    event_date: date | None = None,
    race_format: str | None = "single_day",
    time_to_event_weeks: int | None = 1,
) -> Layer3BPayload:
    """D-66 amendment: Layer3BPayload now carries optional event-metadata
    fields. When mode='no-event', all 4 fields must be None."""
    if mode == "no-event":
        event_date = None
        race_format = None
        time_to_event_weeks = None
    return Layer3BPayload(
        user_id=42,
        as_of=datetime(2026, 5, 31, 10, 0, 0),
        mode=mode,  # type: ignore[arg-type]
        model="claude-opus-4-7",
        temperature=0.0,
        prompt_hash="abc",
        latency_ms=1000,
        input_tokens=2000,
        output_tokens=500,
        etl_version_set={"layer0": "v7"},
        goal_viability=GoalViability(
            viability="achievable",
            confidence="high",
            reasoning_text="r",
            evidence_basis=["e"],
            suggested_adjustments=[],
        ),
        periodization_shape=PeriodizationShape(
            mode="standard",
            start_phase="Base",
            reasoning_text="r",
            evidence_basis=["e"],
        ),
        hitl_surface=[],
        notable_observations=[],
        event_date=event_date,
        event_locale_id="L-finish" if mode == "event" else None,
        race_format=race_format,  # type: ignore[arg-type]
        time_to_event_weeks=time_to_event_weeks,
    )


def _race_event_payload(
    *,
    race_format: str = "single_day",
    event_date: date = _EVENT_DATE,
    route_locales: list[RouteLocale] | None = None,
    distance_km: Decimal | None = None,
    total_elevation_gain_m: Decimal | None = None,
    race_rules_summary: str | None = None,
    mandatory_gear_text: str | None = None,
) -> RaceEventPayload:
    return RaceEventPayload(
        race_event_id=1,
        user_id=42,
        name="Test Race 2026",
        event_date=event_date,
        race_format=race_format,  # type: ignore[arg-type]
        distance_km=distance_km,
        total_elevation_gain_m=total_elevation_gain_m,
        race_rules_summary=race_rules_summary,
        mandatory_gear_text=mandatory_gear_text,
        event_locale_id="L-finish",
        event_locale_mapbox_id="poi.test_anchor",
        is_target_event=True,
        route_locales=route_locales or [],
    )


def _route_locale(
    *,
    sequence_idx: int,
    role: str,
    name: str = "Locale",
    equipment: list[RouteLocaleEquipment] | None = None,
) -> RouteLocale:
    return RouteLocale(
        route_locale_id=sequence_idx,
        role=role,  # type: ignore[arg-type]
        sequence_idx=sequence_idx,
        name=name,
        equipment=equipment or [],
    )


def _prior_taper_session(
    *,
    session_id: str = "T-1",
    d: date | None = None,
) -> Any:
    """Build a prior-plan Taper PlanSession. Uses the same shape as the
    validator-test fixtures but inline-built for race-week-brief tests."""
    from layer4 import CardioBlock, HRTarget, PlanSession, SessionPhaseMetadata

    d = d or (_TODAY + timedelta(days=2))
    dow_map = {0: "Mon", 1: "Tue", 2: "Wed", 3: "Thu", 4: "Fri", 5: "Sat", 6: "Sun"}
    return PlanSession(
        session_id=session_id,
        plan_version_id=1,
        date=d,
        day_of_week=dow_map[d.weekday()],  # type: ignore[arg-type]
        session_index_in_day=0,
        time_of_day="morning",
        kind="cardio",
        discipline_id="D-trail",
        discipline_name="trail_running",
        locale_id="home_gym",
        locale_name="home_gym",
        duration_min=60,
        intensity_summary="easy",
        cardio_blocks=[
            CardioBlock(
                block_kind="main_set",
                duration_min=60,
                intensity_zone="Z2",
                intensity_target=HRTarget(hr_bpm_low=130, hr_bpm_high=145),
                instructions="steady aerobic",
            )
        ],
        phase_metadata=SessionPhaseMetadata(
            phase_name="Taper",
            week_in_phase=1,
            total_weeks_in_phase=2,
            intended_volume_band=(3.0, 6.0),
            intended_intensity_distribution={"Z1-Z2": 0.85, "Z3": 0.10, "Z4-Z5": 0.05},
        ),
        session_notes="x",
        coaching_intent="x",
        coaching_flags=[],
    )


# ─── Tool-output builders for the LLM stub ──────────────────────────────────


def _race_week_brief_obj(
    *,
    race_format: str = "single_day",
    event_date: date = _EVENT_DATE,
    contingencies: list[str] | None = None,
) -> dict[str, Any]:
    return {
        "days_to_event": (event_date - _TODAY).days,
        "event_name": "Test Race 2026",
        "event_date": event_date.isoformat(),
        "event_locale": "Finish line",
        "race_format": race_format,
        "goal_outcome": "Finish",
        "pre_race_logistics": "Arrive Thursday; sleep at hotel; race Saturday.",
        "kit_manifest": [
            {
                "item": "Trail shoes",
                "purpose": "Primary footwear",
                "optional": False,
                "layer0_canonical": False,
            }
        ],
        "kit_check_dates": [(event_date - timedelta(days=7)).isoformat()],
        "race_day_fueling_plan": "60-90g CHO/hr; 500-700ml fluid/hr.",
        "pre_race_meal_strategy": "Higher carb 24h pre; light breakfast 3h before.",
        "pacing_strategy_summary": "Z2 dominant; no Z4 unless emergency.",
        "contingencies": contingencies or [
            "GI distress: switch to fat-adapted backup at hour 12.",
            "Hydration mistake: replenish 500ml + electrolytes; hold pace.",
            "Mechanical: deploy field-fix kit; threshold rim contact.",
        ],
        "mental_prep_cues": [
            "Review 28-day chronic load if doubt creeps in.",
            "Settle into pacing within first 2 hours.",
        ],
    }


def _race_plan_obj(
    *,
    race_format: str = "continuous_multi_day",
    cho_low: int = 60,
    cho_high: int = 90,
    segment_offsets: list[float] | None = None,
    segment_durations: list[int] | None = None,
) -> dict[str, Any]:
    offsets = segment_offsets or [0.0, 6.0, 18.0]
    durations = segment_durations or [180, 720, 480]
    segments = [
        {
            "segment_id": f"seg-{i}",
            "segment_index": i,
            "sport": "trail_running",
            "estimated_start_offset_hr": off,
            "estimated_duration_min": dur,
            "terrain_notes": f"Segment {i} terrain.",
            "pacing_target": {"rpe_low": 5, "rpe_high": 6},
            "coaching_notes": f"Segment {i} coaching.",
        }
        for i, (off, dur) in enumerate(zip(offsets, durations))
    ]
    return {
        "race_name": "Test Race 2026",
        "race_start_datetime": datetime(2026, 6, 8, 6, 0, 0).isoformat(),
        "race_end_estimate_datetime": datetime(2026, 6, 9, 6, 0, 0).isoformat(),
        "race_format": race_format,
        "locales": ["L-start", "L-finish"],
        "segments": segments,
        "transitions": [],
        "pacing_strategy": {
            "overall_intensity_target": "Z2 dominant; no Z4 unless emergency.",
            "pacing_milestones": [],
            "rationale_text": "Conservative effort sustains 24h timeline.",
        },
        "fueling_strategy": {
            "cho_g_per_hr_low": cho_low,
            "cho_g_per_hr_high": cho_high,
            "sodium_mg_per_hr": 600,
            "fluid_ml_per_hr": 600,
            "caffeine_strategy": "100mg per 4h overnight.",
            "rationale_text": "Tier-long fueling per 2E.",
        },
        "contingencies": [
            {
                "trigger": "GI distress past hour 12",
                "action_plan": "Switch to fat-adapted backup.",
                "threshold_to_invoke": "Persists >30 min and Pepto fails.",
            },
            {
                "trigger": "Hydration mistake",
                "action_plan": "500ml + electrolytes; hold pace.",
                "threshold_to_invoke": "Urine darkens past 30 min.",
            },
            {
                "trigger": "Mechanical failure",
                "action_plan": "Deploy field-fix kit.",
                "threshold_to_invoke": "Any contact with rim.",
            },
            {
                "trigger": "Navigation error",
                "action_plan": "Backtrack to last known checkpoint.",
                "threshold_to_invoke": "Course doubt > 10 min.",
            },
            {
                "trigger": "Cumulative fatigue past expected",
                "action_plan": "Drop pace one zone; extend transitions.",
                "threshold_to_invoke": "HR drift > 8 bpm over 3h.",
            },
            {
                "trigger": "Sleep deprivation hallucinations",
                "action_plan": "30 min stationary nap.",
                "threshold_to_invoke": "SpO2 < 92% or visual artifacts.",
            },
        ],
    }


def _taper_override_obj(
    *,
    session_id: str = "T-1",
    d: date | None = None,
    coaching_flags: list[str] | None = None,
    intensity_summary: str = "easy",
    duration_min: int = 180,
) -> dict[str, Any]:
    """Default duration 180 min so a single-override-only Taper week sums to
    3.0h — clears the volume_band ±20% blocker threshold against the
    fixture's 3.0–6.0h Taper band."""
    d = d or (_TODAY + timedelta(days=2))
    dow_map = {0: "Mon", 1: "Tue", 2: "Wed", 3: "Thu", 4: "Fri", 5: "Sat", 6: "Sun"}
    return {
        "session_id_to_override": session_id,
        "date": d.isoformat(),
        "day_of_week": dow_map[d.weekday()],
        "session_index_in_day": 0,
        "time_of_day": "morning",
        "kind": "cardio",
        "discipline_id": "D-trail",
        "discipline_name": "trail_running",
        "locale_id": "home_gym",
        "locale_name": "home_gym",
        "duration_min": duration_min,
        "intensity_summary": intensity_summary,
        "session_notes": "Light easy spin to keep legs fresh.",
        "coaching_intent": "Pre-race taper drop.",
        "coaching_flags": coaching_flags or [],
        "cardio_blocks": [
            {
                "block_kind": "main_set",
                "duration_min": duration_min,
                "intensity_zone": "Z1",
                "intensity_target": {"hr_bpm_low": 110, "hr_bpm_high": 130},
                "instructions": "Easy aerobic.",
            }
        ],
    }


def _tool_args(
    *,
    race_format: str = "single_day",
    overrides: list[dict[str, Any]] | None = None,
    include_race_plan: bool | None = None,
    opportunities: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    """Build a `record_race_week_brief` tool args dict that satisfies all
    payload contracts. `include_race_plan` defaults to multi-day."""
    if include_race_plan is None:
        include_race_plan = race_format != "single_day"
    out: dict[str, Any] = {
        "taper_session_overrides": overrides or [_taper_override_obj()],
        "race_week_brief": _race_week_brief_obj(race_format=race_format),
    }
    if include_race_plan:
        out["race_plan"] = _race_plan_obj(race_format=race_format)
    if opportunities is not None:
        out["opportunities"] = opportunities
    return out


def _stub_caller(tool_args: dict[str, Any]):
    """Return a callable matching the LLMCaller protocol that always returns
    `tool_args`."""

    def _call(*_args, **_kwargs) -> _SynthesizerOutput:
        return _SynthesizerOutput(
            tool_args=tool_args,
            input_tokens=4500,
            output_tokens=2500,
            latency_ms=8500,
        )

    return _call


def _sequence_caller(outputs: list[dict[str, Any]]):
    """Return a callable that yields `outputs[i]` on the i'th call."""
    state = {"i": 0}

    def _call(*_args, **_kwargs) -> _SynthesizerOutput:
        i = state["i"]
        state["i"] = i + 1
        return _SynthesizerOutput(
            tool_args=outputs[i],
            input_tokens=4500,
            output_tokens=2500,
            latency_ms=8500,
        )

    return _call


# ─── RaceEventPayload pydantic validation ───────────────────────────────────


class TestRaceEventPayload:
    def test_happy_single_day(self):
        re = _race_event_payload(race_format="single_day")
        assert re.race_format == "single_day"
        assert re.route_locales == []
        assert re.is_target_event is True

    def test_happy_multi_day_with_route_locales(self):
        re = _race_event_payload(
            race_format="continuous_multi_day",
            route_locales=[
                _route_locale(sequence_idx=1, role="start", name="Start"),
                _route_locale(sequence_idx=2, role="aid_station", name="AS1"),
                _route_locale(sequence_idx=3, role="finish", name="Finish"),
            ],
        )
        assert len(re.route_locales) == 3
        assert re.route_locales[0].role == "start"
        assert re.route_locales[-1].role == "finish"

    def test_extra_field_rejected(self):
        with pytest.raises(ValueError):
            RaceEventPayload(
                race_event_id=1,
                user_id=42,
                name="X",
                event_date=_EVENT_DATE,
                race_format="single_day",
                event_locale_mapbox_id="poi.test_anchor",
                is_target_event=True,
                bogus=True,  # type: ignore[call-arg]
            )

    def test_json_round_trip(self):
        re = _race_event_payload(
            race_format="continuous_multi_day",
            route_locales=[
                _route_locale(sequence_idx=1, role="start", name="S"),
                _route_locale(
                    sequence_idx=5,
                    role="aid_station",
                    name="A",
                    equipment=[
                        RouteLocaleEquipment(
                            equipment_name="Water cache", quantity_text="6L"
                        )
                    ],
                ),
                _route_locale(sequence_idx=10, role="finish", name="F"),
            ],
            distance_km=Decimal("50.5"),
        )
        as_json = re.model_dump_json()
        re2 = RaceEventPayload.model_validate_json(as_json)
        assert re2.race_event_id == re.race_event_id
        assert len(re2.route_locales) == 3
        assert re2.route_locales[1].equipment[0].equipment_name == "Water cache"

    def test_duplicate_sequence_idx_rejected(self):
        with pytest.raises(ValueError, match="sequence_idx values must be unique"):
            _race_event_payload(
                race_format="continuous_multi_day",
                route_locales=[
                    _route_locale(sequence_idx=1, role="start"),
                    _route_locale(sequence_idx=1, role="finish"),
                ],
            )

    def test_out_of_order_sequence_idx_rejected(self):
        with pytest.raises(ValueError, match="sorted ascending"):
            RaceEventPayload(
                race_event_id=1,
                user_id=42,
                name="X",
                event_date=_EVENT_DATE,
                race_format="continuous_multi_day",
                event_locale_mapbox_id="poi.test_anchor",
                is_target_event=True,
                route_locales=[
                    _route_locale(sequence_idx=3, role="start"),
                    _route_locale(sequence_idx=1, role="finish"),
                ],
            )

    def test_first_role_non_start_accepted(self):
        # D-73 Phase 5.2 walkthrough hot-fix (2026-05-23) — start/finish
        # role-anchor invariant LOOSENED to silent accept. Production
        # data (Andy's PGE 2026) lacked explicit start at sequence_idx=1
        # and blocked the entire /plans/v2/new GET pipeline. Missing
        # anchors are now a content/data-quality concern for a future
        # downstream coaching-flag emission, not a payload-construction
        # error. Validator MUST accept whatever role appears first.
        re = _race_event_payload(
            race_format="continuous_multi_day",
            route_locales=[
                _route_locale(sequence_idx=1, role="aid_station"),
                _route_locale(sequence_idx=2, role="finish"),
            ],
        )
        assert re.route_locales[0].role == "aid_station"

    def test_last_role_non_finish_accepted(self):
        # Companion to test_first_role_non_start_accepted — last entry's
        # role is also no longer constrained.
        re = _race_event_payload(
            race_format="continuous_multi_day",
            route_locales=[
                _route_locale(sequence_idx=1, role="start"),
                _route_locale(sequence_idx=2, role="aid_station"),
            ],
        )
        assert re.route_locales[-1].role == "aid_station"

    def test_empty_route_locales_legal(self):
        # §4.2 invariant: empty route_locales is structurally legal;
        # validator rule kit_manifest_inputs_incomplete_no_route_locales
        # surfaces the soft-warning.
        re = _race_event_payload(race_format="continuous_multi_day", route_locales=[])
        assert re.route_locales == []

    def test_negative_distance_rejected(self):
        with pytest.raises(ValueError):
            _race_event_payload(distance_km=Decimal("-1"))


class TestEventLocaleMapboxIdRequired:
    """D-73 Phase 5.2 Bucket C (i) — RaceEventPayload requires
    `event_locale_mapbox_id` non-null on every construction. Defense-in-depth
    backstop for the route-layer flash + redirect; catches any non-route
    writer (admin scripts, integration tests, future API surfaces) that
    would construct an un-anchored payload."""

    def test_missing_mapbox_id_raises(self):
        with pytest.raises(ValueError, match="event_locale_mapbox_id is required"):
            RaceEventPayload(
                race_event_id=1,
                user_id=42,
                name="X",
                event_date=_EVENT_DATE,
                race_format="single_day",
                is_target_event=True,
            )

    def test_explicit_none_mapbox_id_raises(self):
        with pytest.raises(ValueError, match="event_locale_mapbox_id is required"):
            RaceEventPayload(
                race_event_id=1,
                user_id=42,
                name="X",
                event_date=_EVENT_DATE,
                race_format="single_day",
                event_locale_mapbox_id=None,
                is_target_event=True,
            )

    def test_present_mapbox_id_accepted(self):
        re = RaceEventPayload(
            race_event_id=1,
            user_id=42,
            name="X",
            event_date=_EVENT_DATE,
            race_format="single_day",
            event_locale_mapbox_id="poi.nerstrand_finish",
            is_target_event=True,
        )
        assert re.event_locale_mapbox_id == "poi.nerstrand_finish"

    def test_validator_fires_even_when_legacy_slug_present(self):
        # Legacy event_locale_id slug is NOT a substitute for the Mapbox
        # anchor — the legacy column stays nullable for pre-walkthrough rows
        # but new constructions still require mapbox_id. Pins the contract:
        # athletes must re-anchor legacy rows via the picker before saves.
        with pytest.raises(ValueError, match="event_locale_mapbox_id is required"):
            RaceEventPayload(
                race_event_id=1,
                user_id=42,
                name="X",
                event_date=_EVENT_DATE,
                race_format="single_day",
                event_locale_id="legacy_home",
                is_target_event=True,
            )

    def test_validator_applies_to_non_target_races_too(self):
        # D1 ratified all-races scope (not target-only). Calendar-placeholder
        # races (is_target_event=False) also require the Mapbox anchor at
        # write time; this keeps the data contract uniform across the table
        # and the route enforcement uniform across the form surfaces.
        with pytest.raises(ValueError, match="event_locale_mapbox_id is required"):
            RaceEventPayload(
                race_event_id=2,
                user_id=42,
                name="Calendar placeholder race",
                event_date=_EVENT_DATE,
                race_format="single_day",
                is_target_event=False,
            )


# ─── Tool schema ─────────────────────────────────────────────────────────────


class TestToolSchema:
    def test_tool_name_and_top_level_shape(self):
        tool = build_record_race_week_brief_tool()
        assert tool["name"] == "record_race_week_brief"
        assert tool["input_schema"]["type"] == "object"
        assert tool["input_schema"]["additionalProperties"] is False
        assert tool["input_schema"]["required"] == [
            "taper_session_overrides",
            "race_week_brief",
        ]

    def test_taper_overrides_maxitems_42(self):
        tool = build_record_race_week_brief_tool()
        props = tool["input_schema"]["properties"]
        assert props["taper_session_overrides"]["maxItems"] == 42

    def test_taper_override_coaching_flags_closed_enum(self):
        tool = build_record_race_week_brief_tool()
        sess_schema = tool["input_schema"]["properties"]["taper_session_overrides"]["items"]
        cf = sess_schema["properties"]["coaching_flags"]
        assert cf["items"]["enum"] == [
            "intensity_modulated",
            "discipline_specific_intensity",
        ]

    def test_race_week_brief_required_fields(self):
        tool = build_record_race_week_brief_tool()
        rwb = tool["input_schema"]["properties"]["race_week_brief"]
        for field in (
            "days_to_event",
            "event_name",
            "event_date",
            "race_format",
            "kit_manifest",
            "kit_check_dates",
            "contingencies",
            "mental_prep_cues",
        ):
            assert field in rwb["required"], f"{field} missing from required"

    def test_kit_manifest_layer0_canonical_present(self):
        tool = build_record_race_week_brief_tool()
        rwb = tool["input_schema"]["properties"]["race_week_brief"]
        kit = rwb["properties"]["kit_manifest"]["items"]
        assert "layer0_canonical" in kit["properties"]

    def test_race_plan_nullable_for_single_day(self):
        tool = build_record_race_week_brief_tool()
        rp = tool["input_schema"]["properties"]["race_plan"]
        assert rp["type"] == ["object", "null"]

    def test_pacing_target_typed_intensity_target_union(self):
        tool = build_record_race_week_brief_tool()
        rp = tool["input_schema"]["properties"]["race_plan"]
        seg = rp["properties"]["segments"]["items"]
        pacing = seg["properties"]["pacing_target"]
        # D1 amendment 2026-05-17: typed IntensityTarget union (9 shapes).
        assert "oneOf" in pacing
        assert len(pacing["oneOf"]) == 9


# ─── §4.5 input validation ──────────────────────────────────────────────────


class TestInputValidation:
    def _kwargs(self):
        """Common kwargs for valid invocation."""
        return {
            "user_id": 42,
            "layer1_payload": _layer1(),
            "layer2a_payload": _layer2a(),
            "layer2b_payload": _layer2b(),
            "layer2c_payloads": {"home_gym": _layer2c()},
            "layer2d_payload": _layer2d(),
            "layer2e_payload": _layer2e(),
            "layer3a_payload": _layer3a(),
            "layer3b_payload": _layer3b(event_date=_EVENT_DATE),
            "race_event_payload": _race_event_payload(),
            "prior_plan_session_window": [_prior_taper_session()],
            "plan_version_id": 7,
            "etl_version_set": {"layer0": "v7"},
            "today": _TODAY,
            "llm_caller": _stub_caller(_tool_args()),
        }

    def test_race_event_payload_missing_raises(self):
        kwargs = self._kwargs()
        kwargs["race_event_payload"] = None  # type: ignore[assignment]
        with pytest.raises(Layer4InputError) as exc:
            llm_layer4_race_week_brief(**kwargs)
        assert exc.value.code == "race_event_payload_missing"

    def test_race_week_brief_requires_event_mode_raises(self):
        kwargs = self._kwargs()
        kwargs["layer3b_payload"] = _layer3b(mode="no-event")
        with pytest.raises(Layer4InputError) as exc:
            llm_layer4_race_week_brief(**kwargs)
        assert exc.value.code == "race_week_brief_requires_event_mode"

    def test_event_date_in_past_raises(self):
        past = _TODAY - timedelta(days=1)
        kwargs = self._kwargs()
        kwargs["race_event_payload"] = _race_event_payload(event_date=past)
        kwargs["layer3b_payload"] = _layer3b(event_date=past)
        with pytest.raises(Layer4InputError) as exc:
            llm_layer4_race_week_brief(**kwargs)
        assert exc.value.code == "event_date_in_past"

    def test_race_week_brief_too_early_raises(self):
        far = _TODAY + timedelta(days=30)
        kwargs = self._kwargs()
        kwargs["race_event_payload"] = _race_event_payload(event_date=far)
        kwargs["layer3b_payload"] = _layer3b(event_date=far)
        with pytest.raises(Layer4InputError) as exc:
            llm_layer4_race_week_brief(**kwargs)
        assert exc.value.code == "race_week_brief_too_early"

    def test_layer2e_payload_missing_raises(self):
        kwargs = self._kwargs()
        kwargs["layer2e_payload"] = None  # type: ignore[assignment]
        with pytest.raises(Layer4InputError) as exc:
            llm_layer4_race_week_brief(**kwargs)
        assert exc.value.code == "layer2e_payload_missing"

    def test_race_event_date_mismatch_3b_raises(self):
        # 3B says event_date is +5 days; race_event_payload says +7 days
        mismatch = _TODAY + timedelta(days=5)
        kwargs = self._kwargs()
        kwargs["layer3b_payload"] = _layer3b(event_date=mismatch)
        with pytest.raises(Layer4InputError) as exc:
            llm_layer4_race_week_brief(**kwargs)
        assert exc.value.code == "race_event_date_mismatch_3b"

    def test_race_event_date_mismatch_3b_skipped_when_3b_event_date_none(self):
        # Backwards compat: when Layer3BPayload.event_date is None (legacy 3B
        # path or pre-D-66 caller), defensive consistency check skips.
        kwargs = self._kwargs()
        kwargs["layer3b_payload"] = _layer3b(event_date=None)
        # Should not raise — happy path with stub caller
        payload = llm_layer4_race_week_brief(**kwargs)
        assert payload.mode == "race_week_brief"


# ─── Entry-point happy path ─────────────────────────────────────────────────


class TestHappyPath:
    def _kwargs(self, **overrides):
        base = {
            "user_id": 42,
            "layer1_payload": _layer1(),
            "layer2a_payload": _layer2a(),
            "layer2b_payload": _layer2b(),
            "layer2c_payloads": {"home_gym": _layer2c()},
            "layer2d_payload": _layer2d(),
            "layer2e_payload": _layer2e(),
            "layer3a_payload": _layer3a(),
            "layer3b_payload": _layer3b(event_date=_EVENT_DATE),
            "race_event_payload": _race_event_payload(),
            "prior_plan_session_window": [_prior_taper_session()],
            "plan_version_id": 7,
            "etl_version_set": {"layer0": "v7"},
            "today": _TODAY,
            "llm_caller": _stub_caller(_tool_args()),
        }
        base.update(overrides)
        return base

    def test_single_day_race_plan_none(self):
        payload = llm_layer4_race_week_brief(**self._kwargs())
        assert payload.race_plan is None
        assert payload.race_week_brief is not None
        assert payload.race_week_brief.race_format == "single_day"

    def test_multi_day_race_plan_populated(self):
        kwargs = self._kwargs()
        kwargs["race_event_payload"] = _race_event_payload(
            race_format="continuous_multi_day",
            route_locales=[
                _route_locale(
                    sequence_idx=1,
                    role="start",
                    name="Start",
                    equipment=[RouteLocaleEquipment(equipment_name="Headlamp")],
                ),
                _route_locale(sequence_idx=2, role="finish", name="Finish"),
            ],
        )
        kwargs["layer3b_payload"] = _layer3b(
            event_date=_EVENT_DATE, race_format="continuous_multi_day"
        )
        kwargs["llm_caller"] = _stub_caller(_tool_args(race_format="continuous_multi_day"))
        payload = llm_layer4_race_week_brief(**kwargs)
        assert payload.race_plan is not None
        assert payload.race_plan.race_format == "continuous_multi_day"
        assert len(payload.race_plan.segments) == 3

    def test_session_overrides_returned(self):
        payload = llm_layer4_race_week_brief(**self._kwargs())
        # Merged Taper-week view: prior session(s) + overrides, deduped by
        # session_id. Single fixture prior session is overridden → 1 session.
        assert len(payload.sessions) == 1
        assert payload.sessions[0].session_id == "T-1"
        # Override duration (180 min default) replaces the prior 60 min.
        assert payload.sessions[0].duration_min == 180

    def test_phase_metadata_passed_through_from_prior(self):
        """§7.12 C2 amendment: race_week_brief preserves Taper-phase
        metadata verbatim from the prior plan."""
        payload = llm_layer4_race_week_brief(**self._kwargs())
        s = payload.sessions[0]
        assert s.phase_metadata is not None
        assert s.phase_metadata.phase_name == "Taper"

    def test_scope_dates_propagated(self):
        payload = llm_layer4_race_week_brief(**self._kwargs())
        # Sessions on _TODAY+2; event_date on _TODAY+7
        assert payload.scope_start_date == _TODAY + timedelta(days=2)
        assert payload.scope_end_date == _EVENT_DATE

    def test_model_and_temperature_recorded(self):
        payload = llm_layer4_race_week_brief(
            **self._kwargs(model="claude-sonnet-4-6", temperature=0.25)
        )
        assert payload.model_synthesizer == "claude-sonnet-4-6"
        assert payload.temperature == 0.25

    def test_telemetry_aggregated(self):
        payload = llm_layer4_race_week_brief(**self._kwargs())
        assert payload.input_tokens_total == 4500
        assert payload.output_tokens_total == 2500
        assert payload.latency_ms_total == 8500
        assert payload.llm_call_count == 1


# ─── Observation emission ───────────────────────────────────────────────────


class TestObservationEmission:
    def _kwargs(self):
        return {
            "user_id": 42,
            "layer1_payload": _layer1(),
            "layer2a_payload": _layer2a(),
            "layer2b_payload": _layer2b(),
            "layer2c_payloads": {"home_gym": _layer2c()},
            "layer2d_payload": _layer2d(),
            "layer2e_payload": _layer2e(),
            "layer3a_payload": _layer3a(),
            "layer3b_payload": _layer3b(event_date=_EVENT_DATE),
            "race_event_payload": _race_event_payload(),
            "prior_plan_session_window": [_prior_taper_session()],
            "plan_version_id": 7,
            "etl_version_set": {"layer0": "v7"},
            "today": _TODAY,
        }

    def test_intensity_modulated_flag_emits_observation(self):
        kwargs = self._kwargs()
        kwargs["llm_caller"] = _stub_caller(
            _tool_args(
                overrides=[_taper_override_obj(coaching_flags=["intensity_modulated"])]
            )
        )
        payload = llm_layer4_race_week_brief(**kwargs)
        cats = [o.category for o in payload.notable_observations]
        assert "intensity_modulated" in cats

    def test_no_intensity_modulated_flag_no_observation(self):
        kwargs = self._kwargs()
        kwargs["llm_caller"] = _stub_caller(_tool_args())
        payload = llm_layer4_race_week_brief(**kwargs)
        cats = [o.category for o in payload.notable_observations]
        assert "intensity_modulated" not in cats

    def test_opportunity_emits_observation(self):
        kwargs = self._kwargs()
        kwargs["llm_caller"] = _stub_caller(
            _tool_args(
                opportunities=[
                    {
                        "text": "Add 1 short technical-trail session before race",
                        "evidence_basis": ["trail_running specificity"],
                    }
                ]
            )
        )
        payload = llm_layer4_race_week_brief(**kwargs)
        ops = [o for o in payload.notable_observations if o.category == "opportunity"]
        assert len(ops) == 1
        assert "technical-trail" in ops[0].text

    def test_data_gap_emitted_on_no_route_locales_warning(self):
        # Multi-day with empty route_locales → kit_manifest soft-warning →
        # data_gap observation orchestrator-side
        kwargs = self._kwargs()
        kwargs["race_event_payload"] = _race_event_payload(
            race_format="continuous_multi_day", route_locales=[]
        )
        kwargs["layer3b_payload"] = _layer3b(
            event_date=_EVENT_DATE, race_format="continuous_multi_day"
        )
        kwargs["llm_caller"] = _stub_caller(_tool_args(race_format="continuous_multi_day"))
        payload = llm_layer4_race_week_brief(**kwargs)
        data_gaps = [
            o for o in payload.notable_observations if o.category == "data_gap"
        ]
        assert data_gaps
        assert "kit_manifest_inputs_incomplete" in data_gaps[0].text

    def test_route_locales_missing_start_anchor_emits_observation(self):
        # Companion to PR #131. Andy's PGE 2026 case — route_locales
        # captured with no entry at role='start'.
        kwargs = self._kwargs()
        kwargs["race_event_payload"] = _race_event_payload(
            race_format="continuous_multi_day",
            route_locales=[
                _route_locale(sequence_idx=1, role="transition_area"),
                _route_locale(sequence_idx=2, role="finish"),
            ],
        )
        kwargs["layer3b_payload"] = _layer3b(
            event_date=_EVENT_DATE, race_format="continuous_multi_day"
        )
        kwargs["llm_caller"] = _stub_caller(_tool_args(race_format="continuous_multi_day"))
        payload = llm_layer4_race_week_brief(**kwargs)
        data_gaps = [
            o for o in payload.notable_observations if o.category == "data_gap"
        ]
        anchor_gaps = [
            o for o in data_gaps if "route_locales_missing_start_anchor" in o.text
        ]
        assert len(anchor_gaps) == 1
        finish_gaps = [
            o for o in data_gaps if "route_locales_missing_finish_anchor" in o.text
        ]
        assert finish_gaps == []


# ─── Route-locales anchor observation helper (PR #131 companion) ────────────


class TestRouteLocalesAnchorObservations:
    def test_empty_route_locales_emits_nothing(self):
        # Empty list already covered by kit_manifest_inputs_incomplete_no_route_locales;
        # missing-anchor helper short-circuits.
        re = _race_event_payload(race_format="continuous_multi_day", route_locales=[])
        assert _emit_route_locales_anchor_observations(re) == []

    def test_both_anchors_present_emits_nothing(self):
        re = _race_event_payload(
            race_format="continuous_multi_day",
            route_locales=[
                _route_locale(sequence_idx=1, role="start"),
                _route_locale(sequence_idx=2, role="aid_station"),
                _route_locale(sequence_idx=3, role="finish"),
            ],
        )
        assert _emit_route_locales_anchor_observations(re) == []

    def test_start_missing_finish_present_emits_one(self):
        re = _race_event_payload(
            race_format="continuous_multi_day",
            route_locales=[
                _route_locale(sequence_idx=1, role="transition_area"),
                _route_locale(sequence_idx=2, role="finish"),
            ],
        )
        obs = _emit_route_locales_anchor_observations(re)
        assert len(obs) == 1
        assert obs[0].category == "data_gap"
        assert "route_locales_missing_start_anchor" in obs[0].text
        assert obs[0].elevates_to_hitl is False
        assert "PR #131 validator loosen 2026-05-23" in obs[0].evidence_basis

    def test_finish_missing_start_present_emits_one(self):
        re = _race_event_payload(
            race_format="continuous_multi_day",
            route_locales=[
                _route_locale(sequence_idx=1, role="start"),
                _route_locale(sequence_idx=2, role="aid_station"),
            ],
        )
        obs = _emit_route_locales_anchor_observations(re)
        assert len(obs) == 1
        assert "route_locales_missing_finish_anchor" in obs[0].text

    def test_both_anchors_missing_emits_two(self):
        re = _race_event_payload(
            race_format="continuous_multi_day",
            route_locales=[
                _route_locale(sequence_idx=1, role="aid_station"),
                _route_locale(sequence_idx=2, role="transition_area"),
            ],
        )
        obs = _emit_route_locales_anchor_observations(re)
        assert len(obs) == 2
        texts = [o.text for o in obs]
        assert any("route_locales_missing_start_anchor" in t for t in texts)
        assert any("route_locales_missing_finish_anchor" in t for t in texts)

    def test_start_anywhere_in_list_counts(self):
        # Anchor presence is by role anywhere — not by first/last position.
        # A list where start is somewhere in the middle still satisfies.
        re = _race_event_payload(
            race_format="continuous_multi_day",
            route_locales=[
                _route_locale(sequence_idx=1, role="transition_area"),
                _route_locale(sequence_idx=2, role="start"),
                _route_locale(sequence_idx=3, role="finish"),
            ],
        )
        obs = _emit_route_locales_anchor_observations(re)
        assert obs == []

    def test_observation_text_under_240_chars(self):
        # Observation.text Field(max_length=240) — the helper must trim.
        re = _race_event_payload(
            race_format="continuous_multi_day",
            route_locales=[
                _route_locale(sequence_idx=1, role="aid_station"),
                _route_locale(sequence_idx=2, role="transition_area"),
            ],
        )
        obs = _emit_route_locales_anchor_observations(re)
        for o in obs:
            assert len(o.text) <= 240


# ─── Capped retry semantics ─────────────────────────────────────────────────


class TestCappedRetry:
    def _kwargs(self):
        return {
            "user_id": 42,
            "layer1_payload": _layer1(),
            "layer2a_payload": _layer2a(),
            "layer2b_payload": _layer2b(),
            "layer2c_payloads": {"home_gym": _layer2c()},
            "layer2d_payload": _layer2d(),
            "layer2e_payload": _layer2e(),
            "layer3a_payload": _layer3a(),
            "layer3b_payload": _layer3b(event_date=_EVENT_DATE),
            "race_event_payload": _race_event_payload(
                race_format="continuous_multi_day",
                route_locales=[
                    _route_locale(
                        sequence_idx=1,
                        role="start",
                        equipment=[RouteLocaleEquipment(equipment_name="Headlamp")],
                    ),
                    _route_locale(sequence_idx=2, role="finish"),
                ],
            ),
            "prior_plan_session_window": [_prior_taper_session()],
            "plan_version_id": 7,
            "etl_version_set": {"layer0": "v7"},
            "today": _TODAY,
        }

    def test_first_pass_accept_skips_retries(self):
        kwargs = self._kwargs()
        kwargs["layer3b_payload"] = _layer3b(
            event_date=_EVENT_DATE, race_format="continuous_multi_day"
        )
        kwargs["llm_caller"] = _stub_caller(_tool_args(race_format="continuous_multi_day"))
        payload = llm_layer4_race_week_brief(**kwargs)
        assert payload.llm_call_count == 1
        assert payload.validator_results[-1].accepted is True

    def test_validator_fail_then_pass_retries_once(self):
        kwargs = self._kwargs()
        kwargs["layer3b_payload"] = _layer3b(
            event_date=_EVENT_DATE, race_format="continuous_multi_day"
        )
        # First call: race_plan.fueling_strategy cho_low=10 (outside 2E
        # band 60-90). Second call: in-band.
        bad = _tool_args(race_format="continuous_multi_day")
        bad["race_plan"]["fueling_strategy"]["cho_g_per_hr_low"] = 10
        bad["race_plan"]["fueling_strategy"]["cho_g_per_hr_high"] = 20
        good = _tool_args(race_format="continuous_multi_day")
        kwargs["llm_caller"] = _sequence_caller([bad, good])
        payload = llm_layer4_race_week_brief(**kwargs)
        assert payload.llm_call_count == 2
        assert payload.validator_results[-1].accepted is True

    def test_cap_hit_emits_best_effort_observation(self):
        kwargs = self._kwargs()
        kwargs["layer3b_payload"] = _layer3b(
            event_date=_EVENT_DATE, race_format="continuous_multi_day"
        )
        # All passes fail validator (cho outside band)
        bad = _tool_args(race_format="continuous_multi_day")
        bad["race_plan"]["fueling_strategy"]["cho_g_per_hr_low"] = 10
        bad["race_plan"]["fueling_strategy"]["cho_g_per_hr_high"] = 20
        kwargs["llm_caller"] = _sequence_caller([bad, bad, bad])
        payload = llm_layer4_race_week_brief(**kwargs)
        assert payload.llm_call_count == 3
        cats = [o.category for o in payload.notable_observations]
        assert "best_effort_plan" in cats
        # Final validator result accepted=True (best-effort with demoted)
        assert payload.validator_results[-1].accepted is True

    def test_capped_retries_zero_no_retry(self):
        kwargs = self._kwargs()
        kwargs["layer3b_payload"] = _layer3b(
            event_date=_EVENT_DATE, race_format="continuous_multi_day"
        )
        bad = _tool_args(race_format="continuous_multi_day")
        bad["race_plan"]["fueling_strategy"]["cho_g_per_hr_low"] = 10
        bad["race_plan"]["fueling_strategy"]["cho_g_per_hr_high"] = 20
        kwargs["llm_caller"] = _stub_caller(bad)
        kwargs["capped_retries"] = 0
        payload = llm_layer4_race_week_brief(**kwargs)
        assert payload.llm_call_count == 1


# ─── Schema violation ───────────────────────────────────────────────────────


class TestSchemaViolation:
    def _kwargs(self):
        return {
            "user_id": 42,
            "layer1_payload": _layer1(),
            "layer2a_payload": _layer2a(),
            "layer2b_payload": _layer2b(),
            "layer2c_payloads": {"home_gym": _layer2c()},
            "layer2d_payload": _layer2d(),
            "layer2e_payload": _layer2e(),
            "layer3a_payload": _layer3a(),
            "layer3b_payload": _layer3b(event_date=_EVENT_DATE),
            "race_event_payload": _race_event_payload(),
            "prior_plan_session_window": [_prior_taper_session()],
            "plan_version_id": 7,
            "etl_version_set": {"layer0": "v7"},
            "today": _TODAY,
        }

    def test_missing_race_week_brief_raises(self):
        kwargs = self._kwargs()
        bad = {"taper_session_overrides": [_taper_override_obj()]}
        kwargs["llm_caller"] = _sequence_caller([bad, bad, bad])
        with pytest.raises(Layer4OutputError) as exc:
            llm_layer4_race_week_brief(**kwargs)
        assert exc.value.code == "schema_violation"

    def test_multi_day_without_race_plan_raises(self):
        kwargs = self._kwargs()
        kwargs["race_event_payload"] = _race_event_payload(race_format="continuous_multi_day")
        kwargs["layer3b_payload"] = _layer3b(
            event_date=_EVENT_DATE, race_format="continuous_multi_day"
        )
        # Multi-day event but tool output has no race_plan → schema violation
        bad = _tool_args(race_format="continuous_multi_day", include_race_plan=False)
        kwargs["llm_caller"] = _sequence_caller([bad, bad, bad])
        with pytest.raises(Layer4OutputError) as exc:
            llm_layer4_race_week_brief(**kwargs)
        assert exc.value.code == "schema_violation"

    def test_override_session_id_mismatch_raises(self):
        kwargs = self._kwargs()
        # session_id_to_override doesn't match any prior session
        bad_override = _taper_override_obj(session_id="UNKNOWN-ID")
        bad = _tool_args(overrides=[bad_override])
        kwargs["llm_caller"] = _sequence_caller([bad, bad, bad])
        with pytest.raises(Layer4OutputError) as exc:
            llm_layer4_race_week_brief(**kwargs)
        assert exc.value.code == "schema_violation"


# ─── Layer4Payload composition invariants ───────────────────────────────────


class TestLayer4PayloadComposition:
    def _kwargs(self):
        return {
            "user_id": 42,
            "layer1_payload": _layer1(),
            "layer2a_payload": _layer2a(),
            "layer2b_payload": _layer2b(),
            "layer2c_payloads": {"home_gym": _layer2c()},
            "layer2d_payload": _layer2d(),
            "layer2e_payload": _layer2e(),
            "layer3a_payload": _layer3a(),
            "layer3b_payload": _layer3b(event_date=_EVENT_DATE),
            "race_event_payload": _race_event_payload(),
            "prior_plan_session_window": [_prior_taper_session()],
            "plan_version_id": 7,
            "etl_version_set": {"layer0": "v7"},
            "today": _TODAY,
            "llm_caller": _stub_caller(_tool_args()),
        }

    def test_mode_is_race_week_brief(self):
        payload = llm_layer4_race_week_brief(**self._kwargs())
        assert payload.mode == "race_week_brief"

    def test_pattern_is_b(self):
        payload = llm_layer4_race_week_brief(**self._kwargs())
        assert payload.pattern == "B"

    def test_phase_structure_and_seam_reviews_none(self):
        payload = llm_layer4_race_week_brief(**self._kwargs())
        assert payload.phase_structure is None
        assert payload.seam_reviews is None

    def test_validator_results_populated(self):
        payload = llm_layer4_race_week_brief(**self._kwargs())
        assert payload.validator_results
        assert payload.validator_results[-1].accepted is True

    def test_suggestion_id_none(self):
        payload = llm_layer4_race_week_brief(**self._kwargs())
        assert payload.suggestion_id is None

    def test_race_week_brief_non_none(self):
        payload = llm_layer4_race_week_brief(**self._kwargs())
        assert payload.race_week_brief is not None

    def test_race_plan_none_for_single_day(self):
        payload = llm_layer4_race_week_brief(**self._kwargs())
        assert payload.race_plan is None


# ─── Prompt rendering ───────────────────────────────────────────────────────


class TestPromptRendering:
    def test_race_rules_summary_rendered_verbatim(self):
        rules = "Mandatory checkpoint at TA2 by hour 18 or DQ."
        re = _race_event_payload(
            race_format="continuous_multi_day",
            race_rules_summary=rules,
            route_locales=[
                _route_locale(sequence_idx=1, role="start"),
                _route_locale(sequence_idx=2, role="finish"),
            ],
        )
        prompt = _render_user_prompt(
            layer1_payload=_layer1(),
            layer2a_payload=_layer2a(),
            layer2b_payload=_layer2b(),
            layer2c_payloads={"home_gym": _layer2c()},
            layer2d_payload=_layer2d(),
            layer2e_payload=_layer2e(),
            layer3a_payload=_layer3a(),
            layer3b_payload=_layer3b(event_date=_EVENT_DATE),
            race_event_payload=re,
            prior_plan_session_window=[_prior_taper_session()],
            days_to_event=7,
            today=_TODAY,
            retries_used=0,
            rule_failures=[],
        )
        assert rules in prompt

    def test_mandatory_gear_text_rendered_verbatim(self):
        gear = "Headlamp w/ backup batteries; emergency bivvy; full medical kit."
        re = _race_event_payload(
            race_format="continuous_multi_day",
            mandatory_gear_text=gear,
            route_locales=[
                _route_locale(sequence_idx=1, role="start"),
                _route_locale(sequence_idx=2, role="finish"),
            ],
        )
        prompt = _render_user_prompt(
            layer1_payload=_layer1(),
            layer2a_payload=_layer2a(),
            layer2b_payload=_layer2b(),
            layer2c_payloads={"home_gym": _layer2c()},
            layer2d_payload=_layer2d(),
            layer2e_payload=_layer2e(),
            layer3a_payload=_layer3a(),
            layer3b_payload=_layer3b(event_date=_EVENT_DATE),
            race_event_payload=re,
            prior_plan_session_window=[_prior_taper_session()],
            days_to_event=7,
            today=_TODAY,
            retries_used=0,
            rule_failures=[],
        )
        assert gear in prompt

    def test_route_locales_rendered_structured(self):
        re = _race_event_payload(
            race_format="continuous_multi_day",
            route_locales=[
                _route_locale(sequence_idx=1, role="start", name="Start Line"),
                _route_locale(
                    sequence_idx=2,
                    role="aid_station",
                    name="AS Lake Mary",
                    equipment=[
                        RouteLocaleEquipment(
                            equipment_name="6L water cache", quantity_text="6 liters"
                        )
                    ],
                ),
                _route_locale(sequence_idx=3, role="finish", name="Finish"),
            ],
        )
        prompt = _render_user_prompt(
            layer1_payload=_layer1(),
            layer2a_payload=_layer2a(),
            layer2b_payload=_layer2b(),
            layer2c_payloads={"home_gym": _layer2c()},
            layer2d_payload=_layer2d(),
            layer2e_payload=_layer2e(),
            layer3a_payload=_layer3a(),
            layer3b_payload=_layer3b(event_date=_EVENT_DATE),
            race_event_payload=re,
            prior_plan_session_window=[_prior_taper_session()],
            days_to_event=7,
            today=_TODAY,
            retries_used=0,
            rule_failures=[],
        )
        # D-66 amendment renders the route_locales section
        assert "Route locales (D-66 structured graph)" in prompt
        assert "Start Line" in prompt
        assert "AS Lake Mary" in prompt
        assert "6L water cache" in prompt
        # PR #131 companion: anchors-present path has NO missing-anchor note
        assert "no entry has role=" not in prompt

    def test_route_locales_missing_anchors_note_rendered(self):
        # PR #131 companion: when start + finish anchors are missing, the
        # prompt section emits an explicit "do not infer" note so the LLM
        # treats them as unknown instead of inferring from first/last
        # sequence_idx.
        re = _race_event_payload(
            race_format="continuous_multi_day",
            route_locales=[
                _route_locale(sequence_idx=1, role="aid_station", name="AS1"),
                _route_locale(sequence_idx=2, role="transition_area", name="TA1"),
            ],
        )
        prompt = _render_user_prompt(
            layer1_payload=_layer1(),
            layer2a_payload=_layer2a(),
            layer2b_payload=_layer2b(),
            layer2c_payloads={"home_gym": _layer2c()},
            layer2d_payload=_layer2d(),
            layer2e_payload=_layer2e(),
            layer3a_payload=_layer3a(),
            layer3b_payload=_layer3b(event_date=_EVENT_DATE),
            race_event_payload=re,
            prior_plan_session_window=[_prior_taper_session()],
            days_to_event=7,
            today=_TODAY,
            retries_used=0,
            rule_failures=[],
        )
        assert "role='start'" in prompt
        assert "role='finish'" in prompt
        assert "first/last sequence_idx" in prompt

    def test_route_locales_missing_start_only_note_rendered(self):
        re = _race_event_payload(
            race_format="continuous_multi_day",
            route_locales=[
                _route_locale(sequence_idx=1, role="transition_area"),
                _route_locale(sequence_idx=2, role="finish"),
            ],
        )
        prompt = _render_user_prompt(
            layer1_payload=_layer1(),
            layer2a_payload=_layer2a(),
            layer2b_payload=_layer2b(),
            layer2c_payloads={"home_gym": _layer2c()},
            layer2d_payload=_layer2d(),
            layer2e_payload=_layer2e(),
            layer3a_payload=_layer3a(),
            layer3b_payload=_layer3b(event_date=_EVENT_DATE),
            race_event_payload=re,
            prior_plan_session_window=[_prior_taper_session()],
            days_to_event=7,
            today=_TODAY,
            retries_used=0,
            rule_failures=[],
        )
        assert "role='start'" in prompt
        assert "role='finish'" not in prompt

    def test_retry_context_only_on_retries_used_gt_zero(self):
        from layer4 import RuleFailure

        re = _race_event_payload()
        prompt0 = _render_user_prompt(
            layer1_payload=_layer1(),
            layer2a_payload=_layer2a(),
            layer2b_payload=_layer2b(),
            layer2c_payloads={"home_gym": _layer2c()},
            layer2d_payload=_layer2d(),
            layer2e_payload=_layer2e(),
            layer3a_payload=_layer3a(),
            layer3b_payload=_layer3b(event_date=_EVENT_DATE),
            race_event_payload=re,
            prior_plan_session_window=[_prior_taper_session()],
            days_to_event=7,
            today=_TODAY,
            retries_used=0,
            rule_failures=[],
        )
        assert "Validator feedback" not in prompt0
        rf = RuleFailure(
            rule_name="taper_phase_intent_violation_S-1",
            phase_name="Taper",
            severity="blocker",
            detail="hard intensity on event-2",
            affected_session_ids=["S-1"],
        )
        prompt1 = _render_user_prompt(
            layer1_payload=_layer1(),
            layer2a_payload=_layer2a(),
            layer2b_payload=_layer2b(),
            layer2c_payloads={"home_gym": _layer2c()},
            layer2d_payload=_layer2d(),
            layer2e_payload=_layer2e(),
            layer3a_payload=_layer3a(),
            layer3b_payload=_layer3b(event_date=_EVENT_DATE),
            race_event_payload=re,
            prior_plan_session_window=[_prior_taper_session()],
            days_to_event=7,
            today=_TODAY,
            retries_used=1,
            rule_failures=[rf],
        )
        assert "Validator feedback" in prompt1
        assert "taper_phase_intent_violation_S-1" in prompt1


# ─── Layer3BPayload event-metadata schema (D-66 amendment) ──────────────────


class TestLayer3BPayloadEventMetadata:
    def test_event_mode_allows_event_date(self):
        b = _layer3b(event_date=_EVENT_DATE, race_format="continuous_multi_day")
        assert b.event_date == _EVENT_DATE
        assert b.race_format == "continuous_multi_day"

    def test_no_event_mode_rejects_event_date(self):
        with pytest.raises(ValueError, match="mode=='no-event'"):
            Layer3BPayload(
                user_id=42,
                as_of=datetime(2026, 5, 31, 10, 0, 0),
                mode="no-event",
                model="m",
                temperature=0.0,
                prompt_hash="x",
                latency_ms=0,
                input_tokens=0,
                output_tokens=0,
                etl_version_set={"layer0": "v7"},
                goal_viability=GoalViability(
                    viability="achievable",
                    confidence="high",
                    reasoning_text="r",
                    evidence_basis=["e"],
                    suggested_adjustments=[],
                ),
                periodization_shape=PeriodizationShape(
                    mode="standard",
                    start_phase="Base",
                    reasoning_text="r",
                    evidence_basis=["e"],
                ),
                hitl_surface=[],
                notable_observations=[],
                event_date=_EVENT_DATE,
            )


# ─── Best-fit re-model Slice 5 — training-substitution prompt section ─────────


def _substitution_payload() -> TrainingSubstitutionPayload:
    return TrainingSubstitutionPayload(
        etl_version_set={"0A": "v7", "0B": "v7", "0C": "v7"},
        recommendations=[
            TrainingSubstitution(
                discipline_id="D-009",
                discipline_name="Packrafting",
                race_craft="Packrafting",
                candidate_training_crafts=["canoe", "kayak"],
                terrain_emphasis=[
                    TerrainEmphasis(
                        race_terrain_id="TRN-river",
                        terrain_name="River",
                        pct=80.0,
                        proxy_terrain_id="TRN-river",
                        proxy_terrain_name="River",
                        fidelity=1.0,
                        gap_severity="none",
                        emphasis_score=80.0,
                    ),
                ],
                untrainable_terrain=[
                    TerrainGapRef(
                        race_terrain_id="TRN-ww",
                        terrain_name="Whitewater",
                        pct=10.0,
                        gap_severity="unbridgeable",
                        reason="unbridgeable",
                    ),
                ],
            )
        ],
        coaching_flags=[
            TrainingSubstitutionFlag(
                flag_type="terrain_untrainable",
                discipline_id="D-009",
                discipline_name="Packrafting",
                race_terrain_id="TRN-ww",
                message="10% of the Packrafting leg has no local proxy — compensate.",
            )
        ],
    )


class TestTrainingSubstitutionSection:
    def test_section_threads_into_user_prompt(self):
        prompt = _render_user_prompt(
            layer1_payload=_layer1(),
            layer2a_payload=_layer2a(),
            layer2b_payload=_layer2b(),
            layer2c_payloads={"home_gym": _layer2c()},
            layer2d_payload=_layer2d(),
            layer2e_payload=_layer2e(),
            layer3a_payload=_layer3a(),
            layer3b_payload=_layer3b(event_date=_EVENT_DATE),
            race_event_payload=_race_event_payload(),
            prior_plan_session_window=[_prior_taper_session()],
            days_to_event=7,
            today=_TODAY,
            retries_used=0,
            rule_failures=[],
            training_substitution_payload=_substitution_payload(),
        )
        assert "Best-fit training substitution" in prompt
        assert "D-009 Packrafting" in prompt
        assert "candidate training crafts: canoe, kayak" in prompt

    def test_section_absent_when_payload_none(self):
        prompt = _render_user_prompt(
            layer1_payload=_layer1(),
            layer2a_payload=_layer2a(),
            layer2b_payload=_layer2b(),
            layer2c_payloads={"home_gym": _layer2c()},
            layer2d_payload=_layer2d(),
            layer2e_payload=_layer2e(),
            layer3a_payload=_layer3a(),
            layer3b_payload=_layer3b(event_date=_EVENT_DATE),
            race_event_payload=_race_event_payload(),
            prior_plan_session_window=[_prior_taper_session()],
            days_to_event=7,
            today=_TODAY,
            retries_used=0,
            rule_failures=[],
        )
        assert "Best-fit training substitution" not in prompt

    def test_renders_emphasis_untrainable_and_flags(self):
        lines = _render_training_substitution_section(_substitution_payload())
        text = "\n".join(lines)
        assert "Terrain emphasis: River (80%, proxy River @ fidelity 1.00)" in text
        assert "Untrainable terrain: Whitewater (10%, unbridgeable)" in text
        assert "`terrain_untrainable` (D-009 / TRN-ww)" in text

    def test_empty_payload_renders_explanatory_line(self):
        payload = TrainingSubstitutionPayload(
            etl_version_set={"0A": "v7"}, recommendations=[], coaching_flags=[]
        )
        lines = _render_training_substitution_section(payload)
        text = "\n".join(lines)
        assert "No training-substitution recommendations" in text

    def test_no_crafts_renders_none_logged(self):
        payload = TrainingSubstitutionPayload(
            etl_version_set={"0A": "v7"},
            recommendations=[
                TrainingSubstitution(
                    discipline_id="D-009",
                    discipline_name="Packrafting",
                    race_craft="Packrafting",
                    candidate_training_crafts=[],
                )
            ],
            coaching_flags=[],
        )
        text = "\n".join(_render_training_substitution_section(payload))
        assert "candidate training crafts: (none logged)" in text
