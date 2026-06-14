# V5 Implementation — WS-I Slice B: unified craft/terrain feasibility cascade (Closing Handoff)

**Session:** Shipped the cascade half of WS-I — the rewrite where the live **craft-STRENGTH-preempts-INDOOR** bug actually gets fixed. Replaced the two non-composing feasibility axes (a craft ladder that short-circuited ahead of terrain) with a single nested craft/terrain cascade reading the explicit `craft_terrain_compatibility` map Slice A seeded. WS-I is now complete.
**Date:** 2026-06-14
**Predecessor handoff:** `V5_Implementation_WSI_SliceA_CraftEquipmentTaxonomy_2026_06_14_Closing_Handoff_v1.md`
**Branch / PR:** [#588](https://github.com/ahorn885/exercise/pull/588) (`claude/zealous-gauss-bl22ek` — scope is WS-I Slice B). **Squash-merged to `main`, CI-green.** Closes WS-I (#586).
**North-star plan:** `plans/Feasibility_Saturation_And_Locale_Retirement_Plan_v1.md` (WS-I).
**Design:** `designs/CraftEquipment_Taxonomy_And_FeasibilityCascade_Design_v1.md` (§3 cascade, §4 craft↔terrain data).
**Status:** 6 files (2 code + 4 tests). One over the 5-substantive ceiling; the four test edits were all pre-scoped by the Slice A handoff §6.1 (family-map guard, new tier matrix, §4 stale-fixture cleanup) and are mechanical — flagged here per the ceiling rule.

---

## 1. Session-start verification (Rule #9)

Anchor-checked the Slice A handoff §8 table against on-disk state on this branch (which is based on the #587 merge commit) — **all clean, no drift**:

| Claim | Anchor | Result |
|---|---|---|
| Craft enum drop landed | `athlete.py:324` `BIKE_TYPES = ('road_bike', 'mountain_bike', 'gravel_bike')` | ✅ grep |
| New L0 table + seed | `etl/migrations/layer0/0004_*.sql` — `CREATE TABLE IF NOT EXISTS layer0.craft_terrain_compatibility`, 21 grid rows, `cycling_trainer` alias supersede | ✅ read |
| Slice B start state | `orchestrator.py` — `_LAYER0_TABLE_FAMILY` did NOT yet contain `craft_terrain_compatibility`; the `:437` craft-STRENGTH `continue` was still present | ✅ grep (pre-edit) |
| `0004` on Neon | Slice A handoff §10 item 1 | ✅ DONE (Andy, 2026-06-14) — deploy-ordering precondition for this slice satisfied |

`scripts/verify-handoff.sh` ran clean (it lives at `aidstation-sources/scripts/`, run from `aidstation-sources/`). **Reconciliation note:** clean — no gap.

---

## 2. Session narrative

- **Scope.** Andy: "lets go with the next slice." Slice A handoff §6.1 names Slice B precisely; the design is BUILD-READY + fully Andy-ratified (cascade ordering, tier 3 > tier 4, the seed grid). Executed.
- **Kept non-craft disciplines on the existing cascade.** Design §3 is explicit: only craft (bike/paddle) disciplines walk the new unified cascade; foot/swim/climb keep `resolve_terrain_feasibility` untouched. So this slice **adds** `resolve_craft_terrain_feasibility` and **routes** craft disciplines to it — it does not rewrite the terrain-only cascade (surgical; the large existing terrain test surface stays green unchanged).
- **The result type stayed `TerrainResolution`.** It's woven into caching/hashing (`hashing.compute_terrain_feasibility_hash` via `asdict`, `cached_wrappers`, `plan_create`) + the render (`feasibility_line`/`grid_annotation`). The new cascade returns a `TerrainResolution`; the 7 tiers map onto `tier` + the `craft_tier` overlay (one new overlay value `"proxy"` for tier 3). `asdict` folds the new field values into the cache hash automatically — no hashing change.
- **Tier 1 now gates on craft↔terrain compat** (the whole point of §4's explicit data). The old EXACT matched any required terrain in-cluster regardless of which craft you own; now tier 1 = `required ∩ craft_compat ∩ cluster`, so a gravel bike can't "ride" technical singletrack just because it aliases the XC discipline. This is a deliberate behavior change, not a regression.
- **The bug fix falls out of the nesting.** "Craftless" is no longer a branch: tiers 1–4 (owned/proxy craft × terrain) all miss and the walk lands on INDOOR (tier 5) — so a craftless athlete with a Cycling trainer gets the trainer, not strength. Verified by `test_craftless_with_trainer_is_indoor_not_strength`.
- **Validated with the full pytest suite** (2379 passed, 30 skipped) — no throwaway-Postgres run needed this slice (no new SQL; reads the already-applied `0004`).

---

## 3. File-by-file edits

### 3.1 `layer4/session_feasibility.py` (modified — core)
- **Removed** `CraftResolution` + `resolve_craft_feasibility` (the old craft axis that short-circuited ahead of terrain).
- **Added** `resolve_craft_terrain_feasibility(...)` — the unified 7-tier nested cascade (design §3). Returns `None` for non-craft disciplines (caller falls back to `resolve_terrain_feasibility`). Reads `craft_terrain` (`{craft: {TRN-id}}`) at tiers 1–4. Tier ordering: `1 own-craft/required → 2 own-craft/alt-terrain → 3 proxy/desired-terrain → 4 proxy/own-terrain (swap) → 5 indoor → 6 strength → 7 reallocate`. Tier 6 flags `craft_tier="strength"` (+`craft_kind`) only when **craftless**; an owned-craft-but-no-terrain strength keeps `craft_tier=""` (the reason line stays accurate).
- **`TerrainResolution.craft_tier`** Literal extended `+ "proxy"` (tier 3: real terrain on a proxy craft you own; sport unchanged).
- **`feasibility_line`** — added the `craft_tier=="proxy"` prefix; guarded the `tier=="proxy"` branch for `proxy_fidelity is None` (the craft-alt tier-2 case has no gap-rule fidelity number). `grid_annotation` needed no change (tier-3 proxy returns `""` — the sport doesn't change).

### 3.2 `layer4/orchestrator.py` (modified)
- **`_q_craft_terrain_compatibility(db)`** — new reader: `{craft_name: {terrain_id}}` from `layer0.craft_terrain_compatibility` (active rows). Empty dict degrades (tiers 1–4 miss), doesn't crash.
- **`_LAYER0_TABLE_FAMILY`** — added `"craft_terrain_compatibility": "0A"` (sibling of `craft_discipline_aliases`), so grid edits perturb the 0A digest and invalidate plan-gen caches. Deploy-safe: `0004` is on Neon, so `_q_current_etl_version_set`'s `SELECT … FROM layer0.craft_terrain_compatibility` won't hit a missing table.
- **`_build_terrain_feasibility`** — replaced the craft-axis-then-terrain block (incl. the `:437` craft-STRENGTH `continue` and the swap `replace(...)`) with a single call to `resolve_craft_terrain_feasibility`, falling back to `_terrain(...)` on `None`. Removed the now-dead `strength_locale` var + `_craft_kind_of` helper (folded into the cascade) and the unused `replace` import.
- **Rule #15 logging** — per-discipline detail rewritten: for craft disciplines, log `craft_kind`, `owned_same_kind`, and `craft_rideable_in_cluster` (per craft, the compatible terrains present); for non-craft, the gap-rule proxies as before. The header line now also logs `craft_terrain`.

### 3.3 `tests/test_layer4_craft_feasibility.py` (rewritten)
Now exercises `resolve_craft_terrain_feasibility` across all 7 tiers, incl. the two motivating cases: **craftless-with-trainer → INDOOR** (the bug) and **proxy-craft-on-desired-terrain (tier 3)**, plus the tier-3 > tier-4 ordering. Fixtures mirror live data + the 0004 grid.

### 3.4 `tests/test_layer4_terrain_feasibility_wiring.py` (modified)
`_patch_craft` now also stubs `_q_craft_terrain_compatibility`. The two craft wiring tests updated to the new semantics (road-bike-for-MTB is now a tier-4 swap because road can't ride MTB terrain; craftless-no-machine is tier-6 strength).

### 3.5 `tests/test_layer4_orchestrator.py` (modified)
`TestLayer0TableFamilyMap::test_includes_out_of_schema_serving_tables` — added the `craft_terrain_compatibility → "0A"` assertion (the Slice A handoff's "`test_includes_out_of_schema_serving_tables`-style assertion").

### 3.6 `tests/test_layer2_substitution.py` (modified — §4 cleanup)
Removed the stale `cycling_trainer` craft-alias fixture row + the now-impossible `test_trainer_matches_every_bike_discipline` (the narrowing mechanism it tested is already covered by `test_gravel_bike_qualifies_for_both`).

---

## 4. Code / tests

New tests: the full 7-tier matrix in `test_layer4_craft_feasibility.py` (13 cases). Updated: 2 craft wiring tests, 1 family-map assertion, the §4 fixture cleanup. **Full suite green: 2379 passed, 30 skipped, 2 pre-existing unrelated warnings** (`test_layer3b_builder` evidence-basis). Affected suites all green: `test_layer4_craft_feasibility`, `test_layer4_terrain_feasibility_wiring`, `test_layer4_session_feasibility`, `test_layer4_orchestrator`, `test_layer2_substitution`, `test_layer4_plan_create`, `test_layer4_plan_refresh`.

---

## 5. Manual verification

No SQL this slice — reads the already-applied `0004`. Behavioral correctness pinned by tests rather than a live plan-create (the live re-verify is the carried T3-refresh item, §6.2). Key assertions: the bug case (`craftless + trainer → indoor`), tier 1 craft-compat gating (gravel can't "ride" technical it doesn't list), tier 3 beating tier 4, the family-map digest now covering the new table.

---

## 6. Next session pointers

### 6.1 WS-I is complete
Taxonomy (Slice A, #587) + cascade (Slice B, #588) both shipped + squash-merged to `main`. WS-I (#586) closed. **No owed-hands deploy remains** for WS-I (this slice added no DDL).

### 6.2 Architect-recommended next forward move
Down the plan's lower-priority arc (pick per the 4-tier next-step order in `CLAUDE.md`):
- **STILL OWED (carried):** the post-#572 live **T3 *refresh*** re-verify (paired: needs the diag token + Andy pasting logs, Rule #14). pv=71 was a *create*; a *refresh* has never been live-verified post-#572.
- [#582] retire `LOCALES` (WS-B); [#583] onboarding forced-home + craft capture (WS-C); [#584] saturation policy (WS-E2); WS-H away-craft (needs DDL — design first).

### 6.3 Operating notes for next session (Rule #13 read order)
1. `CLAUDE.md` — stable rules (incl. Rules #14/#15).
2. `CURRENT_STATE.md` — top entry = this session; WS-I complete.
3. `CARRY_FORWARD.md` — top entry = this session (Slice B shipped, no owed deploy).
4. This handoff.
5. The plan doc `Feasibility_Saturation_And_Locale_Retirement_Plan_v1.md`.
6. `aidstation-sources/scripts/verify-handoff.sh` (run from `aidstation-sources/`).

**Test env:** `pytest` isn't in `requirements.txt` — `python -m venv /tmp/venv && /tmp/venv/bin/pip install -r requirements.txt pytest`, then run the full `tests/` (isolated single-file collection hits a circular-import quirk; front-load a `tests/test_layer4_*.py` or run the whole dir).

---

## 7. Decisions pinned

| # | Decision | Picked by | Rationale |
|---|---|---|---|
| 1 | Non-craft disciplines keep `resolve_terrain_feasibility`; only craft disciplines walk the new cascade | Design §3 (Andy-ratified) | Surgical — foot/swim/climb behavior + tests unchanged; the rewrite is scoped to the broken axis. |
| 2 | Result type stays `TerrainResolution`; one new `craft_tier="proxy"` overlay value | Claude | Avoids churning caching/hashing/render; `asdict` folds new field values into the cache hash for free. |
| 3 | Tier 1 gates on `required ∩ craft_compat ∩ cluster` (not bare required terrain) | Design §4 | The point of explicit craft↔terrain: a road bike ≠ a gravel bike on singletrack even though both alias road/XC. |
| 4 | `craft_terrain_compatibility` registered in `_LAYER0_TABLE_FAMILY` this slice | Slice A handoff Decision #4 | Lands with the code that reads it; `0004` already on Neon → deploy-safe. |
| 5 | Removed `CraftResolution`/`resolve_craft_feasibility` outright (not deprecated) | Claude | No callers outside the orchestrator + its tests; the two-axis model is the bug. |
| 6 | Shipped at 6 files (1 over the ceiling) | Claude (flagged) | The 4 test edits were all pre-scoped by Slice A §6.1 and are mechanical; splitting would fragment one cohesive rewrite. |

---

## 8. Session-end verification (Rule #10)

| Area | Path | Anchor / check |
|---|---|---|
| Unified cascade added | `layer4/session_feasibility.py` | `def resolve_craft_terrain_feasibility(`; no `resolve_craft_feasibility`/`class CraftResolution`; `craft_tier: Literal["", "swap", "strength", "proxy"]` |
| Short-circuit removed | `layer4/orchestrator.py` | no `craft.tier == "strength"` / `craft.tier == "swap"` block; `_build_terrain_feasibility` calls `resolve_craft_terrain_feasibility` then falls back to `_terrain`; no `from dataclasses import … replace` |
| New reader + family entry | `layer4/orchestrator.py` | `def _q_craft_terrain_compatibility`; `"craft_terrain_compatibility": "0A"` in `_LAYER0_TABLE_FAMILY` |
| Family-map guard | `tests/test_layer4_orchestrator.py` | `_LAYER0_TABLE_FAMILY.get("craft_terrain_compatibility") == "0A"` |
| Bug-fix test | `tests/test_layer4_craft_feasibility.py` | `test_craftless_with_trainer_is_indoor_not_strength` asserts `tier == "indoor"` |
| Stale fixtures cleaned | `tests/test_layer2_substitution.py` | no `cycling_trainer` in `_CRAFT_ALIASES`; `test_trainer_matches_every_bike_discipline` gone |
| Suite | — | `pytest tests/` → 2379 passed, 30 skipped |
| Working tree | — | clean after the bookkeeping commit |

---

## 9. Files shipped this session

**Substantive (6 files):**
1. `layer4/session_feasibility.py`
2. `layer4/orchestrator.py`
3. `tests/test_layer4_craft_feasibility.py`
4. `tests/test_layer4_terrain_feasibility_wiring.py`
5. `tests/test_layer4_orchestrator.py`
6. `tests/test_layer2_substitution.py`

**Bookkeeping (this commit):** `CURRENT_STATE.md`, `CARRY_FORWARD.md`, this handoff.

---

## 10. Owed Andy's hands (Neon — container has no egress)

**None for WS-I.** This slice added no DDL and reads the already-applied `0004`. PR #588 squash-merged → WS-I (#586) closed. Nothing owed.
