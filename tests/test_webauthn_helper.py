"""Unit coverage for the passkey / WebAuthn helpers (`webauthn_helper.py`,
issue #267).

Ceremony crypto (`build_registration_options` / `verify_registration` /
`build_authentication_options` / `verify_authentication`) wraps the
`webauthn` library -- a real authenticator ceremony can't be simulated in a
unit test, so the library's own verify functions are monkeypatched and what's
pinned here is webauthn_helper's own logic: RP ID / origin derivation, the
discoverable-credential registration options, the exclude-list, and the DB
read/write shape. Fake DBs throughout, mirroring tests/test_invites.py.
"""

from __future__ import annotations

import json

import pytest

import webauthn_helper


class _Cur:
    def __init__(self, rows):
        self._rows = list(rows)

    def fetchone(self):
        return self._rows[0] if self._rows else None

    def fetchall(self):
        return self._rows


class _FakeDB:
    def __init__(self, credentials=None):
        self.credentials = list(credentials or [])
        self.executed = []
        self.committed = 0

    def execute(self, sql, params=()):
        s = ' '.join(sql.split())
        self.executed.append((s, params))
        if s.startswith('SELECT id, user_id, credential_id, nickname, created_at, last_used_at '
                         'FROM user_webauthn_credentials WHERE user_id'):
            rows = [c for c in self.credentials if c['user_id'] == params[0]]
            return _Cur(rows)
        if s.startswith('SELECT id, user_id, credential_id, public_key, sign_count '
                         'FROM user_webauthn_credentials WHERE credential_id'):
            rows = [c for c in self.credentials if c['credential_id'] == params[0]]
            return _Cur(rows)
        if s.startswith('INSERT INTO user_webauthn_credentials'):
            row = {'id': len(self.credentials) + 1, 'user_id': params[0],
                   'credential_id': params[1], 'public_key': params[2],
                   'sign_count': params[3], 'nickname': params[4],
                   'created_at': '2026-07-01', 'last_used_at': None}
            self.credentials.append(row)
            return _Cur([])
        if s.startswith('UPDATE user_webauthn_credentials SET sign_count'):
            for c in self.credentials:
                if c['id'] == params[1]:
                    c['sign_count'] = params[0]
                    c['last_used_at'] = 'now'
            return _Cur([])
        if s.startswith('DELETE FROM user_webauthn_credentials'):
            self.credentials = [
                c for c in self.credentials
                if not (c['id'] == params[0] and c['user_id'] == params[1])
            ]
            return _Cur([])
        raise AssertionError('unexpected SQL: ' + s)

    def commit(self):
        self.committed += 1


class TestRpIdForHost:
    def test_strips_port(self):
        assert webauthn_helper.rp_id_for_host('localhost:5000') == 'localhost'

    def test_bare_domain_unchanged(self):
        assert webauthn_helper.rp_id_for_host('app.aidstation.pro') == 'app.aidstation.pro'

    def test_blank_host(self):
        assert webauthn_helper.rp_id_for_host('') == ''
        assert webauthn_helper.rp_id_for_host(None) == ''


class TestOriginForRequest:
    def test_shape(self):
        assert webauthn_helper.origin_for_request('https', 'app.aidstation.pro') == \
            'https://app.aidstation.pro'


class TestBuildRegistrationOptions:
    def test_is_discoverable_and_scoped_to_rp_id(self):
        db = _FakeDB()
        options_json, challenge_b64 = webauthn_helper.build_registration_options(
            db, user_id=7, username='andy', host='app.aidstation.pro:443'
        )
        options = json.loads(options_json)
        assert options['rp']['id'] == 'app.aidstation.pro'
        assert options['rp']['name'] == 'AIDSTATION'
        assert options['user']['name'] == 'andy'
        # Resident-key required -- the login page's passwordless flow depends
        # on every registered passkey being discoverable.
        assert options['authenticatorSelection']['residentKey'] == 'required'
        assert options['excludeCredentials'] == []
        assert challenge_b64  # non-empty, base64-encoded

    def test_excludes_existing_credentials(self):
        db = _FakeDB(credentials=[
            {'user_id': 7, 'credential_id': 'AQIDBA', 'nickname': 'iPhone',
             'created_at': '2026-06-01', 'last_used_at': None},
        ])
        options_json, _ = webauthn_helper.build_registration_options(
            db, user_id=7, username='andy', host='localhost:5000'
        )
        options = json.loads(options_json)
        assert len(options['excludeCredentials']) == 1
        assert options['excludeCredentials'][0]['id'] == 'AQIDBA'

    def test_does_not_exclude_other_users_credentials(self):
        db = _FakeDB(credentials=[
            {'user_id': 99, 'credential_id': 'someoneelse', 'nickname': 'x',
             'created_at': '2026-06-01', 'last_used_at': None},
        ])
        options_json, _ = webauthn_helper.build_registration_options(
            db, user_id=7, username='andy', host='localhost:5000'
        )
        options = json.loads(options_json)
        assert options['excludeCredentials'] == []


class TestBuildAuthenticationOptions:
    def test_no_allow_credentials(self):
        # No allow_credentials -- a discoverable credential means the browser
        # itself, not the server, resolves which account is signing in.
        options_json, challenge_b64 = webauthn_helper.build_authentication_options(
            'app.aidstation.pro'
        )
        options = json.loads(options_json)
        assert options['rpId'] == 'app.aidstation.pro'
        assert 'allowCredentials' not in options or options['allowCredentials'] == []
        assert challenge_b64


class TestVerifyAuthentication:
    def test_unknown_credential_id_returns_none(self):
        db = _FakeDB()
        result = webauthn_helper.verify_authentication(
            db, {'id': 'not-registered'}, 'Y2hhbGxlbmdl', 'localhost', 'http'
        )
        assert result is None

    def test_matched_credential_verified_and_touched(self, monkeypatch):
        db = _FakeDB(credentials=[
            {'id': 1, 'user_id': 7, 'credential_id': 'AQIDBA', 'public_key': 'cHVia2V5',
             'sign_count': 3},
        ])

        class _FakeVerification:
            new_sign_count = 4

        monkeypatch.setattr(
            webauthn_helper, 'verify_authentication_response',
            lambda **kw: _FakeVerification()
        )
        row = webauthn_helper.verify_authentication(
            db, {'id': 'AQIDBA'}, 'Y2hhbGxlbmdl', 'localhost', 'http'
        )
        assert row['user_id'] == 7
        assert db.credentials[0]['sign_count'] == 4

    def test_bad_signature_raises(self, monkeypatch):
        db = _FakeDB(credentials=[
            {'id': 1, 'user_id': 7, 'credential_id': 'AQIDBA', 'public_key': 'cHVia2V5',
             'sign_count': 3},
        ])

        def _boom(**kw):
            raise ValueError('bad signature')

        monkeypatch.setattr(webauthn_helper, 'verify_authentication_response', _boom)
        with pytest.raises(ValueError):
            webauthn_helper.verify_authentication(
                db, {'id': 'AQIDBA'}, 'Y2hhbGxlbmdl', 'localhost', 'http'
            )
        # Sign count untouched on failure.
        assert db.credentials[0]['sign_count'] == 3


class TestCredentialCrud:
    def test_add_list_delete_round_trip(self):
        db = _FakeDB()
        webauthn_helper.add_credential(db, 7, 'AQIDBA', b'somekey', 0, 'My Phone')
        rows = webauthn_helper.list_credentials(db, 7)
        assert len(rows) == 1
        assert rows[0]['nickname'] == 'My Phone'
        assert rows[0]['credential_id'] == 'AQIDBA'

        found = webauthn_helper.find_credential_by_id(db, 'AQIDBA')
        assert found['user_id'] == 7

        webauthn_helper.delete_credential(db, 7, rows[0]['id'])
        assert webauthn_helper.list_credentials(db, 7) == []

    def test_delete_scoped_to_user_id(self):
        db = _FakeDB()
        webauthn_helper.add_credential(db, 7, 'AQIDBA', b'somekey', 0, 'My Phone')
        # A different user's delete call must not remove someone else's row.
        webauthn_helper.delete_credential(db, 99, 1)
        assert len(webauthn_helper.list_credentials(db, 7)) == 1
