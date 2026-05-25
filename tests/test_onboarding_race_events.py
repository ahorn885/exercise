"""Tests for `routes/onboarding.py` D-66 §H.2 + §H.4 helpers + flow.

The onboarding routes themselves consume the well-tested
`race_events_repo` helpers; this file exercises the new onboarding-local
glue:
- Form-input parsers (`_parse_str_field` / `_parse_decimal_field` /
  `_parse_date_field` / `_parse_int_field`) — coercion + empty/invalid
  handling, mirroring the same-named helpers in `routes/race_events.py`.
- `_get_target_race_row(db, uid)` — SELECT shape + dict return on hit +
  None on miss (no target row for this user).
- `_athlete_locale_choices(db, uid)` — SELECT shape + dict return shape +
  COALESCE-driven label fallback (locale_name → locale slug).
- `_write_account_nudge(db, uid, nudge_type)` — INSERT ... ON CONFLICT
  DO NOTHING shape for the (user_id, nudge_type) idempotence.

All tests use the `_FakeConn` / `_FakeCursor` pattern from
`tests/test_race_events_repo.py` — no real DB connection.

End-to-end route walkthrough (GET /onboarding/target-race, POST flows
including the multi-day → route-locales branch + skip nudges) is
captured in the PR's §5.0 manual verification steps rather than pytest
fixtures — matches the precedent set by `routes/race_events.py` (PR for
which also smoke-tested templates inline + deferred route-level pytest
to manual walkthrough).
"""

from __future__ import annotations

from datetime import date

import pytest

from routes.onboarding import (
    _get_target_race_row,
    _parse_date_field,
    _parse_decimal_field,
    _parse_int_field,
    _parse_race_terrain,
    _parse_str_field,
    _terrain_choices,
    _write_account_nudge,
)


# ─── Shared fake conn ───────────────────────────────────────────────────────


class _FakeRow(dict):
    def __getitem__(self, key):
        if isinstance(key, int):
            return list(self.values())[key]
        return super().__getitem__(key)


class _FakeCursor:
    def __init__(self, row=None, rows=None):
        self._row = row
        self._rows = rows or []

    def fetchone(self):
        return _FakeRow(self._row) if self._row else None

    def fetchall(self):
        return [_FakeRow(r) for r in self._rows]


class _FakeConn:
    """Same shape as `tests/test_race_events_repo.py` _FakeConn — captures
    each execute(sql, params) call + lets the test seed responses in order.
    """

    def __init__(self):
        self.calls: list[tuple[str, tuple]] = []
        self.commits: int = 0
        self.responses: list[tuple] = []

    def queue_response(self, row=None, rows=None):
        self.responses.append((row, rows or []))

    def execute(self, sql, params=()):
        self.calls.append((sql, params))
        if self.responses:
            row, rows = self.responses.pop(0)
        else:
            row, rows = None, []
        return _FakeCursor(row=row, rows=rows)

    def commit(self):
        self.commits += 1


# ─── Form-input parsers ─────────────────────────────────────────────────────


class TestParseStrField:
    def test_returns_stripped_value(self):
        assert _parse_str_field({'name': '  hello  '}, 'name') == 'hello'

    def test_empty_returns_none(self):
        assert _parse_str_field({'name': ''}, 'name') is None
        assert _parse_str_field({'name': '   '}, 'name') is None

    def test_missing_key_returns_none(self):
        assert _parse_str_field({}, 'name') is None


class TestParseDecimalField:
    def test_returns_float(self):
        assert _parse_decimal_field({'x': '42.5'}, 'x') == 42.5

    def test_empty_returns_none(self):
        assert _parse_decimal_field({'x': ''}, 'x') is None

    def test_invalid_returns_none(self):
        assert _parse_decimal_field({'x': 'abc'}, 'x') is None

    def test_missing_returns_none(self):
        assert _parse_decimal_field({}, 'x') is None


class TestParseDateField:
    def test_returns_date(self):
        assert _parse_date_field({'d': '2026-07-17'}, 'd') == date(2026, 7, 17)

    def test_empty_returns_none(self):
        assert _parse_date_field({'d': ''}, 'd') is None

    def test_invalid_returns_none(self):
        assert _parse_date_field({'d': 'not-a-date'}, 'd') is None
        # Mid-month-out-of-range — Python rejects.
        assert _parse_date_field({'d': '2026-13-99'}, 'd') is None

    def test_missing_returns_none(self):
        assert _parse_date_field({}, 'd') is None


class TestParseIntField:
    def test_returns_int(self):
        assert _parse_int_field({'n': '7'}, 'n') == 7

    def test_empty_returns_none(self):
        assert _parse_int_field({'n': ''}, 'n') is None

    def test_invalid_returns_none(self):
        assert _parse_int_field({'n': 'abc'}, 'n') is None
        # Float-like input rejected — we expect int() coercion only.
        assert _parse_int_field({'n': '3.14'}, 'n') is None

    def test_missing_returns_none(self):
        assert _parse_int_field({}, 'n') is None


# ─── _get_target_race_row ───────────────────────────────────────────────────


class TestGetTargetRaceRow:
    def test_returns_dict_on_hit(self):
        conn = _FakeConn()
        conn.queue_response(row={
            'id': 5,
            'name': 'Pocket Gopher Extreme',
            'event_date': date(2026, 7, 17),
            'race_format': 'continuous_multi_day',
            'distance_km': 320.5,
            'total_elevation_gain_m': 4800,
            'race_rules_summary': 'Time cut 56h',
            'mandatory_gear_text': 'Helmet, headlamp, PFD',
            'event_locale_id': None,
            'notes': None,
            'race_terrain': [],
            'aid_stations': 0,
        })

        out = _get_target_race_row(conn, uid=42)
        assert out is not None
        assert out['id'] == 5
        assert out['name'] == 'Pocket Gopher Extreme'
        assert out['race_format'] == 'continuous_multi_day'
        assert out['race_terrain'] == []
        assert out['aid_stations'] == 0

        # WHERE clause must scope by user_id AND is_target_event=TRUE.
        # SELECT must include race_terrain + aid_stations so the edit
        # form pre-populates on return-visits and the brief-only cache
        # diff can compare prior values.
        sql, params = conn.calls[0]
        assert 'WHERE user_id = ? AND is_target_event = TRUE' in sql
        assert 'race_terrain' in sql
        assert 'aid_stations' in sql
        assert params == (42,)

    def test_returns_none_on_miss(self):
        conn = _FakeConn()
        conn.queue_response(row=None)
        assert _get_target_race_row(conn, uid=42) is None

    def test_hydrates_race_terrain_from_jsonb_string(self):
        """psycopg2 returns JSONB as native list, sqlite shim returns a
        JSON-encoded string. `_get_target_race_row` tolerates both and
        hydrates to a list of dicts in either case.
        """
        conn = _FakeConn()
        conn.queue_response(row={
            'id': 7,
            'name': 'Race',
            'event_date': date(2026, 7, 17),
            'race_format': 'continuous_multi_day',
            'distance_km': None,
            'total_elevation_gain_m': None,
            'race_rules_summary': None,
            'mandatory_gear_text': None,
            'event_locale_id': None,
            'notes': None,
            'race_terrain': '[{"terrain_id": "TRN-002", "pct_of_race": 35.0}]',
            'aid_stations': None,
        })

        out = _get_target_race_row(conn, uid=42)
        assert out['race_terrain'] == [{'terrain_id': 'TRN-002', 'pct_of_race': 35.0}]

    def test_hydrates_race_terrain_from_native_list(self):
        """psycopg2 default JSONB adapter returns a list directly — the
        hydration should leave it untouched.
        """
        conn = _FakeConn()
        terrain = [
            {'terrain_id': 'TRN-002', 'pct_of_race': 35.0},
            {'terrain_id': 'TRN-003', 'pct_of_race': 30.0},
        ]
        conn.queue_response(row={
            'id': 7,
            'name': 'Race',
            'event_date': date(2026, 7, 17),
            'race_format': 'continuous_multi_day',
            'distance_km': None,
            'total_elevation_gain_m': None,
            'race_rules_summary': None,
            'mandatory_gear_text': None,
            'event_locale_id': None,
            'notes': None,
            'race_terrain': terrain,
            'aid_stations': 4,
        })

        out = _get_target_race_row(conn, uid=42)
        assert out['race_terrain'] == terrain
        assert out['aid_stations'] == 4

    def test_hydrates_none_race_terrain_to_empty_list(self):
        """NULL race_terrain (no migration yet, or row pre-form-refresh)
        falls back to empty list so the template iteration + diff
        comparison never hit a NoneType.
        """
        conn = _FakeConn()
        conn.queue_response(row={
            'id': 7,
            'name': 'Race',
            'event_date': date(2026, 7, 17),
            'race_format': 'continuous_multi_day',
            'distance_km': None,
            'total_elevation_gain_m': None,
            'race_rules_summary': None,
            'mandatory_gear_text': None,
            'event_locale_id': None,
            'notes': None,
            'race_terrain': None,
            'aid_stations': None,
        })

        out = _get_target_race_row(conn, uid=42)
        assert out['race_terrain'] == []
        assert out['aid_stations'] is None


# ─── _parse_race_terrain ────────────────────────────────────────────────────


class TestParseRaceTerrain:
    def test_parses_repeating_rows(self):
        form = {
            'race_terrain[0][terrain_id]': 'TRN-002',
            'race_terrain[0][pct_of_race]': '35',
            'race_terrain[1][terrain_id]': 'TRN-003',
            'race_terrain[1][pct_of_race]': '30.5',
        }
        out = _parse_race_terrain(form)
        # D-73 Phase 5.2 Bucket E.(c)-C1 — every row now carries
        # `discipline_id` (None default when the form field is absent).
        assert out == [
            {'terrain_id': 'TRN-002', 'pct_of_race': 35.0, 'discipline_id': None},
            {'terrain_id': 'TRN-003', 'pct_of_race': 30.5, 'discipline_id': None},
        ]

    def test_empty_form_returns_empty_list(self):
        assert _parse_race_terrain({}) == []

    def test_drops_empty_terrain_id(self):
        form = {
            'race_terrain[0][terrain_id]': '',
            'race_terrain[0][pct_of_race]': '35',
            'race_terrain[1][terrain_id]': 'TRN-002',
            'race_terrain[1][pct_of_race]': '30',
        }
        out = _parse_race_terrain(form)
        assert out == [
            {'terrain_id': 'TRN-002', 'pct_of_race': 30.0, 'discipline_id': None},
        ]

    def test_drops_empty_pct(self):
        form = {
            'race_terrain[0][terrain_id]': 'TRN-002',
            'race_terrain[0][pct_of_race]': '',
        }
        assert _parse_race_terrain(form) == []

    def test_drops_invalid_terrain_id_pattern(self):
        # Wrong shape — not TRN-\d{3}.
        form = {
            'race_terrain[0][terrain_id]': 'TERRAIN-002',
            'race_terrain[0][pct_of_race]': '35',
            'race_terrain[1][terrain_id]': 'TRN-2',
            'race_terrain[1][pct_of_race]': '30',
        }
        assert _parse_race_terrain(form) == []

    def test_drops_non_numeric_pct(self):
        form = {
            'race_terrain[0][terrain_id]': 'TRN-002',
            'race_terrain[0][pct_of_race]': 'thirty',
        }
        assert _parse_race_terrain(form) == []

    def test_drops_out_of_range_pct(self):
        form = {
            'race_terrain[0][terrain_id]': 'TRN-002',
            'race_terrain[0][pct_of_race]': '-5',
            'race_terrain[1][terrain_id]': 'TRN-003',
            'race_terrain[1][pct_of_race]': '120',
        }
        assert _parse_race_terrain(form) == []

    def test_preserves_sorted_order_across_sparse_indices(self):
        # Form rows can have gaps after a user removed a middle row in JS.
        form = {
            'race_terrain[5][terrain_id]': 'TRN-009',
            'race_terrain[5][pct_of_race]': '15',
            'race_terrain[0][terrain_id]': 'TRN-002',
            'race_terrain[0][pct_of_race]': '35',
            'race_terrain[2][terrain_id]': 'TRN-004',
            'race_terrain[2][pct_of_race]': '20',
        }
        out = _parse_race_terrain(form)
        assert out == [
            {'terrain_id': 'TRN-002', 'pct_of_race': 35.0, 'discipline_id': None},
            {'terrain_id': 'TRN-004', 'pct_of_race': 20.0, 'discipline_id': None},
            {'terrain_id': 'TRN-009', 'pct_of_race': 15.0, 'discipline_id': None},
        ]


# ─── _terrain_choices ───────────────────────────────────────────────────────


class TestTerrainChoices:
    def test_returns_id_label_dicts_in_terrain_id_order(self):
        conn = _FakeConn()
        conn.queue_response(rows=[
            {'terrain_id': 'TRN-002', 'canonical_name': 'Singletrack'},
            {'terrain_id': 'TRN-003', 'canonical_name': 'Doubletrack'},
            {'terrain_id': 'TRN-009', 'canonical_name': 'Flat water'},
        ])

        out = _terrain_choices(conn)
        assert out == [
            {'id': 'TRN-002', 'label': 'Singletrack'},
            {'id': 'TRN-003', 'label': 'Doubletrack'},
            {'id': 'TRN-009', 'label': 'Flat water'},
        ]

        sql, _params = conn.calls[0]
        assert 'FROM layer0.terrain_types' in sql
        assert 'superseded_at IS NULL' in sql
        assert 'ORDER BY terrain_id' in sql

    def test_empty_when_no_rows(self):
        conn = _FakeConn()
        conn.queue_response(rows=[])
        assert _terrain_choices(conn) == []


# ─── _athlete_locale_choices removed ────────────────────────────────────────
# D-73 Phase 5.2 walkthrough #1 (2026-05-21) — the saved-locale dropdown on
# the onboarding step 3c race form was replaced with the Mapbox-anchored
# picker (shared partial `_race_locale_picker.html`); the helper was deleted
# alongside the dropdown.


# ─── _write_account_nudge ───────────────────────────────────────────────────


class TestWriteAccountNudge:
    def test_writes_on_conflict_do_nothing(self):
        conn = _FakeConn()
        _write_account_nudge(conn, uid=42, nudge_type='target_race_skipped')

        sql, params = conn.calls[0]
        assert 'INSERT INTO account_nudges' in sql
        assert 'ON CONFLICT (user_id, nudge_type) DO NOTHING' in sql
        assert params == (42, 'target_race_skipped')

    def test_no_commit_inside_helper(self):
        """The helper must NOT commit on its own — the route handler commits
        once at the end of its work unit so multiple writes can land
        atomically (e.g., `target_race_skip` writes a nudge then commits).
        """
        conn = _FakeConn()
        _write_account_nudge(conn, uid=42, nudge_type='target_race_skipped')
        assert conn.commits == 0

    def test_route_locales_incomplete_nudge_type(self):
        conn = _FakeConn()
        _write_account_nudge(conn, uid=42, nudge_type='route_locales_incomplete')
        _, params = conn.calls[0]
        assert params == (42, 'route_locales_incomplete')


# ─── Bucket C (i) — target_race_save Mapbox-required gate ───────────────────


def _make_onboarding_app():
    from flask import Flask
    from routes.onboarding import bp
    app = Flask(__name__)
    app.config['SECRET_KEY'] = 'test'
    app.config['TESTING'] = True
    app.config['WTF_CSRF_ENABLED'] = False
    app.register_blueprint(bp)
    return app


class TestTargetRaceSaveMapboxRequired:
    """Bucket C (i) — `target_race_save` POST blocks when the athlete
    submits without a Mapbox-anchored race location. The `[Skip]` button
    (`target_race_skip`) remains as the escape valve for athletes who can't
    find their race in Mapbox.
    """

    def test_post_without_mapbox_id_flashes_and_redirects(self, monkeypatch):
        app = _make_onboarding_app()
        conn = _FakeConn()
        import routes.onboarding as ob_mod
        monkeypatch.setattr(ob_mod, 'get_db', lambda: conn)
        monkeypatch.setattr(ob_mod, 'current_user_id', lambda: 1)
        # Stub the create/update repo helpers so a stale call would be loud.
        monkeypatch.setattr(ob_mod, 'create_race_event',
                            lambda *a, **k: pytest.fail(
                                'create_race_event called past gate'))
        monkeypatch.setattr(ob_mod, 'update_race_event',
                            lambda *a, **k: pytest.fail(
                                'update_race_event called past gate'))

        with app.test_request_context(
            '/onboarding/target-race',
            method='POST',
            data={
                'name': 'Test Race',
                'event_date': '2026-07-17',
                'race_format': 'continuous_multi_day',
                # `event_locale_mapbox_id` deliberately absent.
            },
        ):
            response = ob_mod.target_race_save()

        assert response.status_code == 302
        # Redirects back to /onboarding/target-race (the GET form).
        assert '/target-race' in response.location

    def test_skip_path_still_works(self, monkeypatch):
        # The [Skip] button bypasses the Mapbox gate entirely. Athletes
        # who can't find their race in Mapbox still have an escape valve.
        app = _make_onboarding_app()
        conn = _FakeConn()
        import routes.onboarding as ob_mod
        monkeypatch.setattr(ob_mod, 'get_db', lambda: conn)
        monkeypatch.setattr(ob_mod, 'current_user_id', lambda: 1)

        with app.test_request_context(
            '/onboarding/target-race/skip', method='POST'
        ):
            response = ob_mod.target_race_skip()

        # Skip writes a nudge + redirects forward; no race row touched.
        assert response.status_code == 302
        assert conn.commits == 1
        # Asserts the INSERT account_nudges fired (the only DB call in
        # target_race_skip), which is what the existing
        # TestWriteAccountNudge::test_target_race_skipped_nudge_type pins.
        assert any('account_nudges' in sql for sql, _ in conn.calls)
