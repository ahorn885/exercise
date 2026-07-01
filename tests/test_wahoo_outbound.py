"""Wahoo outbound push tests (#1094 — matrix §10.2 `plan.json`).

Unlike the still-gated TP Slice-2 connector, Wahoo OAuth is already live, so
this route is UI-driven: every outcome flashes + redirects back to the plan
view rather than returning bare JSON. Network + provider_auth + DB are
monkeypatched. Serializer correctness (`to_wahoo_plan_json`) is covered in
test_outbound_workout.py.
"""

from __future__ import annotations

import os
from datetime import date

from flask import Flask

import routes.wahoo as wahoo


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
    app.register_blueprint(wahoo.bp)

    @app.route('/plans/v2/<int:plan_version_id>', endpoint='plan_create.view_plan')
    def _view_plan(plan_version_id):  # pragma: no cover
        return f'plan {plan_version_id}'

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


_TODAY = date(2026, 6, 20)
_IN_WINDOW_DATE = '2026-06-22'
_OUT_OF_WINDOW_DATE = '2026-07-10'


class TestPush:
    def _setup(self, monkeypatch, db, session=None, token='T',
               scopes=wahoo._WAHOO_SCOPES, auth_active=True):
        monkeypatch.setattr(wahoo, 'current_user_id', lambda: 7)
        monkeypatch.setattr(wahoo, 'get_db', lambda: db)
        monkeypatch.setattr(wahoo, '_today', lambda: _TODAY)
        monkeypatch.setattr(
            wahoo, 'load_plan_session_payload',
            lambda *a, **k: session if session is not None else _bike_session())
        auth = (
            {'status': wahoo.pa.STATUS_ACTIVE, 'scopes': scopes}
            if auth_active else None
        )
        monkeypatch.setattr(wahoo.pa, 'get_auth', lambda *a, **k: auth)
        monkeypatch.setattr(wahoo.pa, 'get_fresh_access_token', lambda *a, **k: token)

    def test_new_session_pushes_and_records(self, monkeypatch):
        db = _DB(existing=None)
        self._setup(monkeypatch, db)
        posted = []
        monkeypatch.setattr(
            wahoo.requests, 'post',
            lambda url, **k: posted.append((url, k)) or _FakeResp({'id': 'p1'}))
        r = _app().test_client().post(
            f'/wahoo/push/12/{_IN_WINDOW_DATE}/0', follow_redirects=False)
        assert r.status_code == 302
        assert r.location.endswith('/plans/v2/12')
        assert any('INSERT INTO provider_outbound_ref' in w[0] for w in db.writes)
        # two-step: plans then workouts
        assert posted[0][0] == wahoo._WAHOO_PLANS_URL
        assert posted[1][0] == wahoo._WAHOO_WORKOUTS_URL
        assert posted[1][1]['json']['workout']['plan_id'] == 'p1'
        assert posted[1][1]['json']['workout']['workout_type_family_id'] == 0  # cycling

    def test_unchanged_payload_is_noop_no_post(self, monkeypatch):
        db1 = _DB(existing=None)
        self._setup(monkeypatch, db1)
        monkeypatch.setattr(wahoo.requests, 'post',
                            lambda *a, **k: _FakeResp({'id': 'p1'}))
        _app().test_client().post(f'/wahoo/push/12/{_IN_WINDOW_DATE}/0')
        insert = [w for w in db1.writes if 'INSERT' in w[0]][0]
        stored_hash = insert[1][4]  # pushed_payload_hash position

        db2 = _DB(existing={'id': 1, 'pushed_payload_hash': stored_hash,
                            'external_id': 'w1'})
        self._setup(monkeypatch, db2)
        called = {'post': False}
        monkeypatch.setattr(
            wahoo.requests, 'post',
            lambda *a, **k: called.__setitem__('post', True) or _FakeResp({}))
        r = _app().test_client().post(f'/wahoo/push/12/{_IN_WINDOW_DATE}/0')
        assert r.status_code == 302
        assert called['post'] is False
        assert db2.writes == []

    def test_changed_payload_updates(self, monkeypatch):
        db = _DB(existing={'id': 5, 'pushed_payload_hash': 'OLD', 'external_id': 'w1'})
        self._setup(monkeypatch, db)
        monkeypatch.setattr(wahoo.requests, 'post',
                            lambda *a, **k: _FakeResp({'id': 'p2'}))
        _app().test_client().post(f'/wahoo/push/12/{_IN_WINDOW_DATE}/0')
        assert any('UPDATE provider_outbound_ref' in w[0] for w in db.writes)

    def test_missing_session_404(self, monkeypatch):
        db = _DB()
        monkeypatch.setattr(wahoo, 'current_user_id', lambda: 7)
        monkeypatch.setattr(wahoo, 'get_db', lambda: db)
        monkeypatch.setattr(wahoo, 'load_plan_session_payload', lambda *a, **k: None)
        r = _app().test_client().post(f'/wahoo/push/12/{_IN_WINDOW_DATE}/0')
        assert r.status_code == 404

    def test_non_cardio_redirects_with_flash(self, monkeypatch):
        db = _DB()
        self._setup(monkeypatch, db, session={'kind': 'strength', 'session_id': 'x'})
        r = _app().test_client().post(
            f'/wahoo/push/12/{_IN_WINDOW_DATE}/0', follow_redirects=False)
        assert r.status_code == 302
        assert db.writes == []

    def test_not_connected_redirects(self, monkeypatch):
        db = _DB()
        self._setup(monkeypatch, db, auth_active=False)
        r = _app().test_client().post(
            f'/wahoo/push/12/{_IN_WINDOW_DATE}/0', follow_redirects=False)
        assert r.status_code == 302
        assert db.writes == []

    def test_missing_plans_write_scope_redirects_without_push(self, monkeypatch):
        db = _DB()
        # connected, but with a pre-scope-bump token (no plans_write)
        self._setup(monkeypatch, db,
                    scopes='user_read workouts_read power_zones_read offline_data')
        called = {'post': False}
        monkeypatch.setattr(
            wahoo.requests, 'post',
            lambda *a, **k: called.__setitem__('post', True) or _FakeResp({}))
        r = _app().test_client().post(
            f'/wahoo/push/12/{_IN_WINDOW_DATE}/0', follow_redirects=False)
        assert r.status_code == 302
        assert called['post'] is False

    def test_outside_sync_window_redirects_without_push(self, monkeypatch):
        db = _DB()
        self._setup(monkeypatch, db)
        called = {'post': False}
        monkeypatch.setattr(
            wahoo.requests, 'post',
            lambda *a, **k: called.__setitem__('post', True) or _FakeResp({}))
        r = _app().test_client().post(
            f'/wahoo/push/12/{_OUT_OF_WINDOW_DATE}/0', follow_redirects=False)
        assert r.status_code == 302
        assert called['post'] is False

    def test_today_is_in_window(self, monkeypatch):
        db = _DB(existing=None)
        self._setup(monkeypatch, db)
        monkeypatch.setattr(wahoo.requests, 'post',
                            lambda *a, **k: _FakeResp({'id': 'p1'}))
        r = _app().test_client().post(
            f'/wahoo/push/12/{_TODAY.isoformat()}/0', follow_redirects=False)
        assert r.status_code == 302
        assert any('INSERT INTO provider_outbound_ref' in w[0] for w in db.writes)

    def test_push_failure_records_error_status(self, monkeypatch):
        db = _DB(existing=None)
        self._setup(monkeypatch, db)

        def _boom(*a, **k):
            import requests
            raise requests.RequestException('network down')

        monkeypatch.setattr(wahoo.requests, 'post', _boom)
        r = _app().test_client().post(
            f'/wahoo/push/12/{_IN_WINDOW_DATE}/0', follow_redirects=False)
        assert r.status_code == 302
        insert = [w for w in db.writes if 'INSERT' in w[0]][0]
        assert insert[1][-1] == wahoo.pa.STATUS_ERROR
