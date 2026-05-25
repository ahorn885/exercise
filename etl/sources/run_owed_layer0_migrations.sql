-- run_owed_layer0_migrations.sql — single ordered runner for the owed
-- Layer 0 (etl/sources) deploys, so they can be applied in ONE Neon psql
-- session instead of pasting each file by hand.
--
-- Generated 2026-05-25 (FormRefresh A1 session). Owed set is sourced from
-- CURRENT_STATE.md "Open next moves":
--   - PR #156  migrate_disciplines_add_primary_movement_v1.sql  (HARD prereq —
--              Layer 2A SELECTs layer0.disciplines.primary_movement)
--   - K3       populate_equipment_items_K3_additions.sql        (additive)
--   - D-74     populate_terrain_gap_rules.sql / _skill_capability_toggles.sql /
--              _discipline_technique_foci.sql                    (idempotency
--              re-runs; Neon already has the correct rows from the R6 deploy —
--              these are hygiene no-ops, included so the stack is one command)
--
-- NOT a substitute for `python init_db.py` — that runs the public-schema
-- migrations (_PG_MIGRATIONS, incl. the FormRefresh A1 race_events changes)
-- via a different channel. This runner is layer0 reference data only.
--
-- Ordering: schema change (migrate_*) before data (populate_*). The included
-- scripts are individually idempotent (ADD COLUMN IF NOT EXISTS /
-- DELETE-by-version / ON CONFLICT DO NOTHING) and each manages its own
-- transaction, so this runner does NOT open a global transaction; ON_ERROR_STOP
-- halts the batch on the first failure instead of limping forward.
--
-- D-76 footgun (deliberate): terrain_gap_rules is pulled from THIS directory
-- (etl/sources/, the live 16-row copy), NOT from aidstation-sources/migrations/
-- (the stale, divergent 12-row copy that shares the same etl_version and would
-- wipe live rows). Do not repoint the \ir below at the migrations/ copy.
--
-- Run from anywhere: `psql "$DATABASE_URL" -f etl/sources/run_owed_layer0_migrations.sql`
-- (\ir resolves each include relative to THIS file's directory, not the CWD.)

\set ON_ERROR_STOP on

\echo '=== [1/5] PR #156 — layer0.disciplines.primary_movement (schema; HARD prereq) ==='
\ir migrate_disciplines_add_primary_movement_v1.sql

\echo '=== [2/5] K3 — layer0.equipment_items additions (additive) ==='
\ir populate_equipment_items_K3_additions.sql

\echo '=== [3/5] D-74 — layer0.terrain_gap_rules (idempotency re-run; etl/sources copy) ==='
\ir populate_terrain_gap_rules.sql

\echo '=== [4/5] D-74 — layer0.skill_capability_toggles (idempotency re-run) ==='
\ir populate_skill_capability_toggles.sql

\echo '=== [5/5] D-74 — layer0.discipline_technique_foci (idempotency re-run) ==='
\ir populate_discipline_technique_foci.sql

\echo '=== owed layer0 migrations complete ==='
