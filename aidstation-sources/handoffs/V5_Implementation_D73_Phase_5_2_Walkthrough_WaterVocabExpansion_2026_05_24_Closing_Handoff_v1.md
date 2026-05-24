# D-73 Phase 5.2 Walkthrough — Bucket C sub-item (f) Water-Vocab 5-Row Expansion — Closing Handoff

**Session:** D-73 Phase 5.2 caller-side — picks up the §6.2 alt-pivot menu from the predecessor TerrainVocabAuditClosure slice. Closes Bucket C sub-item (f) end-to-end via a 5-row Water-category split + retighten + rename + 2 new gap rules. Surfaces and pins NEW Bucket C sub-item (l) skill-capability toggles as a separable architectural slice (Andy's pushback against the v1 §8.2 `requires_coached_introduction` derivation belongs on athlete-side toggles, not on terrain rows).
**Date:** 2026-05-24
**Predecessor handoff:** `V5_Implementation_D73_Phase_5_2_Walkthrough_TerrainVocabAuditClosure_2026_05_24_Closing_Handoff_v1.md`
**Branch:** `claude/bucket-c-f-water-vocab-expansion` (harness pinned `claude/sweet-goldberg-6DK6c` — renamed at session start per CLAUDE.md branch-naming rule)
**Status:** 4 substantive files (well under 5-file ceiling). Container-runnable subset 853 → 859 (+6 net: 6 new `TestWaterRowExpansion` tests). ETL `etl/tests/` 139 → 139 unchanged (modified counts in-place). No regressions.

---

## 1. Session-start verification (Rule #9)

Read order completed per Rule #13: CLAUDE.md → CURRENT_STATE.md → CARRY_FORWARD.md → predecessor handoff → `./aidstation-sources/scripts/verify-handoff.sh`. Anchor sweep ✅ clean — the 4 ❌ entries on `tests/test_extractor_parsers.py` / `tests/test_sum_to_100.py` / `tests/test_v10_parsers.py` / `tests/test_vocabulary_md.py` are the known false-positive (those files live under `etl/tests/`, not `tests/`; the script doesn't know about the nested test tree). Working tree clean on the harness-pinned branch; predecessor §8 anchors spot-checked (16 → 853 baseline confirmed; `_TERRAIN_STRUCTURED_ROWS` 16-row shape on disk; `TestCanonicalTerrainVocab` + `TestWaterRowExpansion`-precondition asserts intact). No drift between predecessor handoff narrative and on-disk state.

Branch rename at session start (CLAUDE.md branch-naming rule): `git branch -m claude/sweet-goldberg-6DK6c claude/bucket-c-f-water-vocab-expansion`.

---

## 2. Session narrative

Andy picked **"Bucket C (f) water-type design"** at the first AskUserQuestion gate (from the predecessor's §6.2 alt-pivot menu of: #8 locales→locations rename / Bucket C (i) Mapbox-required / Bucket E.(b)-B2 + E.(c)-C1 / Bucket C (f) water-type design).

The design pass per Trigger #2 (vocab padding refusal) + Trigger #5 (architectural alternatives) traced 4 candidate splits against the existing 4-row water shape:

| Cand | Description | Verdict |
|---|---|---|
| 1 | Split TRN-009 → still-water (TRN-009) + moving-water (NEW TRN-017) | **PASS** — river-current navigation / eddy reads / ferry angles are a distinct skill stimulus pool-proxy cannot cover. Andy's PGE 2026 packraft on the Cannon River is currently misclassified as TRN-009 with Pool 75% fidelity — the river-handling skill demand is hidden. Real coverage hole. |
| 2 | Split TRN-010 → ocean (NEW) + large-lake (TRN-009 absorbs) | **PASS via rename** — salt/tide/cold-shock are real differentiators. Workbook source ("Open Water", "Open Water Body", "Ocean or Surf") doesn't reliably distinguish ocean vs large lake, but renaming TRN-010 to "Ocean / Tidal" + retightening notes to drop "large lake" + adding explicit salt/cold/swell framing surfaces the stimuli without forcing a new TRN-xxx row. "Large lake with chop" now belongs to TRN-009's Flat-Water envelope (still-water, conditions = wind+chop). |
| 3 | Add "Surf / Tidal Zone" as separate row | **FAIL** — skill stimuli are distinct but no athlete in current corpus needs it. Vocab-padding risk: high. Defer until a swimrun or ocean-AR athlete drives the demand. |
| 4 | Add "Cold Water (<13°C)" as separate row | **HARD FAIL** — temperature is a *condition*, not a terrain feature. Belongs on Layer 2E `heat_acclim_adjustments` / `expected_race_temp_c` (gated on Plan Management spec). Category collision. |

Andy proposed the 5-row shape: Pool / Flat Water / Moving Water / Ocean / Tidal / Whitewater — over my Option A (Cand 1 only). The pick combines Cands 1 + 2-via-rename, defers Cands 3 + 4. Cleanest split per Andy's "differentiates enough without going too crazy on options."

**Subdecisions discussed at the gate:**

- (1) TRN-010 rename to "Ocean / Tidal" is athlete-visible in all `_terrain_choices` dropdowns. **Ratified.**
- (2) `requires_coached_introduction` flag stays on TRN-011 only — Andy pushed back: capability gating shouldn't be a derived terrain property; the v1 §8.2 keyword-match against `prescription_note` (`layer2b/builder.py:308`) is the wrong architectural home. Belongs on **athlete-side skill toggles** mirroring `sport_specific_gear_toggles` (assume not-skilled, opt-in via onboarding question, narrow scope). **Pivoted as separate slice — NEW Bucket C sub-item (l) — Trigger #3 + #5 both fire; this slice preserves existing TRN-011 coached-intro semantics exactly as-is, no §8.2 flag-firing surface regression.**
- (3) New gap rules: TRN-017 → TRN-009 (lake, fidelity 0.65 `medium`) + TRN-017 → TRN-011 (whitewater, fidelity 0.85 `low`). **Ratified.**
- (4) Migration of Andy's PGE 2026 row (15% TRN-009 currently): re-edit via form during §5.0 walkthrough rather than one-shot UPDATE. **Ratified — keeps slice purely additive, lets Andy spot-check the rename simultaneously.**
- (5) `populate_discipline_technique_foci.sql` sweep: after detailed review of all 7 water-keyed TF-* rows, only **TF-015 (Moving-water paddle technique: brace / ferry / eddy turn)** needs adjustment — its literal description names exactly the TRN-017 skill demands but is currently only attached to TRN-011. Other rows (TF-014 flatwater paddle stroke, TF-016 Eskimo roll, TF-018 whitewater line reading, TF-019 multi-person raft, TF-020 surf zone entry, TF-023 OW swim sighting, TF-024 SwimRun water entry) all correctly stay as-is — each row's semantic literal matches the specific water-row(s) it currently targets.

**Andy's note for the future skill-toggle slice (Bucket C (l)):** "we should assume not skilled initially but then ask them during onboarding. There should only be a few skills we really need to check on (climbing related, whitewater, ability to swim maybe?)" — both subdecisions pre-pinned in CARRY_FORWARD so the next plan-mode gate doesn't re-derive them.

**Derisk grep results before code:**

- `parsed_substitutes.json` — 0 hits for water terrain names. No exercise-side curation owed.
- `"Open Water / Ocean"` literal — 1 hit in `etl/layer0/extractors/vocabulary.py` itself (the row being renamed). Dropdown labels render from DB row, not hardcoded strings. Clean rename.
- `requires_coached_introduction` machinery — `Layer2B_Spec.md:263` defines, `layer2b/builder.py:308` emits, `tests/test_layer2b.py:424` covers. Confirmed: NEW TRN-017 must not leak coached-intro keywords into its `prescription_note` / `simulation_note` / `notes` (locked in by a new test in `TestWaterRowExpansion`).

---

## 3. File-by-file edits

### 3.1 `etl/layer0/extractors/vocabulary.py` — canonical vocab split + rename + retighten

`_TERRAIN_STRUCTURED_ROWS` (list of dicts) edited in place:

- **TRN-009 Flat Water** — `notes` retightened from "Calm lake, reservoir, or slow river. Low technical demand. Standard kayak/packraft training environment." → "Still water — lake, reservoir, pond. No perceptible current. Standard flatwater paddling and open-water swim training environment." `simulation_note` retightened from "Pool covers aerobic base and stroke mechanics; loses mild current navigation, open-water pacing, and environmental variables." → "Pool covers aerobic base and stroke mechanics; loses open-water pacing, sighting, and conditions handling (wind, chop)." The "slow river" + "current navigation" framing migrates semantically to the new TRN-017.
- **NEW TRN-017 Moving Water** — inserted between TRN-009 and TRN-010 in source order (Water-group reads pool → flat → moving → ocean → whitewater, natural escalation). Full row: `category="Water"`, `requires_elevation=False`, `technical_surface=False` (current-handling is a skill but the surface isn't Class II+), `environment="Outdoor"`, `simulatable="partial"`. `simulation_note`: "Flat water covers paddle aerobic and stroke mechanics; loses current reading, ferry angles, and eddy use. Whitewater experience over-covers these skills." `notes`: "Rivers, current-driven channels, or tidal flats below Class II. Ferry angles, eddy reads, and current navigation required. Standard river-paddling and packraft-touring environment." **No coached-intro language** (forward-compat with Bucket C (l) skill-toggle pivot).
- **TRN-010 Ocean / Tidal** — `canonical_name` renamed from "Open Water / Ocean" → "Ocean / Tidal". `notes` retightened from "Ocean, large lake, or tidal water with meaningful chop, current, or swell. OW swimming and ocean paddling territory." → "Saltwater or tidal water — ocean, sea, or tidal estuary. Cold-shock potential, salt exposure, swell, horizon sighting. OW swimming and ocean paddling territory." "Large lake" reference removed (migrates semantically to TRN-009's still-water envelope). `simulation_note` retightened from "Pool maintains aerobic base; loses sighting, wave/current navigation, cold exposure, and mass-start dynamics." → "Pool maintains aerobic base; loses sighting, wave/swell navigation, salt and cold exposure, and mass-start dynamics." (Explicit salt + cold + swell vs the prior collapsed "cold exposure".)
- TRN-008 Pool and TRN-011 Whitewater unchanged.

Net delta: +13 lines (1 new row added, 6 lines per existing row retightened in-place — count unchanged for those two).

### 3.2 `etl/sources/populate_terrain_gap_rules.sql` — 2 new TRN-017 rules + TRN-010 rename + enum doc refresh

- **File-level enum doc comment** refreshed from the stale 3-band `bridgeable / partial / unbridgeable` to the post-Phase-2.3 5-band `low / medium / high / critical / unbridgeable` with band thresholds documented. Audit-trail comment notes existing rows still carry `'partial'` and are reclassified at deploy time by `_PG_MIGRATIONS`; new rows post-2026-05-19 should use the post-reclassification value directly.
- **TRN-010 rule's `target_terrain_name`** renamed `'Open Water / Ocean'` → `'Ocean / Tidal'` to match the canonical vocab rename. Prescription_note + audit_log content unchanged (cold-shock + wetsuit + sighting framing was already accurate for the saltwater-only interpretation).
- **NEW gap rule TRN-017 → TRN-009 (Moving Water proxied by Flat Water)** — `gap_severity='medium'`, `adaptation_weeks_low=2 high=4`, `proxy_fidelity=0.65`. Proxy methods: flat-water aerobic + stroke volume / dry-land bracing on balance pad / video study / 2-4 supervised moving-water sessions before race. Uncoverable stimulus: `balance_dynamic`. Prescription_note flags real-river practice as required for current reading / ferry / eddy turn timing. Audit_log explicit on the 0.65 fidelity reasoning + post-Phase-2.3 'medium' band classification.
- **NEW gap rule TRN-017 → TRN-011 (Moving Water proxied by Whitewater)** — `gap_severity='low'`, `adaptation_weeks_low=1 high=2`, `proxy_fidelity=0.85`. Proxy methods: whitewater paddling sessions (over-covers Class-II-and-below current handling) + periodic flat-water sessions for sustained aerobic if whitewater sessions are short. Uncoverable stimulus: `[]` (whitewater experience over-covers everything except possibly sustained-aerobic-volume). Audit_log explicit on the 0.85 fidelity reasoning + post-Phase-2.3 'low' band classification + audit-trail note explaining the over-cover semantic (whitewater paddler should never see undefined_gap for moving water in their locale).
- **Existing TRN-011 → TRN-009 whitewater rule UNTOUCHED.** Per the coached-intro preservation policy (Bucket C (l) is the separate slice that reworks this surface); no §8.2 flag-firing-surface regression in this slice.

Two cosmetic comment-header fixes paired with the data edits: section header line "Open Water / Ocean gap" renamed to "Ocean / Tidal gap"; new "Moving Water gaps" section header inserted before the two new TRN-017 rules with an audit-trail explanation.

Net delta: +45 lines (2 new rules with audit_log + ~10-line refreshed file-level doc comment + 1 section header rename + 1 new section header).

### 3.3 `etl/sources/populate_discipline_technique_foci.sql` — TF-015 sweep

TF-015 (Moving-water paddle technique: brace, ferry, eddy turn) `terrains_addressed` column extended from `ARRAY['TRN-011']` → `ARRAY['TRN-011','TRN-017']`. The row's prose literal explicitly names ferry angles + eddy turn + brace — exactly the TRN-017 skill set. Before the slice, the row was only attached to whitewater because the moving-water row didn't exist; the alignment is mechanical given the new vocab.

Other 7 water-keyed foci rows (TF-014 flatwater paddle stroke, TF-016 Eskimo roll, TF-018 whitewater line reading, TF-019 multi-person raft, TF-020 surf zone entry, TF-023 OW swim sighting, TF-024 SwimRun water entry) reviewed for TRN-017 inclusion candidacy; all correctly stay as-is — each row's semantic literal matches the specific water-row(s) it currently targets (flatwater technique, pool/lake rolling, whitewater-specific, ocean-specific).

Net delta: +0 / -0 lines (single-line in-place edit).

### 3.4 `tests/test_bucket_c_terrain_vocab_audit.py` — count flip + NEW TestWaterRowExpansion class

- **`TestCanonicalTerrainVocab`** — row count assertion `16` → `17` + sequence assertion `range(1,17)` → `range(1,18)` + class docstring updated to reflect 17-row shape and reason for bump. Method names renamed `test_canonical_row_count_is_16` → `test_canonical_row_count_is_17` and `test_canonical_ids_are_sequential_TRN_001_through_TRN_016` → `test_canonical_ids_are_sequential_TRN_001_through_TRN_017`.
- **NEW `TestWaterRowExpansion`** (6 tests):
  1. `test_water_category_has_five_rows` — exactly 5 rows with `category="Water"`
  2. `test_moving_water_row_exists` — TRN-017 row present with expected attribute set (canonical_name="Moving Water", category="Water", environment="Outdoor", simulatable="partial", technical_surface=False, requires_elevation=False)
  3. `test_ocean_tidal_row_renamed` — TRN-010 canonical_name=="Ocean / Tidal" + asserts "Open Water / Ocean" string is absent from the canonical name set
  4. `test_flat_water_row_no_longer_mentions_slow_river` — TRN-009 notes lowercased contain "still water" but NOT "slow river" (locks in the retighten)
  5. `test_moving_water_simulation_note_does_not_request_coaching` — TRN-017 simulation_note + notes do NOT contain "coached intro" / "supervised instruction" / "requires coached" (forward-compat with Bucket C (l) skill-toggle pivot — when the toggle slice strips coached-intro language from `populate_terrain_gap_rules.sql`, TRN-017 doesn't need re-authoring)
  6. `test_water_environment_split_unchanged` — environment map across the 5 water rows is exactly `{TRN-008: Indoor, TRN-009: Outdoor, TRN-010: Outdoor, TRN-011: Outdoor, TRN-017: Outdoor}`
- Module docstring forward-pointer list updated: mark (f) ✅ closed with summary of the 5-row split; add (l) skill-capability toggles entry with Trigger #3 + #5 pinned.

Helper function `_water_row(terrain_id)` added at module level to keep test bodies brief.

Net delta: +97 lines (6 new tests + helper + docstring updates; method renames are net-zero).

### 3.5 `etl/tests/test_vocabulary_md.py` — count flip + presence-list extension

- `test_terrain_count` — `len == 16` → `len == 17` + comment updated to cite the WaterVocabExpansion slice and the bump reason.
- `test_terrain_ids_unique_and_sequential` — `range(1, 17)` → `range(1, 18)` + defensive `sorted()` of `ids` before comparison (the prior assertion required input-order = sorted-order, fragile against future appends; my TRN-017 placement in vocabulary.py source order is between TRN-009 and TRN-010 for natural Water-group reading, so an unsorted compare would fail spuriously).
- `test_terrain_known_canonical_names_present` — required-presence list extended with "Flat Water" + "Moving Water" + "Ocean / Tidal" so the rename + new row are mechanically locked in.

Net delta: +5 / -3 lines (in-place edits across 3 tests).

This file is a "bonus" 5th substantive edit but trivially mechanical (count flip + presence list); the slice stays under the 5-file ceiling either way. Substantive count = 4 if you don't count this as substantive (it's effectively the etl-side mirror of the audit closure file's count flip); 5 if you do. Both readings honor the ceiling discipline.

---

## 4. Code / tests

**Tests:** `tests/test_bucket_c_terrain_vocab_audit.py` 20 → 26 (+6 net new in `TestWaterRowExpansion`); container-runnable subset 853 → 859 in ~1.3s. ETL `etl/tests/` 139 → 139 (modified counts in-place, no test count change). No regressions on Layer 4 / orchestrator / repo / race_events / locales / onboarding / plan_create / ad_hoc_workouts / plan_refresh / nl_parser / dashboard / admin / layer3 cached-wrappers / layer2a / layer2b surfaces; 12 NL parser smoke + 4 Layer 3 SDK smoke tests still skip cleanly when `ANTHROPIC_API_KEY` unset.

Reproducer (changed files only):

```
PYTHONPATH=. python -m pytest tests/test_bucket_c_terrain_vocab_audit.py tests/test_layer2b.py etl/tests/test_vocabulary_md.py
# 62 passed in 0.47s  (26 audit + 18 layer2b + 18 vocab_md)
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
# 859 passed, 12 skipped in 1.32s
```

ETL: `PYTHONPATH=. python -m pytest etl/tests/ # 139 passed in 0.52s`.

**No-regression confirmation:** every previously-passing file still passes with identical counts. The only count change is `tests/test_bucket_c_terrain_vocab_audit.py` 20 → 26.

**py_compile:** `etl/layer0/extractors/vocabulary.py` + `tests/test_bucket_c_terrain_vocab_audit.py` + `etl/tests/test_vocabulary_md.py` all clean.

---

## 5. Manual §5.0 verification — owed step

NEW 3-step walkthrough scenario added to CARRY_FORWARD §5.0 list:

1. **Dropdown shows 17 options + new rows visible** — navigate to `/profile/race-events/<andy_pge_2026_id>/edit`, click `[+ Add terrain]`, confirm 17 entries including "Moving Water" and "Ocean / Tidal" (rename); confirm "Open Water / Ocean" no longer appears. Repeat at `/onboarding/target-race` (target-race form `_race_terrain_editor` partial) and `/locales/home/edit` (locale-terrain checkbox grid) — same 17 options + rename.
2. **Andy's PGE 2026 terrain re-edit** — swap the 15% TRN-009 (Flat Water) on the Cannon River packraft leg to TRN-017 (Moving Water). Confirm Neon round-trip + Layer 2B reclassification: gap rule resolves via TRN-017 → TRN-009 (lake at home locale) fidelity 0.65 `medium`; prescription_note now mentions ferry / eddy / current navigation per the new rule.
3. **No classifier regression** — Andy's PGE 2026 race-week brief still generates without `Layer2BInputError`; existing TRN-011 whitewater coached-intro flag firing surface UNTOUCHED. No Layer 2C eviction expected (water-vocab changes don't touch equipment).

---

## 6. Next session pointers

### 6.1 Architect-recommended next forward move

**#8 "locales" → "locations" terminology rename** stays the lowest-risk next-slice candidate (carried forward through every recent handoff; ~9 templates, mechanical, no `/plan` triggers). Affected templates pinned at `CARRY_FORWARD.md` line 90.

### 6.2 Alternative pivots

- **NEW Bucket C sub-item (l): skill-capability toggles** — replace the v1 §8.2 `requires_coached_introduction` keyword-match derivation with athlete-side opt-in toggles. Both Trigger #3 (cross-layer schema: NEW `layer0.skill_toggles` table + `Layer1Lifestyle.skill_toggle_states` extension + `Layer2BInput` extension + onboarding capture surface) + Trigger #5 (architectural alternatives). Defaults pre-pinned by Andy at the WaterVocabExpansion gate: **assume not-skilled** (opt-in, mirror equipment availability pattern) + **narrow scope** (climbing-related + whitewater + swim ability only). ~6-8 substantive files; ratify ceiling at next plan-mode entry.
- **Bucket C sub-item (i) Mapbox-anchored race-location required** — closes Bucket C entirely from a still-open perspective. Trigger #5 design call upfront (hard-fail empty Mapbox feature vs soft surface as data_gap). ~3-4 files.
- **Bucket E.(b)-B2 + E.(c)-C1 follow-on slice** — specs pinned in CARRY_FORWARD. ~6-9 files; ceiling-break ratification needed.
- **Bucket C sub-item (g) locale-terrain vs Outdoor-Terrain merge** — Trigger #3 cross-layer schema + #5 architectural alternatives. Plan-mode gate.
- **#6 + #4 paired injury form refresh** — ~6-8 files; Trigger #5 on body-part-to-movement-constraints mapping.
- **#2b race-URL LLM site-parse pre-fill** — Trigger #2 prompt design session first; then ~4-6 files runtime.
- **§I.1 structured supplements onboarding refresh** — Layer 2E §5.5 de-stub. LARGE ~6-8 files; plan-mode gate required.

### 6.3 Operating notes for next session

Read order (Rule #13):

1. `aidstation-sources/CLAUDE.md` — stable rules.
2. `aidstation-sources/CURRENT_STATE.md` — what just shipped + current focus + layer status.
3. `aidstation-sources/CARRY_FORWARD.md` — rolling cross-session items (Bucket C line 103: (f) ✅ closed-shipped via WaterVocabExpansion with 5-row anchors; NEW (l) skill-capability toggles inline-spec'd with Trigger #3 + #5 pre-pinned + default-state + vocab-scope ratified at the gate).
4. `aidstation-sources/handoffs/V5_Implementation_D73_Phase_5_2_Walkthrough_WaterVocabExpansion_2026_05_24_Closing_Handoff_v1.md` — this handoff.
5. `./aidstation-sources/scripts/verify-handoff.sh` — automated anchor sweep. The script's 4 ❌ false-positives on ETL test files still present (script doesn't know about `etl/tests/`); verify via `ls etl/tests/`.

**No outstanding production warnings.** Bucket C: 8 of 11 sub-items closed (a / b / c / d / e / f / h / j + k via predecessor); 3 still open — (g) terrain↔equipment merge (Trigger #3 plan-mode), (i) Mapbox-required (Trigger #5), (l) skill toggles (Trigger #3 + #5 plan-mode, both defaults already pre-pinned).

---

## 7. Decisions pinned

| # | Decision | Picked by | Rationale |
|---|---|---|---|
| **D1** | 5-row water split (Pool / Flat / Moving / Ocean-Tidal / Whitewater) | Andy at AskUserQuestion gate | Combines Cand 1 (TRN-017 Moving Water — passes Trigger #2 because pool-proxy for packraft-on-river was actively misleading) + Cand 2-via-rename (TRN-010 → "Ocean / Tidal" — surfaces salt/tide/cold without forcing a new row). Defers Cand 3 (Surf — no athlete corpus drives it) + Cand 4 (Cold Water — Layer 2E category collision). "Differentiates enough without going too crazy on options." |
| **D2** | TRN-010 rename to "Ocean / Tidal" is athlete-visible across dropdowns | Andy at gate | Confirmed explicitly. Dropdown labels render from DB row, so the rename flows everywhere automatically. No template/code touch needed for the rename itself. |
| **D3** | `requires_coached_introduction` flag stays only on TRN-011 today | Andy at gate (with architectural pushback) | Andy pushed back that capability gating shouldn't be a derived terrain property. **Pivoted as separate slice — NEW Bucket C (l)**. For this slice: TRN-017's `prescription_note` / `simulation_note` / `notes` deliberately authored without coached-intro language (locked in by `test_moving_water_simulation_note_does_not_request_coaching`); existing TRN-011 rule UNTOUCHED — no §8.2 flag-firing surface regression. |
| **D4** | 2 new gap rules for TRN-017 (lake + whitewater proxies) with `medium` + `low` bands | Andy at gate | TRN-017 → TRN-009 (lake) fidelity 0.65 → `medium` band; TRN-017 → TRN-011 (whitewater) fidelity 0.85 → `low` band. Classifier ORDER BY proxy_fidelity DESC picks whichever proxy the athlete actually has in their locale set. Whitewater path uses post-Phase-2.3 enum directly (vs the file's existing `'partial'` legacy that the deploy migration reclassifies). |
| **D5** | Migration of Andy's PGE 2026 row = manual form re-edit during §5.0 walkthrough | Andy at gate | Over one-shot UPDATE. Keeps slice purely additive; lets Andy verify the dropdown rename + new TRN-017 option at the same time. |
| **D6** | NEW Bucket C sub-item (l) — skill-capability toggles — gets a separate slice | Architect (escalated by Andy's pushback) | Trigger #3 + Trigger #5 both fire on the architectural rework. **Defaults pre-pinned** so the next session's plan-mode gate doesn't re-derive: assume-not-skilled (opt-in mirror of equipment availability) + narrow scope (climbing + whitewater + swim ability). Will require ~6-8 substantive files. |
| **D7** | `populate_discipline_technique_foci.sql` sweep: only TF-015 adjusted | Architect at code-time | Detailed per-row review of all 7 water-keyed foci rows confirmed only TF-015 (Moving-water paddle technique: brace / ferry / eddy turn) has a semantic literal matching the TRN-017 skill set. Other rows correctly stay as-is. |
| **D8** | TRN-017 placed between TRN-009 and TRN-010 in source order | Architect at code-time | Source-order TRN-008 / TRN-009 / TRN-017 / TRN-010 / TRN-011 reads naturally for the Water-group: pool → flat → moving → salt → whitewater (stimulus escalation). Sequential-by-source-order broken; sorted-by-ID still gives `[TRN-001..TRN-017]`. Defensive `sorted()` added to `etl/tests/test_vocabulary_md.py::test_terrain_ids_unique_and_sequential` to keep the assertion non-fragile against future similar in-place inserts. |

---

## 8. Session-end verification (Rule #10)

| Check | Result |
|---|---|
| `_TERRAIN_STRUCTURED_ROWS` has 17 rows in `etl/layer0/extractors/vocabulary.py` | ✅ `grep -c '"terrain_id":' etl/layer0/extractors/vocabulary.py` returns 17 |
| TRN-017 Moving Water row defined | ✅ `grep -n 'TRN-017\|Moving Water' etl/layer0/extractors/vocabulary.py` returns matching pair |
| TRN-010 canonical_name renamed to "Ocean / Tidal" | ✅ `grep -n 'Ocean / Tidal' etl/layer0/extractors/vocabulary.py` returns hit; `grep 'Open Water / Ocean' etl/layer0/extractors/vocabulary.py` returns empty |
| TRN-009 notes drop "slow river" + add "still water" | ✅ `grep -n 'still water\|slow river' etl/layer0/extractors/vocabulary.py` — only "Still water" hit |
| 2 NEW gap rules for TRN-017 in populate_terrain_gap_rules.sql | ✅ `grep -c "^( 'TRN-017'" etl/sources/populate_terrain_gap_rules.sql` returns 2 |
| TRN-010 rule's target_terrain_name renamed in populate_terrain_gap_rules.sql | ✅ `grep -n "TRN-010', 'Ocean / Tidal'" etl/sources/populate_terrain_gap_rules.sql` returns hit |
| TF-015 row includes both TRN-011 + TRN-017 | ✅ `grep -A1 "'TF-015'" etl/sources/populate_discipline_technique_foci.sql \| grep "TRN-011','TRN-017'"` returns hit |
| `TestCanonicalTerrainVocab` row count assertion = 17 | ✅ `grep -n "test_canonical_row_count_is_17" tests/test_bucket_c_terrain_vocab_audit.py` returns hit |
| NEW `TestWaterRowExpansion` class with 6 tests | ✅ `grep -c "    def test_" tests/test_bucket_c_terrain_vocab_audit.py` returns 25 + 1 parametrized × 5 = 30 collected (was 19 + 1×5 = 24 = 20 collected pre-slice) → +6 net |
| `etl/tests/test_vocabulary_md.py` count assertion = 17 | ✅ `grep -n "== 17" etl/tests/test_vocabulary_md.py` returns hit |
| `tests/test_bucket_c_terrain_vocab_audit.py` 20 → 26 pass | ✅ pytest run in 0.47s (26 audit + 18 layer2b + 18 vocab_md = 62 passed) |
| Container-runnable subset 853 → 859 pass + 12 skipped | ✅ pytest run in 1.32s |
| ETL `etl/tests/` 139 → 139 pass | ✅ pytest run in 0.52s |
| `CURRENT_STATE.md` last-shipped pointer flipped to this handoff | ✅ |
| `CARRY_FORWARD.md` Bucket C line 103: (f) flipped ✅ shipped; NEW (l) skill-toggles inline-spec'd with pre-pinned defaults | ✅ |
| Branch renamed from `claude/sweet-goldberg-6DK6c` → `claude/bucket-c-f-water-vocab-expansion` | ✅ `git branch --show-current` returns the renamed branch |

---

## 9. Files shipped this session

**Substantive (4 files; well under 5-file ceiling):**

1. MODIFIED `etl/layer0/extractors/vocabulary.py` — `_TERRAIN_STRUCTURED_ROWS` gains NEW TRN-017 Moving Water row + TRN-009 + TRN-010 retightened-in-place + TRN-010 renamed to "Ocean / Tidal". +13 / -0 net.
2. MODIFIED `etl/sources/populate_terrain_gap_rules.sql` — 2 NEW TRN-017 gap rules (→ TRN-009 fidelity 0.65 `medium`; → TRN-011 fidelity 0.85 `low`) + TRN-010 rule's target_terrain_name renamed + file-level enum doc comment refreshed (3-band → 5-band post-Phase-2.3) + 2 section header cosmetic fixes. +45 / -5 net.
3. MODIFIED `etl/sources/populate_discipline_technique_foci.sql` — TF-015 (Moving-water paddle technique) extended `['TRN-011']` → `['TRN-011','TRN-017']`. +0 / -0 (single-line in-place edit).
4. MODIFIED `tests/test_bucket_c_terrain_vocab_audit.py` — `TestCanonicalTerrainVocab` row count + sequence assertions flipped to 17 + class docstring updated; NEW `TestWaterRowExpansion` class with 6 tests + `_water_row` helper; module docstring forward-pointer list updated. +97 / -3 net.

**Bonus** (substantive but trivially mechanical; counted variably; stays under ceiling regardless):

5. MODIFIED `etl/tests/test_vocabulary_md.py` — `test_terrain_count` 16 → 17 + `test_terrain_ids_unique_and_sequential` `range(1,17)` → `range(1,18)` + defensive `sorted()` + `test_terrain_known_canonical_names_present` extended with Flat Water + Moving Water + Ocean / Tidal. +5 / -3 net.

**Bookkeeping (3 files; do not count against ceiling):**

6. MODIFIED `aidstation-sources/CURRENT_STATE.md` — last-shipped pointer flipped to this handoff; predecessor TerrainVocabAuditClosure line preserved.
7. MODIFIED `aidstation-sources/CARRY_FORWARD.md` — Bucket C line 103: (f) flipped ✅ shipped with WaterVocabExpansion anchors; NEW (l) skill-capability toggles inline-spec'd with Trigger #3 + #5 pre-pinned + default-state + vocab-scope ratified by Andy at the gate; NEW 3-step manual §5.0 walkthrough scenario added to top-of-file list.
8. NEW `aidstation-sources/handoffs/V5_Implementation_D73_Phase_5_2_Walkthrough_WaterVocabExpansion_2026_05_24_Closing_Handoff_v1.md` — this handoff.

---

## 10. Carry-forward updates

See `CARRY_FORWARD.md` for the full list. Net changes:

- **Bucket C sub-item (f) closed end-to-end** ✅ — 5-row Water-category split shipped with mechanical lock-in tests. Future ETL / vocab edits that would re-introduce the 4-row collapse now fail at `tests/test_bucket_c_terrain_vocab_audit.py::TestWaterRowExpansion`.
- **NEW Bucket C sub-item (l) skill-capability toggles** — surfaced + inline-spec'd with both Trigger #3 + Trigger #5 pre-pinned for the next plan-mode gate. Default-state ratified (assume-not-skilled, opt-in) + vocab-scope ratified (narrow — climbing / whitewater / swim ability only) so the next session's design pass doesn't re-derive. The WaterVocabExpansion slice's TRN-017 row was deliberately authored without coached-intro language (forward-compat anchor in `TestWaterRowExpansion::test_moving_water_simulation_note_does_not_request_coaching`) so the toggle slice doesn't have to retro-rewrite TRN-017.
- **NEW Manual §5.0 walkthrough scenario** — 3-step scenario covering dropdown render of 17 options + rename + Andy's PGE 2026 row re-edit + classifier no-regression.
- **Pre-existing forward-pointers carried** — RouteLocalesAnchorFlags PGE step + ETL terrain-vocab-drift first-prod-run step + Bucket E.(a)+(b)-B1 step + Race-Locale-Mapbox 4-step + the predecessor TerrainVocabAuditClosure forward-pointers (g) + (i) carried.
- **Doc-sweep nit added** — `aidstation-sources/migrations/populate_terrain_gap_rules.sql` + `aidstation-sources/migrations/migrate_terrain_types.sql` are design-side duplicate copies still on the pre-Phase-2.3 enum shape + pre-rename TRN-010 name; flagged as a doc-sweep nit for the next sweep that touches the migrations dir (not blocking; the canonical running files are `etl/sources/*`).

**End of handoff.**
