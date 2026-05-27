# Project Backlog

**Renamed from:** `Layer0_Drift_Backlog.md` (was scoped to Layer 0 drift; now broader)
**Started:** 2026-05-10
**File revision:** v9 — 2026-05-13 (post-FC-4b closure: Spec v7 closes D-21 health_condition_categories column-name reconciliation — deployed column is `category_name`; the §6.2 `system_category` reference was the stale half of the v3 split-reference. **Layer 0 spec is now fully self-consistent against deployed Neon schema across every enumerated table.**)
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
| D-21 | **`health_condition_categories` column name uncertainty.** v3 spec §4.14 / v2 §4.12.2 defines `category_name`; v3 §6.2 validation note references `system_category`. Drift report originally flagged this table as "no drift" but didn't reconcile the column name. Surfaced 2026-05-10 during 2D design. | Low | ✅ Resolved (FC-4b, 2026-05-13) | 2D, 2E | **2026-05-13: D-21 closed.** Neon `information_schema.columns` retry returned 6 columns + 2 constraints. **Deployed column is `category_name`** (matching v3 §4.14 / v2 §4.12.2); the v3 §6.2 validation `system_category` reference was the stale half of the split — corrected to `.category_name` in `Layer0_ETL_Spec_v7.md` §6.2. Full schema block now in v7 §4.14. **Consumer impact: none.** `system_category` continues as the Python dataclass field name on `HealthConditionRecord` in Layer 2D / 2E (independent of the SQL column name); the dataclass field is what 2D and 2E actually read. Layer 2D row 2D-5 and Layer 2E row 2E-16 open-items can resolve on next 2D / 2E touch (no spec bump required just for this; piggyback with D-47). |
| D-22 | **`exercises.movement_components TEXT[]` deployed.** Structured movement-constraint tokens (subset of Onboarding §B.3 11-token enum) replace heuristic keyword-match against `injury_flags_text` for Layer 2D set-intersect. **Population: 159 active rows.** | High | ✅ Resolved (FC-1b, 2026-05-12) | 2D | **2026-05-12: D-22 closed.** 159/159 rows populated via `migrate_exercises_add_movement_components_v1.sql` (57 Pass 1 + 102 Pass 2). All 6 verification checks passed; GIN index `idx_exercises_movement_components` deployed. Full baseline + house rules in `D22_Curation_Reference_v2.md` (Rules 1–11 Pass 1 + Calibrations 12–15 Pass 2). EX024/EX119 consistency precedent applied. Generator: `etl/sources/generate_movement_components_migration.py`. `injury_flags_text` retained as reference data; `movement_components` is now source of truth for 2D. Open follow-ups: D-37 (source-data hygiene), D-38 (wrist deviation token gap). |
| D-23 | **`disciplines.body_parts_at_risk TEXT[]` deployed.** Structured body-part tokens enable direct set-intersect against athlete `Injury Record.body_part` (canonical 51-token vocabulary), replacing the heuristic `BODY_PART_KEYWORDS` map in Layer2D_Spec §5.5. **Population: 31 disciplines.** | High | ✅ Resolved (FC-1b, 2026-05-12) | 2D | **2026-05-12: D-23 closed.** 31/31 rows populated via `migrate_disciplines_add_body_parts_at_risk_v1.sql` (172 total token references across the baseline; 28 of 51 canonical body parts used in discipline-level risk patterns). All 6 verification checks passed; GIN index `idx_disciplines_body_parts_at_risk` deployed. Locked baseline + house rules in `D23_Curation_Reference_v1.md` (Rules 1–7 + Shoulder/Rotator-cuff normalization calibration). Generator: `etl/sources/generate_body_parts_at_risk_migration.py`. Per Andy 2026-05-12: Head/Eye/perineum permanently skipped (not body-part-relevant at this layer); Collarbone added to canonical body parts vocabulary. `common_injury_patterns` retained as reference data; `body_parts_at_risk` is now source of truth for 2D. **Layer2D_Spec §5.5 decision point B locked.** Follow-up: D-39 (Vocabulary_Audit v3 rewrite). |
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
| D-37 | **`exercises.injury_flags_text` source-data hygiene.** Audit reveals flag text contains content that doesn't describe athlete movement-constraint risk: equipment critiques ("machine poorly aligned"), physiological state ("Cardiac — HR spikes"), cognitive notes ("Cognitive — discipline to walk"), surface-tissue signals ("Skin — friction burns", "Blister — sock interface"), recovery-state notes ("sore in the morning"). These don't fit the B.3 11-token movement constraint enum but **carry real signal** (per Andy: skin/blister affect multiple movements) and **must not be dropped**. Surfaced 2026-05-11 during D-22 Pass 1 sampling. | Med | 🟡 Deferred (post-FC-1) | 2D, Layer 4 | Two-part scope: (1) classify the non-movement flag categories present in `injury_flags_text` (cardiac, cognitive, surface-tissue, recovery-state, equipment-criticism); (2) design and populate appropriate structured Layer 0 columns (`physiological_flags TEXT[]`, `surface_tissue_flags TEXT[]`, etc.) — exact schema TBD. **Coordinates with D-22 (movement_components curation)**: cleaner source means simpler downstream classification. **Out of scope:** the equipment-criticism category specifically can probably just be dropped — per Andy, equipment-quality calls belong to the athlete, not the plan-gen system.  |
| D-38 | **Wrist deviation under load** — canonical token gap. The 11 `movement_components` tokens cover wrist *extension* (WristExt) but not wrist *deviation* (ulnar/radial). Surfaced twice in D-22 Pass 2: EX126 Freestyle Pull (ulnar deviation stress at hand entry) and EX235 Tricep Pushdown/Extension (wrist deviation if grip angle wrong). Both force-mapped to `Pain above specific joint angle` (Angle), analogous to Pass 1's Rule 11 lateral-flexion-→-Instab force-mapping. | Low | 🟢 Cleanup | 2D, future v2 vocabulary | Two data points across 159 rows is below threshold for adding a 12th canonical token. Track for Layer 2 v2 vocabulary review. Current force-mapping to Angle documented in `D22_Pass2_Done_MigSQL_D23_Kickoff_Handoff_v1.md` §3 Calibration D-precedent / §2 Aerobic-Endurance + Strength sections. |
| D-39 | **`Vocabulary_Audit` v3 rewrite** — formal canonical body parts list update. Two cleanup items folded together: (1) `Collarbone` added to Section 1 Shoulder region per D-23 curation (2026-05-12); (2) "Total: 41 canonical body parts" header is stale — enumerated tables sum to 51 with Collarbone (50 before). Both surfaced during D-23 work. | Low | ✅ Resolved (FC-2, 2026-05-12) | Layer 1 v3, future vocab work | Vocabulary_Audit_v3.md shipped FC-2: Collarbone added to Section 1 Shoulder canonical list with D-23 attribution; total recount to 51 with per-subsection breakdown (3+5+11+5+6+3+7+5+4+2). "What changed in v3 vs v2" header documents the closure. Section 1 now matches deployed `body_parts_at_risk` vocabulary. Layer2D_Spec_v1 §5.4/§5.5 references updated from v2 → v3. |
| D-40 | **`terrain_gap_rules` schema dump.** Drift report §2.12 documents 12-column deployed table with 12 active rows but does not enumerate columns. ETL_Spec_v3_Corrections_2ABC_v2 §4.10a proposal had 5 cols, doesn't match deployed. Layer0_ETL_Spec_v4 §4.17 contains a placeholder schema block with a `\d layer0.terrain_gap_rules` action note. | Low | ✅ Resolved (FC-3, 2026-05-13) | 2B (terrain gap resolution) | **2026-05-13: D-40 closed.** Neon `\d layer0.terrain_gap_rules` enumerated 12 functional columns: `target_terrain_id`, `target_terrain_name`, `proxy_terrain_id` (nullable), `proxy_terrain_name` (nullable), `gap_severity`, `adaptation_weeks_low/high`, `proxy_fidelity`, `proxy_methods TEXT[]`, `uncoverable_stimulus TEXT[]`, `prescription_note`, `audit_log`. UNIQUE: `(target_terrain_id, proxy_terrain_id, etl_version)`. Nullable `proxy_terrain_id` permits multiple "uncoverable" rows per target. Layer0_ETL_Spec_v5 §4.17 replaces placeholder with full schema block. |
| D-41 | **`terrain_types` 7 enrichment columns enumeration.** Drift report §2.10 names them (`terrain_id`, `category`, `requires_elevation`, `technical_surface`, `environment`, `simulatable`, `simulation_note`) + secondary UNIQUE on `(terrain_id, etl_version)` but v3/v4 vocabulary §4.14 still references the 2-col v2 spec. 16 superseded rows out of 31 indicate hand-curation provenance worth investigating during the same schema-dump session. | Low | ✅ Resolved (FC-4a, 2026-05-13) | 2B (terrain mapping) | **2026-05-13: D-41 closed.** `information_schema.columns` retry returned 9 functional columns + 2 UNIQUE constraints. **Drift report correction:** `simulatable` is `TEXT`, not `BOOLEAN` as §2.10 claimed (permits 'yes'/'no'/'partial'/'conditional'/etc.). `terrain_id` is nullable; UNIQUE on `(terrain_id, etl_version)` permits multiple `terrain_id IS NULL` rows per `etl_version` — consistent with 16/31 hand-curation history. Layer0_ETL_Spec_v6 §4.14 replaces the 2-bullet drift note with full schema block. |
| D-42 | **`cross_sport_properties` deployed-columns reconciliation.** Drift report §2.7 says v3 baseline 6 cols + 4 extras (later 3 after D-14 drop). Batch D v2 §3 "Replacement column list" shows DIFFERENT functional columns (`property_type`, `value`, `unit`, `applies_to_sports`, `applies_to_disciplines` instead of v3's `description`, `scope`, `ranking_text`, `estimated_values`). v4 §4.8 took the drift report as authoritative + retained v3 baseline cols + 3 extras. | Low | ✅ Resolved (FC-3, 2026-05-13) | None currently | **2026-05-13: D-42 closed.** Neon `\d layer0.cross_sport_properties` confirmed v4 column list correct (v3 baseline 6 + `source_evidence` + `notes` + `confidence`). Batch D v2 §3's proposed alternate columns (`property_type`, `value`, `unit`, `applies_to_sports`, `applies_to_disciplines`) confirmed not deployed — drift report was authoritative. **Type correction:** `confidence` is `TEXT`, not `NUMERIC` as v4 spec had it. Column carries qualitative labels (e.g. "High", "Medium", "Low"), not numeric scores. Layer0_ETL_Spec_v5 §4.8 corrected. |
| D-43 | **Batch A and Batch C patch documents not in project knowledge.** Both referenced in Control_Spec_v1 §9 doc map and Batch D v2 §1 companion-docs line, but absent from project files at FC-2 draft time. Their substance was reconstructed from drift report v2 for v4. | Low | 🟢 Cleanup | None | If Batch A/C documents are recovered (likely in repo `etl/patches/` or similar), archive in project knowledge for audit history. No new spec change expected — drift report has the same content table-by-table. |
| D-44 | **`sport_name_aliases` UNIQUE deployed-vs-spec divergence.** v4 §4.16 specified UNIQUE on 2 cols `(exercise_db_sport, etl_version)` and claimed "one-to-one enforced inversely — an exercise_db_sport at a given etl_version maps to exactly one framework_sport." Surfaced during FC-3 pre-v4-lock verification. | Med | ✅ Resolved (FC-3, 2026-05-13) | §4.11 `sport_discipline_bridge` derivation | **2026-05-13: D-44 opened and closed.** Neon `pg_constraint` query revealed deployed UNIQUE is 3 cols `(exercise_db_sport, framework_sport, etl_version)`. Per §6.6, deployed wins. Layer0_ETL_Spec_v5 §4.16 corrected; "one-to-one inverse" claim retracted. **Consumer impact:** §4.11 bridge derivation must treat the alias join as one-to-many. If any active `exercise_db_sport` maps to multiple `framework_sport` values, the bridge build will multiply rows. Follow-up D-46 below. |
| D-45 | **`Layer0_ETL_Spec` §5.2 signatures diverged from per-layer specs.** v4 §5.2 had 2A/2B/2E as 1–2-param stubs vs 4–8 in per-layer spec; FC-2 "corrections" for 2C/2D had wrong shape (2C used flat athlete-equipment vs locale-keyed; 2D pre-partitioned status externally vs internal §5.1 partition). Surfaced during FC-3 §5 narrative refresh. | Med | ✅ Resolved (FC-3, 2026-05-13) | All Layer 2 query implementation | **2026-05-13: D-45 opened and closed.** Layer0_ETL_Spec_v5 §5.2 rewritten to mirror each per-layer spec verbatim with "Mirror of LayerXX_Spec §3" attribution. Formalizes §6.6 spec-of-spec rule at signature level. Prevents FC-2-style misreading from recurring. v5 §5.2 includes a reconciliation log showing each diff. |
| D-46 | **`sport_discipline_bridge` row-multiplication audit.** Follow-up from D-44. If any active `exercise_db_sport` in `layer0.sport_name_aliases` maps to multiple `framework_sport` values at the same `etl_version`, the §4.11 bridge derivation will produce multiplied rows (one per alias mapping). Need to determine whether this is intentional curation (e.g., a sport like "Trail Running" legitimately belongs to multiple framework sports) or accidental dict duplication in `sport_name_aliases.py`. | Med | ✅ Resolved (FC-4a, 2026-05-13) | §4.11 bridge derivation, 2A consumption | **2026-05-13: D-46 closed.** Active-row COUNT returned 21 multi-mapped `exercise_db_sport` values. Pattern confirmed **intentional** for framework sub-format splitting (Triathlon → 5 sub-formats; Swimming → 11 contexts; SkiMo/Rowing/XC Skiing → sub-format variants; General Conditioning → 38 broadly-applicable framework sports). No `sport_name_aliases.py` tightening required. Multi-mapping table documented in Layer0_ETL_Spec_v6 §4.16. Downstream consequence: bridge produces multiplied rows for the same `(exercise_id, discipline_id)` pair when a discipline is shared across multi-mapped framework sports — consumer dedup requirement now documented in §4.11. Layer 2D §5.2 already dedups by `exercise_id` (functional behavior correct); rationale-comment update for that spec tracked separately as D-47. |
| D-47 | **Layer 2D §5.2 SQL rationale comment incomplete.** Comment cites multi-discipline path as the reason for post-query dedup by `exercise_id` but does not cite the framework-mapping multiplication path documented in Layer0_ETL_Spec_v6 §4.11 (multi-mapped `exercise_db_sport` produces multiple bridge rows for the same `(exercise_id, discipline_id)` pair). Functional behavior is correct (dedup-by-exercise_id handles both paths); only the explanatory comment is incomplete. Generalizes: any new consumer joining through `sport_discipline_bridge` needs to know about both paths. | Low | 🟢 Cleanup | Layer 2D, future consumers of `sport_discipline_bridge` | At next Layer 2D revision (or any FC pass that touches Layer2D_Spec), update §5.2 rationale comment to cite both paths. Suggested wording: "An exercise may appear in the join output multiple times for two reasons: (1) it maps to multiple included disciplines, and (2) its `exercise_db_sport` maps to multiple `framework_sport` values whose disciplines overlap (`Layer0_ETL_Spec` §4.11 multiplication property). Post-query dedup by `exercise_id` handles both; track `discipline_ids[]` per exercise for risk attribution." |

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

### Session FC-1b: column promotions — ✅ CLOSED 2026-05-12

**All FC-1b blockers resolved this session:**
- ~~D-22~~ — ✅ Resolved 2026-05-12. `exercises.movement_components TEXT[]` deployed; 159/159 rows populated; GIN index in place.
- ~~D-23~~ — ✅ Resolved 2026-05-12. `disciplines.body_parts_at_risk TEXT[]` deployed; 31/31 rows populated; GIN index in place. Vocabulary amendment: Collarbone added to canonical body parts (tracked as D-39 for formal v3 rewrite).
- ~~D-26~~ — ✅ Resolved 2026-05-11. `supplement_vocabulary` table deployed to Neon dev.

**Layer 2D implementation now unblocked.** Both source-of-truth columns (`movement_components`, `body_parts_at_risk`) live with GIN indexes; the set-intersect paths in Layer2D_Spec §5.4.1 (movement components) and §5.5 (body parts) can ship without the keyword-map fallbacks. Decision Points 2D-1 (body-part keyword map → Path B) and the movement-component path are both locked to structured columns.

### Session FC-2: Spec v4 rewrite — ✅ CLOSED 2026-05-12

**All FC-2 items resolved:**
- ~~D-39~~ — ✅ Resolved 2026-05-12. `Vocabulary_Audit_v3.md` shipped: Collarbone added, total recount to 51.
- ✅ `Layer0_ETL_Spec_v4.md` shipped: 4 new tables added (§4.15 discipline_technique_foci with B-Correction; §4.16 sport_name_aliases; §4.17 terrain_gap_rules placeholder; §4.18 supplement_vocabulary placeholder). All §4 existing tables reconciled to deployed shape (D-02 col renames; D-04 phase_ prefix drop; D-06/D-07 hours rename + parser-fix decisions; D-09 sport_discipline_bridge denormalized cols + corrected UNIQUE; D-14 cross_sport_properties extras; D-15 substitute_name variant key; D-16 muscles TEXT[]; D-01 exercises full reconciliation). New columns documented: `movement_components` on exercises (D-22); `body_parts_at_risk` on disciplines (D-23). §6.6 process note added ("Code is authoritative; spec catches up"). §7 open items refactored to point at this backlog. §8 consumer table corrected per `ETL_Spec_v3_Corrections_2ABC_v2`. §5.2 2D/2C function signatures corrected per Layer2D_Spec_v1 + corrections doc.
- ✅ `Layer2D_Spec_v1.md` shipped: §5.3.3 rewritten to use `movement_components` set-intersect (D-22 closed); §5.4 `discipline_risk()` rewritten to use `body_parts_at_risk` set-intersect (D-23 closed); §5.5 Decision Point B locked + deployed (Path B); §6 drift items D-22, D-23 marked Resolved; §12 open items 2D-1, 2D-2, 2D-6 marked Closed; new item 2D-11 added for D-38 sub-threshold wrist deviation. `MOVEMENT_CONSTRAINT_KEYWORDS` and `BODY_PART_KEYWORDS` demoted to historical reference (not runtime).
- **New cleanup items surfaced:** D-40 (terrain_gap_rules schema dump), D-41 (terrain_types 7 enrichment cols enumeration), D-42 (cross_sport_properties columns reconciliation), D-43 (Batch A/C patch docs not in project knowledge).

**Layer 2 family is now substantively spec-complete through 2D.** Remaining open Layer 0 work: D-03/D-07 ETL parser fixes pending v20 re-run (CC task); D-40/D-41/D-42 schema-dump documentation cleanup; D-43 patch-doc archive. None block Layer 3 design or query-layer implementation.

### Session FC-3: Spec v5 schema corrections + §5 rewrite — ✅ CLOSED 2026-05-13

**All in-scope FC-3 items resolved:**
- ~~D-40~~ — ✅ Resolved 2026-05-13. `terrain_gap_rules` schema enumerated; v5 §4.17 replaces placeholder.
- ~~D-42~~ — ✅ Resolved 2026-05-13. `cross_sport_properties` confirmed; `confidence` type corrected `NUMERIC` → `TEXT` in v5 §4.8. Batch D v2 §3 alternate columns confirmed not deployed.
- ~~D-44~~ — ✅ Opened and closed 2026-05-13. `sport_name_aliases` UNIQUE corrected from 2-col to 3-col `(exercise_db_sport, framework_sport, etl_version)` in v5 §4.16. "One-to-one inverse" claim retracted.
- ~~D-45~~ — ✅ Opened and closed 2026-05-13. `Layer0_ETL_Spec` §5.2 rewritten to mirror per-layer 2A–2E spec signatures verbatim. Formalizes §6.6 spec-of-spec rule at signature level.
- ✅ `Layer0_ETL_Spec_v5.md` shipped: schema corrections (§4.8, §4.16, §4.17), §5 query-layer narrative rewrite (§5.1 primitives note, §5.2 full rewrite with attribution, §5.3 canonical payload updated for `movement_components` + `common_injury_patterns` + `body_parts_at_risk` surfacing + `HealthConditionRecord` field alignment, §5.4 D-15 variant-key annotation).

**Carried forward:**
- **D-41** — `terrain_types` schema dump retry. Neon `\d` query failed in FC-3 on a client-side quoting artifact. Retry uses `information_schema.columns` form. One query + one str_replace edit.
- **D-46** — `sport_discipline_bridge` row-multiplication audit. Follow-up from D-44 closure. Single COUNT query to determine whether any active alias multi-mappings exist.

**Layer 0 spec is now self-consistent against deployed schema** with one verified-pending gap (D-41 `terrain_types`) and one consumer-side audit (D-46 bridge). The §5 query-layer narrative now reflects deployed reality and per-layer authoritative signatures. Layer 0 work has no remaining blockers for Layer 3 design or query-layer implementation.

### Session FC-4a: Spec v6 — D-41 terrain_types + D-46 multi-mapping audit — ✅ CLOSED 2026-05-13

**All in-scope FC-4a items resolved:**
- ~~D-41~~ — ✅ Resolved 2026-05-13. `terrain_types` 9-column schema enumerated; drift report's `simulatable BOOLEAN` claim corrected to `TEXT`; nullable `terrain_id` with NULL-distinct UNIQUE documented. Layer0_ETL_Spec_v6 §4.14 replaces 2-bullet drift note.
- ~~D-46~~ — ✅ Resolved 2026-05-13. 21 multi-mapped `exercise_db_sport` values confirmed intentional for framework sub-format splitting. No `sport_name_aliases.py` tightening. Multi-mapping table documented in v6 §4.16. Bridge multiplication property documented in v6 §4.11 with consumer dedup pattern.
- **New cleanup item D-47** — Layer 2D §5.2 rationale-comment update (functional behavior already correct; comment incomplete). Tracked for next Layer 2D revision.
- ✅ `Layer0_ETL_Spec_v6.md` shipped: §4.14 terrain_types schema enumerated; §4.16 multi-mapping audit findings + table; §4.11 bridge multiplication property + consumer dedup pattern + reference SQL.

**Layer 0 spec is now fully self-consistent against deployed schema** for every Neon-enumerated table. Remaining uncertainty is in `health_condition_categories` column name (D-21, separate session). All other tables either match spec exactly or have FC-1/FC-3/FC-4a corrections committed.

### Session FC-4b: Spec v7 — D-21 health_condition_categories column-name reconciliation — ✅ CLOSED 2026-05-13

**All in-scope FC-4b items resolved:**
- ~~D-21~~ — ✅ Resolved 2026-05-13. Neon `information_schema.columns` returned 6 columns + 2 constraints. **Deployed column is `category_name`**; v3 §6.2 `system_category` reference was the stale half of the split. Layer0_ETL_Spec_v7 §4.14 documents full schema block (6 cols, `UNIQUE (category_name, etl_version)`); §6.2 validation line corrected from `.system_category` → `.category_name`. **No consumer change required** — `system_category` is the Python dataclass field name on `HealthConditionRecord`, independent of the SQL column name.
- ✅ `Layer0_ETL_Spec_v7.md` shipped: §4.14 health_condition_categories schema block replaces D-21 deferral bullet; §6.2 column reference corrected; v6 → v7 changelog block added.
- ✅ Layer 0 spec is now **fully self-consistent against deployed Neon schema** across every enumerated table.

**Carried forward (not FC-4b scope):**
- **D-47** — Layer 2D §5.2 rationale-comment update. Fold into next Layer 2D revision; Layer 2D row 2D-5 and Layer 2E row 2E-16 D-21 housekeeping rows can be cleared in the same pass.
- **D-03 / D-07** — ETL parser fixes pending v20 re-run (CC tasks).

### Session FC-5 (next): tentative scope

**Recommended path: start a fresh chat for Layer 3 design.** The remaining open items (D-03 / D-07 / D-47) are small and orthogonal; Layer 3 is the next big arc and deserves a dedicated context window.

- **Layer 3 design kickoff** — six parallel sub-prompts (race analysis, fitness capacity, training history, injury/risk analysis with HITL trigger generation, goal alignment, constraint mapping) plus the Layer 3.5 hard HITL gate. First session likely focused on the discovery doc / sub-prompt boundary decisions before per-sub-prompt spec work begins. Primary forward move.
- **D-47** — fold into the first Layer 2D touch after Layer 3 starts (likely when 3D injury analysis depends on 2D output, prompting a Layer 2D → v2 revision).
- **D-03 / D-07** — CC task whenever v20 xlsx authoring batch happens. Independent track.

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
