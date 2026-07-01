"""Wahoo live-wiring tests (#681 (B)) — OAuth connect, workout_summary
normalization (matrix §10.2), the synchronous-from-payload ingest, and the
webhook dispatch. Network + the shared cardio writer are monkeypatched.
"""

from __future__ import annotations

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


# ── normalize ─────────────────────────────────────────────────────────

class TestNormalize:
    def test_workout_type_id_resolves_and_converts(self):
        from routes.wahoo import normalize_wahoo_summary
        d = normalize_wahoo_summary({
            'id': 88, 'name': 'Gravel ride', 'workout_type_id': 13,   # MOUNTAIN
            'distance_accum': 32186.8, 'duration_total_accum': 5400,
            'duration_active_accum': 5200, 'ascent_accum': 609.6,
            'heart_rate_avg': 141.6, 'power_avg': 198, 'cadence_avg': 84,
            'work_accum': 1_673_600, 'starts': '2026-06-17T15:00:00Z',
        })
        assert d['discipline_id'] == 'D-008'        # workout_type_id 13 → MTB
        assert d['activity'] == 'cycling'
        assert d['date'] == '2026-06-17'
        assert round(d['distance_mi'], 1) == 20.0
        assert round(d['duration_min'], 0) == 90
        assert round(d['elev_gain_ft'], 0) == 2000
        assert d['avg_hr'] == 142 and d['avg_power'] == 198
        assert d['calories'] == 400               # 1,673,600 J ÷ 4184 → 400 kcal
        assert d['_provider_raw']['bucket'] == 1

    def test_calories_accum_fallback_when_no_work(self):
        from routes.wahoo import normalize_wahoo_summary
        d = normalize_wahoo_summary({'id': 1, 'workout_type_id': 1,
                                     'calories_accum': 512})
        assert d['calories'] == 512

    def test_rowing_type_is_bucket3(self):
        from routes.wahoo import normalize_wahoo_summary
        d = normalize_wahoo_summary({'id': 2, 'workout_type_id': 39})  # ROWING
        assert d['discipline_id'] is None
        assert d['_provider_raw']['bucket'] == 3

    def test_live_nested_workout_shape(self):
        """The live webhook nests type/name/start under a `workout` sub-object
        (verified against a 2026-06-22 push); the summary carries only the
        accumulator metrics. Reading them top-level mislabels the ride as
        `other`/unnamed — this is the regression guard for that fix."""
        from routes.wahoo import normalize_wahoo_summary
        d = normalize_wahoo_summary({
            'id': 417773586, 'started_at': '2026-06-22T06:28:56.000Z',
            'created_at': '2026-06-22T06:29:10.000Z',  # upload time — must NOT win
            'distance_accum': '0.0', 'duration_total_accum': '4.0',
            'duration_active_accum': '4.0',
            'workout': {
                'id': 468665132, 'name': 'Indoor Cycling test',
                'workout_type_id': 12,  # BIKING_INDOOR → D-006
                'starts': '2026-06-22T06:28:56.000Z',
            },
        })
        assert d['activity'] == 'cycling'
        assert d['discipline_id'] == 'D-006'
        assert d['activity_name'] == 'Indoor Cycling test'
        assert d['date'] == '2026-06-22'
        assert d['_provider_raw']['payload']['workout_type_id'] == 12
        assert d['_provider_raw']['payload']['wahoo_workout_id'] == 417773586


# ── ingest ────────────────────────────────────────────────────────────

class _DB:
    def __init__(self, existing=False):
        self._existing = existing

    def execute(self, sql, params=()):
        if 'SELECT id FROM cardio_log' in sql:
            return _Cur({'id': 5} if self._existing else None)
        return _Cur(None)

    def commit(self):
        pass


class TestIngest:
    def test_skips_when_already_imported(self):
        from routes.wahoo import _ingest_workout_summary
        assert _ingest_workout_summary(_DB(existing=True), 7, '88', {'id': 88}) is False

    def test_writes_via_shared_writer(self, monkeypatch):
        import routes.wahoo as wahoo
        import routes.garmin as garmin
        captured = {}
        monkeypatch.setattr(
            garmin, '_bulk_insert_cardio',
            lambda db, data, uid, gid, source='garmin', **k:
                captured.update(data=data, gid=gid, source=source) or 1)
        ok = wahoo._ingest_workout_summary(_DB(), 7, '88', {
            'id': 88, 'workout_type_id': 1, 'distance_accum': 5000,
            'duration_total_accum': 1500})
        assert ok is True
        assert captured['source'] == 'wahoo'
        assert captured['gid'] == '88'
        assert captured['data']['discipline_id'] == 'D-002'


# ── FIT-stream enrichment (#1093) ──────────────────────────────────────

class TestFitStreamUrl:
    def test_top_level_file_url(self):
        from routes.wahoo import _wahoo_fit_url
        assert _wahoo_fit_url({'file': {'url': 'https://x/a.fit'}}) == 'https://x/a.fit'

    def test_nested_under_workout(self):
        from routes.wahoo import _wahoo_fit_url
        assert _wahoo_fit_url(
            {'workout': {'file': {'url': 'https://x/b.fit'}}}
        ) == 'https://x/b.fit'

    def test_absent_is_none(self):
        from routes.wahoo import _wahoo_fit_url
        assert _wahoo_fit_url({'id': 88}) is None


class TestMergeFitStreamFields:
    def test_fills_fields_the_summary_is_missing(self, monkeypatch):
        import routes.wahoo as wahoo
        monkeypatch.setattr(
            'garmin_fit_parser.parse_fit',
            lambda raw: {'log_type': 'cardio', 'data': {
                'max_hr': 178, 'norm_power': 210, 'gct_ms': 245,
            }})
        data = {'avg_hr': 150, 'max_hr': None, 'norm_power': None, 'gct_ms': None}
        added = wahoo._merge_fit_stream_fields(data, b'fake-fit-bytes')
        assert added is True
        assert data['max_hr'] == 178
        assert data['norm_power'] == 210
        assert data['gct_ms'] == 245
        assert data['avg_hr'] == 150  # untouched — not a FIT-stream field

    def test_never_overrides_a_value_the_summary_already_has(self, monkeypatch):
        import routes.wahoo as wahoo
        monkeypatch.setattr(
            'garmin_fit_parser.parse_fit',
            lambda raw: {'log_type': 'cardio', 'data': {'max_hr': 999}})
        data = {'max_hr': 178}
        wahoo._merge_fit_stream_fields(data, b'fake-fit-bytes')
        assert data['max_hr'] == 178

    def test_non_cardio_parse_is_a_no_op(self, monkeypatch):
        import routes.wahoo as wahoo
        monkeypatch.setattr(
            'garmin_fit_parser.parse_fit',
            lambda raw: {'log_type': 'strength', 'data': []})
        data = {'max_hr': None}
        assert wahoo._merge_fit_stream_fields(data, b'fake-fit-bytes') is False
        assert data['max_hr'] is None

    def test_parse_failure_is_swallowed(self, monkeypatch):
        import routes.wahoo as wahoo
        monkeypatch.setattr(
            'garmin_fit_parser.parse_fit',
            lambda raw: (_ for _ in ()).throw(ValueError('no session message')))
        data = {'max_hr': None}
        app = _make_app(wahoo.bp)
        with app.app_context():
            assert wahoo._merge_fit_stream_fields(data, b'garbage') is False
        assert data['max_hr'] is None


class TestIngestWithFitStream:
    def test_full_path_fetches_and_merges_stream_fields(self, monkeypatch):
        import routes.wahoo as wahoo
        import routes.garmin as garmin
        captured = {}
        monkeypatch.setattr(
            garmin, '_bulk_insert_cardio',
            lambda db, data, uid, gid, source='garmin', **k:
                captured.update(data=data, gid=gid, source=source) or 1)
        monkeypatch.setattr(wahoo.pa, 'get_fresh_access_token', lambda *a, **k: 'AT')
        monkeypatch.setattr(
            wahoo.requests, 'get',
            lambda url, headers=None, timeout=None: _FakeFitResp(b'fake-fit-bytes'))
        monkeypatch.setattr(
            'garmin_fit_parser.parse_fit',
            lambda raw: {'log_type': 'cardio', 'data': {'max_hr': 182, 'norm_power': 215}})
        app = _make_app(wahoo.bp)
        with app.app_context():
            ok = wahoo._ingest_workout_summary(_DB(), 7, '88', {
                'id': 88, 'workout_type_id': 1, 'distance_accum': 5000,
                'duration_total_accum': 1500,
                'file': {'url': 'https://api.wahooligan.com/files/88.fit'},
            })
        assert ok is True
        assert captured['data']['max_hr'] == 182
        assert captured['data']['norm_power'] == 215
        # Discipline resolution stays Wahoo's own matrix mapping, untouched by
        # the FIT enrichment.
        assert captured['data']['discipline_id'] == 'D-002'

    def test_no_token_skips_fetch_without_error(self, monkeypatch):
        import routes.wahoo as wahoo
        import routes.garmin as garmin
        captured = {}
        monkeypatch.setattr(
            garmin, '_bulk_insert_cardio',
            lambda db, data, uid, gid, source='garmin', **k:
                captured.update(data=data, gid=gid, source=source) or 1)
        monkeypatch.setattr(wahoo.pa, 'get_fresh_access_token', lambda *a, **k: None)
        ok = wahoo._ingest_workout_summary(_DB(), 7, '88', {
            'id': 88, 'workout_type_id': 1,
            'file': {'url': 'https://api.wahooligan.com/files/88.fit'},
        })
        assert ok is True
        assert captured['data'].get('max_hr') is None

    def test_no_file_url_never_attempts_a_fetch(self, monkeypatch):
        import routes.wahoo as wahoo
        import routes.garmin as garmin
        monkeypatch.setattr(garmin, '_bulk_insert_cardio', lambda *a, **k: 1)

        def _boom(*a, **k):
            raise AssertionError('should not fetch when there is no file url')
        monkeypatch.setattr(wahoo.pa, 'get_fresh_access_token', _boom)
        ok = wahoo._ingest_workout_summary(_DB(), 7, '88', {
            'id': 88, 'workout_type_id': 1})
        assert ok is True


class _FakeFitResp:
    def __init__(self, content, status=200):
        self.content = content
        self.status_code = status

    def raise_for_status(self):
        if self.status_code >= 400:
            import requests
            raise requests.RequestException(f'status {self.status_code}')


# ── OAuth connect ─────────────────────────────────────────────────────

class TestOAuth:
    def test_start_redirects_with_scopes(self, monkeypatch):
        import routes.wahoo as wahoo
        monkeypatch.setattr(wahoo, 'current_user_id', lambda: 7)
        monkeypatch.setenv('WAHOO_CLIENT_ID', 'cid')
        resp = _make_app(wahoo.bp).test_client().get('/wahoo/oauth/start')
        assert resp.status_code == 302
        q = urllib.parse.parse_qs(urllib.parse.urlparse(resp.headers['Location']).query)
        assert q['client_id'] == ['cid']
        assert 'offline_data' in q['scope'][0].split()

    def test_callback_persists_with_fetched_user_id(self, monkeypatch):
        import routes.wahoo as wahoo
        captured = {}
        monkeypatch.setattr(wahoo, 'current_user_id', lambda: 7)
        monkeypatch.setattr(wahoo, 'get_db', lambda: object())
        monkeypatch.setenv('WAHOO_CLIENT_ID', 'cid')
        monkeypatch.setenv('WAHOO_CLIENT_SECRET', 'secret')
        monkeypatch.setattr(wahoo.requests, 'post', lambda *a, **k: _FakeResp({
            'access_token': 'AT', 'refresh_token': 'RT', 'expires_in': 7200}))
        monkeypatch.setattr(wahoo.requests, 'get', lambda *a, **k: _FakeResp({'id': 314}))
        monkeypatch.setattr(wahoo.pa, 'upsert_auth', lambda db, **kw: captured.update(kw) or 1)
        monkeypatch.setattr(wahoo.pa, 'record_oauth_scope_ack', lambda db, **kw: 1)
        # The connect path now also records the identity link (#251 §6.2);
        # stub it — the identity behaviour is covered in test_provider_oauth_signin.
        monkeypatch.setattr(wahoo.pi, 'link_identity', lambda *a, **k: (True, 'linked'))
        client = _make_app(wahoo.bp).test_client()
        start = client.get('/wahoo/oauth/start?return_to=/connections')
        state = urllib.parse.parse_qs(
            urllib.parse.urlparse(start.headers['Location']).query)['state'][0]
        resp = client.get(f'/wahoo/oauth/callback?code=C&state={state}')
        assert resp.status_code == 302
        assert resp.headers['Location'] == '/connections?wahoo_connected=1'
        assert captured['provider'] == 'wahoo'
        assert captured['provider_user_id'] == '314'

    def test_callback_missing_secret_bounces_with_error(self, monkeypatch):
        """A failure after consent redirects back to return_to with a readable
        reason rather than dead-ending on a bare error page."""
        import routes.wahoo as wahoo
        monkeypatch.setattr(wahoo, 'current_user_id', lambda: 7)
        monkeypatch.setenv('WAHOO_CLIENT_ID', 'cid')
        monkeypatch.delenv('WAHOO_CLIENT_SECRET', raising=False)
        client = _make_app(wahoo.bp).test_client()
        start = client.get('/wahoo/oauth/start?return_to=/connections')
        state = urllib.parse.parse_qs(
            urllib.parse.urlparse(start.headers['Location']).query)['state'][0]
        resp = client.get(f'/wahoo/oauth/callback?code=C&state={state}')
        assert resp.status_code == 302
        assert resp.headers['Location'] == '/connections?wahoo_oauth_error=not_configured'

    def test_callback_provider_error_bounces_with_reason(self, monkeypatch):
        """Wahoo bouncing back with ?error=… (e.g. access_denied) is surfaced,
        not swallowed."""
        import routes.wahoo as wahoo
        monkeypatch.setattr(wahoo, 'current_user_id', lambda: 7)
        monkeypatch.setenv('WAHOO_CLIENT_ID', 'cid')
        client = _make_app(wahoo.bp).test_client()
        start = client.get('/wahoo/oauth/start?return_to=/onboarding/connect')
        state = urllib.parse.parse_qs(
            urllib.parse.urlparse(start.headers['Location']).query)['state'][0]
        resp = client.get(
            f'/wahoo/oauth/callback?error=access_denied&state={state}')
        assert resp.status_code == 302
        assert resp.headers['Location'] == \
            '/onboarding/connect?wahoo_oauth_error=access_denied'


# ── webhook ───────────────────────────────────────────────────────────

class _WHDB:
    def __init__(self):
        self.events = []
        self.updates = []

    def execute(self, sql, params=()):
        if 'INSERT INTO webhook_events' in sql:
            self.events.append(params)
            return _Cur({'id': 300})
        if 'UPDATE webhook_events' in sql:
            self.updates.append(params)
        return _Cur(None)

    def commit(self):
        pass


class TestWebhook:
    def test_workout_summary_records_and_ingests(self, monkeypatch):
        import routes.wahoo as wahoo
        db = _WHDB()
        monkeypatch.setattr(wahoo, 'get_db', lambda: db)
        monkeypatch.setattr(wahoo.pa, 'get_auth_by_provider_user_id',
                            lambda d, p, pid: {'user_id': 7})
        monkeypatch.delenv('WAHOO_WEBHOOK_TOKEN', raising=False)
        calls = []
        monkeypatch.setattr(wahoo, '_ingest_workout_summary',
                            lambda d, u, wid, s: calls.append((u, wid)))
        app = Flask(__name__)
        app.register_blueprint(wahoo.bp)
        resp = app.test_client().post('/wahoo/webhook', json={
            'event_type': 'workout_summary', 'user': {'id': 314},
            'workout_summary': {'id': 88, 'workout_type_id': 1}})
        assert resp.status_code == 200
        assert len(db.events) == 1
        assert calls == [(7, '88')]

    def test_bad_token_records_no_ingest(self, monkeypatch):
        import routes.wahoo as wahoo
        db = _WHDB()
        monkeypatch.setattr(wahoo, 'get_db', lambda: db)
        monkeypatch.setattr(wahoo.pa, 'get_auth_by_provider_user_id',
                            lambda d, p, pid: {'user_id': 7})
        monkeypatch.setenv('WAHOO_WEBHOOK_TOKEN', 'expected')
        calls = []
        monkeypatch.setattr(wahoo, '_ingest_workout_summary',
                            lambda d, u, wid, s: calls.append((u, wid)))
        app = Flask(__name__)
        app.register_blueprint(wahoo.bp)
        resp = app.test_client().post('/wahoo/webhook', json={
            'webhook_token': 'WRONG', 'user': {'id': 314},
            'workout_summary': {'id': 88, 'workout_type_id': 1}})
        assert resp.status_code == 200
        assert len(db.events) == 1
        assert calls == []
