"""Account-merge engine tests (orchestration via fake DB).

The information_schema discovery + SAVEPOINT/unique-violation SQL is PG-specific
and verify-owed against a live Postgres (design §7). These tests cover the
engine's branching: guards, FK re-point loop, survivor-wins collision fallback,
and all-or-nothing abort on a non-unique error.
"""

from __future__ import annotations

import os
import re

import pytest
from flask import Flask


class _Cur:
    def __init__(self, rows, rowcount=0):
        self._rows = list(rows)
        self.rowcount = rowcount

    def fetchone(self):
        return self._rows[0] if self._rows else None

    def fetchall(self):
        return self._rows


class _UniqueErr(Exception):
    pgcode = '23505'


class _OtherErr(Exception):
    pgcode = '42P01'  # undefined_table — a "real" fault, not a collision


class _FakeMergeDB:
    def __init__(self, fk_columns, users=(1, 2), collide=(), fail=()):
        self.fk = list(fk_columns)
        self.users = set(users)
        self.collide = set(collide)      # "table.col" → raise unique on UPDATE
        self.fail = set(fail)            # "table.col" → raise a non-unique error
        self.updates = []
        self.deletes = []
        self.committed = 0
        self.rolledback = 0

    def execute(self, sql, params=()):
        s = ' '.join(sql.split())
        if s.startswith('SELECT 1 FROM users WHERE id'):
            return _Cur([{'x': 1}] if params[0] in self.users else [])
        if s.startswith('SELECT tc.table_name'):
            return _Cur([{'t': t, 'c': c} for (t, c) in self.fk])
        if s.startswith(('SAVEPOINT', 'RELEASE SAVEPOINT', 'ROLLBACK TO SAVEPOINT')):
            return _Cur([])
        if s.startswith('UPDATE '):
            t, c = re.match(r'UPDATE (\w+) SET (\w+) =', s).groups()
            key = f'{t}.{c}'
            if key in self.fail:
                raise _OtherErr('relation does not exist')
            if key in self.collide:
                raise _UniqueErr('duplicate key value violates unique constraint')
            self.updates.append((key, params))
            return _Cur([], rowcount=2)
        if s.startswith('DELETE FROM users WHERE id'):
            self.users.discard(params[0])
            return _Cur([], rowcount=1)
        if s.startswith('DELETE FROM '):
            t, c = re.match(r'DELETE FROM (\w+) WHERE (\w+) =', s).groups()
            self.deletes.append((f'{t}.{c}', params))
            return _Cur([], rowcount=1)
        raise AssertionError('unexpected SQL: ' + s)

    def commit(self):
        self.committed += 1

    def rollback(self):
        self.rolledback += 1


@pytest.fixture(autouse=True)
def _enable(monkeypatch):
    monkeypatch.setenv('ACCOUNT_MERGE_ENABLED', '1')


class TestGuards:
    def test_disabled_flag_raises(self, monkeypatch):
        from routes import account_merge as am
        monkeypatch.delenv('ACCOUNT_MERGE_ENABLED', raising=False)
        with pytest.raises(RuntimeError):
            am.merge_accounts(_FakeMergeDB([]), 1, 2)

    def test_self_merge_raises(self):
        from routes import account_merge as am
        with pytest.raises(ValueError):
            am.merge_accounts(_FakeMergeDB([]), 1, 1)

    def test_missing_user_raises(self):
        from routes import account_merge as am
        db = _FakeMergeDB([], users=(1,))  # 2 doesn't exist
        with pytest.raises(ValueError):
            am.merge_accounts(db, 1, 2)


class TestMerge:
    def test_repoints_all_fk_columns_and_deletes_drop(self):
        from routes import account_merge as am
        db = _FakeMergeDB(
            [('cardio_log', 'user_id'), ('gym_profiles', 'created_by_user_id')],
        )
        summary = am.merge_accounts(db, keep_id=1, drop_id=2)
        # both columns re-pointed 2→1
        assert {k for k, _ in db.updates} == {
            'cardio_log.user_id', 'gym_profiles.created_by_user_id'}
        assert all(p == (1, 2) for _, p in db.updates)
        assert summary['repointed'] == {
            'cardio_log.user_id': 2, 'gym_profiles.created_by_user_id': 2}
        assert summary['collided'] == {}
        assert 2 not in db.users          # drop user deleted
        assert db.committed == 1 and db.rolledback == 0

    def test_collision_falls_back_to_survivor_wins(self):
        from routes import account_merge as am
        db = _FakeMergeDB(
            [('cardio_log', 'user_id'), ('athlete_profile', 'user_id')],
            collide={'athlete_profile.user_id'},
        )
        summary = am.merge_accounts(db, keep_id=1, drop_id=2)
        # non-colliding table re-pointed; colliding one deleted for drop
        assert summary['repointed'] == {'cardio_log.user_id': 2}
        assert summary['collided'] == {'athlete_profile.user_id': 1}
        assert ('athlete_profile.user_id', (2,)) in db.deletes
        assert db.committed == 1

    def test_non_unique_error_aborts_whole_merge(self):
        from routes import account_merge as am
        db = _FakeMergeDB(
            [('cardio_log', 'user_id'), ('broken', 'user_id')],
            fail={'broken.user_id'},
        )
        with pytest.raises(_OtherErr):
            am.merge_accounts(db, keep_id=1, drop_id=2)
        assert db.committed == 0          # nothing committed
        assert db.rolledback == 1         # whole transaction rolled back
        assert 2 in db.users              # drop user NOT deleted


# ── Entry-point: staging helpers + confirm/execute routes (design §6) ─────────

class TestStaging:
    def test_stage_get_clear(self):
        from routes import account_merge as am
        sess = {}
        am.stage_merge(sess, 7)
        assert am.staged_drop_id(sess) == 7
        am.clear_staged_merge(sess)
        assert am.staged_drop_id(sess) is None


def _profile_app():
    import routes.profile as profile
    root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    app = Flask(__name__, template_folder=os.path.join(root, 'templates'))
    app.config['SECRET_KEY'] = 'test'
    app.config['TESTING'] = True
    app.register_blueprint(profile.bp)
    return app, profile


class TestMergeExecuteRoute:
    def _setup(self, monkeypatch, profile, *, has_password=False):
        monkeypatch.setenv('ACCOUNT_MERGE_ENABLED', '1')
        monkeypatch.setattr(profile, 'current_user_id', lambda: 1)
        monkeypatch.setattr(profile, 'get_db', lambda: object())
        monkeypatch.setattr(profile.account_merge, 'account_label',
                            lambda db, uid: {'username': f'u{uid}', 'email': None,
                                             'has_password': has_password})

    def test_execute_runs_merge_when_confirmed(self, monkeypatch):
        app, profile = _profile_app()
        self._setup(monkeypatch, profile)
        calls = {}
        monkeypatch.setattr(profile.account_merge, 'merge_accounts',
                            lambda db, keep, drop: calls.update(keep=keep, drop=drop)
                            or {'repointed': {'cardio_log.user_id': 3}})
        c = app.test_client()
        with c.session_transaction() as s:
            s['pending_merge_drop_id'] = 2
        resp = c.post('/profile/merge/execute', data={'confirm': 'MERGE'})
        assert resp.status_code == 302
        assert calls == {'keep': 1, 'drop': 2}
        with c.session_transaction() as s:
            assert 'pending_merge_drop_id' not in s   # cleared after merge

    def test_execute_blocks_without_typed_confirm(self, monkeypatch):
        app, profile = _profile_app()
        self._setup(monkeypatch, profile)
        monkeypatch.setattr(profile.account_merge, 'merge_accounts',
                            lambda *a, **k: pytest.fail('must not merge without confirm'))
        c = app.test_client()
        with c.session_transaction() as s:
            s['pending_merge_drop_id'] = 2
        resp = c.post('/profile/merge/execute', data={'confirm': 'nope'})
        assert resp.status_code == 302
        with c.session_transaction() as s:
            assert s['pending_merge_drop_id'] == 2     # still staged, not run

    def test_execute_404_when_flag_off(self, monkeypatch):
        app, profile = _profile_app()
        monkeypatch.delenv('ACCOUNT_MERGE_ENABLED', raising=False)
        monkeypatch.setattr(profile, 'current_user_id', lambda: 1)
        resp = app.test_client().post('/profile/merge/execute', data={'confirm': 'MERGE'})
        assert resp.status_code == 404

    def test_confirm_redirects_when_nothing_staged(self, monkeypatch):
        app, profile = _profile_app()
        monkeypatch.setenv('ACCOUNT_MERGE_ENABLED', '1')
        monkeypatch.setattr(profile, 'current_user_id', lambda: 1)
        monkeypatch.setattr(profile, 'get_db', lambda: object())
        resp = app.test_client().get('/profile/merge/confirm')
        assert resp.status_code == 302                 # nothing staged → back to settings


class TestStravaMergeCallback:
    """The merge entry: logged-in + intent=merge + the Strava identity belongs to
    a DIFFERENT account → stage it and bounce to the confirm screen."""
    def test_merge_intent_stages_other_account(self, monkeypatch):
        import routes.strava as strava
        root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        app = Flask(__name__, template_folder=os.path.join(root, 'templates'))
        app.config['SECRET_KEY'] = 'test'
        app.register_blueprint(strava.bp)
        app.add_url_rule('/login', endpoint='auth.login', view_func=lambda: '')
        app.add_url_rule('/mc', endpoint='profile.merge_confirm', view_func=lambda: '')

        staged = {}
        monkeypatch.setattr(strava, 'current_user_id', lambda: 1)   # logged in as keep
        monkeypatch.setattr(strava, 'get_db', lambda: object())
        monkeypatch.setenv('STRAVA_CLIENT_ID', 'cid')
        monkeypatch.setenv('STRAVA_CLIENT_SECRET', 'secret')

        class _R:
            def raise_for_status(self): pass
            def json(self): return {'access_token': 'AT', 'refresh_token': 'RT',
                                    'expires_at': 1_900_000_000, 'athlete': {'id': 42}}
        monkeypatch.setattr(strava.requests, 'post', lambda *a, **k: _R())
        monkeypatch.setattr(strava.pi, 'get_identity',
                            lambda db, prov, puid: {'id': 9, 'user_id': 2})  # drop = acct 2
        monkeypatch.setattr(strava.account_merge, 'stage_merge',
                            lambda sess, drop: staged.update(drop=drop))
        monkeypatch.setattr(strava, '_persist_strava_auth',
                            lambda *a, **k: pytest.fail('merge must not persist/link'))
        c = app.test_client()
        start = c.get('/strava/oauth/start?intent=merge&return_to=/profile/account')
        from urllib.parse import urlparse, parse_qs
        state = parse_qs(urlparse(start.headers['Location']).query)['state'][0]
        resp = c.get(f'/strava/oauth/callback?code=C&state={state}')
        assert resp.status_code == 302
        assert resp.headers['Location'] == '/mc'        # bounced to confirm
        assert staged == {'drop': 2}
