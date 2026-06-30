# #884 Unified Gear/Craft Model — Slice 6c-2 (onboarding gear-toggle parity via the unified registry) — Closing Handoff v1

**Session:** 2026-06-30 · branch `claude/slice-6c2-onboarding-gear-parity` (fresh off `main`; NOT stacked on 6c-1) · commit `78858ff` · PR opened on Andy's go ("keep going onto 6c-2").
**Kickoff:** `handoffs/V5_Implementation_UnifiedGearCraftModel_884_DesignV3_Slice6c_OnboardingParityLegacyRetire_2026_06_29_Kickoff_Handoff_v1.md` §3. **Plan:** `plans/UnifiedGearCraft_884_Slice6_CaptureUX_Plan_v1.md` §3 6c (row "Onboarding crafts"). **Design:** §10 (UX/IA). **Predecessor:** 6c-1 (`…Slice6c1_BroughtGearCutover_2026_06_30…`, the brought-gear cutover — independent sub-PR).

---

## 1. Session narrative — Piece B of slice 6c (onboarding parity)

The onboarding **Skills step** (`/onboarding/skills`, 2c.2b) captured owned **crafts** via the craft-only catalog (`load_craft_catalog()` → `replace_athlete_crafts`) and had **no** gear-toggle (ski/snow/climb/alpine) capture — the gap the profile gear tab closed in 4b/6a. So an athlete who set up via onboarding could never declare owned skis/climbing kit until they later found the profile Gear tab. 6c-2 closes the parity gap.

Generalized the onboarding capture to the **full unified gear registry**, mirroring the 6a `save_gear` split exactly: chosen gear is classified by the registry and written across the two repo calls — crafts (bike/paddle) → `replace_athlete_crafts` (baseline CSVs + the unified store), gear toggles (ski/snow/climb/alpine) → `replace_owned_gear_for_kinds(…, _GEAR_TOGGLE_KINDS)`. Onboarding and the profile Gear tab now capture **the same kinds with the same own/have-access semantics**.

## 2. File-by-file edits

### 2.1 `routes/onboarding.py` (substantive)
- Imports: dropped `get_athlete_crafts` + `load_craft_catalog` (now unused); added `from athlete_gear_repo import GearSelectionError, get_gear_access_map, load_gear_registry, load_gear_registry_grouped, parse_gear_registry_form, replace_owned_gear_for_kinds, _GEAR_TOGGLE_KINDS`. Kept `CraftSelectionError` + `replace_athlete_crafts`.
- `skills()` GET: renders `gear_registry=load_gear_registry_grouped()` + `gear_access=get_gear_access_map(db, uid)` (was `craft_catalog=load_craft_catalog()` + `athlete_crafts=get_athlete_crafts(...)`).
- `skills_save()` POST: replaced the craft-only `replace_athlete_crafts(bike_types=…, paddle_crafts=…)` block with the `save_gear` split — `parse_gear_registry_form(request.form)` → classify by `load_gear_registry()` → `replace_athlete_crafts(…, access_by_slug=craft_access)` + `replace_owned_gear_for_kinds(toggle_access, _GEAR_TOGGLE_KINDS)`, wrapped in one `try/except (CraftSelectionError, GearSelectionError)` that bounces to `onboarding.skills`. Rule #15 `[onboarding-gear-capture]` log. The existing single `evict_layer1_on_skill_toggle_change` still covers skills + crafts + gear (the three `evict_layer1_on_*_change` helpers are byte-identical — all call `evict_on_layer_change(cache, uid, "layer1")`).

### 2.2 `templates/onboarding/_crafts_form.html` (substantive)
- Rewritten from the craft-only checkbox picker (`craft_catalog.cycling/.paddling`, `name="bike_types"`/`"paddle_crafts"`) to the **unified registry surface** matching profile (`{% for grp in gear_registry %}` → own/have-access `<select name="gear__{{ item.gear_id }}">`, `gear_access` drives the selected option). The `skills.html` `{% include %}` point is unchanged, so no edit to `skills.html`. (This partial is no longer used by profile — profile's gear tab renders the surface inline in `edit.html` — so the rewrite touches only onboarding.)

## 3. Notes

- **No `KeyError` / no validation regression.** `parse_gear_registry_form` only keeps gear_ids present in the registry, so `chosen ⊆ registry` and the `by_id[g]` classification can't `KeyError`; a malformed POST with an off-registry id is silently dropped (the old craft path raised `CraftSelectionError` and bounced — the unified surface validates at parse time instead). Documented in the new `test_post_unknown_gear_field_ignored`.
- **Cache:** onboarding gear writes `athlete_gear` → the Layer-1 eviction already fired by the step covers it (intended). No new Layer-0 surface → no digest bump.
- **No migration / no Neon apply owed.**

## 4. Manual §5.0 verification step (owed to Andy)

**Onboarding → Skills step** (`/onboarding/skills`): the gear card now lists **all** kinds (bikes, paddle craft, skis & rollerskis, snowshoes, climbing, mountaineering), each with an **Own / Have access** dropdown (was bike+paddle checkboxes only). Set e.g. **Climbing gear → Own**, Save & continue → it persists to `athlete_gear` (visible later on the profile Gear tab, identical surface).

## 5. Next session pointers

### 5.1 Remaining slice 6c (separate branches off `main`, do NOT stack)
- **The `brought_craft` column DROP follow-up** (6c-1's tail) — after 6c-1 deploys: remove the create at `init_db.py:2611` + backfill at `:3113`, add `ALTER TABLE athlete_event_windows DROP COLUMN IF EXISTS brought_craft` at the `_PG_MIGRATIONS` tail.
- **6c-3 — legacy retirement** (kickoff §4, riskiest): retire app-dead `athlete_craft_locale_repo.py` + tests + the `athlete_craft_locale` table. **Do NOT drop the `discipline_baseline_*` craft CSVs** (live Layer-1 substitution source). Coordinate layer0 drops with a redump-fold; may warrant its own Layer-0 housekeeping slice.
- The deferred per-segment **2C re-resolve** (slice-5 §2) also lives in slice 6 — architectural, its own slice.

### 5.2 Merge-ordering note (rolling-doc conflict)
6c-2 branched off `main` *before* 6c-1 merged. Both edit `CURRENT_STATE.md`'s single "Last shipped" pointer + `CARRY_FORWARD.md`'s #884 item, so whichever merges second needs a one-spot conflict resolution (keep the newest as last-shipped, demote the other to a `### Predecessor` section). Resolved for 6c-2 by merging `main` in once 6c-1 lands.

### 5.3 Operating notes (Rule #13)
1. `CLAUDE.md`. 2. `CURRENT_STATE.md` (last-shipped 6c-2). 3. `CARRY_FORWARD.md` (#884 rolling item). 4. This handoff + the 6c kickoff + the 6c-1 closing + the slice-6 plan + design §10. 5. `./scripts/verify-handoff.sh`.

## 6. Decisions pinned

| # | Decision | Picked by | Rationale |
|---|---|---|---|
| 1 | Generalize onboarding to the **full unified registry** (own/have-access, all kinds) rather than bolt craft-checkboxes + toggle-checkboxes side by side | Claude (per kickoff "via the unified registry" + "mirror the 6a save_gear split") | True parity with the profile Gear tab; one capture surface; `_crafts_form.html` is onboarding-only now, so the rewrite touches no other surface |
| 2 | Keep the single `evict_layer1_on_skill_toggle_change` (don't add a second gear eviction) | Claude | The three `evict_layer1_on_*_change` helpers are identical (`evict_on_layer_change(cache, uid, "layer1")`); one Layer-1 eviction covers skills + crafts + gear |

## 7. Session-end verification (Rule #10)

| Claim | File | Check |
|---|---|---|
| Onboarding GET renders the unified registry | `routes/onboarding.py` | `skills()` passes `gear_registry=load_gear_registry_grouped()` + `gear_access=get_gear_access_map(db, uid)`; no `load_craft_catalog`/`get_athlete_crafts` import |
| Onboarding POST splits by kind | `routes/onboarding.py` | `skills_save()` calls `parse_gear_registry_form` → `replace_athlete_crafts(access_by_slug=…)` + `replace_owned_gear_for_kinds(…, _GEAR_TOGGLE_KINDS)`; `[onboarding-gear-capture]` log |
| Template renders own/have-access for all kinds | `templates/onboarding/_crafts_form.html` | `{% for grp in gear_registry %}` + `name="gear__{{ item.gear_id }}"` + `gear_access.get(...)`; no `craft_catalog`/`bike_types`/`paddle_crafts` |
| Toggle-kind capture works | `tests/test_onboarding_skills.py` | `test_post_captures_gear_toggle_kinds` → `(42, 'climbing_gear', 'climb', 'own')` inserted |
| Unknown id ignored (no bounce) | `tests/test_onboarding_skills.py` | `test_post_unknown_gear_field_ignored` → no write, still advances |
| Suite green | (local) | `tests/ etl/tests/` **4040 passed / 30 skipped**; ruff clean on `routes/onboarding.py` |
| No Neon/layer0 apply owed | — | public-schema writes; no migration |

## 8. Files shipped this session (6c-2)

**Substantive (2, under ceiling):** `routes/onboarding.py`, `templates/onboarding/_crafts_form.html`.
**Tests (not counted):** `tests/test_onboarding_skills.py`.
**Bookkeeping (outside the ceiling):** `CURRENT_STATE.md`, `CARRY_FORWARD.md`, this handoff, GitHub issue #884 comment.

---

**End of handoff.**
