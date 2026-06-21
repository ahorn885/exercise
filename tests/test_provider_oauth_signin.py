"""OAuth sign-in / connect-first identity tests (#251, slice 1: Wahoo).

Covers the no-session "sign in / sign up with Wahoo" branch added to
routes/wahoo.py, the logged-in connect path also recording an identity link,
and the pure username-synthesis + feature-flag helpers in
routes/provider_identity.py.

Network + DB writes are monkeypatched (the container can't reach Neon; the
DB-backed identity helpers are verify-owed against live PG, Rule #14). The
assertions cover route branching, the redirect targets, and the values handed
to the identity/auth helpers.
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

    # Endpoints the callback redirects to via url_for — stub so they resolve.
    @app.route('/login', endpoint='auth.login')
    def _login():  # pragma: no cover
        return 'login'

    @app.route('/dash', endpoint='dashboard.index')
    def _dash():  # pragma: no cover
        return 'dash'

    @app.route('/onboarding/connect', endpoint='onboarding.connect')
    def _connect():  # pragma: no cover
        return 'connect'

    return app


def _state_from_location(location):
    q = urllib.parse.urlparse(location).query
    return urllib.parse.parse_qs(q).get('state', [None])[0]


# ── Feature flag + username synthesis (pure) ──────────────────────────────

class TestIdentityHelpers:
    def test_signin_disabled_by_default(self, monkeypatch):
        from routes import provider_identity as pi
        monkeypatch.delenv('PROVIDER_OAUTH_SIGNIN', raising=False)
        assert pi.signin_enabled() is False

    @pytest.mark.parametrize('val', ['1', 'true', 'YES', 'on'])
    def test_signin_enabled_truthy(self, monkeypatch, val):
        from routes import provider_identity as pi
        monkeypatch.setenv('PROVIDER_OAUTH_SIGNIN', val)
        assert pi.signin_enabled() is True

    def test_slugify_strips_to_alphanumeric(self):
        from routes import provider_identity as pi
        assert pi._slugify_username('Alex P.') == 'alexp'
        assert pi._slugify_username('  Renée-Marie  ') == 'renemarie'
        assert pi._slugify_username('') == ''

    def test_garmin_not_a_signin_provider(self):
        from routes import provider_identity as pi
        assert 'garmin' not in pi.SIGNIN_PROVIDERS
        assert {'strava', 'wahoo', 'oura'} <= pi.SIGNIN_PROVIDERS


# ── Wahoo no-session sign-in ──────────────────────────────────────────────

class TestWahooSignin:
    def _token_resp(self):
        return _FakeResp({'access_token': 'AT', 'refresh_token': 'RT',
                          'expires_in': 7200})

    def test_start_bounces_to_login_when_flag_off(self, monkeypatch):
        import routes.wahoo as wahoo
        monkeypatch.setattr(wahoo, 'current_user_id', lambda: None)
        monkeypatch.delenv('PROVIDER_OAUTH_SIGNIN', raising=False)
        client = _make_app(wahoo.bp).test_client()
        resp = client.get('/wahoo/oauth/start')
        assert resp.status_code == 302
        assert resp.headers['Location'].startswith('/login')

    def test_start_redirects_to_consent_when_flag_on(self, monkeypatch):
        import routes.wahoo as wahoo
        monkeypatch.setattr(wahoo, 'current_user_id', lambda: None)
        monkeypatch.setenv('PROVIDER_OAUTH_SIGNIN', '1')
        monkeypatch.setenv('WAHOO_CLIENT_ID', 'cid')
        client = _make_app(wahoo.bp).test_client()
        resp = client.get('/wahoo/oauth/start')
        assert resp.status_code == 302
        assert resp.headers['Location'].startswith(wahoo._WAHOO_AUTH_URL)
        assert _state_from_location(resp.headers['Location'])

    def test_callback_creates_passwordless_account(self, monkeypatch):
        import routes.wahoo as wahoo
        captured = {}
        monkeypatch.setattr(wahoo, 'current_user_id', lambda: None)
        monkeypatch.setattr(wahoo, 'get_db', lambda: object())
        monkeypatch.setenv('PROVIDER_OAUTH_SIGNIN', '1')
        monkeypatch.setenv('WAHOO_CLIENT_ID', 'cid')
        monkeypatch.setenv('WAHOO_CLIENT_SECRET', 'secret')
        monkeypatch.setattr(wahoo.requests, 'post', lambda *a, **k: self._token_resp())
        monkeypatch.setattr(wahoo, '_fetch_wahoo_profile', lambda _t: {
            'id': 555, 'email': 'a@b.test', 'first': 'Alex', 'last': 'P'})
        monkeypatch.setattr(wahoo.pi, 'get_identity', lambda db, p, u: None)
        monkeypatch.setattr(wahoo.pi, 'create_signin_user',
                            lambda db, **kw: captured.update(kw) or (123, 'alex'))
        monkeypatch.setattr(wahoo, '_persist_wahoo_auth',
                            lambda *a, **k: captured.setdefault('persisted', a[1]))
        client = _make_app(wahoo.bp).test_client()

        start = client.get('/wahoo/oauth/start')
        state = _state_from_location(start.headers['Location'])
        resp = client.get(f'/wahoo/oauth/callback?code=C&state={state}')

        assert resp.status_code == 302
        assert resp.headers['Location'] == '/onboarding/connect'  # new athlete
        assert captured['provider'] == 'wahoo'
        assert captured['provider_user_id'] == '555'
        assert captured['email'] == 'a@b.test'
        assert captured['display_name'] == 'Alex P'
        assert captured['persisted'] == 123  # auth persisted for the new user

    def test_callback_logs_in_existing_identity(self, monkeypatch):
        import routes.wahoo as wahoo
        seen = {}
        monkeypatch.setattr(wahoo, 'current_user_id', lambda: None)
        monkeypatch.setattr(wahoo, 'get_db', lambda: object())
        monkeypatch.setenv('PROVIDER_OAUTH_SIGNIN', '1')
        monkeypatch.setenv('WAHOO_CLIENT_ID', 'cid')
        monkeypatch.setenv('WAHOO_CLIENT_SECRET', 'secret')
        monkeypatch.setattr(wahoo.requests, 'post', lambda *a, **k: self._token_resp())
        monkeypatch.setattr(wahoo, '_fetch_wahoo_profile', lambda _t: {'id': 555})
        monkeypatch.setattr(wahoo.pi, 'get_identity',
                            lambda db, p, u: {'id': 9, 'user_id': 42})
        monkeypatch.setattr(wahoo.pi, 'bump_last_login',
                            lambda db, iid: seen.setdefault('bumped', iid))
        monkeypatch.setattr(wahoo.pi, 'get_username', lambda db, uid: 'alex')
        monkeypatch.setattr(wahoo.pi, 'create_signin_user',
                            lambda *a, **k: pytest.fail('must not create on match'))
        monkeypatch.setattr(wahoo, '_persist_wahoo_auth',
                            lambda *a, **k: seen.setdefault('persisted', a[1]))
        client = _make_app(wahoo.bp).test_client()

        start = client.get('/wahoo/oauth/start')
        state = _state_from_location(start.headers['Location'])
        resp = client.get(f'/wahoo/oauth/callback?code=C&state={state}')

        assert resp.status_code == 302
        assert resp.headers['Location'] == '/dash'  # returning athlete
        assert seen['bumped'] == 9
        assert seen['persisted'] == 42

    def test_callback_bounces_to_login_when_flag_off(self, monkeypatch):
        import routes.wahoo as wahoo
        monkeypatch.setattr(wahoo, 'current_user_id', lambda: None)
        monkeypatch.delenv('PROVIDER_OAUTH_SIGNIN', raising=False)
        client = _make_app(wahoo.bp).test_client()
        resp = client.get('/wahoo/oauth/callback?code=C&state=x')
        assert resp.status_code == 302
        assert resp.headers['Location'].startswith('/login')


# ── Wahoo logged-in connect also links identity ───────────────────────────

class TestWahooConnectLinksIdentity:
    def _setup(self, monkeypatch, link_result):
        import routes.wahoo as wahoo
        captured = {}
        monkeypatch.setattr(wahoo, 'current_user_id', lambda: 7)
        monkeypatch.setattr(wahoo, 'get_db', lambda: object())
        monkeypatch.setenv('WAHOO_CLIENT_ID', 'cid')
        monkeypatch.setenv('WAHOO_CLIENT_SECRET', 'secret')
        monkeypatch.setattr(wahoo.requests, 'post', lambda *a, **k: _FakeResp({
            'access_token': 'AT', 'refresh_token': 'RT', 'expires_in': 7200,
            'user': {'id': 42}}))
        monkeypatch.setattr(wahoo, '_persist_wahoo_auth',
                            lambda *a, **k: captured.setdefault('persisted', a[1]))
        monkeypatch.setattr(wahoo.pi, 'link_identity',
                            lambda db, uid, prov, puid, **k:
                            captured.update(link=(uid, prov, puid)) or link_result)
        return wahoo, captured

    def test_connect_records_link_and_redirects(self, monkeypatch):
        wahoo, captured = self._setup(monkeypatch, (True, 'linked'))
        client = _make_app(wahoo.bp).test_client()
        start = client.get('/wahoo/oauth/start?return_to=/connections')
        state = _state_from_location(start.headers['Location'])
        resp = client.get(f'/wahoo/oauth/callback?code=C&state={state}')
        assert resp.status_code == 302
        assert resp.headers['Location'] == '/connections?wahoo_connected=1'
        assert captured['persisted'] == 7
        assert captured['link'] == (7, 'wahoo', '42')

    def test_connect_refuses_identity_claimed_by_other(self, monkeypatch):
        wahoo, captured = self._setup(monkeypatch, (False, 'claimed_by_other'))
        client = _make_app(wahoo.bp).test_client()
        start = client.get('/wahoo/oauth/start?return_to=/connections')
        state = _state_from_location(start.headers['Location'])
        resp = client.get(f'/wahoo/oauth/callback?code=C&state={state}')
        assert resp.status_code == 302
        assert 'wahoo_oauth_error=already_linked' in resp.headers['Location']


# ── Strava no-session sign-in (the no-email path) ─────────────────────────

class TestStravaSignin:
    def _token_resp(self, athlete):
        return _FakeResp({'access_token': 'AT', 'refresh_token': 'RT',
                          'expires_at': 1_900_000_000, 'athlete': athlete})

    def test_start_bounces_to_login_when_flag_off(self, monkeypatch):
        import routes.strava as strava
        monkeypatch.setattr(strava, 'current_user_id', lambda: None)
        monkeypatch.delenv('PROVIDER_OAUTH_SIGNIN', raising=False)
        client = _make_app(strava.bp).test_client()
        resp = client.get('/strava/oauth/start')
        assert resp.status_code == 302
        assert resp.headers['Location'].startswith('/login')

    def test_callback_creates_passwordless_account_without_email(self, monkeypatch):
        import routes.strava as strava
        captured = {}
        monkeypatch.setattr(strava, 'current_user_id', lambda: None)
        monkeypatch.setattr(strava, 'get_db', lambda: object())
        monkeypatch.setenv('PROVIDER_OAUTH_SIGNIN', '1')
        monkeypatch.setenv('STRAVA_CLIENT_ID', 'cid')
        monkeypatch.setenv('STRAVA_CLIENT_SECRET', 'secret')
        monkeypatch.setattr(strava.requests, 'post', lambda *a, **k: self._token_resp(
            {'id': 42, 'firstname': 'Alex', 'lastname': 'P'}))
        monkeypatch.setattr(strava.pi, 'get_identity', lambda db, p, u: None)
        monkeypatch.setattr(strava.pi, 'create_signin_user',
                            lambda db, **kw: captured.update(kw) or (123, 'alex'))
        monkeypatch.setattr(strava, '_persist_strava_auth',
                            lambda *a, **k: captured.setdefault('persisted', a[1]))
        client = _make_app(strava.bp).test_client()

        start = client.get('/strava/oauth/start')
        state = _state_from_location(start.headers['Location'])
        resp = client.get(f'/strava/oauth/callback?code=C&state={state}')

        assert resp.status_code == 302
        assert resp.headers['Location'] == '/onboarding/connect'
        assert captured['provider'] == 'strava'
        assert captured['provider_user_id'] == '42'
        assert captured['email'] is None  # Strava exposes no email
        assert captured['display_name'] == 'Alex P'
        assert captured['persisted'] == 123

    def test_callback_logs_in_existing_identity(self, monkeypatch):
        import routes.strava as strava
        seen = {}
        monkeypatch.setattr(strava, 'current_user_id', lambda: None)
        monkeypatch.setattr(strava, 'get_db', lambda: object())
        monkeypatch.setenv('PROVIDER_OAUTH_SIGNIN', '1')
        monkeypatch.setenv('STRAVA_CLIENT_ID', 'cid')
        monkeypatch.setenv('STRAVA_CLIENT_SECRET', 'secret')
        monkeypatch.setattr(strava.requests, 'post', lambda *a, **k: self._token_resp(
            {'id': 42}))
        monkeypatch.setattr(strava.pi, 'get_identity',
                            lambda db, p, u: {'id': 9, 'user_id': 77})
        monkeypatch.setattr(strava.pi, 'bump_last_login',
                            lambda db, iid: seen.setdefault('bumped', iid))
        monkeypatch.setattr(strava.pi, 'get_username', lambda db, uid: 'alex')
        monkeypatch.setattr(strava.pi, 'create_signin_user',
                            lambda *a, **k: pytest.fail('must not create on match'))
        monkeypatch.setattr(strava, '_persist_strava_auth',
                            lambda *a, **k: seen.setdefault('persisted', a[1]))
        client = _make_app(strava.bp).test_client()

        start = client.get('/strava/oauth/start')
        state = _state_from_location(start.headers['Location'])
        resp = client.get(f'/strava/oauth/callback?code=C&state={state}')

        assert resp.status_code == 302
        assert resp.headers['Location'] == '/dash'
        assert seen['bumped'] == 9
        assert seen['persisted'] == 77

    def test_connect_path_links_identity(self, monkeypatch):
        import routes.strava as strava
        captured = {}
        monkeypatch.setattr(strava, 'current_user_id', lambda: 7)
        monkeypatch.setattr(strava, 'get_db', lambda: object())
        monkeypatch.setenv('STRAVA_CLIENT_ID', 'cid')
        monkeypatch.setenv('STRAVA_CLIENT_SECRET', 'secret')
        monkeypatch.setattr(strava.requests, 'post', lambda *a, **k: self._token_resp(
            {'id': 42}))
        monkeypatch.setattr(strava, '_persist_strava_auth',
                            lambda *a, **k: captured.setdefault('persisted', a[1]))
        monkeypatch.setattr(strava.pi, 'link_identity',
                            lambda db, uid, prov, puid, **k:
                            captured.update(link=(uid, prov, puid)) or (True, 'linked'))
        client = _make_app(strava.bp).test_client()
        start = client.get('/strava/oauth/start?return_to=/connections')
        state = _state_from_location(start.headers['Location'])
        resp = client.get(f'/strava/oauth/callback?code=C&state={state}')
        assert resp.status_code == 302
        assert resp.headers['Location'] == '/connections?strava_connected=1'
        assert captured['persisted'] == 7
        assert captured['link'] == (7, 'strava', '42')
