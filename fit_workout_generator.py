"""Generate Garmin workout FIT files from training plan items.

Each plan item is encoded as a single workout file (.fit) that can be
loaded onto a Garmin device directly or via Garmin Express.
"""
from datetime import datetime

from fit_tool.fit_file_builder import FitFileBuilder
from fit_tool.profile.messages.file_id_message import FileIdMessage
from fit_tool.profile.messages.workout_message import WorkoutMessage
from fit_tool.profile.messages.workout_step_message import WorkoutStepMessage
from fit_tool.profile.profile_type import (
    FileType, Sport, WorkoutStepDuration, WorkoutStepTarget, Intensity
)

# Plan sport_type string → FIT Sport enum
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

# Intensity label → FIT HR zone (1-5)
_HR_ZONE = {
    'easy':      2,
    'moderate':  3,
    'hard':      4,
    'very_hard': 5,
}

# Intensity label → FIT step intensity enum
_FIT_INTENSITY = {
    'easy':      Intensity.ACTIVE,
    'moderate':  Intensity.ACTIVE,
    'hard':      Intensity.INTERVAL,
    'very_hard': Intensity.INTERVAL,
}


def _map_sport(sport_type: str) -> Sport:
    return _SPORT_MAP.get((sport_type or '').lower(), Sport.GENERIC)


def _build_steps(duration_min: float, distance_mi: float, intensity: str, sport: Sport) -> list:
    """Return a list of step dicts describing the workout structure."""
    hr_zone = _HR_ZONE.get(intensity, 3)
    step_intensity = _FIT_INTENSITY.get(intensity, Intensity.ACTIVE)

    # Strength: one open step (Garmin doesn't support per-exercise FIT guidance)
    if sport == Sport.TRAINING:
        return [{
            'name': 'Workout',
            'duration_type': WorkoutStepDuration.OPEN,
            'duration_value': 0,
            'target_type': WorkoutStepTarget.OPEN,
            'target_value': 0,
            'intensity': Intensity.ACTIVE,
        }]

    # Hard/very_hard cardio ≥ 40 min → warmup + main + cooldown
    if duration_min >= 40 and intensity in ('hard', 'very_hard'):
        return [
            {
                'name': 'Warm Up',
                'duration_type': WorkoutStepDuration.TIME,
                'duration_value': int(10 * 60 * 1000),
                'target_type': WorkoutStepTarget.HEART_RATE,
                'target_value': 2,
                'intensity': Intensity.WARMUP,
            },
            {
                'name': 'Work',
                'duration_type': WorkoutStepDuration.TIME,
                'duration_value': int((duration_min - 20) * 60 * 1000),
                'target_type': WorkoutStepTarget.HEART_RATE,
                'target_value': hr_zone,
                'intensity': step_intensity,
            },
            {
                'name': 'Cool Down',
                'duration_type': WorkoutStepDuration.TIME,
                'duration_value': int(10 * 60 * 1000),
                'target_type': WorkoutStepTarget.HEART_RATE,
                'target_value': 2,
                'intensity': Intensity.COOLDOWN,
            },
        ]

    # Single time-based step
    if duration_min:
        return [{
            'name': 'Workout',
            'duration_type': WorkoutStepDuration.TIME,
            'duration_value': int(duration_min * 60 * 1000),
            'target_type': WorkoutStepTarget.HEART_RATE,
            'target_value': hr_zone,
            'intensity': step_intensity,
        }]

    # Single distance-based step
    if distance_mi:
        return [{
            'name': 'Workout',
            'duration_type': WorkoutStepDuration.DISTANCE,
            'duration_value': int(distance_mi * 1609.344),
            'target_type': WorkoutStepTarget.HEART_RATE,
            'target_value': hr_zone,
            'intensity': step_intensity,
        }]

    # No duration or distance: open step
    return [{
        'name': 'Workout',
        'duration_type': WorkoutStepDuration.OPEN,
        'duration_value': 0,
        'target_type': WorkoutStepTarget.HEART_RATE,
        'target_value': hr_zone,
        'intensity': step_intensity,
    }]


def generate_workout_fit(item: dict) -> bytes:
    """Generate a Garmin workout FIT file from a plan item dict.

    Keys used: workout_name, sport_type, target_duration_min,
               target_distance_mi, intensity
    Returns raw bytes of the .fit file — no side effects.
    """
    sport = _map_sport(item.get('sport_type', ''))
    name = (item.get('workout_name') or 'Workout')[:50]
    duration_min = float(item.get('target_duration_min') or 0)
    distance_mi = float(item.get('target_distance_mi') or 0)
    intensity = item.get('intensity') or 'moderate'

    steps = _build_steps(duration_min, distance_mi, intensity, sport)

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
