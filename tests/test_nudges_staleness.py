"""Tests for the #964 reminder / staleness nudges.

Three concerns, all exercised without a real DB:

1. **Registry wiring** — the staleness `NUDGE_REGISTRY` entries
   (`log_reminder`, `body_metric_stale`, `injury_review`) plus the
   plan-attention `plan_needs_review` entry each carry a CTA + their own
   `notification_type`, and the matching `notification_prefs` types are
   registered in-app + push (email deliberately non-applicable — there's no
   nudge→email path and `email` is `available`, so a toggle would imply a
   delivery that never happens).

2. **Preference gating** — `get_active_nudges` suppresses a nudge whose mapped
   in-app notification type is muted, and fails **open** (shows it) if the
   preference read raises. The internal `notification_type` knob never leaks
   into the per-row overlay.

3. **Reconcile cron** — `/cron/nudges/reconcile` is token-gated, and for each
   staleness type runs a DELETE (clear) then an INSERT (arm), reporting per-type
   counts. The DELETE is what lets a one-shot-`UNIQUE` row re-fire later.

Reuses the `_FakeConn` pattern from `tests/test_nudges.py`.
"""

from __future__ import annotations

import os
import sys
from datetime import datetime, timezone

import pytest

os.environ.setdefault('SECRET_KEY', 'test-secret-key-for-staleness')
os.environ['DATABASE_URL'] = ''

import notification_prefs as np  # noqa: E402
from routes.nudges import (  # noqa: E402
    NUDGE_REGISTRY,
    PLAN_REVIEW_RUNGS,
    _STALENESS_RECONCILE,
    get_active_nudges,
)

STALENESS_TYPES = ['log_reminder', 'body_metric_stale', 'injury_review']
# All types the reconcile cron arms/clears — the staleness three plus the
# plan-attention nudge and the race-week reminder (both covered on their own
# below; `plan_needs_review` is `warning`, so it's excluded from the
# `info`-asserting parametrized tests above).
RECONCILE_TYPES = STALENESS_TYPES + ['plan_needs_review', 'race_week_plan_due']


# ─── Shared fake conn (mirrors tests/test_nudges.py) ────────────────────────


class _FakeRow(dict):
    def __getitem__(self, key):
        if isinstance(key, int):
            return list(self.values())[key]
        return super().__getitem__(key)


class _FakeCursor:
    def __init__(self, rows=None):
        self._rows = rows or []

    def fetchone(self):
        return _FakeRow(self._rows[0]) if self._rows else None

    def fetchall(self):
        return [_FakeRow(r) for r in self._rows]


class _FakeConn:
    """Pops queued row-lists in execute() order; records every (sql, params)."""

    def __init__(self):
        self.calls: list[tuple[str, tuple]] = []
        self.commits = 0
        self.responses: list[list] = []

    def queue(self, rows):
        self.responses.append(rows or [])

    def execute(self, sql, params=()):
        self.calls.append((' '.join(sql.split()), params))
        rows = self.responses.pop(0) if self.responses else []
        return _FakeCursor(rows)

    def commit(self):
        self.commits += 1


# ─── 1. Registry wiring ─────────────────────────────────────────────────────


class TestRegistryWiring:
    @pytest.mark.parametrize('nt', STALENESS_TYPES)
    def test_nudge_registry_entry(self, nt):
        entry = NUDGE_REGISTRY[nt]
        assert entry['message']
        assert entry['cta_label']
        assert entry['cta_endpoint']  # a real Flask endpoint
        assert entry['category'] == 'info'
        # Each maps to its own preference type so it can be muted independently.
        assert entry['notification_type'] == nt
        # No display delay — the cron's condition IS the gate.
        assert entry.get('display_delay_days', 0) == 0

    @pytest.mark.parametrize('nt', STALENESS_TYPES)
    def test_notification_type_registered_in_app_and_push(self, nt):
        t = np.TYPES_BY_KEY[nt]
        assert t['channels'] == ['in_app', 'push']
        # In-app on by default; push storable-but-undeliverable per project
        # convention.
        assert np.default_enabled(nt, 'in_app') is True
        assert np.default_enabled(nt, 'push') is True
        # Email is NOT applicable — no nudge→email path; an enabled toggle
        # would falsely imply delivery.
        assert np.is_applicable(nt, 'email') is False
        assert np.default_enabled(nt, 'email') is False

    def test_existing_nudges_roll_up_to_account_reminders(self):
        for nt in ('connect_provider_14d', 'target_race_skipped',
                   'route_locales_incomplete'):
            assert NUDGE_REGISTRY[nt]['notification_type'] == 'account_reminders'


class TestPlanNeedsReviewWiring:
    """The plan-attention nudge mirrors the staleness wiring but carries a
    `warning` category (it blocks a plan from finishing) and its own mutable
    notification type."""

    def test_registry_entry(self):
        entry = NUDGE_REGISTRY['plan_needs_review']
        assert entry['message']
        assert entry['cta_label']
        assert entry['cta_endpoint'] == 'plans.list_plans'
        assert entry['category'] == 'warning'
        assert entry['notification_type'] == 'plan_needs_review'
        assert entry.get('display_delay_days', 0) == 0

    def test_notification_type_registered_in_app_and_push(self):
        t = np.TYPES_BY_KEY['plan_needs_review']
        assert t['channels'] == ['in_app', 'push']
        assert t['category'] == 'warning'
        assert np.default_enabled('plan_needs_review', 'in_app') is True
        assert np.default_enabled('plan_needs_review', 'push') is True
        # Email non-applicable — no nudge→email path (same posture as staleness).
        assert np.is_applicable('plan_needs_review', 'email') is False


class TestRaceWeekPlanDueWiring:
    """The race-week reminder fires when the target race is inside the 14-day
    window with no brief generated yet. `info` category (a reminder to act, not
    a blocker) with its own mutable notification type."""

    def test_registry_entry(self):
        entry = NUDGE_REGISTRY['race_week_plan_due']
        assert entry['message']
        assert entry['cta_label']
        # CTA lands on the plan list (view_brief 404s pre-brief, generate is POST).
        assert entry['cta_endpoint'] == 'plans.list_plans'
        assert entry['category'] == 'info'
        assert entry['notification_type'] == 'race_week_plan_due'
        assert entry.get('display_delay_days', 0) == 0

    def test_notification_type_registered_in_app_and_push(self):
        t = np.TYPES_BY_KEY['race_week_plan_due']
        assert t['channels'] == ['in_app', 'push']
        assert t['category'] == 'info'
        assert np.default_enabled('race_week_plan_due', 'in_app') is True
        assert np.default_enabled('race_week_plan_due', 'push') is True
        # Email non-applicable — no nudge→email path (same posture as staleness).
        assert np.is_applicable('race_week_plan_due', 'email') is False


# ─── 2. Preference gating in get_active_nudges ──────────────────────────────


class TestPreferenceGating:
    def test_muted_type_suppressed(self):
        conn = _FakeConn()
        # First read: the undismissed nudge rows.
        conn.queue([
            {'id': 1, 'nudge_type': 'log_reminder',
             'created_at': datetime.now(timezone.utc)},
            {'id': 2, 'nudge_type': 'connect_provider_14d',
             'created_at': datetime.now(timezone.utc)},
        ])
        # Second read (disabled_in_app_types): log_reminder muted in-app.
        conn.queue([{'notification_type': 'log_reminder'}])
        out = get_active_nudges(conn, uid=42)
        ids = [n['id'] for n in out]
        assert ids == [2]  # log_reminder suppressed, connect_provider kept

    def test_nothing_muted_shows_all(self):
        conn = _FakeConn()
        conn.queue([
            {'id': 1, 'nudge_type': 'body_metric_stale',
             'created_at': datetime.now(timezone.utc)},
        ])
        conn.queue([])  # no overrides → nothing muted
        out = get_active_nudges(conn, uid=42)
        assert [n['id'] for n in out] == [1]

    def test_notification_type_not_leaked_into_overlay(self):
        conn = _FakeConn()
        conn.queue([
            {'id': 1, 'nudge_type': 'injury_review',
             'created_at': datetime.now(timezone.utc)},
        ])
        conn.queue([])
        out = get_active_nudges(conn, uid=42)
        assert len(out) == 1
        assert 'notification_type' not in out[0]
        assert 'display_delay_days' not in out[0]
        assert out[0]['cta_endpoint'] == 'injuries.list_entries'

    def test_preference_read_fault_fails_open(self, monkeypatch):
        # A store hiccup must never hide a nudge.
        import routes.nudges as nudges_mod

        def _boom(db, uid):
            raise RuntimeError('pref store down')

        monkeypatch.setattr(nudges_mod, 'disabled_in_app_types', _boom)
        conn = _FakeConn()
        conn.queue([
            {'id': 1, 'nudge_type': 'log_reminder',
             'created_at': datetime.now(timezone.utc)},
        ])
        out = get_active_nudges(conn, uid=42)
        assert [n['id'] for n in out] == [1]


# ─── 3. Reconcile spec + cron route ─────────────────────────────────────────


class TestReconcileSpec:
    def test_spec_covers_all_staleness_types(self):
        assert {s['nudge_type'] for s in _STALENESS_RECONCILE} == set(RECONCILE_TYPES)

    def test_plan_needs_review_spec_targets_live_parked_plans(self):
        spec = next(s for s in _STALENESS_RECONCILE
                    if s['nudge_type'] == 'plan_needs_review')
        ins = ' '.join(spec['insert'].split())
        dele = ' '.join(spec['delete'].split())
        res = ' '.join(spec['resurface'].split())
        # Fires only on a live (non-superseded, non-archived) plan parked at the
        # review gate; all three statements share that exact predicate.
        for clause in ("generation_status = 'needs_review'",
                       'superseded_at IS NULL', 'archived_at IS NULL'):
            assert clause in ins
            assert clause in dele
            assert clause in res
        # Rung 1 arms the first insert; the delete is age-agnostic.
        assert "INTERVAL '1 day'" in ins
        assert 'INTERVAL' not in dele

    def test_plan_needs_review_resurface_escalates_on_later_rungs(self):
        spec = next(s for s in _STALENESS_RECONCILE
                    if s['nudge_type'] == 'plan_needs_review')
        res = ' '.join(spec['resurface'].split())
        # Re-surface re-arms a seen nudge: clears dismissal + unread + floats it
        # up (re-stamped created_at). Re-stamping is what bounds it to once per
        # rung (created_at then sits at/after the threshold).
        assert res.startswith('UPDATE account_nudges')
        assert 'dismissed_at = NULL' in res
        assert 'read_at = NULL' in res
        assert 'created_at = NOW()' in res
        # The later rungs (every PLAN_REVIEW_RUNGS entry past the first) drive it;
        # the first rung is the insert gate, not a re-surface.
        for rung in PLAN_REVIEW_RUNGS[1:]:
            assert "INTERVAL '%s'" % rung in res
        assert "INTERVAL '%s'" % PLAN_REVIEW_RUNGS[0] not in res

    def test_race_week_plan_due_spec_targets_target_race_and_active_plan(self):
        spec = next(s for s in _STALENESS_RECONCILE
                    if s['nudge_type'] == 'race_week_plan_due')
        ins = ' '.join(spec['insert'].split())
        dele = ' '.join(spec['delete'].split())
        # No escalation ladder for this one — a plain insert/delete pair.
        assert 'resurface' not in spec
        # Both fire/clear off the same eligibility: the athlete's target race
        # inside the 14-day window, still future, with an active plan that has no
        # brief yet. The brief-absent check keys off `race_week_briefs`.
        for clause in ('re.is_target_event = TRUE',
                       're.event_date >= CURRENT_DATE',
                       'CURRENT_DATE + %d' % 14,
                       'FROM race_week_briefs rwb'):
            assert clause in ins
            assert clause in dele
        # Active-plan predicate mirrors load_active_plan_version_id (ready, not
        # archived, not completed) so the brief check targets the right version.
        for clause in ("generation_status = 'ready'",
                       'archived_at IS NULL', 'completed_at IS NULL'):
            assert clause in ins
            assert clause in dele

    @pytest.mark.parametrize('spec', _STALENESS_RECONCILE)
    def test_each_spec_has_insert_and_delete(self, spec):
        ins = ' '.join(spec['insert'].split())
        dele = ' '.join(spec['delete'].split())
        assert ins.startswith("INSERT INTO account_nudges")
        # Idempotent re-insert + one-shot guard.
        assert 'ON CONFLICT (user_id, nudge_type) DO NOTHING' in ins
        assert "nudge_type = '%s'" % spec['nudge_type'] in ins or \
               "'%s'" % spec['nudge_type'] in ins
        # The DELETE is scoped strictly to this type — never touches the
        # onboarding/connect nudges.
        assert dele.startswith('DELETE FROM account_nudges')
        assert "an.nudge_type = '%s'" % spec['nudge_type'] in dele
        assert 'RETURNING id' in ins and 'RETURNING id' in dele


def _cron_client(monkeypatch, conn):
    import app as _appmod
    for mod in list(sys.modules.values()):
        if mod is not None and getattr(mod, 'get_db', None) is not None:
            monkeypatch.setattr(mod, 'get_db', lambda conn=conn: conn,
                                raising=False)
    _appmod.app.config['TESTING'] = True
    return _appmod.app.test_client()


class TestReconcileRoute:
    def test_unauthorized_without_token(self, monkeypatch):
        monkeypatch.delenv('CRON_SECRET', raising=False)
        conn = _FakeConn()
        client = _cron_client(monkeypatch, conn)
        resp = client.get('/cron/nudges/reconcile')
        assert resp.status_code == 401
        assert conn.calls == []  # never touched the DB

    def test_authorized_runs_delete_then_insert_per_type(self, monkeypatch):
        monkeypatch.setenv('CRON_SECRET', 's3cret')
        conn = _FakeConn()
        # Per type: delete (1 cleared), insert (2 armed), and — for a type with
        # a `resurface` statement — an update (1 re-armed), in that order.
        expected_kinds = []
        for s in _STALENESS_RECONCILE:
            conn.queue([{'id': 10}])              # delete
            conn.queue([{'id': 20}, {'id': 21}])  # insert
            expected_kinds += ['DELETE', 'INSERT']
            if s.get('resurface'):
                conn.queue([{'id': 30}])          # resurface
                expected_kinds.append('UPDATE')
        client = _cron_client(monkeypatch, conn)
        resp = client.get('/cron/nudges/reconcile',
                          headers={'Authorization': 'Bearer s3cret'})
        assert resp.status_code == 200
        body = resp.get_json()
        for s in _STALENESS_RECONCILE:
            assert body['cleared'][s['nudge_type']] == 1
            assert body['inserted'][s['nudge_type']] == 2
            if s.get('resurface'):
                assert body['resurfaced'][s['nudge_type']] == 1
        # Exactly one commit, and the statements ran in delete→insert→resurface
        # order per type.
        assert conn.commits == 1
        kinds = [c[0].split()[0] for c in conn.calls]
        assert kinds == expected_kinds
