"""COROS payload ingestion — webhook events to per-provider tables and
`cardio_log` activity rows.

Called from `routes/coros.py:webhook` after the signature has been
verified and the raw event is recorded in `webhook_events`. Branches
on payload shape (which top-level list is populated):

  - `sportDataList`  → activities → `cardio_log` (UPSERT on
                                    `(user_id, coros_label_id)`)
  - `dailyDataList`  → daily summary → `coros_daily_summary` (UPSERT on
                                       `(user_id, happen_day)`)
  - `hrvDataList`    → HRV samples → `coros_hrv_samples` (UPSERT on
                                     `(user_id, timestamp_s)`)

Per Integration v4 §5.3 + §6. COROS does not have a per-activity table;
activities flow into `cardio_log` directly with `coros_label_id` as
the dedup key per §6.

First-pass mapping. COROS's full payload surface is wider than what we
read here; missing fields land in `webhook_events.payload` (raw JSON)
and can be re-derived without a re-fetch when the mapping expands.
"""
from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import Any

# COROS sport-mode integers per their Open API. Map to the v1
# `cardio_log.activity` text vocabulary used by the existing UI.
# Unmapped modes fall through to 'other' so ingestion never drops
# rows on an unknown enum.
_SPORT_MODE = {
    1: 'run',
    5: 'cycle',
    8: 'swim',
    9: 'triathlon',
    10: 'strength',
    13: 'trail_run',
    15: 'hike',
    17: 'ski',
    21: 'ski_touring',
    22: 'rowing',
}

# Unit conversions COROS → cardio_log columns.
_METERS_TO_MILES = 0.000621371
_METERS_TO_FEET = 3.28084


def ingest_event(db: Any, event_id: int, user_id: int | None, payload: dict) -> None:
    """Dispatch a COROS webhook payload to the right per-shape ingester.

    Raises on per-record failures so the caller (the webhook handler)
    can record the error against the `webhook_events` row. Unmapped
    user_id (no `provider_auth` row matching the openId) raises
    immediately — the webhook row stays for later re-dispatch.
    """
    if user_id is None:
        raise RuntimeError(
            'COROS webhook openId not mapped to a local user; event recorded '
            'with user_id=NULL for later resolution'
        )

    if not isinstance(payload, dict):
        return

    activities = payload.get('sportDataList')
    if isinstance(activities, list):
        for item in activities:
            if isinstance(item, dict):
                _ingest_activity(db, user_id, item)

    dailies = payload.get('dailyDataList')
    if isinstance(dailies, list):
        for item in dailies:
            if isinstance(item, dict):
                _ingest_daily_summary(db, user_id, item)

    hrv = payload.get('hrvDataList')
    if isinstance(hrv, list):
        for item in hrv:
            if isinstance(item, dict):
                _ingest_hrv_sample(db, user_id, item)


# ── Per-shape ingesters ───────────────────────────────────────────────

def _ingest_activity(db: Any, user_id: int, item: dict) -> None:
    """COROS activity (`sportDataList[]`) → `cardio_log`. Dedup via
    `coros_label_id`; subsequent re-deliveries of the same activity
    (COROS retries; user re-syncs) update the existing row in place
    rather than appending. UPSERT against `cardio_log_coros_label_uidx`
    (PR3 partial UNIQUE on `(user_id, coros_label_id) WHERE coros_label_id
    IS NOT NULL`) so concurrent webhook deliveries are race-safe."""
    label_id = item.get('labelId')
    if not label_id:
        return  # Without a dedup key we can't safely insert.

    activity = _SPORT_MODE.get(item.get('mode'), 'other')
    distance_m = _as_float(item.get('distance'))
    distance_mi = distance_m * _METERS_TO_MILES if distance_m is not None else None
    duration_s = _as_float(item.get('totalTime'))
    duration_min = duration_s / 60 if duration_s is not None else None
    ascent_m = _as_float(item.get('ascent'))
    elev_gain_ft = ascent_m * _METERS_TO_FEET if ascent_m is not None else None
    descent_m = _as_float(item.get('descent'))
    elev_loss_ft = descent_m * _METERS_TO_FEET if descent_m is not None else None
    date = _epoch_ms_to_date(item.get('startTime')) or _today_iso()

    cols = {
        'date': date,
        'activity': activity,
        'duration_min': duration_min,
        'distance_mi': distance_mi,
        'avg_hr': _as_int(item.get('avgHr')),
        'max_hr': _as_int(item.get('maxHr')),
        'calories': _as_int(item.get('calorie')),
        'elev_gain_ft': elev_gain_ft,
        'elev_loss_ft': elev_loss_ft,
        'avg_cadence': _as_int(item.get('avgCadence')),
        'max_cadence': _as_int(item.get('maxCadence')),
    }
    set_clause = ', '.join(f'{c} = EXCLUDED.{c}' for c in cols)
    col_names = ['user_id', 'coros_label_id'] + list(cols)
    placeholders = ', '.join(['?'] * len(col_names))
    db.execute(
        f'INSERT INTO cardio_log ({", ".join(col_names)}) '
        f'VALUES ({placeholders}) '
        f'ON CONFLICT (user_id, coros_label_id) WHERE coros_label_id IS NOT NULL '
        f'DO UPDATE SET {set_clause}',
        [user_id, str(label_id)] + [cols[c] for c in cols],
    )


def _ingest_daily_summary(db: Any, user_id: int, item: dict) -> None:
    """COROS daily summary → `coros_daily_summary`. UPSERT on
    `(user_id, happen_day)`; COROS may re-emit the same day after
    later device sync, in which case the new payload supersedes."""
    happen_day = _normalise_happen_day(item.get('happenDay'))
    if not happen_day:
        return

    db.execute(
        'INSERT INTO coros_daily_summary '
        '(user_id, happen_day, rhr, calories, steps, ppg_hrv, '
        ' sleep_avg_hr, sleep_start_ms, sleep_end_ms, raw_payload) '
        'VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?) '
        'ON CONFLICT (user_id, happen_day) DO UPDATE SET '
        '    rhr = EXCLUDED.rhr, '
        '    calories = EXCLUDED.calories, '
        '    steps = EXCLUDED.steps, '
        '    ppg_hrv = EXCLUDED.ppg_hrv, '
        '    sleep_avg_hr = EXCLUDED.sleep_avg_hr, '
        '    sleep_start_ms = EXCLUDED.sleep_start_ms, '
        '    sleep_end_ms = EXCLUDED.sleep_end_ms, '
        '    raw_payload = EXCLUDED.raw_payload, '
        '    fetched_at = NOW()',
        (
            user_id, happen_day,
            _as_int(item.get('rhr')),
            _as_int(item.get('calories')),
            _as_int(item.get('steps')),
            _as_int(item.get('ppgHrv')),
            _as_int(item.get('sleepAvgHr')),
            _as_int(item.get('sleepStartTime')),
            _as_int(item.get('sleepEndTime')),
            json.dumps(item),
        ),
    )


def _ingest_hrv_sample(db: Any, user_id: int, item: dict) -> None:
    """COROS HRV sample → `coros_hrv_samples`. Idempotent on
    `(user_id, timestamp_s)`; per-second granularity per COROS docs."""
    ts = _as_int(item.get('timestamp') or item.get('timestampS'))
    if ts is None:
        return
    db.execute(
        'INSERT INTO coros_hrv_samples (user_id, timestamp_s, hrv, hr) '
        'VALUES (?, ?, ?, ?) '
        'ON CONFLICT (user_id, timestamp_s) DO UPDATE SET '
        '    hrv = EXCLUDED.hrv, hr = EXCLUDED.hr',
        (user_id, ts, _as_int(item.get('hrv')), _as_int(item.get('hr'))),
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


def _epoch_ms_to_date(value: Any) -> str | None:
    """COROS startTime is epoch milliseconds. Return ISO-8601 date in
    UTC; per-activity timezone disambiguation is a v2 concern (athletes
    travel; activity start may not be in their home tz)."""
    ms = _as_int(value)
    if ms is None:
        return None
    try:
        return datetime.fromtimestamp(ms / 1000, tz=timezone.utc).date().isoformat()
    except (OverflowError, OSError, ValueError):
        return None


def _normalise_happen_day(value: Any) -> str | None:
    """COROS `happenDay` is documented as an ISO date string but some
    payloads send it as an integer (YYYYMMDD) — coerce to ISO so the
    UNIQUE constraint behaves predictably."""
    if value is None:
        return None
    s = str(value)
    if len(s) == 8 and s.isdigit():
        return f'{s[:4]}-{s[4:6]}-{s[6:8]}'
    return s


def _today_iso() -> str:
    return datetime.now(timezone.utc).date().isoformat()
