-- dedupe_layer0_equipment_items.sql
-- Track 1 (Locations Consolidation) slice A0 — collapse duplicate / case-variant
-- ACTIVE rows in layer0.equipment_items so the equipment picker AND Layer 2C
-- resolve every exercise's equipment_required against ONE canonical name.
--
-- Why (Andy's dump 2026-06-05, already `WHERE superseded_at IS NULL`):
--   (1) Exact duplicates — same canonical_name across multiple etl_versions,
--       none superseded. The table's UNIQUE (canonical_name, etl_version)
--       permits this; the ETL added a newer version without superseding the
--       prior one. ~15 items (Treadmill, Cable machine, Road bike, Kayak,
--       Packraft, Hangboard, Plyo box, Pull buoy, Resistance band, Rice bucket,
--       Canoe, Gravel bike, SUP, Weighted vest, Bike trainer).
--   (2) Case variants — distinct canonical_name rows differing only by case:
--       'Pinch Block'/'Pinch block', 'Trekking Poles'/'Trekking poles',
--       'Wrist Roller'/'Wrist roller'. Because they are different strings, an
--       exercise whose equipment_required holds 'Pinch Block' silently fails to
--       resolve against a pool holding 'Pinch block' — the same class of
--       silent-miss bug as the public-tag ↔ layer0-canonical mismatch, one
--       level down.
--
-- Idempotent (safe to re-run). Run on Neon — container egress to Neon is blocked.

BEGIN;

-- ── (1) Collapse exact duplicates: keep the newest etl_run_at per
--        canonical_name, supersede the rest. Reference-safe — canonical_name is
--        unchanged, so no equipment_required rewrite is needed.
WITH ranked AS (
  SELECT id,
         row_number() OVER (
           PARTITION BY canonical_name
           ORDER BY etl_run_at DESC, id DESC
         ) AS rn
  FROM layer0.equipment_items
  WHERE superseded_at IS NULL
)
UPDATE layer0.equipment_items e
   SET superseded_at = NOW()
  FROM ranked r
 WHERE e.id = r.id
   AND r.rn > 1;

-- ── (2) Merge case variants → sentence-case canonical. Rewrite the references
--        Layer 2C Tier-1 actually reads (exercises.equipment_required, TEXT[]),
--        then supersede the Title-case variant row. JSONB columns
--        (equipment_substitutes_structured / physical_proxies) are surfaced by
--        the verification block below rather than rewritten blind.
DO $$
DECLARE
  pair TEXT[];
  variant_to_canonical TEXT[][] := ARRAY[
    ['Pinch Block',    'Pinch block'],
    ['Trekking Poles', 'Trekking poles'],
    ['Wrist Roller',   'Wrist roller']
  ];
BEGIN
  FOREACH pair SLICE 1 IN ARRAY variant_to_canonical LOOP
    UPDATE layer0.exercises
       SET equipment_required = array_replace(equipment_required, pair[1], pair[2])
     WHERE equipment_required @> ARRAY[pair[1]];

    UPDATE layer0.equipment_items
       SET superseded_at = NOW()
     WHERE canonical_name = pair[1]
       AND superseded_at IS NULL;
  END LOOP;
END $$;

-- ── (3) Prevent recurrence: at most one ACTIVE row per case-insensitive name.
--        Catches both defect classes going forward (a re-added unsuperseded
--        version OR a new case variant both raise a unique violation at insert).
CREATE UNIQUE INDEX IF NOT EXISTS equipment_items_active_ci_name_idx
  ON layer0.equipment_items (lower(canonical_name))
  WHERE superseded_at IS NULL;

-- ── Verify ──────────────────────────────────────────────────────────────────
DO $$
DECLARE
  active_dups INT;
  residual_variant_refs INT;
BEGIN
  SELECT count(*) INTO active_dups FROM (
    SELECT lower(canonical_name)
    FROM layer0.equipment_items
    WHERE superseded_at IS NULL
    GROUP BY lower(canonical_name)
    HAVING count(*) > 1
  ) d;
  IF active_dups > 0 THEN
    RAISE EXCEPTION 'dedupe_layer0_equipment_items: % case-insensitive active duplicate(s) remain', active_dups;
  END IF;

  -- Any residual Title-case variant refs left in JSONB substitute/proxy columns
  -- (array_replace above only covers the TEXT[] equipment_required). Review if >0.
  SELECT count(*) INTO residual_variant_refs
  FROM layer0.exercises
  WHERE equipment_substitutes_structured::text ~ '(Pinch Block|Trekking Poles|Wrist Roller)'
     OR physical_proxies::text             ~ '(Pinch Block|Trekking Poles|Wrist Roller)';

  RAISE NOTICE 'dedupe_layer0_equipment_items: OK — one active row per canonical name. Residual Title-case variant refs in JSONB substitute/proxy columns (review/patch if >0): %', residual_variant_refs;
END $$;

COMMIT;
