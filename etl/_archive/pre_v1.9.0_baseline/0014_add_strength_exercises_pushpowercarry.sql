-- 0014_add_strength_exercises_pushpowercarry.sql
--
-- #679 family slice 3 of 4. New layer0 exercises ratified on the #679 review
-- sheet (Andy 2026-06-17: mint, Tier 3). Push/press + KB/power + carries.
-- EX268-EX279. Same standard as the 0012 calibration slice; existing equipment
-- tokens only; general injury flags. MP -> rx via the layer0_progression crosswalk.
--
--   EX268 Dip                 {Push-V} -> Push
--   EX269 Push Press          {Push-V} -> Push (Power)
--   EX270 Clean & Press       {Hinge,Push-V} -> Hinge (Power; generic KB/barbell)
--   EX271 Chest Flye          {Push-H} -> Push
--   EX272 Asymmetric Stability Ball Push-Up {Push-H,Anti-Rotation} -> Push
--   EX273 Snatch              {Hinge,Pull-V} -> Hinge (Power; generic KB/barbell)
--   EX274 Single-Arm KB Swing {Hinge} -> Hinge (Power)
--   EX275 KB Windmill         {Rotation,Anti-Lateral-Flexion} -> Rotation
--   EX276 Sumo Deadlift High Pull {Hinge,Pull-V} -> Hinge (Power)
--   EX277 Sandbag Get-Up      {Anti-Lateral-Flexion,Isometric} -> Core
--   EX278 Rack Carry          {Carry,Isometric} -> Carry (Loaded Carry)
--   EX279 Bear-Hug Carry      {Carry,Isometric} -> Carry (Loaded Carry; the generic
--         loaded-carry "Sandbag / Pack Carry" maps to — KB/DB/backpack load)
--
-- NOTE: Andy asked for "sandbag" as a load option on the carries + get-up. "Sandbag"
-- is NOT yet an equipment-picker token, so these use the existing {Kettlebell,
-- Dumbbell,Backpack} (Backpack = the catalog's improvised heavy-carry load) and
-- name sandbag in the cue. Adding "Sandbag" to the equipment picker is a separate
-- small vocab decision flagged for Andy.
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
  ('EX268','Dip','Strength','{Push-V}'::text[],
   '{"Pectoralis Major",Triceps}'::text[],'{"Anterior Deltoid",Core}'::text[],'{"Dip bars"}'::text[],
   'Shoulder — anterior strain at the bottom if you go too deep; Elbow — triceps-tendon load; Wrist — load on the bars',
   '{Shoulder,Elbow,Wrist}'::text[],'{}'::text[],
   '{"standard": ["Bench Dip", "Push-Up", "Assisted Dip"], "improvised": ["Two sturdy chairs or counters"]}'::jsonb,
   '[{"exercise_id": "EX228", "exercise_name": "Push-Up (Bodyweight)"}, {"exercise_id": "EX235", "exercise_name": "Tricep Pushdown / Extension (Cable / Band)"}]'::jsonb,
   NULL::text,NULL::text,'EX228','Push-Up (Bodyweight)',NULL::integer,
   'Lean the torso forward for a chest bias, stay upright for triceps; control the depth — stop around upper-arms-parallel to protect the shoulder',
   '0B-v1.6.13',now(),'{}'::text[],'[]'::jsonb,NULL::text[]),

  ('EX269','Push Press','Power','{Push-V}'::text[],
   '{"Anterior Deltoid",Triceps}'::text[],'{Quadriceps,Glutes,Core}'::text[],'{Barbell,Dumbbell,Kettlebell}'::text[],
   'Shoulder — overhead impingement; Lumbar — over-arch on the drive; Wrist — bar/bell position in the rack',
   '{Shoulder,"Lower back",Wrist}'::text[],'{}'::text[],
   '{"standard": ["Strict Overhead Press", "Push Jerk", "DB Push Press"], "improvised": ["Two water jugs or a loaded backpack overhead"]}'::jsonb,
   '[{"exercise_id": "EX098", "exercise_name": "DB Shoulder Press"}, {"exercise_id": "EX032", "exercise_name": "Jump Squat (BW or Light Load)"}]'::jsonb,
   NULL,NULL,'EX098','DB Shoulder Press',NULL,
   'A short dip-and-drive from the legs launches the press; transfers leg power to an overhead lockout — keep the ribs down so the low back does not take the load',
   '0B-v1.6.13',now(),'{}'::text[],'[]'::jsonb,NULL),

  ('EX270','Clean & Press','Power','{Hinge,Push-V}'::text[],
   '{Glutes,"Anterior Deltoid"}'::text[],'{Hamstrings,Triceps,Core,"Erector Spinae"}'::text[],'{Kettlebell,Barbell}'::text[],
   'Lumbar — rounding on the clean; Shoulder — overhead lockout; Wrist — the rack catch',
   '{"Lower back",Shoulder,Wrist}'::text[],'{}'::text[],
   '{"standard": ["KB Clean then Press", "Barbell Clean & Press", "DB Clean & Press"], "improvised": ["Sandbag clean to shoulder and press"]}'::jsonb,
   '[{"exercise_id": "EX245", "exercise_name": "Single-Arm KB Clean"}, {"exercise_id": "EX098", "exercise_name": "DB Shoulder Press"}]'::jsonb,
   NULL,NULL,'EX245','Single-Arm KB Clean',NULL,
   'Clean to the rack, then press or push-press overhead; a full-body power-endurance lift — hinge to clean, brace hard to press; works with a kettlebell or barbell',
   '0B-v1.6.13',now(),'{}'::text[],'[]'::jsonb,NULL),

  ('EX271','Chest Flye','Strength','{Push-H}'::text[],
   '{"Pectoralis Major"}'::text[],'{"Anterior Deltoid",Biceps}'::text[],'{Dumbbell,"Cable machine"}'::text[],
   'Shoulder — anterior-capsule stress at the bottom of the stretch; Elbow — keep a soft fixed bend, do not lock or flex',
   '{Shoulder,Elbow}'::text[],'{}'::text[],
   '{"standard": ["Cable Flye", "Pec-Deck", "Band Flye"], "improvised": ["Floor DB flye with a limited range"]}'::jsonb,
   '[{"exercise_id": "EX229", "exercise_name": "Bench Press (Barbell / DB)"}, {"exercise_id": "EX077", "exercise_name": "Doorway Pec Stretch"}]'::jsonb,
   NULL,NULL,'EX229','Bench Press (Barbell / DB)',NULL,
   'Soft fixed elbow angle, hug a wide arc and feel the stretch across the chest; isolation, not a heavy press — protect the shoulder by not over-stretching at the bottom',
   '0B-v1.6.13',now(),'{}'::text[],'[]'::jsonb,NULL),

  ('EX272','Asymmetric Stability Ball Push-Up','Strength','{Push-H,Anti-Rotation}'::text[],
   '{"Pectoralis Major",Core}'::text[],'{Triceps,"Anterior Deltoid",Obliques}'::text[],'{"Stability ball"}'::text[],
   'Shoulder — instability on the uneven base; Wrist — load on the planted hand; Lumbar — if the hips sag or twist',
   '{Shoulder,Wrist,"Lower back"}'::text[],'{}'::text[],
   '{"standard": ["Push-Up", "Offset Push-Up (one hand on a block)"], "improvised": ["One hand on a basketball"]}'::jsonb,
   '[{"exercise_id": "EX228", "exercise_name": "Push-Up (Bodyweight)"}, {"exercise_id": "EX110", "exercise_name": "Antagonist Push-Up (Fist / Flat)"}]'::jsonb,
   NULL,NULL,'EX228','Push-Up (Bodyweight)',NULL,
   'One hand on the ball, one on the floor — the offset adds an anti-rotation core demand to the press; keep the hips level and square, do not let the trunk twist',
   '0B-v1.6.13',now(),'{}'::text[],'[]'::jsonb,NULL),

  ('EX273','Snatch','Power','{Hinge,Pull-V}'::text[],
   '{Glutes,Hamstrings,"Anterior Deltoid"}'::text[],'{Quadriceps,Core,"Erector Spinae"}'::text[],'{Kettlebell,Barbell}'::text[],
   'Lumbar — rounding under speed; Shoulder — the overhead catch; Wrist — the snap-through at lockout',
   '{"Lower back",Shoulder,Wrist}'::text[],'{}'::text[],
   '{"standard": ["KB Snatch", "Barbell Power Snatch", "DB Snatch"], "improvised": ["Single heavy water jug snatch"]}'::jsonb,
   '[{"exercise_id": "EX031", "exercise_name": "Kettlebell Swing (Two-Hand)"}, {"exercise_id": "EX232", "exercise_name": "Hang Clean (Barbell / KB)"}]'::jsonb,
   NULL,NULL,'EX031','Kettlebell Swing (Two-Hand)',NULL,
   'Explosive hip drive sends the load overhead in one motion to a locked-out catch; power-endurance — keep the bell or bar close and punch through at the top; kettlebell or barbell',
   '0B-v1.6.13',now(),'{}'::text[],'[]'::jsonb,NULL),

  ('EX274','Single-Arm KB Swing','Power','{Hinge}'::text[],
   '{Glutes,Hamstrings}'::text[],'{"Erector Spinae",Core,"Anterior Deltoid"}'::text[],'{Kettlebell}'::text[],
   'Lumbar — rounding or over-extending at the top; Shoulder — the single-arm load pulls the trunk into rotation; Grip — fatigue on the one hand',
   '{"Lower back",Shoulder}'::text[],'{}'::text[],
   '{"standard": ["Two-Hand KB Swing", "DB Swing", "Hand-to-hand swing"], "improvised": ["Backpack swing"]}'::jsonb,
   '[{"exercise_id": "EX031", "exercise_name": "Kettlebell Swing (Two-Hand)"}, {"exercise_id": "EX003", "exercise_name": "Romanian Deadlift (Barbell)"}]'::jsonb,
   NULL,NULL,'EX031','Kettlebell Swing (Two-Hand)',NULL,
   'Hinge and snap the hips to float the bell to chest height with one arm; resist the rotation the single arm creates — anti-rotation hip-power endurance',
   '0B-v1.6.13',now(),'{}'::text[],'[]'::jsonb,NULL),

  ('EX275','KB Windmill','Strength','{Rotation,Anti-Lateral-Flexion}'::text[],
   '{Obliques,"Anterior Deltoid"}'::text[],'{Glutes,Hamstrings,Core}'::text[],'{Kettlebell}'::text[],
   'Shoulder — overhead stability under a rotating load; Lumbar — flexion or twisting under load; Hamstring — overstretch on the reach down',
   '{Shoulder,"Lower back",Hamstring}'::text[],'{}'::text[],
   '{"standard": ["DB Windmill", "Bent Press", "Bodyweight windmill"], "improvised": ["Single water jug overhead"]}'::jsonb,
   '[{"exercise_id": "EX249", "exercise_name": "Kettlebell Halo"}, {"exercise_id": "EX016", "exercise_name": "Thoracic Rotation Drill"}]'::jsonb,
   NULL,NULL,'EX249','Kettlebell Halo',NULL,
   'Load locked overhead, eyes on the bell, hinge and rotate to reach the opposite foot while keeping the overhead arm vertical; thoracic mobility plus shoulder and core stability under load',
   '0B-v1.6.13',now(),'{}'::text[],'[]'::jsonb,NULL),

  ('EX276','Sumo Deadlift High Pull','Power','{Hinge,Pull-V}'::text[],
   '{Glutes,Hamstrings,"Mid Traps"}'::text[],'{Quadriceps,"Rear Delts",Biceps,"Erector Spinae"}'::text[],'{Barbell,Kettlebell}'::text[],
   'Lumbar — rounding under speed; Shoulder — the high-pull elevation; Wrist — the pull to the chin',
   '{"Lower back",Shoulder,Wrist}'::text[],'{}'::text[],
   '{"standard": ["Sumo Deadlift", "Upright Row", "KB High Pull"], "improvised": ["Backpack high pull from a wide stance"]}'::jsonb,
   '[{"exercise_id": "EX230", "exercise_name": "Conventional Deadlift (Barbell)"}, {"exercise_id": "EX031", "exercise_name": "Kettlebell Swing (Two-Hand)"}]'::jsonb,
   NULL,NULL,'EX230','Conventional Deadlift (Barbell)',NULL,
   'Wide-stance hinge into an explosive pull that elevates the elbows to chest height; a conditioning power movement — drive with the hips, the arms only finish the pull',
   '0B-v1.6.13',now(),'{}'::text[],'[]'::jsonb,NULL),

  ('EX277','Sandbag Get-Up','Strength','{Anti-Lateral-Flexion,Isometric}'::text[],
   '{Core,Obliques}'::text[],'{Glutes,Quadriceps,"Anterior Deltoid"}'::text[],'{Kettlebell,Dumbbell,Backpack}'::text[],
   'Shoulder — the loaded arm under an unstable load; Lumbar — twisting under load through the transitions; Wrist — supporting the load',
   '{Shoulder,"Lower back",Wrist}'::text[],'{}'::text[],
   '{"standard": ["Turkish Get-Up", "Half Get-Up"], "improvised": ["Loaded backpack hugged to the chest"]}'::jsonb,
   '[{"exercise_id": "EX239", "exercise_name": "Turkish Get-Up (KB / DB)"}, {"exercise_id": "EX089", "exercise_name": "Hollow Body Hold"}]'::jsonb,
   NULL,NULL,'EX239','Turkish Get-Up (KB / DB)',NULL,
   'Stand up from the floor and back down while controlling an unstable load (a sandbag, kettlebell, or loaded pack); full-body anti-lateral-flexion stability through every transition — slow and deliberate',
   '0B-v1.6.13',now(),'{}'::text[],'[]'::jsonb,NULL),

  ('EX278','Rack Carry','Loaded Carry','{Carry,Isometric}'::text[],
   '{Core,"Anterior Deltoid"}'::text[],'{Quadriceps,Glutes,"Upper Back"}'::text[],'{Kettlebell,Dumbbell}'::text[],
   'Lumbar — over-arch under the front-loaded weight; Shoulder — the rack position; Wrist — supporting the bells',
   '{"Lower back",Shoulder,Wrist}'::text[],'{}'::text[],
   '{"standard": ["Front-Rack Carry", "Goblet Carry", "Zercher Carry"], "improvised": ["Loaded backpack held to the chest"]}'::jsonb,
   '[{"exercise_id": "EX009", "exercise_name": "Farmer Carry"}, {"exercise_id": "EX244", "exercise_name": "Overhead Carry / Waiter Walk"}]'::jsonb,
   NULL,NULL,'EX009','Farmer Carry',NULL,
   'Load held in the front-rack at the shoulders, ribs down, brace and walk; an anti-extension core and postural-endurance carry that mirrors a chest-loaded pack',
   '0B-v1.6.13',now(),'{}'::text[],'[]'::jsonb,NULL),

  ('EX279','Bear-Hug Carry','Loaded Carry','{Carry,Isometric}'::text[],
   '{Core,"Upper Back"}'::text[],'{Glutes,Quadriceps,Forearms}'::text[],'{Kettlebell,Dumbbell,Backpack}'::text[],
   'Lumbar — rounding under the hugged load; Hip — instability over a long carry; Grip — sustained squeeze fatigue',
   '{"Lower back",Hip}'::text[],'{}'::text[],
   '{"standard": ["Sandbag Bear-Hug Carry", "Sandbag / Pack Carry", "Zercher Carry"], "improvised": ["Loaded backpack hugged to the chest"]}'::jsonb,
   '[{"exercise_id": "EX095", "exercise_name": "Portage Carry Simulation"}, {"exercise_id": "EX009", "exercise_name": "Farmer Carry"}]'::jsonb,
   NULL,NULL,'EX095','Portage Carry Simulation',NULL,
   'Hug an awkward heavy load (sandbag, pack, or a kettlebell at the chest) and walk while bracing the trunk; the generic loaded carry that mirrors hauling gear over portages and approaches',
   '0B-v1.6.13',now(),'{}'::text[],'[]'::jsonb,NULL)
) AS v
WHERE NOT EXISTS (SELECT 1 FROM layer0.exercises e WHERE e.exercise_id = v.column1 AND e.superseded_at IS NULL);

INSERT INTO layer0.sport_exercise_map (
  exercise_id, exercise_name, exercise_type, sport_name, sport_relevance_note, priority, etl_version, etl_run_at
)
SELECT v.exercise_id, v.exercise_name, v.exercise_type, v.sport_name, v.note, v.priority, '0B-v1.6.13', now()
FROM ( VALUES
  ('EX268','Dip','Strength','General Conditioning','Vertical pressing strength for the chest, triceps, and shoulders','High'),
  ('EX268','Dip','Strength','Rock Climbing','Pressing strength for mantles and topping out','Medium'),
  ('EX268','Dip','Strength','Obstacle Course Racing','Pressing strength for wall climbs and dips over obstacles','Medium'),
  ('EX269','Push Press','Power','General Conditioning','Leg-driven overhead power and shoulder strength','High'),
  ('EX269','Push Press','Power','Obstacle Course Racing','Overhead power for lifting and throwing objects','Medium'),
  ('EX269','Push Press','Power','Kayaking','Overhead pressing power supporting the upper-body drive','Medium'),
  ('EX270','Clean & Press','Power','General Conditioning','Full-body power-endurance from floor to overhead','High'),
  ('EX270','Clean & Press','Power','Obstacle Course Racing','Ground-to-overhead power for sandbags and heavy objects','High'),
  ('EX270','Clean & Press','Power','Hiking','Full-body lifting strength for hoisting and loading packs','Medium'),
  ('EX271','Chest Flye','Strength','General Conditioning','Chest isolation balancing the pressing work','High'),
  ('EX271','Chest Flye','Strength','Rock Climbing','Antagonist chest work balancing heavy pulling','Medium'),
  ('EX272','Asymmetric Stability Ball Push-Up','Strength','General Conditioning','Pressing strength with an added anti-rotation core demand','High'),
  ('EX272','Asymmetric Stability Ball Push-Up','Strength','Rock Climbing','Pressing strength with body-tension control on an unstable base','Medium'),
  ('EX273','Snatch','Power','General Conditioning','Explosive full-body hip power to overhead','High'),
  ('EX273','Snatch','Power','Obstacle Course Racing','Explosive ground-to-overhead power for object lifts','High'),
  ('EX273','Snatch','Power','Rowing','Hip-drive power transferable to the rowing stroke','Medium'),
  ('EX274','Single-Arm KB Swing','Power','General Conditioning','Unilateral hip power with an anti-rotation demand','High'),
  ('EX274','Single-Arm KB Swing','Power','Trail Running','Hip-power endurance and posterior-chain conditioning','Medium'),
  ('EX274','Single-Arm KB Swing','Power','Obstacle Course Racing','Explosive hip drive for jumps, throws, and carries','Medium'),
  ('EX275','KB Windmill','Strength','General Conditioning','Overhead shoulder stability with thoracic mobility and core control','Medium'),
  ('EX275','KB Windmill','Strength','Rock Climbing','Shoulder stability and rotational core control for steep terrain','Medium'),
  ('EX275','KB Windmill','Strength','Kayaking','Rotational core and shoulder stability for the paddle stroke','Medium'),
  ('EX276','Sumo Deadlift High Pull','Power','General Conditioning','Explosive hinge-to-pull conditioning power','High'),
  ('EX276','Sumo Deadlift High Pull','Power','Obstacle Course Racing','Explosive pulling power for heavy drags and lifts','High'),
  ('EX277','Sandbag Get-Up','Strength','General Conditioning','Full-body anti-lateral-flexion stability under an unstable load','High'),
  ('EX277','Sandbag Get-Up','Strength','Obstacle Course Racing','Ground-to-standing strength with awkward heavy objects','High'),
  ('EX277','Sandbag Get-Up','Strength','Hiking','Full-body strength for getting up under a heavy pack','Medium'),
  ('EX278','Rack Carry','Loaded Carry','General Conditioning','Front-loaded anti-extension core and postural-endurance carry','High'),
  ('EX278','Rack Carry','Loaded Carry','Hiking','Chest-loaded carry mirroring a front-loaded pack','High'),
  ('EX278','Rack Carry','Loaded Carry','Obstacle Course Racing','Front-rack carry strength for object carries','Medium'),
  ('EX278','Rack Carry','Loaded Carry','Packrafting','Postural carry strength for hauling gear','Medium'),
  ('EX279','Bear-Hug Carry','Loaded Carry','General Conditioning','Awkward-object loaded carry for total-body bracing endurance','High'),
  ('EX279','Bear-Hug Carry','Loaded Carry','Hiking','Carries the demand of hauling awkward gear over approaches','High'),
  ('EX279','Bear-Hug Carry','Loaded Carry','Packrafting','Hauling boats and gear over portages','High'),
  ('EX279','Bear-Hug Carry','Loaded Carry','Obstacle Course Racing','Sandbag and heavy-object carries','Medium')
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
     AND exercise_id IN ('EX268','EX269','EX270','EX271','EX272','EX273','EX274','EX275','EX276','EX277','EX278','EX279');
  IF v_ex <> 12 THEN RAISE EXCEPTION '0014: expected 12 new exercises at 0B-v1.6.13, found %', v_ex; END IF;

  SELECT count(*) INTO v_map FROM layer0.sport_exercise_map
   WHERE superseded_at IS NULL
     AND exercise_id IN ('EX268','EX269','EX270','EX271','EX272','EX273','EX274','EX275','EX276','EX277','EX278','EX279');
  IF v_map <> 35 THEN RAISE EXCEPTION '0014: expected 35 sport_exercise_map rows, found %', v_map; END IF;

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
    RAISE EXCEPTION '0014: dangling ref(s) (prog=%, regr=%, proxy=%, map=%)', v_prog, v_regr, v_proxy, v_mapfk;
  END IF;

  RAISE NOTICE '0014: OK — 12 push/power/carry strength exercises (EX268-EX279) + 35 sport_exercise_map rows at 0B-v1.6.13';
END $$;

COMMIT;

-- End of 0014_add_strength_exercises_pushpowercarry.sql
