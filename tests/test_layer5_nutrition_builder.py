"""Tests for `layer5.builder` — deterministic per-day + race-day nutrition.

Covers the ``load_redistribution_v1`` energy model:
- weekly per-day kcal reconcile to the 2E phase baseline (no floor case)
- rest days land near the resting floor, below training days
- carbohydrate absorbs the day-to-day swing; protein + fat held steady
- resting floor clamps rest-day intake on very high-volume weeks
- determinism (identical inputs → identical artifact)
- standalone race-day fueling projection + per-day race flagging
- empty-plan safety
"""

from __future__ import annotations

from datetime import date, datetime, timedelta, timezone

from layer4.context import (
    DailyNutritionBaseline,
    DailyPhaseTargets,
    MacroTargets,
    RaceDayFueling,
)
from layer4.payload import (
    CardioBlock,
    HRTarget,
    PlanSession,
    SessionPhaseMetadata,
)
from layer5 import build_plan_nutrition, build_race_day_fueling_plan

_DOW = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]
BW = 70.0


# ─── factories ───────────────────────────────────────────────────────────────


def _dow(d: date) -> str:
    return _DOW[d.weekday()]


def _macros(
    *,
    protein_g_per_kg: float = 1.7,
    fat_g: int = 70,
    fat_floor_constrained: bool = False,
) -> MacroTargets:
    protein_g = round(protein_g_per_kg * BW)
    return MacroTargets(
        cho_g=420,
        cho_g_per_kg=6.0,
        cho_kcal=420 * 4,
        protein_g=protein_g,
        protein_g_per_kg=protein_g_per_kg,
        protein_kcal=protein_g * 4,
        fat_g=fat_g,
        fat_kcal=fat_g * 9,
        fat_floor_constrained=fat_floor_constrained,
    )


def _phase_targets(daily_kcal: int) -> DailyPhaseTargets:
    return DailyPhaseTargets(
        activity_multiplier=1.7,
        activity_multiplier_source={"phase": "Base", "volume_tier_index": 1},
        daily_calorie_target_kcal=daily_kcal,
        macros=_macros(),
    )

def _baseline(daily_kcal: int = 3000) -> DailyNutritionBaseline:
    return DailyNutritionBaseline(
        per_phase={
            p: _phase_targets(daily_kcal) for p in ("Base", "Build", "Peak", "Taper")
        }
    )


def _pm(phase: str = "Base", week: int = 1) -> SessionPhaseMetadata:
    return SessionPhaseMetadata(
        phase_name=phase,
        week_in_phase=week,
        total_weeks_in_phase=4,
        intended_volume_band=(8.0, 10.0),
        intended_intensity_distribution={"Z2": 0.8, "Z4": 0.2},
    )


def _block(duration_min: int, zone: str = "Z2") -> CardioBlock:
    return CardioBlock(
        block_kind="main_set",
        duration_min=duration_min,
        intensity_zone=zone,
        intensity_target=HRTarget(hr_bpm_low=120, hr_bpm_high=145),
        instructions="steady",
    )


def _cardio(
    d: date,
    *,
    duration_min: int = 90,
    zone: str = "Z2",
    phase: str = "Base",
    week: int = 1,
    sid: str | None = None,
) -> PlanSession:
    return PlanSession(
        session_id=sid or f"c-{d.isoformat()}",
        plan_version_id=1,
        date=d,
        day_of_week=_dow(d),
        session_index_in_day=0,
        time_of_day="morning",
        kind="cardio",
        discipline_id="run",
        discipline_name="Running",
        duration_min=duration_min,
        intensity_summary="moderate",
        cardio_blocks=[_block(duration_min, zone)],
        phase_metadata=_pm(phase, week),
        session_notes="",
        coaching_intent="",
        coaching_flags=[],
    )


def _rest(d: date, *, phase: str = "Base", week: int = 1) -> PlanSession:
    return PlanSession(
        session_id=f"r-{d.isoformat()}",
        plan_version_id=1,
        date=d,
        day_of_week=_dow(d),
        session_index_in_day=0,
        time_of_day="unspecified",
        kind="rest",
        duration_min=0,
        intensity_summary="rest",
        rest_reason="planned_recovery",
        phase_metadata=_pm(phase, week),
        session_notes="",
        coaching_intent="",
        coaching_flags=[],
    )


def _moderate_week(monday: date) -> list[PlanSession]:
    """5×75min Z2, 1×120min Z3 (Sat), rest Sun — does not hit the RMR floor."""
    sessions = []
    for i in range(5):
        sessions.append(_cardio(monday + timedelta(days=i), duration_min=75, zone="Z2"))
    sessions.append(_cardio(monday + timedelta(days=5), duration_min=120, zone="Z3"))
    sessions.append(_rest(monday + timedelta(days=6)))
    return sessions


# ─── tests ───────────────────────────────────────────────────────────────────


def test_weekly_sum_reconciles_to_phase_baseline():
    monday = date(2026, 6, 1)  # Monday
    sessions = _moderate_week(monday)
    out = build_plan_nutrition(
        plan_version_id=1,
        sessions=sessions,
        baseline=_baseline(3000),
        bmr_kcal=1600.0,
        body_weight_kg=BW,
    )
    assert len(out.days) == 7
    assert len(out.week_reconciliation) == 1
    wr = out.week_reconciliation[0]
    assert wr.non_training_floor_applied is False
    assert wr.weekly_baseline_kcal == 7 * 3000
    # Σ(per-day) reconciles to the weekly baseline within per-day rounding.
    assert abs(wr.weekly_assigned_kcal - wr.weekly_baseline_kcal) <= 13 * wr.days
    assert sum(d.total_kcal for d in out.days) == wr.weekly_assigned_kcal


def test_rest_day_below_training_day_and_near_floor():
    monday = date(2026, 6, 1)
    sessions = _moderate_week(monday)
    out = build_plan_nutrition(
        plan_version_id=1,
        sessions=sessions,
        baseline=_baseline(3000),
        bmr_kcal=1600.0,
        body_weight_kg=BW,
    )
    by_day = {d.date: d for d in out.days}
    rest_day = by_day[date(2026, 6, 7)]   # Sunday rest
    hard_day = by_day[date(2026, 6, 6)]   # Saturday Z3 120min
    assert rest_day.is_rest_day is True
    assert rest_day.exercise_kcal == 0
    assert rest_day.load_tier == "rest"
    assert hard_day.exercise_kcal > 0
    assert rest_day.total_kcal < hard_day.total_kcal


def test_carbohydrate_absorbs_swing_protein_and_fat_steady():
    monday = date(2026, 6, 1)
    sessions = _moderate_week(monday)
    out = build_plan_nutrition(
        plan_version_id=1,
        sessions=sessions,
        baseline=_baseline(3000),
        bmr_kcal=1600.0,
        body_weight_kg=BW,
    )
    by_day = {d.date: d for d in out.days}
    rest_day = by_day[date(2026, 6, 7)]
    hard_day = by_day[date(2026, 6, 6)]
    # CHO tracks load …
    assert hard_day.macros.cho_g > rest_day.macros.cho_g
    # … while protein and fat are held steady across days.
    assert hard_day.macros.protein_g == rest_day.macros.protein_g
    assert hard_day.macros.fat_g == rest_day.macros.fat_g
    # macro kcal stay internally consistent.
    for day in out.days:
        m = day.macros
        assert m.cho_kcal == m.cho_g * 4
        assert m.protein_kcal == m.protein_g * 4
        assert m.fat_kcal == m.fat_g * 9


def test_resting_floor_clamps_huge_volume_week():
    monday = date(2026, 6, 1)
    sessions = []
    for i in range(6):
        sessions.append(
            _cardio(monday + timedelta(days=i), duration_min=180, zone="Z4")
        )
    sessions.append(_rest(monday + timedelta(days=6)))

    bmr = 1700.0
    out = build_plan_nutrition(
        plan_version_id=1,
        sessions=sessions,
        baseline=_baseline(3000),
        bmr_kcal=bmr,
        body_weight_kg=BW,
    )
    wr = out.week_reconciliation[0]
    assert wr.non_training_floor_applied is True
    # Floor pushes the weekly total above the flat baseline (more is needed).
    assert wr.weekly_assigned_kcal > wr.weekly_baseline_kcal
    # Rest day sits at the rounded resting floor (BMR × 1.2).
    rest_day = next(d for d in out.days if d.is_rest_day)
    floor = round((bmr * 1.2) / 25) * 25
    assert rest_day.total_kcal == floor
    assert rest_day.non_training_floor_applied is True


def test_determinism():
    monday = date(2026, 6, 1)
    sessions = _moderate_week(monday)
    fixed = datetime(2026, 6, 8, 12, 0, tzinfo=timezone.utc)
    kwargs = dict(
        plan_version_id=1,
        sessions=sessions,
        baseline=_baseline(3000),
        bmr_kcal=1600.0,
        body_weight_kg=BW,
        generated_at=fixed,
    )
    a = build_plan_nutrition(**kwargs)
    b = build_plan_nutrition(**kwargs)
    assert a.model_dump() == b.model_dump()


def test_race_day_fueling_standalone_and_flagging():
    race_date = date(2026, 6, 6)
    rdf = RaceDayFueling(
        event_id="e1",
        event_name="Spring 100",
        duration_tier="tier_long",
        cho_g_per_hr_low=60.0,
        cho_g_per_hr_high=90.0,
        na_mg_per_hr_low=400.0,
        na_mg_per_hr_high=700.0,
        fluid_ml_per_hr_low=450.0,
        fluid_ml_per_hr_high=750.0,
        sport_modifier_applied=1.0,
        salt_tolerance_modifier_applied=1.0,
        heat_acclim_modifier_applied=1.0,
        recommended_formats=["gel", "drink_mix"],
        blocked_formats=["solid_bar"],
        sleep_dep_overlay_applies=False,
        notes=["practise in training"],
    )

    # Standalone projection (used by the future race-day plan generator).
    plans = build_race_day_fueling_plan([rdf], event_dates={"e1": race_date})
    assert len(plans) == 1
    p = plans[0]
    assert p.event_id == "e1"
    assert p.event_date == race_date
    assert p.cho_g_per_hr == (60.0, 90.0)
    assert p.na_mg_per_hr == (400.0, 700.0)
    assert p.fluid_ml_per_hr == (450.0, 750.0)
    assert p.recommended_formats == ["gel", "drink_mix"]

    # End-to-end: the race date is flagged on its per-day record.
    out = build_plan_nutrition(
        plan_version_id=1,
        sessions=[_cardio(race_date, duration_min=120, zone="Z3")],
        baseline=_baseline(3000),
        bmr_kcal=1600.0,
        body_weight_kg=BW,
        race_day_fueling=[rdf],
        event_dates={"e1": race_date},
    )
    day = out.days[0]
    assert day.is_race_day is True
    assert day.race_fueling_event_ids == ["e1"]
    assert len(out.race_fueling) == 1


def test_empty_plan_is_safe():
    out = build_plan_nutrition(
        plan_version_id=7,
        sessions=[],
        baseline=_baseline(3000),
        bmr_kcal=1600.0,
        body_weight_kg=BW,
    )
    assert out.days == []
    assert out.week_reconciliation == []
    assert out.plan_version_id == 7
