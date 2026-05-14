"""COROS integration — first real OAuth provider on `provider_auth`.

Three endpoints:

- `GET  /coros/oauth/start`     — kicks off the OAuth flow. Generates a
                                  CSRF state token, stores it in the
                                  session, and redirects the user to
                                  the COROS authorization URL.
- `GET  /coros/oauth/callback`  — receives `?code=…&state=…` from COROS.
                                  Exchanges the code for tokens, stores
                                  via `provider_auth.upsert_auth`,
                                  records the per-provider scope ack in
                                  Account Config 3, and redirects per
                                  D-58 §3 (mid-onboarding → onboarding
                                  step 3; post-onboarding → Account
                                  Config 1 management).
- `POST /coros/webhook`         — COROS push from their servers. Verifies
                                  the `client` + `secret` headers,
                                  records to `webhook_events`, and (on
                                  successful signature) dispatches to
                                  `routes.coros_ingest.ingest_event`.

URL convention deviation: the OAuth callback lives at
`/coros/oauth/callback`, not `/auth/coros/callback` (the stub
convention in `routes/oauth_callbacks.py`). The redirect_uri registered
in COROS's developer portal must match this. The stub registry no
longer claims `coros` so there's no routing conflict.

CSRF: the webhook is exempted in `app.py` (server-to-server push, no
browser session). The OAuth callback is browser-initiated GET only —
no CSRF concern at the Flask level; OAuth state-parameter validation
provides the equivalent guarantee against CSRF-style request forgery.

Pre-deploy verification (§5.0 sanity check #1): COROS's actual OAuth
endpoint URLs, token-exchange request shape, and webhook signature
method need to be confirmed against current COROS Open API docs before
this ships. The placeholders below match the documented public API as
of 2026-05; if COROS has changed surface since then, override via the
COROS_AUTH_URL / COROS_TOKEN_URL env vars and update the token-response
parsing.
"""
from __future__ import annotations

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

bp = Blueprint('coros', __name__, url_prefix='/coros')

# COROS Open API surface. Per Integration v4 §3 + PROVIDERS_SCHEMA.md
# §3 env-var convention. Override via env if COROS rotates the public
# host or version paths.
_COROS_AUTH_URL = os.environ.get(
    'COROS_AUTH_URL', 'https://open.coros.com/oauth2/authorize',
)
_COROS_TOKEN_URL = os.environ.get(
    'COROS_TOKEN_URL', 'https://open.coros.com/oauth2/accesstoken',
)

# Scope set requested at OAuth flow time. Bump _COROS_SCOPE_VERSION
# whenever this changes — re-acknowledgment of the disclosure is keyed
# on `version_id` in `disclosure_acknowledgments` (D-58 decision #7).
_COROS_SCOPES = 'activity wellness sleep hr'
_COROS_SCOPE_VERSION = '2026-05-14'

# Access token validity per Integration v4 §4.1 / PROVIDERS_SCHEMA.md
# §5.1. Refresh token never expires; we don't store an expiry for it.
_COROS_ACCESS_TTL = timedelta(days=30)

# Session keys.
_OAUTH_STATE = 'coros_oauth_state'
_OAUTH_RETURN_TO = 'coros_oauth_return_to'


# ── OAuth initiation ──────────────────────────────────────────────────

@bp.route('/oauth/start', methods=['GET'])
def oauth_start():
    """Generate a state token, stash it + the post-callback redirect
    target in session, and bounce the user to COROS.

    Query parameters:
      - `return_to`: relative path the callback should redirect to on
        success. Defaults to dashboard. The frontend onboarding flow
        passes the onboarding step-3 URL here when mid-onboarding; the
        Account Config 1 management screen passes its own URL.
    """
    if current_user_id() is None:
        # OAuth needs a logged-in user to attach the auth row to. Bounce
        # to login with this URL as `next` so they come back here after.
        return redirect(url_for('auth.login', next=request.url))

    client_id = os.environ.get('COROS_CLIENT_ID')
    if not client_id:
        current_app.logger.error('COROS_CLIENT_ID not configured')
        abort(503)

    state = secrets.token_urlsafe(32)
    session[_OAUTH_STATE] = state
    return_to = request.args.get('return_to') or '/'
    # Only allow same-origin redirects to prevent open-redirect abuse.
    if not return_to.startswith('/') or return_to.startswith('//'):
        return_to = '/'
    session[_OAUTH_RETURN_TO] = return_to

    redirect_uri = url_for('coros.oauth_callback', _external=True)
    params = {
        'client_id': client_id,
        'redirect_uri': redirect_uri,
        'response_type': 'code',
        'scope': _COROS_SCOPES,
        'state': state,
    }
    return redirect(f'{_COROS_AUTH_URL}?{urllib.parse.urlencode(params)}')


# ── OAuth callback ────────────────────────────────────────────────────

@bp.route('/oauth/callback', methods=['GET'])
def oauth_callback():
    """COROS redirects the user back here with `?code=…&state=…`.
    Exchange code for tokens, persist via `provider_auth`, record the
    scope acknowledgment, and redirect per D-58 §3.
    """
    user_id = current_user_id()
    if user_id is None:
        # Session expired between initiation and callback. Bounce to
        # login; user can retry the connect from Account Config 1.
        return redirect(url_for('auth.login'))

    expected_state = session.pop(_OAUTH_STATE, None)
    return_to = session.pop(_OAUTH_RETURN_TO, '/')
    received_state = request.args.get('state')
    if not expected_state or not received_state or not hmac.compare_digest(
        expected_state, received_state,
    ):
        current_app.logger.warning('COROS OAuth state mismatch for user %s', user_id)
        abort(400)

    if 'error' in request.args:
        # User denied consent or COROS returned an error. Send them back
        # to the return_to with a flag so the UI can surface "connect
        # cancelled".
        return redirect(f'{return_to}?coros_oauth_error={request.args.get("error")}')

    code = request.args.get('code')
    if not code:
        abort(400)

    client_id = os.environ.get('COROS_CLIENT_ID')
    client_secret = os.environ.get('COROS_CLIENT_SECRET')
    if not client_id or not client_secret:
        current_app.logger.error('COROS client credentials not configured')
        abort(503)

    redirect_uri = url_for('coros.oauth_callback', _external=True)
    try:
        resp = requests.post(
            _COROS_TOKEN_URL,
            data={
                'grant_type': 'authorization_code',
                'code': code,
                'client_id': client_id,
                'client_secret': client_secret,
                'redirect_uri': redirect_uri,
            },
            timeout=10,
        )
        resp.raise_for_status()
        token_data = resp.json()
    except requests.RequestException as exc:
        current_app.logger.exception('COROS token exchange failed: %s', exc)
        abort(502)

    access_token = token_data.get('access_token')
    refresh_token = token_data.get('refresh_token')
    # COROS uses `openId` per Integration v4 §4.1. Some COROS responses
    # nest the user id under `data.openId`; accept both.
    open_id = token_data.get('openId') or (token_data.get('data') or {}).get('openId')
    if not access_token or not open_id:
        current_app.logger.error('COROS token response missing fields: %s', token_data)
        abort(502)

    db = get_db()
    pa.upsert_auth(
        db,
        user_id=user_id,
        provider='coros',
        access_token=access_token,
        refresh_token=refresh_token,
        token_expires_at=datetime.now(timezone.utc) + _COROS_ACCESS_TTL,
        provider_user_id=str(open_id),
        scopes=_COROS_SCOPES,
        status=pa.STATUS_ACTIVE,
        registered_at=datetime.now(timezone.utc),
    )
    pa.record_oauth_scope_ack(
        db,
        user_id=user_id,
        provider='coros',
        scopes_granted=_COROS_SCOPES,
        version_id=_COROS_SCOPE_VERSION,
    )

    # D-58 §3 redirect rules + v5 §A.2.5 re-onboarding prompt trigger.
    # PR1 is backend-only; the actual prompt UI ships in PR2 frontend.
    # The query-param signal is the contract — frontend reads it on the
    # next page render to decide whether to surface the prefill prompt.
    sep = '&' if '?' in return_to else '?'
    return redirect(f'{return_to}{sep}coros_connected=1')


# ── Webhook ───────────────────────────────────────────────────────────

@bp.route('/webhook', methods=['GET', 'POST'])
def webhook():
    """COROS push handler. GETs (probe) return the success envelope;
    POSTs verify the `client` + `secret` headers, record to
    `webhook_events`, and dispatch to ingestion when the signature is
    good.

    COROS expects `{"result":"0000","message":"ok"}` for success; any
    other shape is treated as a delivery failure on their side. We
    return 401 with the same envelope structure on signature failure
    so audit logs stay parseable.
    """
    if request.method == 'GET':
        # Probe / liveness — no payload to record.
        return jsonify(result='0000', message='ok'), 200

    expected_client = os.environ.get('COROS_CLIENT_ID')
    expected_secret = os.environ.get('COROS_CLIENT_SECRET')
    received_client = request.headers.get('client') or ''
    received_secret = request.headers.get('secret') or ''
    sig_ok = bool(
        expected_client and expected_secret
        and hmac.compare_digest(received_client, expected_client)
        and hmac.compare_digest(received_secret, expected_secret)
    )

    raw_body = request.get_data(as_text=True) or ''
    try:
        payload = json.loads(raw_body) if raw_body else {}
    except json.JSONDecodeError:
        payload = {}

    # COROS payload shape: per their Open API webhook docs, push events
    # include `sportDataList` / `dailyDataList` / etc. plus an `openId`
    # identifying the user. Top-level event_type is implied by which
    # list is populated; we record the raw payload and let ingestion
    # branch on shape.
    open_id = payload.get('openId') if isinstance(payload, dict) else None
    event_type = _infer_event_type(payload) if isinstance(payload, dict) else None
    entity_id = _infer_entity_id(payload) if isinstance(payload, dict) else None

    db = get_db()
    auth_row = (
        pa.get_auth_by_provider_user_id(db, 'coros', str(open_id))
        if open_id else None
    )
    user_id = auth_row['user_id'] if auth_row else None

    cur = db.execute(
        'INSERT INTO webhook_events '
        '(provider, event_type, provider_user_id, entity_id, user_id, '
        ' payload, signature_ok, received_at) '
        'VALUES (?, ?, ?, ?, ?, ?, ?, NOW()) RETURNING id',
        ('coros', event_type, str(open_id) if open_id else None,
         entity_id, user_id, raw_body, sig_ok),
    )
    event_id = cur.fetchone()['id']
    db.commit()

    if not sig_ok:
        # Per Integration v4 §4.2: rows with signature_ok=False are
        # written for audit but never dispatched. Return 401 so COROS
        # sees the failure (and so an attacker can't probe for our
        # secret by watching for the success envelope).
        return jsonify(result='0401', message='signature invalid'), 401

    # Dispatch. Import here to avoid a top-of-module cycle if ingest
    # ever needs to call back into this module.
    from routes import coros_ingest
    try:
        coros_ingest.ingest_event(db, event_id, user_id, payload)
        db.execute(
            'UPDATE webhook_events SET processed_at = NOW() WHERE id = ?',
            (event_id,),
        )
        db.commit()
    except Exception as exc:  # noqa: BLE001 — log + record + continue
        current_app.logger.exception('COROS ingestion failed for event %s', event_id)
        db.execute(
            'UPDATE webhook_events SET processed_at = NOW(), error = ? WHERE id = ?',
            (str(exc)[:500], event_id),
        )
        db.commit()
        # Still return success to COROS — the event is durably recorded
        # in `webhook_events` for re-dispatch. Returning a non-2xx would
        # make COROS retry, which would re-record duplicate rows.

    return jsonify(result='0000', message='ok'), 200


# ── Payload introspection (small, kept here for webhook locality) ────

def _infer_event_type(payload: dict) -> str | None:
    """Classify a COROS webhook payload by which top-level list is
    present. Used for the `webhook_events.event_type` column.
    """
    if 'sportDataList' in payload:
        return 'activity'
    if 'dailyDataList' in payload:
        return 'daily_summary'
    if 'hrvDataList' in payload:
        return 'hrv'
    return None


def _infer_entity_id(payload: dict) -> str | None:
    """Extract the dedup key from a COROS payload. COROS uses `labelId`
    for activities + plans (per Integration v4 §3); daily-summary
    payloads don't have a per-entity id (date is the natural key)."""
    for key in ('sportDataList', 'dailyDataList', 'hrvDataList'):
        items = payload.get(key)
        if isinstance(items, list) and items:
            first = items[0]
            if isinstance(first, dict):
                return first.get('labelId') or first.get('happenDay')
    return None
