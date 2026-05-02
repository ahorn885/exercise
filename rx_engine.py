"""Single entry point for applying a logged session to current_rx.

Consolidates the previously-duplicated logic from routes/training.py and
the two strength-import paths in routes/garmin.py. The shape:

    apply_session_outcome(db, exercise, date, sets, targets..., rx_source)
        → dict the caller uses to populate the training_log row.

Semantics (per Andy's 2026-05 rules):
  - current_<dim> is the **prescribed baseline**, not last performance.
    It only moves up on PROGRESS (Family B may promote it to a working
    value above target), and only moves down after `regression_threshold`
    consecutive REDUCEs. REPEAT and isolated REDUCE leave it alone.
  - Any update to current also recomputes next, so the prescription never
    goes stale.
  - FIT imports run in bootstrap mode: no targets → seed both current_*
    and next_* from the actuals so first-time exercises get a real Rx
    from the upload.
  - new current_rx rows are created on demand (UPSERT) so a FIT file with
    a never-before-logged exercise still produces a baseline.
"""

from calculations import (
    calculate_outcome_from_sets,
    calculate_next_rx,
    project_next_from_current,
)


def _bootstrap_baseline(sets):
    """Derive baseline values from a target-less session (FIT bootstrap).

    Conservative: use the min reps/weight/duration the user actually hit on
    every set with non-zero data. That's "the level they hit consistently."
    """
    actual_sets = len(sets)
    reps = [s.get('reps') or 0 for s in sets if (s.get('reps') or 0) > 0]
    wts = [s.get('weight_lbs') or 0 for s in sets if (s.get('weight_lbs') or 0) > 0]
    durs = [s.get('duration_sec') or 0 for s in sets if (s.get('duration_sec') or 0) > 0]
    return {
        'sets': actual_sets or None,
        'reps': min(reps) if reps else None,
        'weight': min(wts) if wts else None,
        'duration': min(durs) if durs else None,
    }


def apply_session_outcome(db, exercise, date, sets,
                          target_sets=None, target_reps=None,
                          target_weight=None, target_duration=None,
                          rx_source='From Training Log'):
    """Compute outcome, project next, UPSERT current_rx, return result for caller.

    Caller uses returned dict to populate the training_log row's outcome /
    next_* / movement_pattern columns. All db writes here are uncommitted —
    caller commits.

    Returns:
        {
          movement_pattern, exercise_id,
          outcome, exceeded_significantly,
          baseline_sets, baseline_reps, baseline_weight, baseline_duration,
          next_sets, next_reps, next_weight, next_duration,
          consecutive_failures,
        }
    """
    rx = db.execute(
        '''SELECT movement_pattern, weight_increment, consecutive_failures,
                  current_sets, current_reps, current_weight, current_duration
           FROM current_rx WHERE exercise=?''',
        (exercise,)
    ).fetchone()

    ei = db.execute(
        '''SELECT id, discipline, type, movement_pattern,
                  suggested_volume, weight_increment
           FROM exercise_inventory WHERE exercise=?''',
        (exercise,)
    ).fetchone()
    exercise_id = ei['id'] if ei else None

    if rx:
        movement_pattern = rx['movement_pattern'] or (ei['movement_pattern'] if ei else None)
        weight_increment = rx['weight_increment']
        if weight_increment is None and ei:
            weight_increment = ei['weight_increment']
        consecutive_failures = rx['consecutive_failures'] or 0
        baseline_sets = rx['current_sets']
        baseline_reps = rx['current_reps']
        baseline_weight = rx['current_weight']
        baseline_duration = rx['current_duration']
    else:
        movement_pattern = ei['movement_pattern'] if ei else None
        weight_increment = ei['weight_increment'] if ei else None
        consecutive_failures = 0
        baseline_sets = baseline_reps = baseline_weight = baseline_duration = None

    result = calculate_outcome_from_sets(
        target_sets, target_reps, target_weight, target_duration, sets
    )
    outcome = result['outcome']
    exceeded = result['exceeded_significantly']

    if outcome == 'PROGRESS ↑':
        # Family B: promote any over-target dim to its working value before
        # projecting next, so next is built from what the user actually did.
        new_baseline_sets = result['working_sets'] or target_sets or baseline_sets
        new_baseline_reps = result['working_reps'] or target_reps or baseline_reps
        new_baseline_weight = result['working_weight'] or target_weight or baseline_weight
        new_baseline_duration = result['working_duration'] or target_duration or baseline_duration
        nxt = calculate_next_rx(
            outcome, movement_pattern,
            new_baseline_sets, new_baseline_reps, new_baseline_weight, new_baseline_duration,
            weight_increment=weight_increment,
            consecutive_failures=consecutive_failures,
            exceeded_significantly=exceeded,
        )
        new_failures = nxt['consecutive_failures']
    elif outcome in ('REPEAT →', 'REDUCE ↓'):
        # Baseline doesn't move (until REDUCE crosses the regression threshold,
        # in which case calculate_next_rx returns the regressed next_* and we
        # surface that as the new baseline below).
        nxt = calculate_next_rx(
            outcome, movement_pattern,
            baseline_sets, baseline_reps, baseline_weight, baseline_duration,
            weight_increment=weight_increment,
            consecutive_failures=consecutive_failures,
            exceeded_significantly=False,
        )
        new_failures = nxt['consecutive_failures']
        # If regression fired, new_failures was reset to 0 inside calculate_next_rx
        # AND next_* was lowered. Promote the lowered next to baseline so the
        # user's next session targets the regressed Rx rather than the unchanged one.
        regressed = (
            outcome == 'REDUCE ↓'
            and new_failures == 0
            and (nxt['next_weight'] != baseline_weight
                 or nxt['next_reps'] != baseline_reps
                 or nxt['next_duration'] != baseline_duration)
        )
        if regressed:
            new_baseline_sets = nxt['next_sets'] if nxt['next_sets'] is not None else baseline_sets
            new_baseline_reps = nxt['next_reps'] if nxt['next_reps'] is not None else baseline_reps
            new_baseline_weight = nxt['next_weight'] if nxt['next_weight'] is not None else baseline_weight
            new_baseline_duration = nxt['next_duration'] if nxt['next_duration'] is not None else baseline_duration
            # After regression, project a fresh next from the new baseline
            nxt = {**nxt, **project_next_from_current(
                new_baseline_sets, new_baseline_reps, new_baseline_weight, new_baseline_duration,
                movement_pattern, weight_increment=weight_increment,
            )}
        else:
            new_baseline_sets = baseline_sets
            new_baseline_reps = baseline_reps
            new_baseline_weight = baseline_weight
            new_baseline_duration = baseline_duration
    else:
        # Bootstrap mode: no targets (FIT import without a plan-item match),
        # OR empty sets data. Seed baseline from actuals and project next.
        boot = _bootstrap_baseline(sets)
        new_baseline_sets = boot['sets'] or baseline_sets
        new_baseline_reps = boot['reps'] or baseline_reps
        new_baseline_weight = boot['weight'] or baseline_weight
        new_baseline_duration = boot['duration'] or baseline_duration
        nxt = project_next_from_current(
            new_baseline_sets, new_baseline_reps, new_baseline_weight, new_baseline_duration,
            movement_pattern, weight_increment=weight_increment,
        )
        new_failures = consecutive_failures

    # UPSERT current_rx
    if rx:
        db.execute(
            '''UPDATE current_rx SET
                 exercise_id=?, current_sets=?, current_reps=?, current_weight=?, current_duration=?,
                 last_performed=?, last_outcome=?, consecutive_failures=?,
                 next_sets=?, next_reps=?, next_weight=?, next_duration=?,
                 rx_source=?
               WHERE exercise=?''',
            (exercise_id, new_baseline_sets, new_baseline_reps, new_baseline_weight, new_baseline_duration,
             date, outcome, new_failures,
             nxt['next_sets'], nxt['next_reps'], nxt['next_weight'], nxt['next_duration'],
             rx_source, exercise)
        )
    else:
        discipline = ei['discipline'] if ei else None
        ex_type = ei['type'] if ei else None
        sugg_vol = ei['suggested_volume'] if ei else None
        db.execute(
            '''INSERT INTO current_rx
                 (exercise, exercise_id, discipline, type, movement_pattern,
                  inventory_sugg_volume, current_sets, current_reps, current_weight, current_duration,
                  last_performed, last_outcome, consecutive_failures, weight_increment,
                  next_sets, next_reps, next_weight, next_duration, rx_source)
               VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)''',
            (exercise, exercise_id, discipline, ex_type, movement_pattern,
             sugg_vol, new_baseline_sets, new_baseline_reps, new_baseline_weight, new_baseline_duration,
             date, outcome, new_failures, weight_increment,
             nxt['next_sets'], nxt['next_reps'], nxt['next_weight'], nxt['next_duration'],
             rx_source)
        )

    return {
        'movement_pattern': movement_pattern,
        'exercise_id': exercise_id,
        'outcome': outcome,
        'exceeded_significantly': exceeded,
        'baseline_sets': new_baseline_sets,
        'baseline_reps': new_baseline_reps,
        'baseline_weight': new_baseline_weight,
        'baseline_duration': new_baseline_duration,
        'next_sets': nxt['next_sets'],
        'next_reps': nxt['next_reps'],
        'next_weight': nxt['next_weight'],
        'next_duration': nxt['next_duration'],
        'consecutive_failures': new_failures,
    }
