# `rx_engine` progression algorithm — spec

This document captures the strength-training progression algorithm
implemented in `calculations.py` and `rx_engine.py` precisely enough
to reimplement from scratch in another language. Pair with
`DATABASE.md` for table layouts; this doc references those tables and
columns by exact name.

The engine has one entry point — `apply_session_outcome` — that takes
a logged session and writes back to `current_rx`, returning a result
the caller uses to populate a `training_log` row. Three secondary
helpers (`project_next_from_current`, `compute_deload_baseline`, and
the manual-edit path) round it out.

---

## 1. Inputs and outputs

### `apply_session_outcome` inputs

| Argument | Type | Source | Notes |
| :--- | :--- | :--- | :--- |
| `db` | DB handle | caller | Writes are not committed; caller commits. |
| `exercise` | string | `exercise_inventory.exercise` | Denormalized name — UNIQUE in catalog and on `(user_id, exercise)` in `current_rx`. |
| `date` | ISO date | caller | Used to set `current_rx.last_performed`. |
| `sets` | list of `{reps, weight_lbs, duration_sec}` | per-set actuals | One element per set. Each field can be NULL/0/missing. |
| `target_sets` | int or NULL | plan / form / NULL on FIT bootstrap | |
| `target_reps` | int or NULL | plan / form | |
| `target_weight` | float or NULL | plan / form | Pounds. |
| `target_duration` | int or NULL | plan / form | Seconds. |
| `rx_source` | string | caller | Stored on `current_rx.rx_source` for provenance. Conventional values: `'From Training Log'`, `'From FIT Import'`, `'Manual override'`, `'Auto-deload'`. |
| `user_id` | int | session | Scopes every read/write. |

### What it writes

- **`current_rx`** — UPSERT scoped on `(user_id, exercise)`:
  `current_sets`, `current_reps`, `current_weight`, `current_duration`
  (the prescribed baseline), `next_sets`, `next_reps`, `next_weight`,
  `next_duration` (the projection for the next session),
  `last_performed`, `last_outcome`, `consecutive_failures`,
  `sessions_since_progress`, `rx_source`. On INSERT also copies
  `discipline`, `type`, `movement_pattern`, `inventory_sugg_volume`,
  `weight_increment` from `exercise_inventory`.
- **Caller separately writes** the `training_log` row (with the
  returned `outcome`, `movement_pattern`, `next_*` from this
  function) and the per-set rows in `training_log_sets`.

### Returned dict

```
{
  movement_pattern, exercise_id,
  outcome,                  # 'PROGRESS ↑' | 'REPEAT →' | 'REDUCE ↓' | None
  exceeded_significantly,   # bool — Family-A trigger fired
  baseline_sets, baseline_reps, baseline_weight, baseline_duration,
  next_sets, next_reps, next_weight, next_duration,
  consecutive_failures,
  sessions_since_progress,
  deload_suggested,         # bool: sessions_since_progress >= DELOAD_THRESHOLD
}
```

### Outcome string values (canonical)

The engine emits and stores **exactly** these three strings (the
arrows are part of the value):

```
'PROGRESS ↑'   'REPEAT →'   'REDUCE ↓'
```

A fourth state — `None` — is returned in **bootstrap mode** (no
targets, or empty `sets`); see §11. Note that `DATABASE.md` describes
the column as `{PROGRESS, REPEAT, FAIL}` — that's a paraphrase. The
column literally holds the arrowed strings (and NULL on bootstrap).

---

## 2. Outcome computation

Implemented in `calculate_outcome_from_sets(target_sets, target_reps,
target_weight, target_duration, sets_data)`.

### 2.1 Empty / no-target short circuit

- If `sets_data` is empty → return all-None (bootstrap-style result).
- If `target_sets`, `target_reps`, `target_weight`, and
  `target_duration` are all falsy → return all-None. The caller
  (bootstrap path) takes over.

### 2.2 Mode selection

```
duration_mode = (target_duration > 0) AND (target_reps is falsy)
```

Duration mode applies to time-based exercises (planks, carries,
holds, isometrics). Otherwise the engine is in rep mode (every set is
judged on reps and optional weight).

### 2.3 Per-set pass test

```
def set_passed(s):
    reps      = s.reps      or 0
    weight    = s.weight    or 0
    duration  = s.duration  or 0
    if duration_mode:
        return duration >= target_duration
    rep_ok    = (reps   >= target_reps)   if target_reps   else True
    weight_ok = (weight >= target_weight) if target_weight else True
    return rep_ok and weight_ok
```

Missing target dimensions are treated as "no requirement on this
dimension" (return True). Missing actual values count as 0.

### 2.4 PROGRESS test

```
all_passed = every(s in sets_data : set_passed(s))
if target_sets and len(sets_data) < target_sets:
    all_passed = False
```

If `all_passed` → outcome is `'PROGRESS ↑'`.

### 2.5 REPEAT vs REDUCE — volume ratio

When at least one set failed:

```
if duration_mode:
    target_vol = (target_sets or 1) * target_duration
    actual_vol = sum(s.duration or 0 for s in sets_data)
else:
    # Bodyweight fallback: a missing/zero target_weight contributes 1
    # so the ratio reduces to "fraction of target reps completed".
    target_vol = (target_sets or 1) * (target_reps or 1) * (target_weight or 1)
    actual_vol = sum((s.reps or 0) * ((s.weight or 0) or 1)
                     for s in sets_data)

ratio = actual_vol / target_vol  if target_vol > 0 else 0
outcome = 'REPEAT →'  if ratio >= 0.75 else 'REDUCE ↓'
```

The **0.75 threshold** is the constant: ≥ 75% of total target
volume → REPEAT; below → REDUCE.

---

## 3. Family A vs Family B

These are not stored attributes — they are **two parallel rules** that
both apply on every PROGRESS outcome. Every exercise is implicitly
both: Family A modifies the projection (the kicker), Family B may
modify the baseline (working-value promotion).

### 3.1 Family A — "exceeded significantly" 2× kicker

If the user blew through the prescription, push the next session
harder than a normal increment.

### 3.2 Family B — baseline promotion

If the user did better than prescribed on a dimension across multiple
sets, treat their actual achievement as the new baseline for that
dimension before projecting next.

### 3.3 Movement-pattern table

Each exercise is classified by `exercise_inventory.movement_pattern`,
which selects an entry from the `PROGRESSION_RULES` table:

| Pattern        | weight_incr (lb) | rep_incr | duration_incr (s) | regression_threshold |
| :--- | ---: | ---: | ---: | ---: |
| `Squat`        | 5    | 0 | 0 | 3 |
| `Hinge`        | 5    | 0 | 0 | 3 |
| `Lunge`        | 5    | 0 | 0 | 3 |
| `Push`         | 5    | 1 | 0 | 3 |
| `Pull`         | 5    | 1 | 0 | 3 |
| `Core`         | 0    | 2 | 5 | 3 |
| `Carry`        | 5    | 0 | 0 | 3 |
| `Rotation`     | 2.5  | 0 | 0 | 3 |
| `Plyo`         | 0    | 0 | 0 | 3  *(progresses by adding sets)* |
| `Balance`      | 0    | 0 | 5 | 3 |
| `Various`      | 2.5  | 1 | 5 | 3  *(also the fallback for unrecognized patterns)* |
| `Complex`      | 5    | 0 | 0 | 3 |
| `Conditioning` | 0    | 0 | 5 | 3 |
| `Grip`         | 0    | 2 | 5 | 3 |
| `Locomotion`   | 0    | 0 | 5 | 3 |
| `Mobility`     | 0    | 0 | 5 | 3 |

If `movement_pattern` is missing or unrecognized, fall back to the
`Various` row.

### 3.4 Weight-increment resolution

The `weight_incr` column above is a static fallback. Actual increment
is resolved at progression time:

```
def resolve_weight_increment(per_exercise_override, actual_weight, pattern_default):
    if per_exercise_override is not None:
        return per_exercise_override          # exercise_inventory.weight_increment
    if actual_weight is not None:
        return 2.5 if actual_weight < 15 else 5.0
    return pattern_default
```

`per_exercise_override` is resolved from the database before being
passed in: `current_rx.weight_increment` is checked first (per-user,
per-exercise override stored on the Rx row). If that is NULL, fall
back to `exercise_inventory.weight_increment` (catalog-level default
override). If both are NULL, the runtime rule (`< 15 lb` → 2.5,
`>= 15 lb` → 5.0) takes over, with the pattern default as the final
fallback when `actual_weight` is also unavailable. The runtime rule
(2.5 lb under 15 lb,
5 lb at/above) handles light kettlebells/dumbbells with micro-plate
loading vs. standard plate-loading.

---

## 4. The Family-A 2× kicker — significance

### 4.1 Significance triggers

Computed from the same `sets_data` even on a PROGRESS outcome:

```
rep_threshold      = ceil(target_reps     * 1.10)   if target_reps     else None
duration_threshold = ceil(target_duration * 1.10)   if target_duration else None

sets_over_rep_pct = count of sets where (reps or 0) >= rep_threshold
                                          (0 if rep_threshold is None)

sets_over_dur_pct = count of sets where (duration or 0) >= duration_threshold
                                          (0 if duration_threshold is None)

# "Qualifying extras": sets logged BEYOND target_sets that themselves passed.
qualifying_extras = 0
if target_sets and len(sets_data) > target_sets:
    for s in sets_data[target_sets:]:
        if set_passed(s):  # same predicate as §2.3
            qualifying_extras += 1

exceeded_significantly = (
    sets_over_rep_pct >= 2
    or sets_over_dur_pct >= 2
    or qualifying_extras >= 1
)
```

The **1.10 (10%-over) and the count-of-2** are the constants. A
single PR-rep set doesn't fire significance — needs to be repeated
(or one bonus set beyond the prescription).

### 4.2 What the kicker does

In `calculate_next_rx` on a PROGRESS outcome, the next-session bump
is determined by movement-pattern dimension priority (see §8). The
kicker modifies whichever dimension is being bumped:

```
if dimension is weight:
    bump = (w_increment * 2)  if exceeded_significantly else w_increment
elif dimension is reps:
    normal = current_reps + r_increment
    bump   = max(normal, ceil(current_reps * 1.10))   if exceeded_significantly else normal
elif dimension is duration:
    normal = current_duration + d_increment
    bump   = max(normal, ceil(current_duration * 1.10)) if exceeded_significantly else normal
```

For weight the kicker doubles the increment. For reps/duration it
is `max(normal_increment, +10% rounded up)` — so the kicker can never
*shrink* the bump below normal. Only one dimension is bumped per
session.

The kicker does **not** apply to the Plyo pattern (which progresses
by adding a set rather than by bumping a numeric dimension). Sets
just go from N → N+1.

---

## 5. Family-B baseline promotion

On a PROGRESS outcome, before projecting the next session, the
baseline is promoted to "the level the user actually achieved on
multiple sets" — the `working_*` values:

```
def working_dim(target, key):
    if not target:
        return None
    over_target = [s[key] or 0 for s in sets_data if (s[key] or 0) > target]
    return min(over_target) if len(over_target) >= 2 else None

working_weight   = working_dim(target_weight,   'weight_lbs')
working_reps     = working_dim(target_reps,     'reps')
working_duration = working_dim(target_duration, 'duration_sec')

working_sets = (target_sets + qualifying_extras)  if qualifying_extras else None
```

The conservative `min(...)` is intentional: if the user did three
sets at 8/10/9 reps over a target of 7, the new baseline is 8 (the
floor of what they hit twice), not 9 or 10. "The level they hit
twice."

The promotion is applied per-dimension when calculating the new
baseline that gets stored on `current_rx` and used as input to the
next-session projection:

```
new_baseline_sets     = working_sets     or target_sets     or current_baseline_sets
new_baseline_reps     = working_reps     or target_reps     or current_baseline_reps
new_baseline_weight   = working_weight   or target_weight   or current_baseline_weight
new_baseline_duration = working_duration or target_duration or current_baseline_duration
```

Falsy → falsy → falsy precedence: a working value wins; otherwise
the prescribed target is taken (so the baseline at least catches up
to the plan); otherwise the previous baseline is preserved.

On **REPEAT** and isolated **REDUCE**, baselines do **not** move
(the baseline is the "prescribed" Rx, not the last performance).
On **REDUCE that triggers regression**, the new baseline is the
regressed value — see §7.

---

## 6. Counter logic

Two independent counters live on `current_rx`:

### 6.1 `consecutive_failures` — strictly consecutive REDUCEs

```
PROGRESS  → 0
REPEAT    → 0   ← important: REPEAT resets, doesn't freeze
REDUCE    → consecutive_failures + 1
              (when this reaches the regression_threshold, regression
              fires and the counter resets to 0)
```

The "REPEAT resets to 0" rule is explicit: REPEAT was originally
considered a freeze (counter unchanged), but the current behavior is
to **reset** so the user gets plateau tolerance. A user who alternates
REPEAT and REDUCE never accumulates enough failures to regress on
this counter alone — that's why the second counter (§6.2) exists.

### 6.2 `sessions_since_progress` — plateau detector

```
PROGRESS         → 0
REPEAT or REDUCE → sessions_since_progress + 1
None (bootstrap) → sessions_since_progress (unchanged)
```

Used to surface a deload suggestion when
`sessions_since_progress >= DELOAD_THRESHOLD` (constant: **5**). The
deload itself does not auto-fire; the user clicks the deload button
on `/rx`, or the coaching context surfaces it as a flag.

### 6.3 What's stored vs. what's returned

`apply_session_outcome` writes both counters to `current_rx` and
returns them in its result dict, plus a derived
`deload_suggested = sessions_since_progress >= DELOAD_THRESHOLD`.

---

## 7. Deload — trigger and baseline

Deload is **not auto-fired** by the engine. It's a manual one-click
operation invoked from the `/rx` UI, but the math lives in
`compute_deload_baseline` and is reused by `apply_session_outcome`'s
regression path under the hood.

### 7.1 `compute_deload_baseline(current_*, movement_pattern, weight_increment, pct=0.10)`

Drops the **primary** progression dimension by `pct` (default 10%).
Mirrors the §8 dimension priority so the dimension we deload is the
one progression would have touched.

```
if movement_pattern == 'Plyo' and current_sets:
    new_sets = max(1, current_sets - 1)

elif current_weight:
    w_inc  = resolve_weight_increment(...) or 5.0   # safety floor
    target = current_weight * (1 - pct)
    # Round DOWN to a multiple of the increment so a 5-lb deload of
    # a 100-lb load lands at 95, not back at 100.
    new_weight = max(w_inc, floor(target / w_inc) * w_inc)

elif current_reps:
    drop = max(1, round(current_reps * pct))
    new_reps = max(1, current_reps - drop)

elif current_duration:
    target = current_duration * (1 - pct)
    new_duration = max(5, round(target / 5) * 5)    # round to nearest 5s, floor 5s

else:
    no-op
```

Returns `{sets, reps, weight, duration}`. Caller is responsible for
re-projecting `next_*` from the deloaded baseline.

### 7.2 The /rx deload-button workflow

When the operator clicks deload on `/rx/<id>/deload`:

1. Look up the `current_rx` row.
2. `deloaded = compute_deload_baseline(current_*, movement_pattern, weight_increment)`.
3. `next = project_next_from_current(deloaded.*, movement_pattern, weight_increment)`.
4. UPDATE `current_rx`:
   - `current_sets, current_reps, current_weight, current_duration` ← `deloaded.*`
   - `next_sets, next_reps, next_weight, next_duration` ← `next.*`
   - `consecutive_failures = 0`
   - `sessions_since_progress = 0`
   - `rx_source = 'Auto-deload'`

Both counters reset — the deload starts a fresh window.

### 7.3 Auto-regression (different from deload)

When `consecutive_failures >= regression_threshold` (always 3) on a
REDUCE outcome, `calculate_next_rx` regresses by **one increment** on
the primary dimension instead of bumping. This happens inside the
normal session-write path, not via the deload route:

```
# inside calculate_next_rx, on REDUCE with new_failures >= threshold:
if w_inc and current_weight and current_weight > w_inc:
    next_weight = current_weight - w_inc
elif d_inc and current_duration and current_duration > d_inc:
    next_duration = current_duration - d_inc
elif r_inc and current_reps and current_reps > r_inc:
    next_reps = current_reps - r_inc
new_failures = 0     # fresh window at the lower target
```

Note the dimension priority on regression is **weight → duration →
reps**, which differs slightly from the progression priority (weight
→ reps → duration; see §8). This is preserved verbatim from the
code; rationale not captured in code.

When regression fires, `apply_session_outcome` then *promotes the
regressed `next_*` into the new baseline* and re-projects `next_*`
from there (single-step `project_next_from_current`), so the user's
upcoming target is the lower level + one increment (i.e. back to
where they were, ready to retry the bump).

---

## 8. Next-session projection

### 8.1 `calculate_next_rx` — used after a real session

Called from `apply_session_outcome` with the post-Family-B baseline.
Behavior depends on outcome:

- **PROGRESS:**
  Pick one dimension to bump in priority order (first match wins):
  1. `Plyo` pattern → `next_sets = (current_sets or 1) + 1`. (No
     other dimension touched. Kicker does not apply.)
  2. Else if `w_inc > 0` AND `current_weight` truthy →
     `next_weight = current_weight + (w_inc * 2 if exceeded else w_inc)`.
  3. Else if `r_inc > 0` AND `current_reps` truthy →
     `next_reps = current_reps + r_inc`, possibly kicked to
     `ceil(current_reps * 1.10)` (whichever is larger).
  4. Else if `d_inc > 0` AND `current_duration` truthy →
     analogous to reps with the 10% kicker option.
  5. Else: no change.
  Reset `consecutive_failures` to 0.

- **REPEAT:**
  Reset `consecutive_failures` to 0. No `next_*` change.

- **REDUCE:**
  Increment `consecutive_failures`. If threshold met → regress (§7.3)
  and reset failures. Otherwise no `next_*` change.

### 8.2 `project_next_from_current` — used outside session writes

Same dimension-priority logic as PROGRESS but **always one normal
increment** (no kicker) and **no failure-counter mutation**. Used by:

- **Manual edits to `current_rx`** (`/rx/<id>/edit`): user changes the
  baseline; engine re-derives `next_*` so the prescription doesn't
  go stale.
- **FIT bootstrap** (§11): no prior baseline to derive from, just
  one tick up from what the user did.
- **Post-deload re-projection** (§7.2 step 3, §7.3 follow-up).

```
# Same dimension priority as PROGRESS, no kicker:
if movement_pattern == 'Plyo':
    next_sets = (current_sets or 1) + 1
elif w_inc and current_weight:
    next_weight = current_weight + w_inc
elif r_inc and current_reps:
    next_reps = current_reps + r_inc
elif d_inc and current_duration:
    next_duration = current_duration + d_inc
```

Returns `{next_sets, next_reps, next_weight, next_duration}`.

---

## 9. Per-set storage and aggregation

### 9.1 `training_log_sets` — per-set fact rows

Columns (per `DATABASE.md`): `id`, `user_id`, `training_log_id` (FK
with `ON DELETE CASCADE` to `training_log`), `set_number`, `reps`,
`weight_lbs`, `duration_sec`. One row per set within a `training_log`
entry. Cascade delete is the **only** cascade in the schema —
deleting the parent `training_log` row drops its sets without
explicit DELETE.

### 9.2 Aggregation up to `training_log`

The route that wraps `apply_session_outcome` derives aggregate values
for the `training_log` row from the per-set list. Convention used by
both `routes/training.py` and `routes/garmin.py`:

| `training_log` column | Derivation from `sets` list |
| :--- | :--- |
| `actual_sets`     | `len(sets)` |
| `actual_reps`     | `sets[-1].reps` (last set's reps; representative for the typical "did N sets of X" log) |
| `actual_weight`   | `max(s.weight_lbs or 0 for s in sets)`, then `0 → NULL` |
| `actual_duration` | `sets[-1].duration_sec` (last set's duration) |
| `volume`          | `sum((s.reps or 0) * (s.weight_lbs or 0) for s in sets)`, then `0 → NULL` |
| `est_1rm`         | `max(epley_1rm(s.weight_lbs, s.reps) or 0 for s in sets)`, then `0 → NULL` |
| `body_weight`     | most-recent `body_metrics.weight_lbs` for the user (lookup at write time) |
| `outcome`         | from `apply_session_outcome` result |
| `next_*`          | from `apply_session_outcome` result |
| `target_*`        | input from form / plan item (preserved verbatim) |
| `movement_pattern`| from `apply_session_outcome` result (alias `sub_group` in legacy column) |
| `exercise_id`     | from `apply_session_outcome` result |

### 9.3 Epley 1RM

```
def epley_1rm(weight, reps):
    if not weight or not reps or weight <= 0 or reps <= 0:
        return None
    if reps == 1:
        return round(weight, 1)
    return round(weight * (1 + reps / 30.0), 1)
```

(Used for the `est_1rm` column only; not part of the progression
math.)

### 9.4 Aggregate-snapshot edit form

The single-entry edit form on `/training/<id>/edit` doesn't have
per-set data — it has a single tuple `(actual_sets, actual_reps,
actual_weight, actual_duration)`. The engine entry path **synthesizes**
N=`actual_sets` identical sets and feeds those to
`apply_session_outcome`:

```
synthesized = [
    {reps: actual_reps, weight_lbs: actual_weight, duration_sec: actual_duration}
    for _ in range(actual_sets or 1)
]
```

Consequence: significance triggers (which depend on per-set variance,
e.g. "2+ sets at >=10% over reps") will fire only if the single
aggregate value itself meets the threshold. Family-B promotion behaves
similarly — the working value derives from a uniform list, so any
over-target dimension is at the same value across all synthesized
sets.

A legacy helper `calculate_outcome(target_sets, target_reps,
target_duration, actual_sets, actual_reps, actual_duration)` exists
in `calculations.py` for the aggregate-snapshot path's own use, but
is no longer the engine's outcome computation — the synthesized-sets
path runs through `calculate_outcome_from_sets` like the per-set
flows.

---

## 10. UPSERT semantics and concurrency

### 10.1 The UNIQUE constraint

`current_rx` has `UNIQUE (user_id, exercise)`. The engine UPSERTs by:

1. `SELECT ... FROM current_rx WHERE exercise = ? AND user_id = ?`
2. If found → `UPDATE`.
3. Else → `INSERT`, copying static fields (`discipline`, `type`,
   `movement_pattern`, `inventory_sugg_volume`, `weight_increment`)
   from the matching `exercise_inventory` row.

A new `current_rx` row is created on demand if the exercise has been
seeded in the catalog but no row exists yet for this user (e.g. a
brand-new user logs an unfamiliar exercise via FIT import).

### 10.2 Concurrency

**The engine does no concurrency control.** Reads and writes are not
atomic against simultaneous writers. The pattern relies on:

- The two route entry points each running in a single Flask request
  (uncommitted writes; caller commits the transaction).
- The session being naturally serialized per-user.

Two simultaneous writes for the same `(user_id, exercise)` could
race; the second `INSERT` would hit the UNIQUE constraint and the
caller's transaction would fail. No automatic retry.

### 10.3 Caller commits

`apply_session_outcome` does not call `db.commit()`. The caller wraps
the engine call, the `training_log` insert, the `training_log_sets`
inserts, and the optional `plan_items.status = 'completed'` update
in one transaction.

---

## 11. Bootstrap mode (FIT import / first-time exercise)

Triggered when **all targets are missing** AND/OR **`sets` is
empty** — i.e. `outcome` from `calculate_outcome_from_sets` is `None`.

In this state the engine derives a baseline directly from actuals
rather than computing PROGRESS/REPEAT/REDUCE.

### 11.1 `_bootstrap_baseline(sets)` derivation

```
def bootstrap_baseline(sets):
    return {
        sets:      len(sets) or None,
        reps:      min(non-zero reps in sets)            or None,
        weight:    min(non-zero weight_lbs in sets)      or None,
        duration:  min(non-zero duration_sec in sets)    or None,
    }
```

The `min(...)` is conservative — "the level they hit on every
qualifying set" — same philosophy as Family-B promotion. Sets with
zero/missing values for a dimension are excluded from that
dimension's min so a single zero doesn't drag the baseline down.

### 11.2 Bootstrap outcome resolution

```
new_baseline_sets     = bootstrapped.sets     or existing_baseline_sets
new_baseline_reps     = bootstrapped.reps     or existing_baseline_reps
new_baseline_weight   = bootstrapped.weight   or existing_baseline_weight
new_baseline_duration = bootstrapped.duration or existing_baseline_duration

next = project_next_from_current(new_baseline_*, movement_pattern, weight_increment)

new_failures               = consecutive_failures        # unchanged
new_sessions_since_progress = sessions_since_progress    # unchanged
outcome stored on current_rx.last_outcome = None / NULL
```

The counters do **not** advance — a target-less FIT import is
neither a win nor a stall, so it can't be a plateau session and
isn't a regression candidate.

### 11.3 New `current_rx` row creation under bootstrap

If no `current_rx` row exists yet for `(user_id, exercise)`, the
INSERT path runs with the bootstrapped baseline as `current_*` and
the projected `next_*`. Static fields (`discipline`, `type`,
`movement_pattern`, `inventory_sugg_volume`, `weight_increment`) come
from `exercise_inventory`. If the exercise is also missing from
`exercise_inventory`, those fields are NULL and the row is still
created — `movement_pattern` will be NULL, which routes the
progression rules through the `Various` fallback on the next session.

---

## 12. Edge cases

### 12.1 Missing or zero values in a logged set

- `reps`, `weight_lbs`, `duration_sec` are each independently
  nullable. Missing → treated as 0 in the per-set predicate.
- A set with zero reps on a rep-mode exercise contributes 0 to
  actual volume but still counts toward `len(sets)`. PROGRESS
  becomes impossible (a 0-rep set fails the per-set predicate
  unless `target_reps` is also missing).
- A set with `duration_sec > 0` but no `reps` on a duration-mode
  exercise (target_duration set, target_reps falsy) is judged on
  the duration alone.
- Bodyweight rep work (`target_weight = 0` or NULL): the per-set
  predicate's weight check is skipped, and the volume formula's
  weight factor is replaced by 1 (so the ratio reduces to a
  rep-count fraction).

### 12.2 Partial sets (fewer logged than `target_sets`)

`all_passed` is forced to false when `len(sets) < target_sets`,
regardless of whether each logged set passed. The volume ratio still
runs against `target_sets * target_<dim>` (full prescription), so
under-completion typically lands as REDUCE.

### 12.3 Zero-rep / weight-only / weight-and-reps records

- A set logged with weight only and 0 reps → counts as a failed set
  in rep mode (reps < target). Contributes 0 to actual volume.
- A set logged with reps only and 0 weight on a weighted exercise →
  fails the weight check (unless `target_weight` is missing/0). On
  a bodyweight exercise (`target_weight` is missing/0) the weight
  check is skipped.

### 12.4 Duration-based with no weight or reps

Duration mode applies. Only `duration_sec` is checked per set;
`reps` and `weight_lbs` are ignored for outcome computation
(though they're still stored in `training_log_sets` if provided).

### 12.5 Manual edits via `/rx/<id>/edit` (bypass outcome computation)

The manual-edit form does **not** call `apply_session_outcome`. It:

1. Updates `current_*` from form values.
2. Re-projects `next_*` via `project_next_from_current` so the
   prescription doesn't go stale.
3. Optionally resets `consecutive_failures` (if `reset_failures`
   checkbox is set) and/or `sessions_since_progress` (if
   `reset_plateau` checkbox is set). Otherwise both are preserved at
   their prior values, **except** `consecutive_failures` which the
   form reads explicitly from a numeric field — operator can edit
   the count directly.
4. Sets `rx_source = 'Manual override'`.

No `training_log` row is written for a manual edit; this path is
purely Rx-tuning, not session logging.

### 12.6 Manual deload (`/rx/<id>/deload`) vs auto-regression

- **Manual deload** (§7.2): -10% on the primary dimension; resets
  *both* counters to 0; sets `rx_source = 'Auto-deload'`. No
  outcome computation. No `training_log` row.
- **Auto-regression** (§7.3): triggered inside `calculate_next_rx`
  on a REDUCE that pushes `consecutive_failures` to the threshold
  (always 3); regresses by *one increment* (not 10%) on the primary
  dimension; resets only `consecutive_failures`. The
  `sessions_since_progress` counter still ticks (REDUCE bumps it
  +1), so accumulated plateau pressure persists across regressions.

### 12.7 NLP entry path (`routes/natural_log.py`) — caveat

The NLP-entry POST (`/log-natural/save`) inserts `training_log` and
`training_log_sets` rows directly **without calling
`apply_session_outcome`**. Consequence:

- The new `training_log` row has `outcome = NULL`,
  `target_* = NULL`, `next_* = NULL`.
- `current_rx` is **not** updated. `last_performed`, baseline,
  `next_*`, and both counters stay at whatever the last
  engine-mediated session set them to.

This means an NLP-only logger's `current_rx` will drift out of
sync with their actual training. Reimplementations should decide
whether this is the intended behavior (NLP entries as
journal-only) or a divergence that needs unification with the
engine path.

(`DATABASE.md` says "NLP edits flow through `rx_engine`" — that's
inaccurate; the code does not. Code is the source of truth.)

### 12.8 FIT import without targets

The FIT import (`routes/garmin.py`) **never** passes targets to
`apply_session_outcome` — even when the import is matched to a
plan item, the matcher records the disposition but doesn't pull
prescription targets from the plan. So every FIT-imported strength
session runs in **bootstrap mode** (§11). Counters don't advance,
outcome is NULL, and the baseline updates only from
above-existing-baseline actuals.

### 12.9 New exercises absent from `exercise_inventory`

If `exercise` doesn't match any row in `exercise_inventory`,
`exercise_id` stays NULL, `movement_pattern` is NULL, and
progression rules fall back to the `Various` table row. The
`current_rx` INSERT still succeeds (no FK requires the inventory
row).

### 12.10 Outcome `None` round-trips to NULL

A bootstrap-mode session writes `last_outcome = NULL` on
`current_rx` and `outcome = NULL` on `training_log`. Downstream
consumers (coaching context, dashboard) must tolerate NULL
outcomes alongside the three string values.

### 12.11 The `'REDUCE ↓'` outcome that *isn't* a regression

A normal REDUCE — one without `consecutive_failures` reaching the
threshold — leaves `current_*` and `next_*` unchanged. The user's
next session targets the same prescription they just under-hit.
This is by design ("baseline doesn't move until we're sure it's
not a one-off"), and is the reason `sessions_since_progress`
exists as a separate plateau detector.

---

## Constants — at-a-glance

| Constant | Value | Where applied |
| :--- | :--- | :--- |
| Volume threshold for REPEAT vs REDUCE | **0.75** | §2.5 |
| Significance — sets-over multiplier | **1.10** (10%) | §4.1 |
| Significance — over-target set count | **2** (or 1 qualifying extra) | §4.1 |
| Family-A weight kicker | **2×** the weight increment | §4.2 |
| Family-A rep/duration kicker | **+10%, rounded up, floored at normal increment** | §4.2 |
| Family-B promotion floor | `min(over-target values)` over **≥2** sets | §5 |
| `regression_threshold` (every pattern) | **3** consecutive REDUCEs | §6.1, §7.3 |
| `DELOAD_THRESHOLD` | **5** non-PROGRESS sessions in a row | §6.2 |
| Manual deload `pct` | **0.10** (10%) | §7.1 |
| Light-weight runtime cutoff | **15 lb** → 2.5 lb increment, else 5 lb | §3.4 |
| Duration deload rounding | Nearest **5 seconds**, floor 5 | §7.1 |
| Reps deload | `max(1, round(current * pct))` dropped | §7.1 |
| Plyo PROGRESS / regression / deload | Add / subtract **one set** | §7.1, §8.1 |

---

## Summary diagram

```
                    apply_session_outcome(db, exercise, date, sets, targets..., user_id)
                                            │
                                            ▼
                    ┌─────────────────────────────────────┐
                    │ SELECT current_rx, exercise_inventory│
                    └─────────────────────────────────────┘
                                            │
                                            ▼
                    ┌─────────────────────────────────────┐
                    │ calculate_outcome_from_sets()       │
                    │   → outcome,                        │
                    │   → exceeded_significantly,         │
                    │   → working_{sets,reps,wt,dur}      │
                    └──────────────┬──────────────────────┘
                                   │
       ┌───────────────────────────┼───────────────────────────────┐
       │                           │                                │
       ▼                           ▼                                ▼
   PROGRESS ↑                REPEAT → / REDUCE ↓                 None
       │                           │                                │
   promote baseline            keep baseline                   bootstrap:
   to working_*                (unless REDUCE +                seed baseline
   then bump via               threshold → regress             from min(actuals)
   calculate_next_rx           and PROMOTE next→base)
   (with kicker)
       │                           │                                │
       └─────────────┬─────────────┴──────────────┬─────────────────┘
                     ▼                            ▼
        update consecutive_failures      update sessions_since_progress
        (PROGRESS → 0,                   (PROGRESS → 0,
         REPEAT   → 0,                    REPEAT/REDUCE → +1,
         REDUCE   → +1 / regress→0,       None → unchanged)
         None     → unchanged)
                     │
                     ▼
           UPSERT current_rx (UPDATE if row exists, else INSERT
           with static fields from exercise_inventory)
                     │
                     ▼
       Return {outcome, baselines, next_*, counters, deload_suggested}
       to caller, who writes training_log + training_log_sets and
       commits the transaction.
```

---

## Open items flagged for the rebuild

The following rules are present in code but their rationale is not
documented in code comments. Surface them for the rebuild to decide:

- **REPEAT resets `consecutive_failures`.** Originally documented as
  "freeze," changed to reset for plateau tolerance. *(Rationale not
  captured in code.)*
- **Regression dimension priority differs from progression.**
  Regression: weight → duration → reps. Progression: weight → reps →
  duration. *(Rationale not captured in code.)*
- **NLP entries bypass the engine.** Whether intentional (NLP as
  journal) or oversight is not documented. *(Rationale not captured
  in code.)*
- **FIT imports never pass targets even when plan-matched.** A
  matched FIT import could in principle pull targets from the plan
  item; the current code does not. *(Rationale not captured in code.)*
- **Concurrency is unsynchronized.** Single-user-per-request
  assumption is not enforced; second-writer would hit UNIQUE.
  *(Rationale not captured in code.)*
