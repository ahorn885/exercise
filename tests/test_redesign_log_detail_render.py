"""Render smoke tests for the redesign injury log + strength edit form +
coach-memory feedback detail (finish-the-open).

Boots the real app with a permissive fake DB and drives each GET route on the
new `.app` shell, asserting structure + CSP-cleanliness. The feedback row is
faked by SQL so `view_feedback` doesn't 404.
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
    def execute(self, sql, *a, **k):
        s = ' '.join(sql.split())
        if 'FROM feedback_log' in s:
            return _Cursor(_FakeRow(id=1, source='chat', raw_content='felt strong today',
                                    captured_at='2026-06-01'))
        if 'FROM training_log' in s:
            return _Cursor(_FakeRow(id=5, date='2026-06-01', exercise='Back Squat'))
        if 'FROM users' in s:
            return _Cursor(_FakeRow(id=1, username='owner', email='o@x.test', display_name='Owner'))
        return _Cursor(None)

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
    assert 'app-shell' in html
    assert title in html
    assert 'style="' not in html
    assert 'onclick=' not in html
    return html


def test_injuries_list_render(monkeypatch):
    html = _check(monkeypatch, '/injuries', 'Injury log.')
    assert 'No injuries logged' in html   # empty branch (table block still compiled)
    assert 'Log injury' in html           # topbar CTA


def test_training_form_render(monkeypatch):
    # training/form.html is the EDIT template (new_entry renders the §08 form).
    html = _check(monkeypatch, '/training/5/edit', 'Edit entry.')
    assert 'onb-form' in html             # Bootstrap-grid body with gutters restored


def test_feedback_detail_render(monkeypatch):
    html = _check(monkeypatch, '/profile/feedback/1', 'Original feedback.')
    assert 'felt strong today' in html    # the faked verbatim row renders
