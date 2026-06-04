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
    html = _check(monkeypatch, '/training', 'Strength log.')
    assert 'Log session' in html        # topbar CTA on the new shell


def test_cardio_list_render(monkeypatch):
    _check(monkeypatch, '/cardio', 'Cardio log.')


def test_body_list_render(monkeypatch):
    _check(monkeypatch, '/body', 'Body metrics.')


def test_conditions_list_render(monkeypatch):
    _check(monkeypatch, '/conditions', 'Conditions log.')
