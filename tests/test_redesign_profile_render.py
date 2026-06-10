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


# ── §18 Nutrition surface (standing protocol + active-plan baseline) ──

from datetime import date, timedelta  # noqa: E402
from types import SimpleNamespace  # noqa: E402

import routes.profile as _profile  # noqa: E402


def _fake_plan_nutrition():
    """Minimal stand-in exposing only what the profile template reads."""
    macros = SimpleNamespace(cho_g=420, protein_g=119, fat_g=70)
    base = SimpleNamespace(daily_calorie_target_kcal=3000, macros=macros)
    return SimpleNamespace(
        per_phase_baseline={'Base': base},
        standing_supplement_notes='Iron 18mg with breakfast',
    )


def test_profile_nutrition_protocol_renders(monkeypatch):
    profile = {
        'primary_sport': 'triathlon',
        'dietary_pattern': 'vegetarian,gluten_free',
        'supplement_protocol_notes': 'Creatine 5g daily',
        'caffeine_tolerance': 'moderate',
        'caffeine_daily_mg_estimate': 200,
        'salt_electrolyte_tolerance': 'high',
        'fueling_format_preference': 'gel,drink_mix',
        'gi_triggers_known': 'high fructose',
        'updated_at': '2026-05-30 10:00:00',
    }
    client = _client(monkeypatch, _Conn(profile=profile))
    html = client.get('/profile/?tab=athlete').get_data(as_text=True)
    assert 'Nutrition &amp; fueling' in html
    # Editable controls present.
    assert 'name="dietary_pattern"' in html
    assert 'name="fueling_format_preference"' in html
    assert 'name="caffeine_tolerance"' in html
    assert 'name="supplement_protocol_notes"' in html
    # Stored values pre-fill the inputs (free-text, number, and >=1 checkbox).
    assert 'Creatine 5g daily' in html
    assert 'high fructose' in html
    assert 'value="200"' in html
    assert 'checked' in html  # multi-select tokens pre-checked
    # No live plan in the default conn -> the plan-baseline card stays hidden.
    assert 'Active plan · daily baseline' not in html
    assert 'style="' not in html


def test_profile_nutrition_protocol_empty_form(monkeypatch):
    client = _client(monkeypatch, _Conn(
        profile={'primary_sport': 'run', 'updated_at': '2026-05-30 10:00:00'}))
    html = client.get('/profile/?tab=athlete').get_data(as_text=True)
    assert 'Nutrition &amp; fueling' in html
    assert 'name="dietary_pattern"' in html      # form still rendered
    assert 'checked' not in html                  # nothing pre-selected
    assert 'Active plan · daily baseline' not in html


def test_profile_post_persists_nutrition(monkeypatch):
    captured = {}
    monkeypatch.setattr(_profile, 'upsert_athlete_profile',
                        lambda db, uid, **kw: captured.update(kw) or {})
    monkeypatch.setitem(_appmod.app.config, 'WTF_CSRF_ENABLED', False)
    client = _client(monkeypatch, _Conn(profile={}))
    resp = client.post('/profile/', data={
        'unit_preference': 'metric',
        'dietary_pattern': ['vegan', 'keto', 'bogus'],   # 'bogus' not in vocab
        'fueling_format_preference': ['gel', 'drink_mix'],
        'caffeine_tolerance': 'moderate',
        'caffeine_daily_mg_estimate': '180',
        'salt_electrolyte_tolerance': 'high',
        'gi_triggers_known': 'dairy mid-effort',
        'supplement_protocol_notes': 'creatine 5g',
    })
    assert resp.status_code in (302, 303)
    # Multi-selects join to CSV and filter to the known vocab ('bogus' dropped).
    assert captured['dietary_pattern'] == 'vegan,keto'
    assert captured['fueling_format_preference'] == 'gel,drink_mix'
    assert captured['caffeine_tolerance'] == 'moderate'
    assert captured['caffeine_daily_mg_estimate'] == 180
    assert captured['salt_electrolyte_tolerance'] == 'high'
    assert captured['gi_triggers_known'] == 'dairy mid-effort'
    assert captured['supplement_protocol_notes'] == 'creatine 5g'


def test_profile_active_plan_baseline_renders(monkeypatch):
    monkeypatch.setattr(_profile, '_load_active_plan_nutrition',
                        lambda db, uid: (77, _fake_plan_nutrition()))
    client = _client(monkeypatch, _Conn(
        profile={'primary_sport': 'run', 'updated_at': '2026-05-30 10:00:00'}))
    html = client.get('/profile/?tab=athlete').get_data(as_text=True)
    assert 'Active plan · daily baseline' in html
    assert '3000 kcal' in html
    assert 'Iron 18mg with breakfast' in html
    assert '/plans/v2/77' in html  # link to the live plan
    assert 'style="' not in html


class _PlanRowsConn:
    """Serves only the active-plan SELECT for the helper unit tests."""
    def __init__(self, rows):
        self._rows = rows

    def execute(self, sql, params=()):
        return SimpleNamespace(fetchall=lambda: self._rows, fetchone=lambda: None)


def test_load_active_plan_nutrition_picks_live_plan(monkeypatch):
    today = date.today()
    rows = [
        {'id': 1, 'scope_start_date': today + timedelta(days=5),
         'scope_end_date': today + timedelta(days=40), 'completed_at': None},   # upcoming
        {'id': 2, 'scope_start_date': today - timedelta(days=3),
         'scope_end_date': today + timedelta(days=20), 'completed_at': None},   # live
        {'id': 3, 'scope_start_date': today - timedelta(days=60),
         'scope_end_date': today - timedelta(days=2), 'completed_at': None},    # ended
    ]
    monkeypatch.setattr(_profile, 'load_plan_nutrition_by_version',
                        lambda db, pvid: f'NUTR-{pvid}')
    pid, nutr = _profile._load_active_plan_nutrition(_PlanRowsConn(rows), uid=9)
    assert pid == 2 and nutr == 'NUTR-2'


def test_load_active_plan_nutrition_none_when_no_live_plan(monkeypatch):
    today = date.today()
    rows = [
        {'id': 3, 'scope_start_date': today - timedelta(days=60),
         'scope_end_date': today - timedelta(days=2), 'completed_at': None},    # ended
        {'id': 4, 'scope_start_date': today - timedelta(days=10),
         'scope_end_date': today + timedelta(days=10), 'completed_at': 'done'},  # completed
    ]
    called = []
    monkeypatch.setattr(_profile, 'load_plan_nutrition_by_version',
                        lambda db, pvid: called.append(pvid))
    pid, nutr = _profile._load_active_plan_nutrition(_PlanRowsConn(rows), uid=9)
    assert pid is None and nutr is None
    assert called == []  # never loads nutrition when nothing is live
