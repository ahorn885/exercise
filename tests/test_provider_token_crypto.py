"""Provider OAuth-secret at-rest encryption (#682 / D-12).

Covers the crypto helpers (round-trip / passthrough / legacy-plaintext) and the
provider_auth write+read boundaries (encrypt-on-upsert, decrypt-on-get).
"""

from __future__ import annotations

from cryptography.fernet import Fernet

from routes import provider_token_crypto as ptc
from routes import provider_auth as pa

_KEY = Fernet.generate_key().decode()


def _set_key(monkeypatch):
    monkeypatch.setenv('PROVIDER_TOKEN_ENC_KEY', _KEY)


# ── crypto helpers ─────────────────────────────────────────────────────

class TestCrypto:
    def test_round_trip_with_key(self, monkeypatch):
        _set_key(monkeypatch)
        ct = ptc.encrypt_token('secret-token')
        assert ct != 'secret-token'            # actually encrypted
        assert ptc.decrypt_token(ct) == 'secret-token'

    def test_passthrough_without_key(self, monkeypatch):
        monkeypatch.delenv('PROVIDER_TOKEN_ENC_KEY', raising=False)
        assert ptc.encrypt_token('secret') == 'secret'
        assert ptc.decrypt_token('secret') == 'secret'

    def test_legacy_plaintext_decrypts_to_itself(self, monkeypatch):
        _set_key(monkeypatch)
        # A pre-existing plaintext row (not a ciphertext) must pass through.
        assert ptc.decrypt_token('legacy-plaintext-token') == 'legacy-plaintext-token'

    def test_none_and_empty_pass_through(self, monkeypatch):
        _set_key(monkeypatch)
        assert ptc.encrypt_token(None) is None
        assert ptc.encrypt_token('') == ''
        assert ptc.decrypt_token(None) is None
        assert ptc.decrypt_token('') == ''

    def test_malformed_key_raises(self, monkeypatch):
        monkeypatch.setenv('PROVIDER_TOKEN_ENC_KEY', 'not-a-valid-fernet-key')
        try:
            ptc.encrypt_token('x')
            assert False, 'expected RuntimeError on malformed key'
        except RuntimeError:
            pass


# ── provider_auth write + read boundaries ──────────────────────────────

class _Cur:
    def __init__(self, one=None):
        self._one = one

    def fetchone(self):
        return self._one


class _DB:
    def __init__(self, ret_one=None):
        self.calls = []
        self._ret = ret_one

    def execute(self, sql, params=()):
        self.calls.append((sql, list(params)))
        return _Cur(self._ret)

    def commit(self):
        pass


class TestProviderAuthBoundaries:
    def test_upsert_encrypts_tokens_in_params(self, monkeypatch):
        _set_key(monkeypatch)
        db = _DB(ret_one={'id': 5})
        pa.upsert_auth(db, 1, 'strava',
                       access_token='AT-plain', refresh_token='RT-plain',
                       status='active')
        params = db.calls[0][1]
        # Raw plaintext must NOT be present; an encrypted form that decrypts
        # back to it must be.
        assert 'AT-plain' not in params
        assert 'RT-plain' not in params
        assert any(isinstance(p, str) and ptc.decrypt_token(p) == 'AT-plain' for p in params)
        assert any(isinstance(p, str) and ptc.decrypt_token(p) == 'RT-plain' for p in params)

    def test_get_auth_decrypts_tokens(self, monkeypatch):
        _set_key(monkeypatch)
        enc = ptc.encrypt_token('AT-plain')
        db = _DB(ret_one={'access_token': enc, 'refresh_token': None,
                          'status': 'active', 'user_id': 1, 'provider': 'strava'})
        row = pa.get_auth(db, 1, 'strava')
        assert row['access_token'] == 'AT-plain'
        assert row['refresh_token'] is None

    def test_get_auth_passthrough_legacy_plaintext(self, monkeypatch):
        _set_key(monkeypatch)
        db = _DB(ret_one={'access_token': 'legacy-plain', 'refresh_token': None})
        row = pa.get_auth(db, 1, 'strava')
        assert row['access_token'] == 'legacy-plain'

    def test_get_auth_none_passthrough(self, monkeypatch):
        _set_key(monkeypatch)
        db = _DB(ret_one=None)
        assert pa.get_auth(db, 1, 'strava') is None
