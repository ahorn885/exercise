-- spec_drift_sweep_introspection.sql
-- Purpose:
--   Produce an authoritative dump of the deployed Layer 0 schema so we can
--   compare against Layer0_ETL_Spec_v3.md and the Batch A/B patches and
--   produce a drift report. Read-only.
--
-- How to run:
--   psql $DATABASE_URL -f spec_drift_sweep_introspection.sql > layer0_deployed_state.txt
--
-- Then paste layer0_deployed_state.txt back in the next message.
--
-- What this answers:
--   - Which tables exist in layer0
--   - Every column's name, data_type, udt_name (TEXT vs TEXT[] visible here:
--     text = TEXT, _text = TEXT[], jsonb = JSONB, etc.), nullability, default
--   - All indexes (incl. partial / GIN / etc.)
--   - All PK + UNIQUE constraints with their column ordering
--   - Active vs total row counts (for tables that carry superseded_at)
--   - Distinct etl_version values per versioned table
--
-- Safe to re-run. No writes.

\pset pager off
\pset format aligned
\pset null '∅'

\echo ''
\echo '##############################################################'
\echo '# 1. TABLES IN layer0'
\echo '##############################################################'
SELECT table_name
FROM information_schema.tables
WHERE table_schema = 'layer0'
  AND table_type = 'BASE TABLE'
ORDER BY table_name;

\echo ''
\echo '##############################################################'
\echo '# 2. COLUMNS — every layer0 table, in ordinal position'
\echo '#    Read udt_name to distinguish array vs scalar:'
\echo '#      text      = TEXT (scalar)'
\echo '#      _text     = TEXT[] (array)'
\echo '#      jsonb     = JSONB'
\echo '#      timestamp = timestamp without time zone'
\echo '#      timestamptz = timestamp with time zone'
\echo '##############################################################'
SELECT
  table_name,
  ordinal_position AS pos,
  column_name,
  data_type,
  udt_name,
  is_nullable AS nullable,
  COALESCE(column_default, '') AS default_expr
FROM information_schema.columns
WHERE table_schema = 'layer0'
ORDER BY table_name, ordinal_position;

\echo ''
\echo '##############################################################'
\echo '# 3. INDEXES (all layer0 tables)'
\echo '##############################################################'
SELECT
  tablename,
  indexname,
  indexdef
FROM pg_indexes
WHERE schemaname = 'layer0'
ORDER BY tablename, indexname;

\echo ''
\echo '##############################################################'
\echo '# 4. PRIMARY KEY + UNIQUE CONSTRAINTS (with column ordering)'
\echo '##############################################################'
SELECT
  tc.table_name,
  tc.constraint_name,
  tc.constraint_type,
  string_agg(kcu.column_name, ', ' ORDER BY kcu.ordinal_position) AS columns
FROM information_schema.table_constraints tc
JOIN information_schema.key_column_usage kcu
  ON tc.constraint_name = kcu.constraint_name
 AND tc.table_schema    = kcu.table_schema
WHERE tc.table_schema = 'layer0'
  AND tc.constraint_type IN ('PRIMARY KEY', 'UNIQUE')
GROUP BY tc.table_name, tc.constraint_name, tc.constraint_type
ORDER BY tc.table_name, tc.constraint_type, tc.constraint_name;

\echo ''
\echo '##############################################################'
\echo '# 5. FOREIGN KEY CONSTRAINTS'
\echo '##############################################################'
SELECT
  tc.table_name,
  tc.constraint_name,
  string_agg(kcu.column_name, ', ' ORDER BY kcu.ordinal_position) AS columns,
  ccu.table_name  AS references_table,
  string_agg(DISTINCT ccu.column_name, ', ') AS references_columns
FROM information_schema.table_constraints tc
JOIN information_schema.key_column_usage kcu
  ON tc.constraint_name = kcu.constraint_name
 AND tc.table_schema    = kcu.table_schema
JOIN information_schema.constraint_column_usage ccu
  ON tc.constraint_name = ccu.constraint_name
 AND tc.table_schema    = ccu.table_schema
WHERE tc.table_schema = 'layer0'
  AND tc.constraint_type = 'FOREIGN KEY'
GROUP BY tc.table_name, tc.constraint_name, ccu.table_name
ORDER BY tc.table_name, tc.constraint_name;

\echo ''
\echo '##############################################################'
\echo '# 6. ROW COUNTS — active vs total (versioned tables only)'
\echo '#    Non-versioned tables report total rows only.'
\echo '##############################################################'
DO $$
DECLARE
  r RECORD;
  active_count BIGINT;
  total_count  BIGINT;
BEGIN
  FOR r IN
    SELECT t.table_name,
           EXISTS (
             SELECT 1 FROM information_schema.columns c
             WHERE c.table_schema = 'layer0'
               AND c.table_name   = t.table_name
               AND c.column_name  = 'superseded_at'
           ) AS has_versioning
    FROM information_schema.tables t
    WHERE t.table_schema = 'layer0'
      AND t.table_type   = 'BASE TABLE'
    ORDER BY t.table_name
  LOOP
    IF r.has_versioning THEN
      EXECUTE format(
        'SELECT COUNT(*) FROM layer0.%I WHERE superseded_at IS NULL',
        r.table_name
      ) INTO active_count;
      EXECUTE format('SELECT COUNT(*) FROM layer0.%I', r.table_name) INTO total_count;
      RAISE NOTICE '% — active=%, total=%', r.table_name, active_count, total_count;
    ELSE
      EXECUTE format('SELECT COUNT(*) FROM layer0.%I', r.table_name) INTO total_count;
      RAISE NOTICE '% — rows=% (no superseded_at)', r.table_name, total_count;
    END IF;
  END LOOP;
END $$;

\echo ''
\echo '##############################################################'
\echo '# 7. ETL_VERSION DISTRIBUTION (where etl_version column exists)'
\echo '#    Per-version row counts, active-only.'
\echo '##############################################################'
DO $$
DECLARE
  r RECORD;
  v RECORD;
  q TEXT;
BEGIN
  FOR r IN
    SELECT t.table_name
    FROM information_schema.tables t
    WHERE t.table_schema = 'layer0'
      AND t.table_type   = 'BASE TABLE'
      AND EXISTS (
        SELECT 1 FROM information_schema.columns c
        WHERE c.table_schema = 'layer0'
          AND c.table_name   = t.table_name
          AND c.column_name  = 'etl_version'
      )
    ORDER BY t.table_name
  LOOP
    RAISE NOTICE '--- % ---', r.table_name;
    q := format(
      'SELECT etl_version, COUNT(*) AS active_rows
       FROM layer0.%I
       WHERE %s
       GROUP BY etl_version
       ORDER BY etl_version',
      r.table_name,
      CASE
        WHEN EXISTS (
          SELECT 1 FROM information_schema.columns c
          WHERE c.table_schema = 'layer0'
            AND c.table_name   = r.table_name
            AND c.column_name  = 'superseded_at'
        ) THEN 'superseded_at IS NULL'
        ELSE 'TRUE'
      END
    );
    FOR v IN EXECUTE q LOOP
      RAISE NOTICE '  % : %', v.etl_version, v.active_rows;
    END LOOP;
  END LOOP;
END $$;

\echo ''
\echo '##############################################################'
\echo '# 8. SPOT-CHECK — selected columns of high interest'
\echo '#    Direct answers to Open Item R and other lingering questions.'
\echo '##############################################################'
\echo ''
\echo '-- 8a. exercises: primary_muscles / secondary_muscles types'
SELECT column_name, data_type, udt_name, is_nullable
FROM information_schema.columns
WHERE table_schema = 'layer0'
  AND table_name   = 'exercises'
  AND column_name IN ('primary_muscles', 'secondary_muscles');

\echo ''
\echo '-- 8b. exercises: substitutes columns (legacy + structured) — both present?'
SELECT column_name, data_type, udt_name, is_nullable
FROM information_schema.columns
WHERE table_schema = 'layer0'
  AND table_name   = 'exercises'
  AND column_name IN (
    'equipment_substitutes',
    'equipment_substitutes_standard',
    'equipment_substitutes_improvised',
    'equipment_substitutes_structured'
  )
ORDER BY column_name;

\echo ''
\echo '-- 8c. exercises: terrain_required, physical_proxies, contraindicated_*'
SELECT column_name, data_type, udt_name, is_nullable
FROM information_schema.columns
WHERE table_schema = 'layer0'
  AND table_name   = 'exercises'
  AND column_name IN (
    'terrain_required',
    'physical_proxies',
    'contraindicated_parts',
    'contraindicated_conditions',
    'movement_patterns',
    'equipment_required',
    'coaching_cues'
  )
ORDER BY column_name;

\echo ''
\echo '-- 8d. sport_exercise_map: confirm denormalized exercise_type column'
SELECT column_name, data_type, udt_name, is_nullable
FROM information_schema.columns
WHERE table_schema = 'layer0'
  AND table_name   = 'sport_exercise_map'
ORDER BY ordinal_position;

\echo ''
\echo '-- 8e. sport_specific_gear_toggles: confirm also_satisfies column from Batch A'
SELECT column_name, data_type, udt_name, is_nullable
FROM information_schema.columns
WHERE table_schema = 'layer0'
  AND table_name   = 'sport_specific_gear_toggles'
ORDER BY ordinal_position;

\echo ''
\echo '-- 8f. discipline_technique_foci: confirm Batch B table shape'
SELECT column_name, data_type, udt_name, is_nullable
FROM information_schema.columns
WHERE table_schema = 'layer0'
  AND table_name   = 'discipline_technique_foci'
ORDER BY ordinal_position;

\echo ''
\echo '##############################################################'
\echo '# 9. SANITY CHECK — duplicate-active-row detection'
\echo '#    Any row with the same business key active twice = bug.'
\echo '#    Currently checks exercises.exercise_id.'
\echo '##############################################################'
SELECT
  exercise_id,
  COUNT(*) AS active_rows
FROM layer0.exercises
WHERE superseded_at IS NULL
GROUP BY exercise_id
HAVING COUNT(*) > 1
ORDER BY exercise_id;

\echo ''
\echo '##############################################################'
\echo '# END OF INTROSPECTION'
\echo '##############################################################'
