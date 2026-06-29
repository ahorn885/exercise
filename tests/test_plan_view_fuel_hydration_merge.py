"""Render-coverage for the #942 fuel+hydration merge in
`templates/plan_create/view.html`.

The day view used to show hydration/electrolyte guidance twice: a 5A fueling
note (plus the electrolyte pick) under the date, and a 5B "heat" weather chip
that was also about hydration/electrolytes. This renders the *real* `view.html`
against both a `PlanNutrition` and a hot-day `PlanConditions` for the same date
and asserts the heat advisory is folded into the fueling note as one coherent
line and no longer rendered as a separate weather chip — while the non-heat
(cold-start / rain) advisories stay with the conditions.
"""

from __future__ import annotations

from datetime import date, datetime, timezone

from jinja2 import ChoiceLoader, DictLoader, Environment, FileSystemLoader

from layer4.context import (
    DailyNutritionBaseline,
    DailyPhaseTargets,
    MacroTargets,
)
from layer4.payload import CardioBlock, HRTarget, PlanSession, SessionPhaseMetadata
from layer5 import build_plan_nutrition
from layer5.conditions_builder import build_plan_conditions
from weather_client import ExpectedConditions

DAY = date(2026, 7, 1)
BW = 70.0


def _env() -> Environment:
    env = Environment(
        loader=ChoiceLoader(
            [
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


def _session() -> PlanSession:
    return PlanSession(
        session_id="c-1", plan_version_id=1, date=DAY, day_of_week="Wed",
        session_index_in_day=0, time_of_day="morning", kind="cardio",
        discipline_id="run", discipline_name="Running",
        locale_id="park", locale_name="City Park",
        duration_min=90, intensity_summary="moderate",
        cardio_blocks=[
            CardioBlock(
                block_kind="main_set", duration_min=90, intensity_zone="Z2",
                intensity_target=HRTarget(hr_bpm_low=120, hr_bpm_high=140),
                instructions="steady",
            )
        ],
        phase_metadata=SessionPhaseMetadata(
            phase_name="Base", week_in_phase=1, total_weeks_in_phase=4,
            intended_volume_band=(8.0, 10.0),
            intended_intensity_distribution={"Z2": 1.0},
        ),
        session_notes="", coaching_intent="", coaching_flags=[],
    )


def _baseline() -> DailyNutritionBaseline:
    targets = DailyPhaseTargets(
        activity_multiplier=1.7,
        activity_multiplier_source={"phase": "Base"},
        daily_calorie_target_kcal=3000,
        macros=MacroTargets(
            cho_g=420, cho_g_per_kg=6.0, cho_kcal=420 * 4,
            protein_g=119, protein_g_per_kg=1.7, protein_kcal=119 * 4,
            fat_g=70, fat_kcal=70 * 9, fat_floor_constrained=False,
        ),
    )
    return DailyNutritionBaseline(per_phase={"Base": targets})


def _nutrition():
    return build_plan_nutrition(
        plan_version_id=1,
        sessions=[_session()],
        baseline=_baseline(),
        bmr_kcal=1600.0,
        body_weight_kg=BW,
        generated_at=datetime(2026, 6, 20, tzinfo=timezone.utc),
    )


def _conditions(ec: ExpectedConditions):
    return build_plan_conditions(
        plan_version_id=1,
        sessions=[_session()],
        conditions_for=lambda _l, _d: ec,
        generated_at=datetime(2026, 6, 20, tzinfo=timezone.utc),
    )


def _render(nutrition, conditions):
    session = _session()
    plan_version = {
        "id": 1, "pattern": "A", "created_via": "plan_create",
        "scope_start_date": DAY, "scope_end_date": DAY,
    }
    tmpl = _env().get_template("plan_create/view.html")
    return tmpl.render(
        plan_version=plan_version,
        plan_version_id=1,
        lifecycle_state="Active",
        days=[(DAY, DAY.strftime("%a"), [session])],
        session_count=1,
        nutrition=nutrition,
        nutrition_by_date={d.date: d for d in nutrition.days} if nutrition else {},
        conditions=conditions,
        conditions_by_date=(
            {d.date: d for d in conditions.days} if conditions else {}
        ),
    )


def test_heat_advisory_folds_into_the_fueling_note():
    # A hot day that also trips the cold-start and rain advisories (a large
    # diurnal range + wet), so we can prove only the heat flag is moved.
    ec = ExpectedConditions(
        temp_max_c=31.0, temp_min_c=1.0, wet_day_probability_pct=70,
        sample_days=30, sample_years=5,
    )
    html = _render(_nutrition(), _conditions(ec))

    nutr = _nutrition()
    note = nutr.days[0].fueling_note
    # The fueling note and the heat hydration guidance now read as one line.
    assert note in html
    assert "In the heat, front-load hydration and electrolytes; favour cooler hours." in html

    # The heat advisory is no longer a standalone weather chip…
    assert 'chip warn">heat' not in html
    # …but the kit-oriented advisories still are.
    assert 'chip warn">cold start' in html
    assert 'chip warn">rain likely' in html


def test_heat_stays_a_weather_chip_when_no_fueling_block():
    # No nutrition for the day → nothing to fold heat into, so it must still
    # surface as a weather chip rather than vanish.
    ec = ExpectedConditions(
        temp_max_c=33.0, temp_min_c=22.0, wet_day_probability_pct=0,
        sample_days=30, sample_years=5,
    )
    html = _render(None, _conditions(ec))
    assert 'chip warn">heat' in html
    assert "In the heat," not in html
