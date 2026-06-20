"""TrainingPeaks integration — OAuth connect + structured-workout PUSH
(#681 Wave 3b outbound, Slice 2).

TrainingPeaks is a *destination*: we push planned structured workouts to it via
`POST /v2/workouts/plan` (matrix §11.1 outbound). Inbound (completed workouts /
metrics) is partner-gated and out of scope here — this connector is outbound-only.

- `GET  /trainingpeaks/oauth/start`     — CSRF state → consent redirect.
- `GET  /trainingpeaks/oauth/callback`  — code→token exchange; fetch the athlete
                                          id (`/v1/athlete/profile`); persist.
- `POST /trainingpeaks/push/<pv>/<date>/<idx>` — serialize one cardio plan-session
                                          (`outbound_workout.to_tp_structure`) and
                                          push it, idempotent via
                                          `provider_outbound_ref` (pushed_payload_hash
                                          → no-op when unchanged, update when changed).
- `GET/POST /trainingpeaks/webhook`     — Phase-0 stub kept (auth-exempt reference
                                          in app.py); inbound is partner-gated.

GATED / VERIFY-OWED (matrix §11.1): TrainingPeaks partner access is approval-gated
("no personal use," reportedly paused to new partners), so this is **untestable
against live TP** — the auth/profile/push URLs + the `/plan` body shape are the
documented form, env-overridable, and owed a live verify if/when partner access
opens. Built per Andy's explicit "full Wave 3b" call (2026-06-20).
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
from plan_sessions_repo import load_plan_session_payload
from provider_cardio_resolve import DISCIPLINE_TO_PLAN_SPORT
from routes import provider_auth as pa
from routes.auth import current_user_id
from routes.outbound_workout import to_tp_structure

bp = Blueprint('trainingpeaks', __name__, url_prefix='/trainingpeaks')

_TP_AUTH_URL = os.environ.get('TP_AUTH_URL', 'https://oauth.trainingpeaks.com/OAuth/Authorize')
_TP_TOKEN_URL = os.environ.get('TP_TOKEN_URL', 'https://oauth.trainingpeaks.com/oauth/token')
_TP_PROFILE_URL = os.environ.get('TP_PROFILE_URL', 'https://api.trainingpeaks.com/v1/athlete/profile')
_TP_PLAN_URL = os.environ.get('TP_PLAN_URL', 'https://api.trainingpeaks.com/v2/workouts/plan')

# Outbound needs the plan-write scope (matrix §11.1). Space-separated.
_TP_SCOPES = 'athlete:profile workouts:plan'
_TP_SCOPE_VERSION = '2026-06-20'

_OAUTH_STATE = 'tp_oauth_state'
_OAUTH_RETURN_TO = 'tp_oauth_return_to'

# coarse `_plan_sport_type` → TP `WorkoutType` (matrix §11.1 enum).
_TP_WORKOUT_TYPE = {
    'running': 'run', 'cycling': 'bike', 'swimming': 'swim', 'hiking': 'walk',
}


# ── OAuth initiation ──────────────────────────────────────────────────

@bp.route('/oauth/start', methods=['GET'])
def oauth_start():
    if current_user_id() is None:
        return redirect(url_for('auth.login', next=request.url))
    client_id = os.environ.get('TP_CLIENT_ID')
    if not client_id:
        current_app.logger.error('TP_CLIENT_ID not configured')
        abort(503)
    state = secrets.token_urlsafe(32)
    session[_OAUTH_STATE] = state
    return_to = request.args.get('return_to') or '/'
    if not return_to.startswith('/') or return_to.startswith('//'):
        return_to = '/'
    session[_OAUTH_RETURN_TO] = return_to
    params = {
        'client_id': client_id,
        'redirect_uri': url_for('trainingpeaks.oauth_callback', _external=True),
        'response_type': 'code',
        'scope': _TP_SCOPES,
        'state': state,
    }
    return redirect(f'{_TP_AUTH_URL}?{urllib.parse.urlencode(params)}')


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
        current_app.logger.warning('TrainingPeaks OAuth state mismatch for user %s', user_id)
        abort(400)
    if 'error' in request.args:
        return redirect(f'{return_to}?trainingpeaks_oauth_error={request.args.get("error")}')
    code = request.args.get('code')
    if not code:
        abort(400)
    client_id = os.environ.get('TP_CLIENT_ID')
    client_secret = os.environ.get('TP_CLIENT_SECRET')
    if not client_id or not client_secret:
        current_app.logger.error('TrainingPeaks client credentials not configured')
        abort(503)
    redirect_uri = url_for('trainingpeaks.oauth_callback', _external=True)
    try:
        resp = requests.post(_TP_TOKEN_URL, data={
            'grant_type': 'authorization_code',
            'code': code,
            'client_id': client_id,
            'client_secret': client_secret,
            'redirect_uri': redirect_uri,
        }, timeout=10)
        resp.raise_for_status()
        token_data = resp.json()
    except requests.RequestException as exc:
        current_app.logger.exception('TrainingPeaks token exchange failed: %s', exc)
        abort(502)

    access_token = token_data.get('access_token')
    refresh_token = token_data.get('refresh_token')
    expires_in = token_data.get('expires_in')
    if not access_token:
        current_app.logger.error('TrainingPeaks token response missing access_token')
        abort(502)

    # The token response carries no athlete id → fetch the profile for it.
    tp_athlete_id = None
    try:
        prof = requests.get(_TP_PROFILE_URL,
                            headers={'Authorization': f'Bearer {access_token}'},
                            timeout=10)
        prof.raise_for_status()
        tp_athlete_id = prof.json().get('Id') or prof.json().get('AthleteId')
    except requests.RequestException as exc:
        current_app.logger.exception('TrainingPeaks profile fetch failed: %s', exc)
        abort(502)

    token_expires_at = (
        datetime.now(timezone.utc) + timedelta(seconds=int(expires_in))
        if expires_in else None
    )
    db = get_db()
    pa.upsert_auth(
        db, user_id=user_id, provider='trainingpeaks',
        access_token=access_token, refresh_token=refresh_token,
        token_expires_at=token_expires_at,
        provider_user_id=str(tp_athlete_id) if tp_athlete_id is not None else None,
        scopes=_TP_SCOPES, status=pa.STATUS_ACTIVE,
        registered_at=datetime.now(timezone.utc),
    )
    pa.record_oauth_scope_ack(
        db, user_id=user_id, provider='trainingpeaks',
        scopes_granted=_TP_SCOPES, version_id=_TP_SCOPE_VERSION,
    )
    print(f'[tp-oauth] connected user={user_id} tp_athlete_id={tp_athlete_id} '  # noqa: T201
          f'expires_in={expires_in}')
    sep = '&' if '?' in return_to else '?'
    return redirect(f'{return_to}{sep}trainingpeaks_connected=1')


# ── Webhook stub (inbound partner-gated; kept for the auth-exempt ref) ──

@bp.route('/webhook', methods=['GET', 'POST'])
def webhook():
    return jsonify(status='ok'), 200


# ── Outbound push ─────────────────────────────────────────────────────

def _tp_workout_body(session_payload: dict[str, Any], athlete_id: str | None) -> dict[str, Any]:
    """Build the `POST /v2/workouts/plan` body for a cardio session
    (documented form; verify-owed). Raises ValueError for a non-exportable
    session (propagated from the serializer)."""
    structure = to_tp_structure(session_payload)
    coarse = DISCIPLINE_TO_PLAN_SPORT.get(session_payload.get('discipline_id') or '')
    title = (f"AIDSTATION {session_payload.get('discipline_name') or 'Workout'} "
             f"{session_payload.get('date') or ''}").strip()
    return {
        'AthleteId': athlete_id,
        'Title': title,
        'WorkoutDay': session_payload.get('date'),
        'WorkoutType': _TP_WORKOUT_TYPE.get(coarse or '', 'other'),
        'IntensityTargetType': structure['IntensityTargetType'],
        'Structure': structure['Structure'],
    }


@bp.route('/push/<int:plan_version_id>/<date>/<int:idx>', methods=['POST'])
def push_session(plan_version_id: int, date: str, idx: int):
    """Push one cardio plan-session to TrainingPeaks as a planned workout.

    Idempotent via `provider_outbound_ref` (user, 'trainingpeaks', session_id):
    same payload hash → no-op; changed → re-push + update. 404 unknown session;
    400 non-exportable; 409 if TrainingPeaks isn't connected.
    """
    uid = current_user_id()
    db = get_db()
    payload = load_plan_session_payload(db, uid, plan_version_id, date, idx)
    if payload is None:
        print(f'[tp-push] user={uid} pv={plan_version_id} {date}#{idx} -> 404')  # noqa: T201
        abort(404)

    auth = pa.get_auth(db, uid, 'trainingpeaks')
    if not auth or auth.get('status') != pa.STATUS_ACTIVE:
        print(f'[tp-push] user={uid} -> 409 not connected')  # noqa: T201
        abort(409, description='TrainingPeaks not connected')

    try:
        body = _tp_workout_body(payload, auth.get('provider_user_id'))
    except ValueError as exc:
        print(f'[tp-push] user={uid} pv={plan_version_id} {date}#{idx} -> 400 {exc}')  # noqa: T201
        abort(400, description=str(exc))

    session_id = payload.get('session_id') or f'{plan_version_id}:{date}:{idx}'
    payload_hash = hashlib.sha256(
        json.dumps(body, sort_keys=True, default=str).encode()).hexdigest()

    existing = db.execute(
        'SELECT id, pushed_payload_hash, external_id FROM provider_outbound_ref '
        'WHERE user_id = ? AND provider = ? AND session_id = ?',
        (uid, 'trainingpeaks', session_id),
    ).fetchone()
    if existing and existing['pushed_payload_hash'] == payload_hash:
        print(f'[tp-push] user={uid} session={session_id} -> no-op (unchanged)')  # noqa: T201
        return jsonify(status='unchanged', external_id=existing['external_id']), 200

    token = pa.get_fresh_access_token(
        db, uid, 'trainingpeaks', token_url=_TP_TOKEN_URL,
        client_id=os.environ.get('TP_CLIENT_ID'),
        client_secret=os.environ.get('TP_CLIENT_SECRET'),
    )
    if not token:
        print(f'[tp-push] user={uid} -> 409 no usable token')  # noqa: T201
        abort(409, description='TrainingPeaks token unavailable; reconnect')

    try:
        resp = requests.post(
            _TP_PLAN_URL, json=body,
            headers={'Authorization': f'Bearer {token}'}, timeout=15)
        resp.raise_for_status()
        external_id = str((resp.json() or {}).get('Id') or '')
    except requests.RequestException as exc:
        current_app.logger.exception('TrainingPeaks push failed: %s', exc)
        _record_outbound(db, existing, uid, session_id, payload_hash, None, pa.STATUS_ERROR)
        abort(502, description='TrainingPeaks push failed')

    status = 'updated' if existing else 'pushed'
    _record_outbound(db, existing, uid, session_id, payload_hash, external_id, status)
    print(f'[tp-push] user={uid} session={session_id} -> {status} '  # noqa: T201
          f'tp_workout={external_id} type={body["WorkoutType"]}')
    return jsonify(status=status, external_id=external_id), 200


def _record_outbound(db, existing, uid, session_id, payload_hash, external_id, status):
    """Upsert the `provider_outbound_ref` ledger row (tier-2 = structured workout)."""
    if existing:
        db.execute(
            'UPDATE provider_outbound_ref SET external_id = ?, '
            'pushed_payload_hash = ?, status = ?, updated_at = NOW() WHERE id = ?',
            (external_id, payload_hash, status, existing['id']),
        )
    else:
        db.execute(
            'INSERT INTO provider_outbound_ref '
            '(user_id, provider, session_id, external_id, tier, '
            ' pushed_payload_hash, status) VALUES (?, ?, ?, ?, 2, ?, ?)',
            (uid, 'trainingpeaks', session_id, external_id, payload_hash, status),
        )
    db.commit()
