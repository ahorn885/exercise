-- 0025_cardio_drill_gear_requirements.sql
--
-- #884 slice 3b — gear-gated cardio drills (design v3 §6a / Decision 11).
--
-- Builds the Layer-0 relation `cardio_drill_gear_requirements (exercise_id,
-- gear_id)`: a cardio DRILL (cardio_drills[] pool member) requires the listed
-- owned gear. The runtime gate (`compute_cardio_drill_pool_ids` /
-- `_format_cardio_drill_pool`, layer4/per_phase.py) drops a drill from the pool
-- when the athlete doesn't OWN the gear (reads `athlete_gear`, group_kind
-- 'swim') — NOT a discipline-feasibility gate (D-004 Swimming stays feasible on
-- water), NOT an `equipment_required` gate. The runtime hard-codes the same
-- mapping by stable EX-id (`_CARDIO_DRILL_GEAR_REQUIREMENTS`), exactly like the
-- constituent-sport gate hard-codes its drill set; this table is the canonical
-- authoring source, kept in lockstep by
-- test_layer4_cardio_drill_pool.test_gear_requirement_map_matches_seed.
--
-- Seed (the only two gear-specific swim drills in the active catalog — verified
-- against layer0.exercises, no padding):
--   EX126 Freestyle Pull (With Buoy)     -> pull_buoy
--   EX128 Kicking Drill (Flutter / Frog) -> kickboard
-- (paddles / fins are seeded into the gear keyspace — athlete_gear_repo
-- GEAR_REGISTRY, Andy 2026-06-23 — but gate no active drill yet, so no row here.)
--
-- DEFERRED to slice 4 (Andy 2026-06-23): moving pull_buoy/kickboard OUT of the
-- gym `equipment_items` catalog + stripping them from EX126/EX128
-- `equipment_required`. That is a SERVING-RELEVANT 0B edit (those exercises
-- reference the gear, so it changes 2C resolution → README "edit shape #2":
-- supersede + re-insert at a bumped 0B version → a global plan-gen cache
-- invalidation). The owned-gear gate works WITHOUT it (the drills are merely
-- double-gated and the owned-gear gate dominates), so the strip is a separable
-- model-cleanliness step folded into slice 4's Layer-0 work, not this PR.
--
-- This table is unread by any live serving query (the runtime uses the hard-coded
-- map), so — like slice 3a's gear_discipline_aliases — it needs no
-- _q_current_etl_version_set / _LAYER0_TABLE_FAMILY coordination yet. When a
-- future redump folds it into the baseline, map it (or add to
-- _FAMILY_MAP_EXCEPTIONS as a hard-coded-at-runtime / no-live-reader table).
--
-- Idempotent: CREATE IF NOT EXISTS + delete-this-version-then-insert.

\set ON_ERROR_STOP on

BEGIN;

CREATE TABLE IF NOT EXISTS layer0.cardio_drill_gear_requirements (
    id            integer PRIMARY KEY,
    exercise_id   text    NOT NULL,
    gear_id       text    NOT NULL,
    etl_version   text    NOT NULL,
    etl_run_at    timestamp with time zone NOT NULL,
    superseded_at timestamp with time zone
);

-- Re-runnable: drop this version's rows before re-seeding.
DELETE FROM layer0.cardio_drill_gear_requirements WHERE etl_version = '0B-v1.9.1';

INSERT INTO layer0.cardio_drill_gear_requirements
    (id, exercise_id, gear_id, etl_version, etl_run_at)
VALUES
    (1, 'EX126', 'pull_buoy', '0B-v1.9.1', now()),
    (2, 'EX128', 'kickboard', '0B-v1.9.1', now());

-- Verify (atomic): 2 active rows, and each maps an EX-id that really is an active
-- swim drill in the catalog (catch a typo'd / superseded exercise_id).
DO $$
DECLARE
    n_rows    int;
    n_dangling int;
BEGIN
    SELECT count(*) INTO n_rows
      FROM layer0.cardio_drill_gear_requirements WHERE superseded_at IS NULL;
    IF n_rows <> 2 THEN
        RAISE EXCEPTION '0025 verify: expected 2 active rows, found %', n_rows;
    END IF;

    SELECT count(*) INTO n_dangling
      FROM layer0.cardio_drill_gear_requirements r
     WHERE r.superseded_at IS NULL
       AND NOT EXISTS (
         SELECT 1 FROM layer0.exercises e
          WHERE e.superseded_at IS NULL AND e.exercise_id = r.exercise_id
       );
    IF n_dangling > 0 THEN
        RAISE EXCEPTION '0025 verify: % requirement row(s) name a non-active exercise_id', n_dangling;
    END IF;

    RAISE NOTICE '0025: OK — cardio_drill_gear_requirements seeded (EX126->pull_buoy, EX128->kickboard)';
END $$;

COMMIT;

-- End of 0025_cardio_drill_gear_requirements.sql
