"""Identity-OAuth helpers — the durable "sign in with <provider>" linkage.

Distinct from routes/provider_auth.py, which owns the *revocable sync
credential* (the provider_auth row). This module owns provider_identity: the
login link that must survive a sync disconnect. provider_auth.disconnect()
deliberately nulls provider_user_id, so login can't ride on that table — see
Onboarding_OAuth_Signin_Design_v1 §2. The schema's
UNIQUE (provider, provider_user_id) is the real backstop for
one-provider-account → one-AIDSTATION-account; the helpers here check-then-act
inside the request for friendly errors, but the constraint is the guarantee
against a race.

Feature-gated: signin_enabled() (env PROVIDER_OAUTH_SIGNIN) keeps the whole
no-session sign-in/up path dark until each provider's profile payload is
verified live (Rule #14). Logged-in linking and the password flow are
unaffected by the flag.
"""
from __future__ import annotations

import os
import re
from typing import Any, Optional, Tuple

# Providers wired for identity sign-in. Garmin is intentionally absent: it has
# no OAuth (garth username/password; API paused), so it cannot authenticate a
# sign-in (design §4, decision #8). COROS/Polar/etc. expose weaker identity
# (opaque id, no profile/email) — add later if wanted.
SIGNIN_PROVIDERS = frozenset({'strava', 'wahoo', 'oura'})

_USERNAME_STRIP = re.compile(r'[^a-z0-9]+')
_MAX_USERNAME = 32  # users.username is 3–32 chars (routes/auth.register)


def signin_enabled() -> bool:
    """Master gate for the no-session 'sign in / sign up with <provider>'
    path. Off by default; flip PROVIDER_OAUTH_SIGNIN=1 once the provider's
    live profile payload is confirmed."""
    return os.environ.get('PROVIDER_OAUTH_SIGNIN', '').strip().lower() in (
        '1', 'true', 'yes', 'on',
    )


# Providers whose no-session branch is actually IMPLEMENTED and so can render a
# "Continue with <provider>" button. Oura is in SIGNIN_PROVIDERS by design but
# joins this list when its callback branch lands. (slug, label, start endpoint,
# client-id env var.)
_SIGNIN_BUTTONS = (
    ('strava', 'Strava', 'strava.oauth_start', 'STRAVA_CLIENT_ID'),
    ('wahoo', 'Wahoo', 'wahoo.oauth_start', 'WAHOO_CLIENT_ID'),
)


def enabled_signin_providers() -> list[dict]:
    """[{slug, label, endpoint}] for the buttons that should render on the
    auth pages: feature flag on AND the provider's client id configured.
    Returns [] when the flag is off, so the auth pages stay password-only."""
    if not signin_enabled():
        return []
    return [
        {'slug': slug, 'label': label, 'endpoint': endpoint}
        for slug, label, endpoint, id_env in _SIGNIN_BUTTONS
        if os.environ.get(id_env)
    ]


def get_identity(db: Any, provider: str, provider_user_id: Any) -> Optional[dict]:
    """The provider_identity row for `(provider, provider_user_id)`, or None.
    This is the login lookup: a hit means an existing account to sign into."""
    row = db.execute(
        'SELECT * FROM provider_identity WHERE provider = ? AND provider_user_id = ?',
        (provider, str(provider_user_id)),
    ).fetchone()
    return dict(row) if row else None


def get_username(db: Any, user_id: int) -> Optional[str]:
    """The account's username (for the session), or None if the row is gone."""
    row = db.execute('SELECT username FROM users WHERE id = ?', (user_id,)).fetchone()
    return row['username'] if row else None


def bump_last_login(db: Any, identity_id: int) -> None:
    db.execute(
        'UPDATE provider_identity SET last_login_at = NOW() WHERE id = ?',
        (identity_id,),
    )
    db.commit()


def count_login_methods(db: Any, user_id: int) -> int:
    """Independent ways `user_id` can authenticate: each linked provider
    identity + 1 if a password is set. Backs the last-method guard (design
    decision #9) so an athlete can't unlink themselves into a lockout."""
    n = db.execute(
        'SELECT COUNT(*) AS n FROM provider_identity WHERE user_id = ?', (user_id,)
    ).fetchone()['n']
    has_pw = db.execute(
        "SELECT 1 FROM users WHERE id = ? AND COALESCE(password_hash, '') <> ''",
        (user_id,),
    ).fetchone() is not None
    return n + (1 if has_pw else 0)


def link_identity(
    db: Any, user_id: int, provider: str, provider_user_id: Any,
    email_at_link: Optional[str] = None,
) -> Tuple[bool, str]:
    """Attach a provider identity to an already-authenticated `user_id`
    (design §6.2 — the only auto-link path).

    Returns (ok, reason):
      - (False, 'claimed_by_other') — identity already links a different
        account. Caller surfaces a flash; we never silently steal it.
      - (True, 'linked')            — inserted, or repointed this user's
        existing row for the provider to a new provider_user_id (e.g. the
        athlete connected a different Strava account). Idempotent.
    """
    pid = str(provider_user_id)
    existing = get_identity(db, provider, pid)
    if existing and existing['user_id'] != user_id:
        return False, 'claimed_by_other'
    # UNIQUE (user_id, provider) ⇒ at most one row per provider per user.
    # Update-then-insert covers both first link and re-point/refresh.
    cur = db.execute(
        'UPDATE provider_identity '
        'SET provider_user_id = ?, email_at_link = ?, last_login_at = NOW() '
        'WHERE user_id = ? AND provider = ?',
        (pid, email_at_link, user_id, provider),
    )
    if (cur.rowcount or 0) == 0:
        db.execute(
            'INSERT INTO provider_identity '
            '(user_id, provider, provider_user_id, email_at_link, last_login_at) '
            'VALUES (?, ?, ?, ?, NOW())',
            (user_id, provider, pid, email_at_link),
        )
    db.commit()
    return True, 'linked'


def unlink_identity(db: Any, user_id: int, provider: str) -> Tuple[bool, str]:
    """Remove a provider login link (Account Config 1 "Remove sign-in",
    distinct from D-58 "Disconnect" which stops sync). Refuses to remove the
    athlete's last login method (design decision #9).

    Returns (ok, reason): (False, 'last_method') when blocked; (True/False,
    'removed') otherwise (False = no such row, a harmless no-op)."""
    has = db.execute(
        'SELECT 1 FROM provider_identity WHERE user_id = ? AND provider = ?',
        (user_id, provider),
    ).fetchone() is not None
    if has and count_login_methods(db, user_id) <= 1:
        return False, 'last_method'
    cur = db.execute(
        'DELETE FROM provider_identity WHERE user_id = ? AND provider = ?',
        (user_id, provider),
    )
    db.commit()
    return ((cur.rowcount or 0) > 0), 'removed'


def _slugify_username(hint: Optional[str]) -> str:
    """Provider display name → a username seed: lowercase alphanumerics only."""
    return _USERNAME_STRIP.sub('', (hint or '').strip().lower())[:24]


def _unique_username(db: Any, hint: Optional[str]) -> str:
    """A free username derived from `hint`, with a numeric suffix on collision
    (`alex`, `alex2`, …). Guarantees the 3–32 char bound auth.register uses."""
    base = _slugify_username(hint)
    if len(base) < 3:
        base = (base + 'athlete')[:24]
    candidate, n = base, 1
    while db.execute(
        'SELECT 1 FROM users WHERE username = ?', (candidate,)
    ).fetchone():
        n += 1
        suffix = str(n)
        candidate = f'{base[:_MAX_USERNAME - len(suffix)]}{suffix}'
    return candidate


def create_signin_user(
    db: Any, *, provider: str, provider_user_id: Any,
    email: Optional[str] = None, display_name: Optional[str] = None,
    username_hint: Optional[str] = None, email_verified: bool = False,
) -> Tuple[int, str]:
    """Create a passwordless account from a provider sign-in and link the
    identity (design §6.1, new-athlete branch). Returns (user_id, username).

    Mirrors auth.register's current_rx seed so /rx isn't blank on first load.
    Email is stored on the account only when it won't collide with an existing
    one — a colliding email is DROPPED (account created with NULL email)
    rather than attached to a second account (no silent merge, decision #5).
    The raw provider email is still recorded in provider_identity.email_at_link
    for audit either way.
    """
    username = _unique_username(db, username_hint or display_name or provider)
    account_email = email
    if account_email and db.execute(
        'SELECT 1 FROM users WHERE LOWER(email) = LOWER(?)', (account_email,)
    ).fetchone():
        account_email = None  # collision → no email; athlete can add + verify later
    user_id = db.execute(
        'INSERT INTO users (username, email, password_hash, display_name, email_verified) '
        'VALUES (?, ?, NULL, ?, ?) RETURNING id',
        (username, account_email, display_name,
         email_verified if account_email else False),
    ).fetchone()['id']

    # Seed current_rx so /rx isn't blank (mirrors auth.register). Don't block
    # account creation on a seed failure — init_db retries.
    try:
        from init_db import _seed_current_rx_for_user
        is_pg = bool(os.environ.get('DATABASE_URL'))
        _seed_current_rx_for_user(db, user_id, is_postgres=is_pg)
    except Exception:
        pass

    db.execute(
        'INSERT INTO provider_identity '
        '(user_id, provider, provider_user_id, email_at_link, last_login_at) '
        'VALUES (?, ?, ?, ?, NOW())',
        (user_id, provider, str(provider_user_id), email),
    )
    db.commit()
    return user_id, username
