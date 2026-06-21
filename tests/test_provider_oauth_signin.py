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

    def test_enabled_signin_providers_empty_when_flag_off(self, monkeypatch):
        from routes import provider_identity as pi
        monkeypatch.delenv('PROVIDER_OAUTH_SIGNIN', raising=False)
        monkeypatch.setenv('STRAVA_CLIENT_ID', 'cid')
        assert pi.enabled_signin_providers() == []

    def test_enabled_signin_providers_needs_client_id(self, monkeypatch):
        from routes import provider_identity as pi
        monkeypatch.setenv('PROVIDER_OAUTH_SIGNIN', '1')
        monkeypatch.setenv('STRAVA_CLIENT_ID', 'cid')
        monkeypatch.delenv('WAHOO_CLIENT_ID', raising=False)
        monkeypatch.delenv('OURA_CLIENT_ID', raising=False)
        slugs = [p['slug'] for p in pi.enabled_signin_providers()]
        assert slugs == ['strava']  # wahoo/oura omitted — no client id configured

    def test_enabled_signin_providers_all_configured(self, monkeypatch):
        from routes import provider_identity as pi
        monkeypatch.setenv('PROVIDER_OAUTH_SIGNIN', '1')
        monkeypatch.setenv('STRAVA_CLIENT_ID', 'cid')
        monkeypatch.setenv('WAHOO_CLIENT_ID', 'cid')
        monkeypatch.setenv('OURA_CLIENT_ID', 'cid')
        providers = pi.enabled_signin_providers()
        slugs = {p['slug'] for p in providers}
        assert slugs == {'strava', 'wahoo', 'oura'}
        # endpoint references are well-formed for url_for
        assert all(p['endpoint'].endswith('.oauth_start') for p in providers)


class _Cur:
    def __init__(self, rows, rowcount=0):
        self._rows = rows
        self.rowcount = rowcount

    def fetchone(self):
        return self._rows[0] if self._rows else None

    def fetchall(self):
        return self._rows


class _FakeIdentityDB:
    """Minimal in-memory stand-in for the provider_identity + users queries
    unlink_identity / count_login_methods issue, so the self-lockout guard can
    be verified without a live PG (NOW()/dialect bugs stay verify-owed)."""
    def __init__(self, identities, passworded_users=()):
        self.identities = set(identities)          # {(user_id, provider)}
        self.passworded = set(passworded_users)    # {user_id}
        self.committed = False

    def execute(self, sql, params=()):
        s = ' '.join(sql.split())
        if s.startswith('SELECT 1 FROM provider_identity WHERE user_id = ? AND provider = ?'):
            uid, prov = params
            return _Cur([{'x': 1}] if (uid, prov) in self.identities else [])
        if s.startswith('SELECT COUNT(*) AS n FROM provider_identity WHERE user_id = ?'):
            uid = params[0]
            return _Cur([{'n': sum(1 for (u, _p) in self.identities if u == uid)}])
        if s.startswith("SELECT 1 FROM users WHERE id = ? AND COALESCE(password_hash"):
            return _Cur([{'x': 1}] if params[0] in self.passworded else [])
        if s.startswith('DELETE FROM provider_identity WHERE user_id = ? AND provider = ?'):
            uid, prov = params
            existed = (uid, prov) in self.identities
            self.identities.discard((uid, prov))
            return _Cur([], rowcount=1 if existed else 0)
        raise AssertionError('unexpected SQL: ' + s)

    def commit(self):
        self.committed = True


class TestUnlinkGuard:
    def test_blocks_removing_the_only_login_method(self):
        from routes import provider_identity as pi
        db = _FakeIdentityDB({(1, 'strava')})  # one identity, no password
        ok, reason = pi.unlink_identity(db, 1, 'strava')
        assert (ok, reason) == (False, 'last_method')
        assert (1, 'strava') in db.identities  # not removed

    def test_allows_unlink_when_password_is_set(self):
        from routes import provider_identity as pi
        db = _FakeIdentityDB({(1, 'strava')}, passworded_users={1})
        ok, reason = pi.unlink_identity(db, 1, 'strava')
        assert (ok, reason) == (True, 'removed')
        assert (1, 'strava') not in db.identities

    def test_allows_unlink_when_another_identity_remains(self):
        from routes import provider_identity as pi
        db = _FakeIdentityDB({(1, 'strava'), (1, 'wahoo')})
        ok, reason = pi.unlink_identity(db, 1, 'strava')
        assert (ok, reason) == (True, 'removed')
        assert db.identities == {(1, 'wahoo')}

    def test_noop_when_not_a_signin_method(self):
        from routes import provider_identity as pi
        db = _FakeIdentityDB({(1, 'strava')}, passworded_users={1})
        ok, reason = pi.unlink_identity(db, 1, 'oura')  # no oura identity
        assert ok is False and reason == 'removed'

    def test_count_login_methods_sums_identities_and_password(self):
        from routes import provider_identity as pi
        db = _FakeIdentityDB({(1, 'strava'), (1, 'wahoo')}, passworded_users={1})
        assert pi.count_login_methods(db, 1) == 3
        db2 = _FakeIdentityDB({(1, 'strava')})
        assert pi.count_login_methods(db2, 1) == 1


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
        monkeypatch.setattr(wahoo.pi, 'get_email',
                            lambda db, uid: captured.setdefault('acct_email', 'a@b.test'))
        monkeypatch.setattr(wahoo, 'send_verification_email',
                            lambda db, uid, email: captured.setdefault('verify_sent', (uid, email)))
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
        # provider-seeded email triggers a confirmation link
        assert captured['verify_sent'] == (123, 'a@b.test')

    def test_new_account_no_verification_when_email_dropped(self, monkeypatch):
        import routes.wahoo as wahoo
        captured = {}
        monkeypatch.setattr(wahoo, 'current_user_id', lambda: None)
        monkeypatch.setattr(wahoo, 'get_db', lambda: object())
        monkeypatch.setenv('PROVIDER_OAUTH_SIGNIN', '1')
        monkeypatch.setenv('WAHOO_CLIENT_ID', 'cid')
        monkeypatch.setenv('WAHOO_CLIENT_SECRET', 'secret')
        monkeypatch.setattr(wahoo.requests, 'post', lambda *a, **k: self._token_resp())
        monkeypatch.setattr(wahoo, '_fetch_wahoo_profile', lambda _t: {
            'id': 555, 'email': 'collides@b.test', 'first': 'Alex'})
        monkeypatch.setattr(wahoo.pi, 'get_identity', lambda db, p, u: None)
        monkeypatch.setattr(wahoo.pi, 'create_signin_user', lambda db, **kw: (123, 'alex'))
        # Collision: create_signin_user dropped the email → account has none.
        monkeypatch.setattr(wahoo.pi, 'get_email', lambda db, uid: None)
        monkeypatch.setattr(wahoo, 'send_verification_email',
                            lambda *a, **k: captured.setdefault('verify_sent', True))
        monkeypatch.setattr(wahoo, '_persist_wahoo_auth', lambda *a, **k: None)
        client = _make_app(wahoo.bp).test_client()
        start = client.get('/wahoo/oauth/start')
        state = _state_from_location(start.headers['Location'])
        resp = client.get(f'/wahoo/oauth/callback?code=C&state={state}')
        assert resp.status_code == 302
        assert 'verify_sent' not in captured  # nothing to confirm

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


# ── Oura no-session sign-in (email scope, no name) ────────────────────────

class TestOuraSignin:
    def _token_resp(self):
        return _FakeResp({'access_token': 'AT', 'refresh_token': 'RT',
                          'expires_in': 86400})

    def test_callback_creates_account_seeding_username_from_email(self, monkeypatch):
        import routes.oura as oura
        captured = {}
        monkeypatch.setattr(oura, 'current_user_id', lambda: None)
        monkeypatch.setattr(oura, 'get_db', lambda: object())
        monkeypatch.setenv('PROVIDER_OAUTH_SIGNIN', '1')
        monkeypatch.setenv('OURA_CLIENT_ID', 'cid')
        monkeypatch.setenv('OURA_CLIENT_SECRET', 'secret')
        monkeypatch.setattr(oura.requests, 'post', lambda *a, **k: self._token_resp())
        monkeypatch.setattr(oura, '_fetch_oura_personal_info',
                            lambda _t: {'id': 'oura-99', 'email': 'ringwearer@b.test'})
        monkeypatch.setattr(oura.pi, 'get_identity', lambda db, p, u: None)
        monkeypatch.setattr(oura.pi, 'create_signin_user',
                            lambda db, **kw: captured.update(kw) or (123, 'ringwearer'))
        monkeypatch.setattr(oura.pi, 'get_email',
                            lambda db, uid: 'ringwearer@b.test')
        monkeypatch.setattr(oura, 'send_verification_email',
                            lambda db, uid, email: captured.setdefault('verify_sent', (uid, email)))
        monkeypatch.setattr(oura, '_persist_oura_auth',
                            lambda *a, **k: captured.setdefault('persisted', a[1]))
        client = _make_app(oura.bp).test_client()

        start = client.get('/oura/oauth/start')
        state = _state_from_location(start.headers['Location'])
        resp = client.get(f'/oura/oauth/callback?code=C&state={state}')

        assert resp.status_code == 302
        assert resp.headers['Location'] == '/onboarding/connect'
        assert captured['provider'] == 'oura'
        assert captured['provider_user_id'] == 'oura-99'
        assert captured['email'] == 'ringwearer@b.test'
        assert captured['display_name'] is None       # Oura exposes no name
        assert captured['username_hint'] == 'ringwearer'  # email local-part
        assert captured['persisted'] == 123
        # provider-seeded email triggers a confirmation link
        assert captured['verify_sent'] == (123, 'ringwearer@b.test')

    def test_callback_logs_in_existing_identity(self, monkeypatch):
        import routes.oura as oura
        seen = {}
        monkeypatch.setattr(oura, 'current_user_id', lambda: None)
        monkeypatch.setattr(oura, 'get_db', lambda: object())
        monkeypatch.setenv('PROVIDER_OAUTH_SIGNIN', '1')
        monkeypatch.setenv('OURA_CLIENT_ID', 'cid')
        monkeypatch.setenv('OURA_CLIENT_SECRET', 'secret')
        monkeypatch.setattr(oura.requests, 'post', lambda *a, **k: self._token_resp())
        monkeypatch.setattr(oura, '_fetch_oura_personal_info',
                            lambda _t: {'id': 'oura-99', 'email': None})
        monkeypatch.setattr(oura.pi, 'get_identity',
                            lambda db, p, u: {'id': 5, 'user_id': 88})
        monkeypatch.setattr(oura.pi, 'bump_last_login',
                            lambda db, iid: seen.setdefault('bumped', iid))
        monkeypatch.setattr(oura.pi, 'get_username', lambda db, uid: 'ringwearer')
        monkeypatch.setattr(oura.pi, 'create_signin_user',
                            lambda *a, **k: pytest.fail('must not create on match'))
        monkeypatch.setattr(oura, '_persist_oura_auth',
                            lambda *a, **k: seen.setdefault('persisted', a[1]))
        client = _make_app(oura.bp).test_client()

        start = client.get('/oura/oauth/start')
        state = _state_from_location(start.headers['Location'])
        resp = client.get(f'/oura/oauth/callback?code=C&state={state}')

        assert resp.status_code == 302
        assert resp.headers['Location'] == '/dash'
        assert seen['bumped'] == 5
        assert seen['persisted'] == 88
