"""Tests for `layer5.conditions_builder` — the deterministic 5B advisor.

Pure mapping coverage (temp → band → clothing/kit/flags) plus `build_plan_conditions`
against a stub `conditions_for` resolver, so the day-selection + wiring logic runs
with no DB and no network.
"""

from __future__ import annotations

from datetime import date

from layer4.payload import CardioBlock, HRTarget, PlanSession
from layer5.conditions_builder import (
    CONDITIONS_MODEL_NAME,
    advisory_flags,
    build_plan_conditions,
    classify_band,
    clothing_for,
    kit_for,
)
from layer5.conditions_payload import ThermalBand
from weather_client import ExpectedConditions

PVID = 12


# ─── fixtures ────────────────────────────────────────────────────────────────


def _cardio(d: date, sid: str, locale_id: str | None, locale_name: str | None) -> PlanSession:
    return PlanSession(
        session_id=sid,
        plan_version_id=PVID,
        date=d,
        day_of_week=d.strftime("%a"),  # type: ignore[arg-type]
        session_index_in_day=0,
        time_of_day="morning",
        kind="cardio",
        discipline_id="run",
        discipline_name="Running",
        locale_id=locale_id,
        locale_name=locale_name,
        duration_min=60,
        intensity_summary="moderate",
        cardio_blocks=[
            CardioBlock(
                block_kind="main_set",
                duration_min=60,
                intensity_zone="Z2",
                intensity_target=HRTarget(hr_bpm_low=120, hr_bpm_high=140),
                instructions="steady",
            )
        ],
        session_notes="",
        coaching_intent="",
        coaching_flags=[],
    )


def _rest(d: date, sid: str) -> PlanSession:
    return PlanSession(
        session_id=sid,
        plan_version_id=PVID,
        date=d,
        day_of_week=d.strftime("%a"),  # type: ignore[arg-type]
        session_index_in_day=0,
        time_of_day="unspecified",
        kind="rest",
        duration_min=0,
        intensity_summary="rest",
        rest_reason="planned_recovery",
        session_notes="",
        coaching_intent="",
        coaching_flags=[],
    )


def _ec(tmax: float, tmin: float, wet: int = 0) -> ExpectedConditions:
    return ExpectedConditions(
        temp_max_c=tmax,
        temp_min_c=tmin,
        wet_day_probability_pct=wet,
        sample_days=30,
        sample_years=5,
    )


# ─── pure mappings ───────────────────────────────────────────────────────────


def test_classify_band_boundaries():
    cases: list[tuple[float, ThermalBand]] = [
        (-1.0, "freezing"),
        (0.0, "cold"),
        (7.9, "cold"),
        (8.0, "cool"),
        (14.9, "cool"),
        (15.0, "mild"),
        (21.9, "mild"),
        (22.0, "warm"),
        (27.9, "warm"),
        (28.0, "hot"),
        (35.0, "hot"),
    ]
    for tmax, expected in cases:
        assert classify_band(tmax) == expected, tmax


def test_clothing_present_for_every_band():
    for band in ("freezing", "cold", "cool", "mild", "warm", "hot"):
        assert clothing_for(band)  # type: ignore[arg-type]


def test_kit_adds_waterproof_only_when_wet():
    dry = kit_for("mild", wet=False)
    wet = kit_for("mild", wet=True)
    assert "waterproof layer" not in dry
    assert wet == dry + ["waterproof layer"]


def test_advisory_flags_each_threshold():
    assert advisory_flags(30.0, 18.0, 0) == [
        "heat — front-load hydration and electrolytes; favour cooler hours"
    ]
    assert advisory_flags(10.0, 0.0, 0) == [
        "cold start — cover hands and ears; wear a layer you can shed"
    ]
    assert advisory_flags(18.0, 10.0, 55) == [
        "rain likely — pack a waterproof layer and mind your footing"
    ]
    # A benign day raises nothing.
    assert advisory_flags(20.0, 12.0, 10) == []


def test_advisory_flags_stable_order_when_combined():
    flags = advisory_flags(31.0, 1.0, 70)
    assert len(flags) == 3
    assert flags[0].startswith("heat")
    assert flags[1].startswith("cold start")
    assert flags[2].startswith("rain likely")


# ─── build_plan_conditions ───────────────────────────────────────────────────


def test_build_skips_days_without_locale_or_resolution():
    d1, d2, d3 = date(2026, 6, 1), date(2026, 6, 2), date(2026, 6, 3)
    sessions = [
        _cardio(d1, "c1", "park", "City Park"),  # resolves → row
        _rest(d2, "r1"),  # no locale → skipped
        _cardio(d3, "c2", "gym", "Downtown Gym"),  # resolver returns None → skipped
    ]
    resolved = {("park", d1): _ec(24.0, 12.0, wet=10)}

    def resolver(locale_id: str, d: date):
        return resolved.get((locale_id, d))

    pc = build_plan_conditions(
        plan_version_id=PVID, sessions=sessions, conditions_for=resolver
    )

    assert pc.plan_version_id == PVID
    assert pc.model_meta.model == CONDITIONS_MODEL_NAME
    assert [day.date for day in pc.days] == [d1]  # only the resolvable outdoor day
    day = pc.days[0]
    assert day.locale_id == "park"
    assert day.locale_name == "City Park"
    assert day.thermal_band == "warm"  # 24°C high
    assert day.clothing_summary == clothing_for("warm")
    assert day.advisory_flags == []  # benign
    assert pc.notes  # standing note present when there's at least one day


def test_build_filters_session_ids_to_represented_locale():
    d = date(2026, 6, 10)
    # Two sessions same day: first sets the represented locale; a same-locale
    # second is included, a different-locale third is not.
    sessions = [
        _cardio(d, "a", "park", "City Park"),
        _cardio(d, "b", "park", "City Park"),
        _cardio(d, "c", "track", "Track"),
    ]
    # session_index_in_day must differ within a day.
    sessions[1].session_index_in_day = 1
    sessions[2].session_index_in_day = 2

    def resolver(locale_id: str, _d: date):
        return _ec(5.0, -2.0, wet=60) if locale_id == "park" else None

    pc = build_plan_conditions(
        plan_version_id=PVID, sessions=sessions, conditions_for=resolver
    )
    assert len(pc.days) == 1
    day = pc.days[0]
    assert day.session_ids == ["a", "b"]
    assert day.thermal_band == "cold"  # 5°C high
    assert "waterproof layer" in day.kit_items  # wet=60 ≥ threshold
    # heat off, cold-start on (low -2°C), rain on (60%)
    assert any(f.startswith("cold start") for f in day.advisory_flags)
    assert any(f.startswith("rain likely") for f in day.advisory_flags)


def test_build_empty_when_nothing_resolves():
    d = date(2026, 6, 1)
    pc = build_plan_conditions(
        plan_version_id=PVID,
        sessions=[_rest(d, "r1")],
        conditions_for=lambda _l, _d: None,
    )
    assert pc.days == []
    assert pc.notes == []  # no standing note when there's nothing to advise
