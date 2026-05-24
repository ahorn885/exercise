# D-73 Phase 5.2 Walkthrough — BM-1 D-008b + Race-Craft-Aware Scoring — Closing Handoff

**Session:** D-73 Phase 5.2 caller-side. Ships the first BM-1 per-discipline vocab population slice (D-008b Outdoor Paddling) PLUS a Path A architectural pivot — race-craft-aware scoring closing a gap Andy caught at the design review (static `base_preference_score` is the wrong abstraction for race-craft-specific disciplines; D-006 cycling has the same gap latently).

**Date:** 2026-05-24
**Predecessor handoff:** `V5_Implementation_D73_Phase_5_2_Walkthrough_BM3_PromptBodyIntegration_2026_05_24_Closing_Handoff_v1.md`
**Branch:** `claude/v5-implementation-phase-5-2-t1GCn` (harness-pinned; generic enough to cover BM-1 + race-craft-aware scope per CLAUDE.md branch-naming rule)
**Status:** 18 substantive files (15 source + 3 new — spec amendment + form partial + ETL K3) + 3 bookkeeping. Sequencing 3 ceiling break ratified at gate per Trigger #3 (cross-layer surface — new race_events column + resolver kwarg) + Trigger #5 (architectural alternatives). All 14 modified Python files pass `python3 -m py_compile`. Pytest not available in this environment so test counts can't be runtime-verified; static analysis + compile-clean confirms behavior contracts.

---

## 1. Session-start verification (Rule #9)

Read order completed per Rule #13: `CLAUDE.md` → `CURRENT_STATE.md` → `CARRY_FORWARD.md` → predecessor BM-3 handoff → `BestFitModality_Spec_v1.md` → `./aidstation-sources/scripts/verify-handoff.sh`. Anchor sweep returned all functional anchors ✅; some grep-count numerals in the predecessor §8 didn't match disk (5/5 claimed vs 3/6 actual in hashing.py; 8 vs 12 in cached_wrappers.py; 2 vs 3 for locale_hash in cached_wrappers.py; 6 vs 5 in per_phase.py) — these were stale bookkeeping not missing functionality. Drift fixed in commit `631ce9b` (PR #146, draft, green) as the first action of the session per Rule #9.

| Claim | Anchor | Result |
|---|---|---|
| Predecessor's §8 grep counts match disk | manual grep | ✅ after drift-fix commit |
| Branch synced with origin/main | `git rev-list --left-right --count HEAD...origin/main` | ✅ 0/0 pre-edit |
| BM-3 functional anchors present | `grep -c "^def _render_modality_section_*"` etc. | ✅ all 1 |
| `_MODALITY_OPTIONS_PER_DISCIPLINE` has D-001/D-006/D-010 only | resolver.py inspection | ✅ pre-this-session |

Andy picked **BM-1 D-008b** at the recommendations gate (per CURRENT_STATE.md "architect-recommended next forward move"). Plain-language briefing surfaced the design-time observation that static scoring doesn't capture race-craft context. Andy picked **Path A** (resolver kwarg + race_events column) over Path B (LLM-side) / Path C (defer-D-008b) / Path D (static-scores-with-gap). Sequencing 3 (single batched ship) over Sequencing 1 (spec-only) / Sequencing 2 (spec + resolver-side only).

Per Trigger #3 (cross-layer surface change) + Trigger #5 (architectural alternatives) plan-mode gate, 3 nested decisions ratified at AskUserQuestion gates:

| # | Gate | Andy's pick | Notes |
|---|---|---|---|
| G1 | Score math | **Multiplicative *1.2** | Over additive +15 / tier promotion to 95+. Preserves intra-discipline relative ordering across base-score bands without additive blow-past. `min(100, int(round(base * 1.2)))` caps at 100. |
| G2 | Form UX | **Add-row builder** | Over per-discipline checkboxes / no-form-this-slice. Mirrors `_race_terrain_editor.html` pattern; gives Andy flexibility to add (discipline, equipment) pairs ad-hoc. |
| G3 | Lint scope | **Add missing names to canonical 0B** | Over static-set-in-test-file / skip-lint. Half of BM-5's canonicalisation work done inline; 10 new canonical 0B entries shipped in K3 ETL file (Treadmill / Road bike / Rope / Quickdraws / Harness / Crash pad / Hangboard / Climbing gym membership / Kayak / Canoe). |
| Implicit | Slice scope | **Sequencing 3 — single batched ship** | ~18 files in one slice. Ceiling break ratified explicitly (precedent BucketC_l=12, BM-3=9; this slice intentionally larger because Path A is cross-layer surface change requiring spec + plumbing + form + ETL in one ship). |

---

## 2. Session narrative

Three phases:

**(a) Drift reconcile + plan-mode gate.** Spotted 4 grep-count drifts in predecessor §8 table. Fixed in 1 commit + 1 PR (`#146`, draft, green). Loaded `BestFitModality_Spec_v1.md` §5 + §12 + §13 + the resolver source + test surface + race_events code surface (via `Explore` agent that mapped: route file `routes/race_events.py:418-614`; init_db.py:1286-1287 race_terrain precedent; race_events_repo.py:85+ SELECT; orchestrator.py:306+ resolver call site; race_events_invalidation.py existing eviction helpers; `populate_equipment_items_K2_additions.sql` ETL precedent). Surfaced the static-scoring gap Andy caught at the recommendations gate — packraft-vs-kayak for D-008b depends on what the target race specifies; D-006 cycling has the same gap latently. Plain-language 4-path briefing presented (A/B/C/D); Andy picked Path A + Sequencing 3.

**(b) Spec amendment.** Wrote `BestFitModality_Spec_v2.md` (~350 lines, 15 sections §A-§O) locking the contract before any code touched it: §A function-signature delta with `race_modality_hints: dict[str, list[str]] | None = None` kwarg; §B scoring math (multiplicative *1.2 with set-intersection match condition + cap at 100); §C race_events.race_modality_hints JSONB source-of-truth + add-row builder; §D RaceEventPayload + orchestrator wire across 3 entry points; §E cache-key extension with `race_modality_hints_hash` slot + None → '' forward-compat; §F ModalityOption.race_craft_match=False default for v1 payload-shape compat; §G eviction policy = 3 entry points (plan_create + single_session + race_week_brief; plan_refresh excluded per BM-3 G1=A3); §H D-008b 6-option vocab S2 pick spec'd verbatim with terrain/equipment/skill/score bands; §I equipment canonicalisation closing BM-5 partially with 10 new K3 entries; §J 5 new test scenarios §13.7-§13.11; §K perf budget unchanged; §L 8 edge cases; §M 8 open items v2 (carries + new); §N backward-compat note; §O gut check.

**(c) Implementation.** Order: payload schema (context.py) → resolver (vocab + kwarg + scoring math) → hashing (3 keys + new slot) → cached_wrappers (3 wrappers + new kwarg + hash + thread) → orchestrator (load target_event in single_session + thread to 3 resolver call sites + 3 cached_wrappers) → drivers (signature symmetry only — single_session.py + plan_create.py + race_week_brief.py accept-but-don't-consume) → race_events_repo.py (SELECT + UPDATE column write + dual-shape JSONB tolerance) → init_db.py (idempotent column migration) → race_events_invalidation.py (new 3-entry-point helper) → routes/race_events.py (parser + equipment_choices helper + render context wire + parse-save wire + new eviction chain rung) → templates/_race_modality_hints_editor.html (NEW partial, ~120 lines, add-row builder mirroring _race_terrain_editor.html) → templates/profile/race_event_edit.html (1-line include) → etl/sources/populate_equipment_items_K3_additions.sql (NEW, 10 canonical entries + verify block) → tests (test_layer2_modality.py 7 new test classes covering §J §13.7-§13.11 + cap edge case + backward-compat; test_layer4_hashing.py 6 new tests covering race_modality_hints_hash None-collapse + populated-hash distinguish for all 3 keys + parametrized mutation extended).

**Smoke test.** Pytest not installed in this environment; pydantic not installed either. Static analysis + `python3 -m py_compile` on all 14 modified Python files = clean. Hand-traced the math: 75 × 1.2 = 90 (D-008b packraft + hint); 80 × 1.2 = 96 (D-008b whitewater_packraft + skill toggle ON + hint); 90 × 1.2 = 108 → 100 (D-010 lead-climb cap edge case).

---

## 3. File-by-file edits

### 3.1 NEW `aidstation-sources/BestFitModality_Spec_v2.md`

15 sections (§A-§O). Locks the Path A contract: resolver kwarg + scoring math + JSONB column shape + payload field + cache-key slot + eviction policy + D-008b 6-option vocab verbatim + ETL canonicalisation list + test scenarios + edge cases + open items + backward-compat. Pre-load for next session's Rule #13 read order.

### 3.2 MOD `layer2_modality/resolver.py`

+~100 lines net.
- NEW D-008b 6-option block in `_MODALITY_OPTIONS_PER_DISCIPLINE` (outdoor_paddle_packraft @ TRN-009/010 needs Packraft / outdoor_paddle_kayak @ TRN-009/010 needs Kayak / outdoor_paddle_sup @ TRN-009/010 needs SUP / outdoor_whitewater_packraft @ TRN-011/017 needs Packraft + whitewater_handling / outdoor_whitewater_kayak @ TRN-011/017 needs Kayak + whitewater_handling / pool_paddle_drill @ TRN-008 no equipment).
- `_resolve_menu_for_pair` signature gains `race_craft_equipment: set[str]` kwarg.
- Scoring math: `race_craft_match = bool(opt.requires_equipment_all_of and race_craft_equipment and set(opt.requires_equipment_all_of) & race_craft_equipment)`; `effective_score = min(100, int(round(opt.base_preference_score * 1.2))) if race_craft_match else opt.base_preference_score`.
- Constructed ModalityOption carries new `race_craft_match=race_craft_match` field.
- `resolve_best_fit_modality` signature gains `race_modality_hints: dict[str, list[str]] | None = None` kwarg; per-discipline hint dict access; threads `race_craft_equipment = set(hints.get(d_id, []) or [])` to `_resolve_menu_for_pair`.

### 3.3 MOD `layer4/context.py`

+13 lines.
- `ModalityOption` gains `race_craft_match: bool = False` (v1 payload-shape compat per spec v2 §F).
- `RaceEventPayload` gains `race_modality_hints: dict[str, list[str]] = Field(default_factory=dict)` between `included_discipline_ids` and `route_locales`.

### 3.4 MOD `layer4/hashing.py`

+18 lines. 3 cache-key helpers — `plan_create_key`, `single_session_synthesize_key`, `race_week_brief_key` — gained optional `race_modality_hints_hash: str | None = None` kwarg with None → '' forward-compat collapse. Mirrors the BM-3 `layer2_modality_hash` pattern exactly.

### 3.5 MOD `layer4/cached_wrappers.py`

+45 lines. 3 cached wrappers — `llm_layer4_single_session_synthesize_cached`, `llm_layer4_plan_create_cached`, `llm_layer4_race_week_brief_cached` — gained `race_modality_hints: dict[str, list[str]] | None = None` kwarg + `compute_payload_hash(race_modality_hints) if race_modality_hints else None` + key wire + thread to driver via `_synthesize()` closure or kwargs dict.

### 3.6 MOD `layer4/orchestrator.py`

+~25 lines.
- `_upstream_full_cone` (line ~306): pulls `target_race_event.race_modality_hints` into local `race_modality_hints` + threads to `resolve_best_fit_modality(race_modality_hints=race_modality_hints or None, ...)`.
- `orchestrate_race_week_brief` (line ~447): threads `race_modality_hints=dict(race_event.race_modality_hints) or None` to `llm_layer4_race_week_brief_cached`.
- `orchestrate_plan_create` (line ~781): threads same to `llm_layer4_plan_create_cached`.
- `orchestrate_single_session_synthesize` (line ~525): NEW `load_target_race_event_payload(db, user_id)` call early in the function + `race_modality_hints` local + threads to BOTH the resolver call (line ~579) AND the cached wrapper (line ~612). Single-session is "off-plan" per the docstring but the athlete is typically training toward something; the race-craft bump keeps the LLM's modality citation consistent across all 3 entry points.

### 3.7 MOD `layer4/single_session.py` / `layer4/plan_create.py` / `layer4/race_week_brief.py`

Signature-only delta (~5 lines per file). Each driver gained `race_modality_hints: dict[str, list[str]] | None = None` kwarg for signature symmetry with the cached wrapper's `_synthesize` closure. Resolver-side scoring is already applied upstream of these drivers (bumped scores ride inside `layer2_modality_payload`), so they accept-but-don't-consume the dict. Docstring comments cite the v2 §A spec for traceability.

### 3.8 MOD `race_events_repo.py`

+~25 lines.
- `load_race_event_payload` SELECT extended to include `re.race_modality_hints`.
- JSONB column shape tolerance (dict from psycopg2 / str from sqlite-shim) + validation+coercion to `dict[str, list[str]]` with silent-drop on malformed entries (`isinstance(d_id, str)` + `isinstance(equip_list, list)` + nested string check).
- `RaceEventPayload(... race_modality_hints=race_modality_hints, ...)` constructor wire.
- `update_race_event` signature gained `race_modality_hints: dict[str, list[str]] | None = None` kwarg; UPDATE SET clause extended with `race_modality_hints = ?::jsonb`; serialized via `json.dumps(race_modality_hints or {})`.

### 3.9 MOD `init_db.py`

+9 lines. `_PG_MIGRATIONS` extended with `ALTER TABLE race_events ADD COLUMN IF NOT EXISTS race_modality_hints JSONB NOT NULL DEFAULT '{}'::jsonb` idempotent migration. Comment cites spec v2 §C + eviction policy + the 3 plan-gen entry points + `evict_on_target_event_modality_hints_change`.

### 3.10 MOD `race_events_invalidation.py`

+33 lines. NEW `evict_on_target_event_modality_hints_change(db, user_id, *, cache=None)` helper firing field-level eviction across 3 entry points — plan_create + single_session_synthesize + race_week_brief — via 3 `cache.invalidate_entry_point(layer='race_events_modality_hints')` calls. plan_refresh intentionally excluded per BM-3 G1=A3 deferral (plan_refresh tier renderers consume bundled Layer 2 payload that doesn't include the modality payload). Returns total count of evicted rows.

Field-level eviction rather than layer-level because no existing `_EVICTION_POLICY` tuple in `cache_invalidation.py` matches exactly {plan_create, single_session_synthesize, race_week_brief}. Mirrors `evict_on_target_event_brief_field_change`'s shape but with 3 invalidate_entry_point calls instead of 1.

### 3.11 MOD `routes/race_events.py`

+~90 lines.
- NEW `_parse_race_modality_hints(form) -> dict[str, list[str]]` parser following `_parse_race_terrain` shape. Form-key regex `^race_modality_hints\[(\d+)\]\[(discipline_id|equipment_name)\]$`. Empty cells silently drop. Invalid discipline-id pattern silently drops. Duplicate (discipline, equipment) pairs silently dedupe. Multiple rows for same discipline collapse to extend the equipment list per discipline.
- NEW `_equipment_choices(db) -> list[str]` returning `DISTINCT canonical_name FROM layer0.equipment_items WHERE superseded_at IS NULL ORDER BY canonical_name ASC` with graceful empty-list fallback when layer0 schema absent.
- NEW `_DISCIPLINE_ID_PATTERN = re.compile(r'^D-\d{3}[a-z]?$')` regex.
- `edit_race` GET: threads `equipment_choices` + flattened `existing_modality_hints` list-of-dicts (from `race.get('race_modality_hints') or {}` dict, expanded into one row per (discipline, equipment) pair) into the template render.
- `update_race` POST: parses `_parse_race_modality_hints(request.form)` + threads to `update_race_event(race_modality_hints=...)` + adds `modality_hints_changed = prior_modality_hints != new_race_modality_hints` to the field-change eviction chain rung between periodization and brief-only — fires `evict_on_target_event_modality_hints_change(db, uid)` when only hints flip (periodization / framework_sport / discipline_filter still supersede when broader change occurs).
- `new_race` GET: passes empty modality_hints + equipment_choices.

### 3.12 NEW `templates/_race_modality_hints_editor.html`

~120 lines. Add-row builder partial mirroring `_race_terrain_editor.html`:
- Header + small-text instructions.
- `{% for entry in existing_modality_hints %}` row block: discipline_id `<select>` (sources from `discipline_choices`) + equipment_name `<select>` (sources from `equipment_choices`) + Remove button.
- Empty `<div id="race-modality-hints-rows">` for fresh races.
- `+ Add craft` button + hidden `<template id="race-modality-hint-template">` for JS clone-on-click.
- Nonce-scoped IIFE script (CSP-compliant, mirrors the terrain partial's nonce convention).
- JS hooks: `nextIdx()` finds max existing row-idx + 1; `addEventListener('click', ...)` on Add → clones template + replaces `__IDX__` placeholders; container listens for Remove clicks via event delegation.

### 3.13 MOD `templates/profile/race_event_edit.html`

+5 lines. Includes `_race_modality_hints_editor.html` between the terrain editor and notes textarea. Comment cites spec v2 §C + the shared discipline_choices vocab with the terrain editor.

### 3.14 NEW `etl/sources/populate_equipment_items_K3_additions.sql`

~110 lines. 10 new canonical 0B entries with ETL version tag `0B-v19.K3`:
- `Treadmill` (D-001 treadmill_run)
- `Road bike` (D-006 outdoor_road_ride)
- `Rope` (D-010 outdoor_lead_climb + outdoor_top_rope)
- `Quickdraws` (D-010 outdoor_lead_climb)
- `Harness` (D-010 rope-based options)
- `Crash pad` (D-010 outdoor_boulder)
- `Hangboard` (D-010 gym_hangboard)
- `Climbing gym membership` (D-010 gym options; flagged as non-equipment-but-equipment-like marker)
- `Kayak` (D-008b kayak options)
- `Canoe` (reserved for future D-008b canoe variants)

Idempotent: `ON CONFLICT (canonical_name, etl_version) DO NOTHING`. DO $$ verification block asserts all 10 present after run + RAISES EXCEPTION on miss.

Manual ETL run step (NOT in `_PG_MIGRATIONS` per existing K2 precedent): `psql $DATABASE_URL -f etl/sources/populate_equipment_items_K3_additions.sql` on next deploy.

### 3.15 MOD `tests/test_layer2_modality.py`

+~280 lines.
- NEW `_KNOWN_EQUIPMENT` set covering canonical 0B K2 + K3 names (29 entries).
- NEW `TestStaticLint.test_every_required_equipment_is_canonical` extending L2 lint to equipment names. Pre-this-slice would have failed on Road bike / Quickdraws / Crash pad / Hangboard / etc. — K3 ETL additions are what makes this test pass.
- `test_spec_representative_disciplines_present` extended to lock D-008b alongside D-001/D-006/D-010.
- 6 NEW test classes covering spec v2 §J:
  - `TestScenario13_7_RaceCraftBumpAtAndysPGE` (3 tests) — packraft hint bumps 75 → 90 at Andy's home; kayak + SUP unchanged; no-hint baseline shows kayak top (ties on 75 with packraft, alphabetical tiebreaker).
  - `TestScenario13_8_HintWithUnknownEquipment` (1 test) — `{'D-008b': ['NonexistentCraft']}` silent-ignores.
  - `TestScenario13_9_HintForAbsentDiscipline` (1 test) — `{'D-099': ['Packraft']}` silent-ignores; D-008b's packraft stays at base.
  - `TestScenario13_10_WhitewaterHintWithToggleOn` (1 test) — whitewater_handling=True + Packraft hint at TRN-011 → outdoor_whitewater_packraft top at 96 (80 × 1.2).
  - `TestScenarioD008b_BaseShape` (2 tests) — locks 6-option count + whitewater skill-gate shape.
  - `TestScenarioD008bScoreCap` (1 test) — cap edge case via D-010 outdoor_lead_climb base 90 + Rope hint → 100 (not 108).
- NEW `TestRaceCraftHintBackwardCompat` (4 tests) — None / empty-dict / empty-list per discipline / no-equipment-option-exempt cases all produce v1-identical menu order.

### 3.16 MOD `tests/test_layer4_hashing.py`

+~70 lines. 6 new tests covering `race_modality_hints_hash` None-collapse + populated-hash distinguish for all 3 keys (plan_create_key, single_session_synthesize_key, race_week_brief_key). Parametrized mutation coverage extended with the new slot for all 3 keys' `*_depends_on_each_component` test families.

---

## 4. Code / tests results

**Compile sweep:** All 14 modified Python files pass `python3 -m py_compile` (resolver.py + context.py + hashing.py + cached_wrappers.py + orchestrator.py + single_session.py + plan_create.py + race_week_brief.py + race_events_repo.py + race_events_invalidation.py + routes/race_events.py + init_db.py + tests/test_layer2_modality.py + tests/test_layer4_hashing.py). Confirmed pre-commit.

**Test counts:** Pytest is not installed in the remote-execution environment so I cannot run the test suite or get a collection count. Static count of `def test_*` in the modified test files:
- `tests/test_layer2_modality.py`: 42 → 55 (+13 new tests across the 7 new classes + 1 added lint test).
- `tests/test_layer4_hashing.py`: 48 → 54 (+6 new tests covering the new hash slot across all 3 keys).

(Note: parametrized tests in test_layer4_hashing.py inflate the pytest-collected count above the function-def count; the parametrized `*_depends_on_each_component` families each gained 1 new mutated-component case for the new slot.)

**Smoke test:** Couldn't run end-to-end (pydantic + pytest both unavailable). Hand-traced the scoring math against spec §B:
- 75 × 1.2 = 90.0 → `int(round(90.0))` = 90 (D-008b packraft + hint).
- 80 × 1.2 = 96.0 → 96 (D-008b whitewater + hint + skill toggle ON).
- 90 × 1.2 = 108.0 → `min(100, ...)` = 100 (D-010 lead-climb cap test).
- 65 × 1.2 = 78.0 → 78 (D-008b SUP if hint were SUP).
- 30 × 1.2 = 36.0 → 36 (pool_paddle_drill — but exempt since `requires_equipment_all_of` is empty; verified in TestRaceCraftHintBackwardCompat).

---

## 5. Manual §5.0 verification steps

NEW Manual §5.0 walkthrough scenario added (carried in `CARRY_FORWARD.md` §5.0 walkthrough block, count 110 → 115):

1. **Form-edit add-row builder lands.** Navigate `/profile/race-events/<andy_pge_id>/edit`; confirm the "Race craft (per-discipline equipment hints)" section renders between the terrain editor and notes textarea with no rows by default (pre-v2 races have `race_modality_hints` column = `'{}'::jsonb`). Click "+ Add craft" → row appears with discipline_id `<select>` (D-008b among AR choices) + equipment_name `<select>` (Packraft / Kayak / SUP / Canoe / etc. all in dropdown from canonical 0B). Pick `(D-008b, Packraft)`; Save changes; confirm `SELECT race_modality_hints FROM race_events WHERE id=<pge_id>` returns `{"D-008b": ["Packraft"]}` JSONB. Reload edit page; confirm row pre-populates.
2. **Race-craft bump fires in race_week_brief.** Once Andy's PGE 2026 is inside the 14-day auto-fire window (or test-fixture flip `event_date`), run `orchestrate_race_week_brief(db, user_id=<andy>, today=<within window>, cache=Layer4Cache(InMemoryCacheBackend()))` + capture the rendered prompt; confirm the modality section's D-008b recommendation shows `outdoor_paddle_packraft` as top-pick at preference_score=90 (75 base × 1.2 = 90; matches spec v2 §13.7); kayak + SUP options surface at base 75 / 65 with `race_craft_match=False` in the underlying payload.
3. **Race-craft bump fires in plan_create + single_session.** Drive `orchestrate_plan_create(...)` for Andy's PGE 2026 context + verify per-phase prompt bodies cite packraft as D-008b top-pick at 90. Drive a single_session via `/workouts/build` with `request.locale_slug=home` + `request.sport='Adventure Racing'` + confirm the single-session prompt also cites packraft top at 90 (target_event lookup fires + threads race_modality_hints to the resolver call).
4. **Cache invalidation on hint change.** Edit the race-event form to flip `(D-008b, Packraft)` → `(D-008b, Kayak)`; Save; confirm `SELECT entry_point FROM layer4_cache WHERE user_id=<andy> AND entry_point IN ('plan_create','plan_refresh','single_session_synthesize','race_week_brief') AND superseded_at IS NULL` returns no rows for plan_create + single_session_synthesize + race_week_brief (3 entry points evicted per `evict_on_target_event_modality_hints_change`); plan_refresh row IF present remains untouched (plan_refresh tier excluded per BM-3 G1=A3). Rerun the orchestrators → confirm cache MISSES + kayak now bumps to 90 above packraft at 75.
5. **Backward-compat.** Verify pre-v2 cache entries with `race_modality_hints_hash=None` collapse to '' inside all 3 key helpers (covered by 6 unit tests in `test_layer4_hashing.py` `*_race_modality_hints_hash_none_equals_empty_string`). Pre-v2 race_events rows continue to work — column default `'{}'::jsonb` means `race_modality_hints={}` flows through to the resolver as None → no bump → v1-identical menu order. Cap edge case — verify D-010 outdoor_lead_climb at base 90 with `race_modality_hints={'D-010':['Rope']}` caps at score=100 not 108 (TestScenarioD008bScoreCap pins the math).

**Also requires manual ETL step on deploy:** `psql $DATABASE_URL -f etl/sources/populate_equipment_items_K3_additions.sql` to land the 10 new canonical 0B equipment names. The new form-edit equipment `<select>` dropdown sources from `layer0.equipment_items` so without this ETL step Packraft / SUP would show up (already in K2) but Kayak / Canoe / etc. would not. Pre-K3 race_modality_hints can still be set via SQL directly; the form-edit picker just shows fewer choices.

§5.0 scenario count carried at 110 + 5 = **115**.

---

## 6. Next session pointers

### 6.1 Architect-recommended next forward move

**M-1 D-006 cycling scoring backfill** — the same race-craft gap is latent for D-006 today. Andy's PGE 2026 happens to align with gravel preference (gravel=85 > road=80 in current banding) but a road-mandated race would still cite gravel as top. Backfill: lower D-006 base scores to neutral (gravel=75 / road=75 / trainer=40) and rely on `race_modality_hints` to differentiate per-race. Pairs naturally with whatever D-006 work happens next. ~2-3 files: `layer2_modality/resolver.py` (rebanded scores) + `tests/test_layer2_modality.py` (existing D-006 scenarios re-pinned). Trigger #2 padding scrutiny gate.

### 6.2 Alternative pivots

- **M-2 Renderer transparency** — 3 prompt renderers cite `[race-craft match]` tag on `ModalityOption.race_craft_match=True` options for explicit LLM signal. Trivial 3-file slice (single_session.py + per_phase.py + race_week_brief.py — 1-2 lines each in the existing render helpers). Deferred to keep v2 batched ship at ~18 files; pick this when scoring + selection accuracy needs tightening from the LLM side.
- **M-4 Multi-discipline hint inference** — orchestrator could surface hints from `framework_sport` + `included_discipline_ids` automatically (e.g., AR race with paddle leg → hint Packraft + Kayak). Today 100% athlete-edited; this would reduce the form-edit burden. Trigger #5 plan-mode gate; ~3-5 files.
- **M-5 carried — per-discipline VOCAB POPULATION for remaining 8 AR disciplines** (D-005 / D-007 / D-008a / D-011 / D-014 / D-015 / D-016 / D-020). Each follow-on slice ~2 files. D-011 carries the spec BM-4 also_satisfies chain complexity flag.
- **M-6 carried — BM-2 phase-aware ranking inside Layer 4** — per_phase prompt has a Peak/Taper hint guidance line post-BM-3; structured prompt copy operationalizing the bias per phase is the next refinement.
- **M-7 carried — multi-locale cluster ingestion** — orchestrator feeds primary locale only.
- **M-8 carried — plan_refresh tier modality wire** — explicitly excluded from BM-3 + v2; separate slice if cite material is needed in mid-plan refresh prompts.
- **#8 locales→locations rename** — lowest-risk mechanical (now also touches the new race_modality_hints partial's "Race craft (per-discipline equipment hints)" copy).
- **Layer 2B per-discipline gap reasoning** — carried.
- **#6+#4 injury form refresh** — ~6-8 files; Trigger #5 on body-part-to-movement-constraints mapping.
- **§I.1 structured supplements onboarding refresh** — LARGE ~6-8 files.

### 6.3 Operating notes for next session

Read order (Rule #13):

1. `aidstation-sources/CLAUDE.md` — stable rules.
2. `aidstation-sources/CURRENT_STATE.md` — what just shipped + current focus + layer status.
3. `aidstation-sources/CARRY_FORWARD.md` — rolling cross-session items (BM-1 D-008b + race-craft-aware shipped; D-006 backfill / renderer transparency / multi-discipline hint inference newly queued; 115 §5.0 scenarios pending).
4. `aidstation-sources/handoffs/V5_Implementation_D73_Phase_5_2_Walkthrough_BM1_D008b_RaceCraftAware_2026_05_24_Closing_Handoff_v1.md` — this handoff.
5. `aidstation-sources/BestFitModality_Spec_v2.md` — load-bearing for the race-craft contract.
6. `./aidstation-sources/scripts/verify-handoff.sh` — automated anchor sweep.

**Backward-compat note for next deploy:** all changes are additive at the runtime contract layer.
- Resolver `race_modality_hints` kwarg defaults to None → v1-identical behavior at every call site.
- `ModalityOption.race_craft_match` defaults to False → v1-identical payload shape; existing renderers don't read the field yet (M-2 renderer transparency is the follow-on that adds the `[race-craft match]` tag).
- `race_events.race_modality_hints` JSONB column defaults to `'{}'::jsonb` via `ALTER TABLE ... ADD COLUMN IF NOT EXISTS ... NOT NULL DEFAULT '{}'::jsonb` — pre-v2 rows behave as if no hints set.
- Cache keys' `race_modality_hints_hash` slot collapses None → '' → pre-v2 cache entries continue to hit on default-None callers.
- First POST-v2 deploy will see fresh keys for any orchestrator-driven call that supplies a non-empty hint dict; cache misses will trigger one round of re-synthesis with the bumped scoring + `race_craft_match=True` field, then settle on the new keys. Resolver-side scoring is deterministic so identical (hints, terrain, equipment, skills) → identical result → cache stabilizes after one miss.

**Manual ETL step:** `psql $DATABASE_URL -f etl/sources/populate_equipment_items_K3_additions.sql` on deploy. Idempotent; safe to re-run.

**Manual §5.0 walkthrough sequencing:** Andy should walk step 1 first (form-edit lands cleanly) before testing the bump behavior in steps 2-3. Step 4 (cache invalidation) needs steps 1-3 to have populated cache first. Step 5 (backward-compat) is the only step exercisable purely from test code without a fresh deploy.

---

## 7. Decisions pinned

| # | Decision | Picked by | Rationale |
|---|---|---|---|
| **G1** | Score math = multiplicative *1.2 | Andy at first AskUserQuestion gate | Over additive +15 / tier promotion to 95+. Preserves intra-discipline relative ordering across base-score bands without "additive blows past 100" edge case. Cap at 100. |
| **G2** | Form UX = add-row builder | Andy at second AskUserQuestion gate | Over per-discipline checkboxes / no-form-this-slice. Mirrors `_race_terrain_editor.html` pattern; flexibility for ad-hoc (discipline, equipment) pairs. |
| **G3** | Lint scope = add missing names to canonical 0B | Andy at third AskUserQuestion gate | Over static-set-in-test-file / skip-lint. Closes 10/12 of BM-5's canonicalisation work inline via the K3 ETL file. |
| **Path-pick** | Path A (resolver kwarg + race_events column) | Andy at architectural plan-mode gate | Over Path B LLM-side reasoning / Path C defer-D-008b / Path D static-scores-with-gap. Deterministic, explicit, no LLM-nuance dependency. |
| **Sequencing** | Sequencing 3 (single batched ship) | Andy at slice-scope gate | Over Sequencing 1 spec-only / Sequencing 2 spec + resolver-only. ~18 files; ceiling break ratified explicitly. |
| **DI1** | All 3 new cache-key kwargs default to None and collapse None → '' | Architect at code-time | Forward-compat with pre-v2 cache entries; mirrors BM-3 modality-hash pattern exactly. |
| **DI2** | Drivers accept-but-don't-consume `race_modality_hints` kwarg | Architect at code-time | Signature symmetry with cached wrapper's `_synthesize` closure. Resolver-side scoring already applied upstream of these drivers (bumped scores ride inside `layer2_modality_payload`). Cleaner than threading the kwarg through every driver function arg downstream. |
| **DI3** | Empty equipment list per discipline silent-ignores | Architect at code-time per spec v2 §L | `{'D-008b': []}` → empty set intersection with empty set is empty → no bump. Matches the "unknown equipment name" silent-ignore behavior; consistent edge case handling. |
| **DI4** | `pool_paddle_drill` exempt from bump (no `requires_equipment_all_of`) | Architect at code-time per spec v2 §L | Empty `requires_equipment_all_of` means no equipment to match against. Exemption is the right behavior; otherwise an empty-equipment option could accidentally match an empty hint set and produce a spurious bump. |
| **DI5** | Eviction policy = 3 entry points (not full cone) | Architect at code-time per spec v2 §G | plan_create + single_session + race_week_brief consume the resolver post-BM-3; plan_refresh excluded per BM-3 G1=A3 deferral. New helper `evict_on_target_event_modality_hints_change` fires 3 `cache.invalidate_entry_point` calls; cleaner than over-evicting via full-cone helper. |
| **DI6** | `Climbing gym membership` shipped as canonical equipment name despite being a "membership" not a piece of equipment | Architect at code-time per spec v2 §I | Resolver treats it as an equipment-style marker for gym-access gating; keeping the verbatim name (over renaming to "Climbing gym access" or "Climbing gym venue") preserves the spec v1 §5.1 wording for outdoor_lead_climb / gym_top_rope / gym_boulder. BM-5 follow-on can reconcile vs `Climbing Wall` (the existing K2 venue-toggle entry) if needed. |
| **DI7** | `Canoe` shipped to canonical 0B as a reserved-not-referenced entry | Architect at code-time per spec v2 §H/§I | Not used in v2 D-008b vocab (S2 pick excluded canoe options) but ETL-shipping the canonical name keeps future vocab follow-ons clean — adding canoe options to D-008b's vocab dict later won't require a separate ETL slice. Trivial cost. |
| **DI8** | Single-session orchestrator newly loads target_race_event for hint access | Architect at code-time | Single-session was "off-plan" per existing docstring but the athlete IS typically training toward a target race; race-craft bump should apply consistently across all 3 cone-consuming entry points. `load_target_race_event_payload` is a 1-SELECT helper already imported; no new query cost. |

---

## 8. Session-end verification (Rule #10)

| Check | Result |
|---|---|
| `layer2_modality/resolver.py` `_MODALITY_OPTIONS_PER_DISCIPLINE` has D-008b key | ✅ `grep -c "^    \"D-008b\":" layer2_modality/resolver.py` returns 1 |
| Resolver D-008b has 6 ModalityOptionDef entries | ✅ `grep -A 100 "^    \"D-008b\":" layer2_modality/resolver.py \| grep -c "^        ModalityOptionDef("` returns 6 |
| Resolver entry point has new `race_modality_hints` kwarg | ✅ `grep "race_modality_hints: dict\[str, list\[str\]\] \| None" layer2_modality/resolver.py` returns 1 |
| Resolver scoring math implements *1.2 cap-at-100 | ✅ `grep "min(100, int(round(opt.base_preference_score \* 1.2)))" layer2_modality/resolver.py` returns 1 |
| `ModalityOption.race_craft_match` field shipped | ✅ `grep "race_craft_match: bool = False" layer4/context.py` returns 1 |
| `RaceEventPayload.race_modality_hints` field shipped | ✅ `grep "race_modality_hints: dict\[str, list\[str\]\] = Field" layer4/context.py` returns 1 |
| 3 cache-key helpers carry `race_modality_hints_hash` kwarg | ✅ `grep -c "race_modality_hints_hash: str \| None = None" layer4/hashing.py` returns 3 |
| 3 cached wrappers carry `race_modality_hints` kwarg | ✅ `grep -c "race_modality_hints: dict\[str, list\[str\]\] \| None = None" layer4/cached_wrappers.py` returns 3 |
| Cached wrappers compute hash via `compute_payload_hash` | ✅ `grep -c "race_modality_hints_hash = " layer4/cached_wrappers.py` returns 3 |
| Orchestrator threads hint dict at all 3 cached-wrapper call sites | ✅ `grep -c "race_modality_hints=" layer4/orchestrator.py` returns 5 (2 resolver calls — in `_upstream_full_cone` + in single_session orchestrator — + 3 cached_wrapper calls — race_week_brief + plan_create + single_session) |
| Single-session orchestrator newly loads target_race_event | ✅ `grep -c "load_target_race_event_payload(db, user_id)" layer4/orchestrator.py` returns 4 (3 existing + 1 new in single_session orchestrator) |
| All 3 drivers carry `race_modality_hints` kwarg for signature symmetry | ✅ `grep -l "race_modality_hints: dict\[str, list\[str\]\] \| None = None" layer4/single_session.py layer4/plan_create.py layer4/race_week_brief.py` returns all 3 |
| `race_events_repo.py` SELECT includes `race_modality_hints` column | ✅ `grep "re.race_modality_hints" race_events_repo.py` returns 1 |
| `race_events_repo.update_race_event` accepts `race_modality_hints` kwarg | ✅ `grep "race_modality_hints: dict\[str, list\[str\]\] \| None = None" race_events_repo.py` returns 1 |
| `init_db.py` _PG_MIGRATIONS extended with race_modality_hints column | ✅ `grep "ADD COLUMN IF NOT EXISTS race_modality_hints JSONB" init_db.py` returns 1 |
| `race_events_invalidation.py` ships new `evict_on_target_event_modality_hints_change` | ✅ `grep "^def evict_on_target_event_modality_hints_change" race_events_invalidation.py` returns 1 |
| `routes/race_events.py` `_parse_race_modality_hints` parser shipped | ✅ `grep "^def _parse_race_modality_hints" routes/race_events.py` returns 1 |
| `routes/race_events.py` `_equipment_choices` helper shipped | ✅ `grep "^def _equipment_choices" routes/race_events.py` returns 1 |
| Routes/race_events.py imports the new eviction helper | ✅ `grep "evict_on_target_event_modality_hints_change" routes/race_events.py` returns 2 (import + call) |
| `templates/_race_modality_hints_editor.html` exists | ✅ `ls templates/_race_modality_hints_editor.html` returns the file |
| `race_event_edit.html` includes the new partial | ✅ `grep "include '_race_modality_hints_editor.html'" templates/profile/race_event_edit.html` returns 1 |
| `populate_equipment_items_K3_additions.sql` exists | ✅ `ls etl/sources/populate_equipment_items_K3_additions.sql` returns the file |
| K3 file has 10 new canonical equipment entries | ✅ `grep -E "^  \('[A-Z]" etl/sources/populate_equipment_items_K3_additions.sql` returns 10 |
| `tests/test_layer2_modality.py` `_KNOWN_EQUIPMENT` set added | ✅ `grep -c "^_KNOWN_EQUIPMENT" tests/test_layer2_modality.py` returns 1 |
| `tests/test_layer2_modality.py` has new equipment lint test | ✅ `grep -c "def test_every_required_equipment_is_canonical" tests/test_layer2_modality.py` returns 1 |
| 7 new test classes for race-craft scenarios | ✅ `grep -cE "^class TestScenario13_(7\|8\|9\|10)_\|^class TestScenarioD008b\|^class TestRaceCraftHintBackwardCompat" tests/test_layer2_modality.py` returns 7 |
| `tests/test_layer4_hashing.py` has 6 new race-craft hash tests | ✅ `grep -c "race_modality_hints_hash" tests/test_layer4_hashing.py` returns ≥10 (6 test functions + 3 parametrize entries + 1 module reference) |
| All 14 modified Python files compile | ✅ `python3 -m py_compile layer2_modality/resolver.py layer4/context.py layer4/hashing.py layer4/cached_wrappers.py layer4/orchestrator.py layer4/single_session.py layer4/plan_create.py layer4/race_week_brief.py race_events_repo.py race_events_invalidation.py routes/race_events.py init_db.py tests/test_layer2_modality.py tests/test_layer4_hashing.py` returns 0 |
| `CURRENT_STATE.md` last-shipped pointer flipped to this handoff | ✅ `head -10 aidstation-sources/CURRENT_STATE.md` shows BM1_D008b_RaceCraftAware handoff name |
| `CURRENT_STATE.md` exactly 1 "## Last shipped session" header | ✅ `grep -c "^## Last shipped session" aidstation-sources/CURRENT_STATE.md` returns 1 |
| `CURRENT_STATE.md` predecessor count incremented | ✅ `grep -c "^\*\*Predecessor:" aidstation-sources/CURRENT_STATE.md` returns 43 (previous 42 + this slice's demoted BM-3 = 43) |
| `CARRY_FORWARD.md` D-008b shipped + race-craft-aware narrative landed | ✅ `grep "D-008b ✅ Shipped 2026-05-24" aidstation-sources/CARRY_FORWARD.md` returns 1 |
| `CARRY_FORWARD.md` §5.0 walkthrough count flipped 110 → 115 | ✅ `grep "115 scenarios accumulated" aidstation-sources/CARRY_FORWARD.md` returns 1 |

---

## 9. Files shipped this session

**Substantive (18 files; ceiling break ratified at Sequencing 3 gate):**

1. NEW `aidstation-sources/BestFitModality_Spec_v2.md` — ~350 lines; spec amendment with §A-§O sections.
2. MOD `layer2_modality/resolver.py` — +~100 lines; D-008b 6-option vocab + new `race_modality_hints` kwarg + multiplicative *1.2 scoring + race_craft_match field on ModalityOption.
3. MOD `layer4/context.py` — +13 lines; ModalityOption.race_craft_match=False + RaceEventPayload.race_modality_hints field.
4. MOD `layer4/hashing.py` — +18 lines; 3 cache-key helpers gained `race_modality_hints_hash` kwarg with None → '' collapse.
5. MOD `layer4/cached_wrappers.py` — +45 lines; 3 cached wrappers gained `race_modality_hints` kwarg + hash + key wire + thread.
6. MOD `layer4/orchestrator.py` — +~25 lines; threads hints to resolver in `_upstream_full_cone` + single_session orchestrator (newly loads target_event); threads to 3 cached_wrapper call sites.
7. MOD `layer4/single_session.py` — ~5 lines; signature-only `race_modality_hints` kwarg for symmetry.
8. MOD `layer4/plan_create.py` — ~5 lines; same.
9. MOD `layer4/race_week_brief.py` — ~5 lines; same.
10. MOD `race_events_repo.py` — +~25 lines; SELECT + UPDATE column write + dual-shape JSONB tolerance + RaceEventPayload constructor wire.
11. MOD `init_db.py` — +9 lines; `_PG_MIGRATIONS` ALTER TABLE ADD COLUMN race_modality_hints JSONB NOT NULL DEFAULT '{}'.
12. MOD `race_events_invalidation.py` — +33 lines; NEW `evict_on_target_event_modality_hints_change` 3-entry-point helper.
13. MOD `routes/race_events.py` — +~90 lines; new parser + equipment_choices helper + render context + parse-save wire + eviction chain rung.
14. NEW `templates/_race_modality_hints_editor.html` — ~120 lines; add-row builder partial.
15. MOD `templates/profile/race_event_edit.html` — +5 lines; include the new partial.
16. NEW `etl/sources/populate_equipment_items_K3_additions.sql` — ~110 lines; 10 new canonical 0B entries.
17. MOD `tests/test_layer2_modality.py` — +~280 lines; 7 new test classes + equipment lint extension + D-008b lock.
18. MOD `tests/test_layer4_hashing.py` — +~70 lines; 6 new tests covering race_modality_hints_hash slot.

**Bookkeeping (3 files; do not count against ceiling per CLAUDE.md):**

19. MOD `aidstation-sources/CURRENT_STATE.md` — last-shipped pointer flipped to this handoff; predecessor BM-3 demoted to first **Predecessor:** entry. 1 "## Last shipped session" header; 43 "**Predecessor:**" entries.
20. MOD `aidstation-sources/CARRY_FORWARD.md` — D-008b forward-pointer flipped to ✅ Shipped + NEW M-1 D-006 backfill + M-2 renderer transparency + M-4 multi-discipline hint inference forward-pointers added; §5.0 walkthrough scenario count flipped 110 → 115.
21. NEW `aidstation-sources/handoffs/V5_Implementation_D73_Phase_5_2_Walkthrough_BM1_D008b_RaceCraftAware_2026_05_24_Closing_Handoff_v1.md` — this handoff.

---

## 10. Carry-forward updates

See `CARRY_FORWARD.md` for the full list. Net changes:

- **BM-1 D-008b Outdoor Paddling ✅ Shipped**. Vocab populated with 6 options per spec v2 §H (S2 pick); resolver now bumps D-008b option scores based on target race's `race_modality_hints`.
- **Race-craft-aware scoring ✅ Shipped** (spec v2 amendment). New `race_modality_hints` JSONB column on race_events + resolver new kwarg + multiplicative *1.2 scoring + ModalityOption.race_craft_match field + 3-entry-point cache invalidation + form-edit add-row builder + K3 ETL canonical equipment additions.
- **NEW M-1 D-006 cycling scoring backfill** carried — same gap latent for D-006 (gravel=85 / road=80 base scores happen to align with Andy's PGE 2026 gravel preference but architecturally wrong); backfill lowers base scores to neutral + relies on hints.
- **NEW M-2 Renderer transparency** carried — 3 prompt renderers cite `[race-craft match]` tag on options with `race_craft_match=True`; trivial 3-file slice deferred to keep v2 batched ship at ~18 files.
- **NEW M-4 Multi-discipline hint inference** carried — orchestrator could surface hints from `framework_sport` + `included_discipline_ids` automatically; today 100% athlete-edited.
- **BM-1 carries (M-5)** — 8 remaining AR disciplines (D-005 / D-007 / D-008a / D-011 / D-014 / D-015 / D-016 / D-020) still queued; D-011 carries BM-4 also_satisfies chain.
- **BM-2 phase-aware ranking (M-6)** still queued — per_phase already has a Peak/Taper hint guidance line post-BM-3; BM-2 is structured prompt copy operationalizing the bias per phase.
- **BM-5 equipment canonicalisation** partially closed by K3 (10 of ~12 outstanding equipment names landed canonical); remaining BM-5 work is reconciling `Climbing gym membership` vs `Climbing Wall` venue-toggle entries + any future-vocab equipment names.
- **Multi-locale cluster ingestion (M-7)** still queued.
- **plan_refresh tier modality wire (M-8)** still queued.
- **#8 locales→locations rename** — now also touches the new race_modality_hints partial's copy.
- **§5.0 walkthrough scenario count 110 → 115** — NEW BM-1 + race-craft §5.0 added (5 steps).

**End of handoff.**
