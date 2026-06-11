-- populate_equipment_items_K2_additions.sql
-- Adds canonical entries introduced by Pass 1 (equipment column cleanup) and
-- Pass 2 (token resolution) that are NOT present in Vocabulary_Audit_v2.md
-- Section 3 / prior K1 patch.
--
-- Source: HANDOFF_equipment_cleanup_pass1.md (K2 requirement) +
--         Equipment_Column_Canonical_Addendum.md (Pass 2 decisions)
-- ETL version tag: 0B-v19.K2
--
-- Idempotent: ON CONFLICT (canonical_name) DO NOTHING
-- Safe to run multiple times. Run BEFORE ETL against v19.

BEGIN;

INSERT INTO layer0.equipment_items
  (canonical_name, equipment_category, is_universal, notes, etl_version, etl_run_at)
VALUES

  -- ── Pass 1 aggregates ────────────────────────────────────────────────────

  ('Climbing gear',
   'Sport-Specific — Climbing', FALSE,
   'Aggregate canonical: harness, rope, belay device, carabiners, slings, fixed rope, anchor hardware, mechanical ascender, via ferrata Y-lanyard. Use this token for any exercise requiring a full climbing setup.',
   '0B-v19.K2', NOW()),

  ('XC ski kit',
   'Sport-Specific — Winter', FALSE,
   'Aggregate canonical: cross-country skis (classic or skate), XC ski boots, XC ski poles. Ski poles do NOT appear as a separate token for XC exercises.',
   '0B-v19.K2', NOW()),

  ('Touring ski kit',
   'Sport-Specific — Winter', FALSE,
   'Aggregate canonical: touring skis, touring boots, climbing skins, ski crampons, alpine skis. Ski poles do NOT appear as a separate token for touring exercises.',
   '0B-v19.K2', NOW()),

  ('SUP',
   'Sport-Specific — Water', FALSE,
   'Stand-up paddleboard. Normalized from "Stand-Up Paddleboard". Includes paddle.',
   '0B-v19.K2', NOW()),

  -- ── Pass 2 aggregates ────────────────────────────────────────────────────

  ('Mountaineering kit',
   'Sport-Specific — Mountaineering', FALSE,
   'Aggregate canonical: crampons, ice axe, mountaineering boots, ski crampons. Use this token for any exercise requiring mountaineering-specific hardware. Distinct from Climbing gear (rope/harness system).',
   '0B-v19.K2', NOW()),

  -- ── Venue toggle ─────────────────────────────────────────────────────────

  ('Climbing Wall',
   'Venue — Climbing', FALSE,
   'Venue toggle: athlete must have access to an indoor or outdoor climbing wall. Controls schedulability of climbing-gym exercises. Distinct from Climbing gear (physical equipment). Normalized from "Rock Wall".',
   '0B-v19.K2', NOW()),

  -- ── Permissive inserts for tokens in v19 that may not yet be in DB ───────
  -- These are canonical per Vocabulary_Audit_v2.md Section 3 but may not
  -- have been inserted by prior ETL runs. ON CONFLICT makes this safe.

  ('TT Bike',
   'Cardio — Cycling', FALSE,
   'Time trial / triathlon bike. Distinct from Road bike; relevant for bike-interval exercises where aero position training is intended.',
   '0B-v19.K2', NOW()),

  ('Gravel bike',
   'Cardio — Cycling', FALSE,
   'Drop-bar off-road bike. Interchangeable with Road bike for most endurance intervals but distinct for surface-handling work.',
   '0B-v19.K2', NOW()),

  ('Cable machine',
   'Machines — Upper Body', FALSE,
   'Pulley-based cable machine. Normalized from "Cable", "Cable Machine".',
   '0B-v19.K2', NOW()),

  ('Plyo box',
   'Plyo & Power', FALSE,
   'Plyometric box. Normalized from "Box", "Plyo Box", "Vault Box".',
   '0B-v19.K2', NOW()),

  ('Weighted vest',
   'Bodyweight & Portable', FALSE,
   'Weight vest for added load on bodyweight exercises. Normalized from "Vest", "Weight Vest".',
   '0B-v19.K2', NOW()),

  ('Resistance band',
   'Bodyweight & Portable', FALSE,
   'Elastic resistance band. Normalized from "Band", "Rubber Band", "Resistance Band".',
   '0B-v19.K2', NOW()),

  ('Bike trainer',
   'Cardio — Cycling', FALSE,
   'Indoor cycling trainer (smart or dumb). Normalized from "Trainer", "Bike Trainer".',
   '0B-v19.K2', NOW()),

  ('Pull buoy',
   'Sport-Specific — Water', FALSE,
   'Foam float held between legs during swim drills to isolate upper body pull.',
   '0B-v19.K2', NOW()),

  ('Rice bucket',
   'Grip & Forearm', FALSE,
   'Container of dry rice for hand/finger/wrist strength and rehabilitation exercises.',
   '0B-v19.K2', NOW()),

  ('Pinch Block',
   'Grip & Forearm', FALSE,
   'Grip training block for pinch-strength development. Distinct from Weight plates (used for plate pinches).',
   '0B-v19.K2', NOW()),

  ('Wrist Roller',
   'Grip & Forearm', FALSE,
   'Roller with weight for wrist flexion/extension endurance.',
   '0B-v19.K2', NOW()),

  ('Trekking Poles',
   'Bodyweight & Portable', FALSE,
   'Collapsible trekking/hiking poles. Distinct from ski poles (which fold into XC ski kit or Touring ski kit). Used independently for hiking, trail running, snowshoeing.',
   '0B-v19.K2', NOW()),

  ('Packraft',
   'Sport-Specific — Water', FALSE,
   'Inflatable single-person raft. Normalized from "Inflatable Raft", "Loaded Packraft". Functionally equivalent to Inflatable Raft for AR purposes.',
   '0B-v19.K2', NOW())

ON CONFLICT (canonical_name) DO NOTHING;

-- ── Verification ─────────────────────────────────────────────────────────────
DO $$
DECLARE
  required_names TEXT[] := ARRAY[
    'Climbing gear', 'XC ski kit', 'Touring ski kit', 'SUP',
    'Mountaineering kit', 'Climbing Wall', 'TT Bike', 'Gravel bike',
    'Cable machine', 'Plyo box', 'Weighted vest', 'Resistance band',
    'Bike trainer', 'Pull buoy', 'Rice bucket', 'Pinch Block',
    'Wrist Roller', 'Trekking Poles', 'Packraft'
  ];
  missing_names TEXT[];
BEGIN
  SELECT ARRAY_AGG(n)
  INTO missing_names
  FROM UNNEST(required_names) AS n
  WHERE n NOT IN (SELECT canonical_name FROM layer0.equipment_items);

  IF missing_names IS NOT NULL AND ARRAY_LENGTH(missing_names, 1) > 0 THEN
    RAISE EXCEPTION 'K2 verify failed — missing from equipment_items: %', missing_names;
  END IF;

  RAISE NOTICE 'K2 verify OK — all 19 required entries present in equipment_items';
END $$;

COMMIT;
