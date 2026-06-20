"""Whoop live ingest — webhook event → REST fetch → canonical wellness (#681 (B)).

The inbound half of #681 (B) live wiring for Whoop. A Whoop webhook is a thin
pointer (`{user_id, id, type}`, type ∈ `recovery.updated` / `sleep.updated` /
`workout.updated` + their `.deleted`) — not the resource — so on an `.updated`
we GET the resource over REST (fresh token via
`provider_auth.get_fresh_access_token`) and fold its canonical fields into the
athlete's per-day record.

The load-bearing shape note: Whoop delivers the Layer-3A `daily_summary` fields
across SEPARATE events — `recovery` carries HRV + resting-HR, `sleep` carries the
sleep duration — so each ingest **merges its subset into the existing day's
`provider_raw_record` row** (read-modify-write) rather than overwriting, or a
sleep event would clobber the recovery event's HRV/RHR and vice versa. The target
shape is exactly what the manual-CSV path writes and Layer-3A reads
(`total_sleep_min` / `hrv_rmssd_ms` / `resting_hr`, keyed on the ISO date in
`external_id`) — so live + manual coalesce uniformly (`layer3a/integration.py`).

Field mapping per `specs/Provider_Inbound_Matrix_v2.md` §3 + the seed
`provider_value_map_seed.WELLNESS_VALUE_MAP`: `hrv_rmssd_milli` is already ms;
`total_sleep_min` = Σ(deep+rem+light)/60000 (the §3.2 asleep convention).

BEST-EFFORT / VERIFY-OWED (Rule #14): the v2 endpoint paths, the webhook
signature scheme, and the signed-timestamp units below are Whoop's documented
form but unverified against live payloads from the container — all are
env-overridable and the signature is the security gate; confirm against
developer.whoop.com at go-live. Workout events are recorded raw (no `cardio_log`
Whoop id column exists yet) — a later refinement can add one.
"""
from __future__ import annotations

import base64
import hashlib
import hmac
import json
import os
from datetime import datetime, timezone
from typing import Any

import requests

from routes import provider_auth as pa

_WHOOP_API_BASE = os.environ.get('WHOOP_API_BASE', 'https://api.prod.whoop.com/developer')
_WHOOP_TOKEN_URL = os.environ.get(
    'WHOOP_TOKEN_URL', 'https://api.prod.whoop.com/oauth/oauth2/token')
# v2 resource paths (override via env if Whoop's surface differs).
_RECOVERY_PATH = os.environ.get('WHOOP_RECOVERY_PATH', '/v2/cycle/{id}/recovery')
_SLEEP_PATH = os.environ.get('WHOOP_SLEEP_PATH', '/v2/activity/sleep/{id}')
_WORKOUT_PATH = os.environ.get('WHOOP_WORKOUT_PATH', '/v2/activity/workout/{id}')


# ── Webhook signature ─────────────────────────────────────────────────

def verify_signature(raw_body: bytes, signature: str | None,
                     timestamp: str | None, secret: str | None) -> bool:
    """Whoop webhook auth: `base64(HMAC-SHA256(secret, timestamp + raw_body))`
    must equal `X-WHOOP-Signature`. The signed timestamp (`X-WHOOP-Signature-
    Timestamp`) is part of the MAC input, which binds it against replay; we don't
    additionally reject on age here (the units are unverified — a strict window
    on a wrong unit guess would drop valid events; replay hardening is a
    follow-up). Documented scheme — verify at go-live (Rule #14)."""
    if not secret or not signature or not timestamp:
        return False
    body = raw_body if isinstance(raw_body, bytes) else (raw_body or '').encode()
    mac = hmac.new(secret.encode(), timestamp.encode() + body, hashlib.sha256).digest()
    expected = base64.b64encode(mac).decode()
    return hmac.compare_digest(expected, signature)


# ── Dispatch ──────────────────────────────────────────────────────────

def process_event(db: Any, event_type: str | None, resource_id: Any,
                  user_id: int) -> bool:
    """Route a verified Whoop `.updated` event to its ingester. Returns True if a
    record was written. `.deleted` and unknown types are no-ops (recorded in
    webhook_events upstream). Raises on a fetch failure so the webhook handler
    records the error for re-delivery."""
    etype = event_type or ''
    if etype.startswith('recovery.updated'):
        return _ingest_recovery(db, user_id, resource_id)
    if etype.startswith('sleep.updated'):
        return _ingest_sleep(db, user_id, resource_id)
    if etype.startswith('workout.updated'):
        return _ingest_workout(db, user_id, resource_id)
    return False


# ── Per-domain ingesters ──────────────────────────────────────────────

def _ingest_recovery(db: Any, user_id: int, cycle_id: Any) -> bool:
    """Whoop recovery → daily_summary {hrv_rmssd_ms, resting_hr} (+ bucket-2
    corroboration). HRV `hrv_rmssd_milli` is already ms (matrix §3.1)."""
    data = _fetch(db, user_id, _RECOVERY_PATH.format(id=cycle_id))
    if not data:
        return False
    score = data.get('score') or {}
    day = _date_of(data.get('created_at') or data.get('updated_at'))
    if not day:
        return False
    partial: dict[str, Any] = {}
    if score.get('hrv_rmssd_milli') is not None:
        partial['hrv_rmssd_ms'] = float(score['hrv_rmssd_milli'])
    if score.get('resting_heart_rate') is not None:
        partial['resting_hr'] = int(round(float(score['resting_heart_rate'])))
    # bucket-2 proprietary — recorded raw, never surfaced (matrix §3.1/§3.6)
    for k in ('recovery_score', 'spo2_percentage', 'skin_temp_celsius'):
        if score.get(k) is not None:
            partial[k] = score[k]
    _merge_daily(db, user_id, day, partial)
    print(f'[whoop-ingest] recovery cycle={cycle_id} user={user_id} day={day} '  # noqa: T201
          f'hrv={partial.get("hrv_rmssd_ms")} rhr={partial.get("resting_hr")}')
    return True


def _ingest_sleep(db: Any, user_id: int, sleep_id: Any) -> bool:
    """Whoop sleep → daily_summary {total_sleep_min}. Asleep total = Σ(deep+rem+
    light)/60000 (the §3.2 decision; in-bed is NOT used)."""
    data = _fetch(db, user_id, _SLEEP_PATH.format(id=sleep_id))
    if not data:
        return False
    score = data.get('score') or {}
    stage = score.get('stage_summary') or {}
    day = _date_of(data.get('end') or data.get('updated_at'))
    if not day:
        return False
    parts = [stage.get(k) for k in (
        'total_slow_wave_sleep_time_milli',
        'total_rem_sleep_time_milli',
        'total_light_sleep_time_milli',
    ) if stage.get(k) is not None]
    partial: dict[str, Any] = {}
    if parts:
        partial['total_sleep_min'] = sum(float(p) for p in parts) / 60000.0
    if score.get('respiratory_rate') is not None:
        partial['respiratory_rate'] = score['respiratory_rate']
    _merge_daily(db, user_id, day, partial)
    print(f'[whoop-ingest] sleep id={sleep_id} user={user_id} day={day} '  # noqa: T201
          f'total_sleep_min={partial.get("total_sleep_min")}')
    return True


def _ingest_workout(db: Any, user_id: int, workout_id: Any) -> bool:
    """Whoop workout → provider_raw_record (record-don't-drop). No `cardio_log`
    Whoop id column exists, so the cardio write is deferred; the raw is kept so it
    can light up later without a re-fetch."""
    data = _fetch(db, user_id, _WORKOUT_PATH.format(id=workout_id))
    if not data:
        return False
    _record_raw(db, user_id, 'workout', str(workout_id), data)
    print(f'[whoop-ingest] workout id={workout_id} user={user_id} recorded-raw')  # noqa: T201
    return True


# ── REST + writers ────────────────────────────────────────────────────

def _fetch(db: Any, user_id: int, path: str) -> dict | None:
    token = pa.get_fresh_access_token(
        db, user_id, 'whoop',
        token_url=_WHOOP_TOKEN_URL,
        client_id=os.environ.get('WHOOP_CLIENT_ID'),
        client_secret=os.environ.get('WHOOP_CLIENT_SECRET'),
    )
    if not token:
        print(f'[whoop-ingest] {path} user={user_id} SKIP no-token')  # noqa: T201
        return None
    resp = requests.get(
        _WHOOP_API_BASE + path,
        headers={'Authorization': f'Bearer {token}'},
        timeout=10,
    )
    resp.raise_for_status()
    return resp.json()


def _merge_daily(db: Any, user_id: int, day: str, partial: dict) -> None:
    """Read-modify-write the day's whoop `daily_summary` row, folding in `partial`
    (non-destructive — a sleep event keeps the recovery event's HRV/RHR and vice
    versa). Idempotent per (user, provider, data_type, external_id=day)."""
    if not partial:
        return
    row = db.execute(
        "SELECT raw_payload FROM provider_raw_record "
        "WHERE user_id = ? AND provider = 'whoop' AND data_type = 'daily_summary' "
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
        "VALUES (?, 'whoop', 'daily_summary', ?, ?, ?::jsonb) "
        'ON CONFLICT (user_id, provider, data_type, external_id) DO UPDATE SET '
        '    observed_at = EXCLUDED.observed_at, '
        '    raw_payload = EXCLUDED.raw_payload, '
        '    fetched_at = NOW()',
        (user_id, day, day, json.dumps(existing)),
    )


def _record_raw(db: Any, user_id: int, data_type: str, external_id: str,
                payload: dict) -> None:
    """Record a whoop resource verbatim into provider_raw_record (record-don't-
    drop). Idempotent per (user, provider, data_type, external_id)."""
    db.execute(
        'INSERT INTO provider_raw_record '
        '(user_id, provider, data_type, external_id, observed_at, raw_payload) '
        "VALUES (?, 'whoop', ?, ?, NULL, ?::jsonb) "
        'ON CONFLICT (user_id, provider, data_type, external_id) DO UPDATE SET '
        '    raw_payload = EXCLUDED.raw_payload, fetched_at = NOW()',
        (user_id, data_type, external_id, json.dumps(payload)),
    )


def _date_of(value: Any) -> str | None:
    """ISO timestamp/date string → 'YYYY-MM-DD' (the daily_summary key)."""
    if not value:
        return None
    return str(value)[:10] or None
