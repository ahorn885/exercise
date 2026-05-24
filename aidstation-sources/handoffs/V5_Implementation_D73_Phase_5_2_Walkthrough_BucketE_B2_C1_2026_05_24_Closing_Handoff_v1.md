# D-73 Phase 5.2 Walkthrough — Bucket E.(b)-B2 + E.(c)-C1 Follow-on Slice — Closing Handoff

**Session:** D-73 Phase 5.2 caller-side — picks up the §6.2 alt-pivot menu from the predecessor WaterVocabExpansion slice. Closes the deferred-from-BucketE_TerrainNone_FrameworkSport-R3-split follow-on end-to-end via NEW `race_events.included_discipline_ids TEXT[]` column + `discipline_id_filter` post-filter on Layer 2A + per-row `RaceTerrainEntry.discipline_id` for C1 + B2 Bootstrap checkbox grid with inline CSP-nonced JS rebind on framework_sport input change. Closes Bucket E end-to-end (a/b/c all shipped).
**Date:** 2026-05-24
**Predecessor handoff:** `V5_Implementation_D73_Phase_5_2_Walkthrough_WaterVocabExpansion_2026_05_24_Closing_Handoff_v1.md`
**Branch:** `claude/eager-babbage-Oz12k` (harness-pinned; matches Bucket-E-B2+C1 scope so no rename per CLAUDE.md branch-naming rule)
**Status:** 11 substantive code/template files + 5 test files (ceiling break ratified at AskUserQuestion gate). Container-runnable subset 859 → 889 (+30 net new). ETL `etl/tests/` 139 → 139 unchanged. No regressions.

---

## 1. Session-start verification (Rule #9)

Read order completed per Rule #13: CLAUDE.md → CURRENT_STATE.md → CARRY_FORWARD.md → predecessor WaterVocabExpansion handoff → `./aidstation-sources/scripts/verify-handoff.sh`. Anchor sweep ✅ clean — the 4 ❌ entries on `tests/test_extractor_parsers.py` / `tests/test_sum_to_100.py` / `tests/test_v10_parsers.py` / `tests/test_vocabulary_md.py` are the known false-positives (those files live under `etl/tests/`, not `tests/`; the script doesn't know about the nested test tree). Working tree clean on the harness-pinned branch; predecessor §8 anchors spot-checked (17-row terrain vocab confirmed; TRN-017 + Ocean / Tidal rename intact; 2 new gap rules in `populate_terrain_gap_rules.sql`; TF-015 extension; `TestWaterRowExpansion` 6 tests). 853 → 859 baseline + 139 ETL confirmed. No drift between predecessor handoff narrative and on-disk state.

Andy picked **Bucket E.(b)-B2 + E.(c)-C1 follow-on** at the first AskUserQuestion gate over: #8 locales→locations rename / Bucket C (l) skill-capability toggles / Bucket C (i) Mapbox-required.

---

## 2. Session narrative

The CARRY_FORWARD entry (line 108) pre-spec'd the contract from the BucketE_TerrainNone_FrameworkSport R3 split:

- **B2:** `race_events.included_discipline_ids TEXT[] NULL` + `RaceEventPayload.included_discipline_ids` + `discipline_id_filter: list[str] | None = None` kwarg on `q_layer2a_discipline_classifier_payload` that post-filters the bridge SELECT result against the explicit ID list. Form UI was open (CARRY_FORWARD mentioned `<select multiple>` as a sketch, not a ratification).
- **C1:** `RaceTerrainEntry.discipline_id: str | None = None` field; per-row `<select>` in `_race_terrain_editor.html` keyed on B2's discipline list; Layer 2B passes through without behavior change (per-discipline gap reasoning carries as Trigger #1).

The plan-mode gate ratified 4 open design choices via AskUserQuestion:

| # | Question | Andy's pick | Notes |
|---|---|---|---|
| Q1 | Ceiling break to ~12 files? | **Yes — ship as one slice** | Contract pre-spec'd; cognitive load per file is low. Precedent: BucketE_TerrainNone_FrameworkSport=10, RaceLocaleMapbox=13. |
| Q2 | B2 form UX pattern? | **Bootstrap checkbox grid** | 3-col grid (`col-md-6 col-lg-4`) mirroring `/locales/<slug>/edit` precedent. Best for typical-sport 7-12 disciplines; accessible without JS. |
| Q3 | framework_sport ↔ included_discipline_ids interaction? | **Auto-clear with flash message** | Avoid the UI/runtime mismatch silently-drop alternative. Forces re-pick from new sport's valid set. |
| Q4 | Discipline-list refresh on framework_sport change? | **Client-side JS fetch** (Andy's pick over my server-side save-and-reload recommendation) | Better UX; justifies the inline JS surface + JSON endpoint with CSP nonce per PR #126 lessons. |

**Order of work** (locked by C1 depending on B2's discipline-list query for form population):

1. Schema + payload models (init_db, layer4/context)
2. Repo layer (race_events_repo)
3. Layer 2A builder (discipline_id_filter post-filter)
4. Orchestrator threading
5. Eviction helper
6. Routes + JSON endpoint + form parsing + auto-clear
7. Templates + inline JS (CSP-nonced)
8. Tests across 5 files

**Derisk grep results before code:**

- `framework_sport` precedent intact across all 8 of {init_db / context / repo / invalidation / builder / orchestrator / routes / onboarding} — mirror exactly.
- `_race_terrain_editor.html` is shared between race-event-edit + onboarding/target-race; the partial's `entry.X` attribute access on dict items relies on Jinja's permissive Undefined semantics. For backward-compat: pre-C1 race_terrain JSONB rows have no `discipline_id` key; Jinja `entry.discipline_id` evaluates to Undefined → comparison `dc.id == Undefined` is False → no checkbox marks as selected (graceful default).
- `layer0.sport_discipline_bridge` directly maps `framework_sport → discipline_id, discipline_name` — the canonical source for the form's discipline checkbox grid. Layer 2A's `_load_disciplines` uses `sport_discipline_map` with `top_level_sport` (after `_strip_sub_format`), but the bridge is the right surface for the form (no sub-format unpacking needed; the bridge already knows about "Triathlon (Standard / Olympic)" vs "Triathlon (Sprint)").

---

## 3. File-by-file edits

### 3.1 `init_db.py` — `race_events.included_discipline_ids TEXT[]` migration

Appended after the framework_sport ADD COLUMN at line 1193, with a comment block explaining the column's role + the auto-clear policy.

### 3.2 `layer4/context.py` — both pydantic model extensions

- **`RaceTerrainEntry`** — gains `discipline_id: str | None = None` after `pct_of_race`. Comment cites Layer 2B pass-through and Trigger #1 future-work pointer.
- **`RaceEventPayload`** — gains `included_discipline_ids: list[str] | None = None` after `framework_sport`. Comment cites Layer 2A post-filter semantics + auto-clear policy.

### 3.3 `race_events_repo.py` — load + storage threading

- `load_race_event_payload` SELECT extended with `re.included_discipline_ids`. Raw value defensively coerced to list when non-list iterable (psycopg2 array adapter may surface as tuple under some shapes). `RaceTerrainEntry` construction extended to read `entry.get("discipline_id")` (graceful default to None for pre-C1 rows).
- `get_race_event` SELECT extended; result dict gets the same defensive list-coerce.
- `create_race_event` signature kwarg added after `framework_sport`; INSERT column list extended; VALUES placeholder uses `?::text[]` cast (defensive against psycopg2 array-adapter drift, matching the locale_terrain_ids precedent); params tuple threads the value.
- `update_race_event` signature kwarg added; UPDATE SET clause extended with `included_discipline_ids = ?::text[]`; params tuple threads the value.

### 3.4 `race_events_invalidation.py` — NEW `evict_on_target_event_included_discipline_ids_change`

Mirrors `evict_on_target_event_framework_sport_change` exactly — routes through `layer2a` policy (same widest cut as framework_sport since both reshape Layer 2A's discipline output). Docstring explicit on the rationale.

### 3.5 `layer2a/builder.py` — `discipline_id_filter` post-filter

`q_layer2a_discipline_classifier_payload` gains keyword arg `discipline_id_filter: list[str] | None = None` (placed before `etl_version_set`). Immediately after `raw_rows = _load_disciplines(...)`, if `discipline_id_filter is not None`, the function prunes `raw_rows` to only rows whose `discipline_id` is in the explicit set. The post-filter preserves rationale + phase_load + training_gap on surviving rows (the filter is a list comprehension over the existing SELECT result; it doesn't re-query or strip metadata). Empty list (`[]`) behaves as "explicit no disciplines" — hits the existing unresolved-sport edge case with `hitl_required=True`; the route layer collapses empty form selections to None to avoid this path being reached via UI.

### 3.6 `layer4/orchestrator.py` — `_upstream_full_cone` threading

Adds 1 new variable `discipline_id_filter` resolved from `target_race_event.included_discipline_ids` (None when no target race). Threaded into `q_layer2a_discipline_classifier_payload(..., discipline_id_filter=...)`. Comment explicit on the auto-clear-on-framework-sport-change invariant so the filter never references stale IDs.

### 3.7 `routes/race_events.py` — helpers + JSON endpoint + form integration

- **NEW `_parse_discipline_id_filter(form)`** — calls `form.getlist('included_discipline_ids')` (Flask MultiDict semantic); strips whitespace + drops blanks; returns None when no boxes checked.
- **NEW `_disciplines_for_framework_sport(db, framework_sport)`** — queries `layer0.sport_discipline_bridge WHERE framework_sport = ? AND superseded_at IS NULL ORDER BY discipline_id`; returns `[{id, label}, ...]` list (mirrors `_terrain_choices` shape). Empty string / None framework_sport short-circuits to `[]`.
- **NEW `_resolve_effective_framework_sport(db, user_id, race)`** — race override → athlete `primary_sport` fallback. Mirrors the orchestrator's resolution order so the form's initial render matches what Layer 2A would see if the athlete saved immediately.
- **NEW `disciplines_search` JSON endpoint** at `/profile/race-events/disciplines/search?framework_sport=...` — returns `{framework_sport, results: [{id, label}, ...]}`. Auth-gated via `current_user_id()` (re-uses session boundary; no data exposure beyond what the bridge contains). Empty framework_sport returns empty results — the JS swaps to a "No disciplines available" hint.
- **`_parse_race_terrain` extended** for per-row `discipline_id` — regex pattern + per-index reader extended; blank value parses to None (C1 race-wide default).
- **`new_race` POST** — `create_race_event(..., included_discipline_ids=_parse_discipline_id_filter(request.form))`.
- **`update_race` POST** — parses `included_discipline_ids`; auto-clear logic when `prior_framework_sport != new_framework_sport` AND `prior_included_discipline_ids` is non-NULL (sets `new_discipline_filter = None` + flashes "Sport override changed — your discipline picks were cleared. Re-select them for the new sport."); thread into `update_race_event`. Eviction wiring: NEW `discipline_filter_changed` branch after `framework_sport_changed`, before `periodization_changed` (same `layer2a` policy as framework_sport; subsumed when framework_sport itself is what's changing).
- **`new_race` + `edit_race` GET handlers** — both compute `initial_framework_sport` via `_resolve_effective_framework_sport` + `discipline_choices` via `_disciplines_for_framework_sport`, thread both to the template via `render_template(...)`.
- **Imports** — added `get_athlete_profile` from `athlete` for the resolver; added `evict_on_target_event_included_discipline_ids_change` from `race_events_invalidation`.

### 3.8 `routes/onboarding.py` — mirror

- `_parse_race_terrain` extended (mirrors race_events) for per-row `discipline_id`.
- NEW `_parse_discipline_id_filter(form)` (mirrors race_events; uses same `form.getlist` pattern; cross-references the race_events helper in docstring).
- `_get_target_race_row` SELECT extended with `included_discipline_ids`; defensive list-coerce mirrors the repo pattern.
- `target_race` GET imports `_resolve_effective_framework_sport` + `_disciplines_for_framework_sport` from `routes.race_events` (re-use; the helpers are idempotent over a db handle + user_id). Threads `discipline_choices` + `initial_framework_sport` into the template.
- `target_race_save` POST adds auto-clear (UPDATE branch only — the new-target CREATE branch has no prior selection to invalidate) + eviction wiring (NEW `discipline_filter_changed` branch).
- Import: `evict_on_target_event_included_discipline_ids_change` added.

### 3.9 `templates/_race_terrain_editor.html` — C1 per-row discipline `<select>`

Row layout restructured from `col-md-7 / col-md-3 / col-md-2` to `col-md-5 / col-md-2 / col-md-3 / col-md-2` for terrain / pct / discipline / remove. New per-row `<select data-discipline-select="1">` with `<option value="">Race-wide</option>` as the empty default; rest of the options come from `discipline_choices` context var (each option labeled `"D-NNN — Discipline Name"`). The hidden `<template id="race-terrain-template">` mirror gets the same column. Existing add/remove JS handles the new column unchanged via the `__IDX__` template — no JS edits needed in the partial itself (the rebind logic lives in the parent templates' inline JS picker).

### 3.10 `templates/profile/race_event_edit.html` — B2 checkbox grid + inline JS

- New `<div id="discipline-grid">` block between the framework_sport input and the race_rules_summary textarea. Renders a Bootstrap 3-col grid (`col-md-6 col-lg-4`) of `<input type="checkbox" name="included_discipline_ids" value="D-NNN">` keyed on `discipline_choices`; `checked` when the ID is in `race.included_discipline_ids` (graceful no-op when the race has None / no race exists). Empty state copy via `data-empty-text` attr.
- Inline `<script nonce="{{ csp_nonce() }}">` block at the end of the content block — debounces `framework_sport` input changes (350ms) + fetches `/profile/race-events/disciplines/search?framework_sport=...` + rebinds BOTH the checkbox grid AND every `[data-discipline-select]` per-row terrain select. Preserves previously-checked/selected IDs that survive the new bridge set. Uses minimal `htmlEscape` helper for the dynamic insert. Network/parse errors silently leave the existing grid alone.

### 3.11 `templates/onboarding/target_race.html` — mirror

Identical B2 checkbox grid block (added after the framework_sport input; tied to `target.included_discipline_ids` instead of `race.included_discipline_ids`). Identical inline JS picker at the end of the template (between the skip form and `{% endblock %}`).

### 3.12 `tests/test_race_events_repo.py` — `TestIncludedDisciplineIdsOverride`

8 NEW tests + `_race_row` helper extended with `"included_discipline_ids": None` default:
1. `test_load_payload_populates_included_discipline_ids_when_present`
2. `test_load_payload_defaults_included_discipline_ids_to_none`
3. `test_load_payload_coerces_non_list_iterable_to_list` — psycopg2 tuple adapter path
4. `test_create_passes_included_discipline_ids_kwarg` — SQL contains the column + `?::text[]` cast + list in params
5. `test_create_defaults_included_discipline_ids_to_none`
6. `test_update_passes_included_discipline_ids_kwarg`
7. `test_update_can_clear_included_discipline_ids`

### 3.13 `tests/test_race_events_invalidation.py` — `TestIncludedDisciplineIdsChange`

3 NEW tests covering the eviction helper:
1. `test_evicts_all_four_entry_points` — count == 4
2. `test_scoped_to_user` — cross-user isolation
3. `test_metrics_tagged_with_layer2a` — `cache.metrics.evictions_per_layer["layer2a"] == 4`

### 3.14 `tests/test_layer4_orchestrator.py` — `TestIncludedDisciplineIdsOverride`

`_queue_target_race_event` extended with `included_discipline_ids: list[str] | None = None` kwarg; queued row dict gains the column. 2 NEW tests:
1. `test_filter_threads_to_layer2a_when_set` — Layer 2A mock's `discipline_id_filter` kwarg matches the race row's list
2. `test_filter_defaults_to_none_when_unset` — Layer 2A mock's `discipline_id_filter` kwarg is None

### 3.15 `tests/test_layer2a.py` — `TestDisciplineIdFilter`

5 NEW tests against `q_layer2a_discipline_classifier_payload` using the existing `_ar_rows` test substrate:
1. `test_none_filter_returns_full_bridge_list` — pre-B2 behavior (all 7 AR disciplines)
2. `test_subset_filter_narrows_disciplines` — `["D-001","D-013"]` → 2 disciplines with rationale + phase_load preserved
3. `test_empty_filter_returns_no_disciplines` — `[]` → empty + unresolved-sport flag fires
4. `test_filter_with_nonexistent_ids_silently_drops` — `["D-999"]` → empty (defensive)
5. `test_filter_preserves_phase_load_and_training_gap` — D-016 row's `training_gap` survives the post-filter

### 3.16 `tests/test_routes_race_events.py` — 4 NEW classes (13 tests)

NEW `_FakeMultiDict` + `_FakeConn` substrates added at the top. Classes:
- **TestParseDisciplineIdFilter** (4 tests): empty → None / returns checked subset / strips whitespace + drops blanks / missing-getlist → None
- **TestParseRaceTerrainDisciplineId** (3 tests): row with discipline_id threaded / blank discipline_id → None / missing field → None (backward-compat with pre-C1 forms)
- **TestDisciplinesForFrameworkSport** (2 tests): returns `{id, label}` dicts from bridge / empty framework_sport short-circuits
- **TestResolveEffectiveFrameworkSport** (4 tests, monkeypatched `get_athlete_profile`): race override wins / falls back to primary_sport / no race row uses profile / returns None when both unset

### 3.17 `tests/test_onboarding_race_events.py` — 3 in-place test updates

`test_parses_repeating_rows`, `test_drops_empty_terrain_id`, `test_preserves_sorted_order_across_sparse_indices` — all 3 had their expected dict literals extended with `'discipline_id': None` to match the C1-extended parser output.

---

## 4. Code / tests

**Tests:** container-runnable subset 859 → 889 (+30 net new: 8 + 3 + 2 + 5 + 13 - 1 modified-but-not-counted in onboarding tests = 30); ETL `etl/tests/` 139 → 139 unchanged. No regressions on Layer 4 / orchestrator / repo / race_events / locales / onboarding / plan_create / ad_hoc_workouts / plan_refresh / nl_parser / dashboard / admin / layer3 cached-wrappers / layer2a / layer2b surfaces; 12 NL parser smoke + 4 Layer 3 SDK smoke tests still skip cleanly when `ANTHROPIC_API_KEY` unset.

Reproducer (changed files only):

```
PYTHONPATH=. python -m pytest tests/test_race_events_repo.py \
  tests/test_race_events_invalidation.py tests/test_layer4_orchestrator.py \
  tests/test_layer2a.py tests/test_routes_race_events.py \
  tests/test_onboarding_race_events.py
# 282 passed in 1.18s
```

Full container subset (mirrors predecessor's exact invocation):

```
PYTHONPATH=. python -m pytest tests/test_layer4_orchestrator.py tests/test_locales.py \
  tests/test_race_events_repo.py tests/test_race_events_invalidation.py \
  tests/test_onboarding_race_events.py tests/test_layer4_context.py \
  tests/test_layer4_payload.py tests/test_layer4_hashing.py tests/test_layer4_cache.py \
  tests/test_layer4_race_week_brief.py tests/test_plan_sessions_repo.py \
  tests/test_routes_ad_hoc_workouts.py tests/test_routes_plan_create.py \
  tests/test_nl_parser.py tests/test_routes_plan_refresh.py tests/test_nl_parser_smoke.py \
  tests/test_routes_dashboard.py tests/test_routes_admin.py \
  tests/test_layer3_cached_wrappers.py tests/test_routes_race_events.py \
  tests/test_layer2a.py tests/test_layer2b.py tests/test_bucket_c_terrain_vocab_audit.py
# 889 passed, 12 skipped in 2.04s
```

ETL: `PYTHONPATH=. python -m pytest etl/tests/ # 139 passed in 0.43s`.

**py_compile:** all 8 edited Python files (init_db / layer4/context / layer4/orchestrator / race_events_repo / race_events_invalidation / layer2a/builder / routes/race_events / routes/onboarding) clean. All 5 edited test files clean.

**Jinja2 parse:** all 3 edited templates (`_race_terrain_editor.html` + `profile/race_event_edit.html` + `onboarding/target_race.html`) parse cleanly via `Environment(loader=FileSystemLoader('templates')).get_template(...)`.

---

## 5. Manual §5.0 verification — owed step

NEW 3-step walkthrough scenario added to CARRY_FORWARD §5.0 list. Summarized:

1. **B2 checkbox grid render + initial population** — confirm grid renders the AR bridge set keyed on Andy's effective framework_sport at `/profile/race-events/<pge_id>/edit` + `/onboarding/target-race`.
2. **JS rebind on framework_sport change** — edit framework_sport input; confirm grid rebinds within ~400ms; confirm per-row terrain discipline `<select>` rebinds; confirm network tab shows the `/disciplines/search` JSON call; bogus framework_sport renders the empty-state copy.
3. **B2 + C1 save + Layer 2A round-trip** — check D-001 + D-006 + D-013; pick D-006 on the TRN-017 row; save; verify Neon column populated + cache evicts on `layer2a` + Layer 2A narrows disciplines on next orchestrator run; then flip framework_sport to "Trail Running" + save; confirm flash + auto-clear to NULL + cache evicts again.

---

## 6. Next session pointers

### 6.1 Architect-recommended next forward move

**#8 "locales" → "locations" terminology rename** remains the lowest-risk next-slice candidate (carried forward through every recent handoff; ~9 templates, mechanical, no `/plan` triggers). Affected templates pinned at `CARRY_FORWARD.md` line 91.

### 6.2 Alternative pivots

- **Bucket C sub-item (l): skill-capability toggles** — Trigger #3 + Trigger #5 plan-mode gate. Defaults pre-pinned by Andy (assume-not-skilled; narrow vocab = climbing/whitewater/swim ability). ~6-8 substantive files.
- **Bucket C sub-item (i) Mapbox-anchored race-location required** — Trigger #5; closes Bucket C from a still-open perspective. ~3-4 files.
- **Bucket C sub-item (g) locale-terrain vs Outdoor-Terrain merge** — Trigger #3 cross-layer schema + #5 architectural alternatives. Plan-mode gate.
- **Layer 2B per-discipline gap reasoning (consume C1)** — Trigger #1 prompt-body update. Now unblocked since C1 ships the data shape; ~3-5 files including spec + prompt + tests.
- **#6 + #4 paired injury form refresh** — ~6-8 files; Trigger #5 on body-part-to-movement-constraints mapping.
- **#2b race-URL LLM site-parse pre-fill** — Trigger #2 prompt design session first; then ~4-6 files runtime.
- **§I.1 structured supplements onboarding refresh** — Layer 2E §5.5 de-stub. LARGE ~6-8 files; plan-mode gate required.

### 6.3 Operating notes for next session

Read order (Rule #13):

1. `aidstation-sources/CLAUDE.md` — stable rules.
2. `aidstation-sources/CURRENT_STATE.md` — what just shipped + current focus + layer status.
3. `aidstation-sources/CARRY_FORWARD.md` — rolling cross-session items (Bucket E.(b)-B2 + E.(c)-C1 line 108 flipped ✅; Bucket E now fully closed across (a)/(b)-B1+B2/(c)-C1).
4. `aidstation-sources/handoffs/V5_Implementation_D73_Phase_5_2_Walkthrough_BucketE_B2_C1_2026_05_24_Closing_Handoff_v1.md` — this handoff.
5. `./aidstation-sources/scripts/verify-handoff.sh` — automated anchor sweep. The script's 4 ❌ false-positives on ETL test files still present (script doesn't know about `etl/tests/`); verify via `ls etl/tests/`.

**No outstanding production warnings.** Bucket E: all 3 sub-items (a/b/c) closed end-to-end. Bucket C: 8 of 11 sub-items closed (a/b/c/d/e/f/h/j + k via earlier slices); 3 still open — (g) terrain↔equipment merge, (i) Mapbox-required, (l) skill toggles.

---

## 7. Decisions pinned

| # | Decision | Picked by | Rationale |
|---|---|---|---|
| **D1** | Ship as one slice (~12-file ceiling break) | Andy at AskUserQuestion gate | Over split-into-two-slices + B2-only-defer-C1. Contract pre-spec'd; cognitive load per file is low. Precedent: BucketE_TerrainNone_FrameworkSport=10, RaceLocaleMapbox=13. |
| **D2** | Bootstrap checkbox grid for B2 | Andy at gate | Over `<select multiple>` native (poor ctrl-click UX) + bootstrap-select 3rd-party JS lib (new CSP-nonce surface + dependency). The grid mirrors `/locales/<slug>/edit` terrain-grid precedent; accessible without JS; best for typical 7-12 disciplines. |
| **D3** | Auto-clear with flash message on framework_sport change | Andy at gate | Over silent-drop (creates UI/runtime mismatch) + hard-block-with-validation-error (worst UX). Auto-clear forces re-pick from new sport's valid set + the flash message tells the athlete exactly what happened. Only fires when prior selection was non-NULL — no spurious flash on already-empty rows. |
| **D4** | Client-side JS fetch on framework_sport input change | Andy at gate | Over server-side save-and-reload (my recommendation). Better UX justifies the inline JS surface + the new JSON endpoint. CSP nonce per PR #126 lessons. 350ms debounce keeps the network chatter bounded. |
| **D5** | Bridge query (not SDM via `_strip_sub_format`) for the form's discipline list | Architect at code-time | The bridge (`layer0.sport_discipline_bridge`) directly maps `framework_sport → discipline_id, discipline_name` for whatever the athlete typed (handles "Triathlon (Standard / Olympic)" vs "Triathlon (Sprint)" naturally). SDM is keyed on the stripped top-level sport; using it for the form would lose the sub-format distinction. Layer 2A's classifier still uses SDM internally (where the rationale + phase_load + training_gap columns live) — the form's view of the discipline set is the bridge's projection. |
| **D6** | Defensive `?::text[]` cast on INSERT/UPDATE | Architect at code-time | Mirrors the locale_terrain_ids precedent from Bucket B #3. Harmless when psycopg2's array adapter behaves correctly; decisive against adapter drift on production Neon. |
| **D7** | C1 backward-compat via Jinja Undefined semantics | Architect at code-time | Pre-C1 race_terrain JSONB rows have no `discipline_id` key. The template's `dc.id == entry.discipline_id` evaluates against Jinja Undefined (returns False) so no checkbox marks as selected — graceful default to "race-wide" for legacy rows. The repo hydration explicitly defaults `entry.get("discipline_id")` so the typed `RaceTerrainEntry` always has the field populated (None for pre-C1). |
| **D8** | Empty filter list semantically distinct from None at the Layer 2A boundary; route layer collapses to None | Architect at code-time | `discipline_id_filter=[]` is the explicit "no disciplines" case (hits the unresolved-sport edge case with `hitl_required=True`). The route layer's `_parse_discipline_id_filter` collapses an empty form selection to None so the UI path can't accidentally fire that edge case; direct caller use (e.g. tests) can still supply `[]` to exercise the empty path. |

---

## 8. Session-end verification (Rule #10)

| Check | Result |
|---|---|
| `race_events.included_discipline_ids TEXT[] NULL` ALTER TABLE present | ✅ `grep -n 'ADD COLUMN IF NOT EXISTS included_discipline_ids' init_db.py` returns hit |
| `RaceEventPayload.included_discipline_ids` field defined | ✅ `grep -n 'included_discipline_ids: list\[str\] \| None' layer4/context.py` returns hit |
| `RaceTerrainEntry.discipline_id` field defined | ✅ `grep -n 'discipline_id: str \| None' layer4/context.py` returns 1 hit on RaceTerrainEntry |
| `q_layer2a_discipline_classifier_payload` accepts `discipline_id_filter` | ✅ `grep -n 'discipline_id_filter' layer2a/builder.py` returns 3 hits (kwarg + post-filter + comment) |
| Orchestrator threads `discipline_id_filter` to Layer 2A | ✅ `grep -n 'discipline_id_filter' layer4/orchestrator.py` returns hit |
| NEW `evict_on_target_event_included_discipline_ids_change` helper | ✅ `grep -n 'def evict_on_target_event_included_discipline_ids_change' race_events_invalidation.py` returns hit |
| NEW `disciplines_search` JSON endpoint at `/profile/race-events/disciplines/search` | ✅ `grep -n "disciplines/search" routes/race_events.py` returns hit |
| `_parse_discipline_id_filter` helpers on both route surfaces | ✅ `grep -c 'def _parse_discipline_id_filter' routes/race_events.py routes/onboarding.py` returns 2 |
| `_disciplines_for_framework_sport` queries `layer0.sport_discipline_bridge` | ✅ `grep -A4 'def _disciplines_for_framework_sport' routes/race_events.py \| grep sport_discipline_bridge` returns hit |
| `_resolve_effective_framework_sport` race-override-wins | ✅ `grep -A3 'def _resolve_effective_framework_sport' routes/race_events.py \| grep framework_sport` returns hit |
| Auto-clear flash message present | ✅ `grep -n "Sport override changed" routes/race_events.py routes/onboarding.py` returns 2 hits |
| Per-row `data-discipline-select` attribute in `_race_terrain_editor.html` | ✅ `grep -c 'data-discipline-select' templates/_race_terrain_editor.html` returns 2 (entry + template row) |
| Inline CSP-nonced JS on race_event_edit.html + target_race.html | ✅ `grep -c "ENDPOINT = " templates/profile/race_event_edit.html templates/onboarding/target_race.html` returns 2 |
| `tests/test_race_events_repo.py` 282 → 282 (+0 net — already counted by extension) | ✅ all green |
| `tests/test_race_events_invalidation.py` +3 in TestIncludedDisciplineIdsChange | ✅ pytest run in 0.52s |
| `tests/test_layer4_orchestrator.py` +2 in TestIncludedDisciplineIdsOverride | ✅ pytest run |
| `tests/test_layer2a.py` +5 in TestDisciplineIdFilter | ✅ pytest run |
| `tests/test_routes_race_events.py` +13 across 4 new classes | ✅ pytest run |
| Container-runnable subset 859 → 889 pass + 12 skipped | ✅ pytest run in 2.04s |
| ETL `etl/tests/` 139 → 139 pass | ✅ pytest run in 0.43s |
| `CURRENT_STATE.md` last-shipped pointer flipped to this handoff | ✅ |
| `CARRY_FORWARD.md` Bucket E.(b)-B2 + E.(c)-C1 line 108 flipped ✅ shipped + §5.0 walkthrough scenario added | ✅ |

---

## 9. Files shipped this session

**Substantive (11 code/template files; ceiling break ratified at AskUserQuestion gate):**

1. MODIFIED `init_db.py` — `ALTER TABLE race_events ADD COLUMN IF NOT EXISTS included_discipline_ids TEXT[] NULL`.
2. MODIFIED `layer4/context.py` — `RaceTerrainEntry.discipline_id: str | None` + `RaceEventPayload.included_discipline_ids: list[str] | None`.
3. MODIFIED `race_events_repo.py` — load + get + create + update threading; `?::text[]` cast; list-coerce hydration.
4. MODIFIED `race_events_invalidation.py` — NEW `evict_on_target_event_included_discipline_ids_change` helper.
5. MODIFIED `layer2a/builder.py` — `discipline_id_filter` kwarg + post-filter on raw_rows.
6. MODIFIED `layer4/orchestrator.py` — `_upstream_full_cone` threads the filter.
7. MODIFIED `routes/race_events.py` — 3 NEW helpers (`_parse_discipline_id_filter`, `_disciplines_for_framework_sport`, `_resolve_effective_framework_sport`) + NEW `disciplines_search` JSON endpoint + `_parse_race_terrain` C1 extension + form integration on new_race/update_race/edit_race + auto-clear + eviction wiring.
8. MODIFIED `routes/onboarding.py` — mirror.
9. MODIFIED `templates/_race_terrain_editor.html` — restructured row layout + per-row `<select data-discipline-select="1">` with "Race-wide" empty option.
10. MODIFIED `templates/profile/race_event_edit.html` — B2 checkbox grid + inline CSP-nonced JS picker (debounced rebind on framework_sport input change).
11. MODIFIED `templates/onboarding/target_race.html` — mirror.

**Substantive (5 test files):**

12. MODIFIED `tests/test_race_events_repo.py` — `_race_row` fixture extended; NEW `TestIncludedDisciplineIdsOverride` (8 tests).
13. MODIFIED `tests/test_race_events_invalidation.py` — NEW `TestIncludedDisciplineIdsChange` (3 tests).
14. MODIFIED `tests/test_layer4_orchestrator.py` — `_queue_target_race_event` extended; NEW `TestIncludedDisciplineIdsOverride` (2 tests).
15. MODIFIED `tests/test_layer2a.py` — NEW `TestDisciplineIdFilter` (5 tests).
16. MODIFIED `tests/test_routes_race_events.py` — NEW `_FakeMultiDict` + `_FakeConn` substrates; 4 NEW classes (13 tests).

**Bookkeeping (3 files; do not count against ceiling per CLAUDE.md):**

17. MODIFIED `tests/test_onboarding_race_events.py` — 3 in-place test updates for the C1 discipline_id passthrough.
18. MODIFIED `aidstation-sources/CURRENT_STATE.md` — last-shipped pointer flipped to this handoff; predecessor WaterVocabExpansion line preserved.
19. MODIFIED `aidstation-sources/CARRY_FORWARD.md` — Bucket E.(b)-B2 + E.(c)-C1 line 108 flipped ✅ shipped; NEW 3-step Manual §5.0 walkthrough scenario added.
20. NEW `aidstation-sources/handoffs/V5_Implementation_D73_Phase_5_2_Walkthrough_BucketE_B2_C1_2026_05_24_Closing_Handoff_v1.md` — this handoff.

---

## 10. Carry-forward updates

See `CARRY_FORWARD.md` for the full list. Net changes:

- **Bucket E.(b)-B2 + E.(c)-C1 closed end-to-end** ✅ — Bucket E is now FULLY CLOSED (all 3 sub-items a/b/c shipped across BucketE_TerrainNone_FrameworkSport + BucketE_B2_C1 slices).
- **NEW Manual §5.0 walkthrough scenario** — 3-step scenario covering B2 checkbox grid render + JS rebind + B2/C1 save + Layer 2A round-trip + auto-clear flow.
- **Layer 2B per-discipline gap reasoning forward-pointer** — now unblocked (C1's `discipline_id` field exists and round-trips through the pipeline unused); Trigger #1 prompt-body update is the next consumer-side slice if the next session wants it.
- **Pre-existing forward-pointers carried** — Bucket C (g)/(i)/(l) still open + plan-mode-gate required for (g) and (l); #8 locales→locations rename remains the lowest-risk next-slice candidate; #2b race-URL LLM site-parse + §I.1 supplements + #6/#4 injury form refresh all carry.

**End of handoff.**
