-- 0018_add_evidence_based_cardio_drills.sql
--
-- #698 Track 2 — add three evidence-based cardio drills that fill genuine,
-- non-duplicate gaps in the Interval/Tempo + Aerobic/Endurance pool (the strict
-- no-padding rule: each is a distinct physiological stimulus no existing entry
-- covers). Andy-ratified (AskUserQuestion, 2026-06-19) after a 5-angle
-- deep-research evidence pass; design + citations in
-- aidstation-sources/designs/CardioDrill_EvidenceBased_Additions_EX290-292_2026_06_19.md
--   EX290 Flat VO2max Run Intervals  — flat aerobic-power running; distinct from
--         Hill Repeats (strength-endurance at lower velocity/impact). Strong
--         evidence (Billat; Daniels I-pace; 2025 crossover PMID 39835194).
--   EX291 Swim CSS / Threshold Intervals — first structured swim FITNESS set
--         (Freestyle Pull / Kick are technique-aerobic only). Validated concept
--         (Wakayoshi 1992/93); CSS slightly overestimates MLSS (Dekerle 2005).
--   EX292 Bike Over-Under Intervals  — variable-power threshold for lactate
--         clearance; distinct from steady Threshold/Sweet-Spot. Textbook
--         mechanism (lactate shuttle, MCT1) + practitioner consensus; no RCT
--         isolates the protocol (lowest evidence tier — Andy ratified eyes-open).
--
-- Sequenced after 0017 (the 47-row Technical/Skill cull). None of the three new
-- rows reference a culled exercise — every progression/regression/physical_proxy
-- target is an Interval/Tempo or Aerobic/Endurance row that survives the cull
-- (EX178, EX126, EX073, EX074, EX048, EX090) — so 0017 and 0018 are independent.
--
-- Edit shape (README §"Two edit shapes"): pure additions — three new exercises +
-- their 23 sport_exercise_map rows, inserted at 0B-v1.6.15 -> 0B-v1.6.16 (digest
-- advances; plan-gen caches invalidate). No public-schema DDL. No
-- LAYER4_PROMPT_REVISION bump (data-only; cache rides the 0B digest).
--
-- Idempotent: each exercise INSERT is guarded by NOT EXISTS on an active row with
-- that id; the sport_exercise_map INSERT is guarded per (exercise_id, sport_name).
-- A re-run selects nothing.
--
-- Atomic: the verification DO block RAISEs (rolling back) unless all 3 exercises
-- are active at 0B-v1.6.16, every new row's FK targets are active, exactly 23 new
-- sport_exercise_map rows are active, and the active Interval/Tempo count is 12
-- (= 9 + 3).

\set ON_ERROR_STOP on

BEGIN;

-- ── EX290 — Flat VO2max Run Intervals ─────────────────────────────────────────
INSERT INTO layer0.exercises (
  exercise_id, exercise_name, exercise_type, movement_patterns, primary_muscles,
  secondary_muscles, equipment_required, injury_flags_text, contraindicated_parts,
  contraindicated_conditions, equipment_substitutes, physical_proxies,
  progression_exercise_id, progression_exercise_name, regression_exercise_id,
  regression_exercise_name, sport_count, coaching_cues,
  etl_version, etl_run_at, terrain_required, equipment_substitutes_structured,
  movement_components)
SELECT
  'EX290', 'Flat VO2max Run Intervals', 'Interval / Tempo',
  '{Locomotion}'::text[],
  '{"Aerobic System",Glutes,Hamstrings,"Hip Flexors"}'::text[],
  '{Calves,Core,"Tibialis Anterior"}'::text[],
  '{Treadmill}'::text[],
  'Hamstring — terminal-swing eccentric strain at vVO2max velocity; Achilles — high impact / loading rate vs hill reps; IT Band — if gait breaks down under fatigue',
  '{Hamstring,Achilles,"IT Band"}'::text[],
  '{}'::text[],
  '{"standard": ["400 m running track", "Treadmill at 0–1% grade with pace surges"], "improvised": ["Flat road or path with marked 800–1000 m segments"]}'::jsonb,
  '[{"exercise_id": "EX048", "exercise_name": "Hill Repeats"}, {"exercise_id": "EX074", "exercise_name": "VO2 Max Intervals (Bike)"}]'::jsonb,
  NULL, NULL,
  'EX178', 'Tempo Run (Flat / Road)',
  NULL,
  '3–5 min reps at ~95–100% vVO2max (≈ current 3K–5K race pace; HRmax only reached late in each rep); jog recovery roughly equal to the work bout (~1:1); 4–6 reps. Cap total quality volume at the lesser of 10 km or 8% of weekly mileage. Use 3–5 min reps, not 30–30s — long reps bank more true time at VO2max. 1×/week, ≥48 h from the next hard session. Flat aerobic-power complement to Hill Repeats (strength-endurance at lower impact).',
  '0B-v1.6.16', now(),
  '{Road,"Flat Trail"}'::text[],
  '[{"is_improvised": false, "substitute_text": "400 m running track", "equipment_required": []}, {"is_improvised": false, "substitute_text": "Treadmill at 0–1% grade with pace surges", "equipment_required": [["Treadmill"]]}, {"is_improvised": true, "substitute_text": "Flat road or path with marked 800–1000 m segments", "equipment_required": []}]'::jsonb,
  NULL
WHERE NOT EXISTS (SELECT 1 FROM layer0.exercises WHERE exercise_id='EX290' AND superseded_at IS NULL);

-- ── EX291 — Swim CSS / Threshold Intervals ────────────────────────────────────
INSERT INTO layer0.exercises (
  exercise_id, exercise_name, exercise_type, movement_patterns, primary_muscles,
  secondary_muscles, equipment_required, injury_flags_text, contraindicated_parts,
  contraindicated_conditions, equipment_substitutes, physical_proxies,
  progression_exercise_id, progression_exercise_name, regression_exercise_id,
  regression_exercise_name, sport_count, coaching_cues,
  etl_version, etl_run_at, terrain_required, equipment_substitutes_structured,
  movement_components)
SELECT
  'EX291', 'Swim CSS / Threshold Intervals', 'Interval / Tempo',
  '{"Pull-H",Rotation}'::text[],
  '{"Aerobic System","Latissimus Dorsi",Triceps,"Anterior Deltoid"}'::text[],
  '{Core,Obliques,"Rotator Cuff"}'::text[],
  '{}'::text[],
  'Shoulder — subacromial impingement / rotator-cuff overuse with high-volume short-rest threshold sets; Wrist — entry stress',
  '{Shoulder,Wrist}'::text[],
  '{}'::text[],
  '{"standard": ["Finis Tempo Trainer Pro set to CSS pace"], "improvised": ["Pace clock / poolside timer on the wall"]}'::jsonb,
  '[{"exercise_id": "EX090", "exercise_name": "Paddling Ergometer Session"}]'::jsonb,
  NULL, NULL,
  'EX126', 'Freestyle Pull (With Buoy)',
  NULL,
  'Set CSS first: best 400 m + best 200 m time trial in one session (full recovery between). CSS pace per 100 m = (t400 − t200) ÷ 2; retest every 4–6 weeks. Threshold set: 100–400 m reps at or just above CSS (CSS to CSS−1–2 s/100 m), short rest 10–20 s; ~800–2000 m of threshold volume (e.g. 8–10×100, 5×200, 3×400); 1–2×/week. CSS slightly overestimates true MLSS, so literal-CSS pace sits a hair above threshold — intended. Open-water/swimrun: add ~2–5 s/100 m for no wall push-offs and sighting; wetsuit offsets some.',
  '0B-v1.6.16', now(),
  '{Pool}'::text[],
  '[{"is_improvised": false, "substitute_text": "Finis Tempo Trainer Pro set to CSS pace", "equipment_required": []}, {"is_improvised": true, "substitute_text": "Pace clock / poolside timer on the wall", "equipment_required": []}]'::jsonb,
  NULL
WHERE NOT EXISTS (SELECT 1 FROM layer0.exercises WHERE exercise_id='EX291' AND superseded_at IS NULL);

-- ── EX292 — Bike Over-Under Intervals ─────────────────────────────────────────
INSERT INTO layer0.exercises (
  exercise_id, exercise_name, exercise_type, movement_patterns, primary_muscles,
  secondary_muscles, equipment_required, injury_flags_text, contraindicated_parts,
  contraindicated_conditions, equipment_substitutes, physical_proxies,
  progression_exercise_id, progression_exercise_name, regression_exercise_id,
  regression_exercise_name, sport_count, coaching_cues,
  etl_version, etl_run_at, terrain_required, equipment_substitutes_structured,
  movement_components)
SELECT
  'EX292', 'Bike Over-Under Intervals', 'Interval / Tempo',
  '{Locomotion}'::text[],
  '{"Aerobic System",Quads,Glutes}'::text[],
  '{Core,"Hip Flexors"}'::text[],
  '{"Cycling trainer"}'::text[],
  'Knee — patellofemoral stress at supra-FTP power; Hip Flexor — fatigue at or above threshold',
  '{Knee,"Hip Flexor"}'::text[],
  '{}'::text[],
  '{"standard": ["Outdoor steady climb for the over/under blocks", "Rowing erg over-unders (cross-training)"], "improvised": []}'::jsonb,
  '[{"exercise_id": "EX178", "exercise_name": "Tempo Run (Flat / Road)"}]'::jsonb,
  'EX074', 'VO2 Max Intervals (Bike)',
  'EX073', 'Threshold Intervals (Bike)',
  NULL,
  'Variable-power threshold rep: alternate "under" 90–95% FTP for 2–4 min with "over" 105–110% FTP for 1–2 min; 3+ cycles per rep; 2–3 reps of 10–20 min; ~2:1 work:rest between reps (~8–10 min easy). 1×/week, late-base/build only — establish 2×20 sweet-spot durability first. Trains lactate clearance/buffering at race intensity (produce on the over, clear on the under) — distinct from steady threshold/sweet-spot. Do not make the over too long/hard or the under too short to clear.',
  '0B-v1.6.16', now(),
  '{}'::text[],
  '[{"is_improvised": false, "substitute_text": "Outdoor steady climb for the over/under blocks", "equipment_required": []}, {"is_improvised": false, "substitute_text": "Rowing erg over-unders (cross-training)", "equipment_required": [["Rowing ergometer"]]}]'::jsonb,
  NULL
WHERE NOT EXISTS (SELECT 1 FROM layer0.exercises WHERE exercise_id='EX292' AND superseded_at IS NULL);

-- ── sport_exercise_map: 23 rows for the three new drills ──────────────────────
INSERT INTO layer0.sport_exercise_map (
  exercise_id, exercise_name, exercise_type, sport_name, sport_relevance_note,
  priority, etl_version, etl_run_at)
SELECT v.exercise_id, v.exercise_name, 'Interval / Tempo', v.sport_name, v.note, v.priority,
       '0B-v1.6.16', now()
FROM (VALUES
  -- EX290 Flat VO2max Run Intervals (12)
  ('EX290','Flat VO2max Run Intervals','Marathon','VO2max ceiling underpins sustainable marathon pace; flat aerobic-power complement to tempo work','Critical'),
  ('EX290','Flat VO2max Run Intervals','Mountain Running / Sky Running','Raises aerobic-power ceiling for sustained efforts on runnable grade','High'),
  ('EX290','Flat VO2max Run Intervals','Fell Running','Aerobic-power ceiling for fast fell racing on runnable sections','High'),
  ('EX290','Flat VO2max Run Intervals','Trail Running','Top-end aerobic power for surges and runnable climbs','High'),
  ('EX290','Flat VO2max Run Intervals','Orienteering','Race-pace aerobic power for fast legs','High'),
  ('EX290','Flat VO2max Run Intervals','Obstacle Course Racing','Aerobic power for repeated high-intensity running between obstacles','High'),
  ('EX290','Flat VO2max Run Intervals','Multi-Sport Race','Run-leg aerobic-power ceiling','High'),
  ('EX290','Flat VO2max Run Intervals','Run-Bike-Run Duathlon','Raises run-leg VO2max for both run legs','High'),
  ('EX290','Flat VO2max Run Intervals','Triathlon','Run-leg top-end aerobic power off the bike','High'),
  ('EX290','Flat VO2max Run Intervals','Long Distance Orienteering','Aerobic-power reserve for surges; secondary to threshold/economy at distance','Medium'),
  ('EX290','Flat VO2max Run Intervals','Ultramarathon','Small VO2max reserve; secondary to threshold/economy at ultra distance','Medium'),
  ('EX290','Flat VO2max Run Intervals','SwimRun','Run-leg aerobic power; secondary to threshold','Medium'),
  -- EX291 Swim CSS / Threshold Intervals (3)
  ('EX291','Swim CSS / Threshold Intervals','Swimming','Core swim-fitness session; trains pace at/near aerobic threshold (CSS)','Critical'),
  ('EX291','Swim CSS / Threshold Intervals','Triathlon','Primary swim-fitness set for sustainable open-water pace','Critical'),
  ('EX291','Swim CSS / Threshold Intervals','SwimRun','Threshold swim fitness across repeated water sections','Critical'),
  -- EX292 Bike Over-Under Intervals (8)
  ('EX292','Bike Over-Under Intervals','Road Cycling','Lactate clearance at race intensity for surging/sustained road efforts','Critical'),
  ('EX292','Bike Over-Under Intervals','Gravel Cycling','Buffers repeated over-threshold surges on rolling gravel','Critical'),
  ('EX292','Bike Over-Under Intervals','Triathlon','Sustained-power durability for the bike leg','High'),
  ('EX292','Bike Over-Under Intervals','Run-Bike-Run Duathlon','Bike-leg threshold durability between runs','High'),
  ('EX292','Bike Over-Under Intervals','Mountain Biking','Clears lactate from repeated punchy climbs','High'),
  ('EX292','Bike Over-Under Intervals','XC / AR Cycling','Variable-power durability for adventure-race riding','High'),
  ('EX292','Bike Over-Under Intervals','Bikepacking','Threshold durability for long loaded days; secondary','Medium'),
  ('EX292','Bike Over-Under Intervals','Multi-Sport Race','Bike-leg sustained-power durability; secondary','Medium')
) AS v(exercise_id, exercise_name, sport_name, note, priority)
WHERE NOT EXISTS (
  SELECT 1 FROM layer0.sport_exercise_map m
   WHERE m.superseded_at IS NULL AND m.exercise_id = v.exercise_id AND m.sport_name = v.sport_name);

-- ── Verify (atomic) ───────────────────────────────────────────────────────────
DO $$
DECLARE
  v_ex  INT;
  v_fk  INT;
  v_sem INT;
  v_it  INT;
BEGIN
  SELECT count(*) INTO v_ex FROM layer0.exercises
   WHERE superseded_at IS NULL AND etl_version='0B-v1.6.16'
     AND exercise_id IN ('EX290','EX291','EX292');
  IF v_ex <> 3 THEN RAISE EXCEPTION '0018: expected 3 new exercises at 0B-v1.6.16, found %', v_ex; END IF;

  -- Every new row's progression/regression/physical_proxies target is active.
  SELECT count(*) INTO v_fk FROM layer0.exercises e
   WHERE e.superseded_at IS NULL AND e.exercise_id IN ('EX290','EX291','EX292')
     AND (
       (e.progression_exercise_id IS NOT NULL AND NOT EXISTS
          (SELECT 1 FROM layer0.exercises t WHERE t.superseded_at IS NULL AND t.exercise_id=e.progression_exercise_id))
    OR (e.regression_exercise_id IS NOT NULL AND NOT EXISTS
          (SELECT 1 FROM layer0.exercises t WHERE t.superseded_at IS NULL AND t.exercise_id=e.regression_exercise_id))
    OR EXISTS (SELECT 1 FROM jsonb_array_elements(e.physical_proxies) p
                WHERE NOT EXISTS (SELECT 1 FROM layer0.exercises t
                                   WHERE t.superseded_at IS NULL AND t.exercise_id=p->>'exercise_id'))
     );
  IF v_fk > 0 THEN RAISE EXCEPTION '0018: % new row(s) have a dangling FK target', v_fk; END IF;

  SELECT count(*) INTO v_sem FROM layer0.sport_exercise_map
   WHERE superseded_at IS NULL AND exercise_id IN ('EX290','EX291','EX292');
  IF v_sem <> 23 THEN RAISE EXCEPTION '0018: expected 23 new sport_exercise_map rows, found %', v_sem; END IF;

  SELECT count(*) INTO v_it FROM layer0.exercises
   WHERE superseded_at IS NULL AND exercise_type='Interval / Tempo';
  IF v_it <> 12 THEN RAISE EXCEPTION '0018: expected 12 active Interval/Tempo exercises, found %', v_it; END IF;

  RAISE NOTICE '0018: OK — EX290/EX291/EX292 added with 23 sport_exercise_map rows; Interval/Tempo 9->12';
END $$;

COMMIT;

-- End of 0018_add_evidence_based_cardio_drills.sql
