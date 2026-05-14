# Project Backlog

**Renamed from:** `Layer0_Drift_Backlog.md` (was scoped to Layer 0 drift; now broader)
**Started:** 2026-05-10
**File revision:** v2 — 2026-05-11 (post-FC-1a closure)
**Purpose:** Single rolling tracker for cross-layer deferred work — drift findings, design decisions parked for later, cleanup tasks, items surfaced in one layer's work that need fixing in another. Updated at every layer/node boundary. Final-cleanup batches read this doc at the end of each layer phase.
**Categories:** Blocker / Deferred / Cleanup. Items can promote to Blocker but never silently demote.
**Source of initial findings:** `Layer0_Deployed_Schema_and_Drift_Report.md` v2 + per-session surface area as Layer 2 design progressed.

---

## Categorization rule

**Blocker** — must fix before continuing. Triggers:
- Current or imminent node would consume wrong/incomplete data because of it
- Causes silent wrong results downstream
- Blocks data the next node must produce

**Deferred** — documentation only OR doesn't affect current/imminent nodes OR has a query-layer workaround. Goes to final cleanup.

**Cleanup** — known spec/doc drift that has no functional impact. Pure documentation work. Lowest priority within the final cleanup batch.

---

## Status legend

- 🔴 Blocker — fix immediately
- 🟡 Deferred — verify on each node-boundary; promote if scope intersects new node
- 🟢 Cleanup — pure doc/cosmetic, final-batch only
- ✅ Resolved
- ⚪ Wont-Fix (intentional, with reason)

---

## Open items

| # | Finding | Severity | Status | Affects nodes | Notes / workaround |
|---|---|---|---|---|---|
| D-01 | `exercises` §4.12 spec block fully stale — 7 missing cols, wrong names on 4, contradictory UNIQUE | High | 🟡 Deferred | None directly; Batch B/C patches already document deployed shape | Batch B + Batch C patches are the authoritative reference. Final cleanup folds them into v4. |
| D-02 | `disciplines` §4.3 — 4 cols missing from spec, 3 renames, 2 spec-only numerics not built | High | 🟡 Deferred | 2A consumer (discipline classification), 2D (injury risk) | Deployed columns are correct and consumable as-is. Spec rewrite is documentation. |
| D-03 | `phase_load_allocation` — `is_conditional BOOLEAN` and `vertical_gain_notes TEXT` defined in spec, NOT in deployed | High (spec-ahead) | 🟡 Decision locked, code change deferred (FC-1a, 2026-05-11) | 2A (discipline classification), 2D (injury risk), 4 (plan-gen) | **Decision: BUILD** (retain both in v4 §4.5; Andy confirmed 2026-05-11). Implementation lands in ETL extractor before v20 re-run — parser additions per spec §4.5 derivation rules (`is_conditional` from Role/Notes markers; `vertical_gain_notes` from sport-conditional Notes parse). v4 spec footnote required: "scheduled for v20 ETL re-run; not yet deployed — do not query as available until v20 ships." Code-side TODO for CC. |
| D-04 | `phase_load_allocation` — column-name `phase_` prefix in spec, no prefix in deployed | Med | ✅ Resolved (FC-1a, 2026-05-11) | All | Idempotent rename migration confirmed deployed state matches target (8 unprefixed band columns). Spec patch in `Layer0_ETL_Spec_v3_Patch_Batch_D` §4.x. SQL: `migrate_phase_load_allocation_rename_phase_prefix_v1.sql` (no-op verify; columns already correct). |
| D-05 | **`phase_load_allocation` ETL not filtering aggregator rows.** 33 WEEKLY TOTAL TARGET rows present alongside 162 discipline rows. **Verified 2026-05-10:** all 33 sports affected, including AR. | High | 🟡 **Partial — cleanup done, ETL code patch + standing rule retirement pending** | 2A, 2D, 2E, 4 | **2026-05-11 (FC-1a):** Cleanup SQL ran (`cleanup_phase_load_allocation_aggregators_v1.sql`) — all 33 aggregator rows were already in `superseded_at IS NOT NULL` state at pre-flight (prior unrecorded cleanup); current `phase_load_allocation` active row count clean. **STILL PENDING:** (a) ETL extractor code patch per `FC1a_Closing_Handoff_v1.md` §5 — apply via CC; (b) Control_Spec §8.2 standing rule retirement after next clean ETL run confirms no regression. Defensive filter MUST remain in query-layer nodes until both (a) and (b) land. |
| D-06 | `phase_load_weekly_totals` — `hours_low/high` renamed to `weekly_low_hours/high_hours` | Low | ✅ Resolved (FC-1a, 2026-05-11) | 2E (nutrition uses hours), 4 (plan-gen) | Deployed columns renamed to match spec §4.5.1 (`hours_low`, `hours_high`). SQL: `migrate_phase_load_weekly_totals_rename_hours_cols_v1.sql`. |
| D-07 | `phase_load_weekly_totals` — 16 rows short. **Verified 2026-05-10:** 4 missing sports are Off-Road / Adventure Multisport (Non-Nav), Open Water Marathon Swimming (10km / Olympic Distance), Open Water Marathon Swimming (25km / Ultra Distance), Swimrun. AR has all 4 phase rows ✓ | Med | ✅ Resolved with decisions (FC-1a, 2026-05-11) — **CC implementation pending** | 2E, 4 | xlsx inspection revealed **three distinct parser failure modes**: (1) multi-sub-format hours per phase (Off-Road, Swimrun); (2) km-based volume not hrs (Open Water 10km, 25km); (3) percentage-cut TAPER (Swimrun). **Decisions locked (Andy 2026-05-11):** 7.1 = Option A (collapse multi-sub-format to min low / max high range); 7.2 = Option B (convert km→hrs at parse time at ~20 min/km marathon swim pace); 7.3 = Option A (derive TAPER hours = PEAK midpoint × (1 − taper_pct_midpoint)). Full parser fix spec in `FC1a_Closing_Handoff_v1.md` §5.2. CC task — not FC-1a or FC-1b. |
| D-08 | `sport_discipline_map` — 3 rows missing in deployed (73 source vs 70 deployed). **Verified 2026-05-10:** 3 missing rows are Long Distance / Endurance Cycling (-2: 5 in xlsx, 3 deployed) and Triathlon (-1: 5 in xlsx, 4 deployed). AR has all 15 disciplines ✓ | Med | ✅ Resolved with explanation (FC-1a, 2026-05-11) | 2A | **Not a parser bug.** Source xlsx has rows that share `(sport, discipline_id)` within a sport — UNIQUE constraint correctly dedups at load. Long Distance / Endurance Cycling: D-005 appears 3× (Road / Gravel / TT sub-formats), D-006 appears 2× (XC / Enduro) — legitimate sub-format expansion; collapse accepted (Andy 2026-05-11). Triathlon: D-002 Road Running appears 2× — one detailed row (sub-distance breakdown) + one brief stale row — **xlsx source fix required:** delete brief row at xlsx idx=18 in "Sport × Discipline Map" sheet; keep idx=17. Sub-format-specific plan-gen scales via `phase_load_allocation` sub-format-keyed rows (D-17 standing rule), not via the discipline map. |
| D-09 | `sport_discipline_bridge` §4.11 — deployed has 4 denormalized cols + different UNIQUE; spec describes 4 cols only | Med | 🟡 Deferred | 2C (uses bridge for discipline→exercise_db_sport resolution) | 2C already designed against deployed shape. Spec rewrite is documentation. |
| D-10 | `terrain_types` v2 §4.12.4 — deployed has 7 enrichment cols + second UNIQUE; spec describes 2 cols only | High (doc) | 🟡 Deferred | 2B (terrain mapping) | 2B already designed against deployed shape. Provenance unclear — check populate scripts during final cleanup. |
| D-11 | `terrain_gap_rules` — not in spec v3 §4 at all (only in unmerged corrections doc, schema wrong there too) | High (doc) | 🟡 Deferred | 2B (terrain gap resolution) | Deployed schema is authoritative. v4 needs full new §4.x. |
| D-12 | `sport_name_aliases` — schema not documented in §4 (only mentioned in §6.2 run order) | Med (doc) | ✅ Resolved (FC-1a, 2026-05-11) | 2C, 2A (via bridge) | Schema block drafted in `Layer0_ETL_Spec_v3_Patch_Batch_D` §4.x. UNIQUE constraint assumption flagged for verification before v4 lock — verification query in the patch doc. |
| D-13 | `discipline_technique_foci` — Batch B patch says `source_exercise_id` singular; deployed is `source_exercise_ids[]` array. Patch also missing `audit_log` col | Low | ✅ Resolved (FC-1a, 2026-05-11) | 4 (plan-gen consumes foci) | Correction drafted in `Layer0_ETL_Spec_v3_Patch_Batch_B_Correction` — `source_exercise_ids TEXT[]` + `audit_log TEXT`. Documentation-only; deployed shape already matches corrected spec. |
| D-14 | `cross_sport_properties` §4.8 — deployed has 4 extra cols (`source_evidence`, `notes`, `source_text`, `confidence`). `source_text` is suspicious — duplicates `source_evidence` semantically | Low | ✅ Resolved (FC-1a, 2026-05-11) | None currently | Investigation 2026-05-11: confirmed source_text content identical to source_evidence on single deployed row. Column dropped via `migrate_cross_sport_properties_drop_source_text_v1.sql`. Spec catches up in Batch D v2 — cross_sport_properties now has 3 extra cols (source_evidence, notes, confidence). |
| D-15 | `discipline_substitutes` §4.9 — UNIQUE in deployed includes `substitute_name`; spec doesn't. Loose constraint allows duplicate (target, substitute) with different names | Low | ✅ Resolved with explanation (FC-1a, 2026-05-11) | 2D? (substitution logic), 4 (plan-gen) | Investigation 2026-05-11: 2 conflict rows found, both **deliberately-authored sub-format variants with distinct Fidelity ratings**. D-008b→D-007 (Packrafting): whitewater 0.6 vs flat-water 0.4. D-023→D-001 (Trail Running): sustained downhill 0.85 vs rolling 0.3. Tightening would destroy real coaching signal. **Decision: leave deployed UNIQUE loose** (Option D, Andy 2026-05-11). Spec catches up to code in Batch D v2 §4.9 — `UNIQUE (target_id, substitute_id, substitute_name, etl_version)`; substitute_name acts as variant key. Layer 2D substitution logic should query all variants and pick by fidelity given athlete context (locale terrain, equipment, etc.). |
| D-16 | `primary_muscles` / `secondary_muscles` — Open Item R now resolved; spec v3 §4.12 doesn't list them | Low | ✅ Resolved (FC-1a, 2026-05-11) | None (data is fine; doc gap) | Type confirmed `TEXT[]` per Drift Report §1. ETL transform documented: `string_to_array(value, ', ')`. Folds into `Layer0_ETL_Spec_v3_Patch_Batch_B_Correction` (replacement rows for Batch B patch §4.12 "Columns added" table). |
| D-17 | **Sport naming convention mismatch between Sheet 3 and Sheet 5.** Surfaced 2026-05-10 during D-07 verification. `sport_discipline_map` and `sport_discipline_bridge` use top-level sport names ("Triathlon", "Skimo", "Long Distance / Endurance Cycling", "Canoe / Kayak Marathon", "Open Water Marathon Swimming"). `phase_load_allocation` and `phase_load_weekly_totals` use sub-format expansions ("Triathlon (Standard / Olympic)", "Skimo (Sprint)", etc.) — 1:N relationship. AR uses the same name in both tables ✓ | Med | 🟡 Deferred (AR-safe) — **design requirement, not cleanup** | Layer 1 race-goal capture, 2A | **Not an FC-1 task.** This is a forward design item. Resolution path: athlete's race goal (race distance + event format) drives sub-format selection. The mapping logic belongs in Layer 1 onboarding or 2A discipline classification, not in an ETL fix. Owner: whoever drafts the Layer 1 race-goal spec. **D-08 closure (2026-05-11) confirmed plan-gen scales correctly under this naming convention** — phase_load_allocation has sub-format-specific rows for all multi-format sports. |
| D-21 | **`health_condition_categories` column name uncertainty.** v3 spec §4.14 / v2 §4.12.2 defines `category_name`; v3 §6.2 validation note references `system_category`. Drift report originally flagged this table as "no drift" but didn't reconcile the column name. Surfaced 2026-05-10 during 2D design. | Low | 🟡 Deferred | 2D, 2E | 2D's input validation aligns against deployed column. 2E matches against `system_category` string values (symbol-based), so column rename is housekeeping not correctness. FC-1 / FC-2 reconciliation. Standing rule: 2D / 2E match on enum values, not column names. |
| D-22 | **`exercises.injury_flags_text` → structured `movement_components TEXT[]` promotion.** Free text in this column is the only source of "movement constraint × exercise" overlap for 2D. Keyword matching is heuristic with known false-negative risk. Promotion to structured TEXT[] enables set-intersect against B.3 enum tokens (mathematically exact). **Population: 159 active rows** (per Neon `layer0.exercises` query 2026-05-11). Cross-layer note exists in `Athlete_Onboarding_Data_Spec_v2` §B.3. | High | 🔴 **Blocker for 2D implementation (FC-1b)** | 2D | **Pass 1 sampling complete 2026-05-11:** 57 rows classified (36% of population), house rules locked, edits applied per Andy review. Remaining 102 rows + migration SQL pending FC-1b. House rules + Pass 1 baseline live in `D22_Curation_Reference.md`. Spec'd in Layer2D_Spec §5.5 / §6. |
| D-23 | **`disciplines.body_parts_at_risk TEXT[]` companion column** to `common_injury_patterns`. Enables per-discipline risk via set-intersect against athlete injuries instead of hand-curated keyword map. ~150 cells curation. Seed drafted in Layer2D_Spec §5.5. | High | 🔴 **Blocker for 2D implementation (FC-1b)** | 2D | Smaller curation than D-22 but same pattern. v1 fallback path is code-side hand-curated keyword map; structured column is the durable solution. |
| D-24 | **Medications × exercise interaction surface** — deferred to future work (not v1). | Low | 🟡 Deferred | Future | Risk space exists (beta blockers, anticoagulants, etc.) but v1 keeps it out of 2D scope. Revisit post-cohort feedback. Related: D-33 (beta blocker × Cardiac inference). |
| D-25 | **§I v3 polish candidates** — 10 onboarding refinement items parked during §I structured rewrite. | Low | 🟢 Cleanup | Layer 1 v3 | See `Section_I_Audit`. v3 onboarding pass, not now. Not blocking 2E. |
| D-26 | **`supplement_vocabulary` Layer 0 table implemented in FC-1.** | High | ✅ Resolved (FC-1, 2026-05-11) | 2E | Table deployed to Neon dev with 25 seed entries per `Supplement_Vocabulary_Spec`. Schema: 8-value `category` enum + 4-value `evidence_quality` enum + structured `contraindications TEXT[]` for 2E coaching-flag cross-ref against §B. 2E supplement FK reads now valid. ETL tag: `supp_vocab.v1.FC1`. Migration: `etl/sources/migrate_supplement_vocabulary.sql` (already in `main` from IJKL-drift commit 50785df; deployed this session). |
| D-27 | **Plan Management spec not yet written.** 2E names contracts for `HeatAcclimState`, `expected_race_temp_c`, and `current_phase` source-of-truth that Plan Management must honor. Plan Management subsystem also handles weight staleness advisories and adherence-drop logic (see `Adherence_Drop_Spec_v2`). | High | 🟡 Deferred | 2E, future Layer 3/4 | Spec lands post-Layer-3 design. 2E ships with documented contract; Plan Management implementation comes later. Named contract is the protection. |
| D-28 | **FFM (`ffm_kg`) field not captured in onboarding.** Cunningham BMR formula requires FFM; falls back to Mifflin-St Jeor when absent. Onboarding §A (demographics) vs §F (performance testing) home — Andy decision pending. | Med | 🟡 Deferred | 2E | 2E auto-switches BMR formula based on availability (no spec change needed). Onboarding v3 work. |
| D-29 | **`race_fueling_bands` Layer 0 table** — promotion candidate for §5.4.2 5-tier duration band × 7-column matrix currently in code. Sibling: **`dietary_pattern_adjustments`** table (vegan B12/iron/EPA, low-FODMAP race adj, etc., currently in §5.6 logic). | Low | 🟡 Deferred (post-v1) | 2E | Hand-curated bands ship in v1 code; promote when curation pressure rises. Splits curation from algorithm. Mirrors D-22 / D-23 promotion pattern. |
| D-30 | **`sport_endurance_modifier` Layer 0 table** — promotion candidate for §5.4.3 sport modifier (6×3 matrix) currently in code. Sport profile classification currently hand-coded. | Low | 🟡 Deferred (post-v1) | 2E | Same pattern as D-29. Promoting both formalizes the curation pipeline. |
| D-31 | **`sport_mets_table` (Compendium-based)** — promotion candidate enabling a v3 MET-based activity multiplier path more precise than v1 phase × volume lookup in §5.2.2. | Low | 🟡 Deferred (post-v1) | 2E | Multiplier-based fallback used today. METs path is a v3 refinement. |
| D-32 | **HRT × BMR research** — current spec produces miscalibrated BMR for HRT athletes. Coaching flag surfaces the limitation; doesn't fix it. | Low | 🟡 Deferred | 2E | v2 candidate. Research-bound. |
| D-33 | **Beta blocker × Cardiac inference** — should beta blocker presence imply a Cardiac condition for HITL purposes, or require explicit condition record? v1 stays conservative. | Low | 🟡 Deferred | 2E | Defer until first-cohort data informs. Related to D-24 (broader medications surface). |
| D-34 | **Pregnancy status capture** — §B has no explicit pregnancy status field. 2E currently reads `is_pregnant` via free text / HRT class proxy. Either add to §B or treat as Health Condition record (Endocrine/Metabolic). | Med | 🟡 Deferred | 2E, Layer 1 | Onboarding v3 work. 2E has HITL gates dependent on this signal (stimulant × pregnancy, contra supp × pregnancy). |
| D-35 | **Per-discipline GI-risk classification** — currently sport-level via §5.4.3 sport modifier. Discipline-level would tighten race fueling format choice. | Low | 🟡 Deferred (post-v1) | 2E | Future FC. |
| D-36 | **§L.2 Role on Team enum** — deleted from `Athlete_Link_Entity_v2` during V2 spec design (Captain / Navigator / Pacer / Specialist taxonomy was replaced by Discipline Focus on Team). Iceboxed for post-launch consideration. AR Navigator role specifically has distinct training implications (navigation prep, mental load) that may warrant revisit if post-launch evidence of need emerges. | Low | ⚪ Wont-Fix (v1) | §L, future team-training spec | Per Andy 2026-05-11: do not track for v1. Revisit post-launch only if cohort feedback shows the role taxonomy meaningfully improves prescriptions for AR / multi-discipline teams. Functional substitute today: Discipline Focus on Team (L.2) captures which legs an athlete owns, which is the operational signal. |
| D-37 | **`exercises.injury_flags_text` source-data hygiene.** Audit reveals flag text contains content that doesn't describe athlete movement-constraint risk: equipment critiques ("machine poorly aligned"), physiological state ("Cardiac — HR spikes"), cognitive notes ("Cognitive — discipline to walk"), surface-tissue signals ("Skin — friction burns", "Blister — sock interface"), recovery-state notes ("sore in the morning"). These don't fit the B.3 11-token movement constraint enum but **carry real signal** (per Andy: skin/blister affect multiple movements) and **must not be dropped**. Surfaced 2026-05-11 during D-22 Pass 1 sampling. | Med | 🟡 Deferred (post-FC-1) | 2D, Layer 4 | Two-part scope: (1) classify the non-movement flag categories present in `injury_flags_text` (cardiac, cognitive, surface-tissue, recovery-state, equipment-criticism); (2) design and populate appropriate structured Layer 0 columns (`physiological_flags TEXT[]`, `surface_tissue_flags TEXT[]`, etc.) — exact schema TBD. **Coordinates with D-22 (movement_components curation)**: cleaner source means simpler downstream classification. **Out of scope:** the equipment-criticism category specifically can probably just be dropped — per Andy, equipment-quality calls belong to the athlete, not the plan-gen system. |

**Numbering note:** D-18, D-19, D-20 were never assigned (artifact of an aborted earlier numbering plan during the 2026-05-10 / 2026-05-11 session sequence). IDs in this table are stable references from per-layer specs; do not renumber.

---

## Spec doc backfill — completed 2026-05-10

| Item | Status | Notes |
|---|---|---|
| `Layer2A_Spec.md` | ✅ Backfilled | Source: `Layer1_2B_Done_2C_Kickoff_Handoff.md` §"Node 2A". Depth standard matches `Layer2C_Spec.md`. |
| `Layer2B_Spec.md` | ✅ Backfilled | Source: same handoff doc, §"Node 2B". Depth standard matches `Layer2C_Spec.md`. |
| `Layer2C_Spec.md` | ✅ Drafted earlier this session | First per-node consolidated spec; established depth standard. |
| `Control_Spec.md` | ✅ Drafted | Architecture overview; lives above per-node specs. |
| `Project_Backlog.md` | ✅ Renamed from `Layer0_Drift_Backlog.md` | Scope broadened from Layer 0 drift to cross-layer deferred work. |
| Memory rules added | ✅ | Memory edits #4, #5, #6 enforce per-node spec doc rule, backlog rule, control spec rule going forward. |

## Going-forward rule

Every layer/sublayer designed from this point on gets its own `LayerNX_Spec` at the `Layer2C_Spec` depth standard. Handoff docs are session bookkeeping; specs are source of truth. New spec → update `Control_Spec` §9 doc map.

---

## Verification checks — all resolved

**Run:** 2026-05-10 via `verify_drift_specifics.sql`. Output: `drift_verification.txt`.

All three checks (A, B, C) confirmed: D-05, D-07, D-08 are AR-safe and stay deferred. D-05 elevated to "standing rule" status — every Layer 2 query node spec MUST include the defensive aggregator filter. D-17 added as new finding from cross-referencing Check B and Check C outputs.

Verification SQL committed to project for reproducibility (Andy's note: matches prior introspection-script pattern).

---

## Final cleanup batch — status

### Session FC-1a: ETL bug fixes — ✅ CLOSED 2026-05-11

**All 11 items resolved or partial:**
- ~~D-04~~ — ✅ Resolved
- ~~D-05~~ — 🟡 Partial (cleanup done; ETL code patch + standing rule retirement deferred to CC)
- ~~D-06~~ — ✅ Resolved
- ~~D-07~~ — ✅ Resolved with decisions (CC parser fix pending; specs in `FC1a_Closing_Handoff_v1.md` §5.2)
- ~~D-08~~ — ✅ Resolved with explanation (no bug; xlsx source fix queued for Triathlon D-002 stale row)
- ~~D-12~~ — ✅ Resolved (Batch D patch)
- ~~D-13~~ — ✅ Resolved (Batch B Correction)
- ~~D-14~~ — ✅ Resolved (source_text dropped; spec catches up in Batch D v2)
- ~~D-15~~ — ✅ Resolved with explanation (loose UNIQUE preserved as variant key; spec catches up in Batch D v2)
- ~~D-16~~ — ✅ Resolved (TEXT[] confirmed; Batch B Correction)
- D-03 — Decision locked: BUILD (CC implementation deferred to v20 ETL re-run)

### Session FC-1b: column promotions — UPCOMING

**Blocker class — 2D implementation depends on these:**
- D-22 — promote `exercises.movement_components TEXT[]` (Pass 1 sampling done 2026-05-11; 57/159 classified, house rules locked. Remaining 102 rows + migration SQL).
- D-23 — promote `disciplines.body_parts_at_risk TEXT[]` (~150 cells curation; seed drafted in Layer2D_Spec §5.5).
- ~~D-26~~ — ✅ Resolved 2026-05-11. `supplement_vocabulary` table deployed to Neon dev.

Estimated 2–4 hours for D-22 batch 2, plus D-23 curation and migration SQL.

### Session FC-2: Spec v4 rewrite — UPCOMING
- Fold Batches A, B, C, D, B-Correction, this report's drift items into a unified `Layer0_ETL_Spec_v4`
- Add missing §4 sections for `terrain_gap_rules` (and confirm `sport_name_aliases` from Batch D landed; `discipline_technique_foci` already in Batch B + B-Correction)
- Apply all §8 consumer table corrections from `ETL_Spec_v3_Corrections_2ABC_v2`
- Document the "code is authoritative; spec catches up" pattern as a §6 process note

---

## Process notes

1. At every Layer 2 node-boundary (end of 2C consolidation, end of 2D design, end of 2E design):
   - Re-read this backlog
   - Flag any 🟡 Deferred item that the just-finished node interacted with — does it need to promote to 🔴 Blocker before the next node starts?
   - Add new findings from the just-finished node, categorized fresh

2. The "Blocker" status is sticky-up but not sticky-down. Once promoted to blocker, stays blocker until resolved. A blocker is resolved only by a fix, not by deciding to ignore it.

3. If a "Cleanup" item turns out to have functional impact mid-flight, it gets recategorized 🟡 or 🔴 with a note. No reverse path — pure documentation issues that surface as blockers were never just docs.

4. Drift findings DO carry over to the v20 xlsx work — see the existing drift report §4 and §5 for the v20-specific items. v20 xlsx is its own batch, not in this backlog's scope.

---

## Open items NOT in this backlog (out of scope)

- v20 xlsx authoring (separate batch)
- Spec v4 narrative sections beyond §4 schema blocks (§3 parsing rules, §5 query layer, §8 consumer table) — fold into FC-2 if quick, otherwise own session
- Hand-curated table protection rules (terrain_types enrichment, terrain_gap_rules, discipline_technique_foci) — needs a "v20 ETL doesn't touch these" rule. Lives with v20 batch.
- Layer 3 design — separate workstream
- **LEA / RED-S surveillance** — bone health, energy availability tracking. Out of v1 scope per 2026-05-11 decision during 2E design. v3+ candidate. Status: ⚪ Wont-Fix for v1.
