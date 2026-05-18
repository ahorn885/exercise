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
    _athlete_locale_choices,
    _get_target_race_row,
    _parse_date_field,
    _parse_decimal_field,
    _parse_int_field,
    _parse_str_field,
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
            'race_format': 'expedition_ar',
            'distance_km': 320.5,
            'total_elevation_gain_m': 4800,
            'race_rules_summary': 'Time cut 56h',
            'mandatory_gear_text': 'Helmet, headlamp, PFD',
            'event_locale_id': None,
            'notes': None,
        })

        out = _get_target_race_row(conn, uid=42)
        assert out is not None
        assert out['id'] == 5
        assert out['name'] == 'Pocket Gopher Extreme'
        assert out['race_format'] == 'expedition_ar'

        # WHERE clause must scope by user_id AND is_target_event=TRUE.
        sql, params = conn.calls[0]
        assert 'WHERE user_id = ? AND is_target_event = TRUE' in sql
        assert params == (42,)

    def test_returns_none_on_miss(self):
        conn = _FakeConn()
        conn.queue_response(row=None)
        assert _get_target_race_row(conn, uid=42) is None


# ─── _athlete_locale_choices ────────────────────────────────────────────────


class TestAthleteLocaleChoices:
    def test_returns_dicts_in_label_order(self):
        conn = _FakeConn()
        conn.queue_response(rows=[
            {'id': 7, 'locale': 'home_gym_1', 'locale_name': 'Apartment'},
            {'id': 9, 'locale': 'hotel_xyz', 'locale_name': None},
        ])

        out = _athlete_locale_choices(conn, uid=42)
        assert out == [
            {'id': 7, 'label': 'Apartment'},
            {'id': 9, 'label': 'hotel_xyz'},  # falls back to slug
        ]

        sql, params = conn.calls[0]
        assert 'FROM locale_profiles' in sql
        assert 'WHERE user_id = ?' in sql
        assert 'ORDER BY COALESCE(locale_name, locale)' in sql
        assert params == (42,)

    def test_empty_when_no_locales(self):
        conn = _FakeConn()
        conn.queue_response(rows=[])
        assert _athlete_locale_choices(conn, uid=42) == []


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
