"""Tests for `routes/plan_create.py` plan-create caller-side helpers.

Exercises the inline helpers (`_parse_plan_start_date`,
`_load_plan_version`, `_resolve_plan_scope_end_date`,
`_orchestration_error_message`) directly. Matches the
`tests/test_onboarding_race_events.py` + `tests/test_race_events_repo.py`
test precedent for route modules; end-to-end Flask test-client
walkthrough captured in the §5.0 manual verification steps.
"""

from __future__ import annotations

from datetime import date, timedelta

import pytest

from routes.plan_create import (
    _load_plan_version,
    _mark_plan_failed,
    _orchestration_error_message,
    _parse_plan_start_date,
    _resolve_plan_scope_end_date,
    _terminal_status_response,
)
from layer4 import OrchestrationError


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
    def __init__(self):
        self.calls: list[tuple[str, tuple]] = []
        self.commits: int = 0
        self.rollbacks: int = 0
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

    def rollback(self):
        self.rollbacks += 1


# ─── _parse_plan_start_date ─────────────────────────────────────────────────


class TestParsePlanStartDate:
    def test_happy_path(self):
        result, err = _parse_plan_start_date({'plan_start_date': '2026-06-01'})
        assert err is None
        assert result == date(2026, 6, 1)

    def test_strips_whitespace(self):
        result, err = _parse_plan_start_date({'plan_start_date': '  2026-06-01 '})
        assert err is None
        assert result == date(2026, 6, 1)

    def test_empty_rejected(self):
        result, err = _parse_plan_start_date({'plan_start_date': ''})
        assert result is None
        assert err is not None
        assert 'required' in err.lower()

    def test_missing_key_rejected(self):
        result, err = _parse_plan_start_date({})
        assert result is None
        assert err is not None

    def test_invalid_format_rejected(self):
        result, err = _parse_plan_start_date({'plan_start_date': '06/01/2026'})
        assert result is None
        assert err is not None
        assert 'yyyy-mm-dd' in err.lower()

    def test_out_of_range_date_rejected(self):
        result, err = _parse_plan_start_date({'plan_start_date': '2026-13-99'})
        assert result is None
        assert err is not None


# ─── _load_plan_version ─────────────────────────────────────────────────────


class TestLoadPlanVersion:
    def test_returns_dict_on_hit(self):
        conn = _FakeConn()
        conn.queue_response(row={
            'id': 7, 'user_id': 3, 'created_at': 'ts',
            'created_via': 'plan_create',
            'scope_start_date': date(2026, 6, 1),
            'scope_end_date': date(2026, 7, 17),
            'pattern': 'A',
            'generation_status': 'ready',
            'generation_error': None,
        })
        result = _load_plan_version(conn, user_id=3, plan_version_id=7)
        assert result is not None
        assert result['id'] == 7
        assert result['user_id'] == 3
        assert result['created_via'] == 'plan_create'
        assert result['pattern'] == 'A'
        assert result['generation_status'] == 'ready'
        assert result['generation_error'] is None
        sql, params = conn.calls[0]
        assert 'WHERE id = ? AND user_id = ?' in sql
        assert 'generation_status' in sql
        assert params == (7, 3)

    def test_returns_none_on_miss(self):
        conn = _FakeConn()
        assert _load_plan_version(conn, user_id=3, plan_version_id=999) is None

    def test_scoped_by_user_id(self):
        """user_id filter prevents cross-user-id leak."""
        conn = _FakeConn()
        _load_plan_version(conn, user_id=99, plan_version_id=1)
        _, params = conn.calls[0]
        # Defensive: user_id is part of the WHERE — a crafted GET against a
        # plan_version_id belonging to another user returns None (404).
        assert params == (1, 99)


# ─── _resolve_plan_scope_end_date ───────────────────────────────────────────


class _FakeRaceEvent:
    def __init__(self, event_date: date | None):
        self.event_date = event_date


class TestResolvePlanScopeEndDate:
    def test_uses_race_event_date_when_in_future(self):
        result = _resolve_plan_scope_end_date(
            date(2026, 4, 1),
            _FakeRaceEvent(date(2026, 7, 17)),
        )
        assert result == date(2026, 7, 17)

    def test_falls_back_to_24_weeks_when_no_race(self):
        start = date(2026, 4, 1)
        result = _resolve_plan_scope_end_date(start, None)
        assert result == start + timedelta(days=168)

    def test_falls_back_to_24_weeks_when_race_in_past(self):
        start = date(2026, 4, 1)
        result = _resolve_plan_scope_end_date(
            start,
            _FakeRaceEvent(date(2026, 1, 1)),  # in the past relative to start
        )
        assert result == start + timedelta(days=168)

    def test_handles_race_event_missing_event_date(self):
        start = date(2026, 4, 1)
        result = _resolve_plan_scope_end_date(start, _FakeRaceEvent(None))
        assert result == start + timedelta(days=168)

    def test_same_day_race_uses_race_date(self):
        start = date(2026, 4, 1)
        result = _resolve_plan_scope_end_date(start, _FakeRaceEvent(start))
        assert result == start


# ─── _orchestration_error_message ───────────────────────────────────────────


class TestOrchestrationErrorMessage:
    def test_known_codes_have_messages(self):
        for code in (
            'etl_version_set_undiscoverable',
            'primary_locale_missing',
            'framework_sport_missing',
        ):
            msg = _orchestration_error_message(OrchestrationError(code))
            assert msg

    def test_unknown_code_falls_back_to_generic(self):
        msg = _orchestration_error_message(OrchestrationError('some_new_code'))
        assert 'some_new_code' in msg
        assert 'plan creation failed' in msg.lower()


# ─── _terminal_status_response (async-generation poller) ─────────────────────


class TestTerminalStatusResponse:
    def test_ready_returns_redirect(self):
        pv = {'generation_status': 'ready', 'generation_error': None}
        out = _terminal_status_response(pv, '/plans/v2/7')
        assert out == {'status': 'ready', 'redirect': '/plans/v2/7'}

    def test_failed_returns_stored_error(self):
        pv = {'generation_status': 'failed', 'generation_error': 'boom (x)'}
        out = _terminal_status_response(pv, '/plans/v2/7')
        assert out['status'] == 'failed'
        assert out['error'] == 'boom (x)'

    def test_failed_without_stored_error_falls_back(self):
        pv = {'generation_status': 'failed', 'generation_error': None}
        out = _terminal_status_response(pv, '/plans/v2/7')
        assert out['status'] == 'failed'
        assert out['error']  # non-empty fallback copy

    def test_generating_returns_none_to_proceed(self):
        pv = {'generation_status': 'generating', 'generation_error': None}
        assert _terminal_status_response(pv, '/plans/v2/7') is None


# ─── _mark_plan_failed ───────────────────────────────────────────────────────


class TestMarkPlanFailed:
    def test_persists_failure_and_returns_json(self):
        conn = _FakeConn()
        out = _mark_plan_failed(conn, plan_version_id=7, user_id=3, message='nope')
        assert out == {'status': 'failed', 'error': 'nope'}
        # Rolls back to clear any aborted/pending txn, then writes + commits.
        assert conn.rollbacks == 1
        assert conn.commits == 1
        sql, params = conn.calls[0]
        assert "generation_status = 'failed'" in sql
        assert "WHERE id = ? AND user_id = ?" in sql
        assert params == ('nope', 7, 3)
