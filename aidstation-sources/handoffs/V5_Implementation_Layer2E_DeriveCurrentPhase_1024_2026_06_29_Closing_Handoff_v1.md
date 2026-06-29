# V5 — #1024: wire `derive_current_phase` into 2E `current_phase` (§5.1): SHIPPED (pending PR/merge)

Closing handoff. #1024 closed the #220 gap — `plan_management.derive_current_phase`
(§5.1 week-indexed active phase) was built by #221 but had **no call site**, so
Layer 2E was always fed the plan's *first* block (`start_phase`) as
`current_phase`. Now the shared cone derives the phase active **today**. Built on
`claude/v5-layer2e-heat-destub-1024-ukw1p5`; **pushed, PR opens on Andy's go**.

> **NEXT STEP:** no in-flight follow-up from this slice. The remaining #210
> de-stub arc is the deferred-by-design HITL/pregnancy work (#223/#518), icebox
> Layer-0 promotions (#229/#232/#233), and #222 ffm_kg. The standing **#884**
> (slice 6) and **#964** (recurring-send) arcs remain live threads.

## 1. What shipped

The bug: `_upstream_full_cone` (the upstream cone shared by plan_create,
plan_refresh, and race_week_brief) assembled `PlanManagementState` with
`current_phase=layer3b_payload.periodization_shape.start_phase` — always the
plan's first block. For any athlete past their first block, a refresh or
race-week brief computed the 2E nutrition baseline as if they were still in
Base (the per-phase calorie/macro scaling consumes `current_phase`).

`derive_current_phase` (§5.1) derives the phase active on a given date from the
3B shape + plan start + total weeks (reusing Layer 4's canonical
`phase_structure_from_3b` → `phase_for_date`). #221 added it; #220 deliberately
left it unwired (a behavior change = separate decision). #1024 wires it.

### Rule #9 finding — the #220 handoff's "mechanical one-liner" was wrong

The #220 closing handoff §4 claimed the change was a one-line `str_replace`
because "the inputs (`plan_start`, `_compute_total_weeks`) are already on hand at
the orchestrator's 2E call site." Verified false:

- The 2E call site is inside `_upstream_full_cone`, **shared by all 3 entry
  points** — not a per-caller site.
- `plan_start` only reaches the cone for **plan_create** (as
  `viability_current_date`); it is `None` for plan_refresh and race_week_brief.
- `_compute_total_weeks(layer3b, plan_start, race_event)` is called in the
  **plan_create caller**, *after* the cone returns (`orchestrator.py` ~L1896) —
  not at the 2E site.

So a correct wiring needs `plan_start` threaded/resolved per path.

### Andy decision (AskUserQuestion 2026-06-29 — "All three now")

Wire it for create + refresh + race_week_brief, including resolving the original
plan start for the refresh/brief paths. (Two earlier framings of the question
were corrected by Andy — the change affects **all tenants past their first
block**, not one test athlete's plan.)

### The implementation

- **`layer4/orchestrator.py`** — `_upstream_full_cone` gained a keyword-only
  `plan_start: date | None = None`. It resolves the running plan's **origin**
  (`origin_plan_start`): use `plan_start` when supplied (plan_create), else read
  it from `plan_versions` (refresh/brief). When an origin is resolved,
  `current_phase = derive_current_phase(layer3b_payload, origin_plan_start,
  today, _compute_total_weeks(layer3b_payload, origin_plan_start,
  target_race_event))`. When none is resolvable, fall back to `start_phase` and
  `print(...)` the substitution (Rule #15 — the only otherwise-silent branch).
  `derive_current_phase` is now imported from `plan_management`.
  - **plan_create caller** passes `plan_start=plan_start_date` directly — its
    plan isn't persisted yet, and at creation `today == plan_start` → week 0 →
    first block, so **create is a no-op** (current_phase == start_phase). This
    also avoids the cone reading a *stale older* plan's origin from the DB.
  - **plan_refresh + race_week_brief callers are unchanged** — they leave
    `plan_start` None, so the cone resolves the origin from `plan_versions`
    (uniform across tiers; no dependence on the refresh `plan_start_date` kwarg,
    which is only supplied for T3).
- **`plan_sessions_repo.py`** — new `load_current_plan_start(db, user_id,
  on_or_before)`: returns the `scope_start_date` of the most recent
  `created_via='plan_create'` `plan_versions` row with `scope_start_date <=
  on_or_before` (`ORDER BY created_at DESC, id DESC`), or `None`.
  - **Why not the active version's scope start:** `plan_versions` has **no
    parent pointer**, and a refresh writes a NEW row scoped to the *refresh*
    window (`created_via='plan_refresh_t*'`). So the active version's scope start
    is the last edit, not where periodization phase 0 began. The original full
    plan is the `plan_create` row, and its `scope_start_date` is the §5.1 anchor.
  - **No archived/completed filter** — a `plan_create` row stays the origin even
    after refreshes supersede it for the dates they re-plan.

## 2. Decisions

- **Scope = all three paths (Andy, AskUserQuestion 2026-06-29).** create (no-op
  guard) + refresh + race_week_brief.
- **Origin resolution centralized in the cone, read from `plan_versions`** (not
  threaded as a new kwarg from each caller). Refresh/brief don't carry the
  original plan start cleanly; reading the `plan_create` row is uniform and
  correct for all tiers. plan_create is the one path that *must* pass it (its
  plan isn't on disk yet).
- **`current_phase` stays plain `str`** — unchanged from #220; the 2E builder's
  `_validate_inputs` remains the `{Base,Build,Peak,Taper}` membership gate.
- **PM-1 tradeoff accepted (the §5.1 soft spot).** The 3B-shape phase can
  diverge from Layer 4's reshaped calendar, but `derive_current_phase` reuses
  the *same* `phase_structure_from_3b` decomposition Layer 4 renders into, so the
  boundaries match — divergence is minimized, not introduced.

## 3. Verification

- Full suite **3957 passed / 30 skipped** (only the 3 pre-existing #217 Layer3B
  `evidence_basis` warnings). Run: `/tmp/venv/bin/python -m pytest tests/ etl/tests/ -q`.
- ruff clean on changed files. The 3 `mocks` F841 in `test_layer4_orchestrator.py`
  + 2 F401 (`typing.Any`, `load_active_window_with_rest`) in
  `test_plan_sessions_repo.py` that ruff reports are **pre-existing** — confirmed
  by re-linting under `git stash` (5 findings before this session's diff).
- New tests: `test_layer4_orchestrator.py` `TestCurrentPhaseDerivation`
  (refresh derives **Build** from a Base-start 16-week standard plan begun at
  `_PLAN_START` 2026-04-01 / create **anchors at the first block** / no-origin
  **falls back to start_phase**); `test_plan_sessions_repo.py`
  `TestLoadCurrentPlanStart` (returns plan_create scope start / None / SQL shape).
  Anchoring math: §6.1 standard over 16 weeks = Base 8 / Build 4 / Peak 2 /
  Taper 2; from 2026-04-01 that puts `_TODAY` (2026-06-01) in Build.
- **No Neon/layer0 apply owed** — public-schema read of `plan_versions`;
  `current_phase` recomputed on read, never pinned to `etl_version_set`.

## 4. Files (2 code, under ceiling)

`layer4/orchestrator.py`, `plan_sessions_repo.py` + tests
`tests/test_layer4_orchestrator.py`, `tests/test_plan_sessions_repo.py`.

## 5. Out of scope / deferred

- The remaining #210 de-stub arc: HITL gates 1-4 + pregnancy (#223/#518);
  icebox Layer-0 promotions (#229/#232/#233); #222 ffm_kg.
- `expected_race_temp_c` refresh cadence as events cross the horizon (PM-4 —
  #220 carry-forward, scheduling).
- Standing threads: **#884** slice 6 (gear capture UX), **#964** recurring-send.

## 6.3 Read order for next session (Rule #13)

1. `CLAUDE.md` — stable rules
2. `CURRENT_STATE.md` — #1024 is the last shipped session
3. `CARRY_FORWARD.md`
4. This handoff
5. (no `scripts/verify-handoff.sh` in-repo — Rule #9 spot-check by the §7 anchors)

## 7. Verification anchors (Rule #10)

| Claim | Anchor | Check |
|---|---|---|
| derive_current_phase wired | `derive_current_phase(` call in `layer4/orchestrator.py` (was def-only) | grep |
| cone takes plan origin | `plan_start: date \| None = None` param on `_upstream_full_cone` | grep |
| origin resolver | `def load_current_plan_start` in `plan_sessions_repo.py` (`created_via = 'plan_create'`) | grep |
| create passes its start | `plan_start=plan_start_date` at the plan_create cone call | grep |
| fallback logged | `current_phase fallback to start_phase` print in `_upstream_full_cone` | grep |
| suite green | 3957 passed / 30 skipped | pytest |

## 8. Operating-flow note

Per the project rule (CLAUDE.md *Ops automation*, Andy 2026-06-19/23): pushed +
bookkept; **PR opens only on Andy's go**. Bookkeeping (this handoff +
`CURRENT_STATE.md` pointer + #1024 issue comment) rides the **same branch** as
the code so it lands with the work. Merge method = real merge commit, never
squash.
