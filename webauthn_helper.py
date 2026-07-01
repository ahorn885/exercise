"""Passkey / WebAuthn authentication — issue #267.

Registration ceremony: from Profile -> Account, an athlete attaches a
passkey (Face ID, Touch ID, Windows Hello, a hardware security key, ...) to
their account. Authentication ceremony: the login page offers "Sign in with
a passkey" using a discoverable/resident credential, so the browser's own
passkey picker resolves which account is signing in -- no username typed
first.

Andy's call (AskUserQuestion, 2026-07-01): a passkey is an *alternative*
sign-in path alongside password[+TOTP], not a replacement -- and a
successful passkey ceremony is accepted on its own. It is not followed by a
TOTP challenge even when the account has TOTP enabled: the ceremony already
proves possession of the authenticator plus a local user-verification step
(biometric/PIN), at least as strong as password+TOTP.

Two layers, mirroring mfa.py:

  Ceremony wrappers (thin adapters over the `webauthn` library, no DB):
    build_registration_options / verify_registration
    build_authentication_options

  DB helpers (take an open `db`, operate on `user_webauthn_credentials`,
  one row per registered authenticator):
    list_credentials / find_credential_by_id / add_credential /
    touch_credential / delete_credential / verify_authentication
"""
import base64

from webauthn import (
    generate_authentication_options,
    generate_registration_options,
    options_to_json,
    verify_authentication_response,
    verify_registration_response,
)
from webauthn.helpers import base64url_to_bytes, bytes_to_base64url
from webauthn.helpers.structs import (
    AuthenticatorSelectionCriteria,
    PublicKeyCredentialDescriptor,
    ResidentKeyRequirement,
    UserVerificationRequirement,
)

RP_NAME = 'AIDSTATION'


def rp_id_for_host(host: str) -> str:
    """Bare domain for the WebAuthn Relying Party ID -- strip the port
    ('localhost:5000' -> 'localhost'; 'app.aidstation.pro:443' -> the
    domain). A passkey is bound to this value at registration; every later
    sign-in must present a request for the same RP ID or the browser won't
    offer the credential at all."""
    return (host or '').split(':')[0]


def origin_for_request(scheme: str, host: str) -> str:
    return f'{scheme}://{host}'


# ── Registration ceremony ───────────────────────────────────────────────────

def build_registration_options(db, user_id, username, host):
    """Options for `navigator.credentials.create()`. Returns
    (options_json_str, challenge_b64) -- the caller stashes the challenge
    (in `session`) to check against the completed ceremony.

    Registers as a discoverable/resident credential (Andy's UX call: the
    login page offers passwordless sign-in without asking for a username
    first) and excludes the athlete's existing credentials so re-adding the
    same authenticator is rejected client-side rather than silently
    duplicating a row."""
    existing = list_credentials(db, user_id)
    options = generate_registration_options(
        rp_id=rp_id_for_host(host),
        rp_name=RP_NAME,
        user_id=str(user_id).encode('utf-8'),
        user_name=username,
        authenticator_selection=AuthenticatorSelectionCriteria(
            resident_key=ResidentKeyRequirement.REQUIRED,
            user_verification=UserVerificationRequirement.PREFERRED,
        ),
        exclude_credentials=[
            PublicKeyCredentialDescriptor(id=base64url_to_bytes(c['credential_id']))
            for c in existing
        ],
    )
    return options_to_json(options), base64.b64encode(options.challenge).decode('ascii')


def verify_registration(credential, expected_challenge_b64, host, scheme):
    """Verify a completed registration ceremony. `credential` is the JSON
    dict the client posted (from `navigator.credentials.create()`). Raises
    the `webauthn` library's own exceptions on failure -- callers catch
    broadly and flash a generic error; there's no user-actionable detail to
    surface."""
    return verify_registration_response(
        credential=credential,
        expected_challenge=base64.b64decode(expected_challenge_b64),
        expected_rp_id=rp_id_for_host(host),
        expected_origin=origin_for_request(scheme, host),
    )


# ── Authentication ceremony ─────────────────────────────────────────────────

def build_authentication_options(host):
    """Options for `navigator.credentials.get()`. Deliberately no
    `allow_credentials` -- a discoverable/resident credential means the
    browser resolves which registered passkey (and thus which account) to
    offer, so the server doesn't need to know who's signing in yet."""
    options = generate_authentication_options(
        rp_id=rp_id_for_host(host),
        user_verification=UserVerificationRequirement.PREFERRED,
    )
    return options_to_json(options), base64.b64encode(options.challenge).decode('ascii')


def verify_authentication(db, credential, expected_challenge_b64, host, scheme):
    """Verify a completed authentication ceremony and return the matched
    `user_webauthn_credentials` row (bumping its `sign_count` /
    `last_used_at`), or None if `credential`'s id isn't registered to
    anyone. Raises (via the `webauthn` library) on a bad signature /
    challenge / origin."""
    cred_id = credential.get('id') if isinstance(credential, dict) else None
    row = find_credential_by_id(db, cred_id) if cred_id else None
    if not row:
        return None
    verification = verify_authentication_response(
        credential=credential,
        expected_challenge=base64.b64decode(expected_challenge_b64),
        expected_rp_id=rp_id_for_host(host),
        expected_origin=origin_for_request(scheme, host),
        credential_public_key=base64url_to_bytes(row['public_key']),
        credential_current_sign_count=row['sign_count'],
    )
    touch_credential(db, row['id'], verification.new_sign_count)
    return row


# ── DB helpers ───────────────────────────────────────────────────────────────

def list_credentials(db, user_id):
    """Every passkey registered to `user_id`, oldest first -- drives the
    Account page's list + the exclude-list at registration."""
    return db.execute(
        'SELECT id, user_id, credential_id, nickname, created_at, last_used_at '
        'FROM user_webauthn_credentials WHERE user_id = ? ORDER BY created_at',
        (user_id,),
    ).fetchall()


def find_credential_by_id(db, credential_id_b64url):
    return db.execute(
        'SELECT id, user_id, credential_id, public_key, sign_count '
        'FROM user_webauthn_credentials WHERE credential_id = ?',
        (credential_id_b64url,),
    ).fetchone()


def add_credential(db, user_id, credential_id_b64url, public_key: bytes, sign_count, nickname):
    """Does not commit; the caller owns the transaction boundary (mirrors
    mfa.start_enrollment)."""
    db.execute(
        'INSERT INTO user_webauthn_credentials '
        '(user_id, credential_id, public_key, sign_count, nickname) '
        'VALUES (?, ?, ?, ?, ?)',
        (user_id, credential_id_b64url, bytes_to_base64url(public_key), sign_count, nickname),
    )


def touch_credential(db, row_id, new_sign_count) -> None:
    db.execute(
        'UPDATE user_webauthn_credentials SET sign_count = ?, last_used_at = NOW() '
        'WHERE id = ?',
        (new_sign_count, row_id),
    )


def delete_credential(db, user_id, credential_row_id) -> None:
    """Scoped to `user_id` so one athlete can't delete another's row by
    guessing an id."""
    db.execute(
        'DELETE FROM user_webauthn_credentials WHERE id = ? AND user_id = ?',
        (credential_row_id, user_id),
    )
