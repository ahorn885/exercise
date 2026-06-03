"""Render smoke test for the redesign §29 a11y sweep — roving tab-order +
landmark wiring on the real shell.

The roving behaviour itself is JS (arrow-key focus management in app.js); this
asserts the server-rendered *hooks* it consumes are present and correct on the
real nav elements: the [data-roving] containers, the [data-roving-item] markers,
the Primary-labelled <nav> landmark, and aria-current on the active item.
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
        return _FakeRow(id=1, username='owner', email='o@x.test',
                        display_name='Owner')

    def fetchall(self):
        return []


class _Conn:
    def execute(self, sql, *a, **k):
        return _Cursor()

    def commit(self):
        pass


def _client(monkeypatch):
    for mod in list(sys.modules.values()):
        if mod is not None and getattr(mod, 'get_db', None) is not None:
            monkeypatch.setattr(mod, 'get_db', lambda: _Conn(), raising=False)
    _appmod.app.config['TESTING'] = True
    c = _appmod.app.test_client()
    with c.session_transaction() as sess:
        sess['user_id'] = 1
    return c


def test_roving_and_landmark_wiring(monkeypatch):
    client = _client(monkeypatch)
    resp = client.get('/plans/')
    assert resp.status_code == 200
    html = resp.get_data(as_text=True)

    # Both primary navs are roving containers with the right orientation.
    assert 'data-roving="vertical"' in html    # desktop sidebar
    assert 'data-roving="horizontal"' in html  # mobile tab bar

    # The Primary landmark label now lives on the <nav>, not the <aside>.
    assert 'class="sidebar-nav" aria-label="Primary"' in html
    assert 'class="sidebar" aria-label="Primary"' not in html

    # Roving items are marked on the real links (sidebar groups + 5 tabs).
    assert html.count('data-roving-item') >= 10

    # Active item still carries aria-current (the roving initial stop).
    assert 'aria-current="page"' in html

    # CSP-clean shell.
    assert 'style="' not in html
    assert 'onclick=' not in html
