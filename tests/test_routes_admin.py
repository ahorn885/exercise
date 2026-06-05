"""Tests for D-73 Phase 5.2 refresh-flow telemetry aggregate helpers in
`routes/admin.py`.

Coverage:
- `_telemetry_window_threshold(now)` — returns `now - 30 days`; defaults
  to UTC `datetime.now()`.
- `_percentile(sorted, pct)` — nearest-rank percentile with None on empty,
  clamp on out-of-range pct.
- `_aggregate_ad_hoc_suggestions(db, threshold)` — SQL shape +
  GROUP BY status + logged-rate computation.
- `_aggregate_t1_hook_dismissals(db, threshold)` — single COUNT(*).
- `_aggregate_plan_refresh_log(db, threshold)` — per-tier
  count/success/cap_override/parser_degraded/t1_hook_attribution rates +
  p50/p95 duration on success-only rows.

Route-level smoke (the `/admin/telemetry/refresh` GET against a Flask
test client) is deferred to manual §5.0 — mirrors `tests/test_locales.py`
+ `tests/test_routes_plan_refresh.py` precedent for admin-gated routes.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

from routes.admin import (
    TELEMETRY_WINDOW_DAYS,
    _aggregate_ad_hoc_suggestions,
    _aggregate_plan_refresh_log,
    _aggregate_t1_hook_dismissals,
    _percentile,
    _telemetry_window_threshold,
)


# ─── Shared fakes ───────────────────────────────────────────────────────────


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
    """`db`-shaped fake: queued responses returned in FIFO order."""

    def __init__(self):
        self.calls: list[tuple[str, tuple]] = []
        self._responses: list[tuple] = []

    def queue_response(self, row=None, rows=None):
        self._responses.append((row, rows or []))

    def execute(self, sql, params=()):
        self.calls.append((sql, params))
        if self._responses:
            row, rows = self._responses.pop(0)
        else:
            row, rows = None, []
        return _FakeCursor(row=row, rows=rows)


# ─── _telemetry_window_threshold ─────────────────────────────────────────────


class TestTelemetryWindowThreshold:
    def test_subtracts_window_days(self):
        now = datetime(2026, 5, 21, 12, 0, 0, tzinfo=timezone.utc)
        result = _telemetry_window_threshold(now=now)
        assert result == now - timedelta(days=TELEMETRY_WINDOW_DAYS)

    def test_default_now_is_utc(self):
        before = datetime.now(timezone.utc)
        result = _telemetry_window_threshold()
        after = datetime.now(timezone.utc)
        # Should land between (before - 30d) and (after - 30d).
        assert (before - timedelta(days=TELEMETRY_WINDOW_DAYS)) <= result
        assert result <= (after - timedelta(days=TELEMETRY_WINDOW_DAYS))


# ─── _percentile ────────────────────────────────────────────────────────────


class TestPercentile:
    def test_empty_returns_none(self):
        assert _percentile([], 50) is None
        assert _percentile([], 95) is None

    def test_single_value(self):
        assert _percentile([42], 50) == 42
        assert _percentile([42], 95) == 42

    def test_p50_median(self):
        # Nearest-rank p50 on 10 values: idx = int(0.5 * 10) = 5 → values[5].
        assert _percentile([10, 20, 30, 40, 50, 60, 70, 80, 90, 100], 50) == 60

    def test_p95_near_top(self):
        # idx = int(0.95 * 10) = 9 → values[9] = 100.
        assert _percentile([10, 20, 30, 40, 50, 60, 70, 80, 90, 100], 95) == 100

    def test_clamp_min(self):
        assert _percentile([1, 2, 3], 0) == 1
        assert _percentile([1, 2, 3], -10) == 1

    def test_clamp_max(self):
        assert _percentile([1, 2, 3], 100) == 3
        assert _percentile([1, 2, 3], 200) == 3


# ─── _aggregate_ad_hoc_suggestions ──────────────────────────────────────────


class TestAggregateAdHocSuggestions:
    _T = datetime(2026, 4, 21, tzinfo=timezone.utc)

    def test_empty_window_zero_counts(self):
        db = _FakeConn()
        db.queue_response(rows=[])
        result = _aggregate_ad_hoc_suggestions(db, self._T)
        assert result == {
            'total': 0,
            'suggested': 0,
            'logged': 0,
            'discarded': 0,
            'regenerated': 0,
            'logged_rate': 0.0,
        }

    def test_sql_filters_on_requested_at_threshold(self):
        db = _FakeConn()
        db.queue_response(rows=[])
        _aggregate_ad_hoc_suggestions(db, self._T)
        sql, params = db.calls[0]
        assert 'ad_hoc_workout_suggestions' in sql
        assert 'requested_at >= ?' in sql
        assert 'GROUP BY status' in sql
        assert params == (self._T,)

    def test_aggregates_all_statuses(self):
        db = _FakeConn()
        db.queue_response(rows=[
            {'status': 'suggested', 'n': 2},
            {'status': 'logged', 'n': 5},
            {'status': 'discarded', 'n': 1},
            {'status': 'regenerated', 'n': 2},
        ])
        result = _aggregate_ad_hoc_suggestions(db, self._T)
        assert result['total'] == 10
        assert result['suggested'] == 2
        assert result['logged'] == 5
        assert result['discarded'] == 1
        assert result['regenerated'] == 2
        assert result['logged_rate'] == 0.5

    def test_missing_status_keys_default_to_zero(self):
        db = _FakeConn()
        db.queue_response(rows=[{'status': 'logged', 'n': 3}])
        result = _aggregate_ad_hoc_suggestions(db, self._T)
        assert result['logged'] == 3
        assert result['suggested'] == 0
        assert result['discarded'] == 0
        assert result['regenerated'] == 0
        assert result['logged_rate'] == 1.0


# ─── _aggregate_t1_hook_dismissals ──────────────────────────────────────────


class TestAggregateT1HookDismissals:
    _T = datetime(2026, 4, 21, tzinfo=timezone.utc)

    def test_returns_count(self):
        db = _FakeConn()
        db.queue_response(row={'n': 7})
        assert _aggregate_t1_hook_dismissals(db, self._T) == {'total': 7}

    def test_no_row_returns_zero(self):
        db = _FakeConn()
        # No queued response → COUNT(*) returns None
        assert _aggregate_t1_hook_dismissals(db, self._T) == {'total': 0}

    def test_sql_filters_on_dismissed_at_threshold(self):
        db = _FakeConn()
        db.queue_response(row={'n': 0})
        _aggregate_t1_hook_dismissals(db, self._T)
        sql, params = db.calls[0]
        assert 't1_hook_telemetry' in sql
        assert 'dismissed_at >= ?' in sql
        assert params == (self._T,)


# ─── _aggregate_plan_refresh_log ────────────────────────────────────────────


class TestAggregatePlanRefreshLog:
    _T = datetime(2026, 4, 21, tzinfo=timezone.utc)

    def test_empty_returns_zero_filled_per_tier(self):
        db = _FakeConn()
        db.queue_response(rows=[])
        result = _aggregate_plan_refresh_log(db, self._T)
        assert set(result.keys()) == {'T1', 'T2', 'T3'}
        for tier in ('T1', 'T2', 'T3'):
            assert result[tier]['total'] == 0
            assert result[tier]['success_count'] == 0
            assert result[tier]['success_rate'] == 0.0
            assert result[tier]['cap_override_count'] == 0
            assert result[tier]['cap_override_rate'] == 0.0
            assert result[tier]['parser_degraded_count'] == 0
            assert result[tier]['t1_hook_attributed_count'] == 0
            assert result[tier]['p50_duration_ms'] is None
            assert result[tier]['p95_duration_ms'] is None

    def test_sql_pins(self):
        db = _FakeConn()
        db.queue_response(rows=[])
        _aggregate_plan_refresh_log(db, self._T)
        sql, params = db.calls[0]
        assert 'plan_refresh_log' in sql
        assert 'tier' in sql
        assert 'success' in sql
        assert 'cap_overridden' in sql
        assert 'triggered_by_ad_hoc_id' in sql
        assert 'failure_reason' in sql
        assert 'duration_ms' in sql
        assert 'triggered_at >= ?' in sql
        assert params == (self._T,)

    def test_per_tier_aggregates(self):
        db = _FakeConn()
        # T1: 3 rows — 2 success (durations 100, 300), 1 failure
        #     1 with cap_override, 1 with parser_degraded (the failure),
        #     2 with triggered_by_ad_hoc_id set.
        # T2: 1 row, success, no cap, no parser_degraded, no attribution.
        # T3: nothing.
        db.queue_response(rows=[
            {'tier': 'T1', 'success': True, 'cap_overridden': True,
             'triggered_by_ad_hoc_id': 99, 'failure_reason': None,
             'duration_ms': 100},
            {'tier': 'T1', 'success': True, 'cap_overridden': False,
             'triggered_by_ad_hoc_id': 100, 'failure_reason': None,
             'duration_ms': 300},
            {'tier': 'T1', 'success': False, 'cap_overridden': False,
             'triggered_by_ad_hoc_id': None, 'failure_reason': 'parser_degraded',
             'duration_ms': None},
            {'tier': 'T2', 'success': True, 'cap_overridden': False,
             'triggered_by_ad_hoc_id': None, 'failure_reason': None,
             'duration_ms': 500},
        ])
        result = _aggregate_plan_refresh_log(db, self._T)

        t1 = result['T1']
        assert t1['total'] == 3
        assert t1['success_count'] == 2
        assert t1['success_rate'] == 2 / 3
        assert t1['cap_override_count'] == 1
        assert t1['cap_override_rate'] == 1 / 3
        assert t1['parser_degraded_count'] == 1
        assert t1['parser_degraded_rate'] == 1 / 3
        assert t1['t1_hook_attributed_count'] == 2
        assert t1['t1_hook_attribution_rate'] == 2 / 3
        # success durations = [100, 300] → nearest-rank p50 idx=1 → 300.
        assert t1['p50_duration_ms'] == 300
        assert t1['p95_duration_ms'] == 300

        t2 = result['T2']
        assert t2['total'] == 1
        assert t2['success_count'] == 1
        assert t2['success_rate'] == 1.0
        assert t2['p50_duration_ms'] == 500

        t3 = result['T3']
        assert t3['total'] == 0
        assert t3['p50_duration_ms'] is None

    def test_failure_rows_excluded_from_duration_percentiles(self):
        db = _FakeConn()
        db.queue_response(rows=[
            {'tier': 'T1', 'success': True, 'cap_overridden': False,
             'triggered_by_ad_hoc_id': None, 'failure_reason': None,
             'duration_ms': 200},
            # Failure row with a duration — must NOT enter p50/p95.
            {'tier': 'T1', 'success': False, 'cap_overridden': False,
             'triggered_by_ad_hoc_id': None, 'failure_reason': 'orchestration:foo',
             'duration_ms': 9999},
        ])
        result = _aggregate_plan_refresh_log(db, self._T)
        assert result['T1']['p50_duration_ms'] == 200
        assert result['T1']['p95_duration_ms'] == 200


# ─── /admin/plan/<id>/diag token auth (Rule #14 log-visibility) ──────────────
# Route smoke is deferred to manual §5.0 per the module precedent; the pure
# token-comparison helper is unit-tested here.


class TestDiagTokenOk:
    """`_diag_token_ok(supplied, configured)` — the constant-time token gate
    for the token-readable diag endpoint."""

    def test_no_token_configured_denies_even_with_supplied(self):
        from routes.admin import _diag_token_ok
        # DIAG_TOKEN unset -> no token bypass; only the admin session authorizes.
        assert _diag_token_ok("anything", None) is False
        assert _diag_token_ok("anything", "") is False

    def test_missing_or_wrong_supplied_denied(self):
        from routes.admin import _diag_token_ok
        assert _diag_token_ok(None, "secret") is False
        assert _diag_token_ok("", "secret") is False
        assert _diag_token_ok("wrong", "secret") is False

    def test_exact_match_authorizes(self):
        from routes.admin import _diag_token_ok
        assert _diag_token_ok("secret", "secret") is True


class TestSummarizeProgressBlocks:
    """`_summarize_progress_blocks(blocks)` — the pure per-block diag view +
    timing rollup the diag JSON exposes so per-block synthesis latency/retries/
    cap_hit (the stall-localizing signal) is readable past the login wall."""

    def test_rollup_aggregates_metadata_and_picks_latest_snapshot(self):
        from datetime import datetime, timezone
        from routes.admin import _summarize_progress_blocks

        t0 = datetime(2026, 6, 4, 12, 17, tzinfo=timezone.utc)
        t1 = datetime(2026, 6, 4, 12, 29, tzinfo=timezone.utc)
        blocks = [
            {"phase_idx": 0, "phase_name": "Base",
             "sessions": [{"id": "a"}, {"id": "b"}],
             "synthesis_metadata": {"latency_ms": 169000, "retries_used": 1,
                                    "cap_hit": False},
             "snapshot_at": t0},
            {"phase_idx": 1, "phase_name": "Base",
             "sessions": [{"id": "c"}],
             "synthesis_metadata": {"latency_ms": 240000, "retries_used": 0,
                                    "cap_hit": True},
             "snapshot_at": t1},
        ]

        out = _summarize_progress_blocks(blocks)

        assert out["block_timing"] == {
            "total_latency_ms": 409000,
            "max_block_latency_ms": 240000,
            "total_retries": 1,
            "any_cap_hit": True,
            "last_snapshot_at": str(t1),   # the most-recent snapshot, not t0
        }
        # Per-block view carries counts + metadata, NOT the session bodies.
        assert [b["session_count"] for b in out["blocks"]] == [2, 1]
        assert "sessions" not in out["blocks"][0]
        assert out["blocks"][0]["synthesis_metadata"]["latency_ms"] == 169000

    def test_missing_or_null_metadata_tolerated(self):
        from routes.admin import _summarize_progress_blocks

        # A block snapshotted before its metadata landed (None) must not raise
        # and contributes zero to the rollup.
        out = _summarize_progress_blocks([
            {"phase_idx": 0, "phase_name": "Base", "sessions": None,
             "synthesis_metadata": None, "snapshot_at": None},
        ])

        assert out["block_timing"]["total_latency_ms"] == 0
        assert out["block_timing"]["any_cap_hit"] is False
        assert out["block_timing"]["last_snapshot_at"] is None
        assert out["blocks"][0]["session_count"] == 0
        assert out["blocks"][0]["synthesis_metadata"] is None

    def test_empty_blocks_is_zeroed_rollup(self):
        from routes.admin import _summarize_progress_blocks
        out = _summarize_progress_blocks([])
        assert out["blocks"] == []
        assert out["block_timing"]["total_latency_ms"] == 0
        assert out["block_timing"]["max_block_latency_ms"] == 0
        assert out["block_timing"]["last_snapshot_at"] is None
