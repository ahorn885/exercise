-- 0004_craft_terrain_compat_and_drop_cycling_trainer.sql
--
-- Issue #586 (WS-I) — craft/equipment taxonomy + the data half of the unified
-- feasibility cascade. Design:
--   aidstation-sources/designs/CraftEquipment_Taxonomy_And_FeasibilityCascade_Design_v1.md
-- This migration is the Layer-0 data slice (PR1). The cascade rewrite that
-- READS craft_terrain_compatibility (and adds it to the per-table cache digest
-- _LAYER0_TABLE_FAMILY) lands in the follow-on PR2 — so this file only
-- provisions + seeds the table and retires the cycling_trainer craft alias.
--
-- TWO independent changes, one transaction:
--
--   (1) NEW TABLE layer0.craft_terrain_compatibility — the explicit craft->terrain
--       map (design §4). Tiers 2-4 of the cascade need to know which terrains a
--       craft can be used on; today only craft->discipline (craft_discipline_aliases)
--       and discipline->terrain exist, so craft->terrain was only derivable. Per
--       Andy (2026-06-13) it is declared explicitly, not derived (a road bike and
--       a gravel bike alias the same road/XC disciplines but differ on singletrack).
--       Spec-sourced like terrain_gap_rules (0003): created by this self-contained
--       migration, NOT added to etl/layer0/schema.sql.
--
--   (2) RETIRE the cycling_trainer craft alias rows from craft_discipline_aliases.
--       A trainer/erg is fixed gear, not a mobile vessel -> it is EQUIPMENT, not a
--       craft (design §2). cycling_trainer also leaves the craft capture enum
--       (athlete.py BIKE_TYPES, same PR), so no athlete can own it as a craft going
--       forward, and the one existing stored instance (Andy's set B) moves to gym
--       equipment via the owed-hands app-data fix bundled in the PR. With no
--       serving path left to reference these rows, this is a CACHE-NEUTRAL
--       structural removal (README §"Two edit shapes", same shape as 0001): soft
--       supersede, no etl_version bump, caches stay warm.
--
-- Idempotent: CREATE ... IF NOT EXISTS; seed is INSERT ... ON CONFLICT DO NOTHING;
-- the supersede matches no active rows on a second pass.

BEGIN;

-- ── 1. craft_terrain_compatibility: table ──────────────────────────────────
-- Shape mirrors its sibling layer0.craft_discipline_aliases (craft_name keyed,
-- row-invalidation versioned). 0A family (sports framework) like the alias map.

CREATE TABLE IF NOT EXISTS layer0.craft_terrain_compatibility (
  id             SERIAL PRIMARY KEY,
  craft_name     TEXT NOT NULL,
  terrain_id     TEXT NOT NULL,
  etl_version    TEXT NOT NULL,
  etl_run_at     TIMESTAMPTZ NOT NULL,
  superseded_at  TIMESTAMPTZ,
  UNIQUE (craft_name, terrain_id, etl_version)
);

-- ── 2. craft_terrain_compatibility: seed grid (design §4, Andy-ratified) ────
-- Indoor surfaces (TRN-016 Gym, TRN-008 Pool, TRN-014 Climbing Gym) are excluded
-- by construction — those are the INDOOR cascade tier, not craft terrain.
--   road_bike     TRN-001 Road, TRN-004 Hill/Rolling
--   gravel_bike   + TRN-002 Groomed Trail, TRN-020 Gravel  (rides groomed trail,
--                   NOT technical TRN-003; road bike excludes Gravel)
--   mountain_bike + TRN-003 Technical Trail, TRN-015 Pump/Skills  (excludes
--                   Mountain/Alpine TRN-005 + Tech Rock/Scree TRN-007 = hike-a-bike)
--   kayak         TRN-009 Flat, TRN-010 Ocean/Tidal, TRN-011 Whitewater, TRN-017 Moving
--   canoe         TRN-009 Flat, TRN-017 Moving
--   packraft      TRN-009 Flat, TRN-011 Whitewater, TRN-017 Moving
-- (kayak is a single generic slug carrying both ocean + whitewater; a sea/ww/rec
-- subtype split is a deferred vocab decision, design §4 known limitation.)

INSERT INTO layer0.craft_terrain_compatibility
  (craft_name, terrain_id, etl_version, etl_run_at)
VALUES
  ('road_bike',     'TRN-001', '0A-v1.6.7', now()),
  ('road_bike',     'TRN-004', '0A-v1.6.7', now()),
  ('gravel_bike',   'TRN-001', '0A-v1.6.7', now()),
  ('gravel_bike',   'TRN-002', '0A-v1.6.7', now()),
  ('gravel_bike',   'TRN-004', '0A-v1.6.7', now()),
  ('gravel_bike',   'TRN-020', '0A-v1.6.7', now()),
  ('mountain_bike', 'TRN-001', '0A-v1.6.7', now()),
  ('mountain_bike', 'TRN-002', '0A-v1.6.7', now()),
  ('mountain_bike', 'TRN-003', '0A-v1.6.7', now()),
  ('mountain_bike', 'TRN-004', '0A-v1.6.7', now()),
  ('mountain_bike', 'TRN-015', '0A-v1.6.7', now()),
  ('mountain_bike', 'TRN-020', '0A-v1.6.7', now()),
  ('kayak',         'TRN-009', '0A-v1.6.7', now()),
  ('kayak',         'TRN-010', '0A-v1.6.7', now()),
  ('kayak',         'TRN-011', '0A-v1.6.7', now()),
  ('kayak',         'TRN-017', '0A-v1.6.7', now()),
  ('canoe',         'TRN-009', '0A-v1.6.7', now()),
  ('canoe',         'TRN-017', '0A-v1.6.7', now()),
  ('packraft',      'TRN-009', '0A-v1.6.7', now()),
  ('packraft',      'TRN-011', '0A-v1.6.7', now()),
  ('packraft',      'TRN-017', '0A-v1.6.7', now())
ON CONFLICT (craft_name, terrain_id, etl_version) DO NOTHING;

-- ── 3. Retire the cycling_trainer craft alias (cache-neutral removal) ───────
-- Genesis-snapshot rows: cycling_trainer -> {D-006, D-007, D-008, D-030, D-031}
-- at 0A-v1.6.7. cycling_trainer is no longer a craft (it is equipment), so these
-- soft-supersede out of the active set; they remain as history.

UPDATE layer0.craft_discipline_aliases
   SET superseded_at = now()
 WHERE superseded_at IS NULL
   AND craft_name = 'cycling_trainer';

COMMIT;
