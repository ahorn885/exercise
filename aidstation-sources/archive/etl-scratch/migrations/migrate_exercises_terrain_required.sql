-- migrate_exercises_terrain_required.sql
-- Adds terrain_required TEXT[] to layer0.exercises.
--
-- Why this field exists:
--   vocabulary_transforms.py strips terrain tokens from exercises.equipment[]
--   at ETL time (Vocabulary Audit §3 cleanup task). Before this migration those
--   tokens were dropped entirely, producing two bugs:
--     1. Terrain-gated exercises appeared Tier 1 available to 2C (equipment[]
--        satisfied) even when the athlete had no relevant terrain access.
--     2. Layer 4 had no way to cross-reference exercise terrain requirements
--        against 2B terrain gap output.
--   terrain_required[] stores those tokens so 2C can annotate each exercise
--   and Layer 4 can do the terrain-exercise cross-reference without an LLM call.
--
-- 2C contract:
--   2C annotates exercises with terrain_required[] but does NOT filter on it.
--   2C has no terrain access input. Layer 4 receives both 2B terrain gap output
--   and 2C terrain_required annotations; it performs the cross-reference.
--
-- Data population:
--   Column is added NULL-able. Existing rows remain NULL until the next ETL
--   re-run. vocabulary_transforms.py must be updated (see companion note below)
--   to route terrain tokens to this field instead of dropping.
--   ETL re-run is already queued for v3 changes (new tables + columns).
--
-- etl_version: no version bump here — this is a schema-only migration.
--   The first ETL run after this migration will populate terrain_required
--   under its own etl_version (0B-v17.0-r2).
--
-- Safe to re-run: ADD COLUMN IF NOT EXISTS.

BEGIN;

-- ── 1. Schema migration ────────────────────────────────────────────────────

ALTER TABLE layer0.exercises
  ADD COLUMN IF NOT EXISTS terrain_required TEXT[];

-- ── 2. Verify ──────────────────────────────────────────────────────────────

DO $$
DECLARE
  col_exists BOOLEAN;
BEGIN
  SELECT EXISTS (
    SELECT 1
    FROM information_schema.columns
    WHERE table_schema = 'layer0'
      AND table_name   = 'exercises'
      AND column_name  = 'terrain_required'
  ) INTO col_exists;

  IF NOT col_exists THEN
    RAISE EXCEPTION 'migrate_exercises_terrain_required: column terrain_required not found on layer0.exercises';
  END IF;

  RAISE NOTICE 'migrate_exercises_terrain_required: OK — terrain_required column present on layer0.exercises';
END $$;

COMMIT;


-- ── vocabulary_transforms.py update (companion note) ──────────────────────
--
-- The TERRAIN_TOKENS set in vocabulary_transforms.py already exists to
-- identify terrain items in col 7. The required change is to route matched
-- tokens into terrain_required[] instead of dropping them.
--
-- Relevant section to update in split_equipment_column():
--
--   BEFORE:
--     equipment_items = [t for t in tokens if t not in TERRAIN_TOKENS
--                                          and t not in SITUATIONAL_TOKENS]
--     # terrain tokens were discarded here
--
--   AFTER:
--     equipment_items  = [t for t in tokens if t not in TERRAIN_TOKENS
--                                           and t not in SITUATIONAL_TOKENS]
--     terrain_items    = [t for t in tokens if t in TERRAIN_TOKENS]
--     # situational tokens (Darkness, Group Riding Environment, Partner/Team)
--     # remain discarded — they are not terrain and not equipment
--
--   Return terrain_items alongside equipment_items. ETL writer assigns
--   terrain_items → exercises.terrain_required[].
--
-- TERRAIN_TOKENS (for reference — from Vocab Audit §3 Terrain table):
--   'Outdoor Hill', 'Steep Hill', 'Steep Mountain', 'Steep Track',
--   'Trail', 'Flat Trail', 'Gravel or Dirt Trail',
--   'Road', 'Descent Road', 'Gravel Road',
--   'Pump Track',
--   'Pool', 'Open Water', 'Open Water Body', 'Pool or Flat Water',
--   'Open Water or Ocean', 'Ocean or Surf', 'Flat or Choppy Water',
--   'Whitewater', 'Moving Water', 'River',
--   'Snow Slope', 'Groomed Slope', 'Groomed Track', 'Deep Snow or Sand',
--   'Rocky Terrain', 'Boulders', 'Scree Field', 'Loose Rocky Slope',
--   'Fell Terrain', 'Steep Grass', 'Moorland', 'Heather', 'Bog',
--   'Climb',
--   'Varied Terrain',
--   'Rock Wall', 'Climbing Gym'
--
-- SITUATIONAL_TOKENS (discarded — not terrain, not equipment):
--   'Darkness',
--   'Group Riding Environment',
--   'Partner or Visual Cue', 'Tandem Partner', 'Team'
