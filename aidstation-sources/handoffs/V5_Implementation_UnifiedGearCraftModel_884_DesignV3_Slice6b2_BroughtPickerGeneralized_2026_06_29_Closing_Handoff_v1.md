# #884 Unified Gear/Craft Model — Slice 6b-2 (brought gear picker generalized to the unified registry) — Closing Handoff v1

**Session:** 2026-06-29 · branch `claude/slice-6b-cutover-kickoff-od105s` (same branch as 6b-1 — two commits, one PR) · PR not yet opened (push + bookkeep + wait for Andy's go).
**Kickoff:** `handoffs/V5_Implementation_UnifiedGearCraftModel_884_DesignV3_Slice6b_BringItBroughtCutover_2026_06_29_Kickoff_Handoff_v1.md`. **Plan:** `plans/UnifiedGearCraft_884_Slice6_CaptureUX_Plan_v1.md` §3 6b. **Design:** §10 (UX/IA), §17 (brought-gear-at-away scenario). **Predecessor:** `handoffs/V5_Implementation_UnifiedGearCraftModel_884_DesignV3_Slice6b1_StandingPickerGeneralized_2026_06_29_Closing_Handoff_v1.md` (6b-1 — standing picker generalized).

---

## 1. Session narrative — the symmetric half + a scope deviation flagged

6b-1 generalized the **standing** (gear↔locale) picker. 6b-2 does the symmetric move for the **brought** (event-window) picker: the per-window "gear brought" picker is cut from the craft-only catalog (`load_craft_catalog`) to the full unified gear registry (`load_gear_registry_grouped`, all 6 kinds), so an athlete can bring skis/climbing gear to an away window. The slice-5 away overlay already unions brought∪standing gear and filters to `_CRAFT_ALIAS_GROUP_KINDS` (= {bike,paddle,ski,snow,climb,alpine}), so brought toggle-kind gear resolves feasible **in that away segment only** — design §17's "brings climbing gear to an away window → climbing feasible there, home unchanged". **With 6b-1 + 6b-2, both halves of slice 5's away plumbing (station + bring) are now observable.**

**Deliberate deviation from the kickoff (flagged for Andy).** The kickoff frames 6b's second goal as cutting the brought READ from `brought_craft` → `brought_gear` (the pre-created, verbatim-backfilled column). I **kept storage on `brought_craft`** this slice and **deferred the `brought_craft`→`brought_gear` column/field rename to 6c**. Why:
- **Ceiling.** Renaming the `EventWindow.brought_craft` *attribute* ripples to every reader — `layer4/orchestrator.py`, `layer4/session_feasibility.py` (`EventWindowOverride`), `layer4/hashing.py`, `layer1/builder.py`, and two display templates (`event_windows.html:54`, `plan_create/new_form.html:66`) — ~7 substantive files for a **behavior-neutral** rename. That busts the 5-file ceiling for zero product value.
- **Cleaner factoring.** Plan §3 **6c already owns retiring the `brought_craft` column**. Doing the rename + read-cutover + column drop **atomically in 6c** (one redump-fold touch) is cleaner than cut-the-read-in-6b + drop-the-column-in-6c (two touches of the same column).
- **The observable win doesn't need it.** `brought_craft` already holds gear_ids (craft slugs ARE gear_ids); the away overlay treats them as gear_ids and `compute_event_windows_hash` folds the field by `getattr` + sort — so brought ski/climb flows through and re-hashes correctly **without** any column/layer4 change. This is the exact symmetry with 6b-1, where the standing `craft_slug` field now carries all-kind gear_ids un-renamed.

Net: 6b-2 is **3 substantive files**, observable, within ceiling, zero layer4 touch. The `brought_gear` column stays dormant (harmless — backfilled, unread) until 6c folds it. **If Andy wants the brought_gear cutover landed inside 6b instead, it's a clean follow-up — say so and I'll do the ~7-file rename as its own PR.**

## 2. File-by-file edits

### 2.1 `athlete_event_windows_repo.py` (modified — substantive)
- `_validate_crafts` generalized from the craft-only `_CRAFT_SLUGS` (bike/paddle) to the full unified registry: validates against + emits in the order of `load_gear_registry()` (the same catalog the picker offers — swim excluded, `_GEAR_IDS` order), so picker/validator/stored-CSV share one source. **Lazy import** of `load_gear_registry` (function-level) avoids the layer4 package-init cycle (this repo is imported at layer4 init time — same reason `evict_plan_caches_on_event_windows_change` lazily imports `layer4.cache`).
- Removed the now-orphaned `_CRAFT_SLUGS` constant + `from athlete import BIKE_TYPES, PADDLE_CRAFT_TYPES` import.
- `EventWindow.brought_craft` field comment + the `add_event_window` brought-validation comment updated to "gear"; **attribute name kept `brought_craft`** (rename rides 6c).
- Byte-identical for existing craft-only data: registry order == BIKE+PADDLE order for the craft subset (registry is bikes→paddles→toggles), so `test_away_stores_brought_craft_in_enum_order` ("road_bike,packraft") still holds.

### 2.2 `routes/profile.py` (modified — substantive)
- `event_windows()` render context: `craft_catalog=load_craft_catalog()` → `gear_registry=load_gear_registry_grouped()` (already imported for 6a). Dropped the now-unused `load_craft_catalog` import (its only use here). `load_craft_catalog` stays defined in `athlete_crafts_repo` — still consumed by onboarding (`routes/onboarding.py` + `templates/onboarding/_crafts_form.html`), a 6c parity target.

### 2.3 `templates/profile/event_windows.html` (modified — substantive)
- The "Gear brought" fieldset iterates the registry-grouped list (`{% for grp in gear_registry %}{% for c in grp.rows %}`) instead of the craft-catalog dict; `value`/`id` keyed on `c.gear_id`. **Form field stays `name="brought_craft"`** (the route + draft-stash + `add_event_window` kwarg are unchanged — values are gear_ids of any kind). Legend "Craft brought" → "Gear brought"; hint copy generalized. Display read `w.brought_craft` (`:54`) unchanged (attribute kept). CSP-clean.

## 3. Code / tests

- `tests/test_layer4_event_windows.py`: `test_away_stores_brought_toggle_gear_in_registry_order` (mixed `['climbing_gear','mountain_bike']` accepted, emitted `"mountain_bike,climbing_gear"` — bikes precede toggle kinds) + `test_brought_toggle_gear_passed_as_owned_crafts` (the design §17 overlay scenario — brought `climbing_gear` → away segment `owned_crafts == ['climbing_gear']`).
- `tests/test_redesign_locales_form_render.py`: the three `profile/event_windows.html` render tests repointed from `craft_catalog={…dict}` → `gear_registry=[…grouped]`; the capture test now asserts a climbing row renders (`Climbing gear` + `value="climbing_gear"`) alongside bike/paddle.
- **VERIFIED:** full `tests/ etl/tests/` suite **3980 passed / 30 skipped** (only the 3 pre-existing #217 Layer3B warnings). `ruff check athlete_event_windows_repo.py` clean; `routes/profile.py` — the 3 F401s (bcrypt / PROFILE_FIELDS / DEFAULT_UNIT_PREFERENCE) are HEAD-pre-existing (named in the 6a handoff), my import edit added none.

## 4. Manual §5.0 verification steps (owed to Andy)

**Profile → Event windows**, add an **away** window:
1. The "Gear brought" picker now lists **all** kinds (bikes, paddle craft, skis, snow, climbing, mountaineering), not just bikes + paddle craft.
2. Check **Climbing gear**, set an away destination + dates, Save → the window persists with the climbing gear (shows "· with climbing gear" in the list).
3. End-to-end: with that away window overlapping a plan, generate/refresh → the away segment resolves the climbing discipline as feasible **only for those dates** (home segment unchanged) — design §17.

## 5. Next session pointers

### 5.1 Slice 6c (now carries the deferred brought rename)
- **`brought_craft`→`brought_gear` rename + read-cutover + drop** (deferred from 6b-2): rename the `EventWindow.brought_craft` attribute → `brought_gear` and propagate (`layer4/orchestrator.py:902/947`, `layer4/session_feasibility.py:850`, `layer4/hashing.py:230/255`, `layer1/builder.py:910`, `templates/profile/event_windows.html:54`, `templates/plan_create/new_form.html:66`); cut the repo SELECT/INSERT onto the `brought_gear` column; **drop the `brought_craft` column via a redump-fold** (re-backfill `brought_gear` first). Byte-identical (column backfilled verbatim).
- Onboarding gear-toggle parity via the unified registry (the gap `load_craft_catalog` still serves at `routes/onboarding.py`).
- Retire app-dead `athlete_craft_locale_repo` + legacy craft columns (slice-4.3 redump-fold pattern).
- The deferred per-segment **2C re-resolve** (slice-5 §2) also lives in slice 6.

### 5.2 Operating notes (Rule #13)
1. `CLAUDE.md`. 2. `CURRENT_STATE.md` (last-shipped 6b-2). 3. `CARRY_FORWARD.md` (#884 rolling item). 4. This handoff + the 6b kickoff + the 6b-1 closing + the slice-6 plan + design §10/§17. 5. `./scripts/verify-handoff.sh`.

## 6. Decisions pinned

| # | Decision | Picked by | Rationale |
|---|---|---|---|
| 1 | Generalize the brought picker to all kinds on the existing `brought_craft` storage; **defer the `brought_craft`→`brought_gear` rename/cutover/drop to 6c** | Claude (flagged for Andy) | Field rename is behavior-neutral + ripples to ~7 files (ceiling); 6c already owns the column drop, so rename+cutover+drop atomically there is cleaner; the observable win needs neither (brought already holds gear_ids; away overlay + hash treat them as such) |
| 2 | Keep the form field `brought_craft` (values are any-kind gear_ids) | Claude | Renaming touches the draft stash + route + `add_event_window` kwarg for no behavior gain; symmetric with 6b-1's `craft_slug` (surgical) |
| 3 | Validate + order brought via `load_gear_registry()` (lazy import) | Claude | Single source shared with the picker (swim excluded, `_GEAR_IDS` order); lazy import dodges the layer4 init cycle |

## 7. Session-end verification (Rule #10)

| Claim | File | Check |
|---|---|---|
| Brought validation generalized to the registry | `athlete_event_windows_repo.py` | `_validate_crafts` imports `load_gear_registry`, validates against `entry["gear_id"]` set; no `_CRAFT_SLUGS` / `from athlete import` remains |
| Brought picker fed by the registry | `routes/profile.py` | `event_windows()` passes `gear_registry=load_gear_registry_grouped()`; no `load_craft_catalog` import |
| Template renders the registry, all kinds, field kept | `templates/profile/event_windows.html` | `{% for grp in gear_registry %}` + `grp.rows` + `value="{{ c.gear_id }}"`; `name="brought_craft"` retained; legend "Gear brought" |
| Brought toggle gear accepted + ordered | `tests/test_layer4_event_windows.py` | `test_away_stores_brought_toggle_gear_in_registry_order` → `"mountain_bike,climbing_gear"` |
| §17 brought-climb-at-away resolves | `tests/test_layer4_event_windows.py` | `test_brought_toggle_gear_passed_as_owned_crafts` → `owned_crafts == ['climbing_gear']` |
| Suite green | (local) | `tests/ etl/tests/` 3980 passed / 30 skipped |
| No Neon/layer0 apply owed | — | public-schema; no migration; `brought_gear` cutover deferred to 6c |

## 8. Files shipped this session (6b-2)

**Substantive (3, under ceiling):** `athlete_event_windows_repo.py`, `routes/profile.py`, `templates/profile/event_windows.html`.
**Tests (not counted):** `tests/test_layer4_event_windows.py`, `tests/test_redesign_locales_form_render.py`.
**Bookkeeping (outside the ceiling):** `CURRENT_STATE.md`, `CARRY_FORWARD.md`, this handoff, GitHub issue #884 comment.

---

**End of handoff.**
