# V5 Implementation — #884 Unified Gear/Craft Model — Slice 3b (gear-gated cardio drills, wired live) — Closing Handoff

**Date:** 2026-06-23
**Branch:** `claude/vigilant-rubin-xhicao` (shared with slice 3 — see §4.1)
**Issue:** #884 (go-live blocker). Predecessors: slice 3 (public `athlete_gear` store, same branch), slice 3a (`0024`), slice 2 (#919), slice 1 (`0022`).
**PR:** [#932](https://github.com/ahorn885/exercise/pull/932) (shared with slice 3; **MERGED 2026-06-28 as `42216e1`**; `0025` applied to prod via `layer0-apply` run #17).

## 0. Thread continuity — STAY ON THIS THREAD (READ FIRST)

Continuous build of #884. Next is **slice 4 — the cascade cutover** (design v3 §15), and it carries two deferred items from this slice (see §4.2). Then slice 5 (away) and slice 6 (capture UX). Do not drift to another epic until #884's slices 4→6 are done or Andy redirects (tier-1 finish-the-in-flight-task).

## 1. What shipped — the swim-gear cardio-drill gate, wired LIVE

Design v3 §6a / Decision 11: gear can enable cardio **drills**, never strength or discipline feasibility. A swim drill that needs owned gear (pull buoy → pull set, kickboard → kick set) is dropped from the live `cardio_drills[]` pool unless the athlete owns the gear.

**Decisions this session (Andy 2026-06-23, two AskUserQuestion rounds + a follow-up):**
- **Vocab:** `pull_buoy`, `kickboard`, `paddles`, `fins` (no snorkel). The catalog survey (loaded v1.9.0 baseline into local PG, joined `exercises`→`sport_exercise_map`→`sport_discipline_map`) found **only two** gear-specific swim drills exist — **EX126 Freestyle Pull → pull buoy, EX128 Kicking Drill → kickboard**. So the `cardio_drill_gear_requirements` seed is those two (no padding); `paddles`/`fins` are capturable vocab Andy added for future drills.
- **Gear home:** swim gear is owned portable gear (`athlete_gear`, group_kind `swim`), NOT discipline-unlocking → **no `gear_discipline_aliases` row**.
- **Wire it all live now** (over my recommendation to stage): the gate fires in live plan-gen, threaded through every consumer.
- **Deferred (my call when the question tool failed + Andy said continue):** the `equipment_required` strip (§4.2) — a separable 0B serving-relevant edit; the gate works without it.

**Substantive files (~13 — over the 5-file ceiling; see §3 for the rationale):**

1. **`etl/migrations/layer0/0025_cardio_drill_gear_requirements.sql` (NEW)** — relation `cardio_drill_gear_requirements (id, exercise_id, gear_id, etl_version, etl_run_at, superseded_at)` + seed (EX126→pull_buoy, EX128→kickboard). Idempotent (CREATE IF NOT EXISTS + delete-this-version-then-insert); verify `DO`-block asserts 2 active rows + no dangling exercise_id. Unread at runtime (the gate hard-codes the map) → no `_q_current_etl_version_set` / `_LAYER0_TABLE_FAMILY` coordination yet (like slice 3a's `gear_discipline_aliases`); map it on a future redump.
2. **`athlete_gear_repo.py`** — `GEAR_REGISTRY` += the 4 swim slugs (group_kind `swim`). The keyspace guard test now splits discipline-unlocking (↔ `0024`) from drill-gating swim gear.
3. **`layer1/builder.py`** — `_load_owned_gear(db, user_id)` (reads `athlete_gear` via the repo, sorted) → wired into `build_layer1_payload`.
4. **`layer4/context.py`** — `Layer1Payload.owned_gear: list[str]` (top-level, rides `layer1_hash`); `ValidatorContext.owned_gear: frozenset[str]`.
5. **`layer4/per_phase.py`** — `_CARDIO_DRILL_GEAR_REQUIREMENTS` (hard-coded map, stable EX-id, like `_CONSTITUENT_SPORT_GATED_DRILLS`) + `_gear_gate_ok`; both `compute_cardio_drill_pool_ids` and `_format_cardio_drill_pool` gain an `owned_gear` param + the gate (+ the `dropped["gear"]` counter + Rule-#15 log). Threaded at `synthesize_phase`'s compute call, `render_user_prompt`'s format call, and the per-block validator ctx.
6–10. **`single_session.py` / `plan_refresh.py` / `plan_create.py` / `race_week_brief.py`** — thread `owned_gear` (from `layer1_payload.get("owned_gear")`) into their compute/format calls and `ValidatorContext` builds. `plan_refresh._build_validator_context` gained an `owned_gear` param.
11–13. **Tests** — `test_layer4_cardio_drill_pool.py` (+5: gate drops/keeps, default-empty, render lockstep, **map↔migration-seed guard**), `test_athlete_gear_repo.py` (swim-vocab guard), `test_layer1_builder.py` (`_load_owned_gear` fixture + 2 threading tests).

**The gate is hard-coded at runtime, table-canonical at rest** — the `_CARDIO_DRILL_GEAR_REQUIREMENTS` dict mirrors `_CONSTITUENT_SPORT_GATED_DRILLS` (Layer-0-derived data hard-coded by stable id to avoid threading static data through 7 call sites), with `cardio_drill_gear_requirements` (migration 0025) as the canonical authoring source. `test_gear_requirement_map_matches_migration_seed` keeps them in lockstep.

## 2. Interim behavior (READ — the gate is live but "always-drops" until slice 6)

`owned_gear` comes from `athlete_gear` (group_kind `swim`), which is **empty until swim-gear capture exists (slice 6)** — the slice-3 backfill only seeds owned *crafts*. So the live gate currently drops EX126/EX128 from **every** pool. This is the interim Andy accepted ("wire it all live now"). It does **not** affect Andy's own plans (Pocket Gopher has no swim leg → D-004 drills never enter his pool). The validator reads `ctx.owned_gear` so it stays in lockstep with the synthesizer the moment capture lands.

## 3. Why ~13 files (over the 5-file ceiling)

Andy chose "wire it all live now (~8 files)" over staging. The estimate grew because a **live** gate must stay in lockstep across the enum (`compute_cardio_drill_pool_ids`), the rendered prompt menu (`_format_cardio_drill_pool`), **and** the validator (`_rule_cardio_drill_pool_membership` re-runs compute) — so `owned_gear` had to thread through 4 compute sites + 3 format sites + 5 `ValidatorContext` builds, plus the Layer-1 read and the migration. Cohesive single feature; flagged not split per the ceiling rule. The hard-coded-map decision kept the *requirements* off the call-site threading (only `owned_gear`, which is athlete-specific, threads).

## 4. Owed / next

### 4.1 Owed
- **Open the PR** on Andy's go. The branch carries **slice 3 + the CLAUDE.md conflict-fix + slice 3b**. Slice 3 (public-schema backfill) auto-applies on deploy; **slice 3b's `0025` needs `layer0-apply`** (Andy one-tap) after merge. Andy may split the branch into two PRs at open time if he prefers.
- **`Provider_Inbound_Matrix_v2` §12 rollerski footnote** — still owed (slice 3a doc nit).

### 4.2 Next — slice 4 (cascade cutover) carries two deferred items
- **The deferred equipment strip** (design choice B, Andy 2026-06-23): supersede + re-insert EX126/EX128 at a bumped 0B version with `equipment_required` emptied of the swim gear, and supersede `Pull buoy`/`Kickboard`/**`Swim fins`** from `equipment_items` (0023 deferred Swim fins to "a later swim slice" too). This is README edit-shape #2 (global plan-gen cache invalidation). The gate works without it today (double-gated; owned-gear gate dominates), so it's pure model-cleanliness — fold it into slice 4's Layer-0 work.
- **The read/write authority gap** (from slice 3): slice 4 makes the cascade *read* `athlete_gear` while the craft picker still *writes* `discipline_baseline_*` until slice 6 — don't let it read a stale store (see CARRY_FORWARD #884 attention item 1).
- **Slice 4 proper:** re-home `_collect_athlete_crafts`/`_q_craft_*` onto `athlete_gear`/`gear_discipline_aliases`; ascending-`fidelity_rank` walk; the rollerski dryland-terrain PROXY carve-out; retire `craft_discipline_aliases` (forced redump — heed the redump-fold rule).

## 6. Owed / operating notes

### 6.3 Read order for next session (Rule #13)
1. `CLAUDE.md` — stable rules (note the now-settled PR-gating clause).
2. `CURRENT_STATE.md` — last-shipped (slice 3b) + the slice-3/3a predecessors.
3. `CARRY_FORWARD.md` — the #884 rolling item (slice progress + the ⚠ slice-4 attention items incl. the deferred strip).
4. This handoff.
5. `designs/Unified_GearCraft_Model_And_Feasibility_884_Design_v3.md` — §6a (gate), §15 (slices), §5.5 (keyspace).
6. `./scripts/verify-handoff.sh`.

## 8. Session-end verification (Rule #10)

| Claim | File | Check |
|---|---|---|
| Migration `0025` creates the relation + seeds EX126/EX128 | `etl/migrations/layer0/0025_cardio_drill_gear_requirements.sql` | grep `CREATE TABLE IF NOT EXISTS layer0.cardio_drill_gear_requirements` + the 2 VALUES rows + the verify `DO $$` |
| Swim vocab in the keyspace | `athlete_gear_repo.py` | grep `"pull_buoy": "swim"` … `"fins": "swim"` in `GEAR_REGISTRY` |
| owned_gear on the Layer 1 payload + loader | `layer4/context.py`, `layer1/builder.py` | `owned_gear: list[str]` on `Layer1Payload`; `def _load_owned_gear` reads `athlete_gear` |
| The gate + hard-coded map | `layer4/per_phase.py` | grep `_CARDIO_DRILL_GEAR_REQUIREMENTS` (EX126→pull_buoy, EX128→kickboard) + `def _gear_gate_ok` + `owned_gear=` in both `compute_cardio_drill_pool_ids` and `_format_cardio_drill_pool` |
| Validator stays in lockstep | `layer4/validator.py` | `ValidatorContext.owned_gear` + `owned_gear=ctx.owned_gear` in the `compute_cardio_drill_pool_ids` call |
| Map ↔ migration guard + gate behavior | `tests/test_layer4_cardio_drill_pool.py` | `test_gear_requirement_map_matches_migration_seed` + the 4 gate tests; suite green |
| Gate passes the Layer-0 gate + full suite | (local, not committed) | `validate_layer0` PASS on baseline+0024+0025; `tests/ etl/tests/` 3654 passed / 30 skipped |
| Pointer updated | `CURRENT_STATE.md` | "Last shipped" names slice 3b; slice 3 demoted to predecessor |

**Substantive files:** the migration + `athlete_gear_repo.py` + `layer1/builder.py` + `layer4/{context,per_phase,single_session,plan_refresh,plan_create,race_week_brief,validator}.py` + the 3 test files (~13 — over ceiling, §3). (Bookkeeping: `CURRENT_STATE.md`, `CARRY_FORWARD.md`, this handoff.)
