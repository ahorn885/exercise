-- migrate_toggles_v3_columns.sql
-- Adds also_satisfies TEXT[] + gated_discipline_ids TEXT[] to
-- layer0.sport_specific_gear_toggles, then populates active rows with the
-- known cases from Vocabulary_Audit_v2.md §4.
--
-- Why these fields exist (Layer2C_Spec.md §5.1 + §6 + §8.3 / D-73 Phase 2.4-Prep):
--
--   also_satisfies — Transitive-implication chains. Single known case:
--     `Climbing — roped` ALSO_SATISFIES `Rappelling / abseiling`. Athletes
--     with full roped setup automatically pass rappelling-gated exercises.
--     Per Layer2C_Spec.md §6: no cascade beyond one hop. The single case is
--     v1; future toggles can extend this list as new sports come online.
--
--   gated_discipline_ids — Reverse mapping of disciplines whose exercise
--     pool depends on this toggle being ON. Used by Layer 2C §8.3 to fire
--     the `toggle_off_for_discipline` coaching flag. Empty list = toggle
--     gates no disciplines (or none yet enumerated).
--
--     Andy 2026-05-19 picked (b) structured-column over (a) hard-coded
--     mapping in 2C code (Layer2C_Spec.md §8.3 Decision Point + Open Item
--     2C-2). Tradeoff: structured carries traceability + survives spec
--     evolution; hard-coded would have been faster but accumulates as tech
--     debt across non-AR sports.
--
-- 2C contract:
--   Layer 2C reads both columns at runtime per §5.1 Decision Point (A)
--   runtime-lookup pick (Andy 2026-05-19). The single SELECT against
--   sport_specific_gear_toggles for the active etl_version pulls all four
--   fields (paired_equipment_categories, also_satisfies,
--   gated_discipline_ids, plus toggle_name + display_label). 11 rows;
--   indexed by UNIQUE (toggle_name, etl_version).
--
-- Data population (this script):
--   Three active toggle rows updated. Mapping per Vocabulary_Audit_v2.md
--   §4.2 + §6 (Vocab Audit Section 1 + Section 4) + Layer2A spec discipline
--   IDs (D-012 Rock Climbing, D-013 Abseiling, D-017 Snowshoeing):
--
--     toggle_name              | also_satisfies                | gated_discipline_ids
--     -------------------------|-------------------------------|---------------------
--     Climbing — roped         | {'Rappelling / abseiling'}    | {'D-012'}
--     Rappelling / abseiling   | {}                            | {'D-013'}
--     Snowshoeing setup        | {}                            | {'D-017'}
--
--   Other toggles (ski setups, paddle, MTB, etc.) ship with empty lists
--   for both fields. Populate further as new sports come online.
--
-- etl_version: no version bump here — this is a schema-only migration
--   with data backfill against existing active rows. The first ETL re-run
--   after this migration produces NEW versioned rows already carrying
--   these values (etl/layer0/extractors/vocabulary.py _parse_gear_toggles
--   now emits them from code-side constants).
--
-- Safe to re-run: ADD COLUMN IF NOT EXISTS + UPDATEs are idempotent.

BEGIN;

-- ── 1. Schema migration ────────────────────────────────────────────────────

ALTER TABLE layer0.sport_specific_gear_toggles
  ADD COLUMN IF NOT EXISTS also_satisfies TEXT[];

ALTER TABLE layer0.sport_specific_gear_toggles
  ADD COLUMN IF NOT EXISTS gated_discipline_ids TEXT[];

-- ── 2. Data population on active rows ──────────────────────────────────────

UPDATE layer0.sport_specific_gear_toggles
   SET also_satisfies       = ARRAY['Rappelling / abseiling'],
       gated_discipline_ids = ARRAY['D-012']
 WHERE toggle_name  = 'Climbing — roped'
   AND superseded_at IS NULL;

UPDATE layer0.sport_specific_gear_toggles
   SET also_satisfies       = ARRAY[]::TEXT[],
       gated_discipline_ids = ARRAY['D-013']
 WHERE toggle_name  = 'Rappelling / abseiling'
   AND superseded_at IS NULL;

UPDATE layer0.sport_specific_gear_toggles
   SET also_satisfies       = ARRAY[]::TEXT[],
       gated_discipline_ids = ARRAY['D-017']
 WHERE toggle_name  = 'Snowshoeing setup'
   AND superseded_at IS NULL;

-- ── 3. Verify ──────────────────────────────────────────────────────────────

DO $$
DECLARE
  also_col_exists BOOLEAN;
  gated_col_exists BOOLEAN;
  climbing_also_count INTEGER;
  climbing_gated_count INTEGER;
BEGIN
  SELECT EXISTS (
    SELECT 1
      FROM information_schema.columns
     WHERE table_schema = 'layer0'
       AND table_name   = 'sport_specific_gear_toggles'
       AND column_name  = 'also_satisfies'
  ) INTO also_col_exists;

  SELECT EXISTS (
    SELECT 1
      FROM information_schema.columns
     WHERE table_schema = 'layer0'
       AND table_name   = 'sport_specific_gear_toggles'
       AND column_name  = 'gated_discipline_ids'
  ) INTO gated_col_exists;

  IF NOT also_col_exists THEN
    RAISE EXCEPTION 'migrate_toggles_v3_columns: also_satisfies column not found';
  END IF;

  IF NOT gated_col_exists THEN
    RAISE EXCEPTION 'migrate_toggles_v3_columns: gated_discipline_ids column not found';
  END IF;

  -- Active 'Climbing — roped' row should carry both fields populated. If
  -- the row doesn't exist (vocabulary md hasn't been loaded yet) the
  -- UPDATEs above no-op silently — surface a NOTICE rather than fail so
  -- this migration is safe to run before the first ETL.
  SELECT COALESCE(array_length(also_satisfies, 1), 0)
    INTO climbing_also_count
    FROM layer0.sport_specific_gear_toggles
   WHERE toggle_name = 'Climbing — roped'
     AND superseded_at IS NULL
   LIMIT 1;

  SELECT COALESCE(array_length(gated_discipline_ids, 1), 0)
    INTO climbing_gated_count
    FROM layer0.sport_specific_gear_toggles
   WHERE toggle_name = 'Climbing — roped'
     AND superseded_at IS NULL
   LIMIT 1;

  IF climbing_also_count IS NULL THEN
    RAISE NOTICE 'migrate_toggles_v3_columns: no active row for Climbing — roped (ETL not yet run? skipping population check)';
  ELSE
    IF climbing_also_count <> 1 THEN
      RAISE EXCEPTION 'migrate_toggles_v3_columns: Climbing — roped should also_satisfy 1 entry, got %', climbing_also_count;
    END IF;
    IF climbing_gated_count <> 1 THEN
      RAISE EXCEPTION 'migrate_toggles_v3_columns: Climbing — roped should gate 1 discipline, got %', climbing_gated_count;
    END IF;
  END IF;

  RAISE NOTICE 'migrate_toggles_v3_columns: OK — columns added + active rows populated';
END $$;

COMMIT;
