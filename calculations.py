"""Auto-calculation logic matching the Excel formulas.

Progression rules (PROGRESSION_RULES):
  Each movement pattern defines the default step sizes and regression threshold.
  weight_incr   — fallback lb increment when actual_weight is unavailable (see _resolve_weight_incr)
  rep_incr      — reps to add per PROGRESS session (bodyweight / rep-focused patterns)
  duration_incr — seconds to add per PROGRESS session (time-based patterns)
  regression_threshold — consecutive REDUCE outcomes before weight/duration actually decreases

Weight increment runtime rule (overrides weight_incr when actual_weight is known):
  actual_weight < 15 lb  → 2.5 lb increment  (light KB/DB; micro-plate scale)
  actual_weight >= 15 lb → 5.0 lb increment   (standard KB/DB or barbell)
  explicit weight_increment arg   → use that value instead (per-exercise override stored in exercise_inventory)

Consecutive failure counter logic:
  PROGRESS → reset to 0
  REPEAT   → freeze (unchanged)
  REDUCE   → increment by 1; regression fires when counter reaches regression_threshold
"""


PROGRESSION_RULES = {
    'Squat':       {'weight_incr': 5,   'rep_incr': 0, 'duration_incr': 0,  'regression_threshold': 3},
    'Hinge':       {'weight_incr': 5,   'rep_incr': 0, 'duration_incr': 0,  'regression_threshold': 3},
    'Lunge':       {'weight_incr': 5,   'rep_incr': 0, 'duration_incr': 0,  'regression_threshold': 3},
    'Push':        {'weight_incr': 5,   'rep_incr': 1, 'duration_incr': 0,  'regression_threshold': 3},
    'Pull':        {'weight_incr': 5,   'rep_incr': 1, 'duration_incr': 0,  'regression_threshold': 3},
    'Core':        {'weight_incr': 0,   'rep_incr': 2, 'duration_incr': 5,  'regression_threshold': 3},
    'Carry':       {'weight_incr': 5,   'rep_incr': 0, 'duration_incr': 0,  'regression_threshold': 3},
    'Rotation':    {'weight_incr': 2.5, 'rep_incr': 0, 'duration_incr': 0,  'regression_threshold': 3},
    'Plyo':        {'weight_incr': 0,   'rep_incr': 0, 'duration_incr': 0,  'regression_threshold': 3},  # add sets only
    'Balance':     {'weight_incr': 0,   'rep_incr': 0, 'duration_incr': 5,  'regression_threshold': 3},
    'Various':     {'weight_incr': 2.5, 'rep_incr': 1, 'duration_incr': 5,  'regression_threshold': 3},
    'Complex':     {'weight_incr': 5,   'rep_incr': 0, 'duration_incr': 0,  'regression_threshold': 3},
    'Conditioning':{'weight_incr': 0,   'rep_incr': 0, 'duration_incr': 5,  'regression_threshold': 3},
    'Grip':        {'weight_incr': 0,   'rep_incr': 2, 'duration_incr': 5,  'regression_threshold': 3},
    'Locomotion':  {'weight_incr': 0,   'rep_incr': 0, 'duration_incr': 5,  'regression_threshold': 3},
    'Mobility':    {'weight_incr': 0,   'rep_incr': 0, 'duration_incr': 5,  'regression_threshold': 3},
}


def _resolve_weight_incr(weight_increment_override, actual_weight, pattern_default):
    """Return the lb increment to use for progression/regression.

    Priority:
      1. Explicit per-exercise override (stored in exercise_inventory.weight_increment)
      2. Runtime rule from actual_weight: < 15 lb → 2.5, >= 15 lb → 5.0
      3. Pattern default from PROGRESSION_RULES (fallback when weight unknown)
    """
    if weight_increment_override is not None:
        return weight_increment_override
    if actual_weight is not None:
        return 2.5 if actual_weight < 15 else 5.0
    return pattern_default


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


def calculate_outcome_from_sets(target_sets, target_reps, target_weight, target_duration, sets_data):
    """Compute outcome from per-set logged data.

    PROGRESS ↑: all sets passed AND at least one set exceeded target (more reps or more weight)
    REPEAT →:   all sets passed AND none exceeded (exactly met target on every set)
    REDUCE ↓:   fewer sets than target, or any set failed to meet target

    sets_data: list of dicts with keys reps, weight_lbs, duration_sec (all optional/nullable).
    """
    if not sets_data:
        return None
    if not target_reps and not target_duration:
        return None

    target_s = target_sets or 0
    target_r = target_reps or 0
    target_w = target_weight or 0
    target_d = target_duration or 0

    if target_s and len(sets_data) < target_s:
        return 'REDUCE ↓'

    all_passed = True
    any_exceeded = False

    for s in sets_data:
        reps = s.get('reps') or 0
        weight = s.get('weight_lbs') or 0
        duration = s.get('duration_sec') or 0

        if target_d and not target_r:
            passed = duration >= target_d
            exceeded = duration > target_d
        else:
            rep_ok = (reps >= target_r) if target_r else True
            wt_ok = (weight >= target_w) if target_w else True
            passed = rep_ok and wt_ok
            exceeded = (reps > target_r if target_r else False) or (weight > target_w if target_w else False)

        if not passed:
            all_passed = False
        if exceeded:
            any_exceeded = True

    if not all_passed:
        return 'REDUCE ↓'
    if any_exceeded:
        return 'PROGRESS ↑'
    return 'REPEAT →'


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
                      actual_sets, actual_reps, actual_weight, actual_duration,
                      weight_increment=None, consecutive_failures=0):
    """Apply progression rules based on outcome and movement pattern.

    Args:
        weight_increment: per-exercise override lb step (from exercise_inventory); None = auto
        consecutive_failures: current count of consecutive REDUCE outcomes for this exercise

    Returns dict with next_weight, next_sets, next_reps, next_duration, consecutive_failures.
    """
    rules = PROGRESSION_RULES.get(movement_pattern, PROGRESSION_RULES['Various'])

    next_weight = actual_weight
    next_sets = actual_sets
    next_reps = actual_reps
    next_duration = actual_duration
    new_failures = consecutive_failures or 0

    if outcome == 'PROGRESS \u2191':
        new_failures = 0
        w_inc = _resolve_weight_incr(weight_increment, actual_weight, rules['weight_incr'])
        r_inc = rules['rep_incr']
        d_inc = rules['duration_incr']

        if movement_pattern == 'Plyo':
            next_sets = (actual_sets or 1) + 1
        elif w_inc and actual_weight:
            next_weight = (actual_weight or 0) + w_inc
        elif r_inc and actual_reps:
            next_reps = (actual_reps or 0) + r_inc
        elif d_inc and actual_duration:
            next_duration = (actual_duration or 0) + d_inc

    elif outcome == 'REDUCE \u2193':
        new_failures = (consecutive_failures or 0) + 1
        threshold = rules.get('regression_threshold', 3)
        if new_failures >= threshold:
            w_inc = _resolve_weight_incr(weight_increment, actual_weight, rules['weight_incr'])
            d_inc = rules['duration_incr']
            r_inc = rules['rep_incr']
            if w_inc and actual_weight and actual_weight > w_inc:
                next_weight = actual_weight - w_inc
            elif d_inc and actual_duration and actual_duration > d_inc:
                next_duration = actual_duration - d_inc
            elif r_inc and actual_reps and actual_reps > r_inc:
                next_reps = actual_reps - r_inc

    # REPEAT → keeps same values; new_failures unchanged (frozen)

    return {
        'next_weight': next_weight,
        'next_sets': next_sets,
        'next_reps': next_reps,
        'next_duration': next_duration,
        'consecutive_failures': new_failures,
    }
