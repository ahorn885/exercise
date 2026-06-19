"""Parse TCX / GPX activity exports into the normalized cardio dict (#767 slice 2).

Companion to ``garmin_fit_parser.parse_fit``: :func:`parse_tcx` / :func:`parse_gpx`
emit the SAME ``{'log_type': 'cardio', 'data': {...}}`` shape, so
``routes.garmin._bulk_insert_cardio`` (+ dedup + provider-raw recording) ingests
them with zero change. TCX/GPX cover the non-Garmin per-session activity exports
(Polar / COROS / Strava) that the FIT path doesn't.

These formats carry **activities only** — no wellness/daily-metric data. Streams
are derived from trackpoints (GPX has no summary at all; TCX lap summaries are
used when present for timer-time / distance / calories), and every value is
converted to the cardio_log unit conventions (mi, mph, ft, min; one-leg cadence
doubled to full strides for foot sports) so the output matches ``parse_fit``
field-for-field. Running-dynamics fields (stride length, vertical oscillation,
GCT) aren't in TCX/GPX, so they come through as None — exactly as a FIT from a
device that doesn't record them.

Design: ``designs/ManualUpload_MultiService_Ingestion_Design_v1.md`` §5 (TCX/GPX).
"""

from __future__ import annotations

import math
import xml.etree.ElementTree as ET
from datetime import datetime

from garmin_fit_parser import _pace_from_speed

# Foot sports: report pace (min/mi) and double the one-leg cadence to full
# strides/min, matching garmin_fit_parser (FIT stores one-foot cadence). TCX/GPX
# vendors are inconsistent on cadence units; doubling keeps cross-format parity
# with the FIT path so the same run reads the same whichever export it came from.
_FOOT_SPORTS = {'running', 'trail_running', 'hiking', 'walking'}

# TCX ``<Activity Sport>`` is a 3-value enum (Running/Biking/Other); GPX
# ``<trk><type>`` is free text. Both resolve through this format-level map to the
# EXISTING layer0 discipline ids — no provider context is needed here (the chosen
# upload source tags the row's provider-id column separately, slice 1). An
# unmapped token → bucket 3 (record-don't-drop): discipline None, the raw token
# kept in provider_raw_record. Keys are lowercased tokens. (Kept local rather than
# in provider_value_map_seed.CARDIO_DISCIPLINE_MAP because the sport axis here is
# the file FORMAT's vocabulary, not a provider's — see handoff for the
# fold-into-seed alternative.)
_SPORT_DISCIPLINE: dict[str, tuple[str, str | None, str | None]] = {
    # token   -> (activity name, discipline_id, coarse plan_sport_type)
    'running':  ('Running',  'D-002', 'running'),
    'run':      ('Running',  'D-002', 'running'),
    'biking':   ('Cycling',  'D-006', 'cycling'),
    'cycling':  ('Cycling',  'D-006', 'cycling'),
    'ride':     ('Cycling',  'D-006', 'cycling'),
    'hiking':   ('Hiking',   'D-003', 'hiking'),
    'hike':     ('Hiking',   'D-003', 'hiking'),
    'walking':  ('Walking',  None,    'walking'),
    'walk':     ('Walking',  None,    'walking'),
    'swimming': ('Swimming', 'D-004', 'swimming'),
    'swim':     ('Swimming', 'D-004', 'swimming'),
}

# GPS-elevation noise floor: ignore per-point altitude deltas below this (metres)
# when accumulating gain/loss, so jittery consumer-GPS tracks don't inflate climb.
_ELEV_NOISE_M = 1.0


# ── XML helpers (namespace-agnostic: real-world TCX/GPX vary the namespace URI /
#    version, so we match on the local tag name and ignore the namespace) ───────

def _ln(tag: str) -> str:
    """Local name of an ElementTree tag (drops any ``{namespace}`` prefix)."""
    return tag.rsplit('}', 1)[-1]


def _first(el, name):
    """First descendant (or self) whose local tag name is ``name``, else None."""
    for e in el.iter():
        if _ln(e.tag) == name:
            return e
    return None


def _all(el, name):
    """All descendants whose local tag name is ``name``."""
    return [e for e in el.iter() if _ln(e.tag) == name]


def _text(el, name):
    """Text of the first descendant named ``name`` (stripped), or None."""
    e = _first(el, name)
    return e.text.strip() if (e is not None and e.text) else None


def _f(val):
    """Parse a float, returning None for missing / non-numeric / non-positive."""
    try:
        f = float(val)
    except (TypeError, ValueError):
        return None
    return f if (not math.isnan(f) and f > 0) else None


def _i(val):
    """Parse an int (via float, to tolerate '85.0'), None for missing / ≤0."""
    f = _f(val)
    return int(f) if f is not None else None


def _coord(val):
    """Parse a lat/lon coordinate (negatives and zero are valid), or None."""
    try:
        f = float(val)
    except (TypeError, ValueError):
        return None
    return f if not math.isnan(f) else None


def _parse_dt(s: str | None):
    """Parse an ISO-8601 timestamp (with 'Z' or offset) to a datetime, or None."""
    if not s:
        return None
    s = s.strip()
    if s.endswith('Z'):
        s = s[:-1] + '+00:00'
    try:
        return datetime.fromisoformat(s)
    except ValueError:
        try:
            return datetime.strptime(s[:19], '%Y-%m-%dT%H:%M:%S')
        except ValueError:
            return None


def _haversine_m(lat1, lon1, lat2, lon2) -> float:
    """Great-circle distance in metres between two lat/lon points."""
    r = 6371000.0
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dlam = math.radians(lon2 - lon1)
    a = math.sin(dphi / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dlam / 2) ** 2
    return 2 * r * math.asin(math.sqrt(a))


# ── public entry points ──────────────────────────────────────────────────────

def parse_tcx(raw: bytes) -> dict:
    """Parse TCX bytes → the normalized cardio dict (see module docstring)."""
    root = _parse_xml(raw)
    activity = _first(root, 'Activity')
    if activity is None:
        raise ValueError('No Activity found in TCX file.')

    sport_token = (activity.get('Sport') or '').strip()
    start_dt = _parse_dt(_text(activity, 'Id'))

    # Lap summaries: timer time, distance, calories (sum across laps).
    timer_s = dist_m = calories = 0.0
    for lap in _all(activity, 'Lap'):
        timer_s += _f(_text(lap, 'TotalTimeSeconds')) or 0.0
        dist_m += _f(_text(lap, 'DistanceMeters')) or 0.0
        calories += _f(_text(lap, 'Calories')) or 0.0

    points = []
    for tp in _all(activity, 'Trackpoint'):
        hb = _first(tp, 'HeartRateBpm')
        points.append({
            'time': _parse_dt(_text(tp, 'Time')),
            'ele': _f(_text(tp, 'AltitudeMeters')),
            'cum_dist': _f(_text(tp, 'DistanceMeters')),
            'hr': _i(_text(hb, 'Value')) if hb is not None else None,
            'cad': _i(_text(tp, 'Cadence')) or _i(_text(tp, 'RunCadence')),
            'watts': _i(_text(tp, 'Watts')),
        })

    # Prefer the cumulative trackpoint distance (most precise), fall back to the
    # summed lap distance.
    cum = [p['cum_dist'] for p in points if p['cum_dist']]
    total_dist_m = max(cum) if cum else (dist_m or None)

    return _assemble(points, sport_token, 'tcx', total_dist_m,
                     timer_s or None, calories or None, start_dt)


def parse_gpx(raw: bytes) -> dict:
    """Parse GPX bytes → the normalized cardio dict (see module docstring).

    GPX is the thinnest format — no lap summary, often no sport — so distance is
    integrated from the track geometry (haversine) and duration from the
    trackpoint time span. Sport comes from ``<trk><type>`` when present, else the
    activity is recorded with no discipline (bucket 3)."""
    root = _parse_xml(raw)
    trk = _first(root, 'trk')
    if trk is None:
        raise ValueError('No track (<trk>) found in GPX file.')

    sport_token = (_text(trk, 'type') or '').strip()

    points = []
    total_dist_m = 0.0
    prev = None
    for tp in _all(trk, 'trkpt'):
        lat, lon = _coord(tp.get('lat')), _coord(tp.get('lon'))
        if lat is not None and lon is not None and prev is not None:
            total_dist_m += _haversine_m(prev[0], prev[1], lat, lon)
        if lat is not None and lon is not None:
            prev = (lat, lon)
        points.append({
            'time': _parse_dt(_text(tp, 'time')),
            'ele': _f(_text(tp, 'ele')),
            'cum_dist': None,
            'hr': _i(_text(tp, 'hr')),
            'cad': _i(_text(tp, 'cad')),
            'watts': _i(_text(tp, 'power')) or _i(_text(tp, 'PowerInWatts')),
        })

    start_dt = next((p['time'] for p in points if p['time']), None)
    return _assemble(points, sport_token, 'gpx', total_dist_m or None,
                     None, None, start_dt)


# ── shared assembly ──────────────────────────────────────────────────────────

def _parse_xml(raw: bytes):
    try:
        return ET.fromstring(raw)
    except ET.ParseError as e:
        raise ValueError(f'Malformed XML: {e}') from e


def _assemble(points, sport_token, fmt, total_dist_m, timer_s, calories,
              start_dt) -> dict:
    """Build the normalized cardio dict from extracted trackpoints + summaries."""
    if not points:
        raise ValueError(f'No trackpoints in {fmt.upper()} file.')

    times = [p['time'] for p in points if p['time']]
    if start_dt is None and times:
        start_dt = min(times)
    elapsed_s = ((max(times) - min(times)).total_seconds()
                 if len(times) >= 2 else None)

    activity_date = start_dt.date().isoformat() if start_dt else ''

    token = sport_token.lower()
    activity_name, discipline_id, plan_sport = _SPORT_DISCIPLINE.get(
        token, ('Activity', None, None))
    bucket = 1 if (discipline_id or plan_sport) else 3

    # Speed: distance over the best available time base (timer beats elapsed).
    speed_ms = None
    if total_dist_m and (timer_s or elapsed_s):
        speed_ms = total_dist_m / (timer_s or elapsed_s)

    is_foot = (plan_sport in _FOOT_SPORTS)
    cadence_mult = 2 if is_foot else 1
    # Pace (min/mi) is only meaningful for foot sports — suppress for cycling.
    avg_pace = (_pace_from_speed(speed_ms) or None) if (speed_ms and is_foot) else None

    hrs = [p['hr'] for p in points if p['hr']]
    cads = [p['cad'] for p in points if p['cad']]
    watts = [p['watts'] for p in points if p['watts']]

    gain_m, loss_m = _elev_gain_loss([p['ele'] for p in points])

    data = {
        'date': activity_date,
        'activity': activity_name,
        'activity_name': '',
        'duration_min': round(elapsed_s / 60, 2) if elapsed_s else None,
        'moving_time_min': round(timer_s / 60, 2) if timer_s else None,
        'distance_mi': round(total_dist_m * 0.000621371, 3) if total_dist_m else None,
        'avg_pace': avg_pace,
        'avg_speed': round(speed_ms * 2.23694, 2) if speed_ms else None,
        'avg_hr': round(sum(hrs) / len(hrs)) if hrs else None,
        'max_hr': max(hrs) if hrs else None,
        'calories': int(calories) if calories else None,
        'elev_gain_ft': round(gain_m * 3.28084, 1) if gain_m else None,
        'elev_loss_ft': round(loss_m * 3.28084, 1) if loss_m else None,
        'avg_cadence': round(sum(cads) / len(cads)) * cadence_mult if cads else None,
        'max_cadence': max(cads) * cadence_mult if cads else None,
        'avg_power': round(sum(watts) / len(watts)) if watts else None,
        'max_power': max(watts) if watts else None,
        'norm_power': None,
        'aerobic_te': None,
        'anaerobic_te': None,
        'swolf': None,
        'active_lengths': None,
        'notes': '',
        # Running dynamics — not present in TCX/GPX.
        'stride_length_m': None,
        'vert_oscillation_cm': None,
        'vert_ratio_pct': None,
        'gct_ms': None,
        'gct_balance': None,
        'discipline_id': discipline_id,
        '_provider_raw': {
            # 'provider' is overridden by the chosen upload source at write time
            # (routes.garmin._record_provider_raw_cardio); 'manual' is the honest
            # fallback for the unattributed single-file case.
            'provider': 'manual',
            'observed_at': activity_date or None,
            'bucket': bucket,
            'canonical_ref': discipline_id,
            'payload': {
                'sport': sport_token,
                'format': fmt,
                'activity': activity_name,
                'discipline_id': discipline_id,
                'plan_sport_type': plan_sport,
                'indoor_machine': None,
            },
        },
    }
    print(  # Rule #15 — the decision this parse made, legible in /admin/logs
        f"[cardio-ingest] {fmt} sport={sport_token!r} "
        f"-> discipline_id={discipline_id} coarse={plan_sport} bucket={bucket}"
    )
    return {'log_type': 'cardio', 'data': data}


def _elev_gain_loss(eles) -> tuple[float, float]:
    """Sum positive / negative consecutive altitude deltas above the noise floor."""
    gain = loss = 0.0
    prev = None
    for e in eles:
        if e is None:
            continue
        if prev is not None:
            d = e - prev
            if abs(d) >= _ELEV_NOISE_M:
                if d > 0:
                    gain += d
                else:
                    loss += -d
        prev = e
    return gain, loss
