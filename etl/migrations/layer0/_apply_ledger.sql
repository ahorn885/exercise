-- _apply_ledger.sql — apply-tracking ledger for the layer0-apply workflow.
--
-- WHY: layer0-apply previously re-applied the ENTIRE etl/migrations/layer0/*.sql
-- chain on every run. The data UPDATEs are idempotent, but each migration's
-- atomic verify-block asserts the state right after ITSELF — which a later
-- migration legitimately moves on:
--   * 0008 pins EX150/EX153 keeping survivor tokens, but 0009 supersedes them
--     (the snowshoe cull) -> 0008 re-run fails "expected 4 survivors, found 2".
--   * 0009 pins EX176 at 0B-v1.6.10, but 0010 re-versions it to 0B-v1.6.11
--     (stripping a phantom regression) -> 0009 re-run would fail next.
-- So re-running a migration against a prod that already has the LATER migrations
-- falsely fails. The CI layer0-gate never sees this because it applies the chain
-- in-order from a clean baseline (each verify runs before the migration that
-- invalidates it).
--
-- FIX: a ledger so layer0-apply applies each migration exactly once, ever
-- (mirroring how the public-schema _PG_MIGRATIONS runner already works). A
-- verify-block then only ever runs in-order, right after its own migration.
--
-- This file is a BOOTSTRAP, not a migration: the apply workflow runs it first
-- (every run, idempotent), then loops the numbered [0-9]*.sql migrations,
-- skipping any already in the ledger and recording each one it applies. The
-- CI layer0-gate globs [0-9]*.sql, so it never runs this file.
--
-- Idempotent: CREATE ... IF NOT EXISTS + ON CONFLICT DO NOTHING.
--
-- NOTE: a future `layer0-redump` would capture layer0._applied_migrations in the
-- baseline dump; whoever re-dumps adds it to _FAMILY_MAP_EXCEPTIONS (same as
-- supplement_vocabulary / discipline_technique_foci) since it is apply-infra, not
-- versioned reference data.

CREATE TABLE IF NOT EXISTS layer0._applied_migrations (
  filename    text PRIMARY KEY,
  applied_at  timestamptz NOT NULL DEFAULT now()
);

-- One-time history seed: these migrations were applied to prod BEFORE the ledger
-- existed (each verified live in its own session — see the #616/#622/#623/#644
-- handoffs). Mark them applied so the apply loop never re-runs them. Migrations
-- newer than this (0010+) are recorded by the loop as it applies them.
INSERT INTO layer0._applied_migrations (filename) VALUES
  ('0006_populate_disciplines_primary_movement.sql'),
  ('0007_retire_vessel_equipment_add_crafts.sql'),
  ('0008_retire_assumed_gear.sql'),
  ('0009_cull_nontrainable_technical_skill.sql')
ON CONFLICT (filename) DO NOTHING;

-- End of _apply_ledger.sql
