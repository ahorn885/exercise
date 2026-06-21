"""Unit coverage for the TOTP two-factor helpers (`mfa.py`, issue #265).

Pure-crypto only — no DB, no Flask app. The DB helpers (`start_enrollment`
etc.) are thin SQL wrappers exercised by the route layer; what's worth pinning
here is the verification behaviour the login security rests on.
"""

from __future__ import annotations

import pyotp
import pytest

import mfa


class TestGenerateSecret:
    def test_is_valid_base32(self):
        secret = mfa.generate_secret()
        # base32 alphabet, length pyotp emits (32 chars / 160 bits).
        assert secret.isalnum()
        assert len(secret) == 32
        # A generated secret must actually drive a TOTP without error.
        assert pyotp.TOTP(secret).now()

    def test_secrets_are_distinct(self):
        assert mfa.generate_secret() != mfa.generate_secret()


class TestVerifyCode:
    def setup_method(self):
        self.secret = mfa.generate_secret()

    def test_accepts_current_code(self):
        assert mfa.verify_code(self.secret, pyotp.TOTP(self.secret).now())

    def test_rejects_wrong_code(self):
        # Pick a code that is definitely not the current one.
        now = pyotp.TOTP(self.secret).now()
        wrong = '000000' if now != '000000' else '111111'
        assert not mfa.verify_code(self.secret, wrong)

    def test_tolerates_spaces(self):
        code = pyotp.TOTP(self.secret).now()
        spaced = f'{code[:3]} {code[3:]}'
        assert mfa.verify_code(self.secret, spaced)

    def test_rejects_non_digits(self):
        assert not mfa.verify_code(self.secret, 'abcdef')

    @pytest.mark.parametrize('code', ['', None])
    def test_rejects_empty(self, code):
        assert not mfa.verify_code(self.secret, code)

    def test_rejects_empty_secret(self):
        assert not mfa.verify_code('', pyotp.TOTP(self.secret).now())

    def test_never_raises_on_garbage_secret(self):
        # A malformed secret must fail closed, not 500 the login.
        assert mfa.verify_code('not a real secret!!!', '123456') is False

    def test_adjacent_window_accepted(self):
        # The ±1 window should accept the previous 30s step's code.
        totp = pyotp.TOTP(self.secret)
        import time
        prev_code = totp.at(int(time.time()) - 30)
        assert mfa.verify_code(self.secret, prev_code)


class TestProvisioningUri:
    def test_shape(self):
        secret = mfa.generate_secret()
        uri = mfa.provisioning_uri(secret, 'you@example.com')
        assert uri.startswith('otpauth://totp/')
        assert 'AIDSTATION' in uri
        assert f'secret={secret}' in uri

    def test_blank_account_name_falls_back(self):
        # Empty account name must not crash; pyotp needs a label.
        uri = mfa.provisioning_uri(mfa.generate_secret(), '')
        assert uri.startswith('otpauth://totp/')


class TestQrSvg:
    def test_returns_svg_markup(self):
        uri = mfa.provisioning_uri(mfa.generate_secret(), 'you@example.com')
        svg = mfa.qr_svg(uri)
        # qrcode is a declared dependency, so this should render. It's inline
        # SVG markup (CSP-clean), not a data: URI.
        assert svg is not None
        assert '<svg' in svg
        assert 'data:image' not in svg
