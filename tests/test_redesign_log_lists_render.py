"""Render smoke tests for the redesign logging history lists (finish-the-open).

§08 migrated the logging entry *forms*; these are the history *list* views
(training / cardio / body / conditions), now on the new `.app` shell. Boots the
real app with a permissive fake DB and drives each GET route on the empty
branch (Jinja still compiles the populated table block), asserting the new
shell + topbar CTA + CSP-cleanliness.
"""

from __future__ import annotations

import os
import sys

os.environ.setdefault('SECRET_KEY', 'test-secret-key-for-render-tests')
os.environ['DATABASE_URL'] = ''

import app as _appmod  # noqa: E402


class _FakeRow(dict):
    pass


class _Cursor:
    def fetchone(self):
        return _FakeRow(id=1, username='owner', email='o@x.test', display_name='Owner')

    def fetchall(self):
        return []


class _Conn:
    def execute(self, sql, *a, **k):
        return _Cursor()

    def commit(self):
        pass


def _client(monkeypatch):
    conn = _Conn()
    for mod in list(sys.modules.values()):
        if mod is not None and getattr(mod, 'get_db', None) is not None:
            monkeypatch.setattr(mod, 'get_db', lambda conn=conn: conn, raising=False)
    _appmod.app.config['TESTING'] = True
    c = _appmod.app.test_client()
    with c.session_transaction() as sess:
        sess['user_id'] = 1
    return c


def _check(monkeypatch, path, title):
    resp = _client(monkeypatch).get(path)
    assert resp.status_code == 200, f'{path} → {resp.status_code}'
    html = resp.get_data(as_text=True)
    assert 'app-shell' in html          # new shell, not base_legacy
    assert title in html
    assert 'style="' not in html        # CSP-clean
    assert 'onclick=' not in html
    return html


def test_training_list_render(monkeypatch):
    # /training is the federated Workouts feed (#441) — strength + cardio.
    html = _check(monkeypatch, '/training', 'Workouts.')
    assert 'Log strength' in html       # topbar CTAs (both modalities)
    assert 'Log cardio' in html
    # Modality filter replaced the strength-only exercise filter.
    assert 'name="modality"' in html


def test_cardio_list_render(monkeypatch):
    # The cardio-specific list survives at /cardio for back-compat; the
    # sidebar's Workouts entry points at the federated /training feed.
    _check(monkeypatch, '/cardio', 'Cardio log.')


def test_workouts_feed_aggregates_strength_by_session(monkeypatch):
    """SQL-routed fake: a strength session with multiple exercises renders
    as ONE row on /training, not one row per exercise. Cardio interleaves."""

    # One strength session on 2026-06-05 with three exercises.
    session_row = _FakeRow(id=7, date='2026-06-05', notes=None, plan_item_id=None)
    log_rows = [
        _FakeRow(id=11, session_id=7, exercise='Back squat', volume=3375),
        _FakeRow(id=12, session_id=7, exercise='Bench press', volume=2250),
        _FakeRow(id=13, session_id=7, exercise='Deadlift',    volume=4500),
    ]
    cardio_row = _FakeRow(
        id=22, date='2026-06-06', activity='Trail Running', activity_name='Lebanon hills',
        duration_min=62, distance_mi=6.4, avg_pace='9:42', avg_speed=None,
        avg_hr=148, elev_gain_ft=420, avg_power=None, norm_power=None, aerobic_te=3.1,
    )

    class _RoutedCursor:
        def __init__(self, rows): self._rows = rows
        def fetchone(self):
            return _FakeRow(id=1, username='owner', email='o@x.test', display_name='Owner')
        def fetchall(self):
            return self._rows

    class _RoutedConn:
        def execute(self, sql, *_a, **_k):
            s = sql.lower()
            if 'from training_sessions' in s:
                return _RoutedCursor([session_row])
            if 'from training_log' in s and 'training_log_sets' not in s:
                return _RoutedCursor(log_rows)
            if 'from cardio_log' in s:
                return _RoutedCursor([cardio_row])
            return _RoutedCursor([])
        def commit(self):
            pass

    conn = _RoutedConn()
    for mod in list(sys.modules.values()):
        if mod is not None and getattr(mod, 'get_db', None) is not None:
            monkeypatch.setattr(mod, 'get_db', lambda conn=conn: conn, raising=False)
    _appmod.app.config['TESTING'] = True
    c = _appmod.app.test_client()
    with c.session_transaction() as sess:
        sess['user_id'] = 1
    resp = c.get('/training')
    assert resp.status_code == 200
    html = resp.get_data(as_text=True)
    # Strength session aggregates: ONE row showing the count + summary, NOT
    # three rows (one per exercise).
    assert '3 exercises' in html
    assert 'Back squat' in html and 'Bench press' in html and 'Deadlift' in html
    # Cardio still renders independently and sorts before strength (date desc).
    assert 'Trail Running' in html
    assert html.index('Trail Running') < html.index('3 exercises')
    # The per-exercise outcome / 1RM / Next Rx columns are gone from the feed.
    assert 'Next Rx' not in html and 'Target' not in html
    assert 'style="' not in html


def test_session_detail_renders_each_exercise(monkeypatch):
    """The new /training/session/<id> detail page renders every exercise in
    the session with its per-set chips + outcome + per-exercise edit link."""

    session_row = _FakeRow(id=7, date='2026-06-05', notes='Heavy day.',
                           user_id=1, plan_item_id=None)
    log_rows = [
        _FakeRow(id=11, session_id=7, exercise='Back squat',
                 target_sets=3, target_reps=5, target_weight=225,
                 actual_sets=3, actual_reps=5, actual_weight=225,
                 rpe=8, volume=3375, est_1rm=275,
                 outcome='PROGRESS ↑', next_sets=3, next_reps=5, next_weight=230,
                 notes=None),
        _FakeRow(id=12, session_id=7, exercise='Bench press',
                 target_sets=None, target_reps=None, target_weight=None,
                 actual_sets=3, actual_reps=8, actual_weight=185,
                 rpe=7, volume=4440, est_1rm=235,
                 outcome='REPEAT →', next_sets=3, next_reps=8, next_weight=185,
                 notes=None),
    ]
    sets_rows = [
        _FakeRow(id=101, training_log_id=11, set_number=1, reps=5, weight_kg=102, duration_sec=None),
        _FakeRow(id=102, training_log_id=11, set_number=2, reps=5, weight_kg=102, duration_sec=None),
        _FakeRow(id=103, training_log_id=11, set_number=3, reps=5, weight_kg=102, duration_sec=None),
    ]

    class _RoutedCursor:
        def __init__(self, rows, one=None): self._rows = rows; self._one = one
        def fetchone(self):
            return self._one if self._one is not None else _FakeRow(
                id=1, username='owner', email='o@x.test', display_name='Owner')
        def fetchall(self):
            return self._rows

    class _RoutedConn:
        def execute(self, sql, *_a, **_k):
            s = sql.lower()
            if 'from training_sessions' in s and 'where id' in s:
                return _RoutedCursor([], one=session_row)
            if 'from training_log_sets' in s:
                return _RoutedCursor(sets_rows)
            if 'from training_log' in s:
                return _RoutedCursor(log_rows)
            return _RoutedCursor([])
        def commit(self):
            pass

    conn = _RoutedConn()
    for mod in list(sys.modules.values()):
        if mod is not None and getattr(mod, 'get_db', None) is not None:
            monkeypatch.setattr(mod, 'get_db', lambda conn=conn: conn, raising=False)
    _appmod.app.config['TESTING'] = True
    c = _appmod.app.test_client()
    with c.session_transaction() as sess:
        sess['user_id'] = 1
    resp = c.get('/training/session/7')
    assert resp.status_code == 200
    html = resp.get_data(as_text=True)
    assert 'Back squat' in html and 'Bench press' in html
    assert 'PROGRESS ↑' in html and 'REPEAT →' in html
    assert '/training/11/edit' in html and '/training/12/edit' in html
    assert 'Heavy day.' in html      # session notes render
    assert 'S1:' in html and 'S2:' in html and 'S3:' in html  # per-set chips
    assert 'Delete session' in html  # session-level delete CTA
    assert 'style="' not in html


def test_body_list_render(monkeypatch):
    _check(monkeypatch, '/body', 'Body metrics.')


def test_conditions_list_render(monkeypatch):
    _check(monkeypatch, '/conditions', 'Conditions log.')
