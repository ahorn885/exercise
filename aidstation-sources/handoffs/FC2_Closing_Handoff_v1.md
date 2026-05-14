# FC-2 Closing Handoff — Spec v4 Rewrite + Layer2D Promotion + Vocabulary v3

**Session:** FC-2 (Final Cleanup batch 2 — Layer 0 spec consolidation)
**Date:** 2026-05-12
**Predecessor handoff:** `FC1b_Closing_Handoff_v1.md`
**Status:** ✅ All FC-2 in-scope items shipped. Five files in `/mnt/user-data/outputs/` ready for upload.
**Time-on-task:** Long single session (all-in scope was Andy's call after Claude flagged the size).

---

## 1. Session-start verification (rule #9 — completed)

Per the verification rule, the prior handoff's claimed file updates were spot-checked at session start:

| Claimed by FC-1b handoff | Verified on disk | Notes |
|---|---|---|
| `Project_Backlog_v5.md` with D-22/D-23 ✅ Resolved, D-39 row added | ✅ Present | All three rows present and correctly stated |
| `D23_Curation_Reference_v1.md` | ✅ Present | Used as v4 / Vocabulary v3 source |
| `FC1b_Closing_Handoff_v1.md` itself | ✅ Present | — |
| `migrate_exercises_add_movement_components_v1.sql` | ✅ Present in project knowledge | D-22 migration |
| D-23 migration SQL + 2 generator .py scripts | ❌ Not in project knowledge | Confirmed by Andy: convention is repo-only; D-22 SQL inclusion was incidental. No gap. |
| Neon deployed state (both columns + GIN indexes live) | ✅ Confirmed by Andy | — |

**Gap reconciliation result:** zero. FC-1b state matches reality.

---

## 2. Scope confirmed at session start

Andy chose **all-in** scope despite Claude's flag that the session would be long:

1. ✅ Full `Layer0_ETL_Spec_v4.md` rewrite folding all patches + drift report items
2. ✅ `Layer2D_Spec_v1.md` — §5.3.3 / §5.4 / §5.5 set-intersect rewrite to use deployed columns
3. ✅ `Vocabulary_Audit_v3.md` — Collarbone + total recount (D-39 closure)
4. ✅ `Project_Backlog_v6.md` — D-39 close, new D-40 through D-43 cleanup items
5. ✅ `Control_Spec_v2.md` — §9 doc map update

---

## 3. Files shipped (in `/mnt/user-data/outputs/`)

### 3.1 `Vocabulary_Audit_v3.md`

Surgical edits to v2 baseline. Three changes:

- **Header → v3** with new `## What changed in v3 vs v2` section documenting D-39 closure (Collarbone added, total recount 41→51, no other section changes).
- **Section 1 — Shoulder canonical list:** added `Collarbone` row with D-23 (FC-1b, 2026-05-12) attribution and notes "Clavicle — added for D-006 (Mountain Biking) crash injury patterns. Common clinical/athlete-facing term retained over 'clavicle'."
- **Section 1 total:** "Total: 41 canonical body parts" → "Total: 51 canonical body parts" with per-subsection breakdown footnote (Head/Neck 3 · Shoulder 5 · Arm 11 · Back 5 · Hip 6 · Upper leg 3 · Knee 7 · Lower leg 5 · Foot/Ankle 4 · Trunk 2 = 51).

Sections 2–8 (Health Conditions, Equipment, Sport-Specific Gear Toggles, Required Changes Summary, Col 7 cleanup tasks, UX flow note, v2 spec changes summary, No-equipment fallback logic, Open items deferred) carry forward unchanged from v2.

### 3.2 `Layer2D_Spec_v1.md`

Surgical edits to unversioned baseline. Six edit points:

- **Header → v1** with new `## What changed in v1 vs unversioned draft` section enumerating §5.3.3 / §5.4 / §5.5 / §6 / §12 changes + the wrist-deviation 2D-11 addition.
- **§5.3.3 (Movement-constraint match) rewritten** to set-intersect against deployed `exercises.movement_components TEXT[]`. Code block updated. `MOVEMENT_CONSTRAINT_KEYWORDS` map demoted to "DEPRECATED — kept for v1→v4 transition audit. Do not call." D-38 wrist deviation sub-threshold gap documented.
- **§5.4 (`discipline_risk()`) rewritten** to set-intersect against deployed `disciplines.body_parts_at_risk TEXT[]`. Function signature drops the `body_part_keywords` parameter. Postgres `&&` overlap query pattern documented. Vocabulary-alignment rationale added.
- **§5.5 (Body-part vocabulary alignment)** marked as Locked / Path B deployed FC-1b. `BODY_PART_KEYWORDS` code block demoted to historical reference. Why Path B won (queryable + auditable; no synonym drift; maintenance with vocab not code; removes false-negative risk) documented. Curation reference cited (`D23_Curation_Reference_v1.md`).
- **§6 (Drift items affecting 2D):** D-22 and D-23 marked ✅ Resolved (FC-1b, 2026-05-12) with deployed column counts and GIN-index names. D-15 marked ✅ Resolved (FC-1a). D-21 reclassified Deferred (documentation). D-38 added as 🟢 Cleanup (v2 vocab review).
- **§12 (Open items):** 2D-1, 2D-2, 2D-6 marked ✅ Closed (FC-1b). 2D-11 added for D-38 wrist deviation.

§§1-4, §5.1, §5.2, §5.3.1-2, §5.3.4-5, §5.6, §5.7, §§7-11, §§13-14 unchanged from unversioned draft.

### 3.3 `Layer0_ETL_Spec_v4.md`

File-revision rewrite. Schema version stays v3 — v4 is documentation consolidation only, no schema fork.

**Header → v4** with comprehensive `## What changed in v4 vs v3` enumerating 22 items: 4 new tables, 6 schema additions/promotions, 13 corrections to existing tables (FC-1a closures), 2 pending implementations (D-03/D-07 CC tasks), the new §6.6 process note, and out-of-scope items carried forward.

Per-table edits in §4:

- **§4.3 disciplines (UPDATED v4):** column renames `injury_patterns`→`common_injury_patterns`, `preceding_behaviors`→`injury_preceding_behaviors` (D-02). Added `body_parts_at_risk TEXT[]` + GIN index (D-23). `stimulus_components` marked populated.
- **§4.5 phase_load_allocation (UPDATED v4):** `phase_` prefix dropped from band columns (D-04). `is_conditional` and `vertical_gain_notes` marked `[NOT-YET-DEPLOYED]` (D-03 pending CC for v20). D-05 standing rule + D-17 sub-format naming explained.
- **§4.5.1 phase_load_weekly_totals (UPDATED v4):** D-06 column renames documented. D-07 parser-fix decisions (7.1A multi-sub-format collapse, 7.2B km→hrs conversion, 7.3A percentage-cut TAPER derivation) recorded.
- **§4.8 cross_sport_properties (UPDATED v4):** `source_evidence`, `notes`, `confidence` added per drift report §2.7. `source_text` dropped per D-14. **Known inconsistency flagged:** Batch D v2 §3 lists different functional columns; v4 takes drift report as authoritative. Tracked as D-42.
- **§4.9 discipline_substitutes (UPDATED v4):** loose UNIQUE preserved with `substitute_name` as variant key (D-15). Consumer guidance for Layer 2D/4 added.
- **§4.11 sport_discipline_bridge (UPDATED v4):** 4 denormalized cols added (`discipline_name`, `role`, `default_race_time_pct_low/high`) per drift report §2.6. UNIQUE corrected to `(framework_sport, discipline_id, etl_version)`.
- **§4.12 exercises (UPDATED v4):** comprehensive Batch B + B-Correction reconciliation. 4 renames + 1 structure change + 1 column removed + 7 cols added + 1 UNIQUE contradiction resolved. Added `movement_components TEXT[]` + GIN index (D-22). `injury_flags_text` retained as REFERENCE; `movement_components` is source of truth for 2D. `primary_muscles`/`secondary_muscles` confirmed `TEXT[]` with `string_to_array(value, ', ')` ETL transform (D-16). `equipment_substitutes` confirmed single JSONB (not split). Type vocabulary update: `Technical / Skill` deprecated as of `0B-v19.B`. D-37 source-data hygiene noted.
- **§4.14 vocabulary tables (UPDATED v4):** source bumped to `Vocabulary_Audit_v3.md`. Drift notes for `terrain_types` (D-41), `health_condition_categories` (D-21), `sport_specific_gear_toggles` (no action). Body parts and equipment items per v2 §4.12.
- **§4.15 discipline_technique_foci (NEW in v4):** Batch B + B-Correction. `source_exercise_ids TEXT[]` + `audit_log TEXT` per D-13.
- **§4.16 sport_name_aliases (NEW in v4):** Batch D v2 schema. UNIQUE shape verification query carried forward as pre-v4-lock action.
- **§4.17 terrain_gap_rules (NEW in v4):** placeholder schema block. Drift report §2.12 says 12 cols; full enumeration requires Neon `\d` dump (D-40).
- **§4.18 supplement_vocabulary (NEW in v4):** placeholder pointing at `Supplement_Vocabulary_Spec.md` as authoritative; reproduce full schema in future FC pass once entries stabilize beyond 25 seed rows.

§5.2 per-consumer function signatures updated for 2C (added `athlete_equipment`, `athlete_gear_toggles`, `athlete_terrain_access` per corrections doc) and 2D (added `current_injuries`, `current_conditions`, `history_injuries`, `history_conditions` per Layer2D_Spec_v1 §3 — replaces unbuildable v3 signature).

§6.6 new process note documents "Code is authoritative; spec catches up" — when deployed schema diverges from spec, deployed wins; spec catches up at next FC pass. Companion to memory rules #9–#12.

§7 open items rewritten to defer to `Project_Backlog_v6` as active tracker. v3 numbered items 1–20 enumerated with current status; new v4 items 21–25 surface the schema-dump cleanups and Batch A/C archive task.

§8 consumer table updated: 2A added sport_discipline_bridge; 2B added terrain_gap_rules; 2C added sport_discipline_bridge + equipment_substitutes_structured; 2D full revision (movement_components, body_parts_at_risk, discipline_substitutes); 2E added supplement_vocabulary; 4 added discipline_technique_foci; 5B added supplement_vocabulary.

§9 future work added D-37 (`injury_flags_text` non-movement signal extraction) and D-38 (12th movement-components token threshold).

### 3.4 `Project_Backlog_v6.md`

Surgical edits to v5:

- **Header → v6** with FC-2 close note.
- **D-39 → ✅ Resolved (FC-2, 2026-05-12).** Pointer to `Vocabulary_Audit_v3.md` outputs.
- **D-40 added (🟢 Cleanup):** `terrain_gap_rules` schema dump needed (action: `\d layer0.terrain_gap_rules`).
- **D-41 added (🟢 Cleanup):** `terrain_types` 7 enrichment cols enumeration needed.
- **D-42 added (🟢 Cleanup):** `cross_sport_properties` deployed-columns reconciliation (Batch D v2 §3 inconsistency vs drift report §2.7).
- **D-43 added (🟢 Cleanup):** Batch A and Batch C patch docs not in project knowledge; archive if recovered.
- **Final cleanup batch section: "Session FC-2: Spec v4 rewrite — ✅ CLOSED 2026-05-12"** with file pointers, item-by-item summary, and tentative FC-3 scope.
- Layer 2 family declared substantively spec-complete through 2D.

### 3.5 `Control_Spec_v2.md`

Surgical edits to v1:

- **Header → v2** with `## What changed in v2 vs v1` section.
- **§9 Doc map:** Layer 0 spec promoted v3→v4 (status: shipped); v3 marked historical; Batch B/B-Correction/D-v1/D-v2 noted as folded; Batch A/C noted as missing-but-reconstructed (D-43). Layer 2D promoted to v1. Vocabulary_Audit_v3 added under both Layer 0 §0C and Layer 1 references. Control_Spec → v2. Project_Backlog → v6 with note about new cleanup items D-40–D-43.

§§1–8 and §§10–11 unchanged from v1.

---

## 4. Session-end verification (rule #10 — completed)

Each claimed file edit was spot-checked against the on-disk file before composing this handoff. Verification queries run via grep:

| File | Critical anchors verified | Status |
|---|---|---|
| `Vocabulary_Audit_v3.md` | v3 header, D-39 closure, Collarbone row in Shoulder, Total: 51 with per-subsection breakdown | ✅ |
| `Layer2D_Spec_v1.md` | v1 header with change log, §5.3.3 set-intersect with movement_components, §5.4 set-intersect with body_parts_at_risk, §5.5 Path B selected, §6 D-22/D-23 ✅ Resolved, §12 2D-1/2D-2/2D-6 ✅ Closed | ✅ |
| `Layer0_ETL_Spec_v4.md` | v4 header, body_parts_at_risk + GIN in §4.3, movement_components + GIN in §4.12, §4.15/§4.16/§4.17/§4.18 new tables, §6.6 process note, §8 consumer corrections, §5.2 corrected 2C/2D signatures | ✅ |
| `Project_Backlog_v6.md` | v6 header, D-39 ✅ Resolved (FC-2), D-40/D-41/D-42/D-43 rows added, "Session FC-2: Spec v4 rewrite — ✅ CLOSED 2026-05-12" section | ✅ |
| `Control_Spec_v2.md` | v2 header with change log, §9 doc map updated to Layer0 v4 / Layer2D v1 / Vocab v3 / Project_Backlog v6 / Control_Spec v2 | ✅ |

No drift between this handoff narrative and committed file state.

---

## 5. Open items carried forward (for next session)

These are tracked in `Project_Backlog_v6` and require either Neon access or future work; no spec edits are deferred from this session with mechanically-applicable instructions, because all such edits depend on schema dumps that aren't available yet.

### Immediate-priority cleanup (next FC pass — ~30 min in Neon + spec str_replace)

| ID | Task | Action |
|---|---|---|
| D-40 | `terrain_gap_rules` schema enumeration | Run `\d layer0.terrain_gap_rules` in Neon dev → enumerate 12 functional columns + UNIQUE → str_replace `Layer0_ETL_Spec_v4` §4.17 placeholder with full schema block |
| D-41 | `terrain_types` 7 enrichment cols enumeration | Run `\d layer0.terrain_types` → enumerate 7 enrichment cols + secondary UNIQUE → str_replace `Layer0_ETL_Spec_v4` §4.14 sub-block |
| D-42 | `cross_sport_properties` reconciliation | Run `\d layer0.cross_sport_properties` → reconcile drift report §2.7 vs Batch D v2 §3 inconsistency → str_replace `Layer0_ETL_Spec_v4` §4.8 if Batch D v2 §3 was actually the deployed shape |
| Pre-v4-lock | `sport_name_aliases` UNIQUE verification | Run the `pg_constraint` query in `Layer0_ETL_Spec_v4` §4.16; confirm or correct |

**Bundle these into a single short Neon-dump session.** Each is a 1-query verification + 1 str_replace edit. Pair with FC-3 kickoff.

### Mid-priority deferred (CC tasks pending v20 ETL re-run)

| ID | Task | Notes |
|---|---|---|
| D-03 | `phase_load_allocation` parser additions | `is_conditional` (Role/Notes markers) + `vertical_gain_notes` (sport-conditional Notes parse). Decisions locked FC-1a. Code change in ETL extractor before v20 re-run. |
| D-07 | `phase_load_weekly_totals` parser fixes | Three modes per FC-1a decisions: multi-sub-format collapse, km→hrs conversion, percentage-cut TAPER derivation. CC task. |
| D-05 | ETL aggregator-row filter code patch | Cleanup SQL already ran; ETL extractor code change pending. Standing rule retirement requires both code patch and one clean ETL run with no regression. |

### Lower-priority / future / cross-layer

D-21, D-24, D-25, D-27, D-28, D-29, D-30, D-31, D-32, D-33, D-34, D-35, D-37, D-38, D-43 — see `Project_Backlog_v6` open items table for details.

---

## 6. Gut check

**What this session got right.**

- All five planned outputs shipped with surgical-edit pattern (copy v(N-1), apply targeted str_replace edits, preserve unchanged sections). Token-efficient vs from-scratch rewrites.
- Session-start and session-end verification (rules #9 and #10) both completed with documented reconciliation.
- v4 made conscious choices where source documents conflicted (Batch D v2 §3 vs drift report §2.7 for cross_sport_properties — drift report taken as authoritative; tracked as D-42 for Neon-side reconciliation).
- New cleanup items (D-40 through D-43) properly cataloged with action verbs, not just narrative.
- The §6.6 process note ("Code is authoritative; spec catches up") formalizes what was already happening informally — turns implicit drift handling into an explicit, documented policy.

**Risks.**

- **v4 §4.17 (terrain_gap_rules) and §4.18 (supplement_vocabulary) shipped as placeholders.** Anyone querying these tables from prompt-side must read Neon directly until D-40 lands. The placeholder pattern is honest about the gap but it means v4 isn't fully consumable from a single document.
- **v4 §4.8 (cross_sport_properties)** took the drift report as authoritative over Batch D v2 §3 — but Batch D v2 was written *after* the drift report. If Batch D v2 §3 was correct about a quietly-deployed schema change, v4 §4.8 is currently wrong. D-42 schema-dump will reveal which.
- **Batch A and Batch C patch documents** are still missing from project knowledge. v4 was reconstructed from drift report instead. If those documents are recovered later and contain decisions not captured in the drift report, v4 may have gaps.
- **§5 query layer** in v4 has only the §5.2 function-signature corrections; the rest of §5 (Architecture, payload shapes, substitution resolution) still reads as v3. Layer 2E spec consumption + a §5 narrative refresh is queued for FC-3.

**What might be missing.**

- A "what's deployed vs spec-only" cheat sheet for engineers — currently scattered across v4 §4 table-by-table and Project_Backlog D-03/D-07 status notes. Could be a §4.0 overview table.
- A version-bump rule for when v4 itself needs revision. Currently inferred from rule #12 (revisions bump numeric suffix) but not stated in v4 itself. Probably fine.

**Best argument against this session's scope.**

All-in was a bigger commitment than necessary. A two-session split (Vocab v3 + Layer2D v1 in session A; ETL v4 + backlog + control in session B) would have given each piece its own dedicated context window and made handoff-on-pause cleaner. Counter-argument: the three are tightly coupled (v4 references Vocab v3 references Layer2D v1 references back to v4), and folding them in one pass meant no risk of inconsistent cross-references between revisions. Andy's call was defensible; the session was long but coherent.

---

## 7. Forward pointers

- **FC-3 tentative scope** (`Project_Backlog_v6` §"Session FC-3 (next): tentative scope"):
  1. Layer 0 schema-dump cleanup pass: D-40 + D-41 + D-42 + sport_name_aliases UNIQUE verification — ~30 min combined
  2. Layer 0 §5 query-layer narrative rewrite (currently v3 verbiage with v4 patches) — pair with Layer 2E spec consumption
  3. Layer 3 design kickoff if Andy's priorities permit
- **Rules in force, unchanged this session:** #9 session-start verification, #10 session-end verification, #11 mechanically-applicable deferred edits, #12 numeric version suffixes.
- **No new memory rules proposed.** §6.6 in v4 codifies "code is authoritative; spec catches up" but that's a project-internal policy, not a session-loop behavior rule.

---

*End of FC-2 closing handoff.*
