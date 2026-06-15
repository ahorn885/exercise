-- run_owed_layer0_migrations.sql — single ordered runner for the owed
-- Layer 0 (etl/sources) deploys, so they can be applied in ONE Neon psql
-- session instead of pasting each file by hand.
--
-- Generated 2026-05-25 (FormRefresh A1 session). Owed set is sourced from
-- CURRENT_STATE.md "Open next moves":
--   - (primary_movement MOVED 2026-06-15 to the migrations pipeline —
--      etl/migrations/layer0/0006_populate_disciplines_primary_movement.sql.
--      The old one-shot migrate_disciplines_add_primary_movement_v1.sql was
--      stale (pre-drift D-001..D-029 keyspace) and is retired; 0006 backfills
--      the current canon and is gated in CI. See the genesis/#604 follow-up.)
--   - (K3 equipment additions REMOVED 2026-06-15 — those items are unwanted;
--      climbing gear lives in sport_specific_gear_toggles. See closed #613.)
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

\echo '=== [1/3] D-74 — layer0.terrain_gap_rules (idempotency re-run; etl/sources copy) ==='
\ir populate_terrain_gap_rules.sql

\echo '=== [2/3] D-74 — layer0.skill_capability_toggles (idempotency re-run) ==='
\ir populate_skill_capability_toggles.sql

\echo '=== [3/3] D-74 — layer0.discipline_technique_foci (idempotency re-run) ==='
\ir populate_discipline_technique_foci.sql

\echo '=== owed layer0 migrations complete ==='
