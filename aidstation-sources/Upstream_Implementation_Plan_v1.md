# Upstream Layer Implementation Plan v1

**Date:** 2026-05-19
**Purpose:** Sequenced multi-session arc for Layer 1 + 2A-E + 3A + 3B runtime implementation. Layer 4 is complete (Steps 1–6 of 8 shipped per §14.3.4); no upstream layer has runtime implementation. This document is the plan to close that gap.
**Predecessor:** `handoffs/V5_Implementation_D72_Locale_FK_Type_Alignment_Closing_Handoff_v1.md` §6.1 forward-pointer ("Layer 3B caller-side rewire — the actual orchestrator build … longest forward-pointer").
**Format precedent:** `Layer4_Spec.md` §14.3.4.

---

## 1. Purpose & scope

The Layer 4 implementation arc is complete through Step 6 (cache + per-phase wiring + telemetry; six entry-point functions shipped). The arc was built against `layer4/context.py` — typed pydantic v2 mirrors of every upstream payload contract — using **dependency-injected test fixtures** for upstream data. No runtime upstream layer code exists:

- No `layer1/` module (no `q_layer1_payload(...)` builder)
- No `layer2a/` / `layer2b/` / `layer2c/` / `layer2d/` / `layer2e/` modules
- No `layer3a/` / `layer3b/` modules
- No Layer 4 orchestrator (Layer 4 entry points exist as cached-wrapper functions; no caller produces the upstream payloads to thread through them)

This plan sequences the arc to close all four gaps in dependency order. It does NOT propose code this session — Andy ratifies the plan before any implementation session opens.

**Out of scope:** Layer 0 (deployed; locked); Layer 4 (already implemented; only orchestrator-wiring lands here); Layer 4.5 joint-session coordinator (separate spec; deferred); Layer 5 supplemental outputs (not yet specced).

---

## 2. Current state inventory

### 2.1 Spec completeness

| Layer | Canonical spec file | Lines | Status | Gaps |
|---|---|---|---|---|
| **1** | None (consolidation pending) | — | 🔴 No spec file | Source-of-truth split across `Athlete_Onboarding_Data_Spec_v5.md` (§A–§L form fields) + `Athlete_Data_Integration_Spec_v5.md` §7.6 (storage gaps). D-51 field inventory is blocked-pending. |
| **2A** | `Layer2A_Spec.md` | 443 | 🟢 Complete | None flagged. |
| **2B** | `Layer2B_Spec.md` | 403 | 🟢 Complete | None flagged. |
| **2C** | `Layer2C_Spec.md` | 515 | 🟢 Complete | Two §5 Decision Point callouts (runtime vs pre-resolved toggle lookup; discipline-to-toggle mapping). Minor design questions — will need /plan-mode gate when 2C implementation opens. |
| **2D** | `Layer2D_Spec.md` | 1169 | 🟢 Complete | Amended 2026-05-17 (PR-C-followon — 6-modality `AccommodationModality` typed union). D-70 ROM modality + D-71 phase-sequencing deferred to v2 (no v1 forcing function). |
| **2E** | `Layer2E_Spec.md` | 1324 | 🟢 Complete | Largest of Layer 2 (race-day-fueling matrix). None flagged. |
| **3A** | `Layer3_3A_Spec.md` | 649 | 🟢 Complete | None flagged. |
| **3B** | `Layer3_3B_Spec.md` | 524 | 🟢 Complete | Amended 2026-05-18 (D-66 event-metadata fields) + D-72 type-alignment resolved 2026-05-19. §8.3 wording drift (`mode='open_ended'` vs canonical typed `mode='no-event'`) — doc-sweep nit; not load-bearing. |

### 2.2 Implementation skeletons

**Layer 4 (reference):** 22 modules in `layer4/` (~6500 lines total) + 11 test files + 751 passing tests. Six entry-point functions cached + wrapped + telemetry-instrumented. Built using stub LLM callers throughout — no live API integration yet (Step 7 carry-forward).

**Layers 1–3:** zero runtime code. Spec-only.

### 2.3 Typed payload mirrors in `layer4/context.py` — LOAD-BEARING REUSE OPPORTUNITY

The typed pydantic v2 contracts for ALL upstream payloads already exist:

- `Layer1Payload` — NOT typed in context.py (treated as `dict[str, Any]` opaque pass-through per PR-D precedent; Layer 1 typed schema deferred to v2 because the Layer 1 spec itself doesn't exist yet)
- `Layer2APayload` + 9 sub-types (lines 320-...)
- `Layer2BPayload` + 5 sub-types
- `Layer2CPayload` + 5 sub-types
- `Layer2DPayload` + 8 sub-types (+ 6-variant `AccommodationModality` discriminated union)
- `Layer2EPayload` + 14 sub-types
- `Layer3APayload` + 8 sub-types
- `Layer3BPayload` + 4 sub-types (with D-66 event-metadata fields + D-72 slug-typed `event_locale_id`)
- `DailyAvailabilityWindow` (§G.1)
- `RaceEventPayload` + `RouteLocale` + `RouteLocaleEquipment` (D-66)

**Implication:** upstream implementation does NOT need to design payload schemas — they're done. Implementation produces **builders** that return these typed payloads, plus (for 3A + 3B) **LLM drivers** that synthesize via Anthropic SDK + tool-use.

### 2.4 Data source readiness

| Data source | Current state | Blocks |
|---|---|---|
| `athlete_profile` table | 🟡 Partial — D-50 PR6 (2026-05-14) added body_weight_kg + hrmax_bpm + LT_HR + vo2max + cycling_ftp_w. Most of §C/§E/§F/§I/§L still missing per D-51. | Layer 1 builder |
| `conditions_log` table | 🟢 Exists (v5 onboarding writes) | Layer 1 (§B injury aggregation); Layer 2D input |
| `cardio_log` table | 🟡 Missing D-56 fields (`is_race BOOLEAN`, `start_time TEXT`) | Layer 3A (race-result filter + Night Running detection) |
| `training_log` table | 🟢 Exists | Layer 1 (§C training history); Layer 3A (recent-perf rollups) |
| `provider_auth` + per-provider tables | 🟢 D-50 Phase 1 shipped — COROS + Polar live; Garmin paused | Layer 1 (§C aggregation from provider feeds) |
| `locale_profiles` + overrides + windows tables | 🟢 D-58/59/60/61 schema shipped | Layer 1 (§J); Layer 2C (equipment mapper); Layer 4 validator |
| `race_events` + route-locales tables | 🟢 D-66 shipped 2026-05-18 | Layer 3B (event-mode metadata); Layer 4 race-week-brief |
| `daily_availability_windows` | 🟢 D-61 shipped | Layer 1 (§G); Layer 4 daily_window_fit rule |
| Layer 0 reference data (`layer0.*` schema) | 🟢 Deployed (v7-v19 catalogs) | Layer 2A-E (query nodes consume Layer 0 catalogs) — **but blocked by D-52** (app currently reads from `public.*` legacy catalogs, not `layer0.*`) |
| Race-day fueling tier bands | 🟢 In `Layer2E_Spec.md` §3 (no DB table yet) | Layer 2E (read from spec-pinned constants) |

### 2.5 Open blockers (cross-cutting)

- **D-51** — Layer 1 field inventory + schema design. Blocks Layer 1 builder. Estimated 2-3 sessions of design work. **Hard blocker** for Phase 1.
- **D-52** — Catalog migration (`public.*` → `layer0.*`). Blocks Layer 2 builders from consuming `layer0.*` cleanly. **Soft blocker** — Layer 2 builders can be implemented against `public.*` initially with a paired refactor when D-52 finishes; or D-52 lands first.
- **D-56** — `cardio_log` schema additions. Blocks Layer 3A. **Hard blocker** for Phase 3 — small migration; can fold into Phase 1 prep.

---

## 3. Dependency graph & build order

```
Layer 0 (deployed)
   │
   ▼
Layer 1 (athlete profile aggregation)
   │
   ├─→ Layer 2A (discipline classifier) ──┐
   ├─→ Layer 2B (terrain classifier) ─────┤
   ├─→ Layer 2C (equipment mapper) ───────┼─→ all four Layer 4 entry points
   ├─→ Layer 2D (injury risk) ────────────┤
   └─→ Layer 2E (nutrition baseline) ─────┤
   │                                      │
   ▼                                      │
Layer 3A (athlete state evaluation) ──────┤
   │                                      │
   ▼                                      │
Layer 3B (goal viability + periodization)─┘
   │
   ▼
Layer 4 orchestrator (composes everything; threads to llm_layer4_*_cached)
```

**Build-order rules:**

1. Layer 1 must exist before Layer 2A-E (all five consume Layer 1).
2. Layer 2A must exist before Layer 2B/2C/2D/2E (they consume 2A's `included_discipline_ids`).
3. Layer 2A-E can be implemented in parallel sessions once 2A lands.
4. Layer 3A consumes Layer 1 + Layer 2A; lands after both.
5. Layer 3B consumes Layer 1 + Layer 3A + Layer 2A + race_events; lands after 3A.
6. Layer 4 orchestrator consumes everything; lands last.

**Layer 2 query nodes are NOT LLM-driven** per the specs — they're Postgres aggregation functions. Significantly simpler than Layer 3A/3B (which ARE LLM-driven and follow the Layer 4 Step 4a precedent).

---

## 4. Sequenced multi-session arc

### Phase 1 — Spec & schema closure (3-5 sessions)

| Step | Session scope | Files (est.) | Notes |
|---|---|---|---|
| **1.1** | **D-51 design wave** — field-by-field inventory of Layer 1 §A-§L against `public.*` + decisions on new columns/tables/onboarding-only fields | 4-6 (design doc + backlog + closing handoff + spec amendments) | Trigger #5 + #8 + #11 likely fire. Output: `Layer1_D51_Design_v1.md` (similar to D-66 design doc) — closes the schema gap for §C/§E/§F/§I/§L. |
| **1.2** | **D-51 implementation** — `init_db.py` `_PG_MIGRATIONS` append per the design wave + `athlete_profile` column additions + any new tables (peak-volume history, training-history rows, network-relationships, etc.) | 3-5 (init_db.py + tests/test_init_db_d51.py + bookkeeping) | Closes D-51. Lands the storage substrate Layer 1 builder will read. |
| **1.3** | **Layer 1 spec consolidation** — new `Layer1_Spec.md` consolidating §A-§L form fields + §7 typed `Layer1Payload` pydantic v2 schema + §3 builder signature + §4 input validation + §5 algorithm | 3-4 (new spec + paired `layer4/context.py` `Layer1Payload` addition + bookkeeping) | Promotes Layer 1 from "treated as opaque dict" to typed payload. Layer 4 callers can keep accepting `dict[str, Any]` for backwards compatibility OR swap to typed at this point (paired decision). |
| **1.4** | **D-56 cardio_log additions** (optional — can fold into 1.2) | 1-2 (init_db.py append + tests) | `is_race BOOLEAN` + `start_time TEXT` — small migration. Hard blocker for 3A. |
| **1.5** | **D-52 catalog migration Phase 1** (parallel; deferrable) | varies; 5-10+ across multiple sessions | Independent track per `Catalog_Migration_Plan_v3.md`. Layer 2A-E builders can ship reading `public.*` initially with a paired D-52 follow-on; or D-52 lands first. **Architect-pick deferred to the Phase-2-kickoff session.** |

**Phase 1 total:** ~3-5 sessions, ~15-20 files.

**Triggers expected:** #5 (schema), #8 (alternatives), #11 (new D-rows — Layer 1 sub-decisions surface fresh D-rows for body-weight history, network relationships, etc.).

### Phase 2 — Layer 2 query node implementation (3-5 sessions)

All Layer 2 nodes are pure Postgres aggregation (no LLM). Each ships as one session per the Layer 4 §14.3.4 Step 4 precedent (one entry point per session).

| Step | Session scope | Files (est.) | Notes |
|---|---|---|---|
| **2.1** | **Layer 2A — discipline classifier** | 4-5 (new `layer2a.py` + new `tests/test_layer2a.py` + bookkeeping) | Foundation for 2B/C/D/E. Pure query — reads §C inputs + `layer0.sport_discipline_map` + `layer0.phase_load_allocation`; emits `Layer2APayload` with `included_discipline_ids` + per-discipline phase-load bands. |
| **2.2** | **Layer 2D — injury risk** | 4-5 | Consumes 2D's typed `ExerciseRisk` + `AccommodationModality` (already in `layer4/context.py`). Reads `injury_log` + `conditions_log` + Layer 0 `sport_discipline_bridge` + `sport_exercise_map` + `exercises` + `disciplines` + `discipline_substitutes` + `discipline_training_gaps` (per `Layer2D_Spec.md` §5.2 + §5.4 + §5.6). **No new design** — 2D + accommodation modality framework already shipped 2026-05-17 (PR-C-followon). |
| **2.3** | **Layer 2B — terrain classifier** | 4-5 | Reads target event terrain description (Layer 1 §H) + Layer 0 terrain taxonomy. |
| **2.4** | **Layer 2C — equipment mapper** | Split into Prep (6 files, shipped 2026-05-19) + Builder (3 files, shipped 2026-05-20). Decision Points pre-resolved before Builder session — no /plan-mode gate remained. Prep landed schema + ETL substrate (`equipment_substitutes_structured` JSONB + `terrain_required` TEXT[] on `layer0.exercises`; `also_satisfies` TEXT[] + `gated_discipline_ids` TEXT[] on `layer0.sport_specific_gear_toggles`); Builder shipped `layer2c/{__init__,builder}.py` + `tests/test_layer2c.py` against the resolved Decision Points (DP1 (A) Runtime; DP2 (b) Structured column). |
| **2.5** | **Layer 2E — nutrition baseline** | 4-5 | Reads §B health + §H event + §I lifestyle + 2A framework_sport + 2A discipline_ids + Layer 0 fueling-tier bands (read from `Layer2E_Spec.md` §3 constants until a DB table lands). |

**Phase 2 total:** ~5 sessions, ~25 files.

**Triggers expected:** #5 (during 2C Decision Point), #8 (during 2C), #2 (no — query nodes have no prompt bodies).

### Phase 3 — Layer 3A LLM driver (2 sessions — Split decided 2026-05-20)

Split following the Phase 2.4-Prep / 2.4 precedent: substrate first (query nodes, no LLM, no triggers), driver second (LLM + prompt body + plan-mode gate). The "6-8 files" estimate in the v1 plan assumed integration substrate was already in place; it wasn't. `Layer3AIntegrationBundle` + the 5 `q_layer3A_*` accessors per `Athlete_Data_Integration_Spec_v6.md` §10 needed their own session.

| Step | Session scope | Files (est.) | Notes |
|---|---|---|---|
| **3.1-Substrate** ✅ Shipped 2026-05-20 | **Layer 3A integration substrate** — `Layer3AIntegrationBundle` + 5 `q_layer3A_*` accessors (recent_workouts / recent_sleep / recent_hrv / combined_load / connected_providers) + `assemble_layer3a_integration_bundle` aggregator | 5 (layer4/context.py data shapes; layer3a/__init__.py + integration.py; tests/test_layer3a_integration.py; this row annotation) | Pure SQL query nodes, no LLM. Tests 901 → 941 (+40). ACWR computation uses `cardio_log.duration_min` as primary (per Integration Spec §10); `polar_cardio_load` exposed as cross-ref only. Source-tagging via `WorkoutSource` / `SleepSource` / `HRVSource` Literals supports the LLM's §6.1 weighting rules without resolving conflicts in the substrate. |
| **3.1-Driver** ✅ Shipped 2026-05-20 | **Layer 3A LLM integration** — `llm_layer3a_athlete_state(...)` + paired `Layer3A_v1.md` prompt body + cache wrapper | 5 substantive (layer3a/builder.py + cached_wrapper.py + prompts/Layer3A_v1.md + tests/test_layer3a_builder.py + Layer3_3A_Spec.md 1-line model literal fix) + bookkeeping (layer4/cache.py LAYER4_ENTRY_POINTS split + layer4/__init__.py re-export + layer3a/__init__.py re-exports + tests/test_layer4_cache.py 6 assertion swaps). Tests 941 → 995 (+54). | First upstream LLM driver. Pattern: Layer 4 Step 4a single-session precedent — pydantic schema (done), single capped retry on schema violation (lighter than Step 4a per spec §5.3 step 1), confidence-floor validator (§6.2 floor rules + high-gate criteria), Anthropic SDK extended-thinking + tool-use, dependency-injectable `LLMCaller`. Prompt body source decisions D1-D10 (forced tool-use; 4000-token thinking budget; inline-Python rendering; single-retry; full Layer3APayload schema mirror; sonnet-4-6 default with paired spec §3.3 correction; post-LLM floor clamp + auto-append observation; name-existence evidence_basis check; CLAUDE.md voice rules inlined). Cache wrapper reuses generic `CacheBackend` from layer4/cache.py with 3A-specific serialize/hydrate helpers + day-granular cache key per spec §9.1. |

**Phase 3 total:** 2 sessions (substrate ✅ + driver ✅), ~10 substantive files + bookkeeping shipped. **Phase 3 complete for Layer 3A.** Layer 3B driver (Phase 4) shipped same-day-after-Phase-3 (2026-05-20).

### Phase 4 — Layer 3B LLM driver (1-2 sessions)

| Step | Session scope | Files (est.) | Notes |
|---|---|---|---|
| **4.1** | **Layer 3B event-metadata helper** — `load_layer3b_event_metadata(db, user_id)` in `race_events_repo.py` returning `(mode, event_date, event_locale_id, race_format, time_to_event_weeks)` | 2-3 (helper + tests + closing handoff) | ✅ **Folded into 4.2 driver via D14 internal population (2026-05-20).** Original "Layer 3B caller-side rewire" scope from the D-72 forward-pointer. The driver's `_assemble_payload_candidate` populates the 4 event-metadata fields directly from the passed `RaceEventPayload`; an additional standalone tuple-returning helper in `race_events_repo.py` adds no net value over `load_target_race_event_payload + driver call` (deferred — re-add as bookkeeping if a future orchestrator wants the tuple without invoking the driver). |
| **4.2** | **Layer 3B LLM integration** — `llm_layer3b_goal_timeline_viability(...)` + paired `Layer3B_v1.md` prompt body | 6-8 (over ceiling — same precedent as 3.1) | ✅ **Shipped 2026-05-20.** 5 substantive files at ceiling: `layer3b/builder.py` (~950 LOC) + `layer3b/cached_wrapper.py` (~200 LOC) + `aidstation-sources/prompts/Layer3B_v1.md` (~700 lines) + `tests/test_layer3b_builder.py` (~1100 lines, 77 tests across 11 classes) + `Race_Events_D66_Design_v1.md` §8.3 paired fix (`open_ended` → `no-event`). D1-D14 source decisions per `Layer3B_v1.md`. Tests 995 → 1072 (+77). Bookkeeping: `layer3b/__init__.py` re-exports; `layer4/cache.py` `VALID_ENTRY_POINTS` adds `"llm_layer3b_goal_timeline_viability"`. **Triggers #2 + #5 fired**; `/plan-mode` gate ran D1-D14 + scope decision (combine 4.1+4.2 → approved). |

**Phase 4 total:** 1 session, 5 substantive + bookkeeping shipped. **Phase 4 complete.** All upstream LLM drivers (3A + 3B) now operational.

### Phase 5 — Orchestrator wiring (1-2 sessions)

| Step | Session scope | Files (est.) | Notes |
|---|---|---|---|
| **5.1** | **Layer 4 orchestrator vertical slice — race_week_brief** | 5-7 | ✅ **Shipped 2026-05-20** (PR #109; `claude/phase-5-1-orchestrator-aPvU0`). `layer4/orchestrator.py:orchestrate_race_week_brief(db, user_id, *, cache, today=None)` threads Layer 1 → 2A/2B/2D/2C → 3A → 3B → 2E → `llm_layer4_race_week_brief_cached`. `OrchestrationError` covers `no_target_event` / `race_week_brief_too_early` (pre-flight auto-fire gate skipping 3A+3B LLM cost on out-of-window invocations) / `framework_sport_missing` / `primary_locale_missing` / `etl_version_set_undiscoverable`. 10 smoke tests (`tests/test_layer4_orchestrator.py`); paired Layer4_Spec.md §4.5 D-72 audit-trail wording fix landed. Forward-pointers carried for Phase 5.2: `prior_plan_session_window=[]` (no v2 plan-gen yet); `plan_version_id=1` hardcode; Layer 2B `race_terrain=[]` (§H.2 form-refresh gap; **closed by 5.1.A 2026-05-20 for race-event edit path**); Layer 3A/3B uncached at orchestrator level. |
| **5.1.A** | **Form-refresh A — race_terrain + aid_stations end-to-end (race-event edit path)** | 8 (ceiling break ratified at plan-mode gate) | ✅ **Shipped 2026-05-20** (`claude/v5-orchestrator-phase-5-closing-OYoDT`). Closes the highest-leverage Phase 5.1 forward-pointer (race_terrain) + partial-closes Layer2B_Spec.md §12 Open Item 2B-3 (race-event edit path captures terrain; onboarding §H.2 step-3c follow-on). 8 substantive files: `init_db.py` (2 ALTER TABLE migrations: `race_events.race_terrain JSONB NOT NULL DEFAULT '[]'::jsonb` + `race_events.aid_stations INTEGER NULL CHECK (aid_stations IS NULL OR aid_stations >= 0)`), `layer4/context.py` (`RaceEventPayload` gains 2 fields + new `model_validator` enforcing TRN-\d{3} pattern), `race_events_repo.py` (5 functions threaded: list/load/create/get/update with JSONB list-or-string hydration tolerance), `routes/race_events.py` (new `_terrain_choices(db)` + `_parse_race_terrain(form)` helpers + invalidation extended to fire on race_terrain or aid_stations changes), `templates/profile/race_event_edit.html` (terrain editor with TRN-xxx select + percent input + remove + Add buttons backed by inline vanilla-JS template-clone + aid_stations input), `layer4/orchestrator.py` (2 forward-pointer flips + docstring), `tests/test_race_events_repo.py` (+9 tests in `TestRaceTerrainAndAidStations`), `tests/test_layer4_orchestrator.py` (+3 tests in `TestRaceTerrainAndAidStationsWireUp`). 9 D-decisions ratified at plan-mode gate (D1-D9 pinned in §7 of closing handoff). Tests 1082 → 1094 (+12). Slice intentionally does NOT loosen Layer 2B `_validate_inputs` empty-rejection (separate follow-on). |
| **5.1.B** | **Form-refresh B — §H.2 onboarding step-3c terrain capture** | 5 (at ceiling) | ✅ **Shipped 2026-05-20** (`claude/form-refresh-race-terrain-B63VT`). Mirrors 5.1.A's terrain editor on the onboarding side so newly-onboarding athletes capture race terrain breakdown during initial onboarding rather than via post-onboarding edit. **Fully closes Layer2B_Spec.md §12 Open Item 2B-3.** 5 substantive files: `routes/onboarding.py` (route-local `_TRN_PATTERN` + `_parse_race_terrain` + `_terrain_choices` mirrored from `routes/race_events.py` per D1 v1 duplicate-with-cross-ref strategy; `_get_target_race_row` SELECT extended with race_terrain + aid_stations + JSONB list-or-string hydration; `target_race_save()` threads new fields into both `create_race_event` (new-target branch) + `update_race_event` (existing-target branch); brief-only invalidation diff extended to include prior-vs-new race_terrain + aid_stations comparison), NEW `templates/_race_terrain_editor.html` (extracted shared partial — terrain rows + add button + hidden `<template>` + inline vanilla-JS row management; used by both onboarding/target_race.html + profile/race_event_edit.html), `templates/onboarding/target_race.html` (distance + elevation columns shrunk from col-md-6 × 2 → col-md-4 × 3 to fit new aid_stations input; `{% include '_race_terrain_editor.html' %}` between mandatory_gear textarea and notes textarea), `templates/profile/race_event_edit.html` (behavior-neutral refactor: replaced inline terrain section + bottom `<script>` block with `{% include %}` of the new partial), `tests/test_onboarding_race_events.py` (+16 new tests: 3 added to `TestGetTargetRaceRow` covering race_terrain hydration from JSONB string / native list / None; new `TestParseRaceTerrain` class with 8 tests; new `TestTerrainChoices` class with 2 tests; existing `test_returns_dict_on_hit` extended with new column assertions). 8 D-decisions ratified at plan-mode gate (D1-D8 pinned in §7 of closing handoff). Tests 1094 → 1110 (+16). Container-runnable subset (layer4 + race_events + onboarding race_events) 408 → 443. Layer 2B `_validate_inputs` empty-rejection still owed (separate loosen-for-empty follow-on; paired with form-refresh C). |
| **5.1.C** | **Form-refresh C — §J locale-terrain capture + Layer 2B empty-race_terrain loosen** | 8 (ceiling break ratified at plan-mode gate) | ✅ **Shipped 2026-05-20** (`claude/form-refresh-aid-station-a79BN`). Closes the orchestrator's last `locale_terrain_ids=[]` forward-pointer + **fully closes Layer2B_Spec.md §12 Open Item 2B-2** (`§J Locale terrain access` controlled vocabulary on canonical TRN-xxx) + paired Layer 2B `_validate_inputs` loosen for empty `race_terrain` (athletes who skip §H.2 capture now get a working orchestrator end-to-end with a `race_terrain_unset` coaching flag instead of `Layer2BInputError`). 8 substantive files: `init_db.py` (1 ALTER TABLE migration: `locale_profiles.locale_terrain_ids TEXT[] NOT NULL DEFAULT '{}'`); `routes/locales.py` (route-local `_TRN_PATTERN` + `_terrain_choices` + `_parse_locale_terrain` + `_hydrate_locale_terrain_ids` + `_evict_layer2b_on_terrain_change` per D1 v1 duplicate-with-cross-ref strategy; thread through both `_edit_legacy_locale` + `_edit_shared_locale` GET + POST per D4; D10 invalidation fires on actual terrain-set change for forward-compat with cluster-union); `templates/locales/form.html` (new "Terrain accessible from this location" multi-checkbox grid between equipment fieldsets + city/notes per D2 — checkbox grid mirrors equipment pattern); `layer2b/builder.py` (loosen `_validate_inputs` to accept empty `race_terrain`; per-entry + pct-sum checks skip when empty; new `race_terrain_unset` coaching flag emit via `_emit_coaching_flags` short-circuit when race_terrain is empty); `layer4/orchestrator.py` (hoist `_q_primary_locale` + new `_q_locale_terrain_ids(db, uid, locale)` helper above Layer 2B; flip `locale_terrain_ids=[]` to query result; docstring forward-pointer block updated); `tests/test_layer2b.py` (existing `test_empty_race_terrain_raises` removed; new `TestEmptyRaceTerrainLoosen` class with 4 tests covering payload shape on empty, both-empty case, non-list-still-raises, and orthogonal validation still firing); NEW `tests/test_locales.py` (21 tests across 5 classes — `TestTrnPattern` 2 / `TestParseLocaleTerrain` 8 / `TestTerrainChoices` 2 / `TestHydrateLocaleTerrainIds` 8 / `TestEvictLayer2bOnTerrainChange` 1); `tests/test_layer4_orchestrator.py` (new `TestLocaleTerrainIdsWireUp` class with 4 tests covering thread-into-2b-call + null column + missing row + JSON-string shim; existing `test_empty_race_terrain_still_passed_through_unchanged` docstring updated to reflect loosen). 11 D-decisions ratified at plan-mode gate (D1-D11 pinned in §7 of closing handoff). Tests 1110 → 1135 (+25; +21 new locales tests + 4 orchestrator wire-up tests; +4 new layer2b loosen tests pre-existing-circular-import-blocked from container subset same as the rest of `test_layer2b.py`). Container-runnable subset (layer4 + race_events + onboarding + locales) 443 → 468. **Phase 5.1 form-refresh trilogy A + B + C complete; orchestrator has no remaining Layer 2B input forward-pointers.** |
| **5.2** | **Remaining 3 entry points** — `single_session_synthesize`, `plan_refresh` (all 3 tiers), `plan_create` | 4-6 per entry point; can batch | Each is structurally similar to 5.1; mostly composing the upstream-builder calls + threading inputs. Auto-fire policy decisions (race_week_brief days_to_event ≤ 14 trigger; D-64 plan_refresh tier dispatch) need their own /plan-mode gates per Layer 4 §14.3.4 Step 8. |
| **5.2.S1** | **Phase 5.2 slice 1 — `single_session_synthesize` orchestrator** | 2 substantive (well under ceiling) | ✅ **Shipped 2026-05-20** (`claude/form-refresh-locale-phase5-O5XLg`). `layer4/orchestrator.py:orchestrate_single_session_synthesize(db, user_id, request, suggestion_id, *, cache, today=None)` threads Layer 1 → 2A → 2D → 2C (locale-only) → 3A → `llm_layer4_single_session_synthesize_cached`. Narrower cone than race_week_brief (no 2B/2E/3B). New `_q_locale_by_slug(db, uid, slug)` helper validates athlete-picked locale; `_q_current_etl_version_set` + `_q_locale_equipment_pool` shared with race_week_brief. `OrchestrationError` codes: `request_sport_unavailable` (Layer 2A's `Layer2AInputError` caught + re-raised) / `locale_unknown` (slug not in `locale_profiles`) / `etl_version_set_undiscoverable` (shared). 9 D-decisions ratified at plan-mode gate (D1-D9 pinned in §7 of closing handoff): D1=defer shared `_upstream_pipeline` extract until 3rd entry point (Rule of Three); D2=`request.sport` for 2A (athlete-overriding per D-63 §6.1); D3=skip 2C on quick_equipment path; D4=`suggestion_id` as kwarg (caller-allocated); D5=3 pre-flight gates; D6=validate locale via `_q_locale_by_slug`; D7=`today` kwarg matches race_week_brief signature; D8=~10 tests; D9=call cached wrapper at orchestrator level. 2 substantive files: `layer4/orchestrator.py` (+~150 LOC: new function + helper + docstring update); `tests/test_layer4_orchestrator.py` (+~400 LOC: 10 tests across 6 `TestOrchestrateSingleSessionSynthesize*` classes). Bookkeeping: `layer4/__init__.py` re-export of `orchestrate_single_session_synthesize`. Tests 1135 → 1145 (+10). Container-runnable subset 468 → 478 passing. No `/plan` Trigger #1 / #3 fired (no prompt body, no schema, no form copy); Trigger #5 covered by D-decisions ratification. |

**Phase 5 total:** ~1-2 sessions, ~10-15 files.

### Arc total

**~10-14 sessions, ~70-90 files across the full upstream arc.** This is comparable to Layer 4 implementation Steps 1-6 (which shipped in ~12 sessions, ~85 files per the CLAUDE.md `Last shipped` chain).

---

## 5. Cross-cutting concerns

### 5.1 Test fixture infrastructure

The Layer 4 test suite uses `_FakeCursor` / `_FakeConn` mocks (per `tests/test_layer4_cache.py` + `tests/test_race_events_repo.py`) for Postgres calls — no live DB. Layer 1-3 tests will reuse this pattern. New fixture infrastructure likely needed:

- **Layer 0 catalog fixtures** — shared `tests/conftest.py` with reusable `exercise_inventory` + `sport_discipline_map` + `phase_load_allocation` test data (Layer 2A-E tests will consume). Estimated 1 new conftest.py + ~200 LOC of fixture data.
- **Layer 1 fixtures** — multi-table `_FakeConn` setup for athlete_profile + conditions_log + cardio_log + training_log + provider_auth joins. Estimated 1 fixture module + ~150 LOC.
- **LLM call mocks for 3A/3B** — reuse Layer 4's `LLMCaller` type alias + dependency-injectable stub pattern (`_stub_caller` + `_sequence_caller` in `tests/test_layer4_single_session.py`).

### 5.2 Prompt-body arc for Layer 3A + 3B

Two new prompt bodies will ship in Phase 3 + Phase 4. Precedent: Layer 4 5-prompt arc (`Layer4_SeamReviewer_v1.md` through `Layer4_RaceWeekBrief_v2.md`) per `aidstation-sources/prompts/`. Each prompt body lands as one session with paired CLAUDE.md + backlog + closing handoff bump per the established cadence.

**File location:** `aidstation-sources/prompts/Layer3A_v1.md` + `aidstation-sources/prompts/Layer3B_v1.md`.

**Source decisions:** D1 tool-use; D2 extended thinking budget; D3 input format (full payloads verbatim vs trimmed); D4 retry context shape; D5 coaching-flag enum (per 3A + 3B specs' closed flag sets); D6 schema length caps; D7 voice (per CLAUDE.md "direct, evidence-grounded" + the 3A/3B specs' own coaching-flag emission patterns); D8 file location.

### 5.3 Cache integration

Layer 4's per-entry-point cache (Step 5 shipped) already keys on upstream-payload hashes via `compute_payload_hash` per `layer4/hashing.py` §9.1. Upstream layer builders need to be cache-aware OR cache-agnostic with the orchestrator wrapping them:

- **Cache-agnostic (recommended):** Layer 1/2/3 builders are pure functions returning typed payloads. Orchestrator computes the payload hash + checks the Layer 4 cache before threading to `llm_layer4_*_cached`. Per-upstream-layer caching can be added later if telemetry shows benefit.
- **Cache-aware (more work):** each upstream builder takes a `cache: Layer4Cache | None = None` kwarg. Adds complexity; not justified by v1 needs.

**Architect-pick: cache-agnostic.** Defer per-upstream-layer caching until telemetry justifies.

### 5.4 File-count ceiling

Per CLAUDE.md "5-file quality ceiling per session" rule — most Phase 2 sessions land at ceiling; Phase 3 + 4 LLM driver sessions break ceiling (~6-8 files) per the Layer 4 Step 4a precedent. Phase 1 design sessions land 4-6 files per the D-66 design wave precedent.

**Ceiling breaks expected on:** ~~2.4 (Layer 2C Decision Point gate adds files)~~ — Phase 2.4 split into Prep + Builder per Andy 2026-05-19; Prep landed 6 files (over ceiling with explicit Andy stretch authorization on the `exercise_db.py` 6-vs-5 gate), Builder landed 3 files (well under ceiling), avoiding a single mega-session. Remaining expected ceiling breaks: 3.1 (Layer 3A driver + prompt body), 4.2 (Layer 3B driver + prompt body), 5.1 (orchestrator vertical slice). All precedented across the D-66 / Layer 4 chains.

### 5.5 Production data dependencies — Andy's athlete account

Andy's data already exists in production (Pocket Gopher Extreme 2026 race; wrist injury; Nerstrand locale; trail-running / hiking / MTB / packrafting / rock-climbing / abseiling disciplines). Phase 5 vertical slice will run against Andy's data as the first real end-to-end test — race_week_brief for July 17-19, 2026.

**Forcing function:** race-week-brief naturally fires when `days_to_event ≤ 14`. For PGE 2026 (July 17), that window opens 2026-07-03. The orchestrator vertical slice should land before then so Andy gets a real LLM-generated race-week brief on the actual fire date.

---

## 6. Open questions / triggers expected to fire

Sub-decisions that need /plan-mode AskUserQuestion gates when the corresponding session opens:

1. **D-51 scope** (Phase 1.1) — Triggers #5/#8/#11. Field inventory granularity: per-field migrations vs batched; new tables for peak-volume history + network-relationships vs JSONB columns on athlete_profile; onboarding-only fields vs Layer 1 payload fields.
2. **D-52 sequencing** (Phase 1 or Phase 2 kickoff) — Trigger #8. Does Layer 2 land first reading `public.*` then refactor to `layer0.*`, or does D-52 land first?
3. **Layer 1 typed payload promotion** (Phase 1.3) — Trigger #5. Does Layer 4 swap `dict[str, Any]` → `Layer1Payload` in the entry-point signatures, or stay opaque for v1 backwards compatibility?
4. **Layer 2C §5 Decision Points** (Phase 2.4) — ~~Triggers #5/#8.~~ ✅ Resolved 2026-05-19 (D-73 Phase 2.4-Prep). DP1 (A) Runtime toggle lookup; DP2 (b) Structured `gated_discipline_ids` column.
5. **Layer 3A prompt body D-decisions** (Phase 3.1) — Trigger #2 + #8. Extended-thinking budget; input format; retry-context shape; coaching-flag enum closed-set scope.
6. **Layer 3B prompt body D-decisions** (Phase 4.2) — Trigger #2 + #8. Same as 3A.
7. **Orchestrator auto-fire policy** (Phase 5.2) — Trigger #8. Per Layer 4 §14.3.4 Step 8 — race_week_brief days_to_event ≤ 14 trigger granularity; D-64 plan_refresh tier dispatch heuristics.
8. **Pre-existing nits to bundle** — `routes/onboarding.py:710` docstring tense (Phase 4 or Phase 5); `Layer4_Spec.md` §4.5 source-pointer wording (Phase 5.1); `Race_Events_D66_Design_v1.md` §8.3 `open_ended` → `no-event` (Phase 4.2). All doc-sweep; can fold into the natural session that touches the file.

---

## 7. Backlog additions

**New D-rows for the v61 backlog:**

- **D-73** — **Upstream Layer 1-3 implementation arc.** Multi-session arc per `Upstream_Implementation_Plan_v1.md`. 10-14 sessions; 70-90 files. Dependencies: D-51 (Phase 1.1); D-52 (deferrable); D-56 (Phase 1.4). Status: 🟡 Deferred — activates when Andy picks Phase 1.1 (D-51 design wave) as a session scope. Cross-layer scope (Layer 1 + 2A-E + 3A + 3B + Layer 4 orchestrator + tests + prompt bodies + paired specs).

**Updates to existing D-rows:**

- **D-51** — `Affects nodes` extended to include "blocks Phase 1 of D-73 upstream implementation arc." Status unchanged (🟡 Deferred).
- **D-52** — `Affects nodes` extended to include "soft-blocks Phase 2 of D-73 upstream implementation arc." Status unchanged.
- **D-56** — `Affects nodes` extended to include "blocks Phase 3 of D-73 upstream implementation arc." Status unchanged.

---

## 8. Gut check

**What this plan gets right:**

- Honest about the scope (10-14 sessions; not solvable in one).
- Reuses `layer4/context.py` typed payloads (no payload-schema design work needed for 2A-E + 3A + 3B).
- Reuses Layer 4's `LLMCaller` dependency-injection + capped-retry pattern for 3A + 3B drivers.
- Reuses Layer 4's `_FakeConn` / `_FakeCursor` test pattern.
- Sequences dependencies correctly (leaves first).
- Identifies blockers (D-51, D-52, D-56) up-front so Phase 1 isn't a surprise.
- Identifies which sessions will fire which stop-and-ask triggers (so /plan-mode gates are anticipated).
- Plan ITSELF is a small document; doesn't preempt the design work each session will do.

**Risks:**

- **D-51 may be larger than 2-3 sessions** — the gap inventory is substantial (most of §C/§E/§F/§I/§L); could expand to 4-5 sessions if multi-event substructure + peak-volume history + network-relationships need their own design waves. Mitigation: D-51.1 design wave session should be a survey-only session (no code), similar to this plan.
- **D-52 sequencing risk** — if Layer 2A-E ships against `public.*` and D-52 lands later, every Layer 2 builder + every Layer 2 test needs a paired refactor. ~30% of the file count for those sessions. Mitigation: pick the D-52-vs-Layer-2 ordering at Phase 2 kickoff as an explicit /plan-mode gate.
- **Layer 1 typed payload promotion risk** (Phase 1.3) — if Layer 4 entry-point signatures swap `dict[str, Any]` → `Layer1Payload`, every Layer 4 test fixture needs updating. ~10-15 test files. Mitigation: keep `dict[str, Any]` for v1 backwards compat; promote in v2.
- **Prompt body drift risk** for 3A + 3B — Layer 4 saw 3 amendment rounds across the prompt-body arc (D-63 sport-unavailable; `intensity_modulated` broadening; D-66 paired). Phase 3 + 4 will likely see similar amendment rounds. Mitigation: bundle prompt-body amendments into the driver session per the Layer 4 Step 4a precedent (paired v1 → v2 file per Rule #12).
- **Andy's PGE 2026 forcing function** — if the upstream arc slips past 2026-07-03 (14 days before PGE), the first live race-week-brief misses the natural fire date. ~10 weeks of runway from 2026-05-19. 10-14 sessions at typical Andy cadence (every 1-3 days) should comfortably fit.

**Best argument against this plan's structure:**

The 5-phase structure presumes sequential dependency. **Layer 2A-E nodes ARE parallelizable** (after 2A lands) — they could ship in parallel sessions if Andy wants to delegate to multiple Claude Code instances. This plan presumes serial. Counter: serial sessions catch design-drift across the 5 nodes (e.g., a 2C Decision Point pick that ripples to 2E); parallel sessions miss that.

**What might be missing:**

- No coverage for **D-50 follow-on provider integrations** (Strava, Wahoo, TrainingPeaks, Zwift) — Layer 1 §C aggregation depends on broader provider coverage than current COROS + Polar. May need Phase 1 sub-step for "broaden provider integration before Layer 1 builder ships."
- No coverage for **Layer 1 prompt body** — Layer 1 is described as "aggregation" but the integration spec implies some LLM judgment (e.g., parsing free-text in §C history). May need a Layer 1 LLM driver, in which case Phase 1 expands.
- No coverage for **HITL gate (Layer 3.5)** — Layer 3D HITL queue surfacing per `Layer3_3B_Spec.md` §6 (acknowledge / revise options). Spec says "designed; not yet implemented" per CLAUDE.md. Could fold into Phase 4 or land as its own phase.
- No coverage for **Layer 5** (parallel supplemental outputs) — spec doesn't exist; out of scope for this plan.

---

## 9. Next forward move

**Andy's choice when Phase 1 opens:** D-51 design wave (Phase 1.1) is the longest-lever next move; everything else is downstream. Recommended Phase 1.1 session prompt:

> Open D-51 design wave per `Upstream_Implementation_Plan_v1.md` §4 Phase 1.1. Field-by-field inventory of Layer 1 §A-§L against `public.*` existing tables. Output: `Layer1_D51_Design_v1.md` + paired `Athlete_Data_Integration_Spec_v5.md` §7.6 update + backlog row updates. ~5 files; under ceiling.

**Alternative:** if Andy wants to defer Phase 1 entirely and pivot to Layer 4 Step 7 (live LLM integration) or Step 4f (`llm_layer4_plan_create`), this plan stays as the carry-forward roadmap. The arc isn't time-critical until PGE 2026 forcing function activates (~2026-07-03).

---

*End of plan v1. Composed 2026-05-19 from D-72 closing handoff §6.1 forward-pointer + comprehensive upstream-state recon. Ratification gate: Andy reviews this plan before any Phase implementation session opens.*
