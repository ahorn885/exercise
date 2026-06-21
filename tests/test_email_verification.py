"""Email-verification token lifecycle tests (#251).

The auth routes need the full app (CSRF, limiter) which can't import in this
container, so we test the storage-level helpers — issue_email_verification and
consume_email_verification — against a fake DB. The route handlers are thin
flash/redirect wrappers over consume_email_verification's status.
"""

from __future__ import annotations

from datetime import datetime, timedelta

import pytest


class _Cur:
    def __init__(self, rows):
        self._rows = list(rows)

    def fetchone(self):
        return self._rows[0] if self._rows else None


class _FakeVerifyDB:
    """In-memory stand-in for the email_verifications + users queries that
    issue/consume_email_verification issue."""
    def __init__(self, row=None):
        self.row = row              # dict the SELECT JOIN returns, or None
        self.user_verified = {}     # user_id -> True after the UPDATE
        self.token_used = {}        # token -> used_at after the UPDATE
        self.inserted = []          # issued rows
        self.committed = 0

    def execute(self, sql, params=()):
        s = ' '.join(sql.split())
        if s.startswith('INSERT INTO email_verifications'):
            self.inserted.append(params)
            return _Cur([])
        if s.startswith('SELECT ev.user_id, ev.email'):
            return _Cur([self.row] if self.row else [])
        if s.startswith('UPDATE users SET email_verified = TRUE'):
            self.user_verified[params[0]] = True
            return _Cur([])
        if s.startswith('UPDATE email_verifications SET used_at'):
            self.token_used[params[1]] = params[0]
            return _Cur([])
        raise AssertionError('unexpected SQL: ' + s)

    def commit(self):
        self.committed += 1


def _iso(delta):
    return (datetime.utcnow() + delta).isoformat(timespec='seconds')


def _row(**over):
    base = {
        'user_id': 5,
        'email': 'a@b.test',
        'current_email': 'a@b.test',
        'expires_at': _iso(timedelta(hours=1)),
        'used_at': None,
    }
    base.update(over)
    return base


class TestIssue:
    def test_issues_token_and_inserts_row(self):
        from routes import auth
        db = _FakeVerifyDB()
        token = auth.issue_email_verification(db, 5, 'a@b.test')
        assert token and isinstance(token, str)
        assert len(db.inserted) == 1
        ins = db.inserted[0]
        assert ins[0] == token and ins[1] == 5 and ins[2] == 'a@b.test'
        assert db.committed == 1


class TestConsume:
    def test_ok_flips_flag_and_consumes_token(self):
        from routes import auth
        db = _FakeVerifyDB(_row())
        status, uid = auth.consume_email_verification(db, 'tok')
        assert (status, uid) == ('ok', 5)
        assert db.user_verified == {5: True}
        assert 'tok' in db.token_used

    def test_invalid_token(self):
        from routes import auth
        db = _FakeVerifyDB(None)
        assert auth.consume_email_verification(db, 'tok') == ('invalid', None)
        assert db.user_verified == {}

    def test_already_used(self):
        from routes import auth
        db = _FakeVerifyDB(_row(used_at=_iso(timedelta(hours=-1))))
        status, uid = auth.consume_email_verification(db, 'tok')
        assert (status, uid) == ('used', 5)
        assert db.user_verified == {}  # not re-verified

    def test_expired(self):
        from routes import auth
        db = _FakeVerifyDB(_row(expires_at=_iso(timedelta(hours=-1))))
        status, uid = auth.consume_email_verification(db, 'tok')
        assert (status, uid) == ('expired', 5)
        assert db.user_verified == {}

    def test_stale_when_email_changed(self):
        from routes import auth
        db = _FakeVerifyDB(_row(current_email='new@b.test'))
        status, uid = auth.consume_email_verification(db, 'tok')
        assert (status, uid) == ('stale', 5)
        assert db.user_verified == {}

    def test_email_match_is_case_insensitive(self):
        from routes import auth
        db = _FakeVerifyDB(_row(email='A@B.test', current_email='a@b.TEST'))
        status, _uid = auth.consume_email_verification(db, 'tok')
        assert status == 'ok'


class TestSend:
    def test_blank_email_is_noop(self):
        from routes import auth
        db = _FakeVerifyDB()
        assert auth.send_verification_email(db, 5, '') is False
        assert db.inserted == []
