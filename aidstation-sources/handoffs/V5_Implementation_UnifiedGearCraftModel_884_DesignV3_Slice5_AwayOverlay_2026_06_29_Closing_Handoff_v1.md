# V5 Implementation — #884 Unified Gear/Craft Model — Slice 5 (away overlay: cut the away cascade onto the unified gear store) — Closing Handoff

**Session:** Slice 5 of #884 — the **away-overlay** slice. Generalize `_build_event_window_overlay` so the away segment resolves its `owned_crafts` off the **unified `athlete_gear_locale` store** (instead of the legacy bike/paddle-only `athlete_craft_locale`), and cut the standing craft↔locale **capture** (`routes/locales.py`) over to that same store so the read isn't stale. **Trigger #3** (the eviction story moves from `craft_locale`→`gear_locale`; cache invalidation preserved). Andy-ratified scope (design v3 §7 / §15 slice 5).
**Date:** 2026-06-29
**Predecessor handoff:** `V5_Implementation_UnifiedGearCraftModel_884_DesignV3_Slice4_3_RedumpRetire_EquipmentStrip_2026_06_29_Closing_Handoff_v1.md` (slice 4.3, merged `5576a59` / PR #1008; redump-fold baked into `v1.10.0`).
**Branch:** `claude/884-unified-gear-craft-fbhabu` (off `main` HEAD `f209f58`).
**Status:** code done, **suite 3874/30 green**, ruff clean on changed files, **2 substantive files** (`routes/locales.py` + `layer4/orchestrator.py`) under the ceiling. **No migration / no Neon apply owed** (public-schema reads only; the gear-locale store is already live from the slice-3 backfill). **PR opening + auto-merge MERGE (Andy's go 2026-06-29).** **#884 CONTINUES — next is slice 6** (capture UX + unified gear registry — Andy ratified the full 6a/6b/6c plan + decisions D1/D2; see §6.2).

> **Andy decision this session (AskUserQuestion, 2026-06-29):** slice-5 scope = **"Feasibility now, 2C later."** Ship the away **feasibility** generalization onto the unified store; **defer** the full per-segment **2C** re-resolve (away equipment pool driving the strength-substitute exercise pool) to slice 6. Rationale below (§2).

---

## 0. Thread continuity — NEXT SESSION CONTINUES #884

**The next forward move is slice 6** (capture-UX "Your gear" surface + onboarding parity + the unified picker/validator registry, design v3 §10). Design v3 §15: 1→2→3→3a→3b→4(a/4.2/4b)→4.3→**5 (this)**→6. **STAY ON THE #884 THREAD** until 6 is done or Andy redirects.

---

## 1. The change

### Decision context (no NEW architecture — ratified scope executed)
Slice 5 is design v3 §15 ("Away overlay — generalize `_build_event_window_overlay` + away re-resolve, §7"). §7 reads "union standing `athlete_gear_locale` + `brought_gear` … re-resolve the away environment's feasibility **+ 2C** for that segment." The session's only open shape decision — how far to take "+2C" — was resolved by Andy (AskUserQuestion): **feasibility now, 2C later** (§2).

### Part A — away overlay reads the unified gear store (`layer4/orchestrator.py`)
`_build_event_window_overlay` previously loaded the standing map via `athlete_craft_locale_repo.load_craft_locales` (bike/paddle craft slugs only) and unioned it with the window's `brought_craft` to form the away segment's `owned_crafts`. Now it loads **`athlete_gear_repo.load_gear_locales`** (the unified store — all gear kinds) and **filters the brought∪standing union to the craft cascade kinds** (`GEAR_REGISTRY.get(g) in _CRAFT_ALIAS_GROUP_KINDS` — bike/paddle/ski/snow/climb/alpine; the same filter `_collect_athlete_crafts` applies at home), so swim/other gear can't leak into the craft cascade.
- **Behavior-preserving for bike/paddle** — the gear store was backfilled 1:1 from the craft tables (slice 3); craft slugs ⊆ `_GEAR_IDS`.
- **New capability (plumbed):** ski/snow/climb/alpine gear kept at a destination locale now feeds the away cascade's `owned_crafts` → a stationed/brought discipline-unlocking gear resolves EXACT/PROXY in that segment. (UI-reachable once slice 6 generalizes the picker catalog — see §3.)
- **Brought (c) stays the `brought_craft` field** — its values are craft slugs (= gear_ids) and union fine with the gear store; the brought-**gear** picker (offering the toggle kinds) is slice-6 capture. `compute_event_windows_hash` still folds `brought_craft` unchanged → no hash churn.

### Part B — standing-capture cutover (`routes/locales.py`)
The standing craft↔locale **write** path still targeted the legacy `athlete_craft_locale` (via `replace_craft_locale` / `evict_plan_caches_on_craft_locale_change`), while `athlete_gear_locale` was only a deploy-time backfill mirror with **zero live writers**. Reading the mirror in Part A without cutting the write over would read stale data (post-deploy edits never propagate). So both `routes/locales.py` write sites — the standalone `save_craft_locale` route and the unified `_edit_locale` save (#953) — plus the GET render now use **`replace_gear_locale` / `load_gear_locales` / `evict_plan_caches_on_gear_locale_change`** (and catch `GearSelectionError`). The picker **catalog stays craft-only** (`load_craft_catalog`) — the unified gear picker is slice 6 — so `replace_gear_locale` only ever sees craft gear_ids → byte-identical to the prior craft-locale write.

---

## 2. The "+2C" scope decision (Andy: feasibility now, 2C later)

Investigation finding (corroborated by a code-map sweep): **Layer 2C is built once against the home cluster and has no per-segment plumbing at synthesis time.** The away environment is captured *only* in `EventWindowSegment.away_feasibility` (terrain/craft-based). The gear-toggle gating that drives **discipline feasibility** already flows through `owned_crafts` into the slice-4b cascade — so the contained Part-A change covers the feasibility routing. What a literal "+2C re-resolve" would *add* is the away **equipment pool** feeding the **strength-substitute exercise pool** (`pool_by_discipline`) + the `toggle_off_for_discipline` flag, scoped per away segment — which requires **new synthesis plumbing** threading an away-cluster 2C payload through `EventWindowSegment` → `per_phase` → `synthesize_phase`. That is architecturally significant, over the 5-file ceiling, and depends on slice-6 brought-gear capture to be observable. **Andy chose to defer it** (it folds naturally into slice 6). The away-week strength-substitute pool therefore still uses the **home** gym's equipment — an existing limitation that predates slice 5 (slices 2/3/4 carried it), now explicitly tracked for slice 6.

---

## 3. Behavior change (intended) + cache

- **Bike/paddle:** byte-identical (store backfilled 1:1; same craft slugs union the same way).
- **Ski/snow/climb/alpine:** the away cascade now *can* resolve these gear kinds when stationed at / brought to a destination — but there is **no capture path that writes those kinds into `athlete_gear_locale` yet** (the standing picker catalog is craft-only; the brought picker is `brought_craft` craft-only). So slice 5 is a **behavior-preserving cutover/plumbing** slice (the slice-4a pattern). The new away capability lights up in **slice 6** when the unified picker captures ski/climbing gear at a locale / as brought.
- **Cache:** the standing-edit eviction moves from `layer="craft_locale"` → `layer="gear_locale"` (both evict `plan_create`/`plan_refresh` — unchanged targets). `compute_event_windows_hash` unchanged (still folds `brought_craft`). No one-time invalidation introduced.

---

## 4. File-by-file edits

### 4.1 `layer4/orchestrator.py` (modified)
- Import: `from athlete_craft_locale_repo import load_craft_locales` → `from athlete_gear_repo import GEAR_REGISTRY, load_gear_locales`.
- `_build_event_window_overlay`: `craft_locale_map = load_craft_locales(...)` → `gear_locale_map = load_gear_locales(...)`; the away branch now computes `away_crafts = sorted(g for g in (brought | standing) if GEAR_REGISTRY.get(g) in _CRAFT_ALIAS_GROUP_KINDS)` where `standing` reads the gear store. Comments + the Rule #15 `_away_dbg` log updated.

### 4.2 `routes/locales.py` (modified)
- Import block: craft-locale symbols → `GearSelectionError, evict_plan_caches_on_gear_locale_change, load_gear_locales, replace_gear_locale` (kept `load_craft_catalog`).
- `save_craft_locale` (standalone route): `replace_gear_locale` + `except GearSelectionError` + `evict_plan_caches_on_gear_locale_change`.
- `_edit_locale` (#953 unified save): `prior_crafts = load_gear_locales(...)`, `replace_gear_locale(...)` + `except GearSelectionError`, `evict_plan_caches_on_gear_locale_change`.
- GET render: `crafts_here=load_gear_locales(...)`.

### 4.3 `tests/test_layer4_event_windows.py` (modified — not counted)
- Repointed the 4 `orch.load_craft_locales` monkeypatches → `load_gear_locales`; renamed the `craft_locales` helper params → `gear_locales`. `TestCraftLocaleRepo` left intact (it unit-tests the still-present `athlete_craft_locale_repo` module directly). **+2 slice-5 cases:** `test_standing_gear_toggle_kind_unioned` (standing `climbing_gear` → in `owned_crafts`) + `test_non_craft_gear_filtered_out` (swim `paddles`/`pull_buoy` dropped; `mountain_bike` kept).

### 4.4 `tests/test_locales.py` (modified — not counted)
- `_patch_craft_save` helper + the `TestEditLocaleSavesCraftInline` eviction spy repointed to the gear symbols.

---

## 5. Code / tests validation

- **Suite `tests/ etl/tests/`: 3874 passed / 30 skipped** (only the 3 pre-existing #217 Layer3B `evidence_basis` warnings).
- **Ruff:** clean on all 4 changed files' edited regions. (The 1 pre-existing `F401 pytest` in `tests/test_locales.py` is HEAD-pre-existing — confirmed via stash — and untouched.)
- **No migration / no Neon apply / no layer0 gate owed** — public-schema reads; `athlete_gear_locale` is live from the slice-3 backfill.
- **Compatibility checks done:** all 9 craft slugs ⊆ `_GEAR_IDS` (so `replace_gear_locale` accepts every craft-catalog submission — no rejection regression); the swim gear ids (`fins`/`kickboard`/`paddles`/`pull_buoy`) are the only non-craft-kind `_GEAR_IDS` → correctly filtered out of the away `owned_crafts`.
- **File count:** 2 substantive (`orchestrator.py` + `routes/locales.py`) — under the ceiling.

---

## 6. Next session pointers

### 6.1 Open follow-ons surfaced this session
- **`athlete_craft_locale_repo.py` is now app-dead** — no non-test importer remains (only comment/docstring mentions in `layer4/hashing.py` + `athlete_gear_repo.py`, and the `init_db` backfill still reads the `athlete_craft_locale` *table* as its source). Its own unit tests (`TestCraftLocaleRepo` in `test_layer4_event_windows.py`) still pass. **Flagged, NOT deleted** (surgical-changes rule). Retire the module + the table in a slice-6 cleanup or the next redump-fold once the backfill source is no longer needed.
- **Per-segment 2C re-resolve (the deferred "+2C" half of §7)** — fold into slice 6: thread an away-cluster 2C payload (away equipment pool + away gear-toggle states) through `EventWindowSegment` → `per_phase` so an away week's strength-substitute pool + `toggle_off_for_discipline` flag reflect the destination, not the home gym.
- **`replace_gear_locale` replace-all trap (for slice 6):** it replaces *all* gear at a locale. Safe now (only craft gear can be there). When slice 6's picker offers ski/climbing/swim at a locale, the form must submit the full owned-at-locale set (or switch to a kind-scoped replace) so a craft-only save can't wipe stationed ski/climbing gear.

### 6.2 Next session — CONTINUE #884 → slice 6 (capture UX + unified gear registry) — RATIFIED
**This is the next step. Andy ratified the full slice-6 plan (2026-06-29):** build **all three sub-PRs 6a/6b/6c**; **D1 = consolidate the "Your gear" surface on the existing profile Gear & skills tab** (not a new page); **D2 = a runtime gear registry** folding the two catalogs (no new Layer-0 surface). Execute against **`plans/UnifiedGearCraft_884_Slice6_CaptureUX_Plan_v1.md`** (the full file map, sub-PR breakdown, and §4 decision record):
- **6a** — unified gear registry + the consolidated owned "Your gear" surface (fold the craft picker + gear-toggle form into one grouped-by-`group_kind` section on the profile gear tab; behavior-preserving capture).
- **6b** — "bring it" + the standing/brought pickers generalized to **all** gear kinds + cut the brought read `brought_craft`→`brought_gear`. **This is the slice that makes slice-5's plumbing observable** (station/bring ski/climbing gear → feasible away; the design §17 climbing-at-away scenario). Watch the `replace_gear_locale` replace-all trap (§6.1).
- **6c** — onboarding gear-toggle parity + retire the now-app-dead `athlete_craft_locale_repo` (+ legacy craft columns) via a redump-fold (the slice-4.3 pattern).

Slice 6 is also the home for the **deferred per-segment 2C re-resolve** (§2 / §6.1). Slice 6 should start on a **fresh branch off main once slice 5 merges** (don't stack on the slice-5 branch). **STAY ON THE #884 THREAD until 6 is done.**

### 6.3 Open follow-ons (carried, not owed by this slice)
- **`Provider_Inbound_Matrix_v2` §12 rollerski footnote** (CARRY_FORWARD doc-nit, #884 design v3 Decision 10).

### 6.4 Operating notes (Rule #13)
1. `CLAUDE.md` — stable rules. 2. `CURRENT_STATE.md` — last-shipped (this) + #884 predecessors. 3. `CARRY_FORWARD.md` — the #884 rolling item + ops gotchas. 4. This handoff + `plans/UnifiedGearCraft_884_Slice4_CascadeCutover_Plan_v1.md` + `designs/Unified_GearCraft_Model_And_Feasibility_884_Design_v3.md` (§7/§10/§15). 5. `./scripts/verify-handoff.sh`.

---

## 7. Decisions pinned

| # | Decision | Picked by | Rationale |
|---|---|---|---|
| 1 | Slice-5 scope = away **feasibility** generalization now; defer the per-segment **2C** re-resolve to slice 6 | Andy 2026-06-29 | The feasibility routing is covered by `owned_crafts`; the "+2C" half needs new synthesis plumbing (over ceiling, architectural) + slice-6 capture to be observable |
| 2 | Cut the standing-capture **write** over to `athlete_gear_locale` in the same slice as the away **read** | Claude | The gear-locale store had zero live writers (backfill mirror only); reading it without the write-cutover would read stale data |
| 3 | Brought (c) surface stays the `brought_craft` field for slice 5 | Claude | Craft slugs are gear_ids and union fine; the brought-**gear** picker is slice-6 capture — keeps the slice at 2 files + no hash churn |

---

## 8. Session-end verification (Rule #10)

| Claim | File | Check |
|---|---|---|
| Away overlay reads the unified store | `layer4/orchestrator.py` | grep `load_gear_locales` + `GEAR_REGISTRY.get(g) in _CRAFT_ALIAS_GROUP_KINDS`; no `load_craft_locales`/`craft_locale_map` remain |
| Standing capture cut over | `routes/locales.py` | grep `replace_gear_locale`/`load_gear_locales`/`evict_plan_caches_on_gear_locale_change`; no `*_craft_locale*` symbols remain |
| Slice-5 away tests | `tests/test_layer4_event_windows.py` | `test_standing_gear_toggle_kind_unioned` + `test_non_craft_gear_filtered_out` present + green |
| Locale-route tests repointed | `tests/test_locales.py` | `_patch_craft_save` patches gear symbols; `TestEditLocaleSavesCraftInline` green |
| Suite green | (local) | `tests/ etl/tests/` 3874 passed / 30 skipped |
| No Neon/layer0 apply owed | — | public-schema reads only; gear-locale live from slice-3 backfill |

---

## 9. Files shipped this session

**Substantive (2, under ceiling):**
1. `layer4/orchestrator.py` — away overlay reads `load_gear_locales` + craft-kind filter
2. `routes/locales.py` — standing craft↔locale capture cut over to the unified gear store

**Tests (not counted):** `tests/test_layer4_event_windows.py`, `tests/test_locales.py`.
**Bookkeeping (outside the ceiling):** `CURRENT_STATE.md`, `CARRY_FORWARD.md`, this handoff, GitHub issue updates.

---

## 10. Carry-forward updates

`CARRY_FORWARD.md` #884: slice-5 (away overlay) **done+pushed** (branch `claude/884-unified-gear-craft-fbhabu`), PR awaiting Andy's go; behavior-preserving cutover (bike/paddle byte-identical; ski/climb away plumbed, lights up at slice-6 capture); no Neon apply owed. **Next: slice 6 (capture UX + unified gear registry)** — also the home for the deferred per-segment 2C re-resolve.

---

**End of handoff.**
