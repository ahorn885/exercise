"""Render smoke tests for the redesign §17 Connections hub.

Boots the real Flask app with a fake DB and drives `connections.hub`
through `render_template` on the new shell across its three tabs. The route
reads provider_auth (via load_connections), cardio_log (Files), and the
Garmin auth status (best-effort). A fake connection keyed off the SQL
exercises each tab. Assertions stay structural + CSP-clean.
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
    def __init__(self, rows, one=None):
        self._rows = rows
        self._one = one

    def fetchone(self):
        if self._one is not None:
            return self._one
        return _FakeRow(id=1, username='owner', email='o@x.test',
                        display_name='Owner', garth_session=None,
                        garmin_username=None)

    def fetchall(self):
        return self._rows


class _Conn:
    def __init__(self, providers, activities, strength=()):
        self._providers = providers
        self._activities = activities
        self._strength = list(strength)

    def execute(self, sql, *a, **k):
        s = ' '.join(sql.split())
        if 'FROM provider_auth' in s:
            return _Cursor(self._providers)
        if 'COUNT(*)' in s and 'cardio_log' in s:
            return _Cursor([], one=_FakeRow(n=len(self._activities)))
        if 'COUNT(*)' in s and 'training_sessions' in s:
            return _Cursor([], one=_FakeRow(n=len(self._strength)))
        if 'FROM cardio_log' in s:
            return _Cursor(self._activities)
        if 'FROM training_sessions' in s and 'JOIN training_log' in s:
            return _Cursor(self._strength)
        return _Cursor([])

    def commit(self):
        pass


def _activity(**kw):
    base = {
        'id': 1, 'date': '2026-05-22', 'activity': 'Run',
        'activity_name': 'Morning trail run', 'duration_min': 78,
        'distance_mi': 9.42, 'avg_hr': 152, 'max_hr': 178, 'calories': 924,
        'garmin_activity_id': 'fit:abc123', 'created_at': '2026-05-22',
    }
    base.update(kw)
    return _FakeRow(base)


def _strength_session(**kw):
    base = {
        'id': 1, 'date': '2026-05-23', 'garmin_activity_id': 'fit:strhash',
        'exercise_count': 5, 'created_at': '2026-05-23',
    }
    base.update(kw)
    return _FakeRow(base)


def _client(monkeypatch, providers=(), activities=(), strength=()):
    conn = _Conn(list(providers), list(activities), list(strength))
    for mod in list(sys.modules.values()):
        if mod is not None and getattr(mod, 'get_db', None) is not None:
            monkeypatch.setattr(mod, 'get_db', lambda conn=conn: conn,
                                raising=False)
    _appmod.app.config['TESTING'] = True
    c = _appmod.app.test_client()
    with c.session_transaction() as sess:
        sess['user_id'] = 1
    return c


def test_sources_tab(monkeypatch):
    client = _client(monkeypatch)
    resp = client.get('/connections/')
    assert resp.status_code == 200
    html = resp.get_data(as_text=True)
    assert 'app-shell' in html
    assert 'Bring data in.' in html
    # Three tabs present.
    assert 'role="tablist"' in html
    assert '?tab=files' in html and '?tab=prefs' in html
    # Real OAuth providers + Garmin PAUSED + at least one stub.
    assert 'COROS' in html
    assert 'Polar' in html
    assert 'Garmin' in html and 'Paused' in html
    assert 'Strava' in html and 'Not available yet' in html
    # Drop zone posts to the real import pipeline.
    assert '/garmin/import' in html
    assert 'style="' not in html
    assert 'onclick=' not in html


def test_files_tab_lists_activities(monkeypatch):
    activities = [
        _activity(id=1, activity_name='Manual trail run',
                  garmin_activity_id='fit:hash1'),
        _activity(id=2, activity='Ride', activity_name='Synced ride',
                  garmin_activity_id='garmin-998877', distance_mi=18.6),
    ]
    client = _client(monkeypatch, activities=activities)
    resp = client.get('/connections/?tab=files')
    assert resp.status_code == 200
    html = resp.get_data(as_text=True)
    assert 'app-shell' in html
    assert 'Manual trail run' in html
    assert 'Synced ride' in html
    # Manual (fit:) vs synced classification.
    assert 'Manual .FIT' in html
    assert 'Synced' in html
    # The developer FIT inspector moved to the admin surface (issue #473) —
    # the user-facing Files tab no longer carries it.
    assert '/connections/inspect' not in html
    assert 'data-copy-all' not in html
    assert 'style="' not in html


def test_files_tab_lists_strength_sessions(monkeypatch):
    # Strength sessions live in training_sessions/training_log, not cardio_log;
    # the Files list rolls each session up to a single row (issue #474).
    activities = [_activity(id=1, date='2026-05-22',
                            activity_name='Morning run')]
    strength = [
        _strength_session(id=7, date='2026-05-24', exercise_count=5,
                          garmin_activity_id='fit:strhash'),
        _strength_session(id=8, date='2026-05-21', exercise_count=1,
                          garmin_activity_id=None),
    ]
    client = _client(monkeypatch, activities=activities, strength=strength)
    resp = client.get('/connections/?tab=files')
    assert resp.status_code == 200
    html = resp.get_data(as_text=True)
    # Both the cardio and the strength sessions are surfaced.
    assert 'Morning run' in html
    assert 'Strength session · 5 exercises' in html
    assert 'Strength session · 1 exercise' in html  # singular
    # A FIT-imported strength session is tagged Manual; count covers both kinds.
    assert 'Manual .FIT' in html
    assert 'of 3' in html  # 1 cardio + 2 strength sessions


def test_files_tab_empty(monkeypatch):
    client = _client(monkeypatch)
    resp = client.get('/connections/?tab=files')
    assert resp.status_code == 200
    html = resp.get_data(as_text=True)
    assert 'No files yet' in html
    assert '/connections/inspect' not in html
    assert 'style="' not in html


def test_prefs_tab_is_grounded(monkeypatch):
    client = _client(monkeypatch)
    resp = client.get('/connections/?tab=prefs')
    assert resp.status_code == 200
    html = resp.get_data(as_text=True)
    assert 'app-shell' in html
    # Grounded, real-behavior facts — no fabricated toggles.
    assert 'Duplicate detection' in html
    assert 'SHA-256' in html
    assert 'Paused' in html
    assert 'style="' not in html


def test_bad_tab_falls_back_to_sources(monkeypatch):
    client = _client(monkeypatch)
    resp = client.get('/connections/?tab=bogus')
    assert resp.status_code == 200
    html = resp.get_data(as_text=True)
    assert 'Bring data in.' in html
    # Sources content present.
    assert 'Auto-sync providers' in html

# NOTE: the FIT field-dump inspector moved to the admin surface
# (admin.fit_inspect, issue #473). Its render + copy-all coverage now lives in
# tests/test_redesign_admin_render.py.
