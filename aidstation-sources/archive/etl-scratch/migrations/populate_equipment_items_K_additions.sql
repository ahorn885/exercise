-- populate_equipment_items_K_additions.sql
-- Adds 10 new canonical equipment entries to layer0.equipment_items.
--
-- Source: vocab_patch_K_new_entries.md (v3, after user decisions)
-- These entries are needed for Layer 1 Node 2C Tier 2 resolution to match
-- substitute equipment requirements emitted by parse_substitutes.py.
--
-- Idempotent: ON CONFLICT clause prevents duplicate inserts on re-run.

BEGIN;

INSERT INTO layer0.equipment_items
  (canonical_name, equipment_category, is_universal, notes, etl_version, etl_run_at)
VALUES
  ('Wobble board',          'Stability & Balance',           FALSE,
   'Hard wood/plastic balance trainer; distinct from BOSU ball, Balance disc, Foam pad',
   '0A-v17.K', NOW()),

  ('Mini hurdles',          'Plyo & Power',                  FALSE,
   'Agility hurdles ~6-12 inches; distinct from Cones (markers) and Agility ladder (flat)',
   '0A-v17.K', NOW()),

  ('Mini trampoline',       'Plyo & Power',                  FALSE,
   'Rebounder for low-impact plyometric / cardio',
   '0A-v17.K', NOW()),

  ('Ab straps',             'Bodyweight & Portable',         FALSE,
   'Loop straps that hang from a pull-up bar for hanging knee/leg raise',
   '0A-v17.K', NOW()),

  ('Stick roller',          'Recovery & Therapy',            FALSE,
   'Handheld muscle roller (e.g., The Stick); distinct from Foam roller (floor-rolled)',
   '0A-v17.K', NOW()),

  ('Climbing holds',        'Sport-Specific — Climbing',     FALSE,
   'Wall-mounted training holds (jugs, crimps, slopers); new sub-category',
   '0A-v17.K', NOW()),

  ('Climbing rope',         'Sport-Specific — Climbing',     FALSE,
   'Rope for rope-climb training; distinct from Jump rope',
   '0A-v17.K', NOW()),

  ('Rollerskis',            'Sport-Specific — Winter',       FALSE,
   'Dryland XC ski training apparatus',
   '0A-v17.K', NOW()),

  ('Inline skates',         'Sport-Specific — Winter',       FALSE,
   'Skating dryland substitute for skate skiing',
   '0A-v17.K', NOW()),

  ('Hyperextension bench',  'Machines — Lower Body',         FALSE,
   '45-degree posterior chain bench (Roman chair); distinct from GHD',
   '0A-v17.K', NOW()),

  ('Stairs',                'Bodyweight & Portable',         FALSE,
   'A full flight of stairs (multi-step structure); distinct from Stair climber machine. Single steps / edges are universal and not tracked.',
   '0A-v17.K', NOW())
ON CONFLICT (canonical_name) DO NOTHING;

-- ── Verification ──────────────────────────────────────────────────────────
DO $$
DECLARE
  expected_new INT := 11;
  actual_count INT;
BEGIN
  SELECT COUNT(*) INTO actual_count
  FROM layer0.equipment_items
  WHERE canonical_name IN (
    'Wobble board', 'Mini hurdles', 'Mini trampoline', 'Ab straps',
    'Stick roller', 'Climbing holds', 'Climbing rope', 'Rollerskis',
    'Inline skates', 'Hyperextension bench', 'Stairs'
  );

  IF actual_count <> expected_new THEN
    RAISE EXCEPTION 'populate_equipment_items_K_additions: expected % entries, found %',
      expected_new, actual_count;
  END IF;

  RAISE NOTICE 'populate_equipment_items_K_additions: OK — % entries verified', actual_count;
END $$;

COMMIT;
