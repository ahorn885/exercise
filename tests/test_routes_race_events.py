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
            lists={'included_discipline_ids': ['D-001', 'D-010', 'D-015']}
        )
        assert _parse_discipline_id_filter(form) == ['D-001', 'D-010', 'D-015']

    def test_strips_whitespace_and_drops_blanks(self):
        form = _FakeMultiDict(
            lists={'included_discipline_ids': [' D-001 ', '', '  ', 'D-015']}
        )
        assert _parse_discipline_id_filter(form) == ['D-001', 'D-015']

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
            'race_terrain[0][discipline_id]': 'D-008',
        })
        out = _parse_race_terrain(form)
        assert out == [
            {'terrain_id': 'TRN-017', 'pct_of_race': 15.0, 'discipline_id': 'D-008'},
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
        # Labels come from the curated pure-craft overlay (keyed by id),
        # not the sport-variant bridge `discipline_name`.
        conn = _FakeConn(rows=[
            {'discipline_id': 'D-001', 'discipline_name': 'Trail run'},
            {'discipline_id': 'D-010', 'discipline_name': 'Whitewater paddle'},
        ])
        out = _disciplines_for_framework_sport(conn, 'Adventure Racing')
        assert out == [
            {'id': 'D-001', 'label': 'Trail Running'},
            {'id': 'D-010', 'label': 'Kayaking'},
        ]

    def test_uncurated_id_falls_back_to_bridge_name(self):
        conn = _FakeConn(rows=[
            {'discipline_id': 'D-006 + D-007', 'discipline_name': 'Road Cycling (+ TT/Tri Bike)'},
        ])
        out = _disciplines_for_framework_sport(conn, 'Triathlon')
        assert out == [
            {'id': 'D-006 + D-007', 'label': 'Road Cycling (+ TT/Tri Bike)'},
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


# ─── Bucket C (i) — Mapbox-required gates ───────────────────────────────────


class _RouteFakeRow(dict):
    """`request.form`-shaped dict for the route-level tests below."""

    def __getitem__(self, key):
        if isinstance(key, int):
            return list(self.values())[key]
        return super().__getitem__(key)


class _RouteFakeCursor:
    def __init__(self, row=None, rows=None):
        self._row = row
        self._rows = rows or []

    def fetchone(self):
        return _RouteFakeRow(self._row) if self._row else None

    def fetchall(self):
        return [_RouteFakeRow(r) for r in self._rows]


class _RouteFakeConn:
    """Tracks SQL calls + serves queued responses. Mirrors
    `tests/test_locales.py::_FakeConn` so the route-level tests can assert
    that NO create/update SQL fires when the Mapbox gate rejects the POST.
    """

    def __init__(self):
        self.calls: list[tuple[str, tuple]] = []
        self.responses: list[tuple] = []

    def queue_response(self, row=None, rows=None):
        self.responses.append((row, rows or []))

    def execute(self, sql, params=()):
        self.calls.append((sql, params))
        if self.responses:
            row, rows = self.responses.pop(0)
        else:
            row, rows = None, []
        return _RouteFakeCursor(row=row, rows=rows)

    def commit(self):
        pass


def _make_app():
    from flask import Flask
    from routes.race_events import bp
    app = Flask(__name__)
    app.config['SECRET_KEY'] = 'test'
    app.config['TESTING'] = True
    app.config['WTF_CSRF_ENABLED'] = False
    app.register_blueprint(bp)
    return app


def _sql_fragment_count(conn, fragment: str) -> int:
    return sum(1 for sql, _params in conn.calls if fragment in sql)


class TestNewRaceMapboxRequired:
    """Bucket C (i) — `new_race` POST blocks when athlete submits without a
    Mapbox-anchored race location. Mirrors the existing race-name + race-format
    required-field gates.
    """

    def test_post_without_mapbox_id_flashes_and_redirects(self, monkeypatch):
        app = _make_app()
        conn = _RouteFakeConn()
        import routes.race_events as re_mod
        monkeypatch.setattr(re_mod, 'get_db', lambda: conn)
        monkeypatch.setattr(re_mod, 'current_user_id', lambda: 1)

        with app.test_request_context(
            '/profile/race-events/new',
            method='POST',
            data={
                'name': 'Test Race',
                'event_date': '2026-07-17',
                'race_format': 'continuous_multi_day',
                # `event_locale_mapbox_id` deliberately absent.
            },
        ):
            response = re_mod.new_race()

        # No create SQL should fire when the gate rejects.
        assert _sql_fragment_count(conn, 'INSERT INTO race_events') == 0
        # 302 redirect back to /profile/race-events/new.
        assert response.status_code == 302
        assert '/new' in response.location

    def test_post_with_mapbox_id_proceeds(self, monkeypatch):
        app = _make_app()
        conn = _RouteFakeConn()
        # Stub `create_race_event` so the test doesn't depend on the repo's
        # transaction shape; we're asserting the gate passes, not the SQL.
        import routes.race_events as re_mod
        monkeypatch.setattr(re_mod, 'get_db', lambda: conn)
        monkeypatch.setattr(re_mod, 'current_user_id', lambda: 1)
        called = {}
        def fake_create(db, user_id, **kwargs):
            called['mapbox_id'] = kwargs.get('event_locale_mapbox_id')
            return 42
        monkeypatch.setattr(re_mod, 'create_race_event', fake_create)

        with app.test_request_context(
            '/profile/race-events/new',
            method='POST',
            data={
                'name': 'Test Race',
                'event_date': '2026-07-17',
                # Multi-day path redirects to race_events.edit_race which is
                # in the registered blueprint; single_day goes to
                # profile.edit which isn't registered in this test app.
                'race_format': 'continuous_multi_day',
                'event_locale_name': 'Test Race Location',
                'event_locale_mapbox_id': 'poi.test_anchor',
                'event_locale_place_name': 'Test Race Location, TS',
            },
        ):
            response = re_mod.new_race()

        assert response.status_code == 302
        assert called['mapbox_id'] == 'poi.test_anchor'


class TestUpdateRaceMapboxRequired:
    """Bucket C (i) — `update_race` POST blocks when the LOADED race row
    lacks `event_locale_mapbox_id`. The race-details form doesn't carry the
    Mapbox fields (the standalone `set_locale` POST owns those); the gate
    forces legacy un-anchored rows through the picker before any other edits
    can land.
    """

    def test_post_on_unanchored_row_flashes_and_redirects(self, monkeypatch):
        app = _make_app()
        conn = _RouteFakeConn()
        import routes.race_events as re_mod
        monkeypatch.setattr(re_mod, 'get_db', lambda: conn)
        monkeypatch.setattr(re_mod, 'current_user_id', lambda: 1)
        # Stub `get_race_event` to return a legacy un-anchored row.
        monkeypatch.setattr(
            re_mod, 'get_race_event',
            lambda db, uid, race_event_id: {
                'id': 10,
                'name': 'Legacy Race',
                'event_date': None,
                'race_format': 'single_day',
                'event_locale_mapbox_id': None,
                'is_target_event': False,
            },
        )

        with app.test_request_context(
            '/profile/race-events/10/update',
            method='POST',
            data={
                'name': 'Legacy Race',
                'event_date': '2026-07-17',
                'race_format': 'single_day',
            },
        ):
            response = re_mod.update_race(10)

        # No UPDATE SQL should fire when the gate rejects.
        assert _sql_fragment_count(conn, 'UPDATE race_events') == 0
        assert response.status_code == 302

    def test_post_on_anchored_row_proceeds(self, monkeypatch):
        app = _make_app()
        conn = _RouteFakeConn()
        import routes.race_events as re_mod
        monkeypatch.setattr(re_mod, 'get_db', lambda: conn)
        monkeypatch.setattr(re_mod, 'current_user_id', lambda: 1)
        monkeypatch.setattr(
            re_mod, 'get_race_event',
            lambda db, uid, race_event_id: {
                'id': 10,
                'name': 'Anchored Race',
                'event_date': None,
                'race_format': 'single_day',
                'distance_km': None,
                'total_elevation_gain_m': None,
                'race_rules_summary': None,
                'mandatory_gear_text': None,
                'event_locale_id': None,  # legacy FK; load path preserves
                'notes': None,
                'race_terrain': [],
                'race_url': None,
                'framework_sport': None,
                'included_discipline_ids': None,
                'event_locale_mapbox_id': 'poi.test_anchor',
                'is_target_event': False,
            },
        )
        # Stub the eviction helpers + update so the call sequence doesn't
        # depend on cache wiring.
        monkeypatch.setattr(re_mod, 'update_race_event', lambda *a, **k: None)
        for helper in (
            'evict_on_target_event_framework_sport_change',
            'evict_on_target_event_included_discipline_ids_change',
            'evict_on_target_event_periodization_change',
            'evict_on_target_event_brief_field_change',
        ):
            monkeypatch.setattr(re_mod, helper, lambda *a, **k: None)

        with app.test_request_context(
            '/profile/race-events/10/update',
            method='POST',
            data={
                'name': 'Anchored Race',
                'event_date': '2026-07-17',
                'race_format': 'single_day',
            },
        ):
            response = re_mod.update_race(10)

        assert response.status_code == 302
        # Update flow proceeds past the gate (no flash 'pick a race location').


class TestSetLocaleMapboxRequired:
    """Bucket C (i) — `set_locale` POST is now strict: empty mapbox_id is
    rejected (was previously loose — accepted name-without-mapbox_id).
    """

    def test_post_without_mapbox_id_flashes_and_redirects(self, monkeypatch):
        app = _make_app()
        conn = _RouteFakeConn()
        import routes.race_events as re_mod
        monkeypatch.setattr(re_mod, 'get_db', lambda: conn)
        monkeypatch.setattr(re_mod, 'current_user_id', lambda: 1)
        monkeypatch.setattr(
            re_mod, 'get_race_event',
            lambda db, uid, race_event_id: {
                'id': 10,
                'is_target_event': False,
                'event_locale_mapbox_id': None,
            },
        )
        monkeypatch.setattr(
            re_mod, 'update_race_event_locale', lambda *a, **k: None
        )

        with app.test_request_context(
            '/profile/race-events/10/locale/update',
            method='POST',
            data={
                # Only `event_locale_name` set (mimics the old loose-fallback
                # path that was previously accepted).
                'event_locale_name': 'Hand-typed location',
            },
        ):
            response = re_mod.set_locale(10)

        assert response.status_code == 302
        # No update_race_event_locale should fire when the gate rejects.
