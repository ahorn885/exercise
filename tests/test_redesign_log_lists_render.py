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


def test_workouts_feed_renders_both_modalities(monkeypatch):
    """SQL-routed fake: strength + cardio rows BOTH appear on /training."""

    strength_row = _FakeRow(
        id=11, date='2026-06-05', exercise='Back squat',
        actual_sets=3, actual_reps=5, actual_weight=225, rpe=8,
        volume=3375, outcome='PROGRESS ↑', est_1rm=275,
        next_sets=3, next_reps=5, next_weight=230,
        target_sets=None, target_reps=None, target_weight=None,
    )
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
            if 'from training_log' in s and 'training_log_sets' not in s:
                return _RoutedCursor([strength_row])
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
    # Both rows render with the right modality chip.
    assert 'Back squat' in html and 'Strength' in html
    assert 'Trail Running' in html and 'Cardio' in html
    # Cardio (2026-06-06) sorts before strength (2026-06-05) — date desc.
    assert html.index('Trail Running') < html.index('Back squat')
    # Dropped columns are gone from the row markup.
    assert 'Next Rx' not in html and 'Target' not in html and '1RM' not in html
    assert 'style="' not in html


def test_body_list_render(monkeypatch):
    _check(monkeypatch, '/body', 'Body metrics.')


def test_conditions_list_render(monkeypatch):
    _check(monkeypatch, '/conditions', 'Conditions log.')
