# #694 cull + #691 Tier-2 substitution render — Closing Handoff

**Session:** Continued the 6/17 plan-71 batch. Shipped two items stacked on **one PR (#697)** because the harness pins a single dev branch: **#694** (cull 5 non-trainable v1 catalog entries) and **#691** (surface the Tier-2 strength substitution as the directive). Also filed **#698** (catalog-wiring audit) from a read-only sweep.
**Date:** 2026-06-17
**Predecessor handoff:** `V5_Implementation_ProviderTranslation_GarminStrength_679_2026_06_17_Closing_Handoff_v1.md` (#679 landed on `main` in parallel as #699)
**Branch:** `claude/intelligent-darwin-aegp1o` (harness-pinned; rebased clean onto `main` @ `6c97d91`)
**Status:** committed; **PR #697 — auto-merge OFF** (Andy ratifies the #694 cull by merging; #691 rides along).

---

## 1. Session-start verification (Rule #9)
PR #696 (#688/#693) merged earlier; #697 (#694) had gone `mergeable_state: dirty` because `main` advanced with #699 (#679 Garmin resolver), which edited `CURRENT_STATE.md`. Resolved by `reset --hard origin/main` + cherry-picking the two **code** commits (#694, #691) onto current main and **rewriting the bookkeeping fresh** (no CURRENT_STATE merge conflict). Branch diff vs main is the 5 substantive/test files only.

## 2. What shipped

### 2.1 #694 — cull 5 non-trainable v1 `exercise_inventory` entries (`init_db.py`)
Five `exercise_type='Novel'` rows on `/rx` are cardio sessions / coaching cues, not trackable strength exercises: **1,000 Step-Up Challenge · Hanging Leg Raise in Boots · Weighted Treadmill Incline Walk · High-Rep Strength Endurance Sets · Nasal-Breathing-Only Climbing.** Audit (vs `etl/output/layer0_etl_v1.8.0.sql`): none are active **layer0** 0B exercises; nothing in layer0 (progression/regression/proxy/`sport_exercise_map`) references them → **v1-catalog only, zero Layer-4 impact** (Layer 4 selects from the layer0 `feasible_pool_ids` enum). Removed from `EXERCISES` + `EXERCISE_EQUIPMENT` (both seeds run every deploy with `ON CONFLICT DO NOTHING`, so leaving them would re-seed/flip-flop) + a public `_PG_MIGRATIONS` cull (auto-applies on deploy) in **FK-safe order**: `exercise_equipment` (FK) → `injury_exercise_modifications` (FK) → name-keyed `current_rx` (the rows `/rx` shows; FK dropped in #430 Slice C) → `exercise_inventory`. **Trigger #2** (exercise removal) → auto-merge OFF.

### 2.2 #691 — surface the Tier-2 strength substitution (`templates/plan_create/view.html` + `static/style.css`)
A Tier-2 substitution rendered the un-available **base** exercise (e.g. "Reverse Sled Drag") as the headline with the actual substitute ("band walk-back") a footnote below the prescription → an athlete with no sled reads "prescribed a sled drag." **Traced the full path: 2C→prompt→synthesizer is correct** — `per_phase.py:787` appends `substitute: <text>`, and the validator requires `substitute_text` for `resolution_tier == 2`, so it's always populated. The bug was purely the **render hierarchy**. Fix: for `resolution_tier == 2`, render a prominent **"Do instead: {{ substitute_text }}"** (new `.sess-exercise-sub`, weight 600) under the name and **above** the prescription; the footnote path now only fires for non-tier-2. Tier-3 proxy already names the proxy exercise, so it's unchanged. **No prompt change** (not Trigger #1).

## 3. Tests
- `tests/test_exercise_inventory_cull_694.py` — 5 absent from both seeds; cull migration present + FK-ordered; `current_rx` cleanup present.
- `tests/test_redesign_view_plan_render.py` — extended: tier-2 renders `sess-exercise-sub` + `Do instead: …` (not just the footnote).
- **Full suite 2567 passed / 30 skipped.** No DDL.

## 4. Decisions / triggers
| # | Decision | By |
|---|---|---|
| 1 | Cull the 5 (Trigger #2) — auto-merge OFF, ratify-by-merge | Andy (named them) + Claude |
| 2 | #691 = render-prominence fix (deterministic, no prompt) — "Do instead:" directive | Andy approved the framing |
| 3 | Stack #694 + #691 on one PR (single pinned branch) — flagged; split on request | Claude |

## 5. Filed this session
- **#698** — audit: exercises not wired properly. Seeded with the read-only sweep finding: **13 active exercises carry skill/discipline tokens mis-filed in `equipment_required`** (`Climbing — roped` ×8, `Touring/AT ski setup` ×4, `Mountaineering` ×1) — the equipment gate can never match them; the catalog conflates equipment / skill-capability / discipline in one column.

## 6. Next pointers (read order — Rule #13)
1. `CLAUDE.md` 2. `CURRENT_STATE.md` 3. `CARRY_FORWARD.md` 4. This handoff 5. `./scripts/verify-handoff.sh`.
Rest of the 6/17 batch: **#689/#690/#624** (Trigger #1 prompt), **#692** (Trigger #2 bike vocab), **#283** (FIT-decode prod log). **#691 tier-confirmation** (was it tier 2 vs 3?) via the plan `effective_pool` log is optional — the render fix helps either tier.

## 7. Manual verification — OWED (Andy-action)
- After #697 merges + deploys: `/rx` no longer lists the 5; a Tier-2 substitution on a plan shows "Do instead: …" as the directive above the prescription.
- The `neon-query` results pasted this session confirmed the sled data is canonical (`{"Weighted sled"}`), so #691 is render-only — no data fix needed there.
- (Carried) post-#572 live T3 refresh; #430 Slice C / #679 EX-id self-heal live-verify.

## 8. Files
**Substantive (3):** `init_db.py`, `templates/plan_create/view.html`, `static/style.css`. **Tests:** `tests/test_exercise_inventory_cull_694.py`, `tests/test_redesign_view_plan_render.py`. **Bookkeeping:** `CURRENT_STATE.md`, this handoff, GitHub issues #694 / #698.

---

**End of handoff.**
