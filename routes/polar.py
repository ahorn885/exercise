"""Polar AccessLink integration — second real OAuth provider on `provider_auth`.

Three endpoints, matching the COROS pattern (routes/coros.py):

- `GET  /polar/oauth/start`     — generates a CSRF state token, stashes it in
                                  the session, and redirects to Polar's
                                  authorize URL.
- `GET  /polar/oauth/callback`  — receives `?code=…&state=…`. Exchanges code
                                  for tokens (HTTP Basic auth with
                                  client_id:client_secret), POSTs `/v3/users`
                                  to register the partner-user relationship,
                                  persists via `provider_auth.upsert_auth`,
                                  records the OAuth-scope ack, and redirects
                                  to `return_to?polar_connected=1`.
- `POST /polar/webhook`         — Polar push handler. Verifies the
                                  `Polar-Webhook-Signature` HMAC-SHA256 header
                                  against `POLAR_WEBHOOK_SECRET` (separate
                                  from CLIENT_SECRET), records to
                                  `webhook_events`, and dispatches to
                                  `routes.polar_ingest.ingest_event` for the
                                  transaction-fetch handshake.

Polar-specific shape differences vs COROS (per PR2 handoff §5.1 Option C):

- **Tokens don't expire** (Polar AccessLink docs §3). `expires_in` in the
  token response is a nominal-large value; we record it as
  `token_expires_at` if present (defensive) but the refresh path is not
  exercised by Polar. No `refresh_token` is issued.
- **Registration call** required after token exchange: POST `/v3/users`
  with body `{"member-id": <our-user-id>}` and Bearer access_token. Polar
  responds 200 (created) or 409 (already registered) — both are success.
  Only after that call returns do we flip `status=active` +
  `registered_at=NOW()`.
- **Webhook signature** is HMAC-SHA256 hex of the raw body using a
  *separate* `POLAR_WEBHOOK_SECRET` env var (Polar issues this when the
  webhook URL is registered via their partner API; it is NOT the OAuth
  client_secret). Header name: `Polar-Webhook-Signature`.
- **Webhook delivers notifications, not data.** Each event names a
  resource (`event`, `user_id`, `entity_id`/`url`). Ingestion fetches the
  named resource via the AccessLink read API; for EXERCISE the read is
  transaction-based (POST → GET → PUT-commit).

Pre-deploy verification (PR3 §5.0): the AccessLink URL surface below is
the documented public API as of 2026-05; if Polar has rotated anything
(token endpoint shape, header names, payload field names), override via
the `POLAR_*_URL` env vars and update the response parsing.
"""
from __future__ import annotations

import hashlib
import hmac
import json
import os
import secrets
import urllib.parse
from datetime import datetime, timedelta, timezone

import requests
from flask import (
    Blueprint, abort, current_app, jsonify, redirect, request, session, url_for,
)

from database import get_db
from routes import provider_auth as pa
from routes.auth import current_user_id

bp = Blueprint('polar', __name__, url_prefix='/polar')

# Polar AccessLink surface. Override via env if Polar rotates the public
# host or version paths.
_POLAR_AUTH_URL = os.environ.get(
    'POLAR_AUTH_URL', 'https://flow.polar.com/oauth2/authorization',
)
_POLAR_TOKEN_URL = os.environ.get(
    'POLAR_TOKEN_URL', 'https://polarremote.com/v2/oauth2/token',
)
_POLAR_API_URL = os.environ.get(
    'POLAR_API_URL', 'https://www.polaraccesslink.com',
)

# Scope set requested at OAuth time. Polar's AccessLink scope token is
# `accesslink.read_all`. Bump _POLAR_SCOPE_VERSION when this changes so
# disclosure_acknowledgments re-keys.
_POLAR_SCOPES = 'accesslink.read_all'
_POLAR_SCOPE_VERSION = '2026-05-14'

# Polar tokens are documented as long-lived ("don't expire" per Integration
# v4 §4.1). We still record a far-future expiry if the token response
# carries `expires_in` so the column reflects reality; if absent, leave
# NULL.
_POLAR_DEFAULT_TTL = timedelta(days=3650)

# Session keys (distinct from COROS's so a concurrent multi-provider connect
# flow doesn't clobber state).
_OAUTH_STATE = 'polar_oauth_state'
_OAUTH_RETURN_TO = 'polar_oauth_return_to'


# ── OAuth initiation ──────────────────────────────────────────────────

@bp.route('/oauth/start', methods=['GET'])
def oauth_start():
    """Generate state token, stash + same-origin-guarded return_to, bounce
    to Polar's authorize URL."""
    if current_user_id() is None:
        return redirect(url_for('auth.login', next=request.url))

    client_id = os.environ.get('POLAR_CLIENT_ID')
    if not client_id:
        current_app.logger.error('POLAR_CLIENT_ID not configured')
        abort(503)

    state = secrets.token_urlsafe(32)
    session[_OAUTH_STATE] = state
    return_to = request.args.get('return_to') or '/'
    if not return_to.startswith('/') or return_to.startswith('//'):
        return_to = '/'
    session[_OAUTH_RETURN_TO] = return_to

    redirect_uri = url_for('polar.oauth_callback', _external=True)
    params = {
        'response_type': 'code',
        'client_id': client_id,
        'redirect_uri': redirect_uri,
        'scope': _POLAR_SCOPES,
        'state': state,
    }
    return redirect(f'{_POLAR_AUTH_URL}?{urllib.parse.urlencode(params)}')


# ── OAuth callback ────────────────────────────────────────────────────

@bp.route('/oauth/callback', methods=['GET'])
def oauth_callback():
    """Polar redirects back here with `?code=…&state=…`. Exchange code,
    register the partner-user, persist, and bounce to return_to."""
    user_id = current_user_id()
    if user_id is None:
        return redirect(url_for('auth.login'))

    expected_state = session.pop(_OAUTH_STATE, None)
    return_to = session.pop(_OAUTH_RETURN_TO, '/')
    received_state = request.args.get('state')
    if not expected_state or not received_state or not hmac.compare_digest(
        expected_state, received_state,
    ):
        current_app.logger.warning('Polar OAuth state mismatch for user %s', user_id)
        abort(400)

    if 'error' in request.args:
        sep = '&' if '?' in return_to else '?'
        return redirect(
            f'{return_to}{sep}polar_oauth_error={request.args.get("error")}'
        )

    code = request.args.get('code')
    if not code:
        abort(400)

    client_id = os.environ.get('POLAR_CLIENT_ID')
    client_secret = os.environ.get('POLAR_CLIENT_SECRET')
    if not client_id or not client_secret:
        current_app.logger.error('Polar client credentials not configured')
        abort(503)

    redirect_uri = url_for('polar.oauth_callback', _external=True)

    # Polar AccessLink token endpoint requires HTTP Basic auth (client_id +
    # client_secret), not the body-credential pattern COROS uses.
    try:
        resp = requests.post(
            _POLAR_TOKEN_URL,
            data={
                'grant_type': 'authorization_code',
                'code': code,
                'redirect_uri': redirect_uri,
            },
            auth=(client_id, client_secret),
            headers={'Accept': 'application/json'},
            timeout=10,
        )
        resp.raise_for_status()
        token_data = resp.json()
    except requests.RequestException as exc:
        current_app.logger.exception('Polar token exchange failed: %s', exc)
        abort(502)

    access_token = token_data.get('access_token')
    # Polar AccessLink: x_user_id is the Polar-side user identifier, returned
    # alongside the access_token. Accept variants in case of doc rotation.
    polar_user_id = (
        token_data.get('x_user_id')
        or token_data.get('polar-user-id')
        or token_data.get('user_id')
    )
    if not access_token or not polar_user_id:
        current_app.logger.error('Polar token response missing fields: %s', token_data)
        abort(502)

    expires_in = token_data.get('expires_in')
    if isinstance(expires_in, (int, float)) and expires_in > 0:
        token_expires_at = datetime.now(timezone.utc) + timedelta(seconds=int(expires_in))
    else:
        token_expires_at = datetime.now(timezone.utc) + _POLAR_DEFAULT_TTL

    db = get_db()
    # Stage one: record the auth row with pending_backfill so a failure in
    # the /v3/users registration call doesn't lose the access_token. The
    # registration call is retryable later from a maintenance route.
    pa.upsert_auth(
        db,
        user_id=user_id,
        provider='polar',
        access_token=access_token,
        token_expires_at=token_expires_at,
        provider_user_id=str(polar_user_id),
        scopes=_POLAR_SCOPES,
        status=pa.STATUS_PENDING_BACKFILL,
    )

    # Stage two: register the partner-user relationship. Polar requires this
    # before any /v3/users/<id>/* call will succeed. 200 = created, 409 =
    # already registered (re-connect path); both are success.
    register_ok = _register_polar_user(access_token, user_id)
    if register_ok:
        pa.upsert_auth(
            db,
            user_id=user_id,
            provider='polar',
            status=pa.STATUS_ACTIVE,
            registered_at=datetime.now(timezone.utc),
        )
    else:
        pa.upsert_auth(
            db,
            user_id=user_id,
            provider='polar',
            status=pa.STATUS_ERROR,
        )

    pa.record_oauth_scope_ack(
        db,
        user_id=user_id,
        provider='polar',
        scopes_granted=_POLAR_SCOPES,
        version_id=_POLAR_SCOPE_VERSION,
    )

    sep = '&' if '?' in return_to else '?'
    flag = 'polar_connected=1' if register_ok else 'polar_register_error=1'
    return redirect(f'{return_to}{sep}{flag}')


def _register_polar_user(access_token: str, user_id: int) -> bool:
    """POST /v3/users with `{member-id: <user_id>}` to activate the
    partner-user relationship. Returns True on 200 or 409 (already
    registered); False on other errors."""
    try:
        resp = requests.post(
            f'{_POLAR_API_URL}/v3/users',
            json={'member-id': str(user_id)},
            headers={
                'Authorization': f'Bearer {access_token}',
                'Accept': 'application/json',
                'Content-Type': 'application/json',
            },
            timeout=10,
        )
    except requests.RequestException as exc:
        current_app.logger.exception('Polar /v3/users registration failed: %s', exc)
        return False
    if resp.status_code in (200, 201, 409):
        return True
    current_app.logger.error(
        'Polar /v3/users registration returned %s: %s',
        resp.status_code, resp.text[:200],
    )
    return False


# ── Webhook ───────────────────────────────────────────────────────────

@bp.route('/webhook', methods=['GET', 'POST'])
def webhook():
    """Polar push handler. GETs (Polar's registration probe) return 200;
    POSTs verify the `Polar-Webhook-Signature` HMAC, record to
    `webhook_events`, and dispatch to ingestion when the signature is
    good.

    Per Polar docs §6 the webhook URL must respond 200 to the registration
    probe (an unsigned GET). For signed POSTs we return 200 on success and
    401 on signature failure so audit logs stay parseable.
    """
    if request.method == 'GET':
        return jsonify(status='ok'), 200

    webhook_secret = os.environ.get('POLAR_WEBHOOK_SECRET')
    raw_body = request.get_data() or b''
    received_sig = request.headers.get('Polar-Webhook-Signature') or ''
    sig_ok = False
    if webhook_secret:
        expected_sig = hmac.new(
            webhook_secret.encode('utf-8'),
            raw_body,
            hashlib.sha256,
        ).hexdigest()
        sig_ok = hmac.compare_digest(expected_sig, received_sig)

    try:
        payload = json.loads(raw_body.decode('utf-8')) if raw_body else {}
    except (json.JSONDecodeError, UnicodeDecodeError):
        payload = {}

    # Polar webhook delivery shape is documented as a single event per
    # POST. Older partner docs show a `available-notifications` batch
    # wrapper; accept either to be defensive.
    notifications = _extract_notifications(payload)
    db = get_db()

    if not notifications:
        # Polar can send the empty-list probe to verify the endpoint is
        # alive. Record once for audit; no dispatch.
        db.execute(
            'INSERT INTO webhook_events '
            '(provider, event_type, provider_user_id, entity_id, user_id, '
            ' payload, signature_ok, received_at) '
            'VALUES (?, ?, ?, ?, ?, ?, ?, NOW())',
            ('polar', None, None, None, None,
             raw_body.decode('utf-8', errors='replace'), sig_ok),
        )
        db.commit()
        if not sig_ok and webhook_secret:
            return jsonify(status='signature invalid'), 401
        return jsonify(status='ok'), 200

    if not sig_ok:
        # Audit-and-reject: insert one row per notification with signature_ok
        # so the audit log stays per-event, but skip dispatch. Don't fall
        # through to ingestion.
        for n in notifications:
            db.execute(
                'INSERT INTO webhook_events '
                '(provider, event_type, provider_user_id, entity_id, user_id, '
                ' payload, signature_ok, received_at) '
                'VALUES (?, ?, ?, ?, ?, ?, ?, NOW())',
                ('polar', n.get('event'), str(n.get('user_id', '')) or None,
                 _entity_id_of(n), None,
                 raw_body.decode('utf-8', errors='replace'), False),
            )
        db.commit()
        return jsonify(status='signature invalid'), 401

    # Signed path — record + dispatch each notification.
    from routes import polar_ingest
    for n in notifications:
        provider_user_id = str(n.get('user_id', '')) or None
        auth_row = (
            pa.get_auth_by_provider_user_id(db, 'polar', provider_user_id)
            if provider_user_id else None
        )
        user_id = auth_row['user_id'] if auth_row else None
        cur = db.execute(
            'INSERT INTO webhook_events '
            '(provider, event_type, provider_user_id, entity_id, user_id, '
            ' payload, signature_ok, received_at) '
            'VALUES (?, ?, ?, ?, ?, ?, ?, NOW()) RETURNING id',
            ('polar', n.get('event'), provider_user_id, _entity_id_of(n),
             user_id, json.dumps(n), True),
        )
        event_id = cur.fetchone()['id']
        db.commit()

        if user_id is None or auth_row is None:
            # Unmapped — keep the row, mark processed with an explanatory
            # error so it isn't retried by /admin/webhooks reprocess.
            db.execute(
                'UPDATE webhook_events SET processed_at = NOW(), error = ? WHERE id = ?',
                ('polar user_id not mapped to local user', event_id),
            )
            db.commit()
            continue

        try:
            polar_ingest.ingest_event(
                db, event_id, user_id, n, auth_row['access_token'],
            )
            db.execute(
                'UPDATE webhook_events SET processed_at = NOW() WHERE id = ?',
                (event_id,),
            )
            db.commit()
        except Exception as exc:  # noqa: BLE001 — log + record + continue
            current_app.logger.exception(
                'Polar ingestion failed for event %s', event_id,
            )
            db.execute(
                'UPDATE webhook_events SET processed_at = NOW(), error = ? WHERE id = ?',
                (str(exc)[:500], event_id),
            )
            db.commit()
            # Still return 200 — durable copy in webhook_events, same
            # COROS-style retry-storm avoidance.

    return jsonify(status='ok'), 200


# ── Payload introspection ─────────────────────────────────────────────

def _extract_notifications(payload: dict) -> list[dict]:
    """Normalise Polar webhook delivery shape to a list of per-event
    dicts. Supports the documented single-event push shape and the
    older `available-notifications` batch wrapper."""
    if not isinstance(payload, dict):
        return []
    if 'available-notifications' in payload and isinstance(
        payload['available-notifications'], list,
    ):
        return [n for n in payload['available-notifications'] if isinstance(n, dict)]
    if 'event' in payload:
        return [payload]
    return []


def _entity_id_of(notification: dict) -> str | None:
    """Pull the dedup key out of a Polar notification. `entity_id` is the
    documented field; `url` is the AccessLink resource URI which uniquely
    identifies the entity for the data pull. Either is acceptable."""
    return (
        notification.get('entity_id')
        or notification.get('entity-id')
        or notification.get('url')
        or None
    )
