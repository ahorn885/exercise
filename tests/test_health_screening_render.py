"""Render + flow smoke tests for the Phase 0 health-screening step.

Boots the real app with a permissive fake DB (same pattern as
`test_redesign_onboarding_render.py`) and drives the GET questions screen, the
POST acknowledgment screen (no-flags / flagged / pregnancy), and the final
acknowledge POST that persists and advances to the profile form.
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
    def __init__(self, one):
        self._one = one

    def fetchone(self):
        return self._one

    def fetchall(self):
        return []


class _Conn:
    def __init__(self):
        self.commits = 0
        self.writes = []

    def execute(self, sql, *a, **k):
        s = ' '.join(sql.split())
        if 'FROM users' in s:
            return _Cursor(_FakeRow(id=1, username='owner', email='o@x.test',
                                    display_name='Owner'))
        if 'INSERT INTO health_screening' in s:
            self.writes.append((s, a))
            return _Cursor(None)
        # health_screening SELECT → no prior screening (fresh athlete)
        return _Cursor(None)

    def commit(self):
        self.commits += 1


def _client(monkeypatch, conn=None):
    conn = conn or _Conn()
    for mod in list(sys.modules.values()):
        if mod is not None and getattr(mod, 'get_db', None) is not None:
            monkeypatch.setattr(mod, 'get_db', lambda conn=conn: conn,
                                raising=False)
    _appmod.app.config['TESTING'] = True
    _appmod.app.config['WTF_CSRF_ENABLED'] = False
    c = _appmod.app.test_client()
    with c.session_transaction() as sess:
        sess['user_id'] = 1
    return c, conn


def test_questions_render(monkeypatch):
    c, _ = _client(monkeypatch)
    resp = c.get('/onboarding/health-screening')
    assert resp.status_code == 200
    html = resp.get_data(as_text=True)
    assert 'onb-steps' in html and 'app-shell' in html       # shell + stepper
    assert 'style="' not in html and 'onclick=' not in html  # CSP-clean
    assert 'A few health questions' in html
    assert 'Health' in html                                  # new stepper pill
    # all 10 questions + the sensitive opt-in
    assert html.count('type="radio"') == 20                  # 10 × (yes/no)
    assert 'name="details_optin"' in html
    assert 'chest pain' in html.lower()


def test_acknowledge_no_flags(monkeypatch):
    c, _ = _client(monkeypatch)
    form = {f'q{i}': 'no' for i in range(1, 11)}
    resp = c.post('/onboarding/health-screening', data=form)
    assert resp.status_code == 200
    html = resp.get_data(as_text=True)
    assert 'No items in this screening require physician consultation' in html
    assert 'I acknowledge and continue' in html
    assert 'name="acknowledge" value="1"' in html


def test_acknowledge_pregnancy_paragraph(monkeypatch):
    c, _ = _client(monkeypatch)
    form = {f'q{i}': 'no' for i in range(1, 11)}
    form['q8'] = 'yes'  # PREGNANCY
    resp = c.post('/onboarding/health-screening', data=form)
    html = resp.get_data(as_text=True)
    assert 'consult a physician' in html
    assert 'Currently pregnant or within 6 months postpartum' in html
    assert 'does not provide pregnancy-specific coaching' in html


def test_final_acknowledge_persists_and_redirects(monkeypatch):
    c, conn = _client(monkeypatch)
    form = {f'q{i}': 'no' for i in range(1, 11)}
    form['q3'] = 'yes'
    form['acknowledge'] = '1'
    resp = c.post('/onboarding/health-screening', data=form)
    assert resp.status_code == 302
    assert '/profile?tab=athlete' in resp.headers['Location']
    assert conn.writes, 'expected a health_screening upsert'
    assert conn.commits >= 1
