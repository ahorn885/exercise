"""Ride With GPS integration — OAuth connect + record-and-defer webhook ingest
(#681 (B) live wiring).

RWGPS is the one provider whose webhook **must not** fetch synchronously: it
requires a 2xx within ~1 second and **does not retry** (a slow handler loses the
event for good). So this uses **record-and-defer**: the webhook records the thin
event(s) to `webhook_events` (processed_at NULL) and returns 200 immediately; an
every-minute Vercel cron (`/ride-with-gps/cron/process`) drains the pending rows,
fetches each trip over REST (fresh token), and writes it to `cardio_log`. This is
the deferred-processing model the synchronous providers (Strava/Whoop/Wahoo/Oura)
can adopt later if their ack windows ever bite.

Endpoints:
- `GET  /ride-with-gps/oauth/start` / `…/callback` — OAuth connect (fetch the
  current user id for the webhook reverse-lookup).
- `POST /ride-with-gps/webhook`   — HMAC-verify `x-rwgps-signature`, record each
  notification (deferred), return 200 fast.
- `GET  /ride-with-gps/cron/process` — Bearer-CRON_SECRET cron: drain pending
  rwgps events → fetch trip → `cardio_log`.

Provider tag is **`rwgps`** (matches `provider_value_map_seed` / `_SOURCE_MAP` /
the `rwgps_trip_id` dedup column); the blueprint name stays `ride_with_gps`.
Mapping per matrix §10.1: distance m→mi, elevation m→ft, duration s→min, speed
km/h (not stored), `activity_type` → discipline via the #681 resolver.

BEST-EFFORT / VERIFY-OWED (Rule #14): the OAuth/token/user/webhook surface +
trip JSON shape are RWGPS's documented form, env-overridable, unverified against
live payloads — confirm at go-live.
"""
from __future__ import annotations

import hashlib
import hmac
import json
import os
import secrets
import urllib.parse
from datetime import datetime, timedelta, timezone
from typing import Any

import requests
from flask import (
    Blueprint, abort, current_app, jsonify, redirect, request, session, url_for,
)

from database import get_db
from provider_cardio_resolve import resolve_cardio_discipline
from routes import provider_auth as pa
from routes.auth import cron_authorized, current_user_id

bp = Blueprint('ride_with_gps', __name__, url_prefix='/ride-with-gps')

_RWGPS_AUTH_URL = os.environ.get('RWGPS_AUTH_URL', 'https://ridewithgps.com/oauth/authorize')
_RWGPS_TOKEN_URL = os.environ.get('RWGPS_TOKEN_URL', 'https://ridewithgps.com/oauth/token')
_RWGPS_API_BASE = os.environ.get('RWGPS_API_BASE', 'https://ridewithgps.com')
_RWGPS_USER_URL = os.environ.get('RWGPS_USER_URL', 'https://ridewithgps.com/users/current.json')

_RWGPS_SCOPES = os.environ.get('RWGPS_SCOPES', 'read')
_RWGPS_SCOPE_VERSION = '2026-06-20'

_OAUTH_STATE = 'rwgps_oauth_state'
_OAUTH_RETURN_TO = 'rwgps_oauth_return_to'

_M_TO_MI = 0.000621371
_M_TO_FT = 3.28084


def _as_int(value: Any) -> int | None:
    if value is None or value == '':
        return None
    try:
        return int(round(float(value)))
    except (TypeError, ValueError):
        return None


# ── OAuth ─────────────────────────────────────────────────────────────

@bp.route('/oauth/start', methods=['GET'])
def oauth_start():
    if current_user_id() is None:
        return redirect(url_for('auth.login', next=request.url))
    client_id = os.environ.get('RWGPS_CLIENT_ID')
    if not client_id:
        current_app.logger.error('RWGPS_CLIENT_ID not configured')
        abort(503)
    state = secrets.token_urlsafe(32)
    session[_OAUTH_STATE] = state
    return_to = request.args.get('return_to') or '/'
    if not return_to.startswith('/') or return_to.startswith('//'):
        return_to = '/'
    session[_OAUTH_RETURN_TO] = return_to
    params = {
        'client_id': client_id,
        'redirect_uri': url_for('ride_with_gps.oauth_callback', _external=True),
        'response_type': 'code',
        'state': state,
    }
    if _RWGPS_SCOPES:
        params['scope'] = _RWGPS_SCOPES
    return redirect(f'{_RWGPS_AUTH_URL}?{urllib.parse.urlencode(params)}')


@bp.route('/oauth/callback', methods=['GET'])
def oauth_callback():
    user_id = current_user_id()
    if user_id is None:
        return redirect(url_for('auth.login'))
    expected_state = session.pop(_OAUTH_STATE, None)
    return_to = session.pop(_OAUTH_RETURN_TO, '/')
    received_state = request.args.get('state')
    if not expected_state or not received_state or not hmac.compare_digest(
        expected_state, received_state,
    ):
        current_app.logger.warning('RWGPS OAuth state mismatch for user %s', user_id)
        abort(400)
    if 'error' in request.args:
        return redirect(f'{return_to}?rwgps_oauth_error={request.args.get("error")}')
    code = request.args.get('code')
    if not code:
        abort(400)
    client_id = os.environ.get('RWGPS_CLIENT_ID')
    client_secret = os.environ.get('RWGPS_CLIENT_SECRET')
    if not client_id or not client_secret:
        current_app.logger.error('RWGPS client credentials not configured')
        abort(503)
    redirect_uri = url_for('ride_with_gps.oauth_callback', _external=True)
    try:
        resp = requests.post(_RWGPS_TOKEN_URL, data={
            'grant_type': 'authorization_code',
            'code': code,
            'client_id': client_id,
            'client_secret': client_secret,
            'redirect_uri': redirect_uri,
        }, timeout=10)
        resp.raise_for_status()
        token_data = resp.json()
    except requests.RequestException as exc:
        current_app.logger.exception('RWGPS token exchange failed: %s', exc)
        abort(502)

    access_token = token_data.get('access_token')
    refresh_token = token_data.get('refresh_token')
    expires_in = token_data.get('expires_in')
    if not access_token:
        current_app.logger.error('RWGPS token response missing access_token: %s', token_data)
        abort(502)

    rwgps_user_id = None
    try:
        prof = requests.get(_RWGPS_USER_URL,
                            headers={'Authorization': f'Bearer {access_token}'},
                            timeout=10)
        prof.raise_for_status()
        body = prof.json()
        rwgps_user_id = (body.get('user') or {}).get('id') or body.get('id')
    except requests.RequestException as exc:
        current_app.logger.exception('RWGPS user fetch failed: %s', exc)
        abort(502)
    if rwgps_user_id is None:
        current_app.logger.error('RWGPS user id missing')
        abort(502)

    token_expires_at = (
        datetime.now(timezone.utc) + timedelta(seconds=int(expires_in))
        if expires_in else None
    )
    db = get_db()
    pa.upsert_auth(
        db, user_id=user_id, provider='rwgps',
        access_token=access_token, refresh_token=refresh_token,
        token_expires_at=token_expires_at, provider_user_id=str(rwgps_user_id),
        scopes=_RWGPS_SCOPES, status=pa.STATUS_ACTIVE,
        registered_at=datetime.now(timezone.utc),
    )
    pa.record_oauth_scope_ack(
        db, user_id=user_id, provider='rwgps',
        scopes_granted=_RWGPS_SCOPES, version_id=_RWGPS_SCOPE_VERSION,
    )
    print(f'[rwgps-oauth] connected user={user_id} rwgps_user_id={rwgps_user_id}')  # noqa: T201
    sep = '&' if '?' in return_to else '?'
    return redirect(f'{return_to}{sep}rwgps_connected=1')


# ── Webhook (record-and-defer — 1s ack, no retry) ─────────────────────

def _verify_signature(raw_body: bytes, signature: str | None, secret: str | None) -> bool:
    """RWGPS `x-rwgps-signature` = hex HMAC-SHA256 of the raw body with the API
    client secret. (Documented form — verify at go-live.)"""
    if not secret or not signature:
        return False
    mac = hmac.new(secret.encode(), raw_body, hashlib.sha256).hexdigest()
    return hmac.compare_digest(mac, signature)


@bp.route('/webhook', methods=['GET', 'POST'])
def webhook():
    if request.method == 'GET':
        return jsonify(status='ok'), 200

    raw_body = request.get_data() or b''
    signature = request.headers.get('x-rwgps-signature')
    sig_ok = _verify_signature(raw_body, signature, os.environ.get('RWGPS_CLIENT_SECRET'))
    try:
        body = json.loads(raw_body.decode('utf-8')) if raw_body else {}
    except (json.JSONDecodeError, UnicodeDecodeError):
        body = {}
    if not isinstance(body, dict):
        body = {}

    # RWGPS may batch notifications; tolerate the single-object shape too.
    notifications = body.get('notifications')
    if not isinstance(notifications, list):
        notifications = [body]

    db = get_db()
    recorded = 0
    for notif in notifications:
        if not isinstance(notif, dict):
            continue
        item_url = notif.get('item_url')
        if not item_url:
            continue
        rwgps_uid = notif.get('user_id') or body.get('user_id')
        auth_row = (
            pa.get_auth_by_provider_user_id(db, 'rwgps', str(rwgps_uid))
            if rwgps_uid is not None else None
        )
        user_id = auth_row['user_id'] if auth_row else None
        # Deferred: processed_at stays NULL → the cron picks it up. Store the
        # single notification as the row payload; entity_id carries item_url.
        db.execute(
            'INSERT INTO webhook_events '
            '(provider, event_type, provider_user_id, entity_id, user_id, '
            ' payload, signature_ok, received_at) '
            'VALUES (?, ?, ?, ?, ?, ?, ?, NOW())',
            ('rwgps', notif.get('action') or 'trip',
             str(rwgps_uid) if rwgps_uid is not None else None,
             str(item_url), user_id, json.dumps(notif), sig_ok),
        )
        recorded += 1
    db.commit()
    print(f'[rwgps-webhook] recorded={recorded} sig_ok={sig_ok} (deferred)')  # noqa: T201
    return jsonify(status='ok', recorded=recorded), 200


# ── Cron processor (drains the deferred queue) ────────────────────────

@bp.route('/cron/process', methods=['GET', 'POST'])
def cron_process():
    """Drain pending rwgps webhook events (signature-ok, mapped user, last 24h):
    fetch each trip and write it to cardio_log. On success → processed_at=NOW();
    on failure → record the error, leave it pending to retry until it ages out of
    the 24h window. Bearer-CRON_SECRET gated."""
    if not cron_authorized():
        abort(401)
    db = get_db()
    rows = db.execute(
        "SELECT id, user_id, entity_id, payload FROM webhook_events "
        "WHERE provider = 'rwgps' AND processed_at IS NULL "
        "  AND signature_ok AND user_id IS NOT NULL "
        "  AND received_at > NOW() - INTERVAL '1 day' "
        "ORDER BY received_at LIMIT 50"
    ).fetchall()
    processed = failed = 0
    for row in rows:
        try:
            _fetch_and_ingest_trip(db, row['user_id'], row['entity_id'])
            db.execute('UPDATE webhook_events SET processed_at = NOW() WHERE id = ?',
                       (row['id'],))
            db.commit()
            processed += 1
        except Exception as exc:  # noqa: BLE001 — leave pending for retry in-window
            current_app.logger.exception('RWGPS cron ingest failed for event %s', row['id'])
            db.execute('UPDATE webhook_events SET error = ? WHERE id = ?',
                       (str(exc)[:500], row['id']))
            db.commit()
            failed += 1
    print(f'[rwgps-cron] pending={len(rows)} processed={processed} failed={failed}')  # noqa: T201
    return jsonify(pending=len(rows), processed=processed, failed=failed), 200


# ── Ingest ────────────────────────────────────────────────────────────

def normalize_rwgps_trip(trip: dict) -> dict:
    """RWGPS trip JSON → the shared cardio dict (matrix §10.1 units). speed is
    km/h (not stored); distance/elevation are meters; activity_type → discipline."""
    act_type = trip.get('activity_type')
    res = resolve_cardio_discipline('rwgps', act_type)
    dist_m = trip.get('distance')
    dur_s = trip.get('duration') or trip.get('moving_time')
    gain_m = trip.get('elevation_gain')
    loss_m = trip.get('elevation_loss')
    start = trip.get('departed_at') or trip.get('created_at')
    activity_date = (str(start)[:10] if start else
                     datetime.now(timezone.utc).date().isoformat())
    indoor = bool(trip.get('is_stationary'))
    machine = ('Cycling trainer'
               if indoor and res.discipline_id in ('D-006', 'D-008', 'D-030') else None)
    return {
        'date': activity_date,
        'activity': res.plan_sport_type or 'other',
        'activity_name': trip.get('name'),
        'duration_min': (float(dur_s) / 60) if dur_s not in (None, '') else None,
        'distance_mi': (float(dist_m) * _M_TO_MI) if dist_m not in (None, '') else None,
        'avg_hr': _as_int(trip.get('avg_hr')),
        'max_hr': _as_int(trip.get('max_hr')),
        'calories': _as_int(trip.get('calories')),
        'elev_gain_ft': (float(gain_m) * _M_TO_FT) if gain_m not in (None, '') else None,
        'elev_loss_ft': (float(loss_m) * _M_TO_FT) if loss_m not in (None, '') else None,
        'avg_cadence': _as_int(trip.get('avg_cad')),
        'avg_power': _as_int(trip.get('avg_watts')),
        'max_power': _as_int(trip.get('max_watts')),
        'discipline_id': res.discipline_id,
        '_provider_raw': {
            'provider': 'rwgps', 'observed_at': str(start) if start else None,
            'bucket': res.bucket, 'canonical_ref': res.discipline_id,
            'payload': {'activity_type': act_type, 'indoor_machine': machine,
                        'is_stationary': trip.get('is_stationary'),
                        'rwgps_trip_id': trip.get('id')},
        },
    }


def _fetch_and_ingest_trip(db: Any, user_id: int, item_url: str) -> bool:
    token = pa.get_fresh_access_token(
        db, user_id, 'rwgps',
        token_url=_RWGPS_TOKEN_URL,
        client_id=os.environ.get('RWGPS_CLIENT_ID'),
        client_secret=os.environ.get('RWGPS_CLIENT_SECRET'),
    )
    if not token:
        print(f'[rwgps-ingest] {item_url} user={user_id} SKIP no-token')  # noqa: T201
        return False
    url = item_url if str(item_url).startswith('http') else (_RWGPS_API_BASE + item_url)
    resp = requests.get(url, headers={'Authorization': f'Bearer {token}'}, timeout=10)
    resp.raise_for_status()
    body = resp.json()
    trip = body.get('trip') if isinstance(body, dict) and 'trip' in body else body
    if not isinstance(trip, dict) or trip.get('id') is None:
        print(f'[rwgps-ingest] {item_url} user={user_id} SKIP no-trip')  # noqa: T201
        return False
    gid = str(trip['id'])
    if db.execute(
        'SELECT id FROM cardio_log WHERE rwgps_trip_id = ? AND user_id = ?',
        (gid, user_id),
    ).fetchone() is not None:
        print(f'[rwgps-ingest] trip={gid} user={user_id} SKIP already-imported')  # noqa: T201
        return False
    from routes.garmin import _bulk_insert_cardio
    data = normalize_rwgps_trip(trip)
    _bulk_insert_cardio(db, data, user_id, gid, source='rwgps')
    print(f'[rwgps-ingest] trip={gid} user={user_id} -> cardio_log '  # noqa: T201
          f'discipline={data.get("discipline_id")} bucket={data["_provider_raw"]["bucket"]}')
    return True
