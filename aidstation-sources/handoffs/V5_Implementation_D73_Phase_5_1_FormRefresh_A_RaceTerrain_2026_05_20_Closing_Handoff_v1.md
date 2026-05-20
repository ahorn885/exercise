# D-73 Phase 5.1 Form-Refresh A — race_terrain + aid_stations End-to-End — Closing Handoff

**Session:** D-73 Phase 5.1 form-refresh A — closes the highest-leverage Phase 5.1 orchestrator forward-pointer (`race_terrain=[]`) + `Layer2ETargetEvent.aid_stations=None` on the race-event edit path. First slice of the §H.2 / §J / §I.1 form-refresh PR per predecessor handoff §6.1 architect-recommended next move.
**Date:** 2026-05-20
**Predecessor handoff:** `V5_Implementation_D73_Phase_5_1_Orchestrator_2026_05_20_Closing_Handoff_v1.md`
**Branch:** `claude/v5-orchestrator-phase-5-closing-OYoDT`
**Status:** 8 substantive files (3-file ceiling break, ratified at plan-mode gate); container-runnable subset 348 → 408 layer4+race_events tests (+60 including pre-existing race_events_invalidation suite reached by my deps); production count 1082 → 1094 (+12 new: 9 repo + 3 orchestrator); 4 SDK smoke tests still skip cleanly. **Phase 5.1 form-refresh A complete.**

---

## 1. Session-start verification (Rule #9)

Anchor-check the predecessor handoff's §8 table claims against on-disk state.

| Claim | Anchor | Result |
|---|---|---|
| `layer4/orchestrator.py` exists; `orchestrate_race_week_brief` + `OrchestrationError` defined | `grep -n "^def orchestrate_race_week_brief\|^class OrchestrationError" layer4/orchestrator.py` | ✅ (line 65 + 81) |
| `tests/test_layer4_orchestrator.py` exists; 10 tests | `pytest --collect-only` | ✅ |
| `layer4/__init__.py` re-exports `orchestrate_race_week_brief` + `OrchestrationError` | `grep -n` lines 116-117 + 281-282 | ✅ (pydantic-import smoke test fails on container-missing `pydantic`; pip-installed during session) |
| `Layer4_Spec.md` §4.5 source-pointer narrative mentions D-72 slug-FK follow-on | line 803 | ✅ |
| `Upstream_Implementation_Plan_v1.md` §4 row 5.1 flipped to ✅ | line 179 | ✅ |
| PR #109 merged to main as `8854fa4` | `git log --oneline -1 origin/main` | ✅ (5aeb90e bookkeeping PR #110 followed; both on origin/main) |

**Reconciliation note:** Clean. No drift between predecessor's claims and on-disk state.

---

## 2. Session narrative

Andy ratified "do the recommended step" → §H.2 / §J / §I.1 form-refresh PR. Survey agent mapped all 4 gaps + sized them at ~1015 LOC total — well over single-session ceiling. Three sub-slices proposed; Andy picked **Slice A** (race_terrain + aid_stations end-to-end on race-event edit path).

Plan-mode gate (Trigger #1 user-facing form copy + Trigger #5 multi-layer wire-up) surfaced **9 D-decisions** + an explicit 5-file → 8-file ceiling break callout. Andy ratified Option A (ship all 8 files in one session, ceiling break explicitly flagged).

Implementation flow:

1. **Schema** — `layer4/context.py` extended `RaceEventPayload` with `race_terrain: list[RaceTerrainEntry] = Field(default_factory=list)` + `aid_stations: int | None = Field(default=None, ge=0)`; added module-top `_TRN_PATTERN = re.compile(r"^TRN-\d{3}$")` + new `model_validator` enforcing per-entry pattern. No sum check at payload boundary — Layer 2B owns `[80, 120]` tolerance; partial-edit rows must round-trip.
2. **Migration** — `init_db.py` `_PG_MIGRATIONS` adds 2 ALTER TABLE rows right after the existing `race_events` CREATE TABLE block: `ADD COLUMN IF NOT EXISTS race_terrain JSONB NOT NULL DEFAULT '[]'::jsonb` + `ADD COLUMN IF NOT EXISTS aid_stations INTEGER NULL CHECK (aid_stations IS NULL OR aid_stations >= 0)`.
3. **Repo** — `race_events_repo.py` threaded through 5 functions: `list_athlete_race_events` (add aid_stations to SELECT for tab listing), `load_race_event_payload` (SELECT + JSONB→list[RaceTerrainEntry] hydration with list-or-string tolerance), `create_race_event` (new kwargs + INSERT with `json.dumps`), `get_race_event` (SELECT + tolerant hydration so the edit form pre-populates), `update_race_event` (new kwargs + UPDATE with `?::jsonb` cast).
4. **Route** — `routes/race_events.py` new `_terrain_choices(db)` helper (~16 rows from `layer0.terrain_types`; no caching; matches `_athlete_locale_choices` precedent) + new `_parse_race_terrain(form)` helper (parses `race_terrain[N][terrain_id]` + `race_terrain[N][pct_of_race]` repeating rows; empty / malformed / non-numeric / out-of-range rows silently dropped); threaded through `new_race()` + `update_race()`; cache invalidation extended to fire on race_terrain or aid_stations change (brief-only — both fields feed Layer 2B + 2E which are uncached at orchestrator level; Layer 4 brief is cache-load-bearing).
5. **Template** — `templates/profile/race_event_edit.html` added repeating-row terrain editor (TRN-xxx select + percent input + remove button + "Add terrain" button backed by a `<template>` block and inline vanilla-JS clone hook) + aid_stations single integer input next to distance/elevation. Live row-index management via `data-row-idx` attribute + `nextIdx()` scan; no Alpine / HTMX.
6. **Orchestrator** — `layer4/orchestrator.py` flipped 2 forward-pointers: line 151 `race_terrain=[]` → `race_terrain=race_event.race_terrain`; line 207 `aid_stations=None` → `aid_stations=race_event.aid_stations`. Module docstring forward-pointer block updated to reflect closure (race_terrain now flows; locale_terrain_ids remains empty per Open Item 2B-2; honest about Layer 2B's empty-rejection still being a separate fix).
7. **Tests** — `tests/test_race_events_repo.py` extended `_race_row()` fixture with the 2 new columns (default empty/None); added `TestRaceTerrainAndAidStations` class with 9 tests: 4 covering load (list adapter / JSONB string adapter / None defaults to empty / pattern validator rejects malformed terrain_id at payload boundary), 2 covering create (serialization + empty defaults to `[]`), 1 covering update serialization, 1 covering get_race_event hydration, 1 covering list_athlete_race_events column inclusion. `tests/test_layer4_orchestrator.py` extended `_queue_target_race_event` fixture with race_terrain + aid_stations kwargs; added `TestRaceTerrainAndAidStationsWireUp` class with 3 tests: race_terrain threads into Layer 2B kwargs, aid_stations threads into `Layer2ETargetEvent.aid_stations`, empty-terrain pass-through unchanged.
8. **Test fix** — one off-by-one in param-index assertion (UPDATE has 13 params; aid_stations is `-3` not `-4`); landed in single edit pass.
9. **Test suite** — container-runnable subset 408 tests green (pre-existing circular import between `layer2*/__init__.py` ↔ `layer4/__init__.py` blocks ~6 test files from collection; same gap the predecessor handoff §4 noted as "container-level missing flask/psycopg2" — verified by git-stash + re-run pre-change that the failures are not introduced by this slice).
10. **Bookkeeping** — `CURRENT_STATE.md` last-shipped pointer flip + tests count + layer-status update; `CARRY_FORWARD.md` Open Item 2B-3 partial-close annotation + new §H.2 form-refresh A walkthrough entry + new Phase 5.1 form-refresh follow-ons section; `Upstream_Implementation_Plan_v1.md` new §5.1.A row; `Layer2B_Spec.md` §12 Open Item 2B-3 status annotation; this closing handoff.

No `/plan-mode` triggers fired during implementation (no prompt body, no schema change beyond agreed, no HITL gate, no padding refusal).

---

## 3. File-by-file edits

### 3.1 `init_db.py` (MODIFIED, +12 LOC)

Added 2 `ALTER TABLE IF NOT EXISTS` statements + spec-section comment block right after the `race_events_user_date_idx` line.

### 3.2 `layer4/context.py` (MODIFIED, +24 LOC)

- Added `import re` + module-level `_TRN_PATTERN = re.compile(r"^TRN-\d{3}$")` after the existing import block.
- Extended `RaceEventPayload` with `race_terrain: list[RaceTerrainEntry] = Field(default_factory=list)` + `aid_stations: int | None = Field(default=None, ge=0)` (placed between `notes` and `route_locales` to keep route_locale fields adjacent).
- New `model_validator(mode="after")` named `_check_race_terrain_terrain_id_pattern` iterates each entry and raises `ValueError` on pattern mismatch. Sum check intentionally omitted (Layer 2B owns `[80, 120]` tolerance).

### 3.3 `race_events_repo.py` (MODIFIED, +60 LOC across 5 functions)

- Import block: added `RaceTerrainEntry` to the `layer4.context` import tuple.
- `list_athlete_race_events`: SELECT extended with `aid_stations` (no race_terrain — listing is partial).
- `load_race_event_payload`: SELECT extended with `re.race_terrain, re.aid_stations`; added JSONB list-or-string hydration block (tolerates psycopg2 list-default + sqlite shim str-default + missing column None-default → `[]`) constructing `RaceTerrainEntry` instances; `RaceEventPayload` constructor takes 2 new kwargs.
- `create_race_event`: 2 new kwargs (`race_terrain: list[dict] | None = None`, `aid_stations: int | None = None`); INSERT params + columns list extended; `json.dumps(race_terrain or [])` serializes the JSONB list.
- `get_race_event`: SELECT extended; new hydration block coerces list-or-string-or-None into a list dict.
- `update_race_event`: 2 new kwargs; UPDATE SQL extended with `race_terrain = ?::jsonb` + `aid_stations = ?` clauses; param tuple extended.

### 3.4 `routes/race_events.py` (MODIFIED, +90 LOC)

- Added `import re` + module-level `_TRN_PATTERN`.
- New `_terrain_choices(db)` helper (request-time SELECT against `layer0.terrain_types`).
- New `_parse_race_terrain(form)` parser: scans `request.form` keys for `race_terrain[N][...]` matches; iterates sorted indices; drops empty / non-TRN-pattern / non-numeric / out-of-range rows; returns clean list of `{"terrain_id", "pct_of_race"}` dicts.
- `new_race()`: passes `race_terrain=_parse_race_terrain(request.form)` + `aid_stations=_parse_int(request.form, 'aid_stations')` into `create_race_event`; render_template kwargs gain `terrain_choices=terrain_choices`.
- `edit_race()`: render_template kwargs gain `terrain_choices=terrain_choices`.
- `update_race()`: parses 2 new fields, passes into `update_race_event`; brief-only cache invalidation extended to compare prior `race.get('race_terrain')` + `race.get('aid_stations')` against new values.

### 3.5 `templates/profile/race_event_edit.html` (MODIFIED, +90 LOC)

- Added "Aid stations" integer input as a new 4-column grid item next to total_elevation_gain_m.
- Added "Race terrain breakdown" full-width section between mandatory-gear textarea and notes textarea:
  - `<div id="race-terrain-rows">` containing one row per existing `race.race_terrain` entry (pre-populated via Jinja loop with `loop.index0` as the row index).
  - "+ Add terrain" button (`#add-terrain-row`).
  - `<template id="race-terrain-template">` block (Jinja-rendered terrain options inline; `__IDX__` placeholders swapped by JS).
- Added inline `<script>` block at end of `{% block content %}` with vanilla-JS hooks: `nextIdx()` scans existing rows for max `data-row-idx`, "Add" button clones template + appends, click delegation on `data-action="remove-terrain-row"` removes the row.

### 3.6 `layer4/orchestrator.py` (MODIFIED, +/-10 LOC)

- Module docstring forward-pointer block: replaced "Layer 2B `race_terrain` + `locale_terrain_ids` are empty until §H.2 ..." with a 2-bullet version that flags race_terrain as now flowing (with the Layer 2B empty-rejection caveat) and `locale_terrain_ids` as still empty per Open Item 2B-2.
- Line 151: `race_terrain=[]` → `race_terrain=race_event.race_terrain`.
- Line 207: `aid_stations=None` → `aid_stations=race_event.aid_stations`.

### 3.7 `tests/test_race_events_repo.py` (MODIFIED, +160 LOC)

- Import: added `RaceTerrainEntry`.
- `_race_row()` fixture: added `race_terrain=[]` + `aid_stations=None` defaults (so existing tests unaffected; new tests override).
- New `TestRaceTerrainAndAidStations` class with 9 tests (full coverage of CRUD + adapter tolerance + payload-validator rejection).

### 3.8 `tests/test_layer4_orchestrator.py` (MODIFIED, +120 LOC)

- `_queue_target_race_event`: added `race_terrain` + `aid_stations` kwargs (default empty/None); fixture row dict extended.
- New `TestRaceTerrainAndAidStationsWireUp` class with 3 tests asserting orchestrator threading.

---

## 4. Code / tests

**Test count delta:** 1082 → 1094 in production count (+12 new: 9 repo + 3 orchestrator); 4 SDK smoke tests still skip cleanly.

**Container-runnable subset:** 408 layer4+race_events tests green (60 net from prior 348 — the +12 new tests + 48 pre-existing race_events_invalidation + race_events_repo tests that the predecessor's "348 layer4" count didn't include). The full 1082+ count requires the layer2*/layer3* test modules; those collect-fail on the pre-existing circular import between `layer{2a,2b,2c,2d,2e}/__init__.py` and `layer4/__init__.py` → `layer4/orchestrator.py` → `layer{2a,...}.builder`. Verified via `git stash` round-trip that this circular import is **not** introduced by this slice; the import chain was already present after Phase 5.1 orchestrator shipped.

Run reproducer:
```
PYTHONPATH=. python3 -m pytest tests/test_race_events_repo.py tests/test_layer4_orchestrator.py \
                                tests/test_layer4_context.py tests/test_layer4_payload.py \
                                tests/test_layer4_hashing.py tests/test_layer4_cache.py \
                                tests/test_layer4_race_week_brief.py tests/test_race_events_invalidation.py -v
# 408 passed in 0.83s
```

The +12 new tests:
- `tests/test_race_events_repo.py::TestRaceTerrainAndAidStations::*` (9 tests)
- `tests/test_layer4_orchestrator.py::TestRaceTerrainAndAidStationsWireUp::*` (3 tests)

---

## 5. Manual §5.0 verification steps

Added to `CARRY_FORWARD.md` "Manual §5.0 walkthrough" backlog:

**Phase 5.1 form-refresh A** — 2-step walkthrough on Vercel:

**Step 1: Race-event edit form.** Navigate to `/profile/race-events/<andy_pge_2026_id>/edit`. Confirm:
- New "Race terrain breakdown" section renders below the mandatory-gear textarea, with no rows by default for unmigrated rows.
- Click "+ Add terrain" — confirm a fresh row appears with the TRN-xxx select + percent input + remove button.
- Select Andy's PGE 2026 terrain estimate: TRN-002 (Singletrack) 35%, TRN-003 (Doubletrack) 30%, TRN-004 (Gravel) 15%, TRN-009 (Flat water) 15%, TRN-016 (Bushwhack) 5%.
- Enter `aid_stations=0` (PGE is self-supported expedition AR).
- Save changes.
- Confirm Neon row reflects: `SELECT race_terrain, aid_stations FROM race_events WHERE id=<andy_pge_id>` returns 5-row JSONB array + 0.
- Reload the edit page; confirm all 5 terrain rows pre-populate from persisted JSONB.

**Step 2: Orchestrator real-LLM end-to-end (post Layer 2B `_validate_inputs` loosen, OR after Step 1 captures terrain).** `orchestrate_race_week_brief(db, user_id=<andy>, today=date(2026, 7, 3), cache=Layer4Cache(InMemoryCacheBackend()))`. Confirm:
- Layer 2B output now contains the 5 race_terrain entries with proper covered/gap classification against `locale_profiles` Nerstrand home terrain set (TRN-002 + TRN-003 + TRN-004 + TRN-008 + TRN-016 per the existing 2B Phase 2.3 walkthrough entry).
- Layer 2E `race_day_fueling` reflects `aid_stations=0` in the self-supported fueling cadence reasoning.
- Real-LLM cost: ~$0.50.

---

## 6. Next session pointers

### 6.1 Architect-recommended next forward move

**Form-refresh B — §H.2 onboarding step-3c terrain capture.** Mirror form-refresh A's race-event-edit terrain editor on the onboarding side so newly-onboarding athletes capture terrain breakdown during initial onboarding rather than via post-onboarding edit. Repo's `create_race_event` already accepts `race_terrain` kwarg from form-refresh A so wiring is shallow.

Files (est. 3-4):
1. `routes/onboarding.py` — extend the §H.2 Step 3c `target_race_save()` handler with `_parse_race_terrain(request.form)` + `aid_stations` (duplicate or share the helper from `routes/race_events.py` — recommend extracting to `race_events_repo.py` as a public helper if shared, OR duplicate as a tiny route-local function for v1).
2. `templates/onboarding/target_race.html` — add the same terrain editor + aid_stations input. Identical Jinja + JS to `race_event_edit.html` — extract to a `_race_terrain_editor.html` partial to dedupe.
3. NEW `templates/onboarding/_race_terrain_editor.html` (partial; shared between onboarding + race_event_edit).
4. `tests/test_onboarding_race_events.py` — extend with terrain capture round-trip.

Closes Layer2B_Spec.md §12 Open Item 2B-3 fully.

`/plan-mode` gate per Trigger #1 (user-facing form copy).

### 6.2 Alternative pivots

- **Form-refresh C** §J locale-terrain capture (Open Item 2B-2) — `locale_profiles` schema migration + new UI surface + orchestrator's `locale_terrain_ids=[]` flip. ~4-5 files. Closes the last orchestrator Layer-2B-input forward-pointer.
- **Form-refresh D** §I.1 structured supplements (Layer 2E §5.5 de-stub) — LARGE; requires architectural pick on schema (table vs JSONB). ~6-8 files.
- **Layer 2B `_validate_inputs` loosen** — pair with form-refresh B so athletes without terrain captured still get a working orchestrator with a `race_terrain_unset` coaching flag instead of `Layer2BInputError`. ~1-2 files.
- **Phase 5.2** — remaining 3 Layer 4 entry points (`single_session_synthesize`, `plan_refresh` T1/T2/T3, `plan_create`). Extract `_upstream_pipeline(db, user_id, today)` shared helper.
- **Layer 3B None-tolerant kwargs L3B-P-2** — migrate driver kwargs to typed RaceEventPayload fields once form-refresh B captures `goal_outcome` + `first_time_at_distance` + `previous_attempts` etc. ~3-4 files.
- **Real-LLM Layer 4 regression** parity to race_week_brief / single_session / plan_refresh / plan_create entry points (~$2/full smoke pass).

### 6.3 Operating notes for next session

Read order (Rule #13):

1. `aidstation-sources/CLAUDE.md` — stable rules.
2. `aidstation-sources/CURRENT_STATE.md` — what just shipped + current focus + layer status.
3. `aidstation-sources/CARRY_FORWARD.md` — rolling cross-session items (now includes Phase 5.1 form-refresh follow-ons section + form-refresh A walkthrough).
4. `aidstation-sources/handoffs/V5_Implementation_D73_Phase_5_1_FormRefresh_A_RaceTerrain_2026_05_20_Closing_Handoff_v1.md` — this handoff.
5. `./scripts/verify-handoff.sh` — automated anchor sweep.

---

## 7. Decisions pinned

| # | Decision | Picked by | Rationale |
|---|---|---|---|
| **D1** | DB shape: 2 columns on `race_events` (race_terrain JSONB + aid_stations INTEGER) — not a side table | Andy ratified plan-mode gate | race_terrain rows aren't independently queried; whole-list reads at orchestrator time; avoids JOIN + audit-table overhead. Side table can land in v2 if independent queries surface. |
| **D2** | No DB-level vocabulary CHECK on terrain_id | Andy | Would couple `race_events` to `layer0.terrain_types` etl_version pinning. Validate at route + pydantic model_validator. |
| **D3** | Pydantic enforces TRN-\d{3} pattern only (NO sum check at payload boundary) | Andy | Layer 2B owns `[80, 120]` tolerance at its `_validate_inputs`; partial-edit rows must round-trip through `RaceEventPayload` cleanly. |
| **D4** | Form field shape: `race_terrain[N][terrain_id]` + `race_terrain[N][pct_of_race]` repeating rows | Andy | Standard flat-form pattern; index-based; empty rows silently dropped. |
| **D5** | Terrain choices: `_terrain_choices(db)` per-request query against `layer0.terrain_types WHERE superseded_at IS NULL` | Andy | ~16 rows; not worth caching; matches `_athlete_locale_choices` precedent for request-time vocabulary lookups. |
| **D6** | `aid_stations` is form-level optional (blank → None) | Andy | No per-race-format business rules in v1; Andy's PGE 2026 = 0; aid-supported ultras typically 4–12. |
| **D7** | Cache invalidation on target-event race_terrain + aid_stations edit: `evict_on_target_event_brief_field_change` | Andy | Both fields read only by Layer 2B + Layer 2E (uncached at orchestrator level); Layer 4 brief is the cache-load-bearing artifact downstream of both. Not periodization-grade. |
| **D8** | Orchestrator flip is unconditional (no fallback to `[]` / `None`) | Andy | Typed-payload defaults already handle empty/None; explicit branch on missing data would be redundant. |
| **D9** | 8-file ceiling break ratified at plan-mode gate (over 5-file substantive ceiling) | Andy | Slice is one coherent end-to-end wire-up; splitting produces half-done features that force Andy to track follow-on. |

---

## 8. Session-end verification (Rule #10)

| Check | Result |
|---|---|
| `layer4/context.py` `RaceEventPayload` carries `race_terrain` + `aid_stations` fields | ✅ `grep -n "race_terrain: list\[RaceTerrainEntry\]\|aid_stations: int" layer4/context.py` |
| `RaceEventPayload._check_race_terrain_terrain_id_pattern` model_validator landed | ✅ `grep -n "_check_race_terrain_terrain_id_pattern" layer4/context.py` |
| `init_db.py` `_PG_MIGRATIONS` has 2 new ALTER TABLE rows | ✅ `grep -n "ADD COLUMN IF NOT EXISTS race_terrain\|ADD COLUMN IF NOT EXISTS aid_stations" init_db.py` |
| `race_events_repo.py` imports `RaceTerrainEntry` + 5 functions thread new fields | ✅ `grep -n "RaceTerrainEntry\|race_terrain\|aid_stations" race_events_repo.py` (multiple hits across 5 functions) |
| `routes/race_events.py` has `_terrain_choices` + `_parse_race_terrain` helpers | ✅ `grep -n "_terrain_choices\|_parse_race_terrain" routes/race_events.py` |
| `templates/profile/race_event_edit.html` has terrain editor block + JS script | ✅ `grep -n "race-terrain-rows\|race-terrain-template\|add-terrain-row" templates/profile/race_event_edit.html` |
| `layer4/orchestrator.py` line 151 flipped to `race_terrain=race_event.race_terrain` + line 207 to `aid_stations=race_event.aid_stations` | ✅ `grep -n "race_terrain=race_event.race_terrain\|aid_stations=race_event.aid_stations" layer4/orchestrator.py` |
| `tests/test_race_events_repo.py` has `TestRaceTerrainAndAidStations` class with 9 tests | ✅ `grep -cn "class TestRaceTerrainAndAidStations\|^    def test_" tests/test_race_events_repo.py` |
| `tests/test_layer4_orchestrator.py` has `TestRaceTerrainAndAidStationsWireUp` class with 3 tests | ✅ `grep -n "class TestRaceTerrainAndAidStationsWireUp" tests/test_layer4_orchestrator.py` |
| Container-runnable subset (layer4 + race_events) green at 408 | ✅ `pytest tests/test_layer4_*.py tests/test_race_events_*.py` reports 408 passed |
| `Upstream_Implementation_Plan_v1.md` §4 row 5.1.A flipped to ✅ Shipped 2026-05-20 | ✅ `grep -n "5.1.A.*Shipped 2026-05-20" aidstation-sources/Upstream_Implementation_Plan_v1.md` |
| `Layer2B_Spec.md` §12 Open Item 2B-3 partial-close annotation landed | ✅ `grep -n "Partial-close 2026-05-20.*Phase 5.1 form-refresh A" aidstation-sources/Layer2B_Spec.md` |

---

## 9. Files shipped this session

**Substantive (8 files; 3-file ceiling break ratified at plan-mode gate):**

1. MODIFIED `init_db.py` (+12 LOC) — 2 ALTER TABLE rows.
2. MODIFIED `layer4/context.py` (+24 LOC) — `RaceEventPayload` field additions + `_TRN_PATTERN` constant + model_validator.
3. MODIFIED `race_events_repo.py` (+60 LOC) — 5-function thread-through with JSONB adapter tolerance.
4. MODIFIED `routes/race_events.py` (+90 LOC) — 2 new helpers + handler wiring + cache invalidation extension.
5. MODIFIED `templates/profile/race_event_edit.html` (+90 LOC) — terrain editor section + aid_stations input + inline JS.
6. MODIFIED `layer4/orchestrator.py` (+/-10 LOC) — 2 forward-pointer flips + docstring.
7. MODIFIED `tests/test_race_events_repo.py` (+160 LOC) — `TestRaceTerrainAndAidStations` (9 tests).
8. MODIFIED `tests/test_layer4_orchestrator.py` (+120 LOC) — `TestRaceTerrainAndAidStationsWireUp` (3 tests).

**Bookkeeping (4 files):**

9. MODIFIED `aidstation-sources/CURRENT_STATE.md` — last-shipped pointer + tests count + layer-4 + arc-summary updates.
10. MODIFIED `aidstation-sources/CARRY_FORWARD.md` — Open Item 2B-3 partial-close + new §5.1.A walkthrough entry + new "Phase 5.1 form-refresh follow-ons" section.
11. MODIFIED `aidstation-sources/Upstream_Implementation_Plan_v1.md` — new §5.1.A row.
12. MODIFIED `aidstation-sources/Layer2B_Spec.md` — §12 Open Item 2B-3 partial-close annotation.
13. NEW `aidstation-sources/handoffs/V5_Implementation_D73_Phase_5_1_FormRefresh_A_RaceTerrain_2026_05_20_Closing_Handoff_v1.md` — this handoff.

---

## 10. Carry-forward updates

See `CARRY_FORWARD.md` for the full list. Net adds:

- §5.1.A walkthrough entry under "Manual §5.0 walkthrough" (race-event edit terrain capture + post-capture orchestrator end-to-end).
- New "Phase 5.1 form-refresh follow-ons" section with 6 follow-on items: form-refresh B (onboarding §H.2 step-3c), form-refresh C (§J locale-terrain), form-refresh D (§I.1 supplements), Layer 2B `_validate_inputs` loosen, L3B-P-2 None-tolerant kwargs migration, onboarding step-3c paired copy refresh.

Phase 5.1 form-refresh A closes the 9 D-decisions ratified at the plan-mode gate; no carry-forward of unresolved decisions.

---

**End of handoff.**
