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
            record per-date into `provider_raw_record`
            (provider='polar', data_type='sleep').
  - NIGHTLY_RECHARGE → GET /v3/users/{uid}/nightly-recharge → record
            per-date into `provider_raw_record` (data_type='hrv').
  - CARDIO_LOAD → GET /v3/users/{uid}/cardio-load → record per-date
            into `provider_raw_record` (data_type='cardio_load').
  - CONTINUOUS_HEART_RATE → GET the resource → upsert per-timestamp
            into the canonical `wellness_log`.

Per #681 §4 Slice 3 the per-provider Polar wellness tables were retired:
sleep / nightly-recharge / cardio-load land in `provider_raw_record`
(provider-tagged, record-don't-drop — Layer-3A reads them back filtered to
`provider='polar'`), and continuous HR flows into the canonical `wellness_log`.

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

from canonical_wellness import materialize_wellness_for_provider

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
        # Normalised snake_case keys so Layer-3A reads stable fields back out of
        # raw_payload; `_raw` carries the full provider body (record-don't-drop).
        _record_raw(db, user_id, 'sleep', date, {
            'total_sleep_min': _as_int(
                night.get('total_sleep_min') or night.get('total-sleep-min')),
            'continuity': _as_float(night.get('continuity')),
            'light_sleep_min': _as_int(night.get('light_sleep_min')),
            'deep_sleep_min': _as_int(night.get('deep_sleep_min')),
            'rem_sleep_min': _as_int(night.get('rem_sleep_min')),
            'unknown_sleep_min': _as_int(night.get('unknown_sleep_min')),
            'sleep_start_time': night.get('sleep_start_time'),
            'sleep_end_time': night.get('sleep_end_time'),
            'stages': night.get('sleep_stages') or night.get('stages') or {},
            '_raw': night,
        })


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
        # data_type='hrv' — Layer-3A's recent-HRV accessor reads `hrv_rmssd_ms`.
        _record_raw(db, user_id, 'hrv', date, {
            'hrv_rmssd_ms': _as_float(
                item.get('hrv_rmssd_ms') or item.get('hrv-rmssd-ms')),
            'ans_charge': _as_int(item.get('ans_charge')),
            'ans_charge_status': item.get('ans_charge_status'),
            'breathing_rate': _as_float(
                item.get('breathing_rate') or item.get('breathing_rate_avg')),
            'recovery_indicator': item.get('recovery_indicator'),
            '_raw': item,
        })


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
        # data_type='cardio_load' — Layer-3A's combined-load accessor reads the
        # latest of these as a Polar cross-reference (not the primary ACWR).
        _record_raw(db, user_id, 'cardio_load', date, {
            'daily_load': _as_float(item.get('daily_load')),
            'acute_load': _as_float(item.get('acute_load')),
            'chronic_load': _as_float(item.get('chronic_load')),
            'cardio_load_status': item.get('cardio_load_status'),
            'strain': _as_float(item.get('strain')),
            '_raw': item,
        })


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
        _record_hr_sample(
            db, user_id, ts, _as_int(s.get('heart_rate') or s.get('heart-rate')),
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


# ── Canonical writers (#681 §4 Slice 3) ───────────────────────────────

def _record_raw(
    db: Any, user_id: int, data_type: str, external_id: str, payload: dict,
) -> None:
    """Record a Polar daily-wellness signal into `provider_raw_record`
    (record-don't-drop, provider-tagged). Idempotent per
    (user_id, provider, data_type, external_id) so a re-delivered day refreshes
    in place. `external_id` is the ISO date; `observed_at` mirrors it (a daily
    aggregate has no finer timestamp). A raise propagates to the webhook handler
    so the `webhook_events` row stays for re-dispatch (the existing contract)."""
    db.execute(
        'INSERT INTO provider_raw_record '
        '(user_id, provider, data_type, external_id, observed_at, raw_payload) '
        'VALUES (?, ?, ?, ?, ?, ?::jsonb) '
        'ON CONFLICT (user_id, provider, data_type, external_id) DO UPDATE SET '
        '    observed_at = EXCLUDED.observed_at, '
        '    raw_payload = EXCLUDED.raw_payload, '
        '    fetched_at = NOW()',
        (user_id, 'polar', data_type, external_id, external_id, json.dumps(payload)),
    )
    # #196 Phase 2 Slice 2.2 — refresh the canonical daily-wellness row when this
    # write is a wellness source (sleep/hrv); cardio_load is gated out.
    materialize_wellness_for_provider(db, user_id, 'polar', data_type, external_id)


def _record_hr_sample(db: Any, user_id: int, ts_ms: int, heart_rate: int | None) -> None:
    """Polar continuous-HR sample → canonical `wellness_log` (per-timestamp HR,
    `source='polar'`). Idempotent on (user_id, timestamp_ms)."""
    date = datetime.fromtimestamp(ts_ms / 1000, tz=timezone.utc).date().isoformat()
    db.execute(
        'INSERT INTO wellness_log (user_id, date, timestamp_ms, heart_rate, source) '
        'VALUES (?, ?, ?, ?, ?) '
        'ON CONFLICT (user_id, timestamp_ms) DO UPDATE SET '
        '    heart_rate = EXCLUDED.heart_rate, source = EXCLUDED.source',
        (user_id, date, ts_ms, heart_rate, 'polar'),
    )


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
