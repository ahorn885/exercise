"""Auto-calculation logic matching the Excel formulas."""


PROGRESSION_RULES = {
    'Squat':    {'weight_incr': 5, 'rep_incr': 0, 'duration_incr': 0},
    'Hinge':    {'weight_incr': 5, 'rep_incr': 0, 'duration_incr': 0},
    'Lunge':    {'weight_incr': 5, 'rep_incr': 0, 'duration_incr': 0},
    'Push':     {'weight_incr': 5, 'rep_incr': 0, 'duration_incr': 0},
    'Pull':     {'weight_incr': 5, 'rep_incr': 0, 'duration_incr': 0},
    'Core':     {'weight_incr': 0, 'rep_incr': 2, 'duration_incr': 5},
    'Carry':    {'weight_incr': 5, 'rep_incr': 0, 'duration_incr': 0},
    'Rotation': {'weight_incr': 2.5, 'rep_incr': 0, 'duration_incr': 0},
    'Plyo':     {'weight_incr': 0, 'rep_incr': 0, 'duration_incr': 0},  # add sets only
    'Balance':  {'weight_incr': 0, 'rep_incr': 0, 'duration_incr': 5},
    'Various':  {'weight_incr': 2.5, 'rep_incr': 1, 'duration_incr': 5},
    'Complex':  {'weight_incr': 5, 'rep_incr': 0, 'duration_incr': 0},
    'Conditioning': {'weight_incr': 0, 'rep_incr': 0, 'duration_incr': 5},
    'Grip':     {'weight_incr': 0, 'rep_incr': 2, 'duration_incr': 5},
    'Locomotion': {'weight_incr': 0, 'rep_incr': 0, 'duration_incr': 5},
    'Mobility': {'weight_incr': 0, 'rep_incr': 0, 'duration_incr': 5},
}


def calculate_outcome(target_sets, target_reps, target_duration,
                      actual_sets, actual_reps, actual_duration):
    """
    PROGRESS ↑: Actual Sets >= Target Sets AND Actual Reps >= Target Reps (or Duration)
    REPEAT →: Completed >= 75% of target but not all
    REDUCE ↓: Completed < 75% of target sets or reps
    """
    if not target_sets and not target_reps and not target_duration:
        return None

    # Duration-based exercises
    if target_duration and target_duration > 0 and not target_reps:
        actual_d = actual_duration or 0
        actual_s = actual_sets or 0
        target_s = target_sets or 1
        if actual_s >= target_s and actual_d >= target_duration:
            return 'PROGRESS \u2191'
        total_target = target_s * target_duration
        total_actual = actual_s * actual_d
        if total_target > 0 and total_actual / total_target >= 0.75:
            return 'REPEAT \u2192'
        return 'REDUCE \u2193'

    # Rep-based exercises
    target_s = target_sets or 1
    target_r = target_reps or 1
    actual_s = actual_sets or 0
    actual_r = actual_reps or 0

    if actual_s >= target_s and actual_r >= target_r:
        return 'PROGRESS \u2191'

    total_target = target_s * target_r
    total_actual = actual_s * actual_r
    if total_target > 0 and total_actual / total_target >= 0.75:
        return 'REPEAT \u2192'

    return 'REDUCE \u2193'


def calculate_1rm(weight, reps):
    """Epley formula: 1RM = weight * (1 + reps/30)"""
    if not weight or not reps or weight <= 0 or reps <= 0:
        return None
    if reps == 1:
        return round(weight, 1)
    return round(weight * (1 + reps / 30.0), 1)


def calculate_volume(sets, reps, weight):
    """Volume = sets * reps * weight"""
    s = sets or 0
    r = reps or 0
    w = weight or 0
    return s * r * w


def calculate_next_rx(outcome, movement_pattern,
                      actual_sets, actual_reps, actual_weight, actual_duration):
    """Apply progression rules based on outcome and movement pattern."""
    rules = PROGRESSION_RULES.get(movement_pattern, PROGRESSION_RULES['Various'])

    next_weight = actual_weight
    next_sets = actual_sets
    next_reps = actual_reps

    if outcome == 'PROGRESS \u2191':
        w_inc = rules['weight_incr']
        r_inc = rules['rep_incr']

        if movement_pattern == 'Plyo':
            next_sets = (actual_sets or 1) + 1
        elif w_inc and actual_weight:
            next_weight = (actual_weight or 0) + w_inc
        elif r_inc and actual_reps:
            next_reps = (actual_reps or 0) + r_inc
    elif outcome == 'REDUCE \u2193':
        w_inc = rules['weight_incr']
        if w_inc and actual_weight and actual_weight > w_inc:
            next_weight = actual_weight - w_inc

    # REPEAT → keeps same values

    return {
        'next_weight': next_weight,
        'next_sets': next_sets,
        'next_reps': next_reps,
    }
