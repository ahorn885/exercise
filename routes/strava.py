"""Strava integration — OAuth connect flow (#681 (B) live wiring) + webhook stub.

Three endpoints (the OAuth pair mirrors `routes/coros.py`):

- `GET  /strava/oauth/start`     — generates a CSRF state token, stashes it +
                                   the post-callback redirect target in session,
                                   and redirects to Strava's authorization URL.
- `GET  /strava/oauth/callback`  — receives `?code=…&state=…&scope=…`, exchanges
                                   the code for tokens via `provider_auth.
                                   upsert_auth`, records the per-provider scope
                                   ack, and redirects back with `?strava_connected=1`.
- `GET/POST /strava/webhook`     — Strava push subscription. The GET handshake
                                   (`hub.mode`/`hub.verify_token`/`hub.challenge`)
                                   is live so the subscription validates; POST
                                   event dispatch (thin `{object_type, object_id,
                                   aspect_type, owner_id}` event → REST fetch of
                                   the activity, with token refresh) lands in the
                                   ingest slice — see CARRY_FORWARD (B) ingest
                                   architecture (token refresh + thin-webhook
                                   fetch, Trigger #5).

Strava OAuth surface (developers.strava.com/docs/authentication): scope is
**comma-separated**; the token response carries `access_token`, `refresh_token`,
`expires_at` (absolute epoch seconds), and `athlete.id` (→ `provider_user_id`).
Strava lets the athlete deselect scopes at the consent screen, so the callback's
`scope` query param is the *granted* set — recorded over the requested set.

Pre-deploy verification: confirm the authorize/token hosts + the scope syntax
against current Strava docs before the subscription is created. Override the
hosts via `STRAVA_AUTH_URL` / `STRAVA_TOKEN_URL` if Strava rotates them.
"""
from __future__ import annotations

import hmac
import json
import os
import secrets
import urllib.parse
from datetime import datetime, timezone

import requests
from flask import (
    Blueprint, abort, current_app, jsonify, redirect, request, session, url_for,
)

from database import get_db
from routes import provider_auth as pa
from routes import provider_identity as pi
from routes.auth import current_user_id

bp = Blueprint('strava', __name__, url_prefix='/strava')

_STRAVA_AUTH_URL = os.environ.get(
    'STRAVA_AUTH_URL', 'https://www.strava.com/oauth/authorize',
)
_STRAVA_TOKEN_URL = os.environ.get(
    'STRAVA_TOKEN_URL', 'https://www.strava.com/oauth/token',
)

# Read scopes per Provider_Inbound_Matrix_v2 §2: activities + webhooks need
# `activity:read_all`; the `/athlete/zones` + profile fields need
# `profile:read_all`. Comma-separated (Strava convention). Bump the version on
# any change — re-ack is keyed on version_id in disclosure_acknowledgments.
_STRAVA_SCOPES = 'activity:read_all,profile:read_all'
_STRAVA_SCOPE_VERSION = '2026-06-20'

_OAUTH_STATE = 'strava_oauth_state'
_OAUTH_RETURN_TO = 'strava_oauth_return_to'
_OAUTH_INTENT = 'strava_oauth_intent'  # 'signin' (no session) vs 'connect' (logged in)


# ── OAuth initiation ──────────────────────────────────────────────────

@bp.route('/oauth/start', methods=['GET'])
def oauth_start():
    """Stash a state token + the post-callback redirect target, then bounce
    the user to Strava's consent screen.

    No session = "sign in / sign up with Strava" (design §6.1), gated by the
    feature flag. Flag off keeps the legacy connect-only behaviour (bounce to
    login)."""
    signin = current_user_id() is None
    if signin and not pi.signin_enabled():
        return redirect(url_for('auth.login', next=request.url))

    client_id = os.environ.get('STRAVA_CLIENT_ID')
    if not client_id:
        current_app.logger.error('STRAVA_CLIENT_ID not configured')
        abort(503)

    state = secrets.token_urlsafe(32)
    session[_OAUTH_STATE] = state
    session[_OAUTH_INTENT] = 'signin' if signin else 'connect'
    return_to = request.args.get('return_to') or '/'
    if not return_to.startswith('/') or return_to.startswith('//'):
        return_to = '/'
    session[_OAUTH_RETURN_TO] = return_to

    redirect_uri = url_for('strava.oauth_callback', _external=True)
    params = {
        'client_id': client_id,
        'redirect_uri': redirect_uri,
        'response_type': 'code',
        'scope': _STRAVA_SCOPES,
        'approval_prompt': 'auto',
        'state': state,
    }
    return redirect(f'{_STRAVA_AUTH_URL}?{urllib.parse.urlencode(params)}')


# ── OAuth callback ────────────────────────────────────────────────────

@bp.route('/oauth/callback', methods=['GET'])
def oauth_callback():
    """Strava redirects back with `?code=…&state=…&scope=…`. Exchange the
    code for tokens, persist via `provider_auth`, record the scope ack."""
    user_id = current_user_id()
    signin = user_id is None
    session.pop(_OAUTH_INTENT, None)
    if signin and not pi.signin_enabled():
        return redirect(url_for('auth.login'))

    expected_state = session.pop(_OAUTH_STATE, None)
    return_to = session.pop(_OAUTH_RETURN_TO, '/')
    received_state = request.args.get('state')
    if not expected_state or not received_state or not hmac.compare_digest(
        expected_state, received_state,
    ):
        current_app.logger.warning('Strava OAuth state mismatch for user %s', user_id)
        abort(400)

    if 'error' in request.args:
        return redirect(f'{return_to}?strava_oauth_error={request.args.get("error")}')

    code = request.args.get('code')
    if not code:
        abort(400)

    client_id = os.environ.get('STRAVA_CLIENT_ID')
    client_secret = os.environ.get('STRAVA_CLIENT_SECRET')
    if not client_id or not client_secret:
        current_app.logger.error('Strava client credentials not configured')
        abort(503)

    try:
        resp = requests.post(
            _STRAVA_TOKEN_URL,
            data={
                'client_id': client_id,
                'client_secret': client_secret,
                'code': code,
                'grant_type': 'authorization_code',
            },
            timeout=10,
        )
        resp.raise_for_status()
        token_data = resp.json()
    except requests.RequestException as exc:
        current_app.logger.exception('Strava token exchange failed: %s', exc)
        abort(502)

    access_token = token_data.get('access_token')
    refresh_token = token_data.get('refresh_token')
    expires_at = token_data.get('expires_at')  # absolute epoch seconds
    athlete = token_data.get('athlete') or {}
    athlete_id = athlete.get('id')
    if not access_token or not athlete_id:
        current_app.logger.error('Strava token response missing fields: %s', token_data)
        abort(502)
    athlete_id = str(athlete_id)

    token_expires_at = (
        datetime.fromtimestamp(int(expires_at), tz=timezone.utc)
        if expires_at else None
    )
    # The athlete may have deselected scopes at consent → the callback `scope`
    # is the granted set (comma-separated). Fall back to the requested set.
    granted_scopes = request.args.get('scope') or _STRAVA_SCOPES

    db = get_db()

    # ── No-session sign-in / sign-up (design §6.1) ────────────────────────
    if signin:
        identity = pi.get_identity(db, 'strava', athlete_id)
        if identity:  # existing account → log in
            user_id = identity['user_id']
            pi.bump_last_login(db, identity['id'])
            username = pi.get_username(db, user_id)
            dest = url_for('dashboard.index')
            print(f'[strava-signin] match user={user_id} athlete_id={athlete_id}')  # noqa: T201
        else:  # new athlete → passwordless account. Strava gives no email,
               # so the account starts email-less (design §4/§7) — name comes
               # from the token's `athlete` object.
            display = ' '.join(
                p for p in (athlete.get('firstname'), athlete.get('lastname')) if p
            ) or None
            user_id, username = pi.create_signin_user(
                db, provider='strava', provider_user_id=athlete_id,
                email=None, display_name=display,
                username_hint=athlete.get('firstname') or display,
            )
            dest = url_for('onboarding.connect')
            print(f'[strava-signin] new-account user={user_id} '  # noqa: T201
                  f'athlete_id={athlete_id} username={username}')
        _persist_strava_auth(db, user_id, access_token, refresh_token,
                             token_expires_at, athlete_id, granted_scopes)
        session.clear()
        session['user_id'] = user_id
        session['username'] = username
        return redirect(dest)

    # ── Logged-in connect / link path ─────────────────────────────────────
    _persist_strava_auth(db, user_id, access_token, refresh_token,
                         token_expires_at, athlete_id, granted_scopes)
    sep = '&' if '?' in return_to else '?'
    ok, reason = pi.link_identity(db, user_id, 'strava', athlete_id)
    if not ok and reason == 'claimed_by_other':
        current_app.logger.warning(
            'Strava identity %s already linked to another account', athlete_id)
        return redirect(f'{return_to}{sep}strava_oauth_error=already_linked')
    # Rule #15 — record the connect decision (no token material).
    print(  # noqa: T201
        f'[strava-oauth] connected user={user_id} athlete_id={athlete_id} '
        f'scopes={granted_scopes!r} expires_at={expires_at}'
    )
    return redirect(f'{return_to}{sep}strava_connected=1')


def _persist_strava_auth(db, user_id, access_token, refresh_token,
                         token_expires_at, athlete_id, granted_scopes) -> None:
    """Upsert the provider_auth sync credential + record the scope ack. Shared
    by the sign-in and connect paths so the persisted shape is identical."""
    pa.upsert_auth(
        db,
        user_id=user_id,
        provider='strava',
        access_token=access_token,
        refresh_token=refresh_token,
        token_expires_at=token_expires_at,
        provider_user_id=str(athlete_id),
        scopes=granted_scopes,
        status=pa.STATUS_ACTIVE,
        registered_at=datetime.now(timezone.utc),
    )
    pa.record_oauth_scope_ack(
        db,
        user_id=user_id,
        provider='strava',
        scopes_granted=granted_scopes,
        version_id=_STRAVA_SCOPE_VERSION,
    )


# ── Webhook ───────────────────────────────────────────────────────────

@bp.route('/webhook', methods=['GET', 'POST'])
def webhook():
    """Strava push subscription handler.

    GET: the subscription-validation handshake — echo `hub.challenge`.

    POST: a thin event `{object_type, object_id, aspect_type, owner_id,
    subscription_id}`. Record it to `webhook_events`, map `owner_id` → local
    user, and on an `activity` `create`/`update` synchronously fetch + ingest the
    activity over REST (`routes.strava_ingest`). Strava events carry no
    signature — the only authenticity check is the `subscription_id` matching the
    one subscription we own (when `STRAVA_SUBSCRIPTION_ID` is configured). We
    always return 200 (Strava retries any non-2xx, which would re-record); a
    failed ingest is recorded against the event row for re-delivery."""
    if request.method == 'GET':
        challenge = request.args.get('hub.challenge')
        if challenge is not None:
            return jsonify({'hub.challenge': challenge}), 200
        return jsonify(status='ok'), 200

    raw_body = request.get_data(as_text=True) or ''
    try:
        event = json.loads(raw_body) if raw_body else {}
    except json.JSONDecodeError:
        event = {}
    if not isinstance(event, dict):
        event = {}

    expected_sub = os.environ.get('STRAVA_SUBSCRIPTION_ID')
    received_sub = str(event.get('subscription_id') or '')
    sig_ok = (not expected_sub) or hmac.compare_digest(received_sub, expected_sub)

    object_type = event.get('object_type')
    object_id = event.get('object_id')
    aspect_type = event.get('aspect_type')
    owner_id = event.get('owner_id')

    db = get_db()
    auth_row = (
        pa.get_auth_by_provider_user_id(db, 'strava', str(owner_id))
        if owner_id is not None else None
    )
    user_id = auth_row['user_id'] if auth_row else None

    cur = db.execute(
        'INSERT INTO webhook_events '
        '(provider, event_type, provider_user_id, entity_id, user_id, '
        ' payload, signature_ok, received_at) '
        'VALUES (?, ?, ?, ?, ?, ?, ?, NOW()) RETURNING id',
        ('strava', f'{object_type}.{aspect_type}',
         str(owner_id) if owner_id is not None else None,
         str(object_id) if object_id is not None else None,
         user_id, raw_body, sig_ok),
    )
    event_id = cur.fetchone()['id']
    db.commit()

    should_ingest = (
        sig_ok and user_id is not None
        and object_type == 'activity' and aspect_type in ('create', 'update')
    )
    if should_ingest:
        from routes import strava_ingest
        try:
            strava_ingest.fetch_and_ingest_activity(db, user_id, object_id)
            db.execute(
                'UPDATE webhook_events SET processed_at = NOW() WHERE id = ?',
                (event_id,),
            )
            db.commit()
        except Exception as exc:  # noqa: BLE001 — log + record + still 200
            current_app.logger.exception('Strava ingestion failed for event %s', event_id)
            db.execute(
                'UPDATE webhook_events SET processed_at = NOW(), error = ? WHERE id = ?',
                (str(exc)[:500], event_id),
            )
            db.commit()

    return jsonify(status='ok'), 200
