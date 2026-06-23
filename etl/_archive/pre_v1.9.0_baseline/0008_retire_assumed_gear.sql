-- 0008_retire_assumed_gear.sql
--
-- #623 — stop tracking "assumed" basic gear in the per-location equipment
-- vocabulary, and make sure none of it gates feasibility. The per-locale gear
-- editor (routes/locales._layer0_equipment) renders every active
-- layer0.equipment_items row, so items every athlete in these sports is assumed
-- to own — and that carry no training-feasibility signal — only clutter the
-- picker (and, where an exercise hard-requires one, silently gate sessions on a
-- checkbox the athlete should never have to tick).
--
-- Andy-ratified via AskUserQuestion (2026-06-16; Trigger #2 vocab + Trigger #3
-- cross-layer). Retire set = the 17 below:
--   * 8 sport-specific "assumed" items (the #623 list):
--       Backpack, Headlamp, Hiking boots, Running shoes, Trekking poles,
--       Wetsuit, Swim cap and goggles, Avalanche safety gear.
--     (Avalanche safety gear's old equipment_items note claimed a "safety gate"
--      but it is wired NOWHERE in code — no .py reference, no toggle — so
--      retiring it breaks no live gate; Andy chose to retire it as assumed.)
--   * 9 items already self-labelled in the "Assumed Universal" category and
--     flagged is_universal=true, yet still shown in the picker because the
--     is_universal flag is dead code (2C's effective-pool builder never reads
--     it): Bodyweight, Floor space, Wall, Doorway, Outdoor space, Anchor point,
--     Compass, GPS, Topographic map.
--
-- Approach = de-drift, mirroring 0007 (vessels). Live read (read-only
-- neon-query, 2026-06-16) confirmed which active exercises hard-require a
-- retire-set item in equipment_required (the tier-1 gate):
--   Backpack       -> EX010, EX050, EX095, EX120, EX122, EX123, EX124, EX144,
--                     EX150, EX153  (10)
--   Trekking poles -> EX118, EX121, EX124, EX153, EX154, EX155, EX183  (7)
--   Doorway        -> EX077, EX097  (2)
-- (the other 14 retire-set items gate zero exercises). This migration strips the
-- retire-set tokens from equipment_required so those exercises auto-resolve at
-- tier-1 (assumed gear = always available) instead of dropping to tier-0 once
-- the item leaves the picker. Non-retire tokens are preserved verbatim, so e.g.
-- EX150 keeps {Mountaineering} (a gear toggle, not an equipment item), EX153
-- keeps {Snowshoes}, EX010 keeps {Weighted vest}, EX050 keeps {Treadmill}.
--
-- equipment_substitutes_structured is intentionally LEFT untouched. Backpack is
-- named in ~20 exercises' substitutes as a load fallback; once Backpack leaves
-- the pool a pool-checked Backpack substitute group goes unreachable, but a live
-- audit confirmed every one of those exercises retains a safety net (an
-- is_improvised="backpack loaded with books"-style household sub that resolves
-- regardless of pool, plus physical proxies and non-retired substitutes) — so
-- no session drops. These are tier-2 enrichment, not the tier-1 feasibility gate
-- #623 is about; rewriting 20 JSON blobs is out of scope.
--
-- Edit shape (README §"Two edit shapes"):
--   * equipment_items: SERVING-RELEVANT removal (changes the picker + 2C
--     effective pool). Supersede-only; cache invalidation rides the 0B bump
--     below (every plan reads exercises). Mirrors 0007's equipment_items retire.
--   * exercises: SERVING-RELEVANT edit — supersede + re-insert each affected row
--     at 0B-v1.6.8 -> 0B-v1.6.9, so the exercises-table digest advances and the
--     plan-gen caches invalidate.
-- Both tables are already in _LAYER0_TABLE_FAMILY — no family-map change. No
-- public-schema DDL.
--
-- Idempotent: the equipment_items supersede matches only still-active retire-set
-- rows; the exercise reinsert/supersede is guarded to the pre-bump rows
-- (etl_version <> '0B-v1.6.9' AND equipment_required && the retire set), and the
-- reinserted rows carry no retire token, so a re-run selects nothing — a clean
-- no-op (no UNIQUE collision on (exercise_id, etl_version)).
--
-- Atomic: the verification DO block RAISEs (rolling back the whole txn) if any
-- retire-set item is left active in equipment, any active exercise still names
-- one in equipment_required, or an expected non-retired survivor got nuked.

\set ON_ERROR_STOP on

BEGIN;

-- The 17 canonical names retired from equipment_items + stripped from exercise
-- equipment_required. Dropped at COMMIT.
CREATE TEMP TABLE _assumed_gear (name text PRIMARY KEY) ON COMMIT DROP;
INSERT INTO _assumed_gear (name) VALUES
  ('Backpack'), ('Headlamp'), ('Hiking boots'), ('Running shoes'),
  ('Trekking poles'), ('Wetsuit'), ('Swim cap and goggles'),
  ('Avalanche safety gear'),
  ('Bodyweight'), ('Floor space'), ('Wall'), ('Doorway'), ('Outdoor space'),
  ('Anchor point'), ('Compass'), ('GPS'), ('Topographic map');

-- ── (0C) Retire the assumed gear from the equipment vocabulary ───────────────
-- Supersede-only (history preserved). The picker filters superseded_at IS NULL,
-- so the items vanish from it the moment this commits.
UPDATE layer0.equipment_items e
   SET superseded_at = now()
  FROM _assumed_gear g
 WHERE e.superseded_at IS NULL
   AND e.canonical_name = g.name;

-- ── (0B) De-drift the affected exercises ─────────────────────────────────────
-- Re-insert each active exercise whose equipment_required names a retire-set
-- item, with those tokens removed (order preserved) at the bumped version.
-- Every other column copied verbatim; id (serial) + superseded_at (NULL) omitted.
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
  e.exercise_id, e.exercise_name, e.exercise_type, e.movement_patterns, e.primary_muscles,
  e.secondary_muscles,
  (
    SELECT COALESCE(array_agg(tok ORDER BY ord), '{}')
      FROM unnest(e.equipment_required) WITH ORDINALITY AS u(tok, ord)
     WHERE tok NOT IN (SELECT name FROM _assumed_gear)
  ),
  e.injury_flags_text, e.contraindicated_parts,
  e.contraindicated_conditions, e.equipment_substitutes, e.physical_proxies,
  e.progression_exercise_id, e.progression_exercise_name, e.regression_exercise_id,
  e.regression_exercise_name, e.sport_count, e.coaching_cues,
  '0B-v1.6.9', now(), e.terrain_required, e.equipment_substitutes_structured,
  e.movement_components
FROM layer0.exercises e
WHERE e.superseded_at IS NULL
  AND e.etl_version <> '0B-v1.6.9'
  AND e.equipment_required && ARRAY(SELECT name FROM _assumed_gear);

-- Supersede the old (gear-bearing) rows now replaced by the cleaned copies.
UPDATE layer0.exercises e
   SET superseded_at = now()
 WHERE e.superseded_at IS NULL
   AND e.etl_version <> '0B-v1.6.9'
   AND e.equipment_required && ARRAY(SELECT name FROM _assumed_gear);

-- ── Verify (atomic — any failure rolls back the whole migration) ─────────────
DO $$
DECLARE
  v_left_active INT;
  v_ex_dirty    INT;
  v_survivors   INT;
BEGIN
  -- 0C: no retire-set item is still active in the equipment vocabulary.
  SELECT count(*) INTO v_left_active
    FROM layer0.equipment_items
   WHERE superseded_at IS NULL
     AND canonical_name IN (SELECT name FROM _assumed_gear);
  IF v_left_active > 0 THEN
    RAISE EXCEPTION '0008: % assumed-gear item(s) still active in equipment_items', v_left_active;
  END IF;

  -- 0B: no active exercise still names a retired item in equipment_required.
  SELECT count(*) INTO v_ex_dirty
    FROM layer0.exercises
   WHERE superseded_at IS NULL
     AND equipment_required && ARRAY(SELECT name FROM _assumed_gear);
  IF v_ex_dirty > 0 THEN
    RAISE EXCEPTION '0008: % active exercise(s) still name a retired assumed-gear item', v_ex_dirty;
  END IF;

  -- 0B: guard against an over-broad strip — the non-retired tokens that share a
  -- de-drifted row must survive (EX150 keeps the Mountaineering toggle, EX153
  -- keeps Snowshoes, EX010 keeps Weighted vest, EX050 keeps Treadmill).
  SELECT count(*) INTO v_survivors
    FROM (VALUES
      ('EX150', 'Mountaineering'),
      ('EX153', 'Snowshoes'),
      ('EX010', 'Weighted vest'),
      ('EX050', 'Treadmill')
    ) s(exercise_id, token)
   WHERE EXISTS (
     SELECT 1 FROM layer0.exercises e
      WHERE e.superseded_at IS NULL
        AND e.exercise_id = s.exercise_id
        AND s.token = ANY(e.equipment_required)
   );
  IF v_survivors <> 4 THEN
    RAISE EXCEPTION '0008: expected 4 non-retired survivor tokens, found % — de-drift over-stripped', v_survivors;
  END IF;

  RAISE NOTICE '0008: OK — 17 assumed-gear items retired from the picker; affected exercises de-drifted (non-retired tokens preserved)';
END $$;

COMMIT;

-- End of 0008_retire_assumed_gear.sql
