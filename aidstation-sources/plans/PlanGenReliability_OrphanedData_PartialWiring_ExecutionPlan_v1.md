# Execution Plan — Plan-Gen Reliability, Orphaned Data & Partial Wiring

> Written for step-by-step execution by any LLM (incl. Sonnet). Do exactly what each task says.
> Do not infer extra work. Do not refactor neighboring code. Stop at every **GATE**.

---

## 0. Executor rules (read before any task)

1. **One task at a time, in the order given.** Do not start a task whose *Preconditions* aren't met.
2. **Locate before you edit.** All symbol anchors below were verified by direct read on 2026-07-01,
   but line numbers can still shift. Before editing, `grep` for the named **symbol/anchor string**
   (e.g. `def format_upstream_coaching_flags`, `_bulk_insert_cardio`, `class ParsedIntent`) and edit
   *that* location, not the literal line number. If a symbol is gone or its meaning changed, **STOP**
   and report — do not guess a replacement.
3. **Stay in scope.** Only touch the files a task lists. Do not "improve" adjacent code, comments,
   or formatting. Do not add fields, flags, or abstractions the task doesn't name.
4. **Stop at GATEs.** A task marked `GATE:` requires a human decision (Andy) or a prior ratification
   first. Do not proceed past a GATE on your own; report and wait.
5. **5-file ceiling per PR.** Count only substantive code/spec/prompt files (not tests, not docs).
   If a task would exceed it, split into sub-PRs at the natural boundary the task marks.
6. **Every code change ships with a test** (the task's *Verify* names it). Run
   `python -m venv /tmp/venv && /tmp/venv/bin/pip install -r requirements.txt pytest` once, then
   `/tmp/venv/bin/python -m pytest tests/` (front-load `tests/test_layer4_*.py`).
7. **Do NOT bump `LAYER4_PROMPT_REVISION`** (`layer4/hashing.py`, currently "20") except in the ONE
   task that says to (T-2.9). Bumping it invalidates every cached plan fleet-wide.
8. **Do NOT push or open PRs** unless Andy says so (project rule). Commit to the working branch.

---

## 1. Ground truth (verified 2026-07-01 — trust this over the GitHub issue text)

The issues are partly stale. These corrections are load-bearing; do not "fix" things already done.

- `layer4/telemetry.py` **does not exist** (removed). Nothing counts `notable_observations`.
- `Layer4Payload.notable_observations` (class `Observation`, `payload.py:466`) is read by NOTHING
  except the `shape_override` validator (`payload.py:~741`) + seam-row composition. Confirmed dead.
- 3A observations ARE consumed (`recovery_guidance.py:75-83`); 3B's are not. Layer-3 uses a
  *different class* `Layer3Observation` (`context.py:859`) — **do not** try to serve both with one
  surface.
- `shape_override` is dead: hardcoded `None` at all 8 build sites; only an unreachable validator.
- #306: `notes` + locale already render; only `race_url` is missing.
- #1060: the "exceeds 20 hr" text is an advisory coaching flag (`layer2e/builder.py:~1242`), NOT a
  blocking check. It does not throw.
- #284: no real multi-user leak — Garmin just uses a legacy `garmin_auth` table. Fold into #249.
- #890 already live; #747 already fixed; #833 blocked on partner. Verify/defer — do not build.

---

## 2. Hard cross-wiring rules (the plan's spine — violating these causes rework)

- **R1 — One prompt-revision bump, one walk.** All Layer-4 prompt-body changes (#297/#299/#301/#302/
  #306/#1060/#559) land together and bump `LAYER4_PROMPT_REVISION` **once** (T-2.9), followed by
  **one** real-LLM walk. Never bump it per-issue.
- **R2 — Every newly-rendered field gets a re-run trigger.** If a task wires an upstream field into a
  Layer-4 prompt, it must add that field's `ParsedIntent.triggers_*` mapping (`context.py:~1510`) in
  the same PR, or a T1/T2 refresh will feed stale data. (This is #305, woven in — not a separate step.)
- **R3 — #930 before #847.** Ship the taper anchor (T-1.4) before enabling week-seam auto-resynth
  (T-1.5), or auto-resynth will rebuild correct ultra tapers.
- **R4 — #847 re-synth blocks must count as generation progress.** Their cache `phase_idx` must be in
  `[0, 1000)` (the band `routes/plan_create.py:_count_cached_blocks` counts), in a NEW sub-band that
  doesn't collide with primary blocks `[0,500)` or phase-seam re-synth `[500,1000)`. Do NOT reuse the
  `[3000,)` review band.

---

## 3. Tasks

Format per task — **Issue · Preconditions · Files · Steps · Do NOT · GATE · Verify**.

### WS-4 — Plan identity (isolated; do first)

**T-4.1 — Stop plans renaming themselves (#1056)** — **DONE 2026-07-01, PR #1104, merged to `main`.**
- Preconditions: none.
- Files: `init_db.py`, `plan_sessions_repo.py`, `routes/plans.py`, `routes/dashboard.py`,
  `plan_notifications.py`, `tests/`. (Helpers `generated_plan_name`=`plan_naming.py:54`,
  `target_race_name`=`plan_naming.py:12` — do not modify them.)
- Steps:
  1. Add migration in `init_db.py` `_PG_MIGRATIONS`: `ALTER TABLE plan_versions ADD COLUMN IF NOT
     EXISTS display_name TEXT;` (idempotent, nullable, no default).
  2. At plan creation, set `display_name`. The `plan_versions` INSERT is
     `allocate_plan_version_row` (`plan_sessions_repo.py:80`); store
     `generated_plan_name(target_race_name(...), scope_start, scope_end)` at insert time.
  3. At each plan-name *read* site, prefer stored `display_name` when non-null, else the computed
     fallback. The read sites are exactly: `routes/plans.py:267`, `routes/dashboard.py:35` and
     `:139`, `plan_notifications.py:77`, `routes/plan_create.py:1235`. (Confirm each by grep before
     editing.) Note `routes/plans.py:267` already emits a computed `display_name` key — switch it to
     read the column with the computed value as fallback.
- Do NOT: change how `generated_plan_name` computes; touch race-event association logic.
- GATE: none.
- Verify: `tests/test_plan_management.py` (or nearest) — add a test: create plan → assert display_name
  stored; set a *new* target race → assert the existing plan's rendered name is unchanged.

### WS-1 — Observations & seam correctness (self-contained; parallel to WS-2/3)

**T-1.1 — Persist Layer-4 observations + render on the operator page (#418, part 1)** — **DONE 2026-07-01, PR [#1108](https://github.com/ahorn885/exercise/pull/1108), merged to `main` (commit `a8539e0`), bundled with T-1.2.**
- Preconditions: none.
- Files: `init_db.py` (or a repo helper), `routes/plan_create.py`, `routes/admin.py` + its inspect
  template, `tests/`.
- Steps:
  1. Confirm anchors: `persist_layer4_sessions` (`plan_sessions_repo.py:~198`); the ready-transaction
     (`routes/plan_create.py:~731-741`); `plan_inspect` (`routes/admin.py:~514`); `_diag_authorized`
     (`routes/admin.py:~563`).
  2. Add migration: `ALTER TABLE plan_versions ADD COLUMN IF NOT EXISTS generation_observations
     JSONB;` (nullable). **Store shape:** the JSON list of `notable_observations` from the payload
     (`[obs.model_dump(mode="json") for obs in result.notable_observations]`).
  3. In the ready-transaction (right after `persist_layer4_sessions(db, result)`,
     `routes/plan_create.py:~735`), write `generation_observations` for the plan version in the SAME
     transaction. Best-effort: wrap so a write fault cannot break generation (mirror the existing
     provenance try/commit at `~759`).
  4. In `plan_inspect` (`routes/admin.py:~514`), read `generation_observations` and render a
     "Generation observations" panel grouped by `category`, surfacing `best_effort_plan` and
     `seam_unresolved` first. Token-gated by the existing `_diag_authorized`.
- Do NOT: add any athlete-facing surface; touch `Layer3Observation`; persist `seam_reviews` here
  (that's a separate filed issue).
- GATE: none. (Store shape decided: JSONB column, not a new table.)
- Verify: a test that a plan with a forced `best_effort_plan` observation persists it and the admin
  view renders it. `tests/test_layer4_plan_create.py` for the persist round-trip.

**T-1.2 — Remove `shape_override` dead code (#295-adjacent; bundle with T-1.1, same model touch)** — **DONE 2026-07-01, PR [#1108](https://github.com/ahorn885/exercise/pull/1108), merged to `main` (commit `a8539e0`).**
- Preconditions: T-1.1 in the same PR (touch the `Observation`/`Layer4Payload` model once).
- Files: `layer4/payload.py`, the 8 build sites, `tests/`.
- Steps:
  1. Confirm no code sets `shape_override` to non-None: `grep -rn "shape_override=" layer4/` — all
     must be `=None`. If any is non-None, **STOP** (not dead; abort this task).
  2. Delete the field `shape_override: ShapeOverride | None` (`payload.py:~613`), the validator
     `_check_shape_override_observation` (`~738-745`), and the `"shape_override"` member of
     `Observation.category` (`~472`).
  3. Remove the `shape_override=None` kwarg at all 8 construction sites (grep from step 1).
  4. Remove the now-unused `ShapeOverride` class if nothing else imports it (`grep -rn ShapeOverride`).
- Do NOT: remove any other `Observation.category` member; touch `notable_observations`.
- GATE: none.
- Verify: full `tests/test_layer4_*.py` green after removal.

**T-1.3 — Drop the unwired HITL-escalation claim (#418, part 2 — spec only)** — **DONE 2026-07-01, commit `e87cd8d` on branch `claude/orphaned-data-partial-wiring-87rdt7`.**
- Preconditions: T-1.1.
- Files: `aidstation-sources/specs/Layer4_Spec.md`.
- Steps: in §6.2 / §8.7, replace "escalate to next-run HITL gate" language with: Layer-4
  observations are advisory and surfaced on the operator inspect page; `elevates_to_hitl` is retained
  as advisory metadata and gates nothing. Do not change any code branch (there are none to change).
- Do NOT: remove the `elevates_to_hitl` field.
- GATE: none.
- Verify: doc-only; no test.

**T-1.4 — One-sided taper tolerance in the week-seam reviewer (#930)** — **DONE 2026-07-01.**
- Preconditions: none. **Must land before T-1.5 (R3).**
- Files: `layer4/week_seam_review.py`, `aidstation-sources/prompts/Layer4_WeekSeamReviewer_v1.md`,
  `tests/`.
- Steps:
  1. Confirm anchor: the "CALIBRATION ANCHORS" block in `SYSTEM_PROMPT` (`week_seam_review.py:~68-76`).
  2. Add one Taper anchor: a taper week dropping *steeper* than the planned descent is acceptable for
     long/ultra events; keep flagging a taper that drops *less* than planned (under-taper). Mirror the
     wording in the prompt-doc §4.
- Do NOT: change `periodization._taper_multipliers`; change any other anchor; bump
  `LAYER4_PROMPT_REVISION` (the seam reviewer has its own content-hashed cache key).
- GATE: **Trigger #1 (prompt change) — Andy ratifies the exact anchor wording before merge.** Andy
  ratified the exact wording in chat (2026-07-01) before this landed.
- Verify: `tests/test_layer4_week_seam_review.py` — add: a steeper-than-planned taper drop is NOT
  `flagged_major`; an under-taper still is.
- **As-built:** the reviewer's actual verdict is LLM-judged (the module's own docstring: "Coherence
  itself is only judged on a real-LLM run" — Andy's real-LLM walk, container can't run one), so the
  new `tests/test_layer4_week_seam_review.py::TestTaperAnchor` pins the two mechanical things that
  don't need a live LLM call: the anchor text states both directions (steeper-OK, shallower-flagged)
  in one bullet (not two anchors that could drift apart), and `render_week_seam_prompt` actually
  surfaces "Taper phase" + the planned descent ratio for a Taper-phase seam. **Also found:** the
  design doc (`Layer4_WeekSeamReviewer_v1.md` §4) already carried a vaguer Taper bullet ("judge
  against the descent, not a flat band") that had drifted out of sync with the runtime
  `SYSTEM_PROMPT` — which had **no** Taper anchor at all before this session. Both are now in sync
  with the ratified one-sided wording. Suite +2 (4171 passed / 49 skipped); `ruff check` on both
  touched files — 0 new findings (2 pre-existing unused-`Any`-import findings confirmed unchanged via
  `git stash` diff).

**T-1.5 — Week-seam auto-resynth (#847)**
- Preconditions: T-1.4 merged (R3).
- Files: `layer4/plan_create.py`, `layer4/hashing.py`, `aidstation-sources/specs/Layer4_Spec.md`,
  `tests/`.
- Steps:
  1. Study the existing phase-seam re-synth as the template: `plan_create.py:~1136-1360` (budget gate,
     cache key `compute_seam_resynth_block_cache_key`, iter-2 cached review). Study the week-seam pass
     you'll modify: `~1419-1586`.
  2. In the week-seam pass, on a verdict of `flagged_major`/`patched` with direction
     `re_prompt_prior`/`re_prompt_next` AND remaining retry budget for that (phase, week): re-synthesize
     the ONE targeted week-block via `synthesize_phase(..., week_range=(k,k))`.
  3. **R4 — cache band:** add a NEW `phase_idx` sub-band inside `[0,1000)` for week-seam re-synth
     blocks that does NOT collide with primary `[0,500)` or phase-seam re-synth `[500,1000)`. Update
     the namespace comment block (`plan_create.py:~440-465`) and add the constant. Add a
     `hashing.py` key helper (mirror `compute_seam_resynth_block_cache_key`).
  4. **CW-c — splice-back:** the re-synthesized week's sessions must replace only that week's sessions
     inside the phase's `results_by_index[phase]` session list (filtered by
     `phase_metadata.week_in_phase`), then rebuild that phase's `PhaseSynthesisResult`. This is
     different from the phase path (which replaces a whole phase). Do this explicitly.
  5. **CW-b — cascade containment:** after re-synth, if the re-prompted block's accepted-output hash is
     unchanged, do NOT re-roll the downstream per-block chain. Otherwise accept ≤1 downstream rebuild.
  6. Re-review that one seam once at `seam_iteration=2` (the reviewer already supports it), per-seam
     cap 2.
  7. For an UN-fixable tail (`accept_with_observation` or budget exhausted): record the observation
     (already happens) — that's the operator-surface path from T-1.1. Do not escalate to any athlete.
- Do NOT: change the phase-seam path; enable auto-resynth on taper seams if T-1.4 isn't merged; touch
  the `[3000,)` review band.
- GATE: none (mechanics), but note this is the most complex task — follow steps exactly.
- Verify: `tests/test_layer4_week_seam_review.py` / `test_layer4_plan_create.py` — (a) injected
  mid-phase cliff → `re_prompt` → corrected block; (b) planned recovery week → no re-synth; (c) a
  week-seam re-synth cache row is counted by `_count_cached_blocks` (R4); (d) unchanged re-prompt
  output does not invalidate downstream weeks (CW-b).

### WS-2 — Upstream-signal wiring + partial-update (#297/#299/#301/#302/#306 + #305)

> GATE (whole workstream): **Trigger #1 — Andy ratifies the render-vs-trim disposition per field
> (table below) before ANY WS-2 code.** Executor must not decide render vs trim. Recommended defaults
> are shown; Andy confirms/edits, then the executor implements exactly the ratified column.

| Task | Issue | Field | Recommended disposition | Ratified 2026-07-01 |
|---|---|---|---|---|
| T-2.1 | #297 | `Layer2BPayload` unread surface (see as-built — NOT `terrain_by_discipline` itself, which is live) | TRIM (substitution payload already carries the terrain narrative) | TRIM — **DONE**, see as-built |
| T-2.2 | #299 | `Layer2DPayload.discipline_risk_profiles` + evidence | RENDER a compact block via the #307 pattern | Andy said TRIM in chat, but verification found a real reader (`layer3d/gate.py`) outside Layer 4 — deleting the field breaks Layer 3D. **Resolution: no-op, left alone** (it was never rendered in a Layer 4 prompt to begin with; there's nothing to trim without breaking Layer 3D). Andy confirmed this reading. |
| T-2.3 | #301 | ~~`TrainingSubstitution.uncoverable_stimulus`/`proxy_methods`~~ — **correction:** those fields don't exist on `TrainingSubstitution`; they live on `TerrainGap` (`layer4/context.py`), reachable via `Layer2BPayload.terrain_by_discipline[].terrain_gaps[]` | RENDER (most coaching-relevant) | RENDER, from the corrected location — Andy confirmed |
| T-2.4 | #302 | `goal_viability.reasoning_text` (per_phase) | RENDER in per_phase (already in race_week_brief) | RENDER |
| T-2.5 | #302 | 3B `notable_observations`, `sleep_quality` scale | 3B: TRIM; `sleep_quality`: separate — see T-2.6 | 3B: TRIM |
| T-2.6 | #302 | `SleepRecord.sleep_quality` 1–5 vs 1–10 | reconcile scale in 3A sleep block (data fix, not prompt) | fix — **DONE** |
| T-2.7 | #306 | `RaceEventPayload.race_url` | RENDER in race-week brief | RENDER |

- Each **RENDER** task (T-2.2/2.3/2.4/2.7):
  - Files — the render helper + ALL FIVE render sites (the refresh renderer is split into three):
    `layer4/per_phase.py` (helper `format_upstream_coaching_flags`=`:2367`; sibling
    `format_measured_physiology`=`:2330`; `render_user_prompt`=`:2539`, append point `:2782-2792`),
    `layer4/single_session.py` (`_render_user_prompt`=`:567`, append `:619`),
    `layer4/race_week_brief.py` (`_render_user_prompt`=`:944`, append `:1161`),
    `layer4/plan_refresh_t1.py` / `plan_refresh_t2.py` / `plan_refresh_t3.py` (each has
    `render_user_prompt`; refresh append is orchestrated at `plan_refresh.py:1132-1143`);
    plus `layer4/context.py` (the `ParsedIntent` trigger, per R2) and `tests/`.
  - Steps: (1) confirm the field is still unread (`grep`); (2) write a new `format_<field>()` helper
    modeled EXACTLY on `format_upstream_coaching_flags` (`per_phase.py:2367`) — suppress-on-empty
    (`return []` when no data), return `["header", "- line", …]` otherwise; (3) at each append point
    above, add `lines = format_<field>(...)` then `if lines: user_prompt += "\n\n" + "\n".join(lines)`
    — mirror the existing `upstream_flag_lines` append exactly; (4) **R2:** add the field's trigger to
    `class ParsedIntent` (`context.py:1508`, fields at `:1510-1514`) so a change re-runs the right
    layer; (5) do NOT bump the revision here (T-2.9 does it once).
  - Do NOT: render more fields than the task's one; change the prompt's coaching instructions; skip
    any of the five render sites.
  - Verify: a unit test that the render block appears when the field is populated and is absent when
    empty; a #305 test that editing the field flips the corresponding `ParsedIntent.triggers_*`.
- Each **TRIM** task (T-2.1/2.5): delete the unread field from its payload class in `context.py` and
  any producer that sets it; confirm zero readers first (`grep`). Do NOT trim if any reader exists.
- T-2.6 (sleep_quality): reconcile the 1–5 vs 1–10 scale where 3A reads sleep; data/mapping fix only.

**T-2.9 — Single revision bump + walk (R1)**
- Preconditions: T-2.1…T-2.7 code merged to the branch.
- Files: `layer4/hashing.py`.
- Steps: bump `LAYER4_PROMPT_REVISION` "20" → "21" ONCE, with a comment listing the issues folded in.
- GATE: Andy runs the one real-LLM walk (container can't). Provide the walk checklist: each rendered
  field appears; a T1/T2 refresh editing a rendered field re-runs the right layer (no stale data).
- Verify: full suite green; walk is Andy-run.

### WS-3 — Deterministic feasibility & eligibility (#831/#559/#1060/#573; #427 frame)

**T-3.1 — Delete the impossible sleep-dep advisory (#1060)**
- Files: `layer2e/builder.py`, `tests/`.
- Steps: the emission is inside `_build_sleep_dep_overlay` (`layer2e/builder.py:1218`); delete the
  `flags.append(Layer2ECoachingFlag(flag_type="sleep_dep_data_missing", …))` block at `:1237-1248`.
  Confirm no test asserts on `sleep_dep_data_missing` before deleting; if one does, delete/adjust it.
- Do NOT: remove other coaching flags; touch the 20hr event classification itself.
- GATE: its prompt-content effect rides T-2.9's walk (do not run a separate walk).
- Verify: `tests/test_layer2e.py` — a >20hr event with empty sleep-dep fields yields no such flag.

**T-3.2 — Prevent double-strength-same-day crash (#831)**
- Files: `layer4/session_feasibility.py` (the deterministic resolution cascade — tiers
  `exact/proxy/indoor/strength/reallocate` on `ResolvedDiscipline.tier`, ~`:146`; the `strength` and
  `reallocate` tiers are where too many strength substitutions originate) and the day/week assignment
  path that a `tests/test_layer4_session_grid_saturation.py` already exercises (grep for the module it
  imports — likely `layer4/session_grid*.py`); `tests/`.
- Steps: implement a deterministic pre-synthesis cap so no day is assigned two strength sessions —
  cap strength substitution across the week and reallocate excess to feasible disciplines BEFORE
  synthesis, so the validator `_check_two_per_day` (`payload.py:713`, `no strength+strength on same
  day`) is never hit. Follow `Feasibility_Saturation_And_Locale_Retirement_Plan_v1.md` §2/WS-E2 for
  the exact cap rule (read that doc first).
- Do NOT: relax the `payload.py:713` validator; change the seam reviewers.
- GATE: **Andy confirms the saturation-cap rule matches the Feasibility_Saturation doc** before build
  (Trigger-#3-adjacent).
- Verify: `tests/test_layer4_session_grid_saturation.py` — a packed multi-discipline infeasible week
  produces ≤1 strength/day and the plan validates.

**T-3.3 — Team-only sport gate for solo athletes (#559)**
- Files: a Layer-0 migration (`etl/migrations/layer0/*.sql`), `layer1/builder.py`, `layer2a/builder.py`,
  `tests/`.
- Steps: (1) persist `requires_team` on the Layer-0 disciplines table; (2) add a solo/team flag to the
  Layer-1 payload; (3) gate discipline inclusion in Layer 2A to exclude team-only disciplines for a
  solo athlete.
- Do NOT: hardcode specific disciplines; change synthesis prompts beyond the gate.
- GATE: **Layer-0 migration is Andy-gated** (`layer0-apply` workflow, one-tap approve). Its
  prompt-content effect (if any) rides T-2.9's walk.
- Verify: `tests/test_layer2a.py` — a solo athlete's discipline set excludes a `requires_team` sport.

**T-3.4 — Terrain-substitute backup strength in refresh (#573)** — **DONE 2026-07-01, branch `claude/orphaned-data-partial-wiring-87rdt7`.**
- Files: `layer4/plan_refresh.py`, `tests/`.
- Steps: enable the backup-strength substitution on the refresh path when terrain rules out the
  original (mirror the create-path behavior). Confirm the create-path equivalent first.
- Do NOT: change create-path behavior.
- GATE: none.
- Verify: a refresh test where terrain-infeasibility triggers the backup strength.
- **As-built correction (session-start verification caught this):** the file list above was wrong —
  `layer4/plan_refresh.py` only dispatches; the actual renderers are the tier files. Also, the
  create-path terrain-feasibility *data* wiring (#557) had already shipped, but the failover
  *trigger tag* it depends on (`grid_annotation()`) was never wired into any refresh renderer, so the
  failover template was still dormant on refresh despite #557. Actually touched:
  `layer4/per_phase.py` (`_format_session_feasibility` gained an `include_grid_tag` param, default
  `False` — create's own call site is unchanged), `layer4/plan_refresh_t1.py` /
  `plan_refresh_t2.py` (pass `include_grid_tag=True`), `layer4/plan_refresh_t3.py` (same, plus it was
  missing `STRENGTH_PROGRAMMING_GUIDANCE` entirely — added). Bundled in the same PR (same
  `Layer4Payload`/`PlanSession` touch, per Rule #12 T-1.1+T-1.2 precedent): the issue #573
  "advisory-quality tail" flagged in `CARRY_FORWARD.md` — added `PlanSession.strength_substitution:
  bool = False` (`layer4/payload.py`), the matching tool-schema property in both
  `per_phase.py::_session_schema` and `plan_refresh.py::_session_schema`, one new sentence in
  `layer4/strength_guidance.py::STRENGTH_PROGRAMMING_GUIDANCE` instructing the LLM to set it on a
  failover composition (Trigger #1 — Andy ratified the exact wording in plan mode before this
  landed), and excluded `strength_substitution=True` sessions from
  `layer4/validator.py::_rule_strength_frequency_band`'s count.

> #427 (assemble-from-pre-checked-options) is the DESIGN FRAME for WS-3, not a code task here. Build
> T-3.1–T-3.4 deterministically/upstream so #427's later ratified reframe reuses them. Do not attempt
> #427's broad reframe in this plan.

### WS-5 — Integrations (parallel track; no plan-gen coupling)

**T-5.1 — Move Garmin onto shared `provider_auth` (#249; resolves #284)** — **DONE 2026-07-01.**
- Files: `garmin_connect.py`, `routes/garmin.py`, `tests/`.
- Steps: the shared API is `routes/provider_auth.py` (`upsert_auth`=`:47`, `get_auth`=`:110`,
  `refresh_access_token`). The legacy Garmin storage is the `garmin_auth` table (Garth session JSON),
  read/written in `garmin_connect.py:124-169`. Migrate those reads/writes to `provider_auth` calls
  (provider `'garmin'`), keeping the per-user `WHERE user_id = ?` filtering that already exists. Add a
  one-time data migration for existing `garmin_auth` rows if needed.
- Do NOT: change other providers.
- GATE: none. (#284 needs no separate fix — note in its issue that it's resolved by #249.)
- Verify: a multi-user test that two users' Garmin auth never cross.
- **As-built correction (session-start caught this):** issue #249 was labeled `status:blocked`
  ("Garmin's API is closed") — the plan's "GATE: none" didn't mention it. Andy ratified proceeding
  anyway (AskUserQuestion): the block is about the closed *official OAuth* API; garth is an unofficial
  session-login library, not OAuth, so the storage-layer migration isn't actually blocked by it.
  `PROVIDERS_SCHEMA.md`/`DATABASE.md` had explicitly documented "wait for API reopen" — updated both
  in this same PR to reflect the migration landing now. Actually touched: `garmin_connect.py` (all 4
  read/write sites — `_save_session_to_db`/`_load_client`/`get_auth_status`/`fetch_activities` — now
  call `routes/provider_auth.py`'s `upsert_auth`/`get_auth`, `session_blob` carries the garth JSON,
  `provider_user_id` carries `garmin_username`); `routes/garmin.py` (`auth_import_cookies` +
  `auth_import_tokens` — the two direct-SQL endpoints the plan's file list didn't call out by name, but
  are covered by "Files: ... `routes/garmin.py`"); `routes/admin.py` (`_delete_user_and_data` — added
  `DELETE FROM provider_auth WHERE user_id = ?`, since without it a Garmin-or-any-provider-connected
  user's account delete would now hit an FK violation — this table was never in the cascade chain for
  ANY provider, a pre-existing gap this migration exposed, not introduced). **No data migration
  needed** — a read-only `neon-query` confirmed `garmin_auth` has 0 rows in prod. Did **not** drop the
  `garmin_auth` table itself (out of scope for this task; it auto-applies via `_PG_MIGRATIONS` with no
  gate, so left as a flagged follow-up rather than an unrequested irreversible DDL). New test file
  `tests/test_garmin_provider_auth_migration.py` (8 tests) — the multi-user isolation test runs the
  real `upsert_auth`/`get_auth` SQL shapes against an in-memory `(user_id, provider)` store, not a
  mock, per the plan's stated verify. Full suite 4137 passed / 30 skipped (+8).

**T-5.2 — TCX/GPX single-file ingest route (#1092)** — **DONE 2026-07-01.**
- Files: `routes/garmin.py` (or a new upload route), `tests/`.
- Steps: `tcx_gpx_parser.py` already returns the normalized cardio dict. Add the upload route that
  detects TCX vs GPX, calls `parse_tcx`/`parse_gpx`, and feeds the shared
  `routes/garmin.py:~892 _bulk_insert_cardio(source=...)`.
- Do NOT: modify `_bulk_insert_cardio`'s contract.
- GATE: none.
- Verify: upload a sample TCX and GPX → cardio_log rows via the shared path.
- **As-built correction:** session-start audit found the *bulk* drop zone (`routes/garmin.py
  import_bulk`, the connections-hub uploader) already dispatched `.tcx`/`.gpx` through
  `parse_tcx`/`parse_gpx`/`detect_source` end-to-end (#767 Slice 2/5, shipped 2026-06-19/20) —
  the plan's "add the upload route" framing was stale. The real gap #1092's own evidence pointed
  at: the **single-file review-and-plan-match flow** (`import_fit`/`import_preview`/
  `import_confirm` — the "Single activity" section on `garmin/import.html`, called out by name in
  `connections/hub.html`'s own comment as "the single-file review-and-plan-match path") was still
  hard-restricted to `.fit`/`.zip`, both in the form's `accept` attribute and the server-side
  extension check in `import_fit`. Extended that flow: `import_fit` now dispatches
  `.fit`/`.tcx`/`.gpx` to `parse_fit`/`parse_tcx`/`parse_gpx`, auto-detects the source via
  `detect_source` for non-FIT uploads (mirroring the bulk path), and stores it in a new
  `flask_session['fit_import_source']` key so `import_confirm` can tag the `provider_raw_record`
  write with the detected source (`provider=...`) instead of the parser's generic `'manual'`
  fallback. Also fixed the *same page's* bulk-section `accept` attribute, which was still
  `.fit,.zip` even though it posts to the same `import_bulk` endpoint the hub's drop zone (which
  already had the full accept list) uses — a same-endpoint UI/copy inconsistency `#1092`'s
  evidence also flagged. Retitled the page "Import activity files" (was "Import .FIT files") since
  it now genuinely isn't FIT-only. Deliberately did **not** retrofit dedup-before-preview onto the
  single-file path (FIT never had it either — an interactive human-reviewed confirm step, unlike
  the bulk backfill path's idempotency need) and did **not** touch the bulk-vs-zip .fit-only
  extraction (`.tcx`/`.gpx` inside a zip stays a bulk-import concern). New
  `tests/test_garmin_single_file_tcx_gpx_import.py` (4 tests) — extension gate, TCX/GPX parser
  dispatch + source auto-detection, dedup-prefix correctness, provider_raw_record tagging with the
  detected source.

**T-5.3 — Wahoo full FIT stream (#1093)** — **DONE 2026-07-01.**
- Files: `routes/wahoo.py`, `tests/`.
- Steps: fetch `workout_summary.file.url`, parse it with `garmin_fit_parser.parse_fit()` (reuse
  directly — do NOT extract a shared parser; keep scope minimal), feed `_bulk_insert_cardio(source=
  'wahoo')` with the richer fields.
- Do NOT: refactor `garmin_fit_parser` into a shared module (out of scope).
- GATE: none.
- Verify: a Wahoo webhook fixture with a FIT URL yields stream-level fields.
- **As-built note:** `_ingest_workout_summary` now reads `workout_summary.file.url` (nested-first
  under `workout`, top-level fallback — same defensive pattern `normalize_wahoo_summary` already
  uses for other fields; BEST-EFFORT/VERIFY-OWED per Rule #14, unconfirmed against a live payload
  that actually carries a file link), fetches it with a fresh OAuth token
  (`provider_auth.get_fresh_access_token`, same pattern as `routes/strava_ingest.py`), and parses it
  with `garmin_fit_parser.parse_fit()` unmodified. The FIT's stream-level fields (`max_hr`,
  `moving_time_min`, `max_cadence`, `max_power`, `norm_power`, `aerobic_te`/`anaerobic_te`,
  running-dynamics fields, `elev_loss_ft`, `swolf`/`active_lengths`) are overlaid onto the summary
  dict **only where the summary itself has nothing** — discipline resolution and
  `_provider_raw` tagging deliberately stay Wahoo's own matrix-§10.2 `workout_type_id` mapping, not
  the FIT sport enum, so a FIT-enriched activity resolves identically to a summary-only one (the
  plan's "feed `_bulk_insert_cardio` with the richer fields" reads as enriching the summary, not
  replacing its already-spec'd discipline/provider identity with the FIT's). The fetch+parse is
  best-effort end to end (no token, network failure, non-2xx, malformed FIT, or an unexpected
  strength-type FIT all fall back silently to summary-only fields) — a stream-enrichment failure
  must never block the base cardio_log import. New tests in `tests/test_wahoo_ingest.py` (10 new
  tests) — `file.url` extraction (nested + top-level + absent), the field-overlay semantics
  (fills gaps, never overrides a summary-derived value, no-ops on a non-cardio or failed parse),
  and the full `_ingest_workout_summary` path (fetch+merge; no-token skip; no-file-url skip with no
  fetch attempted at all).

**T-5.4 — Komoot connect + ingest (#891)** — **BLOCKED-ON-PARTNER 2026-07-01, not built.**
- Files: `routes/komoot.py` (not created), `tests/`.
- Steps (as planned): new `routes/komoot.py` modeled on `routes/strava.py`/`polar.py`
  (provider_auth + a normalizer feeding `_bulk_insert_cardio(source='komoot')`).
- **As-built correction:** session-start check found Komoot's OAuth2 API (`komoot.de/b2b/connect`)
  requires an approved business partnership — there's no self-serve developer-registration path
  like Strava/Polar/Wahoo have, so there's no `client_id`/`client_secret` to build against. Same
  shape as **#833** (TrainingPeaks inbound) below. Andy's call: skip, same precedent as #833 —
  don't write OAuth/ingest code against an API we can't reach. #891 labeled `status:blocked`,
  left open (not closed — matches #833's convention). Unblocks when partner access is approved.

**T-5.5 — Wahoo plan.json export (#1094)** — **DONE 2026-07-01.**
- Files: `routes/outbound_workout.py`, `routes/wahoo.py`, `tests/`.
- Steps: add `to_wahoo_plan_json(session)` in `routes/outbound_workout.py` reusing `Step`/
  `session_to_steps` (`~60-111`) + a download route.
- **As-built correction:** the issue's own scope note called this a passive file download ("not a
  push API"), matching Zwift's `.zwo` pattern — wrong per both the matrix §10.2 ("`plans_write`
  pushes a Wahoo-proprietary `plan.json`") and Wahoo's real Cloud API docs: it's a genuine push
  (create a `plan`, attach to a `workout` dated within 6 days of today, Wahoo syncs it to the
  ELEMNT/RIVAL device in ~30s). A passive download has no known manual-import path on Wahoo
  hardware (unlike Zwift's folder-drop) — would have shipped something unusable. Andy confirmed:
  build the real push. Built `to_wahoo_plan_json` (flat `intervals[]`, reps expanded rather than a
  fabricated repeat-wrapper — the matrix's source doesn't document one) + `POST
  /wahoo/push/<pv>/<date>/<idx>` in `routes/wahoo.py` (two-step plan→workout push, idempotent via
  `provider_outbound_ref`, refuses pushes outside the 6-day sync window). Bumped `_WAHOO_SCOPES`
  to add `plans_write` (scope version bumped — already-connected athletes must reconnect once).
  Added a real "Send to Wahoo" button on the plan session view (`routes/plan_create.py` +
  `templates/plan_create/view.html`) gated on an active `plans_write`-carrying connection — unlike
  the still-gated TP connector (backend-only, no UI), Wahoo OAuth is already live, so this ships
  something usable today. BEST-EFFORT/VERIFY-OWED (Rule #14): exact `plan.json`/endpoint field
  names are this session's best reading of the matrix's terse source note, not live-confirmed.
  New tests: `TestWahooPlanJson` in `tests/test_outbound_workout.py` (8) + new
  `tests/test_wahoo_outbound.py` (10). Suite 4169 passed / 30 skipped (+18).

**T-5.6 — Karoo download target (#1095)** — **DONE 2026-07-01.**
- Files: `templates/plans/item.html`, `templates/dashboard.html`, `templates/plan_create/view.html`.
- Steps: verify `fit_workout_generator.generate_workout_fit` output imports to Karoo; surface the
  existing FIT/ZWO links as Karoo-compatible. No new serializer.
- **As-built:** confirmed as scoped — `download_item_fit` already calls `generate_workout_fit`
  (proper `WorkoutMessage` FIT, not an activity recording); `_build_steps`'s distance-only branch
  correctly emits a `WorkoutStepDuration.DISTANCE` step (valid FIT, not a bug — Karoo's own
  "may not import as expected" caveat is a Karoo-side behavior on spec-correct input, not ours to
  fix); the Layer4 `.zwo` export is 100% time-based already (no distance field in `CardioBlock`).
  Pure UI-labeling change: `templates/plans/item.html`'s FIT rail-note + `templates/dashboard.html`'s
  `.FIT` button tooltip + `templates/plan_create/view.html`'s Zwift link (relabeled "↓ .zwo (Zwift,
  Karoo)") now note Karoo compatibility. No logic changes; suite unaffected.

**T-5.7 — Real-DB ingest test (#754, do last)** — **DONE 2026-07-01.**
- Files: `tests/test_cardio_ingest.py` (not yet created).
- Steps: add `tests/test_cardio_ingest.py` (real-DB) covering `_bulk_insert_cardio` + dedup +
  provider_raw across all sources.
- No-ops: **#890** verify already-live; **#747** already fixed; **#833** blocked on partner — do not
  build.
- **As-built:** used the local `postgres:16` cluster already installed in the container (start it,
  bootstrap a scratch `aidstation_test` DB via `init_db.init_postgres()`) rather than reaching for a
  new CI job in this PR — the recipe the predecessor handoff left. Added a `requires_real_postgres`
  skipif marker to `tests/conftest.py` (mirrors `requires_anthropic_api_key`'s pattern exactly): gated
  on a `TEST_DATABASE_URL` env var, so `pytest tests/` stays $0/side-effect-free by default and the new
  file collects but skips (19 skipped) unless the var is set. New `tests/test_cardio_ingest.py` (19
  tests) runs `_bulk_insert_cardio` + `_record_provider_raw_cardio` + `_already_imported` against the
  real bootstrapped schema (not a fake connection that just records SQL strings): gid lands in the
  right per-source column (garmin/coros/wahoo/polar/strava); `provider_raw_record` is tagged with the
  true source and upserts (not duplicates) on a second write for the same external_id — proving the
  `ON CONFLICT (user_id, provider, data_type, external_id)` arbiter actually matches the table's real
  unique constraint; the #752 regression class itself (a blank `observed_at` string, which is not a
  valid Postgres TIMESTAMP literal) stores NULL rather than raising, against a real server this time;
  the partial UNIQUE index each of coros/wahoo/polar/strava has on `(user_id, <col>)` really exists and
  raises `UniqueViolation` on a same-user duplicate, and really is scoped per-user (a different user
  can reuse the same external id); `_already_imported` (the caller-side dedup guard `garmin` relies on,
  since it has no DB-level unique index) is correctly scoped to the authenticated user only. **CI
  job deliberately NOT wired this session** (the predecessor handoff flagged deciding this as part of
  T-5.7 itself) — filed as a fast-follow, see §5.

---

## 4. Global order

1. T-4.1 (isolated quick win). — **DONE 2026-07-01, PR #1104.**
2. WS-1: T-1.1+T-1.2 (one PR) — **DONE 2026-07-01, PR [#1108](https://github.com/ahorn885/exercise/pull/1108), MERGED** → T-1.3 — **DONE 2026-07-01, commit `e87cd8d`** → T-1.4 — **DONE 2026-07-01, Andy-ratified wording** → T-1.5 (next, unbuilt — the plan's most complex task; not started this session). Parallel to WS-2/3.
3. WS-2: after Andy ratifies the render/trim table → T-2.1…T-2.7 → **T-2.9 (single bump + walk)**.
4. WS-3: T-3.1 (rides T-2.9 walk) → T-3.2 (gated) → T-3.3 (Layer-0 gated) → T-3.4 — **DONE 2026-07-01 (built independently of T-3.1–3.3, per its own "no preconditions").**
5. WS-5: independent throughout — T-5.1 — **DONE 2026-07-01** → T-5.2/T-5.3 — **DONE 2026-07-01**
   → T-5.4 — **BLOCKED-ON-PARTNER 2026-07-01, skipped** → T-5.5/T-5.6 — **DONE 2026-07-01**
   → T-5.7 — **DONE 2026-07-01. WS-5 fully closed.**

## 5. Bookkeeping (after approval; outside plan mode)

- ~~File 2 new issues: `shape_override` dead code (→ T-1.2); persistence gap for `seam_reviews`/
  `validator_results` (T-1.1 covers only `notable_observations`).~~ **DONE 2026-07-01** (T-1.1+T-1.2,
  PR #1108): filed [#1107](https://github.com/ahorn885/exercise/issues/1107) for the
  `seam_reviews`/`validator_results` persistence gap. Did not file a separate `shape_override` issue —
  T-1.2 removed the dead code in the same PR, so there was nothing left to track.
- Re-scope on GitHub: #302 → Layer-3B/sleep_quality only; #306 → race_url only; #284 → resolved by
  #249; #890/#747 → close after verify; update #1060 description.
- **T-5.7 (#754) — DONE 2026-07-01:** closed `completed`. Filed
  [#1125](https://github.com/ahorn885/exercise/issues/1125) for the CI-wiring fast-follow (the tests
  exist and pass locally against `TEST_DATABASE_URL`, but nothing in CI sets that var yet — deciding
  whether to reuse/extend `layer0-gate`'s Postgres service or add a new job is its own scoped piece,
  not a T-5.7 sub-step). **WS-5 is now fully closed** — every task DONE or BLOCKED-ON-PARTNER.
