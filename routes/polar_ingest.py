"""Polar AccessLink payload ingestion — webhook notifications to
per-provider tables and `cardio_log`.

Called from `routes/polar.py:webhook` after signature has been verified
and the per-notification row recorded in `webhook_events`. Polar
delivers notifications, not data — for each event we fetch the named
resource from AccessLink before persisting:

  - EXERCISE → POST /v3/users/{uid}/exercise-transactions → GET the
              transaction URI → GET each exercise URL → upsert into
              `cardio_log` keyed on (user_id, polar_exercise_id) → PUT
              the transaction URI to commit (Polar then stops re-queuing
              those exercises in subsequent transactions).
  - SLEEP → GET /v3/users/{uid}/sleep (or the notification's `url`) →
            upsert per-date into `polar_sleep`.
  - NIGHTLY_RECHARGE → GET /v3/users/{uid}/nightly-recharge → upsert
            per-date into `polar_nightly_recharge`.
  - CARDIO_LOAD → GET /v3/users/{uid}/cardio-load → upsert per-date
            into `polar_cardio_load`.
  - CONTINUOUS_HEART_RATE → GET the resource → upsert per-timestamp
            into `polar_continuous_hr_samples`.

Per Integration v4 §5.3 + §6. The exercise-transaction handshake is
Polar-specific; the daily pulls are direct reads with no commit step.
Any per-notification failure raises so the caller (the webhook handler)
records the error against `webhook_events` and the row stays for later
re-dispatch.

The full AccessLink payload surface is wider than what we read here;
unmapped fields are preserved in `raw_payload` where the destination
table supports it, and the raw notification body is in
`webhook_events.payload` for re-derivation without a re-fetch.
"""
from __future__ import annotations

import json
import os
from datetime import datetime, timezone
from typing import Any

import requests
from flask import current_app

# Polar AccessLink base URL. Mirror the env override in routes/polar.py
# so the two modules can rotate independently of code.
_POLAR_API_URL = os.environ.get(
    'POLAR_API_URL', 'https://www.polaraccesslink.com',
)

# Polar sport strings → v1 `cardio_log.activity` vocabulary. Per
# AccessLink docs the `sport` field is an uppercase enum. Unmapped sports
# fall through to 'other' so ingestion never drops rows.
_SPORT_MAP = {
    'RUNNING': 'run',
    'JOGGING': 'run',
    'TRAIL_RUNNING': 'trail_run',
    'TREADMILL_RUNNING': 'run',
    'ROAD_RUNNING': 'run',
    'CYCLING': 'cycle',
    'ROAD_BIKING': 'cycle',
    'INDOOR_CYCLING': 'cycle',
    'MOUNTAIN_BIKING': 'cycle',
    'SWIMMING': 'swim',
    'POOL_SWIMMING': 'swim',
    'OPEN_WATER_SWIMMING': 'swim',
    'TRIATHLON': 'triathlon',
    'STRENGTH_TRAINING': 'strength',
    'HIKING': 'hike',
    'CROSS-COUNTRY_SKIING': 'ski',
    'SKIING': 'ski',
    'SKI_TOURING': 'ski_touring',
    'ROWING': 'rowing',
    'INDOOR_ROWING': 'rowing',
    'WALKING': 'walk',
}

_METERS_TO_MILES = 0.000621371
_METERS_TO_FEET = 3.28084


def ingest_event(
    db: Any,
    event_id: int,
    user_id: int,
    notification: dict,
    access_token: str,
) -> None:
    """Dispatch a Polar webhook notification to the right per-event
    ingester. Raises on per-record failures so the caller can record the
    error against the `webhook_events` row.

    `access_token` is read from the matching `provider_auth` row at
    dispatch time (in the webhook handler) so we don't issue a second
    SELECT here. Polar tokens are long-lived; refresh-on-401 is a
    future-PR concern (the refresh skeleton in provider_auth.py isn't
    exercised by Polar today).
    """
    event = (notification.get('event') or '').upper()
    polar_user_id = str(notification.get('user_id') or '')
    if not polar_user_id:
        raise ValueError(f'Polar notification missing user_id: {notification!r}')

    if event == 'EXERCISE':
        _ingest_exercise_transaction(db, user_id, polar_user_id, access_token)
    elif event in ('SLEEP', 'SLEEP_WISE_ALARM_OUTPUT'):
        _ingest_sleep(db, user_id, polar_user_id, access_token, notification)
    elif event == 'NIGHTLY_RECHARGE':
        _ingest_nightly_recharge(db, user_id, polar_user_id, access_token, notification)
    elif event == 'CARDIO_LOAD':
        _ingest_cardio_load(db, user_id, polar_user_id, access_token, notification)
    elif event == 'CONTINUOUS_HEART_RATE':
        _ingest_continuous_hr(db, user_id, polar_user_id, access_token, notification)
    else:
        # Unknown event type — no-op. The raw notification is preserved
        # in webhook_events.payload for later inspection / re-derivation.
        current_app.logger.info(
            'Polar event %r not mapped (event_id=%s); recorded only',
            event, event_id,
        )


# ── EXERCISE: transaction-based ───────────────────────────────────────

def _ingest_exercise_transaction(
    db: Any, user_id: int, polar_user_id: str, access_token: str,
) -> None:
    """POST → GET transaction → GET each exercise → upsert → PUT commit.

    A Polar transaction is per-user and per-resource (`/exercise-transactions`).
    Once we PUT to commit, Polar drops these exercises from the next
    transaction. If commit fails (or anything fails before commit), the
    transaction is automatically discarded by Polar after a timeout and the
    same exercises return in the next transaction — so partial-ingest is
    re-deliverable without state on our side.
    """
    headers = {
        'Authorization': f'Bearer {access_token}',
        'Accept': 'application/json',
    }
    tx_url = f'{_POLAR_API_URL}/v3/users/{polar_user_id}/exercise-transactions'

    create = requests.post(tx_url, headers=headers, timeout=15)
    if create.status_code == 204:
        return  # No new exercises since last commit.
    create.raise_for_status()
    tx = create.json()
    resource_uri = tx.get('resource-uri') or tx.get('resource_uri')
    if not resource_uri:
        raise RuntimeError(f'Polar transaction response missing resource-uri: {tx!r}')

    listing = requests.get(resource_uri, headers=headers, timeout=15)
    listing.raise_for_status()
    body = listing.json()
    exercise_urls = body.get('exercises') or []

    for ex_url in exercise_urls:
        ex_resp = requests.get(ex_url, headers=headers, timeout=15)
        ex_resp.raise_for_status()
        ex = ex_resp.json()
        _upsert_exercise(db, user_id, ex)

    commit = requests.put(resource_uri, headers=headers, timeout=15)
    commit.raise_for_status()


def _upsert_exercise(db: Any, user_id: int, ex: dict) -> None:
    """Polar exercise → `cardio_log`. Dedup key is `polar_exercise_id`
    (the Polar-side id, stored as text). Backed by the
    `cardio_log_polar_exercise_uidx` partial UNIQUE index so ON CONFLICT
    is race-safe."""
    polar_id = ex.get('id') or ex.get('exercise-id') or ex.get('transactionId')
    if not polar_id:
        return  # Without a dedup key we can't safely insert.

    activity = _SPORT_MAP.get((ex.get('sport') or '').upper(), 'other')
    date = _polar_date(ex.get('start-time') or ex.get('upload-time'))
    duration_min = _iso_duration_to_min(ex.get('duration'))
    distance_m = _as_float(ex.get('distance'))
    distance_mi = distance_m * _METERS_TO_MILES if distance_m is not None else None
    heart_rate = ex.get('heart-rate') if isinstance(ex.get('heart-rate'), dict) else {}
    avg_hr = _as_int(heart_rate.get('average'))
    max_hr = _as_int(heart_rate.get('maximum'))
    calories = _as_int(ex.get('calories'))

    cols = {
        'date': date or _today_iso(),
        'activity': activity,
        'duration_min': duration_min,
        'distance_mi': distance_mi,
        'avg_hr': avg_hr,
        'max_hr': max_hr,
        'calories': calories,
    }
    set_clause = ', '.join(f'{c} = EXCLUDED.{c}' for c in cols)
    col_names = ['user_id', 'polar_exercise_id'] + list(cols)
    placeholders = ', '.join(['?'] * len(col_names))
    db.execute(
        f'INSERT INTO cardio_log ({", ".join(col_names)}) '
        f'VALUES ({placeholders}) '
        f'ON CONFLICT (user_id, polar_exercise_id) WHERE polar_exercise_id IS NOT NULL '
        f'DO UPDATE SET {set_clause}',
        [user_id, str(polar_id)] + [cols[c] for c in cols],
    )


# ── SLEEP: direct pull, no commit ─────────────────────────────────────

def _ingest_sleep(
    db: Any, user_id: int, polar_user_id: str, access_token: str,
    notification: dict,
) -> None:
    url = notification.get('url') or f'{_POLAR_API_URL}/v3/users/sleep'
    body = _get_json(url, access_token)
    nights = body.get('nights') or body.get('sleep') or ([body] if 'date' in body else [])
    for night in nights:
        if not isinstance(night, dict):
            continue
        date = night.get('date')
        if not date:
            continue
        db.execute(
            'INSERT INTO polar_sleep '
            '(user_id, date, sleep_start_time, sleep_end_time, total_sleep_min, '
            ' continuity, light_sleep_min, deep_sleep_min, rem_sleep_min, '
            ' unknown_sleep_min, stages_json, raw_payload) '
            'VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?) '
            'ON CONFLICT (user_id, date) DO UPDATE SET '
            '    sleep_start_time = EXCLUDED.sleep_start_time, '
            '    sleep_end_time = EXCLUDED.sleep_end_time, '
            '    total_sleep_min = EXCLUDED.total_sleep_min, '
            '    continuity = EXCLUDED.continuity, '
            '    light_sleep_min = EXCLUDED.light_sleep_min, '
            '    deep_sleep_min = EXCLUDED.deep_sleep_min, '
            '    rem_sleep_min = EXCLUDED.rem_sleep_min, '
            '    unknown_sleep_min = EXCLUDED.unknown_sleep_min, '
            '    stages_json = EXCLUDED.stages_json, '
            '    raw_payload = EXCLUDED.raw_payload, '
            '    fetched_at = NOW()',
            (
                user_id, date,
                night.get('sleep_start_time'),
                night.get('sleep_end_time'),
                _as_int(night.get('total_sleep_min') or night.get('total-sleep-min')),
                _as_float(night.get('continuity')),
                _as_int(night.get('light_sleep_min')),
                _as_int(night.get('deep_sleep_min')),
                _as_int(night.get('rem_sleep_min')),
                _as_int(night.get('unknown_sleep_min')),
                json.dumps(night.get('sleep_stages') or night.get('stages') or {}),
                json.dumps(night),
            ),
        )


# ── NIGHTLY_RECHARGE: direct pull ─────────────────────────────────────

def _ingest_nightly_recharge(
    db: Any, user_id: int, polar_user_id: str, access_token: str,
    notification: dict,
) -> None:
    url = notification.get('url') or (
        f'{_POLAR_API_URL}/v3/users/{polar_user_id}/nightly-recharge'
    )
    body = _get_json(url, access_token)
    items = body.get('recharges') or ([body] if 'date' in body else [])
    for item in items:
        if not isinstance(item, dict):
            continue
        date = item.get('date')
        if not date:
            continue
        db.execute(
            'INSERT INTO polar_nightly_recharge '
            '(user_id, date, ans_charge, ans_charge_status, hrv_rmssd_ms, '
            ' breathing_rate, recovery_indicator, raw_payload) '
            'VALUES (?, ?, ?, ?, ?, ?, ?, ?) '
            'ON CONFLICT (user_id, date) DO UPDATE SET '
            '    ans_charge = EXCLUDED.ans_charge, '
            '    ans_charge_status = EXCLUDED.ans_charge_status, '
            '    hrv_rmssd_ms = EXCLUDED.hrv_rmssd_ms, '
            '    breathing_rate = EXCLUDED.breathing_rate, '
            '    recovery_indicator = EXCLUDED.recovery_indicator, '
            '    raw_payload = EXCLUDED.raw_payload, '
            '    fetched_at = NOW()',
            (
                user_id, date,
                _as_int(item.get('ans_charge')),
                item.get('ans_charge_status'),
                _as_float(item.get('hrv_rmssd_ms') or item.get('hrv-rmssd-ms')),
                _as_float(item.get('breathing_rate') or item.get('breathing_rate_avg')),
                item.get('recovery_indicator'),
                json.dumps(item),
            ),
        )


# ── CARDIO_LOAD: direct pull ──────────────────────────────────────────

def _ingest_cardio_load(
    db: Any, user_id: int, polar_user_id: str, access_token: str,
    notification: dict,
) -> None:
    url = notification.get('url') or (
        f'{_POLAR_API_URL}/v3/users/{polar_user_id}/cardio-load'
    )
    body = _get_json(url, access_token)
    items = body.get('loads') or ([body] if 'date' in body else [])
    for item in items:
        if not isinstance(item, dict):
            continue
        date = item.get('date')
        if not date:
            continue
        db.execute(
            'INSERT INTO polar_cardio_load '
            '(user_id, date, daily_load, acute_load, chronic_load, '
            ' cardio_load_status, strain, raw_payload) '
            'VALUES (?, ?, ?, ?, ?, ?, ?, ?) '
            'ON CONFLICT (user_id, date) DO UPDATE SET '
            '    daily_load = EXCLUDED.daily_load, '
            '    acute_load = EXCLUDED.acute_load, '
            '    chronic_load = EXCLUDED.chronic_load, '
            '    cardio_load_status = EXCLUDED.cardio_load_status, '
            '    strain = EXCLUDED.strain, '
            '    raw_payload = EXCLUDED.raw_payload, '
            '    fetched_at = NOW()',
            (
                user_id, date,
                _as_float(item.get('daily_load')),
                _as_float(item.get('acute_load')),
                _as_float(item.get('chronic_load')),
                item.get('cardio_load_status'),
                _as_float(item.get('strain')),
                json.dumps(item),
            ),
        )


# ── CONTINUOUS_HEART_RATE: direct pull ────────────────────────────────

def _ingest_continuous_hr(
    db: Any, user_id: int, polar_user_id: str, access_token: str,
    notification: dict,
) -> None:
    url = notification.get('url') or (
        f'{_POLAR_API_URL}/v3/users/{polar_user_id}/continuous-heart-rate'
    )
    body = _get_json(url, access_token)
    # Polar returns either a flat samples list or a per-date wrapper.
    samples = body.get('samples') or body.get('heart-rate-samples') or []
    if isinstance(body.get('days'), list):
        for day in body['days']:
            if isinstance(day, dict):
                samples.extend(day.get('samples') or [])
    for s in samples:
        if not isinstance(s, dict):
            continue
        ts = _as_int(s.get('timestamp_ms') or s.get('timestamp-ms') or s.get('timestamp'))
        if ts is None:
            continue
        db.execute(
            'INSERT INTO polar_continuous_hr_samples '
            '(user_id, timestamp_ms, heart_rate) '
            'VALUES (?, ?, ?) '
            'ON CONFLICT (user_id, timestamp_ms) DO UPDATE SET '
            '    heart_rate = EXCLUDED.heart_rate',
            (user_id, ts, _as_int(s.get('heart_rate') or s.get('heart-rate'))),
        )


# ── HTTP helper ───────────────────────────────────────────────────────

def _get_json(url: str, access_token: str) -> dict:
    """GET an AccessLink resource with a Bearer access_token and return
    the parsed JSON body. Raises on non-2xx."""
    resp = requests.get(
        url,
        headers={
            'Authorization': f'Bearer {access_token}',
            'Accept': 'application/json',
        },
        timeout=15,
    )
    resp.raise_for_status()
    return resp.json() if resp.content else {}


# ── Coercion helpers ──────────────────────────────────────────────────

def _as_int(value: Any) -> int | None:
    if value is None or value == '':
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def _as_float(value: Any) -> float | None:
    if value is None or value == '':
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _polar_date(value: Any) -> str | None:
    """Polar start-time / upload-time are ISO-8601 strings. Return the
    date portion (YYYY-MM-DD) for `cardio_log.date`. Per-activity
    timezone disambiguation is a v2 concern."""
    if not value:
        return None
    s = str(value)
    return s[:10] if len(s) >= 10 else None


def _iso_duration_to_min(value: Any) -> float | None:
    """Convert Polar's ISO-8601 duration (e.g. `PT1H23M45S`) to minutes.
    Polar exercises always use ISO durations; non-conformant inputs
    return None rather than raising."""
    if not value or not isinstance(value, str) or not value.startswith('PT'):
        return None
    rest = value[2:]
    h = m = s = 0.0
    num = ''
    for ch in rest:
        if ch.isdigit() or ch == '.':
            num += ch
        elif ch == 'H' and num:
            h = float(num)
            num = ''
        elif ch == 'M' and num:
            m = float(num)
            num = ''
        elif ch == 'S' and num:
            s = float(num)
            num = ''
    return h * 60 + m + s / 60


def _today_iso() -> str:
    return datetime.now(timezone.utc).date().isoformat()
