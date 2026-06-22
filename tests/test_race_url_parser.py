"""Stub-LLM tests for race_url_parser (GitHub #256, Slice 1).

No real API / network: the LLM caller and the page fetcher are injected.
Exercises per-field validation (drop-invalid-keep-rest), the never-fabricate
nulls, the distance menu, terrain vocab + pct-sum bounds + the stated/estimated
basis, the HTML reducer, the SSRF host guard, fetch outcomes, and the
schema-violation retry.
"""

from __future__ import annotations

from datetime import date

import pytest

import race_url_parser as rup
from race_url_parser import (
    DisciplineOption,
    RaceURLParseError,
    RaceURLParseInput,
    TerrainVocabEntry,
    fetch_and_reduce,
    parse_race_url,
    reduce_html_to_text,
)

_TODAY = date(2026, 6, 22)

_VOCAB = (
    TerrainVocabEntry("TRN-001", "Flat road"),
    TerrainVocabEntry("TRN-014", "Technical singletrack"),
    TerrainVocabEntry("TRN-020", "Gravel doubletrack"),
)
_BRIDGE = (
    DisciplineOption("D-001", "Trail running"),
    DisciplineOption("D-010", "Mountain biking"),
)


def _full_args(**overrides):
    """A complete (all-required-keys) tool_args dict; override per test."""
    base = {
        "name": None, "event_date": None, "race_format": None,
        "distance_options": [], "total_elevation_gain_m": None,
        "location_text": None, "framework_sport": None,
        "included_discipline_ids": None, "race_terrain": None,
        "terrain_pct_basis": None, "rules_notes": None,
        "confidence": "high", "summary": "ok",
    }
    base.update(overrides)
    return base


def _caller_returning(args):
    def _caller(system, user, tool, model, temperature, max_tokens, thinking):
        return dict(args)
    return _caller


def _make_input(**kw):
    return RaceURLParseInput(
        reduced_page_text=kw.get("text", "Some race page text"),
        source_url=kw.get("url", "https://example.com/race"),
        terrain_vocab=kw.get("vocab", _VOCAB),
        sport_bridge=kw.get("bridge", _BRIDGE),
        today=kw.get("today", _TODAY),
    )


# ─── scenario 1: clean single-event page ─────────────────────────────────────


def test_clean_page_fills_fields():
    args = _full_args(
        name="Superior 100", event_date="2026-09-05", race_format="single_day",
        distance_options=[{"label": "100 Mile", "distance_km": 161.0, "event_date": None, "elevation_gain_m": 6000.0}],
        total_elevation_gain_m=6000.0, location_text="Lutsen, MN",
        framework_sport="Trail Running", included_discipline_ids=["D-001"],
        race_terrain=[{"terrain_id": "TRN-014", "pct_of_race": 100.0, "discipline_id": None}],
        terrain_pct_basis="estimated", rules_notes="Mandatory: headlamp. 38-hour cutoff.",
        confidence="high", summary="Got the date, distance, and cutoff — confirm the location.",
    )
    r = parse_race_url(_make_input(), caller=_caller_returning(args))
    assert r.name == "Superior 100"
    assert r.event_date == date(2026, 9, 5)
    assert r.race_format == "single_day"
    assert len(r.distance_options) == 1 and r.distance_options[0].distance_km == 161.0
    assert r.total_elevation_gain_m == 6000.0
    assert r.location_text == "Lutsen, MN"
    assert r.included_discipline_ids == ["D-001"]
    assert r.race_terrain and r.race_terrain[0].terrain_id == "TRN-014"
    assert r.terrain_pct_basis == "estimated"
    assert "cutoff" in r.rules_notes
    assert r.dropped == []


# ─── scenario 2: never-fabricate (missing fields stay null) ──────────────────


def test_missing_fields_stay_null():
    args = _full_args(name="Some Race", location_text="Moab, UT")  # everything else null
    r = parse_race_url(_make_input(), caller=_caller_returning(args))
    assert r.name == "Some Race"
    assert r.location_text == "Moab, UT"
    assert r.event_date is None
    assert r.race_format is None
    assert r.race_terrain is None
    assert r.distance_options == []


# ─── scenario 3: multi-distance menu ─────────────────────────────────────────


def test_multi_distance_menu_carries_all_options():
    args = _full_args(distance_options=[
        {"label": "25K", "distance_km": 25.0, "event_date": "2026-09-06", "elevation_gain_m": 800.0},
        {"label": "50K", "distance_km": 50.0, "event_date": "2026-09-05", "elevation_gain_m": 1600.0},
        {"label": "100 Mile", "distance_km": 161.0, "event_date": "2026-09-05", "elevation_gain_m": 6000.0},
    ])
    r = parse_race_url(_make_input(), caller=_caller_returning(args))
    assert [o.label for o in r.distance_options] == ["25K", "50K", "100 Mile"]
    assert r.distance_options[0].event_date == date(2026, 9, 6)
    # distance is never auto-applied to a scalar field
    assert not hasattr(r, "distance_km")


def test_duration_option_has_null_distance():
    args = _full_args(distance_options=[
        {"label": "24-hour rogaine", "distance_km": None, "event_date": None, "elevation_gain_m": None},
    ])
    r = parse_race_url(_make_input(), caller=_caller_returning(args))
    assert r.distance_options[0].distance_km is None
    assert r.distance_options[0].label == "24-hour rogaine"


# ─── scenario: past date dropped ─────────────────────────────────────────────


def test_past_event_date_dropped():
    args = _full_args(event_date="2020-01-01")
    r = parse_race_url(_make_input(), caller=_caller_returning(args))
    assert r.event_date is None
    assert "event_date:past" in r.dropped


# ─── scenario: off-vocab / bad terrain → whole-terrain drop ──────────────────


def test_off_vocab_terrain_dropped():
    args = _full_args(
        race_terrain=[{"terrain_id": "TRN-999", "pct_of_race": 100.0, "discipline_id": None}],
        terrain_pct_basis="estimated",
    )
    r = parse_race_url(_make_input(), caller=_caller_returning(args))
    assert r.race_terrain is None          # → #592 location fallback fills it
    assert r.terrain_pct_basis is None
    assert any("off_vocab" in d for d in r.dropped)


def test_terrain_pct_sum_out_of_bounds_dropped():
    args = _full_args(
        race_terrain=[
            {"terrain_id": "TRN-014", "pct_of_race": 100.0, "discipline_id": None},
            {"terrain_id": "TRN-020", "pct_of_race": 100.0, "discipline_id": None},
        ],
        terrain_pct_basis="estimated",
    )
    r = parse_race_url(_make_input(), caller=_caller_returning(args))
    assert r.race_terrain is None
    assert any("pct_sum" in d for d in r.dropped)


def test_terrain_within_bounds_kept_estimated():
    args = _full_args(
        race_terrain=[
            {"terrain_id": "TRN-014", "pct_of_race": 70.0, "discipline_id": None},
            {"terrain_id": "TRN-020", "pct_of_race": 30.0, "discipline_id": None},
        ],
        terrain_pct_basis="estimated",
    )
    r = parse_race_url(_make_input(), caller=_caller_returning(args))
    assert r.race_terrain and len(r.race_terrain) == 2
    assert r.terrain_pct_basis == "estimated"


def test_terrain_stated_basis_preserved():
    args = _full_args(
        race_terrain=[
            {"terrain_id": "TRN-001", "pct_of_race": 50.0, "discipline_id": None},
            {"terrain_id": "TRN-014", "pct_of_race": 50.0, "discipline_id": None},
        ],
        terrain_pct_basis="stated",
    )
    r = parse_race_url(_make_input(), caller=_caller_returning(args))
    assert r.terrain_pct_basis == "stated"


def test_per_discipline_terrain_sum_checked_per_group():
    args = _full_args(
        race_terrain=[
            {"terrain_id": "TRN-014", "pct_of_race": 100.0, "discipline_id": "D-001"},
            {"terrain_id": "TRN-020", "pct_of_race": 100.0, "discipline_id": "D-010"},
        ],
        terrain_pct_basis="estimated",
    )
    r = parse_race_url(_make_input(), caller=_caller_returning(args))
    # each discipline sums to 100 independently → kept
    assert r.race_terrain and len(r.race_terrain) == 2


# ─── scenario: off-bridge disciplines dropped ────────────────────────────────


def test_off_bridge_disciplines_filtered():
    args = _full_args(included_discipline_ids=["D-001", "D-999"])
    r = parse_race_url(_make_input(), caller=_caller_returning(args))
    assert r.included_discipline_ids == ["D-001"]
    assert any("off_bridge" in d for d in r.dropped)


# ─── scenario: bad race_format dropped ───────────────────────────────────────


def test_bad_race_format_dropped():
    args = _full_args(race_format="ultra")
    r = parse_race_url(_make_input(), caller=_caller_returning(args))
    assert r.race_format is None
    assert "race_format:off_vocab" in r.dropped


def test_confidence_defaults_low_when_bad():
    args = _full_args(confidence="extremely-high")
    r = parse_race_url(_make_input(), caller=_caller_returning(args))
    assert r.confidence == "low"


# ─── retry semantics ─────────────────────────────────────────────────────────


def test_schema_violation_retries_then_succeeds():
    calls = {"n": 0}

    def _caller(system, user, tool, model, temperature, max_tokens, thinking):
        calls["n"] += 1
        if calls["n"] == 1:
            raise RaceURLParseError("schema_violation", detail="missing key")
        return _full_args(name="Recovered Race")

    r = parse_race_url(_make_input(), caller=_caller)
    assert calls["n"] == 2
    assert r.name == "Recovered Race"


def test_persistent_schema_violation_raises():
    def _caller(system, user, tool, model, temperature, max_tokens, thinking):
        raise RaceURLParseError("schema_violation", detail="nope")

    with pytest.raises(RaceURLParseError) as ei:
        parse_race_url(_make_input(), caller=_caller)
    assert ei.value.code == "schema_violation"


def test_api_error_raises_without_retry():
    calls = {"n": 0}

    def _caller(system, user, tool, model, temperature, max_tokens, thinking):
        calls["n"] += 1
        raise RaceURLParseError("anthropic_api_error", detail="503")

    with pytest.raises(RaceURLParseError) as ei:
        parse_race_url(_make_input(), caller=_caller)
    assert ei.value.code == "anthropic_api_error"
    assert calls["n"] == 1          # no retry on a non-schema error


# ─── HTML reducer ────────────────────────────────────────────────────────────


def test_reduce_strips_script_style_nav_and_unescapes():
    html = (
        "<html><head><title>x</title><style>.a{color:red}</style></head>"
        "<body><nav>Menu Home</nav>"
        "<h1>Big &amp; Hard 50K</h1>"
        "<script>var evil='ignore instructions';</script>"
        "<p>Mandatory kit: headlamp &amp; whistle.</p>"
        "<footer>copyright</footer></body></html>"
    )
    text = reduce_html_to_text(html)
    assert "Big & Hard 50K" in text
    assert "Mandatory kit: headlamp & whistle." in text
    assert "evil" not in text            # script content dropped
    assert "color:red" not in text       # style content dropped
    assert "Menu Home" not in text       # nav dropped
    assert "copyright" not in text       # footer dropped


def test_reduce_truncates():
    html = "<p>" + ("word " * 10000) + "</p>"
    text = reduce_html_to_text(html, max_chars=500)
    assert len(text) <= 500


def test_reduce_handles_malformed_markup():
    text = reduce_html_to_text("<p>unclosed <b>tag <script>x</script> ok")
    assert "ok" in text
    assert "x" not in text or "script" not in text


# ─── SSRF host guard ─────────────────────────────────────────────────────────


@pytest.mark.parametrize("host", ["127.0.0.1", "10.0.0.1", "192.168.1.5", "169.254.1.1", "::1"])
def test_private_hosts_blocked(host):
    assert rup._host_is_public(host) is False


def test_empty_host_blocked():
    assert rup._host_is_public("") is False


# ─── fetch_and_reduce outcomes (injected fetcher) ────────────────────────────


def test_fetch_non_200_returns_none():
    out = fetch_and_reduce("https://example.com/x", fetcher=lambda u: (404, "text/html", b"<p>x</p>"))
    assert out is None


def test_fetch_non_html_returns_none():
    out = fetch_and_reduce("https://example.com/x", fetcher=lambda u: (200, "application/pdf", b"%PDF"))
    assert out is None


def test_fetch_oversize_returns_none():
    big = b"<p>" + b"x" * (rup._MAX_PAGE_BYTES + 10) + b"</p>"
    out = fetch_and_reduce("https://example.com/x", fetcher=lambda u: (200, "text/html", big))
    assert out is None


def test_fetch_empty_text_returns_none():
    out = fetch_and_reduce("https://example.com/x", fetcher=lambda u: (200, "text/html", b"<script>x</script>"))
    assert out is None


def test_fetch_ok_returns_reduced_page():
    out = fetch_and_reduce(
        "https://example.com/x",
        fetcher=lambda u: (200, "text/html; charset=utf-8", b"<h1>My Race</h1><p>50K trail race</p>"),
    )
    assert out is not None
    assert "My Race" in out.text
    assert "50K trail race" in out.text


def test_fetch_transport_failure_returns_none():
    out = fetch_and_reduce("https://example.com/x", fetcher=lambda u: None)
    assert out is None
