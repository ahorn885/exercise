-- migrate_disciplines_add_primary_movement_v1.sql
--
-- Add a per-discipline `primary_movement` column to `layer0.disciplines`.
-- This is the movement axis (running / cycling / swimming / paddling /
-- skiing / climbing / hiking / navigation / other_skill) that the terrain
-- axis `discipline_category` cannot express — e.g. 'Water / Ocean' (swim)
-- and 'Water / River' (paddle) share a category but differ in movement.
--
-- Consumer: Layer 2E nutrition (§5.4.3 sport-profile CHO modifier) resolves
-- the race-day fueling archetype from the weighted mix of primary_movement,
-- and the §5.3.3 protein band treats 'climbing' as strength-biased. Plumbed
-- to Layer 2E via Layer 2A onto `Layer2ADiscipline.primary_movement`.
--
-- Population: 29 active discipline rows (post-R6 collapse, D-001..D-029).
-- Source of truth: canonical discipline definitions in
-- discipline_display_names.py + Sports_Framework_v11 Discipline Library.
--
-- Vocabulary: Layer 0 ENUM_MOVEMENTS (9 tokens, locked in
-- etl/layer0/extractors/sports_framework.py).
--
-- Idempotent: ALTER uses IF NOT EXISTS; UPDATEs are hardcoded per
-- discipline_id so re-running is a no-op on the canonical set.
--
-- Atomic: the DO $$ verification block RAISEs EXCEPTION on any violation,
-- rolling back the entire transaction.

BEGIN;

-- ── 1. Schema migration ──────────────────────────────────────────────

ALTER TABLE layer0.disciplines
  ADD COLUMN IF NOT EXISTS primary_movement TEXT;

COMMENT ON COLUMN layer0.disciplines.primary_movement IS
  'Dominant locomotor movement (subset of ENUM_MOVEMENTS). Movement axis '
  'for fueling/strength classification; complements the discipline_category '
  'terrain axis. Populated by migrate_disciplines_add_primary_movement_v1.';

-- ── 2. Populate — 29 UPDATE statements grouped by movement family ─────

-- Running / foot
UPDATE layer0.disciplines SET primary_movement = 'running'
 WHERE discipline_id = 'D-001' AND superseded_at IS NULL;  -- Trail Running
UPDATE layer0.disciplines SET primary_movement = 'running'
 WHERE discipline_id = 'D-002' AND superseded_at IS NULL;  -- Road Running
UPDATE layer0.disciplines SET primary_movement = 'hiking'
 WHERE discipline_id = 'D-003' AND superseded_at IS NULL;  -- Hiking
UPDATE layer0.disciplines SET primary_movement = 'running'
 WHERE discipline_id = 'D-015' AND superseded_at IS NULL;  -- Orienteering (locomotion; nav is a skill overlay)
UPDATE layer0.disciplines SET primary_movement = 'hiking'
 WHERE discipline_id = 'D-017' AND superseded_at IS NULL;  -- Snowshoeing
UPDATE layer0.disciplines SET primary_movement = 'running'
 WHERE discipline_id = 'D-024' AND superseded_at IS NULL;  -- Mountain Running
UPDATE layer0.disciplines SET primary_movement = 'running'
 WHERE discipline_id = 'D-026' AND superseded_at IS NULL;  -- Laser Run (run-dominant)
UPDATE layer0.disciplines SET primary_movement = 'running'
 WHERE discipline_id = 'D-027' AND superseded_at IS NULL;  -- Obstacle Racing (run-dominant)

-- Cycling
UPDATE layer0.disciplines SET primary_movement = 'cycling'
 WHERE discipline_id = 'D-006' AND superseded_at IS NULL;  -- Road Cycling
UPDATE layer0.disciplines SET primary_movement = 'cycling'
 WHERE discipline_id = 'D-007' AND superseded_at IS NULL;  -- Time-Trial Cycling
UPDATE layer0.disciplines SET primary_movement = 'cycling'
 WHERE discipline_id = 'D-008' AND superseded_at IS NULL;  -- Mountain Biking

-- Swimming
UPDATE layer0.disciplines SET primary_movement = 'swimming'
 WHERE discipline_id = 'D-004' AND superseded_at IS NULL;  -- Open Water Swimming
UPDATE layer0.disciplines SET primary_movement = 'swimming'
 WHERE discipline_id = 'D-005' AND superseded_at IS NULL;  -- Pool Swimming
UPDATE layer0.disciplines SET primary_movement = 'swimming'
 WHERE discipline_id = 'D-016' AND superseded_at IS NULL;  -- Swimming
UPDATE layer0.disciplines SET primary_movement = 'swimming'
 WHERE discipline_id = 'D-020' AND superseded_at IS NULL;  -- Swimrun (swim-limited fueling dominates)

-- Paddling
UPDATE layer0.disciplines SET primary_movement = 'paddling'
 WHERE discipline_id = 'D-009' AND superseded_at IS NULL;  -- Packrafting
UPDATE layer0.disciplines SET primary_movement = 'paddling'
 WHERE discipline_id = 'D-010' AND superseded_at IS NULL;  -- Kayaking
UPDATE layer0.disciplines SET primary_movement = 'paddling'
 WHERE discipline_id = 'D-011' AND superseded_at IS NULL;  -- Canoeing
UPDATE layer0.disciplines SET primary_movement = 'paddling'
 WHERE discipline_id = 'D-019' AND superseded_at IS NULL;  -- Paddle Rafting

-- Climbing / vertical
UPDATE layer0.disciplines SET primary_movement = 'climbing'
 WHERE discipline_id = 'D-012' AND superseded_at IS NULL;  -- Rock Climbing
UPDATE layer0.disciplines SET primary_movement = 'climbing'
 WHERE discipline_id = 'D-013' AND superseded_at IS NULL;  -- Abseiling
UPDATE layer0.disciplines SET primary_movement = 'climbing'
 WHERE discipline_id = 'D-014' AND superseded_at IS NULL;  -- Via Ferrata
UPDATE layer0.disciplines SET primary_movement = 'climbing'
 WHERE discipline_id = 'D-018' AND superseded_at IS NULL;  -- Mountaineering

-- Skiing
UPDATE layer0.disciplines SET primary_movement = 'skiing'
 WHERE discipline_id = 'D-021' AND superseded_at IS NULL;  -- Ski Touring
UPDATE layer0.disciplines SET primary_movement = 'skiing'
 WHERE discipline_id = 'D-022' AND superseded_at IS NULL;  -- Alpine Skiing
UPDATE layer0.disciplines SET primary_movement = 'skiing'
 WHERE discipline_id = 'D-023' AND superseded_at IS NULL;  -- Ski Transitions
UPDATE layer0.disciplines SET primary_movement = 'skiing'
 WHERE discipline_id = 'D-028' AND superseded_at IS NULL;  -- Cross-Country Skiing

-- Other skill (low-locomotor / shooting / blade)
UPDATE layer0.disciplines SET primary_movement = 'other_skill'
 WHERE discipline_id = 'D-025' AND superseded_at IS NULL;  -- Fencing
UPDATE layer0.disciplines SET primary_movement = 'other_skill'
 WHERE discipline_id = 'D-029' AND superseded_at IS NULL;  -- Rifle Shooting

-- ── 3. Verification ───────────────────────────────────────────────────

DO $$
DECLARE
  v_enum         TEXT[] := ARRAY[
    'running','cycling','swimming','paddling','skiing',
    'climbing','hiking','navigation','other_skill'
  ];
  v_null_count   INT;
  v_bad_value    TEXT;
BEGIN
  -- 3a: every active row populated
  SELECT COUNT(*) INTO v_null_count
    FROM layer0.disciplines
    WHERE superseded_at IS NULL AND primary_movement IS NULL;
  IF v_null_count > 0 THEN
    RAISE EXCEPTION 'migrate_primary_movement: % active row(s) still NULL', v_null_count;
  END IF;

  -- 3b: every value within ENUM_MOVEMENTS
  SELECT primary_movement INTO v_bad_value
    FROM layer0.disciplines
    WHERE superseded_at IS NULL
      AND NOT (primary_movement = ANY (v_enum))
    LIMIT 1;
  IF v_bad_value IS NOT NULL THEN
    RAISE EXCEPTION 'migrate_primary_movement: non-enum value %', v_bad_value;
  END IF;

  RAISE NOTICE 'migrate_primary_movement: OK — all active rows populated within ENUM_MOVEMENTS';
END $$;

COMMIT;

-- End of migrate_disciplines_add_primary_movement_v1.sql
