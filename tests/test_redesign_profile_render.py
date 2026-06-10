"""Render smoke tests for the redesign §18 Athlete profile, §19 Account
settings, and §20 Coach memory.

Boots the real Flask app with a fake DB and drives the three profile
surfaces through `render_template` on the new shell. Assertions stay
structural + CSP-clean (the inline tab-activation script the legacy page
carried is gone — tabs are now plain ?tab= links).
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
                        display_name='Owner', last_login='2026-06-01',
                        garth_session=None, garmin_username=None)

    def fetchall(self):
        return self._rows


class _Conn:
    """Routes reads by SQL fragment. `profile` / `users` / `memory` /
    misc-list shapes are served via keyword maps; everything else returns an
    empty cursor (the page tolerates empty schedule/skills/connection lists)."""

    def __init__(self, profile=None, memory=(), user=None):
        self._profile = profile or {}
        self._memory = list(memory)
        self._user = user

    def execute(self, sql, *a, **k):
        s = ' '.join(sql.split())
        if 'FROM users' in s:
            u = self._user or _FakeRow(
                username='owner', display_name='Owner', email='o@x.test',
                last_login='2026-06-01', password_hash='x')
            return _Cursor([], one=u)
        if 'FROM coaching_preferences' in s or 'preferences' in s and 'category' in s:
            return _Cursor(self._memory)
        if 'athlete_profile' in s:
            return _Cursor([], one=_FakeRow(self._profile) if self._profile else None)
        return _Cursor([])

    def commit(self):
        pass


def _client(monkeypatch, conn):
    for mod in list(sys.modules.values()):
        if mod is not None and getattr(mod, 'get_db', None) is not None:
            monkeypatch.setattr(mod, 'get_db', lambda conn=conn: conn,
                                raising=False)
    _appmod.app.config['TESTING'] = True
    c = _appmod.app.test_client()
    with c.session_transaction() as sess:
        sess['user_id'] = 1
    return c


# ── §18 Athlete profile ──────────────────────────────────────────────

def test_profile_athlete_tab_first_run(monkeypatch):
    client = _client(monkeypatch, _Conn(profile={}))
    resp = client.get('/profile/')
    assert resp.status_code == 200
    html = resp.get_data(as_text=True)
    assert 'app-shell' in html
    assert 'Your profile.' in html
    # First-run banner when nothing is saved.
    assert 'First run' in html
    # Sub-tabs present; athlete fields rendered.
    assert '?tab=schedule' in html and '?tab=skills' in html
    assert 'name="primary_sport"' in html
    # #469 — body weight is entered in the athlete's display unit; the form
    # field is `body_weight`, storage is canonical kg.
    assert 'name="body_weight"' in html
    assert 'name="unit_preference"' in html
    # The legacy Bootstrap tab-activation inline script is gone.
    assert 'bootstrap.Tab' not in html
    assert 'style="' not in html
    assert 'onclick=' not in html


def test_profile_athlete_tab_populated_no_firstrun(monkeypatch):
    profile = {'primary_sport': 'triathlon', 'body_weight_kg': 72,
               'updated_at': '2026-05-30 10:00:00'}
    client = _client(monkeypatch, _Conn(profile=profile))
    resp = client.get('/profile/?tab=athlete')
    assert resp.status_code == 200
    html = resp.get_data(as_text=True)
    assert 'First run' not in html
    assert 'triathlon' in html
    assert 'Last saved' in html


def test_profile_skills_tab(monkeypatch):
    client = _client(monkeypatch, _Conn(profile={}))
    resp = client.get('/profile/?tab=skills')
    assert resp.status_code == 200
    html = resp.get_data(as_text=True)
    assert 'Race-day skills' in html
    assert '/profile/skills' in html  # save action
    assert 'style="' not in html


# ── §19 Account settings ─────────────────────────────────────────────

def test_account_settings(monkeypatch):
    client = _client(monkeypatch, _Conn())
    resp = client.get('/profile/account')
    assert resp.status_code == 200
    html = resp.get_data(as_text=True)
    assert 'app-shell' in html
    assert 'Account settings.' in html
    assert 'owner' in html  # identity
    # Change-password form posts to the real route; sign-out to logout.
    assert '/profile/password' in html
    assert '/logout' in html
    assert 'name="current_password"' in html
    assert 'style="' not in html


# ── §20 Coach memory ─────────────────────────────────────────────────

def test_coach_memory_with_prefs(monkeypatch):
    memory = [
        _FakeRow(id=1, category='exclusions', content='No burpees',
                 permanent=1, fb_source='chat', fb_captured_at='2026-05-20',
                 source_feedback_id=7, created_at='2026-05-20'),
        _FakeRow(id=2, category='preferences', content='Prefers AM runs',
                 permanent=0, fb_source=None, source_feedback_id=None,
                 created_at='2026-05-21'),
    ]
    client = _client(monkeypatch, _Conn(memory=memory))
    resp = client.get('/profile/memory')
    assert resp.status_code == 200
    html = resp.get_data(as_text=True)
    assert 'app-shell' in html
    assert 'What the coach remembers.' in html
    assert 'No burpees' in html
    assert 'Prefers AM runs' in html
    # Provenance: captured-from vs added-manually.
    assert 'Captured from chat' in html
    assert 'Added manually' in html
    # Add + delete both wired.
    assert '/profile/preference/add' in html
    assert '/profile/preference/1/delete' in html
    assert 'style="' not in html


def test_coach_memory_empty(monkeypatch):
    client = _client(monkeypatch, _Conn(memory=[]))
    resp = client.get('/profile/memory')
    assert resp.status_code == 200
    html = resp.get_data(as_text=True)
    assert 'No coaching preferences yet' in html
    assert '/profile/preference/add' in html
    assert 'style="' not in html


def test_profile_schedule_tab(monkeypatch):
    client = _client(monkeypatch, _Conn(profile={}))
    resp = client.get('/profile/?tab=schedule')
    assert resp.status_code == 200
    html = resp.get_data(as_text=True)
    assert 'Training windows' in html
    assert '/profile/schedule' in html  # save action
    assert 'style="' not in html
