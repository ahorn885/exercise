-- 0015_add_strength_exercises_coreconditioning.sql
--
-- #679 family slice 4 of 4 (final exercise batch). New layer0 exercises ratified
-- on the #679 review sheet (Andy 2026-06-17: mint, Tier 3). Core/plank + rotation
-- + conditioning. EX280-EX289. Same standard as the 0012 calibration slice.
--
--   EX280 Spiderman Plank            {Anti-Extension,Anti-Rotation} -> Core
--   EX281 Side Kick Plank            {Anti-Lateral-Flexion} -> Core
--   EX282 Side Plank Lift            {Anti-Lateral-Flexion} -> Core
--   EX283 Seated Glute Squeeze (Iso) {Isometric} -> Core
--   EX284 Cable Woodchop (Low-to-High) {Rotation} -> Rotation
--   EX285 Plank with Rotation        {Rotation,Anti-Extension} -> Rotation
--   EX286 Side Plank + Banded Leg Raise {Anti-Lateral-Flexion} -> Core
--   EX287 Battle Ropes               {} -> Various (conditioning)
--   EX288 Treadwall Intervals        {} -> Various (cardio-climb)
--   EX289 Forearm Wrist Curls        {} -> Various (wrist flexion)
--
-- NOTE: Battle Ropes / Treadwall need their own equipment-picker tokens ("Battle
-- ropes", "Treadwall") which don't exist yet — minted with empty equipment_required
-- for now (always-feasible) and flagged for Andy alongside "Sandbag" (0014) as a
-- small equipment-vocab decision. Forearm Wrist Curls uses general injury flags only
-- (no athlete-specific wrist warning, per Andy's rule).
--
-- SERVING-RELEVANT: rows carry 0B-v1.6.13. Pure additions, idempotent, atomic verify.

\set ON_ERROR_STOP on

BEGIN;

INSERT INTO layer0.exercises (
  exercise_id, exercise_name, exercise_type, movement_patterns, primary_muscles,
  secondary_muscles, equipment_required, injury_flags_text, contraindicated_parts,
  contraindicated_conditions, equipment_substitutes, physical_proxies,
  progression_exercise_id, progression_exercise_name, regression_exercise_id,
  regression_exercise_name, sport_count, coaching_cues,
  etl_version, etl_run_at, terrain_required, equipment_substitutes_structured, movement_components
)
SELECT * FROM ( VALUES
  ('EX280','Spiderman Plank','Isometric','{Anti-Extension,Anti-Rotation}'::text[],
   '{"Rectus Abdominis",Obliques}'::text[],'{"Hip Flexors","Anterior Deltoid",Glutes}'::text[],'{}'::text[],
   'Lumbar — sagging or rotating hips out of the plank; Shoulder — supporting load; Hip Flexor — cramping on the knee drive',
   '{"Lower back",Shoulder,"Hip Flexor"}'::text[],'{}'::text[],
   '{"standard": ["Front Plank", "Mountain Climber"], "improvised": ["Forearm plank with a slow knee-to-elbow"]}'::jsonb,
   '[{"exercise_id": "EX216", "exercise_name": "Plank (Front)"}, {"exercise_id": "EX221", "exercise_name": "Mountain Climber"}]'::jsonb,
   NULL::text,NULL::text,'EX216','Plank (Front)',NULL::integer,
   'Hold a strict plank and slowly drive one knee out to the same-side elbow without letting the hips drop or twist; anti-extension and anti-rotation core under a moving load',
   '0B-v1.6.13',now(),'{}'::text[],'[]'::jsonb,NULL::text[]),

  ('EX281','Side Kick Plank','Isometric','{Anti-Lateral-Flexion}'::text[],
   '{Obliques,"Quadratus Lumborum"}'::text[],'{Glutes,"Hip Abductors",Core}'::text[],'{}'::text[],
   'Shoulder — load on the bottom arm; Lumbar — sagging hips; Hip — instability on the kick',
   '{Shoulder,"Lower back",Hip}'::text[],'{}'::text[],
   '{"standard": ["Side Plank", "Side Plank with Leg Lift"], "improvised": ["Knees-down side plank regression"]}'::jsonb,
   '[{"exercise_id": "EX219", "exercise_name": "Side Plank"}, {"exercise_id": "EX012", "exercise_name": "Copenhagen Plank"}]'::jsonb,
   NULL,NULL,'EX219','Side Plank',NULL,
   'Hold a side plank and kick the top leg forward and back without letting the hips drop; anti-lateral-flexion core plus hip control',
   '0B-v1.6.13',now(),'{}'::text[],'[]'::jsonb,NULL),

  ('EX282','Side Plank Lift','Isometric','{Anti-Lateral-Flexion}'::text[],
   '{Obliques,"Quadratus Lumborum"}'::text[],'{Glutes,"Hip Abductors",Core}'::text[],'{}'::text[],
   'Shoulder — load on the bottom arm; Lumbar — sagging or hiking the hips; Hip — instability through the lift',
   '{Shoulder,"Lower back",Hip}'::text[],'{}'::text[],
   '{"standard": ["Side Plank hold", "Copenhagen Plank"], "improvised": ["Knees-down side plank lift"]}'::jsonb,
   '[{"exercise_id": "EX219", "exercise_name": "Side Plank"}, {"exercise_id": "EX012", "exercise_name": "Copenhagen Plank"}]'::jsonb,
   NULL,NULL,'EX219','Side Plank',NULL,
   'From a side plank, lower the hip toward the floor and lift it back up under control; a dynamic anti-lateral-flexion variation that loads the obliques through a range',
   '0B-v1.6.13',now(),'{}'::text[],'[]'::jsonb,NULL),

  ('EX283','Seated Glute Squeeze (Isometric)','Isometric','{Isometric}'::text[],
   '{Glutes}'::text[],'{Hamstrings,Core}'::text[],'{}'::text[],
   'Lumbar — over-arching while squeezing; Hamstring — cramping if over-gripped',
   '{"Lower back",Hamstring}'::text[],'{}'::text[],
   '{"standard": ["Glute Bridge hold", "Standing glute squeeze"], "improvised": ["Seated isometric squeeze, no equipment"]}'::jsonb,
   '[{"exercise_id": "EX039", "exercise_name": "Glute Bridge (Double-Leg)"}, {"exercise_id": "EX013", "exercise_name": "Hip Circle (Band)"}]'::jsonb,
   NULL,NULL,'EX039','Glute Bridge (Double-Leg)',NULL,
   'Seated tall, squeeze the glutes hard and hold without arching the low back; a low-skill activation hold to wake up the glutes before lower-body work or after long sitting',
   '0B-v1.6.13',now(),'{}'::text[],'[]'::jsonb,NULL),

  ('EX284','Cable Woodchop (Low-to-High)','Strength','{Rotation}'::text[],
   '{Obliques,Core}'::text[],'{"Anterior Deltoid",Glutes,"Erector Spinae"}'::text[],'{"Cable machine","Resistance band"}'::text[],
   'Lumbar — rotating from the spine instead of the hips; Shoulder — if the arms drive the motion',
   '{"Lower back",Shoulder}'::text[],'{}'::text[],
   '{"standard": ["Cable High-to-Low Chop", "Landmine Rotation", "Band low-to-high chop"], "improvised": ["Band anchored low to a post"]}'::jsonb,
   '[{"exercise_id": "EX087", "exercise_name": "Cable High-to-Low Chop"}, {"exercise_id": "EX086", "exercise_name": "Landmine Rotation"}]'::jsonb,
   NULL,NULL,'EX087','Cable High-to-Low Chop',NULL,
   'Drive the handle from low at one hip up across the body, rotating from the hips and trunk — not the arms; the upward diagonal that complements the high-to-low chop',
   '0B-v1.6.13',now(),'{}'::text[],'[]'::jsonb,NULL),

  ('EX285','Plank with Rotation','Isometric','{Rotation,Anti-Extension}'::text[],
   '{Obliques,"Rectus Abdominis"}'::text[],'{"Anterior Deltoid",Core,Glutes}'::text[],'{}'::text[],
   'Lumbar — sagging the hips while rotating; Shoulder — load on the supporting arm; Wrist — on the planted hand',
   '{"Lower back",Shoulder,Wrist}'::text[],'{}'::text[],
   '{"standard": ["Side Plank Rotation", "Thread-the-Needle plank", "T-rotation push-up"], "improvised": ["Forearm plank with a slow reach-through"]}'::jsonb,
   '[{"exercise_id": "EX216", "exercise_name": "Plank (Front)"}, {"exercise_id": "EX219", "exercise_name": "Side Plank"}]'::jsonb,
   NULL,NULL,'EX216','Plank (Front)',NULL,
   'From a plank, rotate the trunk to reach one arm under the body and then open up toward the ceiling; controlled rotation on a braced anti-extension base',
   '0B-v1.6.13',now(),'{}'::text[],'[]'::jsonb,NULL),

  ('EX286','Side Plank + Banded Leg Raise','Isometric','{Anti-Lateral-Flexion}'::text[],
   '{Obliques,"Hip Abductors"}'::text[],'{Glutes,"Quadratus Lumborum",Core}'::text[],'{"Resistance band"}'::text[],
   'Shoulder — load on the bottom arm; Lumbar — sagging hips; Hip — abductor cramping under the band',
   '{Shoulder,"Lower back",Hip}'::text[],'{}'::text[],
   '{"standard": ["Side Plank", "Side-Lying Banded Abduction"], "improvised": ["Side plank with an unweighted leg raise"]}'::jsonb,
   '[{"exercise_id": "EX219", "exercise_name": "Side Plank"}, {"exercise_id": "EX017", "exercise_name": "Lateral Band Walk"}]'::jsonb,
   NULL,NULL,'EX219','Side Plank',NULL,
   'Hold a side plank and raise the top leg against band tension; stacks anti-lateral-flexion core with loaded hip abduction for lateral hip and trunk strength',
   '0B-v1.6.13',now(),'{}'::text[],'[]'::jsonb,NULL),

  ('EX287','Battle Ropes','Power','{}'::text[],
   '{"Anterior Deltoid",Forearms}'::text[],'{Core,"Upper Back","Aerobic System"}'::text[],'{}'::text[],
   'Shoulder — sustained overhead-adjacent work under fatigue; Lumbar — if you round to generate waves; Grip — forearm fatigue',
   '{Shoulder,"Lower back"}'::text[],'{}'::text[],
   '{"standard": ["Heavier or longer ropes", "Sled push intervals", "Assault bike intervals"], "improvised": ["Anchored heavy rope or thick band waves"]}'::jsonb,
   '[{"exercise_id": "EX029", "exercise_name": "Sled Push"}, {"exercise_id": "EX238", "exercise_name": "Burpee"}]'::jsonb,
   NULL,NULL,'EX029','Sled Push',NULL,
   'Drive waves down the ropes from the hips and shoulders for timed intervals; upper-body power-endurance conditioning — progress by heavier or longer ropes or a longer work interval',
   '0B-v1.6.13',now(),'{}'::text[],'[]'::jsonb,NULL),

  ('EX288','Treadwall Intervals','Interval / Tempo','{}'::text[],
   '{"Latissimus Dorsi",Forearms}'::text[],'{Biceps,Core,"Aerobic System"}'::text[],'{}'::text[],
   'Forearm — sustained grip pump and pulley load on small holds; Shoulder — high pulling volume',
   '{Forearm,Shoulder}'::text[],'{}'::text[],
   '{"standard": ["Roped wall laps", "Bouldering circuits", "Hangboard repeaters"], "improvised": ["Continuous traversing on a home wall"]}'::jsonb,
   '[{"exercise_id": "EX113", "exercise_name": "Movement on Route (Top-Rope / Lead)"}, {"exercise_id": "EX100", "exercise_name": "Hangboard Half-Crimp Hold"}]'::jsonb,
   NULL,NULL,'EX113','Movement on Route (Top-Rope / Lead)',NULL,
   'Continuous climbing on a rotating wall for timed intervals; builds climbing-specific aerobic capacity and grip endurance — control the pace and breathing rather than sprinting',
   '0B-v1.6.13',now(),'{}'::text[],'[]'::jsonb,NULL),

  ('EX289','Forearm Wrist Curls','Strength','{}'::text[],
   '{"Forearm Flexors"}'::text[],'{Forearms}'::text[],'{Dumbbell,Kettlebell,Barbell,"Cable machine","Resistance band"}'::text[],
   'Wrist — flexion load on the joint; Elbow — if the forearm is not supported and you swing the load',
   '{Wrist,Elbow}'::text[],'{}'::text[],
   '{"standard": ["Reverse Wrist Curl (extension)", "Wrist Roller", "Cable wrist curl"], "improvised": ["Single light DB or water jug, forearm on the thigh"]}'::jsonb,
   '[{"exercise_id": "EX111", "exercise_name": "Reverse Wrist Curl (DB)"}, {"exercise_id": "EX103", "exercise_name": "Wrist Roller"}]'::jsonb,
   NULL,NULL,'EX111','Reverse Wrist Curl (DB)',NULL,
   'Forearm supported, curl the wrist up against the load through a full range; trains wrist-flexor and grip strength as the counterpart to the reverse (extension) wrist curl',
   '0B-v1.6.13',now(),'{}'::text[],'[]'::jsonb,NULL)
) AS v
WHERE NOT EXISTS (SELECT 1 FROM layer0.exercises e WHERE e.exercise_id = v.column1 AND e.superseded_at IS NULL);

INSERT INTO layer0.sport_exercise_map (
  exercise_id, exercise_name, exercise_type, sport_name, sport_relevance_note, priority, etl_version, etl_run_at
)
SELECT v.exercise_id, v.exercise_name, v.exercise_type, v.sport_name, v.note, v.priority, '0B-v1.6.13', now()
FROM ( VALUES
  ('EX280','Spiderman Plank','Isometric','General Conditioning','Anti-extension and anti-rotation core under a moving load','High'),
  ('EX280','Spiderman Plank','Isometric','Rock Climbing','Core tension and body control for steep terrain','Medium'),
  ('EX281','Side Kick Plank','Isometric','General Conditioning','Anti-lateral-flexion core with dynamic hip control','High'),
  ('EX281','Side Kick Plank','Isometric','Rock Climbing','Lateral core and hip control for flagging and body tension','Medium'),
  ('EX282','Side Plank Lift','Isometric','General Conditioning','Dynamic oblique strength through a loaded range','High'),
  ('EX282','Side Plank Lift','Isometric','Trail Running','Lateral trunk strength for stability on uneven terrain','Medium'),
  ('EX283','Seated Glute Squeeze (Isometric)','Isometric','General Conditioning','Low-skill glute activation hold to prime lower-body work','Medium'),
  ('EX284','Cable Woodchop (Low-to-High)','Strength','General Conditioning','Rotational power through an upward diagonal','High'),
  ('EX284','Cable Woodchop (Low-to-High)','Strength','Kayaking','Trunk rotation power for the paddle stroke','Medium'),
  ('EX284','Cable Woodchop (Low-to-High)','Strength','Packrafting','Rotational strength for paddling propulsion','Medium'),
  ('EX285','Plank with Rotation','Isometric','General Conditioning','Controlled rotation on a braced anti-extension base','High'),
  ('EX285','Plank with Rotation','Isometric','Kayaking','Rotational trunk control with core stability for paddling','Medium'),
  ('EX286','Side Plank + Banded Leg Raise','Isometric','General Conditioning','Anti-lateral-flexion core stacked with loaded hip abduction','High'),
  ('EX286','Side Plank + Banded Leg Raise','Isometric','Trail Running','Lateral hip and trunk strength for stable single-leg stance','Medium'),
  ('EX287','Battle Ropes','Power','General Conditioning','Upper-body power-endurance conditioning','High'),
  ('EX287','Battle Ropes','Power','Obstacle Course Racing','Grip and upper-body conditioning for sustained efforts','Medium'),
  ('EX288','Treadwall Intervals','Interval / Tempo','Rock Climbing','Climbing-specific aerobic capacity and grip endurance','High'),
  ('EX288','Treadwall Intervals','Interval / Tempo','General Conditioning','Sustained pulling and grip conditioning','Medium'),
  ('EX289','Forearm Wrist Curls','Strength','General Conditioning','Wrist-flexor and grip strength balancing the extensors','Medium'),
  ('EX289','Forearm Wrist Curls','Strength','Rock Climbing','Grip and wrist strength for crimps and sustained holds','High'),
  ('EX289','Forearm Wrist Curls','Strength','Kayaking','Grip and forearm endurance for the paddle','Medium')
) AS v(exercise_id, exercise_name, exercise_type, sport_name, note, priority)
WHERE NOT EXISTS (
  SELECT 1 FROM layer0.sport_exercise_map m
   WHERE m.exercise_id = v.exercise_id AND m.sport_name = v.sport_name AND m.superseded_at IS NULL
);

DO $$
DECLARE v_ex INT; v_map INT; v_prog INT; v_regr INT; v_proxy INT; v_mapfk INT;
BEGIN
  SELECT count(*) INTO v_ex FROM layer0.exercises
   WHERE superseded_at IS NULL AND etl_version='0B-v1.6.13'
     AND exercise_id IN ('EX280','EX281','EX282','EX283','EX284','EX285','EX286','EX287','EX288','EX289');
  IF v_ex <> 10 THEN RAISE EXCEPTION '0015: expected 10 new exercises at 0B-v1.6.13, found %', v_ex; END IF;

  SELECT count(*) INTO v_map FROM layer0.sport_exercise_map
   WHERE superseded_at IS NULL
     AND exercise_id IN ('EX280','EX281','EX282','EX283','EX284','EX285','EX286','EX287','EX288','EX289');
  IF v_map <> 21 THEN RAISE EXCEPTION '0015: expected 21 sport_exercise_map rows, found %', v_map; END IF;

  SELECT count(*) INTO v_prog FROM layer0.exercises e WHERE e.superseded_at IS NULL AND e.progression_exercise_id IS NOT NULL
     AND NOT EXISTS (SELECT 1 FROM layer0.exercises a WHERE a.superseded_at IS NULL AND a.exercise_id=e.progression_exercise_id);
  SELECT count(*) INTO v_regr FROM layer0.exercises e WHERE e.superseded_at IS NULL AND e.regression_exercise_id IS NOT NULL
     AND NOT EXISTS (SELECT 1 FROM layer0.exercises a WHERE a.superseded_at IS NULL AND a.exercise_id=e.regression_exercise_id);
  SELECT count(*) INTO v_proxy FROM layer0.exercises e, jsonb_array_elements(
           CASE WHEN jsonb_typeof(e.physical_proxies)='array' THEN e.physical_proxies ELSE '[]'::jsonb END) p
   WHERE e.superseded_at IS NULL AND p->>'exercise_id' IS NOT NULL
     AND NOT EXISTS (SELECT 1 FROM layer0.exercises a WHERE a.superseded_at IS NULL AND a.exercise_id=p->>'exercise_id');
  SELECT count(*) INTO v_mapfk FROM layer0.sport_exercise_map m WHERE m.superseded_at IS NULL
     AND NOT EXISTS (SELECT 1 FROM layer0.exercises a WHERE a.superseded_at IS NULL AND a.exercise_id=m.exercise_id);
  IF v_prog + v_regr + v_proxy + v_mapfk > 0 THEN
    RAISE EXCEPTION '0015: dangling ref(s) (prog=%, regr=%, proxy=%, map=%)', v_prog, v_regr, v_proxy, v_mapfk;
  END IF;

  RAISE NOTICE '0015: OK — 10 core/conditioning strength exercises (EX280-EX289) + 21 sport_exercise_map rows at 0B-v1.6.13';
END $$;

COMMIT;

-- End of 0015_add_strength_exercises_coreconditioning.sql
