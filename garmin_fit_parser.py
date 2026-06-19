"""Parse a Garmin .fit file and return structured data ready for cardio_log or training_log."""
import math
import os
import uuid
import tempfile
from datetime import datetime, timezone

# Fine layer0 discipline id for a completed cardio activity (#681 §4 Slice 2b);
# the indoor-machine flag for provider_raw_record (#681 §4 Slice 2c).
from provider_cardio_resolve import resolve_cardio_discipline, resolve_indoor_machine

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


def _humanize_enum_name(name: str) -> str:
    """Garmin enum names are SCREAM_CASE with an N-prefix on tokens that start
    with a digit (Python identifier rule): `N3_WAY_CALF_RAISE` → "3 Way Calf
    Raise". Strip the N-prefix where applicable, then title-case."""
    parts = name.split('_')
    parts = [
        p[1:] if (len(p) > 1 and p[0] == 'N' and p[1].isdigit()) else p
        for p in parts
    ]
    return ' '.join(p.capitalize() for p in parts)


def _build_exercise_subtype_map() -> dict:
    """Walk fit_tool's per-category `<Category>ExerciseName` enums to build
    `{category_code: {subtype_code: 'Human Name'}}`. Garmin's FIT SDK is the
    source of truth — pulling at import time keeps this in sync with any
    `fit_tool` upgrade without hand-maintaining ~30 enums of 10-100 members.
    Degrades gracefully to an empty map if `fit_tool` isn't importable."""
    try:
        from fit_tool.profile.profile_type import ExerciseCategory
        import fit_tool.profile.profile_type as _pt
    except ImportError:
        return {}
    out: dict = {}
    for cat in ExerciseCategory:
        # Naming convention: BENCH_PRESS → BenchPressExerciseName.
        enum_class_name = ''.join(
            w.capitalize() for w in cat.name.split('_')
        ) + 'ExerciseName'
        enum_class = getattr(_pt, enum_class_name, None)
        if enum_class is None:
            continue
        subtypes: dict = {}
        for member in enum_class:
            # Skip the per-category UNKNOWN sentinel (65535) consistently.
            if member.value >= 65534:
                continue
            subtypes[member.value] = _humanize_enum_name(member.name)
        if subtypes:
            out[cat.value] = subtypes
    return out


_EXERCISE_SUBTYPE_MAP = _build_exercise_subtype_map()

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


# Strength-set physical sanity ceilings. Some FIT exports surface a
# scale-mismatched or device-internal value that isn't in the sentinel set
# but is still clearly garbage (e.g. Andy's 2026-05-25 import: weight=4096 kg,
# raw uint16 4096 with an unexpected scale). Anything above these caps is
# treated as missing — a strongman deadlift is ~500 kg, a high-rep set tops
# out around 100, no per-set duration runs an hour.
_SET_REPS_MAX = 500
_SET_WEIGHT_KG_MAX = 1000.0
_SET_DURATION_SEC_MAX = 7200


def _set_int(value, *, max_reasonable=None):
    """Strength-set int field with FIT sentinel + sanity-ceiling filtering.
    Returns None for missing, zero, the uint8/uint16/uint32 "no value"
    sentinels, or anything above the optional ceiling."""
    if value is None:
        return None
    try:
        i = int(value)
    except (TypeError, ValueError):
        return None
    if i <= 0 or i in _INT_SENTINELS:
        return None
    if max_reasonable is not None and i > max_reasonable:
        return None
    return i


def _set_float(value, *, max_reasonable=None):
    """Strength-set float counterpart. Same shape as _set_int."""
    if value is None:
        return None
    try:
        f = float(value)
    except (TypeError, ValueError):
        return None
    if math.isnan(f) or f <= 0.0 or f in _FLOAT_SENTINELS:
        return None
    if max_reasonable is not None and f > max_reasonable:
        return None
    return f

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


def _garmin_disc_token(sport: str, sub_sport: str) -> str:
    """Refine a FIT (sport, sub_sport) into the fine Garmin token the discipline
    crosswalk keys on (#681 §4 Slice 2b). The FIT `sport_key` is coarse (the
    sub_sport carries the trail/MTB/gravel/open-water signal that the display
    name already uses), so mirror that refinement for the discipline id."""
    s = (sport or '').lower()
    ss = (sub_sport or '').lower()
    if s == 'running':
        return 'trail_running' if ss == 'trail_running' else 'running'
    if s == 'cycling':
        if ss == 'mountain':
            return 'mountain_biking'
        if ss == 'gravel_cycling':
            return 'gravel_cycling'
        if ss in ('indoor_cycling', 'spin'):
            return 'indoor_cycling'
        return 'cycling'
    if s == 'swimming':
        return 'open_water_swimming' if ss == 'open_water' else 'swimming'
    return s


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

    result = _parse_cardio(session, activity_name, sport_key)
    # #681 §4 Slice 2b — carry the fine layer0 discipline id (option C).
    disc = resolve_cardio_discipline('garmin', _garmin_disc_token(sport_key, sub_key))
    result['data']['discipline_id'] = disc.discipline_id
    # #681 §4 Slice 2c — the raw provider signal (record-don't-drop) + the
    # indoor-machine flag for provider_raw_record. The indoor signal is the FIT
    # sub_sport (indoor_cycling/spin/treadmill/indoor_rowing); fall back to the
    # sport for the rare case it lands there.
    machine = (resolve_indoor_machine('garmin', sub_key)
               or resolve_indoor_machine('garmin', sport_key))
    result['data']['_provider_raw'] = {
        'provider': 'garmin',
        'observed_at': result['data'].get('date'),
        'bucket': disc.bucket,
        'canonical_ref': disc.discipline_id or machine,
        'payload': {
            'sport': sport_key,
            'sub_sport': sub_key,
            'activity': activity_name,
            'discipline_id': disc.discipline_id,
            'plan_sport_type': disc.plan_sport_type,
            'indoor_machine': machine,
        },
    }
    print(  # Rule #15
        f"[cardio-ingest] garmin-fit sport={sport_key!r} sub={sub_key!r} "
        f"-> discipline_id={disc.discipline_id} coarse={disc.plan_sport_type} "
        f"bucket={disc.bucket} machine={machine!r}"
    )
    return result


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
         'sets': [{'reps': int|None, 'weight_kg': float|None, 'duration_sec': int|None}, ...]},
        ...
      ]}

    Weight is read from the FIT record's native `weight` field (kg per the
    FIT spec) and stored as-is. Display-side unit conversion is the
    consumer's responsibility (see `units.format_weight`).

    Sets are grouped by exercise (all sets of the same exercise together),
    preserving the order in which exercises first appear.
    """
    activity_date = _fit_timestamp_to_date(
        getattr(session, 'start_time', None) or getattr(session, 'timestamp', None)
    )

    def _coerce_list(v):
        if v is None:
            return []
        return list(v) if isinstance(v, (list, tuple)) else [v]

    def _exercise_name(s):
        # Most specific: `(category, category_subtype)` → the per-category
        # `<Category>ExerciseName` enum (e.g. (0, 1) → "Barbell Bench Press").
        cats = _coerce_list(getattr(s, 'category', None))
        subs = _coerce_list(getattr(s, 'category_subtype', None))
        for cat, sub in zip(cats, subs):
            try:
                cat_int, sub_int = int(cat), int(sub)
            except (TypeError, ValueError):
                continue
            if cat_int >= 65534 or sub_int >= 65534:
                continue
            cat_map = _EXERCISE_SUBTYPE_MAP.get(cat_int)
            if cat_map and sub_int in cat_map:
                return cat_map[sub_int]
        # Coarse fallback: category only.
        for cat in cats:
            try:
                c_int = int(cat)
                if c_int < 65534:
                    return _EXERCISE_CATEGORY_MAP.get(c_int, f'Exercise {c_int}')
            except (TypeError, ValueError):
                continue
        # Free-form string label (non-SetMessage callers).
        ex = getattr(s, 'exercise_name', None)
        if ex is not None:
            ex_str = str(ex)
            if ex_str not in ('None', '', '65535', '65534'):
                return ex_str.replace('_', ' ').title()
        return 'Unknown Exercise'

    # Group all sets by exercise, preserving first-seen order (handles circuits)
    exercise_sets: dict = {}
    exercise_order: list = []

    for s in sets:
        name = _exercise_name(s)

        # Filter FIT sentinels + physical-sanity ceilings before recording.
        # Without this the set chips render junk like "65535r 9030.0lb"
        # (uint16 sentinel reps + scale-mismatched weight) and poison the
        # downstream volume / est_1RM aggregates.
        reps_int = _set_int(
            getattr(s, 'repetitions', None), max_reasonable=_SET_REPS_MAX,
        )
        weight_kg = _set_float(
            getattr(s, 'weight', None), max_reasonable=_SET_WEIGHT_KG_MAX,
        )
        # FIT weight is already kg (per spec); round to 1 dp for chip display.
        weight_kg = round(weight_kg, 1) if weight_kg else None
        duration_sec = _set_int(
            getattr(s, 'duration', None), max_reasonable=_SET_DURATION_SEC_MAX,
        )

        if name not in exercise_sets:
            exercise_sets[name] = []
            exercise_order.append(name)
        exercise_sets[name].append(
            {'reps': reps_int, 'weight_kg': weight_kg, 'duration_sec': duration_sec}
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
    generic_samples = {}         # global_id -> up to 5 distinct field dicts

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
        """Extract fields from a GenericMessage by iterating its typed field list.

        Key every field by its field_id. fit_tool usually names generic fields
        just "field", so keying by name alone collides — every field but the
        last is lost. Keying by field_id keeps them all and surfaces the id,
        which is exactly what's needed to reverse-engineer unmapped Garmin
        message types (HRV, sleep, training readiness, SpO2, …)."""
        gid = getattr(m, 'global_id', '?')
        out = {'global_id': str(gid)}
        for field in getattr(m, 'fields', []):
            try:
                fid = getattr(field, 'field_id', '?')
                name = getattr(field, 'name', None)
                key = f'field_{fid}' if (not name or name == 'field') else f'{name}_{fid}'
                val = field.get_value(0)
                if val is not None:
                    out[key] = str(val)
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
            # Keep a few distinct samples per global_id so real values are
            # visible even when one message carries a sentinel — needed to
            # tell e.g. a valid body-battery from the -200 "invalid" marker.
            # For [275] sleep stages we keep every instance — each one is a
            # distinct stage transition and the 5-cap would lose mid-night
            # stages, breaking the duration tally.
            _bucket = generic_samples.setdefault(str(gid), [])
            try:
                _gid_int = int(gid)
            except (TypeError, ValueError):
                _gid_int = None
            if _gid_int in _DUMP_KEEP_ALL_INSTANCES:
                _bucket.append(fields)
            elif len(_bucket) < 5 and fields not in _bucket:
                _bucket.append(fields)
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

    # Surface decode candidates for `[384] field_5/6/7` (the Deep/Light/REM
    # minute split hypothesis was retired in PR #489 — f7 turned out to be
    # HRV × 65536; see `_METRICS_SLEEP_SUMMARY_MSG`).
    # The operator can paste Connect's stage minutes alongside the candidates
    # to find the decoder (if any) that matches the new reference day.
    sleep_stage_candidates = []
    for sample in generic_samples.get(str(_METRICS_SLEEP_SUMMARY_MSG), []):
        try:
            f5 = int(sample.get('field_5', ''))
            f6 = int(sample.get('field_6', ''))
            f7 = int(sample.get('field_7', ''))
        except (TypeError, ValueError):
            continue
        sleep_stage_candidates.append({
            'raw': {'f5': f5, 'f6': f6, 'f7': f7},
            'candidates': _sleep_stage_decode_candidates(f5, f6, f7),
        })

    # Walk `_SLEEP_DATA.fit` `[275]` stage transitions and tally minutes per
    # code. Final stage's duration uses the latest available sleep_end_ts
    # (from `[384] field_11` if the file also contains metrics, else None —
    # in the standalone _SLEEP_DATA.fit case we omit the last segment, which
    # still recovers all the stage codes for matching against Connect).
    sleep_stage_events = _walk_sleep_stage_events(fit)
    sleep_end_ts = None
    for sample in generic_samples.get(str(_METRICS_SLEEP_SUMMARY_MSG), []):
        try:
            sleep_end_ts = int(sample.get('field_11', ''))
            break
        except (TypeError, ValueError):
            continue
    sleep_stage_minutes = _stage_minutes_from_events(
        sleep_stage_events, sleep_end_ts=sleep_end_ts,
    )

    # Surface candidate sub-score slot values for `[346] field_5/7/8/10`.
    # The slot ↔ Stress/Light/REM/Awake mapping isn't locked; the
    # diagnostic carries raw values, intra-night ranks, and qualitative
    # bands so the operator can correlate against Connect's per-
    # contributor ratings across multiple nights. See
    # `_sleep_sub_score_slot_candidates` for the disambiguation strategy.
    sleep_sub_score_slot_candidates = []
    for sample in generic_samples.get(str(_SLEEP_DATA_SCORE_MSG), []):
        raw = {
            slot: sample.get(slot, '')
            for slot in _SLEEP_SUB_SCORE_SLOTS
        }
        candidates = _sleep_sub_score_slot_candidates(
            raw['field_5'], raw['field_7'],
            raw['field_8'], raw['field_10'],
        )
        if candidates:
            sleep_sub_score_slot_candidates.append({
                'raw': raw,
                'candidates': candidates,
            })

    # Surface counter-derivation candidates for `[346] field_12 / field_13`
    # — the mystery sleep counters (issue #283). Computes plausible
    # derivations from the `[275]` event list (stage-period counts,
    # transition count) and flags any that match the raw `[346]` values
    # in the same file. Operator hypothesis-tests across nights.
    sleep_counter_candidates = []
    for sample in generic_samples.get(str(_SLEEP_DATA_SCORE_MSG), []):
        raw_counters = {
            'field_12': sample.get('field_12', ''),
            'field_13': sample.get('field_13', ''),
        }
        cand = _sleep_counter_derivation_candidates(
            sleep_stage_events, raw_counters,
        )
        if cand:
            sleep_counter_candidates.append(cand)

    return {
        'message_counts': dict(sorted(msg_counts.items())),
        'session_fields': session_fields,
        'developer_field_defs': developer_field_defs,
        'developer_data_samples': dev_data_samples,
        'sample_records': sample_records,
        'all_message_samples': all_message_samples,
        'generic_samples': dict(sorted(generic_samples.items())),
        'sleep_stage_decode_candidates': sleep_stage_candidates,
        'sleep_stage_events': sleep_stage_events,
        'sleep_stage_minutes_by_code': sleep_stage_minutes,
        'sleep_sub_score_slot_candidates': sleep_sub_score_slot_candidates,
        'sleep_counter_derivation_candidates': sleep_counter_candidates,
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


# `_WELLNESS.fit` `GenericMessage[211]` — daily resting-HR summary.
# Verified across May 28 (Garmin Connect: 7d 48, daily 44) and May 30
# (7d 45, daily 46):
#   field_0 = 7d_avg_resting_hr  (bpm)
#   field_1 = today_resting_hr   (bpm) — Garmin's authoritative value,
#                                        computed from a sustained-low
#                                        overnight window. More accurate
#                                        than MIN(wellness_log.heart_rate),
#                                        which can pick up brief dips.
_WELLNESS_RESTING_HR_MSG = 211


def parse_wellness_daily_extras(fit_bytes: bytes) -> dict:
    """Pull the daily-aggregate values that live in `_WELLNESS.fit` but
    aren't per-second readings:
      - resting metabolic rate (from `MonitoringInfoMessage`)
      - today's resting HR + 7-day-avg resting HR (`GenericMessage[211]`)
      - floors climbed / descended (from `MonitoringMessage.ascent`/`descent`,
        cumulative across the day → take MAX per file)
      - intensity minutes (`moderate_activity_minutes + 2 * vigorous_*`,
        also cumulative → MAX)
      - SpO₂ avg / low (`MonitoringMessage.pulse_ox` if the watch emits it;
        Garmin's wrist-pulse-ox measurement otherwise lives in `_SPO2_DATA.fit`
        which this watch doesn't appear to produce — captured opportunistically)

    Returns `{date, resting_metabolic_rate?, resting_hr?, resting_hr_7day_avg?,
    floors_climbed?, floors_descended?, intensity_minutes?, spo2_avg?,
    spo2_low?}` or `{}` if none of the daily fields are present. The bulk
    importer UPSERTs this into `garmin_daily_metrics` so the wellness page
    can surface it alongside the daily activity card.
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

    out: dict = {}
    file_ts_ms = 0
    # MonitoringMessage cumulative trackers (running max across the file).
    max_ascent = max_descent = None
    max_moderate = max_vigorous = None
    spo2_samples: list = []
    for record in fit.records:
        msg = record.message
        mtype = type(msg).__name__
        if mtype == 'MonitoringInfoMessage' and 'resting_metabolic_rate' not in out:
            v = getattr(msg, 'resting_metabolic_rate', None)
            if v is not None:
                try:
                    n = int(v)
                    # 0 is a sensible "device didn't compute" sentinel;
                    # values < 800 or > 4000 kcal aren't physiological.
                    if 800 <= n <= 4000:
                        out['resting_metabolic_rate'] = n
                except (TypeError, ValueError):
                    pass
        elif mtype == 'MonitoringMessage':
            # ascent / descent / *_activity_minutes are cumulative running
            # totals — take the file's MAX rather than summing.
            ascent = getattr(msg, 'ascent', None)
            if ascent is not None:
                try:
                    n = int(ascent)
                    if n >= 0 and (max_ascent is None or n > max_ascent):
                        max_ascent = n
                except (TypeError, ValueError):
                    pass
            descent = getattr(msg, 'descent', None)
            if descent is not None:
                try:
                    n = int(descent)
                    if n >= 0 and (max_descent is None or n > max_descent):
                        max_descent = n
                except (TypeError, ValueError):
                    pass
            mod = getattr(msg, 'moderate_activity_minutes', None)
            if mod is not None:
                try:
                    n = int(mod)
                    if n >= 0 and (max_moderate is None or n > max_moderate):
                        max_moderate = n
                except (TypeError, ValueError):
                    pass
            vig = getattr(msg, 'vigorous_activity_minutes', None)
            if vig is not None:
                try:
                    n = int(vig)
                    if n >= 0 and (max_vigorous is None or n > max_vigorous):
                        max_vigorous = n
                except (TypeError, ValueError):
                    pass
            # Pulse-ox: opportunistic — try the documented attribute names;
            # fit_tool's typed MonitoringMessage may not expose any of them,
            # in which case spo2_samples stays empty.
            for attr in ('pulse_ox', 'current_pulse_ox', 'spo2'):
                v = getattr(msg, attr, None)
                if v is not None:
                    try:
                        n = int(v)
                        # Garmin reports SpO₂ as a 0-100 % integer; 0 means
                        # "no reading this minute".
                        if 50 <= n <= 100:
                            spo2_samples.append(n)
                    except (TypeError, ValueError):
                        pass
                    break  # only one attribute should populate per message
        elif mtype == 'GenericMessage' and \
                getattr(msg, 'global_id', None) == _WELLNESS_RESTING_HR_MSG:
            # First occurrence wins — these repeat with the same value
            # throughout the file.
            fields = _generic_field_map(msg)
            if 'resting_hr_7day_avg' not in out and fields.get(0) is not None:
                try:
                    hr7 = int(fields[0])
                    if 30 <= hr7 <= 120:
                        out['resting_hr_7day_avg'] = hr7
                except (TypeError, ValueError):
                    pass
            if 'resting_hr' not in out and fields.get(1) is not None:
                try:
                    hr = int(fields[1])
                    if 30 <= hr <= 120:
                        out['resting_hr'] = hr
                except (TypeError, ValueError):
                    pass
        elif mtype == 'FileIdMessage' and not file_ts_ms:
            tc = getattr(msg, 'time_created', None)
            if tc is not None:
                try:
                    ms = int(tc)
                    if ms < 1_000_000_000_000:
                        ms *= 1000
                    file_ts_ms = ms
                except (TypeError, ValueError):
                    pass

    if max_ascent is not None:
        out['floors_climbed'] = max_ascent
    if max_descent is not None:
        out['floors_descended'] = max_descent
    # Garmin's published "Intensity Minutes" = moderate + 2 × vigorous,
    # per the activity tracker spec. Cap at a generous physiological ceiling
    # (24 h × 60 min = 1440) to drop any scale-mismatched outlier.
    if max_moderate is not None or max_vigorous is not None:
        total = (max_moderate or 0) + 2 * (max_vigorous or 0)
        if 0 <= total <= 1440:
            out['intensity_minutes'] = total
    if spo2_samples:
        out['spo2_avg'] = int(round(sum(spo2_samples) / len(spo2_samples)))
        out['spo2_low'] = min(spo2_samples)

    if not out or not file_ts_ms:
        return {}
    out['date'] = datetime.fromtimestamp(file_ts_ms / 1000.0, tz=timezone.utc) \
                          .strftime('%Y-%m-%d')
    return out


# ── Metrics / Sleep / HRV FIT parsers ────────────────────────────────────────
# Three new file types beyond `_WELLNESS.fit`, all of which Garmin emits per
# day:
#   _METRICS.fit      — daily derived metrics (sleep score, sleep timing,
#                       sleep contributors, sleep respiration, HRV daily, …)
#   _SLEEP_DATA.fit   — sleep detail (overall score + 6 contributor sub-scores)
#   _HRV_STATUS.fit   — overnight HRV (avg + per-period samples)
#
# fit_tool has no typed profiles for the GenericMessage types these files use;
# all decoding here is reverse-engineered against `442850388081_METRICS.fit`,
# `442850395134_METRICS.fit`, `442850402350_SLEEP_DATA.fit`, and
# `442850380765_HRV_STATUS.fit` (all from 2026-05-28), cross-referenced against
# the user's Garmin Connect screenshots for the same date (sleep score 96,
# bedtime 01:14 IST, wake 09:30 IST, awake 4 min, avg sleep respiration 13,
# overnight HRV 54 ms).
#
# Field mappings are documented with the verifying value in the comment. Where
# a field's purpose is unverified (no second reference day yet), it's parsed
# but left out of the returned dict, with a TODO. Don't guess what unverified
# fields hold — issue #283 follow-up will revisit once more days land.

# `_METRICS.fit` `GenericMessage[330]` — simple sleep-score row.
# field_2 = sleep score (verified: 96 ↔ Garmin Connect 96).
_METRICS_SLEEP_SCORE_SIMPLE_MSG = 330

# `_METRICS.fit` `GenericMessage[384]` — rich sleep summary.
# Verified across May 28 + May 30 + Jun 2 references:
#   field_2              = sleep_score (96 / 65 / 58 ↔ Garmin Connect)
#                          NOTE: field_16 was 96 on May 28 but 75 on May 30 —
#                          NOT a duplicate of sleep_score. Observation across
#                          6 reference nights (Jun 10 2026): field_16 tracks
#                          field_8 (Stress sub-score) more closely than the
#                          overall score —
#                            May 28: f8=95 / f16=96 (Δ +1)
#                            May 29: f8=74 / f16=82 (Δ +8; long sleep bonus?)
#                            Mar 17: f8=94 / f16=84 (Δ -10; short sleep)
#                            Sep 8:  f8=98 / f16=90 (Δ -8; lots of awake)
#                            Jun 2:  f8=46 / f16=43 (Δ -3)
#                          Looks like Stress sub-score adjusted by duration
#                          /awake. No clean formula locks across all 6
#                          nights — left documented, not surfaced.
#   field_9              = sleep_start_time (FIT epoch sec)
#                          May 28: 01:14 IST ✓, May 30: 02:11 IST ✓
#   field_11             = sleep_end_time
#                          May 28: 09:30 IST ✓, May 30: 07:16 IST ✓
#   field_24             = awake_minutes (May 28: 4 ✓, May 30: 8 ✓, Jun 2: 10 ✓)
#                          field_17 also = 4 on May 28 (coincidence) but
#                          diverged on May 30 (3 vs actual 8) — NOT awake.
# RETRACTED in this PR:
#   field_18 was claimed = sleep_avg_respiration (May 28 was 13 brpm, both
#   field and Connect agreed). Jun 2 disproved it — Andy's Connect breath
#   rate was 12, but field_18 = 70. May 30 was 49. The 13/49/70 spread
#   tracks INVERSELY with sleep quality (96/65/58) — likely sleep onset
#   latency or pre-sleep disturbance, not respiration. Not surfaced.
#
# field_18 = sleep_stress_above_resting_pct (best-guess from Jun 10 2026
# research — Garmin doesn't publish this metric; no community FIT
# reverse-engineering project documents msg 384). Across 6 reference
# nights field_18 cleanly fits "percentage of overnight stress samples
# at >25 on Garmin's 0-100 stress scale" (i.e. fraction of the night
# the body was NOT in fully resting state):
#   May 28 score=96 stress_avg=6.83 → field_18=13 (mostly resting)
#   May 29 score=82 stress_avg=9.53 → field_18=38 (moderate)
#   May 30 score=65 stress_avg=15.06 → field_18=49 (~half above resting)
#   Mar 17 score=54 stress_avg=4.81 → field_18=32 (short fragmented sleep)
#   Sep 8 score=37 stress_avg=3.40 → field_18=51 (driven by 72 min awake
#                                                — high stress while awake)
#   Jun 2 score=58 stress_avg=25.78 → field_18=70 (most samples elevated)
# Why this matches better than "100 - body_battery_overnight_delta":
# 3 of 5 BB-delta nights matched within 4 (May 29/30/Jun 2), but May 28
# (BB +75 / field_18=13) and Mar 17 (BB +40 / field_18=32) broke it.
# The "% above resting" framing accommodates Sep 8 (low avg stress but
# fragmented sleep with high-stress awake periods) which any pure
# stress-avg or BB-only formula can't explain. Garmin's published stress
# bands (0-25 resting, 26-50 low, 51-75 medium, 76-100 high) are sampled
# every ~3 min from HRV — the count of non-resting samples ÷ total
# samples × 100 is the candidate. Not surfaced as a chart yet — flagged
# best-guess until either a Connect-API field confirms or the formula
# gets disproven on a new reference night.
#
# Confirmed in PR #489 (Andy's Jun 9 Connect data):
#   field_7              = hrv_overnight_avg_ms × 65536
#                          May 28: 3543590 / 65536 = 54.07 ms (Connect: 54) ✓
#                          May 30: 3440511 / 65536 = 52.50 ms (Connect: 52) ✓
#                          Jun  2: 2558531 / 65536 = 39.04 ms (Connect: 39) ✓
#   Duplicate of `_HRV_STATUS.fit` `[370] field_1` — not surfaced from here,
#   parser stays single-source on the HRV file. But it locks the 16.16
#   fixed-point encoding for this message family, so other unmapped fields
#   probably use the same /65536 scale.
#
# Retracted in PR #489 — Deep / Light / REM split was NOT in field_5/6/7:
#   The Jun 9 ground-truth data from Connect (May 30: D=70 L=180 R=47;
#   Jun 2: D=75 L=170 R=50) ruled out every scalar+permutation candidate.
#   Combined with the f7=HRV confirmation, f5/f6 are also not stage minutes —
#   they're some other per-night metric we haven't named yet. After /65536:
#   f5 = 357.25 / 109.33 / 149.50 min; f6 = 174.33 / 544.92 / 558.34 min.
#   The stage split lives in some other field position of `[384]` —
#   field_3, _8, _10, _12, _13, _14, _15 are unprobed. `_dump_fit` now
#   surfaces every field plus the `_sleep_stage_decode_candidates` block,
#   so the next pass can grep the dump for the known stage minute values
#   (70 / 180 / 47 on May 30) across every field.
_METRICS_SLEEP_SUMMARY_MSG = 384

# Sleep-stage decode candidates for `[384] field_5/6/7`. None of these is
# verified — they're surfaced for fast eyeball comparison against Garmin
# Connect's Deep/Light/REM minutes once the next reference day lands.
# `value_fn` takes the raw uint and returns the candidate in minutes.
_SLEEP_STAGE_DECODE_CANDIDATES = (
    ('raw_seconds_to_min',   'raw value / 60 (treat as seconds)',
     lambda v: v / 60.0),
    ('ms_to_min',            'raw value / 60000 (treat as milliseconds)',
     lambda v: v / 60000.0),
    ('fixed_point_min',      'raw value / 65536 (16.16 fixed-point minutes)',
     lambda v: v / 65536.0),
    ('fixed_point_sec',      'raw value / 65536 / 60 (16.16 fixed-point seconds)',
     lambda v: v / 65536.0 / 60.0),
    ('scale_1024_sec',       'raw value / 1024 / 60 (scaled seconds to minutes)',
     lambda v: v / 1024.0 / 60.0),
    ('scale_16384_sec',      'raw value / 16384 / 60 (scaled seconds to minutes)',
     lambda v: v / 16384.0 / 60.0),
    ('upper16_min',          'upper 16 bits as minutes',
     lambda v: float((v >> 16) & 0xFFFF)),
    ('upper16_sec_to_min',   'upper 16 bits as seconds, expressed in minutes',
     lambda v: ((v >> 16) & 0xFFFF) / 60.0),
)


def _sleep_stage_decode_candidates(f5, f6, f7) -> list:
    """Emit candidate Deep/Light/REM minute decodings of `[384] field_5/6/7`.

    Returns a list of dicts, one per decoder in `_SLEEP_STAGE_DECODE_CANDIDATES`:
      `{decoder, description, f5_min, f6_min, f7_min, sum_min}`.

    Skips decoders that error on the input. Used by the FIT inspector to
    surface the candidates next to the raw values — paste Connect's stage
    minutes alongside to find the decoder (if any) that matches.
    """
    out = []
    raws = (f5, f6, f7)
    if any(r is None for r in raws):
        return out
    try:
        raws = tuple(int(r) for r in raws)
    except (TypeError, ValueError):
        return out
    for name, desc, fn in _SLEEP_STAGE_DECODE_CANDIDATES:
        try:
            vals = tuple(fn(r) for r in raws)
        except (ZeroDivisionError, ValueError, OverflowError):
            continue
        out.append({
            'decoder': name,
            'description': desc,
            'f5_min': round(vals[0], 2),
            'f6_min': round(vals[1], 2),
            'f7_min': round(vals[2], 2),
            'sum_min': round(sum(vals), 2),
        })
    return out


# `[346]` sub-score slot positions whose Stress / Light / REM / Awake
# alignment isn't locked yet. field_4 (Duration) and field_9 (Deep min)
# are already pinned to their own keys; field_14/_15 carry the stress
# sample count + sum — so the four remaining contributor sub-scores
# live in these positions in some unknown order.
_SLEEP_SUB_SCORE_SLOTS = ('field_5', 'field_7', 'field_8', 'field_10')


def _sleep_sub_score_slot_candidates(f5, f7, f8, f10) -> list:
    """Per-night diagnostic for `[346] field_5 / 7 / 8 / 10` — the four
    sub-score positions for Stress / Light / REM / Awake contributors.

    Locks (Jun 10 2026 — disambiguated across 5 reference nights including
    Sep 8 2025's 37-score night with 72 min awake on 306 min sleep):
      • `field_5` = **Light sub-score** — penalized when Light fraction is
        high (May 28's 8h12m great sleep had Light ~68% → field_5 = 83
        Excellent-low; Jun 2's 5h05m short sleep with Light 55.7% in
        ideal range → field_5 = 92 Excellent).
      • `field_7` = **REM sub-score** — penalized when REM fraction is
        low (May 28's REM ~20% ideal → field_7 = 95 Excellent; Jun 2's
        REM 16.4% slightly low → field_7 = 73 Good).
      • `field_8` = **Stress sub-score** — most reactive, 46 Fair on Jun 2
        (Connect Stress avg 27 = Fair band), 98 Excellent on Sep 8 even
        though sleep was atrocious (stress avg 3.40 = low → stress
        sub-score stays high; bad sleep was awake-driven). Triple-
        confirmed across May 28 / Jun 2 / Sep 8.
      • `field_10` = **Awake sub-score** — 100 Excellent on May 28 (4 min
        awake), 0 Poor (rank 1) on Sep 8 (72 min awake = 23.5%). Inverse-
        tracks awake-time fraction across nights.

    All four contributor positions now locked: Light=5, REM=7, Stress=8,
    Awake=10.

    Earlier wrong-lock retraction: Jun 2 alone suggested `field_5 =
    Awake` because field_5 = 92 with Awake = 10 min looked plausible —
    but Sep 8 surfaced `field_5 = 61` despite 72 min awake, while
    `field_10 = 0` matched perfectly. The Light vs REM disambiguation
    came from May 28 + Jun 2 stage-ratio analysis.

    Returns one dict per slot with the raw value, a 1-to-4 rank (1 = the
    lowest of the four that night, 4 = highest), and the qualitative band
    under Garmin's standard 0-100 quartile bands (Poor/Fair/Good/Excellent
    at 25/50/75 cutoffs).

    The standard quartiles applied fine once Andy's Jun 2 brought a real
    "Fair" reading (field_8 = 46). On nights where all sub-scores land in
    Excellent, rank-relative comparison stays the useful signal.

    Skips slots whose raw value is None or non-integer. Ranks tie-break
    by slot order (earliest wins) so output stays stable across runs.
    """
    raws = []
    for slot, raw in (
        ('field_5', f5), ('field_7', f7),
        ('field_8', f8), ('field_10', f10),
    ):
        if raw is None:
            continue
        try:
            raws.append((slot, int(raw)))
        except (TypeError, ValueError):
            continue
    if not raws:
        return []

    ordered = sorted(enumerate(raws), key=lambda ix: (ix[1][1], ix[0]))
    rank_by_slot = {slot: i + 1 for i, (_, (slot, _)) in enumerate(ordered)}

    def _band(v: int) -> str:
        if v <= 25:
            return 'Poor'
        if v <= 50:
            return 'Fair'
        if v <= 75:
            return 'Good'
        return 'Excellent'

    return [
        {
            'slot': slot,
            'raw': raw,
            'rank': rank_by_slot[slot],
            'band_garmin_std': _band(raw),
        }
        for slot, raw in raws
    ]


def find_value_match_fields(
    dump,
    targets: list,
    *,
    scales: tuple = (1.0, 0.1, 10.0, 0.01, 100.0),
    message_ids: tuple | None = None,
    tolerance: float = 0.5,
) -> list:
    """Single-file scan that finds GenericMessage fields whose value
    matches *any* of the supplied target values (under one of the
    candidate scales).

    Designed for "Connect shows these reference values for last night —
    which raw fields encode them?" use cases. Issue #283 motivating case:
    Connect-smoothed Light / REM / Awake / Deep minutes (May 30: 180 /
    47 / 8 / 70); pass those as targets and the scanner returns every
    field that matches, ordered by message_id / field_id.

    Inputs:
      dump        — a `_dump_fit()` result OR just its `generic_samples`
                    sub-dict — both shapes work.
      targets     — list of values to match (e.g. [180, 47, 8, 70]).
      scales      — multipliers to try (default covers Garmin's common
                    ×10 / ÷10 fixed-point encodings).
      message_ids — restrict the scan to these gids. None scans every
                    gid present in the dump.
      tolerance   — allowed |scaled − target| (covers FIT round-trip
                    drift).

    Returns one entry per (gid, field_id, target, scale) match:
      {message_id, field_id, target, scale, raw_value, scaled_value}.

    Unlike `find_constant_value_fields` (cross-file, single target),
    this scans a single file and matches against multiple targets —
    useful when you have a per-night ground truth but don't have
    multiple nights to cross-correlate."""
    if not targets:
        return []
    samples = dump.get('generic_samples') if isinstance(dump, dict) else None
    if samples is None:
        samples = dump if isinstance(dump, dict) else {}
    matches = []
    for gid_str, instances in sorted(samples.items()):
        try:
            if message_ids is not None and int(gid_str) not in message_ids:
                continue
        except (TypeError, ValueError):
            continue
        seen_fields: set = set()
        for sample in instances:
            if not isinstance(sample, dict):
                continue
            for field_key, raw in sample.items():
                if not field_key.startswith('field_'):
                    continue
                key = (gid_str, field_key)
                if key in seen_fields:
                    continue
                try:
                    val = float(raw)
                except (TypeError, ValueError):
                    continue
                seen_fields.add(key)
                for target in targets:
                    for scale in scales:
                        scaled = val * scale
                        if abs(scaled - target) <= tolerance:
                            matches.append({
                                'message_id': gid_str,
                                'field_id': field_key,
                                'target': target,
                                'scale': scale,
                                'raw_value': val,
                                'scaled_value': round(scaled, 3),
                            })
                            break  # one scale per (field, target)
    return matches


def _sleep_counter_derivation_candidates(
    stage_events: list,
    raw_counters: dict,
) -> dict:
    """Per-night diagnostic that surfaces derivations from `[275]` stage
    transitions for comparison against the `[346] field_12 / field_13`
    mystery counter values (issue #283).

    Pinned facts on Andy's Fenix 8:
      • May 28: field_12=2, field_13=7
      • May 30: field_12=14, field_13=0

    The values are obviously sleep-derived counters but the exact
    derivation isn't locked. This helper computes the plausible
    candidates from the `[275]` event list — stage-period counts,
    transition counts, REM-onset counts — and surfaces them next to
    the raw `[346]` values. Operator compares: any derivation that hits
    both raw counters on ≥2 nights is the lock candidate.

    Stage codes (from `_SLEEP_DATA_STAGE_MSG` docs): 1=Unmeasurable,
    2=Light, 3=Deep, 4=REM. `[275]` instances mark the entry into a
    stage; a contiguous run of identical codes (rare — each transition
    emits a new event) is one stage period.

    Inputs:
      stage_events — `[(ts, code), ...]` from `_walk_sleep_stage_events`.
      raw_counters — `{field_12: str_value, field_13: str_value}` from
                     the `[346]` GenericMessage. Pass empty dict if the
                     file has no `[346]`.

    Returns:
      {
        'raw': {'field_12': int|None, 'field_13': int|None},
        'derived': {
          'total_events':         len(stage_events),
          'transition_count':     len(stage_events) - 1,
          'light_period_count':   contiguous runs of code 2,
          'deep_period_count':    contiguous runs of code 3,
          'rem_period_count':     contiguous runs of code 4,
          'awake_period_count':   contiguous runs of code 1,
        },
        'matches_field_12': [list of derivation keys equal to field_12],
        'matches_field_13': [list of derivation keys equal to field_13],
      }
    Returns {} when there are no `[275]` events at all (nothing to
    derive from)."""
    if not stage_events:
        return {}

    # Count contiguous runs of each code — back-to-back events with the
    # same code count once. (Adjacent same-code events are rare but
    # possible if the watch re-emits the same stage.)
    period_counts = {1: 0, 2: 0, 3: 0, 4: 0}
    prev_code = None
    for _ts, code in stage_events:
        if code != prev_code:
            if code in period_counts:
                period_counts[code] += 1
            prev_code = code

    derived = {
        'total_events': len(stage_events),
        'transition_count': max(len(stage_events) - 1, 0),
        'awake_period_count': period_counts[1],
        'light_period_count': period_counts[2],
        'deep_period_count': period_counts[3],
        'rem_period_count': period_counts[4],
    }

    def _as_int(v):
        try:
            return int(float(v))
        except (TypeError, ValueError):
            return None

    raw = {
        'field_12': _as_int(raw_counters.get('field_12')),
        'field_13': _as_int(raw_counters.get('field_13')),
    }

    matches_12 = [k for k, v in derived.items() if raw['field_12'] is not None and v == raw['field_12']]
    matches_13 = [k for k, v in derived.items() if raw['field_13'] is not None and v == raw['field_13']]

    return {
        'raw': raw,
        'derived': derived,
        'matches_field_12': matches_12,
        'matches_field_13': matches_13,
    }


def find_constant_value_fields(
    nights: list,
    target: float,
    *,
    scales: tuple = (1.0, 0.1, 10.0, 0.01, 100.0),
    message_ids: tuple | None = None,
    tolerance: float = 0.5,
) -> list:
    """Cross-file scan that finds GenericMessage fields whose value equals
    `target` (under one of the candidate `scales`) on every night.

    Designed for "this metric is constant on Andy's device — which raw
    field encodes it?" use cases. The motivating case (issue #283) is
    VO2max running ≈ 48: scan unmapped `_METRICS.fit` fields across 2+
    nights for a field that lands on 48 under some scale on every night.

    Inputs:
      nights      — list of `_dump_fit()['generic_samples']`-shaped dicts.
                    Each element: `{gid_str: [field_dict_per_instance,…]}`.
      target      — the expected constant (e.g. 48 for VO2max running).
      scales      — multipliers to try (default covers raw, /10, ×10, /100,
                    ×100 — covers common FIT fixed-point encodings).
      message_ids — restrict the scan to these gids. Pass e.g.
                    `(281, 330, 378, 384)` for `_METRICS.fit` messages
                    only. None scans every gid present.
      tolerance   — allowed |scaled − target| (covers small FIT round-trip
                    drift; 0.5 allows ±0.5 ml/kg/min for VO2max).

    Returns one entry per matching (gid, field, scale): {message_id,
    field_id, scale, raw_values_per_night, scaled_values_per_night}. Each
    entry carries the per-night raw values so the operator can sanity-
    check before locking. Fields missing from any night are dropped — a
    constant has to be continuously present to be a constant.

    Requires at least 2 nights (one night admits trivially many fits)."""
    if len(nights) < 2:
        return []

    # Take the first instance's value per (gid, field) per night — fields
    # with multiple instances at different values aren't day-constants by
    # construction. First-instance keeps the rule simple and deterministic.
    from collections import defaultdict
    per_field_values: dict = defaultdict(list)
    for night in nights:
        seen: set = set()
        for gid_str, samples in night.items():
            try:
                if message_ids is not None and int(gid_str) not in message_ids:
                    continue
            except (TypeError, ValueError):
                continue
            for sample in samples:
                for field_key, raw in sample.items():
                    if not field_key.startswith('field_'):
                        continue
                    key = (gid_str, field_key)
                    if key in seen:
                        continue
                    try:
                        val = float(raw)
                    except (TypeError, ValueError):
                        continue
                    per_field_values[key].append(val)
                    seen.add(key)

    matches = []
    for (gid, field), values in sorted(per_field_values.items()):
        if len(values) != len(nights):
            continue
        for scale in scales:
            scaled = [v * scale for v in values]
            if all(abs(s - target) <= tolerance for s in scaled):
                matches.append({
                    'message_id': gid,
                    'field_id': field,
                    'scale': scale,
                    'raw_values': values,
                    'scaled_values': [round(s, 3) for s in scaled],
                })
                break  # one scale wins per field
    return matches


def sleep_stress_avg(stress_sum: int, sleep_min: int) -> float | None:
    """Garmin Connect's "Stress avg" for a night's sleep, computed from
    `[346] field_15` (sum of all stress samples taken during sleep) and
    the total sleep duration in minutes.

    Garmin samples stress every ~3 minutes during sleep, so the sample
    count is `sleep_min // 3`. The average is the sum divided by the
    sample count. Verified against May 30: 1491 × 3 / 297 = 15.06 ↔
    Connect "Stress 15 avg" ✓.

    `field_14` carries the same sample count but capped at 100 — using
    the un-capped derived count keeps the average accurate on nights
    with sleep duration > 300 min.

    Returns None when sleep_min is missing or <= 0 (the caller can't
    derive a meaningful average without the duration)."""
    if sleep_min is None or sleep_min <= 0 or stress_sum is None:
        return None
    samples = sleep_min // 3
    if samples <= 0:
        return None
    return round(stress_sum / samples, 1)


def _walk_sleep_stage_events(fit) -> list:
    """Collect `[275]` sleep-stage transition events from a parsed FIT file
    and return `[(timestamp_fit_sec, code), ...]` sorted by timestamp.

    Each `[275]` instance marks the entry into a sleep stage (Deep / Light /
    REM / Awake / Unmeasurable); the stage's duration is the gap to the
    next instance's timestamp. See `_SLEEP_DATA_STAGE_MSG`."""
    events = []
    for record in fit.records:
        msg = record.message
        if type(msg).__name__ != 'GenericMessage':
            continue
        if getattr(msg, 'global_id', None) != _SLEEP_DATA_STAGE_MSG:
            continue
        fields = _generic_field_map(msg)
        code = fields.get(0)
        ts = fields.get(253) or getattr(msg, 'timestamp', None)
        if code is None or ts is None:
            continue
        try:
            events.append((int(ts), int(code)))
        except (TypeError, ValueError):
            continue
    events.sort()
    return events


def _stage_minutes_from_events(events: list, *, sleep_end_ts: int = None) -> dict:
    """Tally `[275]` event list into `{code: minutes_in_that_code}`.

    Each adjacent pair `(events[i], events[i+1])` contributes
    `events[i+1].ts - events[i].ts` seconds to `events[i].code`. The final
    event's duration uses `sleep_end_ts` — when caller can't supply it
    (the standalone `_SLEEP_DATA.fit` parse path), the last event is
    skipped so the tallies still recover every stage code that appears
    mid-night. Sanity-clips per-segment durations to `< 24 h`.
    """
    if not events:
        return {}
    durations_s = {}
    for i, (ts, code) in enumerate(events):
        if i + 1 < len(events):
            next_ts = events[i + 1][0]
        elif sleep_end_ts is not None:
            next_ts = int(sleep_end_ts)
        else:
            continue
        delta = next_ts - ts
        if 0 < delta < 86400:
            durations_s[code] = durations_s.get(code, 0) + delta
    return {code: round(s / 60) for code, s in durations_s.items()}


def find_sleep_stage_decoder(reference_set, *, tolerance_min: float = 2.0) -> list:
    """Brute-force find a (decoder, field-to-stage permutation) that maps
    `[384] field_5/6/7` to (Deep, Light, REM) minutes consistently across a
    reference set of nights.

    `reference_set` is an iterable of `(f5, f6, f7, deep_min, light_min,
    rem_min)` tuples — at least 2 nights with materially different stage
    distributions are needed for the result to be meaningful.

    Returns a list of `{decoder, description, permutation, max_error_min}`
    matches, sorted by `max_error_min` ascending. An empty list means no
    candidate decoder fits within `tolerance_min` minutes per stage per
    night — the encoding likely uses a non-scalar transform (bit-packing,
    variable-resolution, …) that this helper doesn't model.
    """
    from itertools import permutations

    rows = list(reference_set)
    if len(rows) < 2:
        return []

    matches = []
    stage_keys = ('deep', 'light', 'rem')
    for name, desc, fn in _SLEEP_STAGE_DECODE_CANDIDATES:
        # Decode each night's (f5, f6, f7) once.
        try:
            decoded = [tuple(fn(int(r[i])) for i in (0, 1, 2)) for r in rows]
        except (ZeroDivisionError, ValueError, OverflowError, TypeError):
            continue
        # Try every assignment of (f5, f6, f7) -> (deep, light, rem).
        for perm in permutations((0, 1, 2)):
            max_err = 0.0
            for r, dec in zip(rows, decoded):
                actual = (r[3], r[4], r[5])
                for stage_idx, slot in enumerate(perm):
                    err = abs(dec[slot] - actual[stage_idx])
                    if err > max_err:
                        max_err = err
            if max_err <= tolerance_min:
                matches.append({
                    'decoder': name,
                    'description': desc,
                    'permutation': dict(zip(
                        (f'field_{5 + p}' for p in perm), stage_keys,
                    )),
                    'max_error_min': round(max_err, 2),
                })
    matches.sort(key=lambda m: m['max_error_min'])
    return matches

# `_METRICS.fit` `GenericMessage[378]` — daily training-state row.
# Verified across May 27 + 28 + 30:
#   field_3 = acute_training_load
#             May 28: 98, May 30: 59 (Andy's interpretation — values in
#             range and tracking with recent workout intensity).
#   field_4 = 219 (static — profile/zone threshold, not a daily metric)
# Other fields (0, 1, 2, 5) vary day-to-day but their semantics aren't
# locked yet — left out of the returned dict.
_METRICS_TRAINING_STATE_MSG = 378

# `_METRICS.fit` `GenericMessage[281]` — daily wellness summary.
# Verified across May 27 + 28 + 30:
#   field_6 = heat_acclimation_pct
#             May 27/28: 32%, May 30: 22% (Andy's reference — decreasing
#             after moving from US to Ireland tracks loss of acclimation).
# field_9 also varies (38/32/26) but isn't yet identified.
_METRICS_WELLNESS_SUMMARY_MSG = 281

# `_SLEEP_DATA.fit` `GenericMessage[346]` — sleep contributors.
# Verified:
#   field_6 = sleep_score (=96/65 ↔ Garmin Connect)
#   field_4 = duration_sub_score
#             May 28 (8h 12m): 100 ("Excellent")
#             May 30 (4h 57m): 51  ("Fair")
#   field_9 = deep_sleep_min — LOCKED in PR #489 across 2 days:
#             May 28 = 81 min (16.5% of 8h12m sleep — Excellent range)
#             May 30 = 70 min ↔ Connect "1h 10m" exactly ✓
#             (NOT a sub-score as previously assumed — value tracks
#             stage MINUTES, and on a Good Deep night the value lands
#             well below the 76-100 "Excellent" sub-score range.)
#   field_14 = sleep_stress_sample_count_capped100 — LOCKED PR #489:
#             Garmin samples stress every ~3 minutes during sleep, so
#             expected count = sleep_min // 3, capped at 100.
#             May 30: 297 // 3 = 99 (uncapped) ✓ exact
#             May 28: 492 // 3 = 164 → capped to 100 ✓ exact
#   field_15 = sleep_stress_sample_sum — LOCKED PR #489:
#             Sum of all 0-100 stress values taken during sleep.
#             Derived: avg_sleep_stress = field_15 × 3 / sleep_min.
#             May 30: 1491 × 3 / 297 = 15.06 ↔ Connect "Stress 15 avg" ✓
#             May 28: 1120 × 3 / 492 = 6.83 (very low stress, matches
#             the great-sleep night — direction ✓; Connect avg
#             unverified but plausible).
# The remaining positions in field_5/7/8/10 likely carry sub-scores
# for the other contributors but the slot-to-name mapping isn't locked
# — most values land in the Excellent band even on nights when Connect
# rates Light or REM lower, so the absolute quartile thresholds don't
# align. The inspector dumps an `_sleep_sub_score_slot_candidates`
# block per [346] sample carrying raw values + intra-night rank +
# qualitative band so the operator can correlate the rank-1 slot
# against Connect's worst-rated contributor across nights; once a
# stable correlation appears the slot ↔ name mapping locks.
_SLEEP_DATA_SCORE_MSG = 346

# `_SLEEP_DATA.fit` `GenericMessage[382]` — sleep event counts.
# Verified across May 28 / May 30 / Jun 2:
#   field_1 = restless_moments_count (May 28: 28 ✓ matches Garmin Connect
#             "28 Restless Moments"; May 30: 15; Jun 2: 32)
#   field_0 = sleep_start_seconds_since_local_midnight — LOCKED PR #489
#             across 2 days:
#             May 28: 4500 / 60 = 75 min = 01:15 AM ↔ Connect 01:14 ✓
#             May 30: 7860 / 60 = 131 min = 02:11 AM ↔ Connect 02:11 ✓
#   field_2 = wake_event_count — LOCKED PR #489 across 2 days:
#             May 28: 4 events / 4 min awake = 1 min avg per event
#             May 30: 9 events / 8 min awake = <1 min avg per event
#             (Distinct from `awake_min` in `[384] field_24`, which is
#             the total awake duration.)
_SLEEP_DATA_EVENTS_MSG = 382

# `_SLEEP_DATA.fit` `GenericMessage[275]` — per-stage sleep transitions.
# DISCOVERED + code-mapping LOCKED in PR #489 against May 30 (15 events,
# stage timing matches textbook patterns):
#   field_0   = stage code:
#               1 = unmeasurable / restless (Connect doesn't surface this
#                   directly — see "interpolation" note below)
#               2 = LIGHT (occupies gaps between Deep / REM)
#               3 = DEEP (all 3 May-30 occurrences in first half:
#                   t+38 / t+88 / t+152 min — textbook Deep distribution)
#               4 = REM (first at t+126 min = classic first REM cycle;
#                   second at t+277 min, long late-night REM — textbook)
#   field_253 = stage_start_time (FIT epoch sec)
# Stage duration = (next instance's ts) - (this instance's ts). The final
# instance lands exactly at `sleep_end_ts` (= `[384] field_11`) and acts
# as the END marker — it contributes 0 to its own code's tally.
#
# Interpolation gap — Connect's reported D/L/R/A minutes are HIGHER than
# the raw [275] code 2/3/4 tally:
#   May 30 raw tally:   {1: 74, 2: 125, 3: 57, 4: 38} = 294 min
#   May 30 in-bed:      305 min (sleep_end - sleep_start)
#   May 30 unmeasured:  74 (code 1) + 11 (pre-sleep gap) = 85 min
#   May 30 Connect:     Deep=70 / Light=180 / REM=47 / Awake=8 = 305 min
#   Connect needs:      +13 Deep, +55 Light, +9 REM, +8 Awake = 85 min ✓
# Garmin's algorithm smooths the unmeasurable 85 min into the 4 stages.
# We don't reverse-engineer the smoothing — for Deep we use the Connect-
# smoothed value directly from `[346] field_9` (locked); for Light / REM
# / Awake the smoothed values aren't yet found in any decoded field.
_SLEEP_DATA_STAGE_MSG = 275

# Most GenericMessage types repeat with redundant payloads — we cap at 5
# distinct samples per gid in `_dump_fit` to keep dumps small. Exception:
# messages where each instance carries unique event data (e.g. [275]
# sleep stage transitions — capping there would lose mid-night stages).
_DUMP_KEEP_ALL_INSTANCES = frozenset({_SLEEP_DATA_STAGE_MSG})


# `_HRV_STATUS.fit` `GenericMessage[370]` — nightly HRV summary.
# Verified across May 28 + 30:
#   field_0 = 7d_avg_hrv * 128 (65535 sentinel = "No Status" before
#             the 19-day baseline window is filled)
#   field_1 = overnight_avg_hrv_ms * 128
#             May 28: 6912/128 = 54.0 ms ✓
#             May 30: 6656/128 = 52.0 ms ✓
#   field_2 = highest_5min_avg_hrv_ms * 128
#             May 28: 9856/128 = 77.0 ms
#             May 30: 10112/128 = 79.0 ms ✓ (matches Garmin Connect "79 ms")
_HRV_STATUS_SUMMARY_MSG = 370

# `_HRV_STATUS.fit` `GenericMessage[371]` — per-period HRV samples through
# the night. field_0 = sample * 128 (range 65-90 ms observed, plausible).
# 99 instances in the May 28 file → ~5-minute cadence over an 8h sleep.
_HRV_STATUS_SAMPLE_MSG = 371

# Garmin `FileIdMessage.type` enum identifies the file type. Confirmed values
# from the May 28 dumps:
#   32 = wellness (per-second monitoring)
#   44 = metrics  (daily derived)
#   49 = sleep_data
#   68 = hrv_status
_FIT_FILE_TYPE_WELLNESS   = 32
_FIT_FILE_TYPE_METRICS    = 44
_FIT_FILE_TYPE_SLEEP_DATA = 49
_FIT_FILE_TYPE_HRV_STATUS = 68


def _fit_seconds_to_unix_ms(raw_ts) -> int:
    """Treat a FIT timestamp value as **FIT epoch seconds** and return Unix ms.

    Used for the GenericMessage timestamp fields in metrics/sleep/hrv files,
    which arrive as FIT-epoch seconds (~1.1 billion range). `_fit_ts_to_unix_ms`
    above is ambiguous between Unix-seconds / FIT-seconds / Unix-ms — these
    metric files always use FIT seconds, so we don't want the auto-detect.
    """
    if raw_ts is None:
        return 0
    try:
        ts = int(raw_ts)
        if ts <= 0:
            return 0
        return (ts + _FIT_EPOCH_OFFSET_S) * 1000
    except (TypeError, ValueError):
        return 0


def _fit_seconds_to_date(raw_ts) -> str:
    """FIT epoch seconds → YYYY-MM-DD UTC. Empty on bad input."""
    ms = _fit_seconds_to_unix_ms(raw_ts)
    if not ms:
        return ''
    try:
        return datetime.fromtimestamp(ms / 1000.0, tz=timezone.utc).strftime('%Y-%m-%d')
    except Exception:
        return ''


def _generic_field_map(msg) -> dict:
    """Read a GenericMessage as {field_id: value}. Skip None values."""
    out = {}
    for field in getattr(msg, 'fields', []):
        try:
            fid = getattr(field, 'field_id', None)
            if fid is None:
                continue
            v = field.get_value(0)
            if v is not None:
                out[fid] = v
        except Exception:
            pass
    return out


def _fit_file_type(fit) -> int | None:
    """Read the FileIdMessage.type enum (32=wellness, 44=metrics, …)."""
    for record in fit.records:
        msg = record.message
        if type(msg).__name__ == 'FileIdMessage':
            t = getattr(msg, 'type', None)
            try:
                return int(t) if t is not None else None
            except (TypeError, ValueError):
                return None
    return None


def fit_file_meta(fit_bytes: bytes) -> tuple:
    """Return `(kind, time_created_ms)` from the file's FileIdMessage in a
    single parse pass. `kind` is one of 'wellness' / 'metrics' / 'sleep_data'
    / 'hrv_status' / 'unknown'. `time_created_ms` is Unix ms (0 if absent).

    The bulk importer reads both up front so it can sort uploads by
    chronological order before UPSERTing — without that, three `_METRICS.fit`
    files for the same day landing in arbitrary zip order can have the
    earliest ATL/RMR clobber the latest.
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
    type_code = None
    time_ms = 0
    for record in fit.records:
        msg = record.message
        if type(msg).__name__ == 'FileIdMessage':
            t = getattr(msg, 'type', None)
            try:
                type_code = int(t) if t is not None else None
            except (TypeError, ValueError):
                pass
            tc = getattr(msg, 'time_created', None)
            if tc is not None:
                try:
                    ms = int(tc)
                    if ms < 1_000_000_000_000:
                        ms *= 1000
                    time_ms = ms
                except (TypeError, ValueError):
                    pass
            break  # FileIdMessage is the first record by FIT-spec
    kind = {
        _FIT_FILE_TYPE_WELLNESS:   'wellness',
        _FIT_FILE_TYPE_METRICS:    'metrics',
        _FIT_FILE_TYPE_SLEEP_DATA: 'sleep_data',
        _FIT_FILE_TYPE_HRV_STATUS: 'hrv_status',
    }.get(type_code, 'unknown')
    return (kind, time_ms)


def detect_fit_type(fit_bytes: bytes) -> str:
    """Backwards-compat wrapper. Prefer `fit_file_meta` so the importer can
    sort by `time_created_ms` without a second parse."""
    return fit_file_meta(fit_bytes)[0]


def parse_metrics_fit(fit_bytes: bytes) -> dict:
    """Parse a Garmin `_METRICS.fit` file (FileIdMessage.type = 44).

    Returns a dict of daily-derived metrics keyed for UPSERT into
    `garmin_daily_metrics`. `date` is the UTC date of the record timestamp
    (Garmin attributes the night to the wake day). Returns `{}` if the file
    carries no recognized metric.

    Known limitation: Deep / Light / REM minute split isn't returned — see
    `_METRICS_SLEEP_SUMMARY_MSG` for the decode TODO.
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

    out: dict = {}
    for record in fit.records:
        msg = record.message
        if type(msg).__name__ != 'GenericMessage':
            continue
        gid = getattr(msg, 'global_id', None)
        fields = _generic_field_map(msg)
        if not fields:
            continue

        if gid == _METRICS_SLEEP_SUMMARY_MSG:
            # Rich sleep summary — wins over the simpler [330] row if both
            # appear in the same file, because it carries timing + awake +
            # respiration in addition to the score.
            #
            # field_2 is the only reliable sleep_score slot (field_16 was a
            # match on May 28 but diverged from the overall score on May 30).
            if fields.get(2) is not None:
                out['sleep_score'] = int(fields[2])
            start_ts = _fit_seconds_to_unix_ms(fields.get(9))
            end_ts   = _fit_seconds_to_unix_ms(fields.get(11))
            if start_ts:
                out['sleep_start_ms'] = start_ts
            if end_ts:
                out['sleep_end_ms'] = end_ts
            # Awake minutes is field_24 only — field_17 looked like a
            # duplicate on May 28 (both = 4) but diverged on May 30 (3 vs
            # actual 8), so it's some other metric.
            if fields.get(24) is not None:
                out['sleep_awake_min'] = int(fields[24])
            # field_18 = sleep_stress_above_resting_pct (best-guess;
            # see the comment block above `_METRICS_SLEEP_SUMMARY_MSG`).
            # Surfaced as a "sleep stress fraction" chart so the operator
            # can spot nights where most of the overnight stress samples
            # crossed the resting threshold even when the average stress
            # stayed low. Not Connect-visible directly.
            if fields.get(18) is not None:
                out['sleep_stress_above_resting_pct'] = int(fields[18])
            # Date = the wake day (sleep is attributed to the morning).
            if end_ts:
                out['date'] = datetime.fromtimestamp(
                    end_ts / 1000.0, tz=timezone.utc
                ).strftime('%Y-%m-%d')

        elif gid == _METRICS_SLEEP_SCORE_SIMPLE_MSG:
            # Only fill score if the rich [384] row didn't already provide it.
            if 'sleep_score' not in out and fields.get(2) is not None:
                out['sleep_score'] = int(fields[2])
            if 'date' not in out:
                # field_253 (record timestamp) → date
                ts = _fit_seconds_to_unix_ms(getattr(msg, 'timestamp', None)) or \
                     _fit_seconds_to_unix_ms(fields.get(3))
                if ts:
                    out['date'] = datetime.fromtimestamp(
                        ts / 1000.0, tz=timezone.utc
                    ).strftime('%Y-%m-%d')

        elif gid == _METRICS_TRAINING_STATE_MSG:
            # Acute training load (Andy's interpretation; values track recent
            # workout intensity day-to-day).
            if fields.get(3) is not None:
                out['acute_training_load'] = int(fields[3])

        elif gid == _METRICS_WELLNESS_SUMMARY_MSG:
            # Heat acclimation percent (verified across May 27/28/30).
            if fields.get(6) is not None:
                out['heat_acclimation_pct'] = int(fields[6])

    # Fall back to the file-level timestamp if no GenericMessage gave us a date.
    if 'date' not in out:
        for record in fit.records:
            msg = record.message
            if type(msg).__name__ == 'FileIdMessage':
                tc = getattr(msg, 'time_created', None)
                if tc is not None:
                    try:
                        ts_ms = int(tc)
                        if ts_ms < 1_000_000_000_000:
                            ts_ms *= 1000
                        out['date'] = datetime.fromtimestamp(
                            ts_ms / 1000.0, tz=timezone.utc
                        ).strftime('%Y-%m-%d')
                    except (TypeError, ValueError):
                        pass
                break

    return out if out.get('date') else {}


def parse_sleep_data_fit(fit_bytes: bytes) -> dict:
    """Parse a Garmin `_SLEEP_DATA.fit` file (FileIdMessage.type = 49).

    Returns the daily-derived sleep keys for UPSERT into
    `garmin_daily_metrics`: sleep_score, the 4 contributor sub-scores
    (Light/REM/Stress/Awake — all locked Jun 10 2026), Deep minutes,
    Stress sum/sample-count, restless moments.
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

    out: dict = {}
    for record in fit.records:
        msg = record.message
        if type(msg).__name__ != 'GenericMessage':
            continue
        gid = getattr(msg, 'global_id', None)
        if gid == _SLEEP_DATA_SCORE_MSG:
            fields = _generic_field_map(msg)
            if fields.get(6) is not None:
                out['sleep_score'] = int(fields[6])
            # Duration sub-score — verified across May 28 (100, "Excellent")
            # and May 30 (51, "Fair", short 4h 57m sleep). Named separately
            # because it's the only contributor slot whose position is
            # locked.
            if fields.get(4) is not None:
                out['sleep_duration_sub_score'] = int(fields[4])
            # Deep sleep minutes — LOCKED in PR #489 across 2 days:
            # May 28 = 81 min ✓ (Andy's verification), May 30 = 70 min ↔
            # Connect "1h 10m" exactly. NOT a sub-score (the values land
            # outside Garmin's 0-100 qualitative bands on most nights).
            # Keyed to match the DB column name (`sleep_deep_min`).
            if fields.get(9) is not None:
                out['sleep_deep_min'] = int(fields[9])
            # Stress sample count + sum during sleep — LOCKED in PR #489.
            # field_14 is the count of 0-100 stress readings taken during
            # the sleep period (every ~3 min, capped at 100). field_15 is
            # the SUM of those readings; dividing by the sample count
            # yields Garmin Connect's "Stress avg" for sleep.
            if fields.get(14) is not None:
                out['sleep_stress_sample_count_capped'] = int(fields[14])
            if fields.get(15) is not None:
                out['sleep_stress_sum'] = int(fields[15])
            # All four contributor positions LOCKED Jun 10 2026 across
            # 6 reference nights including Sep 8 2025 (37 score with 72 min
            # awake = the disambiguation night). See
            # `_sleep_sub_score_slot_candidates` docstring for the mapping
            # evidence per slot.
            for fid, name in (
                (5,  'sleep_light_sub_score'),
                (7,  'sleep_rem_sub_score'),
                (8,  'sleep_stress_sub_score'),
                (10, 'sleep_awake_sub_score'),
            ):
                v = fields.get(fid)
                if v is not None:
                    out[name] = int(v)
            # Legacy `sleep_contributors` ordered-list — kept for backwards
            # compat with `sleep_contributors_json` rows already in prod
            # (#283 Phase A). New consumers should read the named columns.
            contributors = []
            for fid in (5, 7, 8, 10):
                v = fields.get(fid)
                contributors.append(int(v) if v is not None else None)
            if any(c is not None for c in contributors):
                out['sleep_contributors'] = contributors
        elif gid == _SLEEP_DATA_EVENTS_MSG:
            fields = _generic_field_map(msg)
            if fields.get(1) is not None:
                out['restless_moments'] = int(fields[1])
            # Sleep start time as seconds since local midnight — LOCKED in
            # PR #489 against May 28 + May 30: 4500/7860 = 01:15/02:11.
            # Surfaced for cross-check; the canonical sleep_start_ts FIT-
            # epoch sec lives in `[384] field_9`.
            if fields.get(0) is not None:
                out['sleep_start_seconds_since_midnight'] = int(fields[0])
            # Wake event count — distinct from awake_min (total awake
            # duration in `[384] field_24`). LOCKED PR #489 against May
            # 28 (4 events / 4 min) + May 30 (9 events / 8 min).
            # Keyed `sleep_wake_count` to match the DB column.
            if fields.get(2) is not None:
                out['sleep_wake_count'] = int(fields[2])

    # Walk `[275]` stage transitions — each instance is a stage entry.
    # The importer cross-files `[384] field_11` for sleep_end_ts to compute
    # the final segment; here we surface the raw (ts, code) list and the
    # tally-without-last-segment so the inspector dump can still recover
    # every code that appears mid-night.
    stage_events = _walk_sleep_stage_events(fit)
    if stage_events:
        out['sleep_stage_events'] = stage_events
        out['sleep_stage_minutes_by_code_partial'] = _stage_minutes_from_events(
            stage_events,
        )
        # Derive `sleep_stress_avg` (= Connect's "Stress avg" during sleep)
        # when both `[346] field_15` (stress sum) and a sleep_period are
        # available. sleep_period_min = (last_event_ts - first_event_ts) / 60
        # is a few-minute approximation of the actual sleep duration (which
        # lives in [384] field_11 - field_9 - awake_min in a separate file),
        # but it round-trips to the same Connect-rounded average.
        sum_raw = out.get('sleep_stress_sum')
        if sum_raw is not None and len(stage_events) >= 2:
            span_min = (stage_events[-1][0] - stage_events[0][0]) // 60
            avg = sleep_stress_avg(sum_raw, span_min)
            if avg is not None:
                out['sleep_stress_avg'] = avg

    # Date = the file's creation timestamp (= morning sync after sleep).
    for record in fit.records:
        msg = record.message
        if type(msg).__name__ == 'FileIdMessage':
            tc = getattr(msg, 'time_created', None)
            if tc is not None:
                try:
                    ts_ms = int(tc)
                    if ts_ms < 1_000_000_000_000:
                        ts_ms *= 1000
                    out['date'] = datetime.fromtimestamp(
                        ts_ms / 1000.0, tz=timezone.utc
                    ).strftime('%Y-%m-%d')
                except (TypeError, ValueError):
                    pass
            break
    return out if out.get('date') and 'sleep_score' in out else {}


_HRV_NO_STATUS_SENTINEL = 65535


def parse_hrv_status_fit(fit_bytes: bytes) -> dict:
    """Parse a Garmin `_HRV_STATUS.fit` file (FileIdMessage.type = 68).

    Returns `{date, hrv_overnight_avg_ms, hrv_highest_5min_ms,
    hrv_7d_avg_ms, hrv_samples}`. All HRV values are de-scaled from the
    raw `value * 128` storage (6912/128 = 54.0 ms ↔ Garmin Connect 54 ms).
    `field_0` may carry the 65535 sentinel meaning "7-day baseline not
    established yet" (≥19 days of overnight data needed) — in that case
    `hrv_7d_avg_ms` is omitted entirely so the chart shows it as missing
    rather than a fake 511 ms.
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

    out: dict = {}
    samples: list = []
    for record in fit.records:
        msg = record.message
        if type(msg).__name__ != 'GenericMessage':
            continue
        gid = getattr(msg, 'global_id', None)
        fields = _generic_field_map(msg)
        if not fields:
            continue

        if gid == _HRV_STATUS_SUMMARY_MSG:
            # Overnight avg (field_1) and highest 5-min avg (field_2) — both
            # always present once HRV tracking is on. 7-day avg (field_0)
            # uses the 65535 sentinel before the 19-day baseline window is
            # filled, so check for that explicitly.
            for fid, key in ((1, 'hrv_overnight_avg_ms'),
                             (2, 'hrv_highest_5min_ms'),
                             (0, 'hrv_7d_avg_ms')):
                raw = fields.get(fid)
                if raw is None:
                    continue
                try:
                    n = int(raw)
                except (TypeError, ValueError):
                    continue
                if n == _HRV_NO_STATUS_SENTINEL:
                    continue
                out[key] = round(n / 128.0, 1)
            ts = _fit_seconds_to_unix_ms(fields.get(253) or
                                         getattr(msg, 'timestamp', None))
            if ts and 'date' not in out:
                out['date'] = datetime.fromtimestamp(
                    ts / 1000.0, tz=timezone.utc
                ).strftime('%Y-%m-%d')

        elif gid == _HRV_STATUS_SAMPLE_MSG:
            raw = fields.get(0)
            ts = _fit_seconds_to_unix_ms(fields.get(253) or
                                         getattr(msg, 'timestamp', None))
            if raw is not None and ts:
                try:
                    samples.append((ts, round(int(raw) / 128.0, 1)))
                except (TypeError, ValueError):
                    pass

    if samples:
        out['hrv_samples'] = samples
        if 'date' not in out:
            # Use the latest sample's date as the night attribution.
            out['date'] = datetime.fromtimestamp(
                max(s[0] for s in samples) / 1000.0, tz=timezone.utc
            ).strftime('%Y-%m-%d')

    return out if out.get('date') and (
        'hrv_overnight_avg_ms' in out or 'hrv_highest_5min_ms' in out
        or 'hrv_7d_avg_ms' in out or 'hrv_samples' in out
    ) else {}
