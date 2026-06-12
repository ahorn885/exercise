# V5 Implementation — Track 2 slice 2c.2c: the craft-feasibility axis (shipped)

**Date:** 2026-06-12
**Branch:** `claude/inspiring-galileo-nvnqys`
**PR:** [#562](https://github.com/ahorn885/exercise/pull/562) — squash-merged to `main`
**Issue:** [#540](https://github.com/ahorn885/exercise/issues/540) (go-live blocker — create-path feasibility now COMPLETE: terrain #553/#556 + craft #562)

> **Continuing #540?** The **create-path** feasibility cascade is now complete on both axes — terrain (where can you do it) + craft (do you own the vehicle). What remains under #540 is the gated tail: **#557** refresh-path wiring (behind #208) + the **layer0 column lift** (Track-3-gated). Neither is a live surface. The next *live* move is the other go-live blocker, **#539** (tab-closed plan-gen crawl). Do **not** re-open the craft vocabulary (settled — see the 2c.2b handoff §3).

---

## 1. What this session was

Started from a question — explain what the MTB→road scenario does today and whether the craft axis is worth building. Walking it through surfaced that the gap is real but narrow: terrain alone already handles "no off-road terrain → road ride," but an athlete who **has** trail terrain yet owns **no MTB** was still prescribed an un-equippable trail ride (only an advisory X1b.3b flag caught it). Andy chose the **full ladder** (own the wrong bike → train as the bike you own; own no bike → strength), reconciling it as a *feasibility-substitute* axis distinct from group_id pooling. Designed, got the render copy approved (Trigger #1), built, shipped.

## 2. What shipped (PR #562)

The terrain axis answers "is there a surface for discipline D?"; the craft axis answers "does the athlete own the vehicle?". The craft ladder runs **first** per discipline, then terrain runs on the (possibly swapped) effective discipline.

- **`layer4/session_feasibility.py`** — NEW pure `resolve_craft_feasibility` + `CraftResolution` (owned → swap → strength; only the craft-bearing `group_kind`s `bike`/`paddle`; returns `None` for non-craft disciplines → terrain owns them). `TerrainResolution` gained a craft overlay (`craft_tier`/`owned_craft`/`craft_swap_to_name`/`craft_kind`). `feasibility_line` prepends the swap reason / supplies the no-craft STRENGTH reason; `grid_annotation` emits `[CRAFT-SWAP]` / `[NO CRAFT]` inline tags.
- **`layer4/orchestrator.py`** — two readers (`_q_modality_group_kind` group→kind, `_q_craft_group_kind` craft→kind); craft+terrain composition in `_build_terrain_feasibility`. **owned/non-craft** → terrain as-is; **swap** → `_terrain(effective_discipline)` + craft overlay (e.g. MTB allocation resolved on the road surface); **strength** → the discipline's own ranked pool at the equipment-bearing locale (`craft_kind` set). Folds into the existing render + cache hash with **no new plumbing** (the resolution is already `asdict`-hashed).
- **`aidstation-sources/designs/Modality_Group_Spec_v2.md`** (NEW; v1 archived) — §3.3 records `group_kind`'s **second** use (Layer-4 feasibility substitute) as distinct from group_id WEIGHT pooling; §12 forward-ref. Additive only — the pooling algorithm and the §2 "does NOT do" boundary are unchanged.
- **Tests:** `tests/test_layer4_craft_feasibility.py` (NEW — pure ladder across bike+paddle, owned/swap/strength, determinism); craft-axis wiring + render coverage added to `tests/test_layer4_terrain_feasibility_wiring.py` (road-bike-for-MTB swap re-runs terrain on the road discipline; no-bike → strength **even when MTB terrain exists**; the rendered swap / no-craft lines + grid tags).

**The key behavior:** craft runs ahead of terrain, so owning the wrong bike (or none) is resolved deterministically **before** terrain — closing the "has the trail, lacks the bike" hole that was previously advisory-only.

## 3. Design reconciliation (read before touching either axis)

`group_id` and `group_kind` now have **two non-conflicting jobs**, documented in `Modality_Group_Spec_v2` §3.3:
- **Pooling (`group_id`, Layer 2A):** redistributes a race's discipline **WEIGHT** within a modality group. Unchanged by this slice.
- **Feasibility substitute (`group_kind`, Layer 4):** chooses which **SESSION** to actually do once weights are fixed. Same-`group_id` ownership (a gravel bike for MTB — both `bike_offroad`) is "owned"; only a same-`group_kind`-but-other-`group_id` craft (a road bike for MTB — `bike_pavement` vs `bike_offroad`) triggers a swap.

Coaching rationale for road-for-MTB over strength: a road ride trains most of the MTB aerobic/pedaling demand (only the technical handling is lost, which no home substitute recovers). Strength is the terminal only when no craft of the kind is owned at all.

## 4. Verification

- Full suite **2327 passed / 30 skipped**. CI green (Python unit suite, Layer 0 integrity gate, JS harness, Vercel preview; Real-LLM smoke skipped). **No DDL, no vocab adds** — reads genesis-resident `layer0.modality_groups` / `craft_discipline_aliases` + the 2c.2b craft columns (already existed). **Nothing owed Andy's-hands for this slice** — live the moment the deploy lands.

## 5. Owed / next move

1. **#539** (tab-closed plan-gen crawl) — go-live blocker, now the top live move (the #540 create-path is done). **← NEXT (recommended).**
2. **#540 tail (gated, not urgent):** **#557** refresh-path wiring (mirror the create wiring at `orchestrate_plan_refresh`; sequenced behind #208 — refresh route not a live surface) + the **layer0 column lift** of the discipline→terrain / indoor-machine maps (Track-3-gated). Consider whether #540 should be **closed** with #557 + the column-lift carrying the residual — flagged to Andy.
3. **Quality batch:** #541 (shallow strength — prompt change, Trigger #1), #542 (low-protein macros), #543 (structured health conditions — vocab add).
4. **Pre-existing owed deploys (NOT from this slice):** confirm `layer0.skill_capability_toggles` applied on Neon (#336 gate is data-driven off it); `plan_versions.archived_at` (#531); the sleep columns (#283/#504). See CARRY_FORWARD's consolidated list.

### 6.3 Operating notes for next session (Rule #13 read order)
1. `CLAUDE.md` · 2. `CURRENT_STATE.md` · 3. `CARRY_FORWARD.md` (the #540 section) · 4. **this handoff** · 5. `./scripts/verify-handoff.sh`. **2c.2c is shipped — the create-path feasibility cascade is complete (terrain + craft).** Next live move is **#539** (§5.1). The #540 refresh tail (#557) + column lift are gated; the craft vocabulary + the two-axis design are settled (§3) — don't re-open them.

## 6. Stop-and-asks this session
- **Trigger #1 (prompt render):** the synthesis-prompt copy — the swap line (`"you own a road bike, not the gear for it — train this allocation as Road Cycling"`), the no-craft STRENGTH reason, and the `[CRAFT-SWAP]` / `[NO CRAFT]` inline tags — was drafted and **approved by Andy before wiring**.
- **Trigger #5 (architecture):** the full-ladder vs tight-strength-gate choice, and the feasibility-axis-vs-pooling reconciliation, were put to Andy; he chose the full ladder. No Trigger #2 (no vocab adds); no Trigger #3 DDL (reads existing columns).

## 7. §8 anchor table (Rule #10)

| Claim | File | Anchor / check |
|---|---|---|
| Pure craft ladder | `layer4/session_feasibility.py` | `def resolve_craft_feasibility`, `class CraftResolution`, `_CRAFT_GROUP_KINDS = frozenset({"bike", "paddle"})` |
| Craft overlay on resolution | `layer4/session_feasibility.py` | `TerrainResolution` fields `craft_tier` / `owned_craft` / `craft_swap_to_name` / `craft_kind`; `grid_annotation` `"[CRAFT-SWAP:"` / `"[NO CRAFT:"` |
| Readers | `layer4/orchestrator.py` | `def _q_modality_group_kind`, `def _q_craft_group_kind` |
| Composition | `layer4/orchestrator.py` | in `_build_terrain_feasibility`: `resolve_craft_feasibility(`, `craft.tier == "swap"`, `craft.tier == "strength"`, `_craft_kind_of` |
| Spec note | `aidstation-sources/designs/Modality_Group_Spec_v2.md` | §3.3 "Second use — Layer 4 craft-feasibility axis"; v1 in `archive/superseded-specs/` |
| Tests | `tests/test_layer4_craft_feasibility.py`, `tests/test_layer4_terrain_feasibility_wiring.py` | `test_road_bike_for_mtb_swaps_to_road`; `test_build_craft_swap_road_bike_for_mtb`; `test_build_craft_strength_when_no_bike_owned` |
| Merged | PR [#562](https://github.com/ahorn885/exercise/pull/562) | squash-merged; full suite 2327 |
