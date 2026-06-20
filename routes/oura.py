"""Oura integration — OAuth connect + webhook ingest (#681 (B) live wiring).

Oura API v2 (api.ouraring.com). Like Whoop, a webhook is a thin pointer
(`{event_type, data_type, object_id, user_id}`) → GET the document over REST and
fold its canonical fields into the athlete's per-day `provider_raw_record` row.

- `GET  /oura/oauth/start`     — CSRF state + return_to → redirect to consent.
- `GET  /oura/oauth/callback`  — exchange code for tokens; fetch
                                 `personal_info` for the user id (webhook
                                 reverse-lookup needs it); persist + scope ack.
- `GET/POST /oura/webhook`     — GET echoes the subscription `challenge`; POST
                                 records the event, maps `user_id` → local user,
                                 and on a `sleep` create/update fetches the sleep
                                 document → daily_summary (merge-partial).

Mapping per `specs/Provider_Inbound_Matrix_v2.md` §4: Oura durations are SECONDS
(`total_sleep_duration` ÷60 → `total_sleep_min`), `lowest_heart_rate` is the real
RHR, `average_hrv` is rMSSD/ms. Written in the same daily_summary shape the
manual-CSV / Whoop paths use (`total_sleep_min`/`hrv_rmssd_ms`/`resting_hr`,
keyed on the sleep `day`).

Layer-3A reads this back: `layer3a/integration.py` has an `oura` daily_summary
reader branch + `oura` in `_WELLNESS_SOURCE_PRIORITY` (ranked just under Whoop,
above Polar/COROS), so Oura sleep/HRV/RHR reaches the coaching coalesce.

BEST-EFFORT / VERIFY-OWED (Rule #14): the OAuth/token/personal_info/webhook
surface + the event payload shape are Oura's documented form, env-overridable,
unverified against live payloads — confirm at go-live.
"""
from __future__ import annotations

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
from routes import provider_auth as pa
from routes.auth import current_user_id

bp = Blueprint('oura', __name__, url_prefix='/oura')

_OURA_AUTH_URL = os.environ.get('OURA_AUTH_URL', 'https://cloud.ouraring.com/oauth/authorize')
_OURA_TOKEN_URL = os.environ.get('OURA_TOKEN_URL', 'https://api.ouraring.com/oauth/token')
_OURA_API_BASE = os.environ.get('OURA_API_BASE', 'https://api.ouraring.com/v2')
_OURA_PERSONAL_INFO = _OURA_API_BASE + '/usercollection/personal_info'

# Read scopes per matrix §4 (space-separated).
_OURA_SCOPES = 'email personal daily heartrate workout spo2'
_OURA_SCOPE_VERSION = '2026-06-20'

_OAUTH_STATE = 'oura_oauth_state'
_OAUTH_RETURN_TO = 'oura_oauth_return_to'


# ── OAuth initiation ──────────────────────────────────────────────────

@bp.route('/oauth/start', methods=['GET'])
def oauth_start():
    if current_user_id() is None:
        return redirect(url_for('auth.login', next=request.url))
    client_id = os.environ.get('OURA_CLIENT_ID')
    if not client_id:
        current_app.logger.error('OURA_CLIENT_ID not configured')
        abort(503)
    state = secrets.token_urlsafe(32)
    session[_OAUTH_STATE] = state
    return_to = request.args.get('return_to') or '/'
    if not return_to.startswith('/') or return_to.startswith('//'):
        return_to = '/'
    session[_OAUTH_RETURN_TO] = return_to
    params = {
        'client_id': client_id,
        'redirect_uri': url_for('oura.oauth_callback', _external=True),
        'response_type': 'code',
        'scope': _OURA_SCOPES,
        'state': state,
    }
    return redirect(f'{_OURA_AUTH_URL}?{urllib.parse.urlencode(params)}')


# ── OAuth callback ────────────────────────────────────────────────────

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
        current_app.logger.warning('Oura OAuth state mismatch for user %s', user_id)
        abort(400)
    if 'error' in request.args:
        return redirect(f'{return_to}?oura_oauth_error={request.args.get("error")}')
    code = request.args.get('code')
    if not code:
        abort(400)
    client_id = os.environ.get('OURA_CLIENT_ID')
    client_secret = os.environ.get('OURA_CLIENT_SECRET')
    if not client_id or not client_secret:
        current_app.logger.error('Oura client credentials not configured')
        abort(503)
    redirect_uri = url_for('oura.oauth_callback', _external=True)
    try:
        resp = requests.post(_OURA_TOKEN_URL, data={
            'grant_type': 'authorization_code',
            'code': code,
            'client_id': client_id,
            'client_secret': client_secret,
            'redirect_uri': redirect_uri,
        }, timeout=10)
        resp.raise_for_status()
        token_data = resp.json()
    except requests.RequestException as exc:
        current_app.logger.exception('Oura token exchange failed: %s', exc)
        abort(502)

    access_token = token_data.get('access_token')
    refresh_token = token_data.get('refresh_token')
    expires_in = token_data.get('expires_in')
    if not access_token:
        current_app.logger.error('Oura token response missing access_token: %s', token_data)
        abort(502)

    oura_user_id = None
    try:
        prof = requests.get(_OURA_PERSONAL_INFO,
                            headers={'Authorization': f'Bearer {access_token}'},
                            timeout=10)
        prof.raise_for_status()
        oura_user_id = prof.json().get('id')
    except requests.RequestException as exc:
        current_app.logger.exception('Oura personal_info fetch failed: %s', exc)
        abort(502)
    if oura_user_id is None:
        current_app.logger.error('Oura personal_info missing id')
        abort(502)

    token_expires_at = (
        datetime.now(timezone.utc) + timedelta(seconds=int(expires_in))
        if expires_in else None
    )
    db = get_db()
    pa.upsert_auth(
        db, user_id=user_id, provider='oura',
        access_token=access_token, refresh_token=refresh_token,
        token_expires_at=token_expires_at, provider_user_id=str(oura_user_id),
        scopes=_OURA_SCOPES, status=pa.STATUS_ACTIVE,
        registered_at=datetime.now(timezone.utc),
    )
    pa.record_oauth_scope_ack(
        db, user_id=user_id, provider='oura',
        scopes_granted=_OURA_SCOPES, version_id=_OURA_SCOPE_VERSION,
    )
    print(f'[oura-oauth] connected user={user_id} oura_user_id={oura_user_id} '  # noqa: T201
          f'expires_in={expires_in}')
    sep = '&' if '?' in return_to else '?'
    return redirect(f'{return_to}{sep}oura_connected=1')


# ── Webhook ───────────────────────────────────────────────────────────

@bp.route('/webhook', methods=['GET', 'POST'])
def webhook():
    """GET = the subscription-verification handshake (echo `challenge`). POST =
    a thin event; record it, map `user_id` → local user, and on a `sleep`
    create/update fetch the document → daily_summary."""
    if request.method == 'GET':
        challenge = request.args.get('challenge')
        if challenge is not None:
            return jsonify({'challenge': challenge}), 200
        return jsonify(status='ok'), 200

    raw_body = request.get_data(as_text=True) or ''
    try:
        event = json.loads(raw_body) if raw_body else {}
    except json.JSONDecodeError:
        event = {}
    if not isinstance(event, dict):
        event = {}

    oura_user_id = event.get('user_id')
    data_type = event.get('data_type')
    object_id = event.get('object_id')
    event_type = event.get('event_type')

    db = get_db()
    auth_row = (
        pa.get_auth_by_provider_user_id(db, 'oura', str(oura_user_id))
        if oura_user_id is not None else None
    )
    user_id = auth_row['user_id'] if auth_row else None

    cur = db.execute(
        'INSERT INTO webhook_events '
        '(provider, event_type, provider_user_id, entity_id, user_id, '
        ' payload, signature_ok, received_at) '
        'VALUES (?, ?, ?, ?, ?, ?, ?, NOW()) RETURNING id',
        ('oura', f'{data_type}.{event_type}',
         str(oura_user_id) if oura_user_id is not None else None,
         str(object_id) if object_id is not None else None,
         user_id, raw_body, True),
    )
    event_id = cur.fetchone()['id']
    db.commit()

    should_ingest = (
        user_id is not None and object_id is not None
        and data_type == 'sleep' and event_type in ('create', 'update')
    )
    if should_ingest:
        try:
            _ingest_sleep(db, user_id, object_id)
            db.execute('UPDATE webhook_events SET processed_at = NOW() WHERE id = ?',
                       (event_id,))
            db.commit()
        except Exception as exc:  # noqa: BLE001
            current_app.logger.exception('Oura ingestion failed for event %s', event_id)
            db.execute('UPDATE webhook_events SET processed_at = NOW(), error = ? WHERE id = ?',
                       (str(exc)[:500], event_id))
            db.commit()

    return jsonify(status='ok'), 200


# ── Ingest ────────────────────────────────────────────────────────────

def _ingest_sleep(db: Any, user_id: int, sleep_id: Any) -> bool:
    """Oura sleep document → daily_summary {total_sleep_min, hrv_rmssd_ms,
    resting_hr}. Durations are seconds (÷60); `lowest_heart_rate` is the real RHR
    (NOT the readiness contributor); `average_hrv` is rMSSD/ms (matrix §4.1)."""
    data = _fetch(db, user_id, f'/usercollection/sleep/{sleep_id}')
    if not data:
        return False
    day = data.get('day') or (str(data.get('bedtime_end') or '')[:10] or None)
    if not day:
        return False
    partial: dict[str, Any] = {}
    total_s = data.get('total_sleep_duration')
    if total_s is not None:
        partial['total_sleep_min'] = float(total_s) / 60.0
    if data.get('average_hrv') is not None:
        partial['hrv_rmssd_ms'] = float(data['average_hrv'])
    if data.get('lowest_heart_rate') is not None:
        partial['resting_hr'] = int(round(float(data['lowest_heart_rate'])))
    if data.get('average_breath') is not None:
        partial['respiratory_rate'] = data['average_breath']
    _merge_daily(db, user_id, day, partial)
    print(f'[oura-ingest] sleep id={sleep_id} user={user_id} day={day} '  # noqa: T201
          f'sleep_min={partial.get("total_sleep_min")} hrv={partial.get("hrv_rmssd_ms")} '
          f'rhr={partial.get("resting_hr")}')
    return True


def _fetch(db: Any, user_id: int, path: str) -> dict | None:
    token = pa.get_fresh_access_token(
        db, user_id, 'oura',
        token_url=_OURA_TOKEN_URL,
        client_id=os.environ.get('OURA_CLIENT_ID'),
        client_secret=os.environ.get('OURA_CLIENT_SECRET'),
    )
    if not token:
        print(f'[oura-ingest] {path} user={user_id} SKIP no-token')  # noqa: T201
        return None
    resp = requests.get(_OURA_API_BASE + path,
                        headers={'Authorization': f'Bearer {token}'}, timeout=10)
    resp.raise_for_status()
    return resp.json()


def _merge_daily(db: Any, user_id: int, day: str, partial: dict) -> None:
    """Read-modify-write the day's oura daily_summary row (the shape Layer-3A's
    oura reader branch consumes)."""
    if not partial:
        return
    row = db.execute(
        "SELECT raw_payload FROM provider_raw_record "
        "WHERE user_id = ? AND provider = 'oura' AND data_type = 'daily_summary' "
        "AND external_id = ?",
        (user_id, day),
    ).fetchone()
    existing: dict[str, Any] = {}
    if row and row['raw_payload']:
        rp = row['raw_payload']
        existing = rp if isinstance(rp, dict) else json.loads(rp)
    existing.update(partial)
    existing['date'] = day
    db.execute(
        'INSERT INTO provider_raw_record '
        '(user_id, provider, data_type, external_id, observed_at, raw_payload) '
        "VALUES (?, 'oura', 'daily_summary', ?, ?, ?::jsonb) "
        'ON CONFLICT (user_id, provider, data_type, external_id) DO UPDATE SET '
        '    observed_at = EXCLUDED.observed_at, '
        '    raw_payload = EXCLUDED.raw_payload, '
        '    fetched_at = NOW()',
        (user_id, day, day, json.dumps(existing)),
    )
