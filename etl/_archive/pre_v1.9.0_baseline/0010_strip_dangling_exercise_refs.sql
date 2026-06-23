-- 0010_strip_dangling_exercise_refs.sql
--
-- #648 — strip dangling exercise references surfaced by the new exercises-FK
-- validator (etl/layer0/validation/exercises_fk_check.py). The validator's first
-- gate run found 11 references on active layer0.exercises rows that point at
-- exercise_ids which were NEVER created in the library (phantom targets — they
-- appear only as reference targets, never as a subject row, and their names do
-- not resolve to any real exercise under another id). These are aspirational
-- progression / regression / physical_proxies targets an author named during DB
-- curation but never added as real entries; several even carry a coaching note
-- baked into the "name" (e.g. "(practice in isolation first)"). They have
-- resolved to nothing silently this whole time (Tier-3 proxy resolution /
-- progression-regression display); the validator just makes them loud.
--
-- Decision (Andy via AskUserQuestion, 2026-06-16): STRIP all 11 dead refs (over
-- authoring the missing exercises — that would be Trigger #2 padding, and most
-- of the names are non-exercise cues). No new vocab; conservative removal only.
--
-- The 5 phantom (never-created) target ids and the 10 active holders:
--   EX059 "Neck Isometric Hold"              — physical_proxy of EX057, EX058,
--                                               EX069, EX140, EX158
--   EX193 "Shooting Breath Control & Stance" — physical_proxy of EX139, EX194;
--                                               regression of EX194
--   EX141 "Wetsuit Swimming Technique"       — regression of EX176
--   EX147 "Loose Surface Threshold Braking"  — regression of EX184
--   EX204 "On-Water Boat Balance Drill"      — progression of EX200
-- → 11 refs across 10 distinct active exercises.
--
-- Edit shape (README §"Two edit shapes"): SERVING-RELEVANT (physical_proxies feed
-- Tier-3 resolution; progression/regression feed display) — supersede + re-insert
-- each affected exercise at the bumped version 0B-v1.6.10 -> 0B-v1.6.11, with the
-- phantom proxy elements removed (order preserved) and any phantom
-- progression/regression id+name cleared to NULL. The reinsert is also the
-- migration's digest-bump carrier, so plan-gen caches invalidate (same mechanism
-- as 0007/0008/0009). No public-schema DDL. No LAYER4_PROMPT_REVISION bump
-- (data-only; cache rides the 0B digest).
--
-- Idempotent: the reinsert is guarded to rows that still reference a phantom AND
-- are not already at 0B-v1.6.11; the reinserted rows carry neither, so a re-run
-- selects nothing. The supersede UPDATE matches only still-active phantom-bearing
-- rows. A re-run is a clean no-op.
--
-- Atomic: the verification DO block RAISEs (rolling back the whole txn) if any
-- active exercise still references a phantom id (progression/regression/
-- physical_proxies) or if the 10 holders were not reinserted at 0B-v1.6.11.

\set ON_ERROR_STOP on

BEGIN;

-- The 5 phantom exercise_ids (referenced but never created). Dropped at COMMIT.
CREATE TEMP TABLE _phantom_ids (exercise_id text PRIMARY KEY) ON COMMIT DROP;
INSERT INTO _phantom_ids (exercise_id) VALUES
  ('EX059'), ('EX141'), ('EX147'), ('EX193'), ('EX204');

-- ── Re-insert each active holder with the phantom refs stripped ───────────────
-- physical_proxies: drop elements naming a phantom (order preserved; non-array /
-- NULL preserved as-is). progression/regression: clear id+name to NULL when the
-- id is a phantom. Every other column copied verbatim; id (serial) + superseded_at
-- (NULL) omitted; version bumped + etl_run_at = now().
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
  e.secondary_muscles, e.equipment_required, e.injury_flags_text, e.contraindicated_parts,
  e.contraindicated_conditions, e.equipment_substitutes,
  CASE
    WHEN jsonb_typeof(e.physical_proxies) = 'array' THEN
      COALESCE(
        (SELECT jsonb_agg(elem ORDER BY ord)
           FROM jsonb_array_elements(e.physical_proxies) WITH ORDINALITY AS u(elem, ord)
          WHERE elem->>'exercise_id' NOT IN (SELECT exercise_id FROM _phantom_ids)),
        '[]'::jsonb)
    ELSE e.physical_proxies
  END,
  CASE WHEN e.progression_exercise_id IN (SELECT exercise_id FROM _phantom_ids)
       THEN NULL ELSE e.progression_exercise_id END,
  CASE WHEN e.progression_exercise_id IN (SELECT exercise_id FROM _phantom_ids)
       THEN NULL ELSE e.progression_exercise_name END,
  CASE WHEN e.regression_exercise_id IN (SELECT exercise_id FROM _phantom_ids)
       THEN NULL ELSE e.regression_exercise_id END,
  CASE WHEN e.regression_exercise_id IN (SELECT exercise_id FROM _phantom_ids)
       THEN NULL ELSE e.regression_exercise_name END,
  e.sport_count, e.coaching_cues,
  '0B-v1.6.11', now(), e.terrain_required, e.equipment_substitutes_structured,
  e.movement_components
FROM layer0.exercises e
WHERE e.superseded_at IS NULL
  AND e.etl_version <> '0B-v1.6.11'
  AND (
        e.progression_exercise_id IN (SELECT exercise_id FROM _phantom_ids)
     OR e.regression_exercise_id IN (SELECT exercise_id FROM _phantom_ids)
     OR EXISTS (
          SELECT 1 FROM jsonb_array_elements(
                 CASE WHEN jsonb_typeof(e.physical_proxies) = 'array'
                      THEN e.physical_proxies ELSE '[]'::jsonb END) p
           WHERE p->>'exercise_id' IN (SELECT exercise_id FROM _phantom_ids))
      );

-- Supersede the old phantom-bearing rows now replaced by the cleaned copies.
UPDATE layer0.exercises e
   SET superseded_at = now()
 WHERE e.superseded_at IS NULL
   AND e.etl_version <> '0B-v1.6.11'
   AND (
         e.progression_exercise_id IN (SELECT exercise_id FROM _phantom_ids)
      OR e.regression_exercise_id IN (SELECT exercise_id FROM _phantom_ids)
      OR EXISTS (
           SELECT 1 FROM jsonb_array_elements(
                  CASE WHEN jsonb_typeof(e.physical_proxies) = 'array'
                       THEN e.physical_proxies ELSE '[]'::jsonb END) p
            WHERE p->>'exercise_id' IN (SELECT exercise_id FROM _phantom_ids))
       );

-- ── Verify (atomic — any failure rolls back the whole migration) ──────────────
DO $$
DECLARE
  v_prog  INT;
  v_regr  INT;
  v_proxy INT;
  v_bumped INT;
BEGIN
  -- No active exercise still references a phantom id.
  SELECT count(*) INTO v_prog
    FROM layer0.exercises
   WHERE superseded_at IS NULL
     AND progression_exercise_id IN (SELECT exercise_id FROM _phantom_ids);
  SELECT count(*) INTO v_regr
    FROM layer0.exercises
   WHERE superseded_at IS NULL
     AND regression_exercise_id IN (SELECT exercise_id FROM _phantom_ids);
  SELECT count(*) INTO v_proxy
    FROM layer0.exercises e, jsonb_array_elements(
           CASE WHEN jsonb_typeof(e.physical_proxies) = 'array'
                THEN e.physical_proxies ELSE '[]'::jsonb END) p
   WHERE e.superseded_at IS NULL
     AND p->>'exercise_id' IN (SELECT exercise_id FROM _phantom_ids);
  IF v_prog + v_regr + v_proxy > 0 THEN
    RAISE EXCEPTION '0010: dangling phantom ref(s) remain (progression=%, regression=%, proxy=%)',
      v_prog, v_regr, v_proxy;
  END IF;

  -- The 10 holders were reinserted at the bumped version (digest carrier).
  SELECT count(*) INTO v_bumped
    FROM layer0.exercises
   WHERE superseded_at IS NULL
     AND etl_version = '0B-v1.6.11';
  IF v_bumped <> 10 THEN
    RAISE EXCEPTION '0010: expected 10 holders reinserted at 0B-v1.6.11, found %', v_bumped;
  END IF;

  RAISE NOTICE '0010: OK — 11 dangling phantom refs stripped across 10 active exercises; reinserted at 0B-v1.6.11';
END $$;

COMMIT;

-- End of 0010_strip_dangling_exercise_refs.sql
