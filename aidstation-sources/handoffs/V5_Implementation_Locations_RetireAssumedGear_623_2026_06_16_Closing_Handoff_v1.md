# V5 Implementation — #623 Retire "assumed" basic gear + de-drift exercises — Closing Handoff

**Date:** 2026-06-16
**Branch:** `claude/v5-locations-surface-routing-21dtsx` (harness-pinned; kept per "never push to a different branch")
**PR:** [#643](https://github.com/ahorn885/exercise/pull/643) — opened ready-for-review, auto-merge (squash) enabled, awaiting CI (Layer 0 integrity gate + Python unit suite + JS harness).
**Migration:** `etl/migrations/layer0/0008_retire_assumed_gear.sql`
**Predecessor handoff:** `handoffs/V5_Implementation_Locations_SurfaceSpecificRouting_624_Slice3_2026_06_16_Closing_Handoff_v1.md` (#624 Slice 3, PR #642 merged, #624 CLOSED).

Picked up the "Locations & Gear" arc after #624 closed (Andy: "let's keep working!"). Session-start Rule #9 sweep was clean; confirmed PR #642 merged + #624 closed completed on GitHub before opening new work.

---

## 1. What shipped — #623

### The gap
The per-locale gear editor (`routes/locales._layer0_equipment`) renders **every** active `layer0.equipment_items` row. So "assumed" basic gear — items every athlete in these sports owns, that carry no training-feasibility signal — clutters the picker, and where an exercise *hard-requires* one in `equipment_required`, silently gates that session on a checkbox the athlete should never have to tick (`_tier_1` = `equipment_required ⊆ effective_pool`; the pool is only the athlete's picked gear + toggle-paired categories — `is_universal` is **dead code**, never read by `layer2c/builder._build_effective_pool`).

### Audit (read-only `neon-query` vs live prod, run id 27594129687)
- Live active equipment_items = **118** (= the v1.8.0 dump's 127 − the 9 vessels `0007` retired; the vessel/`Mountaineering kit` probe returned 0 rows → `0007` confirmed fully applied live).
- All **17** retire targets active. Of them, only **3 gear items hard-gate** `equipment_required`: Backpack ×10, Trekking poles ×7, Doorway ×2. The other 14 gate zero exercises.
- Exact de-drift set (17 exercises): EX010, EX050, EX077, EX095, EX118, EX120, EX121, EX122, EX123, EX124, EX144, EX150, EX153, EX154, EX155, EX183, EX097.

### Decisions (Andy via `AskUserQuestion`, Trigger #2 vocab + Trigger #3 cross-layer)
1. **Audit first** → then **de-drift** (the `0007` pattern), not `is_universal`-wiring, not retire-clean-6-only.
2. **Retire all 17** = the 8 sport-specific (Backpack, Headlamp, Hiking boots, Running shoes, Trekking poles, Wetsuit, Swim cap and goggles, Avalanche safety gear) + the 9 self-labelled "Assumed Universal" (Bodyweight, Floor space, Wall, Doorway, Outdoor space, Anchor point, Compass, GPS, Topographic map).
3. **Avalanche safety gear → retire as assumed** (its old "safety gate" note is wired *nowhere* in code — no `.py`, no toggle — so retiring breaks no live gate).

### The build (1 substantive file)
- **`etl/migrations/layer0/0008_retire_assumed_gear.sql`** —
  - **(0C)** supersede the 17 `equipment_items` rows (supersede-only; picker filters `superseded_at IS NULL` → they vanish).
  - **(0B)** de-drift: supersede + reinsert every active exercise whose `equipment_required` overlaps the retire set, with those tokens stripped (order preserved), at `0B-v1.6.8`→`0B-v1.6.9` so the per-table digest advances and plan-gen caches invalidate. Non-retire tokens preserved — EX150 keeps `{Mountaineering}` (a gear toggle, not an item), EX153 `{Snowshoes}`, EX010 `{Weighted vest}`, EX050 `{Treadmill}`; EX077/EX120/EX124 → `{}` (always-available).
  - Idempotent (reinsert/supersede guarded to `etl_version <> '0B-v1.6.9' AND equipment_required && retire-set`; reinserted rows carry no retire token → re-run is a clean no-op). Atomic DO-block verify (no retire item active; no active exercise still names one; 4 known survivor tokens intact).
- **`equipment_substitutes_structured` intentionally left untouched** — a live audit confirmed every one of the ~20 backpack-substitute exercises retains a safety net (an `is_improvised` "backpack loaded with books"-style sub that resolves regardless of pool, plus physical proxies + non-retired subs) → **no session drops**. Substitutes are tier-2 enrichment, not the tier-1 gate this issue is about; rewriting 20 JSON blobs is out of scope.

**NO DDL. No app/template change** (picker auto-excludes superseded rows; nothing in `routes/`/`templates/`/`layer*` hardcodes these names; the only test hits are self-contained `test_layer2c.py` mock fixtures). **No `LAYER4_PROMPT_REVISION` bump** — data-only; cache invalidation rides the `0B-v1.6.9` digest (same as `0007`).

### Verification
Replicated the CI Layer-0 gate **locally on the v1.8.0 baseline (local PG16 — stricter than CI's PG17):** `0006`→`0008` apply clean + idempotent; `validate_layer0` **PASS** (all checks clean/waived). Post-apply: **101 active** equipment_items (118−17), **0** retire items active, **0** active exercises still naming a retire item in `equipment_required`, survivors intact; re-run of `0008` = clean no-op (17 rows at `0B-v1.6.9`, no dupes). Python suite **2496 passed / 30 skipped**; `etl/tests` **89 passed**.

## 2. STILL OWED on #623
- ⬜ **APPLY to prod** — trigger `layer0-apply` (Andy one-tap on the `production` environment) **after #643 merges**, then verify via `neon-query` (expect 101 active items, 0 exercises gating a retire item). #623 should be **CLOSED completed** once applied + verified.

## 3. Side-findings this session
- **`Mountaineering` false alarm cleared.** It is a gear *toggle* (`sport_specific_gear_toggles`), not an orphan equipment token. The old `Mountaineering kit` equipment_item was superseded 2026-06-10 — retired into the toggle model alongside climbing gear. EX148/EX149/EX150 reference it correctly (mirrors EX195→`Climbing — roped`) and fall back via Tier-3 physical_proxies when the gear/skill is absent → **no action**; not in the #623 retire set.
- **Adjacent (separate, pre-existing, not actioned):** all 12 active gear toggles have `paired_equipment_categories = {}` (confirmed intentional in `populate_gear_toggles_batch_a.sql` — migrations only ever set `also_satisfies`/`gated_discipline_ids`). So a toggle-named `equipment_required` token can never tier-1 resolve even with the toggle ON; those exercises reach availability only via Tier-3 proxies. Likely by design (gate-to-proxy). Flagged for Andy; not filed.

## 4. NEW issue filed this session
- **[#644](https://github.com/ahorn885/exercise/issues/644)** — Curate the `Technical / Skill` exercise library. **65 of 211 active exercises (31%) are `Technical / Skill`**; some are non-trainable familiarization/gear-setup ("Snowshoe Gait Technique" = walking in snowshoes; "Pack Fit Optimization Drill" = gear setup; "Rest Step Technique" = a breathing cue) that Layer 4 can prescribe into a plan. Needs per-entry coaching judgment (Trigger #2) — keep real skill *sessions* (eskimo roll, transitions, line reading), cull the rest. Surfaced mid-#623; Andy chose to ship #623 and file this as its own pass. The issue carries the full 65-entry list + FK-integrity caution.

## 5. NEXT STEPS — "Locations & Gear" arc continues
- **[#644](https://github.com/ahorn885/exercise/issues/644)** — Technical/Skill exercise-library curation (Trigger #2; per-entry sign-off).
- **[#619](https://github.com/ahorn885/exercise/issues/619)** — profile Locations tab + nav IA. Pure UI/IA.
- **Carried (unrelated):** post-#572 live **T3 *refresh*** re-verify (Rule #14 — needs Andy's live hands + diag token).

## 6. Bookkeeping done this session
- **`CURRENT_STATE.md`:** new top "Last shipped session" entry (#623); Slice 3 demoted to predecessor (marked #642 MERGED / #624 CLOSED).
- **GitHub:** PR #643 opened (ready-for-review) + auto-merge; issue #644 filed; #623 to be commented + closed-on-apply.
- **`CARRY_FORWARD.md`:** no edit.

## 6.3 Operating notes (Rule #13 read order)
1. `CLAUDE.md` — stable rules. 2. `CURRENT_STATE.md` — top entry = this session. 3. `CARRY_FORWARD.md` — Ops automation / operating model. 4. This handoff. 5. `./scripts/verify-handoff.sh`.

---

## 8. Session-end verification (Rule #10)

| Area | Path | Anchor / check |
|---|---|---|
| Migration | `etl/migrations/layer0/0008_retire_assumed_gear.sql` | `CREATE TEMP TABLE _assumed_gear`; 17 names; `(0C)` supersede equipment_items; `(0B)` reinsert at `'0B-v1.6.9'`; verify DO-block RAISEs on dirty state |
| De-drift logic | same | `unnest(e.equipment_required) WITH ORDINALITY ... WHERE tok NOT IN (SELECT name FROM _assumed_gear)`; `equipment_required && ARRAY(SELECT name FROM _assumed_gear)` |
| No app change | `routes/locales.py` | `_layer0_equipment` already filters `WHERE superseded_at IS NULL` — no edit |
| Local gate | — | PG16: baseline v1.8.0 + 0006–0008 apply clean + idempotent; `validate_layer0` PASS; 101 active items; 0 exercises gating |
| Suite | — | tests/ 2496 passed / 30 skipped; etl/tests 89 |
| Gate | — | NO DDL; Layer-0 gate validates 0008 in CI; JS harness unaffected |
| Issue #623 | — | OPEN until `layer0-apply` runs on prod + `neon-query` verifies → CLOSE completed |
| Issue #644 | — | NEW — Technical/Skill curation (65/211); full list in the issue body |
| Owed | — | (1) apply 0008 to prod after #643 merges; (2) post-#572 live T3-refresh re-verify carried (Rule #14) |
