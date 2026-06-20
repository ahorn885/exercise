"""Tests for `layer5.supplements` — the deterministic supplement engine (#621).

Covers the two surfaces:
- Standard (always-take): baseline + dietary additions, contraindication-screened,
  with `already_in_protocol` tagging.
- Daily (effort/event-based): load-tier mapping + race-day passthrough.
"""

from __future__ import annotations

from layer4.context import (
    DietaryPatternFlag,
    IntegratedSupplement,
    Layer2ECoachingFlag,
    RaceDaySupplementSuggestion,
    SupplementIntegrationPayload,
)
from layer5.supplements import (
    build_standing_supplements,
    effort_supplements_for_day,
)


def _si(*, integrated=None, race=None, flags=None) -> SupplementIntegrationPayload:
    return SupplementIntegrationPayload(
        integrated=integrated or [],
        race_day_suggestions=race or [],
        contraindication_flags=flags or [],
        contraindication_hitl_items=[],
    )


# ─── Standard block ──────────────────────────────────────────────────────────


def test_standing_baseline_present_when_no_integration():
    recs = build_standing_supplements(None, None)
    names = [r.name for r in recs]
    assert "Creatine" in names and "Omega-3" in names
    assert all(r.source == "baseline" for r in recs)
    assert all(r.already_in_protocol is False for r in recs)


def test_standing_marks_already_in_protocol():
    si = _si(integrated=[
        IntegratedSupplement(
            supplement_id="omega_3", canonical_name="Omega-3",
            is_known=True, contraindication_hits=[],
        )
    ])
    recs = build_standing_supplements(si, None)
    omega = next(r for r in recs if r.name == "Omega-3")
    assert omega.already_in_protocol is True
    # An unmatched baseline line stays False.
    creatine = next(r for r in recs if r.name == "Creatine")
    assert creatine.already_in_protocol is False


def test_standing_drops_contraindicated_baseline():
    si = _si(flags=[
        Layer2ECoachingFlag(
            flag_type="supplement_contraindicated",
            event_id=None, supplement_id="omega_3",
            message="contraindicated", severity="high", metadata={},
        )
    ])
    recs = build_standing_supplements(si, None)
    assert "Omega-3" not in [r.name for r in recs]
    # Other baseline lines survive.
    assert "Creatine" in [r.name for r in recs]


def test_standing_adds_dietary_flag_supplements():
    flags = [
        DietaryPatternFlag(
            pattern="Vegan", concern="b12_deficiency_risk", severity="moderate",
            rationale="risk", suggested_supplement_id="vitamin_b12",
        )
    ]
    recs = build_standing_supplements(None, flags)
    b12 = next(r for r in recs if r.name == "Vitamin B12")
    assert b12.source == "dietary"
    assert "Vegan" in (b12.reason or "")


def test_standing_dietary_deduped_against_baseline():
    # omega_3 is already a baseline line; a Vegan omega_3 flag must not double it.
    flags = [
        DietaryPatternFlag(
            pattern="Vegan", concern="epa_dha_conversion", severity="low",
            rationale="conversion", suggested_supplement_id="omega_3",
        )
    ]
    recs = build_standing_supplements(None, flags)
    omega_lines = [r for r in recs if r.name.startswith("Omega-3")]
    assert len(omega_lines) == 1
    assert omega_lines[0].source == "baseline"


# ─── Daily / effort block ────────────────────────────────────────────────────


def test_effort_rest_and_light_are_empty():
    assert effort_supplements_for_day("rest", is_race_day=False) == []
    assert effort_supplements_for_day("light", is_race_day=False) == []


def test_effort_hard_day_has_electrolytes_and_recovery():
    recs = effort_supplements_for_day("hard", is_race_day=False)
    names = [r.name for r in recs]
    assert "Electrolyte mix" in names
    assert "Tart cherry" in names
    assert all(r.source == "effort" for r in recs)


def test_effort_peak_adds_carbohydrate():
    names = [r.name for r in effort_supplements_for_day("peak", is_race_day=False)]
    assert "Carbohydrate drink" in names


def test_race_day_passes_through_2e_suggestions():
    sugs = [
        RaceDaySupplementSuggestion(
            event_id="1", supplement_id="electrolyte_mix",
            canonical_name="Electrolyte mix", reason="replace sodium",
            already_in_athlete_protocol=True,
        )
    ]
    recs = effort_supplements_for_day(
        "peak", is_race_day=True, race_suggestions=sugs)
    assert len(recs) == 1
    assert recs[0].source == "race"
    assert recs[0].already_in_protocol is True
    assert recs[0].reason == "replace sodium"
