"""Account email-change route tests (#251).

Drives profile.change_email via a test client with a fake DB so the
validation + verification-trigger branches are covered without the full app.
"""

from __future__ import annotations

import os

import pytest
from flask import Flask


class _Cur:
    def __init__(self, rows):
        self._rows = list(rows)

    def fetchone(self):
        return self._rows[0] if self._rows else None


class _FakeUserDB:
    """Stand-in for the users queries change_email issues."""
    def __init__(self, current_email=None, taken=False):
        self.current_email = current_email
        self.taken = taken
        self.updates = []     # (email, uid) from the UPDATE
        self.committed = 0

    def execute(self, sql, params=()):
        s = ' '.join(sql.split())
        if s.startswith('SELECT email FROM users WHERE id'):
            return _Cur([{'email': self.current_email}])
        if s.startswith('SELECT 1 FROM users WHERE LOWER(email) = LOWER(?) AND id <> ?'):
            return _Cur([{'x': 1}] if self.taken else [])
        if s.startswith('UPDATE users SET email=?, email_verified=FALSE'):
            self.updates.append((params[0], params[1]))
            return _Cur([])
        raise AssertionError('unexpected SQL: ' + s)

    def commit(self):
        self.committed += 1


def _make_app():
    import routes.profile as profile
    root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    app = Flask(__name__, template_folder=os.path.join(root, 'templates'))
    app.config['SECRET_KEY'] = 'test'
    app.register_blueprint(profile.bp)
    return app, profile


class TestChangeEmail:
    def test_sets_new_email_unverified_and_sends_link(self, monkeypatch):
        app, profile = _make_app()
        db = _FakeUserDB(current_email=None)
        sent = {}
        monkeypatch.setattr(profile, 'get_db', lambda: db)
        monkeypatch.setattr(profile, 'current_user_id', lambda: 5)
        monkeypatch.setattr(profile, 'send_verification_email',
                            lambda d, uid, email: sent.update(uid=uid, email=email))
        resp = app.test_client().post('/profile/email', data={'email': 'New@b.test'})
        assert resp.status_code == 302
        assert db.updates == [('New@b.test', 5)]   # stored, flag reset to FALSE
        assert sent == {'uid': 5, 'email': 'New@b.test'}

    def test_rejects_email_taken_by_another_account(self, monkeypatch):
        app, profile = _make_app()
        db = _FakeUserDB(current_email=None, taken=True)
        sent = {}
        monkeypatch.setattr(profile, 'get_db', lambda: db)
        monkeypatch.setattr(profile, 'current_user_id', lambda: 5)
        monkeypatch.setattr(profile, 'send_verification_email',
                            lambda *a, **k: sent.setdefault('called', True))
        resp = app.test_client().post('/profile/email', data={'email': 'taken@b.test'})
        assert resp.status_code == 302
        assert db.updates == []      # not stored
        assert sent == {}            # no link sent

    def test_rejects_malformed_email(self, monkeypatch):
        app, profile = _make_app()
        db = _FakeUserDB(current_email=None)
        monkeypatch.setattr(profile, 'get_db', lambda: db)
        monkeypatch.setattr(profile, 'current_user_id', lambda: 5)
        monkeypatch.setattr(profile, 'send_verification_email', lambda *a, **k: None)
        resp = app.test_client().post('/profile/email', data={'email': 'notanemail'})
        assert resp.status_code == 302
        assert db.updates == []

    def test_clearing_email_sets_null_no_send(self, monkeypatch):
        app, profile = _make_app()
        db = _FakeUserDB(current_email='old@b.test')
        sent = {}
        monkeypatch.setattr(profile, 'get_db', lambda: db)
        monkeypatch.setattr(profile, 'current_user_id', lambda: 5)
        monkeypatch.setattr(profile, 'send_verification_email',
                            lambda *a, **k: sent.setdefault('called', True))
        resp = app.test_client().post('/profile/email', data={'email': ''})
        assert resp.status_code == 302
        assert db.updates == [(None, 5)]   # NULL email
        assert sent == {}                  # nothing to verify

    def test_unchanged_email_is_noop(self, monkeypatch):
        app, profile = _make_app()
        db = _FakeUserDB(current_email='same@b.test')
        monkeypatch.setattr(profile, 'get_db', lambda: db)
        monkeypatch.setattr(profile, 'current_user_id', lambda: 5)
        monkeypatch.setattr(profile, 'send_verification_email', lambda *a, **k: None)
        resp = app.test_client().post('/profile/email', data={'email': 'same@b.test'})
        assert resp.status_code == 302
        assert db.updates == []
