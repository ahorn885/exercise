# V5 Implementation — Layer 0 slice 3b: per-table version resolution (decouple serving from `etl_version`)

**Date:** 2026-06-11
**Branch:** `claude/determined-dirac-5mjwge` · **PR [#544](https://github.com/ahorn885/exercise/pull/544)** · **Epic [#488](https://github.com/ahorn885/exercise/issues/488)**

## 1. What this session was

The next move off the Open-item-E / migrations-convention handoff: slice 3b, "re-architect the lookup" (Andy's call) so a *serving-relevant* Layer 0 migration touches only the changed table instead of re-stamping the whole ~14-table family. Andy had applied migration `0001` in Neon (the owed-hands deploy from the prior session) — confirmed at session start.

## 2. The finding that reshaped the work

Every Layer 0 serving query — all 26 sites across `layer2a–2e` plus the two `_q_*` helpers in `layer4/orchestrator.py` — pairs `etl_version = ?` **with** `superseded_at IS NULL`. Because supersede-before-insert keeps a table's active set at exactly one version, `superseded_at IS NULL` **alone** already selects the identical rows; the `etl_version` predicate did zero work for row-selection. Its only live job was feeding the plan-gen cache key.

That reframed "resolve `etl_version` per-table" into a fork (stop-and-ask, Trigger #3 `etl_version_set` pinning + Trigger #5):

- **Option A** — thread a per-table version map, exact-match it everywhere. Faithful but invasive (every builder contract + ~20 rebinds + cache shape), and the per-cone "snapshot pin" it appears to buy is illusory (a superseding migration mid-cone evaporates the pinned version's rows anyway).
- **Option B (chosen)** — drop `etl_version` from the WHERE clauses, serve on `superseded_at IS NULL`, keep the version only as the cache-invalidation signal.
  - **B2 (chosen):** per-table cache tag → foot-gun-free invalidation, one-time deploy cache wipe.
  - B1: family-MAX tag → no wipe but a silent-stale foot-gun (mis-numbered bump misses invalidation).

Andy picked **B / B2 / take the one-time wipe** after confirming it does not increase ongoing plan regeneration (cleanup edits = no regen; serving-relevant edits regen affected plans, same as today; only the deploy is a one-time wipe).

## 3. What shipped (PR #544, code)

- **Serving de-versioned.** All 26 serving `etl_version` predicates + binds removed; queries read `WHERE superseded_at IS NULL`. Orphaned `version_0a/0b/0c` locals and the helper params they fed (`_load_disciplines`, `_load_weekly_total_hours`, `_load_modality_groups` ×2, `_load_terrain_names`, `_load_best_proxy`, `_load_skill_capability_toggle_defs` ×2, `_load_toggle_defs`, `_load_discipline_info`, `_load_exercises`, `_load_candidates`, `_load_substitutes`, `_load_training_gaps`, `_load_phase_weekly_hours`, `_compute_activity_multiplier`, `_q_modality_groups`, `_q_craft_discipline_aliases`) removed. Builders keep accepting/validating/echoing `etl_version_set` (cache provenance), they just no longer use it in SQL.
- **Per-table discovery.** `_q_current_etl_version_set` keeps the `{0A,0B,0C}` `dict[str,str]` contract, but each value is now a per-table digest (`"sports=0A-v1.6.7;disciplines=0A-v1.6.8;…"`) built from a single `UNION ALL` over `_LAYER0_TABLE_FAMILY` (24 tables), bucketed by the table's family (NOT the version prefix), per-table max via `_max_etl_version`. Any single-table version change perturbs the digest → cache invalidates.
- **Coverage / drift.** `_LAYER0_TABLE_FAMILY` includes `terrain_gap_rules` (0C, created outside `schema.sql`, read by 2B `_load_best_proxy`); `supplement_vocabulary` deliberately excluded (own `supp_vocab.*` line, never in `etl_version_set`). `TestLayer0TableFamilyMap` guards the map against `schema.sql` drift + asserts the out-of-schema serving table.
- **Docs:** `etl/migrations/layer0/README.md` "Two edit shapes" — shape 2 rewritten to single-table (no family re-stamp); design `§5.3` updated.

## 4. Owed / next move

1. **Andy's-hands — NO Neon migration this slice.** On the next prod deploy, the cache-key value shape changes once → all plan-gen caches invalidate and regenerate on demand (same as #521; harmless). **Cold-plan live check owed:** run a cold AR plan post-deploy and confirm it still reaches `ready` with non-empty terrain + real exercise pool (serving now rides `superseded_at IS NULL`).
2. **Phase 4** (design §6): freeze the extractors + remaining workbooks (`Sports_Framework_v14.xlsx`, `AR_Exercise_Database_v19.xlsx`) + the `etl/layer0/extractors`/`run.py`/`emit_sql.py` once 2–3 migrations have gone through; then DB→xlsx export (decision B).
3. **Open (pre-existing, out of this slice):** `terrain_gap_rules` carried `0C-v2.0-r2` while `terrain_types` is `0C-v1.6.7` — under the old exact-match, 2B's best-proxy may have been resolving empty against the family `0C` version. Slice 3b incidentally **fixes** this (reads active rows regardless of version). Worth a cold-plan confirm that terrain-gap proxies now populate.

## 5. Stop-and-ask status

None pending. The Trigger #3/#5 architecture fork (decouple-serving vs per-table-exact-match; cache-tag granularity) was put to Andy and signed off (B/B2/one-time-wipe) before any code.

### 5.3 Operating notes for next session (Rule #13 read order)

1. `CLAUDE.md` · 2. `CURRENT_STATE.md` · 3. `CARRY_FORWARD.md` · 4. this handoff · 5. `./scripts/verify-handoff.sh`. Then read epic #488 + `Layer0_AuthoringModel_DBSourceOfTruth_Design_v1.md` (§5.3 + §6 phase 4 is the next slice).

## 7. §8 anchor table (Rule #10)

| Claim | File | Anchor / check |
|---|---|---|
| Per-table version digest | `layer4/orchestrator.py` | `def _q_current_etl_version_set` → `UNION ALL` over `_LAYER0_TABLE_FAMILY`; per-family digest `f"{table}={_max_etl_version(...)}"` |
| Table→family map (24, incl. terrain_gap_rules) | `layer4/orchestrator.py` | `_LAYER0_TABLE_FAMILY` dict; `"terrain_gap_rules": "0C"`; supplement_vocabulary note |
| Serving reads active rows (all 5 builders) | `layer2a/builder.py` | zero `etl_version = ?` / `= ANY(?)` remain across `layer2a`–`layer2e/builder.py`; queries end `WHERE … superseded_at IS NULL` |
| Helpers de-versioned | `layer4/orchestrator.py` | `_q_modality_groups(db)` / `_q_craft_discipline_aliases(db)` — no version arg |
| Drift guard | `tests/test_layer4_orchestrator.py` | `class TestLayer0TableFamilyMap` (3 tests) |
| Discovery test reworked | `tests/test_layer4_orchestrator.py` | `class TestQCurrentEtlVersionSet` → `test_digest_is_per_table_within_each_family` |
| Migration recipe updated | `etl/migrations/layer0/README.md` | shape 2 = single-table bump, "no whole-family re-stamp" |
| Design note | `aidstation-sources/Layer0_AuthoringModel_DBSourceOfTruth_Design_v1.md` | §5.3 "slice 3b (2026-06-11) decoupled it from serving" |

## 8. Summary

Slice 3b decouples Layer 0 serving from `etl_version`: the builders read the active row set (`superseded_at IS NULL`) directly — the version predicate was provably redundant for row-selection — so a migration serves the instant it commits. The version survives only as a **per-table** cache-invalidation digest (`_q_current_etl_version_set` + `_LAYER0_TABLE_FAMILY`), so a serving-relevant edit bumps just the changed table with no whole-family re-stamp and no advance-the-max foot-gun. One-time cost: the first deploy wipes plan caches once. Suite 2294 / 30; etl/tests 185. No Neon migration owed; cold-plan post-deploy verify is the only owed-hands item. Next: phase 4 (freeze extractors + DB→xlsx export).
