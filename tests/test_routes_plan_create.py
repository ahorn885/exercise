"""Tests for `routes/plan_create.py` plan-create caller-side helpers.

Exercises the inline helpers (`_parse_plan_start_date`,
`_load_plan_version`, `_resolve_plan_scope_end_date`,
`_orchestration_error_message`, `_mark_plan_failed`) plus the shared
generation engine `_advance_plan_generation` (driven by both the
progress-screen poller and the background cron) and the cron scanner
`cron_generate_pending`. Matches the
`tests/test_onboarding_race_events.py` + `tests/test_race_events_repo.py`
test precedent for route modules; end-to-end Flask test-client
walkthrough captured in the §5.0 manual verification steps.
"""

from __future__ import annotations

from datetime import date, timedelta

import pytest
from flask import Flask

import routes.plan_create as plan_create
from routes.auth import cron_authorized
from routes.plan_create import (
    _advance_plan_generation,
    _count_cached_blocks,
    _generation_stalled,
    _load_plan_version,
    _mark_plan_failed,
    _orchestration_error_message,
    _parse_plan_start_date,
    _resolve_plan_scope_end_date,
    bp as plan_create_bp,
)
from layer3a.builder import Layer3AOutputError
from layer3b.builder import Layer3BOutputError
from layer2e.builder import Layer2EInputError
from layer4 import OrchestrationError
from layer4.errors import Layer4OutputError


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
            'generation_units_cached': 0,
            'generation_stall_passes': 0,
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


# ─── _advance_plan_generation (shared poller + cron engine) ──────────────────


def _queue_plan_version(
    conn, *, status, error=None, pvid=7, uid=3, units_cached=0, stall_passes=0
):
    """Queue the `_load_plan_version` SELECT response for a plan row."""
    conn.queue_response(row={
        'id': pvid, 'user_id': uid, 'created_at': 'ts',
        'created_via': 'plan_create',
        'scope_start_date': date(2026, 6, 1),
        'scope_end_date': date(2026, 7, 17),
        'pattern': 'A',
        'generation_status': status,
        'generation_error': error,
        'generation_units_cached': units_cached,
        'generation_stall_passes': stall_passes,
    })


class TestAdvancePlanGeneration:
    def test_not_found_returns_status(self):
        conn = _FakeConn()  # no queued row → _load_plan_version returns None
        assert _advance_plan_generation(conn, 3, 999) == {'status': 'not_found'}

    def test_ready_short_circuits_without_running_cone(self, monkeypatch):
        conn = _FakeConn()
        _queue_plan_version(conn, status='ready')

        def _boom(*a, **k):  # cone must not run on a terminal row
            raise AssertionError("orchestrate_plan_create should not be called")

        monkeypatch.setattr(plan_create, 'orchestrate_plan_create', _boom)
        assert _advance_plan_generation(conn, 3, 7) == {'status': 'ready'}
        assert conn.commits == 0  # short-circuit writes nothing

    def test_failed_short_circuits_with_stored_error(self, monkeypatch):
        conn = _FakeConn()
        _queue_plan_version(conn, status='failed', error='boom (x)')
        monkeypatch.setattr(
            plan_create, 'orchestrate_plan_create',
            lambda *a, **k: (_ for _ in ()).throw(AssertionError("ran cone")),
        )
        out = _advance_plan_generation(conn, 3, 7)
        assert out == {'status': 'failed', 'error': 'boom (x)'}

    def test_failed_without_stored_error_falls_back(self):
        conn = _FakeConn()
        _queue_plan_version(conn, status='failed', error=None)
        out = _advance_plan_generation(conn, 3, 7)
        assert out['status'] == 'failed'
        assert out['error']  # non-empty fallback copy

    def test_generating_runs_pass_and_marks_ready(self, monkeypatch):
        conn = _FakeConn()
        _queue_plan_version(conn, status='generating')
        calls = {}

        def _fake_orchestrate(db, uid, **kwargs):
            calls['orchestrate'] = (uid, kwargs)
            return 'RESULT_SENTINEL'

        monkeypatch.setattr(plan_create, 'orchestrate_plan_create', _fake_orchestrate)
        monkeypatch.setattr(plan_create, '_build_layer4_cache', lambda: 'CACHE')
        persisted = {}
        monkeypatch.setattr(
            plan_create, 'persist_layer4_sessions',
            lambda db, result: persisted.setdefault('result', result),
        )

        out = _advance_plan_generation(conn, 3, 7)
        assert out == {'status': 'ready'}
        assert calls['orchestrate'][0] == 3
        assert calls['orchestrate'][1]['plan_version_id'] == 7
        assert calls['orchestrate'][1]['plan_start_date'] == date(2026, 6, 1)
        assert persisted['result'] == 'RESULT_SENTINEL'
        # DELETE-guard + status flip + commit on the success path.
        assert any('DELETE FROM plan_sessions' in c[0] for c in conn.calls)
        assert any("generation_status = 'ready'" in c[0] for c in conn.calls)
        # 2 commits: the D-77 progress-backstop counter persist (pass start) +
        # the success status flip.
        assert conn.commits == 2

    def test_generating_persist_failure_marks_failed(self, monkeypatch):
        # Regression: persist + ready-flip now run INSIDE the try, so a
        # plan_sessions write failure marks the row failed (catch-all) rather
        # than escaping as a raw 500 that leaves the row 'generating' for the
        # every-minute cron to re-pick.
        conn = _FakeConn()
        _queue_plan_version(conn, status='generating')
        monkeypatch.setattr(plan_create, '_build_layer4_cache', lambda: 'CACHE')
        monkeypatch.setattr(
            plan_create, 'orchestrate_plan_create',
            lambda *a, **k: 'RESULT_SENTINEL',
        )
        monkeypatch.setattr(
            plan_create, 'persist_layer4_sessions',
            lambda db, result: (_ for _ in ()).throw(RuntimeError("db boom")),
        )
        out = _advance_plan_generation(conn, 3, 7)
        assert out['status'] == 'failed'
        assert out['error']  # generic "unexpected" message
        assert any("generation_status = 'failed'" in c[0] for c in conn.calls)
        assert not any("generation_status = 'ready'" in c[0] for c in conn.calls)

    def test_generating_orchestration_error_marks_failed(self, monkeypatch):
        conn = _FakeConn()
        _queue_plan_version(conn, status='generating')
        monkeypatch.setattr(
            plan_create, '_build_layer4_cache', lambda: 'CACHE')
        monkeypatch.setattr(
            plan_create, 'orchestrate_plan_create',
            lambda *a, **k: (_ for _ in ()).throw(
                OrchestrationError('primary_locale_missing')),
        )
        out = _advance_plan_generation(conn, 3, 7)
        assert out['status'] == 'failed'
        assert out['error']  # mapped orchestration message
        assert any("generation_status = 'failed'" in c[0] for c in conn.calls)

    def test_generating_layer4_error_marks_failed(self, monkeypatch):
        conn = _FakeConn()
        _queue_plan_version(conn, status='generating')
        monkeypatch.setattr(plan_create, '_build_layer4_cache', lambda: 'CACHE')
        monkeypatch.setattr(
            plan_create, 'orchestrate_plan_create',
            lambda *a, **k: (_ for _ in ()).throw(
                Layer4OutputError('schema_violation')),
        )
        out = _advance_plan_generation(conn, 3, 7)
        assert out['status'] == 'failed'
        assert 'schema_violation' in out['error']
        assert 'synthesis failed' in out['error'].lower()

    def test_generating_layer4_error_logs_detail(self, monkeypatch, capsys):
        # The user-facing message only carries exc.code; the failing
        # field/invariant lives in exc.detail (e.g. the pydantic
        # ValidationError for a mis-emitted session). Log it so a Layer 4
        # schema_violation is diagnosable from the runtime log — the detail
        # must NOT be swallowed the way it was before.
        conn = _FakeConn()
        _queue_plan_version(conn, status='generating')
        monkeypatch.setattr(plan_create, '_build_layer4_cache', lambda: 'CACHE')
        monkeypatch.setattr(
            plan_create, 'orchestrate_plan_create',
            lambda *a, **k: (_ for _ in ()).throw(
                Layer4OutputError(
                    'schema_violation',
                    detail="tool output did not parse as PlanSession list: "
                    "CardioBlock.rest_intensity_zone required for interval_set")),
        )
        out = _advance_plan_generation(conn, 3, 7)
        assert out['status'] == 'failed'
        # detail is NOT leaked to the athlete-facing message ...
        assert 'rest_intensity_zone' not in out['error']
        # ... but IS captured in the runtime log for diagnosis.
        logged = capsys.readouterr().out
        assert 'Layer4OutputError' in logged
        assert 'schema_violation' in logged
        assert 'rest_intensity_zone' in logged

    def test_generating_layer3_error_marks_failed(self, monkeypatch):
        conn = _FakeConn()
        _queue_plan_version(conn, status='generating')
        monkeypatch.setattr(plan_create, '_build_layer4_cache', lambda: 'CACHE')
        monkeypatch.setattr(
            plan_create, 'orchestrate_plan_create',
            lambda *a, **k: (_ for _ in ()).throw(
                Layer3AOutputError('schema_violation')),
        )
        out = _advance_plan_generation(conn, 3, 7)
        assert out['status'] == 'failed'
        assert 'evaluation failed' in out['error'].lower()

    def test_generating_layer2_input_error_marks_failed_not_unexpected(self, monkeypatch):
        # Layer 1/2 upstream-input failures (e.g. 2E missing body_weight_kg)
        # are bare ValueError subclasses; they used to fall through to the
        # catch-all and surface as the opaque "failed unexpectedly". Now they
        # flip the row to a NAMED, diagnosable failure.
        conn = _FakeConn()
        _queue_plan_version(conn, status='generating')
        monkeypatch.setattr(plan_create, '_build_layer4_cache', lambda: 'CACHE')
        monkeypatch.setattr(
            plan_create, 'orchestrate_plan_create',
            lambda *a, **k: (_ for _ in ()).throw(
                Layer2EInputError(
                    "performance.body_weight_kg must be > 30 kg; got None")),
        )
        out = _advance_plan_generation(conn, 3, 7)
        assert out['status'] == 'failed'
        assert 'Layer2EInputError' in out['error']
        assert 'unexpectedly' not in out['error'].lower()
        assert any("generation_status = 'failed'" in c[0] for c in conn.calls)


# ─── D-77 §6 progress-based stall backstop ───────────────────────────────────


class TestCountCachedBlocks:
    def test_counts_plan_create_block_rows(self):
        conn = _FakeConn()
        conn.queue_response(row={'n': 12})
        assert _count_cached_blocks(conn, 3) == 12
        sql, params = conn.calls[0]
        assert 'COUNT(*)' in sql
        assert "entry_point = 'plan_create'" in sql
        # Block rows only: phase_idx in [0, _SEAM_CACHE_PHASE_IDX_BASE).
        assert 'phase_idx >= 0' in sql and 'phase_idx < ?' in sql
        assert params == (3, plan_create._SEAM_CACHE_PHASE_IDX_BASE)

    def test_zero_when_no_rows(self):
        conn = _FakeConn()  # no queued response → fetchone None
        assert _count_cached_blocks(conn, 3) == 0


class TestStallBackstop:
    def test_stall_trips_when_no_block_cached_within_window(self, monkeypatch):
        conn = _FakeConn()
        _queue_plan_version(conn, status='generating', units_cached=0)
        conn.queue_response(row={'n': 0})            # _count_cached_blocks
        conn.queue_response(row={'stalled': True})   # over the wall-clock window

        def _boom(*a, **k):
            raise AssertionError("cone must not run once the backstop trips")

        monkeypatch.setattr(plan_create, 'orchestrate_plan_create', _boom)
        out = _advance_plan_generation(conn, 3, 7)
        assert out['status'] == 'failed'
        assert 'stalled' in out['error'].lower()
        assert any("generation_status = 'failed'" in c[0] for c in conn.calls)
        # The stall signal is wall-clock now — the per-call counter is never
        # written (it's still SELECTed by _load_plan_version, hence "= ?").
        assert not any('generation_stall_passes = ?' in c[0] for c in conn.calls)

    def test_recent_progress_runs_cone_and_records_count(self, monkeypatch):
        conn = _FakeConn()
        _queue_plan_version(conn, status='generating', units_cached=2)
        conn.queue_response(row={'n': 5})            # 5 blocks cached so far
        conn.queue_response(row={'stalled': False})  # a block cached recently
        monkeypatch.setattr(plan_create, '_build_layer4_cache', lambda: 'CACHE')
        monkeypatch.setattr(
            plan_create, 'orchestrate_plan_create', lambda *a, **k: 'RESULT'
        )
        monkeypatch.setattr(
            plan_create, 'persist_layer4_sessions', lambda db, r: None
        )
        out = _advance_plan_generation(conn, 3, 7)
        assert out['status'] == 'ready'
        # Progress count persisted (telemetry); the stall_passes column is gone.
        upd = [c for c in conn.calls if 'generation_units_cached = ?' in c[0]]
        assert upd and upd[0][1] == (5, 7, 3)

    def test_in_flight_first_block_does_not_false_trip(self, monkeypatch):
        # Regression for the plan_version_id=24 incident: a brand-new generation
        # has zero cached blocks while the first ~300s block is still in flight.
        # The every-minute cron fires during that window; the wall-clock gate
        # reports NOT stalled (generation just started), so the cone runs rather
        # than the plan being failed ~46s in (the old per-call counter's bug).
        conn = _FakeConn()
        _queue_plan_version(conn, status='generating', units_cached=0)
        conn.queue_response(row={'n': 0})            # nothing cached yet
        conn.queue_response(row={'stalled': False})  # within the wall-clock window
        ran = {}
        monkeypatch.setattr(plan_create, '_build_layer4_cache', lambda: 'CACHE')
        monkeypatch.setattr(
            plan_create, 'orchestrate_plan_create',
            lambda *a, **k: ran.setdefault('ran', True) or 'RESULT',
        )
        monkeypatch.setattr(
            plan_create, 'persist_layer4_sessions', lambda db, r: None
        )
        out = _advance_plan_generation(conn, 3, 7)
        assert ran.get('ran') is True
        assert out['status'] == 'ready'


class TestGenerationStalled:
    def test_true_when_db_reports_over_window(self):
        conn = _FakeConn()
        conn.queue_response(row={'stalled': True})
        assert _generation_stalled(conn, 3, 7) is True
        sql, params = conn.calls[0]
        # Wall-clock gate on the DB clock, anchored on the most-recent block
        # (or generation start when no block has cached yet).
        assert 'NOW()' in sql and 'MAX(created_at)' in sql
        assert "entry_point = 'plan_create'" in sql
        assert 'phase_idx >= 0' in sql and 'phase_idx < ?' in sql
        assert "INTERVAL '1 second'" in sql
        assert params == (
            3, plan_create._SEAM_CACHE_PHASE_IDX_BASE,
            plan_create._STALL_WALLCLOCK_S, 7, 3,
        )

    def test_false_when_db_reports_within_window(self):
        conn = _FakeConn()
        conn.queue_response(row={'stalled': False})
        assert _generation_stalled(conn, 3, 7) is False

    def test_false_when_row_missing(self):
        conn = _FakeConn()  # no queued response → fetchone None → not stalled
        assert _generation_stalled(conn, 3, 7) is False


# ─── cron_authorized (shared CRON_SECRET gate) ───────────────────────────────


class TestCronAuthorized:
    def _ctx(self, headers):
        return Flask(__name__).test_request_context(headers=headers)

    def test_no_secret_set_fails_closed(self, monkeypatch):
        monkeypatch.delenv('CRON_SECRET', raising=False)
        with self._ctx({'Authorization': 'Bearer anything'}):
            assert cron_authorized() is False

    def test_correct_bearer_token_authorized(self, monkeypatch):
        monkeypatch.setenv('CRON_SECRET', 's3cret')
        with self._ctx({'Authorization': 'Bearer s3cret'}):
            assert cron_authorized() is True

    def test_wrong_token_rejected(self, monkeypatch):
        monkeypatch.setenv('CRON_SECRET', 's3cret')
        with self._ctx({'Authorization': 'Bearer nope'}):
            assert cron_authorized() is False

    def test_missing_header_rejected(self, monkeypatch):
        monkeypatch.setenv('CRON_SECRET', 's3cret')
        with self._ctx({}):
            assert cron_authorized() is False

    def test_wrong_scheme_rejected(self, monkeypatch):
        monkeypatch.setenv('CRON_SECRET', 's3cret')
        with self._ctx({'Authorization': 'Basic s3cret'}):
            assert cron_authorized() is False


# ─── cron_generate_pending (background scanner) ──────────────────────────────


def _cron_app():
    app = Flask(__name__)
    app.register_blueprint(plan_create_bp)
    return app


class TestCronGeneratePending:
    URL = '/plans/v2/cron/generate-pending'

    def test_unauthorized_returns_401(self, monkeypatch):
        monkeypatch.setattr(plan_create, 'cron_authorized', lambda: False)
        app = _cron_app()
        resp = app.test_client().get(self.URL)
        assert resp.status_code == 401

    def test_advances_generating_rows_and_tallies(self, monkeypatch):
        monkeypatch.setattr(plan_create, 'cron_authorized', lambda: True)
        conn = _FakeConn()
        # The scanner's SELECT returns two generating rows (id, user_id).
        conn.queue_response(rows=[
            {'id': 11, 'user_id': 2},
            {'id': 12, 'user_id': 5},
        ])
        monkeypatch.setattr(plan_create, 'get_db', lambda: conn)

        seen = []

        def _fake_advance(db, uid, pvid):
            seen.append((uid, pvid))
            return {'status': 'ready'} if pvid == 11 else {'status': 'failed', 'error': 'x'}

        monkeypatch.setattr(plan_create, '_advance_plan_generation', _fake_advance)

        app = _cron_app()
        resp = app.test_client().get(self.URL)
        assert resp.status_code == 200
        assert resp.get_json() == {'advanced': 2, 'ready': 1, 'failed': 1}
        # Each row advanced under its own owner's user id.
        assert seen == [(2, 11), (5, 12)]
        # The SELECT filters to generating rows + the batch LIMIT.
        sql, params = conn.calls[0]
        assert "generation_status = 'generating'" in sql
        assert params == (plan_create._CRON_ADVANCE_BATCH,)

    def test_empty_generating_set_is_noop(self, monkeypatch):
        monkeypatch.setattr(plan_create, 'cron_authorized', lambda: True)
        conn = _FakeConn()
        conn.queue_response(rows=[])
        monkeypatch.setattr(plan_create, 'get_db', lambda: conn)
        app = _cron_app()
        resp = app.test_client().get(self.URL)
        assert resp.status_code == 200
        assert resp.get_json() == {'advanced': 0, 'ready': 0, 'failed': 0}

    def test_stops_starting_passes_once_wall_clock_budget_spent(self, monkeypatch):
        # The cron must not start a pass it can't finish before the function
        # cap: once the wall-clock budget is spent, the remaining rows are left
        # 'generating' for the next fire instead of being started + 504'd.
        monkeypatch.setattr(plan_create, 'cron_authorized', lambda: True)
        conn = _FakeConn()
        conn.queue_response(rows=[
            {'id': 11, 'user_id': 2},
            {'id': 12, 'user_id': 5},
            {'id': 13, 'user_id': 8},
        ])
        monkeypatch.setattr(plan_create, 'get_db', lambda: conn)

        # Simulate the clock: start at 0, then each pass burns most of the
        # budget so the second deadline check trips before row 3 is started.
        ticks = iter([
            0.0,                                            # deadline anchor
            0.0,                                            # check before row 11
            plan_create._CRON_WALL_CLOCK_BUDGET_S - 1,      # check before row 12
            plan_create._CRON_WALL_CLOCK_BUDGET_S + 1,      # check before row 13 → break
        ])
        monkeypatch.setattr(plan_create.time, 'monotonic', lambda: next(ticks))

        seen = []

        def _fake_advance(db, uid, pvid):
            seen.append((uid, pvid))
            return {'status': 'ready'}

        monkeypatch.setattr(plan_create, '_advance_plan_generation', _fake_advance)

        app = _cron_app()
        resp = app.test_client().get(self.URL)
        assert resp.status_code == 200
        # Rows 11 + 12 ran; row 13 was left for the next fire.
        assert seen == [(2, 11), (5, 12)]
        assert resp.get_json() == {'advanced': 2, 'ready': 2, 'failed': 0}


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
