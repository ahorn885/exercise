# FC-1a Closing Handoff — v1

**Date:** 2026-05-11
**Predecessor:** `D26_Done_D22_Pass1_Done_FC1a_Kickoff_Handoff.md`
**Working doc (now superseded):** `FC1a_Pass1_Bundle_v1.md`
**Status:** FC-1a closed. FC-1b kickoff in §7.

---

## §0. Scope summary

FC-1a was the **ETL bug fixes + drift cleanup batch** preceding FC-1b column promotions. 11 items in scope:

| ID | Description | Type |
|---|---|---|
| D-03 | `is_conditional` / `vertical_gain_notes` build-or-drop decision | Decision |
| D-04 | `phase_load_allocation` `phase_` prefix removal | SQL migration |
| D-05 | Aggregator-row filter into ETL | SQL cleanup + ETL code patch |
| D-06 | `phase_load_weekly_totals` `hours_low/high` rename | SQL migration |
| D-07 | 4 sports missing weekly_totals rows | Investigation + parser fix |
| D-08 | 3 missing rows in `sport_discipline_map` | Investigation |
| D-12 | `sport_name_aliases` schema doc | Spec patch |
| D-13 | `discipline_technique_foci` Batch B correction | Spec patch |
| D-14 | `cross_sport_properties.source_text` dedup | Investigation + SQL |
| D-15 | `discipline_substitutes` UNIQUE constraint review | Investigation + spec patch |
| D-16 | `primary_muscles` / `secondary_muscles` Batch B addition | Spec patch |

All 11 closed. Deliverables in §3; deferred items in §5–§7.

---

## §1. Resolution status

| ID | Status | Deliverable |
|---|---|---|
| D-03 | ✅ Decision locked — code change deferred to v20 ETL re-run | Backlog row updated; CC task |
| D-04 | ✅ Resolved | `migrate_phase_load_allocation_rename_phase_prefix_v1.sql` — ran 2026-05-11, no-op verify (deployed already correct); spec patch in Batch D |
| D-05 | 🟡 Partial — cleanup done; ETL code patch + standing rule retirement pending | `cleanup_phase_load_allocation_aggregators_v1.sql` — ran 2026-05-11 (no-op; 33 rows already superseded by prior unrecorded cleanup); ETL extractor patch spec in §5.1 below — **CC task** |
| D-06 | ✅ Resolved | `migrate_phase_load_weekly_totals_rename_hours_cols_v1.sql` — ran 2026-05-11, rename complete |
| D-07 | ✅ Resolved with decisions — CC parser fix pending | 4 sports confirmed missing via Step 1 query; xlsx inspection identified 3 distinct parser failure modes; decisions locked (7.1A / 7.2B / 7.3A); spec for fix in §5.2 below — **CC task** |
| D-08 | ✅ Resolved with explanation | Step 2 query confirmed 70 deployed rows; xlsx inspection showed dedup behavior is correct; Triathlon D-002 stale row identified for xlsx fix (see §6); sub-format collapse accepted; plan-gen scales via `phase_load_allocation` sub-format rows |
| D-12 | ✅ Resolved | Spec block in `Layer0_ETL_Spec_v3_Patch_Batch_D_v2.md` §2 |
| D-13 | ✅ Resolved | Correction in `Layer0_ETL_Spec_v3_Patch_Batch_B_Correction_v1.md` |
| D-14 | ✅ Resolved | Step 3 query confirmed `source_text == source_evidence` identical content on single deployed row; `migrate_cross_sport_properties_drop_source_text_v1.sql` ran 2026-05-11; spec patch in Batch D v2 §3 |
| D-15 | ✅ Resolved with explanation | Step 4 query found 2 conflict rows, both deliberately-authored sub-format variants with distinct Fidelity ratings; loose UNIQUE preserved (Option D); spec patch in Batch D v2 §4 |
| D-16 | ✅ Resolved | Type confirmed `TEXT[]`; transform documented in `Layer0_ETL_Spec_v3_Patch_Batch_B_Correction_v1.md` |

---

## §2. Decisions locked this session

| Decision ID | Choice | Rationale |
|---|---|---|
| D-03 | **BUILD** `is_conditional` + `vertical_gain_notes` in v4 spec | Simple derivation; structured form cheaper to consume than re-parsing notes everywhere. Footnote: "scheduled for v20 ETL re-run; not yet deployed." |
| D-07.1 | **Option A** — collapse multi-sub-format hours to single range (min low, max high across sub-formats) | Sub-format detail preserved in `notes_conditions` raw column for consumers that need it. Cheapest fix. |
| D-07.2 | **Option B** — convert km → hrs at parse time using marathon swim pace assumption (~20 min/km) | Simpler downstream; consumer math stays in hrs unit. Lossy vs Option A but acceptable given low row count. |
| D-07.3 | **Option A** — derive TAPER hours from PEAK midpoint × (1 − taper_pct_midpoint) | Concrete hours value more useful than a percentage. Unambiguous derivation. |
| D-08 | **Accept dedup** — UNIQUE collapses correct sub-format variants in `sport_discipline_map` | Sub-format detail correctly lives in `phase_load_allocation`; map layer works at top-level sport name. Plus xlsx fix for Triathlon D-002 stale row. |
| D-14 | **Drop `source_text` column** | Content identical to `source_evidence`. Pre-flight protected against losing the wrong column. |
| D-15 | **Option D** — leave deployed UNIQUE loose; substitute_name as variant key | Fidelity ratings per variant are deliberate coaching signal. Tightening would destroy real info. Spec catches up to code. |
| Versioning Rule | **Option H** (memory rule #12) — files save with numeric version suffix; Andy uploads with bumped name; cross-refs cite logical name | One-action revision flow; no rename dance; structurally prevents name collisions |

---

## §3. Files produced this session — Andy upload checklist

### Spec documents (project knowledge)

| File | Action | Notes |
|---|---|---|
| `Project_Backlog_v2.md` | **Upload** | Supersedes staged _v1.md; reflects all 11 FC-1a closures |
| `Control_Spec_v1.md` | **Upload** | Already current; no v2 needed (per rule #12 trigger criterion — no material restructure) |
| `Layer0_ETL_Spec_v3_Patch_Batch_D_v2.md` | **Upload** | Supersedes staged _v1.md; adds D-14 + D-15 patches alongside D-12 |
| `Layer0_ETL_Spec_v3_Patch_Batch_B_Correction_v1.md` | **Upload** | Stays at v1; covers D-13 + D-16 |
| `FC1a_Closing_Handoff_v1.md` | **Upload** | This doc — session bookkeeping |

### SQL migration files (repo `etl/sources/`)

| File | Status |
|---|---|
| `migrate_phase_load_allocation_rename_phase_prefix_v1.sql` | ✅ Run 2026-05-11 |
| `migrate_phase_load_weekly_totals_rename_hours_cols_v1.sql` | ✅ Run 2026-05-11 |
| `cleanup_phase_load_allocation_aggregators_v1.sql` | ✅ Run 2026-05-11 |
| `migrate_cross_sport_properties_drop_source_text_v1.sql` | ✅ Run 2026-05-11 |

All 4 SQL files should be committed to repo if not already (CC task).

### Files now superseded — do NOT upload

| File | Replaced by |
|---|---|
| `FC1a_Pass1_Bundle_v1.md` (staged) | This handoff — bundle was working-doc only |
| `Project_Backlog_v1.md` (staged) | `Project_Backlog_v2.md` |
| `Layer0_ETL_Spec_v3_Patch_Batch_D_v1.md` (staged) | `Layer0_ETL_Spec_v3_Patch_Batch_D_v2.md` |

---

## §4. Memory rules — current state

| # | Rule | Status |
|---|---|---|
| 9 | Session-start verification | Active |
| 10 | Session-end verification | Active |
| 11 | Handoff defer = mechanically-applicable edits | Active |
| 12 | File versioning convention (Option H — _v<N> suffix) | Active (confirmed 2026-05-11) |

No changes this session beyond #12 which was locked earlier.

---

## §5. Deferred to Claude Code

### §5.1 D-05 ETL extractor patch — aggregator filter

**Goal:** stop the ETL from emitting WEEKLY TOTAL TARGET aggregator rows into `phase_load_allocation`. The cleanup SQL handled deployed state; this patch prevents regression on next ETL run.

**Target file:** `etl/layer0/extract_phase_load_allocation.py` (or equivalent — CC locates in repo). Whichever module loads Sheet 5 ("Phase Load Allocation") and emits rows into `phase_load_allocation`.

**Patch logic:**

After parsing each Sheet 5 row, before emission, add:

```python
discipline_name = row.get('Discipline')  # or whatever the source column is named
if discipline_name and 'WEEKLY TOTAL TARGET' in discipline_name:
    continue  # routed to phase_load_weekly_totals (§4.5.1), not phase_load_allocation
```

**Unit test:** add a test fixture row containing `'WEEKLY TOTAL TARGET'` in its discipline_name; assert it is not emitted into the `phase_load_allocation` row stream.

**Standing rule retirement:** after CC patch lands and next ETL run confirms no regression, Andy retires Control_Spec §8.2 D-05 standing rule. Defensive query-layer filters can stay in place (harmless) or be removed per FC-2.

### §5.2 D-07 parser fix — three failure modes

**Goal:** patch the `phase_load_weekly_totals` Notes parser to handle the 4 missing sports.

**Target file:** the module that parses `Notes / Conditions` from Sheet 5 aggregator rows into `phase_load_weekly_totals`. CC locates in repo.

**Affected sports:**
- Off-Road / Adventure Multisport (Non-Nav) — Variant 1
- Open Water Marathon Swimming (10km / Olympic Distance) — Variant 2
- Open Water Marathon Swimming (25km / Ultra Distance) — Variant 2
- Swimrun — Variants 1 + 3

#### Variant 1 — multi-sub-format hours (Off-Road, Swimrun)

**Source format:**
```
WEEKLY TARGET HOURS:
BASE: XTERRA: 8–12 hrs
Quadrathlon: 9–13 hrs
Free-format: 8–14 hrs
BUILD: XTERRA: 10–15 hrs
Quadrathlon: 10–15 hrs
Free-format: 10–16 hrs
PEAK: ...
TAPER: 5–8 hrs
```

**Decision: 7.1 Option A — collapse to single range per phase.**

Parser logic per phase:
1. Detect phase label (`BASE`, `BUILD`, `PEAK`, `TAPER`).
2. Collect all sub-format range lines until next phase label or end of block.
3. Across all collected sub-format ranges for the phase:
   - `hours_low = MIN(all low values across sub-formats)`
   - `hours_high = MAX(all high values across sub-formats)`
4. Emit one row per phase with the collapsed low/high.

E.g., Off-Road BASE collapses (8, 9, 8) → low and (12, 13, 14) → high = `hours_low=8, hours_high=14`.

#### Variant 2 — km volume, pipe-delimited single-line (Open Water Marathon Swimming)

**Source format:**
```
WEEKLY TARGET VOLUME (km/wk): BASE: 30–45 km | BUILD: 40–55 km | PEAK: 45–60 km | TAPER: 20–30 km
```

**Decision: 7.2 Option B — convert km → hrs at parse time.**

**Conversion assumption:** marathon-distance open water swimming pace ≈ **20 min/km** (1 km / 20 min = 3 km/hr). This is in line with elite 10km marathon swim race times (~2 hrs) and amateur ultra-distance (25km) times (~6–8 hrs). Document this assumption in the parser code with a comment.

Parser logic:
1. Detect header containing `VOLUME (km/wk)` or unit `km`.
2. Split row by `|` delimiter to get one phase chunk per pipe section.
3. For each phase chunk:
   - Extract phase label (`BASE`, `BUILD`, `PEAK`, `TAPER`) and km low/high values.
   - Convert: `hours = km × (20 / 60)` → `hours = km / 3`.
   - Round to 1 decimal place.
4. Emit one row per phase with converted hours.

E.g., 10km BASE: `30–45 km` → `10.0–15.0 hrs`. PEAK: `45–60 km` → `15.0–20.0 hrs`.

Note: pace assumption is a parser-level constant. If a future sport uses a different pace (e.g., 50km ultra at 25 min/km), parser will need per-sport pace lookup — but that's not in current scope.

#### Variant 3 — percentage-cut TAPER (Swimrun)

**Source format (within Swimrun's TAPER block):**
```
TAPER: 40–50% volume cut
(2–3 wks)
```

**Decision: 7.3 Option A — derive TAPER hours from PEAK.**

Parser logic:
1. Detect TAPER value is a percentage-cut expression (matches pattern like `<low>–<high>% volume cut`).
2. Compute `taper_pct_low_remaining = 1 − (high/100)` and `taper_pct_high_remaining = 1 − (low/100)`. E.g., `40–50% cut` → remaining 50–60%.
3. Look up PEAK row that's just been parsed for this sport (same parser pass).
4. Derive: 
   - `peak_midpoint = (PEAK.hours_low + PEAK.hours_high) / 2`
   - `taper.hours_low = peak_midpoint × taper_pct_low_remaining`
   - `taper.hours_high = peak_midpoint × taper_pct_high_remaining`
5. Round to 1 decimal place.

E.g., Swimrun PEAK hours_low=12 / hours_high=16 (after Variant 1 collapse). Midpoint = 14. TAPER: 40–50% cut → remaining 50–60% → `low = 14 × 0.5 = 7.0`, `high = 14 × 0.6 = 8.4`. Emit TAPER row with `hours_low=7.0, hours_high=8.4`.

**Detection order:** the parser should try detectors in order: Variant 2 (km header) → Variant 3 (percentage-cut TAPER) → Variant 1 (multi-sub-format) → original simple format. First match wins for each phase.

**Unit tests required:**
- Off-Road BASE collapse: (XTERRA 8–12, Quadrathlon 9–13, Free-format 8–14) → low=8, high=14
- Swimrun TAPER derivation: PEAK 12–16 hrs, "40–50% volume cut" → TAPER 7.0–8.4 hrs
- Open Water 25km BASE: "35–50 km" → 11.7–16.7 hrs
- Adventure Racing BASE (control — must still parse correctly): "~18 hrs" → low=18, high=18

---

## §6. Manual source-xlsx tasks for Andy

Track outside this handoff; do whenever convenient.

### §6.1 Triathlon D-002 Road Running stale duplicate

**File:** `Sports_Framework_v10.xlsx` Sheet "Sport × Discipline Map"

**Source row to delete:** the brief Triathlon D-002 Road Running row (xlsx idx ~18, the one with `% of Race Time = '30–40%'` and brief context "Run begins immediately after bike dismount (T2)..."). Keep the detailed row (idx ~17) with the sub-distance breakdown and longer brick-context block.

This row will get picked up on next ETL run regardless of fix order — no urgency.

### §6.2 Long Distance / Endurance Cycling sub-format rows — NO CHANGE NEEDED

Per D-08 resolution: the 5 source rows (Road / Gravel / TT / XC / Enduro sub-formats) collapse correctly at load. Sub-format coaching detail correctly lives in `phase_load_allocation`'s sub-format-keyed rows (per D-17 standing rule). Leave xlsx as-is.

---

## §7. FC-1b kickoff scope

After this handoff uploads, FC-1b starts. **Scope:**

### §7.1 Blocker items for 2D implementation

**D-22 batch 2** — remaining `exercises.movement_components TEXT[]` classification.
- Pass 1 done 2026-05-11: 57/159 rows classified, house rules locked, edits applied per Andy review.
- **Remaining: 102 rows** at ~1.5–3 min/row pace → estimated 2.5–5 hours.
- House rules + Pass 1 baseline in `D22_Curation_Reference.md`.
- Spec'd in `Layer2D_Spec` §5.5 / §6.

**D-23** — `disciplines.body_parts_at_risk TEXT[]` companion column.
- ~150 cells curation against a smaller table than D-22.
- Seed drafted in `Layer2D_Spec` §5.5.
- Same pattern as D-22; faster pace expected because cleaner source data.

### §7.2 Migration SQL — FC-1b deliverable

After both curations complete:
- `migrate_exercises_add_movement_components_v1.sql` — adds column, populates from curation results, indexes.
- `migrate_disciplines_add_body_parts_at_risk_v1.sql` — same pattern.

### §7.3 FC-1b session-start checklist (rule #9)

When kicking off FC-1b:
1. Verify `Project_Backlog_v2.md` and other FC-1a uploads landed.
2. Re-read `D22_Curation_Reference.md` to refresh house rules and Pass 1 baseline.
3. Pull current `layer0.exercises` row IDs not in Pass 1 sample — those are the 102 remaining.
4. Sample batches of 15–20 rows for Andy review.

---

## §8. Open audit items

Track but not blocking FC-1b.

| Item | Where | Action |
|---|---|---|
| D-12 sport_name_aliases deployed UNIQUE constraint verification | Batch D v2 §2 | Run the constraint introspection query before v4 lock |
| D-05 next-ETL-run regression check | After CC patches D-05 | Confirm no new aggregator rows in `phase_load_allocation` |
| D-07 parser fix regression check | After CC patches D-07 | Confirm 132 active rows in `phase_load_weekly_totals` (vs current 116) |
| D-08 next-ETL-run cleanup confirmation | After Triathlon xlsx fix | Confirm sport_discipline_map row count = 69 for Triathlon (was 4, will be 4 still; the stale duplicate is dedup'd today anyway — no net change in active rows expected) |

---

## §9. Gut check

**What this session got right:**
- All 4 SQL migrations ran clean — no rollbacks, no surprises.
- Investigation queries surfaced architectural findings (D-15 fidelity, D-08 sub-format dedup) that would have been wrong if we'd applied "obvious" fixes. The pre-approved decision pattern with conditional rules (tighten if 0 conflicts; drop if identical) prevented bad migrations.
- Versioning rule landed clean — Option H is concretely better than B or G for this workflow.
- Project_Backlog and Control_Spec stayed honest about what's resolved vs partial.

**Risks:**
- D-05's mystery 33-rows-already-superseded state is unexplained. Probably a prior unrecorded cleanup, but if it was an unintended side-effect of some other operation, the same operation could fire again and mess up other tables. Low-probability but worth a quick "audit your recent operations on layer0" if you've got a moment.
- The 4 SQL files I produced were named with `_v1` suffix but written before the file-versioning rule was confirmed. They're still _v1, which is fine — but the convention going forward (per rule #12) is that the suffix means a revision count, not an arbitrary tag. First versions of new files should arguably not have a `_v1` suffix at all. Won't matter operationally; just an inconsistency to be aware of.
- D-07 parser fix is non-trivial — 3 failure modes, 4 sports, derivations. CC will need real test fixtures. Worth committing the test data alongside the parser changes.

**What might be missing:**
- I haven't audited whether the FC-1b D-22 batch 2 curation work will surface new D-37-class issues (non-movement flag content). Pass 1 surfaced cardiac / cognitive / surface-tissue / equipment-criticism categories. Batch 2 might surface more. Plan for that.
- Control_Spec §3 "Layer 1 → Layer 2" table doesn't mention the D-17 standing rule explicitly for downstream sub-format expansion. Probably fine; the rule is documented in §8.2 and referenced from per-layer specs. But worth a future read-through.

**Best argument against the session:**
- Several "Option D / leave deployed loose" resolutions stacked up (D-09 deferred, D-15 explicit Option D, plus the existing Batch B pattern). The "spec catches up to code" mode is now the dominant pattern. That's pragmatic but creates risk that spec drift becomes invisible because nobody is checking. Mitigation: FC-2 v4 rewrite is the explicit moment for closing that gap. Don't let FC-2 slip.

---

*End of FC-1a Closing Handoff.*
