# V5 Implementation — #884 Unified Gear/Craft Model — Slice 1 (Gear Toggle Catalog) — Closing Handoff

**Date:** 2026-06-23
**Branch:** `claude/unified-gear-craft-model-pw4kb0`
**PR:** #914 (MERGED — squash) — first build slice off the #884 design.
**Issue:** #884 (go-live blocker); advances the live part of #298 (starved gear-toggle subsystem).
**Design (ratified):** `aidstation-sources/designs/Unified_GearCraft_Model_And_Feasibility_884_Design_v2.md`
**Predecessor handoff:** `handoffs/V5_Design_UnifiedGearCraftModel_884_2026_06_23_Closing_Handoff_v1.md` (design-only).

Shipped one Layer 0 migration — **`etl/migrations/layer0/0022_unify_gear_toggle_catalog.sql`** — the "catalog shape only" subset of design slice 1. Applies to prod via the `layer0-apply` Action (Andy one-tap), then `layer0-redump`.

---

## 1. What shipped

A single migration (idempotent, atomic verify-DO-block, mirroring #623's `0008` / #622's `0007`):

**0C — `sport_specific_gear_toggles` reshape (active set 12 → 6):**
- **Delete** 4 orphans that gate nothing and belong to no modelled sport in scope: Bouldering, Whitewater paddling setup, Fencing setup, Shooting setup.
- **Roll up** the 3 roped-climbing toggles (Climbing — roped, Rappelling / abseiling, Via ferrata) into one **"Climbing gear"** gating `{D-012 Rock Climbing, D-013 Abseiling, D-014 Via Ferrata}`; `also_satisfies` → `{}` (the multi-row gate subsumes the one-hop alias and no longer dangles to a deleted toggle name).
- **Rename** "Touring/AT ski setup" → **"Skimo / AT setup"** (gating stays `{}` — see §3 finding A).
- Survivors untouched: Classic XC ski setup, Skate XC ski setup, Mountaineering, Snowshoeing setup (keeps its `D-017` gate).

**0B — de-drift the 2 active exercises that gate on a renamed toggle** (same pattern as 0007/0008; 0017/0021 already culled the rest):
- **EX170** "SkiMo Race Transition Drill": `equipment_required {Touring/AT ski setup}` → `{Skimo / AT setup}`.
- **EX101** "Hangboard Open-Hand Hold": structured-substitute requirement `[["Climbing — roped"]]` → `[["Climbing gear"]]`.

**Cache invalidation:** serving-relevant on both families, so re-inserted toggles land at `0C-v1.6.8` (current active toggles all `0C-v1.6.7`) and de-drifted exercises at `0B-v1.6.19` (current 0B numeric max active `0B-v1.6.18`; `_max_etl_version` compares integer tuples — string-max mis-sorts, see §3). Both tables already in `_LAYER0_TABLE_FAMILY` → no family-map change, no public-schema DDL, no app/Python change.

---

## 2. Why this is a SUBSET of design slice 1 (Andy ratified the re-scope, 2026-06-23)

Design slice 1 was framed as "L0 catalog + the `gear_discipline_aliases` rename + `fidelity_rank` + gear alias rows + new gated-discipline wiring," assumed inert to the app. Investigation contradicted that framing on three points; Andy chose **"Catalog shape only (safe)"** via AskUserQuestion. The deferred pieces (table rename, `fidelity_rank`, gear alias rows, new gated wiring) all cluster naturally with the **gear consumer + athlete-gear store** (design slices 3–4), so they move there.

Two AskUserQuestion decisions this session:
- **Skimo toggle:** *reuse + rename* the existing "Touring/AT ski setup" row → "Skimo / AT setup" (NOT add-new — the row already exists; see §3 finding A).
- **Slice 1 scope:** *Catalog shape only (safe)* — no table rename, no `paired_equipment_categories` drop, no new gated wiring this slice.

---

## 3. Findings that re-shaped the plan (read before building slice 3/4)

**A. The "Skimo / AT setup" toggle already exists** — it is the live "Touring/AT ski setup" row (id 265, `0C-v1.6.7`), whose description already enumerates SkiMo/AT gear. Design §3 said "ADD (new vocab)"; reality is a **rename**, not an insert. No new-vocab Trigger-#2 padding involved.

**B. The hard table rename `craft_discipline_aliases → gear_discipline_aliases` cannot ship in one PR.** Three constraints contradict each other for a `RENAME`:
- `layer0-gate` loads the committed baseline (which has `craft_discipline_aliases`) and applies migrations on top — so the baseline **must keep the old name** for the rename to apply.
- `TestLayer0TableFamilyMap` (`tests/test_layer4_orchestrator.py`) reads that **same baseline snapshot** (`etl/output/layer0_etl_v*.sql`, newest) and requires every baseline table to be a key in `_LAYER0_TABLE_FAMILY` — so the map can't drop `craft_discipline_aliases`.
- But post-rename **live**, `_q_current_etl_version_set` (`layer4/orchestrator.py:1997`) iterates the map and runs `FROM layer0.{table}` for every key → querying `craft_discipline_aliases` after the rename throws, breaking plan-gen.

The baseline only reconciles via a post-apply `layer0-redump`. **Resolution:** do the rename in the gear-consumer slice, sequenced as: migration renames → `layer0-apply` → `layer0-redump` (baseline now carries `gear_discipline_aliases`) → in the SAME or a follow-up PR, repoint the map key + `orchestrator.py` reads. The redump must land before (or with) the map/app repoint.

**C. The toggle catalog is read live by Layer 2C.** `layer2c/builder.py:152` (`_load_toggle_defs`, called every plan-gen at line 828) selects `paired_equipment_categories`, `also_satisfies`, `gated_discipline_ids`, `display_label`. Consequences:
- **Dropping `paired_equipment_categories`** would break that SELECT → requires a coupled `layer2c/builder.py` edit deployed with the migration. Deferred.
- **Wiring new `gated_discipline_ids`** (Classic/Skate→D-028, Mountaineering→D-018, Skimo→D-021/022) emits `toggle_off_for_discipline` flags (builder.py ~582-603) — but both 2C call sites pass `cluster_gear_toggle_states={}` (orchestrator.py:1098, 1530), so until the athlete-gear **store** exists to turn a toggle ON, every gear discipline would emit a spurious "toggle off" flag. Gating must land **with** the store. Deferred.

**D. `_max_etl_version` is integer-tuple, not lexical.** `max(etl_version)` in SQL returns `0B-v1.6.9` over `0B-v1.6.18` (string compare), but the digest uses `_max_etl_version` (`orchestrator.py:1909`) which parses `\d+` runs into a tuple. Pick a bump that wins **numerically** (e.g. `0B-v1.6.19` > `0B-v1.6.18`), not lexically.

**E. The de-drift coupling is real but tiny.** A toggle name in an exercise's `equipment_required` (or a structured substitute's `equipment_required`) is the tier-1 gear gate. Renaming a toggle without de-drifting those references silently severs the gear→exercise linkage for the future enable path. Post-0021 only **EX170** (req) and **EX101** (structured) remained — both handled here. Re-run the reference sweep (§8) before any future toggle rename.

---

## 4. Revised build plan for the remaining slices

The design's 6-slice plan (§15) still holds; this re-scope moves a few items between slices:

- **Slice 2 — Equipment boundary de-drift** (unchanged): strip craft/gear items from `equipment_items` + exercises' `equipment_required` (extends `0008`).
- **Slice 3 — Athlete gear store** (unchanged): `athlete_gear` / `athlete_gear_locale` / `brought_gear` public tables + backfill + `athlete_gear_repo` + eviction.
- **Slice 4 — Cascade wiring + the deferred Layer 0 pieces** (now larger): the `gear_discipline_aliases` rename (+`fidelity_rank` + migrate craft rows + **add the gear alias rows**) sequenced with a `layer0-redump` and the `_LAYER0_TABLE_FAMILY` / `orchestrator.py` repoint; **wire the new `gated_discipline_ids`** (Classic/Skate→D-028, Mountaineering→D-018, Skimo→D-021/022); **drop `paired_equipment_categories`** with the coupled `layer2c/builder.py` edit; re-home `_collect_athlete_crafts` to read `athlete_gear`; feed gear into both 2C sites; fidelity-rank walk + skill composition (§6); the Elliptical proxy-map edit. This is bigger than 5 files — **split it** (e.g. 4a = rename+redump+repoint; 4b = gated-wiring + paired-drop + 2C edit; 4c = cascade/fidelity/skill).
- **Slices 5–6** (unchanged): away overlay; capture UX.

---

## 5. Verification (local, against the genesis baseline)

Reproduced the CI `layer0-gate` with a throwaway Postgres (`pg_virtualenv`): baseline + full migration chain (0006–0022) applies, `0022` verify block passes, **`validate_layer0` → PASS** (all checks clean; `sum_to_100` waivers pre-existing). Targeted suites pass (**119**): `TestLayer0TableFamilyMap`, `test_layer2c`, `test_layer2c_prep`, `test_validate_layer0`, `test_vocabulary_transforms`. Repeated applies of `0022` are a clean no-op (idempotent). Post-state confirmed: 6 active toggles (Climbing gear → D-012/013/014, Snowshoeing → D-017); EX170 → `{Skimo / AT setup}`; EX101 structured → `Climbing gear`.

**CI on PR #914:** Layer 0 integrity gate ✓, Python unit suite (stubbed) ✓, JS harness (jsdom) ✓, Vercel ✓; Real-LLM smoke skipped (nightly only).

---

## 6. Owed / next

### 6.1 OWED (Andy-action)
- **Apply to prod:** trigger `layer0-apply` (one-tap approve the `production` env) to run `0022` against Neon, then `layer0-redump` (input `version` = next, e.g. `1.9.0`) to refresh the baseline snapshot. The app picks up the active set live (serving reads `WHERE superseded_at IS NULL`); the `0C`/`0B` digest bumps re-key affected plan-gen caches. **No code deploy is coupled to this migration** (no app change shipped).
- Comment #884 / #298 with the PR ref (done this session where possible).

### 6.2 Follow-up (non-blocking)
- Stale comment in `layer2c/builder.py` ("Single query against the 11-row table") — the table is now 6 rows (was already wrong at 12). Left untouched per the migration-only scope; fix opportunistically in slice 4 when that file is edited anyway.

### 6.3 Operating notes (Rule #13 read order)
1. `CLAUDE.md` — stable rules. 2. `CURRENT_STATE.md` — top entry = this session. 3. `CARRY_FORWARD.md`. 4. This handoff. 5. `./scripts/verify-handoff.sh`. Then the **design doc** (`designs/Unified_GearCraft_Model_And_Feasibility_884_Design_v2.md`, §6 cascade / §11 migration / §15 slices) and **§3 findings above** before touching slice 3/4.

---

## 8. Session-end verification (Rule #10)

| Area | Path | Anchor / check |
|---|---|---|
| The migration (deliverable) | `etl/migrations/layer0/0022_unify_gear_toggle_catalog.sql` | header "#884 ... slice 1, 'catalog shape only'"; verify DO-block RAISEs on shape/gate/dangling-reference violations; `RAISE NOTICE '0022: OK — gear toggle catalog reshaped to 6 ...'` |
| Catalog post-state | (apply + `neon-query` or local gate) | 6 active `sport_specific_gear_toggles`; `Climbing gear` gates `{D-012,D-013,D-014}`; `Skimo / AT setup` active; no active row named `Touring/AT ski setup` / `Climbing — roped` / `Bouldering` / `Whitewater paddling setup` / `Fencing setup` / `Shooting setup` / `Rappelling / abseiling` / `Via ferrata` |
| De-drift | same | EX170 `equipment_required` has `Skimo / AT setup`; EX101 `equipment_substitutes_structured` names `Climbing gear`; no active exercise references a renamed toggle name |
| Cache families | `layer4/orchestrator.py` | `_LAYER0_TABLE_FAMILY` unchanged; `sport_specific_gear_toggles`+`exercises` mapped; `_max_etl_version` (line ~1909) is integer-tuple |
| Reference-sweep recipe | (for future renames) | active exercises where `equipment_required && ARRAY[<name>]` OR `equipment_substitutes_structured::text LIKE '%<name>%'` (jsonb columns: cast `::text`) |
| Deferred (NOT in this PR) | design §4 / §3-finding-B,C | `gear_discipline_aliases` rename, `fidelity_rank`, gear alias rows, new `gated_discipline_ids`, `paired_equipment_categories` drop → slice 4 |
| CI | PR #914 | Layer 0 integrity gate / Python unit suite / JS harness all green |

---

*End of handoff.*
