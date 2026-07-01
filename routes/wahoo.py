"""Wahoo integration — OAuth connect + webhook ingest (#681 (B) live wiring).

Wahoo Cloud API (api.wahooligan.com). Unlike Strava/Whoop's thin pointers, a
Wahoo `workout_summary` webhook pushes the summary metrics inline, so the base
ingest is synchronous-from-payload (like COROS) — no REST fetch needed for the
summary. When the payload links a full FIT file (`workout_summary.file.url`,
#1093), that's fetched too (fresh OAuth token, `garmin_fit_parser.parse_fit`
reused as-is — FIT is a vendor-neutral format) and its stream-level fields
(max HR/power/cadence, normalized power, training effect, running dynamics)
enrich the summary's rolled-up averages. Discipline resolution + provider
tagging always stay Wahoo's own matrix-§10.2 `workout_type_id` mapping, not
the FIT sport enum, so a FIT-enriched activity resolves identically to a
summary-only one. The FIT fetch/parse is best-effort — any failure falls back
to the summary-only fields, never blocking the base import.

- `GET  /wahoo/oauth/start`     — CSRF state + return_to → redirect to consent.
- `GET  /wahoo/oauth/callback`  — exchange code for tokens; the token response
                                  has no user id, so fetch `/v1/user` for it
                                  (webhook reverse-lookup needs it); persist +
                                  scope ack. On any failure it redirects back to
                                  `return_to` with `?wahoo_oauth_error=<reason>`
                                  (not a bare abort) so the connect screen can
                                  say what broke.

CONFIG (go-live): set `WAHOO_CLIENT_ID` + `WAHOO_CLIENT_SECRET`, and register
the developer-portal redirect_uri EXACTLY as `…/wahoo/oauth/callback` (what
`oauth_start` sends). A mismatch (e.g. the old `/auth/wahoo/callback` stub) makes
Wahoo error right after the user logs in — the most common "login showed but
then errored" failure.
- `POST /wahoo/webhook`         — verify the configured webhook token, record to
                                  `webhook_events`, map `user.id` → local user,
                                  and ingest the `workout_summary` → `cardio_log`
                                  (source='wahoo', `wahoo_workout_id` dedup).

Mapping per `specs/Provider_Inbound_Matrix_v2.md` §10.2: `workout_type_id` →
discipline via the #681 resolver; distance m→mi, ascent m→ft, duration s→min;
HR/power/cadence canonical; `work_accum` is JOULES (÷4184→kcal).

BEST-EFFORT / VERIFY-OWED (Rule #14): the OAuth/token/user/webhook surface +
the webhook payload shape are Wahoo's documented form, env-overridable, unverified
against live payloads from the container — confirm at go-live. `ftp_w` from the
power-zones endpoint is a later refinement (the workout webhook doesn't carry it).
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
from provider_cardio_resolve import resolve_cardio_discipline
from routes import account_merge
from routes import provider_auth as pa
from routes import provider_identity as pi
from routes.auth import current_user_id, send_verification_email

bp = Blueprint('wahoo', __name__, url_prefix='/wahoo')

_WAHOO_AUTH_URL = os.environ.get('WAHOO_AUTH_URL', 'https://api.wahooligan.com/oauth/authorize')
_WAHOO_TOKEN_URL = os.environ.get('WAHOO_TOKEN_URL', 'https://api.wahooligan.com/oauth/token')
_WAHOO_USER_URL = os.environ.get('WAHOO_USER_URL', 'https://api.wahooligan.com/v1/user')

# Read scopes per matrix §10.2 + offline_data (refresh token + the workout
# webhook). Space-separated. Bump the version on change.
_WAHOO_SCOPES = 'user_read workouts_read power_zones_read offline_data'
_WAHOO_SCOPE_VERSION = '2026-06-20'

_OAUTH_STATE = 'wahoo_oauth_state'
_OAUTH_RETURN_TO = 'wahoo_oauth_return_to'
_OAUTH_INTENT = 'wahoo_oauth_intent'  # 'signin' (no session) vs 'connect' (logged in)

_M_TO_MI = 0.000621371
_M_TO_FT = 3.28084
_J_TO_KCAL = 1.0 / 4184.0


# ── OAuth initiation ──────────────────────────────────────────────────

@bp.route('/oauth/start', methods=['GET'])
def oauth_start():
    # No session = "sign in / sign up with Wahoo" (design §6.1), gated by the
    # feature flag. When the flag is off, keep the legacy behaviour: bounce to
    # login so OAuth is connect-only for an authenticated athlete.
    signin = current_user_id() is None
    if signin and not pi.signin_enabled():
        return redirect(url_for('auth.login', next=request.url))
    client_id = os.environ.get('WAHOO_CLIENT_ID')
    if not client_id:
        current_app.logger.error('WAHOO_CLIENT_ID not configured')
        abort(503)
    state = secrets.token_urlsafe(32)
    session[_OAUTH_STATE] = state
    if signin:
        intent = 'signin'
    elif request.args.get('intent') == 'merge':
        intent = 'merge'  # account-merge entry (design §6) — prove the other account
    else:
        intent = 'connect'
    session[_OAUTH_INTENT] = intent
    return_to = request.args.get('return_to') or '/'
    if not return_to.startswith('/') or return_to.startswith('//'):
        return_to = '/'
    session[_OAUTH_RETURN_TO] = return_to
    params = {
        'client_id': client_id,
        'redirect_uri': url_for('wahoo.oauth_callback', _external=True),
        'response_type': 'code',
        'scope': _WAHOO_SCOPES,
        'state': state,
    }
    return redirect(f'{_WAHOO_AUTH_URL}?{urllib.parse.urlencode(params)}')


# ── OAuth callback ────────────────────────────────────────────────────

@bp.route('/oauth/callback', methods=['GET'])
def oauth_callback():
    user_id = current_user_id()
    signin = user_id is None
    intent = session.pop(_OAUTH_INTENT, None)
    if signin and not pi.signin_enabled():
        return redirect(url_for('auth.login'))
    expected_state = session.pop(_OAUTH_STATE, None)
    return_to = session.pop(_OAUTH_RETURN_TO, '/')
    received_state = request.args.get('state')
    if not expected_state or not received_state or not hmac.compare_digest(
        expected_state, received_state,
    ):
        current_app.logger.warning('Wahoo OAuth state mismatch for user %s', user_id)
        abort(400)

    def _fail(reason: str):
        """Bounce back to the originating screen with a readable reason rather
        than dead-ending on a bare error page. Both connect surfaces (onboarding
        Step 2 + the connections hub) render `?wahoo_oauth_error=` as a
        '<provider> did not connect' alert, so the athlete sees what went wrong
        and the matching `current_app.logger` line above is the breadcrumb."""
        sep = '&' if '?' in return_to else '?'
        return redirect(f'{return_to}{sep}wahoo_oauth_error={reason}')

    if 'error' in request.args:
        return _fail(request.args.get('error') or 'denied')
    code = request.args.get('code')
    if not code:
        return _fail('no_code')
    client_id = os.environ.get('WAHOO_CLIENT_ID')
    client_secret = os.environ.get('WAHOO_CLIENT_SECRET')
    if not client_id or not client_secret:
        current_app.logger.error('Wahoo client credentials not configured')
        return _fail('not_configured')
    redirect_uri = url_for('wahoo.oauth_callback', _external=True)
    try:
        resp = requests.post(_WAHOO_TOKEN_URL, data={
            'grant_type': 'authorization_code',
            'code': code,
            'client_id': client_id,
            'client_secret': client_secret,
            'redirect_uri': redirect_uri,
        }, timeout=10)
        resp.raise_for_status()
        token_data = resp.json()
    except requests.RequestException as exc:
        current_app.logger.exception('Wahoo token exchange failed: %s', exc)
        return _fail('token_exchange_failed')

    access_token = token_data.get('access_token')
    refresh_token = token_data.get('refresh_token')
    expires_in = token_data.get('expires_in')
    if not access_token:
        current_app.logger.error('Wahoo token response missing access_token: %s', token_data)
        return _fail('no_access_token')

    db = get_db()

    # ── No-session sign-in / sign-up (design §6.1) ────────────────────────
    if signin:
        # Need id + email + name for the account, so fetch the full profile
        # (the connect path below only needs the id).
        prof = _fetch_wahoo_profile(access_token)
        wahoo_user_id = prof.get('id')
        if wahoo_user_id is None:
            current_app.logger.error('Wahoo profile missing user id (signin)')
            abort(502)
        wahoo_user_id = str(wahoo_user_id)

        identity = pi.get_identity(db, 'wahoo', wahoo_user_id)
        if identity:  # existing account → log in
            user_id = identity['user_id']
            pi.bump_last_login(db, identity['id'])
            username = pi.get_username(db, user_id)
            dest = url_for('dashboard.index')
            print(f'[wahoo-signin] match user={user_id} '  # noqa: T201
                  f'wahoo_user_id={wahoo_user_id}')
        else:  # new athlete → create a passwordless account
            display = ' '.join(
                p for p in (prof.get('first'), prof.get('last')) if p
            ) or None
            user_id, username = pi.create_signin_user(
                db, provider='wahoo', provider_user_id=wahoo_user_id,
                email=prof.get('email'), display_name=display,
                username_hint=prof.get('first') or display,
            )
            dest = url_for('onboarding.connect')
            print(f'[wahoo-signin] new-account user={user_id} '  # noqa: T201
                  f'wahoo_user_id={wahoo_user_id} username={username}')
            # Confirm the provider-seeded email if one was actually stored
            # (dropped to NULL on collision). Best-effort — never block sign-in.
            acct_email = pi.get_email(db, user_id)
            if acct_email:
                try:
                    send_verification_email(db, user_id, acct_email)
                except Exception:
                    pass

        # Write the sync credential + scope ack just like the connect path, so
        # D-58 prefill has tokens immediately for the just-signed-in athlete.
        _persist_wahoo_auth(db, user_id, access_token, refresh_token,
                            expires_in, wahoo_user_id)
        session.clear()
        session['user_id'] = user_id
        session['username'] = username
        return redirect(dest)

    # ── Logged-in connect / link path ─────────────────────────────────────
    wahoo_user_id = (token_data.get('user') or {}).get('id')
    if wahoo_user_id is None:
        try:
            prof = requests.get(_WAHOO_USER_URL,
                                headers={'Authorization': f'Bearer {access_token}'},
                                timeout=10)
            prof.raise_for_status()
            wahoo_user_id = prof.json().get('id')
        except requests.RequestException as exc:
            current_app.logger.exception('Wahoo user fetch failed: %s', exc)
            return _fail('profile_fetch_failed')
    if wahoo_user_id is None:
        current_app.logger.error('Wahoo user id missing')
        return _fail('no_user_id')
    wahoo_user_id = str(wahoo_user_id)

    # ── Account-merge entry (design §6) ───────────────────────────────────
    # OAuth proved control of whatever account owns this Wahoo identity; if
    # that's a DIFFERENT account, stage it as the merge "drop" and bounce to
    # the confirm screen (no persist/link here — the merge re-points drop→keep).
    if intent == 'merge':
        other = pi.get_identity(db, 'wahoo', wahoo_user_id)
        sep = '&' if '?' in return_to else '?'
        if other and other['user_id'] != user_id:
            account_merge.stage_merge(session, other['user_id'])
            return redirect(url_for('profile.merge_confirm'))
        return redirect(f'{return_to}{sep}merge_error=nothing_to_merge')

    _persist_wahoo_auth(db, user_id, access_token, refresh_token,
                        expires_in, wahoo_user_id)
    # Record the identity link so Wahoo can later sign this athlete in
    # (design §6.2). Refuse if the Wahoo account already links elsewhere.
    sep = '&' if '?' in return_to else '?'
    ok, reason = pi.link_identity(db, user_id, 'wahoo', wahoo_user_id)
    if not ok and reason == 'claimed_by_other':
        current_app.logger.warning(
            'Wahoo identity %s already linked to another account', wahoo_user_id)
        return redirect(f'{return_to}{sep}wahoo_oauth_error=already_linked')
    print(f'[wahoo-oauth] connected user={user_id} wahoo_user_id={wahoo_user_id} '  # noqa: T201
          f'expires_in={expires_in}')
    return redirect(f'{return_to}{sep}wahoo_connected=1')


def _fetch_wahoo_profile(access_token: str) -> dict:
    """Best-effort GET /v1/user → {id, email, first, last}. Returns {} on
    failure (caller treats a missing id as fatal).

    VERIFY-OWED (Rule #14): only `id` is exercised by the connect path today;
    confirm `email` / `first` / `last` are present under the `user_read` scope
    against a live payload before flipping PROVIDER_OAUTH_SIGNIN on. If they're
    absent, sign-in still works (id-only) — the account just gets no email seed
    and a name-less synthesized username."""
    try:
        resp = requests.get(_WAHOO_USER_URL,
                            headers={'Authorization': f'Bearer {access_token}'},
                            timeout=10)
        resp.raise_for_status()
        data = resp.json() or {}
    except requests.RequestException as exc:
        current_app.logger.exception('Wahoo profile fetch failed: %s', exc)
        return {}
    return {
        'id': data.get('id'),
        'email': data.get('email'),
        'first': data.get('first') or data.get('first_name'),
        'last': data.get('last') or data.get('last_name'),
    }


def _persist_wahoo_auth(db, user_id, access_token, refresh_token,
                        expires_in, wahoo_user_id) -> None:
    """Upsert the provider_auth sync credential + record the scope ack. Shared
    by the sign-in and connect paths so the persisted shape is identical."""
    token_expires_at = (
        datetime.now(timezone.utc) + timedelta(seconds=int(expires_in))
        if expires_in else None
    )
    pa.upsert_auth(
        db, user_id=user_id, provider='wahoo',
        access_token=access_token, refresh_token=refresh_token,
        token_expires_at=token_expires_at, provider_user_id=str(wahoo_user_id),
        scopes=_WAHOO_SCOPES, status=pa.STATUS_ACTIVE,
        registered_at=datetime.now(timezone.utc),
    )
    pa.record_oauth_scope_ack(
        db, user_id=user_id, provider='wahoo',
        scopes_granted=_WAHOO_SCOPES, version_id=_WAHOO_SCOPE_VERSION,
    )


# ── Webhook (push-with-data; ingest synchronously) ────────────────────

@bp.route('/webhook', methods=['GET', 'POST'])
def webhook():
    if request.method == 'GET':
        return jsonify(status='ok'), 200

    raw_body = request.get_data(as_text=True) or ''
    try:
        event = json.loads(raw_body) if raw_body else {}
    except json.JSONDecodeError:
        event = {}
    if not isinstance(event, dict):
        event = {}

    # Wahoo includes the registered webhook token in each push; verify it when
    # configured (the only authenticity signal Wahoo offers for the workout push).
    expected_token = os.environ.get('WAHOO_WEBHOOK_TOKEN')
    received_token = str(event.get('webhook_token') or '')
    sig_ok = (not expected_token) or hmac.compare_digest(received_token, expected_token)

    wahoo_user_id = (event.get('user') or {}).get('id') or event.get('user_id')
    summary = event.get('workout_summary') or {}
    workout_id = summary.get('id') or (event.get('workout') or {}).get('id')

    db = get_db()
    auth_row = (
        pa.get_auth_by_provider_user_id(db, 'wahoo', str(wahoo_user_id))
        if wahoo_user_id is not None else None
    )
    user_id = auth_row['user_id'] if auth_row else None

    cur = db.execute(
        'INSERT INTO webhook_events '
        '(provider, event_type, provider_user_id, entity_id, user_id, '
        ' payload, signature_ok, received_at) '
        'VALUES (?, ?, ?, ?, ?, ?, ?, NOW()) RETURNING id',
        ('wahoo', event.get('event_type'),
         str(wahoo_user_id) if wahoo_user_id is not None else None,
         str(workout_id) if workout_id is not None else None,
         user_id, raw_body, sig_ok),
    )
    event_id = cur.fetchone()['id']
    db.commit()

    if sig_ok and user_id is not None and summary and workout_id is not None:
        try:
            _ingest_workout_summary(db, user_id, str(workout_id), summary)
            db.execute('UPDATE webhook_events SET processed_at = NOW() WHERE id = ?',
                       (event_id,))
            db.commit()
        except Exception as exc:  # noqa: BLE001
            current_app.logger.exception('Wahoo ingestion failed for event %s', event_id)
            db.execute('UPDATE webhook_events SET processed_at = NOW(), error = ? WHERE id = ?',
                       (str(exc)[:500], event_id))
            db.commit()

    return jsonify(status='ok'), 200


# ── Ingest ────────────────────────────────────────────────────────────

def _as_int(value: Any) -> int | None:
    if value is None or value == '':
        return None
    try:
        return int(round(float(value)))
    except (TypeError, ValueError):
        return None


def normalize_wahoo_summary(summary: dict) -> dict:
    """Wahoo `workout_summary` → the shared cardio dict (matrix §10.2 units).
    `workout_type_id` → discipline via the #681 resolver; `work_accum` is joules
    (÷4184→kcal), falling back to `calories_accum`.

    The live webhook nests the workout's type/name/start under a `workout`
    sub-object (`workout_summary.workout.*`); only the accumulator metrics sit
    directly on the summary. Read nested-first with a top-level fallback so a
    flattened payload still resolves. Verified against a live push (2026-06-22):
    `workout.workout_type_id=12` (BIKING_INDOOR), `workout.name`, and the summary
    carries `started_at` (the parser previously read only `starts`/`start_time`/
    `created_at`, so it fell back to the upload time)."""
    workout = summary.get('workout') or {}
    type_id = workout.get('workout_type_id')
    if type_id is None:
        type_id = summary.get('workout_type_id')
    res = resolve_cardio_discipline('wahoo', str(type_id) if type_id is not None else None)
    dist_m = summary.get('distance_accum')
    dur_s = summary.get('duration_total_accum')
    active_s = summary.get('duration_active_accum')
    ascent_m = summary.get('ascent_accum')
    work_j = summary.get('work_accum')
    calories = summary.get('calories_accum')
    kcal = (float(work_j) * _J_TO_KCAL) if work_j not in (None, '') else None
    name = workout.get('name') or summary.get('name')
    start = (summary.get('started_at') or workout.get('starts')
             or summary.get('starts') or summary.get('start_time')
             or summary.get('created_at'))
    activity_date = (str(start)[:10] if start else
                     datetime.now(timezone.utc).date().isoformat())
    return {
        'date': activity_date,
        'activity': res.plan_sport_type or 'other',
        'activity_name': name,
        'duration_min': (float(dur_s) / 60) if dur_s not in (None, '') else None,
        'moving_time_min': (float(active_s) / 60) if active_s not in (None, '') else None,
        'distance_mi': (float(dist_m) * _M_TO_MI) if dist_m not in (None, '') else None,
        'avg_hr': _as_int(summary.get('heart_rate_avg')),
        'calories': _as_int(kcal if kcal is not None else calories),
        'elev_gain_ft': (float(ascent_m) * _M_TO_FT) if ascent_m not in (None, '') else None,
        'avg_cadence': _as_int(summary.get('cadence_avg')),
        'avg_power': _as_int(summary.get('power_avg') or summary.get('power_bike_avg')),
        'discipline_id': res.discipline_id,
        '_provider_raw': {
            'provider': 'wahoo', 'observed_at': str(start) if start else None,
            'bucket': res.bucket, 'canonical_ref': res.discipline_id,
            'payload': {'workout_type_id': type_id, 'indoor_machine': None,
                        'wahoo_workout_id': summary.get('id')},
        },
    }


def _wahoo_fit_url(summary: dict) -> str | None:
    """The linked full-FIT-file URL (#1093), nested-first under `workout` (the
    live shape observed 2026-06-22 for other fields, see normalize_wahoo_summary)
    with a top-level fallback. BEST-EFFORT/VERIFY-OWED (Rule #14) — unconfirmed
    against a live payload that actually carries a file link."""
    workout = summary.get('workout') or {}
    return ((workout.get('file') or {}).get('url')
            or (summary.get('file') or {}).get('url'))


# Fields the FIT stream carries that Wahoo's inline JSON summary doesn't (or
# only as a rolled-up average) — max HR/cadence/power, normalized power,
# training effect, running dynamics. Overlaid onto the summary dict only where
# the summary itself has nothing (never overrides a summary-derived value).
_FIT_STREAM_FIELDS = (
    'max_hr', 'moving_time_min', 'elev_loss_ft', 'max_cadence',
    'max_power', 'norm_power', 'aerobic_te', 'anaerobic_te',
    'swolf', 'active_lengths', 'stride_length_m',
    'vert_oscillation_cm', 'vert_ratio_pct', 'gct_ms', 'gct_balance',
)


def _fetch_wahoo_fit_stream(db: Any, user_id: int, file_url: str) -> bytes | None:
    """Best-effort GET of the FIT file linked from a workout_summary (#1093)
    using a fresh OAuth token. Returns None on any failure (no token, network,
    non-2xx) — the summary fields alone are still a complete cardio_log row, so
    a fetch failure must never block that base import."""
    token = pa.get_fresh_access_token(
        db, user_id, 'wahoo',
        token_url=_WAHOO_TOKEN_URL,
        client_id=os.environ.get('WAHOO_CLIENT_ID'),
        client_secret=os.environ.get('WAHOO_CLIENT_SECRET'),
    )
    if not token:
        return None
    try:
        resp = requests.get(file_url, headers={'Authorization': f'Bearer {token}'},
                            timeout=15)
        resp.raise_for_status()
        return resp.content
    except requests.RequestException as exc:
        current_app.logger.warning('Wahoo FIT stream fetch failed: %s', exc)
        return None


def _merge_fit_stream_fields(data: dict, fit_bytes: bytes) -> bool:
    """Parse the linked FIT (reusing `garmin_fit_parser.parse_fit` directly —
    FIT is a vendor-neutral format, not extracting a shared module per the
    plan's scope) and overlay its stream-level fields onto the Wahoo summary
    dict. Discipline resolution + provider tagging are left untouched (Wahoo's
    own matrix §10.2 mapping, not the FIT sport enum). Returns whether any
    field was added; any parse failure (malformed FIT, strength-only session)
    is swallowed — best-effort enrichment, not a required input."""
    from garmin_fit_parser import parse_fit
    try:
        parsed = parse_fit(fit_bytes)
    except Exception as exc:  # noqa: BLE001 — best-effort, never break the import
        current_app.logger.warning('Wahoo FIT stream parse failed: %s', exc)
        return False
    if parsed.get('log_type') != 'cardio':
        return False
    fit_data = parsed['data']
    added = False
    for field in _FIT_STREAM_FIELDS:
        val = fit_data.get(field)
        if val is not None and data.get(field) is None:
            data[field] = val
            added = True
    return added


def _ingest_workout_summary(db: Any, user_id: int, workout_id: str, summary: dict) -> bool:
    """Write a Wahoo workout_summary to cardio_log (idempotent on
    (user_id, wahoo_workout_id)). When the payload links a full FIT file
    (#1093), fetch + parse it to fill in the stream-level fields the inline
    summary doesn't carry (see module docstring)."""
    if db.execute(
        'SELECT id FROM cardio_log WHERE wahoo_workout_id = ? AND user_id = ?',
        (workout_id, user_id),
    ).fetchone() is not None:
        print(f'[wahoo-ingest] workout={workout_id} user={user_id} SKIP already-imported')  # noqa: T201
        return False
    from routes.garmin import _bulk_insert_cardio
    data = normalize_wahoo_summary(summary)
    fit_stream_used = False
    file_url = _wahoo_fit_url(summary)
    if file_url:
        fit_bytes = _fetch_wahoo_fit_stream(db, user_id, file_url)
        if fit_bytes:
            fit_stream_used = _merge_fit_stream_fields(data, fit_bytes)
    _bulk_insert_cardio(db, data, user_id, workout_id, source='wahoo')
    print(f'[wahoo-ingest] workout={workout_id} user={user_id} '  # noqa: T201
          f'-> cardio_log discipline={data.get("discipline_id")} '
          f'bucket={data["_provider_raw"]["bucket"]} fit_stream_used={fit_stream_used}')
    return True
