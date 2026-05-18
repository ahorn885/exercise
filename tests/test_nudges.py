"""Tests for `routes/nudges.py` D-66 consumer-side UI extensions.

Closes the consumer-side gap for the D-66 onboarding skip nudges
(`target_race_skipped` + `route_locales_incomplete`) that the
onboarding flow now writes at skip-time. Covers:

- `NUDGE_REGISTRY` registry shape for the two new entries +
  unchanged-shape verification for the PR9 `connect_provider_14d`
  entry (no `display_delay_days` field).
- `_past_display_delay` boundary handling — 0-delay always True,
  None created_at fail-open, naive vs aware datetime comparison.
- `get_active_nudges` filter behavior — recent D-66 nudges suppressed
  inside the 14-day grace window; older ones surface; PR9-style
  immediate nudges always surface; `display_delay_days` is stripped
  from the per-row output overlay so the template partial doesn't
  see the implementation detail.

Uses the `_FakeConn` / `_FakeCursor` pattern from
`tests/test_race_events_repo.py` + `tests/test_onboarding_race_events.py`
— no real DB.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest

from routes.nudges import (
    NUDGE_REGISTRY,
    _past_display_delay,
    get_active_nudges,
)


# ─── Shared fake conn (mirrors other test files) ───────────────────────────


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


# ─── NUDGE_REGISTRY shape ──────────────────────────────────────────────────


class TestNudgeRegistry:
    """The registry is the single source of truth for per-nudge_type UI
    metadata + delay policy. Onboarding write paths in routes/onboarding.py
    name these keys; the banner partial reads the overlay. Drift between
    writer and registry is loud (unknown nudge_type falls through to raw
    type as message) but registry shape changes should still be guarded.
    """

    def test_target_race_skipped_registered(self):
        entry = NUDGE_REGISTRY['target_race_skipped']
        assert entry['cta_endpoint'] == 'onboarding.target_race'
        assert entry['cta_label']
        assert entry['message']
        assert entry['category'] == 'info'
        # D-66 nudges are written at skip-time; 14-day delay applied on read.
        assert entry['display_delay_days'] == 14

    def test_route_locales_incomplete_registered(self):
        entry = NUDGE_REGISTRY['route_locales_incomplete']
        assert entry['cta_endpoint'] == 'onboarding.route_locales'
        assert entry['cta_label']
        assert entry['message']
        assert entry['category'] == 'info'
        assert entry['display_delay_days'] == 14

    def test_connect_provider_unchanged(self):
        # PR9's cron INSERTs the row only after the account is 14 days old,
        # so display-side delay would be a double-gate. Entry should NOT
        # carry display_delay_days (or carry 0).
        entry = NUDGE_REGISTRY['connect_provider_14d']
        assert entry['cta_endpoint'] == 'onboarding.connect'
        assert entry.get('display_delay_days', 0) == 0


# ─── _past_display_delay ────────────────────────────────────────────────────


class TestPastDisplayDelay:
    def test_zero_delay_always_true(self):
        # 0-delay short-circuits before any date arithmetic — the
        # connect_provider_14d default path.
        assert _past_display_delay(datetime.now(timezone.utc), 0) is True
        assert _past_display_delay(None, 0) is True

    def test_none_created_at_fails_open(self):
        # Legacy rows pre-dating the column default — display proceeds.
        # Mirrors PR9 cron's NULL created_at handling (treats as old enough).
        assert _past_display_delay(None, 14) is True

    def test_recent_created_at_suppresses(self):
        # Inside the grace window — nudge stays hidden.
        recent = datetime.now(timezone.utc) - timedelta(days=3)
        assert _past_display_delay(recent, 14) is False

    def test_old_created_at_surfaces(self):
        # Past the grace window — nudge displays.
        old = datetime.now(timezone.utc) - timedelta(days=20)
        assert _past_display_delay(old, 14) is True

    def test_boundary_at_exactly_delay_days(self):
        # 14 days, 1 hour ago — past the threshold; `.days` of timedelta
        # truncates toward zero so a hair under 14 days reads as 13.
        just_over = datetime.now(timezone.utc) - timedelta(days=14, hours=1)
        assert _past_display_delay(just_over, 14) is True
        just_under = datetime.now(timezone.utc) - timedelta(days=13, hours=23)
        assert _past_display_delay(just_under, 14) is False

    def test_naive_datetime_treated_as_utc(self):
        # PG TIMESTAMP column returns naive datetime via psycopg2 — we
        # must compare safely without TypeError.
        old_naive = (datetime.now(timezone.utc) - timedelta(days=20)).replace(tzinfo=None)
        assert _past_display_delay(old_naive, 14) is True
        recent_naive = (datetime.now(timezone.utc) - timedelta(days=3)).replace(tzinfo=None)
        assert _past_display_delay(recent_naive, 14) is False


# ─── get_active_nudges ──────────────────────────────────────────────────────


class TestGetActiveNudges:
    def test_falsy_uid_returns_empty_without_query(self):
        # Context processor on logged-out pages must be safe.
        conn = _FakeConn()
        assert get_active_nudges(conn, None) == []
        assert get_active_nudges(conn, 0) == []
        assert conn.calls == []

    def test_zero_delay_nudge_surfaces_immediately(self):
        # connect_provider_14d default path — no display_delay_days, banner
        # shows whenever the row exists.
        conn = _FakeConn()
        conn.queue_response(rows=[{
            'id': 1,
            'nudge_type': 'connect_provider_14d',
            'created_at': datetime.now(timezone.utc),
        }])
        out = get_active_nudges(conn, uid=42)
        assert len(out) == 1
        assert out[0]['nudge_type'] == 'connect_provider_14d'
        assert out[0]['cta_endpoint'] == 'onboarding.connect'

    def test_recent_d66_nudge_suppressed(self):
        # Athlete skipped target-race step yesterday — banner stays
        # hidden during the 14-day grace window.
        conn = _FakeConn()
        conn.queue_response(rows=[{
            'id': 1,
            'nudge_type': 'target_race_skipped',
            'created_at': datetime.now(timezone.utc) - timedelta(days=1),
        }])
        out = get_active_nudges(conn, uid=42)
        assert out == []

    def test_old_d66_nudge_surfaces(self):
        # Past the 14-day grace — banner displays.
        conn = _FakeConn()
        conn.queue_response(rows=[{
            'id': 7,
            'nudge_type': 'target_race_skipped',
            'created_at': datetime.now(timezone.utc) - timedelta(days=20),
        }])
        out = get_active_nudges(conn, uid=42)
        assert len(out) == 1
        assert out[0]['id'] == 7
        assert out[0]['nudge_type'] == 'target_race_skipped'
        assert out[0]['cta_endpoint'] == 'onboarding.target_race'

    def test_route_locales_incomplete_surfaces_after_delay(self):
        conn = _FakeConn()
        conn.queue_response(rows=[{
            'id': 9,
            'nudge_type': 'route_locales_incomplete',
            'created_at': datetime.now(timezone.utc) - timedelta(days=15),
        }])
        out = get_active_nudges(conn, uid=42)
        assert len(out) == 1
        assert out[0]['cta_endpoint'] == 'onboarding.route_locales'

    def test_mixed_recent_and_old(self):
        # Three rows in DB; one recent D-66 (filtered), one old D-66 (kept),
        # one zero-delay connect_provider_14d (kept). Order preserved per
        # ORDER BY created_at DESC SQL.
        now = datetime.now(timezone.utc)
        conn = _FakeConn()
        conn.queue_response(rows=[
            {
                'id': 1,
                'nudge_type': 'target_race_skipped',
                'created_at': now - timedelta(days=1),
            },
            {
                'id': 2,
                'nudge_type': 'route_locales_incomplete',
                'created_at': now - timedelta(days=20),
            },
            {
                'id': 3,
                'nudge_type': 'connect_provider_14d',
                'created_at': now - timedelta(days=5),
            },
        ])
        out = get_active_nudges(conn, uid=42)
        ids = [n['id'] for n in out]
        assert ids == [2, 3]

    def test_unknown_nudge_type_falls_through(self):
        # Forward-compat: a writer lands a new type before this registry
        # catches up. Show an ugly-but-visible banner rather than silent miss.
        conn = _FakeConn()
        conn.queue_response(rows=[{
            'id': 1,
            'nudge_type': 'some_future_nudge',
            'created_at': datetime.now(timezone.utc),
        }])
        out = get_active_nudges(conn, uid=42)
        assert len(out) == 1
        assert out[0]['message'] == 'some_future_nudge'
        assert out[0]['cta_endpoint'] is None

    def test_display_delay_days_stripped_from_overlay(self):
        # The banner partial shouldn't see the internal delay knob; it
        # only consumes the user-facing fields. Keeps the template
        # context surface stable as we add more delay-bearing entries.
        conn = _FakeConn()
        conn.queue_response(rows=[{
            'id': 1,
            'nudge_type': 'target_race_skipped',
            'created_at': datetime.now(timezone.utc) - timedelta(days=20),
        }])
        out = get_active_nudges(conn, uid=42)
        assert len(out) == 1
        assert 'display_delay_days' not in out[0]

    def test_naive_created_at_from_pg_handled(self):
        # psycopg2 returns TIMESTAMP columns as naive datetime; the filter
        # must not TypeError. Real production data path.
        old_naive = (datetime.now(timezone.utc) - timedelta(days=20)).replace(tzinfo=None)
        conn = _FakeConn()
        conn.queue_response(rows=[{
            'id': 1,
            'nudge_type': 'target_race_skipped',
            'created_at': old_naive,
        }])
        out = get_active_nudges(conn, uid=42)
        assert len(out) == 1

    def test_sql_scopes_to_user_and_undismissed(self):
        # Defense against accidental cross-user reads + dismissed-row
        # leakage; the registry overlay can't paper over a broken SQL.
        conn = _FakeConn()
        conn.queue_response(rows=[])
        get_active_nudges(conn, uid=42)
        sql, params = conn.calls[0]
        assert 'WHERE user_id = ? AND dismissed_at IS NULL' in sql
        assert 'ORDER BY created_at DESC' in sql
        assert params == (42,)
