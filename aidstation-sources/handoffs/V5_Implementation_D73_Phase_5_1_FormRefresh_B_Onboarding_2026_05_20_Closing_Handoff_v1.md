# D-73 Phase 5.1 Form-Refresh B — §H.2 Onboarding Step-3c Terrain Capture — Closing Handoff

**Session:** D-73 Phase 5.1 form-refresh B — closes Layer2B_Spec.md §12 Open Item 2B-3 fully by mirroring form-refresh A's terrain editor on the onboarding side. Second slice of the §H.2 / §J / §I.1 form-refresh PR per predecessor handoff §6.1 architect-recommended next move.
**Date:** 2026-05-20
**Predecessor handoff:** `V5_Implementation_D73_Phase_5_1_FormRefresh_A_RaceTerrain_2026_05_20_Closing_Handoff_v1.md`
**Branch:** `claude/form-refresh-race-terrain-B63VT`
**Status:** 5 substantive files (at ceiling); container-runnable subset 408 → 443 layer4+race_events+onboarding tests (+35: +16 new + 19 pre-existing onboarding race_events tests that were not counted in the predecessor's 408 layer4+race_events scope); production count 1094 → 1110 (+16 new); 4 SDK smoke tests still skip cleanly. **Phase 5.1 form-refresh B complete; Open Item 2B-3 fully resolved.**

---

## 1. Session-start verification (Rule #9)

Anchor-check the predecessor handoff's §8 table claims against on-disk state.

| Claim | Anchor | Result |
|---|---|---|
| `layer4/context.py` `RaceEventPayload` carries `race_terrain` + `aid_stations` fields | `grep -n "race_terrain: list\[RaceTerrainEntry\]\|aid_stations: int" layer4/context.py` | ✅ |
| `RaceEventPayload._check_race_terrain_terrain_id_pattern` model_validator landed | `grep -n "_check_race_terrain_terrain_id_pattern" layer4/context.py` | ✅ |
| `init_db.py` `_PG_MIGRATIONS` has 2 new ALTER TABLE rows | `grep -n "ADD COLUMN IF NOT EXISTS race_terrain\|ADD COLUMN IF NOT EXISTS aid_stations" init_db.py` | ✅ |
| `race_events_repo.py` imports `RaceTerrainEntry` + 5 functions thread new fields | `grep -n "RaceTerrainEntry\|race_terrain\|aid_stations" race_events_repo.py` | ✅ (multiple hits across 5 functions) |
| `routes/race_events.py` has `_terrain_choices` + `_parse_race_terrain` helpers | `grep -n "_terrain_choices\|_parse_race_terrain" routes/race_events.py` | ✅ |
| `templates/profile/race_event_edit.html` has terrain editor block | `grep -n "race-terrain-rows\|race-terrain-template\|add-terrain-row" templates/profile/race_event_edit.html` | ✅ (still present pre-edit; this session refactors to a partial) |
| `layer4/orchestrator.py` lines 151 + 207 flipped | `grep -n "race_terrain=race_event.race_terrain\|aid_stations=race_event.aid_stations" layer4/orchestrator.py` | ✅ |
| `tests/test_race_events_repo.py` has `TestRaceTerrainAndAidStations` class | `grep -n "class TestRaceTerrainAndAidStations" tests/test_race_events_repo.py` | ✅ (9 tests) |
| `tests/test_layer4_orchestrator.py` has `TestRaceTerrainAndAidStationsWireUp` class | `grep -n "class TestRaceTerrainAndAidStationsWireUp" tests/test_layer4_orchestrator.py` | ✅ (3 tests) |
| `Upstream_Implementation_Plan_v1.md` §4 row 5.1.A flipped to ✅ Shipped 2026-05-20 | `grep -n "5.1.A.*Shipped 2026-05-20" aidstation-sources/Upstream_Implementation_Plan_v1.md` | ✅ |
| `Layer2B_Spec.md` §12 Open Item 2B-3 partial-close annotation landed | `grep -n "Partial-close 2026-05-20.*Phase 5.1 form-refresh A" aidstation-sources/Layer2B_Spec.md` | ✅ (pre-edit; this session flips to ✅ Resolved) |

`./scripts/verify-handoff.sh` flagged 1 missing path — `templates/onboarding/_race_terrain_editor.html` — which appeared in the predecessor §6.1 as a NEW-file forward-pointer for this session; not actual drift.

**Reconciliation note:** Clean. No drift between predecessor's claims and on-disk state.

---

## 2. Session narrative

Andy picked Form-refresh B at the AskUserQuestion gate (over form-refresh C, Layer 2B `_validate_inputs` loosen, or B+loosen paired). Plan-mode gate fired per Trigger #1 (user-facing form copy). 8 D-decisions surfaced + ratified before implementation.

Implementation flow:

1. **Partial template** — Created `templates/_race_terrain_editor.html` at root templates level (D2 location pick over `templates/onboarding/_race_terrain_editor.html` originally suggested in the predecessor §6.1, since the partial serves both onboarding/ and profile/ subdirs). Contains the terrain-rows container + add button + hidden `<template>` for JS cloning + inline vanilla-JS row-management hooks. Inputs from context: `existing_terrain` (list of dicts) + `terrain_choices` (list of `{id, label}` dicts). Single-render-per-page assumption documented in header comment (JS IDs scoped to single instance).
2. **Race-event-edit refactor** — Replaced the inline `<div class="col-12">` terrain block (~65 lines) + the bottom `<script>` block (~35 lines) in `templates/profile/race_event_edit.html` with `{% set existing_terrain = (race.race_terrain if race and race.race_terrain else []) %}` + `{% include '_race_terrain_editor.html' %}`. Behavior-neutral; net -103 LOC in this template, +98 at the partial.
3. **Onboarding template** — `templates/onboarding/target_race.html` shrunk distance + total_elevation_gain_m columns from `col-md-6 × 2` to `col-md-4 × 3` to fit a new `aid_stations` integer input (D4 layout pick mirroring race_event_edit.html). Inserted `{% set existing_terrain = (target.race_terrain if target and target.race_terrain else []) %}` + `{% include '_race_terrain_editor.html' %}` between mandatory_gear textarea and notes textarea. aid_stations help text matches the post-onboarding edit surface verbatim per D7.
4. **Route** — `routes/onboarding.py` added module-local `_TRN_PATTERN` + `_parse_race_terrain(form)` + `_terrain_choices(db)` mirroring `routes/race_events.py` (D1 v1 route-local duplicate-with-cross-ref strategy; ~12 LOC duplication keeps the 5-file ceiling intact and avoids forcing `race_events_repo.py` to grow form-parsing concerns). Cross-reference comment block names the source file + drift-mitigation strategy (tests on both sides exercise the same edge cases). Extended `_get_target_race_row()` SELECT to include `race_terrain` + `aid_stations` columns + JSONB list-or-string hydration mirroring `race_events_repo.get_race_event` adapter tolerance (psycopg2 native JSONB list vs sqlite shim JSON string vs NULL). Threaded `terrain_choices=_terrain_choices(db)` into `target_race()` GET render kwargs. `target_race_save()` POST parses `race_terrain` + `aid_stations` and threads into both `create_race_event` (new-target branch) + `update_race_event` (existing-target branch). Brief-only cache invalidation diff extended with `prior_terrain != new_race_terrain` + `prior_aid != new_aid_stations` comparisons (D5 — same `evict_on_target_event_brief_field_change` routing as `routes/race_events.py:update_race`).
5. **Tests** — `tests/test_onboarding_race_events.py` extended: added imports for the 2 new helpers; 3 new tests on `TestGetTargetRaceRow` covering race_terrain hydration paths (JSONB string / native list / None-defaults-empty); new `TestParseRaceTerrain` class with 8 tests (happy multi-row parse, empty form, drop-on-empty-terrain_id, drop-on-empty-pct, drop-on-invalid-TRN-pattern, drop-on-non-numeric-pct, drop-on-out-of-range-pct, sorted-order-across-sparse-indices); new `TestTerrainChoices` class with 2 tests (SELECT shape + ORDER BY + dict mapping, empty-rows degenerate); existing `test_returns_dict_on_hit` extended with new race_terrain + aid_stations column assertions in SELECT + dict pass-through.
6. **Test suite** — container-runnable subset 443 tests green (was 408 layer4+race_events; +35 from onboarding tests not counted in predecessor's scope — 19 pre-existing + 16 new). Default `pytest tests/test_onboarding_race_events.py -v` reports 35 passed in 0.53s. The pre-existing layer1/layer4 circular-import that the predecessor §4 noted as blocking collection of ~6 test files remains in place (not introduced by this slice; verified by `git stash` round-trip).
7. **Jinja syntax check** — All 3 affected templates compile cleanly via `jinja2.Environment.get_template()` smoke check.
8. **Bookkeeping** — `CURRENT_STATE.md` last-shipped pointer flip + tests count + arc summary update; `CARRY_FORWARD.md` Open Item 2B-3 full-close annotation + new §5.1.B walkthrough entry + form-refresh B follow-on strikethrough + onboarding paired-fix follow-on strikethrough; `Upstream_Implementation_Plan_v1.md` new §5.1.B row; `Layer2B_Spec.md` §12 Open Item 2B-3 flipped from 🟡 Partial-close to ✅ Resolved; this closing handoff.

No `/plan-mode` triggers fired during implementation past the initial gate (no prompt body, no schema change, no HITL gate, no padding refusal — the form copy was reused verbatim from form-refresh A).

---

## 3. File-by-file edits

### 3.1 `routes/onboarding.py` (MODIFIED, +96 LOC)

- Imports: added `import json` + `import re` at the top of the module.
- New module constant `_TRN_PATTERN = re.compile(r"^TRN-\d{3}$")` with explicit cross-ref comment block naming `routes/race_events.py` as the source and the drift-mitigation strategy (route-local duplicate + tests on both sides exercise the same edge cases + tiny LOC duplication).
- New `_parse_race_terrain(form)` function: scans form keys for `race_terrain[N][...]` matches; iterates sorted indices; drops empty / malformed / non-numeric / out-of-range rows; returns clean list of `{"terrain_id", "pct_of_race"}` dicts. Mirrors `routes/race_events.py:_parse_race_terrain`.
- New `_terrain_choices(db)` helper: request-time SELECT against `layer0.terrain_types WHERE superseded_at IS NULL ORDER BY terrain_id`; returns `{id, label}` dicts. Mirrors `routes/race_events.py:_terrain_choices`.
- `_get_target_race_row(db, uid)`: SELECT extended with `race_terrain, aid_stations` columns; result hydration block added (list-or-string-or-None tolerant; mirrors `race_events_repo.get_race_event:393-397`).
- `target_race()` GET: added `terrain_choices = _terrain_choices(db)` + threaded `terrain_choices=terrain_choices` into render_template kwargs.
- `target_race_save()` POST: parsed `new_race_terrain = _parse_race_terrain(request.form)` + `new_aid_stations = _parse_int_field(request.form, 'aid_stations')`; threaded into both `update_race_event` (existing-target branch) and `create_race_event` (new-target branch); brief-only cache-invalidation diff extended with `prior_terrain != new_race_terrain` + `prior_aid != new_aid_stations` comparisons (same `evict_on_target_event_brief_field_change` routing as `routes/race_events.py:update_race`).

### 3.2 NEW `templates/_race_terrain_editor.html` (+98 LOC)

Shared Jinja partial. Header comment names callers (`templates/profile/race_event_edit.html` + `templates/onboarding/target_race.html`) + context inputs + single-render-per-page assumption. Body:
- `<div class="col-12">` containing label + help text + `<div id="race-terrain-rows">` with `{% for entry in existing_terrain %}` loop rendering one row per persisted entry (per-row TRN-xxx `<select>` + percent input + remove button).
- "+ Add terrain" button (`#add-terrain-row`).
- Hidden `<template id="race-terrain-template">` block (Jinja-rendered terrain options inline; `__IDX__` placeholders swapped by JS).
- Inline `<script>` block with vanilla-JS hooks: `nextIdx()` scans existing rows for max `data-row-idx`; add-button clones template + appends; click delegation on `data-action="remove-terrain-row"` removes the row.

### 3.3 `templates/onboarding/target_race.html` (MODIFIED, +16 LOC net)

- Distance + total_elevation_gain_m columns shrunk from `col-md-6 × 2` to `col-md-4 × 3`.
- Added aid_stations integer input as the third `col-md-4` element (same row as distance + elevation). Help text identical to `templates/profile/race_event_edit.html` per D7.
- `{% set existing_terrain = (target.race_terrain if target and target.race_terrain else []) %}` + `{% include '_race_terrain_editor.html' %}` inserted between mandatory_gear textarea and notes textarea.

### 3.4 `templates/profile/race_event_edit.html` (MODIFIED, -103 LOC behavior-neutral refactor)

- Replaced the inline `<div class="col-12">` terrain block (rendering identical to the new partial) with `{% set existing_terrain = (race.race_terrain if race and race.race_terrain else []) %}` + `{% include '_race_terrain_editor.html' %}`.
- Removed the bottom `<script>` block (now bundled inside the partial).
- aid_stations input + the row containing distance / elevation / aid_stations / event_locale_id all untouched (unchanged from form-refresh A).

### 3.5 `tests/test_onboarding_race_events.py` (MODIFIED, +199 LOC)

- Imports: added `_parse_race_terrain` + `_terrain_choices`.
- `TestGetTargetRaceRow::test_returns_dict_on_hit`: extended fixture row with `race_terrain=[]` + `aid_stations=0`; added new assertions: SELECT includes `race_terrain` + `aid_stations` substrings + dict pass-through verified.
- Added 3 new `TestGetTargetRaceRow` tests:
  - `test_hydrates_race_terrain_from_jsonb_string` (sqlite shim path)
  - `test_hydrates_race_terrain_from_native_list` (psycopg2 native JSONB path)
  - `test_hydrates_none_race_terrain_to_empty_list` (NULL / pre-migration path)
- New `TestParseRaceTerrain` class with 8 tests covering the full edge-case matrix from `routes/race_events.py:_parse_race_terrain` semantics.
- New `TestTerrainChoices` class with 2 tests: SELECT shape + ORDER BY assertions + dict mapping shape, and empty-rows degenerate.

---

## 4. Code / tests

**Test count delta:** 1094 → 1110 in production count (+16 new: 3 + 8 + 2 + 3 existing-test extensions on `TestGetTargetRaceRow`); 4 SDK smoke tests still skip cleanly.

**Container-runnable subset:** 443 layer4+race_events+onboarding race_events tests green (35 of which are the onboarding race_events file — 19 pre-existing + 16 new — that the predecessor's 408 count didn't include since it was scoped to layer4+race_events).

Run reproducer:
```
PYTHONPATH=. python3 -m pytest tests/test_onboarding_race_events.py tests/test_race_events_repo.py \
                                tests/test_race_events_invalidation.py tests/test_layer4_orchestrator.py \
                                tests/test_layer4_context.py tests/test_layer4_payload.py \
                                tests/test_layer4_hashing.py tests/test_layer4_cache.py \
                                tests/test_layer4_race_week_brief.py
# 443 passed in 1.44s
```

The +16 new tests:
- `tests/test_onboarding_race_events.py::TestGetTargetRaceRow::test_hydrates_race_terrain_from_jsonb_string`
- `tests/test_onboarding_race_events.py::TestGetTargetRaceRow::test_hydrates_race_terrain_from_native_list`
- `tests/test_onboarding_race_events.py::TestGetTargetRaceRow::test_hydrates_none_race_terrain_to_empty_list`
- `tests/test_onboarding_race_events.py::TestParseRaceTerrain::*` (8 tests)
- `tests/test_onboarding_race_events.py::TestTerrainChoices::*` (2 tests)
- `tests/test_onboarding_race_events.py::TestGetTargetRaceRow::test_returns_dict_on_hit` (extended assertions; +0 net tests but expanded coverage)

Jinja partials compile-checked via `jinja2.Environment.get_template()` on all 3 affected templates.

---

## 5. Manual §5.0 verification steps

Added to `CARRY_FORWARD.md` "Manual §5.0 walkthrough" backlog:

**Phase 5.1 form-refresh B** — 2-step walkthrough on Vercel:

**Step 1: Onboarding step-3c form.** Log in as a fresh athlete who has NOT yet completed onboarding (or reset Andy's onboarding state to step 3c via direct DB UPDATE on the relevant `onboarding_progress` / equivalent column). Navigate to `/onboarding/target-race`. Confirm:
- The form now renders distance/elevation/aid_stations as 3 `col-md-4` inputs in a single row.
- The "Race terrain breakdown" section renders between the mandatory_gear textarea and the notes textarea, with no rows by default (identical editor to `/profile/race-events/<id>/edit` since both use the shared `templates/_race_terrain_editor.html` partial).
- Click "+ Add terrain" — confirm a row appears.
- Fill in 1-2 terrain rows + `aid_stations=0`. Submit the form.
- Confirm the race_events row is created with `race_terrain` JSONB + `aid_stations` populated: `SELECT race_terrain, aid_stations FROM race_events WHERE user_id=<andy> AND is_target_event=TRUE`.
- Return to `/onboarding/target-race` (the existing target row should pre-populate). Confirm the terrain rows + aid_stations pre-populate from the persisted JSONB.

**Step 2: Cache invalidation regression.** Edit a target race terrain row through onboarding, confirm the brief-only cache invalidation fires on race_terrain or aid_stations change but not on no-op saves: `SELECT * FROM layer4_cache WHERE user_id=<andy> AND entry_point='llm_layer4_race_week_brief' AND superseded_at IS NULL` should show eviction after a terrain edit, not after a no-op submit.

---

## 6. Next session pointers

### 6.1 Architect-recommended next forward move

**Form-refresh C — §J locale-terrain capture.** Closes the orchestrator's last `locale_terrain_ids=[]` forward-pointer + Layer2B_Spec.md §12 Open Item 2B-2. Mirrors form-refresh B's TRN-xxx vocabulary pattern but on a different table (`locale_profiles`).

Files (est. 4-5):
1. NEW `aidstation-sources/migrations/migrate_locale_terrain_ids.sql` or extension to `init_db.py` `_PG_MIGRATIONS` — ALTER TABLE on `locale_profiles` adding `locale_terrain_ids TEXT[] NOT NULL DEFAULT '{}'` (or JSONB — plan-mode gate at session start).
2. `routes/profile.py` or wherever locale-edit lives — extend the locale-edit form handler with `locale_terrain_ids` parsing (likely a multi-select per TRN-xxx; same `_terrain_choices(db)` helper can be reused — extract to a shared module here if D1 from form-refresh B's route-local duplicate strategy starts to bite).
3. `templates/profile/...locale_edit...html` — add multi-select widget bound to TRN-xxx choices.
4. `layer4/orchestrator.py` — flip the `locale_terrain_ids=[]` forward-pointer (line ~155-160 area) to `locale_terrain_ids=primary_locale.locale_terrain_ids` (or similar — depends on which loader returns it).
5. `tests/test_locale_profiles_*.py` or extended `tests/test_layer4_orchestrator.py` — round-trip + wire-up coverage.

Closes Layer2B_Spec.md §12 Open Item 2B-2 + the orchestrator's last Layer 2B input forward-pointer.

`/plan-mode` gate per Trigger #1 (user-facing form copy) + Trigger #3 (cross-layer schema change on `locale_profiles`).

### 6.2 Alternative pivots

- **Layer 2B `_validate_inputs` loosen for empty race_terrain** — paired with form-refresh C so athletes who skip terrain still get a working orchestrator end-to-end with a `race_terrain_unset` coaching flag instead of `Layer2BInputError`. ~1-2 files (`layer2b/builder.py` + tests). Pairing with C keeps total scope at ~5-6 files.
- **Form-refresh D** §I.1 structured supplements (Layer 2E §5.5 de-stub) — LARGE; requires architectural pick on schema (table vs JSONB) at the plan-mode gate. ~6-8 files.
- **Phase 5.2** — remaining 3 Layer 4 entry points (`single_session_synthesize`, `plan_refresh` T1/T2/T3, `plan_create`). Extract `_upstream_pipeline(db, user_id, today)` shared helper.
- **Layer 3B None-tolerant kwargs L3B-P-2** — migrate driver kwargs to typed RaceEventPayload fields. With form-refresh A + B's race_terrain landing, this becomes less hypothetical.
- **Real-LLM Layer 4 regression** parity to race_week_brief / single_session / plan_refresh / plan_create entry points (~$2/full smoke pass).
- **Manual §5.0 walkthrough** of the accumulated scenarios + new Phase 5.1 orchestrator end-to-end against Andy's PGE 2026 row (real-LLM ~$0.50 pass; depends on Layer 2B `_validate_inputs` loosen or on Andy walking step 1 of the Phase 5.1 form-refresh A/B walkthroughs).

### 6.3 Operating notes for next session

Read order (Rule #13):

1. `aidstation-sources/CLAUDE.md` — stable rules.
2. `aidstation-sources/CURRENT_STATE.md` — what just shipped + current focus + layer status.
3. `aidstation-sources/CARRY_FORWARD.md` — rolling cross-session items (now includes Phase 5.1 form-refresh B closure annotations on Open Item 2B-3 + the §5.1.B walkthrough entry).
4. `aidstation-sources/handoffs/V5_Implementation_D73_Phase_5_1_FormRefresh_B_Onboarding_2026_05_20_Closing_Handoff_v1.md` — this handoff.
5. `./scripts/verify-handoff.sh` — automated anchor sweep.

---

## 7. Decisions pinned

| # | Decision | Picked by | Rationale |
|---|---|---|---|
| **D1** | Helper-sharing strategy: route-local duplicate of `_TRN_PATTERN` + `_parse_race_terrain` + `_terrain_choices` (with explicit cross-ref comment) | Andy ratified plan-mode gate | v1 simplicity per predecessor handoff §6.1; ~12 LOC duplication keeps the 5-file ceiling intact; avoids forcing `race_events_repo.py` to grow form-parsing concerns (mis-layered) or introducing cross-blueprint imports (antipattern). Tests on both sides exercise the same edge cases so drift surfaces fast. |
| **D2** | Partial location: `templates/_race_terrain_editor.html` (root templates dir) | Andy | `_` prefix marks partial; sibling to `base.html`; resolved from both `onboarding/` and `profile/` subdirs without `../`. Handoff §6.1 originally suggested `templates/onboarding/_race_terrain_editor.html` but that mis-scopes the partial since it serves the profile path too. |
| **D3** | Partial scope: terrain editor only (not aid_stations input) | Andy | aid_stations is a single trivial integer input — embedding it in the partial increases coupling without saving meaningful LOC. Terrain is the part with JS / template-clone complexity worth deduping. |
| **D4** | aid_stations layout in onboarding: `col-md-4 × 3` (distance + elevation + aid_stations) | Andy | Mirrors `templates/profile/race_event_edit.html` layout exactly. Distance + elevation in onboarding were `col-md-6 × 2` — shrink both to `col-md-4` to fit aid_stations as the third. |
| **D5** | Cache invalidation: extend brief_only_changed diff to include race_terrain + aid_stations | Andy | Same target-event semantics as `routes/race_events.py:update_race`; both fields feed Layer 2B + 2E (uncached at orchestrator); Layer 4 brief is cache-load-bearing. New-target creation case continues to fire `evict_on_target_event_periodization_change` (broader; covers race_terrain/aid_stations as a subset). |
| **D6** | Skip semantics: empty terrain section saves with `race_terrain=[]` + `aid_stations=None` (current behavior; no new account_nudge) | Andy | Layer 2B `_validate_inputs` loosen is the paired follow-on that makes empty terrain produce a usable brief. v1 doesn't introduce a `target_race_terrain_missing`-style nudge. |
| **D7** | Form copy: identical to `templates/profile/race_event_edit.html` (race terrain help text + aid_stations help text) | Andy | Re-using existing copy preserves coaching voice consistency between the onboarding + post-onboarding edit surfaces. Trigger #1 explicit ratification. |
| **D8** | Section heading copy: "Race terrain breakdown" (matches edit surface label) | Andy | Same Trigger #1. Alternative onboarding-friendly phrasings considered ("What kind of terrain?" / "Surface mix") but consistency with the post-onboarding edit surface argued for re-using the label. |

---

## 8. Session-end verification (Rule #10)

| Check | Result |
|---|---|
| `routes/onboarding.py` imports `json` + `re` | ✅ `grep -n "^import json\|^import re" routes/onboarding.py` |
| `routes/onboarding.py` has `_TRN_PATTERN` + `_parse_race_terrain` + `_terrain_choices` | ✅ `grep -n "^_TRN_PATTERN\|^def _parse_race_terrain\|^def _terrain_choices" routes/onboarding.py` |
| `_get_target_race_row` SELECT includes race_terrain + aid_stations + hydration block | ✅ `grep -n "race_terrain, aid_stations\|raw_terrain = result.get" routes/onboarding.py` |
| `target_race()` GET passes `terrain_choices=terrain_choices` to template | ✅ `grep -n "terrain_choices=terrain_choices" routes/onboarding.py` |
| `target_race_save()` threads `race_terrain` + `aid_stations` into both create + update branches | ✅ `grep -n "race_terrain=new_race_terrain\|aid_stations=new_aid_stations" routes/onboarding.py` (4 hits — 2 per branch) |
| `target_race_save()` brief-only diff extended with prior_terrain + prior_aid comparisons | ✅ `grep -n "prior_terrain != new_race_terrain\|prior_aid != new_aid_stations" routes/onboarding.py` |
| NEW `templates/_race_terrain_editor.html` exists with terrain rows + script | ✅ `test -f templates/_race_terrain_editor.html && grep -n "race-terrain-rows\|race-terrain-template" templates/_race_terrain_editor.html` |
| `templates/onboarding/target_race.html` uses col-md-4 × 3 + aid_stations input + include | ✅ `grep -n "col-md-4\|aid_stations\|_race_terrain_editor.html" templates/onboarding/target_race.html` |
| `templates/profile/race_event_edit.html` uses include + no inline terrain block + no bottom script | ✅ `grep -n "_race_terrain_editor.html" templates/profile/race_event_edit.html` + `grep -c "race-terrain-rows" templates/profile/race_event_edit.html` returns 0 |
| `tests/test_onboarding_race_events.py` has `TestParseRaceTerrain` (8) + `TestTerrainChoices` (2) classes + extended `TestGetTargetRaceRow` (5 tests) | ✅ `grep -n "class TestParseRaceTerrain\|class TestTerrainChoices\|class TestGetTargetRaceRow" tests/test_onboarding_race_events.py` |
| Container-runnable subset green at 443 | ✅ `pytest tests/test_layer4_*.py tests/test_race_events_*.py tests/test_onboarding_race_events.py` reports 443 passed |
| `Upstream_Implementation_Plan_v1.md` §4 row 5.1.B flipped to ✅ Shipped 2026-05-20 | ✅ `grep -n "5.1.B.*Shipped 2026-05-20" aidstation-sources/Upstream_Implementation_Plan_v1.md` |
| `Layer2B_Spec.md` §12 Open Item 2B-3 flipped from 🟡 Partial-close → ✅ Resolved | ✅ `grep -n "Resolved 2026-05-20.*Phase 5.1 form-refresh A + B" aidstation-sources/Layer2B_Spec.md` |
| `CARRY_FORWARD.md` Open Item 2B-3 entry flipped to ✅ Resolved + Form-refresh B follow-on flipped to ✅ Shipped + onboarding paired fix flipped to ✅ Resolved | ✅ `grep -n "Resolved 2026-05-20.*Phase 5.1 form-refresh A + B\|Form-refresh B.*Shipped 2026-05-20" aidstation-sources/CARRY_FORWARD.md` |

---

## 9. Files shipped this session

**Substantive (5 files; at ceiling):**

1. MODIFIED `routes/onboarding.py` (+96 LOC) — `import json` + `import re` + `_TRN_PATTERN` + `_parse_race_terrain` + `_terrain_choices` + `_get_target_race_row` SELECT/hydration extension + `target_race()` GET render kwarg + `target_race_save()` POST threading + brief-only invalidation diff extension.
2. NEW `templates/_race_terrain_editor.html` (+98 LOC) — shared terrain-breakdown editor partial with rows loop + add button + hidden `<template>` + inline vanilla-JS row management.
3. MODIFIED `templates/onboarding/target_race.html` (+16 LOC) — col-md-6 × 2 → col-md-4 × 3 layout shift + aid_stations integer input + include partial between mandatory_gear and notes.
4. MODIFIED `templates/profile/race_event_edit.html` (-103 LOC behavior-neutral refactor) — inline terrain section + bottom script block → include partial.
5. MODIFIED `tests/test_onboarding_race_events.py` (+199 LOC) — `TestParseRaceTerrain` (8 tests) + `TestTerrainChoices` (2 tests) + `TestGetTargetRaceRow` 3 new + 1 extended.

**Bookkeeping (5 files):**

6. MODIFIED `aidstation-sources/CURRENT_STATE.md` — last-shipped pointer + tests count + current focus + arc summary updates.
7. MODIFIED `aidstation-sources/CARRY_FORWARD.md` — Open Item 2B-3 full-close annotation + new §5.1.B walkthrough entry + form-refresh B follow-on strikethrough + onboarding paired-fix follow-on strikethrough.
8. MODIFIED `aidstation-sources/Upstream_Implementation_Plan_v1.md` — new §5.1.B row.
9. MODIFIED `aidstation-sources/Layer2B_Spec.md` — §12 Open Item 2B-3 flipped from 🟡 Partial-close to ✅ Resolved.
10. NEW `aidstation-sources/handoffs/V5_Implementation_D73_Phase_5_1_FormRefresh_B_Onboarding_2026_05_20_Closing_Handoff_v1.md` — this handoff.

---

## 10. Carry-forward updates

See `CARRY_FORWARD.md` for the full list. Net changes:

- §H.2 race-terrain capture surface — Open Item 2B-3 ✅ **Resolved 2026-05-20** (form-refresh A + B both shipped same day).
- New §5.1.B walkthrough entry under "Manual §5.0 walkthrough" (onboarding step-3c terrain capture + cache invalidation regression).
- Form-refresh B follow-on flipped to ✅ Shipped under "Phase 5.1 form-refresh follow-ons" section.
- Onboarding paired-fix follow-on flipped to ✅ Resolved (folded into form-refresh B).

Phase 5.1 form-refresh B closes the 8 D-decisions ratified at the plan-mode gate; no carry-forward of unresolved decisions.

---

**End of handoff.**
