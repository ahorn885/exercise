"""Account-merge engine tests (orchestration via fake DB).

The information_schema discovery + SAVEPOINT/unique-violation SQL is PG-specific
and verify-owed against a live Postgres (design §7). These tests cover the
engine's branching: guards, FK re-point loop, survivor-wins collision fallback,
and all-or-nothing abort on a non-unique error.
"""

from __future__ import annotations

import re

import pytest


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
