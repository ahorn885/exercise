"""Strava live-ingest tests (#681 (B)) — token refresh helper, activity
normalization, the fetch→write path, and the webhook dispatch.

Network + the shared cardio writer are monkeypatched; assertions cover the
matrix §2.1 unit conversions, the #681 discipline resolution, idempotent dedup,
and the webhook recording the event + dispatching only on activity create/update.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest


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


# ── normalize_strava_activity (matrix §2.1 / §2.2) ────────────────────

class TestNormalize:
    def test_trail_run_maps_to_fine_discipline_and_converts_units(self):
        from routes.strava_ingest import normalize_strava_activity
        d = normalize_strava_activity({
            'id': 555, 'name': 'Morning trail run', 'sport_type': 'TrailRun',
            'distance': 16093.4, 'moving_time': 3600, 'elapsed_time': 3720,
            'total_elevation_gain': 304.8, 'average_heartrate': 152.4,
            'max_heartrate': 178, 'calories': 924,
            'start_date_local': '2026-06-18T07:30:00Z',
        })
        assert d['discipline_id'] == 'D-001'           # TrailRun → fine D-id
        assert d['activity'] == 'running'              # coarse collapse
        assert d['date'] == '2026-06-18'
        assert round(d['distance_mi'], 2) == 10.0      # 16093.4 m → mi
        assert round(d['duration_min'], 0) == 62       # elapsed 3720 s → min
        assert round(d['moving_time_min'], 0) == 60
        assert round(d['elev_gain_ft'], 0) == 1000     # 304.8 m → ft
        assert d['avg_hr'] == 152 and d['max_hr'] == 178
        assert d['_provider_raw']['provider'] == 'strava'
        assert d['_provider_raw']['bucket'] == 1
        assert d['_provider_raw']['payload']['sport_type'] == 'TrailRun'

    def test_virtual_ride_flags_indoor_machine(self):
        from routes.strava_ingest import normalize_strava_activity
        d = normalize_strava_activity({
            'id': 1, 'sport_type': 'VirtualRide', 'trainer': True,
            'distance': 30000, 'average_watts': 210,
        })
        assert d['discipline_id'] == 'D-006'
        assert d['avg_power'] == 210
        assert d['_provider_raw']['payload']['indoor_machine'] == 'Cycling trainer'

    def test_unmapped_sport_is_bucket3_no_discipline(self):
        from routes.strava_ingest import normalize_strava_activity
        d = normalize_strava_activity({'id': 2, 'sport_type': 'Pickleball'})
        assert d['discipline_id'] is None
        assert d['_provider_raw']['bucket'] == 3
        assert d['activity'] == 'pickleball'

    def test_started_at_uses_utc_start_date_not_local(self):
        # #196 P3 Slice 1 — the cross-source fingerprint instant must be UTC, so
        # started_at carries start_date (UTC), NOT start_date_local (local wall-
        # clock). observed_at keeps its existing local-preferring contract.
        from routes.strava_ingest import normalize_strava_activity
        d = normalize_strava_activity({
            'id': 7, 'sport_type': 'Ride',
            'start_date': '2026-06-22T06:28:56Z',
            'start_date_local': '2026-06-21T22:28:56Z',
        })
        assert d['started_at'] == '2026-06-22T06:28:56Z'
        assert d['_provider_raw']['observed_at'] == '2026-06-21T22:28:56Z'


# ── fetch_and_ingest_activity ─────────────────────────────────────────

class _Cur:
    def __init__(self, row=None):
        self._row = row

    def fetchone(self):
        return self._row


class _DB:
    def __init__(self, existing=False):
        self._existing = existing
        self.inserted = []

    def execute(self, sql, params=()):
        if 'SELECT id FROM cardio_log' in sql:
            return _Cur({'id': 9} if self._existing else None)
        return _Cur(None)

    def commit(self):
        pass


class TestFetchAndIngest:
    def test_skips_when_already_imported(self, monkeypatch):
        import routes.strava_ingest as si
        monkeypatch.setattr(si.pa, 'get_fresh_access_token', lambda *a, **k: 'T')
        assert si.fetch_and_ingest_activity(_DB(existing=True), 7, 555) is False

    def test_skips_when_no_token(self, monkeypatch):
        import routes.strava_ingest as si
        monkeypatch.setattr(si.pa, 'get_fresh_access_token', lambda *a, **k: None)
        assert si.fetch_and_ingest_activity(_DB(), 7, 555) is False

    def test_fetches_and_writes_via_shared_writer(self, monkeypatch):
        import routes.strava_ingest as si
        import routes.garmin as garmin
        monkeypatch.setattr(si.pa, 'get_fresh_access_token', lambda *a, **k: 'T')
        monkeypatch.setattr(si.requests, 'get', lambda *a, **k: _FakeResp({
            'id': 555, 'sport_type': 'Run', 'distance': 5000, 'moving_time': 1500,
            'elapsed_time': 1500, 'start_date_local': '2026-06-18T07:00:00Z',
        }))
        captured = {}
        monkeypatch.setattr(
            garmin, '_bulk_insert_cardio',
            lambda db, data, uid, gid, source='garmin', **k:
                captured.update(data=data, uid=uid, gid=gid, source=source) or 1)
        assert si.fetch_and_ingest_activity(_DB(), 7, 555) is True
        assert captured['source'] == 'strava'
        assert captured['gid'] == '555'
        assert captured['data']['discipline_id'] == 'D-002'


# ── provider_auth token refresh ───────────────────────────────────────

class TestTokenRefresh:
    def _row(self, **kw):
        base = {'id': 1, 'status': 'active', 'access_token': 'OLD',
                'refresh_token': 'RT', 'token_expires_at': None}
        base.update(kw)
        return base

    def test_returns_stored_token_when_not_expiring(self, monkeypatch):
        from routes import provider_auth as pa
        future = datetime.now(timezone.utc) + timedelta(hours=3)
        monkeypatch.setattr(pa, 'get_auth',
                            lambda db, u, p: self._row(token_expires_at=future))
        called = {'refresh': False}
        monkeypatch.setattr(pa, 'refresh_access_token',
                            lambda *a, **k: called.update(refresh=True) or 'NEW')
        tok = pa.get_fresh_access_token(object(), 7, 'strava',
                                        token_url='u', client_id='c', client_secret='s')
        assert tok == 'OLD' and called['refresh'] is False

    def test_refreshes_when_expiring(self, monkeypatch):
        from routes import provider_auth as pa
        past = datetime.now(timezone.utc) - timedelta(minutes=1)
        monkeypatch.setattr(pa, 'get_auth',
                            lambda db, u, p: self._row(token_expires_at=past))
        monkeypatch.setattr(pa, 'refresh_access_token', lambda *a, **k: 'NEW')
        tok = pa.get_fresh_access_token(object(), 7, 'strava',
                                        token_url='u', client_id='c', client_secret='s')
        assert tok == 'NEW'

    def test_refresh_persists_rotated_tokens(self, monkeypatch):
        from routes import provider_auth as pa
        monkeypatch.setattr(pa, 'get_auth', lambda db, u, p: self._row())
        monkeypatch.setattr(pa.requests, 'post', lambda *a, **k: _FakeResp({
            'access_token': 'NEW', 'refresh_token': 'RT2', 'expires_at': 1_900_000_000,
        }))
        saved = {}
        monkeypatch.setattr(pa, 'upsert_auth',
                            lambda db, u, p, **kw: saved.update(kw) or 1)
        tok = pa.refresh_access_token(object(), 7, 'strava',
                                      token_url='u', client_id='c', client_secret='s')
        assert tok == 'NEW'
        assert saved['access_token'] == 'NEW'
        assert saved['refresh_token'] == 'RT2'
        assert saved['token_expires_at'] is not None

    def test_refresh_marks_error_on_failure(self, monkeypatch):
        from routes import provider_auth as pa
        monkeypatch.setattr(pa, 'get_auth', lambda db, u, p: self._row())
        monkeypatch.setattr(pa.requests, 'post', lambda *a, **k: _FakeResp({}, status=400))
        statuses = []
        monkeypatch.setattr(pa, 'set_status', lambda db, aid, st: statuses.append(st))
        assert pa.refresh_access_token(object(), 7, 'strava',
                                       token_url='u', client_id='c', client_secret='s') is None
        assert statuses == [pa.STATUS_ERROR]


# ── webhook dispatch ──────────────────────────────────────────────────

class _WHDB:
    def __init__(self, user_id=7):
        self._user_id = user_id
        self.events = []
        self.updates = []

    def execute(self, sql, params=()):
        if 'INSERT INTO webhook_events' in sql:
            self.events.append(params)
            return _Cur({'id': 100})
        if 'UPDATE webhook_events' in sql:
            self.updates.append(params)
        return _Cur(None)

    def commit(self):
        pass


def _webhook_post(monkeypatch, event, user_id=7, ingested=None):
    import routes.strava as strava
    db = _WHDB()
    monkeypatch.setattr(strava, 'get_db', lambda: db)
    monkeypatch.setattr(strava.pa, 'get_auth_by_provider_user_id',
                        lambda d, p, pid: {'user_id': user_id} if user_id else None)
    import routes.strava_ingest as si
    calls = []
    monkeypatch.setattr(si, 'fetch_and_ingest_activity',
                        lambda d, u, oid: calls.append((u, oid)))
    monkeypatch.delenv('STRAVA_SUBSCRIPTION_ID', raising=False)

    import os as _os
    root = _os.path.dirname(_os.path.dirname(_os.path.abspath(__file__)))
    from flask import Flask
    app = Flask(__name__)
    app.register_blueprint(strava.bp)
    client = app.test_client()
    resp = client.post('/strava/webhook', json=event)
    return resp, db, calls


class TestWebhookDispatch:
    def test_activity_create_records_and_ingests(self, monkeypatch):
        resp, db, calls = _webhook_post(monkeypatch, {
            'object_type': 'activity', 'object_id': 555, 'aspect_type': 'create',
            'owner_id': 42,
        })
        assert resp.status_code == 200
        assert len(db.events) == 1
        assert calls == [(7, 555)]
        assert db.updates  # processed_at set

    def test_athlete_event_records_but_does_not_ingest(self, monkeypatch):
        resp, db, calls = _webhook_post(monkeypatch, {
            'object_type': 'athlete', 'object_id': 42, 'aspect_type': 'update',
            'owner_id': 42,
        })
        assert resp.status_code == 200
        assert len(db.events) == 1
        assert calls == []

    def test_unmapped_owner_records_no_ingest(self, monkeypatch):
        resp, db, calls = _webhook_post(monkeypatch, {
            'object_type': 'activity', 'object_id': 9, 'aspect_type': 'create',
            'owner_id': 999,
        }, user_id=None)
        assert resp.status_code == 200
        assert len(db.events) == 1  # recorded for later resolution
        assert calls == []
