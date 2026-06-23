# V5 Implementation — #884 Unified Gear/Craft Model — Design v3 + Slice 3a (L0 `gear_discipline_aliases`) — Closing Handoff

**Date:** 2026-06-23
**Branch:** `claude/unified-gear-craft-model-6noxyt`
**Issue:** #884 (go-live blocker). Predecessor: slice 1 (`0022`, PR #914/#915 merged) + slice 2 boundary de-drift (#919).
**PR:** #PLACEHOLDER (opened + auto-merge armed this session).

## 0. Thread continuity — STAY ON THIS THREAD (READ FIRST)

**This is a continuous build of #884, not a pick-your-next-issue session.** The next session's job is the **very next chunk of this same model**, in this order, and nothing else:

1. **Slice 3 — the public `athlete_gear` store** (its own PR; see §4.2). ← start here
2. Slice 3b — swim-drill gear gate.
3. Slice 4 — cascade cutover (re-home reads onto `gear_discipline_aliases`, fidelity walk, rollerski dryland carve-out, retire `craft_discipline_aliases`).
4. Slice 5 — away overlay. 5. Slice 6 — capture UX + gear registry.

Do **not** drift to a different epic (Layer 3, #196, etc.) until #884's slices 3→6 are done or Andy explicitly redirects. The authoritative plan is `designs/Unified_GearCraft_Model_And_Feasibility_884_Design_v3.md` §15 — follow that slice order. The 4-tier next-step rule (CLAUDE.md) puts this at tier 1 (**finish the in-flight task**): #884 is in flight and partially built; close its slices before anything new.



## 1. What shipped

The session began as "plan the gear store" and Andy opened two design decisions while planning, then said build. Delivered: **design v3** + the **Layer-0 alias foundation** that encodes the freshly-ratified fidelity decision.

**Design decisions (Andy, 2026-06-23 — two AskUserQuestion rounds + plain-language confirm):**
- **D1 — ordinal fidelity.** Rollerskis are **owned gear**, a degraded **dryland** substitute for D-028 Cross-Country Skiing, ranked **above** the gym ski-erg. This forces fidelity from the v2 binary `{primary,degraded}` to an **integer `fidelity_rank`** (0 = best). D-028 ladder: classic_xc_ski 0 / skate_xc_ski 1 / rollerskis 2; the ski-erg stays the gear-independent INDOOR fallback (`session_feasibility._DISCIPLINE_INDOOR_MACHINES`), so "rollerski before ski-erg" falls out of the PROXY-over-INDOOR tier order.
- **D2 — gear enables cardio drills, never strength exercises.** Swim gear (pull buoy / paddles / kickboard) gates **`cardio_drills[]` pool membership** via a new `cardio_drill_gear_requirements` relation read by `compute_cardio_drill_pool_ids` (clones the live constituent-sport gate) — NOT discipline feasibility (D-004 stays feasible on water), NOT `equipment_required`. Slice 3b.
- **Rollerski promotion** reconciled against `Provider_Inbound_Matrix_v2` §12 (which had lumped rollerski with "machines"): inbound classification unchanged; v3 adds the ownership/feasibility treatment. Footnote owed on the matrix.

**Design v3** — `designs/Unified_GearCraft_Model_And_Feasibility_884_Design_v3.md` (v2 → `archive/superseded-specs/` per Rule #12). Records D1/D2 (Decisions 8 revised + 10/11/12), the **pinned `gear_id` keyspace** (§5.5 — unspecified in v2), the gear-gated-drill mechanism (§6a), and a **re-sequenced slice list** (§15): 1 catalog (done 0022), 2 boundary (done #919), **3 public store**, **3a L0 aliases (this)**, **3b swim-drill gate**, 4 cascade cutover, 5 away, 6 UX+registry.

**Slice 3a** — `etl/migrations/layer0/0023_gear_discipline_aliases.sql`. Creates `layer0.gear_discipline_aliases (id, gear_id, discipline_id, group_kind, fidelity_rank INTEGER NOT NULL DEFAULT 0, etl_version, etl_run_at, superseded_at)` and seeds **22 active rows** at `etl_version='0A-v1.9.1'`:
- 12 craft aliases migrated 1:1 from `craft_discipline_aliases` (rank 0): kayak/canoe/packraft/raft/sup (paddle), road/gravel×3/mountain×2/tt (bike).
- 10 gear-toggle rows: climbing_gear→D-012/013/014 (climbing); snowshoes→D-017 (snow); mountaineering→D-018 (alpine); skimo_at→D-021/022 (alpine); **classic_xc_ski→D-028 rank 0 / skate_xc_ski→D-028 rank 1 / rollerskis→D-028 rank 2 (ski)**.

Idempotent (`CREATE TABLE IF NOT EXISTS` + `DELETE WHERE etl_version='0A-v1.9.1'` then re-`INSERT`). Self-contained verify `DO`-block: asserts 22 active rows + the D-028 ladder carries exactly 3 distinct `fidelity_rank`s.

## 2. Staging — why nothing reads it yet (READ before slice 4)

Design v3 §5.3 stages the alias table **alongside** the live `craft_discipline_aliases` rather than renaming it. The orchestrator read paths (`_q_craft_discipline_aliases`/`_q_craft_group_kind`/`_q_craft_terrain_compatibility`, `orchestrator.py:335/362/374`; `_collect_athlete_crafts:215`) still read the **craft** table. The cutover to `gear_discipline_aliases` is **slice 4**, which then retires `craft_discipline_aliases` (the v2 "forced redump finding B"). Temporary craft-row duplication across the two tables during 3a→4 is expected and harmless — nothing serves from the new table, so `0023` changes **no** served output and needs no cache-version coordination (`_q_current_etl_version_set` doesn't yet enumerate the new table).

## 3. Verification

- **Full CI gate path replicated locally** (container PG16 in `/tmp/pgtest`, started as the `postgres` user): loaded the v1.9.0 baseline (stripping the PG17-only `\restrict`/`\unrestrict` meta-commands + the `transaction_timeout` GUC — local-PG16-only; CI runs PG17), applied `0023`, ran `python -m etl.layer0.validate_layer0` → **PASS** (all 11 checks clean/waived). D-028 ladder prints 0/1/2. Idempotent re-apply holds at 22 active rows.
- The v2-baseline `transaction_timeout` strip is a **local-only** workaround; the real CI gate uses PG17 where the GUC is valid — no migration change needed.

## 4. Owed / next

### 4.1 Owed
- **`layer0-apply`** of `0023` to prod Neon (Andy one-tap) — owed once the PR opens. Idempotent; safe to re-run.
- **`Provider_Inbound_Matrix_v2` §12 footnote** — note the rollerski ownership/feasibility promotion (Decision 10) so the two docs don't drift. (Doc nit; logged in CARRY_FORWARD.)

### 4.2 Next (the store proper)
- **Slice 3 (public store)** — its OWN PR (init_db backfill auto-applies to prod, design v3 §18): `athlete_gear (user_id, gear_id, group_kind, access)` + `athlete_gear_locale` + `brought_gear` column in `init_db.py` `_PG_MIGRATIONS`; backfill from `discipline_baseline_{cycling,paddling}` craft CSVs + `athlete_craft_locale` + `athlete_event_windows.brought_craft`; new unified `athlete_gear_repo.py` collapsing `athlete_crafts_repo.py` + `athlete_craft_locale_repo.py`; eviction per §9 (mirror `evict_layer1_on_crafts_change` / `evict_plan_caches_on_craft_locale_change`). `gear_id` keyspace per v3 §5.5. Keep the old craft path live; cutover is slice 4.
- **Slice 3b (swim-drill gate)** — Layer-0 `cardio_drill_gear_requirements (exercise_id, gear_id)` + the `compute_cardio_drill_pool_ids` gear gate (per_phase.py); confirm the minimal swim-gear vocab against the active swim-drill EX rows before seeding (Trigger #2 — no padding).
- **Slice 4 (cascade)** — re-home the orchestrator craft reads onto `athlete_gear`/`gear_discipline_aliases`; ascending-`fidelity_rank` walk; the **rollerski dryland-terrain PROXY carve-out** (design v3 §6/Decision 6 — degraded gear on its own terrain; do NOT silently demand D-028's snow); retire `craft_discipline_aliases` (forced redump — heed the redump-fold rule in `etl/migrations/layer0/README.md`).

## 6. Owed / operating notes

### 6.3 Read order for next session (Rule #13)
1. `CLAUDE.md` — stable rules.
2. `CURRENT_STATE.md` — last-shipped block (this session) + the slice-1/slice-2 predecessors.
3. `CARRY_FORWARD.md` — rolling items (Provider §12 footnote nit added).
4. This handoff.
5. `designs/Unified_GearCraft_Model_And_Feasibility_884_Design_v3.md` — the authoritative slice plan + the pinned keyspace.
6. `./scripts/verify-handoff.sh`.

## 8. Session-end verification (Rule #10)

| Claim | File | Check |
|---|---|---|
| Migration `0023` exists, creates `gear_discipline_aliases` + 22 rows | `etl/migrations/layer0/0023_gear_discipline_aliases.sql` | grep `CREATE TABLE IF NOT EXISTS layer0.gear_discipline_aliases` + the 22 VALUES rows + the verify `DO $$` |
| D-028 ordinal ladder 0/1/2 | same | grep `classic_xc_ski`…`0`, `skate_xc_ski`…`1`, `rollerskis`…`2` |
| Design v3 present; v2 archived | `designs/…_v3.md` + `archive/superseded-specs/…_v2.md` | both files exist; v3 §5.3 has `fidelity_rank INTEGER`, §5.5 keyspace table, §15 re-sliced |
| Gate passes on baseline+0023 | (local, not committed) | `validate_layer0` PASS — re-runnable per §3 recipe |
| Pointer updated | `CURRENT_STATE.md` | "Last shipped session" names design v3 + slice 3a; slice-1 demoted to predecessor |

**Substantive files (2):** `designs/…_v3.md`, `etl/migrations/layer0/0023_gear_discipline_aliases.sql`. (Bookkeeping: `CURRENT_STATE.md`, `CARRY_FORWARD.md`, this handoff, v2 archive move.)
