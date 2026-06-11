"""Tests for the regex parsers in the sports framework + exercise DB extractors."""
from __future__ import annotations

from etl.layer0.extractors.sports_framework import (
    _parse_age_ramps,
    _parse_pack_weight,
    _parse_race_time_pct,
    _parse_recovery_modalities,
    _parse_weeks,
    _parse_yes_no,
    _split_dot_list,
)
from etl.layer0.extractors.exercise_db import (
    parse_equipment_substitutes,
    parse_exercise_ref,
    parse_physical_proxies,
)


# ---------------------------------------------------------------------------
# Sports framework
# ---------------------------------------------------------------------------

def test_pack_weight_en_dash():
    assert _parse_pack_weight("YES — 25–35 lb race pack on foot and bike") == (25.0, 35.0)


def test_pack_weight_hyphen():
    assert _parse_pack_weight("Carry 15-20 lb pack") == (15.0, 20.0)


def test_pack_weight_single_value():
    assert _parse_pack_weight("Add 35 lb sandbag") == (35.0, 35.0)


def test_pack_weight_absent():
    assert _parse_pack_weight("YES — transitions only.") == (None, None)


def test_pack_weight_none_input():
    assert _parse_pack_weight(None) == (None, None)


def test_weeks_range():
    assert _parse_weeks("BASE: 4–6 weeks easy aerobic") == (4, 6)


def test_weeks_single():
    assert _parse_weeks("2 weeks taper") == (2, 2)


def test_age_ramp_typical():
    text = (
        "40–44: Standard ramp; add 1 easy day if 5+ days/wk\n"
        "45–54: Max 8%/week. Watch tendons.\n"
        "55+: Max 5%/week. Mandatory recovery."
    )
    out = _parse_age_ramps(text)
    assert out["40_44"] is None
    assert out["45_54"] == 8.0
    assert out["55_plus"] == 5.0


def test_age_ramp_hyphen_separator():
    text = "40-44: Standard\n45-54: Max 7%/week\n55+: 4%/week"
    out = _parse_age_ramps(text)
    assert out["45_54"] == 7.0
    assert out["55_plus"] == 4.0


def test_age_ramp_missing_band():
    text = "Standard ramp across all age groups."
    out = _parse_age_ramps(text)
    assert out == {"40_44": None, "45_54": None, "55_plus": None}


def test_race_time_pct_range():
    assert _parse_race_time_pct("15–25%") == (15.0, 25.0)


def test_race_time_pct_single():
    assert _parse_race_time_pct("30%") == (30.0, 30.0)


def test_race_time_pct_with_qualifier():
    assert _parse_race_time_pct("100% — overlaid on all") == (100.0, 100.0)


def test_split_dot_list():
    assert _split_dot_list(
        "IT Band Syndrome · Plantar Fasciitis · Stress Fractures"
    ) == ["IT Band Syndrome", "Plantar Fasciitis", "Stress Fractures"]


def test_split_dot_list_empty():
    assert _split_dot_list(None) == []
    assert _split_dot_list("") == []


def test_recovery_modalities_numbered_list():
    text = (
        "1. Sleep (8+ hrs)\n"
        "2. CWI lower body (11–15°C, 10–15 min)\n"
        "3. Compression\n"
        "Some narrative tail without a number"
    )
    out = _parse_recovery_modalities(text)
    assert out == [
        "Sleep (8+ hrs)",
        "CWI lower body (11–15°C, 10–15 min)",
        "Compression",
    ]


def test_yes_no_yes():
    flag, full = _parse_yes_no("YES — Core discipline. Navigation overlaid.")
    assert flag is True
    assert full.startswith("YES")


def test_yes_no_no():
    flag, full = _parse_yes_no("NO — course is marked.")
    assert flag is False
    assert full.startswith("NO")


def test_yes_no_blank():
    flag, full = _parse_yes_no(None)
    assert flag is False
    assert full == ""


# ---------------------------------------------------------------------------
# Exercise DB parsers
# ---------------------------------------------------------------------------

def test_exercise_ref_em_dash():
    out = parse_exercise_ref("EX117 — Loaded Step-Down (Eccentric Box)")
    assert out == {"exercise_id": "EX117", "exercise_name": "Loaded Step-Down (Eccentric Box)"}


def test_exercise_ref_hyphen():
    out = parse_exercise_ref("EX020 - Nordic Hamstring Curl")
    assert out == {"exercise_id": "EX020", "exercise_name": "Nordic Hamstring Curl"}


def test_exercise_ref_unparseable():
    out = parse_exercise_ref("Wall Sit (no ID)")
    assert out == {"exercise_id": None, "exercise_name": None}


def test_exercise_ref_none():
    assert parse_exercise_ref(None) == {"exercise_id": None, "exercise_name": None}


def test_physical_proxies_multiple():
    out = parse_physical_proxies(
        "EX117 — Loaded Step-Down (Eccentric Box); EX020 — Nordic Hamstring Curl"
    )
    assert out == [
        {"exercise_id": "EX117", "exercise_name": "Loaded Step-Down (Eccentric Box)"},
        {"exercise_id": "EX020", "exercise_name": "Nordic Hamstring Curl"},
    ]


def test_physical_proxies_empty():
    assert parse_physical_proxies("") == []
    assert parse_physical_proxies(None) == []


def test_equipment_substitutes_split():
    text = "Safety Bar Squat; Hack Squat machine; 🏠 Sandbag goblet squat"
    out = parse_equipment_substitutes(text)
    assert out == {
        "standard": ["Safety Bar Squat", "Hack Squat machine"],
        "improvised": ["Sandbag goblet squat"],
    }


def test_equipment_substitutes_only_improvised():
    out = parse_equipment_substitutes("🏠 Backpack with books; 🏠 Water jug")
    assert out["standard"] == []
    assert out["improvised"] == ["Backpack with books", "Water jug"]


def test_equipment_substitutes_empty():
    assert parse_equipment_substitutes(None) == {"standard": [], "improvised": []}
