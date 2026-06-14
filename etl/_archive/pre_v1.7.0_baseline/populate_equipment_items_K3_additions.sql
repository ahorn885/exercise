-- populate_equipment_items_K3_additions.sql
-- BestFitModality_Spec_v2.md §I — canonicalisation of the equipment names
-- referenced by `_MODALITY_OPTIONS_PER_DISCIPLINE` in
-- `layer2_modality/resolver.py`. Closes the L2 lint scope picked at the
-- v2 plan-mode gate: every `requires_equipment_all_of` entry in the
-- resolver's vocab dict now resolves against canonical 0B equipment_items.
--
-- ETL version tag: 0B-v19.K3
--
-- Idempotent: ON CONFLICT (canonical_name, etl_version) DO NOTHING
-- Safe to re-run. Apply after K2_additions.

BEGIN;

INSERT INTO layer0.equipment_items
  (canonical_name, equipment_category, is_universal, notes, etl_version, etl_run_at)
VALUES

  -- ── Cardio canonical (D-001 + D-008) ───────────────────────────────────────

  ('Treadmill',
   'Cardio — Running', FALSE,
   'Indoor treadmill. Referenced by D-001 treadmill_run modality option as an indoor substitute when outdoor terrain unavailable.',
   '0B-v19.K3', NOW()),

  ('Road bike',
   'Cardio — Cycling', FALSE,
   'Drop-bar road bike. Referenced by D-008 outdoor_road_ride modality option. Distinct from Gravel bike (off-road geometry); race_modality_hints pin which craft a target race specifies.',
   '0B-v19.K3', NOW()),

  -- ── Sport-Specific — Climbing (D-012) ──────────────────────────────────────

  ('Rope',
   'Sport-Specific — Climbing', FALSE,
   'Single climbing rope (dynamic). Referenced by D-012 outdoor_lead_climb + outdoor_top_rope modality options. Distinct from the Climbing gear aggregate (which bundles rope + harness + draws + hardware).',
   '0B-v19.K3', NOW()),

  ('Quickdraws',
   'Sport-Specific — Climbing', FALSE,
   'Set of quickdraws for lead climbing. Referenced by D-012 outdoor_lead_climb modality option. Top-rope modality does not require them.',
   '0B-v19.K3', NOW()),

  ('Harness',
   'Sport-Specific — Climbing', FALSE,
   'Climbing harness. Referenced by D-012 rope-based modality options (outdoor_lead_climb + outdoor_top_rope). Bouldering does not require.',
   '0B-v19.K3', NOW()),

  ('Crash pad',
   'Sport-Specific — Climbing', FALSE,
   'Bouldering crash pad. Referenced by D-012 outdoor_boulder modality option. Gym bouldering doesn''t require (gym pads are venue-provided).',
   '0B-v19.K3', NOW()),

  ('Hangboard',
   'Sport-Specific — Climbing', FALSE,
   'Finger-strength training board. Referenced by D-012 gym_hangboard modality option as an indoor finger-strength substitute when climbing terrain unavailable.',
   '0B-v19.K3', NOW()),

  -- ── Venue — Climbing (D-012 gym options) ──────────────────────────────────

  ('Climbing gym membership',
   'Venue — Climbing', FALSE,
   'Athlete has access to an indoor climbing gym. Referenced by D-012 gym_lead_climb / gym_top_rope / gym_boulder modality options. Distinct from Climbing Wall (which marks gym-availability venue toggle without requiring membership wording). The two will reconcile in a future BM-5 follow-on.',
   '0B-v19.K3', NOW()),

  -- ── Sport-Specific — Water (D-010 paddling) ──────────────────────────────

  ('Kayak',
   'Sport-Specific — Water', FALSE,
   'Sit-in or sit-on-top kayak. Referenced by D-010 outdoor_paddle_kayak + outdoor_whitewater_kayak modality options (whitewater variant gated by whitewater_handling skill toggle).',
   '0B-v19.K3', NOW()),

  ('Canoe',
   'Sport-Specific — Water', FALSE,
   'Open canoe (solo or tandem). Reserved canonical entry for future D-010 canoe-specific modality options; not currently referenced by v2 vocab but added to canonical 0B for completeness so future vocab follow-ons land cleanly without a separate ETL slice.',
   '0B-v19.K3', NOW())

ON CONFLICT (canonical_name, etl_version) DO NOTHING;

-- ── Verification ─────────────────────────────────────────────────────────────
DO $$
DECLARE
  required_names TEXT[] := ARRAY[
    'Treadmill', 'Road bike', 'Rope', 'Quickdraws', 'Harness',
    'Crash pad', 'Hangboard', 'Climbing gym membership',
    'Kayak', 'Canoe'
  ];
  missing_names TEXT[];
BEGIN
  SELECT ARRAY_AGG(n)
  INTO missing_names
  FROM UNNEST(required_names) AS n
  WHERE n NOT IN (SELECT canonical_name FROM layer0.equipment_items);

  IF missing_names IS NOT NULL AND ARRAY_LENGTH(missing_names, 1) > 0 THEN
    RAISE EXCEPTION 'K3 verify failed — missing from equipment_items: %', missing_names;
  END IF;

  RAISE NOTICE 'K3 verify OK — all 10 required entries present in equipment_items';
END $$;

COMMIT;
