"""Render smoke tests for the redesign auth screens (finish-the-open).

The unauthenticated auth surface (login / register / forgot / reset) was the
last thing still on the old Bootstrap `auth/_shell.html`. These boot the real
app and drive each GET route through the migrated `.app`-themed standalone
shell. Assertions stay structural + CSP-clean; the auth routes are
login-gate-exempt, so no session is needed.
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
    def __init__(self, n_users):
        self._n = n_users

    def execute(self, sql, *a, **k):
        s = ' '.join(sql.split())
        if 'COUNT(*) AS n FROM users' in s:
            return _Cursor(_FakeRow(n=self._n))
        if 'FROM user_invites' in s:
            # A valid, unaccepted, unexpired SMS-channel invite — exercises
            # the invite_token-but-no-invited_email render branch (#272 follow-up).
            return _Cursor(_FakeRow(token='TOK12345', email=None, phone='+15551234567',
                                     channel='sms', accepted_at=None,
                                     expires_at='2099-01-01T00:00:00'))
        if 'FROM password_resets' in s:
            return _Cursor(None)               # unknown token → error branch
        return _Cursor(None)

    def commit(self):
        pass


def _client(monkeypatch, n_users=1):
    monkeypatch.setenv('ALLOW_REGISTRATION', '1')  # so login shows register link
    conn = _Conn(n_users)
    for mod in list(sys.modules.values()):
        if mod is not None and getattr(mod, 'get_db', None) is not None:
            monkeypatch.setattr(mod, 'get_db', lambda conn=conn: conn,
                                raising=False)
    _appmod.app.config['TESTING'] = True
    return _appmod.app.test_client()


def _assert_on_app_shell(html):
    # Migrated onto the `.app` token system, not the old Bootstrap auth-body.
    assert 'class="app auth-page"' in html
    assert 'tokens.css' in html
    assert 'auth-card' in html
    # CSP-clean.
    assert 'style="' not in html
    assert 'onclick=' not in html


def test_login_render(monkeypatch):
    resp = _client(monkeypatch).get('/auth/login')
    assert resp.status_code == 200
    html = resp.get_data(as_text=True)
    _assert_on_app_shell(html)
    assert 'Sign in.' in html
    assert 'name="username"' in html
    assert 'name="password"' in html
    assert 'Forgot?' in html
    # ALLOW_REGISTRATION=1 → the create-account link shows.
    assert '/auth/register' in html
    # #267 — passkey sign-in button: hidden by default (JS un-hides it only
    # when the browser supports WebAuthn) and wired to both ceremony endpoints.
    assert 'data-webauthn-login hidden' in html
    assert 'data-endpoint-options="/auth/webauthn/login/options"' in html
    assert 'data-endpoint-verify="/auth/webauthn/login/verify"' in html
    assert 'webauthn.js' in html


def test_register_bootstrap_render(monkeypatch):
    # No users yet → the first-run owner-setup branch.
    resp = _client(monkeypatch, n_users=0).get('/auth/register')
    assert resp.status_code == 200
    html = resp.get_data(as_text=True)
    _assert_on_app_shell(html)
    assert 'Set up the owner.' in html
    for field in ('name="username"', 'name="display_name"', 'name="email"',
                  'name="password"', 'name="confirm"'):
        assert field in html


def test_register_normal_render(monkeypatch):
    # Users exist + registration open → the regular create-account branch.
    resp = _client(monkeypatch, n_users=1).get('/auth/register')
    assert resp.status_code == 200
    html = resp.get_data(as_text=True)
    _assert_on_app_shell(html)
    assert 'Create account.' in html
    assert '/auth/login' in html  # "Sign in" alt link
    # Default (non-invite) OG copy — the site-wide tagline, not the invite one.
    assert 'AI-driven training for the data-obsessed endurance athlete.' in html
    assert "You're invited" not in html


def test_register_invite_render(monkeypatch):
    # A valid SMS-channel invite (no invited_email) — still hits the
    # "you're invited" branch (keyed off invite_token, #272 follow-up) with
    # on-brand OG title/description for the link-preview card.
    resp = _client(monkeypatch, n_users=1).get('/auth/register?invite=TOK12345')
    assert resp.status_code == 200
    html = resp.get_data(as_text=True)
    _assert_on_app_shell(html)
    assert "You're invited" in html
    assert 'Finish setting up your account.' in html  # no invited_email to name
    assert 'og:title" content="You\'re invited to AIDSTATION"' in html
    assert 'Time to hit the trail' in html
    assert 'og-preview.png' in html


def test_forgot_render(monkeypatch):
    resp = _client(monkeypatch).get('/auth/forgot')
    assert resp.status_code == 200
    html = resp.get_data(as_text=True)
    _assert_on_app_shell(html)
    assert 'Reset your password.' in html
    assert 'name="email"' in html
    assert '/auth/login' in html  # back-to-sign-in link


def test_reset_invalid_token_render(monkeypatch):
    resp = _client(monkeypatch).get('/auth/reset/bogus-token')
    assert resp.status_code == 200
    html = resp.get_data(as_text=True)
    _assert_on_app_shell(html)
    # Unknown token → the error branch, not the password form.
    assert 'Reset link unavailable.' in html
    assert '/auth/forgot' in html
    assert 'name="password"' not in html
