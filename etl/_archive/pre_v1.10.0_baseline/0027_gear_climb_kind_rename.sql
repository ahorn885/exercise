-- 0027_gear_climb_kind_rename.sql
--
-- #884 slice 4b (taxonomy normalization, Andy 2026-06-29) — rename the gear
-- `group_kind` value `climbing` -> `climb` in `gear_discipline_aliases`, aligning
-- the gear taxonomy with the modality vocab (`modality_groups.group_kind` uses
-- `climb`). This removes the only true naming collision between the two
-- taxonomies. The finer gear families `ski`/`snow`/`alpine` are intentionally
-- kept (the single modality `snow` splits into three gear families so snowshoes
-- never proxy for skis) — they have no modality-vocab equivalent, so only
-- `climbing` is renamed.
--
-- Why a new migration (not an edit to 0024): the apply loop runs each migration
-- EXACTLY ONCE via the `_applied_migrations` ledger (by filename), so 0024 will
-- not re-run on prod — its seed value can only be corrected by a later migration.
-- This UPDATE runs after 0024 (filename order), so the final state is `climb`.
--
-- The app code (GEAR_REGISTRY, session_feasibility._CRAFT_GROUP_KINDS,
-- orchestrator._CRAFT_ALIAS_GROUP_KINDS) ships the `climb` value in the same PR;
-- the matching public-schema rename of live `athlete_gear` rows
-- (`group_kind 'climbing' -> 'climb'`) auto-applies on deploy via init_db
-- `_PG_MIGRATIONS`. This 0A migration must land in the SAME `layer0-apply` run as
-- 0026 so the cascade reads the `climb` kind the code expects.
--
-- CACHE: 0026 already bumps the 0A family digest (craft_terrain_compatibility ->
-- 0A-v1.9.2), so plans re-run and read the corrected `climb` rows. This UPDATE
-- keeps the rows' etl_version (`0A-v1.9.1`) — no separate digest bump owed.
--
-- Idempotent: the UPDATE matches only `climbing` rows, so a re-run is a no-op.

\set ON_ERROR_STOP on

BEGIN;

UPDATE layer0.gear_discipline_aliases
   SET group_kind = 'climb'
 WHERE group_kind = 'climbing'
   AND superseded_at IS NULL;

-- Verify (atomic): no `climbing` rows remain, and the 3 climbing_gear aliases
-- (D-012/D-013/D-014) now carry `climb`.
DO $$
DECLARE
    n_old   int;
    n_climb int;
BEGIN
    SELECT count(*) INTO n_old
      FROM layer0.gear_discipline_aliases
     WHERE superseded_at IS NULL AND group_kind = 'climbing';
    IF n_old <> 0 THEN
        RAISE EXCEPTION '0027 verify: % stale `climbing` row(s) remain', n_old;
    END IF;

    SELECT count(*) INTO n_climb
      FROM layer0.gear_discipline_aliases
     WHERE superseded_at IS NULL AND gear_id = 'climbing_gear' AND group_kind = 'climb';
    IF n_climb <> 3 THEN
        RAISE EXCEPTION '0027 verify: expected 3 climbing_gear rows at kind `climb`, found %', n_climb;
    END IF;

    RAISE NOTICE '0027: OK — gear group_kind `climbing` -> `climb` (3 climbing_gear aliases)';
END $$;

COMMIT;

-- End of 0027_gear_climb_kind_rename.sql
