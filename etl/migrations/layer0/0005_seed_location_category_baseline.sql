-- 0005_seed_location_category_baseline.sql
--
-- Issue #581 (WS-H) — Event Windows Slice 3 (F8): category equipment baselines.
-- Design: aidstation-sources/designs/Event_Windows_Design_v1.md §F8.
--
-- THE PROBLEM. A not-yet-logged locale — an away destination the athlete just
-- created inline (Slice 2b), or a cold home gym — links no gym_profile and has
-- no logged terrain, so cluster_equipment_by_locale / cluster_terrain_by_locale
-- return empty for it and the feasibility cascade degrades every discipline to
-- near-strength. "I'm at a hotel in Belfast, I don't know what its gym has"
-- (Andy). Until the athlete logs actuals on arrival, the plan should ASSUME a
-- baseline for that category and build around it; logging real equipment then
-- triggers a T1/T2 refresh of the affected window (the arrival-regen loop, F6).
--
-- THE TABLE. layer0.location_category_equipment_baseline maps a LOGICAL category
-- (commercial / hotel / climbing / pool) to an assumed equipment set + an
-- assumed terrain set (TRN-xxx ids). One authored, editable row per category
-- (Andy: "single baseline that we edit", 2026-06-14) — NOT a crowd aggregate.
-- The 5 gym + 2 pool MANUAL_CATEGORIES slugs (routes/locales.py) collapse to
-- these 4 via locations._CATEGORY_BASELINE_KEY (commercial_chain_gym +
-- independent_gym -> commercial; climbing_gym_chain + _indie -> climbing;
-- pool_indoor + pool_outdoor -> pool).
--
-- REPLACE semantics (Andy): the baseline applies ONLY when the locale has zero
-- logged equipment (terrain: zero logged terrain). Any logged value fully wins
-- — the resolution substitution lives in locations.py, gated on the empty set.
--
-- CONTENTS ratified by Andy 2026-06-14 (Trigger #2). Equipment names are exact
-- layer0.equipment_items canonical tokens; terrain ids are layer0.terrain_types
-- (TRN-001 Road/Paved, TRN-014 Climbing Gym, TRN-016 Indoor/Gym, TRN-008 Pool).
--
-- CACHE. Registered in orchestrator._LAYER0_TABLE_FAMILY (0C) so editing a
-- baseline (supersede + new etl_version) shifts the 0C etl_version_set digest →
-- plan_create_key / plan_refresh_key change → affected plans re-synthesize.
-- BECAUSE the digest UNION queries this table on every plan-gen, THIS MIGRATION
-- MUST BE APPLIED ON NEON BEFORE THE SLICE-3 CODE DEPLOYS (same apply-first
-- ordering as 0004; Neon egress is blocked from the web container).
--
-- Idempotent: CREATE ... IF NOT EXISTS; seed is INSERT ... ON CONFLICT DO NOTHING.

BEGIN;

-- ── 1. table ────────────────────────────────────────────────────────────────
-- Row-invalidation versioned like its 0C siblings (equipment_items, terrain_*).
-- An edit supersedes the active row (superseded_at = NOW()) and inserts a new
-- one with a bumped etl_version; serving reads WHERE superseded_at IS NULL.

CREATE TABLE IF NOT EXISTS layer0.location_category_equipment_baseline (
  id              SERIAL PRIMARY KEY,
  category        TEXT        NOT NULL,
  equipment_tags  TEXT[]      NOT NULL DEFAULT '{}',
  terrain_ids     TEXT[]      NOT NULL DEFAULT '{}',
  etl_version     TEXT        NOT NULL,
  etl_run_at      TIMESTAMPTZ NOT NULL,
  superseded_at   TIMESTAMPTZ,
  UNIQUE (category, etl_version)
);

-- ── 2. seed (Andy-ratified, 2026-06-14) ─────────────────────────────────────

INSERT INTO layer0.location_category_equipment_baseline
  (category, equipment_tags, terrain_ids, etl_version, etl_run_at)
VALUES
  ('commercial',
   ARRAY[
     'Dip bars','Foam roller','Pull-up bar','Resistance band',
     'TRX / suspension trainer','Yoga mat','Barbell','Bench','Dumbbell',
     'EZ curl bar','Kettlebell','Squat rack','Weight plates','Elliptical',
     'Rowing ergometer','Stationary bike','Treadmill','Cable machine',
     'Chest press machine','Lat pulldown machine','Leg press machine',
     'Seated row machine','Smith machine','BOSU ball','Battle ropes',
     'Medicine ball','Plyo box','Stability ball'
   ]::TEXT[],
   ARRAY['TRN-001','TRN-016']::TEXT[],
   '0C-v1.0', NOW()),

  ('hotel',
   ARRAY[
     'Dumbbell','Treadmill','Stationary bike','Elliptical',
     'Bench','Yoga mat','Stability ball'
   ]::TEXT[],
   ARRAY['TRN-001','TRN-016']::TEXT[],
   '0C-v1.0', NOW()),

  ('climbing',
   ARRAY['Treadwall','Hangboard','Pull-up bar','Campus board']::TEXT[],
   ARRAY['TRN-001','TRN-016','TRN-014']::TEXT[],
   '0C-v1.0', NOW()),

  ('pool',
   ARRAY[]::TEXT[],
   ARRAY['TRN-008']::TEXT[],
   '0C-v1.0', NOW())
ON CONFLICT (category, etl_version) DO NOTHING;

-- ── 3. verify ───────────────────────────────────────────────────────────────
-- 4 active rows; every terrain id resolves to a live terrain_types row; every
-- equipment tag resolves to a live equipment_items canonical_name. All hard
-- (RAISE EXCEPTION → the migration rolls back on any mismatch). Every seed token
-- was reconciled against the live layer0.equipment_items vocabulary on apply
-- (2026-06-14) and all are also present in the CI genesis snapshot, so the gate
-- passes with the hard check.

DO $$
DECLARE
  n_rows      INT;
  bad_equip   TEXT;
  bad_terrain TEXT;
BEGIN
  SELECT COUNT(*) INTO n_rows
    FROM layer0.location_category_equipment_baseline
   WHERE superseded_at IS NULL;
  IF n_rows <> 4 THEN
    RAISE EXCEPTION 'expected 4 active baseline rows, found %', n_rows;
  END IF;

  SELECT string_agg(DISTINCT tid, ', ') INTO bad_terrain
    FROM (
      SELECT unnest(terrain_ids) AS tid
        FROM layer0.location_category_equipment_baseline
       WHERE superseded_at IS NULL
    ) t
   WHERE NOT EXISTS (
     SELECT 1 FROM layer0.terrain_types tt
      WHERE tt.terrain_id = t.tid AND tt.superseded_at IS NULL
   );
  IF bad_terrain IS NOT NULL THEN
    RAISE EXCEPTION 'baseline terrain ids absent from terrain_types: %', bad_terrain;
  END IF;

  SELECT string_agg(DISTINCT tag, ', ') INTO bad_equip
    FROM (
      SELECT unnest(equipment_tags) AS tag
        FROM layer0.location_category_equipment_baseline
       WHERE superseded_at IS NULL
    ) t
   WHERE NOT EXISTS (
     SELECT 1 FROM layer0.equipment_items e
      WHERE e.canonical_name = t.tag AND e.superseded_at IS NULL
   );
  IF bad_equip IS NOT NULL THEN
    RAISE EXCEPTION 'baseline equipment tags absent from equipment_items: %', bad_equip;
  END IF;
END $$;

COMMIT;
