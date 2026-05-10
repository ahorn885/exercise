-- update_retype_keeper_exercises.sql  (v2 — deployed-schema corrected)
--
-- Retypes 13 v19 exercises that were classified as 'Technical / Skill' but
-- represent real load-bearing training stimuli. Each gets a new exercise_type.
--
-- Pattern: supersede + reinsert with new etl_version. The exercise_id stays
-- the same; downstream references survive.
--
-- ── Affected tables ────────────────────────────────────────────────────────
--   layer0.exercises          (13 rows reinserted at new etl_version, 13 superseded)
--   layer0.sport_exercise_map (all rows for the 13 IDs reinserted at new etl_version,
--                              old rows superseded — the map carries denormalized
--                              exercise_type which must stay consistent)
--
-- ── Schema verification (added 2026-05-10 after v1 caught) ─────────────────
-- v1 of this script wrote against the column names documented in
-- Layer0_ETL_Spec_v3.md §4.12. Deployed production schema (verified
-- 2026-05-10 via psql \d) has diverged from spec — see the spec patch doc
-- for the full list. Step 1 below introspects the deployed schema and
-- aborts if columns or constraints aren't as expected. This is a guardrail
-- against the same class of bug that hit K1/K2.
--
-- ── Idempotency ────────────────────────────────────────────────────────────
-- ON CONFLICT (exercise_id, etl_version) DO NOTHING on inserts; supersede
-- UPDATE excludes rows already at the new etl_version.
--
-- etl_version: '0B-v19.B'

BEGIN;

-- ╔═══════════════════════════════════════════════════════════════════════╗
-- ║ 1. PRE-FLIGHT — verify deployed schema matches what we'll write to    ║
-- ╚═══════════════════════════════════════════════════════════════════════╝

DO $$
DECLARE
  expected_ex_cols TEXT[] := ARRAY[
    'exercise_id','exercise_name','exercise_type',
    'movement_patterns','primary_muscles','secondary_muscles',
    'equipment_required','injury_flags_text',
    'contraindicated_parts','contraindicated_conditions',
    'equipment_substitutes','physical_proxies',
    'progression_exercise_id','progression_exercise_name',
    'regression_exercise_id','regression_exercise_name',
    'sport_count','coaching_cues',
    'terrain_required','equipment_substitutes_structured',
    'etl_version','etl_run_at','superseded_at'
  ];
  expected_map_cols TEXT[] := ARRAY[
    'exercise_id','exercise_name','exercise_type',
    'sport_name','sport_relevance_note','priority',
    'etl_version','etl_run_at','superseded_at'
  ];
  col TEXT;
  unique_idx_count INT;
BEGIN
  -- Check layer0.exercises columns
  FOREACH col IN ARRAY expected_ex_cols LOOP
    IF NOT EXISTS (
      SELECT 1 FROM information_schema.columns
      WHERE table_schema = 'layer0' AND table_name = 'exercises'
        AND column_name = col
    ) THEN
      RAISE EXCEPTION 'pre-flight: layer0.exercises is missing expected column "%". '
                      'Update this script''s column list to match the deployed schema before running.', col;
    END IF;
  END LOOP;

  -- Check layer0.sport_exercise_map columns
  FOREACH col IN ARRAY expected_map_cols LOOP
    IF NOT EXISTS (
      SELECT 1 FROM information_schema.columns
      WHERE table_schema = 'layer0' AND table_name = 'sport_exercise_map'
        AND column_name = col
    ) THEN
      RAISE EXCEPTION 'pre-flight: layer0.sport_exercise_map is missing expected column "%". '
                      'Update this script''s column list to match the deployed schema before running.', col;
    END IF;
  END LOOP;

  -- Check ON CONFLICT target on sport_exercise_map: expect a UNIQUE index
  -- whose definition ends with "(exercise_id, sport_name, etl_version)".
  -- Using pg_indexes covers both UNIQUE constraints and standalone unique indexes.
  SELECT COUNT(*) INTO unique_idx_count
  FROM pg_indexes
  WHERE schemaname = 'layer0'
    AND tablename = 'sport_exercise_map'
    AND indexdef ILIKE '%UNIQUE%'
    AND indexdef LIKE '%(exercise_id, sport_name, etl_version)%';

  IF unique_idx_count = 0 THEN
    RAISE EXCEPTION 'pre-flight: layer0.sport_exercise_map has no UNIQUE index/constraint on '
                    '(exercise_id, sport_name, etl_version). The INSERT''s ON CONFLICT target '
                    'will fail. Inspect deployed constraints with \d+ layer0.sport_exercise_map '
                    'and adjust the ON CONFLICT clause.';
  END IF;

  RAISE NOTICE 'pre-flight: schema OK — % expected columns on exercises, % on sport_exercise_map, '
               'UNIQUE target on (exercise_id, sport_name, etl_version) confirmed',
               cardinality(expected_ex_cols), cardinality(expected_map_cols);
END $$;

-- Defensive no-op against the v3-spec column-level UNIQUE on exercise_id.
-- Production verified absent (2026-05-10); IF EXISTS protects fresh-build envs
-- created from a literal reading of the spec. Spec correction logged in the
-- Batch B patch §4.12.
ALTER TABLE layer0.exercises
  DROP CONSTRAINT IF EXISTS exercises_exercise_id_key;

-- ╔═══════════════════════════════════════════════════════════════════════╗
-- ║ 2. Define the retype map                                              ║
-- ╚═══════════════════════════════════════════════════════════════════════╝

CREATE TEMP TABLE _batch_b_retypes (
  exercise_id TEXT PRIMARY KEY,
  new_type    TEXT NOT NULL
) ON COMMIT DROP;

INSERT INTO _batch_b_retypes (exercise_id, new_type) VALUES
  ('EX051', 'Aerobic / Endurance'),  -- Uphill Running Technique Drill
  ('EX052', 'Aerobic / Endurance'),  -- Downhill Running Technique Drill
  ('EX070', 'Strength'),              -- Single-Leg Cycling Drill (Trainer)
  ('EX124', 'Aerobic / Endurance'),  -- Power Hiking Technique
  ('EX125', 'Strength'),              -- Quad-Eccentric Walk (Controlled Descent)
  ('EX150', 'Aerobic / Endurance'),  -- Rest Step Technique
  ('EX159', 'Activation / Primer'),   -- Wet Exit & Re-entry (Kayak)
  ('EX168', 'Aerobic / Endurance'),  -- Skinning Uphill Technique
  ('EX180', 'Interval / Tempo'),      -- Walk-Run Interval Method (Ultra Pacing)
  ('EX185', 'Aerobic / Endurance'),  -- Climb Pacing & Cadence Management
  ('EX186', 'Interval / Tempo'),      -- High Cadence Spin Drill
  ('EX197', 'Interval / Tempo'),      -- Double Brick / Run-Bike-Run Pacing Drill
  ('EX215', 'Interval / Tempo');      -- Extreme Gradient Uphill Pacing (VK / Sky)

DO $$
DECLARE
  retype_count INT;
BEGIN
  SELECT COUNT(*) INTO retype_count FROM _batch_b_retypes;
  IF retype_count <> 13 THEN
    RAISE EXCEPTION 'update_retype_keeper_exercises: retype map has % entries, expected 13', retype_count;
  END IF;
END $$;

-- ╔═══════════════════════════════════════════════════════════════════════╗
-- ║ 3. Snapshot pre-state                                                 ║
-- ╚═══════════════════════════════════════════════════════════════════════╝

CREATE TEMP TABLE _pre_state (
  what  TEXT,
  count INT
) ON COMMIT DROP;

INSERT INTO _pre_state
SELECT 'active_exercises_pre',
       COUNT(*)
FROM layer0.exercises e
JOIN _batch_b_retypes r USING (exercise_id)
WHERE e.superseded_at IS NULL
  AND e.exercise_type = 'Technical / Skill';

INSERT INTO _pre_state
SELECT 'active_map_rows_pre',
       COUNT(*)
FROM layer0.sport_exercise_map m
JOIN _batch_b_retypes r USING (exercise_id)
WHERE m.superseded_at IS NULL
  AND m.exercise_type = 'Technical / Skill';

-- ╔═══════════════════════════════════════════════════════════════════════╗
-- ║ 4. Reinsert layer0.exercises with new exercise_type                   ║
-- ╚═══════════════════════════════════════════════════════════════════════╝
--
-- Column list matches deployed schema exactly. Every non-PK, non-superseded_at
-- column is copied; only exercise_type changes (driven by retype map).
-- equipment_substitutes (single JSONB carrying standard + improvised) and
-- equipment_substitutes_structured (added by prior migration) are both copied.

INSERT INTO layer0.exercises (
  exercise_id, exercise_name, exercise_type,
  movement_patterns, primary_muscles, secondary_muscles,
  equipment_required, injury_flags_text,
  contraindicated_parts, contraindicated_conditions,
  equipment_substitutes, physical_proxies,
  progression_exercise_id, progression_exercise_name,
  regression_exercise_id, regression_exercise_name,
  sport_count, coaching_cues,
  terrain_required, equipment_substitutes_structured,
  etl_version, etl_run_at
)
SELECT
  e.exercise_id, e.exercise_name, r.new_type,
  e.movement_patterns, e.primary_muscles, e.secondary_muscles,
  e.equipment_required, e.injury_flags_text,
  e.contraindicated_parts, e.contraindicated_conditions,
  e.equipment_substitutes, e.physical_proxies,
  e.progression_exercise_id, e.progression_exercise_name,
  e.regression_exercise_id, e.regression_exercise_name,
  e.sport_count, e.coaching_cues,
  e.terrain_required, e.equipment_substitutes_structured,
  '0B-v19.B', NOW()
FROM layer0.exercises e
JOIN _batch_b_retypes r USING (exercise_id)
WHERE e.superseded_at IS NULL
  AND e.etl_version <> '0B-v19.B'
ON CONFLICT (exercise_id, etl_version) DO NOTHING;

-- ╔═══════════════════════════════════════════════════════════════════════╗
-- ║ 5. Supersede the prior-version exercises rows                         ║
-- ╚═══════════════════════════════════════════════════════════════════════╝

UPDATE layer0.exercises e
SET superseded_at = NOW()
FROM _batch_b_retypes r
WHERE e.exercise_id = r.exercise_id
  AND e.superseded_at IS NULL
  AND e.etl_version <> '0B-v19.B';

-- ╔═══════════════════════════════════════════════════════════════════════╗
-- ║ 6. Reinsert sport_exercise_map rows with new exercise_type            ║
-- ╚═══════════════════════════════════════════════════════════════════════╝

INSERT INTO layer0.sport_exercise_map (
  exercise_id, exercise_name, exercise_type,
  sport_name, sport_relevance_note, priority,
  etl_version, etl_run_at
)
SELECT
  m.exercise_id, m.exercise_name, r.new_type,
  m.sport_name, m.sport_relevance_note, m.priority,
  '0B-v19.B', NOW()
FROM layer0.sport_exercise_map m
JOIN _batch_b_retypes r USING (exercise_id)
WHERE m.superseded_at IS NULL
  AND m.etl_version <> '0B-v19.B'
ON CONFLICT (exercise_id, sport_name, etl_version) DO NOTHING;

-- ╔═══════════════════════════════════════════════════════════════════════╗
-- ║ 7. Supersede the prior-version map rows                               ║
-- ╚═══════════════════════════════════════════════════════════════════════╝

UPDATE layer0.sport_exercise_map m
SET superseded_at = NOW()
FROM _batch_b_retypes r
WHERE m.exercise_id = r.exercise_id
  AND m.superseded_at IS NULL
  AND m.etl_version <> '0B-v19.B';

-- ╔═══════════════════════════════════════════════════════════════════════╗
-- ║ 8. Verify                                                             ║
-- ╚═══════════════════════════════════════════════════════════════════════╝

DO $$
DECLARE
  ex_pre         INT;
  map_pre        INT;
  ex_active_new  INT;
  ex_active_old  INT;
  map_active_new INT;
  map_active_old INT;
  wrong_type     INT;
BEGIN
  SELECT count INTO ex_pre  FROM _pre_state WHERE what = 'active_exercises_pre';
  SELECT count INTO map_pre FROM _pre_state WHERE what = 'active_map_rows_pre';

  SELECT COUNT(*) INTO ex_active_new
  FROM layer0.exercises e
  JOIN _batch_b_retypes r USING (exercise_id)
  WHERE e.superseded_at IS NULL AND e.etl_version = '0B-v19.B';

  SELECT COUNT(*) INTO map_active_new
  FROM layer0.sport_exercise_map m
  JOIN _batch_b_retypes r USING (exercise_id)
  WHERE m.superseded_at IS NULL AND m.etl_version = '0B-v19.B';

  SELECT COUNT(*) INTO ex_active_old
  FROM layer0.exercises e
  JOIN _batch_b_retypes r USING (exercise_id)
  WHERE e.superseded_at IS NULL AND e.etl_version <> '0B-v19.B';

  SELECT COUNT(*) INTO map_active_old
  FROM layer0.sport_exercise_map m
  JOIN _batch_b_retypes r USING (exercise_id)
  WHERE m.superseded_at IS NULL AND m.etl_version <> '0B-v19.B';

  SELECT COUNT(*) INTO wrong_type
  FROM layer0.exercises e
  JOIN _batch_b_retypes r USING (exercise_id)
  WHERE e.superseded_at IS NULL
    AND e.etl_version = '0B-v19.B'
    AND e.exercise_type <> r.new_type;

  IF ex_active_new <> 13 THEN
    RAISE EXCEPTION 'verify: expected 13 new exercises rows at 0B-v19.B, found %', ex_active_new;
  END IF;

  IF ex_active_old <> 0 THEN
    RAISE EXCEPTION 'verify: % old exercises rows still active', ex_active_old;
  END IF;

  IF map_active_old <> 0 THEN
    RAISE EXCEPTION 'verify: % old map rows still active', map_active_old;
  END IF;

  IF wrong_type <> 0 THEN
    RAISE EXCEPTION 'verify: % new rows have wrong exercise_type', wrong_type;
  END IF;

  RAISE NOTICE 'update_retype_keeper_exercises: OK — 13 exercises retyped, % map rows refreshed (pre-counts: % / %)',
    map_active_new, ex_pre, map_pre;
END $$;

COMMIT;
