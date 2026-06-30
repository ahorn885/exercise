"""Admin invite flow tests (#274, #272 SMS/WhatsApp).

Covers the auth-layer invite token helpers (issue/lookup gate, one per
channel), the admin create/revoke routes, and register's invite-acceptance
path (bypasses closed registration, locks the email when present, marks the
invite used + the email verified when there is one to verify).
Fake DBs throughout — no live PG.
"""

from __future__ import annotations

import os
from datetime import datetime, timedelta

import pytest
from flask import Flask


class _Cur:
    def __init__(self, rows, rowcount=0, lastrowid=None):
        self._rows = list(rows)
        self.rowcount = rowcount
        self._lastrowid = lastrowid

    def fetchone(self):
        return self._rows[0] if self._rows else None

    def fetchall(self):
        return self._rows

    @property
    def lastrowid(self):
        return self._lastrowid


def _iso(delta):
    return (datetime.utcnow() + delta).isoformat(timespec='seconds')


# ── auth helpers: issue_invite / lookup_invite ────────────────────────────

class _InviteHelperDB:
    def __init__(self, row=None):
        self.row = row          # dict the lookup SELECT returns, or None
        self.inserted = []
        self.committed = 0

    def execute(self, sql, params=()):
        s = ' '.join(sql.split())
        if s.startswith('INSERT INTO user_invites'):
            self.inserted.append(params)
            return _Cur([])
        if s.startswith('SELECT token, email, phone, channel, accepted_at, expires_at FROM user_invites'):
            return _Cur([self.row] if self.row else [])
        raise AssertionError('unexpected SQL: ' + s)

    def commit(self):
        self.committed += 1


class TestInviteHelpers:
    def test_issue_inserts_and_returns_token(self):
        from routes import auth
        db = _InviteHelperDB()
        token = auth.issue_invite(db, email='new@b.test', channel='email', created_by=1)
        assert token and isinstance(token, str)
        ins = db.inserted[0]
        assert ins[0] == token and ins[1] == 'new@b.test' and ins[2] is None
        assert ins[3] == 'email' and ins[4] == 1
        assert db.committed == 1

    def test_issue_phone_channel(self):
        from routes import auth
        db = _InviteHelperDB()
        token = auth.issue_invite(db, phone='+15551234567', channel='sms', created_by=1)
        ins = db.inserted[0]
        assert ins[0] == token and ins[1] is None and ins[2] == '+15551234567'
        assert ins[3] == 'sms' and ins[4] == 1

    def test_lookup_valid(self):
        from routes import auth
        row = {'token': 'TOK', 'email': 'a@b.test', 'phone': None, 'channel': 'email',
               'accepted_at': None, 'expires_at': _iso(timedelta(days=1))}
        assert auth.lookup_invite(_InviteHelperDB(row), 'TOK')['email'] == 'a@b.test'

    def test_lookup_none_for_blank_token(self):
        from routes import auth
        assert auth.lookup_invite(_InviteHelperDB(), '') is None

    def test_lookup_none_for_missing(self):
        from routes import auth
        assert auth.lookup_invite(_InviteHelperDB(None), 'TOK') is None

    def test_lookup_none_when_accepted(self):
        from routes import auth
        row = {'token': 'TOK', 'email': 'a@b.test', 'phone': None, 'channel': 'email',
               'accepted_at': _iso(timedelta(hours=-1)),
               'expires_at': _iso(timedelta(days=1))}
        assert auth.lookup_invite(_InviteHelperDB(row), 'TOK') is None

    def test_lookup_none_when_expired(self):
        from routes import auth
        row = {'token': 'TOK', 'email': 'a@b.test', 'phone': None, 'channel': 'email',
               'accepted_at': None, 'expires_at': _iso(timedelta(days=-1))}
        assert auth.lookup_invite(_InviteHelperDB(row), 'TOK') is None


# ── admin routes: /admin/invite and revoke ────────────────────────────────

class _AdminDB:
    def __init__(self, email_exists=False):
        self.email_exists = email_exists
        self.deletes = []
        self.committed = 0

    def execute(self, sql, params=()):
        s = ' '.join(sql.split())
        if s.startswith('SELECT 1 FROM users WHERE LOWER(email) = LOWER(?)'):
            return _Cur([{'x': 1}] if self.email_exists else [])
        if s.startswith('DELETE FROM user_invites WHERE token'):
            self.deletes.append(params)
            return _Cur([], rowcount=1)
        raise AssertionError('unexpected SQL: ' + s)

    def commit(self):
        self.committed += 1


def _admin_app():
    import routes.admin as admin
    app = Flask(__name__)
    app.config['SECRET_KEY'] = 'test'
    app.register_blueprint(admin.bp)
    return app, admin


class TestAdminInvite:
    def test_invite_sends_for_new_email(self, monkeypatch):
        app, admin = _admin_app()
        sent = {}
        db = _AdminDB(email_exists=False)
        monkeypatch.setattr(admin, 'current_user_id', lambda: 1)
        monkeypatch.setattr(admin, 'get_db', lambda: db)
        import routes.auth as auth
        monkeypatch.setattr(auth, 'send_invite_email',
                            lambda d, email, by: sent.update(email=email, by=by))
        resp = app.test_client().post('/admin/invite', data={'channel': 'email', 'email': 'new@b.test'})
        assert resp.status_code == 302
        assert sent == {'email': 'new@b.test', 'by': 1}

    def test_invite_defaults_to_email_channel(self, monkeypatch):
        # No `channel` field posted (e.g. a stale cached form) — defaults to
        # email, matching pre-#272 behavior.
        app, admin = _admin_app()
        sent = {}
        db = _AdminDB(email_exists=False)
        monkeypatch.setattr(admin, 'current_user_id', lambda: 1)
        monkeypatch.setattr(admin, 'get_db', lambda: db)
        import routes.auth as auth
        monkeypatch.setattr(auth, 'send_invite_email',
                            lambda d, email, by: sent.update(email=email, by=by))
        resp = app.test_client().post('/admin/invite', data={'email': 'new@b.test'})
        assert resp.status_code == 302
        assert sent == {'email': 'new@b.test', 'by': 1}

    def test_invite_rejects_existing_email(self, monkeypatch):
        app, admin = _admin_app()
        sent = {}
        db = _AdminDB(email_exists=True)
        monkeypatch.setattr(admin, 'current_user_id', lambda: 1)
        monkeypatch.setattr(admin, 'get_db', lambda: db)
        import routes.auth as auth
        monkeypatch.setattr(auth, 'send_invite_email',
                            lambda *a, **k: sent.setdefault('called', True))
        resp = app.test_client().post('/admin/invite', data={'channel': 'email', 'email': 'dupe@b.test'})
        assert resp.status_code == 302
        assert sent == {}                       # no invite sent

    def test_invite_requires_admin(self, monkeypatch):
        app, admin = _admin_app()
        monkeypatch.setattr(admin, 'current_user_id', lambda: 2)  # not admin
        monkeypatch.setattr(admin, 'get_db', lambda: _AdminDB())
        resp = app.test_client().post('/admin/invite', data={'channel': 'email', 'email': 'x@b.test'})
        assert resp.status_code == 403

    def test_invite_sms_sends_when_configured(self, monkeypatch):
        app, admin = _admin_app()
        sent = {}
        monkeypatch.setattr(admin, 'current_user_id', lambda: 1)
        monkeypatch.setattr(admin, 'get_db', lambda: _AdminDB())
        monkeypatch.setattr(admin, 'sms_configured', lambda: True)
        import routes.auth as auth
        monkeypatch.setattr(auth, 'send_invite_sms',
                            lambda d, phone, by: sent.update(phone=phone, by=by))
        resp = app.test_client().post('/admin/invite',
                                       data={'channel': 'sms', 'phone': '+15551234567'})
        assert resp.status_code == 302
        assert sent == {'phone': '+15551234567', 'by': 1}

    def test_invite_sms_blocked_when_unconfigured(self, monkeypatch):
        app, admin = _admin_app()
        sent = {}
        monkeypatch.setattr(admin, 'current_user_id', lambda: 1)
        monkeypatch.setattr(admin, 'get_db', lambda: _AdminDB())
        monkeypatch.setattr(admin, 'sms_configured', lambda: False)
        import routes.auth as auth
        monkeypatch.setattr(auth, 'send_invite_sms',
                            lambda *a, **k: sent.setdefault('called', True))
        resp = app.test_client().post('/admin/invite',
                                       data={'channel': 'sms', 'phone': '+15551234567'})
        assert resp.status_code == 302
        assert sent == {}

    def test_invite_whatsapp_sends_when_configured(self, monkeypatch):
        app, admin = _admin_app()
        sent = {}
        monkeypatch.setattr(admin, 'current_user_id', lambda: 1)
        monkeypatch.setattr(admin, 'get_db', lambda: _AdminDB())
        monkeypatch.setattr(admin, 'whatsapp_configured', lambda: True)
        import routes.auth as auth
        monkeypatch.setattr(auth, 'send_invite_whatsapp',
                            lambda d, phone, by: sent.update(phone=phone, by=by))
        resp = app.test_client().post('/admin/invite',
                                       data={'channel': 'whatsapp', 'phone': '+15551234567'})
        assert resp.status_code == 302
        assert sent == {'phone': '+15551234567', 'by': 1}

    def test_invite_whatsapp_blocked_when_unconfigured(self, monkeypatch):
        app, admin = _admin_app()
        sent = {}
        monkeypatch.setattr(admin, 'current_user_id', lambda: 1)
        monkeypatch.setattr(admin, 'get_db', lambda: _AdminDB())
        monkeypatch.setattr(admin, 'whatsapp_configured', lambda: False)
        import routes.auth as auth
        monkeypatch.setattr(auth, 'send_invite_whatsapp',
                            lambda *a, **k: sent.setdefault('called', True))
        resp = app.test_client().post('/admin/invite',
                                       data={'channel': 'whatsapp', 'phone': '+15551234567'})
        assert resp.status_code == 302
        assert sent == {}

    def test_invite_rejects_malformed_phone(self, monkeypatch):
        app, admin = _admin_app()
        monkeypatch.setattr(admin, 'current_user_id', lambda: 1)
        monkeypatch.setattr(admin, 'get_db', lambda: _AdminDB())
        resp = app.test_client().post('/admin/invite',
                                       data={'channel': 'sms', 'phone': 'not-a-phone'})
        assert resp.status_code == 302

    def test_invite_rejects_unknown_channel(self, monkeypatch):
        app, admin = _admin_app()
        monkeypatch.setattr(admin, 'current_user_id', lambda: 1)
        monkeypatch.setattr(admin, 'get_db', lambda: _AdminDB())
        resp = app.test_client().post('/admin/invite',
                                       data={'channel': 'carrier-pigeon', 'email': 'x@b.test'})
        assert resp.status_code == 302

    def test_revoke_deletes_pending(self, monkeypatch):
        app, admin = _admin_app()
        db = _AdminDB()
        monkeypatch.setattr(admin, 'current_user_id', lambda: 1)
        monkeypatch.setattr(admin, 'get_db', lambda: db)
        resp = app.test_client().post('/admin/invite/TOK123/revoke')
        assert resp.status_code == 302
        assert db.deletes and db.deletes[0][0] == 'TOK123'


# ── register: invite acceptance ───────────────────────────────────────────

class _RegisterDB:
    def __init__(self, invite_row):
        self.invite_row = invite_row
        self.inserted_user = None
        self.verified = []
        self.accepted = []
        self.committed = 0
        self.rolled_back = 0

    def execute(self, sql, params=()):
        s = ' '.join(sql.split())
        if s.startswith('SELECT COUNT(*) AS n FROM users'):
            return _Cur([{'n': 1}])                     # not bootstrap
        if s.startswith('SELECT token, email, phone, channel, accepted_at, expires_at FROM user_invites'):
            return _Cur([self.invite_row] if self.invite_row else [])
        if s.startswith('SELECT 1 FROM users WHERE username'):
            return _Cur([])
        if s.startswith('SELECT 1 FROM users WHERE email'):
            return _Cur([])
        if s.startswith('INSERT INTO users'):
            self.inserted_user = params
            return _Cur([{'id': 42}], lastrowid=42)
        if s.startswith('UPDATE users SET email_verified = TRUE'):
            self.verified.append(params)
            return _Cur([])
        if s.startswith('UPDATE user_invites SET accepted_at'):
            self.accepted.append(params)
            return _Cur([])
        # rx-seed queries land here; register swallows the error in try/except.
        raise AssertionError('unexpected SQL: ' + s)

    def commit(self):
        self.committed += 1

    def rollback(self):
        # register() rolls back the standalone rx-seed transaction when the seed
        # raises (here the stub raises AssertionError on the seed SQL), leaving
        # the already-committed user intact. Mirrors _PgConn.rollback.
        self.rolled_back += 1


def _auth_app():
    import routes.auth as auth
    root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    app = Flask(__name__, template_folder=os.path.join(root, 'templates'))
    app.config['SECRET_KEY'] = 'test'
    app.config['TESTING'] = True
    app.register_blueprint(auth.bp)

    @app.route('/onb', endpoint='onboarding.connect')
    def _o():  # pragma: no cover
        return 'onb'

    @app.route('/dash', endpoint='dashboard.index')
    def _d():  # pragma: no cover
        return 'dash'

    return app, auth


class TestRegisterInvite:
    def test_invite_bypasses_closed_registration_and_verifies(self, monkeypatch):
        app, auth = _auth_app()
        monkeypatch.setenv('ALLOW_REGISTRATION', '0')   # registration is closed
        row = {'token': 'TOK', 'email': 'invitee@b.test', 'phone': None, 'channel': 'email',
               'accepted_at': None, 'expires_at': _iso(timedelta(days=1))}
        db = _RegisterDB(row)
        monkeypatch.setattr(auth, 'get_db', lambda: db)
        # verification email must NOT be sent on the invite path (already verified)
        monkeypatch.setattr(auth, 'send_verification_email',
                            lambda *a, **k: pytest.fail('should not send verify on invite'))

        resp = app.test_client().post(
            '/auth/register?invite=TOK',
            data={'username': 'invitee9', 'display_name': '',
                  'email': 'attacker@evil.test',   # ignored — invite pins the email
                  'password': 'tr0ubad0ur-xy9q-kestrel',
                  'confirm': 'tr0ubad0ur-xy9q-kestrel'},
        )
        assert resp.status_code == 302
        assert resp.headers['Location'] == '/onb'        # new athlete → connect step
        # email locked to the invited address, not the posted one
        assert db.inserted_user[1] == 'invitee@b.test'
        assert db.verified == [(42,)]                    # email_verified flipped
        assert db.accepted and db.accepted[0][1] == 42 and db.accepted[0][2] == 'TOK'

    def test_closed_registration_without_invite_is_403(self, monkeypatch):
        app, auth = _auth_app()
        monkeypatch.setenv('ALLOW_REGISTRATION', '0')
        db = _RegisterDB(None)
        monkeypatch.setattr(auth, 'get_db', lambda: db)
        resp = app.test_client().post(
            '/auth/register',
            data={'username': 'nope9', 'password': 'tr0ubad0ur-xy9q-kestrel',
                  'confirm': 'tr0ubad0ur-xy9q-kestrel'},
        )
        assert resp.status_code == 403

    def test_phone_invite_bypasses_closed_registration_no_email_pin(self, monkeypatch):
        # An SMS/WhatsApp invite (#272) has no email to pin — the athlete's
        # posted email goes through untouched, same as organic signup, and
        # email_verified is still set (no email at all is harmless to "verify").
        app, auth = _auth_app()
        monkeypatch.setenv('ALLOW_REGISTRATION', '0')
        row = {'token': 'TOK', 'email': None, 'phone': '+15551234567', 'channel': 'sms',
               'accepted_at': None, 'expires_at': _iso(timedelta(days=1))}
        db = _RegisterDB(row)
        monkeypatch.setattr(auth, 'get_db', lambda: db)
        monkeypatch.setattr(auth, 'send_verification_email',
                            lambda *a, **k: pytest.fail('should not send verify on invite'))

        resp = app.test_client().post(
            '/auth/register?invite=TOK',
            data={'username': 'phoneinvitee', 'display_name': '',
                  'email': 'me@b.test',
                  'password': 'tr0ubad0ur-xy9q-kestrel',
                  'confirm': 'tr0ubad0ur-xy9q-kestrel'},
        )
        assert resp.status_code == 302
        assert db.inserted_user[1] == 'me@b.test'         # not pinned — athlete's own email used
        assert db.verified == [(42,)]
        assert db.accepted and db.accepted[0][2] == 'TOK'
