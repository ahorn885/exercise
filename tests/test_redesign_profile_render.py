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

    def __init__(self, profile=None, memory=(), user=None, pack_loads=(),
                 pregnancy_flags=None, screening=None):
        self._profile = profile or {}
        self._memory = list(memory)
        self._user = user
        self._pack_loads = list(pack_loads)
        self._pregnancy_flags = pregnancy_flags  # list[str] | None
        self._screening = screening  # dict | None — get_screening() row shape

    def execute(self, sql, *a, **k):
        s = ' '.join(sql.split())
        if 'FROM users' in s:
            u = self._user or _FakeRow(
                username='owner', display_name='Owner', email='o@x.test',
                last_login='2026-06-01', password_hash='x')
            return _Cursor([], one=u)
        if 'FROM coaching_preferences' in s or 'preferences' in s and 'category' in s:
            return _Cursor(self._memory)
        if 'FROM user_totp' in s:
            # No 2FA enrolled in the render fixtures (account card → 'off'). The
            # default cursor's fetchone() hands back a stub user row even when
            # one=None, so return a genuinely-empty cursor here.
            return SimpleNamespace(fetchone=lambda: None, fetchall=lambda: [])
        if 'pack_load_history' in s:
            return _Cursor([_FakeRow(r) for r in self._pack_loads])
        if 'health_screening' in s:
            # #394 D-85 — get_screening()'s read-view query is distinguishable
            # from get_pregnancy_flag()'s simpler `SELECT flags` by its
            # computed `reassessment_overdue` column.
            if 'reassessment_overdue' in s:
                if self._screening is None:
                    return SimpleNamespace(fetchone=lambda: None, fetchall=lambda: [])
                return _Cursor([], one=_FakeRow(self._screening))
            if self._pregnancy_flags is None:
                return SimpleNamespace(fetchone=lambda: None, fetchall=lambda: [])
            return _Cursor([], one=_FakeRow(flags=self._pregnancy_flags))
        if 'athlete_profile' in s:
            return _Cursor([], one=_FakeRow(self._profile) if self._profile else None)
        if 'discipline_baseline_' in s:
            # 2c.2b craft picker reads bike/paddle baselines; an empty athlete
            # has null craft columns (→ unchecked boxes). _Cursor.fetchone()
            # never returns None, so hand back a row carrying the columns.
            return _Cursor([], one=_FakeRow(
                bike_types_available=None, paddle_craft_types=None))
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
    # Sub-tabs present; athlete fields rendered. #894 regrouped the strip into
    # Athlete · Fuel & health · Gear & skills (Schedule → sidebar; Locations → Log).
    assert '?tab=health' in html and '?tab=gear' in html
    assert '?tab=schedule' not in html  # Schedule left the profile (now in the sidebar)
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


def test_profile_gear_skills_tab(monkeypatch):
    # #894 — Gear & skills groups owned crafts + race-day skills + pack-load
    # experience under one tab (?tab=gear).
    client = _client(monkeypatch, _Conn(profile={}))
    resp = client.get('/profile/?tab=gear')
    assert resp.status_code == 200
    html = resp.get_data(as_text=True)
    assert 'Race-day skills' in html
    assert '/profile/skills' in html        # skills save action
    # #884 slice 6a — the unified "Your gear" surface replaces the two pickers.
    assert 'Your gear' in html
    assert '/profile/gear' in html          # consolidated gear save action
    assert 'Have access' in html            # the own/have-access control
    assert 'Pack-load experience' in html
    assert '/profile/pack-load/add' in html  # pack-load add action
    assert 'style="' not in html
    # #1067 — empty state shows the entry form directly (no disclosure to open).
    assert 'pf-pack-add' not in html


def test_profile_pack_load_form_collapses_once_filled(monkeypatch):
    # #1067 — once a pack-load record exists, the section reads as a summary and
    # the entry form is collapsed behind a disclosure; the row's Remove (delete)
    # stays reachable.
    rows = [{'id': 7, 'pack_weight_kg': 12.0, 'session_count_4wk': 3,
             'longest_session_hrs': 30.0, 'terrain_type': 'trail', 'notes': None}]
    client = _client(monkeypatch, _Conn(profile={}, pack_loads=rows))
    resp = client.get('/profile/?tab=gear')
    assert resp.status_code == 200
    html = resp.get_data(as_text=True)
    assert '12.0 kg' in html                       # summary renders the record
    assert 'pf-pack-add' in html                   # form collapsed behind details
    assert 'Add another pack weight' in html
    assert '/profile/pack-load/7/delete' in html   # per-row delete reachable
    assert '/profile/pack-load/add' in html        # form still present, inside


def test_profile_pregnancy_field_renders_on_health_tab(monkeypatch):
    # #223 — the pregnancy checkbox is always visible on the health tab.
    client = _client(monkeypatch, _Conn(profile={}))
    resp = client.get('/profile/?tab=health')
    assert resp.status_code == 200
    html = resp.get_data(as_text=True)
    assert 'pf-pregnancy' in html
    assert 'pf-pregnancy-check' in html
    assert 'pregnancy_status' in html
    assert 'pregnant' in html.lower()
    assert '/profile/pregnancy' in html


def test_profile_pregnancy_field_checked_when_flagged(monkeypatch):
    # #223 — checkbox is checked when PREGNANCY flag is set in health_screening.
    client = _client(monkeypatch, _Conn(profile={}, pregnancy_flags=["PREGNANCY"]))
    resp = client.get('/profile/?tab=health')
    html = resp.get_data(as_text=True)
    assert 'pf-pregnancy' in html
    assert 'checked' in html


def test_profile_health_screening_card_no_screening_on_file(monkeypatch):
    # #394 D-82/D-85 — no acknowledged screening yet: the card still renders
    # with the update link, but shows the "no screening on file" message.
    client = _client(monkeypatch, _Conn(profile={}))
    resp = client.get('/profile/?tab=health')
    assert resp.status_code == 200
    html = resp.get_data(as_text=True)
    assert 'health-screening' in html
    assert 'Update health screening' in html
    assert '/onboarding/health-screening' in html
    assert 'No health screening on file yet.' in html


def test_profile_health_screening_card_renders_flags_and_dates(monkeypatch):
    # #394 D-85 — a screening with flags shows plain-language descriptions +
    # last-assessed / due dates; not overdue ⇒ no overdue chip.
    screening = {
        'flags': ['CARDIO_CONDITION'],
        'details': {},
        'details_optin': False,
        'acknowledged': True,
        'last_assessed_at': '2026-06-01 12:00:00',
        'reassessment_due_at': '2027-06-01 12:00:00',
        'reassessment_overdue': False,
    }
    client = _client(monkeypatch, _Conn(profile={}, screening=screening))
    resp = client.get('/profile/?tab=health')
    html = resp.get_data(as_text=True)
    assert 'Diagnosed heart condition' in html
    assert '2026-06-01' in html
    assert '2027-06-01' in html
    assert 'Reassessment overdue' not in html


def test_profile_health_screening_card_overdue_chip(monkeypatch):
    # #394 D-83/D-85 — an overdue screening shows the warning chip.
    screening = {
        'flags': [],
        'details': {},
        'details_optin': False,
        'acknowledged': True,
        'last_assessed_at': '2025-01-01 00:00:00',
        'reassessment_due_at': '2026-01-01 00:00:00',
        'reassessment_overdue': True,
    }
    client = _client(monkeypatch, _Conn(profile={}, screening=screening))
    resp = client.get('/profile/?tab=health')
    html = resp.get_data(as_text=True)
    assert 'Reassessment overdue' in html
    assert 'chip warn' in html
    assert 'No items flagged for physician consultation.' in html


def test_profile_locations_tab_redirects_to_locales(monkeypatch):
    # #887 — Locations is consolidated under the Log nav group; the profile no
    # longer hosts a Locations tab. Any lingering ?tab=locations link/bookmark
    # redirects to the canonical standalone surface (locales.list_profiles).
    client = _client(monkeypatch, _Conn(profile={}))
    resp = client.get('/profile/?tab=locations')
    assert resp.status_code == 302
    assert resp.headers['Location'].endswith('/locales')


def test_profile_strip_omits_locations_tab(monkeypatch):
    # The profile sub-tab strip no longer offers a Locations tab (#887).
    client = _client(monkeypatch, _Conn(profile={}))
    resp = client.get('/profile/')
    assert resp.status_code == 200
    html = resp.get_data(as_text=True)
    assert '?tab=locations' not in html


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
    # #267 — no passkeys registered: still offers "Add a passkey" (hidden by
    # default; JS un-hides it only when the browser supports WebAuthn).
    assert 'Passkeys' in html
    assert 'data-webauthn-register hidden' in html
    assert '/profile/webauthn/register/options' in html
    assert 'webauthn.js' in html


def test_account_settings_lists_registered_passkeys(monkeypatch):
    import routes.profile as _profile
    monkeypatch.setattr(
        _profile.webauthn_helper, 'list_credentials',
        lambda db, uid: [
            {'id': 3, 'user_id': uid, 'credential_id': 'AQIDBA', 'nickname': 'iPhone',
             'created_at': '2026-06-01 10:00:00', 'last_used_at': '2026-06-15 08:00:00'},
        ],
    )
    client = _client(monkeypatch, _Conn())
    resp = client.get('/profile/account')
    html = resp.get_data(as_text=True)
    assert 'iPhone' in html
    assert '2026-06-01' in html and '2026-06-15' in html
    assert '/profile/webauthn/3/delete' in html
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


def test_profile_schedule_page(monkeypatch):
    # #894 — Schedule moved out of the profile tab strip onto its own page
    # under "Train" in the sidebar (GET /profile/schedule).
    client = _client(monkeypatch, _Conn(profile={}))
    resp = client.get('/profile/schedule')
    assert resp.status_code == 200
    html = resp.get_data(as_text=True)
    assert 'When can you train?' in html
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
    # #894 — nutrition & fueling now lives on the Fuel & health tab, paired with
    # supplements / conditions / medications.
    html = client.get('/profile/?tab=health').get_data(as_text=True)
    assert 'Nutrition &amp; fueling' in html
    # Editable controls present, posting to the dedicated nutrition save handler.
    assert 'name="dietary_pattern"' in html
    assert 'name="fueling_format_preference"' in html
    assert 'name="caffeine_tolerance"' in html
    assert '/profile/nutrition' in html  # nutrition save action (carved out of the main save)
    # Stored values pre-fill the inputs (free-text, number, and >=1 checkbox).
    assert 'high fructose' in html
    assert 'value="200"' in html
    assert 'checked' in html  # multi-select tokens pre-checked
    # The legacy free-text supplement textarea is gone; supplements are now a
    # structured editor paired on this same tab (#619 + #894).
    assert 'name="supplement_protocol_notes"' not in html
    assert 'Current supplements' in html
    # No live plan in the default conn -> the plan-baseline card stays hidden.
    assert 'Active plan · daily baseline' not in html
    assert 'style="' not in html


def test_profile_nutrition_protocol_empty_form(monkeypatch):
    client = _client(monkeypatch, _Conn(
        profile={'primary_sport': 'run', 'updated_at': '2026-05-30 10:00:00'}))
    html = client.get('/profile/?tab=health').get_data(as_text=True)
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
    # #894 — nutrition fields now POST to their own /profile/nutrition handler
    # (carved out of the main save so a partial POST can't wipe the baselines).
    resp = client.post('/profile/nutrition', data={
        'dietary_pattern': ['vegan', 'keto', 'bogus'],   # 'bogus' not in vocab
        'fueling_format_preference': ['gel', 'drink_mix'],
        'caffeine_tolerance': 'moderate',
        'caffeine_daily_mg_estimate': '180',
        'salt_electrolyte_tolerance': 'high',
        'gi_triggers_known': 'dairy mid-effort',
    })
    assert resp.status_code in (302, 303)
    # Multi-selects join to CSV and filter to the known vocab ('bogus' dropped).
    assert captured['dietary_pattern'] == 'vegan,keto'
    assert captured['fueling_format_preference'] == 'gel,drink_mix'
    assert captured['caffeine_tolerance'] == 'moderate'
    assert captured['caffeine_daily_mg_estimate'] == 180
    assert captured['salt_electrolyte_tolerance'] == 'high'
    assert captured['gi_triggers_known'] == 'dairy mid-effort'
    # Supplements moved to structured records (2E-6) — the profile-save upsert
    # no longer writes the legacy free-text column (so it isn't wiped to NULL).
    assert 'supplement_protocol_notes' not in captured


def test_profile_active_plan_baseline_renders(monkeypatch):
    monkeypatch.setattr(_profile, '_load_active_plan_nutrition',
                        lambda db, uid: (77, _fake_plan_nutrition()))
    client = _client(monkeypatch, _Conn(
        profile={'primary_sport': 'run', 'updated_at': '2026-05-30 10:00:00'}))
    # #894 — the active-plan nutrition baseline rides with the Fuel & health tab.
    html = client.get('/profile/?tab=health').get_data(as_text=True)
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
         'scope_end_date': today + timedelta(days=40),
         'completed_at': None, 'archived_at': None},   # upcoming
        {'id': 2, 'scope_start_date': today - timedelta(days=3),
         'scope_end_date': today + timedelta(days=20),
         'completed_at': None, 'archived_at': None},   # live
        {'id': 3, 'scope_start_date': today - timedelta(days=60),
         'scope_end_date': today - timedelta(days=2),
         'completed_at': None, 'archived_at': None},    # ended
    ]
    monkeypatch.setattr(_profile, 'load_plan_nutrition_by_version',
                        lambda db, pvid: f'NUTR-{pvid}')
    pid, nutr = _profile._load_active_plan_nutrition(_PlanRowsConn(rows), uid=9)
    assert pid == 2 and nutr == 'NUTR-2'


def test_load_active_plan_nutrition_none_when_no_live_plan(monkeypatch):
    today = date.today()
    rows = [
        {'id': 3, 'scope_start_date': today - timedelta(days=60),
         'scope_end_date': today - timedelta(days=2),
         'completed_at': None, 'archived_at': None},    # ended
        {'id': 4, 'scope_start_date': today - timedelta(days=10),
         'scope_end_date': today + timedelta(days=10),
         'completed_at': 'done', 'archived_at': None},  # completed
        {'id': 5, 'scope_start_date': today - timedelta(days=4),
         'scope_end_date': today + timedelta(days=18),
         'completed_at': None, 'archived_at': 'shelved'},  # archived (live scope, but shelved)
    ]
    called = []
    monkeypatch.setattr(_profile, 'load_plan_nutrition_by_version',
                        lambda db, pvid: called.append(pvid))
    pid, nutr = _profile._load_active_plan_nutrition(_PlanRowsConn(rows), uid=9)
    assert pid is None and nutr is None
    assert called == []  # never loads nutrition when nothing is live


# ── 2E-6 structured supplement capture ───────────────────────────────

import athlete_supplements_repo as _supp_repo  # noqa: E402


class _SuppConn(_Conn):
    """Adds canned rows for the supplement vocab + the athlete's records, plus
    the §B health-condition / medication capture lists, the resolved-condition
    history (#893), and the Health-tab injury list (#886)."""
    def __init__(self, vocab=(), supps=(), conditions=(), medications=(),
                 resolved_conditions=(), injuries=(), **kw):
        super().__init__(**kw)
        self._vocab = list(vocab)
        self._supps = list(supps)
        self._conditions = list(conditions)
        self._resolved_conditions = list(resolved_conditions)
        self._injuries = list(injuries)
        self._medications = list(medications)

    def execute(self, sql, *a, **k):
        s = ' '.join(sql.split())
        if 'supplement_vocabulary' in s:
            return _Cursor(self._vocab)
        if 'FROM athlete_supplements' in s:
            return _Cursor(self._supps)
        if 'FROM injury_log' in s:
            return _Cursor(self._injuries)
        if 'FROM health_conditions_log' in s:
            # profile.edit reads active + resolved separately — same SQL text,
            # different bound status — so branch on the status param to keep the
            # two lists distinct.
            params = a[0] if a else ()
            status = params[1] if len(params) > 1 else 'Active'
            return _Cursor(self._resolved_conditions if status == 'Resolved'
                           else self._conditions)
        if 'FROM medications_log' in s:
            return _Cursor(self._medications)
        return super().execute(sql, *a, **k)


def test_profile_supplements_card_renders(monkeypatch):
    vocab = [
        _FakeRow(supplement_id='creatine_monohydrate', canonical_name='Creatine monohydrate',
                 category='Performance', typical_dose='5 g', primary_effect='...'),
        _FakeRow(supplement_id='electrolyte_mix', canonical_name='Electrolyte mix',
                 category='Race-day', typical_dose='per session', primary_effect='...'),
    ]
    supps = [_FakeRow(id=7, supplement_id='creatine_monohydrate', canonical_name='Creatine monohydrate',
                      category='Performance', dose='5 g', frequency='daily',
                      timing='post_exercise', notes='micronized')]
    client = _client(monkeypatch, _SuppConn(vocab=vocab, supps=supps,
                                            profile={'primary_sport': 'run', 'updated_at': 'x'}))
    html = client.get('/profile/?tab=health').get_data(as_text=True)
    assert 'Current supplements' in html
    assert 'Creatine monohydrate' in html                             # the record
    # Stored tokens render via their vocab labels, not the raw token.
    assert 'Daily' in html and 'Post-exercise' in html
    assert 'optgroup label="Performance"' in html                     # grouped picker
    assert 'optgroup label="Race-day"' in html
    # Frequency/timing are closed-vocab selects now (not free-text inputs).
    assert 'name="frequency"' in html and 'name="timing"' in html
    assert '<input type="text" name="timing"' not in html
    assert '/profile/supplement/add' in html                          # add form
    assert '/profile/supplement/7/delete' in html                     # delete form
    assert 'style="' not in html


def test_supplement_add_resolves_name_from_vocab(monkeypatch):
    captured = {}
    monkeypatch.setattr(_profile, 'vocab_index', lambda db: {
        'creatine_monohydrate': {'supplement_id': 'creatine_monohydrate',
                                 'canonical_name': 'Creatine monohydrate', 'category': 'Performance'}})
    monkeypatch.setattr(_profile, 'add_athlete_supplement', lambda db, uid, **kw: captured.update(kw))
    monkeypatch.setitem(_appmod.app.config, 'WTF_CSRF_ENABLED', False)
    client = _client(monkeypatch, _Conn(profile={}))
    resp = client.post('/profile/supplement/add', data={
        'supplement_id': 'creatine_monohydrate', 'dose': '5 g',
        'frequency': 'daily', 'timing': 'post_exercise',
        'notes': 'micronized', 'canonical_name': 'SPOOFED'})
    assert resp.status_code in (302, 303)
    # Display fields come from the vocab, not the client-supplied 'canonical_name'.
    assert captured['canonical_name'] == 'Creatine monohydrate'
    assert captured['category'] == 'Performance'
    assert captured['dose'] == '5 g'
    # frequency/timing persist as their vocab tokens.
    assert captured['frequency'] == 'daily' and captured['timing'] == 'post_exercise'
    assert captured['notes'] == 'micronized'


def test_supplement_add_filters_frequency_timing_to_vocab(monkeypatch):
    captured = {}
    monkeypatch.setattr(_profile, 'vocab_index', lambda db: {
        'creatine_monohydrate': {'supplement_id': 'creatine_monohydrate',
                                 'canonical_name': 'Creatine monohydrate', 'category': 'Performance'}})
    monkeypatch.setattr(_profile, 'add_athlete_supplement', lambda db, uid, **kw: captured.update(kw))
    monkeypatch.setitem(_appmod.app.config, 'WTF_CSRF_ENABLED', False)
    client = _client(monkeypatch, _Conn(profile={}))
    resp = client.post('/profile/supplement/add', data={
        'supplement_id': 'creatine_monohydrate',
        'frequency': 'bogus', 'timing': 'whenever'})  # neither in the closed vocab
    assert resp.status_code in (302, 303)
    # Out-of-vocab tokens are dropped to NULL rather than stored.
    assert captured['frequency'] is None and captured['timing'] is None


def test_supplement_add_rejects_unknown_id(monkeypatch):
    calls = []
    monkeypatch.setattr(_profile, 'vocab_index', lambda db: {'creatine_monohydrate': {}})
    monkeypatch.setattr(_profile, 'add_athlete_supplement', lambda *a, **k: calls.append(k))
    monkeypatch.setitem(_appmod.app.config, 'WTF_CSRF_ENABLED', False)
    client = _client(monkeypatch, _Conn(profile={}))
    resp = client.post('/profile/supplement/add', data={'supplement_id': 'snake_oil'})
    assert resp.status_code in (302, 303)
    assert calls == []  # unknown id is never persisted


def test_supplement_delete_is_user_scoped(monkeypatch):
    calls = []
    monkeypatch.setattr(_profile, 'delete_athlete_supplement',
                        lambda db, uid, sid: calls.append((uid, sid)))
    monkeypatch.setitem(_appmod.app.config, 'WTF_CSRF_ENABLED', False)
    client = _client(monkeypatch, _Conn(profile={}))
    resp = client.post('/profile/supplement/9/delete', data={})
    assert resp.status_code in (302, 303)
    assert calls == [(1, 9)]  # scoped on the session user (id=1)


def test_load_supplement_vocab_is_best_effort():
    class _Boom:
        def execute(self, *a, **k):
            raise RuntimeError('layer0 schema missing')
    assert _supp_repo.load_supplement_vocab(_Boom()) == []  # degrades, no raise


def test_supplement_repo_sql_shape():
    class _Rec:
        def __init__(self):
            self.calls = []
        def execute(self, sql, params=()):
            self.calls.append((' '.join(sql.split()), params))
            return _Cursor([])
    db = _Rec()
    _supp_repo.list_athlete_supplements(db, 1)
    _supp_repo.add_athlete_supplement(db, 1, supplement_id='x', canonical_name='X',
                                      category='Health', dose='1', frequency='daily',
                                      timing='post_exercise', notes=None)
    _supp_repo.delete_athlete_supplement(db, 1, 5)
    sqls = [c[0] for c in db.calls]
    assert any('FROM athlete_supplements WHERE user_id' in s for s in sqls)
    assert any('INSERT INTO athlete_supplements' in s for s in sqls)
    # frequency rides alongside timing in both read and write paths.
    assert any('frequency' in s and 'INSERT INTO athlete_supplements' in s for s in sqls)
    ins_call = next(c for c in db.calls if 'INSERT INTO athlete_supplements' in c[0])
    assert 'daily' in ins_call[1] and 'post_exercise' in ins_call[1]
    del_call = next(c for c in db.calls if 'DELETE' in c[0])
    assert del_call[1] == (5, 1)  # (id, user_id) — scoped


def test_supplement_vocab_cleaners():
    # Closed-vocab guards: in-vocab passes, anything else (incl. blank) -> None.
    assert _supp_repo.clean_frequency('twice_daily') == 'twice_daily'
    assert _supp_repo.clean_frequency('  as_needed ') == 'as_needed'
    assert _supp_repo.clean_frequency('bogus') is None
    assert _supp_repo.clean_frequency('') is None and _supp_repo.clean_frequency(None) is None
    assert _supp_repo.clean_timing('during_exercise') == 'during_exercise'
    assert _supp_repo.clean_timing('whenever') is None


# ── §B health-condition + medication capture ─────────────────────────────────

import health_inputs_repo as _hi_repo  # noqa: E402


def test_health_inputs_cards_render(monkeypatch):
    conditions = [_FakeRow(id=3, system_category='cardiac',
                           condition_name='Atrial fibrillation', severity=2, notes=None)]
    medications = [_FakeRow(id=5, medication_class='anticoagulant',
                            medication_name='warfarin', notes=None)]
    client = _client(monkeypatch, _SuppConn(conditions=conditions, medications=medications,
                                            profile={'primary_sport': 'run', 'updated_at': 'x'}))
    html = client.get('/profile/?tab=health').get_data(as_text=True)
    # Both cards + the stored records (rendered via their §B labels).
    assert 'Health conditions' in html and 'Medications' in html
    assert 'Atrial fibrillation' in html and 'Cardiac' in html
    # Medication shows by class only — the exact name is no longer captured/shown.
    assert 'Anticoagulant' in html
    assert 'warfarin' not in html and 'name="medication_name"' not in html
    # Condition capture is now a system-filtered select + free-text escape
    # (#543), not a bare text input; the curated vocab ships to the client.
    assert 'id="condSelect"' in html and 'name="condition_name_other"' in html
    assert 'Hypertension' in html      # a curated condition in the JSON map
    # Vocab-backed add selects + scoped delete forms.
    assert 'name="system_category"' in html and 'name="medication_class"' in html
    assert '/profile/condition/add' in html and '/profile/condition/3/delete' in html
    assert '/profile/medication/add' in html and '/profile/medication/5/delete' in html
    assert 'style="' not in html


def test_condition_add_validates_category(monkeypatch):
    calls = []
    monkeypatch.setattr(_profile, 'add_health_condition',
                        lambda db, uid, **kw: calls.append(kw) or True)
    monkeypatch.setitem(_appmod.app.config, 'WTF_CSRF_ENABLED', False)
    client = _client(monkeypatch, _Conn(profile={}))
    resp = client.post('/profile/condition/add', data={
        'system_category': 'cardiac', 'condition_name': 'SVT', 'severity': '3'})
    assert resp.status_code in (302, 303)
    assert calls[0]['system_category'] == 'cardiac'
    assert calls[0]['condition_name'] == 'SVT' and calls[0]['severity'] == 3


def test_condition_add_uses_freetext_for_other_not_listed(monkeypatch):
    # The "Other (not listed)" select sentinel keeps the system_category but
    # takes the name from the free-text escape (#543).
    calls = []
    monkeypatch.setattr(_profile, 'add_health_condition',
                        lambda db, uid, **kw: calls.append(kw) or True)
    monkeypatch.setitem(_appmod.app.config, 'WTF_CSRF_ENABLED', False)
    client = _client(monkeypatch, _Conn(profile={}))
    client.post('/profile/condition/add', data={
        'system_category': 'cardiac', 'condition_name': '__other__',
        'condition_name_other': 'Brugada syndrome'})
    assert calls[0]['system_category'] == 'cardiac'
    assert calls[0]['condition_name'] == 'Brugada syndrome'


def test_condition_add_other_system_uses_freetext(monkeypatch):
    # The `other` system has no curated list → the free-text input is the name.
    calls = []
    monkeypatch.setattr(_profile, 'add_health_condition',
                        lambda db, uid, **kw: calls.append(kw) or True)
    monkeypatch.setitem(_appmod.app.config, 'WTF_CSRF_ENABLED', False)
    client = _client(monkeypatch, _Conn(profile={}))
    client.post('/profile/condition/add', data={
        'system_category': 'other', 'condition_name': '',
        'condition_name_other': 'Idiopathic something'})
    assert calls[0]['condition_name'] == 'Idiopathic something'


def test_conditions_vocab_keys_are_valid_categories():
    from athlete import KNOWN_SYSTEM_CATEGORIES
    keys = set(_hi_repo.CONDITIONS_BY_CATEGORY)
    assert keys <= set(KNOWN_SYSTEM_CATEGORIES)   # no stray category
    assert 'other' not in keys                    # 'other' is free-text only
    assert all(_hi_repo.CONDITIONS_BY_CATEGORY.values())  # no empty lists


def test_system_category_canonical_set():
    # #255 — the enum is the canonical 11-category set; the retired 8-enum slugs
    # (metabolic / endocrine / gi_immune) must be gone so capture + the Layer 2E
    # supplement screen key on one vocab.
    from athlete import KNOWN_SYSTEM_CATEGORIES
    assert set(KNOWN_SYSTEM_CATEGORIES) == {
        'cardiac', 'respiratory', 'endocrine_metabolic', 'gi', 'neurological',
        'cognitive_mental_health', 'musculoskeletal', 'skin',
        'thermoregulation', 'immune_autoimmune', 'other',
    }
    assert not ({'metabolic', 'endocrine', 'gi_immune'} & set(KNOWN_SYSTEM_CATEGORIES))
    # every category has a display label
    assert set(_hi_repo.SYSTEM_CATEGORY_LABELS) == set(KNOWN_SYSTEM_CATEGORIES)


def test_condition_add_rejects_unknown_category(monkeypatch):
    # The repo guard rejects out-of-vocab categories — no row stored.
    class _Rec:
        def __init__(self):
            self.calls = []
        def execute(self, sql, params=()):
            self.calls.append(sql)
            return _Cursor([])
    db = _Rec()
    assert _hi_repo.add_health_condition(
        db, 1, system_category='bogus', condition_name='x',
        severity=None, notes=None) is False
    assert not any('INSERT' in s for s in db.calls)


def test_medication_add_rejects_unknown_class(monkeypatch):
    class _Rec:
        def __init__(self):
            self.calls = []
        def execute(self, sql, params=()):
            self.calls.append(sql)
            return _Cursor([])
    db = _Rec()
    assert _hi_repo.add_medication(
        db, 1, medication_class='snake_oil', medication_name='x', notes=None) is False
    assert not any('INSERT' in s for s in db.calls)


def test_health_input_deletes_are_user_scoped():
    class _Rec:
        def __init__(self):
            self.calls = []
        def execute(self, sql, params=()):
            self.calls.append((' '.join(sql.split()), params))
            return _Cursor([])
    db = _Rec()
    _hi_repo.delete_health_condition(db, 1, 9)
    _hi_repo.delete_medication(db, 1, 4)
    cond = next(c for c in db.calls if 'health_conditions_log' in c[0])
    med = next(c for c in db.calls if 'medications_log' in c[0])
    assert cond[1] == (9, 1) and med[1] == (4, 1)  # (id, user_id) — scoped


def test_severity_cleaner():
    assert _hi_repo.clean_severity('3') == 3
    assert _hi_repo.clean_severity('0') is None and _hi_repo.clean_severity('6') is None
    assert _hi_repo.clean_severity('') is None and _hi_repo.clean_severity(None) is None


# ── #886 injuries on the Health tab + #893 condition edit / resolve history ───

def test_health_tab_lists_injuries(monkeypatch):
    # The profile "Fuel & health" tab (#894) surfaces the injury log — active +
    # historical — with edit/log/delete that round-trip back to the profile via
    # ?return=profile.
    injuries = [
        _FakeRow(id=8, body_part='Left Knee', status='Active', severity='Acute',
                 start_date='2026-05-01', resolved_date=None, description='ACL tweak'),
        _FakeRow(id=9, body_part='Right Ankle', status='Resolved', severity=None,
                 start_date='2025-09-01', resolved_date='2025-12-01', description=None),
    ]
    client = _client(monkeypatch, _SuppConn(
        injuries=injuries, profile={'primary_sport': 'run', 'updated_at': 'x'}))
    html = client.get('/profile/?tab=health').get_data(as_text=True)
    # The #894 "Fuel & health" tab now carries the injury log.
    assert '● Injuries' in html
    # Injury card + both records (active + historical) render.
    assert 'id="injuries"' in html
    assert 'Left Knee' in html and 'ACL tweak' in html
    assert 'Right Ankle' in html
    # Edit / log / delete are wired with the profile round-trip flag, and the
    # full log (per-exercise modifications) is linked.
    assert '/injuries/8/edit?return=profile' in html
    assert '/injuries/new?return=profile' in html
    assert '/injuries/9/delete' in html
    assert 'name="return" value="profile"' in html
    assert 'href="/injuries"' in html
    assert 'style="' not in html


def test_health_tab_conditions_edit_resolve_and_history(monkeypatch):
    active = [_FakeRow(id=3, system_category='cardiac', condition_name='Afib',
                       severity=2, notes='controlled', status='Active',
                       start_date=None, resolved_date=None)]
    resolved = [_FakeRow(id=4, system_category='respiratory', condition_name='Asthma',
                         severity=None, notes=None, status='Resolved',
                         start_date=None, resolved_date='2026-04-01')]
    client = _client(monkeypatch, _SuppConn(
        conditions=active, resolved_conditions=resolved,
        profile={'primary_sport': 'run', 'updated_at': 'x'}))
    html = client.get('/profile/?tab=health').get_data(as_text=True)
    # Active row: inline edit (collapse) + resolve + delete all wired.
    assert 'id="hc-edit-3"' in html
    assert '/profile/condition/3/edit' in html
    assert '/profile/condition/3/resolve' in html
    assert '/profile/condition/3/delete' in html
    # The edit form pre-fills the stored name.
    assert 'value="Afib"' in html
    # Resolved-history section: reactivate wired + resolved date shown.
    assert 'Resolved (history)' in html
    assert 'Asthma' in html
    assert '/profile/condition/4/reactivate' in html
    assert 'resolved 2026-04-01' in html
    assert 'style="' not in html


def test_condition_update_route_is_user_scoped(monkeypatch):
    calls = []
    monkeypatch.setattr(_profile, 'update_health_condition',
                        lambda db, uid, cid, **kw: calls.append((uid, cid, kw)) or True)
    monkeypatch.setitem(_appmod.app.config, 'WTF_CSRF_ENABLED', False)
    client = _client(monkeypatch, _Conn(profile={}))
    resp = client.post('/profile/condition/3/edit', data={
        'system_category': 'cardiac', 'condition_name': 'SVT',
        'severity': '4', 'notes': 'mild'})
    assert resp.status_code in (302, 303)
    assert 'tab=health' in resp.headers['Location']
    uid, cid, kw = calls[0]
    assert uid == 1 and cid == 3                       # scoped on session user
    assert kw['system_category'] == 'cardiac' and kw['condition_name'] == 'SVT'
    assert kw['severity'] == 4 and kw['notes'] == 'mild'


def test_condition_resolve_route_stamps_date(monkeypatch):
    calls = []
    monkeypatch.setattr(_profile, 'set_health_condition_status',
                        lambda db, uid, cid, **kw: calls.append((uid, cid, kw)) or True)
    monkeypatch.setitem(_appmod.app.config, 'WTF_CSRF_ENABLED', False)
    client = _client(monkeypatch, _Conn(profile={}))
    resp = client.post('/profile/condition/3/resolve', data={})
    assert resp.status_code in (302, 303)
    uid, cid, kw = calls[0]
    assert uid == 1 and cid == 3 and kw['status'] == 'Resolved'
    assert kw['resolved_date']                          # a date was stamped


def test_condition_reactivate_route_clears_date(monkeypatch):
    calls = []
    monkeypatch.setattr(_profile, 'set_health_condition_status',
                        lambda db, uid, cid, **kw: calls.append((uid, cid, kw)) or True)
    monkeypatch.setitem(_appmod.app.config, 'WTF_CSRF_ENABLED', False)
    client = _client(monkeypatch, _Conn(profile={}))
    resp = client.post('/profile/condition/3/reactivate', data={})
    assert resp.status_code in (302, 303)
    uid, cid, kw = calls[0]
    assert kw['status'] == 'Active' and kw['resolved_date'] is None


class _RecConn:
    """Records (normalized-SQL, params) for repo-level write-path assertions."""
    def __init__(self):
        self.calls = []

    def execute(self, sql, params=()):
        self.calls.append((' '.join(sql.split()), params))
        return _Cursor([])


def test_update_health_condition_validates_and_scopes():
    # Unknown category → no update.
    db = _RecConn()
    assert _hi_repo.update_health_condition(
        db, 1, 9, system_category='bogus', condition_name='x',
        severity=None, notes=None) is False
    assert not any('UPDATE' in s for s, _ in db.calls)
    # Blank name → no update.
    db = _RecConn()
    assert _hi_repo.update_health_condition(
        db, 1, 9, system_category='cardiac', condition_name='   ',
        severity=None, notes=None) is False
    assert not any('UPDATE' in s for s, _ in db.calls)
    # Valid → UPDATE scoped on (condition_id, user_id) at the tail.
    db = _RecConn()
    assert _hi_repo.update_health_condition(
        db, 1, 9, system_category='cardiac', condition_name='Afib',
        severity=2, notes='n') is True
    upd = next(c for c in db.calls if 'UPDATE health_conditions_log' in c[0])
    assert upd[1][-2:] == (9, 1)


def test_set_health_condition_status_validates_and_scopes():
    # Unknown status → no write.
    db = _RecConn()
    assert _hi_repo.set_health_condition_status(db, 1, 9, status='Bogus') is False
    assert not db.calls
    # Resolve stamps the date and scopes on (condition_id, user_id).
    db = _RecConn()
    assert _hi_repo.set_health_condition_status(
        db, 1, 9, status='Resolved', resolved_date='2026-06-22') is True
    assert db.calls[0][0].startswith('UPDATE health_conditions_log')
    assert db.calls[0][1] == ('Resolved', '2026-06-22', 9, 1)


def test_list_health_conditions_filters_by_status():
    db = _RecConn()
    _hi_repo.list_health_conditions(db, 1)                       # default Active
    _hi_repo.list_health_conditions(db, 1, status='Resolved')
    assert db.calls[0][1] == (1, 'Active')
    assert db.calls[1][1] == (1, 'Resolved')


# ── #886 injury routes round-trip back to the profile when launched there ─────

def test_injury_delete_returns_to_profile(monkeypatch):
    monkeypatch.setitem(_appmod.app.config, 'WTF_CSRF_ENABLED', False)
    client = _client(monkeypatch, _Conn(profile={}))
    resp = client.post('/injuries/5/delete', data={'return': 'profile'})
    assert resp.status_code in (302, 303)
    loc = resp.headers['Location']
    assert '/profile/' in loc and 'tab=health' in loc


def test_injury_delete_defaults_to_injury_log(monkeypatch):
    monkeypatch.setitem(_appmod.app.config, 'WTF_CSRF_ENABLED', False)
    client = _client(monkeypatch, _Conn(profile={}))
    resp = client.post('/injuries/5/delete', data={})
    assert resp.status_code in (302, 303)
    assert resp.headers['Location'].endswith('/injuries')


def test_injury_new_form_carries_return_flag(monkeypatch):
    client = _client(monkeypatch, _Conn(profile={}))
    html = client.get('/injuries/new?return=profile').get_data(as_text=True)
    # Hidden field threads the round-trip; Cancel points back to the profile.
    assert 'name="return" value="profile"' in html
    assert '/profile/?tab=health#injuries' in html
