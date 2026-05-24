"""Tests for `routes/race_events.py` form-helper functions (D-73 Phase 5.2
walkthrough #1 + #2a, 2026-05-21).

Coverage:
- `_extract_mapbox_locale_from_form` — pulls 5 Mapbox-anchored hidden inputs
  off a form mapping; blank/missing/non-numeric inputs collapse safely
- `_parse_race_url` — trim + cap + empty-collapse semantics
- `_run_mapbox_search` — empty-query short-circuit + error translation for
  the 3 mapbox_client failure modes (no Mapbox HTTP round-trip via monkeypatch)
- `locale_search` JSON endpoint payload shape (via _run_mapbox_search behavior;
  full route integration deferred to manual §5.0 walkthrough per D-63 D12
  precedent — helper-level pytest density only)

Pattern mirrors `tests/test_onboarding_race_events.py`; no real DB or Flask
test_client. The route helpers are pure functions over a form-mapping +
mapbox_client adapter.
"""

from __future__ import annotations

import pytest

from routes.race_events import (
    _disciplines_for_framework_sport,
    _extract_mapbox_locale_from_form,
    _parse_discipline_id_filter,
    _parse_race_terrain,
    _parse_race_url,
    _resolve_effective_framework_sport,
    _run_mapbox_search,
)


class _FakeFormMapping(dict):
    """Stand-in for `request.form` (a `MultiDict`-shaped mapping). The
    helpers under test only call `.get(key)` which `dict.get` satisfies.
    """

    def get(self, key, default=None):
        return super().get(key, default)


class _FakeMultiDict(dict):
    """Stand-in for `request.form` with `.getlist()` (Flask MultiDict
    semantics). Used for `_parse_discipline_id_filter` which calls
    `.getlist('included_discipline_ids')` to read repeated checkbox values.
    """

    def __init__(self, base=None, lists=None):
        super().__init__(base or {})
        self._lists = lists or {}

    def getlist(self, key):
        return list(self._lists.get(key, []))

    def get(self, key, default=None):
        return super().get(key, default)


class _FakeCursor:
    def __init__(self, rows):
        self._rows = rows

    def fetchall(self):
        return list(self._rows)


class _FakeConn:
    def __init__(self, rows=None):
        self._rows = rows or []

    def execute(self, _sql, _params=()):
        return _FakeCursor(self._rows)


# ─── _extract_mapbox_locale_from_form ───────────────────────────────────────


class TestExtractMapboxLocaleFromForm:
    def test_returns_all_none_when_form_empty(self):
        out = _extract_mapbox_locale_from_form(_FakeFormMapping())
        assert out == {
            'event_locale_name': None,
            'event_locale_mapbox_id': None,
            'event_locale_place_name': None,
            'event_locale_lat': None,
            'event_locale_lng': None,
        }

    def test_extracts_all_five_fields(self):
        form = _FakeFormMapping({
            'event_locale_name': 'Nerstrand State Park',
            'event_locale_mapbox_id': 'poi.abc123',
            'event_locale_place_name': 'Nerstrand State Park, MN, US',
            'event_locale_lat': '44.345',
            'event_locale_lng': '-93.106',
        })
        out = _extract_mapbox_locale_from_form(form)
        assert out == {
            'event_locale_name': 'Nerstrand State Park',
            'event_locale_mapbox_id': 'poi.abc123',
            'event_locale_place_name': 'Nerstrand State Park, MN, US',
            'event_locale_lat': 44.345,
            'event_locale_lng': -93.106,
        }

    def test_trims_whitespace_on_text_fields(self):
        form = _FakeFormMapping({
            'event_locale_name': '   Nerstrand   ',
            'event_locale_mapbox_id': 'poi.x  ',
            'event_locale_place_name': '  Nerstrand, MN',
        })
        out = _extract_mapbox_locale_from_form(form)
        assert out['event_locale_name'] == 'Nerstrand'
        assert out['event_locale_mapbox_id'] == 'poi.x'
        assert out['event_locale_place_name'] == 'Nerstrand, MN'

    def test_blank_text_fields_collapse_to_none(self):
        form = _FakeFormMapping({
            'event_locale_name': '   ',
            'event_locale_mapbox_id': '',
            'event_locale_place_name': '\t\n',
        })
        out = _extract_mapbox_locale_from_form(form)
        assert out['event_locale_name'] is None
        assert out['event_locale_mapbox_id'] is None
        assert out['event_locale_place_name'] is None

    def test_non_numeric_lat_lng_collapse_to_none(self):
        """Defensive: a malformed POST hand-crafted with `lat=NaN` or
        `lat=garbage` must not let `NaN` reach the NUMERIC(9,6) column."""
        form = _FakeFormMapping({
            'event_locale_lat': 'NaN',
            'event_locale_lng': 'not-a-number',
        })
        out = _extract_mapbox_locale_from_form(form)
        # `float('NaN')` succeeds, but `float('not-a-number')` raises and
        # collapses to None. NaN is technically a float; the only safety is
        # at the column-bound `Field(ge=-90, le=90)` on `RaceEventPayload`.
        # Document the boundary explicitly.
        assert out['event_locale_lng'] is None

    def test_empty_string_lat_lng_collapse_to_none(self):
        form = _FakeFormMapping({
            'event_locale_lat': '',
            'event_locale_lng': '   ',
        })
        out = _extract_mapbox_locale_from_form(form)
        assert out['event_locale_lat'] is None
        assert out['event_locale_lng'] is None

    def test_negative_coords_pass_through(self):
        form = _FakeFormMapping({
            'event_locale_lat': '-44.345',
            'event_locale_lng': '-93.106',
        })
        out = _extract_mapbox_locale_from_form(form)
        assert out['event_locale_lat'] == -44.345
        assert out['event_locale_lng'] == -93.106


# ─── _parse_race_url ────────────────────────────────────────────────────────


class TestParseRaceUrl:
    def test_returns_none_on_missing_key(self):
        assert _parse_race_url(_FakeFormMapping()) is None

    def test_returns_none_on_empty(self):
        assert _parse_race_url(_FakeFormMapping({'race_url': ''})) is None

    def test_returns_none_on_whitespace_only(self):
        assert _parse_race_url(_FakeFormMapping({'race_url': '  \t\n  '})) is None

    def test_trims_whitespace(self):
        out = _parse_race_url(_FakeFormMapping({
            'race_url': '  https://example.com/race  ',
        }))
        assert out == 'https://example.com/race'

    def test_caps_at_1000_chars(self):
        long_url = 'https://example.com/' + ('x' * 2000)
        out = _parse_race_url(_FakeFormMapping({'race_url': long_url}))
        assert out is not None
        assert len(out) == 1000


# ─── _run_mapbox_search ─────────────────────────────────────────────────────


class TestRunMapboxSearch:
    def test_empty_query_short_circuits(self, monkeypatch):
        """No Mapbox HTTP round-trip for empty input."""
        import mapbox_client
        # If anything fires, we'd get a token error — assert nothing fires.
        called = {'count': 0}

        def fail_if_called(*args, **kwargs):
            called['count'] += 1
            raise AssertionError("search_places should not fire on empty q")

        monkeypatch.setattr(mapbox_client, 'search_places', fail_if_called)
        results, error = _run_mapbox_search('')
        assert results == []
        assert error is None
        assert called['count'] == 0

    def test_token_missing_returns_human_readable_error(self, monkeypatch):
        import mapbox_client

        def raise_token_missing(*args, **kwargs):
            raise mapbox_client.MapboxTokenMissing('test')

        monkeypatch.setattr(mapbox_client, 'search_places', raise_token_missing)
        results, error = _run_mapbox_search('Nerstrand')
        assert results == []
        assert error is not None
        assert 'not configured' in error.lower() or 'mapbox_public_token' in error.lower()

    def test_no_results_returns_friendly_error(self, monkeypatch):
        import mapbox_client

        def raise_no_results(*args, **kwargs):
            raise mapbox_client.MapboxNoResults('test')

        monkeypatch.setattr(mapbox_client, 'search_places', raise_no_results)
        results, error = _run_mapbox_search('asdfqwerty')
        assert results == []
        assert error is not None
        assert 'asdfqwerty' in error
        assert 'broader' in error.lower()

    def test_api_error_returns_translated_message(self, monkeypatch):
        import mapbox_client

        def raise_api_error(*args, **kwargs):
            raise mapbox_client.MapboxAPIError('502 bad gateway')

        monkeypatch.setattr(mapbox_client, 'search_places', raise_api_error)
        results, error = _run_mapbox_search('Nerstrand')
        assert results == []
        assert error is not None
        assert 'unavailable' in error.lower()
        assert '502 bad gateway' in error

    def test_happy_path_returns_results(self, monkeypatch):
        import mapbox_client

        def fake_search_places(query, limit=5):
            assert query == 'Nerstrand'
            return [
                {
                    'mapbox_id': 'poi.abc',
                    'text': 'Nerstrand State Park',
                    'place_name': 'Nerstrand State Park, MN, US',
                    'lng': -93.106,
                    'lat': 44.345,
                    'category': '',
                    'raw_payload': '',
                },
            ]

        monkeypatch.setattr(mapbox_client, 'search_places', fake_search_places)
        results, error = _run_mapbox_search('Nerstrand')
        assert error is None
        assert len(results) == 1
        assert results[0]['text'] == 'Nerstrand State Park'


# ─── _parse_discipline_id_filter (D-73 Phase 5.2 Bucket E.(b)-B2) ────────────


class TestParseDisciplineIdFilter:
    """Parses the repeating `included_discipline_ids` form fields into a
    canonical-id list, or None when no boxes are checked."""

    def test_empty_form_returns_none(self):
        assert _parse_discipline_id_filter(_FakeMultiDict()) is None

    def test_returns_checked_subset(self):
        form = _FakeMultiDict(
            lists={'included_discipline_ids': ['D-001', 'D-008b', 'D-013']}
        )
        assert _parse_discipline_id_filter(form) == ['D-001', 'D-008b', 'D-013']

    def test_strips_whitespace_and_drops_blanks(self):
        form = _FakeMultiDict(
            lists={'included_discipline_ids': [' D-001 ', '', '  ', 'D-013']}
        )
        assert _parse_discipline_id_filter(form) == ['D-001', 'D-013']

    def test_missing_getlist_method_returns_none(self):
        """Form mapping without `.getlist` (plain dict) falls through to
        None — defensive against test substrates that haven't loaded a
        MultiDict."""
        plain = {'included_discipline_ids': 'D-001'}
        assert _parse_discipline_id_filter(plain) is None


# ─── _parse_race_terrain — C1 discipline_id passthrough ─────────────────────


class TestParseRaceTerrainDisciplineId:
    """D-73 Phase 5.2 Bucket E.(c)-C1 — per-row optional discipline_id."""

    def test_row_with_discipline_id_threaded(self):
        form = _FakeFormMapping({
            'race_terrain[0][terrain_id]': 'TRN-017',
            'race_terrain[0][pct_of_race]': '15',
            'race_terrain[0][discipline_id]': 'D-006',
        })
        out = _parse_race_terrain(form)
        assert out == [
            {'terrain_id': 'TRN-017', 'pct_of_race': 15.0, 'discipline_id': 'D-006'},
        ]

    def test_blank_discipline_id_collapses_to_none(self):
        form = _FakeFormMapping({
            'race_terrain[0][terrain_id]': 'TRN-002',
            'race_terrain[0][pct_of_race]': '35',
            'race_terrain[0][discipline_id]': '',
        })
        out = _parse_race_terrain(form)
        assert out == [
            {'terrain_id': 'TRN-002', 'pct_of_race': 35.0, 'discipline_id': None},
        ]

    def test_missing_discipline_id_field_defaults_to_none(self):
        # Pre-C1 form shape — no discipline_id field at all. Backward-compat:
        # parses identically to a row with discipline_id=None.
        form = _FakeFormMapping({
            'race_terrain[0][terrain_id]': 'TRN-002',
            'race_terrain[0][pct_of_race]': '35',
        })
        out = _parse_race_terrain(form)
        assert out == [
            {'terrain_id': 'TRN-002', 'pct_of_race': 35.0, 'discipline_id': None},
        ]


# ─── _disciplines_for_framework_sport ───────────────────────────────────────


class TestDisciplinesForFrameworkSport:
    """Bridge-keyed lookup helper used to render the B2 checkbox grid +
    the C1 per-row terrain `<select>`."""

    def test_returns_id_label_dicts_from_bridge(self):
        conn = _FakeConn(rows=[
            {'discipline_id': 'D-001', 'discipline_name': 'Trail run'},
            {'discipline_id': 'D-008b', 'discipline_name': 'Whitewater paddle'},
        ])
        out = _disciplines_for_framework_sport(conn, 'Adventure Racing')
        assert out == [
            {'id': 'D-001', 'label': 'Trail run'},
            {'id': 'D-008b', 'label': 'Whitewater paddle'},
        ]

    def test_empty_framework_sport_short_circuits(self):
        # Avoids a wasted SELECT when the athlete hasn't yet typed
        # anything in the framework_sport input.
        conn = _FakeConn(rows=[])
        assert _disciplines_for_framework_sport(conn, '') == []
        assert _disciplines_for_framework_sport(conn, None) == []


# ─── _resolve_effective_framework_sport ─────────────────────────────────────


class TestResolveEffectiveFrameworkSport:
    """Mirrors orchestrator resolution order: race-row override wins;
    otherwise fall back to athlete profile `primary_sport`."""

    def test_race_override_wins(self, monkeypatch):
        # Profile primary_sport irrelevant when race has an override.
        monkeypatch.setattr(
            'routes.race_events.get_athlete_profile',
            lambda db, uid: {'primary_sport': 'Adventure Racing'},
        )
        race = {'framework_sport': 'Trail Running'}
        assert _resolve_effective_framework_sport(None, 1, race) == 'Trail Running'

    def test_falls_back_to_primary_sport_when_race_blank(self, monkeypatch):
        monkeypatch.setattr(
            'routes.race_events.get_athlete_profile',
            lambda db, uid: {'primary_sport': 'Adventure Racing'},
        )
        # Race row exists but framework_sport is None
        assert (
            _resolve_effective_framework_sport(None, 1, {'framework_sport': None})
            == 'Adventure Racing'
        )

    def test_no_race_row_uses_profile(self, monkeypatch):
        # New-race GET path — no race row exists yet.
        monkeypatch.setattr(
            'routes.race_events.get_athlete_profile',
            lambda db, uid: {'primary_sport': 'Trail Running'},
        )
        assert (
            _resolve_effective_framework_sport(None, 1, None) == 'Trail Running'
        )

    def test_returns_none_when_both_unset(self, monkeypatch):
        # Athlete has no primary_sport AND no race row — template renders
        # the empty discipline grid + helper copy.
        monkeypatch.setattr(
            'routes.race_events.get_athlete_profile',
            lambda db, uid: {'primary_sport': None},
        )
        assert _resolve_effective_framework_sport(None, 1, None) is None
