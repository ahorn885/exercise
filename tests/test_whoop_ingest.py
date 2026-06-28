"""Whoop live-ingest tests (#681 (B2b)) — HMAC verify, per-domain mapping, the
load-bearing merge-partial daily_summary (recovery + sleep on one day must
coexist), and the webhook dispatch.

REST is monkeypatched; the daily_summary writer runs against a stateful fake DB
so the merge semantics are actually exercised. Field mapping per matrix §3.
"""

from __future__ import annotations

import base64
import hashlib
import hmac
import json


# ── signature ─────────────────────────────────────────────────────────

class TestVerifySignature:
    def _sign(self, secret, ts, body):
        mac = hmac.new(secret.encode(), ts.encode() + body, hashlib.sha256).digest()
        return base64.b64encode(mac).decode()

    def test_valid_signature_passes(self):
        from routes.whoop_ingest import verify_signature
        body = b'{"user_id":1,"id":"x","type":"sleep.updated"}'
        sig = self._sign('secret', '1700000000000', body)
        assert verify_signature(body, sig, '1700000000000', 'secret') is True

    def test_tampered_body_fails(self):
        from routes.whoop_ingest import verify_signature
        sig = self._sign('secret', '1700000000000', b'orig')
        assert verify_signature(b'TAMPERED', sig, '1700000000000', 'secret') is False

    def test_missing_pieces_fail(self):
        from routes.whoop_ingest import verify_signature
        assert verify_signature(b'x', None, '1', 'secret') is False
        assert verify_signature(b'x', 'sig', '1', None) is False


# ── stateful fake DB for the merge ───────────────────────────────────

class _Cur:
    def __init__(self, row=None, rows=None):
        self._row = row
        self._rows = rows or []

    def fetchone(self):
        return self._row

    def fetchall(self):
        return self._rows


class _MergeDB:
    """Keeps daily_summary rows by date so _merge_daily's read-modify-write is
    real; records workout raw-inserts separately."""

    def __init__(self):
        self.daily = {}      # date -> payload dict
        self.raw = []        # (data_type, external_id)

    def execute(self, sql, params=()):
        s = ' '.join(sql.split())
        # Slice 2.2: _merge_daily now re-materializes canonical wellness, which
        # reads the two wellness homes. No Garmin/other-provider data in this
        # unit context → both come back empty (materialize's no-data path).
        if 'FROM daily_wellness_metrics' in s:
            return _Cur(None)
        if s.startswith('SELECT raw_payload, fetched_at'):  # materialize's _prr read
            return _Cur(rows=[])
        if s.startswith('SELECT raw_payload'):     # _merge_daily read-back (single col)
            day = params[1]
            payload = self.daily.get(day)
            return _Cur({'raw_payload': payload} if payload is not None else None)
        if "data_type, external_id, observed_at, raw_payload" in s and "'daily_summary'" in s:
            day, js = params[1], params[3]
            self.daily[day] = json.loads(js)
            return _Cur(None)
        if 'INSERT INTO provider_raw_record' in s:  # _record_raw (workout)
            self.raw.append((params[1], params[2]))
            return _Cur(None)
        return _Cur(None)

    def commit(self):
        pass


_RECOVERY = {
    'created_at': '2026-06-18T13:00:00.000Z',
    'score': {'hrv_rmssd_milli': 31.8, 'resting_heart_rate': 48,
              'recovery_score': 66, 'spo2_percentage': 97.1},
}
_SLEEP = {
    'end': '2026-06-18T06:30:00.000Z',
    'score': {'stage_summary': {
        'total_slow_wave_sleep_time_milli': 5_400_000,   # 90 min
        'total_rem_sleep_time_milli': 5_400_000,         # 90 min
        'total_light_sleep_time_milli': 14_400_000,      # 240 min
    }, 'respiratory_rate': 14.2},
}


class TestPerDomainAndMerge:
    def test_recovery_maps_hrv_rhr(self, monkeypatch):
        import routes.whoop_ingest as wi
        monkeypatch.setattr(wi, '_fetch', lambda db, u, p: _RECOVERY)
        db = _MergeDB()
        assert wi._ingest_recovery(db, 7, 'cyc1') is True
        row = db.daily['2026-06-18']
        assert row['hrv_rmssd_ms'] == 31.8       # already ms, no conversion
        assert row['resting_hr'] == 48
        assert row['recovery_score'] == 66        # bucket-2 corroboration kept raw

    def test_sleep_total_is_sum_of_stages(self, monkeypatch):
        import routes.whoop_ingest as wi
        monkeypatch.setattr(wi, '_fetch', lambda db, u, p: _SLEEP)
        db = _MergeDB()
        assert wi._ingest_sleep(db, 7, 'slp1') is True
        # Σstages = 90+90+240 = 420 min (asleep convention, not in-bed)
        assert db.daily['2026-06-18']['total_sleep_min'] == 420.0

    def test_recovery_then_sleep_coexist_same_day(self, monkeypatch):
        """The load-bearing case: separate events must not clobber each other."""
        import routes.whoop_ingest as wi
        db = _MergeDB()
        monkeypatch.setattr(wi, '_fetch', lambda db, u, p: _RECOVERY)
        wi._ingest_recovery(db, 7, 'cyc1')
        monkeypatch.setattr(wi, '_fetch', lambda db, u, p: _SLEEP)
        wi._ingest_sleep(db, 7, 'slp1')
        row = db.daily['2026-06-18']
        assert row['hrv_rmssd_ms'] == 31.8       # survived the sleep write
        assert row['resting_hr'] == 48
        assert row['total_sleep_min'] == 420.0   # added by the sleep write
        # Layer-3A reads exactly these three keys, keyed on the date
        assert row['date'] == '2026-06-18'

    def test_workout_recorded_raw(self, monkeypatch):
        import routes.whoop_ingest as wi
        monkeypatch.setattr(wi, '_fetch', lambda db, u, p: {'sport_name': 'running'})
        db = _MergeDB()
        assert wi._ingest_workout(db, 7, 'wk1') is True
        assert ('workout', 'wk1') in db.raw

    def test_process_event_routes_by_type(self, monkeypatch):
        import routes.whoop_ingest as wi
        calls = []
        monkeypatch.setattr(wi, '_ingest_recovery', lambda d, u, i: calls.append(('rec', i)) or True)
        monkeypatch.setattr(wi, '_ingest_sleep', lambda d, u, i: calls.append(('slp', i)) or True)
        wi.process_event(object(), 'recovery.updated', 'c1', 7)
        wi.process_event(object(), 'sleep.updated', 's1', 7)
        assert wi.process_event(object(), 'recovery.deleted', 'c2', 7) is False
        assert calls == [('rec', 'c1'), ('slp', 's1')]


# ── webhook dispatch ──────────────────────────────────────────────────

class _WHDB:
    def __init__(self):
        self.events = []
        self.updates = []

    def execute(self, sql, params=()):
        if 'INSERT INTO webhook_events' in sql:
            self.events.append(params)
            return _Cur({'id': 200})
        if 'UPDATE webhook_events' in sql:
            self.updates.append(params)
        return _Cur(None)

    def commit(self):
        pass


def _post(monkeypatch, event, *, sig_ok=True, user_id=7):
    import routes.whoop as whoop
    import routes.whoop_ingest as wi
    db = _WHDB()
    monkeypatch.setattr(whoop, 'get_db', lambda: db)
    monkeypatch.setattr(whoop.pa, 'get_auth_by_provider_user_id',
                        lambda d, p, pid: {'user_id': user_id} if user_id else None)
    monkeypatch.setattr(wi, 'verify_signature', lambda *a, **k: sig_ok)
    calls = []
    monkeypatch.setattr(wi, 'process_event',
                        lambda d, et, rid, u: calls.append((et, rid, u)))
    from flask import Flask
    app = Flask(__name__)
    app.register_blueprint(whoop.bp)
    resp = app.test_client().post('/whoop/webhook', json=event)
    return resp, db, calls


class TestWebhook:
    def test_updated_event_records_and_dispatches(self, monkeypatch):
        resp, db, calls = _post(monkeypatch, {
            'user_id': 9001, 'id': 'cyc1', 'type': 'recovery.updated'})
        assert resp.status_code == 200
        assert len(db.events) == 1
        assert calls == [('recovery.updated', 'cyc1', 7)]
        assert db.updates  # processed_at set

    def test_bad_signature_records_no_dispatch(self, monkeypatch):
        resp, db, calls = _post(monkeypatch, {
            'user_id': 9001, 'id': 'cyc1', 'type': 'recovery.updated'}, sig_ok=False)
        assert resp.status_code == 200
        assert len(db.events) == 1  # audit row still written
        assert calls == []

    def test_unmapped_user_records_no_dispatch(self, monkeypatch):
        resp, db, calls = _post(monkeypatch, {
            'user_id': 1, 'id': 'cyc1', 'type': 'recovery.updated'}, user_id=None)
        assert resp.status_code == 200
        assert calls == []
