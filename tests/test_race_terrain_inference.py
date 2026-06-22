"""Stub-LLM tests for race_terrain_inference (GitHub #592, Slice 2).

No real API: the LLM caller is injected. Exercises the per-discipline
breakdown, the closed terrain vocab + race-discipline validation, the
per-discipline pct-sum bound, no-silent-repair (validation failures raise),
the season phrasing, the race_terrain mapping, and retry semantics.
"""

from __future__ import annotations

from datetime import date

import pytest

import race_terrain_inference as rti
from race_terrain_inference import (
    TerrainInferenceError,
    TerrainInferenceInput,
    infer_terrain,
)
from race_url_parser import DisciplineOption, TerrainVocabEntry

_TODAY = date(2026, 6, 22)
_VOCAB = (
    TerrainVocabEntry("TRN-014", "Technical singletrack"),
    TerrainVocabEntry("TRN-020", "Gravel doubletrack"),
)
_DISC = (DisciplineOption("D-001", "Trail running"), DisciplineOption("D-010", "Mountain biking"))


def _make_input(**kw):
    return TerrainInferenceInput(
        place_name=kw.get("place", "Lutsen, MN"),
        lat=kw.get("lat", 47.65), lng=kw.get("lng", -90.69),
        race_name=kw.get("name", "Superior 100"),
        distance_km=kw.get("distance_km", 161.0),
        elevation_gain_m=kw.get("elevation_gain_m", 6000.0),
        race_format=kw.get("race_format", "single_day"),
        event_date=kw.get("event_date", date(2026, 9, 5)),
        disciplines=kw.get("disciplines", _DISC),
        terrain_vocab=kw.get("vocab", _VOCAB),
        today=kw.get("today", _TODAY),
    )


def _caller_returning(args):
    def _caller(system, user, tool, model, temperature, max_tokens, thinking):
        return dict(args)
    return _caller


# ─── valid breakdowns ────────────────────────────────────────────────────────


def test_single_discipline_breakdown_kept():
    args = {
        "terrain_breakdown": [
            {"discipline_id": "D-001", "terrain_id": "TRN-014", "pct_of_race": 70.0, "rationale": "Sawtooth singletrack"},
            {"discipline_id": "D-001", "terrain_id": "TRN-020", "pct_of_race": 30.0, "rationale": "connector roads"},
        ],
        "confidence": "medium",
        "summary": "Mostly technical singletrack — train climbing and downhill control.",
    }
    r = infer_terrain(_make_input(), caller=_caller_returning(args))
    assert len(r.terrain_breakdown) == 2
    assert r.confidence == "medium"
    mapped = r.as_race_terrain()
    assert mapped[0] == {"terrain_id": "TRN-014", "pct_of_race": 70.0, "discipline_id": "D-001"}


def test_multi_discipline_sums_checked_independently():
    args = {
        "terrain_breakdown": [
            {"discipline_id": "D-001", "terrain_id": "TRN-014", "pct_of_race": 100.0, "rationale": "trail legs"},
            {"discipline_id": "D-010", "terrain_id": "TRN-020", "pct_of_race": 100.0, "rationale": "gravel bike legs"},
        ],
        "confidence": "low", "summary": "Trail run + gravel bike — verify the course.",
    }
    r = infer_terrain(_make_input(), caller=_caller_returning(args))
    assert {e.discipline_id for e in r.terrain_breakdown} == {"D-001", "D-010"}


def test_confidence_defaults_low_when_bad():
    args = {
        "terrain_breakdown": [{"discipline_id": "D-001", "terrain_id": "TRN-014", "pct_of_race": 100.0, "rationale": "x"}],
        "confidence": "very-high", "summary": "s",
    }
    r = infer_terrain(_make_input(), caller=_caller_returning(args))
    assert r.confidence == "low"


# ─── no silent repair: validation failures raise ─────────────────────────────


def test_off_vocab_terrain_raises():
    args = {
        "terrain_breakdown": [{"discipline_id": "D-001", "terrain_id": "TRN-999", "pct_of_race": 100.0, "rationale": "x"}],
        "confidence": "low", "summary": "s",
    }
    with pytest.raises(TerrainInferenceError) as ei:
        infer_terrain(_make_input(), caller=_caller_returning(args))
    assert ei.value.code == "validation"


def test_unknown_discipline_raises():
    args = {
        "terrain_breakdown": [{"discipline_id": "D-777", "terrain_id": "TRN-014", "pct_of_race": 100.0, "rationale": "x"}],
        "confidence": "low", "summary": "s",
    }
    with pytest.raises(TerrainInferenceError):
        infer_terrain(_make_input(), caller=_caller_returning(args))


def test_pct_sum_out_of_bounds_raises():
    args = {
        "terrain_breakdown": [
            {"discipline_id": "D-001", "terrain_id": "TRN-014", "pct_of_race": 100.0, "rationale": "x"},
            {"discipline_id": "D-001", "terrain_id": "TRN-020", "pct_of_race": 100.0, "rationale": "y"},
        ],
        "confidence": "low", "summary": "s",
    }
    with pytest.raises(TerrainInferenceError) as ei:
        infer_terrain(_make_input(), caller=_caller_returning(args))
    assert "pct_sum" in (ei.value.detail or "")


def test_bad_pct_raises():
    args = {
        "terrain_breakdown": [{"discipline_id": "D-001", "terrain_id": "TRN-014", "pct_of_race": -5, "rationale": "x"}],
        "confidence": "low", "summary": "s",
    }
    with pytest.raises(TerrainInferenceError):
        infer_terrain(_make_input(), caller=_caller_returning(args))


def test_empty_breakdown_raises():
    args = {"terrain_breakdown": [], "confidence": "low", "summary": "s"}
    with pytest.raises(TerrainInferenceError):
        infer_terrain(_make_input(), caller=_caller_returning(args))


# ─── retry semantics ─────────────────────────────────────────────────────────


def test_schema_violation_retries_then_succeeds():
    calls = {"n": 0}

    def _caller(system, user, tool, model, temperature, max_tokens, thinking):
        calls["n"] += 1
        if calls["n"] == 1:
            raise TerrainInferenceError("schema_violation", detail="no block")
        return {
            "terrain_breakdown": [{"discipline_id": "D-001", "terrain_id": "TRN-014", "pct_of_race": 100.0, "rationale": "x"}],
            "confidence": "medium", "summary": "s",
        }

    r = infer_terrain(_make_input(), caller=_caller)
    assert calls["n"] == 2 and len(r.terrain_breakdown) == 1


def test_api_error_raises_without_retry():
    calls = {"n": 0}

    def _caller(system, user, tool, model, temperature, max_tokens, thinking):
        calls["n"] += 1
        raise TerrainInferenceError("anthropic_api_error", detail="503")

    with pytest.raises(TerrainInferenceError):
        infer_terrain(_make_input(), caller=_caller)
    assert calls["n"] == 1


def test_validation_failure_does_not_retry():
    calls = {"n": 0}

    def _caller(system, user, tool, model, temperature, max_tokens, thinking):
        calls["n"] += 1
        return {
            "terrain_breakdown": [{"discipline_id": "D-001", "terrain_id": "TRN-999", "pct_of_race": 100.0, "rationale": "x"}],
            "confidence": "low", "summary": "s",
        }

    with pytest.raises(TerrainInferenceError):
        infer_terrain(_make_input(), caller=_caller)
    assert calls["n"] == 1          # validation failure raises immediately (no retry)


# ─── season phrasing ─────────────────────────────────────────────────────────


def test_season_phrase_northern():
    assert "northern-hemisphere summer" in rti._season_phrase(date(2026, 7, 15), 45.0)


def test_season_phrase_southern_flips():
    # July in the southern hemisphere is winter
    assert "southern-hemisphere winter" in rti._season_phrase(date(2026, 7, 15), -33.0)


def test_season_phrase_no_date():
    assert rti._season_phrase(None, 45.0) == "(date not set)"
