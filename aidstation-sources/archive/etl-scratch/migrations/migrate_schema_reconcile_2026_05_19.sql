-- ============================================================
-- Layer0 schema reconcile — draft
-- Generated 2026-05-19 by _drift_check.py
-- Compares etl/layer0/schema.sql against live layer0.* in Neon
-- REVIEW BEFORE APPLYING — renames are heuristic suggestions only
-- ============================================================

BEGIN;

-- Tables in DB but not in schema.sql (legacy — left alone):
--   layer0.discipline_technique_foci
--   layer0.supplement_vocabulary
--   layer0.terrain_gap_rules

-- -----------------------------------------------------------
-- layer0.disciplines
-- -----------------------------------------------------------
-- DB-only columns (no canonical match — review whether to drop):
--   body_parts_at_risk ARRAY

-- -----------------------------------------------------------
-- layer0.exercises
-- -----------------------------------------------------------
-- DB-only columns (no canonical match — review whether to drop):
--   movement_components ARRAY

-- -----------------------------------------------------------
-- layer0.phase_load_weekly_totals
-- -----------------------------------------------------------
-- Suggested RENAMEs (heuristic: matched by type, single candidate):
--   hours_low (NUMERIC) -> weekly_low_hours
ALTER TABLE layer0.phase_load_weekly_totals RENAME COLUMN hours_low TO weekly_low_hours;
--   hours_high (NUMERIC) -> weekly_high_hours
ALTER TABLE layer0.phase_load_weekly_totals RENAME COLUMN hours_high TO weekly_high_hours;

-- -----------------------------------------------------------
-- layer0.terrain_types
-- -----------------------------------------------------------
-- DB-only columns (no canonical match — review whether to drop):
--   terrain_id TEXT
--   category TEXT
--   requires_elevation BOOLEAN
--   technical_surface BOOLEAN
--   environment TEXT
--   simulatable TEXT
--   simulation_note TEXT

COMMIT;
