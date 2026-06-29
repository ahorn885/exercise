"""Tests for the #964 recurring-send schedule store (Slice 1 — storage + capture).

Covers the parts that ship without the delivery cron (Slice 2):

1. **Preference wiring** — the three new `notification_prefs` types
   (`supplement_reminder`, `next_day_workouts`, `daily_log_ping`) are registered
   in-app + push, `info`, with email deliberately non-applicable (no nudge→email
   path).
2. **Schedule registry** — `SCHEDULE_TYPES` map to their preference types (the
   two supplement send times roll up to one `supplement_reminder` toggle), and
   the hour/timezone option lists are sane.
3. **Repo** — `build_schedule_view` resolves stored rows over off-at-default
   defaults and fails open; `save_schedules_from_form` writes each type from the
   form (off state captured by registry iteration, bad hour → default), persists
   a valid timezone and rejects an invalid one, and commits once. `set_schedule`
   / `set_user_timezone` reject crafted bad input.

No real DB — a fake conn records every (sql, params) and replays queued rows,
mirroring `tests/test_nudges_staleness.py`.
"""

from __future__ import annotations

import os

import pytest

os.environ.setdefault('SECRET_KEY', 'test-secret-key-for-schedules')
os.environ['DATABASE_URL'] = ''

import notification_prefs as np  # noqa: E402
import notification_schedules_repo as nsr  # noqa: E402

NEW_PREF_TYPES = ['supplement_reminder', 'next_day_workouts', 'daily_log_ping']


# ─── Fake conn (mirrors tests/test_nudges_staleness.py) ─────────────────────


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


# ─── 1. Preference wiring ───────────────────────────────────────────────────


class TestNewPreferenceTypes:
    @pytest.mark.parametrize('nt', NEW_PREF_TYPES)
    def test_registered_in_app_and_push_info(self, nt):
        t = np.TYPES_BY_KEY[nt]
        assert t['category'] == 'info'
        assert t['channels'] == ['in_app', 'push']
        assert np.default_enabled(nt, 'in_app') is True
        assert np.default_enabled(nt, 'push') is True
        # Email non-applicable — no nudge→email path; a toggle would imply a
        # delivery that never happens.
        assert np.is_applicable(nt, 'email') is False
        assert np.default_enabled(nt, 'email') is False


# ─── 2. Schedule registry ───────────────────────────────────────────────────


class TestScheduleRegistry:
    def test_supplement_times_roll_up_to_one_toggle(self):
        by_key = {s['key']: s for s in nsr.SCHEDULE_TYPES}
        assert by_key['supplement_am']['notification_type'] == 'supplement_reminder'
        assert by_key['supplement_pm']['notification_type'] == 'supplement_reminder'

    @pytest.mark.parametrize('s', nsr.SCHEDULE_TYPES)
    def test_each_type_maps_to_a_registered_pref(self, s):
        # The gate type a schedule rolls up to must be a real preference type.
        assert s['notification_type'] in np.TYPES_BY_KEY
        assert 0 <= s['default_hour'] <= 23

    def test_hour_choices_cover_the_day(self):
        values = [v for v, _ in nsr.HOUR_CHOICES]
        assert values == list(range(24))
        # 12-hour labels with AM/PM (e.g. 0 → '12:00 AM', 13 → '1:00 PM').
        labels = dict(nsr.HOUR_CHOICES)
        assert labels[0] == '12:00 AM'
        assert labels[13] == '1:00 PM'

    def test_timezones_curated_and_include_utc(self):
        assert 'UTC' in nsr.TIMEZONES
        assert 'America/Chicago' in nsr.TIMEZONES


# ─── 3. Repo ────────────────────────────────────────────────────────────────


class TestBuildScheduleView:
    def test_defaults_off_at_default_hour_when_no_rows(self):
        db = _FakeConn()
        db.queue([])                          # get_schedules → no stored rows
        db.queue([{'timezone': None}])        # get_user_timezone
        view = nsr.build_schedule_view(db, 1)
        assert view['timezone'] is None
        by_key = {r['key']: r for r in view['rows']}
        am = by_key['supplement_am']
        assert am['enabled'] is False
        assert am['send_hour'] == 7           # default_hour
        assert am['hour_field'] == 'sched:supplement_am:hour'
        assert am['enabled_field'] == 'sched:supplement_am:enabled'

    def test_stored_row_overrides_default(self):
        db = _FakeConn()
        db.queue([{'schedule_type': 'supplement_am',
                   'send_hour': 6, 'enabled': True}])
        db.queue([{'timezone': 'America/Chicago'}])
        view = nsr.build_schedule_view(db, 1)
        assert view['timezone'] == 'America/Chicago'
        am = next(r for r in view['rows'] if r['key'] == 'supplement_am')
        assert am['enabled'] is True
        assert am['send_hour'] == 6

    def test_read_fault_degrades_to_defaults(self):
        class _Boom(_FakeConn):
            def execute(self, sql, params=()):
                raise RuntimeError('no such table')
        view = nsr.build_schedule_view(_Boom(), 1)
        # Renders every type at its default, timezone unset.
        assert view['timezone'] is None
        assert len(view['rows']) == len(nsr.SCHEDULE_TYPES)
        assert all(r['enabled'] is False for r in view['rows'])


class TestSaveSchedulesFromForm:
    def test_writes_each_type_and_timezone_and_commits_once(self):
        db = _FakeConn()
        form = {
            'sched:supplement_am:hour': '6',
            'sched:supplement_am:enabled': 'on',
            # supplement_pm absent ⇒ off
            'sched:supplement_pm:hour': '20',
            'sched:next_day_workouts:hour': 'not-a-number',  # → default
            'sched:daily_log_ping:hour': '21',
            'sched:daily_log_ping:enabled': 'on',
            'timezone': 'America/Chicago',
        }
        written = nsr.save_schedules_from_form(db, 1, form)
        assert written == 4              # all four schedule rows written
        assert db.commits == 1           # one commit for the whole submit

        # Index the recorded schedule upserts by their (type) param.
        sched_calls = {c[1][1]: c[1] for c in db.calls
                       if c[1] and c[1][0] == 1 and len(c[1]) == 4}
        # supplement_am: enabled True at hour 6.
        assert sched_calls['supplement_am'][2] == 6
        assert sched_calls['supplement_am'][3] is True
        # supplement_pm: off (checkbox absent).
        assert sched_calls['supplement_pm'][3] is False
        # next_day_workouts: bad hour fell back to its default (19).
        assert sched_calls['next_day_workouts'][2] == 19
        # Timezone persisted via an UPDATE.
        assert any('UPDATE users SET timezone' in c[0] for c in db.calls)

    def test_invalid_timezone_not_persisted(self):
        db = _FakeConn()
        form = {'timezone': 'Mars/Olympus_Mons'}
        nsr.save_schedules_from_form(db, 1, form)
        assert not any('UPDATE users SET timezone' in c[0] for c in db.calls)

    def test_falsy_user_writes_nothing(self):
        db = _FakeConn()
        assert nsr.save_schedules_from_form(db, 0, {'timezone': 'UTC'}) == 0
        assert db.calls == []
        assert db.commits == 0


class TestGuards:
    def test_set_schedule_rejects_unknown_type_and_bad_hour(self):
        db = _FakeConn()
        assert nsr.set_schedule(db, 1, 'not_a_type', 7, True) is False
        assert nsr.set_schedule(db, 1, 'supplement_am', 99, True) is False
        assert nsr.set_schedule(db, 1, 'supplement_am', -1, True) is False
        assert nsr.set_schedule(db, 0, 'supplement_am', 7, True) is False
        assert db.calls == []            # nothing written for any rejected input

    def test_set_user_timezone_rejects_unlisted(self):
        db = _FakeConn()
        assert nsr.set_user_timezone(db, 1, 'Mars/Olympus_Mons') is False
        assert nsr.set_user_timezone(db, 1, None) is False
        assert nsr.set_user_timezone(db, 0, 'UTC') is False
        assert db.calls == []
        # A listed zone is accepted.
        assert nsr.set_user_timezone(db, 1, 'UTC') is True
        assert len(db.calls) == 1

    def test_get_user_timezone_fails_open_to_none(self):
        class _Boom(_FakeConn):
            def execute(self, sql, params=()):
                raise RuntimeError('no such column')
        assert nsr.get_user_timezone(_Boom(), 1) is None
