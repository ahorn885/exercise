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
  - sessions_since_progress: counts non-PROGRESS sessions (REPEAT + REDUCE)
    in a row. Used to surface a deload suggestion at >= DELOAD_THRESHOLD,
    catching plateaus where REPEAT/REDUCE alternate without ever hitting
    3-in-a-row to trigger the regression machinery.
"""

from calculations import (
    calculate_outcome_from_sets,
    calculate_next_rx,
    project_next_from_current,
)
from layer0_progression import progression_pattern
from provider_strength_resolve import resolve_strength_ex_id


DELOAD_THRESHOLD = 5


def _layer0_progression_pattern(db, layer0_exercise_id):
    """Resolve the rx progression key from `layer0.exercises.movement_patterns`
    for an EX-id — the single source of truth (#335 / #430 Slice C), replacing
    the old `exercise_inventory.movement_pattern` name-keyed read.

    Returns the collapsed `PROGRESSION_RULES` key (`progression_pattern()`),
    or None when the EX-id is absent or unknown to layer0, so the caller can
    fall back to the legacy pattern (no regression for un-migrated names).
    """
    if not layer0_exercise_id:
        return None
    row = db.execute(
        '''SELECT movement_patterns FROM layer0.exercises
            WHERE exercise_id=? AND superseded_at IS NULL''',
        (layer0_exercise_id,),
    ).fetchone()
    if row is None:
        return None
    return progression_pattern(list(row['movement_patterns'] or []))


def current_rx(db, user_id, exercise_name):
    """Read the current prescription row for `(user_id, exercise_name)`.

    Returns a dict `{sets, reps, weight_kg, duration_sec, movement_pattern}`
    when a row exists with at least one of weight or duration recorded; None
    otherwise. Track 2 slice 2d wires this into `layer4.rx_wire.apply_current_rx`
    to overwrite synthesizer-emitted `load_prescription` text with the
    deterministic baseline.

    Track 3 dependency (per Layer4_DeterminismFirst_Synthesis_Design_v1.md §7):
    `current_rx.exercise` is the public-catalog exercise name, NOT a layer0
    EX-id. Until Track 3 migrates `current_rx` to layer0 ids, a layer0-only
    exercise (no matching public-catalog name row) returns None and the
    rx_wire step falls through to the first-exposure template.
    """
    row = db.execute(
        '''SELECT current_sets, current_reps, current_weight, current_duration,
                  movement_pattern
             FROM current_rx
            WHERE exercise=? AND user_id=?''',
        (exercise_name, user_id),
    ).fetchone()
    if row is None:
        return None
    weight = row['current_weight']
    duration = row['current_duration']
    if weight is None and duration is None:
        return None
    return {
        'sets': row['current_sets'],
        'reps': row['current_reps'],
        'weight_kg': weight,
        'duration_sec': duration,
        'movement_pattern': row['movement_pattern'],
    }


def current_rx_by_layer0_id(db, user_id, layer0_exercise_id):
    """Read the current prescription row for `(user_id, layer0_exercise_id)`.

    Mirrors `current_rx()` but keys off the **layer0 EX-id** — the single source
    of truth the synthesizer emits on `StrengthExercise.exercise_id` — instead of
    the exercise NAME. The name path could never match the layer0 catalog's
    qualified names ("Back Squat (Barbell)") against the bare logged names
    ("Back Squat"); the EX-id is identical on both sides (#335 Phase 2b).

    Returns the same `{sets, reps, weight_kg, duration_sec, movement_pattern}`
    dict as `current_rx()` when a row exists with at least one of weight or
    duration recorded; None otherwise. `rx_wire.apply_current_rx` calls this
    first, falling back to the name path only for rows not yet backfilled.
    """
    if not layer0_exercise_id:
        return None
    row = db.execute(
        '''SELECT current_sets, current_reps, current_weight, current_duration,
                  movement_pattern
             FROM current_rx
            WHERE layer0_exercise_id=? AND user_id=?''',
        (layer0_exercise_id, user_id),
    ).fetchone()
    if row is None:
        return None
    weight = row['current_weight']
    duration = row['current_duration']
    if weight is None and duration is None:
        return None
    return {
        'sets': row['current_sets'],
        'reps': row['current_reps'],
        'weight_kg': weight,
        'duration_sec': duration,
        'movement_pattern': row['movement_pattern'],
    }


def _bootstrap_baseline(sets):
    """Derive baseline values from a target-less session (FIT bootstrap).

    Conservative: use the min reps/weight/duration the user actually hit on
    every set with non-zero data. That's "the level they hit consistently."
    """
    actual_sets = len(sets)
    reps = [s.get('reps') or 0 for s in sets if (s.get('reps') or 0) > 0]
    wts = [s.get('weight_kg') or 0 for s in sets if (s.get('weight_kg') or 0) > 0]
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
                          rx_source='From Training Log', user_id=None):
    """Compute outcome, project next, UPSERT current_rx, return result for caller.

    Caller uses returned dict to populate the training_log row's outcome /
    next_* / movement_pattern columns. All db writes here are uncommitted —
    caller commits.

    Returns:
        {
          movement_pattern, layer0_exercise_id, match_kind, bucket3,
          outcome, exceeded_significantly,
          baseline_sets, baseline_reps, baseline_weight, baseline_duration,
          next_sets, next_reps, next_weight, next_duration,
          consecutive_failures,
        }

    The public `exercise_inventory.id` FK was retired here (#430 Slice C): the
    per-user tables key off the layer0 EX-id, and the catalog is read by name
    only for the denormalized display fields (discipline/type/suggested_volume).
    """
    # Scope by user_id so each user keeps their own prescription. Until Session
    # 2D replaces UNIQUE(exercise) with UNIQUE(user_id, exercise), a second
    # user's first INSERT for a seeded exercise can still hit the unique
    # constraint — that's the gating UNIQUE debt 2D resolves.
    rx = db.execute(
        '''SELECT movement_pattern, weight_increment, consecutive_failures,
                  sessions_since_progress, layer0_exercise_id,
                  current_sets, current_reps, current_weight, current_duration
           FROM current_rx WHERE exercise=? AND user_id=?''',
        (exercise, user_id)
    ).fetchone()

    # Display/progression now source from layer0 (the single canonical catalog),
    # keyed off the EX-id resolved below — the v1 exercise_inventory by-name read
    # is retired (catalog unification). The vestigial current_rx discipline/type/
    # inventory_sugg_volume columns are no longer stamped (dropped in the table-
    # drop slice); movement_pattern comes from the layer0 crosswalk.

    # #430 Slice C + #679 — key the progression off the layer0 EX-id (single
    # source of truth), not the v1 exercise_inventory name. Prefer the row's
    # already-backfilled EX-id; otherwise resolve the logged NAME through the
    # #679 chain (alias → coarse category-collapse → bucket-3). `match_kind`
    # records which step resolved it; `bucket3` (EX-id None) is the explicit
    # record-don't-drop state that replaces the ambiguous "first exposure"
    # rendering for Garmin lifts with no canonical home.
    # `movement_patterns` from layer0 collapses to the rx progression key via the
    # crosswalk; falls back to the legacy denormalized/exercise_inventory pattern
    # only when no EX-id resolves (un-migrated name → status quo, no regression).
    row_ex_id = rx['layer0_exercise_id'] if rx else None
    if row_ex_id:
        layer0_exercise_id, match_kind = row_ex_id, 'existing'
    else:
        layer0_exercise_id, match_kind = resolve_strength_ex_id(exercise)
    layer0_pattern = _layer0_progression_pattern(db, layer0_exercise_id)

    # weight_increment: layer0 carries no per-exercise increment (#335 D4). Keep
    # only the per-user current_rx override; None falls through to calculations'
    # actual-weight runtime rule then the pattern default.
    if rx:
        movement_pattern = layer0_pattern or rx['movement_pattern']
        weight_increment = rx['weight_increment']
        consecutive_failures = rx['consecutive_failures'] or 0
        sessions_since_progress = rx['sessions_since_progress'] or 0
        baseline_sets = rx['current_sets']
        baseline_reps = rx['current_reps']
        baseline_weight = rx['current_weight']
        baseline_duration = rx['current_duration']
    else:
        movement_pattern = layer0_pattern
        weight_increment = None
        consecutive_failures = 0
        sessions_since_progress = 0
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

    # Plateau counter — independent from consecutive_failures (which only
    # counts REDUCEs). Resets on PROGRESS, increments on REPEAT or REDUCE.
    # Bootstrap (outcome is None) leaves it alone — a target-less FIT import
    # is neither a win nor a stall.
    if outcome == 'PROGRESS ↑':
        new_sessions_since_progress = 0
    elif outcome in ('REPEAT →', 'REDUCE ↓'):
        new_sessions_since_progress = sessions_since_progress + 1
    else:
        new_sessions_since_progress = sessions_since_progress

    # UPSERT current_rx. layer0_exercise_id is written on every path so a
    # newly-logged exercise self-heals its EX-id (#430 Slice C) — the #335
    # backfill was a one-time snapshot; without this the write path would keep
    # minting NULL-EX-id rows invisible to the rx_wire EX-id lookup.
    if rx:
        db.execute(
            '''UPDATE current_rx SET
                 layer0_exercise_id=COALESCE(layer0_exercise_id, ?),
                 movement_pattern=?,
                 current_sets=?, current_reps=?, current_weight=?, current_duration=?,
                 last_performed=?, last_outcome=?, consecutive_failures=?, sessions_since_progress=?,
                 next_sets=?, next_reps=?, next_weight=?, next_duration=?,
                 rx_source=?
               WHERE exercise=? AND user_id=?''',
            (layer0_exercise_id, movement_pattern,
             new_baseline_sets, new_baseline_reps, new_baseline_weight, new_baseline_duration,
             date, outcome, new_failures, new_sessions_since_progress,
             nxt['next_sets'], nxt['next_reps'], nxt['next_weight'], nxt['next_duration'],
             rx_source, exercise, user_id)
        )
    else:
        # The denormalized discipline/type/inventory_sugg_volume columns are
        # vestigial (dropped in the table-drop slice) — no longer sourced from
        # the retired v1 catalog. Display reads off the layer0 EX-id now.
        discipline = ex_type = sugg_vol = None
        db.execute(
            '''INSERT INTO current_rx
                 (exercise, layer0_exercise_id, discipline, type, movement_pattern,
                  inventory_sugg_volume, current_sets, current_reps, current_weight, current_duration,
                  last_performed, last_outcome, consecutive_failures, sessions_since_progress,
                  weight_increment,
                  next_sets, next_reps, next_weight, next_duration, rx_source, user_id)
               VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)''',
            (exercise, layer0_exercise_id, discipline, ex_type, movement_pattern,
             sugg_vol, new_baseline_sets, new_baseline_reps, new_baseline_weight, new_baseline_duration,
             date, outcome, new_failures, new_sessions_since_progress, weight_increment,
             nxt['next_sets'], nxt['next_reps'], nxt['next_weight'], nxt['next_duration'],
             rx_source, user_id)
        )

    # Rule #15 — log the EX-id resolution (which name, which #679 step, resolved
    # EX-id or bucket-3) + chosen progression key so a wrong resolution or
    # progression in prod is diagnosable from /admin/logs alone. `match_kind` is
    # the #679 step (existing/alias/category/bucket3); `bucket3` flags the
    # record-don't-drop case; `layer0=y` means the progression key came from
    # layer0 movement_patterns, `n` the legacy fallback (un-migrated name).
    print(
        f"rx_engine.apply_session_outcome: user={user_id} exercise={exercise!r} "
        f"ex_id={layer0_exercise_id} match_kind={match_kind} "
        f"bucket3={layer0_exercise_id is None} progression={movement_pattern} "
        f"layer0={'y' if layer0_pattern is not None else 'n'} outcome={outcome}"
    )

    return {
        'movement_pattern': movement_pattern,
        'layer0_exercise_id': layer0_exercise_id,
        # #679 — resolution provenance for the completed-history record. `bucket3`
        # marks "logged, not prescribed" (no canonical EX-id); a later wave
        # surfaces it inline instead of as an ambiguous first-exposure row.
        'match_kind': match_kind,
        'bucket3': layer0_exercise_id is None,
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
        'sessions_since_progress': new_sessions_since_progress,
        'deload_suggested': new_sessions_since_progress >= DELOAD_THRESHOLD,
    }
