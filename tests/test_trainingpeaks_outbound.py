"""TrainingPeaks outbound connector tests (#681 Wave 3b Slice 2).

OAuth connect + the structured-workout PUSH (idempotent via provider_outbound_ref).
Network + provider_auth are monkeypatched — TP partner access is gated, so there's
no live target (verify-owed). Serializer correctness is covered in
test_outbound_workout.
"""

from __future__ import annotations

import os

import pytest
from flask import Flask

import routes.trainingpeaks as tp


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
    def __init__(self, one=None):
        self._one = one

    def fetchone(self):
        return self._one


class _DB:
    def __init__(self, existing=None):
        self.existing = existing
        self.writes = []
        self.commits = 0

    def execute(self, sql, params=()):
        if sql.strip().upper().startswith('SELECT'):
            return _Cur(self.existing)
        self.writes.append((sql, params))
        return _Cur()

    def commit(self):
        self.commits += 1


def _app():
    root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    app = Flask(__name__, template_folder=os.path.join(root, 'templates'))
    app.config['TESTING'] = True
    app.config['SECRET_KEY'] = 'test'
    app.register_blueprint(tp.bp)

    @app.route('/login', endpoint='auth.login')
    def _login():  # pragma: no cover
        return 'login'

    return app


def _bike_session():
    return {
        'session_id': 's1', 'kind': 'cardio', 'date': '2026-06-20',
        'discipline_id': 'D-006', 'discipline_name': 'Road Cycling',
        'cardio_blocks': [
            {'block_kind': 'warmup', 'duration_min': 10, 'intensity_zone': 'Z1',
             'instructions': 'spin'},
            {'block_kind': 'main_set', 'duration_min': 20, 'intensity_zone': 'Z3',
             'instructions': 'tempo'},
        ],
    }


# ── OAuth ──────────────────────────────────────────────────────────────

class TestOAuth:
    def test_start_redirects_with_scope_and_state(self, monkeypatch):
        monkeypatch.setattr(tp, 'current_user_id', lambda: 7)
        monkeypatch.setenv('TP_CLIENT_ID', 'cid')
        c = _app().test_client()
        r = c.get('/trainingpeaks/oauth/start')
        assert r.status_code == 302
        assert 'workouts%3Aplan' in r.location or 'workouts:plan' in r.location
        assert 'state=' in r.location

    def test_callback_persists_with_fetched_athlete_id(self, monkeypatch):
        monkeypatch.setattr(tp, 'current_user_id', lambda: 7)
        monkeypatch.setattr(tp, 'get_db', lambda: _DB())
        monkeypatch.setenv('TP_CLIENT_ID', 'cid')
        monkeypatch.setenv('TP_CLIENT_SECRET', 'secret')
        monkeypatch.setattr(tp.requests, 'post',
                            lambda *a, **k: _FakeResp({'access_token': 'A',
                                                       'refresh_token': 'R',
                                                       'expires_in': 3600}))
        monkeypatch.setattr(tp.requests, 'get',
                            lambda *a, **k: _FakeResp({'Id': 4242}))
        captured = {}
        monkeypatch.setattr(tp.pa, 'upsert_auth',
                            lambda db, **kw: captured.update(kw))
        monkeypatch.setattr(tp.pa, 'record_oauth_scope_ack', lambda *a, **k: None)
        c = _app().test_client()
        with c.session_transaction() as s:
            s['tp_oauth_state'] = 'st8'
            s['tp_oauth_return_to'] = '/'
        r = c.get('/trainingpeaks/oauth/callback?state=st8&code=xyz')
        assert r.status_code == 302
        assert 'trainingpeaks_connected=1' in r.location
        assert captured['provider_user_id'] == '4242'

    def test_callback_state_mismatch_400(self, monkeypatch):
        monkeypatch.setattr(tp, 'current_user_id', lambda: 7)
        c = _app().test_client()
        with c.session_transaction() as s:
            s['tp_oauth_state'] = 'expected'
        r = c.get('/trainingpeaks/oauth/callback?state=WRONG&code=xyz')
        assert r.status_code == 400


# ── Push ───────────────────────────────────────────────────────────────

class TestPush:
    def _setup(self, monkeypatch, db, session=None, token='T', auth_active=True):
        monkeypatch.setattr(tp, 'current_user_id', lambda: 7)
        monkeypatch.setattr(tp, 'get_db', lambda: db)
        monkeypatch.setattr(tp, 'load_plan_session_payload',
                            lambda *a, **k: session if session is not None else _bike_session())
        auth = {'status': tp.pa.STATUS_ACTIVE, 'provider_user_id': '4242'} if auth_active else None
        monkeypatch.setattr(tp.pa, 'get_auth', lambda *a, **k: auth)
        monkeypatch.setattr(tp.pa, 'get_fresh_access_token', lambda *a, **k: token)

    def test_new_session_pushes_and_records(self, monkeypatch):
        db = _DB(existing=None)
        self._setup(monkeypatch, db)
        posted = {}
        monkeypatch.setattr(tp.requests, 'post',
                            lambda url, **k: posted.update(k) or _FakeResp({'Id': 'w99'}))
        r = _app().test_client().post('/trainingpeaks/push/12/2026-06-20/0')
        assert r.status_code == 200
        assert r.get_json()['status'] == 'pushed'
        assert r.get_json()['external_id'] == 'w99'
        # recorded an INSERT into provider_outbound_ref
        assert any('INSERT INTO provider_outbound_ref' in w[0] for w in db.writes)
        # the pushed body carried the TP Structure + WorkoutType
        assert posted['json']['WorkoutType'] == 'bike'
        assert posted['json']['IntensityTargetType'] == 'PercentOfFtp'

    def test_unchanged_payload_is_noop(self, monkeypatch):
        # first push to learn the stored hash
        db1 = _DB(existing=None)
        self._setup(monkeypatch, db1)
        monkeypatch.setattr(tp.requests, 'post', lambda *a, **k: _FakeResp({'Id': 'w99'}))
        _app().test_client().post('/trainingpeaks/push/12/2026-06-20/0')
        insert = [w for w in db1.writes if 'INSERT' in w[0]][0]
        stored_hash = insert[1][4]  # pushed_payload_hash position

        # second push with the same payload already recorded → no-op, no POST
        db2 = _DB(existing={'id': 1, 'pushed_payload_hash': stored_hash, 'external_id': 'w99'})
        self._setup(monkeypatch, db2)
        called = {'post': False}
        monkeypatch.setattr(tp.requests, 'post',
                            lambda *a, **k: called.__setitem__('post', True) or _FakeResp({'Id': 'x'}))
        r = _app().test_client().post('/trainingpeaks/push/12/2026-06-20/0')
        assert r.get_json()['status'] == 'unchanged'
        assert called['post'] is False
        assert db2.writes == []

    def test_changed_payload_updates(self, monkeypatch):
        db = _DB(existing={'id': 5, 'pushed_payload_hash': 'OLD', 'external_id': 'w1'})
        self._setup(monkeypatch, db)
        monkeypatch.setattr(tp.requests, 'post', lambda *a, **k: _FakeResp({'Id': 'w2'}))
        r = _app().test_client().post('/trainingpeaks/push/12/2026-06-20/0')
        assert r.get_json()['status'] == 'updated'
        assert any('UPDATE provider_outbound_ref' in w[0] for w in db.writes)

    def test_non_cardio_400(self, monkeypatch):
        db = _DB()
        self._setup(monkeypatch, db, session={'kind': 'strength', 'session_id': 'x'})
        r = _app().test_client().post('/trainingpeaks/push/12/2026-06-20/0')
        assert r.status_code == 400

    def test_not_connected_409(self, monkeypatch):
        db = _DB()
        self._setup(monkeypatch, db, auth_active=False)
        r = _app().test_client().post('/trainingpeaks/push/12/2026-06-20/0')
        assert r.status_code == 409

    def test_missing_session_404(self, monkeypatch):
        db = _DB()
        monkeypatch.setattr(tp, 'current_user_id', lambda: 7)
        monkeypatch.setattr(tp, 'get_db', lambda: db)
        monkeypatch.setattr(tp, 'load_plan_session_payload', lambda *a, **k: None)
        r = _app().test_client().post('/trainingpeaks/push/12/2026-06-20/0')
        assert r.status_code == 404
