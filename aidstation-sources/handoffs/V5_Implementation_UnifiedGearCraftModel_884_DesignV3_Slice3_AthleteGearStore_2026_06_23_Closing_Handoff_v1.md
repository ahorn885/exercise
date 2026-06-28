# V5 Implementation — #884 Unified Gear/Craft Model — Slice 3 (public `athlete_gear` store + unified repo + backfill) — Closing Handoff

**Date:** 2026-06-23
**Branch:** `claude/vigilant-rubin-xhicao`
**Issue:** #884 (go-live blocker). Predecessors: slice 1 (`0022`, PR #914/#915 — merged + prod-applied), slice 2 (#919), slice 3a (`0024` `gear_discipline_aliases`, PR #923 — merged + prod-applied).
**PR:** [#932](https://github.com/ahorn885/exercise/pull/932) (opened 2026-06-28; bundled with the CLAUDE.md fix + slice 3b on the pinned branch; auto-merge SQUASH armed).

## 0. Thread continuity — STAY ON THIS THREAD (READ FIRST)

**This is a continuous build of #884, not a pick-your-next-issue session.** The next session's job is the **very next chunk of this same model**, in design v3 §15 order, and nothing else:

1. **Slice 3b — swim-gear cardio-drill gate** (§6a). ← start here
2. Slice 4 — cascade cutover (re-home the orchestrator craft reads onto `athlete_gear`/`gear_discipline_aliases`, ascending-`fidelity_rank` walk, rollerski dryland-terrain PROXY carve-out, retire `craft_discipline_aliases`).
3. Slice 5 — away overlay. 4. Slice 6 — capture UX + unified gear registry.

Do **not** drift to a different epic (Layer 3, #196, etc.) until #884's slices 3b→6 are done or Andy explicitly redirects. The authoritative plan is `designs/Unified_GearCraft_Model_And_Feasibility_884_Design_v3.md` §15. The 4-tier next-step rule (CLAUDE.md) puts this at tier 1 (**finish the in-flight task**).

## 1. What shipped

**Slice 3 — the store proper.** The first-ever public-schema home for owned gear/craft (design v3 §5.1/§5.2/§5.5/§9/§11), merging the two craft families (bikes/boats, previously the `discipline_baseline_{cycling,paddling}` CSV columns) with the owned gear toggles (ski/climbing/mountaineering/snowshoe/skimo + rollerskis — which had **no** store before #884).

**Substantive files (3):**

1. **`athlete_gear_repo.py` (NEW)** — the unified repo, collapsing `athlete_crafts_repo` + `athlete_craft_locale_repo` onto the new tables:
   - **`GEAR_REGISTRY`** — the §5.5 `gear_id` keyspace as the single app-side source of truth (`gear_id → group_kind`). Built from the existing closed craft enums (`BIKE_TYPES`/`PADDLE_CRAFT_TYPES`, no drift with the craft pickers) **+** the 7 gear-toggle slugs incl. the one new `rollerskis` (Decision 10). `group_kind ∈ {bike, paddle, ski, snow, climbing, alpine}`.
   - **owned set:** `get_athlete_gear` (ordered read, `[{gear_id, group_kind, access}]`), `replace_athlete_gear(db, uid, owned: dict[gear_id→access])` (replace-all; validates `gear_id` against the registry + `access ∈ {own, access}`; `group_kind` derived; deterministic INSERT order for the Layer-1 hash).
   - **per-locale:** `load_gear_locales` / `replace_gear_locale` / `delete_gear_locale` — mirror the craft-locale repo (locale app-validated against `locale_profiles`).
   - **eviction (§9):** `evict_layer1_on_gear_change` (→ `evict_on_layer_change(…, "layer1")`, so craft+gear share ONE eviction story) and `evict_plan_caches_on_gear_locale_change` (→ `invalidate_user(layer="gear_locale", entry_points=("plan_create","plan_refresh"))`).

2. **`init_db.py` (`_PG_MIGRATIONS` tail; public-schema → auto-applies on deploy):**
   - DDL: `athlete_gear (user_id, gear_id, group_kind, access NOT NULL DEFAULT 'own', created_at, PK(user_id, gear_id))` + `idx_athlete_gear_user`; `athlete_gear_locale (user_id, gear_id, locale, created_at, PK(user_id, gear_id, locale))` + `idx_agl_user`; `ALTER athlete_event_windows ADD COLUMN IF NOT EXISTS brought_gear TEXT`.
   - **Backfill (idempotent, `ON CONFLICT DO NOTHING`):** each owned bike/paddle craft CSV token explodes (`string_to_array` + `CROSS JOIN LATERAL unnest`) into one `athlete_gear` row (`group_kind` by family, `access='own'`), **filtered to the closed §5.5 craft slugs** (IN-lists built from `BIKE_TYPES`/`PADDLE_CRAFT_TYPES`) so a stale/pruned slug (legacy 'surfski') can't leak in as an unknown `gear_id`; `athlete_craft_locale` → `athlete_gear_locale` 1:1 (craft_slug IS a gear_id, same filter); `brought_craft` → `brought_gear` verbatim CSV copy (NULL/empty-guarded).

3. **`tests/test_athlete_gear_repo.py` (NEW, +21)** — fake-conn unit tests mirroring `test_athlete_crafts_repo`: the §5.5 keyspace guard (registry == the `0024` gear_id set; group_kinds = the closed set), the owned read/write (ordering, derived group_kind, replace-all, unknown-gear/bad-access reject-and-write-nothing), the per-locale read/write/delete (locale-existence precedence, dedup+order, foreign-locale + unknown-gear rejects), and the two eviction surfaces (spied — confirm `layer1` vs `plan_create/plan_refresh`).

**Decisions made this session (not new architecture — executing ratified design v3):**
- **Eviction = `"layer1"`** for `athlete_gear` (not the narrower `plan_create/plan_refresh` of §9's prose). Resolves the §9 vs §4.2-handoff tension toward §9's "craft + gear share one eviction story" — gear evicts identically to crafts, which live in `Layer1DisciplineBaselines`. Inert until slice 4 re-homes the read, then correct.
- **`created_at`** added to both tables beyond the v3 §5.1 column sketch — matches the sibling `athlete_craft_locale` / `athlete_event_windows` audit convention (the sketch omits the obvious audit column its siblings carry). Zero-cost, unread.
- **`access`** is in the write signature (schema has it; §10 UX is own/have-access) but only `'own'` is populated until slice-6 capture sets it.

## 2. Staging — why nothing reads it yet (READ before slice 4)

Per design v3 §15, slice 3 builds the store + backfills it + lands the read/write surface; **nothing reads it yet.** The orchestrator feasibility cascade cuts over onto `athlete_gear`/`gear_discipline_aliases` in **slice 4** (re-home `_collect_athlete_crafts`/`_q_craft_*`); first capture (the "Your gear" surface) is **slice 6**. The OLD craft path (`athlete_crafts_repo` → `discipline_baseline_*`, `athlete_craft_locale_repo`) stays authoritative until then. So slice 3 is inert foundation — same staging theme as slice 3a's `gear_discipline_aliases`.

**Slice-4 trap (see CARRY_FORWARD #884 ⚠):** the backfill is a one-time seed (`ON CONFLICT DO NOTHING`) — additions self-heal on re-deploy but **removals do NOT propagate**. When slice 4 makes the cascade *read* `athlete_gear` while the craft picker still *writes* `discipline_baseline_*` (the write path doesn't move until slice 6), the new store can drift. Slice 4 must decide: sync `athlete_gear` from the craft-picker writes, or move the write path forward — don't silently read a stale store.

## 3. Verification

- **Full CI gate path** (`tests/ etl/tests/`, the gate suite): **3646 passed / 30 skipped** — the only warnings are the 3 pre-existing #217 Layer3B `evidence_basis` ones. No regression from the new `from athlete import …` at `init_db` top (circular-import-free; `test_init_db_schema` + the craft repo tests pass).
- **Real PG16** (local container cluster, port 5439). The **actual** `_PG_MIGRATIONS` strings were pulled from `init_db` (no hand-copy) and run against a representative dataset (multiple bikes/paddles, NULL CSV, a stale 'surfski', craft↔locale rows, brought_craft + NULL): DDL applies clean; backfill routes `group_kind` (7 rows expected, exact match); **'surfski' filtered out** of both `athlete_gear` and `athlete_gear_locale`; `brought_gear` copied verbatim + NULL preserved; **idempotent re-apply** (counts stable at 7/2); and an addition via the old path **self-heals** on re-apply (7→8). Harness: `scratchpad/verify_gear_backfill.py`.
- **No Neon apply owed** — public-schema, auto-applies on the deploy that lands the merge.

## 4. Owed / next

### 4.1 Owed
- **Open the PR** — on Andy's go (operating flow: PRs open only on say-so). Ready, not draft; arm `enable_pr_auto_merge` (SQUASH). The branch is `claude/vigilant-rubin-xhicao`.
- **`Provider_Inbound_Matrix_v2` §12 rollerski footnote** — still owed from slice 3a (logged in CARRY_FORWARD; doc nit).

### 4.2 Next (design v3 §15 order)
- **Slice 3b (swim-drill gate)** — Layer-0 `cardio_drill_gear_requirements (exercise_id, gear_id)` + the `compute_cardio_drill_pool_ids` gear gate (per_phase.py, clones the live constituent-sport gate); **Trigger #2 — confirm the minimal swim-gear vocab (`pull_buoy`/`paddles`/`kickboard`/…) against the active swim-drill EX rows before seeding (no padding).** NOT a discipline-feasibility gate (D-004 stays feasible on water), NOT `equipment_required`.
- **Slice 4 (cascade)** — re-home the orchestrator craft reads onto `athlete_gear`/`gear_discipline_aliases`; ascending-`fidelity_rank` walk; the **rollerski dryland-terrain PROXY carve-out** (design v3 §6/Decision 6 — degraded gear on its own terrain; do NOT silently demand D-028's snow); retire `craft_discipline_aliases` (forced redump — heed the redump-fold rule in `etl/migrations/layer0/README.md`). Heed the §2 read/write-authority trap.

## 6. Owed / operating notes

### 6.3 Read order for next session (Rule #13)
1. `CLAUDE.md` — stable rules.
2. `CURRENT_STATE.md` — last-shipped block (this session) + the slice-1/2/3a predecessors.
3. `CARRY_FORWARD.md` — the #884 rolling item (slice progress + the ⚠ slice-4 attention items) + the Provider §12 footnote nit.
4. This handoff.
5. `designs/Unified_GearCraft_Model_And_Feasibility_884_Design_v3.md` — the authoritative slice plan (§15) + the pinned keyspace (§5.5) + eviction (§9) + backfill (§11).
6. `./scripts/verify-handoff.sh`.

## 8. Session-end verification (Rule #10)

| Claim | File | Check |
|---|---|---|
| Unified repo exists; collapses both craft repos | `athlete_gear_repo.py` | grep `def get_athlete_gear`, `def replace_athlete_gear`, `def load_gear_locales`, `def replace_gear_locale`, `def delete_gear_locale`, `def evict_layer1_on_gear_change`, `def evict_plan_caches_on_gear_locale_change` |
| §5.5 keyspace as single source | `athlete_gear_repo.py` | grep `GEAR_REGISTRY` — 16 gear_ids = bike/paddle craft enums + `classic_xc_ski`/`skate_xc_ski`/`rollerskis`/`snowshoes`/`climbing_gear`/`mountaineering`/`skimo_at` |
| DDL + backfill in migrations | `init_db.py` | grep `CREATE TABLE IF NOT EXISTS athlete_gear `, `athlete_gear_locale`, `ADD COLUMN IF NOT EXISTS brought_gear`, the two `INSERT INTO athlete_gear … unnest(string_to_array` backfills (filtered by `_GEAR_BACKFILL_*_IN`), the `athlete_gear_locale` 1:1 backfill, the `brought_craft → brought_gear` UPDATE |
| Keyspace guard + behavior tests | `tests/test_athlete_gear_repo.py` | `test_registry_matches_layer0_keyspace`; suite green (`pytest tests/test_athlete_gear_repo.py` = 21 passed) |
| Gate + PG16 verification | (suite + local PG, not committed) | `tests/ etl/tests/` 3646 passed / 30 skipped; `scratchpad/verify_gear_backfill.py` ALL CHECKS PASSED (surfski filtered, idempotent, self-heal) |
| Pointer updated | `CURRENT_STATE.md` | "Last shipped session" names slice 3 (store); slice 3a demoted to predecessor |

**Substantive files (3):** `athlete_gear_repo.py`, `init_db.py`, `tests/test_athlete_gear_repo.py`. (Bookkeeping: `CURRENT_STATE.md`, `CARRY_FORWARD.md`, this handoff.)
