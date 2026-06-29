-- 0026_gear_toggle_terrain_compatibility.sql
--
-- #884 slice 4b — seed `layer0.craft_terrain_compatibility` rows for the
-- discipline-unlocking GEAR TOGGLES so the generalized gear/terrain cascade
-- (session_feasibility.resolve_craft_terrain_feasibility, widened from
-- {bike,paddle} to all gear kinds this slice) can resolve ski/snow/climbing/
-- alpine disciplines on real terrain (design v3 §6 / §15.4).
--
-- Until now `craft_terrain_compatibility` carried ONLY bike/paddle crafts, so a
-- gear-toggle discipline pulled into the cascade would find no rideable terrain
-- and drop straight to INDOOR/STRENGTH even with the real surface in-cluster.
-- These rows make the EXACT/PROXY tiers fire on owned gear (design Decision 3,
-- reuse existing paved/snow/rock terrain vocab — NO new terrain entries):
--
--   classic_xc_ski -> TRN-012 (Snow / Winter Alpine)   D-028 EXACT, rank 0
--   skate_xc_ski   -> TRN-012 (Snow / Winter Alpine)   D-028 EXACT, rank 1
--   rollerskis     -> TRN-001 (Road / Paved)           D-028 dryland carve-out,
--       rank 2: required terrain is snow (TRN-012); rollerskis ride pavement, so
--       they resolve via the existing "own the gear, ride an ALTERNATE terrain
--       it's compatible with" PROXY tier (tier 2) — ranked below real snow.
--   snowshoes      -> TRN-012 (Snow / Winter Alpine)   D-017 EXACT
--   climbing_gear  -> TRN-013 (Rock Wall, Outdoor),
--                     TRN-014 (Climbing Gym)           D-012/D-013/D-014 EXACT
--   mountaineering -> TRN-005 (Mountain / Alpine),
--                     TRN-007 (Technical Rock / Scree),
--                     TRN-012 (Snow / Winter Alpine)   D-018 EXACT
--   skimo_at       -> TRN-012 (Snow / Winter Alpine)   D-021/D-022 EXACT
--
-- Each gear_id is an active `gear_discipline_aliases` row (0024); each terrain_id
-- is an active `terrain_types` row — the verify block guards both. The terrain
-- set per gear mirrors the disciplines it unlocks (required terrains from
-- session_feasibility._DISCIPLINE_REQUIRED_TERRAINS), so EXACT fires when that
-- surface is present; the rollerski row is the one deliberate exception.
--
-- CACHE: unlike 0024/0025 (unread by serving), `craft_terrain_compatibility` IS
-- a LIVE cascade read (_q_craft_terrain_compatibility) and is already in the
-- Layer-0 family map (`"craft_terrain_compatibility": "0A"`), so these new rows
-- shift its per-table digest in the plan cache key → plans re-run picking up the
-- ski-gear terrain feasibility. That invalidation is correct and intended.
--
-- Idempotent: delete-this-version-then-insert (the table already exists in the
-- baseline; CREATE IF NOT EXISTS is defensive for a fresh-baseline apply).

\set ON_ERROR_STOP on

BEGIN;

CREATE TABLE IF NOT EXISTS layer0.craft_terrain_compatibility (
    id            integer PRIMARY KEY,
    craft_name    text    NOT NULL,
    terrain_id    text    NOT NULL,
    etl_version   text    NOT NULL,
    etl_run_at    timestamp with time zone NOT NULL,
    superseded_at timestamp with time zone
);

-- Re-runnable: drop this version's rows before re-seeding.
DELETE FROM layer0.craft_terrain_compatibility WHERE etl_version = '0A-v1.9.2';

INSERT INTO layer0.craft_terrain_compatibility
    (id, craft_name, terrain_id, etl_version, etl_run_at)
VALUES
    (29, 'classic_xc_ski', 'TRN-012', '0A-v1.9.2', now()),
    (30, 'skate_xc_ski',   'TRN-012', '0A-v1.9.2', now()),
    (31, 'rollerskis',     'TRN-001', '0A-v1.9.2', now()),
    (32, 'snowshoes',      'TRN-012', '0A-v1.9.2', now()),
    (33, 'climbing_gear',  'TRN-013', '0A-v1.9.2', now()),
    (34, 'climbing_gear',  'TRN-014', '0A-v1.9.2', now()),
    (35, 'mountaineering', 'TRN-005', '0A-v1.9.2', now()),
    (36, 'mountaineering', 'TRN-007', '0A-v1.9.2', now()),
    (37, 'mountaineering', 'TRN-012', '0A-v1.9.2', now()),
    (38, 'skimo_at',       'TRN-012', '0A-v1.9.2', now());

-- Verify (atomic): 10 new active rows; the rollerski dryland carve-out invariant
-- (TRN-001, NOT snow); no dangling terrain_id or gear_id refs.
DO $$
DECLARE
    n_rows     int;
    n_roller   int;
    n_bad_terr int;
    n_bad_gear int;
BEGIN
    SELECT count(*) INTO n_rows
      FROM layer0.craft_terrain_compatibility
     WHERE superseded_at IS NULL AND etl_version = '0A-v1.9.2';
    IF n_rows <> 10 THEN
        RAISE EXCEPTION '0026 verify: expected 10 new gear-toggle rows, found %', n_rows;
    END IF;

    SELECT count(*) INTO n_roller
      FROM layer0.craft_terrain_compatibility
     WHERE superseded_at IS NULL AND craft_name = 'rollerskis'
       AND terrain_id = 'TRN-001';
    IF n_roller <> 1 THEN
        RAISE EXCEPTION '0026 verify: rollerskis carve-out must map to TRN-001 (dryland), found % row(s)', n_roller;
    END IF;

    SELECT count(*) INTO n_bad_terr
      FROM layer0.craft_terrain_compatibility r
     WHERE r.superseded_at IS NULL AND r.etl_version = '0A-v1.9.2'
       AND NOT EXISTS (
         SELECT 1 FROM layer0.terrain_types t
          WHERE t.superseded_at IS NULL AND t.terrain_id = r.terrain_id
       );
    IF n_bad_terr > 0 THEN
        RAISE EXCEPTION '0026 verify: % row(s) name a non-active terrain_id', n_bad_terr;
    END IF;

    SELECT count(*) INTO n_bad_gear
      FROM layer0.craft_terrain_compatibility r
     WHERE r.superseded_at IS NULL AND r.etl_version = '0A-v1.9.2'
       AND NOT EXISTS (
         SELECT 1 FROM layer0.gear_discipline_aliases g
          WHERE g.superseded_at IS NULL AND g.gear_id = r.craft_name
       );
    IF n_bad_gear > 0 THEN
        RAISE EXCEPTION '0026 verify: % row(s) name a gear_id absent from gear_discipline_aliases', n_bad_gear;
    END IF;

    RAISE NOTICE '0026: OK — 10 gear-toggle craft_terrain rows seeded (ski/snow/climbing/alpine; rollerskis=dryland)';
END $$;

COMMIT;

-- End of 0026_gear_toggle_terrain_compatibility.sql
