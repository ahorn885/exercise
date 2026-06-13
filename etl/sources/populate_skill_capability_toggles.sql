-- populate_skill_capability_toggles.sql
-- Seed the 5 canonical skill-capability toggle rows ratified at the
-- D-73 Phase 5.2 Bucket C sub-item (l) plan-mode gate (Andy
-- 2026-05-24). Mirrors the populate_gear_toggles_batch_a.sql shape:
-- each row carries display_label, description, gated_terrain_ids,
-- gated_discipline_ids tagged at the canonical 0C version
-- '0C-v2.0-r2' (matches populate_terrain_gap_rules.sql + the rest of
-- the canonical 0C data).
--
-- Skill toggles capture whether the athlete has acquired the technical
-- skill required to safely access a terrain or train a discipline.
-- Default state is OFF (assume-not-skilled, athlete opts in by
-- toggling). Layer 2B reads `gated_terrain_ids` and emits
-- `requires_skill_capability` when a race terrain falls in the set
-- and the athlete toggle is OFF. Layer 2C reads `gated_discipline_ids`
-- and emits the same flag (different surface) when an included
-- discipline requires a capability the athlete hasn't enabled.
--
-- Ratified mappings (Andy 2026-05-24, tightened from initial proposal):
--   climbing_roped      → {TRN-013}                  | {D-012, D-013}
--   via_ferrata         → {}  (no canonical terrain row) | {D-014}
--   whitewater_handling → {TRN-011, TRN-017}         | {D-010}
--   swim_open_water     → {TRN-009, TRN-010}         | {D-004}
--   mountaineering      → {TRN-005, TRN-012}         | {D-018, D-022}
--
-- Naming convention: snake_case (not the em-dash display strings the
-- gear-toggle precedent uses) to dodge the populate-script-fragility
-- trap documented in populate_gear_toggles_batch_a.sql.
--
-- Idempotent: a DELETE-by-version prefix rebuilds this version's rows from
-- this file on every run, so a row removed from the file can't linger as an
-- active orphan (D-74) — matching etl/layer0/db.py:insert_versioned. The
-- ON CONFLICT (toggle_name, etl_version) DO NOTHING guard is retained as
-- belt-and-suspenders. Verify block at file end asserts the active row
-- count = 5; a clean re-deploy must trip this if any row was missed.

BEGIN;

-- D-74: clear this version's rows first so re-running rebuilds them from this
-- file (a row removed from the file can't survive as an active orphan).
DELETE FROM layer0.skill_capability_toggles WHERE etl_version = '0C-v2.0-r2';

INSERT INTO layer0.skill_capability_toggles
  (toggle_name, display_label, description,
   gated_terrain_ids, gated_discipline_ids,
   etl_version, etl_run_at)
VALUES
  ( 'climbing_roped',
    'Roped climbing (lead / top-rope)',
    'Athlete has practiced lead or top-rope climbing on outdoor rock '
      'with rope-protected technique (anchors, belay, fall management). '
      'Distinct from gym climbing where the bolts are pre-set; outdoor '
      'rock adds protection-placement, route-finding, and real-fall '
      'exposure judgement.',
    ARRAY['TRN-013'],
    ARRAY['D-012', 'D-013'],
    '0C-v2.0-r2', NOW() ),

  ( 'via_ferrata',
    'Via ferrata / fixed-rope traversal',
    'Athlete has traversed via ferrata or fixed-rope route, including '
      'cable-clipping technique, lanyard management, and exposure-tolerance '
      'on protected mountain routes. Distinct from full roped climbing — '
      'no rope-protection skill needed but cable-clipping discipline + '
      'continuous-exposure tolerance is required.',
    ARRAY[]::TEXT[],
    ARRAY['D-014'],
    '0C-v2.0-r2', NOW() ),

  ( 'whitewater_handling',
    'Whitewater / moving-water paddle skill',
    'Athlete can read and navigate moving water (current handling, ferry '
      'angles, eddy reads, brace recovery). Covers Class II and below as '
      'a competence baseline; whitewater above Class II is its own '
      'progression. Distinct from flat-water paddling, where current '
      'reading and brace skills are not exercised.',
    ARRAY['TRN-011', 'TRN-017'],
    ARRAY['D-010'],
    '0C-v2.0-r2', NOW() ),

  ( 'swim_open_water',
    'Open-water swimming competence',
    'Athlete can swim in open water (lake, reservoir, ocean) confidently '
      'without panic at depth, can sight off-shore landmarks, and has '
      'tolerance for cold-shock entry. Pool swimming is the proxy '
      'fitness; open-water adds visibility, temperature, current, and '
      'psychological-exposure stimuli that pool training does not cover.',
    ARRAY['TRN-009', 'TRN-010'],
    ARRAY['D-004'],
    '0C-v2.0-r2', NOW() ),

  ( 'mountaineering',
    'Alpine / glacier travel skill',
    'Athlete has practiced technical alpine travel including crampon '
      'placement, ice-axe arrest, rope-team coordination on glaciers, '
      'and exposure tolerance on sustained vertical. Distinct from '
      'hill / rolling terrain (no technical surface) and from rock '
      'climbing (different skill mix; some overlap with via ferrata).',
    ARRAY['TRN-005', 'TRN-012'],
    ARRAY['D-018', 'D-022'],
    '0C-v2.0-r2', NOW() )
ON CONFLICT (toggle_name, etl_version) DO NOTHING;

-- Verify the expected 5 active rows landed. A clean re-deploy must
-- trip this if any row was missed (e.g. ON CONFLICT swallowed an
-- intended insert due to a duplicate). Tracks the audit cadence
-- established by populate_terrain_gap_rules.sql.
DO $$
DECLARE
  row_count INTEGER;
BEGIN
  SELECT COUNT(*) INTO row_count
    FROM layer0.skill_capability_toggles
   WHERE etl_version = '0C-v2.0-r2'
     AND superseded_at IS NULL;
  IF row_count <> 5 THEN
    RAISE EXCEPTION
      'populate_skill_capability_toggles.sql verify failed: '
      'expected 5 active rows at etl_version=0C-v2.0-r2, found %',
      row_count;
  END IF;
  RAISE NOTICE 'populate_skill_capability_toggles.sql: % active rows', row_count;
END $$;

COMMIT;
