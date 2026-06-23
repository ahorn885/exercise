-- 0006_populate_disciplines_primary_movement.sql
--
-- Backfill `layer0.disciplines.primary_movement` for the active discipline
-- canon. The column itself already exists (it is in the v1.7.0 genesis
-- baseline DDL); this migration restores the *data*, which is NULL on every
-- active row in the baseline.
--
-- Why it is empty
-- ---------------
-- `primary_movement` was first added + populated by the pre-genesis one-shot
-- `etl/sources/migrate_disciplines_add_primary_movement_v1.sql` (PR #156). But
-- a later full ETL re-extraction of the disciplines dimension (the `0A-v1.6.x`
-- family, 2026-06) replaced the active rows *without* carrying it — unlike
-- `endurance_profile`, which the canon normalizer
-- (`discipline_canon.normalize_dimension_rows`) stamps on every extracted row
-- and which therefore survived. The clobber left every active discipline NULL,
-- so this is no longer "add a column" but "re-populate a serving column the
-- ETL drops". The standalone PR #156 migration was also stale (it targeted the
-- pre-drift `D-001..D-029` keyspace, missing D-030/D-031/D-032 and several
-- renamed/removed ids) and is retired in favour of this one.
--
-- Consumer (why it matters)
-- -------------------------
-- Layer 2E nutrition reads `primary_movement` (plumbed via Layer 2A onto
-- `Layer2ADiscipline.primary_movement`) for the §5.4.3 sport-profile CHO
-- modifier and the §5.3.3 protein band (`climbing` is the strength-biased
-- movement). With it NULL, `_movement_sport_profile` falls back to the generic
-- `multi_sport` profile for *every* discipline and the climbing protein bump
-- never fires — i.e. already-shipped plans get movement-blind fuelling.
--
-- Source of truth
-- ---------------
-- The 24-discipline canon in `etl/layer0/discipline_canon.CANONICAL_NAMES`.
-- Values are drawn from Layer 0 `ENUM_MOVEMENTS` (running / cycling / swimming
-- / paddling / skiing / climbing / hiking / navigation / other_skill) — the
-- movement axis the terrain axis (`endurance_profile` / `discipline_category`)
-- cannot express. The 18 currently-active disciplines are the subset of the
-- canon present in the dimension; the other 6 mapped ids are harmless no-ops.
--
-- Edit shape — SERVING-RELEVANT (README §"Two edit shapes" #2)
-- -----------------------------------------------------------
-- `primary_movement` is served (Layer 2E), so this is NOT a cache-neutral edit:
-- the affected rows are superseded and re-inserted at a bumped `disciplines`
-- version (`0A-v1.6.7` -> `0A-v1.6.8`) so the per-table `etl_version` digest
-- advances and plan-gen caches that resolved it as NULL/`multi_sport`
-- invalidate. `disciplines` is already in `_LAYER0_TABLE_FAMILY` (0A), so no
-- family-map change is needed.
--
-- Idempotent: only active rows that still LACK a movement are touched, so a
-- re-run after the baseline is next re-dumped (active rows already populated)
-- is a clean no-op — and no `(discipline_id, etl_version)` UNIQUE collision,
-- because nothing is re-inserted.
--
-- Atomic: the verification DO block RAISEs (rolling back the whole txn) if any
-- mapped active row is left NULL or carries a non-enum value.

\set ON_ERROR_STOP on

BEGIN;

-- The canonical id -> movement map: the single source of truth for this
-- migration, dropped automatically at COMMIT. Keyed by canonical (post-merge)
-- discipline id; mirrors discipline_canon.CANONICAL_NAMES (24 disciplines).
CREATE TEMP TABLE _pm_map (discipline_id text PRIMARY KEY, primary_movement text)
  ON COMMIT DROP;
INSERT INTO _pm_map (discipline_id, primary_movement) VALUES
  ('D-001', 'running'),    -- Trail Running
  ('D-002', 'running'),    -- Road Running
  ('D-003', 'hiking'),     -- Trekking (absorbs former Orienteering; locomotion is on foot)
  ('D-004', 'swimming'),   -- Swimming
  ('D-006', 'cycling'),    -- Road Cycling
  ('D-007', 'cycling'),    -- Time-Trial Cycling
  ('D-008', 'cycling'),    -- Mountain Biking
  ('D-009', 'paddling'),   -- Packrafting
  ('D-010', 'paddling'),   -- Kayaking
  ('D-011', 'paddling'),   -- Canoeing
  ('D-012', 'climbing'),   -- Rock Climbing
  ('D-013', 'climbing'),   -- Abseiling
  ('D-014', 'climbing'),   -- Via Ferrata
  ('D-017', 'hiking'),     -- Snowshoeing
  ('D-018', 'climbing'),   -- Mountaineering
  ('D-019', 'paddling'),   -- Paddle Rafting
  ('D-021', 'skiing'),     -- Uphill Skinning
  ('D-022', 'skiing'),     -- Alpine Descent
  ('D-024', 'running'),    -- Mountain Running
  ('D-027', 'running'),    -- Obstacle Course Racing
  ('D-028', 'skiing'),     -- Cross-Country Skiing
  ('D-030', 'cycling'),    -- Gravel Cycling
  ('D-031', 'cycling'),    -- Cross Country Cycling
  ('D-032', 'paddling');   -- Stand-up Paddleboard

-- 1. Re-insert each movement-less active discipline at the bumped version with
--    its movement applied. Every other column is copied verbatim from the live
--    active row; only primary_movement / etl_version / etl_run_at change. `id`
--    is omitted (serial default) and superseded_at defaults NULL (new active).
INSERT INTO layer0.disciplines (
  discipline_id, discipline_name, min_base_phase_text, min_base_phase_weeks_low,
  min_base_phase_weeks_high, periodization_text, ramp_text, age_adjusted_ramp_text,
  age_ramp_40_44_pct, age_ramp_45_54_pct, age_ramp_55_plus_pct, taper_norms_text,
  common_injury_patterns, injury_preceding_behaviors, recovery_priority_text,
  recovery_modalities, evidence_quality_text, stimulus_components,
  body_parts_at_risk, endurance_profile,
  primary_movement, etl_version, etl_run_at
)
SELECT
  d.discipline_id, d.discipline_name, d.min_base_phase_text, d.min_base_phase_weeks_low,
  d.min_base_phase_weeks_high, d.periodization_text, d.ramp_text, d.age_adjusted_ramp_text,
  d.age_ramp_40_44_pct, d.age_ramp_45_54_pct, d.age_ramp_55_plus_pct, d.taper_norms_text,
  d.common_injury_patterns, d.injury_preceding_behaviors, d.recovery_priority_text,
  d.recovery_modalities, d.evidence_quality_text, d.stimulus_components,
  d.body_parts_at_risk, d.endurance_profile,
  m.primary_movement, '0A-v1.6.8', now()
FROM layer0.disciplines d
JOIN _pm_map m USING (discipline_id)
WHERE d.superseded_at IS NULL
  AND d.primary_movement IS NULL;

-- 2. Supersede the old movement-less rows (kept as history). The new rows from
--    step 1 carry a non-NULL movement, so this predicate matches only the old
--    ones; rows outside the map are never touched.
UPDATE layer0.disciplines d
   SET superseded_at = now()
  FROM _pm_map m
 WHERE d.discipline_id = m.discipline_id
   AND d.superseded_at IS NULL
   AND d.primary_movement IS NULL;

-- 3. Verify: every mapped active discipline now carries an ENUM_MOVEMENTS value.
DO $$
DECLARE
  v_enum     TEXT[] := ARRAY[
    'running','cycling','swimming','paddling','skiing',
    'climbing','hiking','navigation','other_skill'
  ];
  v_null     INT;
  v_bad      TEXT;
BEGIN
  SELECT count(*) INTO v_null
    FROM layer0.disciplines
   WHERE superseded_at IS NULL
     AND discipline_id IN (SELECT discipline_id FROM _pm_map)
     AND primary_movement IS NULL;
  IF v_null > 0 THEN
    RAISE EXCEPTION '0006: % mapped active discipline(s) still NULL primary_movement', v_null;
  END IF;

  SELECT primary_movement INTO v_bad
    FROM layer0.disciplines
   WHERE superseded_at IS NULL
     AND discipline_id IN (SELECT discipline_id FROM _pm_map)
     AND NOT (primary_movement = ANY (v_enum))
   LIMIT 1;
  IF v_bad IS NOT NULL THEN
    RAISE EXCEPTION '0006: non-enum primary_movement value %', v_bad;
  END IF;

  RAISE NOTICE '0006: OK — mapped active disciplines populated within ENUM_MOVEMENTS';
END $$;

COMMIT;

-- End of 0006_populate_disciplines_primary_movement.sql
