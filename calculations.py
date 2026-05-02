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

Outcome rules (calculate_outcome_from_sets, per-set):
  PROGRESS ↑ — every set met target reps AND target weight (and duration if applicable)
  REPEAT →   — at least one set failed AND total volume ≥ 75% of target
  REDUCE ↓   — at least one set failed AND total volume < 75% of target

Significantly-exceeded triggers (Family A — applies a 2× kicker on the
progressing dimension when outcome is PROGRESS):
  - 2+ sets at ≥ ceil(target_reps × 1.10) reps, OR
  - 2+ sets at ≥ ceil(target_duration × 1.10) duration, OR
  - At least one set beyond target_sets that also met target reps + weight

Family B — performance-tracked baseline (always applies on PROGRESS):
  If 2+ sets exceeded target on a given dimension, that dimension's baseline
  promotes to the min logged over-target value ("the level they hit twice").
  next_<dim> is then projected from the new baseline + one increment.

Consecutive failure counter logic:
  PROGRESS → reset to 0
  REPEAT   → reset to 0  (was: freeze; reset gives plateau tolerance)
  REDUCE   → increment by 1; regression fires when counter reaches
             regression_threshold, then resets to 0 so the user gets a fresh
             window at the lower target.
"""

import math


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
    """Aggregate-snapshot outcome (legacy single-entry edit form).

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
            return 'PROGRESS ↑'
        total_target = target_s * target_duration
        total_actual = actual_s * actual_d
        if total_target > 0 and total_actual / total_target >= 0.75:
            return 'REPEAT →'
        return 'REDUCE ↓'

    # Rep-based exercises
    target_s = target_sets or 1
    target_r = target_reps or 1
    actual_s = actual_sets or 0
    actual_r = actual_reps or 0

    if actual_s >= target_s and actual_r >= target_r:
        return 'PROGRESS ↑'

    total_target = target_s * target_r
    total_actual = actual_s * actual_r
    if total_target > 0 and total_actual / total_target >= 0.75:
        return 'REPEAT →'

    return 'REDUCE ↓'


def calculate_outcome_from_sets(target_sets, target_reps, target_weight, target_duration, sets_data):
    """Compute outcome + significance + working baseline values from per-set data.

    Returns dict:
      outcome: 'PROGRESS ↑' | 'REPEAT →' | 'REDUCE ↓' | None
      exceeded_significantly: bool — Family A trigger fired
      working_sets / working_reps / working_weight / working_duration:
        Family B promotion values (None if the dim wasn't exceeded on 2+ sets,
        or for working_sets, no qualifying extra set was logged).

    See module docstring for the full ruleset.
    """
    empty = {
        'outcome': None, 'exceeded_significantly': False,
        'working_sets': None, 'working_reps': None,
        'working_weight': None, 'working_duration': None,
    }
    if not sets_data:
        return empty
    if not (target_reps or target_duration or target_weight or target_sets):
        # No targets — caller (e.g. FIT bootstrap) handles baseline directly.
        return empty

    target_s = target_sets or 0
    target_r = target_reps or 0
    target_w = target_weight or 0
    target_d = target_duration or 0
    duration_mode = bool(target_d) and not target_r

    def _set_passed(s):
        reps = s.get('reps') or 0
        weight = s.get('weight_lbs') or 0
        duration = s.get('duration_sec') or 0
        if duration_mode:
            return duration >= target_d
        rep_ok = (reps >= target_r) if target_r else True
        wt_ok = (weight >= target_w) if target_w else True
        return rep_ok and wt_ok

    all_passed = all(_set_passed(s) for s in sets_data)
    if target_s and len(sets_data) < target_s:
        all_passed = False

    if all_passed:
        outcome = 'PROGRESS ↑'
    else:
        if duration_mode:
            target_vol = (target_s or 1) * target_d
            actual_vol = sum(s.get('duration_sec') or 0 for s in sets_data)
        else:
            # Use weight=1 fallback for bodyweight so the volume check reduces to rep counts
            target_vol = (target_s or 1) * (target_r or 1) * (target_w or 1)
            actual_vol = sum(
                (s.get('reps') or 0) * ((s.get('weight_lbs') or 0) or 1)
                for s in sets_data
            )
        ratio = (actual_vol / target_vol) if target_vol > 0 else 0
        outcome = 'REPEAT →' if ratio >= 0.75 else 'REDUCE ↓'

    # Family A — significance triggers
    rep_threshold = math.ceil(target_r * 1.10) if target_r else None
    sets_over_rep_pct = (
        sum(1 for s in sets_data if (s.get('reps') or 0) >= rep_threshold)
        if rep_threshold else 0
    )
    dur_threshold = math.ceil(target_d * 1.10) if target_d else None
    sets_over_dur_pct = (
        sum(1 for s in sets_data if (s.get('duration_sec') or 0) >= dur_threshold)
        if dur_threshold else 0
    )
    qualifying_extras = 0
    if target_s and len(sets_data) > target_s:
        for s in sets_data[target_s:]:
            if _set_passed(s):
                qualifying_extras += 1

    exceeded_significantly = (
        sets_over_rep_pct >= 2
        or sets_over_dur_pct >= 2
        or qualifying_extras >= 1
    )

    # Family B — working values (min logged over-target across 2+ sets)
    def _working_dim(target, key):
        if not target:
            return None
        over = [s.get(key) or 0 for s in sets_data if (s.get(key) or 0) > target]
        return min(over) if len(over) >= 2 else None

    working_weight = _working_dim(target_w, 'weight_lbs')
    working_reps = _working_dim(target_r, 'reps')
    working_duration = _working_dim(target_d, 'duration_sec')
    working_sets = (target_s + qualifying_extras) if qualifying_extras else None

    return {
        'outcome': outcome,
        'exceeded_significantly': exceeded_significantly,
        'working_sets': working_sets,
        'working_reps': working_reps,
        'working_weight': working_weight,
        'working_duration': working_duration,
    }


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
                      current_sets, current_reps, current_weight, current_duration,
                      weight_increment=None, consecutive_failures=0,
                      exceeded_significantly=False):
    """Apply progression rules based on outcome, movement pattern, and significance.

    Args:
        current_*: post-Family-B baseline (caller promotes working values
            into current_* before invoking, so progression starts from the
            level the user actually achieved).
        exceeded_significantly: Family A trigger — applies the 2× kicker on
            the progressing dimension (weight: 2× increment; reps/duration:
            +10% rounded up, floored to the normal +increment).

    Returns dict with next_weight, next_sets, next_reps, next_duration, consecutive_failures.
    """
    rules = PROGRESSION_RULES.get(movement_pattern, PROGRESSION_RULES['Various'])

    next_weight = current_weight
    next_sets = current_sets
    next_reps = current_reps
    next_duration = current_duration
    new_failures = consecutive_failures or 0

    if outcome == 'PROGRESS ↑':
        new_failures = 0
        w_inc = _resolve_weight_incr(weight_increment, current_weight, rules['weight_incr'])
        r_inc = rules['rep_incr']
        d_inc = rules['duration_incr']

        if movement_pattern == 'Plyo':
            next_sets = (current_sets or 1) + 1
        elif w_inc and current_weight:
            bump = w_inc * 2 if exceeded_significantly else w_inc
            next_weight = current_weight + bump
        elif r_inc and current_reps:
            normal = current_reps + r_inc
            next_reps = max(normal, math.ceil(current_reps * 1.10)) if exceeded_significantly else normal
        elif d_inc and current_duration:
            normal = current_duration + d_inc
            next_duration = max(normal, math.ceil(current_duration * 1.10)) if exceeded_significantly else normal

    elif outcome == 'REPEAT →':
        new_failures = 0  # reset; "consecutive" means strictly consecutive REDUCEs

    elif outcome == 'REDUCE ↓':
        new_failures = (consecutive_failures or 0) + 1
        threshold = rules.get('regression_threshold', 3)
        if new_failures >= threshold:
            w_inc = _resolve_weight_incr(weight_increment, current_weight, rules['weight_incr'])
            d_inc = rules['duration_incr']
            r_inc = rules['rep_incr']
            if w_inc and current_weight and current_weight > w_inc:
                next_weight = current_weight - w_inc
            elif d_inc and current_duration and current_duration > d_inc:
                next_duration = current_duration - d_inc
            elif r_inc and current_reps and current_reps > r_inc:
                next_reps = current_reps - r_inc
            new_failures = 0  # fresh window at the lower target

    return {
        'next_weight': next_weight,
        'next_sets': next_sets,
        'next_reps': next_reps,
        'next_duration': next_duration,
        'consecutive_failures': new_failures,
    }


def project_next_from_current(current_sets, current_reps, current_weight, current_duration,
                              movement_pattern, weight_increment=None):
    """Project next_* by applying one normal progression step from current_*.

    Used by:
      - Manual current_rx edits (rx.py): edit current → re-derive next.
      - FIT import bootstrap (no targets / first-time exercise): set baseline
        from actuals and project next as a single increment so the system has
        something to prescribe next session.

    Equivalent to calculate_next_rx() with outcome=PROGRESS and
    exceeded_significantly=False, but stripped of failure-counter mutation
    so it doesn't masquerade as a real session result.
    """
    rules = PROGRESSION_RULES.get(movement_pattern, PROGRESSION_RULES['Various'])
    next_weight = current_weight
    next_sets = current_sets
    next_reps = current_reps
    next_duration = current_duration

    w_inc = _resolve_weight_incr(weight_increment, current_weight, rules['weight_incr'])
    r_inc = rules['rep_incr']
    d_inc = rules['duration_incr']

    if movement_pattern == 'Plyo':
        next_sets = (current_sets or 1) + 1
    elif w_inc and current_weight:
        next_weight = current_weight + w_inc
    elif r_inc and current_reps:
        next_reps = current_reps + r_inc
    elif d_inc and current_duration:
        next_duration = current_duration + d_inc

    return {
        'next_sets': next_sets,
        'next_reps': next_reps,
        'next_weight': next_weight,
        'next_duration': next_duration,
    }
