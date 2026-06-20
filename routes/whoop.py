"""Whoop integration — OAuth connect flow (#681 (B) live wiring) + webhook stub
+ the manual-CSV writer.

OAuth pair (mirrors `routes/coros.py`):

- `GET /whoop/oauth/start`     — CSRF state + return_to into session, redirect to
                                Whoop's consent screen.
- `GET /whoop/oauth/callback` — exchange code for tokens, fetch the basic profile
                                for the Whoop `user_id` (the token response has
                                none — but the webhook reverse-lookup needs it),
                                persist via `provider_auth`, record the scope ack.

`POST /whoop/webhook` stays a stub: real verification (HMAC-SHA256 over the raw
body with `WHOOP_CLIENT_SECRET`, base64 in `X-WHOOP-Signature`, + the
`X-WHOOP-Signature-Timestamp` window) and dispatch of the thin event (`user_id`,
`id`, `type` e.g. `workout.updated`) → REST fetch land in the ingest slice (token
refresh + thin-webhook fetch architecture — Trigger #5, see CARRY_FORWARD (B)).

Whoop OAuth v2 surface (developer.whoop.com/docs): scope is **space-separated**;
`offline` is required to receive a `refresh_token`; `state` must be ≥8 chars. The
token response carries `access_token`, `refresh_token`, `expires_in` (seconds),
`scope`. Override the hosts via `WHOOP_AUTH_URL` / `WHOOP_TOKEN_URL` /
`WHOOP_PROFILE_URL` if Whoop rotates them.

Manual upload (#767 slice 4 → 5): a WHOOP `physiological_cycles.csv` export is
ingested into `provider_raw_record` (`provider='whoop'`,
`data_type='daily_summary'`) so Layer-3A `recent_wellness` reads Whoop sleep /
HRV / resting-HR independent of the live OAuth/webhook path. The reusable writer
(`ingest_whoop_csv`) is called by the unified uploader on a `.csv`.
"""
from __future__ import annotations

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
from whoop_csv_parser import parse_whoop_physiological_cycles

bp = Blueprint('whoop', __name__, url_prefix='/whoop')

_WHOOP_AUTH_URL = os.environ.get(
    'WHOOP_AUTH_URL', 'https://api.prod.whoop.com/oauth/oauth2/auth',
)
_WHOOP_TOKEN_URL = os.environ.get(
    'WHOOP_TOKEN_URL', 'https://api.prod.whoop.com/oauth/oauth2/token',
)
_WHOOP_PROFILE_URL = os.environ.get(
    'WHOOP_PROFILE_URL', 'https://api.prod.whoop.com/developer/v2/user/profile/basic',
)

# Read scopes per Provider_Inbound_Matrix_v2 §3 + `offline` (required for a
# refresh_token). Space-separated (Whoop convention). Bump the version on change.
_WHOOP_SCOPES = (
    'read:recovery read:sleep read:workout read:cycles '
    'read:body_measurement offline'
)
_WHOOP_SCOPE_VERSION = '2026-06-20'

_OAUTH_STATE = 'whoop_oauth_state'
_OAUTH_RETURN_TO = 'whoop_oauth_return_to'


# ── OAuth initiation ──────────────────────────────────────────────────

@bp.route('/oauth/start', methods=['GET'])
def oauth_start():
    if current_user_id() is None:
        return redirect(url_for('auth.login', next=request.url))

    client_id = os.environ.get('WHOOP_CLIENT_ID')
    if not client_id:
        current_app.logger.error('WHOOP_CLIENT_ID not configured')
        abort(503)

    state = secrets.token_urlsafe(32)  # ≥8 chars (Whoop requirement)
    session[_OAUTH_STATE] = state
    return_to = request.args.get('return_to') or '/'
    if not return_to.startswith('/') or return_to.startswith('//'):
        return_to = '/'
    session[_OAUTH_RETURN_TO] = return_to

    redirect_uri = url_for('whoop.oauth_callback', _external=True)
    params = {
        'client_id': client_id,
        'redirect_uri': redirect_uri,
        'response_type': 'code',
        'scope': _WHOOP_SCOPES,
        'state': state,
    }
    return redirect(f'{_WHOOP_AUTH_URL}?{urllib.parse.urlencode(params)}')


# ── OAuth callback ────────────────────────────────────────────────────

@bp.route('/oauth/callback', methods=['GET'])
def oauth_callback():
    user_id = current_user_id()
    if user_id is None:
        return redirect(url_for('auth.login'))

    expected_state = session.pop(_OAUTH_STATE, None)
    return_to = session.pop(_OAUTH_RETURN_TO, '/')
    received_state = request.args.get('state')
    if not expected_state or not received_state or expected_state != received_state:
        current_app.logger.warning('Whoop OAuth state mismatch for user %s', user_id)
        abort(400)

    if 'error' in request.args:
        return redirect(f'{return_to}?whoop_oauth_error={request.args.get("error")}')

    code = request.args.get('code')
    if not code:
        abort(400)

    client_id = os.environ.get('WHOOP_CLIENT_ID')
    client_secret = os.environ.get('WHOOP_CLIENT_SECRET')
    if not client_id or not client_secret:
        current_app.logger.error('Whoop client credentials not configured')
        abort(503)

    redirect_uri = url_for('whoop.oauth_callback', _external=True)
    try:
        resp = requests.post(
            _WHOOP_TOKEN_URL,
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
        current_app.logger.exception('Whoop token exchange failed: %s', exc)
        abort(502)

    access_token = token_data.get('access_token')
    refresh_token = token_data.get('refresh_token')
    expires_in = token_data.get('expires_in')  # seconds
    if not access_token:
        current_app.logger.error('Whoop token response missing access_token: %s', token_data)
        abort(502)

    # The token response carries no user id; the webhook reverse-lookup keys on
    # the Whoop `user_id`, so fetch the basic profile to capture it.
    whoop_user_id = None
    try:
        prof = requests.get(
            _WHOOP_PROFILE_URL,
            headers={'Authorization': f'Bearer {access_token}'},
            timeout=10,
        )
        prof.raise_for_status()
        whoop_user_id = prof.json().get('user_id')
    except requests.RequestException as exc:
        current_app.logger.exception('Whoop profile fetch failed: %s', exc)
        abort(502)
    if whoop_user_id is None:
        current_app.logger.error('Whoop profile missing user_id')
        abort(502)

    token_expires_at = (
        datetime.now(timezone.utc) + timedelta(seconds=int(expires_in))
        if expires_in else None
    )
    granted_scopes = token_data.get('scope') or _WHOOP_SCOPES

    db = get_db()
    pa.upsert_auth(
        db,
        user_id=user_id,
        provider='whoop',
        access_token=access_token,
        refresh_token=refresh_token,
        token_expires_at=token_expires_at,
        provider_user_id=str(whoop_user_id),
        scopes=granted_scopes,
        status=pa.STATUS_ACTIVE,
        registered_at=datetime.now(timezone.utc),
    )
    pa.record_oauth_scope_ack(
        db,
        user_id=user_id,
        provider='whoop',
        scopes_granted=granted_scopes,
        version_id=_WHOOP_SCOPE_VERSION,
    )
    print(  # noqa: T201 — Rule #15 (no token material)
        f'[whoop-oauth] connected user={user_id} whoop_user_id={whoop_user_id} '
        f'scopes={granted_scopes!r} expires_in={expires_in}'
    )

    sep = '&' if '?' in return_to else '?'
    return redirect(f'{return_to}{sep}whoop_connected=1')


# ── Webhook (stub — real verify + dispatch is the ingest slice) ───────

@bp.route('/webhook', methods=['GET', 'POST'])
def webhook():
    return jsonify(status='ok'), 200


# ── Manual-CSV writer (#767 slice 4/5) ────────────────────────────────

def _record_raw(db, user_id, data_type, external_id, payload):
    """Record one WHOOP daily-wellness signal into `provider_raw_record`
    (record-don't-drop, provider-tagged). Idempotent per
    (user_id, provider, data_type, external_id); `external_id` is the ISO date,
    `observed_at` mirrors it (a daily aggregate has no finer timestamp).
    Mirrors `routes.polar_ingest._record_raw` / `routes.coros_ingest._record_raw`
    so the Layer-3A reader is provider-symmetric."""
    db.execute(
        'INSERT INTO provider_raw_record '
        '(user_id, provider, data_type, external_id, observed_at, raw_payload) '
        'VALUES (?, ?, ?, ?, ?, ?::jsonb) '
        'ON CONFLICT (user_id, provider, data_type, external_id) DO UPDATE SET '
        '    observed_at = EXCLUDED.observed_at, '
        '    raw_payload = EXCLUDED.raw_payload, '
        '    fetched_at = NOW()',
        (user_id, 'whoop', data_type, external_id, external_id,
         json.dumps(payload)),
    )


def ingest_whoop_csv(db, user_id, raw) -> int:
    """Parse a WHOOP `physiological_cycles.csv` and record each day into
    `provider_raw_record` (provider='whoop', data_type='daily_summary'). Returns
    the number of days recorded (≥1 on success). Raises `ValueError` if `raw`
    isn't a usable physiological_cycles export. Does NOT commit — the caller owns
    the transaction (the unified uploader commits per file)."""
    records = parse_whoop_physiological_cycles(raw)
    for rec in records:
        _record_raw(db, user_id, 'daily_summary', rec['date'], rec)
    return len(records)
