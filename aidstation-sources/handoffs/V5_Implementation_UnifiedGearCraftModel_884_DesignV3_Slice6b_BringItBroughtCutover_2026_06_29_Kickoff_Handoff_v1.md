# #884 Unified Gear/Craft Model — Slice 6b ("bring it" + standing/brought generalized + `brought_gear` read-cutover) — Kickoff Handoff v1

**Purpose:** the build recipe for slice 6b, the sub-PR that **makes slice 5's away plumbing observable**. Start on a fresh branch off `main` once 6a merges (don't stack on the 6a branch).
**Predecessor:** `handoffs/V5_Implementation_UnifiedGearCraftModel_884_DesignV3_Slice6a_UnifiedGearRegistry_2026_06_29_Closing_Handoff_v1.md` (6a — unified registry + "Your gear" surface; commit `1b6f050`).
**Plan:** `plans/UnifiedGearCraft_884_Slice6_CaptureUX_Plan_v1.md` §3 (6b). **Design:** `Unified_GearCraft_Model_And_Feasibility_884_Design_v3.md` §10, §17 (climbing-at-away scenario).

---

## 1. Goal

Two halves, one slice:

1. **"Bring it" — generalize the standing + brought pickers to the full unified registry** (all gear kinds, not craft-only), so ski/snow/climb/alpine gear can be stationed at a locale or brought to an event window. The registry built in 6a (`athlete_gear_repo.load_gear_registry` / `load_gear_registry_grouped`) is the picker source.
2. **Cut the brought READ from `brought_craft` → `brought_gear`.** The `brought_gear` column already exists and is **backfilled verbatim** from `brought_craft` (`init_db.py:3088/3113` — same comma-string slug format, byte-identical today, currently unread by the app). 6b makes the app write + read `brought_gear`.

After 6b: "I'm bringing my skis to the race" / "I keep my climbing rack at the Boulder cabin" resolves EXACT/PROXY in that away segment only (the slice-4b feasibility cascade + slice-5 away overlay already consume it via `owned_crafts`).

## 2. File-by-file build recipe (each anchor verified on-disk 2026-06-29)

### 2.1 `routes/locales.py` — standing picker → unified registry
- The standing gear↔locale page currently feeds the picker `load_craft_catalog()` (craft-only). Swap to the unified registry (`load_gear_registry` / `load_gear_registry_grouped`) so all kinds are stationable.
- **⚠ replace-all trap (slice-5 §6.1 — the single biggest risk in 6b).** `athlete_gear_repo.replace_gear_locale` replaces **all** gear at a locale. Today that's safe (only craft gear can be there). Once the picker offers ski/climb/swim, a craft-only (or partial) save would **wipe** the other-kind gear stationed there. Fix: either submit the **full owned-at-locale set** on every save, or switch `replace_gear_locale` to a **kind-scoped replace** (mirror `replace_owned_gear_for_kinds`). Pick one and test it explicitly.
- The write path already uses `replace_gear_locale` / `load_gear_locales` / `evict_plan_caches_on_gear_locale_change` (slice 5 cut it over) — only the **catalog** changes.

### 2.2 Brought picker → unified registry (`routes/profile.py` + `templates/profile/event_windows.html`)
- `routes/profile.py:915` passes `craft_catalog=load_craft_catalog()` to the event-windows template; the add form posts `brought_craft` (`:916`, `:1002`). Generalize the catalog to the unified registry and rename the brought field to `brought_gear` (or keep the form field name and map it — decide once).

### 2.3 `brought_gear` read-cutover (cross-layer — Trigger #3; mechanically identical to slice 5's standing cutover)
- **`athlete_event_windows_repo.py`** — `EventWindow.brought_craft` (`:75`), the SELECT (`:90`/`:106`), `add_event_window(brought_craft=…)` (`:202`/`:245`/`:268`), `_validate_crafts`. Dual-write `brought_gear` (or migrate the field). Keep enum-order for a stable hash (`:323`).
- **`layer4/orchestrator.py`** — `brought_craft=tuple(w.brought_craft)` (`:895`); away path `brought = set(away_ov.brought_craft)` (`:940`) → read `brought_gear`.
- **`layer4/session_feasibility.py`** — `EventWindowOverride.brought_craft` (`:850`) → `brought_gear`.
- **`layer4/hashing.py`** — `compute_event_windows_hash` folds `brought_craft` (`:210`/`:230`/`:255`). Fold `brought_gear` instead. **Byte-identical today** (column backfilled verbatim) → no cache churn on the cutover itself; the new capability (capturing toggle kinds as brought) is what changes hashes going forward.

### 2.4 Tests — the end-to-end scenario
- Design §17: athlete **brings climbing gear to an away window → D-012 feasible in that segment only** (home segment unchanged). Assert the away overlay resolves the brought toggle-kind gear. Plus: the standing replace-all-trap guard (a ski save at a locale doesn't wipe stationed climbing gear).

## 3. Cache / invalidation
- Brought is a declared window field → folded into `compute_event_windows_hash` (not eviction-on-write). The cutover is byte-identical; no one-time invalidation needed.
- Standing gear↔locale → `evict_plan_caches_on_gear_locale_change` (exists, slice 5).
- No new Layer-0 surface → no `0A/0C` digest bump.

## 4. Gut check
- **Biggest risk:** the `replace_gear_locale` replace-all trap (§2.1). Get the full-set-submit or kind-scoped-replace right or a partial save silently wipes stationed gear.
- **Scope:** the cross-layer cutover (§2.3) is mechanically the slice-5 standing-cutover pattern — low novelty, but touches 4 layer4 files; watch the 5-file ceiling (the two picker generalizations + the repo + the hash + at least one layer4 read may push past 5 — if so, split the standing-picker half from the brought-cutover half).
- **Don't forget:** 6b is also a natural place to keep the deferred per-segment 2C re-resolve in view (slice-5 §2), though that's a separate, larger piece.

## 5. Operating notes (Rule #13)
1. `CLAUDE.md`. 2. `CURRENT_STATE.md` (6a last-shipped). 3. `CARRY_FORWARD.md` (#884 rolling item). 4. The 6a closing handoff + this kickoff + the slice-6 plan + design §10/§17. 5. `./scripts/verify-handoff.sh`.

---

**End of kickoff handoff.**
