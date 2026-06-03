"""Render smoke test for the redesign §28 light-mode toggle.

The theme itself is a token swap (`.theme-light` on <html>), so behaviour is
JS-driven and not exercised here; this asserts the *wiring* is present on the
shell: the FOUC-free pre-paint bootstrap (nonced — CSP-clean), the topbar
toggle control, and the mobile-drawer toggle row. Boots the real app and
renders the dashboard on the new shell.
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


def test_theme_toggle_wiring_present(monkeypatch):
    # /plans/ renders the full new shell (sidebar/topbar/drawer + head) at 200
    # on an empty fake conn — the same surface that carries the §28 wiring.
    client = _client(monkeypatch)
    resp = client.get('/plans/')
    assert resp.status_code == 200
    html = resp.get_data(as_text=True)
    assert 'app-shell' in html

    # Pre-paint bootstrap: nonced inline script reading the saved theme.
    assert 'aidstation-theme' in html
    assert "classList.add('theme-light')" in html

    # Topbar toggle + mobile-drawer toggle both present and wired.
    assert html.count('data-theme-toggle') >= 2
    assert 'theme-toggle' in html          # topbar icon button class
    assert 'Light mode' in html            # drawer row label
    assert 'aria-pressed="false"' in html  # default (dark) state

    # CSP discipline: no inline style= / onclick= anywhere on the shell.
    assert 'style="' not in html
    assert 'onclick=' not in html
