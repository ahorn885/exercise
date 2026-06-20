"""At-rest encryption for provider OAuth secrets (#682 / D-12 security gap).

`provider_auth.access_token` / `refresh_token` were stored **plaintext**. This
module encrypts them at rest with Fernet (AES-128-CBC + HMAC), keyed by the
`PROVIDER_TOKEN_ENC_KEY` env var (a urlsafe-base64 32-byte Fernet key).

Transparent migration — no DB backfill needed (and Neon egress is blocked from
the container anyway):
  - **Write** (`provider_auth.upsert_auth`): `encrypt_token` ciphertexts the value
    when a key is configured.
  - **Read** (`provider_auth.get_auth`): `decrypt_token` reverses it, and
    **passes through** anything that isn't a valid ciphertext — so pre-existing
    plaintext rows keep working and self-encrypt on their next write (a token
    refresh rewrites them; Strava ~6h / Whoop ~1h).
  - **Key unset** (dev/test, or prod before the env var is set): both calls pass
    the value through unchanged (current plaintext behaviour) + a one-time warning.
    This makes the rollout safe — deploying this code does not break auth before
    `PROVIDER_TOKEN_ENC_KEY` is set; setting it flips new writes to encrypted.

Generate a key once (chat-only, never commit) and set it as the env var:
    python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
"""
from __future__ import annotations

import os
from typing import Optional

from cryptography.fernet import Fernet, InvalidToken

_ENV_KEY = 'PROVIDER_TOKEN_ENC_KEY'
_warned_no_key = False


def _fernet() -> Optional[Fernet]:
    key = os.environ.get(_ENV_KEY)
    if not key:
        return None
    try:
        return Fernet(key.encode() if isinstance(key, str) else key)
    except (ValueError, TypeError) as exc:
        # A malformed key is an operator error — fail loud (don't silently
        # fall back to plaintext, which would hide a misconfiguration).
        raise RuntimeError(f'{_ENV_KEY} is not a valid Fernet key: {exc}') from exc


def _warn_no_key_once() -> None:
    global _warned_no_key
    if not _warned_no_key:
        _warned_no_key = True
        print(f'[provider-crypto] {_ENV_KEY} unset — provider tokens stored PLAINTEXT')


def encrypt_token(plaintext: Optional[str]) -> Optional[str]:
    """Encrypt a token for storage. None/'' pass through unchanged; with no key
    configured the plaintext is returned as-is (+ a one-time warning)."""
    if plaintext is None or plaintext == '':
        return plaintext
    f = _fernet()
    if f is None:
        _warn_no_key_once()
        return plaintext
    return f.encrypt(plaintext.encode()).decode()


def decrypt_token(stored: Optional[str]) -> Optional[str]:
    """Reverse `encrypt_token`. Passes through values that aren't valid
    ciphertext (legacy plaintext rows, or key-unset) so reads never break."""
    if stored is None or stored == '':
        return stored
    f = _fernet()
    if f is None:
        return stored
    try:
        return f.decrypt(stored.encode()).decode()
    except (InvalidToken, ValueError, TypeError):
        # Not a ciphertext we wrote (pre-existing plaintext, or written before
        # the key was set) — return verbatim; it self-encrypts on next write.
        return stored
