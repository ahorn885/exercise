"""Render-coverage for the Layer 5A nutrition blocks in
`templates/plan_create/view.html`.

The route tests call functions directly (no template render), so a template
data-binding bug (a wrong attribute, a bad filter, the inline race-fueling
loop) would otherwise reach production unseen. This renders the *real*
`view.html` against real `PlanNutrition` / `PlanSession` objects, swapping in a
stub `base.html` and stub `url_for` / `csrf_token` so no Flask app/DB is needed.
"""

from __future__ import annotations

from datetime import date, datetime, timezone

from jinja2 import ChoiceLoader, DictLoader, Environment, FileSystemLoader

from layer4.context import (
    DailyNutritionBaseline,
    DailyPhaseTargets,
    MacroTargets,
    RaceDayFueling,
)
from layer4.payload import CardioBlock, HRTarget, PlanSession, SessionPhaseMetadata
from layer5 import build_plan_nutrition

RACE_DATE = date(2026, 6, 6)
BW = 70.0


def _env() -> Environment:
    env = Environment(
        loader=ChoiceLoader(
            [
                # Minimal base so `{% extends 'base.html' %}` resolves to just
                # the content block — we only care about view.html's body.
                DictLoader(
                    {
                        "base.html": (
                            "{% block title %}{% endblock %}"
                            "{% block crumbs %}{% endblock %}"
                            "{% block content %}{% endblock %}"
                        )
                    }
                ),
                FileSystemLoader("templates"),
            ]
        )
    )
    env.globals["url_for"] = lambda *a, **k: "#"
    env.globals["csrf_token"] = lambda: "test-token"
    return env


def _macros() -> MacroTargets:
    return MacroTargets(
        cho_g=420, cho_g_per_kg=6.0, cho_kcal=420 * 4,
        protein_g=119, protein_g_per_kg=1.7, protein_kcal=119 * 4,
        fat_g=70, fat_kcal=70 * 9, fat_floor_constrained=False,
    )


def _baseline() -> DailyNutritionBaseline:
    targets = DailyPhaseTargets(
        activity_multiplier=1.7,
        activity_multiplier_source={"phase": "Base"},
        daily_calorie_target_kcal=3000,
        macros=_macros(),
    )
    return DailyNutritionBaseline(per_phase={"Base": targets})


def _session() -> PlanSession:
    return PlanSession(
        session_id="c-1", plan_version_id=1, date=RACE_DATE, day_of_week="Sat",
        session_index_in_day=0, time_of_day="morning", kind="cardio",
        discipline_id="run", discipline_name="Running", duration_min=120,
        intensity_summary="moderate",
        cardio_blocks=[
            CardioBlock(
                block_kind="main_set", duration_min=120, intensity_zone="Z3",
                intensity_target=HRTarget(hr_bpm_low=130, hr_bpm_high=150),
                instructions="steady",
            )
        ],
        phase_metadata=SessionPhaseMetadata(
            phase_name="Base", week_in_phase=1, total_weeks_in_phase=4,
            intended_volume_band=(8.0, 10.0),
            intended_intensity_distribution={"Z3": 1.0},
        ),
        session_notes="", coaching_intent="", coaching_flags=[],
    )


def _race_fueling() -> RaceDayFueling:
    return RaceDayFueling(
        event_id="1", event_name="Spring 100", duration_tier="tier_long",
        cho_g_per_hr_low=60.0, cho_g_per_hr_high=90.0,
        na_mg_per_hr_low=400.0, na_mg_per_hr_high=700.0,
        fluid_ml_per_hr_low=450.0, fluid_ml_per_hr_high=750.0,
        sport_modifier_applied=1.0, salt_tolerance_modifier_applied=1.0,
        heat_acclim_modifier_applied=1.0,
        recommended_formats=["gel"], blocked_formats=[],
        sleep_dep_overlay_applies=False, notes=[],
    )


def _nutrition():
    return build_plan_nutrition(
        plan_version_id=1,
        sessions=[_session()],
        baseline=_baseline(),
        bmr_kcal=1600.0,
        body_weight_kg=BW,
        race_day_fueling=[_race_fueling()],
        event_dates={"1": RACE_DATE},
        generated_at=datetime(2026, 6, 8, tzinfo=timezone.utc),
    )


def _render(nutrition):
    session = _session()
    plan_version = {
        "id": 1,
        "pattern": "A",
        "created_via": "plan_create",
        "scope_start_date": RACE_DATE,
        "scope_end_date": RACE_DATE,
    }
    nutrition_by_date = (
        {d.date: d for d in nutrition.days} if nutrition else {}
    )
    tmpl = _env().get_template("plan_create/view.html")
    return tmpl.render(
        plan_version=plan_version,
        plan_version_id=1,
        sessions_by_date=[(RACE_DATE, [session])],
        session_count=1,
        nutrition=nutrition,
        nutrition_by_date=nutrition_by_date,
    )


def test_renders_plan_level_and_per_day_nutrition():
    html = _render(_nutrition())
    # Plan-level baseline card + the phase baseline.
    assert "Nutrition" in html
    assert "3000 kcal" in html
    assert "Regenerate" in html
    # Per-day fuel card (total kcal + macros for the modulated day).
    nutr = _nutrition()
    day = nutr.days[0]
    assert f"{day.total_kcal} kcal" in html
    assert day.fueling_note in html
    # Race-day fueling rendered with the per-hour bands.
    assert "Spring 100" in html
    assert "g/h" in html
    assert "ml/h" in html


def test_renders_without_nutrition():
    # `nutrition=None` (stage not run yet) must still render the plan + a
    # Generate affordance, not error.
    html = _render(None)
    assert "Generate" in html
    assert "hasn't been generated" in html
    assert "Running" in html  # the session list still renders
