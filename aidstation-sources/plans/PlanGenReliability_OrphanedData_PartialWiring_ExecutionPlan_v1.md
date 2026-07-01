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

**T-1.4 — One-sided taper tolerance in the week-seam reviewer (#930)**
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
- GATE: **Trigger #1 (prompt change) — Andy ratifies the exact anchor wording before merge.**
- Verify: `tests/test_layer4_week_seam_review.py` — add: a steeper-than-planned taper drop is NOT
  `flagged_major`; an under-taper still is.

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

| Task | Issue | Field | Recommended disposition |
|---|---|---|---|
| T-2.1 | #297 | `Layer2BPayload.terrain_by_discipline` | TRIM (substitution payload already carries the terrain narrative) |
| T-2.2 | #299 | `Layer2DPayload.discipline_risk_profiles` + evidence | RENDER a compact block via the #307 pattern |
| T-2.3 | #301 | `TrainingSubstitution.uncoverable_stimulus` / `proxy_methods` | RENDER (most coaching-relevant) |
| T-2.4 | #302 | `goal_viability.reasoning_text` (per_phase) | RENDER in per_phase (already in race_week_brief) |
| T-2.5 | #302 | 3B `notable_observations`, `sleep_quality` scale | 3B: TRIM; `sleep_quality`: separate — see T-2.6 |
| T-2.6 | #302 | `SleepRecord.sleep_quality` 1–5 vs 1–10 | reconcile scale in 3A sleep block (data fix, not prompt) |
| T-2.7 | #306 | `RaceEventPayload.race_url` | RENDER in race-week brief |

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

**T-5.1 — Move Garmin onto shared `provider_auth` (#249; resolves #284)**
- Files: `garmin_connect.py`, `routes/garmin.py`, `tests/`.
- Steps: the shared API is `routes/provider_auth.py` (`upsert_auth`=`:47`, `get_auth`=`:110`,
  `refresh_access_token`). The legacy Garmin storage is the `garmin_auth` table (Garth session JSON),
  read/written in `garmin_connect.py:124-169`. Migrate those reads/writes to `provider_auth` calls
  (provider `'garmin'`), keeping the per-user `WHERE user_id = ?` filtering that already exists. Add a
  one-time data migration for existing `garmin_auth` rows if needed.
- Do NOT: change other providers.
- GATE: none. (#284 needs no separate fix — note in its issue that it's resolved by #249.)
- Verify: a multi-user test that two users' Garmin auth never cross.

**T-5.2 — TCX/GPX single-file ingest route (#1092)**
- Files: `routes/garmin.py` (or a new upload route), `tests/`.
- Steps: `tcx_gpx_parser.py` already returns the normalized cardio dict. Add the upload route that
  detects TCX vs GPX, calls `parse_tcx`/`parse_gpx`, and feeds the shared
  `routes/garmin.py:~892 _bulk_insert_cardio(source=...)`.
- Do NOT: modify `_bulk_insert_cardio`'s contract.
- GATE: none.
- Verify: upload a sample TCX and GPX → cardio_log rows via the shared path.

**T-5.3 — Wahoo full FIT stream (#1093)**
- Files: `routes/wahoo.py`, `tests/`.
- Steps: fetch `workout_summary.file.url`, parse it with `garmin_fit_parser.parse_fit()` (reuse
  directly — do NOT extract a shared parser; keep scope minimal), feed `_bulk_insert_cardio(source=
  'wahoo')` with the richer fields.
- Do NOT: refactor `garmin_fit_parser` into a shared module (out of scope).
- GATE: none.
- Verify: a Wahoo webhook fixture with a FIT URL yields stream-level fields.

**T-5.4 — Komoot connect + ingest (#891)**  ·  **T-5.5 — Wahoo plan.json export (#1094)**  ·
**T-5.6 — Karoo download target (#1095)**  ·  **T-5.7 — Real-DB ingest test (#754, do last)**
- T-5.4: new `routes/komoot.py` modeled on `routes/strava.py`/`polar.py` (provider_auth + a
  normalizer feeding `_bulk_insert_cardio(source='komoot')`).
- T-5.5: add `to_wahoo_plan_json(session)` in `routes/outbound_workout.py` reusing `Step`/
  `session_to_steps` (`~60-111`) + a download route.
- T-5.6: verify `fit_workout_generator.generate_workout_fit` output imports to Karoo; surface the
  existing FIT/ZWO links as Karoo-compatible. No new serializer.
- T-5.7: add `tests/test_cardio_ingest.py` (real-DB) covering `_bulk_insert_cardio` + dedup +
  provider_raw across all sources.
- No-ops: **#890** verify already-live; **#747** already fixed; **#833** blocked on partner — do not
  build.

---

## 4. Global order

1. T-4.1 (isolated quick win). — **DONE 2026-07-01, PR #1104.**
2. WS-1: T-1.1+T-1.2 (one PR) — **DONE 2026-07-01, PR [#1108](https://github.com/ahorn885/exercise/pull/1108), MERGED** → T-1.3 — **DONE 2026-07-01, commit `e87cd8d`** → T-1.4 (gated, next) → T-1.5. Parallel to WS-2/3.
3. WS-2: after Andy ratifies the render/trim table → T-2.1…T-2.7 → **T-2.9 (single bump + walk)**.
4. WS-3: T-3.1 (rides T-2.9 walk) → T-3.2 (gated) → T-3.3 (Layer-0 gated) → T-3.4 — **DONE 2026-07-01 (built independently of T-3.1–3.3, per its own "no preconditions").**
5. WS-5: independent throughout — T-5.1 → T-5.2/T-5.3 → T-5.4 → T-5.5/T-5.6 → T-5.7.

## 5. Bookkeeping (after approval; outside plan mode)

- ~~File 2 new issues: `shape_override` dead code (→ T-1.2); persistence gap for `seam_reviews`/
  `validator_results` (T-1.1 covers only `notable_observations`).~~ **DONE 2026-07-01** (T-1.1+T-1.2,
  PR #1108): filed [#1107](https://github.com/ahorn885/exercise/issues/1107) for the
  `seam_reviews`/`validator_results` persistence gap. Did not file a separate `shape_override` issue —
  T-1.2 removed the dead code in the same PR, so there was nothing left to track.
- Re-scope on GitHub: #302 → Layer-3B/sleep_quality only; #306 → race_url only; #284 → resolved by
  #249; #890/#747 → close after verify; update #1060 description.
