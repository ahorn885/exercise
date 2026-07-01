"""Route-level coverage for the passkey / WebAuthn endpoints (#267):
`routes.auth.webauthn_login_*` (sign-in, login-gate-exempt) and
`routes.profile.webauthn_*` (registration + removal, requires a session).

A real authenticator ceremony can't be simulated in a unit test, so the
`webauthn` library's own verify functions are monkeypatched at the point
`webauthn_helper` calls them; what's pinned here is the route wiring: the
session challenge round-trip, the auth-wall exemption, and Andy's call that a
passkey sign-in is accepted on its own (no TOTP challenge afterward, even for
a TOTP-enabled account). Fake DB throughout, mirroring
tests/test_redesign_auth_render.py.
"""

from __future__ import annotations

import os
import sys

os.environ.setdefault('SECRET_KEY', 'test-secret-key-for-webauthn-routes')
os.environ['DATABASE_URL'] = ''

import app as _appmod  # noqa: E402
import webauthn_helper  # noqa: E402
from routes import auth as _auth  # noqa: E402


class _Cur:
    def __init__(self, rows=(), one=None):
        self._rows = list(rows)
        self._one = one

    def fetchone(self):
        return self._one

    def fetchall(self):
        return self._rows


class _Conn:
    def __init__(self, user=None, credentials=()):
        self.user = user or {'id': 7, 'username': 'andy'}
        self.user.setdefault('email', 'andy@example.com')
        self.user.setdefault('display_name', 'Andy')
        self.credentials = list(credentials)
        self.inserted = []
        self.deleted = []
        self.committed = 0

    def execute(self, sql, params=()):
        s = ' '.join(sql.split())
        if s.startswith('SELECT id, username, email, display_name FROM users WHERE id'):
            # The auth-gate's per-request user-row hydration (app.py's
            # `_require_login`) -- must succeed for a session to be honored.
            row = self.user if self.user['id'] == params[0] else None
            return _Cur(one=row)
        if s.startswith('SELECT username FROM users WHERE id'):
            row = self.user if self.user['id'] == params[0] else None
            return _Cur(one=row)
        if s.startswith('SELECT id, user_id, credential_id, nickname'):
            return _Cur(rows=[c for c in self.credentials if c['user_id'] == params[0]])
        if s.startswith('SELECT id, user_id, credential_id, public_key, sign_count'):
            match = next((c for c in self.credentials if c['credential_id'] == params[0]), None)
            return _Cur(one=match)
        if s.startswith('INSERT INTO user_webauthn_credentials'):
            self.inserted.append(params)
            return _Cur()
        if s.startswith('UPDATE user_webauthn_credentials'):
            return _Cur()
        if s.startswith('DELETE FROM user_webauthn_credentials'):
            self.deleted.append(params)
            return _Cur()
        if s.startswith('UPDATE users SET last_login'):
            return _Cur()
        raise AssertionError('unexpected SQL: ' + s)

    def commit(self):
        self.committed += 1


def _client(monkeypatch, conn):
    for mod in list(sys.modules.values()):
        if mod is not None and getattr(mod, 'get_db', None) is not None:
            monkeypatch.setattr(mod, 'get_db', lambda conn=conn: conn, raising=False)
    _appmod.app.config['TESTING'] = True
    _appmod.app.config['WTF_CSRF_ENABLED'] = False
    return _appmod.app.test_client()


def test_login_endpoints_are_auth_exempt():
    # Reached from the login page with no session yet -- must bypass the wall.
    assert 'auth.webauthn_login_options' in _appmod._AUTH_EXEMPT_ENDPOINTS
    assert 'auth.webauthn_login_verify' in _appmod._AUTH_EXEMPT_ENDPOINTS
    # Registration requires an existing session -- must NOT be exempt.
    assert 'profile.webauthn_register_options' not in _appmod._AUTH_EXEMPT_ENDPOINTS
    assert 'profile.webauthn_register_verify' not in _appmod._AUTH_EXEMPT_ENDPOINTS


# ── Sign-in ceremony (routes/auth.py) ───────────────────────────────────────

def test_login_options_issues_discoverable_challenge(monkeypatch):
    client = _client(monkeypatch, _Conn())
    resp = client.post('/auth/webauthn/login/options')
    assert resp.status_code == 200
    data = resp.get_json()
    assert data.get('challenge')
    assert not data.get('allowCredentials')  # discoverable -- no server-side allow-list
    with client.session_transaction() as sess:
        assert sess.get('webauthn_login_challenge')


def test_login_verify_without_prior_options_rejected(monkeypatch):
    client = _client(monkeypatch, _Conn())
    resp = client.post('/auth/webauthn/login/verify', json={'id': 'x'})
    assert resp.status_code == 400


def test_login_verify_unrecognized_credential_rejected(monkeypatch):
    client = _client(monkeypatch, _Conn())
    with client.session_transaction() as sess:
        sess['webauthn_login_challenge'] = 'Y2hhbGxlbmdl'
    resp = client.post('/auth/webauthn/login/verify', json={'id': 'never-registered'})
    assert resp.status_code == 400
    with client.session_transaction() as sess:
        assert 'user_id' not in sess


def test_login_verify_success_grants_session_without_totp(monkeypatch):
    # Andy's call: a passkey is accepted on its own -- signing in with one
    # must never consult mfa.is_enabled / trigger the TOTP challenge, even for
    # an account that has TOTP turned on.
    def _fail_if_called(*a, **k):
        raise AssertionError('mfa must not be consulted for a passkey login')
    monkeypatch.setattr(_auth.mfa, 'is_enabled', _fail_if_called)

    conn = _Conn(
        user={'id': 7, 'username': 'andy'},
        credentials=[{'id': 1, 'user_id': 7, 'credential_id': 'AQIDBA',
                      'public_key': 'cHVia2V5', 'sign_count': 3}],
    )
    client = _client(monkeypatch, conn)
    with client.session_transaction() as sess:
        sess['webauthn_login_challenge'] = 'Y2hhbGxlbmdl'

    class _Verification:
        new_sign_count = 4

    monkeypatch.setattr(webauthn_helper, 'verify_authentication_response',
                        lambda **kw: _Verification())

    resp = client.post('/auth/webauthn/login/verify', json={'id': 'AQIDBA'})
    assert resp.status_code == 200
    assert resp.get_json()['next']
    with client.session_transaction() as sess:
        assert sess.get('user_id') == 7
        assert sess.get('username') == 'andy'
        # The pending-login-challenge marker is consumed, not left lingering.
        assert 'webauthn_login_challenge' not in sess
    assert conn.committed  # _finalize_login's last_login write landed


def test_login_verify_bad_signature_does_not_grant_session(monkeypatch):
    conn = _Conn(credentials=[{'id': 1, 'user_id': 7, 'credential_id': 'AQIDBA',
                              'public_key': 'cHVia2V5', 'sign_count': 3}])
    client = _client(monkeypatch, conn)
    with client.session_transaction() as sess:
        sess['webauthn_login_challenge'] = 'Y2hhbGxlbmdl'

    def _boom(**kw):
        raise ValueError('signature mismatch')

    monkeypatch.setattr(webauthn_helper, 'verify_authentication_response', _boom)
    resp = client.post('/auth/webauthn/login/verify', json={'id': 'AQIDBA'})
    assert resp.status_code == 400
    with client.session_transaction() as sess:
        assert 'user_id' not in sess


# ── Registration ceremony (routes/profile.py) ───────────────────────────────

def test_register_options_requires_a_session(monkeypatch):
    client = _client(monkeypatch, _Conn())
    resp = client.post('/profile/webauthn/register/options')
    # POST + no session -> the auth wall's 401 branch (a GET would redirect).
    assert resp.status_code == 401


def test_register_verify_without_prior_options_rejected(monkeypatch):
    client = _client(monkeypatch, _Conn())
    with client.session_transaction() as sess:
        sess['user_id'] = 7
    resp = client.post('/profile/webauthn/register/verify', json={'id': 'AQIDBA'})
    assert resp.status_code == 400


def test_register_verify_stores_credential_for_session_user(monkeypatch):
    conn = _Conn(user={'id': 7, 'username': 'andy'})
    client = _client(monkeypatch, conn)
    with client.session_transaction() as sess:
        sess['user_id'] = 7
        sess['webauthn_register_challenge'] = 'Y2hhbGxlbmdl'

    class _Verification:
        credential_public_key = b'raw-public-key-bytes'
        sign_count = 0

    monkeypatch.setattr(webauthn_helper, 'verify_registration_response',
                        lambda **kw: _Verification())
    resp = client.post('/profile/webauthn/register/verify',
                       json={'id': 'AQIDBA', 'nickname': 'My Phone'})
    assert resp.status_code == 200
    assert conn.inserted, 'expected an INSERT into user_webauthn_credentials'
    user_id, credential_id, public_key_b64url, sign_count, nickname = conn.inserted[0]
    assert user_id == 7
    assert credential_id == 'AQIDBA'
    assert sign_count == 0
    assert nickname == 'My Phone'
    assert conn.committed


def test_register_verify_bad_ceremony_rejected(monkeypatch):
    conn = _Conn(user={'id': 7, 'username': 'andy'})
    client = _client(monkeypatch, conn)
    with client.session_transaction() as sess:
        sess['user_id'] = 7
        sess['webauthn_register_challenge'] = 'Y2hhbGxlbmdl'

    def _boom(**kw):
        raise ValueError('bad attestation')

    monkeypatch.setattr(webauthn_helper, 'verify_registration_response', _boom)
    resp = client.post('/profile/webauthn/register/verify', json={'id': 'AQIDBA'})
    assert resp.status_code == 400
    assert not conn.inserted


def test_delete_is_scoped_to_the_session_user(monkeypatch):
    conn = _Conn(user={'id': 7, 'username': 'andy'})
    client = _client(monkeypatch, conn)
    with client.session_transaction() as sess:
        sess['user_id'] = 7
    resp = client.post('/profile/webauthn/3/delete')
    assert resp.status_code in (302, 303)
    assert conn.deleted == [(3, 7)]
