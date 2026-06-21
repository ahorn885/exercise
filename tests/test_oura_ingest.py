"""Oura live-wiring tests (#681 (B)) — OAuth connect, the sleep-document → daily
merge, and the webhook dispatch (thin pointer + subscription handshake). Matrix
§4: durations are seconds, lowest_heart_rate is RHR, average_hrv is ms.
"""

from __future__ import annotations

import json
import os
import urllib.parse

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


class _Cur:
    def __init__(self, row=None):
        self._row = row

    def fetchone(self):
        return self._row


class _MergeDB:
    def __init__(self):
        self.daily = {}

    def execute(self, sql, params=()):
        s = ' '.join(sql.split())
        if s.startswith('SELECT raw_payload'):
            return _Cur({'raw_payload': self.daily.get(params[1])}
                        if params[1] in self.daily else None)
        if "'daily_summary'" in s and 'INSERT INTO provider_raw_record' in s:
            self.daily[params[1]] = json.loads(params[3])
            return _Cur(None)
        return _Cur(None)

    def commit(self):
        pass


_SLEEP = {
    'day': '2026-06-18',
    'total_sleep_duration': 25200,    # 420 min
    'lowest_heart_rate': 47,
    'average_hrv': 62,
    'average_breath': 13.5,
}


def _make_app(bp):
    root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    app = Flask(__name__, template_folder=os.path.join(root, 'templates'))
    app.config['SECRET_KEY'] = 'test'
    app.config['TESTING'] = True
    app.register_blueprint(bp)

    @app.route('/login', endpoint='auth.login')
    def _login():  # pragma: no cover
        return 'login'

    return app


class TestSleepIngest:
    def test_sleep_maps_seconds_and_rhr(self, monkeypatch):
        import routes.oura as oura
        monkeypatch.setattr(oura, '_fetch', lambda db, u, p: _SLEEP)
        db = _MergeDB()
        assert oura._ingest_sleep(db, 7, 'slp1') is True
        row = db.daily['2026-06-18']
        assert row['total_sleep_min'] == 420.0     # 25200 s ÷ 60
        assert row['resting_hr'] == 47             # lowest_heart_rate, the real RHR
        assert row['hrv_rmssd_ms'] == 62.0
        assert row['date'] == '2026-06-18'

    def test_missing_day_is_noop(self, monkeypatch):
        import routes.oura as oura
        monkeypatch.setattr(oura, '_fetch', lambda db, u, p: {'total_sleep_duration': 1})
        db = _MergeDB()
        assert oura._ingest_sleep(db, 7, 'x') is False
        assert db.daily == {}


class TestOAuth:
    def test_start_redirects_with_scopes(self, monkeypatch):
        import routes.oura as oura
        monkeypatch.setattr(oura, 'current_user_id', lambda: 7)
        monkeypatch.setenv('OURA_CLIENT_ID', 'cid')
        resp = _make_app(oura.bp).test_client().get('/oura/oauth/start')
        assert resp.status_code == 302
        q = urllib.parse.parse_qs(urllib.parse.urlparse(resp.headers['Location']).query)
        assert q['client_id'] == ['cid']
        assert 'daily' in q['scope'][0].split()

    def test_callback_persists_with_personal_info_id(self, monkeypatch):
        import routes.oura as oura
        captured = {}
        monkeypatch.setattr(oura, 'current_user_id', lambda: 7)
        monkeypatch.setattr(oura, 'get_db', lambda: object())
        monkeypatch.setenv('OURA_CLIENT_ID', 'cid')
        monkeypatch.setenv('OURA_CLIENT_SECRET', 'secret')
        monkeypatch.setattr(oura.requests, 'post', lambda *a, **k: _FakeResp({
            'access_token': 'AT', 'refresh_token': 'RT', 'expires_in': 86400}))
        monkeypatch.setattr(oura.requests, 'get', lambda *a, **k: _FakeResp({'id': 'ouid'}))
        monkeypatch.setattr(oura.pa, 'upsert_auth', lambda db, **kw: captured.update(kw) or 1)
        monkeypatch.setattr(oura.pa, 'record_oauth_scope_ack', lambda db, **kw: 1)
        # Connect path now also records the identity link (#251 §6.2); stub it —
        # identity behaviour is covered in test_provider_oauth_signin.
        monkeypatch.setattr(oura.pi, 'link_identity', lambda *a, **k: (True, 'linked'))
        client = _make_app(oura.bp).test_client()
        start = client.get('/oura/oauth/start?return_to=/connections')
        state = urllib.parse.parse_qs(
            urllib.parse.urlparse(start.headers['Location']).query)['state'][0]
        resp = client.get(f'/oura/oauth/callback?code=C&state={state}')
        assert resp.headers['Location'] == '/connections?oura_connected=1'
        assert captured['provider'] == 'oura'
        assert captured['provider_user_id'] == 'ouid'


class _WHDB:
    def __init__(self):
        self.events = []
        self.updates = []

    def execute(self, sql, params=()):
        if 'INSERT INTO webhook_events' in sql:
            self.events.append(params)
            return _Cur({'id': 400})
        if 'UPDATE webhook_events' in sql:
            self.updates.append(params)
        return _Cur(None)

    def commit(self):
        pass


class TestWebhook:
    def test_get_handshake_echoes_challenge(self):
        import routes.oura as oura
        app = Flask(__name__)
        app.register_blueprint(oura.bp)
        resp = app.test_client().get('/oura/webhook?challenge=abc123')
        assert resp.status_code == 200
        assert resp.get_json()['challenge'] == 'abc123'

    def test_sleep_event_records_and_ingests(self, monkeypatch):
        import routes.oura as oura
        db = _WHDB()
        monkeypatch.setattr(oura, 'get_db', lambda: db)
        monkeypatch.setattr(oura.pa, 'get_auth_by_provider_user_id',
                            lambda d, p, pid: {'user_id': 7})
        calls = []
        monkeypatch.setattr(oura, '_ingest_sleep', lambda d, u, oid: calls.append((u, oid)))
        app = Flask(__name__)
        app.register_blueprint(oura.bp)
        resp = app.test_client().post('/oura/webhook', json={
            'data_type': 'sleep', 'event_type': 'create',
            'object_id': 'slp1', 'user_id': 'ouid'})
        assert resp.status_code == 200
        assert len(db.events) == 1
        assert calls == [(7, 'slp1')]

    def test_non_sleep_event_records_no_ingest(self, monkeypatch):
        import routes.oura as oura
        db = _WHDB()
        monkeypatch.setattr(oura, 'get_db', lambda: db)
        monkeypatch.setattr(oura.pa, 'get_auth_by_provider_user_id',
                            lambda d, p, pid: {'user_id': 7})
        calls = []
        monkeypatch.setattr(oura, '_ingest_sleep', lambda d, u, oid: calls.append((u, oid)))
        app = Flask(__name__)
        app.register_blueprint(oura.bp)
        resp = app.test_client().post('/oura/webhook', json={
            'data_type': 'daily_activity', 'event_type': 'create',
            'object_id': 'a1', 'user_id': 'ouid'})
        assert resp.status_code == 200
        assert len(db.events) == 1
        assert calls == []
