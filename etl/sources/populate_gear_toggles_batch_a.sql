-- populate_gear_toggles_batch_a.sql
-- Two changes to layer0.sport_specific_gear_toggles:
--   1. Populate Climbing — roped's also_satisfies = ['Rappelling / abseiling']
--   2. Supersede the Bouldering toggle row (no replacement)
--
-- Pairs with: migrate_gear_toggles_also_satisfies.sql (must run first).
-- Source: Vocab_Audit_v2_Batch_A_Patch.md §4.1.
-- Driver: Layer 1 Node 2C (Equipment Mapper) design session.
--
-- Why supersede Bouldering rather than DELETE:
--   Bouldering is not a sport in Layer 0B v19. Zero exercises mapped,
--   zero exercises require Bouldering kit. Toggle has no functional role
--   in the current DB. Supersede preserves audit trail for future review
--   if bouldering is reintroduced.
--
-- Why direct UPDATE for also_satisfies (rather than supersede + reinsert):
--   Filling in a new column added by schema migration. The other fields
--   on Climbing — roped (display_label, description, paired_equipment_categories)
--   are unchanged. Direct UPDATE matches the pattern established by
--   populate_substitutes_structured.py — when a new column lands, populate
--   in place rather than versioning a row mutation.
--
-- Toggle name strings in this script:
--   'Climbing — roped'           (em-dash U+2014 with surrounding spaces)
--   'Rappelling / abseiling'     (regular slash with surrounding spaces)
--   'Bouldering'                 (single word)
--   These must match the populated layer0.sport_specific_gear_toggles
--   exactly. If ETL has normalized any of these, this script's WHERE
--   clauses will return zero rows. The verify block will catch this.
--
-- Idempotent: WHERE clauses guard against double-applying. Re-running
-- with no matching active rows is a no-op (verify block handles "already
-- applied" gracefully).

BEGIN;

-- ── 1. Populate Climbing — roped also_satisfies ─────────────────────────────

UPDATE layer0.sport_specific_gear_toggles
SET also_satisfies = ARRAY['Rappelling / abseiling']
WHERE toggle_name = 'Climbing — roped'
  AND superseded_at IS NULL
  AND (also_satisfies IS NULL OR also_satisfies = ARRAY[]::TEXT[]);

-- ── 2. Supersede the Bouldering toggle ──────────────────────────────────────

UPDATE layer0.sport_specific_gear_toggles
SET superseded_at = NOW()
WHERE toggle_name = 'Bouldering'
  AND superseded_at IS NULL;

-- ── 3. Verify ──────────────────────────────────────────────────────────────

DO $$
DECLARE
  roped_satisfies   TEXT[];
  roped_active      INT;
  bouldering_active INT;
BEGIN
  -- Climbing — roped: must exist active and have Rappelling in also_satisfies
  SELECT COUNT(*)
    INTO roped_active
    FROM layer0.sport_specific_gear_toggles
    WHERE toggle_name = 'Climbing — roped'
      AND superseded_at IS NULL;

  IF roped_active = 0 THEN
    RAISE EXCEPTION 'populate_gear_toggles_batch_a: no active Climbing — roped row found. Possible toggle_name string mismatch (em-dash vs hyphen?).';
  END IF;

  SELECT also_satisfies
    INTO roped_satisfies
    FROM layer0.sport_specific_gear_toggles
    WHERE toggle_name = 'Climbing — roped'
      AND superseded_at IS NULL
    LIMIT 1;

  IF roped_satisfies IS NULL OR NOT ('Rappelling / abseiling' = ANY(roped_satisfies)) THEN
    RAISE EXCEPTION 'populate_gear_toggles_batch_a: Climbing — roped also_satisfies not populated correctly. Got: %', roped_satisfies;
  END IF;

  -- Bouldering: must have zero active rows
  SELECT COUNT(*)
    INTO bouldering_active
    FROM layer0.sport_specific_gear_toggles
    WHERE toggle_name = 'Bouldering'
      AND superseded_at IS NULL;

  IF bouldering_active <> 0 THEN
    RAISE EXCEPTION 'populate_gear_toggles_batch_a: Bouldering still has % active row(s); expected 0', bouldering_active;
  END IF;

  RAISE NOTICE 'populate_gear_toggles_batch_a: OK — Climbing — roped implies Rappelling / abseiling; Bouldering superseded';
END $$;

COMMIT;
