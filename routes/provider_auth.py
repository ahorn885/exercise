"""Provider-agnostic helpers for the `provider_auth` table and the
disclosure-acknowledgment writes that every OAuth callback performs.

Per `Athlete_Data_Integration_Spec_v4.md` §4.1 (status enum, UPSERT-by
`(user_id, provider)`, webhook_token rotation Pattern A) and
`Onboarding_D58_Design_v1.md` §7.3 (per-provider OAuth scope ack rows in
Account Config 3 / `disclosure_acknowledgments`).

Provider-specific OAuth handshakes (the code-for-token exchange against
the provider's `/token` endpoint, the request signature for webhooks)
live in `routes/<provider>.py`. This module owns the storage shape only.

Status convention: `active / revoked / error / pending_backfill /
migrating` (Integration v4 §4.1). The v5 / D-58 design docs use
"connected" colloquially — that maps to `STATUS_ACTIVE` here. The
on-disk schema does not have a `connected` value.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any, Mapping, Optional

import requests

STATUS_ACTIVE = 'active'
STATUS_REVOKED = 'revoked'
STATUS_ERROR = 'error'
STATUS_PENDING_BACKFILL = 'pending_backfill'
STATUS_MIGRATING = 'migrating'

_VALID_STATUSES = frozenset({
    STATUS_ACTIVE, STATUS_REVOKED, STATUS_ERROR,
    STATUS_PENDING_BACKFILL, STATUS_MIGRATING,
})

# Columns clients are allowed to set via upsert_auth(). Excludes id /
# created_at (system-managed) and updated_at (bumped on every write).
_UPSERTABLE_COLUMNS = (
    'access_token', 'refresh_token', 'token_expires_at',
    'session_blob', 'provider_user_id', 'scopes',
    'webhook_token', 'status', 'registered_at',
)


def upsert_auth(
    db: Any,
    user_id: int,
    provider: str,
    **fields: Any,
) -> int:
    """UPSERT a `provider_auth` row keyed on `(user_id, provider)`.

    Returns the row id. Unknown field names raise ValueError so caller
    typos surface loudly instead of silently dropping. `status`, when
    supplied, is validated against the enum.

    Webhook handlers call this on every event with the current
    `webhook_token` (Pattern A — UPSERT every event regardless of
    rotation). The cost is one indexed row write; the alternative
    (Pattern B: read-then-compare-then-maybe-write) doubles latency to
    save a write that's already negligible.
    """
    bad = set(fields) - set(_UPSERTABLE_COLUMNS)
    if bad:
        raise ValueError(f'Unknown provider_auth columns: {sorted(bad)}')
    if 'status' in fields and fields['status'] not in _VALID_STATUSES:
        raise ValueError(f'Invalid status {fields["status"]!r}; expected one of {sorted(_VALID_STATUSES)}')

    columns = ['user_id', 'provider'] + list(fields)
    placeholders = ', '.join(['?'] * len(columns))
    update_cols = list(fields) + ['updated_at']
    update_set = ', '.join(f'{c} = EXCLUDED.{c}' for c in fields)
    if update_set:
        update_set += ', updated_at = NOW()'
    else:
        update_set = 'updated_at = NOW()'

    sql = (
        f'INSERT INTO provider_auth ({", ".join(columns)}) '
        f'VALUES ({placeholders}) '
        f'ON CONFLICT (user_id, provider) DO UPDATE SET {update_set} '
        f'RETURNING id'
    )
    cur = db.execute(sql, [user_id, provider] + [fields[c] for c in fields])
    row = cur.fetchone()
    db.commit()
    return row['id'] if row else None


def get_auth(db: Any, user_id: int, provider: str) -> Optional[Mapping[str, Any]]:
    """Fetch the `(user_id, provider)` row, or None if not present."""
    cur = db.execute(
        'SELECT * FROM provider_auth WHERE user_id = ? AND provider = ?',
        (user_id, provider),
    )
    return cur.fetchone()


def get_auth_by_provider_user_id(
    db: Any, provider: str, provider_user_id: str,
) -> Optional[Mapping[str, Any]]:
    """Reverse-lookup used by webhook handlers to map a provider-side
    user id to a local user. Returns None if no row matches; callers
    must handle the unmapped-event case (typically: write the
    `webhook_events` row with `user_id = NULL` for later resolution).
    """
    cur = db.execute(
        'SELECT * FROM provider_auth WHERE provider = ? AND provider_user_id = ?',
        (provider, provider_user_id),
    )
    return cur.fetchone()


def set_status(db: Any, auth_id: int, status: str) -> None:
    """Status transitions per Integration v4 §4.1. Raises on unknown
    status; callers using a constant from this module are safe."""
    if status not in _VALID_STATUSES:
        raise ValueError(f'Invalid status {status!r}; expected one of {sorted(_VALID_STATUSES)}')
    db.execute(
        'UPDATE provider_auth SET status = ?, updated_at = NOW() WHERE id = ?',
        (status, auth_id),
    )
    db.commit()


def disconnect(db: Any, user_id: int, provider: str) -> bool:
    """Athlete-initiated disconnect from Account Config 1.

    Flips status to `revoked` and nulls every credential-bearing column
    on the `(user_id, provider)` row. Preserves `scopes` and
    `registered_at` (audit), and `token_expires_at` (informational; gets
    overwritten on re-connect).

    `provider_user_id` is nulled deliberately: provider webhooks identify
    the local user via `get_auth_by_provider_user_id`, and the existing
    handlers do not gate on `status`. Nulling the reverse-lookup key
    causes any in-flight webhook to land in the unmapped-event branch
    (audit row written, no ingest), which is the correct post-disconnect
    behaviour without having to thread a status check through every
    handler. The raw provider-side identifier is still preserved in
    `webhook_events.payload` if forensic recovery is ever needed.

    Returns True if a row was updated, False if no `(user_id, provider)`
    row existed. Caller can treat False as a no-op (the screen already
    showed the disconnect button on a non-existent row, or a double-tap
    raced).
    """
    cur = db.execute(
        'UPDATE provider_auth '
        'SET status = ?, '
        '    access_token = NULL, '
        '    refresh_token = NULL, '
        '    session_blob = NULL, '
        '    webhook_token = NULL, '
        '    provider_user_id = NULL, '
        '    updated_at = NOW() '
        'WHERE user_id = ? AND provider = ?',
        (STATUS_REVOKED, user_id, provider),
    )
    db.commit()
    return (cur.rowcount or 0) > 0


def rotate_webhook_token(
    db: Any, user_id: int, provider: str, webhook_token: str,
) -> None:
    """Pattern A rotation (Integration v4 §4.1). Wahoo issues a fresh
    `webhook_token` on every event; we write the latest value back
    unconditionally. UPSERT-shape so it works whether or not the
    `provider_auth` row exists yet (it should — OAuth callback creates
    it — but defensive UPSERT avoids a webhook-before-OAuth race)."""
    upsert_auth(db, user_id, provider, webhook_token=webhook_token)


# Refresh the access token this far ahead of its stored expiry (clock skew +
# in-flight request slack), so a token that's about to lapse mid-fetch is
# rotated first.
_REFRESH_SKEW = timedelta(minutes=5)


def _expiry_from_response(data: Mapping[str, Any]) -> Optional[datetime]:
    """Normalise the two expiry shapes providers return on a token grant: Strava
    sends `expires_at` (absolute epoch seconds), Whoop sends `expires_in`
    (seconds from now). Returns an aware UTC datetime, or None (long-lived)."""
    if data.get('expires_at'):
        return datetime.fromtimestamp(int(data['expires_at']), tz=timezone.utc)
    if data.get('expires_in'):
        return datetime.now(timezone.utc) + timedelta(seconds=int(data['expires_in']))
    return None


def refresh_access_token(
    db: Any, user_id: int, provider: str, *,
    token_url: str, client_id: Optional[str], client_secret: Optional[str],
) -> Optional[str]:
    """Run the OAuth2 refresh-token grant for `(user_id, provider)`, persist the
    rotated tokens, and return the new access token (None on failure).

    This is the refresh path Integration v4 §4.1 sketched but no provider had
    exercised (COROS/Polar tokens are long-lived) — Strava (~6h) and Whoop (~1h)
    expire, so the live ingest needs it. On any failure the row is flipped to
    `error` so the connect UI can prompt a re-auth. The provider rotates the
    refresh token on some grants; keep the new one, fall back to the old."""
    row = get_auth(db, user_id, provider)
    if not row or not row.get('refresh_token'):
        return None
    if not client_id or not client_secret:
        return None
    try:
        resp = requests.post(token_url, data={
            'grant_type': 'refresh_token',
            'refresh_token': row['refresh_token'],
            'client_id': client_id,
            'client_secret': client_secret,
        }, timeout=10)
        resp.raise_for_status()
        data = resp.json()
    except requests.RequestException:
        set_status(db, row['id'], STATUS_ERROR)
        return None
    access = data.get('access_token')
    if not access:
        set_status(db, row['id'], STATUS_ERROR)
        return None
    upsert_auth(
        db, user_id, provider,
        access_token=access,
        refresh_token=data.get('refresh_token') or row['refresh_token'],
        token_expires_at=_expiry_from_response(data),
        status=STATUS_ACTIVE,
    )
    return access


def get_fresh_access_token(
    db: Any, user_id: int, provider: str, *,
    token_url: str, client_id: Optional[str], client_secret: Optional[str],
) -> Optional[str]:
    """Return a usable access token for `(user_id, provider)`, refreshing first
    if the stored token is within `_REFRESH_SKEW` of expiry. Returns None if
    there's no active auth row. A row with no `token_expires_at` (COROS/Polar
    long-lived) returns its stored token unchanged."""
    row = get_auth(db, user_id, provider)
    if not row or row.get('status') != STATUS_ACTIVE:
        return None
    expires_at = row.get('token_expires_at')
    if expires_at is not None:
        if isinstance(expires_at, str):
            expires_at = datetime.fromisoformat(expires_at)
        if expires_at.tzinfo is None:
            expires_at = expires_at.replace(tzinfo=timezone.utc)
        if expires_at <= datetime.now(timezone.utc) + _REFRESH_SKEW:
            return refresh_access_token(
                db, user_id, provider,
                token_url=token_url, client_id=client_id, client_secret=client_secret,
            )
    return row.get('access_token')


def record_oauth_scope_ack(
    db: Any,
    user_id: int,
    provider: str,
    scopes_granted: str,
    version_id: Optional[str] = None,
    delivery_method: str = 'in_app',
) -> int:
    """Insert a row into `disclosure_acknowledgments` capturing the
    per-provider OAuth scope acknowledgment (D-58 §7.3, v5 Account
    Config 3). One row per OAuth flow; re-acknowledgment writes a new
    row. Query `MAX(acknowledged_at)` per `(user_id, disclosure_id)`
    to find current state.

    `disclosure_id` follows v5 Account Config 3's enum convention:
    `oauth_scope_<provider>`.
    """
    disclosure_id = f'oauth_scope_{provider}'
    cur = db.execute(
        'INSERT INTO disclosure_acknowledgments '
        '(user_id, disclosure_id, version_id, scopes_granted, delivery_method) '
        'VALUES (?, ?, ?, ?, ?) RETURNING id',
        (user_id, disclosure_id, version_id, scopes_granted, delivery_method),
    )
    row = cur.fetchone()
    db.commit()
    return row['id'] if row else None
