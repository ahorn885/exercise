-- migrate_discipline_technique_foci.sql
-- Creates layer0.discipline_technique_foci, the table that holds technique-only
-- training foci migrated out of the exercises table.
--
-- Source decisions (Batch B, sweep over all 65 v19 exercises with
--   exercise_type = 'Technical / Skill'):
--   - 52 dropped from exercises → migrated as foci here
--   - 13 retyped to load-bearing exercise_types and kept in exercises
--   - 35 focus rows result (collapsed multi-cue where the cue cluster is
--     applied as a single coaching emphasis in a session)
--
-- Why a separate table: technique foci are not training stimuli on their own.
-- They overlay on existing sessions ("during this paddle session, focus on
-- forward-stroke technique"). Keeping them in `exercises` confused selection
-- in Layer 4 — they have no measurable load, no progression curve, no
-- equipment substitutability story. Splitting them out makes both tables
-- easier to reason about.
--
-- Selection model (read by Layer 4, not encoded here):
--   filter foci where:
--     session.discipline ∈ discipline_ids
--     AND (applicable_session_types  IS NULL OR session.type    ∈ list)
--     AND (applicable_terrain_ids   IS NULL OR session.terrain ∈ list)
--     AND (required_equipment       IS NULL OR required_equipment       ⊆ session.locale.equipment)
--     AND (required_gear_toggle     IS NULL OR athlete.toggles[gate]   = TRUE)
--     AND athlete.level ∈ (focus.athlete_level, 'any')
--   pick top 0–2 by priority, rotating across plan-week.
--
-- etl_version: '0B-v19.B' (Batch B against v19 exercise DB)
-- Safe to re-run: CREATE TABLE IF NOT EXISTS guards schema; UNIQUE constraint
-- prevents duplicate inserts at the same etl_version.

BEGIN;

-- ── 1. Create table ────────────────────────────────────────────────────────

CREATE TABLE IF NOT EXISTS layer0.discipline_technique_foci (
  id                          SERIAL      PRIMARY KEY,

  focus_id                    TEXT        NOT NULL,
  focus_name                  TEXT        NOT NULL,
  description                 TEXT        NOT NULL,

  -- Selection criteria — Layer 4 filters foci by these
  discipline_ids              TEXT[]      NOT NULL,                    -- e.g. {'D-009','D-010'}
  applicable_session_types    TEXT[],                                  -- NULL = all session types
  applicable_terrain_ids      TEXT[],                                  -- NULL = all terrains for the discipline
  required_equipment          TEXT[],                                  -- canonical_name in equipment_items; NULL = none beyond what discipline implies
  required_gear_toggle        TEXT,                                    -- canonical_name in sport_specific_gear_toggles

  -- Coaching metadata
  athlete_level               TEXT        NOT NULL DEFAULT 'any',      -- 'beginner'|'intermediate'|'advanced'|'any'
  priority                    TEXT        NOT NULL,                    -- 'Critical'|'Standard'|'Optional'
  when_to_emphasize           TEXT,                                    -- prose: when in plan / under what conditions
  source_exercise_ids         TEXT[],                                  -- traceability to v19 exercises this replaces

  audit_log                   TEXT,                                    -- decisions, gaps, citations

  -- Versioning
  etl_version                 TEXT        NOT NULL,
  etl_run_at                  TIMESTAMPTZ NOT NULL,
  superseded_at               TIMESTAMPTZ,

  UNIQUE (focus_id, etl_version)
);

-- Indexes for the access patterns Layer 4 uses

CREATE INDEX IF NOT EXISTS idx_dtf_disciplines
  ON layer0.discipline_technique_foci USING GIN (discipline_ids);

CREATE INDEX IF NOT EXISTS idx_dtf_active
  ON layer0.discipline_technique_foci (etl_version)
  WHERE superseded_at IS NULL;

-- ── 2. Verify ──────────────────────────────────────────────────────────────

DO $$
DECLARE
  table_exists BOOLEAN;
BEGIN
  SELECT EXISTS (
    SELECT 1 FROM information_schema.tables
    WHERE table_schema = 'layer0' AND table_name = 'discipline_technique_foci'
  ) INTO table_exists;

  IF NOT table_exists THEN
    RAISE EXCEPTION 'migrate_discipline_technique_foci: table not created';
  END IF;

  RAISE NOTICE 'migrate_discipline_technique_foci: OK — table created with indexes';
END $$;

COMMIT;
