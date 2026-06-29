# V5 Implementation — #884 Unified Gear/Craft Model — Slice 4b PR-2 (gear/terrain cascade extension) — Closing Handoff

**Session:** Slice 4b PR-2 of #884 — the **consumer** half. Generalized the feasibility/substitution gear cascade from `{bike, paddle}` to **all** discipline-unlocking gear kinds (ski/snow/climbing/alpine) with an ascending-`fidelity_rank` walk, and seeded the gear-toggle terrain rows (migration `0026`). The captured gear toggles (PR-1) now gate discipline feasibility.
**Date:** 2026-06-29
**Predecessor handoff:** `V5_Implementation_UnifiedGearCraftModel_884_DesignV3_Slice4b_GearToggleCapture_2026_06_28_Closing_Handoff_v1.md` (PR-1, merged as `d2dc258` / PR #976)
**Branch:** `claude/884-gear-toggle-capture-w4nug5`
**Status:** 2 code + 1 migration + 3 test files. Suite green **3709/30**. Migration `0026` validated on PG16 (apply + idempotent + `validate_layer0` PASS). **Neon apply OWED** (`layer0-apply`, `0026`). **PR not yet opened — awaiting Andy's go.**

---

## 0. Thread continuity — STAY ON THIS THREAD

Continuous build of #884. Slice 4b split (Andy 2026-06-28): **PR-1 = capture (merged)**, **PR-2 = cascade extension (this)**. Next: **slice 4.3** (redump retiring `craft_discipline_aliases` + equipment strip) and the **PR-3 2C feed un-starve** (split out this session — see §6). Design: `designs/Unified_GearCraft_Model_And_Feasibility_884_Design_v3.md` §6/§15.4. Plan: `plans/UnifiedGearCraft_884_Slice4_CascadeCutover_Plan_v1.md`.

---

## 1. Session-start verification (Rule #9)

Anchor-checked PR-1's §8 claims against on-disk + merged state — all ✅ (PR-1 is the branch HEAD `d2dc258`; `_GEAR_TOGGLE_KINDS`, `GEAR_TOGGLE_LABELS`, the 3 helpers, `save_gear_toggles` + `[gear-toggle-capture]` log, the gear-toggle form all present). `verify-handoff.sh` all ✅, tree clean. **One cosmetic drift:** PR-1's handoff header names branch `claude/unified-gear-craft-model-veo6he`, but it actually landed via PR #976 on `claude/884-gear-toggle-capture-w4nug5`. Code merged correctly — stale label only.

---

## 2. Two decisions ratified this session (Andy 2026-06-29, AskUserQuestion)

Grounding the cascade surfaced two load-bearing findings; both went to Andy before coding:

1. **Cascade scope = ALL gear kinds now** (not ski-only). The risk: the gear taxonomy (`ski/snow/climbing/alpine`) and the discipline modality taxonomy (`snow/climb/foot`) **diverge**, and `craft_terrain_compatibility` had **zero** rows for snow/climbing/alpine — so naively pulling those disciplines into the cascade without their terrain rows would drop snowshoers / skilled climbers to INDOOR/STRENGTH even with the real surface in-cluster (a regression). Andy chose to pull **all** kinds in **and** seed their terrain rows in `0026` (regression-safe).
2. **2C feed (`cluster_gear_toggle_states` un-starve) SPLIT to PR-3.** It needs a new `gear_id → sport_specific_gear_toggles.toggle_name` bridge (different keyspace) and would blow the file ceiling. PR-2 stays the cascade + `0026`; PR-3 does the bridge + the 2C feed.

---

## 3. File-by-file edits

### 3.1 `layer4/session_feasibility.py` (modified)
- `_CRAFT_GROUP_KINDS` widened `{bike,paddle}` → `{bike,paddle,ski,snow,climbing,alpine}` (swim excluded — drill-gating, slice 3b; it carries no `gear_discipline_aliases` row so never enters).
- `resolve_craft_terrain_feasibility`: **signature** — dropped the now-unused `group_kind` (modality group→kind) param; added `discipline_gear_kind: dict[str,str]` (discipline → **gear-side** kind) + `craft_fidelity_rank: dict[str,int] | None = None`. **Body** — `target_kind = discipline_gear_kind.get(discipline_id)` gated on `_CRAFT_GROUP_KINDS` (the gear-side kind, NOT the modality kind — the two diverge for ski/snow/climbing/alpine; for bike/paddle they coincide → byte-identical). `same_kind` now `sorted(..., key=lambda c: (rank.get(c,0), c))` — ascending fidelity_rank, slug-tie-break. Bike/paddle all rank 0 → identical to the prior slug sort; the D-028 ladder walks classic(0)→skate(1)→rollerskis(2). The 7 tiers are otherwise unchanged.

### 3.2 `layer4/orchestrator.py` (modified)
- `_CRAFT_ALIAS_GROUP_KINDS` widened to match (`_collect_athlete_crafts` now feeds ski/snow/climbing/alpine gear into the cascade + the training-substitution resolver).
- **NEW `_q_gear_fidelity_rank(db)`** → `{gear_id: MIN(fidelity_rank)}` from `gear_discipline_aliases`.
- `_gather_feasibility_inputs`: derives `discipline_gear_kind` **without a new query** (`{d: craft_kind[g] for g,discs in craft_disciplines for d in discs}`) + calls `_q_gear_fidelity_rank`; both added to `_FeasibilityInputs` (new fields) and threaded into the cascade call.
- `_build_terrain_feasibility`: the Rule #15 `_craft_kind_of` log helper repointed to `discipline_gear_kind` (reports ski/snow/climbing/alpine, not just bike/paddle); removed the two now-orphaned local bindings (`discipline_groups`, `group_kind_by_group`) my edit left.

### 3.3 `etl/migrations/layer0/0026_gear_toggle_terrain_compatibility.sql` (new)
Seeds 10 `craft_terrain_compatibility` rows (ids 29–38, `etl_version='0A-v1.9.2'`) for the gear toggles — reuse existing terrain vocab, NO new terrain entries (design Decision 3). Each gear → the required terrains of the disciplines it unlocks, except the rollerski carve-out:
`classic_xc_ski/skate_xc_ski→TRN-012` (snow); **`rollerskis→TRN-001`** (dryland/paved, the carve-out → resolves via the own-gear-alternate-terrain PROXY tier); `snowshoes→TRN-012`; `climbing_gear→TRN-013,TRN-014`; `mountaineering→TRN-005,TRN-007,TRN-012`; `skimo_at→TRN-012`. Atomic verify DO-block: 10 rows + rollerski-carve-out invariant + no dangling terrain_id/gear_id refs. Idempotent (delete-by-version + re-insert).

### 3.4 Tests
- `tests/test_layer4_craft_feasibility.py` (+~17): updated `_resolve` helper to the new signature (added the gear-toggle fixtures: aliases, kinds, ranks, terrain grid; `_DISC_GEAR_KIND` derived as the orchestrator does). New classes: `TestGearToggleSkiLadder` (rank walk classic>skate>rollerskis; rollerski-dryland PROXY incl. with snow present; ski-erg INDOOR below owned gear), `TestGearToggleGatesDiscipline` (no ski gear → not EXACT on snow; snowshoes EXACT / no-snowshoes gated to treadmill), `TestGearToggleClimbAlpine` (climbing gear EXACT on rock wall / indoor wall; mountaineering EXACT on alpine; skimo proxy tier-3; gearless-climber strength flags gear kind). The existing tier-1–7 bike/paddle classes are the **regression pin** (byte-identical).
- `tests/test_layer4_terrain_feasibility_wiring.py`: the two D-008 fixtures gained the proxy discipline's alias row (`mountain_bike→D-008`) — the live `_q_craft_discipline_aliases` always returns the full table, so `discipline_gear_kind` covers proxy targets; the fixtures previously leaned on the modality-derived kind.
- `tests/test_layer4_event_windows.py`: `_FeasibilityInputs(...)` builder gained the two new fields (`={}`).

---

## 4. Behavior change (intended) + a noted side-effect

**Intended served-output change — gear now gates discipline feasibility.** Pre-4b, a discipline like D-028 (skiing) or D-017 (snowshoeing) resolved EXACT on real snow regardless of owned gear. Post-4b it needs the gear: own classic XC skis + snow → EXACT; own no ski gear → INDOOR(ski-erg)/STRENGTH even with snow present (you can't ski without skis). This is the whole point of the slice and is why PR-1 (capture) shipped first. Bike/paddle is **unchanged** (regression-pinned).

**Noted side-effect — `resolve_training_substitution`.** `_collect_athlete_crafts` is shared with the substitution resolver, so for ski/snow/climbing/alpine discipline blocks it now surfaces owned specialized gear as candidate training crafts (where it previously flagged `craft_unavailable`). Benign/consistent with the unified model; bike/paddle blocks unchanged (the per-discipline modality narrowing filters the new gear out). Rides `layer1_hash` for caching. Existing substitution tests stay green.

**Cache:** `craft_terrain_compatibility` is family `0A` and **live-read** (unlike 0024/0025), so the new `0A-v1.9.2` rows raise its per-table digest in `etl_version_set` → plans re-run picking up the ski-gear feasibility. Correct, intended invalidation.

---

## 5. Code / tests / migration validation

- Suite: `tests/ etl/tests/` **3709 passed / 30 skipped** (only the 3 pre-existing #217 Layer3B `evidence_basis` warnings). Ruff clean on all changed files.
- Migration `0026` validated on **PG16** (pg_virtualenv): baseline v1.9.0 + 0023/0024/0025/0026 apply; DO-block NOTICE OK (10 rows, rollerski carve-out, no dangling refs); idempotent re-apply (38 total active rows stable); **`validate_layer0` PASS** (all checks clean/waived).

---

## 6. Next session pointers

### 6.1 OWED this PR
- **Neon apply:** trigger `layer0-apply` for `0026` (Andy one-taps the `production` gate) at/after merge.

### 6.2 Architect-recommended next forward move
- **PR-3 — the 2C feed un-starve (#298 close-out).** Feed `cluster_gear_toggle_states` at `orchestrator.py:1119,1551` (currently `={}`) from `athlete_gear`. Needs a `gear_id → sport_specific_gear_toggles.toggle_name` bridge — the keyspaces differ (`classic_xc_ski` vs `'Classic XC ski setup'`; `mountaineering` vs `'Mountaineering'`). Define the bridge (design v3 §5.5 keyspace is the source), then map owned gear → toggle states. Self-contained, own PR.
- **Slice 4.3 — Layer-0 redump + equipment strip.** Retire `craft_discipline_aliases` (forced redump — **heed the redump-MUST-pair-with-fold rule**, `etl/migrations/layer0/README.md`); strip `pull_buoy`/`kickboard`/`Swim fins` from `equipment_items` + EX126/EX128 `equipment_required` (0B supersede+re-insert → global cache invalidation).

### 6.3 Open follow-on (not owed by this slice)
- **Onboarding parity for gear toggles** (carried from PR-1 §6.2): toggles are captured on the profile gear-tab only; if onboarding should surface them too, it's a small follow-on. Flag for Andy.

### 6.4 Operating notes for next session (Rule #13)
1. `CLAUDE.md` — stable rules.
2. `CURRENT_STATE.md` — last-shipped (this) + the #884 predecessors.
3. `CARRY_FORWARD.md` — the #884 rolling item.
4. This handoff + `plans/UnifiedGearCraft_884_Slice4_CascadeCutover_Plan_v1.md`.
5. `./scripts/verify-handoff.sh`.

---

## 7. Decisions pinned

| # | Decision | Picked by | Rationale |
|---|---|---|---|
| 1 | Cascade extends to ALL gear kinds (not ski-only) + `0026` seeds their terrain rows | Andy 2026-06-29 | "Ski-only" would leave snow/climbing/alpine half-in; seeding all terrain rows is regression-safe |
| 2 | 2C feed split to its own PR-3 | Andy 2026-06-29 | Needs a new gear→toggle_name bridge + would exceed the file ceiling |
| 3 | Discipline gear-kind read from `gear_discipline_aliases`, NOT `modality_groups` | Claude | The two taxonomies diverge for ski/snow/climbing/alpine; gear-side kind is the only one that matches owned gear (bike/paddle byte-identical) |
| 4 | gear-toggle craft_terrain = the disciplines' required terrains, reuse existing vocab | Claude (design Decision 3) | No new terrain entries (Trigger #2 N/A); rollerski→TRN-001 is the one deliberate carve-out |

---

## 8. Session-end verification (Rule #10)

| Claim | File | Check |
|---|---|---|
| Cascade kinds widened | `session_feasibility.py` | grep `_CRAFT_GROUP_KINDS` → ski/snow/climbing/alpine |
| Cascade gates on gear-side kind + rank walk | `session_feasibility.py` | grep `discipline_gear_kind.get(discipline_id)` + `craft_fidelity_rank` |
| Rank reader | `orchestrator.py` | grep `def _q_gear_fidelity_rank` |
| discipline_gear_kind derived | `orchestrator.py` | grep `discipline_gear_kind = {` |
| Alias kinds widened | `orchestrator.py` | grep `_CRAFT_ALIAS_GROUP_KINDS` → 6 kinds |
| Migration 0026 | `etl/migrations/layer0/0026_gear_toggle_terrain_compatibility.sql` | grep `rollerskis` `TRN-001` + DO verify |
| Suite green | (local) | `tests/ etl/tests/` 3709 passed / 30 skipped |
| Migration valid | (PG16) | baseline+0023–0026 apply; `validate_layer0` PASS |

---

## 9. Files shipped this session

**Substantive (2 code + 1 migration):**
1. `layer4/session_feasibility.py` — cascade generalized to all gear kinds + fidelity-rank walk
2. `layer4/orchestrator.py` — rank reader + discipline_gear_kind derivation + wiring + log fix
3. `etl/migrations/layer0/0026_gear_toggle_terrain_compatibility.sql` — gear-toggle terrain rows

**Tests (3):**
4. `tests/test_layer4_craft_feasibility.py` (+~17 — ski ladder / gating / climb-alpine; bike/paddle regression pin)
5. `tests/test_layer4_terrain_feasibility_wiring.py` (full-alias-table fixtures)
6. `tests/test_layer4_event_windows.py` (new `_FeasibilityInputs` fields)

**Bookkeeping (outside the ceiling):** `CURRENT_STATE.md`, `CARRY_FORWARD.md`, this handoff, GitHub issues.

*(6 substantive vs the 5-file soft ceiling — 2 of the 3 test files are mechanical signature/field follow-through forced by the dataclass + signature change, not new logic; cohesive single feature, flagged not split.)*

---

## 10. Carry-forward updates

`CARRY_FORWARD.md` #884: slice-4 PROGRESS — 4a/4.2 done; 4b-PR1 (capture) merged; **4b-PR2 (cascade extension + `0026`) done+pushed, Neon apply owed**; **PR-3 (2C feed un-starve) + 4.3 (redump + equipment strip) next.** #298 gear-toggle starvation: capture (PR-1) + the terrain-feasibility consumer (this) now closed; the 2C-feed consumer remains (PR-3).

---

**End of handoff.**
