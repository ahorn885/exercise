"""Generate Garmin workout FIT files from training plan items.

Parses workout descriptions into proper step sequences (warmup, intervals with
recovery, cooldown) so the resulting .fit file reflects the planned workout.

Example: "10 min easy warmup. 5x5 min @ tempo w/ 2 min jog recovery. 10 min cooldown"
→ Warm Up (10 min, Z2) · Interval (5 min, Z4) · Recovery (2 min, Z2) ×5 · Cool Down (10 min, Z2)
"""
import re
from datetime import date, datetime

from fit_tool.fit_file_builder import FitFileBuilder
from fit_tool.profile.messages.activity_message import ActivityMessage
from fit_tool.profile.messages.file_id_message import FileIdMessage
from fit_tool.profile.messages.lap_message import LapMessage
from fit_tool.profile.messages.session_message import SessionMessage
from fit_tool.profile.messages.workout_message import WorkoutMessage
from fit_tool.profile.messages.workout_step_message import WorkoutStepMessage
from fit_tool.profile.profile_type import (
    Activity as ActivityType, Event, EventType,
    FileType, Intensity, Sport, WorkoutStepDuration, WorkoutStepTarget,
)

# ── Sport mapping ──────────────────────────────────────────────────────────────
_SPORT_MAP = {
    'running':           Sport.RUNNING,
    'trail_running':     Sport.RUNNING,
    'cycling':           Sport.CYCLING,
    'mountain_biking':   Sport.CYCLING,
    'gravel_cycling':    Sport.CYCLING,
    'swimming':          Sport.SWIMMING,
    'hiking':            Sport.HIKING,
    'rowing':            Sport.ROWING,
    'kayaking':          Sport.PADDLING,
    'pack_rafting':      Sport.PADDLING,
    'walking':           Sport.WALKING,
    'strength_training': Sport.TRAINING,
    'multisport':        Sport.MULTISPORT,
}

_HR_ZONE = {'easy': 2, 'moderate': 3, 'hard': 4, 'very_hard': 5}
_FIT_INTENSITY = {
    'easy':      Intensity.ACTIVE,
    'moderate':  Intensity.ACTIVE,
    'hard':      Intensity.INTERVAL,
    'very_hard': Intensity.INTERVAL,
}

# Ordered (zone, pattern) — most specific first so the loop short-circuits
_ZONE_PATTERNS = [
    (5, re.compile(
        r'vo2|zone\s*5|rpe\s*(?:9|10)|all[\s-]*out|maximum|race\s*pace|sprint|very[\s-]*hard',
        re.I)),
    (4, re.compile(
        r'tempo|threshold|comfortably[\s-]*hard|rpe\s*[78]|zone\s*4|(?<!\w)hard(?!\w)|lactate|ltp',
        re.I)),
    (3, re.compile(r'moderate|zone\s*3|aerobic|marathon\s*pace|sweet\s*spot', re.I)),
    (2, re.compile(r'easy|zone\s*[12]|jog|recov|light|comfort|conversational|low\s*intensity', re.I)),
]

# Duration regex: captures (value, optional_unit)
_DUR_RE = re.compile(
    r'(\d+(?:\.\d+)?)\s*(?:(hours?|hr)|min(?:ute)?s?)',
    re.I,
)


def _map_sport(sport_type: str) -> Sport:
    return _SPORT_MAP.get((sport_type or '').lower(), Sport.GENERIC)


def _zone_from_text(text: str, default: int = 3) -> int:
    """Return HR zone 1-5 inferred from description text."""
    for zone, pat in _ZONE_PATTERNS:
        if pat.search(text):
            return zone
    return default


def _ms(value: float, unit: str = 'min') -> int:
    """Convert value+unit to milliseconds."""
    return int(value * (3600000 if unit and unit.lower().startswith('h') else 60000))


def _step(name: str, duration_ms: int, zone: int, intensity: Intensity,
          dtype=WorkoutStepDuration.TIME) -> dict:
    return {
        'name': name,
        'duration_type': dtype,
        'duration_value': duration_ms,
        'target_type': WorkoutStepTarget.HEART_RATE,
        'target_value': zone,
        'intensity': intensity,
    }


def _first_duration(text: str):
    """Return (value, unit) of the first duration found in text, or None."""
    m = _DUR_RE.search(text)
    return (float(m.group(1)), m.group(2) or 'min') if m else None


def _parse_segment(seg: str, default_zone: int) -> list:
    """Parse one sentence/clause of a workout description into step dicts."""
    seg = seg.strip().rstrip('.')
    if not seg:
        return []
    sl = seg.lower()

    # ── Warmup ─────────────────────────────────────────────────────────────
    if 'warm' in sl:
        dur = _first_duration(seg)
        if dur:
            return [_step('Warm Up', _ms(*dur), _zone_from_text(seg, 2), Intensity.WARMUP)]

    # ── Cooldown ────────────────────────────────────────────────────────────
    if 'cool' in sl:
        dur = _first_duration(seg)
        if dur:
            return [_step('Cool Down', _ms(*dur), _zone_from_text(seg, 2), Intensity.COOLDOWN)]

    # ── Intervals: N×M min [desc] [w/ P min recovery] ───────────────────────
    iv = re.match(
        r'(\d+)\s*[x×]\s*(\d+(?:\.\d+)?)\s*(?:(hours?|hr)|min(?:ute)?s?)(.*)',
        seg, re.I,
    )
    if iv:
        reps = int(iv.group(1))
        work_val = float(iv.group(2))
        work_unit = iv.group(3) or 'min'
        tail = iv.group(4).strip()

        # Split work description from recovery at "with" / "w/"
        w_split = re.split(r'\s+w(?:ith|/)\s+', tail, maxsplit=1, flags=re.I)
        work_desc = w_split[0].lstrip('@').strip()
        rec_str = w_split[1].strip() if len(w_split) > 1 else ''

        work_zone = _zone_from_text(work_desc or seg, default_zone)
        work_fit = Intensity.INTERVAL if work_zone >= 4 else Intensity.ACTIVE

        steps = []
        for _ in range(reps):
            steps.append(_step('Interval', _ms(work_val, work_unit), work_zone, work_fit))
            if rec_str:
                rm = re.match(
                    r'(\d+(?:\.\d+)?)\s*(?:(hours?|hr)|min(?:ute)?s?)(.*)',
                    rec_str, re.I,
                )
                if rm:
                    rv, ru, rd = float(rm.group(1)), rm.group(2) or 'min', rm.group(3).strip()
                    rec_zone = _zone_from_text(rd or rec_str, 2)
                    steps.append(_step('Recovery', _ms(rv, ru), rec_zone, Intensity.RECOVERY))
        return steps

    # ── Steady: M min/hr [at/of/@ intensity] ────────────────────────────────
    st = re.match(
        r'(\d+(?:\.\d+)?)\s*(?:(hours?|hr)|min(?:ute)?s?)(.*)',
        seg, re.I,
    )
    if st:
        val = float(st.group(1))
        unit = st.group(2) or 'min'
        desc = re.sub(r'^(?:at|@|of)\s+', '', st.group(3).strip(), flags=re.I)
        zone = _zone_from_text(desc or seg, default_zone)
        fit_i = Intensity.INTERVAL if zone >= 4 else Intensity.ACTIVE
        return [_step('Work', _ms(val, unit), zone, fit_i)]

    # ── [intensity] for M min ────────────────────────────────────────────────
    st2 = re.match(
        r'(.*?)\s+for\s+(\d+(?:\.\d+)?)\s*(?:hours?|hr|min(?:ute)?s?)',
        seg, re.I,
    )
    if st2:
        desc, val = st2.group(1), float(st2.group(2))
        zone = _zone_from_text(desc, default_zone)
        fit_i = Intensity.INTERVAL if zone >= 4 else Intensity.ACTIVE
        return [_step('Work', _ms(val), zone, fit_i)]

    return []


def _parse_description(description: str, default_intensity: str, sport: Sport) -> list | None:
    """Parse a workout description into FIT step dicts.

    Returns None when no recognizable structure is found (caller uses fallback).
    """
    if not description or sport == Sport.TRAINING:
        return None

    default_zone = _HR_ZONE.get(default_intensity, 3)
    text = re.sub(r'\s+', ' ', description).strip()

    # Split on ". " or "; " first; fall back to ", " if no sentences found
    segments = re.split(r'\.\s+|;\s+', text)
    if len(segments) == 1 and re.search(r'warm|cool|\dx', segments[0], re.I):
        segments = re.split(r',\s+', text)

    steps = []
    for seg in segments:
        steps.extend(_parse_segment(seg, default_zone))

    return steps if steps else None


def _build_steps(duration_min: float, distance_mi: float, intensity: str,
                 sport: Sport, description: str = '') -> list:
    """Return the ordered list of step dicts for the workout."""
    # Try to build steps from the description text
    parsed = _parse_description(description, intensity, sport)
    if parsed:
        return parsed

    default_zone = _HR_ZONE.get(intensity, 3)
    step_intensity = _FIT_INTENSITY.get(intensity, Intensity.ACTIVE)

    # Strength: single open step
    if sport == Sport.TRAINING:
        return [{'name': 'Workout', 'duration_type': WorkoutStepDuration.OPEN,
                 'duration_value': 0, 'target_type': WorkoutStepTarget.OPEN,
                 'target_value': 0, 'intensity': Intensity.ACTIVE}]

    # Hard/very_hard cardio ≥ 40 min → warmup + main + cooldown
    if duration_min >= 40 and intensity in ('hard', 'very_hard'):
        return [
            _step('Warm Up',   _ms(10),                   2,            Intensity.WARMUP),
            _step('Work',      _ms(duration_min - 20),    default_zone, step_intensity),
            _step('Cool Down', _ms(10),                   2,            Intensity.COOLDOWN),
        ]

    # Single time-based step
    if duration_min:
        return [_step('Workout', _ms(duration_min), default_zone, step_intensity)]

    # Single distance-based step
    if distance_mi:
        return [{'name': 'Workout', 'duration_type': WorkoutStepDuration.DISTANCE,
                 'duration_value': int(distance_mi * 1609.344),
                 'target_type': WorkoutStepTarget.HEART_RATE,
                 'target_value': default_zone, 'intensity': step_intensity}]

    # Open step (no duration/distance known)
    return [{'name': 'Workout', 'duration_type': WorkoutStepDuration.OPEN,
             'duration_value': 0, 'target_type': WorkoutStepTarget.HEART_RATE,
             'target_value': default_zone, 'intensity': step_intensity}]


def generate_workout_fit(item: dict) -> bytes:
    """Generate a Garmin workout FIT file from a plan item dict.

    Keys used: workout_name, sport_type, target_duration_min,
               target_distance_mi, intensity, description
    Returns raw bytes — no side effects.
    """
    sport = _map_sport(item.get('sport_type', ''))
    name = (item.get('workout_name') or 'Workout')[:50]
    duration_min = float(item.get('target_duration_min') or 0)
    distance_mi = float(item.get('target_distance_mi') or 0)
    intensity = item.get('intensity') or 'moderate'
    description = item.get('description') or ''

    steps = _build_steps(duration_min, distance_mi, intensity, sport, description)

    builder = FitFileBuilder(auto_define=True, min_string_size=50)

    file_id = FileIdMessage()
    file_id.type = FileType.WORKOUT
    file_id.manufacturer = 255  # development / generic
    file_id.product = 0
    file_id.time_created = round(datetime.now().timestamp() * 1000)
    file_id.serial_number = 1
    builder.add(file_id)

    wkt = WorkoutMessage()
    wkt.sport = sport
    wkt.num_valid_steps = len(steps)
    wkt.workout_name = name
    builder.add(wkt)

    for i, s in enumerate(steps):
        step = WorkoutStepMessage()
        step.message_index = i
        step.workout_step_name = s['name']
        step.duration_type = s['duration_type']
        step.duration_value = s['duration_value']
        step.target_type = s['target_type']
        step.target_value = s['target_value']
        step.intensity = s['intensity']
        builder.add(step)

    return builder.build().to_bytes()


def generate_activity_fit(entry: dict) -> bytes:
    """Generate a minimal Garmin activity FIT file from a cardio_log entry dict.

    Keys used: activity, date, duration_min, distance_mi, avg_hr, avg_speed,
               avg_power, calories, elev_gain_ft
    Returns raw bytes — no side effects.
    """
    sport = _map_sport(entry.get('activity', ''))
    duration_min = float(entry.get('duration_min') or 0)
    duration_s = int(duration_min * 60)   # total_elapsed_time / total_timer_time use seconds
    distance_mi = float(entry.get('distance_mi') or 0)
    distance_m = distance_mi * 1609.344 if distance_mi else 0

    avg_speed_mph = entry.get('avg_speed')
    if avg_speed_mph:
        avg_speed_ms = float(avg_speed_mph) * 0.44704  # m/s
    elif duration_min and distance_mi:
        avg_speed_ms = distance_m / (duration_min * 60)
    else:
        avg_speed_ms = None

    avg_hr = entry.get('avg_hr')
    avg_power = entry.get('avg_power')
    calories = entry.get('calories')
    elev_gain_ft = entry.get('elev_gain_ft')
    total_ascent_m = int(float(elev_gain_ft) * 0.3048) if elev_gain_ft else None

    # start_time / timestamp fields use Unix milliseconds
    date_str = entry.get('date') or date.today().isoformat()
    try:
        dt = datetime.strptime(date_str, '%Y-%m-%d')
    except ValueError:
        dt = datetime.now()
    start_ms = round(dt.timestamp() * 1000)
    now_ms = round(datetime.now().timestamp() * 1000)
    end_ms = start_ms + duration_s * 1000

    builder = FitFileBuilder(auto_define=True, min_string_size=50)

    file_id = FileIdMessage()
    file_id.type = FileType.ACTIVITY
    file_id.manufacturer = 255
    file_id.product = 0
    file_id.time_created = now_ms
    file_id.serial_number = 1
    builder.add(file_id)

    act = ActivityMessage()
    act.total_timer_time = duration_s
    act.num_sessions = 1
    act.type = ActivityType.MANUAL
    act.event = Event.ACTIVITY
    act.event_type = EventType.STOP
    act.timestamp = end_ms
    builder.add(act)

    sess = SessionMessage()
    sess.sport = sport
    sess.start_time = start_ms
    sess.total_elapsed_time = duration_s
    sess.total_timer_time = duration_s
    if distance_m:
        sess.total_distance = distance_m
    if avg_hr:
        sess.avg_heart_rate = int(float(avg_hr))
    if avg_speed_ms:
        sess.avg_speed = avg_speed_ms
    if avg_power:
        sess.avg_power = int(float(avg_power))
    if calories:
        sess.total_calories = int(float(calories))
    if total_ascent_m:
        sess.total_ascent = total_ascent_m
    sess.event = Event.SESSION
    sess.event_type = EventType.STOP
    sess.timestamp = end_ms
    builder.add(sess)

    lap = LapMessage()
    lap.start_time = start_ms
    lap.total_elapsed_time = duration_s
    lap.total_timer_time = duration_s
    if distance_m:
        lap.total_distance = distance_m
    if avg_hr:
        lap.avg_heart_rate = int(float(avg_hr))
    if avg_speed_ms:
        lap.avg_speed = avg_speed_ms
    if avg_power:
        lap.avg_power = int(float(avg_power))
    if calories:
        lap.total_calories = int(float(calories))
    if total_ascent_m:
        lap.total_ascent = total_ascent_m
    lap.event = Event.LAP
    lap.event_type = EventType.STOP
    lap.timestamp = end_ms
    builder.add(lap)

    return builder.build().to_bytes()
