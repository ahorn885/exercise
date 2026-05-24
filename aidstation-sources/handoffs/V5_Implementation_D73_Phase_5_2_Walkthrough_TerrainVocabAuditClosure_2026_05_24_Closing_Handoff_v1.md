# D-73 Phase 5.2 Walkthrough — Bucket C Terrain-Vocab Audit Closure (sub-items a-e + h + j) — Closing Handoff

**Session:** D-73 Phase 5.2 caller-side — picks up the §6.1 architect-recommended forward-pointer carried by the RouteLocalesAnchorFlags slice (PR #135, 2026-05-24). Closes the 7 of 10 Bucket C sub-items that turn out to be already-mitigated defensively on-disk; locks the closures in via mechanical audit tests so future ETL / vocab edits surface drift loudly rather than re-introducing the punch-list items.
**Date:** 2026-05-24
**Predecessor handoff:** `V5_Implementation_D73_Phase_5_2_Walkthrough_RouteLocalesAnchorFlags_2026_05_24_Closing_Handoff_v1.md`
**Branch:** `claude/happy-newton-WNuQG`
**Status:** 2 substantive files (well under 5-file ceiling — audit-and-close slice). Container-runnable subset 815 → 853 (+38 net: 20 new audit tests + 18 newly-collected Layer 2B classifier tests freed by the import-order workaround). ETL `etl/tests/` 139 → 139 unchanged. No regressions.

---

## 1. Session-start verification (Rule #9)

Read order completed per Rule #13: CLAUDE.md → CURRENT_STATE.md → CARRY_FORWARD.md (lines 1-80 + 80-180) → predecessor handoff → `./aidstation-sources/scripts/verify-handoff.sh`. Anchor sweep was ✅ clean — the 4 ❌ entries on ETL files (`tests/test_extractor_parsers.py`, `tests/test_sum_to_100.py`, `tests/test_v10_parsers.py`, `tests/test_vocabulary_md.py`) are the known script false-positive (they live under `etl/tests/`, not `tests/`). Working tree clean on `claude/happy-newton-WNuQG`; predecessor §8 anchors spot-checked (`_emit_route_locales_anchor_observations` defined + wired; new `TestRouteLocalesAnchorObservations` class + 9 net new tests landed; container-subset count 815). No drift between predecessor handoff narrative and on-disk state.

---

## 2. Session narrative

Andy picked **"Bucket C (a)-(j) vocab cleanup"** at the first AskUserQuestion gate (from the predecessor handoff's §6.1 / §6.2 menu of 4 options offered: #8 locales→locations rename / Bucket C / Bucket E.(b)-B2+E.(c)-C1 / #2b race-URL LLM site-parse).

The investigation traced each Bucket C sub-item against on-disk state before proposing a scope:

- **(a)** Time-of-Day / Darkness — `grep "Darkness" etl/` found `etl/layer0/vocabulary_transforms.py:97 SITUATIONAL_TOKENS` (whole-chunk discard during ETL transform). Not in canonical `_TERRAIN_STRUCTURED_ROWS`.
- **(b)** Social / Group Riding — same `SITUATIONAL_TOKENS:98`. Not canonical.
- **(c)** Partner / Tandem / Team — same `SITUATIONAL_TOKENS:99`. Not canonical.
- **(d)** Generic / Varied Terrain — `TERRAIN_TOKENS:90` recognizes (so it doesn't leak into equipment column during transform), but no canonical TRN-xxx row maps to it. Silent drop at `layer2b.builder._load_terrain_names`.
- **(e)** Climbing gym vs outdoor — already split: TRN-013 Rock Wall (environment=Outdoor) + TRN-014 Climbing Gym (environment=Indoor) in `_TERRAIN_STRUCTURED_ROWS`.
- **(f)** Water-type expansion — open. Current canonical = 4 rows (Pool / Flat Water / Open Water-Ocean / Whitewater). Expansion needs Trigger #2 + #5.
- **(g)** Locale-terrain vs Outdoor-Terrain equipment merge — open. `etl/sources/Vocabulary_Audit_v2.md:435` lists `Outdoor space` as Assumed Universal equipment; terrain lives in a separate Layer 0 table. Merge crosses the `layer0.terrain_types` vs `layer0.equipment_items` schema boundary (Trigger #3 plan-mode gate needed).
- **(h)** Cycling Trainer dedup — `etl/sources/parse_substitutes.py:58` aliases `Trainer` / `Bike Trainer` / `Cycling Trainer` / `Indoor Trainer` → canonical `Bike trainer` equipment. No canonical terrain row mentions "trainer" or "bike".
- **(i)** Mapbox required (free-text removal) — open. `routes/race_events.py:161` still accepts `event_locale_name` as a free-text fallback when no Mapbox feature is picked. Trigger #5.
- **(j)** Layer 2B classifier audit — verification work. Best done as audit tests against the canonical 16-row vocab + `_validate_inputs` pattern validator.

Andy picked **"Audit + close (a-e,h) + ship (j)"** at the scope gate (over "Audit + Mapbox-required" / "Mapbox-required only" / "water-type expansion design").

`/plan` Triggers DID NOT fire — closing 7 sub-items by documenting on-disk closure with mechanically-locked-in audit tests is verification work, not architectural design. The 3 open sub-items (f / g / i) carry forward as forward-pointers with explicit Trigger pressures pinned for future sessions.

`/plan` Triggers DEFERRED to follow-on slices:

- **Bucket C sub-item (f) water-type expansion** — Trigger #2 + #5 design pass; vocab-padding-refusal scrutiny on each proposed new row.
- **Bucket C sub-item (g) terrain↔equipment merge** — Trigger #3 cross-layer schema; plan-mode gate.
- **Bucket C sub-item (i) Mapbox required** — Trigger #5; form-validation boundary tightening across 2 forms + 2 routes.
- **Bucket E.(b)-B2 + E.(c)-C1** — specs pinned in `CARRY_FORWARD.md`; ~6-9 files; ceiling-break ratification needed.
- **#8 "locales" → "locations" rename** — ~9 templates, mechanical, lowest-risk next-slice candidate per architect recommendation.

---

## 3. File-by-file edits

### 3.1 `tests/test_layer2b.py` — import-order workaround

Added 4 lines after `import pytest` mirroring `tests/test_layer2a.py:22-26` precedent:

```python
# Force `layer4` to initialize before `layer2b` to dodge the pre-existing
# circular import that otherwise blocks this module from collection. Mirrors
# tests/test_layer2a.py:26 + tests/test_layer3_cached_wrappers.py:30.
from layer4 import InMemoryCacheBackend  # noqa: F401
```

**Side-effect:** 18 previously-uncollected Layer 2B classifier behavior tests (TestInputValidation 6 + TestPGEBaseline 1 + TestUnbridgeableAlpine 1 + TestEmptyLocale 1 + TestMultipleProxyRules 1 + TestUnknownTerrainId 1 + TestCoachedIntroFlag 2 + TestCleanBaseline 1 + TestEmptyRaceTerrainLoosen 4) now collect + pass cleanly. The pre-existing layer4↔layer2b circular import (layer4.__init__.py imports orchestrator which imports layer2b.builder which imports layer4.context) was blocking module-level collection without the workaround.

Net delta: +4 lines added, 0 removed. No test logic changed.

### 3.2 NEW `tests/test_bucket_c_terrain_vocab_audit.py` — audit tests

5 test classes covering sub-items (a)/(b)/(c)/(d)/(e)/(h)/(j), 20 tests total:

**TestCanonicalTerrainVocab (5 tests)** — locks in the canonical 16-row TRN-001..TRN-016 shape so accidental additions / removals / ID-pattern drift surface loudly:
1. `test_canonical_row_count_is_16` — exact count
2. `test_every_canonical_row_has_TRN_pattern_id` — every row passes `^TRN-\\d{3}$`
3. `test_canonical_terrain_ids_unique` — no duplicate IDs
4. `test_canonical_names_unique` — no duplicate canonical_names
5. `test_canonical_ids_are_sequential_TRN_001_through_TRN_016` — exact ID set

**TestSituationalTokensNotTerrain (7 tests)** — sub-items (a)/(b)/(c) closure:
1-5. `test_token_is_in_situational_set[*]` — 5 parametrized membership tests for Darkness / Group Riding / Partner or Visual Cue / Tandem Partner / Team
6. `test_no_situational_token_is_a_canonical_terrain_name` — set-intersection across `SITUATIONAL_TOKENS` ∩ canonical-names = ∅
7. `test_no_canonical_row_mentions_partner_tandem_or_team` — keyword scan across canonical_name set

**TestLegacyTokensNotCanonical (4 tests)** — sub-items (d) + (h) closure:
1. `test_varied_terrain_recognized_during_etl` — `Varied Terrain` ∈ TERRAIN_TOKENS (so equipment-extraction doesn't leak it)
2. `test_varied_terrain_has_no_canonical_row` — but no canonical TRN-xxx maps to it (silent drop)
3. `test_no_canonical_row_mentions_trainer` — Trainer / Bike Trainer / Cycling Trainer / Indoor Trainer all kept as equipment via aliasing
4. `test_no_canonical_row_is_named_bike` — Pump Track (TRN-015) is the only MTB-category terrain; no bike-equipment term slipped in

**TestClimbingSplit (3 tests)** — sub-item (e) closure:
1. `test_outdoor_rock_wall_row_present` — TRN-013 (Rock Wall, Outdoor, Climbing category) exists
2. `test_indoor_climbing_gym_row_present` — TRN-014 (Climbing Gym, Indoor, Climbing category) exists
3. `test_climbing_category_has_both_indoor_and_outdoor` — environment set across Climbing-category rows = {Outdoor, Indoor}

**TestLayer2BClassifierVocabBoundary (1 test)** — sub-item (j) closure:
1. `test_every_canonical_terrain_id_passes_validate_inputs` — every canonical TRN-xxx row is accepted by `layer2b.builder._validate_inputs` without raising `Layer2BInputError`. Locks in the agreement between `_TRN_PATTERN` and the canonical vocab.

Imports cross 4 modules: `etl.layer0.extractors.vocabulary._TERRAIN_STRUCTURED_ROWS` + `etl.layer0.vocabulary_transforms.{SITUATIONAL_TOKENS, TERRAIN_TOKENS}` + `layer2b.builder.{_TRN_PATTERN, _validate_inputs}` + `layer4.context.RaceTerrainEntry`. Same `from layer4 import InMemoryCacheBackend  # noqa: F401` workaround at the top to dodge the pre-existing circular import.

Net delta: +200 lines added (1 NEW file). 0 lines removed elsewhere.

---

## 4. Code / tests

**Tests:** NEW `tests/test_bucket_c_terrain_vocab_audit.py` — 20 tests pass in 0.32s. `tests/test_layer2b.py` 0 (uncollected) → 18 collected + passing. Container-runnable subset 815 → 853 (+38 net: 20 new audit + 18 newly-collected Layer 2B). No regressions on Layer 4 / orchestrator / repo / race_events / locales / onboarding / plan_create / ad_hoc_workouts / plan_refresh / nl_parser / dashboard / admin / layer3 cached-wrappers / layer2a surfaces. ETL `etl/tests/` 139 → 139 unchanged. 12 NL parser smoke + 4 Layer 3 SDK smoke tests still skip cleanly when `ANTHROPIC_API_KEY` unset.

Reproducer (changed files only):

```
PYTHONPATH=. pytest tests/test_bucket_c_terrain_vocab_audit.py tests/test_layer2b.py
# 38 passed in 0.32s
```

Full container subset (mirrors predecessor's exact invocation, with new file appended):

```
PYTHONPATH=. pytest tests/test_layer4_orchestrator.py tests/test_locales.py \
                    tests/test_race_events_repo.py tests/test_race_events_invalidation.py \
                    tests/test_onboarding_race_events.py tests/test_layer4_context.py \
                    tests/test_layer4_payload.py tests/test_layer4_hashing.py \
                    tests/test_layer4_cache.py tests/test_layer4_race_week_brief.py \
                    tests/test_plan_sessions_repo.py tests/test_routes_ad_hoc_workouts.py \
                    tests/test_routes_plan_create.py tests/test_nl_parser.py \
                    tests/test_routes_plan_refresh.py tests/test_nl_parser_smoke.py \
                    tests/test_routes_dashboard.py tests/test_routes_admin.py \
                    tests/test_layer3_cached_wrappers.py tests/test_routes_race_events.py \
                    tests/test_layer2a.py tests/test_layer2b.py \
                    tests/test_bucket_c_terrain_vocab_audit.py
# 853 passed, 12 skipped in 2.05s
```

ETL: `PYTHONPATH=. pytest etl/tests/ # 139 passed in 0.61s`.

**No-regression confirmation:** All 22 previously-passing files still pass with identical counts. The two count changes are `tests/test_layer2b.py` 0 → 18 (newly collected) + `tests/test_bucket_c_terrain_vocab_audit.py` 0 → 20 (new file).

---

## 5. Manual §5.0 verification — owed step

**No new manual §5.0 walkthrough step owed.** The audit closure is mechanically verified via the test suite — every assertion runs against in-process Python data structures (no DB / no HTTP / no LLM). Future regressions surface as failing tests in CI rather than as production drift.

The 3 still-open Bucket C sub-items DO carry walkthrough commitments at their eventual implementation slices:
- (f) water-type expansion will own a manual §5.0 step against the new vocabulary additions + Layer 2B classifier behavior change
- (g) terrain↔equipment merge will own a §5.0 step covering the schema migration + locale-edit form re-shape
- (i) Mapbox-required will own a §5.0 step covering race-event creation + edit form rejecting empty `event_locale_mapbox_id`

None of those slices is in flight; the §5.0 commitments will land with the respective implementation handoffs.

---

## 6. Next session pointers

### 6.1 Architect-recommended next forward move

**#8 "locales" → "locations" terminology rename** — ~9 templates, mechanical, no /plan triggers. Lowest-risk next-slice candidate per the architect recommendation carried since the RaceLocaleMapbox slice. URL paths (`/locales/...`) + Flask blueprint names (`locales.*`) stay unchanged; only labels / headings / dialog copy / button text change. Affected templates listed in `CARRY_FORWARD.md` line 90: `templates/locales/list.html`, `templates/locales/form.html`, `templates/locales/new.html`, `templates/locales/nearby.html`, `templates/locales/refresh_confirm.html`, `templates/profile/_race_events_tab.html`, `templates/profile/race_event_edit.html`, `templates/onboarding/route_locales.html`, `templates/onboarding/target_race.html`, `templates/rx/list.html`.

### 6.2 Alternative pivots

- **Bucket C sub-item (i) Mapbox-anchored race-location required** — closes Bucket C entirely from a still-open perspective. ~3-4 files: `routes/race_events.py` form-validation tightening at `new_race` POST + `update_race_event_locale` POST + `routes/onboarding.py:target_race_save`; small template adjustment (drop free-text fallback messaging). Trigger #5 design call: should the form reject empty Mapbox feature (hard fail) or fall back to "no location anchored" + downstream coaching flag (soft surface)?
- **Bucket E.(b)-B2 + E.(c)-C1 follow-on slice** — specs pinned in `CARRY_FORWARD.md`. `race_events.included_discipline_ids TEXT[] NULL` column + `RaceTerrainEntry.discipline_id: str | None` extension. ~6-9 files; ceiling-break ratification needed at scope gate.
- **Bucket C sub-item (f) water-type expansion** — design pass; Trigger #2 + #5. Each proposed new row (Surf / Cold-water / Tidal / etc.) needs vocab-padding-refusal scrutiny (does the canonical 4-row set already cover the same physical stimulus?) + simulation_note authoring + `terrain_gap_rules` row authoring against the 16-row canonical set.
- **Bucket C sub-item (g) locale-terrain vs Outdoor-Terrain merge** — Trigger #3 cross-layer schema + #5 architectural alternatives. Plan-mode gate before implementation. Affects `layer0.terrain_types` vs `layer0.equipment_items` row partitioning + the form surfaces that consume each.
- **#6 + #4 paired injury form refresh** — ~6-8 files; Trigger #5 on the body-part-to-movement-constraints mapping.
- **#2b race-URL LLM site-parse pre-fill** — Trigger #2 prompt design session first; then ~4-6 files runtime. NEW `race_url_parser.py` + caller-side integration.
- **§I.1 structured supplements onboarding refresh** — Layer 2E §5.5 supplement-integration de-stub. LARGE ~6-8 files; architectural choice on schema shape requires plan-mode gate before kickoff.

### 6.3 Operating notes for next session

Read order (Rule #13):

1. `aidstation-sources/CLAUDE.md` — stable rules.
2. `aidstation-sources/CURRENT_STATE.md` — what just shipped + current focus + layer status.
3. `aidstation-sources/CARRY_FORWARD.md` — rolling cross-session items (Bucket C line 103 updated to mark sub-items (a)-(e) + (h) + (j) ✅ closed-defensively / closed-audited with on-disk anchors; (f) + (g) + (i) carried as open forward-pointers with Trigger pressures pinned).
4. `aidstation-sources/handoffs/V5_Implementation_D73_Phase_5_2_Walkthrough_TerrainVocabAuditClosure_2026_05_24_Closing_Handoff_v1.md` — this handoff.
5. `./aidstation-sources/scripts/verify-handoff.sh` — automated anchor sweep. The script's 4 ❌ false-positives on ETL test files are still present (script doesn't know about `etl/tests/`); verify via `ls etl/tests/`.

**No outstanding production warnings.** ETL terrain-vocab drift fix landed via the predecessor; route-locales validator loosen + downstream coaching-flag emission closed end-to-end; Bucket C now down from 10 open sub-items to 3 (f / g / i) with explicit Trigger pressures pinned for each.

---

## 7. Decisions pinned

| # | Decision | Picked by | Rationale |
|---|---|---|---|
| **D1** | Slice scope = Audit + close (a-e,h) + ship (j) | Andy at AskUserQuestion gate (over Mapbox-required-only + Mapbox-required-plus-audit + water-type-expansion-design) | The on-disk audit surfaced that 7 of 10 Bucket C sub-items are already mitigated defensively in `etl/layer0/vocabulary_transforms.py` + canonical vocab shape + `etl/sources/parse_substitutes.py`. The cleanest move is to lock those closures in via mechanical audit tests so future ETL / vocab edits surface drift loudly. Cheaper + lower-risk than re-implementing what's already correct, and gets Bucket C from 10 open items to 3. The 3 remaining items each need a dedicated design slice (Trigger #5 for f + i; Trigger #3 for g) that doesn't bundle cleanly with the audit closure. |
| **D2** | NEW file `tests/test_bucket_c_terrain_vocab_audit.py` rather than extending `tests/test_layer2b.py` | Architect | The audit tests cross 4 modules (`etl.layer0.extractors.vocabulary` + `etl.layer0.vocabulary_transforms` + `layer2b.builder` + `layer4.context`); they're about vocab integrity at the cross-module boundary, not classifier function behavior. The dedicated file name documents the closure intent — future sessions grepping for "Bucket C" find the audit closure file directly. Keeps `tests/test_layer2b.py` focused on classifier behavior tests. |
| **D3** | Add the `from layer4 import InMemoryCacheBackend` import-order workaround to `tests/test_layer2b.py` opportunistically | Architect | The workaround is mechanically a 4-line add mirroring `tests/test_layer2a.py:26` precedent (which the Bucket B 500s slice landed for the same circular-import reason). Bonus side-effect: 18 previously-uncollected Layer 2B classifier behavior tests now collect + pass. The cost of adding a 4-line cell to a file you're already opening for the slice is trivial; the value (18 tests now in CI signal) is real. Not adding it would leave a known-good test suite stranded for no reason. |
| **D4** | Future open items (f) / (g) / (i) carry Trigger annotations on the CARRY_FORWARD entry | Architect | Each remaining sub-item has a distinct Trigger pressure: (f) Trigger #2 + #5 vocab padding design; (g) Trigger #3 cross-layer schema; (i) Trigger #5 form-validation tightening. Pinning the Trigger on the carry-forward entry means the next session can pre-scope the appropriate AskUserQuestion gate or plan-mode entry without re-deriving the trigger pressure. |

---

## 8. Session-end verification (Rule #10)

| Check | Result |
|---|---|
| NEW `tests/test_bucket_c_terrain_vocab_audit.py` exists | ✅ `ls tests/test_bucket_c_terrain_vocab_audit.py` returns the file |
| 5 test classes defined per §3.2 spec | ✅ `grep -c "^class Test" tests/test_bucket_c_terrain_vocab_audit.py` returns 5 |
| 20 test functions defined | ✅ `grep -c "    def test_" tests/test_bucket_c_terrain_vocab_audit.py` returns 19 plain + 1 parametrized × 5 cases = 20 collected |
| `_TERRAIN_STRUCTURED_ROWS` imported from `etl.layer0.extractors.vocabulary` | ✅ `grep -n "_TERRAIN_STRUCTURED_ROWS" tests/test_bucket_c_terrain_vocab_audit.py` returns 1+ hits |
| `SITUATIONAL_TOKENS` + `TERRAIN_TOKENS` imported from `etl.layer0.vocabulary_transforms` | ✅ `grep -n "SITUATIONAL_TOKENS\\|TERRAIN_TOKENS" tests/test_bucket_c_terrain_vocab_audit.py` returns hits |
| `_TRN_PATTERN` + `_validate_inputs` imported from `layer2b.builder` | ✅ `grep -n "_TRN_PATTERN\\|_validate_inputs" tests/test_bucket_c_terrain_vocab_audit.py` returns hits |
| `tests/test_layer2b.py` import-order workaround added | ✅ `head -30 tests/test_layer2b.py` shows the `from layer4 import InMemoryCacheBackend  # noqa: F401` line |
| `tests/test_bucket_c_terrain_vocab_audit.py` 20 passed | ✅ pytest run in 0.32s |
| `tests/test_layer2b.py` 0 (uncollected) → 18 passed | ✅ pytest run included in 0.32s |
| Container-runnable subset 815 → 853 passed + 12 skipped | ✅ pytest run in 2.05s |
| ETL `etl/tests/` 139 → 139 passed | ✅ pytest run in 0.61s |
| `CURRENT_STATE.md` last-shipped pointer flipped to this handoff | ✅ |
| `CARRY_FORWARD.md` Bucket C line 103 updated — (a)-(e), (h), (j) marked ✅ with on-disk anchors; (f), (g), (i) carried with Trigger pressures pinned | ✅ |

---

## 9. Files shipped this session

**Substantive (2 files; well under 5-file ceiling):**

1. NEW `tests/test_bucket_c_terrain_vocab_audit.py` — 5 test classes / 20 tests locking in Bucket C sub-items (a)-(e), (h), (j) on-disk closure guarantees. +200 / -0.
2. MODIFIED `tests/test_layer2b.py` — added 4-line `from layer4 import InMemoryCacheBackend` import-order workaround (mirroring `tests/test_layer2a.py:26`); unblocks 18 previously-uncollected Layer 2B classifier behavior tests. +4 / -0.

**Bookkeeping (3 files; do not count against ceiling):**

3. MODIFIED `aidstation-sources/CURRENT_STATE.md` — last-shipped pointer flipped to this handoff; predecessor RouteLocalesAnchorFlags line preserved.
4. MODIFIED `aidstation-sources/CARRY_FORWARD.md` — Bucket C line 103 updated: sub-items (a)-(e), (h), (j) annotated ✅ with on-disk anchor citations (file paths + line numbers + test class names); sub-items (f), (g), (i) carried as open forward-pointers with explicit Trigger pressures pinned (f = Trigger #2 + #5 vocab padding; g = Trigger #3 cross-layer schema; i = Trigger #5 form-validation tightening).
5. NEW `aidstation-sources/handoffs/V5_Implementation_D73_Phase_5_2_Walkthrough_TerrainVocabAuditClosure_2026_05_24_Closing_Handoff_v1.md` — this handoff.

---

## 10. Carry-forward updates

See `CARRY_FORWARD.md` for the full list. Net changes:

- **Bucket C sub-items (a)/(b)/(c)/(d)/(e)/(h)/(j) closed end-to-end** ✅ — 7 of 10 sub-items annotated ✅ on the CARRY_FORWARD entry with on-disk anchors (file paths + line numbers + test class names). Future ETL / vocab edits that would re-introduce these punch-list items now fail at `tests/test_bucket_c_terrain_vocab_audit.py` collection in CI.
- **Bucket C sub-items (f) / (g) / (i) carried with explicit Trigger pressures** — open forward-pointers ready for the next slice that touches them; each session's AskUserQuestion gate can pre-scope the appropriate trigger without re-deriving.
- **`tests/test_layer2b.py` import-order unblocked** — 18 previously-uncollected Layer 2B classifier behavior tests now contribute to CI signal; the container-runnable subset gains coverage on §13.1 PGE baseline / §13.2 Alpine unbridgeable / §13.3 empty locale / §10 multiple proxy / §10 unknown id / §8.2 coached intro / clean baseline / empty race-terrain loosen.
- **Manual §5.0 walkthrough** — no new step owed by this slice (audit closure is mechanically verified in CI). Pre-existing forward-pointers still owed: RouteLocalesAnchorFlags PGE step + ETL terrain-vocab-drift first-prod-run step + Bucket E.(a) + (b)-B1 step + Race-Locale-Mapbox 4-step.

**End of handoff.**
