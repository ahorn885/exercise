-- populate_terrain_gap_rules.sql
-- Creates layer0.terrain_gap_rules and inserts 16 canonical gap rows.
-- (12 original + 2 from Bucket C (f) WaterVocab 2026-05-24 + 2 from Bucket C
-- (g) Terrain↔Equipment merge 2026-05-24.)
--
-- Purpose: enables 2B (Terrain Classifier) to operate as a pure query node.
-- Given race terrain IDs and locale terrain IDs, plan-gen calls this table
-- to get gap severity, adaptation windows, proxy methods, and prescription
-- notes — no LLM needed for terrain gap classification.
--
-- gap_severity enum (post-Phase-2.3 reclassification per Andy 2026-05-19):
--   low          — proxy_fidelity ≥ 0.70  (high transfer; minimal real-terrain practice needed)
--   medium       — proxy_fidelity 0.50–0.69
--   high         — proxy_fidelity 0.40–0.49
--   critical     — proxy_fidelity < 0.40   (large gap; significant real-terrain block required)
--   unbridgeable — proxy_terrain_id IS NULL  (skill/technique cannot close off-terrain at all)
--
-- Existing rows in this file still carry the pre-Phase-2.3 'partial' tag
-- and are reclassified at deploy time by the idempotent _PG_MIGRATIONS
-- UPDATE keyed on the bands above. NEW rows added after 2026-05-19 should
-- use the post-reclassification value directly (see TRN-017 rules below).
--
-- proxy_fidelity: 0.0–1.0, consistent with discipline_substitutes.fidelity convention
--
-- uncoverable_stimulus values: drawn from the stimulus_components enum on disciplines
--   aerobic_low | aerobic_high | muscular_endurance_legs | muscular_endurance_upper |
--   pack_carry_load | vertical_gain | technical_descent | technical_handwork |
--   grip_strength | balance_dynamic | cold_exposure | fueling_practice |
--   cognitive_navigation | explosive_power
--
-- etl_version: '0C-v2.0-r2' — paired with terrain_types migration
-- Safe to re-run: CREATE TABLE IF NOT EXISTS + ON CONFLICT DO NOTHING on INSERTs

BEGIN;

-- ── 1. Create table ────────────────────────────────────────────────────────

CREATE TABLE IF NOT EXISTS layer0.terrain_gap_rules (
  id                    SERIAL PRIMARY KEY,
  target_terrain_id     TEXT        NOT NULL,
  target_terrain_name   TEXT        NOT NULL,
  proxy_terrain_id      TEXT,                    -- NULL = no meaningful proxy exists
  proxy_terrain_name    TEXT,
  gap_severity          TEXT        NOT NULL,
  adaptation_weeks_low  INTEGER,
  adaptation_weeks_high INTEGER,
  proxy_fidelity        NUMERIC,
  proxy_methods         TEXT[]      NOT NULL,
  uncoverable_stimulus  TEXT[]      NOT NULL,
  prescription_note     TEXT        NOT NULL,
  audit_log             TEXT,

  etl_version           TEXT        NOT NULL,
  etl_run_at            TIMESTAMPTZ NOT NULL,
  superseded_at         TIMESTAMPTZ,

  UNIQUE (target_terrain_id, proxy_terrain_id, etl_version)
);

-- ── 2. Insert 16 gap rules ─────────────────────────────────────────────────

INSERT INTO layer0.terrain_gap_rules (
  target_terrain_id, target_terrain_name,
  proxy_terrain_id,  proxy_terrain_name,
  gap_severity, adaptation_weeks_low, adaptation_weeks_high, proxy_fidelity,
  proxy_methods, uncoverable_stimulus, prescription_note, audit_log,
  etl_version, etl_run_at
) VALUES

-- ── Foot: Mountain / Alpine gaps ───────────────────────────────────────────

( 'TRN-005', 'Mountain / Alpine',
  'TRN-001', 'Road / Paved',
  'partial', 8, 12, 0.40,
  ARRAY[
    'Max-incline treadmill (10–15% grade sustained)',
    'Stair climber (sustained, with pack)',
    'Weighted vest step-ups (3–4 sets × 20 reps, 2–3×/wk)',
    'Loaded stairwell repeats where available'
  ],
  ARRAY['technical_descent', 'balance_dynamic'],
  'Simulate vertical with max-incline treadmill and stair climber; weighted vest builds pack-load tolerance. '
    'Aerobic adaptation to climbing transfers well. No descent EIMD adaptation is possible without actual downhill terrain — '
    'plan 2–3 downhill-specific sessions in the final 4 weeks if any mountain access becomes available.',
  'Descent EIMD: Clarkson & Hubal (2002), Exp Physiol; Treadmill incline as vert proxy: '
    'Harriss et al. (2019), IJSPP — incline >10% produces comparable metabolic load to mountain grades. '
    'Proxy fidelity 0.40 reflects aerobic transfer minus descent mechanics and proprioceptive adaptation.',
  '0C-v2.0-r2', NOW() ),

( 'TRN-005', 'Mountain / Alpine',
  'TRN-004', 'Hill / Rolling',
  'partial', 6, 10, 0.60,
  ARRAY[
    'Sustained hill repeats at maximum available grade',
    'Stair climber to supplement available vert',
    'Weighted vest on all hill sessions in peak phase'
  ],
  ARRAY['technical_descent', 'balance_dynamic'],
  'Hill repeats are the best available proxy for mountain aerobic load. '
    'Prioritize longest sustained climbing available; use stair climber to supplement vert quota. '
    'Descent adaptation still limited — seek any downhill running opportunity.',
  'Proxy fidelity 0.60 — aerobic and vertical load transfer well from sustained hills; '
    'descent EIMD and technical alpine exposure remain uncovered.',
  '0C-v2.0-r2', NOW() ),

( 'TRN-005', 'Mountain / Alpine',
  'TRN-016', 'Indoor / Gym',
  'partial', 10, 14, 0.30,
  ARRAY[
    'Stair climber (primary — maximum sustainable duration)',
    'Max-incline treadmill intervals',
    'Weighted vest loaded step-ups',
    'Single-leg leg press for descent quad endurance'
  ],
  ARRAY['technical_descent', 'vertical_gain', 'balance_dynamic'],
  'Significant terrain gap. Stair climber is the primary tool; build toward 45–60 min continuous sessions with pack. '
    'Expect 10–14 weeks to develop meaningful vertical base from a flat-only starting point. '
    'No descent adaptation is achievable — prioritize single-leg quad strength as partial compensation.',
  'Proxy fidelity 0.30 — indoor simulation covers cardiorespiratory adaptation only. '
    'Vertical gain stimulus partial; descent and balance stimuli absent entirely.',
  '0C-v2.0-r2', NOW() ),

-- ── Foot: Technical Trail gaps ─────────────────────────────────────────────

( 'TRN-003', 'Technical Trail',
  'TRN-002', 'Groomed Trail',
  'partial', 4, 8, 0.60,
  ARRAY[
    'Roughest available local trail surface (prioritize any loose or uneven sections)',
    'Agility ladder drills 2×/wk (lateral speed, foot placement precision)',
    'Single-leg balance work on unstable surface (BOSU, wobble board)',
    'Trail shoes worn on all outdoor runs regardless of surface'
  ],
  ARRAY['balance_dynamic'],
  'Use the most varied terrain available at all times. Agility and single-leg stability work '
    'address proprioceptive demand. Plan 4–6 sessions on actual technical terrain in the 6 weeks '
    'before the race — ankle adaptation to variable surface requires real terrain.',
  'Proprioceptive surface adaptation timeline: Myer et al. (2006), J Athl Train — '
    '4–6 weeks on actual surface required for meaningful neuromuscular adaptation. '
    'Balance work transfers ~60% of stimulus. Proxy fidelity 0.60.',
  '0C-v2.0-r2', NOW() ),

( 'TRN-003', 'Technical Trail',
  'TRN-001', 'Road / Paved',
  'partial', 8, 10, 0.35,
  ARRAY[
    'Any available trail surface (gravel, dirt, uneven) in preference to road',
    'Agility ladder and cone drills 2–3×/wk',
    'Single-leg stability training (wobble board, single-leg deadlift, lateral hops)',
    'Trail shoes on all sessions'
  ],
  ARRAY['balance_dynamic'],
  'Meaningful gap — road provides no proprioceptive transfer to technical trail. '
    'Prioritize any trail access over road. Agility and single-leg work are the primary tools. '
    'Plan minimum 6 sessions on technical terrain before race.',
  'Proxy fidelity 0.35 — aerobic base transfers; surface-specific adaptation negligible on road.',
  '0C-v2.0-r2', NOW() ),

-- ── Foot: Fell / Moorland gap ──────────────────────────────────────────────

( 'TRN-006', 'Fell / Moorland',
  'TRN-002', 'Groomed Trail',
  'partial', 6, 8, 0.45,
  ARRAY[
    'Off-trail hiking sessions on any available unmaintained terrain',
    'Map and compass navigation training (mandatory — any terrain)',
    'Night sessions for navigation-under-fatigue practice',
    'Grass/soft-surface running where available'
  ],
  ARRAY['cognitive_navigation', 'balance_dynamic'],
  'Fell terrain is primarily a navigation and footing challenge. Groomed trail covers aerobic load only. '
    'Mandatory: map and compass training on any terrain, minimum 2 orienteering sessions before race. '
    'Seek any unmaintained, pathless terrain for off-trail movement practice.',
  'Cognitive navigation under fatigue: Dyer et al. (2016) on sleep deprivation and spatial navigation — '
    'fell racing demands real-terrain navigation practice; no marked-course substitute. '
    'Proxy fidelity 0.45 — aerobic load transfers; navigation and footing stimuli substantially uncovered.',
  '0C-v2.0-r2', NOW() ),

-- ── Foot: Gravel gaps ──────────────────────────────────────────────────────
--
-- TRN-020 added by Bucket C sub-item (g) terrain↔equipment merge 2026-05-24
-- as the unambiguous surface gap (TRN-001 paved + TRN-002 dirt singletrack
-- bracket gravel but neither captures the compacted-loose-aggregate surface).
-- TRN serves both gravel-running and gravel-cycling stimuli; modality is
-- captured discipline-side + equipment-side per the surface-only terrain
-- principle. Two proxies registered: TRN-002 (singletrack — closer surface,
-- low band) and TRN-001 (paved — gait/aerobic only, medium band). Classifier
-- ORDER BY proxy_fidelity DESC picks whichever the athlete has access to.

( 'TRN-020', 'Gravel',
  'TRN-002', 'Groomed Trail',
  'low', 1, 2, 0.70,
  ARRAY[
    'Groomed singletrack sessions (high transfer for unpaved-surface gait and aerobic load)',
    'Periodic paved runs for sustained pace work if singletrack volume is variable'
  ],
  ARRAY[]::TEXT[],
  'Groomed singletrack covers unpaved-surface gait adaptation and aerobic load at high fidelity. '
    'The only gravel-specific stimulus partially uncovered is the loose-aggregate slip behaviour '
    '(micro-foot-placement adjustments + occasional embedded rocks); 1–2 gravel-specific sessions '
    'before race close the gap. For gravel-cycling use, MTB-trail riding similarly over-covers the '
    'bike-handling stimulus.',
  'Proxy fidelity 0.70 — singletrack and gravel share the unpaved-surface adaptation; only the loose '
    'aggregate stimulus is gravel-specific. Severity classified ''low'' per the post-Phase-2.3 '
    'fidelity-banded enum (≥0.70 = low).',
  '0C-v2.0-r2', NOW() ),

( 'TRN-020', 'Gravel',
  'TRN-001', 'Road / Paved',
  'medium', 2, 4, 0.65,
  ARRAY[
    'Paved runs for sustained aerobic and cadence work (full fidelity for gait and pace)',
    '2–4 gravel-specific sessions on any unpaved compacted surface before race for surface adaptation',
    'Trail running on any singletrack as a secondary proxy if available'
  ],
  ARRAY['balance_dynamic'],
  'Paved running covers gait, aerobic base, and pace control at full fidelity. The gravel-specific '
    'surface adaptation (slip behaviour, micro-instability, occasional embedded rocks) requires real '
    'gravel exposure. Plan 2–4 gravel sessions in the final 4 weeks before race; for gravel-cycling '
    'use, the same applies via gravel-bike or MTB on any compacted-aggregate surface.',
  'Proxy fidelity 0.65 — paved running keeps full gait/aerobic transfer; the unpaved-surface stimulus '
    'requires real gravel practice. Severity classified ''medium'' per the post-Phase-2.3 fidelity-'
    'banded enum (0.50–0.69 = medium).',
  '0C-v2.0-r2', NOW() ),

-- ── Water: Ocean / Tidal gap ───────────────────────────────────────────────

( 'TRN-010', 'Ocean / Tidal',
  'TRN-008', 'Pool',
  'partial', 4, 6, 0.65,
  ARRAY[
    'Pool aerobic base sessions (primary)',
    'Sighting drill simulation in pool (lift head every 6–8 strokes)',
    'Cold exposure acclimatization (cold showers, cold baths — progressive)',
    'Paddling ergometer for arm endurance if swim is not primary discipline'
  ],
  ARRAY['cold_exposure', 'balance_dynamic'],
  'Pool maintains aerobic base and stroke mechanics — high transfer. '
    'Schedule minimum 4 open water sessions before the race for sighting, '
    'conditions handling, and wetsuit practice. Wetsuit trial is mandatory if race requires one. '
    'Cold water shock response is not trainable in a pool — cold exposure protocol required.',
  'OW-specific adaptation: Knechtle et al. (2021), IJMS — pool-to-OW transfer is high for aerobic capacity '
    'but sighting adds 3–5% metabolic cost (Toussaint 1992); mass start psychology not trainable in pool. '
    'Cold shock: Tipton (2012), Exp Physiol — habituation requires real cold water immersion. '
    'Proxy fidelity 0.65.',
  '0C-v2.0-r2', NOW() ),

-- ── Water: Flat Water gap ──────────────────────────────────────────────────

( 'TRN-009', 'Flat Water',
  'TRN-008', 'Pool',
  'partial', 2, 4, 0.75,
  ARRAY[
    'Pool swimming (aerobic base — high transfer for swim disciplines)',
    'Paddling ergometer (arm and torso endurance for paddle disciplines)',
    'Open water sessions on any calm water body'
  ],
  ARRAY['cold_exposure'],
  'Pool is a high-fidelity proxy for flat water aerobic base. '
    '2–4 open water sessions confirm conditions handling and pacing. '
    'For paddle disciplines specifically, ergometer is preferred over pool.',
  'Proxy fidelity 0.75 — flat water imposes minimal conditions variables beyond basic OW exposure.',
  '0C-v2.0-r2', NOW() ),

-- ── Water: Moving Water gaps ───────────────────────────────────────────────
--
-- TRN-017 was added when the Water vocab split into 5 rows (Pool / Flat /
-- Moving / Ocean-Tidal / Whitewater) per Bucket C (f) closure 2026-05-24.
-- Two proxies registered: TRN-009 (lake — common case) and TRN-011
-- (whitewater — over-covered). Classifier ORDER BY proxy_fidelity DESC
-- picks whichever proxy the athlete actually has access to.

( 'TRN-017', 'Moving Water',
  'TRN-009', 'Flat Water',
  'medium', 2, 4, 0.65,
  ARRAY[
    'Flat water aerobic and stroke volume (high transfer for paddle base)',
    'Dry-land bracing and hip-snap drills on a balance pad or wobble board',
    'Video study of moving-water technique (ferry angles, eddy reads, current vectors)',
    '2–4 supervised moving-water sessions before race for current reading and eddy turn timing'
  ],
  ARRAY['balance_dynamic'],
  'Flat water builds the paddle aerobic base and stroke mechanics — high transfer for fitness. '
    'Current reading, ferry angles, and eddy use require real moving water. '
    'For packraft and river-touring contexts, plan 2–4 sessions on any river-current water '
    'in the final 4 weeks before race; dry-land bracing drills are a useful adjunct.',
  'Proxy fidelity 0.65 — flat-water paddle aerobic transfers directly; current-handling skill '
    'requires real moving-water practice. Severity classified ''medium'' per the post-Phase-2.3 '
    'fidelity-banded enum (0.50–0.69 = medium).',
  '0C-v2.0-r2', NOW() ),

( 'TRN-017', 'Moving Water',
  'TRN-011', 'Whitewater',
  'low', 1, 2, 0.85,
  ARRAY[
    'Whitewater paddling sessions (over-covers Class-II-and-below current handling)',
    'Periodic flat-water sessions for sustained aerobic volume if whitewater sessions are short'
  ],
  ARRAY[]::TEXT[],
  'Whitewater terrain access fully covers moving-water skill demand and provides more '
    'than sufficient current-reading practice. The only stimulus partially uncovered is '
    'sustained aerobic paddling volume — whitewater sessions tend to be shorter than '
    'flat or moving-water training sessions; supplement with longer flat-water work if '
    'race demands extended duration.',
  'Proxy fidelity 0.85 — whitewater over-covers the current-handling stimulus; small '
    'shortfall on sustained aerobic volume only. Severity classified ''low'' per the '
    'post-Phase-2.3 fidelity-banded enum (≥0.70 = low).',
  '0C-v2.0-r2', NOW() ),

-- ── Water: Whitewater gap ──────────────────────────────────────────────────

( 'TRN-011', 'Whitewater',
  'TRN-009', 'Flat Water',
  'partial', 8, 12, 0.30,
  ARRAY[
    'Flat water fitness maintenance (paddle volume and aerobic base)',
    'Pool rolling practice (wet exit + roll in controlled environment)',
    'Dry-land edging and hip-snap drills',
    'Video study of whitewater technique'
  ],
  ARRAY['technical_handwork', 'balance_dynamic'],
  'Flat water maintains paddling fitness but provides no whitewater skill transfer. '
    'Whitewater technique (eddy catches, reading water, bracing, rolling in current) '
    'cannot be acquired from flat-water training alone. Pool rolling is a useful '
    'foundation but does not substitute for real whitewater. Capability gating for '
    'this skill is now surfaced via the `whitewater_handling` skill toggle '
    '(Bucket C (l) 2026-05-24); the v1 prescription_note keyword-match flag '
    'has been retired.',
  'Whitewater skill acquisition: Crespo & Balagué (2023) on technical sport skill transfer — '
    'moving water reading is non-transferable from flat water. '
    'Pool rolling fidelity is high for technique only (not current management). '
    'Proxy fidelity 0.30.',
  '0C-v2.0-r2', NOW() ),

-- ── Snow / Winter Alpine gap ───────────────────────────────────────────────

( 'TRN-012', 'Snow / Winter Alpine',
  'TRN-016', 'Indoor / Gym',
  'partial', 6, 8, 0.30,
  ARRAY[
    'Stair climber with poles (simulates uphill skinning mechanics and aerobic load)',
    'Weighted vest hiking on any available terrain',
    'Single-leg squat and leg press for descent quad endurance',
    'Hip and ankle mobility work (ski-boot substitute)'
  ],
  ARRAY['technical_descent', 'balance_dynamic', 'cold_exposure'],
  'Stair climber with poles is the best uphill proxy — builds aerobic base and approximate skinning mechanics. '
    'Descent skill on snow cannot be trained off-snow. '
    'Maximize any available snow window regardless of duration. '
    'Alpine descent is flagged separately as an unbridgeable gap — see note. '
    'Single-leg strength work partially compensates for descent quad demand.',
  'Uphill skinning proxy: stair climber with poles replicates ~70% of skinning metabolic load '
    '(Fabre et al. 2012, Eur J Appl Physiol). Descent skill: D-020 training gap explicitly documented '
    'in discipline_training_gaps — no off-snow substitute validated. '
    'Proxy fidelity 0.30 reflects uphill-only coverage.',
  '0C-v2.0-r2', NOW() ),

-- ── Climbing: Rock Wall (Outdoor) gaps ────────────────────────────────────

( 'TRN-013', 'Rock Wall (Outdoor)',
  'TRN-014', 'Climbing Gym',
  'partial', 4, 6, 0.75,
  ARRAY[
    'Climbing gym — primary (bouldering and roped)',
    'Hangboard for finger strength and grip endurance',
    'Campus board for contact strength (intermediate+ only)'
  ],
  ARRAY['balance_dynamic'],
  'Gym climbing transfers movement patterns, route-reading, and strength well. '
    'Schedule 4–6 outdoor sessions before the race to adapt to natural rock texture, '
    'exposure, and protection reading. Fear-of-heights response on real cliffs '
    'must be addressed with real outdoor exposure — gym does not substitute.',
  'Gym-to-outdoor transfer: Draper et al. (2011), Eur J Sport Sci — strength and technique '
    'transfer is high; rock-specific friction and feature reading require outdoor sessions. '
    'Proxy fidelity 0.75.',
  '0C-v2.0-r2', NOW() ),

( 'TRN-013', 'Rock Wall (Outdoor)',
  NULL, NULL,
  'unbridgeable', NULL, NULL, 0.00,
  ARRAY[
    'Pull-up and row progressions (general pulling strength only)',
    'Dead hangs for grip endurance (partial transfer)',
    'Core and shoulder stability work'
  ],
  ARRAY['technical_handwork', 'grip_strength', 'balance_dynamic'],
  'No climbing access — general pulling strength is the only available prep. '
    'This does not constitute climbing preparation. '
    'If race includes a climbing leg, strongly recommend sourcing at minimum a climbing gym '
    'membership before the race. Reference discipline_training_gaps for D-010.',
  'No discipline-level substitute for climbing skill exists without actual climbing surface. '
    'See discipline_training_gaps D-010 (Rock Climbing outdoor). '
    'Proxy fidelity 0.00 — general strength is not climbing preparation.',
  '0C-v2.0-r2', NOW() )

ON CONFLICT (target_terrain_id, proxy_terrain_id, etl_version) DO NOTHING;

-- ── 3. Verify ──────────────────────────────────────────────────────────────

DO $$
DECLARE
  row_count INT;
  null_methods INT;
BEGIN
  SELECT COUNT(*) INTO row_count
  FROM layer0.terrain_gap_rules
  WHERE etl_version = '0C-v2.0-r2' AND superseded_at IS NULL;

  SELECT COUNT(*) INTO null_methods
  FROM layer0.terrain_gap_rules
  WHERE superseded_at IS NULL
    AND (proxy_methods IS NULL OR array_length(proxy_methods, 1) = 0);

  IF row_count <> 16 THEN
    RAISE EXCEPTION 'populate_terrain_gap_rules: expected 16 rows, found %', row_count;
  END IF;

  IF null_methods > 0 THEN
    RAISE EXCEPTION 'populate_terrain_gap_rules: % rows have empty proxy_methods', null_methods;
  END IF;

  RAISE NOTICE 'populate_terrain_gap_rules: OK — 16 gap rules active, all proxy_methods populated';
END $$;

COMMIT;
