# Unified Gear/Craft Model (#884) — Slice 6 (Capture UX + unified gear registry) — Implementation Plan v1

**Status:** PLAN ONLY — awaiting Andy's ratification of the open decisions (§4). No code written. Slice 6 is the **last** slice of the design-v3 §15 arc (5→6).
**Depends on:** slice 5 (away overlay) MERGED — slice 6b (below) makes slice-5's plumbing observable, so slice 5 should land first. (Slice 5 done+pushed on `claude/884-unified-gear-craft-fbhabu`, PR awaiting Andy's go.)
**Design:** `designs/Unified_GearCraft_Model_And_Feasibility_884_Design_v3.md` §10 (UX/IA), §5.5 (gear_id keyspace), §8 (validation), §11 (migration). **Predecessor plan:** `UnifiedGearCraft_884_Slice4_CascadeCutover_Plan_v1.md`.

---

## 1. Goal (design §10)

One **"Your gear"** capture surface — crafts + gear together, grouped by `group_kind`, each row own/have-access + a **"bring it"** affordance — backed by one unified **gear registry** (folds `sport_specific_gear_toggles` catalog + craft labels, keyed by §5.5) as the single picker + validator source. **Replaces the two craft pickers; first real capture for the non-bike/paddle gear kinds at locales/windows.** Plus **onboarding parity** for gear toggles.

This is the slice that turns the #884 arc's accumulated plumbing into observable product: after slice 6 an athlete can say "I keep my climbing rack at the Boulder cabin" or "I'm bringing skis to the race" and plan-gen treats that gear as available **there** (the slice-5 away cascade + the slice-4b feasibility cascade already consume it).

---

## 2. Current surfaces (grounded — what exists today)

| Surface | Where | Store | Catalog | Gap slice 6 closes |
|---|---|---|---|---|
| Owned crafts | `routes/profile.py` `/profile/crafts` + `templates/profile/edit.html` | `athlete_gear` (4.2 sync via `replace_athlete_crafts`) | `load_craft_catalog()` (9 bike/paddle slugs) | folded into the unified owned surface |
| Owned gear toggles | `routes/profile.py` `/profile/gear-toggles` `save_gear_toggles` → `replace_owned_gear_for_kinds(..., _GEAR_TOGGLE_KINDS)` | `athlete_gear` | `load_gear_toggle_catalog()` (ski/snow/climb/alpine toggles) | folded into the unified owned surface |
| Standing gear↔locale | `routes/locales.py` locale edit page | `athlete_gear_locale` (**slice 5 cutover**) | `load_craft_catalog()` — **craft-only** | generalize to the full registry → ski/climbing stationable |
| Brought gear | `routes/profile.py` event-windows page + `add_event_window` | `brought_craft` (col `brought_gear` backfilled, unread by app) | `load_craft_catalog()` — **craft-only** | generalize to the full registry + cut the read to `brought_gear` |
| Onboarding crafts | `routes/onboarding.py` step 2c.2b → `replace_athlete_crafts` | `athlete_gear` | `load_craft_catalog()` | add gear-toggle parity |

**Already done by prior slices:** owned-gear *capture* (crafts via 4.2 + toggles via 4b PR-1) writes `athlete_gear`; the feasibility cascade (4b) + away overlay (5) read the unified store. **What's missing is purely the capture UX for the non-craft kinds at locales/windows + the registry consolidation + onboarding parity.**

---

## 3. Proposed sub-PR breakdown (each ≤5 substantive files)

### Slice 6a — Unified gear registry + consolidated owned "Your gear" surface
- **New `gear_registry.py`** (or fold into `athlete_gear_repo`): one ordered catalog keyed by §5.5 `gear_id`, each entry `{gear_id, group_kind, label, source}` — folds `load_craft_catalog` + `load_gear_toggle_catalog` into one source. Validator + picker both read it. *(Runtime Python registry — NOT a new Layer-0 surface; the two catalogs already exist. See decision D2.)*
- **`templates/profile/edit.html`:** replace the two separate forms (craft picker + gear-toggle form) with one **grouped-by-`group_kind`** "Your gear" section (own / have-access per row).
- **`routes/profile.py`:** one POST consolidating the two writes (`replace_owned_gear_for_kinds` over all kinds, or keep two repo calls behind one form) → one `evict_layer1_on_gear_change`.
- Behavior-preserving capture (still writes `athlete_gear`); retire the standalone `/profile/crafts` form (keep the route until onboarding/cleanup, 6c).
- Tests.

### Slice 6b — "Bring it" + standing/brought generalized to the full registry (LIGHTS UP slice 5)
- **`routes/locales.py`:** the standing picker catalog `load_craft_catalog()` → the unified registry (all kinds) so ski/climbing gear is stationable at a locale (`athlete_gear_locale`). **Watch the replace-all trap** (slice-5 §6.1): submit the full owned-at-locale set or switch to a kind-scoped replace so a partial save can't wipe other-kind gear.
- **`routes/profile.py` + event-windows template:** the brought picker → the unified registry; **cut the brought read to `brought_gear`** — `add_event_window` writes `brought_gear` (dual-write or migrate off `brought_craft`); `layer4/orchestrator.py` away path reads `away_ov.brought_gear`; `layer4/session_feasibility.py` `EventWindowOverride.brought_craft`→`brought_gear`; `layer4/hashing.py` folds `brought_gear` (byte-identical today). *(Slice 5 deliberately left brought on `brought_craft`; 6b completes it.)*
- Tests: the climbing-at-away scenario end-to-end (design §17: "brings climbing gear to an away window → D-012 feasible in that segment only").

### Slice 6c — Onboarding parity + legacy cleanup
- **`routes/onboarding.py` + onboarding template:** add gear-toggle capture to step 2c.2b (parity with the profile surface) via the unified registry.
- **Legacy retirement:** `athlete_craft_locale_repo.py` is now app-dead (slice-5 finding); retire it + the legacy craft columns (`discipline_baseline_*` craft CSVs, `athlete_craft_locale` table, `brought_craft` col) — **coordinate with a redump-fold** (the slice-4.3 pattern: the backfill source can't drop until the new baseline no longer needs it). May warrant its own Layer-0 housekeeping slice.

---

## 4. Decisions needing Andy's ratification (stop-and-ask: UX/IA + architecture)

- **D1 — IA placement.** Consolidate the unified "Your gear" surface on the **existing profile Gear & skills tab** (lowest-churn; the plan §S6 note leaned here) vs a **new dedicated "Your gear" page** (system-review note 15 Profile IA reorg). *Recommendation: profile gear tab; revisit a dedicated page if the grouped registry gets large.*
- **D2 — Registry backing.** A **runtime Python registry** folding the two existing catalogs (no new Layer-0 surface) vs a **Layer-0-backed catalog**. *Recommendation: runtime registry keyed by §5.5 — the catalogs already exist; no padding, no new L0 digest.*
- **D3 — "bring it" affordance shape.** A per-row "bring it" shortcut on the gear surface vs **generalizing the existing per-locale (standing) + per-window (brought) pickers** to the full registry. *Recommendation: generalize the existing pickers (minimal, reuses the event-window/locale flows); a per-row shortcut is optional polish.*
- **D4 — Sub-PR split.** 6a / 6b / 6c as above, or fold 6a+6b into one. *Recommendation: keep 6b separate — it carries the `brought_gear` read-cutover + the cross-layer change + the end-to-end scenario; 6c's legacy retirement needs redump coordination so it's naturally last.*
- **D5 — Trigger #2 (no-padding) check** for any new labels/registry entries: the registry must reuse the §5.5 keyspace exactly — no new gear vocabulary. Confirm before adding any label.

---

## 5. Cache / invalidation (Trigger #3 — already ratified, design §9)
- Owned `athlete_gear` change → `evict_layer1_on_gear_change` (exists).
- `athlete_gear_locale` / `brought_gear` change → `evict_plan_caches_on_gear_locale_change` (exists, slice 5) / `compute_event_windows_hash` folds `brought_gear` (6b).
- No new Layer-0 surface (D2 runtime registry) → no `0A/0C` digest bump.

---

## 6. Gut check
- **Strength:** most of slice 6 is capture-UX over stores + a cascade that already read the unified model — low architectural risk; 6b is the only cross-layer piece (the `brought_gear` read-cutover, mechanically identical to slice 5's standing cutover).
- **Biggest risk:** the `replace_gear_locale`/`brought` replace-all trap (6b) wiping other-kind gear on a partial save — the picker must submit the full set or use a kind-scoped replace. And 6c's legacy retirement needs a redump-fold (don't drop the backfill source early).
- **What to watch:** onboarding parity is easy to forget (the gap exists today); D5 no-padding on the registry.
- **Best argument against scope:** if Andy wants the observable win fastest, **6b alone** (generalize the standing/brought pickers + read-cutover) lights up slice 5 without the owned-surface consolidation (6a) — 6a/6c are polish/cleanup. Sequence 6b-first is viable.

---

**End of plan v1.**
