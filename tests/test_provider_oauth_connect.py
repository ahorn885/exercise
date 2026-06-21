"""OAuth connect-flow tests for the Strava + Whoop live-wiring slice (#681 (B)).

Drives `/{provider}/oauth/start` → `/{provider}/oauth/callback` end-to-end via a
test client so the CSRF state round-trips through the real session. Network +
`provider_auth` writes are monkeypatched; the assertions cover the authorize
redirect shape, the token-exchange persist, and the success redirect.
"""

from __future__ import annotations

import os
import urllib.parse

import pytest
from flask import Flask


class _FakeResp:
    def __init__(self, payload, status=200):
        self._payload = payload
        self.status_code = status

    def raise_for_status(self):
        if self.status_code >= 400:
            import requests
            raise requests.RequestException(f'status {self.status_code}')

    def json(self):
        return self._payload


def _make_app(bp):
    root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    app = Flask(__name__, template_folder=os.path.join(root, 'templates'))
    app.config['SECRET_KEY'] = 'test'
    app.config['TESTING'] = True
    app.register_blueprint(bp)

    # oauth_start/callback bounce to url_for('auth.login') when logged out;
    # register a stub endpoint so url_for resolves even though we don't hit it.
    @app.route('/login', endpoint='auth.login')
    def _login():  # pragma: no cover - never reached (user is logged in)
        return 'login'

    return app


def _state_from_location(location):
    q = urllib.parse.urlparse(location).query
    return urllib.parse.parse_qs(q).get('state', [None])[0]


# ── Strava ────────────────────────────────────────────────────────────

class TestStravaOAuth:
    def test_start_redirects_to_authorize_with_scopes_and_state(self, monkeypatch):
        import routes.strava as strava
        monkeypatch.setattr(strava, 'current_user_id', lambda: 7)
        monkeypatch.setenv('STRAVA_CLIENT_ID', 'cid')
        client = _make_app(strava.bp).test_client()

        resp = client.get('/strava/oauth/start?return_to=/connections')
        assert resp.status_code == 302
        loc = resp.headers['Location']
        assert loc.startswith(strava._STRAVA_AUTH_URL)
        q = urllib.parse.parse_qs(urllib.parse.urlparse(loc).query)
        assert q['client_id'] == ['cid']
        assert q['scope'] == ['activity:read_all,profile:read_all']
        assert q['response_type'] == ['code']
        assert q['state'][0]  # non-empty CSRF state

    def test_start_503_without_client_id(self, monkeypatch):
        import routes.strava as strava
        monkeypatch.setattr(strava, 'current_user_id', lambda: 7)
        monkeypatch.delenv('STRAVA_CLIENT_ID', raising=False)
        client = _make_app(strava.bp).test_client()
        assert client.get('/strava/oauth/start').status_code == 503

    def test_callback_exchanges_code_and_persists(self, monkeypatch):
        import routes.strava as strava
        captured = {}
        monkeypatch.setattr(strava, 'current_user_id', lambda: 7)
        monkeypatch.setattr(strava, 'get_db', lambda: object())
        monkeypatch.setenv('STRAVA_CLIENT_ID', 'cid')
        monkeypatch.setenv('STRAVA_CLIENT_SECRET', 'secret')
        monkeypatch.setattr(strava.requests, 'post', lambda *a, **k: _FakeResp({
            'access_token': 'AT', 'refresh_token': 'RT', 'expires_at': 1_900_000_000,
            'athlete': {'id': 42},
        }))
        monkeypatch.setattr(strava.pa, 'upsert_auth',
                            lambda db, **kw: captured.update(kw) or 1)
        monkeypatch.setattr(strava.pa, 'record_oauth_scope_ack',
                            lambda db, **kw: captured.setdefault('ack', kw) or 1)
        # Connect path now also records the identity link (#251 §6.2); stub it —
        # identity behaviour is covered in test_provider_oauth_signin.
        monkeypatch.setattr(strava.pi, 'link_identity', lambda *a, **k: (True, 'linked'))
        client = _make_app(strava.bp).test_client()

        # round-trip the state via a real start call
        start = client.get('/strava/oauth/start?return_to=/connections')
        state = _state_from_location(start.headers['Location'])

        resp = client.get(
            f'/strava/oauth/callback?code=C&state={state}'
            '&scope=activity:read_all')
        assert resp.status_code == 302
        assert resp.headers['Location'] == '/connections?strava_connected=1'
        assert captured['provider'] == 'strava'
        assert captured['access_token'] == 'AT'
        assert captured['refresh_token'] == 'RT'
        assert captured['provider_user_id'] == '42'
        assert captured['status'] == strava.pa.STATUS_ACTIVE
        # granted scope from the callback (athlete may deselect) is recorded
        assert captured['scopes'] == 'activity:read_all'

    def test_callback_400_on_state_mismatch(self, monkeypatch):
        import routes.strava as strava
        monkeypatch.setattr(strava, 'current_user_id', lambda: 7)
        client = _make_app(strava.bp).test_client()
        client.get('/strava/oauth/start')  # sets a state in session
        assert client.get(
            '/strava/oauth/callback?code=C&state=WRONG').status_code == 400


# ── Whoop ─────────────────────────────────────────────────────────────

class TestWhoopOAuth:
    def test_start_redirects_with_space_separated_scopes(self, monkeypatch):
        import routes.whoop as whoop
        monkeypatch.setattr(whoop, 'current_user_id', lambda: 7)
        monkeypatch.setenv('WHOOP_CLIENT_ID', 'cid')
        client = _make_app(whoop.bp).test_client()

        resp = client.get('/whoop/oauth/start?return_to=/connections')
        assert resp.status_code == 302
        q = urllib.parse.parse_qs(urllib.parse.urlparse(resp.headers['Location']).query)
        assert q['client_id'] == ['cid']
        assert 'offline' in q['scope'][0].split()  # refresh_token requires offline
        assert 'read:sleep' in q['scope'][0].split()
        assert q['state'][0]

    def test_callback_fetches_profile_and_persists(self, monkeypatch):
        import routes.whoop as whoop
        captured = {}
        monkeypatch.setattr(whoop, 'current_user_id', lambda: 7)
        monkeypatch.setattr(whoop, 'get_db', lambda: object())
        monkeypatch.setenv('WHOOP_CLIENT_ID', 'cid')
        monkeypatch.setenv('WHOOP_CLIENT_SECRET', 'secret')
        monkeypatch.setattr(whoop.requests, 'post', lambda *a, **k: _FakeResp({
            'access_token': 'AT', 'refresh_token': 'RT', 'expires_in': 3600,
            'scope': 'read:sleep offline',
        }))
        monkeypatch.setattr(whoop.requests, 'get', lambda *a, **k: _FakeResp({
            'user_id': 9001, 'email': 'a@b.test',
        }))
        monkeypatch.setattr(whoop.pa, 'upsert_auth',
                            lambda db, **kw: captured.update(kw) or 1)
        monkeypatch.setattr(whoop.pa, 'record_oauth_scope_ack',
                            lambda db, **kw: 1)
        client = _make_app(whoop.bp).test_client()

        start = client.get('/whoop/oauth/start?return_to=/connections')
        state = _state_from_location(start.headers['Location'])
        resp = client.get(f'/whoop/oauth/callback?code=C&state={state}')

        assert resp.status_code == 302
        assert resp.headers['Location'] == '/connections?whoop_connected=1'
        assert captured['provider'] == 'whoop'
        assert captured['access_token'] == 'AT'
        assert captured['provider_user_id'] == '9001'  # from the profile fetch
        assert captured['token_expires_at'] is not None  # expires_in → absolute


# ── Hub wiring ────────────────────────────────────────────────────────

def test_strava_whoop_are_connectable_not_stubs():
    """They moved from the 'Not available yet' stub list into the real
    OAuth-provider set (each needs a `<slug>.oauth_start` endpoint)."""
    from routes.profile import CONNECTION_PROVIDERS
    from routes.connections import STUB_PROVIDERS
    slugs = {p[0] for p in CONNECTION_PROVIDERS}
    assert {'strava', 'whoop'} <= slugs
    stub_slugs = {s['slug'] for s in STUB_PROVIDERS}
    assert not ({'strava', 'whoop'} & stub_slugs)
    # endpoint references are well-formed
    assert ('strava', 'Strava', 'strava.oauth_start') in CONNECTION_PROVIDERS
    assert ('whoop', 'Whoop', 'whoop.oauth_start') in CONNECTION_PROVIDERS
