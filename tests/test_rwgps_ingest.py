"""RWGPS live-wiring tests (#681 (B)) — OAuth connect, HMAC verify, trip
normalization (matrix §10.1), the record-and-defer webhook (no synchronous
fetch), and the cron drain. Network + the shared writer are monkeypatched.
"""

from __future__ import annotations

import hashlib
import hmac
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
    def __init__(self, rows=None, one=None):
        self._rows = rows or []
        self._one = one

    def fetchone(self):
        return self._one

    def fetchall(self):
        return self._rows


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


# ── signature + normalize ─────────────────────────────────────────────

class TestSignatureAndNormalize:
    def test_signature_hex_hmac(self):
        from routes.ride_with_gps import _verify_signature
        body = b'{"notifications":[]}'
        sig = hmac.new(b'sec', body, hashlib.sha256).hexdigest()
        assert _verify_signature(body, sig, 'sec') is True
        assert _verify_signature(b'tampered', sig, 'sec') is False
        assert _verify_signature(body, None, 'sec') is False

    def test_normalize_trip_units_and_discipline(self):
        from routes.ride_with_gps import normalize_rwgps_trip
        d = normalize_rwgps_trip({
            'id': 7788, 'name': 'Gravel loop', 'activity_type': 'cycling:gravel',
            'distance': 32186.8, 'duration': 5400, 'elevation_gain': 304.8,
            'avg_hr': 142, 'avg_watts': 190, 'departed_at': '2026-06-17T14:00:00Z',
        })
        assert d['discipline_id'] == 'D-030'        # cycling:gravel
        assert d['activity'] == 'cycling'
        assert d['date'] == '2026-06-17'
        assert round(d['distance_mi'], 1) == 20.0
        assert round(d['duration_min'], 0) == 90
        assert round(d['elev_gain_ft'], 0) == 1000
        assert d['avg_hr'] == 142 and d['avg_power'] == 190
        assert d['_provider_raw']['payload']['rwgps_trip_id'] == 7788

    def test_stationary_flags_indoor_machine(self):
        from routes.ride_with_gps import normalize_rwgps_trip
        d = normalize_rwgps_trip({'id': 1, 'activity_type': 'cycling:indoor',
                                  'is_stationary': True})
        assert d['discipline_id'] == 'D-006'
        assert d['_provider_raw']['payload']['indoor_machine'] == 'Cycling trainer'


# ── webhook: record-and-defer ─────────────────────────────────────────

class _WHDB:
    def __init__(self):
        self.inserts = []

    def execute(self, sql, params=()):
        if 'INSERT INTO webhook_events' in sql:
            self.inserts.append(params)
        return _Cur()

    def commit(self):
        pass


class TestWebhookDefers:
    def test_records_without_fetching(self, monkeypatch):
        import routes.ride_with_gps as rw
        db = _WHDB()
        monkeypatch.setattr(rw, 'get_db', lambda: db)
        monkeypatch.setattr(rw.pa, 'get_auth_by_provider_user_id',
                            lambda d, p, pid: {'user_id': 7})
        monkeypatch.setattr(rw, '_verify_signature', lambda *a, **k: True)
        # If the webhook tried to ingest synchronously this would record it:
        fetched = []
        monkeypatch.setattr(rw, '_fetch_and_ingest_trip',
                            lambda d, u, url: fetched.append(url))
        app = Flask(__name__)
        app.register_blueprint(rw.bp)
        resp = app.test_client().post('/ride-with-gps/webhook', json={
            'notifications': [{'user_id': 99, 'item_url': '/api/v1/trips/7788', 'action': 'trip'}]})
        assert resp.status_code == 200
        assert len(db.inserts) == 1          # event recorded
        assert fetched == []                 # but NOT fetched synchronously (deferred)
        # the recorded row carries item_url as entity_id, processed_at NULL implied
        params = db.inserts[0]
        assert '/api/v1/trips/7788' in params


# ── cron drain ────────────────────────────────────────────────────────

class _CronDB:
    def __init__(self, pending):
        self._pending = pending
        self.updated = []

    def execute(self, sql, params=()):
        if 'SELECT id, user_id, entity_id' in sql:
            return _Cur(rows=self._pending)
        if 'UPDATE webhook_events SET processed_at' in sql:
            self.updated.append(params)
        return _Cur()

    def commit(self):
        pass


class TestCronDrain:
    def test_drains_pending_and_marks_processed(self, monkeypatch):
        import routes.ride_with_gps as rw
        db = _CronDB([
            {'id': 1, 'user_id': 7, 'entity_id': '/api/v1/trips/100', 'payload': '{}'},
            {'id': 2, 'user_id': 7, 'entity_id': '/api/v1/trips/200', 'payload': '{}'},
        ])
        monkeypatch.setattr(rw, 'get_db', lambda: db)
        monkeypatch.setattr(rw, 'cron_authorized', lambda: True)
        calls = []
        monkeypatch.setattr(rw, '_fetch_and_ingest_trip',
                            lambda d, u, url: calls.append(url) or True)
        app = Flask(__name__)
        app.register_blueprint(rw.bp)
        resp = app.test_client().get('/ride-with-gps/cron/process')
        assert resp.status_code == 200
        assert resp.get_json()['processed'] == 2
        assert calls == ['/api/v1/trips/100', '/api/v1/trips/200']
        assert len(db.updated) == 2          # both marked processed

    def test_cron_requires_auth(self, monkeypatch):
        import routes.ride_with_gps as rw
        monkeypatch.setattr(rw, 'cron_authorized', lambda: False)
        app = Flask(__name__)
        app.register_blueprint(rw.bp)
        assert app.test_client().get('/ride-with-gps/cron/process').status_code == 401


# ── fetch + ingest ────────────────────────────────────────────────────

class _IngestDB:
    def __init__(self, existing=False):
        self._existing = existing

    def execute(self, sql, params=()):
        if 'SELECT id FROM cardio_log' in sql:
            return _Cur(one={'id': 1} if self._existing else None)
        return _Cur()

    def commit(self):
        pass


class TestFetchIngest:
    def test_fetches_and_writes(self, monkeypatch):
        import routes.ride_with_gps as rw
        import routes.garmin as garmin
        monkeypatch.setattr(rw.pa, 'get_fresh_access_token', lambda *a, **k: 'T')
        monkeypatch.setattr(rw.requests, 'get', lambda *a, **k: _FakeResp({
            'trip': {'id': 100, 'activity_type': 'running:trail', 'distance': 5000,
                     'duration': 1500}}))
        captured = {}
        monkeypatch.setattr(garmin, '_bulk_insert_cardio',
                            lambda db, data, uid, gid, source='garmin', **k:
                                captured.update(gid=gid, source=source, data=data) or 1)
        assert rw._fetch_and_ingest_trip(_IngestDB(), 7, '/api/v1/trips/100') is True
        assert captured['source'] == 'rwgps'
        assert captured['gid'] == '100'
        assert captured['data']['discipline_id'] == 'D-001'

    def test_skips_already_imported(self, monkeypatch):
        import routes.ride_with_gps as rw
        monkeypatch.setattr(rw.pa, 'get_fresh_access_token', lambda *a, **k: 'T')
        monkeypatch.setattr(rw.requests, 'get', lambda *a, **k: _FakeResp({
            'trip': {'id': 100, 'activity_type': 'running:trail'}}))
        assert rw._fetch_and_ingest_trip(_IngestDB(existing=True), 7, '/x') is False


# ── OAuth connect ─────────────────────────────────────────────────────

class TestOAuth:
    def test_start_redirects(self, monkeypatch):
        import routes.ride_with_gps as rw
        monkeypatch.setattr(rw, 'current_user_id', lambda: 7)
        monkeypatch.setenv('RWGPS_CLIENT_ID', 'cid')
        resp = _make_app(rw.bp).test_client().get('/ride-with-gps/oauth/start')
        assert resp.status_code == 302
        assert resp.headers['Location'].startswith(rw._RWGPS_AUTH_URL)

    def test_callback_persists_with_fetched_user(self, monkeypatch):
        import routes.ride_with_gps as rw
        captured = {}
        monkeypatch.setattr(rw, 'current_user_id', lambda: 7)
        monkeypatch.setattr(rw, 'get_db', lambda: object())
        monkeypatch.setenv('RWGPS_CLIENT_ID', 'cid')
        monkeypatch.setenv('RWGPS_CLIENT_SECRET', 'secret')
        monkeypatch.setattr(rw.requests, 'post', lambda *a, **k: _FakeResp({
            'access_token': 'AT', 'refresh_token': 'RT', 'expires_in': 7200}))
        monkeypatch.setattr(rw.requests, 'get', lambda *a, **k: _FakeResp({'user': {'id': 55}}))
        monkeypatch.setattr(rw.pa, 'upsert_auth', lambda db, **kw: captured.update(kw) or 1)
        monkeypatch.setattr(rw.pa, 'record_oauth_scope_ack', lambda db, **kw: 1)
        client = _make_app(rw.bp).test_client()
        start = client.get('/ride-with-gps/oauth/start?return_to=/connections')
        state = urllib.parse.parse_qs(
            urllib.parse.urlparse(start.headers['Location']).query)['state'][0]
        resp = client.get(f'/ride-with-gps/oauth/callback?code=C&state={state}')
        assert resp.headers['Location'] == '/connections?rwgps_connected=1'
        assert captured['provider'] == 'rwgps'
        assert captured['provider_user_id'] == '55'
