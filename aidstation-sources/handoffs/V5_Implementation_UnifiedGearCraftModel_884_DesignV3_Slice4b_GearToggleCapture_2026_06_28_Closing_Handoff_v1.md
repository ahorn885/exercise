# V5 Implementation — #884 Unified Gear/Craft Model — Slice 4b PR-1 (gear-toggle capture surface) — Closing Handoff

**Session:** Slice 4b of #884, started. Shipped the **gear-toggle capture surface** (the "capture-first" half of 4b) — the inert producer that writes the discipline-unlocking gear toggles into `athlete_gear`. Paused before the cascade extension (the consumer).
**Date:** 2026-06-28
**Predecessor handoff:** `V5_Implementation_UnifiedGearCraftModel_884_DesignV3_Slice4a_4_2_CascadeReadCutover_CraftWriteSync_2026_06_28_Closing_Handoff_v1.md`
**Branch:** `claude/unified-gear-craft-model-veo6he` (harness-pinned; scope-correct — keep)
**Status:** 3 substantive code files + 2 test files — under ceiling. Suite green **3692/30**.

---

## 0. Thread continuity — STAY ON THIS THREAD

Continuous build of #884. This session split slice 4b into two reviewable PRs (Andy's call, 2026-06-28): **PR-1 = gear-toggle capture (this session, inert producer)**, **PR-2 = cascade extension (next, the consumer that turns behavior on)**. Then **slice 4.3** (redump retiring `craft_discipline_aliases` + equipment strip). Do not drift off #884 until 4b-PR2→4.3→5→6 are done or Andy redirects (tier-1 finish-the-in-flight-task). Design: `designs/Unified_GearCraft_Model_And_Feasibility_884_Design_v3.md` §6/§9/§15.4. Plan: `plans/UnifiedGearCraft_884_Slice4_CascadeCutover_Plan_v1.md`.

---

## 1. Session-start verification (Rule #9)

Anchor-checked the predecessor (slice 4a/4.2) handoff's §8 claims against on-disk + merged state.

| Claim | Anchor | Result |
|---|---|---|
| Slice 4a/4.2 (PR #937) merged | `git log` → `e70e520` on main | ✅ |
| `_collect_athlete_crafts` reads `owned_gear`, filtered to bike/paddle | grep `layer1_payload.owned_gear` + `_CRAFT_ALIAS_GROUP_KINDS` @ `layer4/orchestrator.py:219,237` | ✅ |
| `_q_craft_*` read `gear_discipline_aliases` | grep `FROM layer0.gear_discipline_aliases` → 2 hits | ✅ |
| Family map tracks the alias table | grep `"gear_discipline_aliases": "0A"` @ `:1999` | ✅ |
| Scoped per-surface gear write | `def replace_owned_gear_for_kinds` @ `athlete_gear_repo.py:125` | ✅ |
| Craft repo forward-syncs athlete_gear | `replace_owned_gear_for_kinds(` @ `athlete_crafts_repo.py:99` | ✅ |
| Suite green | `tests/ etl/tests/` 3692 passed / 30 skipped (baseline this session) | ✅ |

No drift. `verify-handoff.sh` resolves the §8 files relative to repo root (not `aidstation-sources/`) — all ✅, tree clean.

---

## 2. Session narrative

- Andy: "keep working!" on the slice-4 handoff → continue #884, next is slice 4b.
- Grounded the 4b surface: `resolve_craft_terrain_feasibility` (`session_feasibility.py:365`) is gated to `_CRAFT_GROUP_KINDS = {bike,paddle}` and walks `own/proxy_crafts` by **sorted slug, not `fidelity_rank`**; `gear_discipline_aliases` already carries `fidelity_rank` but the 4a readers drop it; 2C is still starved (`cluster_gear_toggle_states={}` @ `orchestrator.py:1119,1551`); `craft_terrain_compatibility` has **no** ski-gear rows in any migration → migration `0026` genuinely needed.
- **Flagged the scoping tension:** slice 4b as the predecessor bundled it (cascade + rank walk + 2C feed + gear-toggle capture + `0026`) ≈ 8–10 substantive files — over the 5-file ceiling + a cross-layer Stop-and-ask Trigger #3. Naively shipping the cascade *before* capture opens a degradation window (ski/snow/climbing/alpine read an empty store → drop to INDOOR/STRENGTH where today they get terrain-only).
- **Andy chose "capture first, then cascade"** (AskUserQuestion). PR-1 ships the capture (inert — nothing reads the toggle kinds yet, safe like slice 3); PR-2 ships the cascade with the store already populated → no degradation window, each PR under the ceiling.
- Built + verified PR-1. Paused before PR-2 (the cascade extension + migration `0026`, which Andy applies via `layer0-apply` — a natural boundary).

---

## 3. File-by-file edits

### 3.1 `athlete_gear_repo.py` (modified)
- `_GEAR_TOGGLE_KINDS = frozenset({"ski","snow","climbing","alpine"})` (`:78`) — the discipline-unlocking toggle kinds this surface owns (crafts have their own picker; swim is drill-gating, slice 6).
- `GEAR_TOGGLE_LABELS` (`:88`) — presentation labels for exactly the 7 toggle slugs (classic_xc_ski/skate_xc_ski/rollerskis/snowshoes/climbing_gear/mountaineering/skimo_at), the analogue of `athlete.CRAFT_LABELS`. Presentation-only for the existing closed §5.5 keyspace — **not** vocab padding.
- `load_gear_toggle_catalog()` (`:170`) — `[{slug,label}, …]` in `_GEAR_IDS` order, filtered to `_GEAR_TOGGLE_KINDS`. Mirrors `load_craft_catalog`.
- `get_owned_gear_toggles(db,uid)` (`:181`) — the owned toggle slugs (filter `get_athlete_gear` to the toggle kinds), in keyspace order — the picker's checked-state source.
- `parse_gear_toggle_form(form)` (`:191`) — coerces `gear__<slug>` checkboxes → `{gear_id:'own'}`; replace-all within the kinds (unchecked omitted, no explicit-False rows, unlike skills); only catalog slugs considered → a malformed POST can't inject an unknown/off-surface gear_id.

### 3.2 `routes/profile.py` (modified)
- Import block from `athlete_gear_repo` (`GearSelectionError`, `evict_layer1_on_gear_change`, the 3 new helpers, `replace_owned_gear_for_kinds`, `_GEAR_TOGGLE_KINDS`).
- `edit()`: loads `gear_toggle_catalog` + `owned_gear_toggles`, passes both to `profile/edit.html`.
- **NEW `save_gear_toggles()` (`POST /profile/gear-toggles`):** parse → `replace_owned_gear_for_kinds(db, uid, owned, _GEAR_TOGGLE_KINDS)` (scoped replace-all, preserves crafts + swim) → commit → `evict_layer1_on_gear_change` → redirect `tab=gear`. `GearSelectionError` → flash + redirect (writes nothing). **Rule #15** `[gear-toggle-capture] uid=… owned=[…]` print (the decision the path made).

### 3.3 `templates/profile/edit.html` (modified)
- New "● Sport-specific gear you own" form in the Gear & skills tab (between the owned-crafts form and the race-day-skills form), posting to `save_gear_toggles`. Checkboxes `gear__<slug>` rendered from `gear_toggle_catalog`, checked against `owned_gear_toggles`. Mirrors the crafts-form structure (no new partial — inline, profile-only).

---

## 4. Code / tests

Suite: **tests/ + etl/tests/ 3692 passed / 30 skipped** (only the 3 pre-existing #217 Layer3B `evidence_basis` warnings). Ruff: no new findings (the 2 F401 in `routes/profile.py` — `PROFILE_FIELDS`, `DEFAULT_UNIT_PREFERENCE` — pre-exist on HEAD).
- `tests/test_athlete_gear_repo.py` — `TestGearToggleCapture` (+7): labels↔kinds lockstep guard; catalog order/membership; parse checked→own / unchecked-omitted / off-surface+unknown ignored / empty; owned-toggles filtered-to-kinds + empty.
- `tests/test_routes_profile_skills.py` — `TestSaveGearTogglesRoute` (+2): POST writes the scoped DELETE (4 kinds, sorted) + 2 INSERTs + evicts + redirects; empty form → single scoped DELETE, no INSERT (replace-all clears only the toggle kinds).

---

## 5. Staging note — this is an INERT producer (no served-output change)

Like slice 3 (the store) and 4a (the read cutover was behavior-preserving), PR-1 changes **no plan output**. The capture writes the toggle kinds into `athlete_gear`, but **nothing reads the toggle kinds yet** — the cascade is still gated to `{bike,paddle}` (`session_feasibility._CRAFT_GROUP_KINDS`), and the 2C feed is still `={}`. So owned toggles accumulate, ready for PR-2 to consume. No Neon apply owed (public-schema table already live since slice 3; this is route + repo + template only). Eviction fires on save (`evict_layer1_on_gear_change` → Layer 1 → all L4 + both L3) so once PR-2 lands and a re-plan runs, the captured gear is already in the hash.

---

## 6. Next session pointers

### 6.1 Architect-recommended next forward move
**Slice 4b PR-2 — cascade extension (the consumer):**
- `session_feasibility.py`: widen `_CRAFT_GROUP_KINDS` from `{bike,paddle}` to all gear kinds; thread `fidelity_rank` (new rank-aware reader — `gear_discipline_aliases` already has the column, but `_q_craft_discipline_aliases` drops it; add `_q_gear_aliases` returning `{gear_id:(disc,rank)}` or extend the readers) and **order `own_crafts`/`proxy_crafts` by ascending rank** (currently sorted-by-slug). Bike/paddle must stay byte-identical (rank-0 single-tier == today) — regression tests pin it.
- **Migration `0026`** (Layer-0, needs `layer0-apply`): seed `craft_terrain_compatibility` ski-gear rows — `classic_xc_ski`→`TRN-012`, `skate_xc_ski`→`TRN-012`, `rollerskis`→`TRN-001` (Decision 3, reuse, no new vocab). Verify-DO block (3 active rows + no dangling refs, mirror 0025). Next free number is `0026` (0023/0024/0025 live).
- Rollerski carve-out **falls out of Tier 2** ("own the craft, ride an alternate compatible terrain"): rank-2 rollerskis on `TRN-001` when D-028's required `TRN-012` (snow) is absent → PROXY. No special-case branch.
- Feed `cluster_gear_toggle_states` from `athlete_gear` at `orchestrator.py:1119,1551` (the #298 un-starve) — bridge owned gear → the 2C `sport_specific_gear_toggles` toggle vocab.
- Tests: rank-walk (classic>skate>rollerski), rollerski-dryland PROXY, climbing gear+skill matrix, bike/paddle regression.

Then **slice 4.3** — forced redump retiring `craft_discipline_aliases` (heed the redump-fold rule, `etl/migrations/layer0/README.md`) + the equipment strip (supersede `pull_buoy`/`kickboard`/`Swim fins` from `equipment_items` + strip from EX126/EX128 `equipment_required`, 0B supersede+re-insert → global cache invalidation).

### 6.2 Open question for PR-2 / later
- **Onboarding parity:** crafts are captured on **both** the profile gear-tab and onboarding (via `replace_athlete_crafts`); gear toggles are captured on the **profile gear-tab only** (the explicit slice-4b instruction — "reuse the profile gear-tab checkbox pattern"). If onboarding should also surface gear toggles, it's a small follow-on (`routes/onboarding.py` + an onboarding template) — not owed by the slice as scoped. Flag for Andy.

### 6.3 Operating notes for next session (Rule #13)
1. `CLAUDE.md` — stable rules.
2. `CURRENT_STATE.md` — last-shipped (this) + the #884 predecessors.
3. `CARRY_FORWARD.md` — the #884 rolling item (slice-4 PROGRESS: 4a/4.2 done; 4b-PR1 done; 4b-PR2/4.3 next; resolved terrain ids).
4. This handoff + `plans/UnifiedGearCraft_884_Slice4_CascadeCutover_Plan_v1.md`.
5. `./scripts/verify-handoff.sh` (run from `aidstation-sources/`).

---

## 7. Decisions pinned

| # | Decision | Picked by | Rationale |
|---|---|---|---|
| 1 | Split slice 4b into PR-1 (capture) + PR-2 (cascade) | Andy 2026-06-28 | 4b ≈ 8–10 files over the ceiling; capture-first avoids the degradation window (cascade reading an empty toggle store) |
| 2 | Capture surface = profile gear-tab only (no onboarding, no new "Your gear" UX) | Andy 2026-06-28 (slice-4 Decision 2) | Reuse the existing checkbox pattern; the unified surface stays S6 |
| 3 | Gear-toggle labels defined in-repo (presentation-only) | Claude | Existing closed §5.5 keyspace; UI copy, not vocab padding (Trigger #2 N/A) |

---

## 8. Session-end verification (Rule #10)

| Claim | File | Check |
|---|---|---|
| Toggle kinds + labels constants | `athlete_gear_repo.py` | grep `_GEAR_TOGGLE_KINDS` + `GEAR_TOGGLE_LABELS` |
| Catalog / owned / parse helpers | `athlete_gear_repo.py` | grep `def load_gear_toggle_catalog` `def get_owned_gear_toggles` `def parse_gear_toggle_form` |
| Capture route writes scoped to toggle kinds | `routes/profile.py` | grep `def save_gear_toggles` + `replace_owned_gear_for_kinds(db, uid, owned, _GEAR_TOGGLE_KINDS)` |
| Rule #15 log | `routes/profile.py` | grep `[gear-toggle-capture]` |
| Gear-toggle form in gear tab | `templates/profile/edit.html` | grep `save_gear_toggles` + `gear__` |
| Suite green | (local) | `tests/ etl/tests/` 3692 passed / 30 skipped |
| Working tree clean | — | `git status` clean at push |

---

## 9. Files shipped this session

**Substantive (3 code):**
1. `athlete_gear_repo.py` — gear-toggle capture helpers (catalog/labels/owned/parse)
2. `routes/profile.py` — `save_gear_toggles` route + `edit()` wiring
3. `templates/profile/edit.html` — gear-toggle form in the Gear & skills tab

**Tests (2):**
4. `tests/test_athlete_gear_repo.py` (+7 `TestGearToggleCapture`)
5. `tests/test_routes_profile_skills.py` (+2 `TestSaveGearTogglesRoute`)

**Bookkeeping (outside the ceiling):** `CURRENT_STATE.md`, `CARRY_FORWARD.md`, this handoff.

---

## 10. Carry-forward updates

`CARRY_FORWARD.md` #884: slice-4 PROGRESS line updated — 4a/4.2 done; **4b-PR1 (gear-toggle capture) done+pushed**; 4b-PR2 (cascade extension + migration `0026`) + 4.3 (redump + equipment strip) next. The #298 gear-toggle starvation is **half-closed** (capture now writes `athlete_gear`; the cascade consumes in PR-2).

---

**End of handoff.**
