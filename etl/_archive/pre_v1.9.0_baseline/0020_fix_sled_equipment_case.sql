-- 0020_fix_sled_equipment_case.sql
--
-- #691 follow-up / #698 equipment-vocab soundness (#428 mismatch class). EX029
-- Sled Push + EX030 Reverse Sled Drag spell their requirement title-cased as
-- "Weighted Sled" in equipment_required, but the canonical layer0.equipment_items
-- name — and these rows' own equipment_substitutes_structured tokens — is the
-- lowercase "Weighted sled" (one active row, 0C-v1.6.7). The Layer 2C _tier_1 gate
-- is exact-match (`set(equipment_required).issubset(effective_pool)`, no
-- case-fold), so "Weighted Sled" never matches a locale pool carrying "Weighted
-- sled": these two never resolve Tier 1 even for an athlete who OWNS a sled — they
-- always fall to the band substitute / bodyweight proxy. Isolated to these two
-- rows (audited vs the v1.7.0 baseline + v1.8.0 snapshot).
--
-- Fix: repoint equipment_required's "Weighted Sled" -> "Weighted sled" via
-- array_replace (touches only the offending element; any other token preserved).
-- No new vocab (strict no-padding satisfied — the canonical token already exists).
-- No name change, so the denormalized sport_exercise_map.exercise_name needs no
-- sync; sport_exercise_map carries no equipment, so no SEM edit at all.
--
-- Edit shape (README "Two edit shapes"): SERVING-RELEVANT supersede-and-reinsert
-- (the 0016 pattern). A sled-owner's pool now resolves EX029/EX030 at Tier 1
-- instead of Tier 2/3, which changes plan-gen output, so the two edited rows move
-- to a bumped 0B version 0B-v1.6.16 -> 0B-v1.6.17 (the per-table digest in
-- _q_current_etl_version_set advances; plan-gen caches invalidate). Every other
-- column is copied verbatim; the old rows are superseded (history preserved). No
-- public-schema DDL. No LAYER4_PROMPT_REVISION bump (data-only; cache rides the 0B
-- digest).
--
-- Idempotent: the supersede/insert are guarded on the title-case token still being
-- present AND etl_version <> '0B-v1.6.17', so a re-run — or a prod already carrying
-- the lowercase token — selects nothing.
--
-- Atomic: the verify DO block RAISEs (rolling back) unless EX029 + EX030 are active,
-- neither still carries title-case "Weighted Sled", both carry "Weighted sled",
-- that token is an active canonical equipment_items name, and no exercise_id is
-- double-active.

\set ON_ERROR_STOP on

BEGIN;

-- ── Re-insert EX029/EX030 with the equipment token case-corrected ─────────────
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
  array_replace(e.equipment_required, 'Weighted Sled', 'Weighted sled'),
  e.injury_flags_text, e.contraindicated_parts, e.contraindicated_conditions,
  e.equipment_substitutes, e.physical_proxies,
  e.progression_exercise_id, e.progression_exercise_name,
  e.regression_exercise_id, e.regression_exercise_name, e.sport_count,
  e.coaching_cues,
  '0B-v1.6.17', now(), e.terrain_required, e.equipment_substitutes_structured,
  e.movement_components
FROM layer0.exercises e
WHERE e.superseded_at IS NULL
  AND e.exercise_id IN ('EX029','EX030')
  AND 'Weighted Sled' = ANY(e.equipment_required)
  AND e.etl_version <> '0B-v1.6.17';

UPDATE layer0.exercises e
   SET superseded_at = now()
 WHERE e.superseded_at IS NULL
   AND e.exercise_id IN ('EX029','EX030')
   AND 'Weighted Sled' = ANY(e.equipment_required)
   AND e.etl_version <> '0B-v1.6.17';

-- ── Verify (atomic) ───────────────────────────────────────────────────────────
DO $$
DECLARE v_titlecase INT; v_fixed INT; v_canon INT; v_dup INT;
BEGIN
  -- No active sled exercise still carries the title-case token.
  SELECT count(*) INTO v_titlecase FROM layer0.exercises
   WHERE superseded_at IS NULL
     AND exercise_id IN ('EX029','EX030')
     AND 'Weighted Sled' = ANY(equipment_required);
  IF v_titlecase <> 0 THEN
    RAISE EXCEPTION '0020: % sled exercise(s) still carry title-case "Weighted Sled"', v_titlecase;
  END IF;

  -- Both EX029 + EX030 are active and now carry the lowercase canonical token.
  SELECT count(*) INTO v_fixed FROM layer0.exercises
   WHERE superseded_at IS NULL
     AND exercise_id IN ('EX029','EX030')
     AND 'Weighted sled' = ANY(equipment_required);
  IF v_fixed <> 2 THEN
    RAISE EXCEPTION '0020: expected EX029+EX030 active with "Weighted sled", found %', v_fixed;
  END IF;

  -- The corrected token is a real active canonical equipment_items name (#428 alignment).
  SELECT count(*) INTO v_canon FROM layer0.equipment_items
   WHERE superseded_at IS NULL AND canonical_name = 'Weighted sled';
  IF v_canon < 1 THEN
    RAISE EXCEPTION '0020: "Weighted sled" is not an active canonical equipment_items name';
  END IF;

  -- No exercise_id is double-active (supersede landed).
  SELECT count(*) INTO v_dup FROM (
    SELECT exercise_id FROM layer0.exercises WHERE superseded_at IS NULL
     GROUP BY exercise_id HAVING count(*) > 1) d;
  IF v_dup > 0 THEN RAISE EXCEPTION '0020: % exercise_id(s) double-active after supersede', v_dup; END IF;

  RAISE NOTICE '0020: OK — EX029/EX030 equipment_required "Weighted Sled" -> "Weighted sled" at 0B-v1.6.17';
END $$;

COMMIT;

-- End of 0020_fix_sled_equipment_case.sql
