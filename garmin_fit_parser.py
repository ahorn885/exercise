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
    7:  'indoor_rowing',
    8:  'mountain',           # mountain biking (matches _CYCLING_SUB key)
    10: 'gravel_cycling',
    17: 'gravel_cycling',
    19: 'lap_swimming',
    20: 'open_water',
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
    'spin': 'Indoor Bike Trainer',
    'track_cycling': 'Road Cycling',
    'indoor_rowing': 'Rowing Ergometer',
}
_SWIM_SUB = {
    'lap_swimming': 'Swimming Pool',
    'open_water': 'Swimming Open',
}
_SWIM_ACTIVITIES = {'Swimming Pool', 'Swimming Open'}

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
    4294967295.0, 4294967.295, 429496.7295,
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
    avg_pace = _pace_from_speed(speed_ms) if speed_ms else None

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
    stride_length_m = _f('avg_stride_length')
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

    for record in fit.records:
        msg = record.message
        msg_type = type(msg).__name__

        msg_counts[msg_type] = msg_counts.get(msg_type, 0) + 1

        fields = _fields(msg)

        if msg_type == 'SessionMessage':
            session_fields = fields
        elif msg_type == 'FieldDescriptionMessage':
            developer_field_defs.append({
                k: v for k, v in fields.items()
                if k in ('field_name', 'units', 'fit_base_type_id',
                         'native_message_num', 'native_field_num',
                         'developer_data_index', 'array')
            })
        elif msg_type == 'RecordMessage' and len(sample_records) < 3:
            sample_records.append(fields)

        if msg_type not in all_message_samples:
            all_message_samples[msg_type] = fields

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
