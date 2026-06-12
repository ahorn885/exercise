"""Slice 2b.2b — `_parse_schedule_form` parsing of the two session-count
ceiling scalars (`two_a_day_preference` + `peak_sessions_max`).

Covers the validation the form layer owns (the DB carries no CHECK):
the two-a-day fallback, the blank-Peak-cap → NULL path, and the
`1..2×available_days` rejection-with-flash.
"""

# Front-load layer4 to dodge the repo's pre-existing layer1/layer4 circular
# import on isolated collection (mirrors tests/test_layer1_builder.py).
from layer4 import InMemoryCacheBackend  # noqa: F401

from routes.onboarding import _parse_schedule_form


def _enable(form, token, start="06:00", duration="60"):
    form[f"enabled_{token}"] = "on"
    form[f"start_{token}"] = start
    form[f"duration_{token}"] = duration


def test_two_a_day_defaults_to_occasionally_when_absent():
    _, profile_updates, _ = _parse_schedule_form({})
    assert profile_updates["two_a_day_preference"] == "occasionally"


def test_two_a_day_invalid_value_falls_back():
    _, profile_updates, _ = _parse_schedule_form({"two_a_day_preference": "always"})
    assert profile_updates["two_a_day_preference"] == "occasionally"


def test_two_a_day_valid_value_preserved():
    _, profile_updates, _ = _parse_schedule_form({"two_a_day_preference": "regularly"})
    assert profile_updates["two_a_day_preference"] == "regularly"


def test_peak_cap_blank_is_null():
    """Blank advanced field → NULL, so the grid derives from the preference."""
    _, profile_updates, errors = _parse_schedule_form({"peak_sessions_max": ""})
    assert profile_updates["peak_sessions_max"] is None
    assert errors == []


def test_peak_cap_within_range_kept():
    form = {"peak_sessions_max": "5"}
    for tok in ("mon", "tue", "wed"):  # available_days = 3 → max 6
        _enable(form, tok)
    _, profile_updates, errors = _parse_schedule_form(form)
    assert profile_updates["peak_sessions_max"] == 5
    assert errors == []


def test_peak_cap_over_two_times_available_days_rejected():
    form = {"peak_sessions_max": "9"}
    for tok in ("mon", "tue", "wed"):  # available_days = 3 → max 6 < 9
        _enable(form, tok)
    _, profile_updates, errors = _parse_schedule_form(form)
    assert profile_updates["peak_sessions_max"] is None
    assert any("Peak" in e for e in errors)
