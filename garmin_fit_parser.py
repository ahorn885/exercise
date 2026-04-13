"""Parse a Garmin .fit file and return structured data ready for cardio_log or training_log."""
import os
import uuid
import tempfile
from datetime import datetime, timezone

# Garmin FIT sport enum → exercise site activity name
SPORT_MAP = {
    'running': 'Running',
    'trail_running': 'Trail Running',
    'treadmill': 'Treadmill',
    'cycling': 'Road Cycling',
    'mountain_biking': 'Mountain Biking',
    'gravel_cycling': 'Gravel Cycling',
    'indoor_cycling': 'Indoor Bike Trainer',
    'hiking': 'Hiking',
    'walking': 'Hiking',
    'swimming': 'Swimming Pool',
    'open_water_swimming': 'Swimming Open',
    'yoga': 'Yoga',
    'rowing': 'Rowing Ergometer',
    'kayaking': 'Kayaking',
    'strength_training': '__strength__',
    'weight_training': '__strength__',
    'gym': '__strength__',
}

# Sports where cadence is stored as one-leg (steps/min of one foot) → multiply by 2
_ONE_LEG_CADENCE_SPORTS = {
    'running', 'trail_running', 'treadmill', 'hiking', 'walking',
}

# Sub-sport overrides for cycling and swimming
_CYCLING_SUB = {
    'mountain': 'Mountain Biking',
    'gravel_cycling': 'Gravel Cycling',
    'indoor_cycling': 'Indoor Bike Trainer',
    'track_cycling': 'Road Cycling',
}
_SWIM_SUB = {
    'lap_swimming': 'Swimming Pool',
    'open_water': 'Swimming Open',
}
_SWIM_ACTIVITIES = {'Swimming Pool', 'Swimming Open'}


def _resolve_activity(sport: str, sub_sport: str):
    """Return (activity_name, sport_key) tuple."""
    sport = (sport or '').lower().replace(' ', '_')
    sub_sport = (sub_sport or '').lower().replace(' ', '_')
    if sport == 'cycling' and sub_sport in _CYCLING_SUB:
        name = _CYCLING_SUB[sub_sport]
    elif sport == 'swimming' and sub_sport in _SWIM_SUB:
        name = _SWIM_SUB[sub_sport]
    else:
        name = SPORT_MAP.get(sport, 'Running')
    return name, sport


def _pace_from_speed(speed_ms: float) -> str:
    """Convert m/s to MM:SS per mile string."""
    if not speed_ms or speed_ms <= 0:
        return ''
    secs_per_mile = 1609.344 / speed_ms
    mins = int(secs_per_mile // 60)
    secs = int(secs_per_mile % 60)
    return f'{mins}:{secs:02d}'


def _fit_timestamp_to_date(ts) -> str:
    """Convert FIT timestamp (seconds since 1989-12-31 UTC) or datetime to YYYY-MM-DD."""
    if ts is None:
        return ''
    try:
        if isinstance(ts, (int, float)):
            fit_epoch = datetime(1989, 12, 31, tzinfo=timezone.utc)
            dt = datetime.fromtimestamp(fit_epoch.timestamp() + ts, tz=timezone.utc)
        else:
            dt = ts
        return dt.strftime('%Y-%m-%d')
    except Exception:
        return ''


def parse_fit(fit_bytes: bytes) -> dict:
    """
    Parse raw FIT bytes. Returns:
      {'log_type': 'cardio', 'data': {...cardio_log fields...}}
      {'log_type': 'strength', 'data': [{...training_log fields...}, ...]}
    """
    from fit_tool.fit_file import FitFile
    from fit_tool.profile.messages.session_message import SessionMessage
    from fit_tool.profile.messages.set_message import SetMessage

    tmp_path = os.path.join(tempfile.gettempdir(), f'fit_{uuid.uuid4().hex}.fit')
    try:
        with open(tmp_path, 'wb') as f:
            f.write(fit_bytes)
        fit = FitFile.from_file(tmp_path)
    finally:
        try:
            os.remove(tmp_path)
        except OSError:
            pass

    session = None
    sets = []

    for record in fit.records:
        msg = record.message
        if isinstance(msg, SessionMessage):
            session = msg
        elif isinstance(msg, SetMessage):
            sets.append(msg)

    if session is None:
        raise ValueError('No session message found in FIT file.')

    sport = getattr(session, 'sport', None)
    sub_sport = getattr(session, 'sub_sport', None)
    sport_str = str(sport).lower().replace('sport.', '').replace(' ', '_') if sport else ''
    sub_str = str(sub_sport).lower().replace('sub_sport.', '').replace(' ', '_') if sub_sport else ''

    activity_name, sport_key = _resolve_activity(sport_str, sub_str)

    if activity_name == '__strength__':
        return _parse_strength(session, sets)

    return _parse_cardio(session, activity_name, sport_key)


def _parse_cardio(session, activity_name: str, sport_key: str) -> dict:
    def _f(attr):
        v = getattr(session, attr, None)
        try:
            f = float(v)
            return f if f != 0.0 else None
        except (TypeError, ValueError):
            return None

    def _i(attr):
        v = getattr(session, attr, None)
        try:
            i = int(v)
            return i if i != 0 else None
        except (TypeError, ValueError):
            return None

    ts = getattr(session, 'start_time', None) or getattr(session, 'timestamp', None)
    activity_date = _fit_timestamp_to_date(ts)

    elapsed_s = _f('total_elapsed_time')
    timer_s = _f('total_timer_time')
    dist_m = _f('total_distance')
    ascent_m = _f('total_ascent')
    descent_m = _f('total_descent')

    duration_min = round(elapsed_s / 60, 2) if elapsed_s else None
    moving_min = round(timer_s / 60, 2) if timer_s else None
    dist_mi = round(dist_m * 0.000621371, 3) if dist_m else None

    # Compute speed from distance/time — more reliable than avg_speed field
    if dist_m and timer_s and timer_s > 0:
        speed_ms = dist_m / timer_s
    else:
        speed_ms = None
    avg_speed_mph = round(speed_ms * 2.23694, 2) if speed_ms else None
    avg_pace = _pace_from_speed(speed_ms) if speed_ms else None

    elev_gain = round(ascent_m * 3.28084, 1) if ascent_m else None
    elev_loss = round(descent_m * 3.28084, 1) if descent_m else None

    # Cadence: FIT stores one-leg (one foot/min) for running — multiply by 2
    cadence_mult = 2 if sport_key in _ONE_LEG_CADENCE_SPORTS else 1
    raw_avg_cad = _i('avg_cadence')
    raw_max_cad = _i('max_cadence')
    avg_cadence = raw_avg_cad * cadence_mult if raw_avg_cad else None
    max_cadence = raw_max_cad * cadence_mult if raw_max_cad else None

    # Power: only meaningful for cycling/rowing; treat 0 as null (already handled by _i)
    avg_power = _i('avg_power')
    max_power = _i('max_power')
    norm_power = _i('normalized_power')

    # Active lengths / SWOLF: swimming only
    is_swim = activity_name in _SWIM_ACTIVITIES
    active_lengths = _i('num_active_lengths') if is_swim else None
    swolf = None  # computed per-lap for swimming; skip for now

    # Training effect
    aerobic_te = _f('total_training_effect')
    anaerobic_te = _f('total_anaerobic_training_effect')

    # Running dynamics (standard FIT fields — None if device doesn't record them)
    stride_length_m = _f('avg_stride_length')     # m
    raw_vert_osc = _f('avg_vertical_oscillation') # mm in FIT → show as cm
    vert_oscillation_cm = round(raw_vert_osc / 10, 1) if raw_vert_osc else None
    vert_ratio_pct = _f('avg_vertical_ratio')      # already %
    gct_ms = _f('avg_stance_time')                 # ms
    raw_gct_bal = _f('avg_stance_time_balance')    # 0–100 %, left side
    gct_balance = f'{raw_gct_bal:.1f}% L / {100-raw_gct_bal:.1f}% R' if raw_gct_bal else None

    return {
        'log_type': 'cardio',
        'data': {
            'date': activity_date,
            'activity': activity_name,
            'activity_name': '',
            'duration_min': duration_min,
            'moving_time_min': moving_min,
            'distance_mi': dist_mi,
            'avg_pace': avg_pace,
            'avg_speed': avg_speed_mph,
            'avg_hr': _i('avg_heart_rate'),
            'max_hr': _i('max_heart_rate'),
            'calories': _i('total_calories'),
            'elev_gain_ft': elev_gain,
            'elev_loss_ft': elev_loss,
            'avg_cadence': avg_cadence,
            'max_cadence': max_cadence,
            'avg_power': avg_power,
            'max_power': max_power,
            'norm_power': norm_power,
            'aerobic_te': aerobic_te,
            'anaerobic_te': anaerobic_te,
            'swolf': swolf,
            'active_lengths': active_lengths,
            'notes': '',
            # Running dynamics
            'stride_length_m': round(stride_length_m, 2) if stride_length_m else None,
            'vert_oscillation_cm': vert_oscillation_cm,
            'vert_ratio_pct': round(vert_ratio_pct, 1) if vert_ratio_pct else None,
            'gct_ms': round(gct_ms, 0) if gct_ms else None,
            'gct_balance': gct_balance,
        }
    }


def _parse_strength(session, sets) -> dict:
    activity_date = _fit_timestamp_to_date(
        getattr(session, 'start_time', None) or getattr(session, 'timestamp', None)
    )

    rows = []
    for s in sets:
        exercise_name = getattr(s, 'exercise_name', None) or getattr(s, 'category', None)
        if exercise_name:
            exercise_name = str(exercise_name).replace('_', ' ').title()
        else:
            exercise_name = 'Unknown Exercise'

        reps = getattr(s, 'repetitions', None)
        weight_kg = getattr(s, 'weight', None)
        duration_s = getattr(s, 'duration', None)

        try:
            weight_lbs = round(float(weight_kg) * 2.20462, 1) if weight_kg else None
        except (TypeError, ValueError):
            weight_lbs = None
        try:
            reps_int = int(reps) if reps is not None else None
        except (TypeError, ValueError):
            reps_int = None
        try:
            duration_s_int = int(duration_s) if duration_s is not None else None
        except (TypeError, ValueError):
            duration_s_int = None

        rows.append({
            'date': activity_date,
            'exercise': exercise_name,
            'actual_sets': 1,
            'actual_reps': reps_int,
            'actual_weight': weight_lbs,
            'actual_duration': duration_s_int,
            'notes': '',
        })

    # Merge consecutive sets of the same exercise
    if rows:
        merged = []
        cur = dict(rows[0])
        for row in rows[1:]:
            if row['exercise'] == cur['exercise']:
                cur['actual_sets'] += 1
            else:
                merged.append(cur)
                cur = dict(row)
        merged.append(cur)
        rows = merged

    return {'log_type': 'strength', 'data': rows}
