-- 0029_strip_swim_gear_equipment.sql
--
-- #884 slice 4.3 — the swim-gear equipment strip Andy DEFERRED from slice 3b
-- (the gear-gated cardio-drill gate). Slice 3b wired the owned-gear gate
-- (`cardio_drill_gear_requirements`: EX126→pull_buoy, EX128→kickboard, read by
-- `compute_cardio_drill_pool_ids`) but explicitly left the two drills ALSO
-- double-gated by their `equipment_required` token + the `equipment_items`
-- picker rows, to be cleaned up here. This migration removes that second gate so
-- swim-drill membership is owned-gear-only (design v3 Decision 4 / Decision 11:
-- gear gates `cardio_drills[]` pool membership, NEVER an `equipment_required`
-- gate on the EX row).
--
-- Two edits, two shapes (README §"Two edit shapes"):
--
--   PART A — exercises (0B, SERVING-RELEVANT supersede+reinsert, the 0020/0016
--   pattern). EX126 Freestyle Pull (With Buoy) carries equipment_required
--   {Pull buoy}; EX128 Kicking Drill (Flutter / Frog) carries {Kickboard}. Both
--   strip to {} and move to a bumped 0B version (0B-v1.6.19 is the current max
--   active exercises version → 0B-v1.6.20), so the per-table digest in
--   `_q_current_etl_version_set` advances and plan-gen caches invalidate. The
--   served output is presently IDENTICAL — slice 3b's owned-gear gate already
--   drops EX126/EX128 from every pool while owned swim gear is empty (no swim-
--   gear capture until slice 6) — so the invalidation is a correct-but-harmless
--   re-synth, the same property the #884 cascade slices carried. Every other
--   column is copied verbatim (incl. equipment_substitutes_structured — the
--   improvised-substitute mechanism is untouched, only the top-level
--   equipment_required array changes, per the plan).
--
--   PART B — equipment_items (0C, CACHE-NEUTRAL supersede-only, the 0023
--   pattern). Pull buoy / Kickboard / Swim fins are retired from the equipment
--   vocabulary (the per-locale picker). After PART A no active exercise names
--   any of them in equipment_required (verified below), so the Layer 2C
--   effective pool is identical before/after for every athlete — picker-only
--   change, NO etl_version bump, caches stay warm (stale == correct). Swim fins
--   was never named by any active exercise (inert, like 0023's retire set); Pull
--   buoy / Kickboard become inert the instant PART A commits.
--
-- Order matters WITHIN this migration: PART A strips the exercises FIRST, so
-- PART B's cache-neutral precondition (0 active exercises reference the retired
-- items) holds at the time the equipment_items rows are superseded.
--
-- No public-schema DDL. No LAYER4_PROMPT_REVISION bump (data-only; the exercises
-- cache rides the 0B digest).
--
-- Idempotent: PART A guards on a swim token still being present AND
-- etl_version <> '0B-v1.6.20'; PART B matches only still-active rows by
-- canonical_name. A re-run — or a prod already carrying the stripped state —
-- selects nothing in both parts (clean no-op).
--
-- Atomic: the verify DO block RAISEs (rolling back the whole txn) unless EX126 +
-- EX128 are active with empty equipment_required, no active exercise references
-- any of the three swim items, none of the three is still an active
-- equipment_items row, and no exercise_id is double-active.

\set ON_ERROR_STOP on

BEGIN;

-- ── PART A — strip equipment_required on EX126/EX128 (0B serving-relevant) ────
INSERT INTO layer0.exercises (
  exercise_id, exercise_name, exercise_type, movement_patterns, primary_muscles,
  secondary_muscles, equipment_required, injury_flags_text, contraindicated_parts,
  contraindicated_conditions, equipment_substitutes, physical_proxies,
  progression_exercise_id, progression_exercise_name, regression_exercise_id,
  regression_exercise_name, sport_count, coaching_cues,
  etl_version, etl_run_at, terrain_required, equipment_substitutes_structured,
  movement_components
)
SELECT
  e.exercise_id, e.exercise_name, e.exercise_type, e.movement_patterns,
  e.primary_muscles, e.secondary_muscles,
  '{}'::text[],
  e.injury_flags_text, e.contraindicated_parts, e.contraindicated_conditions,
  e.equipment_substitutes, e.physical_proxies,
  e.progression_exercise_id, e.progression_exercise_name,
  e.regression_exercise_id, e.regression_exercise_name, e.sport_count,
  e.coaching_cues,
  '0B-v1.6.20', now(), e.terrain_required, e.equipment_substitutes_structured,
  e.movement_components
FROM layer0.exercises e
WHERE e.superseded_at IS NULL
  AND e.exercise_id IN ('EX126','EX128')
  AND e.equipment_required && ARRAY['Pull buoy','Kickboard','Swim fins']
  AND e.etl_version <> '0B-v1.6.20';

UPDATE layer0.exercises e
   SET superseded_at = now()
 WHERE e.superseded_at IS NULL
   AND e.exercise_id IN ('EX126','EX128')
   AND e.equipment_required && ARRAY['Pull buoy','Kickboard','Swim fins']
   AND e.etl_version <> '0B-v1.6.20';

-- ── PART B — retire the swim items from the equipment vocabulary (0C neutral) ─
UPDATE layer0.equipment_items e
   SET superseded_at = now()
 WHERE e.superseded_at IS NULL
   AND e.canonical_name IN ('Pull buoy', 'Kickboard', 'Swim fins');

-- ── Verify (atomic — any failure rolls back the whole migration) ─────────────
DO $$
DECLARE
  v_stripped INT;
  v_ex_dirty INT;
  v_items    INT;
  v_dup      INT;
BEGIN
  -- EX126 + EX128 are active with an EMPTY equipment_required.
  SELECT count(*) INTO v_stripped
    FROM layer0.exercises
   WHERE superseded_at IS NULL
     AND exercise_id IN ('EX126','EX128')
     AND equipment_required = '{}'::text[];
  IF v_stripped <> 2 THEN
    RAISE EXCEPTION '0029: expected EX126+EX128 active with empty equipment_required, found %', v_stripped;
  END IF;

  -- No active exercise still names any of the three swim items (guards PART B's
  -- cache-neutral precondition — if it trips, an exercise still gates on a now-
  -- retired item and the edit is not cache-neutral).
  SELECT count(*) INTO v_ex_dirty
    FROM layer0.exercises
   WHERE superseded_at IS NULL
     AND equipment_required && ARRAY['Pull buoy','Kickboard','Swim fins'];
  IF v_ex_dirty > 0 THEN
    RAISE EXCEPTION '0029: % active exercise(s) still name a retired swim item', v_ex_dirty;
  END IF;

  -- None of the three is still an active equipment_items row.
  SELECT count(*) INTO v_items
    FROM layer0.equipment_items
   WHERE superseded_at IS NULL
     AND canonical_name IN ('Pull buoy', 'Kickboard', 'Swim fins');
  IF v_items > 0 THEN
    RAISE EXCEPTION '0029: % swim item(s) still active in equipment_items', v_items;
  END IF;

  -- No exercise_id is double-active (supersede landed).
  SELECT count(*) INTO v_dup FROM (
    SELECT exercise_id FROM layer0.exercises WHERE superseded_at IS NULL
     GROUP BY exercise_id HAVING count(*) > 1) d;
  IF v_dup > 0 THEN
    RAISE EXCEPTION '0029: % exercise_id(s) double-active after supersede', v_dup;
  END IF;

  RAISE NOTICE '0029: OK — EX126/EX128 equipment_required stripped at 0B-v1.6.20; Pull buoy / Kickboard / Swim fins retired from equipment_items (cache-neutral)';
END $$;

COMMIT;

-- End of 0029_strip_swim_gear_equipment.sql
