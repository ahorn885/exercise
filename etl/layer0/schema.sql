-- Layer 0 ETL — schema definition
--
-- Idempotent: re-running is a no-op. Every table lives in the `layer0`
-- schema, isolated from the existing app's `public` schema.
--
-- Spec: etl/sources/Layer0_ETL_Spec_v3.md §4

CREATE SCHEMA IF NOT EXISTS layer0;

----------------------------------------------------------------------
-- PHASE 1 — Vocabularies (§4.12)
----------------------------------------------------------------------

CREATE TABLE IF NOT EXISTS layer0.body_parts (
  id              SERIAL PRIMARY KEY,
  canonical_name  TEXT NOT NULL,
  body_region     TEXT NOT NULL,
  source_origin   TEXT,
  notes           TEXT,
  etl_version     TEXT NOT NULL,
  etl_run_at      TIMESTAMPTZ NOT NULL,
  superseded_at   TIMESTAMPTZ,
  UNIQUE (canonical_name, etl_version)
);

CREATE TABLE IF NOT EXISTS layer0.health_condition_categories (
  id              SERIAL PRIMARY KEY,
  category_name   TEXT NOT NULL,
  description     TEXT,
  etl_version     TEXT NOT NULL,
  etl_run_at      TIMESTAMPTZ NOT NULL,
  superseded_at   TIMESTAMPTZ,
  UNIQUE (category_name, etl_version)
);

CREATE TABLE IF NOT EXISTS layer0.equipment_items (
  id                 SERIAL PRIMARY KEY,
  canonical_name     TEXT NOT NULL,
  equipment_category TEXT NOT NULL,
  is_universal       BOOLEAN NOT NULL DEFAULT FALSE,
  notes              TEXT,
  etl_version        TEXT NOT NULL,
  etl_run_at         TIMESTAMPTZ NOT NULL,
  superseded_at      TIMESTAMPTZ,
  UNIQUE (canonical_name, etl_version)
);

CREATE TABLE IF NOT EXISTS layer0.terrain_types (
  id              SERIAL PRIMARY KEY,
  canonical_name  TEXT NOT NULL,
  notes           TEXT,
  etl_version     TEXT NOT NULL,
  etl_run_at      TIMESTAMPTZ NOT NULL,
  superseded_at   TIMESTAMPTZ,
  UNIQUE (canonical_name, etl_version)
);

CREATE TABLE IF NOT EXISTS layer0.sport_specific_gear_toggles (
  id                          SERIAL PRIMARY KEY,
  toggle_name                 TEXT NOT NULL,
  display_label               TEXT,
  description                 TEXT,
  paired_equipment_categories TEXT[],
  -- D-73 Phase 2.4-Prep: Layer 2C §5.1 transitive-implication chains.
  -- Single known case: 'Climbing — roped' also_satisfies 'Rappelling /
  -- abseiling' per Vocabulary_Audit_v2.md §4.2 note 1. No transitive
  -- cascade beyond one hop (Layer2C_Spec.md §6).
  also_satisfies              TEXT[],
  -- D-73 Phase 2.4-Prep: Layer 2C §8.3 toggle-OFF-for-discipline flag.
  -- Reverse mapping of disciplines whose exercise pool depends on this
  -- toggle being ON. Andy 2026-05-19 picked (b) structured-column over
  -- (a) hard-coded mapping. Empty for non-gating toggles.
  gated_discipline_ids        TEXT[],
  etl_version                 TEXT NOT NULL,
  etl_run_at                  TIMESTAMPTZ NOT NULL,
  superseded_at               TIMESTAMPTZ,
  UNIQUE (toggle_name, etl_version)
);

----------------------------------------------------------------------
-- PHASE 2 — Sports framework core (§4.2–§4.8)
----------------------------------------------------------------------

CREATE TABLE IF NOT EXISTS layer0.sports (
  id                          SERIAL PRIMARY KEY,
  sport_name                  TEXT NOT NULL,
  typical_duration_range      TEXT,
  team_vs_solo                TEXT,
  flag_navigation             BOOLEAN NOT NULL,
  navigation_notes            TEXT,
  flag_sleep_deprivation      BOOLEAN NOT NULL,
  sleep_deprivation_notes     TEXT,
  flag_pack_carry             BOOLEAN NOT NULL,
  pack_carry_notes            TEXT,
  pack_weight_lbs_low         NUMERIC,
  pack_weight_lbs_high        NUMERIC,
  flag_transition_training    BOOLEAN NOT NULL,
  transition_training_notes   TEXT,
  primary_discipline_count    INTEGER,
  secondary_discipline_count  INTEGER,
  status_label                TEXT,
  etl_version                 TEXT NOT NULL,
  etl_run_at                  TIMESTAMPTZ NOT NULL,
  superseded_at               TIMESTAMPTZ,
  UNIQUE (sport_name, etl_version)
);

CREATE TABLE IF NOT EXISTS layer0.disciplines (
  id                          SERIAL PRIMARY KEY,
  discipline_id               TEXT NOT NULL,
  discipline_name             TEXT NOT NULL,
  discipline_category         TEXT,
  min_base_phase_text         TEXT,
  min_base_phase_weeks_low    INTEGER,
  min_base_phase_weeks_high   INTEGER,
  periodization_text          TEXT,
  ramp_text                   TEXT,
  age_adjusted_ramp_text      TEXT,
  age_ramp_40_44_pct          NUMERIC,
  age_ramp_45_54_pct          NUMERIC,
  age_ramp_55_plus_pct        NUMERIC,
  taper_norms_text            TEXT,
  common_injury_patterns      TEXT[],
  injury_preceding_behaviors  TEXT[],
  recovery_priority_text      TEXT,
  recovery_modalities         TEXT[],
  evidence_quality_text       TEXT,
  etl_version                 TEXT NOT NULL,
  etl_run_at                  TIMESTAMPTZ NOT NULL,
  superseded_at               TIMESTAMPTZ,
  UNIQUE (discipline_id, etl_version)
);

CREATE TABLE IF NOT EXISTS layer0.sport_discipline_map (
  id                      SERIAL PRIMARY KEY,
  sport_name              TEXT NOT NULL,
  discipline_id           TEXT NOT NULL,
  discipline_name         TEXT NOT NULL,
  applicability           TEXT NOT NULL,
  role                    TEXT NOT NULL,
  race_time_pct_text      TEXT,
  race_time_pct_low       NUMERIC,
  race_time_pct_high      NUMERIC,
  sport_specific_context  TEXT,
  b2b_pairing_rule_text   TEXT,
  phase_load_text         TEXT,
  etl_version             TEXT NOT NULL,
  etl_run_at              TIMESTAMPTZ NOT NULL,
  superseded_at           TIMESTAMPTZ,
  UNIQUE (sport_name, discipline_id, etl_version)
);

CREATE TABLE IF NOT EXISTS layer0.discipline_pairing (
  id                  SERIAL PRIMARY KEY,
  discipline_id_a     TEXT NOT NULL,
  discipline_id_b     TEXT NOT NULL,
  pairing_rating      TEXT NOT NULL,
  rationale           TEXT,
  source              TEXT NOT NULL,
  etl_version         TEXT NOT NULL,
  etl_run_at          TIMESTAMPTZ NOT NULL,
  superseded_at       TIMESTAMPTZ,
  UNIQUE (discipline_id_a, discipline_id_b, etl_version)
);

CREATE TABLE IF NOT EXISTS layer0.phase_load_allocation (
  id                  SERIAL PRIMARY KEY,
  sport_name          TEXT NOT NULL,
  discipline_id       TEXT,
  discipline_name     TEXT NOT NULL,
  role                TEXT NOT NULL,
  base_pct_low        NUMERIC,
  base_pct_high       NUMERIC,
  build_pct_low       NUMERIC,
  build_pct_high      NUMERIC,
  peak_pct_low        NUMERIC,
  peak_pct_high       NUMERIC,
  taper_pct_low       NUMERIC,
  taper_pct_high      NUMERIC,
  notes_conditions    TEXT,
  etl_version         TEXT NOT NULL,
  etl_run_at          TIMESTAMPTZ NOT NULL,
  superseded_at       TIMESTAMPTZ,
  UNIQUE (sport_name, discipline_name, etl_version)
);

CREATE TABLE IF NOT EXISTS layer0.team_formats (
  id                              SERIAL PRIMARY KEY,
  sport_name                      TEXT NOT NULL,
  formats_available               TEXT,
  team_format_types               TEXT,
  unified_team_description        TEXT,
  relay_specialist_description    TEXT,
  training_implication_unified    TEXT,
  training_implication_relay      TEXT,
  key_distinctions_notes          TEXT,
  etl_version                     TEXT NOT NULL,
  etl_run_at                      TIMESTAMPTZ NOT NULL,
  superseded_at                   TIMESTAMPTZ,
  UNIQUE (sport_name, etl_version)
);

CREATE TABLE IF NOT EXISTS layer0.cross_sport_properties (
  id                  SERIAL PRIMARY KEY,
  property_id         TEXT NOT NULL,
  property_name       TEXT NOT NULL,
  description         TEXT,
  scope               TEXT,
  ranking_text        TEXT,
  estimated_values    TEXT,
  source_evidence     TEXT,
  notes               TEXT,
  etl_version         TEXT NOT NULL,
  etl_run_at          TIMESTAMPTZ NOT NULL,
  superseded_at       TIMESTAMPTZ,
  UNIQUE (property_id, etl_version)
);

----------------------------------------------------------------------
-- PHASE 3 — Bridge + exercise DB (§4.9–§4.11)
----------------------------------------------------------------------

CREATE TABLE IF NOT EXISTS layer0.sport_discipline_bridge (
  id                          SERIAL PRIMARY KEY,
  framework_sport             TEXT NOT NULL,
  discipline_id               TEXT NOT NULL,
  discipline_name             TEXT NOT NULL,
  exercise_db_sport           TEXT NOT NULL,
  role                        TEXT NOT NULL,
  default_race_time_pct_low   NUMERIC,
  default_race_time_pct_high  NUMERIC,
  etl_version                 TEXT NOT NULL,
  etl_run_at                  TIMESTAMPTZ NOT NULL,
  superseded_at               TIMESTAMPTZ,
  UNIQUE (framework_sport, discipline_id, etl_version)
);

CREATE TABLE IF NOT EXISTS layer0.exercises (
  id                          SERIAL PRIMARY KEY,
  exercise_id                 TEXT NOT NULL,
  exercise_name               TEXT NOT NULL,
  exercise_type               TEXT NOT NULL,
  movement_patterns           TEXT[],
  primary_muscles             TEXT[],
  secondary_muscles           TEXT[],
  equipment_required          TEXT[],
  -- D-73 Phase 2.4-Prep: terrain tokens routed from col 7 via
  -- vocabulary_transforms.transform_equipment_string per
  -- migrate_exercises_terrain_required.sql. Layer 2C annotates each
  -- ResolvedExercise with this list; Layer 4 cross-references with 2B
  -- terrain gap output (Layer2C_Spec.md §5.2 pass-through, §7).
  terrain_required            TEXT[],
  injury_flags_text           TEXT,
  contraindicated_parts       TEXT[],
  contraindicated_conditions  TEXT[],
  equipment_substitutes       JSONB,
  -- D-73 Phase 2.4-Prep: CNF-structured substitutes per
  -- migrate_exercises_substitutes_structured.sql. Shape: [{substitute_text,
  -- equipment_required: [[a,b],[c]], is_improvised}]. Layer 2C §5.4 Tier 2
  -- resolution reads this column; legacy `equipment_substitutes` stays as
  -- reference data per Batch C decision.
  equipment_substitutes_structured JSONB,
  physical_proxies            JSONB,
  progression_exercise_id     TEXT,
  progression_exercise_name   TEXT,
  regression_exercise_id      TEXT,
  regression_exercise_name    TEXT,
  sport_count                 INTEGER,
  coaching_cues               TEXT,
  etl_version                 TEXT NOT NULL,
  etl_run_at                  TIMESTAMPTZ NOT NULL,
  superseded_at               TIMESTAMPTZ,
  UNIQUE (exercise_id, etl_version)
);

CREATE TABLE IF NOT EXISTS layer0.sport_exercise_map (
  id                  SERIAL PRIMARY KEY,
  exercise_id         TEXT NOT NULL,
  exercise_name       TEXT NOT NULL,
  exercise_type       TEXT NOT NULL,
  sport_name          TEXT NOT NULL,
  sport_relevance_note TEXT NOT NULL,
  priority            TEXT NOT NULL,
  etl_version         TEXT NOT NULL,
  etl_run_at          TIMESTAMPTZ NOT NULL,
  superseded_at       TIMESTAMPTZ,
  UNIQUE (exercise_id, sport_name, etl_version)
);

----------------------------------------------------------------------
-- Sport name alias map (Open Item #5 resolution)
----------------------------------------------------------------------

CREATE TABLE IF NOT EXISTS layer0.sport_name_aliases (
  id                SERIAL PRIMARY KEY,
  exercise_db_sport TEXT NOT NULL,
  framework_sport   TEXT NOT NULL,
  etl_version       TEXT NOT NULL,
  etl_run_at        TIMESTAMPTZ NOT NULL,
  superseded_at     TIMESTAMPTZ,
  UNIQUE (exercise_db_sport, framework_sport, etl_version)
);

----------------------------------------------------------------------
-- v10 — new tables (Layer0 ETL Spec v3 §4.13–§4.15)
----------------------------------------------------------------------

CREATE TABLE IF NOT EXISTS layer0.discipline_substitutes (
  id                  SERIAL PRIMARY KEY,
  target_id           TEXT NOT NULL,
  target_name         TEXT NOT NULL,
  substitute_id       TEXT NOT NULL,
  substitute_name     TEXT NOT NULL,
  fidelity            NUMERIC NOT NULL,
  constraints         TEXT,
  category            TEXT,
  substitute_covers   TEXT[],
  etl_version         TEXT NOT NULL,
  etl_run_at          TIMESTAMPTZ NOT NULL,
  superseded_at       TIMESTAMPTZ,
  UNIQUE (target_id, substitute_id, substitute_name, etl_version)
);

CREATE TABLE IF NOT EXISTS layer0.discipline_training_gaps (
  id                          SERIAL PRIMARY KEY,
  discipline_id               TEXT NOT NULL,
  discipline_name             TEXT NOT NULL,
  gap_type                    TEXT NOT NULL,
  notes                       TEXT,
  multi_substitute_candidate  BOOLEAN,
  etl_version                 TEXT NOT NULL,
  etl_run_at                  TIMESTAMPTZ NOT NULL,
  superseded_at               TIMESTAMPTZ,
  UNIQUE (discipline_id, etl_version)
);

CREATE TABLE IF NOT EXISTS layer0.phase_load_weekly_totals (
  id                  SERIAL PRIMARY KEY,
  sport_name          TEXT NOT NULL,
  phase               TEXT NOT NULL,
  weekly_low_hours    NUMERIC,
  weekly_high_hours   NUMERIC,
  weekly_target_text  TEXT,
  etl_version         TEXT NOT NULL,
  etl_run_at          TIMESTAMPTZ NOT NULL,
  superseded_at       TIMESTAMPTZ,
  UNIQUE (sport_name, phase, etl_version)
);

----------------------------------------------------------------------
-- Additive column migrations (idempotent)
----------------------------------------------------------------------

ALTER TABLE layer0.exercises
  ADD COLUMN IF NOT EXISTS contraindicated_conditions TEXT[];

-- v10: Sports Index gained four classification columns
ALTER TABLE layer0.sports
  ADD COLUMN IF NOT EXISTS constituent_movements TEXT[];
ALTER TABLE layer0.sports
  ADD COLUMN IF NOT EXISTS endurance_profile TEXT;
ALTER TABLE layer0.sports
  ADD COLUMN IF NOT EXISTS participation_format TEXT;
ALTER TABLE layer0.sports
  ADD COLUMN IF NOT EXISTS multi_discipline BOOLEAN;

-- v10: Discipline Library gained one nullable column (data populated later)
ALTER TABLE layer0.disciplines
  ADD COLUMN IF NOT EXISTS stimulus_components TEXT[];

-- v10: Phase Load Allocation gained a default_inclusion column and the
-- Notes column is now split into prescription_note + audit_log + raw_notes
ALTER TABLE layer0.phase_load_allocation
  ADD COLUMN IF NOT EXISTS default_inclusion TEXT;
ALTER TABLE layer0.phase_load_allocation
  ADD COLUMN IF NOT EXISTS prescription_note TEXT;
ALTER TABLE layer0.phase_load_allocation
  ADD COLUMN IF NOT EXISTS audit_log TEXT;
ALTER TABLE layer0.phase_load_allocation
  ADD COLUMN IF NOT EXISTS raw_notes TEXT;

-- v10: Cross-Sport Properties — three new columns
-- (notes already exists in the base CREATE; ADD COLUMN IF NOT EXISTS is a no-op)
ALTER TABLE layer0.cross_sport_properties
  ADD COLUMN IF NOT EXISTS source_text TEXT;
ALTER TABLE layer0.cross_sport_properties
  ADD COLUMN IF NOT EXISTS confidence TEXT;
ALTER TABLE layer0.cross_sport_properties
  ADD COLUMN IF NOT EXISTS notes TEXT;

-- Open-water marathon swimming weekly targets are expressed in km/wk, not
-- hours. `weekly_unit` disambiguates the numeric range in
-- `weekly_low_hours` / `weekly_high_hours` (column names are legacy; the
-- values are in the declared unit). NULL means "hrs" for back-compat with
-- pre-migration rows.
ALTER TABLE layer0.phase_load_weekly_totals
  ADD COLUMN IF NOT EXISTS weekly_unit TEXT;
