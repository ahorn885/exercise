"""T-5.1 (#249/#284) — Garmin auth storage moved off the legacy `garmin_auth`
table onto the shared `provider_auth` table (`session_blob` column).

Covers: garmin_connect.py's four read/write sites now go through
`routes.provider_auth`, and two users' Garmin sessions never cross (the
plan's stated verify criterion). The fake DB below implements just enough
of `provider_auth.upsert_auth`/`get_auth`'s real SQL shapes (parsed from the
actual query strings) to prove isolation end-to-end rather than mocking the
helpers away entirely.
"""

from __future__ import annotations

import json
import os
import re
import sys

os.environ.setdefault('SECRET_KEY', 'test-secret-key-for-garmin-migration-tests')
os.environ['DATABASE_URL'] = ''

import pytest

from routes import provider_auth as pa


class _Cur:
    def __init__(self, one=None):
        self._one = one

    def fetchone(self):
        return self._one


class _FakeProviderAuthDB:
    """In-memory `(user_id, provider)`-keyed store backing the real
    `upsert_auth`/`get_auth` SQL text, so isolation is proven against the
    production query shapes, not a stand-in."""

    def __init__(self):
        self._rows = {}
        self._next_id = 1

    def execute(self, sql, params=()):
        params = list(params)
        if sql.startswith('INSERT INTO provider_auth'):
            cols = [c.strip() for c in
                    re.search(r'INSERT INTO provider_auth \(([^)]+)\)', sql).group(1).split(',')]
            values = dict(zip(cols, params))
            key = (values['user_id'], values['provider'])
            row = self._rows.get(key)
            if row is None:
                row = {'id': self._next_id}
                self._next_id += 1
                self._rows[key] = row
            row.update(values)
            return _Cur({'id': row['id']})
        if sql.startswith('SELECT * FROM provider_auth'):
            row = self._rows.get((params[0], params[1]))
            return _Cur(dict(row) if row is not None else None)
        return _Cur(None)

    def commit(self):
        pass


@pytest.fixture
def db():
    return _FakeProviderAuthDB()


def _browser_session(cookie):
    return json.dumps({'type': 'browser_cookie', 'cookie': cookie})


class TestGarminConnectStorageMigration:
    """garmin_connect.py's read/write sites now use provider_auth."""

    def test_save_and_load_status_round_trips_via_provider_auth(self, monkeypatch, db):
        import garmin_connect as gc
        monkeypatch.setattr(gc, 'current_user_id', lambda: 1)
        monkeypatch.setattr(gc, '_read_session_from_tmp', lambda: _browser_session('cookie-1'))

        gc._save_session_to_db(db, username='alice')

        row = pa.get_auth(db, 1, 'garmin')
        assert row['session_blob'] == _browser_session('cookie-1')
        assert row['provider_user_id'] == 'alice'
        assert row['status'] == pa.STATUS_ACTIVE

        status = gc.get_auth_status(db)
        assert status == {'authenticated': True, 'username': 'alice', 'auth_type': 'browser_cookie'}

    def test_get_auth_status_unauthenticated_when_no_row(self, monkeypatch, db):
        import garmin_connect as gc
        monkeypatch.setattr(gc, 'current_user_id', lambda: 1)
        assert gc.get_auth_status(db) == {'authenticated': False, 'username': None}

    def test_load_client_raises_without_saved_session(self, monkeypatch, db):
        import garmin_connect as gc
        monkeypatch.setattr(gc, 'current_user_id', lambda: 1)
        with pytest.raises(RuntimeError):
            gc._load_client(db)

    def test_two_users_garmin_sessions_never_cross(self, monkeypatch, db):
        """The plan's stated verify: two users' Garmin auth must never mix."""
        import garmin_connect as gc
        current = {'uid': None}
        monkeypatch.setattr(gc, 'current_user_id', lambda: current['uid'])

        current['uid'] = 1
        monkeypatch.setattr(gc, '_read_session_from_tmp', lambda: _browser_session('alice-cookie'))
        gc._save_session_to_db(db, username='alice')

        current['uid'] = 2
        monkeypatch.setattr(gc, '_read_session_from_tmp', lambda: _browser_session('bob-cookie'))
        gc._save_session_to_db(db, username='bob')

        current['uid'] = 1
        status1 = gc.get_auth_status(db)
        current['uid'] = 2
        status2 = gc.get_auth_status(db)

        assert status1 == {'authenticated': True, 'username': 'alice', 'auth_type': 'browser_cookie'}
        assert status2 == {'authenticated': True, 'username': 'bob', 'auth_type': 'browser_cookie'}

        row1 = pa.get_auth(db, 1, 'garmin')
        row2 = pa.get_auth(db, 2, 'garmin')
        assert row1['session_blob'] == _browser_session('alice-cookie')
        assert row2['session_blob'] == _browser_session('bob-cookie')
        assert row1['id'] != row2['id']

    def test_fetch_activities_browser_path_reads_own_session(self, monkeypatch, db):
        import garmin_connect as gc
        current = {'uid': None}
        monkeypatch.setattr(gc, 'current_user_id', lambda: current['uid'])

        current['uid'] = 1
        monkeypatch.setattr(gc, '_read_session_from_tmp', lambda: _browser_session('alice-cookie'))
        gc._save_session_to_db(db, username='alice')

        current['uid'] = 2
        monkeypatch.setattr(gc, '_read_session_from_tmp', lambda: _browser_session('bob-cookie'))
        gc._save_session_to_db(db, username='bob')

        captured = {}

        class _FakeResp:
            status_code = 200
            text = '[]'

            def json(self):
                return []

        class _StubSession:
            def get(self, *a, **k):
                return _FakeResp()

        def _stub_browser_session(session_json):
            captured['session_json'] = session_json
            return _StubSession()

        monkeypatch.setattr(gc, '_browser_requests_session', _stub_browser_session)

        current['uid'] = 2
        gc.fetch_activities(db, '2026-06-01', '2026-06-02')
        assert captured['session_json'] == _browser_session('bob-cookie')


class TestGarminAuthImportRoutes:
    """routes/garmin.py's two direct-SQL auth-import endpoints now go
    through provider_auth.upsert_auth (provider='garmin')."""

    def _client(self, monkeypatch, uid):
        import app as _appmod

        class _AuthCursor:
            def fetchone(self):
                return {'id': uid, 'username': 'owner', 'email': 'o@x.test',
                         'display_name': 'Owner', 'last_login': '2026-06-01'}

            def fetchall(self):
                return []

        class _AuthConn:
            def execute(self, sql, *a, **k):
                return _AuthCursor()

            def commit(self):
                pass

        conn = _AuthConn()
        for mod in list(sys.modules.values()):
            if mod is not None and getattr(mod, 'get_db', None) is not None:
                monkeypatch.setattr(mod, 'get_db', lambda conn=conn: conn, raising=False)
        _appmod.app.config['TESTING'] = True
        _appmod.app.config['WTF_CSRF_ENABLED'] = False
        c = _appmod.app.test_client()
        with c.session_transaction() as sess:
            sess['user_id'] = uid
        return c

    def test_import_cookies_upserts_scoped_to_current_user(self, monkeypatch):
        import routes.garmin as garmin
        captured = {}
        monkeypatch.setattr(garmin.pa, 'upsert_auth',
                             lambda db, uid, provider, **kw: captured.update(
                                 uid=uid, provider=provider, **kw) or 1)
        client = self._client(monkeypatch, uid=1)
        resp = client.post('/garmin/auth/import-cookies',
                            data={'cookie_string': 'raw-cookie-string'})
        assert resp.status_code == 302
        assert captured['uid'] == 1
        assert captured['provider'] == 'garmin'
        assert captured['status'] == garmin.pa.STATUS_ACTIVE
        assert json.loads(captured['session_blob']) == {
            'type': 'browser_cookie', 'cookie': 'raw-cookie-string'}

    def test_import_tokens_upserts_scoped_to_current_user(self, monkeypatch):
        import routes.garmin as garmin

        class _FakeGarthClient:
            username = 'imported-user'

        class _FakeGarth:
            client = _FakeGarthClient()

            @staticmethod
            def resume(path):
                pass

        monkeypatch.setitem(sys.modules, 'garth', _FakeGarth)
        monkeypatch.setattr('garmin_connect._write_session_to_tmp', lambda s: None)

        captured = {}
        monkeypatch.setattr(garmin.pa, 'upsert_auth',
                             lambda db, uid, provider, **kw: captured.update(
                                 uid=uid, provider=provider, **kw) or 1)
        client = self._client(monkeypatch, uid=2)
        resp = client.post('/garmin/auth/import-tokens',
                            data={'token_json': json.dumps({'oauth1_token': 'x'})})
        assert resp.status_code == 302
        assert captured['uid'] == 2
        assert captured['provider'] == 'garmin'
        assert captured['provider_user_id'] == 'imported-user'
        assert captured['status'] == garmin.pa.STATUS_ACTIVE


class TestAdminCascadeDelete:
    def test_delete_user_and_data_clears_provider_auth(self):
        import routes.admin as admin

        class _DB:
            def __init__(self):
                self.deleted_tables = []

            def execute(self, sql, params=()):
                m = re.match(r'DELETE FROM (\S+)', sql.strip())
                if m:
                    self.deleted_tables.append(m.group(1))
                return _Cur(None)

        db = _DB()
        admin._delete_user_and_data(db, 42)
        assert 'garmin_auth' in db.deleted_tables
        assert 'provider_auth' in db.deleted_tables
