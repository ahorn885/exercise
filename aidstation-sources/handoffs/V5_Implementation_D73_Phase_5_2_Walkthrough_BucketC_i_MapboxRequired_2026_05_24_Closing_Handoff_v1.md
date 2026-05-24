# D-73 Phase 5.2 Walkthrough — Bucket C sub-item (i) Mapbox-Required — Closing Handoff

**Session:** D-73 Phase 5.2 caller-side — picks up the §6.2 alt-pivot menu from the predecessor BucketE_B2_C1 slice. Closes Bucket C sub-item (i) end-to-end via NEW `_check_event_locale_mapbox_id_required` model_validator on `RaceEventPayload` (defense-in-depth pydantic backstop) + route flash + redirect added to 4 POST handlers (race_events `new_race` + `update_race` + `set_locale` + onboarding `target_race_save`). Closes the last open Bucket C sub-item that was tractable without a plan-mode-gate design pass; (g) terrain↔equipment merge + (l) skill toggles remain open and gated.
**Date:** 2026-05-24
**Predecessor handoff:** `V5_Implementation_D73_Phase_5_2_Walkthrough_BucketE_B2_C1_2026_05_24_Closing_Handoff_v1.md`
**Branch:** `claude/charming-pascal-bfjS3` (harness-pinned; scope mismatch noted but harness rule overrides CLAUDE.md rename guidance for this session)
**Status:** 12 substantive files (3 code + 9 test; ceiling break ratified at AskUserQuestion gate). Container-runnable subset 889 → 901 (+12 net new). ETL `etl/tests/` 139 → 139 unchanged. No regressions.

---

## 1. Session-start verification (Rule #9)

Read order completed per Rule #13: CLAUDE.md → CURRENT_STATE.md → CARRY_FORWARD.md → predecessor BucketE_B2_C1 handoff → `./aidstation-sources/scripts/verify-handoff.sh`. Anchor sweep ✅ clean — the 4 ❌ entries on `tests/test_extractor_parsers.py` / `tests/test_sum_to_100.py` / `tests/test_v10_parsers.py` / `tests/test_vocabulary_md.py` are the known false-positives (those files live under `etl/tests/`, not `tests/`; the script doesn't know about the nested test tree). Working tree clean on the harness-pinned branch; predecessor §8 anchors spot-checked (`race_events.included_discipline_ids` migration intact; `RaceEventPayload.included_discipline_ids` + `RaceTerrainEntry.discipline_id` fields present; `disciplines_search` JSON endpoint present; `_parse_discipline_id_filter` helpers on both route surfaces). 889 → 889 baseline + 139 ETL confirmed. No drift between predecessor handoff narrative and on-disk state.

Andy picked **Bucket C sub-item (i) Mapbox-required** at the first AskUserQuestion gate over: #8 locales→locations rename / Bucket C (l) skill-capability toggles / Layer 2B per-discipline gap reasoning.

---

## 2. Session narrative

The Bucket C (i) carry-forward entry pre-spec'd the contract scope: "require `event_locale_mapbox_id` non-null at the form-validation boundary across 2 forms + 2 routes (race_events new/edit + onboarding)." Investigation surfaced 4 affected POST handlers (not 2 routes): `new_race`, `update_race`, `set_locale`, `target_race_save`. The picker partial (`_race_locale_picker.html`) renders the 5 Mapbox hidden inputs alongside the `set_locale` form (edit path) AND inside the `new_race`/`target_race_save` forms (create path) — `set_locale` decouples Mapbox edits from race-details edits on the existing-row flow.

The plan-mode gate ratified 3 open design choices via AskUserQuestion:

| # | Question | Andy's pick | Notes |
|---|---|---|---|
| D1 | How strict? | **All races, hard block** | Uniform contract across the race_events table + every form surface. Over target-races-only (loses non-target enforcement) + create-only-hard-update-soft (warning-fatigue bypass risk). |
| D2 | Where does enforcement live? | **Pydantic validator + route flash** | Defense-in-depth. Pydantic catches non-route writers (admin scripts, integration tests, future API surfaces) + backstops the LOAD path: `load_race_event_payload` now raises on legacy un-anchored DB rows rather than silently propagating a NULL through the orchestrator. Andy ratified the ceiling-break implication (~25 mechanical test fixture updates). Distinct from PR #131's route_locales validator LOOSEN (that was external-data-quality; this is athlete-input requirement at form-submit). |
| D3 | Onboarding `[Skip]`? | **Keep skip allowed** | Submit path requires Mapbox; `[Skip]` button (target_race_skip POST) remains as the escape valve for athletes who can't find their race in Mapbox. Closes the "can't find my race in Mapbox" friction case at the cost of one bypass path. |

**Slice-size disclosure to Andy mid-gate:** the original carry-forward estimate said "~3-4 files." Tracing the pydantic implication surfaced a ~25-site test fixture wave (Layer 4 orchestrator + Layer 3B + cached wrappers + plan_create + validator + repo `_race_row` default + 16 inline orchestrator constructors). Andy ratified the ceiling break (~10-13 substantive files) before code started, with the realistic count landing at 12.

**Order of work** (locked by validator implication — fixtures must lock to the new shape before new tests can run):

1. Pydantic validator on `RaceEventPayload`
2. Route flash + redirect at 3 race_events POSTs + 1 onboarding POST
3. Central `_race_row` fixture default flip in `test_race_events_repo.py`
4. Bulk-inject `event_locale_mapbox_id="poi.test_anchor"` at 16+ inline `RaceEventPayload(...)` constructors (Layer 4 + Layer 3B test families)
5. Helper-fixture update in `_queue_target_race_event` (Layer 4 orchestrator)
6. Rewrite `test_load_payload_defaults_mapbox_columns_to_none` → `test_load_payload_rejects_unanchored_row` (pin the LOAD-side backstop)
7. NEW `TestEventLocaleMapboxIdRequired` (5 validator tests)
8. NEW `TestNewRaceMapboxRequired` + `TestUpdateRaceMapboxRequired` + `TestSetLocaleMapboxRequired` (5 route tests)
9. NEW `TestTargetRaceSaveMapboxRequired` (2 onboarding route tests; preserves `[Skip]` semantics)

**Derisk findings before code:**

- The picker partial's 5 hidden inputs ALWAYS render (outside the `{% if mapbox_acked %}` block) so prior saves preserve their values across page renders. The search UI only renders when disclosure is acked. This means `set_locale`'s loose `if not name AND not mapbox_id` was the only path that allowed name-without-mapbox_id through (a hand-crafted POST bypassing the JS result-click handler). The strict tightening to `if not mapbox_id` closes that hand-crafted-POST hole.
- `update_race` POST doesn't carry Mapbox fields — the standalone `set_locale` POST owns Mapbox edits on the edit page. Andy's "hard block on every race save" pick means `update_race` should ALSO block when the loaded race row lacks Mapbox (forcing legacy un-anchored rows through the picker before any other edits can land). Implemented via `race.get('event_locale_mapbox_id')` check on the already-loaded `race` dict.
- `get_race_event` returns a dict (not RaceEventPayload), so the GET-edit page for un-anchored legacy rows still renders fine — the validator only fires through `load_race_event_payload` (which is only invoked via `load_target_race_event_payload` from the orchestrator's `_upstream_full_cone`). This is the correct scoping: athlete can see the row in the edit form, but can't save other edits or have the orchestrator load it until they re-anchor.
- Most existing test fixtures construct `RaceEventPayload(..., is_target_event=True)` — `is_target_event=False` constructions are essentially zero in the existing test suite. So the "all races" vs "target only" validator scope distinction makes ~no difference for fixture churn. Picked "all races" for contract clarity.
- Andy's PGE 2026 row is already Mapbox-anchored (per RaceLocaleMapbox slice 2026-05-21); no data migration required for his account.

---

## 3. File-by-file edits

### 3.1 `layer4/context.py` — NEW `_check_event_locale_mapbox_id_required` model_validator

Appended after `_check_route_locales_invariants` (line 1170). Raises `ValueError` when `self.event_locale_mapbox_id is None`. Comment block documents the Bucket C (i) ratification + draws the line to PR #131's loosen precedent (athlete-input requirement, not external-data-quality — different architectural class).

### 3.2 `routes/race_events.py` — Mapbox-required gates on 3 POSTs

- **`new_race` POST** — after `_extract_mapbox_locale_from_form`: `if not locale_fields['event_locale_mapbox_id']: flash + redirect`. Flash text: `Pick a race location before saving.`
- **`update_race` POST** — after the existing name/event_date/race_format gates: `if not race.get('event_locale_mapbox_id'): flash + redirect`. Flash text: `Pick a race location before saving other changes — use the Race location picker above.` Checks the already-loaded `race` dict (the race-details form doesn't carry Mapbox fields).
- **`set_locale` POST** — tightened the loose `if not name AND not mapbox_id` (which permitted hand-crafted name-without-mapbox_id POSTs) to strict `if not mapbox_id: flash + redirect`. Flash text: `Pick a race location.`

### 3.3 `routes/onboarding.py::target_race_save` — Mapbox-required gate

Added immediately after `_extract_mapbox_locale_from_form` (between the form-field parse block and the create/update branch): `if not new_locale_fields['event_locale_mapbox_id']: flash + redirect`. Flash text: `Pick a race location before saving.` Redirects to `/onboarding/target-race` (the GET form). Per D3, the `target_race_skip` POST handler is UNTOUCHED — the `[Skip]` button bypasses the gate and remains the escape valve.

### 3.4 `tests/test_layer4_race_week_brief.py` — NEW `TestEventLocaleMapboxIdRequired`

5 new tests + `_race_event_payload` helper updated:

1. `test_missing_mapbox_id_raises` — kwarg omitted entirely → raises
2. `test_explicit_none_mapbox_id_raises` — `event_locale_mapbox_id=None` explicitly → raises
3. `test_present_mapbox_id_accepted` — happy path
4. `test_validator_fires_even_when_legacy_slug_present` — pinning that the legacy `event_locale_id` slug is NOT a substitute (new contract treats them as orthogonal)
5. `test_validator_applies_to_non_target_races_too` — pinning the "all races" D1 scope (not target-only)

Also 2 inline `RaceEventPayload(...)` constructor sites in existing tests (`test_extra_field_rejected` + `test_out_of_order_sequence_idx_rejected`) updated with `event_locale_mapbox_id="poi.test_anchor"`.

### 3.5 `tests/test_routes_race_events.py` — 3 NEW classes (5 tests)

NEW `_RouteFakeRow` + `_RouteFakeConn` + `_make_app` substrate (mirrors `tests/test_locales.py::_FakeConn` precedent). NEW `_sql_fragment_count(conn, fragment)` helper.

- **TestNewRaceMapboxRequired** (2 tests): POST without mapbox_id → flash + redirect + no INSERT SQL fires / POST with mapbox_id → fake `create_race_event` invoked with the threaded mapbox_id (uses `race_format='multi_day_ultra'` to redirect to `race_events.edit_race` in the registered blueprint, avoiding the `profile.edit` route which isn't registered in the test app).
- **TestUpdateRaceMapboxRequired** (2 tests): POST on un-anchored loaded row → flash + redirect + no UPDATE SQL fires / POST on anchored loaded row → proceeds past the gate (eviction helpers monkeypatched so the call sequence doesn't depend on cache wiring).
- **TestSetLocaleMapboxRequired** (1 test): POST with only `event_locale_name` set (mimics the old loose-fallback path) → flash + redirect + no `update_race_event_locale` fires.

### 3.6 `tests/test_onboarding_race_events.py` — NEW `TestTargetRaceSaveMapboxRequired`

NEW `_make_onboarding_app` helper + 2 tests:

1. `test_post_without_mapbox_id_flashes_and_redirects` — POST without mapbox_id → flash + redirect to `/onboarding/target-race`; the `create_race_event` + `update_race_event` repo helpers are monkeypatched to `pytest.fail` so a stale call would be loud.
2. `test_skip_path_still_works` — the `[Skip]` button (`target_race_skip` POST) bypasses the gate; writes the `target_race_skipped` nudge + redirects forward. Pins D3.

### 3.7 `tests/test_race_events_repo.py` — `_race_row` default flip + rewritten test

- `_race_row` fixture defaults flipped: `event_locale_name=None → "Test Race Location"`, `event_locale_mapbox_id=None → "poi.test_anchor"`, `event_locale_place_name=None → "Test Race Location, Test State"`. Comment block documents the Bucket C (i) flip + the "tests that want the un-anchored path override the field directly" escape.
- `test_load_payload_defaults_mapbox_columns_to_none` rewritten in-place → `test_load_payload_rejects_unanchored_row`. New test pins the LOAD-side backstop: overrides the 3 Mapbox columns back to None on the row dict + asserts `load_race_event_payload` raises `ValueError` matching `event_locale_mapbox_id is required`. This is the contract pin for legacy un-anchored DB rows.

### 3.8-3.12 Bulk fixture updates (test_layer4_orchestrator + test_layer4_plan_create + test_layer4_validator + test_layer3b_builder + test_layer3_cached_wrappers)

Mechanical pass via regex injection: every `is_target_event=True,` line gets a preceding `event_locale_mapbox_id="poi.test_anchor",` line at matching indentation.

- `tests/test_layer4_orchestrator.py` — 16 inline constructors + `_queue_target_race_event` helper dict updated (3 keys: `event_locale_name`, `event_locale_mapbox_id`, `event_locale_place_name` flipped from None to placeholder values + comment block updated)
- `tests/test_layer4_plan_create.py` — 2 inline constructors
- `tests/test_layer4_validator.py` — 1 inline constructor
- `tests/test_layer3b_builder.py` — 1 inline constructor
- `tests/test_layer3_cached_wrappers.py` — 1 inline constructor

---

## 4. Code / tests

**Tests:** container-runnable subset 889 → 901 (+12 net new: 5 in TestEventLocaleMapboxIdRequired + 5 across the 3 race_events route classes + 2 in TestTargetRaceSaveMapboxRequired = 12); ETL `etl/tests/` 139 → 139 unchanged. 1 existing test rewritten in-place (`test_load_payload_defaults_mapbox_columns_to_none` → `test_load_payload_rejects_unanchored_row`), not counted in the +12. No regressions on Layer 4 / orchestrator / repo / race_events / locales / onboarding / plan_create / ad_hoc_workouts / plan_refresh / nl_parser / dashboard / admin / layer3 cached-wrappers / layer2a / layer2b surfaces; 12 NL parser smoke + 4 Layer 3 SDK smoke tests still skip cleanly when `ANTHROPIC_API_KEY` unset.

Reproducer (full container subset, mirrors predecessor's exact invocation):

```
PYTHONPATH=. python3 -m pytest tests/test_layer4_orchestrator.py tests/test_locales.py \
  tests/test_race_events_repo.py tests/test_race_events_invalidation.py \
  tests/test_onboarding_race_events.py tests/test_layer4_context.py \
  tests/test_layer4_payload.py tests/test_layer4_hashing.py tests/test_layer4_cache.py \
  tests/test_layer4_race_week_brief.py tests/test_plan_sessions_repo.py \
  tests/test_routes_ad_hoc_workouts.py tests/test_routes_plan_create.py \
  tests/test_nl_parser.py tests/test_routes_plan_refresh.py tests/test_nl_parser_smoke.py \
  tests/test_routes_dashboard.py tests/test_routes_admin.py \
  tests/test_layer3_cached_wrappers.py tests/test_routes_race_events.py \
  tests/test_layer2a.py tests/test_layer2b.py tests/test_bucket_c_terrain_vocab_audit.py
# 901 passed, 12 skipped in 1.20s
```

ETL: `PYTHONPATH=. python3 -m pytest etl/tests/ # 139 passed in 0.39s`.

**py_compile:** all 3 edited Python code files clean (`layer4/context.py` / `routes/race_events.py` / `routes/onboarding.py`).

---

## 5. Manual §5.0 verification — owed step

NEW 4-step walkthrough scenario added to CARRY_FORWARD §5.0 list. Summarized:

1. **New race POST without Mapbox pick** — confirm flash + redirect + no new race row landed.
2. **Legacy un-anchored existing row** — manually clear an existing row's Mapbox cols (NOT PGE 2026); confirm `/<id>/edit` GET renders fine but race-details form Save flashes + redirects until athlete uses the picker; after picker, race-name update lands cleanly.
3. **Onboarding submit without Mapbox pick** — confirm flash + redirect.
4. **Onboarding `[Skip]` still works** — confirm escape valve preserved; writes `target_race_skipped` nudge; no race row created.

Andy's PGE 2026 row is already Mapbox-anchored so no PGE-affecting verification needed.

---

## 6. Next session pointers

### 6.1 Architect-recommended next forward move

**#8 "locales" → "locations" terminology rename** remains the lowest-risk next-slice candidate (carried forward through every recent handoff; ~9 templates, mechanical, no `/plan` triggers). Affected templates pinned at `CARRY_FORWARD.md` line 92.

### 6.2 Alternative pivots

- **Bucket C sub-item (l): skill-capability toggles** — Trigger #3 + Trigger #5 plan-mode gate. Defaults pre-pinned by Andy (assume-not-skilled; narrow vocab = climbing/whitewater/swim ability). ~6-8 substantive files.
- **Bucket C sub-item (g) locale-terrain vs Outdoor-Terrain merge** — Trigger #3 cross-layer schema + #5 architectural alternatives. Plan-mode gate.
- **Layer 2B per-discipline gap reasoning (consume C1)** — Trigger #1 prompt-body update. Now unblocked since C1 ships the data shape; ~3-5 files including spec + prompt + tests.
- **#6 + #4 paired injury form refresh** — ~6-8 files; Trigger #5 on body-part-to-movement-constraints mapping.
- **#2b race-URL LLM site-parse pre-fill** — Trigger #2 prompt design session first; then ~4-6 files runtime.
- **§I.1 structured supplements onboarding refresh** — Layer 2E §5.5 de-stub. LARGE ~6-8 files; plan-mode gate required.
- **Bucket D — legacy hardcoded locales (a + b)** — depends on Bucket C terrain-vocab decisions landing first (specifically C (g) merge).
- **Manual §5.0 walkthrough** — accumulated 86 scenarios pending; this slice's 4-step scenario joins the list. The most recent shipped surfaces (BucketE_B2_C1 + WaterVocabExpansion + RouteLocalesAnchorFlags + ETLTerrainVocabDriftFix) are all unwalked.

### 6.3 Operating notes for next session

Read order (Rule #13):

1. `aidstation-sources/CLAUDE.md` — stable rules.
2. `aidstation-sources/CURRENT_STATE.md` — what just shipped + current focus + layer status.
3. `aidstation-sources/CARRY_FORWARD.md` — rolling cross-session items (Bucket C (i) line 105 flipped ✅; Bucket C still has (g) + (l) open; 86 §5.0 scenarios pending).
4. `aidstation-sources/handoffs/V5_Implementation_D73_Phase_5_2_Walkthrough_BucketC_i_MapboxRequired_2026_05_24_Closing_Handoff_v1.md` — this handoff.
5. `./aidstation-sources/scripts/verify-handoff.sh` — automated anchor sweep. The script's 4 ❌ false-positives on ETL test files still present (script doesn't know about `etl/tests/`); verify via `ls etl/tests/`.

**No outstanding production warnings.** Bucket C: now 9 of 11 sub-items closed (a/b/c/d/e/f/h/i/j + k); 2 still open — (g) terrain↔equipment merge (Trigger #3 plan-mode), (l) skill toggles (Trigger #3 + #5 plan-mode). Bucket E: fully closed.

**Backward-compat note for next ETL/data session:** the new validator raises on LOAD of legacy un-anchored race rows. If any test athletes other than Andy have race_events rows missing `event_locale_mapbox_id`, those rows will block orchestrator runs (race_week_brief / plan_create / plan_refresh) until re-anchored. Spot-check via `SELECT COUNT(*) FROM race_events WHERE is_target_event=TRUE AND event_locale_mapbox_id IS NULL AND superseded_at IS NULL` — if non-zero, those athletes need to re-edit their target race through the picker before next plan-gen.

---

## 7. Decisions pinned

| # | Decision | Picked by | Rationale |
|---|---|---|---|
| **D1** | All-races hard block (every race save requires Mapbox) | Andy at AskUserQuestion gate | Over target-races-only (leaves calendar-placeholder races un-anchored — inconsistent contract) + create-only-hard-update-soft (warning fatigue + bypass risk; flash-without-block is too easy to dismiss). Uniform enforcement keeps the data shape clean across the table + matches the existing race-name/race-format gate pattern. |
| **D2** | Pydantic validator + route flash + ceiling break for the ~25-fixture wave | Andy at AskUserQuestion gate (after slice-size disclosure mid-gate) | Over route-only (no defense-in-depth against non-route writers + no LOAD-side backstop for legacy un-anchored DB rows). Pydantic catches the LOAD path which the route layer can't reach (orchestrator's `_upstream_full_cone` → `load_target_race_event_payload` → `load_race_event_payload` constructs RaceEventPayload from any target race row). The PR #131 precedent (LOOSENED `_check_route_locales_invariants` 2026-05-23) doesn't argue against this: PR #131 was external-data-quality (route_locales captured without explicit start anchors — real-world race data lacking a synthetic boundary), this is athlete-input requirement (Mapbox pick is what the athlete does at form-submit). Different architectural class. |
| **D3** | Keep onboarding `[Skip]` allowed | Andy at AskUserQuestion gate | Over remove-skip (closes a real use case — athletes who can't find their race in Mapbox lose access to onboarding entirely). Submit path requires Mapbox; `[Skip]` button (`target_race_skip` POST) bypasses the gate + writes `target_race_skipped` nudge. The escape valve is gated to the onboarding surface only — no equivalent for `/profile/race-events/<id>` (if the un-pickable-race friction surfaces, future fix is a `[Manual entry]` button writing synthetic `event_locale_mapbox_id=manual.<slug>`, but no current evidence justifies it). |
| **D4** | `update_race` checks the loaded `race` dict, not the form | Architect at code-time | The race-details form doesn't carry the Mapbox hidden inputs — the standalone `set_locale` POST owns Mapbox edits on the edit page (decoupling from RaceLocaleMapbox slice 2026-05-21 design). `update_race` checks `race.get('event_locale_mapbox_id')` from the dict loaded by `get_race_event` at the route entry; if NULL, the athlete is bounced to the edit page where the picker form is rendered above the race-details form (forces legacy un-anchored rows through the picker before any other edits land). |
| **D5** | `set_locale` tightened from loose `name OR mapbox_id` to strict `mapbox_id required` | Architect at code-time | The picker JS always sets mapbox_id alongside name on result-click, so the old loose check only allowed hand-crafted POSTs through. Tightening closes that hole + matches the uniform requirement. Flash text changed from "Place lookup result was malformed; try again." (which implied the JS failed) to "Pick a race location." (which is the actual intent under the strict contract). |
| **D6** | Validator scoped to ALL RaceEventPayload constructions, not `is_target_event=True` only | Architect at code-time | The scope-only-target alternative would save ~zero test fixture churn (~24 of 25 existing constructors have `is_target_event=True`) while creating an asymmetric data contract (target races require Mapbox; non-target races are allowed un-anchored). Uniform "all-races" matches D1's route-side scope. |
| **D7** | LOAD-side raise on legacy un-anchored DB rows (loud-fail rather than silent-degrade) | Architect at code-time (consequence of D2 + D6) | The new validator fires on `load_race_event_payload`, which means orchestrator runs blow up loudly for legacy un-anchored target rows. Loud-by-design: silent-degrade would propagate NULL anchors through the brief-rendering path (currently surfacing as `event_locale_unresolved` deep in Layer 4) and produce subtly-wrong briefs. Loud-fail forces the athlete to re-anchor via the picker before the next plan-gen. Andy's PGE 2026 is already anchored. |
| **D8** | Bulk fixture updates via regex-injection (`event_locale_mapbox_id="poi.test_anchor",` before every `is_target_event=True,`) | Architect at code-time | Mechanical pass; no semantic risk. Each constructor that needs the field gets it added on a new line above `is_target_event=True` at matching indentation, preserving existing style. Bulk-edit pattern executed via a small Python regex script; verified via grep + targeted pytest runs after each file. |

---

## 8. Session-end verification (Rule #10)

| Check | Result |
|---|---|
| `_check_event_locale_mapbox_id_required` validator added to RaceEventPayload | ✅ `grep -n '_check_event_locale_mapbox_id_required' layer4/context.py` returns hit |
| Validator raises on missing mapbox_id | ✅ `grep -n 'event_locale_mapbox_id is required' layer4/context.py` returns hit |
| `new_race` POST adds Mapbox-required check | ✅ `grep -B1 'Pick a race location before saving' routes/race_events.py` returns hit in new_race body |
| `update_race` POST adds Mapbox-required check on loaded row | ✅ `grep -n "race.get('event_locale_mapbox_id')" routes/race_events.py` returns hit |
| `set_locale` tightened to strict mapbox_id required | ✅ `grep -A3 "Bucket C (i) — strict" routes/race_events.py` returns hit |
| `target_race_save` POST adds Mapbox-required check | ✅ `grep -n "Bucket C (i)" routes/onboarding.py` returns hit |
| `target_race_skip` POST untouched (escape valve preserved) | ✅ `git diff routes/onboarding.py` shows no changes inside `target_race_skip` |
| NEW `TestEventLocaleMapboxIdRequired` (5 tests) | ✅ pytest run in 0.29s |
| NEW `TestNewRaceMapboxRequired` + `TestUpdateRaceMapboxRequired` + `TestSetLocaleMapboxRequired` (5 tests across 3 classes) | ✅ pytest run |
| NEW `TestTargetRaceSaveMapboxRequired` (2 tests) | ✅ pytest run |
| `_race_row` fixture default flipped (event_locale_mapbox_id None → "poi.test_anchor") | ✅ `grep -A1 '"event_locale_mapbox_id"' tests/test_race_events_repo.py` returns the placeholder |
| `test_load_payload_rejects_unanchored_row` pins LOAD-side backstop | ✅ `grep -n 'test_load_payload_rejects_unanchored_row' tests/test_race_events_repo.py` returns hit |
| `_queue_target_race_event` helper updated for Layer 4 orchestrator tests | ✅ `grep -A2 '"event_locale_mapbox_id"' tests/test_layer4_orchestrator.py` returns "poi.test_anchor" |
| Bulk fixture inject across 5 Layer 4/3B test files | ✅ `grep -c 'event_locale_mapbox_id="poi.test_anchor"' tests/test_layer4_orchestrator.py tests/test_layer4_plan_create.py tests/test_layer4_validator.py tests/test_layer3b_builder.py tests/test_layer3_cached_wrappers.py` returns 16+2+1+1+1 = 21 |
| Container-runnable subset 889 → 901 pass + 12 skipped | ✅ pytest run in 1.20s |
| ETL `etl/tests/` 139 → 139 pass | ✅ pytest run in 0.39s |
| `CURRENT_STATE.md` last-shipped pointer flipped to this handoff | ✅ |
| `CARRY_FORWARD.md` Bucket C (i) line 105 flipped ✅ shipped + §5.0 walkthrough scenario added (4 steps) + scenario count 82 → 86 | ✅ |

---

## 9. Files shipped this session

**Substantive (12 files; ceiling break ratified at AskUserQuestion gate; precedent BucketE_B2_C1=11+5, RaceLocaleMapbox=13):**

1. MODIFIED `layer4/context.py` — NEW `_check_event_locale_mapbox_id_required` model_validator on `RaceEventPayload`.
2. MODIFIED `routes/race_events.py` — Mapbox-required check in `new_race` POST + `update_race` POST + tightened `set_locale` from loose `OR` to strict `mapbox_id required`.
3. MODIFIED `routes/onboarding.py` — Mapbox-required check in `target_race_save` POST (between form-field parse and create/update branch).
4. MODIFIED `tests/test_layer4_race_week_brief.py` — NEW `TestEventLocaleMapboxIdRequired` (5 tests); `_race_event_payload` helper updated; 2 inline test sites updated.
5. MODIFIED `tests/test_routes_race_events.py` — NEW `_RouteFakeRow` + `_RouteFakeConn` + `_make_app` substrate; 3 NEW classes (TestNewRaceMapboxRequired 2 / TestUpdateRaceMapboxRequired 2 / TestSetLocaleMapboxRequired 1).
6. MODIFIED `tests/test_onboarding_race_events.py` — NEW `_make_onboarding_app` helper; NEW `TestTargetRaceSaveMapboxRequired` (2 tests).
7. MODIFIED `tests/test_race_events_repo.py` — `_race_row` fixture default flipped (3 Mapbox cols); 1 test rewritten in-place (`test_load_payload_defaults_mapbox_columns_to_none` → `test_load_payload_rejects_unanchored_row`).
8. MODIFIED `tests/test_layer4_orchestrator.py` — `_queue_target_race_event` helper updated (3 keys); 16 inline `RaceEventPayload(...)` constructors updated.
9. MODIFIED `tests/test_layer4_plan_create.py` — 2 inline constructors.
10. MODIFIED `tests/test_layer4_validator.py` — 1 inline constructor.
11. MODIFIED `tests/test_layer3b_builder.py` — 1 inline constructor.
12. MODIFIED `tests/test_layer3_cached_wrappers.py` — 1 inline constructor.

**Bookkeeping (3 files; do not count against ceiling per CLAUDE.md):**

13. MODIFIED `aidstation-sources/CURRENT_STATE.md` — last-shipped pointer flipped to this handoff; predecessor BucketE_B2_C1 line preserved.
14. MODIFIED `aidstation-sources/CARRY_FORWARD.md` — Bucket C (i) line 105 flipped ✅ shipped; NEW 4-step Manual §5.0 walkthrough scenario added; scenario count 82 → 86.
15. NEW `aidstation-sources/handoffs/V5_Implementation_D73_Phase_5_2_Walkthrough_BucketC_i_MapboxRequired_2026_05_24_Closing_Handoff_v1.md` — this handoff.

---

## 10. Carry-forward updates

See `CARRY_FORWARD.md` for the full list. Net changes:

- **Bucket C sub-item (i) closed end-to-end** ✅ — Bucket C now: 9 of 11 sub-items closed (a/b/c/d/e/f/h/i/j + k); 2 still open — (g) terrain↔equipment merge (Trigger #3 plan-mode), (l) skill toggles (Trigger #3 + #5 plan-mode).
- **NEW 4-step Manual §5.0 walkthrough scenario** — new race POST without Mapbox / legacy un-anchored row blocks on update / onboarding submit without Mapbox / `[Skip]` still works.
- **LOAD-side backstop forward-pointer** — if other test athletes have un-anchored target race rows, those rows will block orchestrator runs after this deploy. Spot-check query pinned in §6.3.
- **Pre-existing forward-pointers carried** — #8 locales→locations rename remains the architect-recommended next-slice candidate; (g) + (l) still gated; Layer 2B per-discipline gap reasoning (consume C1) still queued; #6 + #4 injury form refresh / #2b race-URL site-parse / §I.1 structured supplements all carry.

**End of handoff.**
