"""Tests for `notification_preferences_repo.py` — the per-user override store
(#963).

Self-contained fakes — no live Postgres. A recording fake db captures
`(sql, params)` so the tests can assert the upsert conflict target, the
user-scoping, and the fail-open posture of the delivery-time gates.
"""

from __future__ import annotations

import notification_preferences_repo as repo


class _Cur:
    def __init__(self, row=None, rows=None):
        self._row = row
        self._rows = rows or []

    def fetchone(self):
        return self._row

    def fetchall(self):
        return self._rows


class _FakeRow(dict):
    pass


class _RecordingDb:
    """Records every (sql, params); hands back canned cursors FIFO. An
    exhausted list yields an empty cursor (the "this query doesn't matter"
    case). `raise_on` makes execute throw to exercise fail-open paths."""

    def __init__(self, responses=None, raise_on=None):
        self.calls: list[tuple[str, tuple]] = []
        self._responses = list(responses or [])
        self.committed = 0
        self._raise_on = raise_on

    def execute(self, sql, params=()):
        self.calls.append((sql, params))
        if self._raise_on and self._raise_on in sql:
            raise RuntimeError('no such table')
        if self._responses:
            return self._responses.pop(0)
        return _Cur(None)

    def commit(self):
        self.committed += 1


# ─── get_overrides ───────────────────────────────────────────────────────────


def test_get_overrides_empty_for_falsy_user():
    db = _RecordingDb()
    assert repo.get_overrides(db, 0) == {}
    assert db.calls == []


def test_get_overrides_maps_type_channel_to_bool():
    rows = [
        _FakeRow(notification_type='plan_ready', channel='email', enabled=False),
        _FakeRow(notification_type='science_update', channel='in_app', enabled=True),
    ]
    db = _RecordingDb(responses=[_Cur(rows=rows)])
    out = repo.get_overrides(db, 42)
    assert out == {('plan_ready', 'email'): False,
                   ('science_update', 'in_app'): True}
    sql, params = db.calls[0]
    assert 'FROM notification_preferences WHERE user_id = ?' in sql
    assert params == (42,)


# ─── resolve ─────────────────────────────────────────────────────────────────


def test_resolve_prefers_override_then_default():
    overrides = {('plan_ready', 'email'): False}
    # Override wins.
    assert repo.resolve('plan_ready', 'email', overrides) is False
    # No override → registry default (plan_ready in_app default True).
    assert repo.resolve('plan_ready', 'in_app', overrides) is True
    # Non-applicable is always False, even if an override sneaks in.
    assert repo.resolve('account_reminders', 'email',
                        {('account_reminders', 'email'): True}) is False


# ─── build_matrix ────────────────────────────────────────────────────────────


def test_build_matrix_rows_and_cells_align_to_channels():
    db = _RecordingDb(responses=[_Cur(rows=[])])
    matrix = repo.build_matrix(db, 42)
    keys = [r['key'] for r in matrix]
    assert 'plan_ready' in keys and 'account_reminders' in keys
    plan_ready = next(r for r in matrix if r['key'] == 'plan_ready')
    # One cell per channel, in channel order, each with a form field name.
    assert [c['channel'] for c in plan_ready['cells']] == ['in_app', 'push', 'email']
    email_cell = plan_ready['cells'][2]
    assert email_cell['field'] == 'pref:plan_ready:email'
    assert email_cell['applicable'] is True
    assert email_cell['enabled'] is True          # default on
    assert email_cell['available'] is True
    # push cell is applicable but unavailable (wired, undeliverable).
    push_cell = plan_ready['cells'][1]
    assert push_cell['applicable'] is True
    assert push_cell['available'] is False
    # account_reminders: only in_app applicable.
    ar = next(r for r in matrix if r['key'] == 'account_reminders')
    assert ar['cells'][0]['applicable'] is True   # in_app
    assert ar['cells'][2]['applicable'] is False  # email


def test_build_matrix_applies_overrides():
    rows = [_FakeRow(notification_type='plan_ready', channel='email',
                     enabled=False)]
    db = _RecordingDb(responses=[_Cur(rows=rows)])
    matrix = repo.build_matrix(db, 42)
    plan_ready = next(r for r in matrix if r['key'] == 'plan_ready')
    assert plan_ready['cells'][2]['enabled'] is False  # override took


def test_build_matrix_degrades_to_defaults_on_read_fault():
    # SQLite dev (no table) must still render the defaults, not 500.
    db = _RecordingDb(raise_on='notification_preferences')
    matrix = repo.build_matrix(db, 42)
    plan_ready = next(r for r in matrix if r['key'] == 'plan_ready')
    assert plan_ready['cells'][2]['enabled'] is True   # default on


# ─── set_pref ────────────────────────────────────────────────────────────────


def test_set_pref_upserts_with_conflict_target():
    db = _RecordingDb()
    assert repo.set_pref(db, 42, 'plan_ready', 'email', False) is True
    sql, params = db.calls[0]
    assert 'INSERT INTO notification_preferences' in sql
    assert 'ON CONFLICT (user_id, notification_type, channel)' in sql
    assert 'DO UPDATE SET enabled = EXCLUDED.enabled' in sql
    assert params == (42, 'plan_ready', 'email', False)


def test_set_pref_noops_non_applicable_and_falsy_user():
    db = _RecordingDb()
    assert repo.set_pref(db, 42, 'account_reminders', 'email', True) is False
    assert repo.set_pref(db, 0, 'plan_ready', 'email', True) is False
    assert db.calls == []


# ─── save_from_form ──────────────────────────────────────────────────────────


def test_save_from_form_writes_checked_and_unchecked():
    db = _RecordingDb()
    # Only plan_ready:email checked; every other applicable cell is "off".
    form = {'pref:plan_ready:email': 'on'}
    written = repo.save_from_form(db, 42, form)
    assert db.committed == 1
    # One write per applicable cell across the registry (off cells too).
    assert written == len(db.calls)
    # The checked cell wrote True; an unchecked one wrote False.
    by_cell = {(p[1], p[2]): p[3] for (s, p) in db.calls}
    assert by_cell[('plan_ready', 'email')] is True
    assert by_cell[('plan_ready', 'in_app')] is False


def test_save_from_form_noop_for_falsy_user():
    db = _RecordingDb()
    assert repo.save_from_form(db, 0, {'pref:plan_ready:email': 'on'}) == 0
    assert db.calls == []


# ─── channel_enabled (delivery-time gate) ────────────────────────────────────


def test_channel_enabled_uses_override_when_present():
    db = _RecordingDb(responses=[_Cur(row=_FakeRow(enabled=False))])
    assert repo.channel_enabled(db, 42, 'plan_ready', 'email') is False
    sql, params = db.calls[0]
    assert 'SELECT enabled FROM notification_preferences' in sql
    assert params == (42, 'plan_ready', 'email')


def test_channel_enabled_falls_back_to_default_without_row():
    db = _RecordingDb(responses=[_Cur(row=None)])
    assert repo.channel_enabled(db, 42, 'plan_ready', 'email') is True


def test_channel_enabled_fails_open_to_default_on_fault():
    db = _RecordingDb(raise_on='notification_preferences')
    # Read blows up (SQLite dev) → send anyway (registry default True).
    assert repo.channel_enabled(db, 42, 'plan_ready', 'email') is True


def test_channel_enabled_false_for_non_applicable():
    db = _RecordingDb()
    assert repo.channel_enabled(db, 42, 'account_reminders', 'email') is False
    assert db.calls == []  # never queried — non-applicable short-circuits


# ─── disabled_in_app_types (badge gate) ──────────────────────────────────────


def test_disabled_in_app_types_returns_opted_out_set():
    rows = [_FakeRow(notification_type='plan_failed')]
    db = _RecordingDb(responses=[_Cur(rows=rows)])
    out = repo.disabled_in_app_types(db, 42)
    assert out == {'plan_failed'}
    sql, params = db.calls[0]
    assert "channel = ? AND enabled = FALSE" in sql
    assert params == (42, 'in_app')


def test_disabled_in_app_types_empty_on_fault():
    db = _RecordingDb(raise_on='notification_preferences')
    assert repo.disabled_in_app_types(db, 42) == set()


def test_disabled_in_app_types_empty_for_falsy_user():
    db = _RecordingDb()
    assert repo.disabled_in_app_types(db, 0) == set()
    assert db.calls == []
