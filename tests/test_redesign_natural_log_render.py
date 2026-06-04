"""Render smoke test for the redesign natural-language log screen (finish-the-open).

`natural_log/index.html` (the "log via text" parse → preview → confirm flow) was
the last big surface on base_legacy. Its controller script is already nonced;
this drives the GET route on the new `.app` shell, asserting the shell + the
chat scaffold + CSP-cleanliness.
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


def test_natural_log_render(monkeypatch):
    resp = _client(monkeypatch).get('/log-natural/')
    assert resp.status_code == 200
    html = resp.get_data(as_text=True)
    assert 'app-shell' in html               # new shell, not base_legacy
    assert 'Log via text.' in html
    # Chat scaffold + controls the (nonced) controller script binds to.
    assert 'id="chat-area"' in html
    assert 'id="preview-card"' in html
    assert 'id="send-btn"' in html
    assert 'nl-chat' in html                 # token classes, not legacy u-*
    assert 'u-chat-scroll' not in html
    # The controller script is present and nonced (CSP-clean — no style attr).
    assert 'csp-nonce' in html or 'nonce=' in html
    assert 'style="' not in html
    assert 'onclick=' not in html
