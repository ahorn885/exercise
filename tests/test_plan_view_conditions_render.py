"""Render-coverage for the Layer 5B conditions blocks in
`templates/plan_create/view.html`.

The route tests call functions directly (no template render), so a template
data-binding bug (a wrong attribute, the band-icon lookup, the kit/flags loops)
would otherwise reach production unseen. This renders the *real* `view.html`
against a real `PlanConditions` / `PlanSession`, swapping in a stub `base.html`
and stub `url_for` / `csrf_token` so no Flask app/DB is needed.
"""

from __future__ import annotations

from datetime import date, datetime, timezone

from jinja2 import ChoiceLoader, DictLoader, Environment, FileSystemLoader

from layer4.payload import CardioBlock, HRTarget, PlanSession
from layer5.conditions_builder import build_plan_conditions
from weather_client import ExpectedConditions

DAY = date(2026, 7, 1)


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
        duration_min=60, intensity_summary="moderate",
        cardio_blocks=[
            CardioBlock(
                block_kind="main_set", duration_min=60, intensity_zone="Z2",
                intensity_target=HRTarget(hr_bpm_low=120, hr_bpm_high=140),
                instructions="steady",
            )
        ],
        session_notes="", coaching_intent="", coaching_flags=[],
    )


def _conditions(ec: ExpectedConditions):
    return build_plan_conditions(
        plan_version_id=1,
        sessions=[_session()],
        conditions_for=lambda _l, _d: ec,
        generated_at=datetime(2026, 6, 20, tzinfo=timezone.utc),
    )


def _render(conditions):
    session = _session()
    plan_version = {
        "id": 1, "pattern": "A", "created_via": "plan_create",
        "scope_start_date": DAY, "scope_end_date": DAY,
    }
    conditions_by_date = (
        {d.date: d for d in conditions.days} if conditions else {}
    )
    tmpl = _env().get_template("plan_create/view.html")
    return tmpl.render(
        plan_version=plan_version,
        plan_version_id=1,
        lifecycle_state="Active",
        days=[(DAY, DAY.strftime("%a"), [session])],
        session_count=1,
        nutrition=None,
        nutrition_by_date={},
        conditions=conditions,
        conditions_by_date=conditions_by_date,
    )


def test_renders_card_and_per_day_cold_wet_advisory():
    ec = ExpectedConditions(
        temp_max_c=2.0, temp_min_c=-4.0, wet_day_probability_pct=55,
        sample_days=30, sample_years=5,
    )
    html = _render(_conditions(ec))

    # Conditions card header + standing (normals-not-forecast) note + Regenerate.
    assert "Conditions" in html
    assert "climate normals" in html
    assert "Regenerate" in html

    # Per-day: band chip, temps, clothing prose, kit list, and the two flags.
    assert "Cold" in html
    assert "2° / -4°C" in html
    assert "💧 55%" in html
    assert "Long sleeves and tights" in html  # clothing_summary
    assert "waterproof layer" in html  # kit_items includes it when wet
    assert "cold start" in html  # advisory flag
    assert "rain likely" in html  # advisory flag


def test_renders_generate_affordance_without_conditions():
    # `conditions=None` (stage not run / no coords) must still render the plan +
    # a Generate affordance, not error.
    html = _render(None)
    assert "Generate" in html
    assert "need at least one session at a locale with coordinates" in html
    assert "Running" in html  # the session list still renders


def test_hot_day_uses_heat_flag_and_band():
    ec = ExpectedConditions(
        temp_max_c=33.0, temp_min_c=22.0, wet_day_probability_pct=0,
        sample_days=30, sample_years=5,
    )
    html = _render(_conditions(ec))
    assert "Hot" in html
    assert "heat" in html  # heat advisory flag
    assert "Minimal breathable kit" in html  # hot-band clothing
    assert "💧" not in html  # 0% wet → no rain readout
    assert "rain likely" not in html  # dry → no rain flag
