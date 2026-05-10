-- cleanup_sport_exercise_map_header_residue.sql
-- One-shot DELETE: removes the parser-bug row in layer0.sport_exercise_map
-- where sport_name = 'Sport'. This is the column header literal "Sport"
-- leaking through as a data row.
--
-- ROOT CAUSE:
--   AR_Exercise_Database_v19.xlsx Sport-Exercise Map sheet structure:
--     Row 1: title banner cell ("ADVENTURE RACING — SPORT-EXERCISE CROSS REFERENCE")
--     Row 2: column headers ("Exercise ID", "Exercise Name", "Exercise Type",
--            "Sport", "Sport Relevance Note", "Priority")
--     Row 3+: actual data
--
--   The current 0B sport_exercise_map extractor reads row 1 as headers and
--   row 2 as data, producing a junk row whose sport_name is the literal
--   string "Sport" (and exercise_id is "Exercise ID", etc.). Other column
--   header literals leak into the same row.
--
--   The Exercise Master sheet has the same banner+header layout, but its
--   junk row is filtered downstream because exercise_id = 'Exercise ID'
--   fails the EX-prefix validator. Sport-Exercise Map has no such
--   defensive filter on sport_name.
--
-- PERMANENT FIX (REQUIRED IN ETL EXTRACTOR — separate from this script):
--   Update the over-there ETL config so both Exercise Master and
--   Sport-Exercise Map extractors:
--     - Skip row 1 (banner row, single-cell title)
--     - Use row 2 as header row
--     - Read data starting at row 3
--   Avoid relying on downstream type validators (exercise_id EX-prefix
--   filter) to silently drop junk header rows. Apply the offset uniformly.
--
-- This script is a one-shot DB cleanup until the extractor fix lands.
-- After the fix, this script becomes a no-op (no matching rows). Safe to
-- re-run regardless.
--
-- Idempotent: filter is data-driven; running on a clean DB matches zero rows.

BEGIN;

DELETE FROM layer0.sport_exercise_map
WHERE sport_name = 'Sport';

-- ── Verify ──────────────────────────────────────────────────────────────────

DO $$
DECLARE
  residual_count INT;
BEGIN
  SELECT COUNT(*)
    INTO residual_count
    FROM layer0.sport_exercise_map
    WHERE sport_name = 'Sport';

  IF residual_count <> 0 THEN
    RAISE EXCEPTION 'cleanup_sport_exercise_map_header_residue: % rows still match sport_name = ''Sport''', residual_count;
  END IF;

  RAISE NOTICE 'cleanup_sport_exercise_map_header_residue: OK — sport_name = ''Sport'' rows removed';
END $$;

COMMIT;
