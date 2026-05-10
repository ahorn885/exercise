-- migrate_batch_c_bike_load_curation.sql
--
-- Purpose:
--   Curate 10 exercises whose equipment_required[] currently holds implicit-OR
--   alternatives (e.g., "Road bike, Mountain bike, Gravel bike, TT Bike, Bike trainer"
--   on EX073). Split into:
--     - equipment_required[]                 = single primary (AND of required tokens)
--     - equipment_substitutes_structured     = JSONB array of substitutes
--   so that Layer 2C Tier 2 resolution gives Layer 4 a named substitute when
--   the primary fails.
--
-- Pattern:
--   For each of 10 exercises, supersede the active row and reinsert a new row
--   at etl_version '0B-v19.C' with updated equipment_required and a merged
--   equipment_substitutes_structured (new bike/load variants prepended, then
--   existing non-improvised, then existing improvised — per Andy's choice (b),
--   3-bucket re-sort).
--
-- Coverage (per Batch_A_Done_Batches_BC_Kickoff_Handoff.md):
--   EX073 Threshold Intervals (Bike)
--   EX074 VO2 Max Intervals (Bike)
--   EX075 Sweet Spot Training (Bike)
--   EX117 Loaded Step-Down (Eccentric Box)        -- adds Plyo box (was correct), strength fix
--   EX119 Weighted Step-Up (High Box, Heavy Load) -- adds Plyo box (was missing), drops Barbell
--   EX174 Aero / TT Position Hold
--   EX185 Climb Pacing & Cadence Management       -- drops Treadmill entirely
--   EX186 High Cadence Spin Drill
--   EX197 Double Brick / Run-Bike-Run Pacing Drill
--   EX229 Bench Press (Barbell / DB)              -- splits DB variant out of primary
--
-- Pre-flight checks (in order):
--   1. layer0.exercises has all named columns at expected types.
--   2. layer0.exercises UNIQUE (exercise_id, etl_version) constraint present.
--   3. Every equipment token referenced (in new primaries OR new substitute
--      groups) exists as an active row in layer0.equipment_items.
--   4. Active row exists for each of the 10 target exercise_ids.
--   5. None of the 10 are already at version '0B-v19.C' (idempotency).
--
-- Safe to re-run: idempotency via etl_version check. If already applied,
-- script logs NOTICEs and commits a no-op.
--
-- Does NOT touch:
--   - sport_exercise_map (no exercise_type change, no map rows need bumping)
--   - any other layer0 table

\set ON_ERROR_STOP on

BEGIN;

-- ─────────────────────────────────────────────────────────────────────────
-- 1. Pre-flight: column shape on layer0.exercises
-- ─────────────────────────────────────────────────────────────────────────
DO $$
DECLARE
  missing_cols TEXT[];
  expected RECORD;
BEGIN
  -- Expected (col_name, udt_name) pairs for columns we will read or write.
  FOR expected IN
    SELECT * FROM (VALUES
      ('exercise_id',                       'text'),
      ('exercise_name',                     'text'),
      ('exercise_type',                     'text'),
      ('movement_patterns',                 '_text'),
      ('primary_muscles',                   '_text'),
      ('secondary_muscles',                 '_text'),
      ('equipment_required',                '_text'),
      ('injury_flags_text',                 'text'),
      ('contraindicated_parts',             '_text'),
      ('contraindicated_conditions',        '_text'),
      ('equipment_substitutes',             'jsonb'),
      ('physical_proxies',                  'jsonb'),
      ('progression_exercise_id',           'text'),
      ('progression_exercise_name',         'text'),
      ('regression_exercise_id',            'text'),
      ('regression_exercise_name',          'text'),
      ('sport_count',                       'int4'),
      ('coaching_cues',                     'text'),
      ('terrain_required',                  '_text'),
      ('equipment_substitutes_structured',  'jsonb'),
      ('etl_version',                       'text'),
      ('etl_run_at',                        'timestamptz'),
      ('superseded_at',                     'timestamptz')
    ) AS t(col_name, expected_udt)
  LOOP
    IF NOT EXISTS (
      SELECT 1 FROM information_schema.columns
      WHERE table_schema = 'layer0'
        AND table_name   = 'exercises'
        AND column_name  = expected.col_name
        AND udt_name     = expected.expected_udt
    ) THEN
      missing_cols := array_append(missing_cols,
        format('%s (expected udt %s)', expected.col_name, expected.expected_udt));
    END IF;
  END LOOP;

  IF array_length(missing_cols, 1) > 0 THEN
    RAISE EXCEPTION 'Pre-flight FAILED: missing/mistyped columns: %', missing_cols;
  END IF;

  RAISE NOTICE 'Pre-flight 1/5: OK — column shape matches';
END $$;

-- ─────────────────────────────────────────────────────────────────────────
-- 2. Pre-flight: UNIQUE (exercise_id, etl_version) present
-- ─────────────────────────────────────────────────────────────────────────
DO $$
BEGIN
  IF NOT EXISTS (
    SELECT 1
    FROM pg_indexes
    WHERE schemaname = 'layer0'
      AND tablename  = 'exercises'
      AND indexdef LIKE '%UNIQUE%'
      AND indexdef LIKE '%(exercise_id, etl_version)%'
  ) THEN
    RAISE EXCEPTION
      'Pre-flight FAILED: UNIQUE (exercise_id, etl_version) index not found on layer0.exercises';
  END IF;

  RAISE NOTICE 'Pre-flight 2/5: OK — UNIQUE (exercise_id, etl_version) present';
END $$;

-- ─────────────────────────────────────────────────────────────────────────
-- 3. Stage Batch C updates in a temp table
-- ─────────────────────────────────────────────────────────────────────────
CREATE TEMP TABLE batch_c_updates (
  ex_id            TEXT PRIMARY KEY,
  new_equipment    TEXT[],
  new_subs_prepend JSONB
) ON COMMIT DROP;

INSERT INTO batch_c_updates (ex_id, new_equipment, new_subs_prepend) VALUES
  -- EX073 Threshold Intervals (Bike)
  ('EX073',
   ARRAY['Road bike'],
   '[
     {"substitute_text":"Mountain bike",  "equipment_required":[["Mountain bike"]],  "is_improvised":false},
     {"substitute_text":"Gravel bike",    "equipment_required":[["Gravel bike"]],    "is_improvised":false},
     {"substitute_text":"TT Bike",        "equipment_required":[["TT Bike"]],        "is_improvised":false},
     {"substitute_text":"Bike trainer",   "equipment_required":[["Bike trainer"]],   "is_improvised":false}
   ]'::jsonb),

  -- EX074 VO2 Max Intervals (Bike)
  ('EX074',
   ARRAY['Road bike'],
   '[
     {"substitute_text":"Mountain bike",  "equipment_required":[["Mountain bike"]],  "is_improvised":false},
     {"substitute_text":"Gravel bike",    "equipment_required":[["Gravel bike"]],    "is_improvised":false},
     {"substitute_text":"TT Bike",        "equipment_required":[["TT Bike"]],        "is_improvised":false},
     {"substitute_text":"Bike trainer",   "equipment_required":[["Bike trainer"]],   "is_improvised":false}
   ]'::jsonb),

  -- EX075 Sweet Spot Training (Bike)
  ('EX075',
   ARRAY['Road bike'],
   '[
     {"substitute_text":"Mountain bike",  "equipment_required":[["Mountain bike"]],  "is_improvised":false},
     {"substitute_text":"Gravel bike",    "equipment_required":[["Gravel bike"]],    "is_improvised":false},
     {"substitute_text":"TT Bike",        "equipment_required":[["TT Bike"]],        "is_improvised":false},
     {"substitute_text":"Bike trainer",   "equipment_required":[["Bike trainer"]],   "is_improvised":false}
   ]'::jsonb),

  -- EX117 Loaded Step-Down (Eccentric Box)
  -- Existing: [Plyo box, Dumbbell, Kettlebell, Weighted vest]. KB + Vest become substitutes.
  ('EX117',
   ARRAY['Plyo box', 'Dumbbell'],
   '[
     {"substitute_text":"KB Loaded Step-Down",   "equipment_required":[["Plyo box","Kettlebell"]],    "is_improvised":false},
     {"substitute_text":"Vested Loaded Step-Down","equipment_required":[["Plyo box","Weighted vest"]],"is_improvised":false}
   ]'::jsonb),

  -- EX119 Weighted Step-Up (High Box, Heavy Load)
  -- Existing: [Dumbbell, Barbell, Kettlebell, Weighted vest]. Plyo box was missing in
  -- equipment list (authoring fix). Barbell variant removed entirely — separate exercise.
  ('EX119',
   ARRAY['Plyo box', 'Dumbbell'],
   '[
     {"substitute_text":"KB Weighted Step-Up",    "equipment_required":[["Plyo box","Kettlebell"]],     "is_improvised":false},
     {"substitute_text":"Vested Weighted Step-Up","equipment_required":[["Plyo box","Weighted vest"]],  "is_improvised":false}
   ]'::jsonb),

  -- EX174 Aero / TT Position Hold
  -- Existing structured subs already contain "Road bike with clip-on aero bars" — keep as-is.
  -- Add the bike-trainer-in-aero variant only.
  ('EX174',
   ARRAY['TT Bike'],
   '[
     {"substitute_text":"On bike trainer in aero","equipment_required":[["TT Bike","Bike trainer"]],"is_improvised":false}
   ]'::jsonb),

  -- EX185 Climb Pacing & Cadence Management — Treadmill dropped entirely
  ('EX185',
   ARRAY['Road bike'],
   '[
     {"substitute_text":"Mountain bike",  "equipment_required":[["Mountain bike"]],  "is_improvised":false},
     {"substitute_text":"Gravel bike",    "equipment_required":[["Gravel bike"]],    "is_improvised":false},
     {"substitute_text":"TT Bike",        "equipment_required":[["TT Bike"]],        "is_improvised":false},
     {"substitute_text":"Bike trainer",   "equipment_required":[["Bike trainer"]],   "is_improvised":false}
   ]'::jsonb),

  -- EX186 High Cadence Spin Drill
  ('EX186',
   ARRAY['Road bike'],
   '[
     {"substitute_text":"Mountain bike",  "equipment_required":[["Mountain bike"]],  "is_improvised":false},
     {"substitute_text":"Gravel bike",    "equipment_required":[["Gravel bike"]],    "is_improvised":false},
     {"substitute_text":"TT Bike",        "equipment_required":[["TT Bike"]],        "is_improvised":false},
     {"substitute_text":"Bike trainer",   "equipment_required":[["Bike trainer"]],   "is_improvised":false}
   ]'::jsonb),

  -- EX197 Double Brick / Run-Bike-Run Pacing Drill
  -- terrain_required already carries "Road or Trail" from prior ETL split; we don't touch it.
  ('EX197',
   ARRAY['Road bike'],
   '[
     {"substitute_text":"Mountain bike",  "equipment_required":[["Mountain bike"]],  "is_improvised":false},
     {"substitute_text":"Gravel bike",    "equipment_required":[["Gravel bike"]],    "is_improvised":false},
     {"substitute_text":"TT Bike",        "equipment_required":[["TT Bike"]],        "is_improvised":false},
     {"substitute_text":"Bike trainer",   "equipment_required":[["Bike trainer"]],   "is_improvised":false}
   ]'::jsonb),

  -- EX229 Bench Press (Barbell / DB)
  -- DB variant split out as substitute; primary keeps Bench press station shape.
  ('EX229',
   ARRAY['Barbell', 'Bench', 'Squat rack'],
   '[
     {"substitute_text":"On bench press station","equipment_required":[["Barbell","Bench press rack"]],"is_improvised":false},
     {"substitute_text":"DB Bench Press",        "equipment_required":[["Dumbbell","Bench"]],          "is_improvised":false}
   ]'::jsonb);

-- ─────────────────────────────────────────────────────────────────────────
-- 4. Pre-flight: every equipment token in scope exists in equipment_items
-- ─────────────────────────────────────────────────────────────────────────
DO $$
DECLARE
  missing_tokens TEXT[];
  tokens_in_scope TEXT[];
  r RECORD;
BEGIN
  -- Collect all distinct tokens from new_equipment + every group in new_subs_prepend.
  WITH primary_tokens AS (
    SELECT DISTINCT unnest(new_equipment) AS token FROM batch_c_updates
  ),
  sub_tokens AS (
    SELECT DISTINCT inner_token AS token
    FROM batch_c_updates,
         jsonb_array_elements(new_subs_prepend) AS sub,
         jsonb_array_elements(sub->'equipment_required') AS group_arr,
         jsonb_array_elements_text(group_arr) AS inner_token
  )
  SELECT array_agg(DISTINCT token) INTO tokens_in_scope
  FROM (SELECT token FROM primary_tokens UNION SELECT token FROM sub_tokens) t;

  -- Find any tokens not present in equipment_items active rows.
  SELECT array_agg(t.token ORDER BY t.token)
    INTO missing_tokens
  FROM unnest(tokens_in_scope) AS t(token)
  WHERE NOT EXISTS (
    SELECT 1 FROM layer0.equipment_items ei
    WHERE ei.canonical_name = t.token
      AND ei.superseded_at IS NULL
  );

  IF array_length(missing_tokens, 1) > 0 THEN
    RAISE EXCEPTION
      'Pre-flight FAILED: equipment tokens not found as active rows in layer0.equipment_items: %',
      missing_tokens;
  END IF;

  RAISE NOTICE 'Pre-flight 3/5: OK — % distinct equipment tokens all present',
    array_length(tokens_in_scope, 1);
END $$;

-- ─────────────────────────────────────────────────────────────────────────
-- 5. Pre-flight: active row exists for each target exercise_id
-- ─────────────────────────────────────────────────────────────────────────
DO $$
DECLARE
  missing_ids TEXT[];
BEGIN
  SELECT array_agg(b.ex_id ORDER BY b.ex_id)
    INTO missing_ids
  FROM batch_c_updates b
  WHERE NOT EXISTS (
    SELECT 1 FROM layer0.exercises e
    WHERE e.exercise_id = b.ex_id
      AND e.superseded_at IS NULL
  );

  IF array_length(missing_ids, 1) > 0 THEN
    RAISE EXCEPTION
      'Pre-flight FAILED: no active row for exercise_ids: %', missing_ids;
  END IF;

  RAISE NOTICE 'Pre-flight 4/5: OK — active rows present for all 10 target exercises';
END $$;

-- ─────────────────────────────────────────────────────────────────────────
-- 6. Pre-flight: idempotency — if all 10 already at '0B-v19.C', no-op exit
-- ─────────────────────────────────────────────────────────────────────────
DO $$
DECLARE
  already_at_c INTEGER;
BEGIN
  SELECT COUNT(*) INTO already_at_c
  FROM layer0.exercises e
  JOIN batch_c_updates b ON b.ex_id = e.exercise_id
  WHERE e.superseded_at IS NULL
    AND e.etl_version = '0B-v19.C';

  IF already_at_c = 10 THEN
    RAISE NOTICE 'Pre-flight 5/5: All 10 exercises already at 0B-v19.C — script is a no-op';
  ELSIF already_at_c > 0 AND already_at_c < 10 THEN
    RAISE EXCEPTION
      'Pre-flight FAILED: partial Batch C state detected — % of 10 exercises already at 0B-v19.C. Investigate before re-running.',
      already_at_c;
  ELSE
    RAISE NOTICE 'Pre-flight 5/5: OK — none of the 10 yet at 0B-v19.C; proceeding to migrate';
  END IF;
END $$;

-- ─────────────────────────────────────────────────────────────────────────
-- 7. Migration: per-exercise supersede + reinsert with merged substitutes
-- ─────────────────────────────────────────────────────────────────────────
DO $$
DECLARE
  r          RECORD;
  src_row    layer0.exercises%ROWTYPE;
  bucket_b   JSONB;   -- existing non-improvised
  bucket_c   JSONB;   -- existing improvised
  merged     JSONB;
  updated_count INTEGER := 0;
BEGIN
  FOR r IN SELECT * FROM batch_c_updates ORDER BY ex_id LOOP

    SELECT * INTO src_row
    FROM layer0.exercises
    WHERE exercise_id = r.ex_id
      AND superseded_at IS NULL
    LIMIT 1;

    IF src_row.etl_version = '0B-v19.C' THEN
      RAISE NOTICE '% already at 0B-v19.C — skipping', r.ex_id;
      CONTINUE;
    END IF;

    -- Split existing structured subs into 3 buckets:
    --   A: r.new_subs_prepend            (new equipment variants)
    --   B: existing where is_improvised = false
    --   C: existing where is_improvised = true (incl. NULL treated as false; safe-guard for legacy data)
    SELECT COALESCE(jsonb_agg(elem ORDER BY ord), '[]'::jsonb)
      INTO bucket_b
    FROM jsonb_array_elements(
           COALESCE(src_row.equipment_substitutes_structured, '[]'::jsonb)
         ) WITH ORDINALITY AS t(elem, ord)
    WHERE COALESCE((elem->>'is_improvised')::boolean, FALSE) = FALSE;

    SELECT COALESCE(jsonb_agg(elem ORDER BY ord), '[]'::jsonb)
      INTO bucket_c
    FROM jsonb_array_elements(
           COALESCE(src_row.equipment_substitutes_structured, '[]'::jsonb)
         ) WITH ORDINALITY AS t(elem, ord)
    WHERE COALESCE((elem->>'is_improvised')::boolean, FALSE) = TRUE;

    merged := r.new_subs_prepend || bucket_b || bucket_c;

    -- Supersede current active row.
    UPDATE layer0.exercises
       SET superseded_at = NOW()
     WHERE exercise_id = r.ex_id
       AND superseded_at IS NULL;

    -- Reinsert at new version.
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
    ) VALUES (
      src_row.exercise_id, src_row.exercise_name, src_row.exercise_type,
      src_row.movement_patterns, src_row.primary_muscles, src_row.secondary_muscles,
      r.new_equipment, src_row.injury_flags_text,
      src_row.contraindicated_parts, src_row.contraindicated_conditions,
      src_row.equipment_substitutes, src_row.physical_proxies,
      src_row.progression_exercise_id, src_row.progression_exercise_name,
      src_row.regression_exercise_id, src_row.regression_exercise_name,
      src_row.sport_count, src_row.coaching_cues,
      src_row.terrain_required, merged,
      '0B-v19.C', NOW()
    );

    updated_count := updated_count + 1;
    RAISE NOTICE
      '% — equipment_required %, structured_subs count % (was %)',
      r.ex_id,
      r.new_equipment,
      jsonb_array_length(merged),
      jsonb_array_length(COALESCE(src_row.equipment_substitutes_structured, '[]'::jsonb));
  END LOOP;

  RAISE NOTICE 'Batch C: % exercises migrated to 0B-v19.C', updated_count;
END $$;

-- ─────────────────────────────────────────────────────────────────────────
-- 8. Post-flight verification
-- ─────────────────────────────────────────────────────────────────────────
DO $$
DECLARE
  active_at_c        INTEGER;
  total_active       INTEGER;
  duplicate_active   INTEGER;
BEGIN
  SELECT COUNT(*) INTO active_at_c
  FROM layer0.exercises
  WHERE etl_version = '0B-v19.C'
    AND superseded_at IS NULL;

  SELECT COUNT(*) INTO total_active
  FROM layer0.exercises
  WHERE superseded_at IS NULL;

  SELECT COUNT(*) INTO duplicate_active
  FROM (
    SELECT exercise_id
    FROM layer0.exercises
    WHERE superseded_at IS NULL
    GROUP BY exercise_id
    HAVING COUNT(*) > 1
  ) s;

  RAISE NOTICE 'Post-flight: rows at 0B-v19.C (active) = %', active_at_c;
  RAISE NOTICE 'Post-flight: total active exercises    = % (expected unchanged at 159)', total_active;
  RAISE NOTICE 'Post-flight: duplicate-active rows     = % (expected 0)', duplicate_active;

  IF active_at_c <> 10 THEN
    RAISE EXCEPTION 'Post-flight FAILED: expected 10 rows at 0B-v19.C, got %', active_at_c;
  END IF;

  IF total_active <> 159 THEN
    RAISE EXCEPTION 'Post-flight FAILED: total active count changed (% vs 159)', total_active;
  END IF;

  IF duplicate_active > 0 THEN
    RAISE EXCEPTION 'Post-flight FAILED: % exercise_ids have multiple active rows', duplicate_active;
  END IF;

  RAISE NOTICE 'Post-flight: OK';
END $$;

COMMIT;

-- ─────────────────────────────────────────────────────────────────────────
-- 9. Optional manual spot-check after commit (for paste-back)
--    Uncomment to see per-row state.
-- ─────────────────────────────────────────────────────────────────────────
-- SELECT exercise_id, equipment_required, jsonb_array_length(equipment_substitutes_structured) AS subs_count, etl_version
-- FROM layer0.exercises
-- WHERE exercise_id IN ('EX073','EX074','EX075','EX117','EX119','EX174','EX185','EX186','EX197','EX229')
--   AND superseded_at IS NULL
-- ORDER BY exercise_id;
