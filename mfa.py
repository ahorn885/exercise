"""TOTP (RFC 6238) two-factor authentication — issue #265.

Two layers live here:

  Pure crypto (no DB, unit-testable in `tests/test_mfa.py`):
    generate_secret / provisioning_uri / verify_code / qr_svg

  DB helpers (take an open `db`, operate on the single-row-per-user
  `user_totp` table):
    get_totp / is_enabled / start_enrollment / confirm_enrollment / disable

State machine for a user's `user_totp` row:

    row absent            → 2FA not set up
    confirmed_at IS NULL  → enrollment pending (secret issued, awaiting the
                            first valid code from the authenticator app)
    confirmed_at set      → 2FA active (login challenges this user)

Recovery (per Andy, 2026-06-21): a completed password reset
(`routes/auth.reset`) clears the row, so a lost authenticator is recovered
through the existing email reset flow rather than one-time backup codes.
"""

import pyotp

ISSUER = 'AIDSTATION'

# pyotp's default `valid_window` is 0 (only the current 30s step). ±1 accepts
# the adjacent step on each side — tolerates modest client/server clock skew
# and the common case of a user typing a code as it rolls over. Still only a
# 90s window, and the challenge endpoint is rate-limited, so the brute-force
# surface stays negligible.
VALID_WINDOW = 1


# ── Pure crypto ──────────────────────────────────────────────────────────────

def generate_secret() -> str:
    """A fresh base32 TOTP secret (the value an authenticator app stores)."""
    return pyotp.random_base32()


def provisioning_uri(secret: str, account_name: str) -> str:
    """The `otpauth://totp/...` URI encoded into the enrollment QR code and
    offered as a manual fallback. `account_name` is the athlete's email (or
    username) so the app entry reads `AIDSTATION (you@example.com)`."""
    return pyotp.TOTP(secret).provisioning_uri(
        name=account_name or 'athlete', issuer_name=ISSUER
    )


def verify_code(secret: str, code: str, *, valid_window: int = VALID_WINDOW) -> bool:
    """True iff `code` is a currently-valid 6-digit TOTP for `secret`.

    Defensive on input — strips spaces, rejects non-digits, and never raises
    (a malformed secret/code returns False rather than 500-ing the login)."""
    if not secret or not code:
        return False
    code = code.strip().replace(' ', '')
    if not code.isdigit():
        return False
    try:
        return pyotp.TOTP(secret).verify(code, valid_window=valid_window)
    except Exception:
        return False


def qr_svg(uri: str):
    """Inline SVG markup for `uri`, or None when the optional `qrcode` dep
    isn't installed (the setup page falls back to the manual key + URI).

    SVG — not a PNG `data:` URI — keeps the page CSP-clean: it's plain markup
    embedded in the document, so it needs neither a script nonce nor an
    `img-src data:` grant."""
    try:
        import io
        import qrcode
        import qrcode.image.svg

        img = qrcode.make(uri, image_factory=qrcode.image.svg.SvgPathImage)
        buf = io.BytesIO()
        img.save(buf)
        return buf.getvalue().decode('utf-8')
    except Exception:
        return None


# ── DB helpers ───────────────────────────────────────────────────────────────

def get_totp(db, user_id):
    """The user's `user_totp` row (or None if 2FA was never set up)."""
    return db.execute(
        'SELECT user_id, secret, created_at, confirmed_at '
        'FROM user_totp WHERE user_id = ?',
        (user_id,),
    ).fetchone()


def is_enabled(db, user_id) -> bool:
    """True iff the user has *active* (confirmed) 2FA — the flag the login
    flow and the profile UI gate on. A pending-but-unconfirmed enrollment
    returns False (it doesn't challenge logins yet)."""
    row = get_totp(db, user_id)
    return bool(row and row['confirmed_at'])


def start_enrollment(db, user_id) -> str:
    """Issue (or re-issue) a *pending* secret for `user_id` and return it.

    UPSERT so a user who refreshes the setup page mid-enrollment rotates to a
    fresh secret cleanly. Callers must refuse to start when 2FA is already
    active (see `routes/profile.totp_setup`) — this would otherwise reset a
    live `confirmed_at` back to NULL. Does not commit; the caller owns the
    transaction boundary."""
    secret = generate_secret()
    db.execute(
        'INSERT INTO user_totp (user_id, secret, confirmed_at) '
        'VALUES (?, ?, NULL) '
        'ON CONFLICT (user_id) DO UPDATE SET '
        '    secret = EXCLUDED.secret, '
        '    created_at = NOW(), '
        '    confirmed_at = NULL',
        (user_id, secret),
    )
    return secret


def confirm_enrollment(db, user_id) -> None:
    """Flip a pending enrollment to active. No-op once already confirmed."""
    db.execute(
        'UPDATE user_totp SET confirmed_at = NOW() '
        'WHERE user_id = ? AND confirmed_at IS NULL',
        (user_id,),
    )


def disable(db, user_id) -> None:
    """Remove 2FA for `user_id` (clears both pending and active rows). Used by
    the profile disable action and by the password-reset recovery path."""
    db.execute('DELETE FROM user_totp WHERE user_id = ?', (user_id,))
