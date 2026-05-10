# Layer 0 — Deployed Schema & Drift Report

**Date:** 2026-05-10
**Source data:** `layer0_deployed_state.txt` (introspection run this session)
**Compares against:** `Layer0_ETL_Spec_v3.md` + `Layer0_ETL_Spec_v3_Patch_Batch_B.md` + Batch A items captured in `Batch_A_Done_Batches_BC_Kickoff_Handoff.md`
**Status:** Authoritative reference. Use as source of truth for v20 ETL spec rewrite and any future Layer 0 migration.

---

## TL;DR

- 21 tables in `layer0`. All carry the versioning triple (`etl_version`, `etl_run_at`, `superseded_at`) except where noted.
- Zero foreign keys in the schema — relationships are TEXT-based by design.
- Sanity check passed: no duplicate-active rows in `layer0.exercises`.
- **Open Item R resolved**: `primary_muscles` and `secondary_muscles` are `TEXT[]` (udt `_text`). v20 xlsx keeps them as comma-separated strings; ETL splits on `, `.
- Spec v3 has drift in **6 tables** beyond the already-documented `exercises` drift. Most significant: `terrain_gap_rules` deployed schema is unrecognizable from the spec stub; `phase_load_allocation` has 4 undocumented columns; `phase_load_weekly_totals` has column renames; `disciplines` has many undocumented narrative + numeric columns.

---

## 1. Open Item R — RESOLVED

| Column | Deployed type | udt_name |
|---|---|---|
| `primary_muscles` | ARRAY (TEXT[]) | `_text` |
| `secondary_muscles` | ARRAY (TEXT[]) | `_text` |

ETL transform: xlsx col 5 / col 6 comma-separated strings → `string_to_array(value, ', ')`.

v20 xlsx authoring: keep as comma-separated strings (no change needed). Spec v3 §4.12 schema block doesn't list these columns at all — must be added in v4.

---

## 2. Authoritative deployed schema — all 21 tables

Columns listed in deployed ordinal order. Versioning columns (`etl_version TEXT NOT NULL`, `etl_run_at TIMESTAMPTZ NOT NULL`, `superseded_at TIMESTAMPTZ NULL`) and `id SERIAL PRIMARY KEY` omitted from each table for brevity unless they differ from the standard pattern. Every table below has all four.

### 2.1 `body_parts` — 54 active rows @ `0C-v1.3.1`
- `canonical_name TEXT NOT NULL`
- `body_region TEXT NOT NULL`
- `source_origin TEXT NULL`
- `notes TEXT NULL`
- UNIQUE `(canonical_name, etl_version)`

### 2.2 `cross_sport_properties` — 1 active row @ `0A-v1.3.1`
- `property_id TEXT NOT NULL`
- `property_name TEXT NOT NULL`
- `description TEXT NULL`
- `scope TEXT NULL`
- `ranking_text TEXT NULL`
- `estimated_values TEXT NULL`
- `source_evidence TEXT NULL`
- `notes TEXT NULL`
- `source_text TEXT NULL` ← undocumented in spec
- `confidence TEXT NULL` ← undocumented in spec
- UNIQUE `(property_id, etl_version)`
- **Note:** Only 1 row populated. Either Sheet 8 is barely populated upstream or ETL only loaded one row. Worth a sanity check.

### 2.3 `discipline_pairing` — 325 active rows @ `0A-v1.3.1`
- `discipline_id_a TEXT NOT NULL`
- `discipline_id_b TEXT NOT NULL`
- `pairing_rating TEXT NOT NULL`
- `rationale TEXT NULL`
- `source TEXT NOT NULL`
- UNIQUE `(discipline_id_a, discipline_id_b, etl_version)`
- **Matches spec v3 §4.6 exactly.**

### 2.4 `discipline_substitutes` — 91 active rows @ `0A-v1.3.1`
- `target_id TEXT NOT NULL`
- `target_name TEXT NOT NULL`
- `substitute_id TEXT NOT NULL`
- `substitute_name TEXT NOT NULL`
- `fidelity NUMERIC NOT NULL`
- `constraints TEXT NULL`
- `category TEXT NULL`
- `substitute_covers TEXT[] NULL` ← may not be in spec
- UNIQUE `(target_id, substitute_id, substitute_name, etl_version)`

### 2.5 `discipline_technique_foci` — 35 active rows @ `0B-v19.B`
- `focus_id TEXT NOT NULL`
- `focus_name TEXT NOT NULL`
- `description TEXT NOT NULL`
- `discipline_ids TEXT[] NOT NULL`
- `applicable_session_types TEXT[] NULL`
- `applicable_terrain_ids TEXT[] NULL`
- `required_equipment TEXT[] NULL`
- `required_gear_toggle TEXT NULL`
- `athlete_level TEXT NOT NULL DEFAULT 'any'`
- `priority TEXT NOT NULL`
- `when_to_emphasize TEXT NULL`
- `source_exercise_ids TEXT[] NULL` ← deployed is **array**; Batch B spec drafted as `source_exercise_id TEXT` (singular)
- `audit_log TEXT NULL` ← undocumented in spec
- UNIQUE `(focus_id, etl_version)`
- Indexes: `idx_dtf_active` (partial, etl_version where superseded_at IS NULL), `idx_dtf_disciplines` (GIN on discipline_ids)

### 2.6 `discipline_training_gaps` — 3 active rows @ `0A-v1.3.1`
- `discipline_id TEXT NOT NULL`
- `discipline_name TEXT NOT NULL`
- `gap_type TEXT NOT NULL`
- `notes TEXT NULL`
- `multi_substitute_candidate BOOLEAN NULL`
- UNIQUE `(discipline_id, etl_version)`
- **No schema spec exists.** Referenced only in spec v3 §6.2 run order. Schema needs to be documented in v4.

### 2.7 `disciplines` — 31 active rows @ `0A-v1.3.1`
- `discipline_id TEXT NOT NULL`
- `discipline_name TEXT NOT NULL`
- `discipline_category TEXT NULL`
- `min_base_phase_text TEXT NULL`
- `min_base_phase_weeks_low INTEGER NULL`
- `min_base_phase_weeks_high INTEGER NULL`
- `periodization_text TEXT NULL`
- `ramp_text TEXT NULL`
- `age_adjusted_ramp_text TEXT NULL`
- `age_ramp_40_44_pct NUMERIC NULL`
- `age_ramp_45_54_pct NUMERIC NULL`
- `age_ramp_55_plus_pct NUMERIC NULL`
- `taper_norms_text TEXT NULL`
- `common_injury_patterns TEXT[] NULL`
- `injury_preceding_behaviors TEXT[] NULL`
- `recovery_priority_text TEXT NULL`
- `recovery_modalities TEXT[] NULL`
- `evidence_quality_text TEXT NULL`
- `stimulus_components TEXT[] NULL` ← spec v3 added this late
- UNIQUE `(discipline_id, etl_version)`
- **Many columns undocumented in spec v3.** Spec v3 §4.3 (or wherever disciplines lives) needs a full rewrite.

### 2.8 `equipment_items` — 152 active rows
- `canonical_name TEXT NOT NULL`
- `equipment_category TEXT NOT NULL`
- `is_universal BOOLEAN NOT NULL DEFAULT FALSE`
- `notes TEXT NULL`
- UNIQUE `(canonical_name, etl_version)`
- Version breakdown: `0C-v1.3.1` (121), `0A-v17.K` (11 — K-additions), `0B-v19.K2` (19 — K2 additions), `0C-v2.0-r3` (1 — Bench press rack from Batch A)

### 2.9 `exercises` — 159 active rows / 224 total
- Schema **per Batch B patch §4.12 — confirmed canonical**:
  - `exercise_id TEXT NOT NULL`
  - `exercise_name TEXT NOT NULL`
  - `exercise_type TEXT NOT NULL`
  - `movement_patterns TEXT[] NULL`
  - `primary_muscles TEXT[] NULL` ← TEXT[], confirmed
  - `secondary_muscles TEXT[] NULL` ← TEXT[], confirmed
  - `equipment_required TEXT[] NULL`
  - `injury_flags_text TEXT NULL`
  - `contraindicated_parts TEXT[] NULL`
  - `contraindicated_conditions TEXT[] NULL`
  - `equipment_substitutes JSONB NULL` (legacy, kept as reference)
  - `physical_proxies JSONB NULL`
  - `progression_exercise_id TEXT NULL`
  - `progression_exercise_name TEXT NULL`
  - `regression_exercise_id TEXT NULL`
  - `regression_exercise_name TEXT NULL`
  - `sport_count INTEGER NULL`
  - `coaching_cues TEXT NULL`
  - `terrain_required TEXT[] NULL`
  - `equipment_substitutes_structured JSONB NULL` (source of truth for 2C Tier 2)
- UNIQUE `(exercise_id, etl_version)` — **table-level only**, no column-level UNIQUE
- Active version breakdown: `0B-v1.3.1` (146), `0B-v19.B` (13). Total – Active = 65 = 52 (Batch B drops) + 13 (Batch B retypes, the predecessor rows). Math checks.

### 2.10 `health_condition_categories` — 12 active rows @ `0C-v1.3.1`
- `category_name TEXT NOT NULL`
- `description TEXT NULL`
- UNIQUE `(category_name, etl_version)`

### 2.11 `phase_load_allocation` — 195 active rows @ `0A-v1.3.1`
- `sport_name TEXT NOT NULL`
- `discipline_id TEXT NULL`
- `discipline_name TEXT NOT NULL`
- `role TEXT NOT NULL`
- 8 pct columns (`base_pct_low/high`, `build_pct_low/high`, `peak_pct_low/high`, `taper_pct_low/high`) all `NUMERIC NULL`
- `notes_conditions TEXT NULL`
- `default_inclusion TEXT NULL` ← **undocumented in spec**
- `prescription_note TEXT NULL` ← **undocumented in spec**
- `audit_log TEXT NULL` ← **undocumented in spec**
- `raw_notes TEXT NULL` ← **undocumented in spec**
- UNIQUE `(sport_name, discipline_name, etl_version)`

### 2.12 `phase_load_weekly_totals` — 116 active rows @ `0A-v1.3.1`
- `sport_name TEXT NOT NULL`
- `phase TEXT NOT NULL`
- `weekly_low_hours NUMERIC NULL` ← spec calls this `hours_low`
- `weekly_high_hours NUMERIC NULL` ← spec calls this `hours_high`
- `weekly_target_text TEXT NULL`
- UNIQUE `(sport_name, phase, etl_version)`

### 2.13 `sport_discipline_bridge` — 69 active rows @ `0A-v1.3.1`
- `framework_sport TEXT NOT NULL`
- `discipline_id TEXT NOT NULL`
- `discipline_name TEXT NOT NULL`
- `exercise_db_sport TEXT NOT NULL`
- `role TEXT NOT NULL`
- `default_race_time_pct_low NUMERIC NULL`
- `default_race_time_pct_high NUMERIC NULL`
- UNIQUE `(framework_sport, discipline_id, etl_version)`

### 2.14 `sport_discipline_map` — 70 active rows @ `0A-v1.3.1`
- `sport_name TEXT NOT NULL`
- `discipline_id TEXT NOT NULL`
- `discipline_name TEXT NOT NULL`
- `applicability TEXT NOT NULL`
- `role TEXT NOT NULL`
- `race_time_pct_text TEXT NULL`
- `race_time_pct_low NUMERIC NULL`
- `race_time_pct_high NUMERIC NULL`
- `sport_specific_context TEXT NULL`
- `b2b_pairing_rule_text TEXT NULL`
- `phase_load_text TEXT NULL`
- UNIQUE `(sport_name, discipline_id, etl_version)`
- **Matches spec v3 §4.4.**

### 2.15 `sport_exercise_map` — 903 active rows / 1050 total
- `exercise_id TEXT NOT NULL`
- `exercise_name TEXT NOT NULL`
- `exercise_type TEXT NOT NULL`
- `sport_name TEXT NOT NULL`
- `sport_relevance_note TEXT NOT NULL`
- `priority TEXT NOT NULL`
- UNIQUE `(exercise_id, sport_name, etl_version)`
- Active version breakdown: `0B-v1.3.1` (859), `0B-v19.B` (44). 147 superseded total (=52 Batch B drops × N sport-pairings each + 44 retype predecessor rows).
- **Matches spec v3 §4.13.**

### 2.16 `sport_name_aliases` — 123 active rows @ `0C-v1.3.1`
- `exercise_db_sport TEXT NOT NULL`
- `framework_sport TEXT NOT NULL`
- UNIQUE `(exercise_db_sport, framework_sport, etl_version)`

### 2.17 `sport_specific_gear_toggles` — 11 active rows / 12 total
- `toggle_name TEXT NOT NULL`
- `display_label TEXT NULL`
- `description TEXT NULL`
- `paired_equipment_categories TEXT[] NULL`
- `also_satisfies TEXT[] NULL` ← Batch A addition, confirmed
- UNIQUE `(toggle_name, etl_version)`
- 1 superseded row = Bouldering removal (Batch A).

### 2.18 `sports` — 38 active rows @ `0A-v1.3.1`
- 23 columns per introspection. Matches spec v3 §4.2 with the four NEW classification columns (`constituent_movements`, `endurance_profile`, `participation_format`, `multi_discipline`).
- UNIQUE `(sport_name, etl_version)`

### 2.19 `team_formats` — 26 active rows @ `0A-v1.3.1`
- `sport_name TEXT NOT NULL`
- `formats_available TEXT NULL`
- `team_format_types TEXT NULL`
- `unified_team_description TEXT NULL`
- `relay_specialist_description TEXT NULL`
- `training_implication_unified TEXT NULL`
- `training_implication_relay TEXT NULL`
- `key_distinctions_notes TEXT NULL`
- UNIQUE `(sport_name, etl_version)`

### 2.20 `terrain_gap_rules` — 12 active rows @ `0C-v2.0-r2`
- `target_terrain_id TEXT NOT NULL`
- `target_terrain_name TEXT NOT NULL`
- `proxy_terrain_id TEXT NULL`
- `proxy_terrain_name TEXT NULL`
- `gap_severity TEXT NOT NULL`
- `adaptation_weeks_low INTEGER NULL`
- `adaptation_weeks_high INTEGER NULL`
- `proxy_fidelity NUMERIC NULL`
- `proxy_methods TEXT[] NOT NULL`
- `uncoverable_stimulus TEXT[] NOT NULL`
- `prescription_note TEXT NOT NULL`
- `audit_log TEXT NULL`
- UNIQUE `(target_terrain_id, proxy_terrain_id, etl_version)`
- **Spec v3 §4.10a documents this table with completely different columns** (`terrain_required`, `terrain_available`, `satisfies BOOLEAN`, `substitution_quality`, `notes`). Spec stub is unrecognizable; deployed schema is the real one. Major rewrite needed in v4.

### 2.21 `terrain_types` — 15 active rows / 31 total @ `0C-v1.3.1`
- `canonical_name TEXT NOT NULL`
- `notes TEXT NULL`
- `terrain_id TEXT NULL` ← appears after versioning cols (added later)
- `category TEXT NULL`
- `requires_elevation BOOLEAN NULL`
- `technical_surface BOOLEAN NULL`
- `environment TEXT NULL`
- `simulatable TEXT NULL`
- `simulation_note TEXT NULL`
- UNIQUE `(canonical_name, etl_version)` AND `(terrain_id, etl_version)`
- 16 superseded rows — significant churn. Worth checking what changed if v20 ETL re-runs touch this.

---

## 3. Drift items vs spec v3 — summary table

| Table | Drift severity | What needs to change in spec |
|---|---|---|
| `exercises` | High (already documented in Batch B patch) | Full §4.12 rewrite per `Layer0_ETL_Spec_v3_Patch_Batch_B.md`. Plus: add `primary_muscles` / `secondary_muscles` to schema block with `TEXT[]` type and ETL transform note. |
| `phase_load_allocation` | Medium | Add 4 columns to §4.5: `default_inclusion`, `prescription_note`, `audit_log`, `raw_notes`. |
| `phase_load_weekly_totals` | Low | Rename in §4.5.1: `hours_low` → `weekly_low_hours`, `hours_high` → `weekly_high_hours`. |
| `disciplines` | High | Spec section likely incomplete — many narrative/numeric columns undocumented (`age_ramp_*_pct`, `min_base_phase_weeks_*`, `taper_norms_text`, `recovery_*`, `evidence_quality_text`, etc.). Full audit of §4.3 needed. |
| `terrain_gap_rules` | Very high (full rewrite) | §4.10a schema stub is unrecognizable from deployed. Replace entirely with the 12-column deployed schema. |
| `discipline_training_gaps` | Medium | No spec schema documented. Add a new §4.x with the 5-column schema. |
| `discipline_technique_foci` | Low | `source_exercise_id` (singular) drafted in Batch B patch is actually `source_exercise_ids TEXT[]` (array) deployed. Patch needs correction. Also document `audit_log TEXT` and the two indexes. |
| `discipline_substitutes` | Low | Confirm `substitute_covers TEXT[]` column is in spec; if not, add. |
| `cross_sport_properties` | Low | Confirm `source_text` and `confidence` columns are documented; if not, add. Also flag that only 1 row exists — is upstream sheet sparse, or did ETL only load one row? |
| `sports`, `sport_discipline_map`, `sport_discipline_bridge`, `discipline_pairing`, `body_parts`, `equipment_items`, `health_condition_categories`, `sport_name_aliases`, `team_formats`, `sport_exercise_map`, `terrain_types`, `sport_specific_gear_toggles` | None / matches spec or already documented | No action. |

---

## 4. Things to verify before v20 ETL re-run

1. **`cross_sport_properties` row count.** Only 1 active row. Source-sheet inspection: is Sheet 8 nearly empty, or is the ETL extractor undercounting? If undercounting, fix before v20.
2. **`terrain_types` churn.** 16 superseded rows. What changed? If it's a stable churn, fine. If unintended drift, surface in v20 prep.
3. **`phase_load_allocation` extra columns.** `default_inclusion`, `prescription_note`, `audit_log`, `raw_notes` — confirm xlsx Sheet 5 actually has these columns and that the ETL populate scripts produce them.
4. **`disciplines` extra columns.** Confirm xlsx Sheet 2 columns mapping. The age_ramp_*_pct numerics probably need the parser to find them in `age_adjusted_ramp_text`.
5. **`terrain_gap_rules` real source.** The deployed schema looks hand-curated (per the `populate_terrain_gap_rules.sql` file in project). Confirm it's curated SQL, not xlsx-derived — otherwise v20 ETL re-run might wipe it.
6. **`discipline_technique_foci`.** Same — hand-curated (Batch B). v20 ETL re-run must NOT touch this table. Document that explicitly.
7. **`equipment_items` mixed-version state.** 4 different etl_versions are all active. Spec v3 §6.3 says "Set `superseded_at = NOW()` on all prior rows where `superseded_at IS NULL` AND `etl_version` is the prior version of the same source family." The K and K2 additions appear to have been adds-without-supersedes (correct behavior for additive vocab patches). Confirm v20 ETL won't accidentally supersede them.

---

## 5. v20 ETL spec rewrite — implications

`Layer0_ETL_Spec_v3.md` needs a substantial rewrite to be useful for v20. Recommended sequence:

1. **Bulk imports** — pull `Layer0_ETL_Spec_v3_Patch_Batch_B.md` schema block for §4.12; document Batches A and C as completed; resolve Open Items I (this report), K (already resolved), and R (this report).
2. **Section-by-section deployed-schema sync** — for each table in §4, replace any drifted schema block with the deployed schema (cross-reference §2 above).
3. **ETL transform notes** — re-validate the transform notes (e.g., `string_to_array(value, ', ')` for muscle columns, the contraindicated-string splitter) against current code. Where code doesn't exist or differs, mark TBD.
4. **§8 consumer table** — apply all batched corrections from `ETL_Spec_v3_Corrections_2ABC_v2.md` plus Batch B patch.
5. **§6.2 run order** — confirm or revise based on deployed state.

This is its own batch. Not in scope for this session.

---

## 6. Operational recommendations

- **Pre-flight introspection is mandatory** for any future Layer 0 migration touching a table by column name. Pattern from `update_retype_keeper_exercises.sql` v2 is canonical. The Batch C migration in this session also uses it.
- **The drift sweep script (`spec_drift_sweep_introspection.sql`) is the reference dump tool.** Keep it in project; run before any spec rewrite or major migration.
- **No FKs anywhere.** Be careful when superseding rows — nothing prevents orphaned references in other tables. The `update_retype_keeper_exercises.sql` pattern of also touching `sport_exercise_map` is the right model when denormalized data exists.

---

## 7. Gut check

**What this report gets right:** Authoritative deployed-state reference. Every drift item surfaced. Open Item R resolved.

**What it might be missing:**
- Column comments / table comments. Not dumped by the introspection. If you've been using `COMMENT ON COLUMN` for docs, those would be additional drift signal.
- Trigger / function definitions. The schema has zero FKs, but there may be triggers enforcing data shape (e.g., on JSONB structure for `equipment_substitutes`). Not dumped.
- Sequence ownership / restart values. Not relevant for spec drift but matters for any backup/restore.

**Best argument against doing the v20 xlsx rebuild before the spec rewrite:** the spec is the contract. Building v20 against a stale spec creates a third drift surface (xlsx ↔ spec ↔ DB). Better order: spec rewrite first (informed by this report), then v20 xlsx, then ETL re-run. Andy may push back here — the drift frustration is real and the spec rewrite is its own multi-hour job. Practical compromise: spec rewrite goes in parallel with v20 xlsx authoring, and the xlsx structure is locked against deployed state (per §2 above) rather than spec.
