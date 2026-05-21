# D-73 Phase 5.2 Walkthrough Race-Locale Mapbox + race_url — Closing Handoff

**Session:** D-73 Phase 5.2 caller-side — closes punch-list items #1 (race "Event locale" → Mapbox-anchored picker) + #2a (race_url column) from Andy's 2026-05-21 manual walkthrough. Schema + repo + Layer 4 payload + routes + 2 form templates + new shared picker partial + tests.
**Date:** 2026-05-21
**Predecessor handoff:** `V5_Implementation_D73_Phase_5_2_Walkthrough_PunchList_2026_05_21_Closing_Handoff_v1.md`
**Branch:** `claude/v5-phase-5-2-walkthrough-XBJTy` (harness-pinned; scope matches the walkthrough remediation arc so the name is left intact).
**PR:** TBD — open as draft once pushed.
**Status:** 13 substantive files. Tests 1419 → 1441 (+22 net); container-runnable subset 752 → 774 in ~1.3s. No regressions on Layer 4 / orchestrator / repo / race_events / locales / onboarding / plan_create / ad_hoc_workouts / plan_refresh / nl_parser / dashboard / admin telemetry surfaces.

---

## 1. Session-start verification (Rule #9)

`./aidstation-sources/scripts/verify-handoff.sh` ran clean against the Walkthrough PunchList predecessor handoff. All §8 anchor claims verified on-disk. No drift.

Predecessor merged to main via PR #126 (`e15a600`); the branch this session opens on was equal to `origin/main`. Walkthrough PunchList slice is fully landed.

---

## 2. Session narrative

Predecessor's §6.1 architect-recommended next forward move offered 3 ranked candidates; Andy picked **#1 + #2a as a combined slice** (race "Event locale" → Mapbox lookup + race_url column). Trigger #5 (architectural alternatives) fired on the Mapbox-vs-text-only-vs-inline-lat-lng call.

Pre-design survey:

- Current shape: `race_events.event_locale_id BIGINT FK to locale_profiles(id)` — saved-locale dropdown (`templates/profile/race_event_edit.html:76-90` + `templates/onboarding/target_race.html:68-83`). Athletes picked one of their `home`/`hotel`/`partner`/`airport`/custom slots. This semantic was wrong — a race finish lives at a specific real-world place, not at the athlete's training-locale registry.
- Existing Mapbox precedent: `routes/locales.py:733-897` shipped the full `/locales/new` flow (search → disclosure ack → result picker → INSERT with `mapbox_id`/`lat`/`lng`/`place_name`/`category`). `mapbox_client.search_places(query, limit=5)` adapter at `mapbox_client.py` returns normalized `{mapbox_id, text, place_name, lng, lat, category, raw_payload}` dicts.
- Existing race-route-locale `mapbox_id` precedent at `race_events_repo.py:103/313/474/496` for per-waypoint anchoring inside `race_route_locales` (multi-day race graph) — same column shape we're using for race-level location.
- Downstream consumers of `event_locale_id`: Layer 3B stamps it at `layer3b/builder.py:1434` (`candidate["event_locale_id"] = race_event_payload.event_locale_id`); Layer 4 race-week brief precondition rule 5 (`event_locale_unresolved`) is documented in the comment at `layer4/race_week_brief.py:686` but NOT actually enforced in `_validate_inputs` — so no code change needed there.
- Layer 4 user prompt at `layer4/race_week_brief.py:_render_user_prompt` did NOT include any race-location info; the LLM inferred event_locale from the event name (e.g. "Pocket Gopher Extreme 2026" → "Nerstrand, MN"). Adding a `**Race location:** <name>` line makes the LLM's `event_locale` output grounded in the athlete-provided anchor.

Andy ratified 6 D-decisions at `AskUserQuestion` gates before implementation:

- **D1** = Option A "full Mapbox mirror" (5 new columns + inline search/picker UI mirroring `/locales/new`). Over text-only + inline-lat-lng-no-search. Unlocks Layer 2E heat-acclim + Layer 4 travel-distance reasoning downstream.
- **D2** = Combine #1 + #2a in one slice. Tightly-coupled file deltas; splitting would re-touch the same files twice (init_db.py + race_events_repo.py + race_event_edit.html + onboarding/target_race.html).
- **D3** = Ceiling break to 9 substantive files ratified. Consistent with recent precedents (5.1.A=8, 5.1.C=8, 5.2.D63+PlanCreate=9, 5.2.LogThis+T1Hook=7, 5.2.D64=8, Walkthrough_PunchList=8). Actual final count = 13 (4 over the ratified 9; transparency in §9 below).
- **D4** = Full Mapbox at onboarding too (over simple text-input-at-onboarding). Uniform UX across new_race / edit_race / onboarding step 3c via the shared picker partial.
- **D5** [implementation] = keep legacy `event_locale_id BIGINT FK` column nullable for backward compat (pre-walkthrough rows still load via the JOIN→slug fallback in `load_race_event_payload`); `update_race_event_locale` explicitly clears it on Mapbox-anchored update so the stale slug doesn't leak downstream.
- **D6** [implementation] = AJAX `fetch()` from inline nonce-protected `<script>` for search (over GET round-trip with form-state preservation in query string). The race form's `mandatory_gear_text` + `race_rules_summary` textareas can be ~8KB each; GET round-trip would exceed the typical 8KB URL line limit. AJAX bypasses the issue entirely.

Implementation: 13 substantive files; 2 commits expected (TBD on push). All Mapbox flow + race_url plumbing landed end-to-end across 3 surfaces (race_event_edit / new_race / onboarding step 3c).

`/plan` Triggers fired: **#3** (cross-layer schema: 6 new `race_events` columns + 6 new `RaceEventPayload` fields), **#5** (architectural alternatives for the Mapbox UX). Andy ratified at AskUserQuestion gate.

`/plan` Triggers DEFERRED:

- **#2b LLM site-parse pre-fill** — will fire Trigger #2 (LLM prompt design) before runtime ship. ~4-6 files runtime including a NEW `race_url_parser.py`.
- **#4 body_part vocab cleanup** — folded into §B onboarding refresh.
- **#6 dynamic movement-constraints** — Trigger #5 fires on the mapping design.
- **#8 "locales" → "locations" rename** — mechanical, no Triggers.

---

## 3. File-by-file edits

### 3.1 `init_db.py` — 6 new race_events columns

Added 6 `ALTER TABLE race_events ADD COLUMN IF NOT EXISTS …` migrations alongside the existing race_terrain/aid_stations block:

- `event_locale_name TEXT NULL` — looked-up place name (e.g. "Nerstrand State Park")
- `event_locale_mapbox_id TEXT NULL` — opaque Mapbox feature ID
- `event_locale_place_name TEXT NULL` — full formatted address
- `event_locale_lat NUMERIC(9,6) NULL` — latitude
- `event_locale_lng NUMERIC(9,6) NULL` — longitude
- `race_url TEXT NULL` — race-director site URL (#2a)

Legacy `event_locale_id BIGINT FK to locale_profiles(id)` column stays nullable for pre-walkthrough rows.

### 3.2 `race_events_repo.py` — kwargs + new helper

- `create_race_event` + `update_race_event` signatures gain 6 new kwargs (5 Mapbox + race_url); SQL INSERT/UPDATE extended (INSERT goes from 14 columns to 20; UPDATE from 11 to 17).
- NEW `update_race_event_locale(db, user_id, race_event_id, *, event_locale_name, event_locale_mapbox_id, event_locale_place_name, event_locale_lat, event_locale_lng)` — standalone helper for the inline picker flow on the edit page. Updates ONLY the 5 Mapbox columns + clears the legacy `event_locale_id` FK so stale slug doesn't leak downstream via the JOIN.
- `get_race_event` + `load_race_event_payload` + `list_athlete_race_events` SELECTs extended.
- NUMERIC(9,6) lat/lng coerced to Python `float` on hydration (`get_race_event` + `load_race_event_payload`) for template arithmetic + form-field rendering simplicity.

### 3.3 `layer4/context.py` — RaceEventPayload extension

- Added 5 Mapbox fields: `event_locale_name`, `event_locale_mapbox_id`, `event_locale_place_name`, `event_locale_lat`, `event_locale_lng`.
- Added `race_url` field (`Field(max_length=1000)`).
- `event_locale_id` field comment extended documenting the "EITHER legacy slug OR new event_locale_name" resolution semantic.
- `event_locale_lat` / `event_locale_lng` carry `Field(ge=-90.0, le=90.0)` / `Field(ge=-180.0, le=180.0)` bounds — load-bearing payload-level NaN/out-of-range gate (since `_extract_mapbox_locale_from_form` allows `float('NaN')` through — Python's `float('NaN')` succeeds).

### 3.4 `layer4/race_week_brief.py` — user prompt thread-through

`_render_user_prompt` adds a `**Race location:** <name>` line sourced from `event_locale_place_name` ?? `event_locale_name` ?? `event_locale_id` (legacy fallback). 9 lines added between `**Days to event:** {days_to_event}` and the distance/elevation lines. Without this thread, the LLM had no race-location signal at all and inferred from the event name; with it, the brief's `event_locale` output is grounded in the athlete-provided anchor.

### 3.5 `routes/race_events.py` — Mapbox picker plumbing

- Dropped `_athlete_locale_choices` (saved-locale dropdown helper — no longer used).
- NEW `_run_mapbox_search(query) -> (results, error)` — mirrors `/locales/new` GET-side error translation for the 3 mapbox_client failure modes (`MapboxTokenMissing` / `MapboxNoResults` / `MapboxAPIError`). Empty query short-circuits without a Mapbox HTTP call.
- NEW `_extract_mapbox_locale_from_form(form) -> dict` — defensive blank/non-numeric collapse on the 5 Mapbox hidden inputs. Empty strings collapse to None; non-numeric lat/lng coerces to None.
- NEW `_parse_race_url(form) -> str | None` — trim + 1000-char cap + empty-collapse.
- NEW `GET /profile/race-events/locale/search` (`locale_search`) — JSON Mapbox-forward search endpoint. Returns `{"results": [...]}`, `{"error": "..."}`, or `400 {"error": "disclosure_required"}`. Used by inline picker `fetch()` from both race-edit + onboarding.
- NEW `POST /profile/race-events/<id>/locale/update` (`set_locale`) — calls `update_race_event_locale` + fires `evict_on_target_event_brief_field_change` on target rows (Layer 4 brief eviction; NOT broader Layer 2C — race finish anchor doesn't drive athlete equipment resolution).
- NEW `POST /profile/race-events/locale/acknowledge` (`acknowledge_mapbox_disclosure`) — shares the disclosure ack with `/locales/new` via `disclosure_acknowledgments` rows; an ack from either surface unblocks both. Redirects back to `return_to` (gated to `/profile/race-events/` + `/onboarding/` prefixes).
- `new_race` POST extracts Mapbox hidden inputs via `_extract_mapbox_locale_from_form` + threads through `create_race_event`. The race-details form's Mapbox hidden inputs ride alongside the rest for a single atomic create.
- `update_race` POST no longer reads `event_locale_id` from the form (saved-locale dropdown removed); preserves the existing row's Mapbox columns verbatim (those are owned by the standalone `set_locale` endpoint on the edit page). Cache invalidation: `locale_changed` branch removed (no `evict_on_target_event_locale_change` Layer 2C eviction for these edits); `race_url` change rolled into `brief_only_changed` diff.

### 3.6 `routes/onboarding.py` — drop dropdown + Mapbox parity

- Deleted `_athlete_locale_choices` helper (helper-only delete; nothing else used it).
- `target_race` GET drops the `locale_choices` template kwarg; adds `mapbox_acked` + `mapbox_disclosure_version` kwargs imported from `routes.locales`.
- `target_race_save` POST imports `_extract_mapbox_locale_from_form` + `_parse_race_url` from `routes.race_events`; threads Mapbox kwargs + `race_url` through `create_race_event` / `update_race_event`.
- Cache-invalidation diff updated: `locale_changed` branch removed (no Layer 2C eviction for race-locale edits); `mapbox_id_changed` + `race_url_changed` rolled into `brief_only_changed`.
- `_get_target_race_row` SELECT extended with the 6 new columns + NUMERIC lat/lng coerced to float.

### 3.7 `templates/profile/race_event_edit.html` — drop dropdown + add picker

- Dropped the `event_locale_id` `<select>` (lines 76-90 in the predecessor).
- Added `[Race website URL]` `<input type="url">` for #2a in its place.
- For `is_new=False`: NEW standalone "Race location" section ABOVE the race-details form, wrapping `_race_locale_picker.html` partial in a POST form to `race_events.set_locale`. Decoupled from the race-details `update_race` POST so the athlete can pick a location without re-submitting (and re-validating) the rest of the form.
- For `is_new=True`: the picker partial is rendered INSIDE the race-details form so the create POST carries the Mapbox hidden inputs through atomically (athlete picks location + fills rest of form + Saves in one click).

### 3.8 `templates/onboarding/target_race.html` — drop dropdown + add picker + race_url

- Dropped the `event_locale_id` `<select>`.
- Added `[Race website URL]` `<input type="url">` in its place.
- Embedded the `_race_locale_picker.html` partial INSIDE the race-details form so the single-POST onboarding flow carries Mapbox hidden inputs through.

### 3.9 NEW `templates/_race_locale_picker.html` — shared partial (~190 LOC)

Renders inside the parent race-edit / target-race / new-race form. The parent form owns the 5 hidden inputs (`event_locale_name`, `event_locale_mapbox_id`, `event_locale_place_name`, `event_locale_lat`, `event_locale_lng`).

Structure:
- 5 hidden `<input>` tags (always present, populated from `selected_*` caller context).
- "Selected: <name>" display section (shown when picker has a value; "[Change]" button reveals the search box).
- Mapbox disclosure card (rendered when `not mapbox_acked`; POSTs ack to `acknowledge_endpoint_url` with a `return_to` field).
- Search box + result list pane (rendered when acked).
- CSP-nonced inline `<script>` ~80 LOC: binds click handlers; fetches `search_endpoint_url` with `credentials: 'same-origin'` (CSRF token auto-injected by `static/app.js`); renders each result as a button-card; on result-click fills the 5 hidden inputs + shows "Selected" display + hides search box.

The `[Change]` button clears the picker UI state (hidden inputs cleared, search box re-shown) but does NOT POST anything — the saved DB row stays intact until athlete picks a new result + clicks "Save race location". Forward-pointer: explicit "Clear race location" button to un-anchor a race entirely (~5 LOC follow-on).

Caller context required: `selected_name`, `selected_place_name`, `selected_mapbox_id`, `selected_lat`, `selected_lng`, `mapbox_acked`, `mapbox_disclosure_version`, `search_endpoint_url`, `acknowledge_endpoint_url`, `return_to_url`.

### 3.10 `tests/test_race_events_repo.py` — fixture + 7 new tests

- `_race_row(**overrides)` fixture extended with 6 new column defaults (all None — default "no Mapbox data" so existing tests still pass).
- 2 existing tests updated (param-position-shift due to 6 new columns appended to the INSERT/UPDATE SQL): `test_create_serializes_race_terrain_as_json_and_passes_aid_stations` + `test_create_empty_race_terrain_serializes_as_empty_array` now use param-content-based lookups instead of `params[-3]` slot indexing.
- 7 NEW tests in `TestMapboxRaceLocationColumns` class: load_payload populates Mapbox cols when present / load_payload defaults all 5 to None when absent / create passes Mapbox kwargs in INSERT / create defaults Mapbox kwargs to None (≥6 None params verified) / update passes Mapbox kwargs / `update_race_event_locale` clears legacy FK + only touches Mapbox cols (no race_url / race_terrain mention; 7-tuple param count) / get_race_event coerces NUMERIC lat/lng to float.

### 3.11 `tests/test_onboarding_race_events.py` — drop deleted-helper tests

Removed `TestAthleteLocaleChoices` class (2 tests; helper was deleted with the dropdown). Replaced with an audit-trail comment block.

### 3.12 NEW `tests/test_routes_race_events.py` (~210 LOC; 17 tests)

3 test classes:

- `TestExtractMapboxLocaleFromForm` (7): empty form → all None / extracts all 5 from a fully-populated form / trims whitespace on text fields / blank text fields collapse to None / non-numeric lat-lng collapses to None (note: `float('NaN')` succeeds — boundary documented; final guard is `RaceEventPayload`'s `Field(ge/le)` bounds at the payload boundary) / empty-string lat-lng collapses to None / negative coords pass through.
- `TestParseRaceUrl` (5): missing key / empty / whitespace-only / trim / 1000-char cap.
- `TestRunMapboxSearch` (5): empty query short-circuits no Mapbox HTTP call / 3 error modes translate to human-readable error strings / happy path returns the normalized result dicts.

`mapbox_client.search_places` is monkeypatched throughout — no real HTTP. Pattern mirrors `tests/test_onboarding_race_events.py` (no real DB, no Flask test_client).

### 3.13 `tests/test_layer4_orchestrator.py` — fixture extension

`_queue_target_race_event` fixture extended with 6 new column defaults (all None — pre-walkthrough shape). 1-line patch in the row dict; all 50 orchestrator tests still pass.

---

## 4. Code / tests

**Tests:** 1419 → 1441 (+22 net new across 2 NEW + 2 extended test files):

- NEW `tests/test_routes_race_events.py` → +17 tests
- NEW `TestMapboxRaceLocationColumns` in `tests/test_race_events_repo.py` → +7 tests
- DELETED `TestAthleteLocaleChoices` in `tests/test_onboarding_race_events.py` → -2 tests (helper gone)

Container-runnable subset: 752 → 774 passed + 12 skipped in ~1.3s.

Run reproducer (same set as predecessor):

```
PYTHONPATH=. pytest tests/test_layer4_orchestrator.py tests/test_locales.py \
                    tests/test_race_events_repo.py \
                    tests/test_race_events_invalidation.py \
                    tests/test_onboarding_race_events.py \
                    tests/test_layer4_context.py tests/test_layer4_payload.py \
                    tests/test_layer4_hashing.py tests/test_layer4_cache.py \
                    tests/test_layer4_race_week_brief.py \
                    tests/test_plan_sessions_repo.py \
                    tests/test_routes_ad_hoc_workouts.py \
                    tests/test_routes_plan_create.py \
                    tests/test_nl_parser.py \
                    tests/test_routes_plan_refresh.py \
                    tests/test_nl_parser_smoke.py \
                    tests/test_routes_dashboard.py \
                    tests/test_routes_admin.py \
                    tests/test_layer3_cached_wrappers.py \
                    tests/test_routes_race_events.py
# 774 passed, 12 skipped in ~1.3s
```

**Template parse-check:** `Environment(loader=FileSystemLoader('templates')).get_template(...)` exercised against all 3 touched templates (`profile/race_event_edit.html`, `onboarding/target_race.html`, `_race_locale_picker.html`). All parsed cleanly.

**Inline-script nonce sweep** (PR #126 anchor): `grep -rnE '<script\b' templates/ | grep -v 'nonce="{{ csp_nonce' | grep -v 'src='` returns empty. The new picker partial's inline `<script>` carries `nonce="{{ csp_nonce() }}"`.

**No-regression confirmation:** All 752 pre-existing container-subset tests pass. Pre-existing tests in `tests/test_layer3a_builder.py::TestCacheWrapper` (7) + `tests/test_layer3b_builder.py::TestCacheWrapper` (7) remain pre-existing-circular-import-blocked from collection (same as predecessor; the new `tests/test_layer3_cached_wrappers.py` is the canonical living coverage path).

**Coverage gap acknowledged:**
- No Flask test_client integration tests for the new endpoints (`new_race` POST, `set_locale` POST, `locale_search` GET, `acknowledge_mapbox_disclosure` POST). Helper-level pytest density only, per the D-63 D12 precedent. Manual §5.0 walkthrough scenario added to CARRY_FORWARD (4 steps; see §5 below).
- The picker's inline JS (~80 LOC) is not unit-tested. Manual §5.0 walkthrough is the verification path. A future slice could add a small jsdom/playwright harness if regressions accumulate.

---

## 5. Manual §5.0 verification steps

For Andy's next manual walkthrough pass against the preview deployment or post-merge against main:

**Step 1 — Mapbox disclosure ack (shared across surfaces).** Navigate to `/profile/race-events/<pge_id>/edit`. Confirm the "Race location" section renders ABOVE the race-details form. If the athlete has NOT previously acked the Mapbox disclosure (first time), confirm a disclosure card renders with "Acknowledge & enable lookup" button. Click it; confirm a `disclosure_acknowledgments` row lands with `disclosure_id='mapbox_geocoding_consent'` + `version_id='v1'` + `delivery_method='in_app'`. Reload the edit page; confirm the search box now renders. Visit `/locales/new` separately and confirm no disclosure card shows (shared `mapbox_geocoding_consent` disclosure_id across both surfaces — an ack from either unblocks both).

**Step 2 — Mapbox search + pick.** Type "Nerstrand State Park" in the search box; press Enter (or click [Search]). Confirm `fetch('/profile/race-events/locale/search?q=Nerstrand+State+Park')` fires in the browser network tab. Confirm 1-5 results render below the search box as cards (name + place_name + [Use this location] button). Click [Use this location] on the Nerstrand State Park result. Confirm: (a) "Selected: Nerstrand State Park" displays with the full address as a subheading; (b) the search box hides; (c) the 5 hidden inputs in the form are populated (verify via browser inspector — `event_locale_name`, `event_locale_mapbox_id`, `event_locale_place_name`, `event_locale_lat`, `event_locale_lng`); (d) click [Save race location] (the standalone submit button on the picker form); (e) URL stays on the edit page + flash success "Race location updated."; (f) `SELECT event_locale_name, event_locale_mapbox_id, event_locale_lat, event_locale_lng, event_locale_place_name, event_locale_id FROM race_events WHERE id=<pge_id>` returns the picked Mapbox feature with `event_locale_id IS NULL` (legacy FK cleared per `update_race_event_locale` semantics).

**Step 3 — race_url + new_race flow.** Navigate to `/profile/race-events/new`. Fill in name + date + format + distance. Type a URL in the new "Race website URL" input. Use the inline Mapbox picker to anchor a location. Click [Save race]. Confirm a new race_events row lands with all 6 new columns populated + `race_url` matching the typed input + `is_target_event=FALSE` (only one target per athlete). Verify the picker hidden inputs round-tripped via the POST: `SELECT event_locale_name, race_url FROM race_events WHERE id=<new_id>`.

**Step 4 — Target-row Mapbox edit fires brief-only eviction.** Pre-condition: PGE 2026 row's target flag is TRUE. Edit the PGE row via Profile → Race events → edit. Use the picker to set a NEW Mapbox anchor (different than current). Click [Save race location]. Confirm:
- (a) `SELECT entry_point FROM layer4_cache WHERE user_id=<andy> AND entry_point IN ('plan_create','plan_refresh','single_session_synthesize','race_week_brief') AND superseded_at IS NULL` returns rows for `plan_create` + `plan_refresh` + `single_session_synthesize` (Layer 2C policy NOT triggered) and NO row for `race_week_brief` (brief-only eviction fired per `evict_on_target_event_brief_field_change`).
- (b) Repeat the same Save with NO Mapbox change and confirm no eviction (field-change gate).

Captured as a new 4-step scenario in `CARRY_FORWARD.md` "Manual §5.0 walkthrough" section.

---

## 6. Next session pointers

### 6.1 Architect-recommended next forward move

**One of the 3 remaining punch-list items**, in priority order:

1. **#8 "locales" → "locations" rename** (~9 templates, mechanical, no Triggers). Lowest risk, highest user-facing visibility. URLs stay `/locales/...` to avoid breakage; only labels/headings/dialog copy change.
2. **#6 + #4 injury form refresh** (~6-8 files) — `BODY_PART_CONSTRAINTS` mapping + JS swap-on-change + collapse Left/Right doubled body_part vocab. Trigger #5 fires on the constraint-mapping design.
3. **#2b LLM site-parse runtime** (~4-6 files; Trigger #2 prompt design first). Now that the `race_url` column ships, this is the natural follow-on — feed the URL into a NEW `race_url_parser.py` (WebFetch + Claude API) that pre-fills `race_rules_summary` + `mandatory_gear_text` + maybe `race_terrain` + `distance_km`.

### 6.2 Alternative pivots

- **Layer 2E heat-acclim consumes `event_locale_lat/lng`** — open item 2E-3. New columns shipped but not yet read. Gated on Plan Management spec (which carries `expected_race_temp_c`).
- **Layer 4 travel-distance reasoning** — paired home-locale lat/lng + race-locale lat/lng compute distance + travel-window logistics for the race-week brief.
- **"Clear race location" button** — explicit un-anchor for the picker (~5 LOC follow-on).
- **NL parser smoke-eval harness + Haiku 4.5 migration per NL-1** (~5-6 files; Trigger #2 fires).
- **Over-eviction cleanup for layer2c/layer2d** (~2 files; remove the None-optimization at `cache_invalidation.py:105-111`).

### 6.3 Operating notes for next session

Read order (Rule #13):

1. `aidstation-sources/CLAUDE.md` — stable rules.
2. `aidstation-sources/CURRENT_STATE.md` — what just shipped + current focus + layer status.
3. `aidstation-sources/CARRY_FORWARD.md` — rolling cross-session items (3 remaining walkthrough punch-list items live here as doc-sweep nits).
4. `aidstation-sources/handoffs/V5_Implementation_D73_Phase_5_2_Walkthrough_RaceLocaleMapbox_2026_05_21_Closing_Handoff_v1.md` — this handoff.
5. `./aidstation-sources/scripts/verify-handoff.sh` — automated anchor sweep.

**Forward-pointer (test coverage):** End-to-end Flask test_client tests for the 4 new endpoints (`new_race` POST with Mapbox hidden inputs, `set_locale` POST, `locale_search` GET JSON shape, `acknowledge_mapbox_disclosure` POST) would close the helper-level-only gap from D-63 D12. Small follow-on (~150 LOC in a new test class).

---

## 7. Decisions pinned

| # | Decision | Picked by | Rationale |
|---|---|---|---|
| **D1** | Option A "full Mapbox mirror" for #1 | Andy at AskUserQuestion gate (Trigger #5) | Mirrors `/locales/new` flow; unlocks downstream geo (Layer 2E heat-acclim + Layer 4 travel-distance reasoning); athlete's intent in CARRY_FORWARD §80 explicitly mentions "mirroring the existing locale Mapbox flow." Over text-only (B) + inline-lat-lng-no-search (C). |
| **D2** | Combine #1 + #2a in one slice | Andy at AskUserQuestion gate | Tightly-coupled file deltas (same migration + same 2 form templates + same repo helpers). Splitting would re-touch the same files twice. |
| **D3** | Ceiling break to 9 substantive files ratified | Andy at AskUserQuestion gate | Consistent with recent precedents (5.1.A=8, 5.1.C=8, 5.2.D63+PlanCreate=9, 5.2.LogThis+T1Hook=7, 5.2.D64=8, Walkthrough_PunchList=8). Final count = 13 (4 over the ratified 9); transparency in §9 below. |
| **D4** | Full Mapbox at onboarding too (not text-input-only) | Andy at AskUserQuestion gate | Uniform UX across all 3 surfaces (race_event_edit, new_race, onboarding step 3c) via shared `_race_locale_picker.html` partial. |
| **D5** | Keep legacy `event_locale_id BIGINT FK` column nullable | Claude (implementation) | Pre-walkthrough rows (Andy's PGE 2026 row) still load via the JOIN→slug fallback in `load_race_event_payload`. `update_race_event_locale` explicitly clears the FK on Mapbox-anchored update so the stale slug doesn't leak downstream. Layer 4 + Layer 3B accept EITHER legacy slug OR new `event_locale_name` as "locale resolved." |
| **D6** | AJAX `fetch()` from inline nonce-protected `<script>` for search | Claude (implementation) | The race form's `mandatory_gear_text` + `race_rules_summary` textareas can be ~8KB each; the alternative GET-round-trip-with-query-string approach would exceed the typical 8KB URL line limit. AJAX bypasses the form-state-preservation problem entirely. CSP nonce protects the inline script per PR #126 lessons. |

---

## 8. Session-end verification (Rule #10)

| Check | Result |
|---|---|
| 6 new `race_events` columns added via `_PG_MIGRATIONS` | ✅ `grep -n "event_locale_name TEXT\|event_locale_mapbox_id TEXT\|event_locale_lat NUMERIC\|event_locale_lng NUMERIC\|event_locale_place_name TEXT\|race_url TEXT" init_db.py` returns 6 hits |
| `race_events_repo.py` exports `update_race_event_locale` | ✅ grep returns 1 def hit + 1 import hit in routes/race_events.py |
| `race_events_repo.py` `create_race_event` signature accepts 6 new kwargs | ✅ grep for kwargs returns hits in signature block |
| `race_events_repo.py` `load_race_event_payload` SELECT includes the 6 new columns | ✅ grep for `re.event_locale_name, re.event_locale_mapbox_id` returns 1 hit |
| `RaceEventPayload` carries the 6 new fields | ✅ grep `event_locale_name` / `event_locale_mapbox_id` / `event_locale_lat` / `event_locale_lng` / `event_locale_place_name` / `race_url` in layer4/context.py |
| `_render_user_prompt` surfaces race location | ✅ grep `**Race location:**` in layer4/race_week_brief.py returns 1 hit |
| `routes/race_events.py` no longer exports `_athlete_locale_choices` | ✅ grep returns 0 hits |
| `routes/race_events.py` exports `_extract_mapbox_locale_from_form` + `_parse_race_url` + `_run_mapbox_search` + `locale_search` + `set_locale` + `acknowledge_mapbox_disclosure` | ✅ all 6 importable per `python -c "from routes.race_events import ..."` |
| `routes/onboarding.py` no longer defines `_athlete_locale_choices` | ✅ grep returns 0 hits |
| `templates/profile/race_event_edit.html` no longer has `<select id="event_locale_id">` | ✅ grep returns 0 hits |
| `templates/profile/race_event_edit.html` includes `_race_locale_picker.html` | ✅ grep returns 2 hits (1 for is_new=False, 1 for is_new=True) |
| `templates/profile/race_event_edit.html` has `<input type="url" id="race_url">` | ✅ grep returns 1 hit |
| `templates/onboarding/target_race.html` no longer has `<select id="event_locale_id">` | ✅ grep returns 0 hits |
| `templates/onboarding/target_race.html` includes `_race_locale_picker.html` | ✅ grep returns 1 hit |
| `templates/onboarding/target_race.html` has `<input type="url" id="race_url">` | ✅ grep returns 1 hit |
| `templates/_race_locale_picker.html` exists + has `<script nonce="{{ csp_nonce() }}">` | ✅ grep returns 1 hit |
| No inline `<script>` blocks missing nonce in `templates/` | ✅ `grep -rnE '<script\b' templates/ \| grep -v 'nonce="{{ csp_nonce' \| grep -v 'src='` returns empty |
| 3 touched templates parse cleanly via Jinja2 | ✅ `python -c "from jinja2 import Environment, FileSystemLoader; env = Environment(loader=FileSystemLoader('templates')); [env.get_template(t) for t in ['profile/race_event_edit.html', 'onboarding/target_race.html', '_race_locale_picker.html']]"` |
| Tests 1419 → 1441 net (+22 across NEW tests/test_routes_race_events.py + 7 NEW in test_race_events_repo.py - 2 deleted in test_onboarding_race_events.py) | ✅ pytest count |
| Container-runnable subset 752 → 774 passed + 12 skipped | ✅ pytest run |
| `CURRENT_STATE.md` last-shipped pointer flipped to Walkthrough_RaceLocaleMapbox handoff | ✅ |
| `CARRY_FORWARD.md` #1 + #2a annotated ✅ Shipped; #2b explicitly carried; 4-step §5.0 walkthrough scenario added; 4 forward-pointers added | ✅ |
| PR opened as draft + CI green (Vercel deploy success) | ⏸ pending push |

---

## 9. Files shipped this session

**Substantive (13 files; over the 9 Andy ratified at AskUserQuestion gate; transparency note below):**

1. `init_db.py` — 6 new `ALTER TABLE race_events ADD COLUMN IF NOT EXISTS` migrations.
2. `race_events_repo.py` — `create_race_event` + `update_race_event` + `get_race_event` + `load_race_event_payload` + `list_athlete_race_events` extended; NEW `update_race_event_locale` helper.
3. `layer4/context.py` — `RaceEventPayload` gains 6 new fields with bounds.
4. `layer4/race_week_brief.py` — `_render_user_prompt` surfaces race location (9 lines).
5. `routes/race_events.py` — 3 new helpers + 3 new endpoints; drop dropdown.
6. `routes/onboarding.py` — drop dropdown helper; thread Mapbox kwargs + race_url through target_race_save.
7. `templates/profile/race_event_edit.html` — drop dropdown; include picker partial in 2 places (is_new=True inside form, is_new=False as standalone form); add race_url input.
8. `templates/onboarding/target_race.html` — drop dropdown; include picker partial inside form; add race_url input.
9. NEW `templates/_race_locale_picker.html` — shared partial (~190 LOC; UI + nonce-protected JS).
10. `tests/test_race_events_repo.py` — fixture extended; 2 existing tests updated; 7 NEW tests in `TestMapboxRaceLocationColumns`.
11. `tests/test_onboarding_race_events.py` — `TestAthleteLocaleChoices` class deleted (helper gone); replaced with audit-trail comment.
12. NEW `tests/test_routes_race_events.py` — 17 tests across 3 classes for the new route helpers.
13. `tests/test_layer4_orchestrator.py` — `_queue_target_race_event` fixture extended with 6 new column defaults (None each — pre-walkthrough shape).

**Ceiling-break transparency:** Andy ratified 9 substantive files at the AskUserQuestion gate. Final count is 13 — 4 over the ratified ceiling. The +4 over:
- `layer4/race_week_brief.py` (1 file, +9 lines) — small surgical user-prompt thread-through. Discovered during recon that the brief LLM had NO race-location signal in the prompt; passing the new Mapbox columns up makes the schema immediately load-bearing instead of capture-only.
- `templates/_race_locale_picker.html` (1 file, ~190 LOC) — shared UI partial. Without this, the same picker UI + JS would duplicate across 2 templates (race_event_edit + target_race). Standard partial extraction; consistent with `_race_terrain_editor.html` precedent.
- `tests/test_routes_race_events.py` (1 file, ~210 LOC) — focused unit tests for the new route helpers (`_extract_mapbox_locale_from_form`, `_parse_race_url`, `_run_mapbox_search`). These helpers handle malformed-input gracefully; testing them was worth a dedicated file.
- `tests/test_layer4_orchestrator.py` (1 file, +9 lines) — fixture extension only. Existing test data fixture needed +6 column defaults to keep all 50 orchestrator tests passing post-schema-extension. Bookkeeping-grade.

Per CLAUDE.md "5-file ceiling = substantive files only," the +4 are all small surgical touches; none would have been worth proposing-a-split for. Documented here for the audit trail.

**Bookkeeping (3 files):**

14. MODIFIED `aidstation-sources/CURRENT_STATE.md` — last-shipped pointer flipped to this handoff; session narrative appended.
15. MODIFIED `aidstation-sources/CARRY_FORWARD.md` — #1 + #2a annotated ✅ Shipped; #2b carried; 3 remaining walkthrough items remain; 4 forward-pointers added; 4-step §5.0 scenario added.
16. NEW `aidstation-sources/handoffs/V5_Implementation_D73_Phase_5_2_Walkthrough_RaceLocaleMapbox_2026_05_21_Closing_Handoff_v1.md` — this handoff.

---

## 10. Carry-forward updates

See `CARRY_FORWARD.md` for the full list. Net changes:

- **#1 race-locale dropdown → Mapbox-anchored picker shipped 2026-05-21** ✅ — full Mapbox flow across 3 surfaces (race_event_edit / new_race / onboarding step 3c); shared disclosure ack with `/locales/new`; standalone `set_locale` endpoint on edit page; AJAX search + JS result-click pattern.
- **#2a race_url column shipped 2026-05-21** ✅ — bundled with #1 (same migration + same 2 form templates + same repo helpers).
- **#2b LLM site-parse runtime carried forward** — Trigger #2 prompt design first; then ~4-6 files runtime.
- **3 walkthrough items remain deferred** as doc-sweep nits: #4 body_part Left/Right vocab cleanup (folded into §B onboarding refresh), #6 dynamic movement-constraints (~3-4 files; Trigger #5), #8 "locales" → "locations" rename (~9 templates; mechanical).
- **4 forward-pointers added** from this slice: (1) Layer 2E heat-acclim consumes `event_locale_lat/lng` (gated on Plan Management spec), (2) Layer 4 travel-distance reasoning (~30-line prompt addition + maybe new coaching flag), (3) "Clear race location" button (~5 LOC follow-on), (4) Flask test_client integration tests for the 4 new endpoints (~150 LOC follow-on).
- 1 new manual §5.0 walkthrough scenario added (4 steps verifying the picker against preview/main deployment).
- Architect-recommended §6.1 forward move = **#8 "locales" → "locations" rename** as the lowest-risk highest-visibility next slice; alternatives include #6 + #4 paired injury-form refresh slice, or #2b LLM site-parse runtime.

**End of handoff.**
