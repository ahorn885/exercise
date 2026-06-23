-- 0016_rename_exercises_and_equipment_edits.sql
--
-- #679 catalog cleanup ratified on the review sheet (Andy 2026-06-17):
--   (A) 7 RENAMES — drop the equipment qualifier from the display name + set the
--       equipment_required Andy specified.
--   (B) 4 EQUIPMENT FIXES on the new exercises (0014/0015) now that Andy confirmed
--       Sandbag / Battle ropes / Treadwall ARE valid picker tokens.
--   (C) 5 COACH-NOTE appends — progression variations appended to coaching_cues.
--
-- Edit shape: SERVING-RELEVANT supersede-and-reinsert (the 0008 pattern). Each
-- edited row is re-inserted at the bumped version 0B-v1.6.13 -> 0B-v1.6.14 with
-- the changed columns overridden and every other column copied verbatim, then the
-- old row is superseded (history preserved). The bumped version advances the 0B
-- digest and invalidates plan-gen caches. The 7 renamed exercises' denormalized
-- sport_exercise_map.exercise_name is synced the same way.
--
-- physical_proxies / progression name references on OTHER rows still cite the old
-- qualified names — cosmetic only (the exercises_fk gate keys on exercise_id, which
-- is unchanged); left as-is, matching the 0008 precedent.
--
-- Idempotent: re-run is a no-op once the rows are active at 0B-v1.6.14 (the
-- supersede/insert are guarded by etl_version <> '0B-v1.6.14').

\set ON_ERROR_STOP on

BEGIN;

-- ── (A+B+C) Exercises: re-insert the edited rows at 0B-v1.6.14 ─────────────────
WITH ed(exercise_id, new_name, new_equip, cue_suffix) AS (
  VALUES
    -- (A) renames + equipment
    ('EX002','Goblet Squat',          ARRAY['Dumbbell','Kettlebell']::text[], NULL::text),
    ('EX231','Front Squat',           ARRAY['Barbell','Dumbbell','Kettlebell']::text[], NULL),
    ('EX016','Thoracic Rotation',     NULL::text[], NULL),
    ('EX081','Face Pull',             ARRAY['Resistance band','Cable machine']::text[], NULL),
    ('EX061','Good Morning',          ARRAY['Barbell']::text[], NULL),
    ('EX111','Reverse Wrist Curl',    ARRAY['Dumbbell','Kettlebell','Cable machine','Resistance band']::text[], NULL),
    ('EX021','Bulgarian Split Squat', ARRAY['Dumbbell','Kettlebell']::text[], NULL),
    -- (B) equipment fixes on the new exercises
    ('EX277',NULL, ARRAY['Sandbag','Kettlebell','Dumbbell']::text[], NULL),
    ('EX279',NULL, ARRAY['Sandbag','Kettlebell','Dumbbell','Backpack']::text[], NULL),
    ('EX287',NULL, ARRAY['Battle ropes']::text[], NULL),
    ('EX288',NULL, ARRAY['Treadwall']::text[], NULL),
    -- (C) coach-note progression appends
    ('EX022',NULL, NULL::text[], ' Progress the range by elevating the front foot (deficit / elevated reverse lunge).'),
    ('EX031',NULL, NULL, ' Progress the stability demand by swinging on an unstable surface such as an inverted BOSU.'),
    ('EX088',NULL, NULL, ' Progress to a seated med-ball torso rotation for a stricter, more isolated trunk rotation.'),
    ('EX098',NULL, NULL, ' Progress the stability demand with a seated stability-ball shoulder press.'),
    ('EX242',NULL, NULL, ' Progress the stability demand with a stability-ball single-arm press.')
)
INSERT INTO layer0.exercises (
  exercise_id, exercise_name, exercise_type, movement_patterns, primary_muscles,
  secondary_muscles, equipment_required, injury_flags_text, contraindicated_parts,
  contraindicated_conditions, equipment_substitutes, physical_proxies,
  progression_exercise_id, progression_exercise_name, regression_exercise_id,
  regression_exercise_name, sport_count, coaching_cues,
  etl_version, etl_run_at, terrain_required, equipment_substitutes_structured, movement_components
)
SELECT
  e.exercise_id,
  COALESCE(ed.new_name, e.exercise_name),
  e.exercise_type, e.movement_patterns, e.primary_muscles, e.secondary_muscles,
  COALESCE(ed.new_equip, e.equipment_required),
  e.injury_flags_text, e.contraindicated_parts, e.contraindicated_conditions,
  e.equipment_substitutes, e.physical_proxies,
  e.progression_exercise_id, e.progression_exercise_name,
  e.regression_exercise_id, e.regression_exercise_name, e.sport_count,
  CASE WHEN ed.cue_suffix IS NOT NULL
       THEN COALESCE(e.coaching_cues, '') || ed.cue_suffix
       ELSE e.coaching_cues END,
  '0B-v1.6.14', now(), e.terrain_required, e.equipment_substitutes_structured, e.movement_components
FROM layer0.exercises e
JOIN ed ON ed.exercise_id = e.exercise_id
WHERE e.superseded_at IS NULL
  AND e.etl_version <> '0B-v1.6.14';

UPDATE layer0.exercises e
   SET superseded_at = now()
 WHERE e.superseded_at IS NULL
   AND e.etl_version <> '0B-v1.6.14'
   AND e.exercise_id IN ('EX002','EX231','EX016','EX081','EX061','EX111','EX021',
                         'EX277','EX279','EX287','EX288',
                         'EX022','EX031','EX088','EX098','EX242');

-- ── Sync the 7 renamed exercises' denormalized sport_exercise_map.exercise_name ─
WITH rn(exercise_id, new_name) AS (
  VALUES ('EX002','Goblet Squat'),('EX231','Front Squat'),('EX016','Thoracic Rotation'),
         ('EX081','Face Pull'),('EX061','Good Morning'),('EX111','Reverse Wrist Curl'),
         ('EX021','Bulgarian Split Squat')
)
INSERT INTO layer0.sport_exercise_map (
  exercise_id, exercise_name, exercise_type, sport_name, sport_relevance_note, priority, etl_version, etl_run_at
)
SELECT m.exercise_id, rn.new_name, m.exercise_type, m.sport_name, m.sport_relevance_note,
       m.priority, '0B-v1.6.14', now()
FROM layer0.sport_exercise_map m
JOIN rn ON rn.exercise_id = m.exercise_id
WHERE m.superseded_at IS NULL
  AND m.etl_version <> '0B-v1.6.14';

UPDATE layer0.sport_exercise_map m
   SET superseded_at = now()
 WHERE m.superseded_at IS NULL
   AND m.etl_version <> '0B-v1.6.14'
   AND m.exercise_id IN ('EX002','EX231','EX016','EX081','EX061','EX111','EX021');

-- ── Verify (atomic) ───────────────────────────────────────────────────────────
DO $$
DECLARE v_ex INT; v_name INT; v_equip INT; v_dup INT;
BEGIN
  -- All 16 edited exercises are active at exactly one version (0B-v1.6.14).
  SELECT count(*) INTO v_ex FROM layer0.exercises
   WHERE superseded_at IS NULL AND etl_version='0B-v1.6.14'
     AND exercise_id IN ('EX002','EX231','EX016','EX081','EX061','EX111','EX021',
                         'EX277','EX279','EX287','EX288','EX022','EX031','EX088','EX098','EX242');
  IF v_ex <> 16 THEN RAISE EXCEPTION '0016: expected 16 edited exercises at 0B-v1.6.14, found %', v_ex; END IF;

  -- No exercise_id is double-active (supersede landed).
  SELECT count(*) INTO v_dup FROM (
    SELECT exercise_id FROM layer0.exercises WHERE superseded_at IS NULL
     GROUP BY exercise_id HAVING count(*) > 1) d;
  IF v_dup > 0 THEN RAISE EXCEPTION '0016: % exercise_id(s) double-active after supersede', v_dup; END IF;

  -- The renames took (spot-check the qualified names are gone).
  SELECT count(*) INTO v_name FROM layer0.exercises
   WHERE superseded_at IS NULL
     AND exercise_id IN ('EX002','EX231','EX081','EX061','EX111','EX021')
     AND (exercise_name LIKE '%(%' OR exercise_name LIKE '%Band %' OR exercise_name LIKE '%Drill%');
  IF v_name <> 0 THEN RAISE EXCEPTION '0016: % renamed exercise(s) still carry a qualifier', v_name; END IF;

  -- The equipment fixes took (Sandbag/Battle ropes/Treadwall now present).
  SELECT count(*) INTO v_equip FROM layer0.exercises
   WHERE superseded_at IS NULL
     AND ( (exercise_id='EX287' AND NOT ('Battle ropes' = ANY(equipment_required)))
        OR (exercise_id='EX288' AND NOT ('Treadwall' = ANY(equipment_required)))
        OR (exercise_id='EX277' AND NOT ('Sandbag' = ANY(equipment_required))) );
  IF v_equip <> 0 THEN RAISE EXCEPTION '0016: % equipment fix(es) did not take', v_equip; END IF;

  RAISE NOTICE '0016: OK — 7 renames + 4 equipment fixes + 5 coach-note appends at 0B-v1.6.14';
END $$;

COMMIT;

-- End of 0016_rename_exercises_and_equipment_edits.sql
