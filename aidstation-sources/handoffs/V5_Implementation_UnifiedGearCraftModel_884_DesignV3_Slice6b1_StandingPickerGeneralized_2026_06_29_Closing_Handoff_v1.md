# #884 Unified Gear/Craft Model — Slice 6b-1 (standing gear↔locale picker generalized to the unified registry) — Closing Handoff v1

**Session:** 2026-06-29 · branch `claude/slice-6b-cutover-kickoff-od105s` · PR not yet opened (push + bookkeep + wait for Andy's go).
**Kickoff:** `handoffs/V5_Implementation_UnifiedGearCraftModel_884_DesignV3_Slice6b_BringItBroughtCutover_2026_06_29_Kickoff_Handoff_v1.md` (the full-6b build recipe). **Plan:** `plans/UnifiedGearCraft_884_Slice6_CaptureUX_Plan_v1.md` §3 6b. **Design:** `designs/Unified_GearCraft_Model_And_Feasibility_884_Design_v3.md` §10 (UX/IA), §17 (away-gear scenario). **Predecessor:** `handoffs/V5_Implementation_UnifiedGearCraftModel_884_DesignV3_Slice6a_UnifiedGearRegistry_2026_06_29_Closing_Handoff_v1.md` (6a — registry + "Your gear" surface; merged via PR #1027 `979b00f`).

---

## 1. Session-start verification (Rule #9)

`./scripts/verify-handoff.sh` clean against the 6a closing handoff (all referenced files exist; no backlog-pointer drift). Spot-checked the kickoff's on-disk anchors before starting:
- 6a merged to main via PR #1027 (`979b00f`); this branch sits on that merge — **fresh off main with 6a in it**, not stacked on the 6a branch (kickoff §3). ✅
- `athlete_gear_repo.load_gear_registry_grouped` present (6a), emits `{group_kind, label, rows}`. ✅
- `routes/locales.py` standing picker fed `load_craft_catalog()` at the `_edit_locale` GET context (`:1088`); writes already on `replace_gear_locale`/`load_gear_locales` (slice 5). ✅
- **Away overlay consumes all kinds:** `layer4/orchestrator.py:951` unions brought∪standing gear and filters to `_CRAFT_ALIAS_GROUP_KINDS = {bike, paddle, ski, snow, climb, alpine}` (generalized in slice 4b) — so generalizing the standing picker is **genuinely observable**, not cosmetic. ✅
- Full suite green at HEAD before edits. ✅

## 2. Session narrative — why this is a split, and what shipped

The kickoff §4 flags that full slice 6b is **~8 substantive files** (two picker generalizations + the repo + the hash + ≥1 layer4 read + the brought read-cutover) — ~2× the 5-file ceiling — and explicitly says **"split the standing-picker half from the brought-cutover half."** This session ships the **standing-picker half (6b-1)**: 2 substantive files, self-contained, observable on its own.

**What it does.** Generalizes the per-locale "gear you keep here" picker on the locale-edit page from the **craft-only** catalog (`athlete_crafts_repo.load_craft_catalog` — 9 bike/paddle slugs) to the **full unified gear registry** (`athlete_gear_repo.load_gear_registry_grouped` — all 6 kinds: bike/paddle/ski/snow/climb/alpine, swim excluded as in 6a). After 6b-1 an athlete can **station** ski/snow/climbing/mountaineering gear at a locale, and because the slice-5 away overlay already unions standing gear at the destination cluster and filters to `_CRAFT_ALIAS_GROUP_KINDS`, that gear now resolves EXACT/PROXY when the locale is the away destination — design §17's "I keep my climbing rack at the Boulder cabin" → climbing feasible at Boulder. **This lights up the standing half of slice 5's plumbing** (the brought half is 6b-2).

**Replace-all trap (kickoff §2.1 / slice-5 §6.1) — avoided by construction, no repo change.** `athlete_gear_repo.replace_gear_locale` is replace-all-per-locale (DELETE all gear at the locale, INSERT the submitted set). The danger was: if the generalized picker submitted only *some* kinds, the DELETE would wipe the stationed other-kind gear. But the locale-edit standing picker is rendered inside the **single `_edit_locale` form** (folded there by #953), so one submit posts the **full** owned-here set across **all** kinds via the `craft_slug` field → `replace_gear_locale` writes the whole set → replace-all is exactly correct. This is the kickoff's "submit the full owned-at-locale set" option; the alternative kind-scoped repo change is unnecessary here because there is no partial-save path. (The standalone `save_locale_crafts` route — a still-valid direct-POST endpoint the template no longer targets — is unchanged; it also full-replaces from whatever it's given.)

**Field name kept `craft_slug`.** The POST field stays `craft_slug` (now carrying gear_ids of any kind). `replace_gear_locale` validates every id against `GEAR_REGISTRY` (all kinds), so ski/climb ids pass. Renaming would touch both route read-sites + the standalone route + several tests for zero behavior gain — kept it surgical.

## 3. File-by-file edits

### 3.1 `routes/locales.py` (modified — substantive)
- Dropped `from athlete_crafts_repo import load_craft_catalog` (now orphaned — it was the only use in this file; confirmed by grep).
- Added `load_gear_registry_grouped` to the existing `from athlete_gear_repo import (...)` block.
- `_edit_locale` GET render context: `craft_catalog=load_craft_catalog()` → `gear_registry=load_gear_registry_grouped()`. Updated the adjacent comment to record the 6b generalization + the away-overlay consumer. `crafts_here=load_gear_locales(db, uid).get(locale, [])` unchanged (already all-kind).

### 3.2 `templates/locales/form.html` (modified — substantive)
- The "gear kept here" fieldset (`{% if gear_registry %}`): legend "Craft you keep here" → "Gear you keep here"; the loop iterates the registry-grouped **list** (`{% for grp in gear_registry %}` → `grp.label` heading from `_GROUP_KIND_LABELS`, `grp.rows` of `{gear_id, label}`) instead of the craft-catalog **dict** (`craft_catalog.items()` / `group | capitalize`). Checkbox stays `name="craft_slug"`, `value="{{ c.gear_id }}"`, `id="kept_{{ c.gear_id }}"`, checked when `c.gear_id in crafts_here`. Hint copy generalized ("bike at the cabin, skis at the mountain condo, a climbing rack at the desert house"). CSP-clean (no inline styles/handlers).

## 4. Code / tests

- `tests/test_redesign_locales_form_render.py`: `_form_ctx` now supplies `gear_registry=[…]` in the registry-grouped shape (bike + paddle + a **ski** group) instead of `craft_catalog={…}`; `test_form_renders_craft_kept_here` → `test_form_renders_gear_kept_here` asserts the new "Gear you keep here" copy, that **ski rows render** (`Skis &amp; rollerskis` — note the `&amp;` HTML-escape — + `Classic XC skis` + `id="kept_classic_xc_ski"`), `name="craft_slug"` retained, `id="kept_kayak"` checked-state, and the `gear_registry=None` guard hides the fieldset.
- `tests/test_locales.py::TestEditLocaleSavesCraftInline`: new `test_post_replaces_full_cross_kind_set` — a mixed craft+ski POST (`['classic_xc_ski','mountain_bike']`) forwards the **full cross-kind set** to `replace_gear_locale` (the route-level replace-all-trap guard) and evicts on change.
- **VERIFIED:** full `tests/ etl/tests/` suite **3978 passed / 30 skipped** (only the 3 pre-existing #217 Layer3B `evidence_basis` warnings). `ruff check routes/locales.py` clean. The `pytest`/`sys` F401s ruff flags in the two test files are HEAD-pre-existing (not added here) — left untouched per the surgical rule.

## 5. Manual §5.0 verification steps (owed to Andy)

On the deployed app, **Locations → edit a locale**:
1. The "Gear you keep here" card now lists **all** kinds grouped — Bikes / Paddle craft / Skis & rollerskis / Snow / Climbing / Mountaineering–ski-mo — not just bikes + paddle craft.
2. Check a ski (e.g. Classic XC skis) at a locale, Save → reopen the locale → the ski stays checked (round-trips through `athlete_gear_locale`).
3. With a craft already kept at that locale, add a ski and Save → the craft is **still** kept (replace-all writes the full set; no wipe).
4. End-to-end (the slice-5 light-up): set that locale as an **away** destination on an event window overlapping a plan, regenerate/refresh → the away segment resolves the stationed ski/climbing gear (design §17). *(This exercises the brought∪standing union; the brought half itself is still 6b-2.)*

## 6. Next session pointers

### 6.1 Architect-recommended next forward move — slice 6b-2 (the brought-cutover half)
The remaining half of 6b, per the kickoff §2.2/§2.3 (mechanically-spec'd there):
- **Brought picker → unified registry.** `routes/profile.py:915` passes `craft_catalog=load_craft_catalog()` to the event-windows template; the add form posts `brought_craft` (`:916`, `:1002`). Generalize the catalog to the registry; `templates/profile/event_windows.html` loops `craft_catalog.items()` (`:130`) and posts `name="brought_craft"` (`:134`). Decide the field name once (keep `brought_craft` as the form field and map, or rename to `brought_gear`).
- **`brought_craft` → `brought_gear` read-cutover (cross-layer — byte-identical today; column backfilled verbatim at `init_db.py:3088/3113`).** `athlete_event_windows_repo.py`: `EventWindow.brought_craft` (`:75`), the SELECT (`:90`/`:106`), `add_event_window(brought_craft=…)` (`:202`/`:245`/`:268`), `_validate_crafts`, the enum-order rule (`:323`). `layer4/orchestrator.py`: `brought_craft=tuple(w.brought_craft)` (`:902`) + away path `brought = set(away_ov.brought_craft)` (`:947`). `layer4/session_feasibility.py`: `EventWindowOverride.brought_craft` (`:850`). `layer4/hashing.py`: fold `brought_gear` instead of `brought_craft` (`:210`/`:230`/`:255`). `layer1/builder.py:910` reads `w.brought_craft` for a display string. Because the column is byte-identical, the cutover causes **no cache churn**; the new capability (capturing toggle kinds as brought) is what moves hashes going forward.
- **Test:** design §17 — bring climbing gear to an away window → D-012 feasible in that segment only (home segment unchanged).
- **Scope warning:** that's **~6 substantive files** (route + template + repo + 3 layer4 + layer1 display) — over the ceiling. **Split it further**: e.g. PR-A the byte-identical read-cutover (repo + layer4 + hashing + layer1, no UI), PR-B the brought-picker generalization (route + template). Decide at kickoff.

### 6.2 Then slice 6c
Onboarding gear-toggle parity via the unified registry + retire the app-dead `athlete_craft_locale_repo` + legacy craft columns via a redump-fold (slice-4.3 pattern; needs redump coordination → naturally last). Slice 6 also still owns the deferred per-segment **2C re-resolve** (slice-5 §2).

### 6.3 Operating notes for next session (Rule #13)
1. `CLAUDE.md` — stable rules. 2. `CURRENT_STATE.md` — last-shipped (this 6b-1) + #884 predecessor chain. 3. `CARRY_FORWARD.md` — the #884 rolling item + ops gotchas. 4. This handoff + the 6b kickoff (its §2.2/§2.3 brought recipe) + the slice-6 plan + design v3 §10/§17. 5. `./scripts/verify-handoff.sh`.

## 7. Decisions pinned

| # | Decision | Picked by | Rationale |
|---|---|---|---|
| 1 | Ship the standing-picker half (6b-1) alone; defer the brought-cutover half (6b-2) | Claude (kickoff §4 sanction) | Full 6b ~8 files ≫ ceiling; standing half is 2 files, self-contained, observable on its own (lights up the standing half of slice 5) |
| 2 | Avoid the replace-all trap by full-set submit, not a kind-scoped repo change | Claude | `_edit_locale` is one form → it already posts the full owned-here set across all kinds; `replace_gear_locale` replace-all is correct; a kind-scoped repo variant would be unused complexity (Simplicity-first) |
| 3 | Keep the POST field `craft_slug` (carrying any-kind gear_ids) | Claude | Renaming touches both route reads + the standalone route + tests for no behavior gain; `replace_gear_locale` validates against the full `GEAR_REGISTRY` already (surgical) |

## 8. Session-end verification (Rule #10)

| Claim | File | Check |
|---|---|---|
| Standing picker fed by the unified registry | `routes/locales.py` | grep `gear_registry=load_gear_registry_grouped()` in `_edit_locale`; no `load_craft_catalog` import remains (grep returns nothing) |
| Template renders the registry grouped, all kinds | `templates/locales/form.html` | `{% if gear_registry %}` + `{% for grp in gear_registry %}` + `grp.rows` + `value="{{ c.gear_id }}"`; legend "Gear you keep here"; no `craft_catalog` ref |
| Picker offers ski/snow/climb/alpine (observable) | `tests/test_redesign_locales_form_render.py` | `test_form_renders_gear_kept_here` asserts `Skis &amp; rollerskis` + `Classic XC skis` + `id="kept_classic_xc_ski"` |
| Replace-all-trap guard (full cross-kind set) | `tests/test_locales.py` | `test_post_replaces_full_cross_kind_set` asserts `replace_gear_locale` gets `['classic_xc_ski','mountain_bike']` |
| Away overlay consumes the stationed kinds | `layer4/orchestrator.py` | `:951` filter `GEAR_REGISTRY.get(g) in _CRAFT_ALIAS_GROUP_KINDS`; `_CRAFT_ALIAS_GROUP_KINDS = {bike,paddle,ski,snow,climb,alpine}` (`:228`) — unchanged, already all-kind |
| Suite green | (local) | `tests/ etl/tests/` 3978 passed / 30 skipped |
| No Neon/layer0 apply owed | — | public-schema reads only; `athlete_gear_locale` live since the slice-3 backfill; no migration this slice |

## 9. Files shipped this session

**Substantive (2, under ceiling):** `routes/locales.py`, `templates/locales/form.html`.
**Tests (not counted):** `tests/test_redesign_locales_form_render.py`, `tests/test_locales.py`.
**Bookkeeping (outside the ceiling):** `CURRENT_STATE.md`, `CARRY_FORWARD.md`, this handoff, GitHub issue #884 comment.

---

**End of handoff.**
