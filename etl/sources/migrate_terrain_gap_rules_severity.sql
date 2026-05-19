-- migrate_terrain_gap_rules_severity.sql
-- Re-classifies deployed `gap_severity='partial'` rows in
-- `layer0.terrain_gap_rules` to the spec-canonical 4-band enum per
-- `Layer2B_Spec.md` §7 (`critical` | `high` | `medium` | `low` for
-- bridgeable gaps; `unbridgeable` stays untouched; `undefined` is a
-- runtime fallback, not stored).
--
-- Fidelity bands (driver = `proxy_fidelity` set by
-- `populate_terrain_gap_rules.sql`):
--
--   proxy_fidelity >= 0.70   →  low       (small gap; high transfer)
--   proxy_fidelity 0.50–0.69 →  medium    (meaningful but partial)
--   proxy_fidelity 0.40–0.49 →  high      (big gap; modest transfer)
--   proxy_fidelity <  0.40   →  critical  (severe gap; minimal transfer)
--
-- 11 deployed rows are reclassified; 1 unbridgeable row (TRN-013 → NULL)
-- is left untouched. Existing populate rows retain
-- etl_version='0C-v2.0-r2'; no version bump needed for an in-place enum
-- refinement.
--
-- Safe to re-run: WHERE clause filters on `gap_severity = 'partial'` so
-- the UPDATE no-ops after the first successful run. Verification block
-- asserts zero remaining `partial` rows.

BEGIN;

UPDATE layer0.terrain_gap_rules
SET gap_severity = CASE
  WHEN proxy_fidelity >= 0.70 THEN 'low'
  WHEN proxy_fidelity >= 0.50 THEN 'medium'
  WHEN proxy_fidelity >= 0.40 THEN 'high'
  ELSE 'critical'
END
WHERE gap_severity = 'partial'
  AND superseded_at IS NULL;

DO $$
DECLARE
  partial_remaining INT;
BEGIN
  SELECT COUNT(*) INTO partial_remaining
  FROM layer0.terrain_gap_rules
  WHERE gap_severity = 'partial'
    AND superseded_at IS NULL;

  IF partial_remaining > 0 THEN
    RAISE EXCEPTION
      'migrate_terrain_gap_rules_severity: % rows still have severity=partial',
      partial_remaining;
  END IF;

  RAISE NOTICE
    'migrate_terrain_gap_rules_severity: OK — all partial severity values reclassified';
END $$;

COMMIT;
