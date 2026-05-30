-- migrate_disciplines_endurance_profile_v1.sql
--
-- Swap the per-discipline classification on `layer0.disciplines`:
--   + ADD  `endurance_profile` TEXT  (enum: Pure endurance | Mixed | Technical-dominant)
--   - DROP `discipline_category` TEXT (free-text terrain axis — junk; was only
--          ever consumed by a fragile prefix-parse in Layer 2E, now removed).
--
-- `endurance_profile` is the curated aerobic-dependency axis that drives the
-- Layer 2E §5.3.3 daily-carb band. Source of truth:
-- etl/layer0/discipline_canon.DISCIPLINE_ENDURANCE_PROFILE (values confirmed by
-- Andy 2026-05-30). Plumbed to Layer 2E via Layer 2A onto
-- `Layer2ADiscipline.endurance_profile`. (Movement axis `primary_movement`
-- stays — it drives the orthogonal race-day sport-profile + protein band.)
--
-- SEQUENCING (Andy's hands): deploy code -> run THIS migration -> re-run the
-- Layer 0 ETL -> verify. The ETL re-run is what actually removes D-015
-- (folded into D-003 Trekking), D-025/D-026/D-029 (removed) and the Modern
-- Pentathlon / Biathlon sports, and repopulates `endurance_profile` for the
-- fresh etl_version rows from the canon. The UPDATEs below are belt-and-
-- suspenders so the deployed (pre-re-ETL) rows aren't all defaulted to 'Mixed'
-- in the gap between migration and ETL.
--
-- Idempotent: ADD uses IF NOT EXISTS; UPDATEs are hardcoded per discipline_id;
-- DROP uses IF EXISTS. Atomic: the DO $$ block RAISEs on any violation.

BEGIN;

-- ── 1. Schema: add endurance_profile ─────────────────────────────────
ALTER TABLE layer0.disciplines
  ADD COLUMN IF NOT EXISTS endurance_profile TEXT;

COMMENT ON COLUMN layer0.disciplines.endurance_profile IS
  'Aerobic-dependency axis (ENUM_ENDURANCE: Pure endurance | Mixed | '
  'Technical-dominant). Curated in discipline_canon.DISCIPLINE_ENDURANCE_PROFILE; '
  'drives the Layer 2E daily-carb band. Replaced the free-text discipline_category.';

-- ── 2. Populate the 21 surviving canonical disciplines ───────────────
UPDATE layer0.disciplines SET endurance_profile = 'Pure endurance'
 WHERE discipline_id = 'D-001' AND superseded_at IS NULL;  -- Trail Running
UPDATE layer0.disciplines SET endurance_profile = 'Pure endurance'
 WHERE discipline_id = 'D-002' AND superseded_at IS NULL;  -- Road Running
UPDATE layer0.disciplines SET endurance_profile = 'Pure endurance'
 WHERE discipline_id = 'D-003' AND superseded_at IS NULL;  -- Trekking
UPDATE layer0.disciplines SET endurance_profile = 'Pure endurance'
 WHERE discipline_id = 'D-004' AND superseded_at IS NULL;  -- Swimming
UPDATE layer0.disciplines SET endurance_profile = 'Pure endurance'
 WHERE discipline_id = 'D-006' AND superseded_at IS NULL;  -- Road Cycling
UPDATE layer0.disciplines SET endurance_profile = 'Pure endurance'
 WHERE discipline_id = 'D-007' AND superseded_at IS NULL;  -- Time-Trial Cycling
UPDATE layer0.disciplines SET endurance_profile = 'Mixed'
 WHERE discipline_id = 'D-008' AND superseded_at IS NULL;  -- Mountain Biking
UPDATE layer0.disciplines SET endurance_profile = 'Mixed'
 WHERE discipline_id = 'D-009' AND superseded_at IS NULL;  -- Packrafting
UPDATE layer0.disciplines SET endurance_profile = 'Pure endurance'
 WHERE discipline_id = 'D-010' AND superseded_at IS NULL;  -- Kayaking
UPDATE layer0.disciplines SET endurance_profile = 'Pure endurance'
 WHERE discipline_id = 'D-011' AND superseded_at IS NULL;  -- Canoeing
UPDATE layer0.disciplines SET endurance_profile = 'Technical-dominant'
 WHERE discipline_id = 'D-012' AND superseded_at IS NULL;  -- Rock Climbing
UPDATE layer0.disciplines SET endurance_profile = 'Technical-dominant'
 WHERE discipline_id = 'D-013' AND superseded_at IS NULL;  -- Abseiling
UPDATE layer0.disciplines SET endurance_profile = 'Technical-dominant'
 WHERE discipline_id = 'D-014' AND superseded_at IS NULL;  -- Via Ferrata
UPDATE layer0.disciplines SET endurance_profile = 'Pure endurance'
 WHERE discipline_id = 'D-017' AND superseded_at IS NULL;  -- Snowshoeing
UPDATE layer0.disciplines SET endurance_profile = 'Mixed'
 WHERE discipline_id = 'D-018' AND superseded_at IS NULL;  -- Mountaineering
UPDATE layer0.disciplines SET endurance_profile = 'Mixed'
 WHERE discipline_id = 'D-019' AND superseded_at IS NULL;  -- Paddle Rafting
UPDATE layer0.disciplines SET endurance_profile = 'Pure endurance'
 WHERE discipline_id = 'D-021' AND superseded_at IS NULL;  -- Uphill Skinning
UPDATE layer0.disciplines SET endurance_profile = 'Technical-dominant'
 WHERE discipline_id = 'D-022' AND superseded_at IS NULL;  -- Alpine Descent
UPDATE layer0.disciplines SET endurance_profile = 'Pure endurance'
 WHERE discipline_id = 'D-024' AND superseded_at IS NULL;  -- Mountain Running
UPDATE layer0.disciplines SET endurance_profile = 'Mixed'
 WHERE discipline_id = 'D-027' AND superseded_at IS NULL;  -- Obstacle Course Racing
UPDATE layer0.disciplines SET endurance_profile = 'Pure endurance'
 WHERE discipline_id = 'D-028' AND superseded_at IS NULL;  -- Cross-Country Skiing

-- ── 3. Verification ───────────────────────────────────────────────────
DO $$
DECLARE
  v_enum        TEXT[] := ARRAY['Pure endurance','Mixed','Technical-dominant'];
  v_survivors   TEXT[] := ARRAY[
    'D-001','D-002','D-003','D-004','D-006','D-007','D-008','D-009','D-010',
    'D-011','D-012','D-013','D-014','D-017','D-018','D-019','D-021','D-022',
    'D-024','D-027','D-028'
  ];
  v_missing     INT;
  v_bad_value   TEXT;
BEGIN
  -- 3a: every surviving canonical discipline is populated
  SELECT COUNT(*) INTO v_missing
    FROM unnest(v_survivors) AS s(id)
    WHERE NOT EXISTS (
      SELECT 1 FROM layer0.disciplines d
       WHERE d.discipline_id = s.id AND d.superseded_at IS NULL
         AND d.endurance_profile IS NOT NULL
    );
  IF v_missing > 0 THEN
    RAISE EXCEPTION 'migrate_endurance_profile: % surviving discipline(s) not populated', v_missing;
  END IF;

  -- 3b: no non-enum value among populated rows
  SELECT endurance_profile INTO v_bad_value
    FROM layer0.disciplines
    WHERE superseded_at IS NULL
      AND endurance_profile IS NOT NULL
      AND NOT (endurance_profile = ANY (v_enum))
    LIMIT 1;
  IF v_bad_value IS NOT NULL THEN
    RAISE EXCEPTION 'migrate_endurance_profile: non-enum value %', v_bad_value;
  END IF;

  RAISE NOTICE 'migrate_endurance_profile: OK — 21 survivors populated within ENUM_ENDURANCE';
END $$;

-- ── 4. Drop the superseded free-text terrain column ──────────────────
ALTER TABLE layer0.disciplines
  DROP COLUMN IF EXISTS discipline_category;

COMMIT;

-- End of migrate_disciplines_endurance_profile_v1.sql
