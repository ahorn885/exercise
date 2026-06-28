# V5 Implementation — #884 Unified Gear/Craft Model — Slice 4a + 4.2 (cascade read cutover + craft write-sync) — Closing Handoff

**Session:** Slice 4 of #884, started. Shipped the behavior-preserving read cutover (4a) and the craft write-path-forward (4.2); paused before the cascade-extension (4b) and redump (4.3).
**Date:** 2026-06-28
**Predecessor handoff:** `V5_Implementation_UnifiedGearCraftModel_884_DesignV3_Slice3b_GearGatedCardioDrills_2026_06_23_Closing_Handoff_v1.md`
**Branch:** `claude/gear-gated-cardio-drills-xd9q0l` (harness-pinned; kept — the gear scope is close enough, push constraint overrides the rename rule)
**Status:** 4 substantive files (orchestrator + 2 repos + 1 cascade-read test repoint; the 2 other touched test files are test-double updates) — under ceiling. Bookkeeping + plan + this handoff outside the count. Suite green 3678/30.

---

## 0. Thread continuity — STAY ON THIS THREAD

Continuous build of #884. **Next is slice 4b** (the cascade fidelity-rank walk + rollerski carve-out + 2C feed + gear-toggle capture + Layer-0 migration `0026`), **then 4.3** (forced redump retiring `craft_discipline_aliases` + the equipment strip). Do not drift to another epic until #884's 4b→4.3→5→6 are done or Andy redirects (tier-1 finish-the-in-flight-task). Design: `designs/Unified_GearCraft_Model_And_Feasibility_884_Design_v3.md` §6/§9/§15.4. Plan: `plans/UnifiedGearCraft_884_Slice4_CascadeCutover_Plan_v1.md`.

---

## 1. Session-start verification (Rule #9)

Anchor-checked the predecessor (slice 3b) handoff's claims against on-disk + prod state.

| Claim | Anchor | Result |
|---|---|---|
| PR #932 (slices 3+3b) merged | `git log` → `42216e1` on main | ✅ |
| `0025` applied to prod | `layer0-apply` run #17, head_sha `42216e1`, log `0025: OK — seeded EX126→pull_buoy, EX128→kickboard` | ✅ |
| `gear_discipline_aliases` (0024) live | craft rows byte-identical to `craft_discipline_aliases` (grep diff) | ✅ |
| Slice-3b handoff + CURRENT_STATE/CARRY_FORWARD said "auto-merge armed / apply owed" | grep | ❌ stale (written pre-merge) |

**Reconciliation note:** The slice-3b docs were written before #932 merged, so all four pointers still read "auto-merge SQUASH armed / Neon apply owed." Fixed as the first action (commit `20dfb9e`): flipped CURRENT_STATE, CARRY_FORWARD, and both slice-3/3b handoff PR lines to "merged `42216e1` / `0025` applied (run #17)." No on-disk *code* drift — only stale status pointers.

---

## 2. Session narrative

- Andy: "#932 should have a handoff." Found #932 already ships two slice handoffs (3 + 3b) + folded the ref into the rolling docs — but all written pre-merge. The real gap was the stale "armed/owed" status → fixed (the bookkeeping above).
- Andy: what's the next slice? → slice 4 (cascade cutover). Confirmed `0025` already applied (Andy was right; run #17). Thorough doc/code sweep: no slice-4 branch/handoff/sub-issue exists (no duplicate work); all target symbols present.
- Andy ratified: execute slice 4; close the read/write authority gap by **pulling the S6 write path forward** (option b); **write-path only** (no new "Your gear" UX); **reuse an existing paved terrain** for rollerskis; **order 4.2 before 4b**.
- Two parallel Explore agents mapped the read path and the write/redump path. Key finding: slice 4 is **not** a mechanical swap — the cascade has no `fidelity_rank` concept and only handles bike/paddle; the ski/snow/climbing/alpine gating + rollerski ladder is genuinely new behavior (→ deferred to 4b). Split slice 4 into 4a (safe read cutover) + 4.2 (craft write-sync) + 4b (cascade extension) + 4.3 (redump).
- Built + verified + pushed 4a and 4.2. Paused before 4b at Andy's direction (4b is a cross-layer change carrying a migration he applies — a natural boundary).

---

## 3. File-by-file edits

### 3.1 `layer4/orchestrator.py` (modified) — slice 4a
- `_collect_athlete_crafts` (`:233`): now reads `layer1_payload.owned_gear` (slice 3b's `athlete_gear` read, rides `layer1_hash`) filtered to `_CRAFT_ALIAS_GROUP_KINDS = {bike, paddle}` (`:227`), instead of the cycling/paddling discipline baselines. Still pure on `layer1_payload` — call sites unchanged. The gear store's craft rows are backfilled 1:1, so output is identical.
- `_q_craft_discipline_aliases` (`:345`) + `_q_craft_group_kind` (`:380`): read `layer0.gear_discipline_aliases` (migration 0024) in place of `craft_discipline_aliases`. The bike/paddle alias rows are **byte-identical** between the two tables (verified by grep diff), so craft behavior is unchanged; the unified table additionally carries gear-toggle aliases (harmless to craft consumers — they only key on owned bike/paddle slugs).
- `_LAYER0_TABLE_FAMILY` (`:1999`): `+= "gear_discipline_aliases": "0A"` so a re-seed invalidates the version-set digest now that the cascade reads it. `craft_discipline_aliases` stays mapped until slice 4.3 retires it. `craft_terrain_compatibility` untouched (still read).

### 3.2 `athlete_gear_repo.py` (modified) — slice 4.2
- `replace_owned_gear_for_kinds(db, user_id, owned, group_kinds)` (NEW, `:125`): a per-surface **scoped** replace-all — rewrites only rows whose `group_kind ∈ group_kinds`, preserving gear of other kinds. Validates gear_id keyspace + on-surface group_kind (rejects off-surface gear_ids) + access set; writes nothing on a violation. Lets crafts ({bike,paddle}), gear toggles (4b), and swim (S6) each own their slice of the one store.

### 3.3 `athlete_crafts_repo.py` (modified) — slice 4.2
- `replace_athlete_crafts` (`:62`): after the baseline upserts, forward-syncs the bike/paddle rows into `athlete_gear` via `replace_owned_gear_for_kinds(..., {"bike","paddle"})`. Both craft writers (profile `/crafts` + onboarding step 5) route through this repo → both inherit the sync. Baselines stay authoritative for the Layer 1 payload (builder reads them); this is a forward-sync, not a move. Import added at `:25`.

---

## 4. Code / tests

Suite: **tests/ + etl/tests/ 3678 passed / 30 skipped** (only the 3 pre-existing #217 Layer3B `evidence_basis` warnings).
- `tests/test_layer4_terrain_feasibility_wiring.py` — `_cone` fixture sets `owned_gear` (the new read source) alongside the baselines.
- `tests/test_athlete_gear_repo.py` — `TestReplaceForKinds` (+4: scoped delete preserves other kinds; empty clears only those kinds; off-surface gear rejected; unknown id rejected).
- `tests/test_athlete_crafts_repo.py` — `test_valid_upserts…` asserts the baseline upserts + the new athlete_gear sync writes.
- `tests/test_onboarding_skills.py` — two call-count assertions updated for the sync DELETE/INSERT + a gear-insert assertion.

---

## 6. Next session pointers

### 6.1 Architect-recommended next forward move
**Slice 4b** — extend `resolve_craft_terrain_feasibility` (`layer4/session_feasibility.py:365`) from `_CRAFT_GROUP_KINDS = {bike,paddle}` to all gear kinds, ordered by ascending `fidelity_rank`:
- Thread `fidelity_rank` from `gear_discipline_aliases` (add a `_q_gear_aliases` returning rank, or extend the existing readers) and order `own_crafts`/`proxy_crafts` by it.
- Rollerski carve-out **falls out of the existing structure**: it's a rank-2 owned "craft" for D-028 whose required terrain (snow `TRN-012`) is absent but whose own compatible terrain (`TRN-001` Road/Paved) is present → the existing Tier 2 ("own the craft, ride an alternate compatible terrain") fires → PROXY. No special-case branch needed.
- **Migration `0026`** (Layer-0, needs `layer0-apply`): seed `craft_terrain_compatibility` ski-gear rows — `classic_xc_ski`→`TRN-012`, `skate_xc_ski`→`TRN-012`, `rollerskis`→`TRN-001` (reuse, no new vocab — Andy 2026-06-28). Verify-DO block asserting 3 active rows + no dangling refs (mirror 0025).
- Feed `cluster_gear_toggle_states` from `athlete_gear` at `orchestrator.py` 2C call site (currently `={}`) — the #298 un-starve.
- Add the **gear-toggle capture surface** (climbing_gear/snowshoes/mountaineering/skimo_at/classic/skate/rollerskis → `athlete_gear` via `replace_owned_gear_for_kinds(..., {"ski","snow","climbing","alpine"})`, reuse the profile gear-tab checkbox pattern, no new UX). This is where the cascade first *consumes* toggles, so it belongs here, not 4.2.
- Tests: rank-walk (classic>skate>rollerski), rollerski-dryland PROXY, climbing gear+skill matrix, toggle-capture round-trip.

Then **slice 4.3** — forced redump retiring `craft_discipline_aliases` (heed the redump-fold rule) + the equipment strip (supersede `pull_buoy`/`kickboard`/`Swim fins` from `equipment_items` + strip from EX126/EX128 `equipment_required`, 0B supersede+re-insert → global cache invalidation).

### 6.2 Alternative pivots
None recommended — stay on #884 (tier-1).

### 6.3 Operating notes for next session (Rule #13)
1. `CLAUDE.md` — stable rules.
2. `CURRENT_STATE.md` — last-shipped (this) + the #884 predecessors.
3. `CARRY_FORWARD.md` — the #884 rolling item (slice-4 PROGRESS line: 4a/4.2 done; 4b/4.3 next; resolved terrain ids).
4. This handoff + `plans/UnifiedGearCraft_884_Slice4_CascadeCutover_Plan_v1.md` (the file-grounded slice-4 plan).
5. `./scripts/verify-handoff.sh`.

---

## 7. Decisions pinned

| # | Decision | Picked by | Rationale |
|---|---|---|---|
| 1 | Close the read/write gap by pulling the S6 write path forward (option b) | Andy 2026-06-28 | One store the cascade reads + the picker writes; no write-through off the old CSVs |
| 2 | Write-path only — no new "Your gear" UX | Andy 2026-06-28 | Repoint, don't redesign; the unified surface stays S6 proper |
| 3 | Rollerskis reuse an existing paved terrain (`TRN-001`), no new vocab | Andy 2026-06-28 | No-padding; classic/skate→snow `TRN-012`, rollerskis→Road/Paved |
| 4 | Order 4.2 (write) before 4b (cascade) | Andy 2026-06-28 | Capture must write the store before the gate bites |
| 5 | Re-slice: gear-toggle capture → 4b (not 4.2) | Claude (flagged) | Building toggle UI in 4.2 would be dormant until 4b consumes those kinds; the documented gap is craft-specific |

---

## 8. Session-end verification (Rule #10)

| Claim | File | Check |
|---|---|---|
| `_collect_athlete_crafts` reads `owned_gear`, filtered to bike/paddle | `layer4/orchestrator.py` | grep `layer1_payload.owned_gear` + `_CRAFT_ALIAS_GROUP_KINDS` |
| `_q_craft_*` read `gear_discipline_aliases` | `layer4/orchestrator.py` | grep `FROM layer0.gear_discipline_aliases` → 2 hits |
| Family map tracks the new alias table | `layer4/orchestrator.py` | grep `"gear_discipline_aliases": "0A"` |
| Scoped per-surface gear write | `athlete_gear_repo.py` | grep `def replace_owned_gear_for_kinds` |
| Craft repo forward-syncs athlete_gear | `athlete_crafts_repo.py` | grep `replace_owned_gear_for_kinds(` in `replace_athlete_crafts` |
| Suite green | (local) | `tests/ etl/tests/` 3678 passed / 30 skipped |
| Working tree clean | — | `git status` clean at each push |

---

## 9. Files shipped this session

**Substantive (4 files):**
1. `layer4/orchestrator.py` — 4a read cutover (3 readers + family map)
2. `athlete_gear_repo.py` — 4.2 scoped per-surface write
3. `athlete_crafts_repo.py` — 4.2 craft→gear forward-sync
4. `tests/test_layer4_terrain_feasibility_wiring.py` — cascade-read fixture repoint (owned_gear)

**Bookkeeping / test-doubles (outside the ceiling):**
5. `tests/test_athlete_gear_repo.py` (+4 scoped-write tests)
6. `tests/test_athlete_crafts_repo.py` (sync assertion)
7. `tests/test_onboarding_skills.py` (call-count + gear-insert assertions)
8. `aidstation-sources/plans/UnifiedGearCraft_884_Slice4_CascadeCutover_Plan_v1.md` (NEW — the plan)
9. `CURRENT_STATE.md`, `CARRY_FORWARD.md`, the two slice-3/3b handoff PR lines (bookkeeping), this handoff

---

## 10. Carry-forward updates

`CARRY_FORWARD.md` #884: read/write gap marked **RESOLVED for crafts** (4.2); a slice-4 PROGRESS line (4a/4.2 done+pushed; 4b/4.3 next with the resolved terrain ids). The `Provider_Inbound_Matrix_v2` §12 rollerski footnote remains owed (slice-3a doc nit).

---

**End of handoff.**
