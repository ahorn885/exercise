"""Strava live ingest — webhook event → REST fetch → canonical `cardio_log`.

The inbound half of #681 (B) live wiring for Strava. A Strava webhook is a thin
pointer (`{object_type, object_id, owner_id, aspect_type}`) — not the activity
itself — so on an `activity` `create`/`update` we GET the full
`DetailedActivity` over REST (with a fresh token via
`provider_auth.get_fresh_access_token`) and write it through the shared
`routes.garmin._bulk_insert_cardio` writer (source='strava' → the
`strava_activity_id` dedup column + the `provider_raw_record` corroboration row).

Discipline is resolved via the #681 translation map
(`provider_cardio_resolve.resolve_cardio_discipline('strava', sport_type)`) — the
fine layer0 D-id where one exists (matrix-v2 §2.2 option C), bucket-3 raw
otherwise. Units convert to the `cardio_log` vocabulary at the edge (matrix §2.1:
distance m→mi, elevation m→ft, time s→min; HR/power/calories already canonical).

Idempotent on `(user_id, strava_activity_id)`: a re-delivered event (Strava
retry, or create-then-update) is a no-op once the row exists. The fetch is
synchronous in the webhook handler — simplest for a single-user app and safe
because the dedup makes a retried delivery harmless; if Strava's ~2s ack window
ever causes retry churn, the documented upgrade is record-and-defer to a cron
processor (the `idx_webhook_events_pending` index already anticipates it).
"""
from __future__ import annotations

import os
from datetime import datetime, timezone
from typing import Any

import requests

from provider_cardio_resolve import resolve_cardio_discipline
from routes import provider_auth as pa

_STRAVA_API_BASE = os.environ.get('STRAVA_API_BASE', 'https://www.strava.com/api/v3')
_STRAVA_TOKEN_URL = os.environ.get('STRAVA_TOKEN_URL', 'https://www.strava.com/oauth/token')

_M_TO_MI = 0.000621371
_M_TO_FT = 3.28084
# Indoor/virtual rides corroborate the Cycling-trainer machine (matrix §12.3 gap
# 1; inbound indoor-machine flag). Only meaningful for the cycling disciplines.
_CYCLING_DISCIPLINES = {'D-006', 'D-008', 'D-030', 'D-007', 'D-031'}


def _as_int(value: Any) -> int | None:
    if value is None or value == '':
        return None
    try:
        return int(round(float(value)))
    except (TypeError, ValueError):
        return None


def normalize_strava_activity(a: dict) -> dict:
    """Strava `DetailedActivity` JSON → the shared cardio dict
    `_bulk_insert_cardio` consumes. `discipline_id` via the #681 resolver; the
    raw `sport_type` + indoor flag ride in `_provider_raw` (record-don't-drop)."""
    sport = a.get('sport_type') or a.get('type')
    res = resolve_cardio_discipline('strava', sport)

    dist_m = a.get('distance')
    moving_s = a.get('moving_time')
    elapsed_s = a.get('elapsed_time')
    gain_m = a.get('total_elevation_gain')
    start = a.get('start_date_local') or a.get('start_date')
    activity_date = (start or '')[:10] or datetime.now(timezone.utc).date().isoformat()
    indoor = bool(a.get('trainer')) or sport in ('VirtualRide', 'VirtualRun')
    machine = ('Cycling trainer'
               if indoor and res.discipline_id in _CYCLING_DISCIPLINES else None)

    return {
        'date': activity_date,
        'activity': res.plan_sport_type or (sport or 'other').lower(),
        'activity_name': a.get('name'),
        'duration_min': (elapsed_s / 60) if elapsed_s else None,
        'moving_time_min': (moving_s / 60) if moving_s else None,
        'distance_mi': (dist_m * _M_TO_MI) if dist_m is not None else None,
        'avg_hr': _as_int(a.get('average_heartrate')),
        'max_hr': _as_int(a.get('max_heartrate')),
        'calories': _as_int(a.get('calories')),
        'elev_gain_ft': (gain_m * _M_TO_FT) if gain_m is not None else None,
        'avg_cadence': _as_int(a.get('average_cadence')),
        'avg_power': _as_int(a.get('average_watts')),
        'max_power': _as_int(a.get('max_watts')),
        'norm_power': _as_int(a.get('weighted_average_watts')),
        'discipline_id': res.discipline_id,
        '_provider_raw': {
            'provider': 'strava',
            'observed_at': start or None,
            'bucket': res.bucket,
            'canonical_ref': res.discipline_id,
            'payload': {
                'sport_type': sport,
                'indoor_machine': machine,
                'trainer': a.get('trainer'),
                'strava_activity_id': a.get('id'),
            },
        },
    }


def _access_token(db: Any, user_id: int) -> str | None:
    return pa.get_fresh_access_token(
        db, user_id, 'strava',
        token_url=_STRAVA_TOKEN_URL,
        client_id=os.environ.get('STRAVA_CLIENT_ID'),
        client_secret=os.environ.get('STRAVA_CLIENT_SECRET'),
    )


def fetch_and_ingest_activity(db: Any, user_id: int, activity_id: Any) -> bool:
    """Fetch a Strava activity over REST and write it to `cardio_log`.

    Returns True if a row was written, False if skipped (already imported / no
    token). Raises on a fetch failure so the webhook handler records the error
    against the `webhook_events` row (and Strava re-delivers). Rule #15 logs the
    decision + inputs."""
    gid = str(activity_id)
    # Dedup directly (the webhook has no logged-in session, so the session-based
    # _already_imported guard doesn't apply here).
    if db.execute(
        'SELECT id FROM cardio_log WHERE strava_activity_id = ? AND user_id = ?',
        (gid, user_id),
    ).fetchone() is not None:
        print(f'[strava-ingest] activity={gid} user={user_id} SKIP already-imported')  # noqa: T201
        return False

    token = _access_token(db, user_id)
    if not token:
        print(f'[strava-ingest] activity={gid} user={user_id} SKIP no-token')  # noqa: T201
        return False

    try:
        resp = requests.get(
            f'{_STRAVA_API_BASE}/activities/{gid}',
            headers={'Authorization': f'Bearer {token}'},
            timeout=10,
        )
        resp.raise_for_status()
        activity = resp.json()
    except requests.RequestException as exc:
        print(f'[strava-ingest] activity={gid} user={user_id} FETCH-FAIL '  # noqa: T201
              f'{type(exc).__name__}')
        raise

    from routes.garmin import _bulk_insert_cardio
    data = normalize_strava_activity(activity)
    _bulk_insert_cardio(db, data, user_id, gid, source='strava')
    print(  # noqa: T201 — Rule #15
        f'[strava-ingest] activity={gid} user={user_id} sport={activity.get("sport_type")!r} '
        f'-> cardio_log discipline={data.get("discipline_id")} '
        f'bucket={data["_provider_raw"]["bucket"]}'
    )
    return True
