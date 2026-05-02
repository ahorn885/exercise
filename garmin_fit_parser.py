"""Parse a Garmin .fit file and return structured data ready for cardio_log or training_log."""
import math
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
    'indoor_rowing': 'Rowing Ergometer',
    'kayaking': 'Kayaking',
    'strength_training': '__strength__',
    'weight_training': '__strength__',
    'gym': '__strength__',
    'training': '__strength__',
}

# FIT numeric sport IDs (from FIT protocol spec)
# fit-tool returns sport/sub_sport as integers, not enum names
_SPORT_NUM_MAP = {
    1:  'running',
    2:  'cycling',
    5:  'swimming',
    10: 'training',           # strength/fitness equipment
    11: 'walking',
    15: 'rowing',
    17: 'hiking',
    19: 'paddling',
    41: 'kayaking',
    62: 'yoga',
}

# FIT numeric sub-sport IDs
_SUB_SPORT_NUM_MAP = {
    1:  'treadmill',
    3:  'trail_running',
    5:  'spin',
    6:  'indoor_cycling',
    7:  'road',               # road cycling sub_sport
    8:  'mountain',           # mountain biking (matches _CYCLING_SUB key)
    10: 'gravel_cycling',
    14: 'indoor_rowing',      # Garmin Forerunner indoor rowing sub_sport
    17: 'gravel_cycling',
    19: 'lap_swimming',
    20: 'open_water',
    43: 'yoga',
}

# Sports where cadence is stored as one-leg (steps/min of one foot) → multiply by 2
_ONE_LEG_CADENCE_SPORTS = {
    'running', 'trail_running', 'treadmill', 'hiking', 'walking',
}

# Sub-sport overrides for running, cycling, and swimming
_RUNNING_SUB = {
    'trail_running': 'Trail Running',
    'treadmill':     'Treadmill',
}
_CYCLING_SUB = {
    'mountain': 'Mountain Biking',
    'gravel_cycling': 'Gravel Cycling',
    'indoor_cycling': 'Indoor Bike Trainer',
    'spin': 'Indoor Bike Trainer',
    'track_cycling': 'Road Cycling',
}
_SWIM_SUB = {
    'lap_swimming': 'Swimming Pool',
    'open_water': 'Swimming Open',
}
_SWIM_ACTIVITIES = {'Swimming Pool', 'Swimming Open'}

# Garmin FIT ExerciseCategory enum → human-readable name
_EXERCISE_CATEGORY_MAP = {
    0: 'Bench Press', 1: 'Calf Raise', 2: 'Cardio', 3: 'Carry',
    4: 'Chop', 5: 'Core', 6: 'Crunch', 7: 'Curl',
    8: 'Deadlift', 9: 'Flye', 10: 'Hip Raise', 11: 'Hip Stability',
    12: 'Hip Swing', 13: 'Hyperextension', 14: 'Lateral Raise', 15: 'Leg Curl',
    16: 'Leg Raise', 17: 'Lunge', 18: 'Olympic Lift', 19: 'Plank',
    20: 'Hang', 21: 'Pull Up', 22: 'Push Up', 23: 'Row',
    24: 'Shoulder Press', 25: 'Shoulder Stability', 26: 'Shrug', 27: 'Sit Up',
    28: 'Squat', 29: 'Total Body', 30: 'Triceps Extension', 31: 'Warm Up',
    32: 'Run',
}

# FIT sentinel values — these mean "field not recorded by device"
# uint8 max=255, uint16 max=65535, uint32 max=4294967295
# Scaled sentinels appear after fit-tool applies scale factors:
#   uint16/scale=1000 → 65.535  (speed in m/s)
#   uint16/scale=10   → 6553.5  (stance time ms)
#   uint16/scale=100  → 655.35
#   uint8/scale=10    → 25.5    (training effect)
#   uint8/scale=2     → 127.5   (pedal smoothness)
_FLOAT_SENTINELS = frozenset({
    65535.0, 65.535, 6553.5, 655.35, 25.5, 2.55, 127.5,
    4294967295.0, 4294967.295, 429496729.5, 42949672.95, 429496.7295,
})
_INT_SENTINELS = frozenset({255, 65535, 4294967295})

# fit-tool attributes that are internal metadata, not data fields
_DUMP_SKIP_ATTRS = frozenset({
    'definition_message', 'developer_fields', 'endian', 'fields',
    'global_id', 'growable', 'local_id', 'size', 'ID', 'NAME', 'name',
})


def _sport_str(val) -> str:
    """Normalize a sport value (int enum or string) to a lowercase underscore string."""
    if val is None:
        return ''
    try:
        i = int(val)
        return _SPORT_NUM_MAP.get(i, str(i))
    except (TypeError, ValueError):
        return str(val).lower().replace('sport.', '').replace(' ', '_')


def _sub_sport_str(val) -> str:
    """Normalize a sub_sport value (int enum or string) to a lowercase underscore string."""
    if val is None:
        return ''
    try:
        i = int(val)
        return _SUB_SPORT_NUM_MAP.get(i, str(i))
    except (TypeError, ValueError):
        return str(val).lower().replace('sub_sport.', '').replace(' ', '_')


def _resolve_activity(sport: str, sub_sport: str):
    """Return (activity_name, sport_key) tuple."""
    sport = (sport or '').lower().replace(' ', '_')
    sub_sport = (sub_sport or '').lower().replace(' ', '_')
    if sport == 'running' and sub_sport in _RUNNING_SUB:
        name = _RUNNING_SUB[sub_sport]
    elif sport == 'cycling' and sub_sport in _CYCLING_SUB:
        name = _CYCLING_SUB[sub_sport]
    elif sport == 'swimming' and sub_sport in _SWIM_SUB:
        name = _SWIM_SUB[sub_sport]
    elif sub_sport in SPORT_MAP and SPORT_MAP[sub_sport] != '__strength__':
        # sub_sport overrides sport lookup (e.g. yoga stored under sport=training)
        name = SPORT_MAP[sub_sport]
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
    """Convert fit-tool timestamp to YYYY-MM-DD.

    fit-tool returns timestamps as Unix milliseconds (e.g. 1775964920000 for April 2026).
    Also handles datetime objects returned by some fit-tool versions.
    """
    if ts is None:
        return ''
    try:
        if isinstance(ts, (int, float)):
            # fit-tool uses Unix milliseconds
            dt = datetime.fromtimestamp(ts / 1000.0, tz=timezone.utc)
        else:
            # Already a datetime object
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

    sport_key = _sport_str(getattr(session, 'sport', None))
    sub_key = _sub_sport_str(getattr(session, 'sub_sport', None))
    activity_name, sport_key = _resolve_activity(sport_key, sub_key)

    if activity_name == '__strength__':
        return _parse_strength(session, sets)

    return _parse_cardio(session, activity_name, sport_key)


def _parse_cardio(session, activity_name: str, sport_key: str) -> dict:
    def _f(attr):
        """Get float attribute, returning None for missing/zero/sentinel values."""
        v = getattr(session, attr, None)
        try:
            f = float(v)
            if math.isnan(f) or f == 0.0 or f in _FLOAT_SENTINELS:
                return None
            return f
        except (TypeError, ValueError):
            return None

    def _i(attr):
        """Get int attribute, returning None for missing/zero/sentinel values."""
        v = getattr(session, attr, None)
        try:
            i = int(v)
            if i == 0 or i in _INT_SENTINELS:
                return None
            return i
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

    # Speed: prefer enhanced_avg_speed (uint32, reliable on modern Garmin),
    # fall back to computing from distance/time, then avg_speed.
    enhanced_ms = _f('enhanced_avg_speed')
    if enhanced_ms:
        speed_ms = enhanced_ms
    elif dist_m and timer_s and timer_s > 0:
        speed_ms = dist_m / timer_s
    else:
        speed_ms = _f('avg_speed')

    avg_speed_mph = round(speed_ms * 2.23694, 2) if speed_ms else None
    # Pace (min/mi) is only meaningful for foot sports; suppress for cycling/paddling
    _PACE_SPORTS = {'running', 'trail_running', 'treadmill', 'hiking', 'walking'}
    avg_pace = _pace_from_speed(speed_ms) if (speed_ms and sport_key in _PACE_SPORTS) else None

    elev_gain = round(ascent_m * 3.28084, 1) if ascent_m else None
    elev_loss = round(descent_m * 3.28084, 1) if descent_m else None

    # Cadence: FIT stores one-leg (one foot/min) for running → multiply by 2
    cadence_mult = 2 if sport_key in _ONE_LEG_CADENCE_SPORTS else 1
    raw_avg_cad = _i('avg_cadence')
    raw_max_cad = _i('max_cadence')
    avg_cadence = raw_avg_cad * cadence_mult if raw_avg_cad else None
    max_cadence = raw_max_cad * cadence_mult if raw_max_cad else None

    # Power: only meaningful for cycling/rowing; treat 0 and sentinels as null
    avg_power = _i('avg_power')
    max_power = _i('max_power')
    norm_power = _i('normalized_power')

    # Active lengths / SWOLF: swimming only
    is_swim = activity_name in _SWIM_ACTIVITIES
    active_lengths = _i('num_active_lengths') if is_swim else None

    # Training effect
    aerobic_te = _f('total_training_effect')
    anaerobic_te = _f('total_anaerobic_training_effect')

    # Running dynamics (standard FIT fields — None if device doesn't record them)
    # avg_step_length is in mm (one step); a stride = 2 steps → convert to metres
    _step_mm = _f('avg_step_length')
    stride_length_m = round(_step_mm * 2 / 1000, 2) if _step_mm else None
    raw_vert_osc = _f('avg_vertical_oscillation')  # mm in FIT → convert to cm
    vert_oscillation_cm = round(raw_vert_osc / 10, 1) if raw_vert_osc else None
    vert_ratio_pct = _f('avg_vertical_ratio')       # already %
    gct_ms = _f('avg_stance_time')                  # ms
    raw_gct_bal = _f('avg_stance_time_balance')     # 0–100 %, left side
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
            'swolf': None,
            'active_lengths': active_lengths,
            'notes': '',
            # Running dynamics
            'stride_length_m': stride_length_m,
            'vert_oscillation_cm': vert_oscillation_cm,
            'vert_ratio_pct': round(vert_ratio_pct, 1) if vert_ratio_pct else None,
            'gct_ms': round(gct_ms, 0) if gct_ms else None,
            'gct_balance': gct_balance,
        }
    }


def _parse_strength(session, sets) -> dict:
    """Parse a strength FIT session.

    Returns per-exercise data with individual set details preserved:
      {'log_type': 'strength', 'data': [
        {'date': str, 'exercise': str,
         'sets': [{'reps': int|None, 'weight_lbs': float|None, 'duration_sec': int|None}, ...]},
        ...
      ]}

    Sets are grouped by exercise (all sets of the same exercise together),
    preserving the order in which exercises first appear.
    """
    activity_date = _fit_timestamp_to_date(
        getattr(session, 'start_time', None) or getattr(session, 'timestamp', None)
    )

    def _exercise_name(s):
        ex = getattr(s, 'exercise_name', None)
        if ex is not None:
            ex_str = str(ex)
            if ex_str not in ('None', '', '65535', '65534'):
                return ex_str.replace('_', ' ').title()
        cat = getattr(s, 'category', None)
        if cat is not None:
            cats = cat if isinstance(cat, (list, tuple)) else [cat]
            for c in cats:
                try:
                    c_int = int(c)
                    if c_int < 65534:
                        return _EXERCISE_CATEGORY_MAP.get(c_int, f'Exercise {c_int}')
                except (TypeError, ValueError):
                    pass
        return 'Unknown Exercise'

    # Group all sets by exercise, preserving first-seen order (handles circuits)
    exercise_sets: dict = {}
    exercise_order: list = []

    for s in sets:
        name = _exercise_name(s)

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
            duration_sec = int(duration_s) if duration_s is not None else None
        except (TypeError, ValueError):
            duration_sec = None

        if name not in exercise_sets:
            exercise_sets[name] = []
            exercise_order.append(name)
        exercise_sets[name].append(
            {'reps': reps_int, 'weight_lbs': weight_lbs, 'duration_sec': duration_sec}
        )

    data = [
        {'date': activity_date, 'exercise': ex, 'sets': exercise_sets[ex]}
        for ex in exercise_order
    ]
    return {'log_type': 'strength', 'data': data}


# ── Debug dump ────────────────────────────────────────────────────────────────

def _dump_fit(fit_bytes: bytes) -> dict:
    """
    Return a comprehensive dump of every message and field in a FIT file —
    standard fields, developer-defined fields, and developer data values.
    Used by the /garmin/debug-fit route to discover what a device records.
    """
    from fit_tool.fit_file import FitFile

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

    msg_counts = {}
    session_fields = {}
    developer_field_defs = []
    sample_records = []          # first 3 RecordMessage entries with non-None fields
    all_message_samples = {}     # one sample per message type

    def _fields(m):
        """Collect non-None, non-internal attributes as str-converted values."""
        out = {}
        for attr in dir(m):
            if attr.startswith('_') or attr in _DUMP_SKIP_ATTRS:
                continue
            try:
                val = getattr(m, attr)
                if callable(val):
                    continue
                if val is not None:
                    out[attr] = str(val)
            except Exception:
                pass
        return out

    def _generic_fields(m):
        """Extract fields from a GenericMessage by iterating its typed field list."""
        gid = getattr(m, 'global_id', '?')
        out = {'global_id': str(gid)}
        for field in getattr(m, 'fields', []):
            try:
                name = getattr(field, 'name', None) or f'field_{getattr(field, "field_id", "?")}'
                val = field.get_value(0)
                if val is not None:
                    out[name] = str(val)
            except Exception:
                pass
        return out

    for record in fit.records:
        msg = record.message
        msg_type = type(msg).__name__

        if msg_type == 'GenericMessage':
            gid = getattr(msg, 'global_id', '?')
            sample_key = f'GenericMessage[{gid}]'
            msg_counts[sample_key] = msg_counts.get(sample_key, 0) + 1
            fields = _generic_fields(msg)
        else:
            sample_key = msg_type
            msg_counts[msg_type] = msg_counts.get(msg_type, 0) + 1
            fields = _fields(msg)

        if sample_key == 'SessionMessage':
            session_fields = fields
        elif sample_key == 'FieldDescriptionMessage':
            developer_field_defs.append({
                k: v for k, v in fields.items()
                if k in ('field_name', 'units', 'fit_base_type_id',
                         'native_message_num', 'native_field_num',
                         'developer_data_index', 'array')
            })
        elif sample_key == 'RecordMessage' and len(sample_records) < 3:
            sample_records.append(fields)

        if len(fields) > len(all_message_samples.get(sample_key, {})):
            all_message_samples[sample_key] = fields

    # Extract developer data values from records
    dev_data_samples = []
    for record in fit.records:
        msg = record.message
        dev_fields = getattr(msg, 'developer_fields', None)
        if dev_fields:
            entry = {'message_type': type(msg).__name__, 'developer_fields': {}}
            if isinstance(dev_fields, dict):
                entry['developer_fields'] = {k: str(v) for k, v in dev_fields.items()}
            elif hasattr(dev_fields, '__iter__'):
                for df in dev_fields:
                    name = getattr(df, 'name', None) or getattr(df, 'field_name', str(df))
                    value = getattr(df, 'value', getattr(df, 'raw_value', str(df)))
                    entry['developer_fields'][str(name)] = str(value)
            if entry['developer_fields'] and len(dev_data_samples) < 5:
                dev_data_samples.append(entry)

    return {
        'message_counts': dict(sorted(msg_counts.items())),
        'session_fields': session_fields,
        'developer_field_defs': developer_field_defs,
        'developer_data_samples': dev_data_samples,
        'sample_records': sample_records,
        'all_message_samples': all_message_samples,
    }


# ── Wellness FIT parser ───────────────────────────────────────────────────────

# Garmin wellness GenericMessage types fit_tool has no typed profiles for.
# Maps global_id → {field_id → semantic_name}
_WELLNESS_GENERIC_MAP = {
    233: {0: 'heart_rate'},        # monitoring_hr_data: HR in bpm
    279: {0: 'respiration_rate'},  # respiration_rate: breaths/min
    297: {0: 'body_battery'},      # body_battery: 0-100 (negative = invalid)
}

_FIT_TS_FIELD_ID = 253         # FIT protocol standard timestamp field_id
_FIT_EPOCH_OFFSET_S = 631065600  # seconds from 1970-01-01 to FIT epoch 1989-01-01


def _fit_ts_to_unix_ms(raw_ts) -> int:
    """Normalize a raw FIT timestamp to Unix milliseconds.

    fit_tool typed messages return Unix ms; raw GenericMessage field values
    may be in FIT epoch seconds, Unix seconds, or Unix ms.
    """
    if raw_ts is None:
        return 0
    try:
        ts = int(raw_ts)
        if ts <= 0:
            return 0
        if ts > 1_000_000_000_000:   # already Unix ms (> 1 trillion)
            return ts
        if ts > 1_500_000_000:       # Unix seconds (post-2017)
            return ts * 1000
        if ts > 500_000_000:         # FIT epoch seconds
            return (ts + _FIT_EPOCH_OFFSET_S) * 1000
        return 0
    except (TypeError, ValueError):
        return 0


def parse_wellness_fit(fit_bytes: bytes) -> list:
    """Parse a Garmin wellness .fit file.

    Extracts heart rate, stress, body battery, respiration, and monitoring
    interval data (steps, calories, active time, distance).

    Returns a list of row dicts ready for INSERT INTO wellness_log, merged
    by second-level timestamp to produce at most one row per second.
    """
    from fit_tool.fit_file import FitFile

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

    # readings[second_key_ms] → merged row dict
    readings: dict = {}

    def _slot(ts_ms: int) -> dict:
        """Get or create a row slot for the given second boundary."""
        key = (ts_ms // 1000) * 1000
        if key not in readings:
            readings[key] = {
                'timestamp_ms': key,
                'date': '',
                'heart_rate': None,
                'stress_level': None,
                'body_battery': None,
                'respiration_rate': None,
                'steps': None,
                'active_calories': None,
                'active_time_s': None,
                'distance_m': None,
                'activity_type': None,
            }
        return readings[key]

    def _safe_int(v, lo=None, hi=None):
        try:
            i = int(v)
            if lo is not None and i < lo:
                return None
            if hi is not None and i > hi:
                return None
            return i
        except (TypeError, ValueError):
            return None

    def _safe_float(v, lo=None, hi=None):
        try:
            f = float(v)
            if lo is not None and f < lo:
                return None
            if hi is not None and f > hi:
                return None
            return f
        except (TypeError, ValueError):
            return None

    def _generic_ts(msg) -> int:
        """Extract timestamp from a GenericMessage: named attr first, then field_id=253."""
        raw = getattr(msg, 'timestamp', None)
        if raw is not None:
            ts = _fit_ts_to_unix_ms(raw)
            if ts:
                return ts
        for field in getattr(msg, 'fields', []):
            if getattr(field, 'field_id', None) == _FIT_TS_FIELD_ID:
                try:
                    return _fit_ts_to_unix_ms(field.get_value(0))
                except Exception:
                    pass
        return 0

    for record in fit.records:
        msg = record.message
        mtype = type(msg).__name__

        if mtype == 'MonitoringMessage':
            ts_ms = _fit_ts_to_unix_ms(getattr(msg, 'timestamp', None))
            if not ts_ms:
                continue
            r = _slot(ts_ms)

            steps = _safe_int(getattr(msg, 'steps', None), lo=1)
            if steps is not None and r['steps'] is None:
                r['steps'] = steps

            cals = _safe_int(getattr(msg, 'active_calories', None), lo=1)
            if cals is not None and r['active_calories'] is None:
                r['active_calories'] = cals

            act_time = _safe_float(getattr(msg, 'active_time', None), lo=0.01)
            if act_time is not None and r['active_time_s'] is None:
                r['active_time_s'] = round(act_time, 2)

            dist = _safe_float(getattr(msg, 'distance', None), lo=0.01)
            if dist is not None and r['distance_m'] is None:
                r['distance_m'] = round(dist, 2)

            atype = getattr(msg, 'activity_type', None)
            if atype is not None and r['activity_type'] is None:
                try:
                    r['activity_type'] = int(atype)
                except (TypeError, ValueError):
                    pass

        elif mtype == 'StressLevelMessage':
            raw_ts = getattr(msg, 'stress_level_time', None) or getattr(msg, 'timestamp', None)
            ts_ms = _fit_ts_to_unix_ms(raw_ts)
            if not ts_ms:
                continue
            # -2 = computing, -1 = off-wrist; filter with lo=1
            sv = _safe_int(getattr(msg, 'stress_level_value', None), lo=1, hi=100)
            if sv is not None:
                r = _slot(ts_ms)
                if r['stress_level'] is None:
                    r['stress_level'] = sv

        elif mtype == 'GenericMessage':
            gid = getattr(msg, 'global_id', None)
            if gid not in _WELLNESS_GENERIC_MAP:
                continue
            field_map = _WELLNESS_GENERIC_MAP[gid]
            fields_list = getattr(msg, 'fields', [])

            ts_ms = _generic_ts(msg)
            if not ts_ms:
                continue

            extracted = {}
            for field in fields_list:
                fid = getattr(field, 'field_id', None)
                if fid not in field_map:
                    continue
                try:
                    val = field.get_value(0)
                    if val is not None:
                        extracted[field_map[fid]] = val
                except Exception:
                    pass

            if not extracted:
                continue

            r = _slot(ts_ms)

            if 'heart_rate' in extracted:
                hr = _safe_int(extracted['heart_rate'], lo=1, hi=250)
                if hr is not None and r['heart_rate'] is None:
                    r['heart_rate'] = hr

            if 'body_battery' in extracted:
                bb = _safe_int(extracted['body_battery'], lo=0, hi=100)
                if bb is not None and r['body_battery'] is None:
                    r['body_battery'] = bb

            if 'respiration_rate' in extracted:
                rr = _safe_float(extracted['respiration_rate'], lo=1.0, hi=60.0)
                if rr is not None and r['respiration_rate'] is None:
                    r['respiration_rate'] = round(rr, 1)

    # Build output list — fill date, skip empty rows
    result = []
    for ts_ms in sorted(readings):
        row = readings[ts_ms]
        try:
            dt = datetime.fromtimestamp(ts_ms / 1000.0, tz=timezone.utc)
            row['date'] = dt.strftime('%Y-%m-%d')
        except Exception:
            continue
        has_data = any(
            row[f] is not None
            for f in ('heart_rate', 'stress_level', 'body_battery',
                      'respiration_rate', 'steps', 'active_calories', 'active_time_s')
        )
        if has_data:
            result.append(row)

    return result
