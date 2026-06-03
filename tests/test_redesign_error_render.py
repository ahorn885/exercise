"""Render smoke tests for the redesign §27 error states.

Boots the real Flask app and exercises the shared `_error.html` page through
both registered handlers:
  • 404 — GET an unmapped path → "You're off trail." + way-back quicklinks.
  • 500 — a throwaway route that raises → "Something seized up." (handler
    reachable only with PROPAGATE_EXCEPTIONS off, which is the production
    posture; the test client otherwise re-raises).

The page is standalone (no shell), so assertions stay structural + CSP-clean
and confirm the diagnostic block + pre-filled mailto are present.
"""

from __future__ import annotations

import os
import sys

os.environ.setdefault('SECRET_KEY', 'test-secret-key-for-render-tests')
os.environ['DATABASE_URL'] = ''

import app as _appmod  # noqa: E402


# Register the synthetic-failure route at import time (collection phase, before
# any request) — add_url_rule is rejected once the app has served its first
# request, which happens when this module runs alongside the rest of the suite.
def _boom():
    raise RuntimeError('kaboom — synthetic failure for the §27 test')


def _forbidden():
    from flask import abort
    abort(403)


if 'boom' not in _appmod.app.view_functions:
    _appmod.app.add_url_rule('/__boom__', 'boom', _boom)
if 'forbidden' not in _appmod.app.view_functions:
    _appmod.app.add_url_rule('/__forbidden__', 'forbidden', _forbidden)


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
    # Production renders the 500 page; the test client only reaches the handler
    # (instead of re-raising) when exception propagation is off.
    _appmod.app.config['PROPAGATE_EXCEPTIONS'] = False
    c = _appmod.app.test_client()
    with c.session_transaction() as sess:
        sess['user_id'] = 1
    return c


def test_404_renders_trail_voice(monkeypatch):
    client = _client(monkeypatch)
    resp = client.get('/__no_such_route__/x')
    assert resp.status_code == 404
    html = resp.get_data(as_text=True)
    assert 'error-page' in html
    # Title is autoescaped by Jinja ("You&#39;re"); match the stable tail.
    assert 'off trail.' in html
    assert '404 · NO SUCH ROUTE' in html
    # Way-back quicklinks present; no retry button on a 404.
    assert 'error-quicklinks' in html
    assert 'Workouts' in html
    # Diagnostic block + pre-filled support mailto.
    assert 'error-diag' in html
    assert 'request_id' in html
    assert 'mailto:help@aidstation.pro' in html
    # CSP-clean — standalone page, no inline style/handlers/script.
    assert 'style="' not in html
    assert 'onclick=' not in html
    assert '<script' not in html


def test_403_renders_admin_only(monkeypatch):
    client = _client(monkeypatch)
    resp = client.get('/__forbidden__')
    assert resp.status_code == 403
    html = resp.get_data(as_text=True)
    assert 'error-page' in html
    assert 'Crew only past here.' in html
    assert '403 · ADMIN ONLY' in html
    # Permission gate → warn tone, way-back quicklinks, no retry button.
    assert 'error-glyph--warn' in html
    assert 'error-quicklinks' in html
    assert 'Try again' not in html
    assert '403 forbidden' in html
    assert 'mailto:help@aidstation.pro' in html
    # CSP-clean — standalone page.
    assert 'style="' not in html
    assert 'onclick=' not in html
    assert '<script' not in html


def test_500_renders_seized_up(monkeypatch):
    client = _client(monkeypatch)
    resp = client.get('/__boom__')
    assert resp.status_code == 500
    html = resp.get_data(as_text=True)
    assert 'error-page' in html
    assert 'Something seized up.' in html
    assert '500 · SOMETHING BROKE' in html
    # 500 offers a retry; the synthetic exception text never leaks to the user.
    assert 'Try again' in html
    assert 'kaboom' not in html
    assert '500 internal_error' in html
    assert 'mailto:help@aidstation.pro' in html
    assert 'style="' not in html
    assert 'onclick=' not in html
    assert '<script' not in html
