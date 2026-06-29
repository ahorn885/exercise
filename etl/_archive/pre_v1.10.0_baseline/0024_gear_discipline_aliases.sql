-- 0024_gear_discipline_aliases.sql
--
-- Renumbered 0023 → 0024 (PR #923 collided with the slice-2 #919 migration
-- 0023_retire_inert_sport_gear.sql, which had already claimed 0023). This file
-- was first applied to prod under the name 0023_gear_discipline_aliases.sql; the
-- ledger keys by filename, so the apply loop re-runs it once under 0024 — which
-- is harmless because it is idempotent (CREATE IF NOT EXISTS + delete-this-
-- version-then-insert re-seeds the same 22 rows). The stale 0023 ledger entry is
-- inert.
--
-- #884 slice 3a — build the unified gear→discipline alias relation with an
-- ORDINAL fidelity rank (design v3 §5.3 / Decision 8 + 10 + 12).
--
-- Generalizes `craft_discipline_aliases (craft_name, discipline_id, group_kind)`
-- into `gear_discipline_aliases (gear_id, discipline_id, group_kind,
-- fidelity_rank)`, the single table that maps BOTH crafts and owned gear toggles
-- to the disciplines they unlock. `fidelity_rank` is an INTEGER (0 = best, higher
-- = more degraded) — not a {primary,degraded} enum — so one discipline can carry
-- >2 substitute fidelities. D-028 Cross-Country Skiing is the case that forces
-- it: Classic XC (0) → Skate XC (1) → Rollerskis (2, dryland). The gym ski-erg
-- stays the gear-INDEPENDENT INDOOR fallback (session_feasibility), below all
-- owned gear, so "rollerski before ski-erg" falls out of the PROXY-over-INDOOR
-- tier order.
--
-- gear_id keyspace: design v3 §5.5 — craft slugs unchanged; gear toggles get
-- stable snake_case slugs; `rollerskis` is the one new gear entry (Decision 10:
-- owned dryland gear, promoted from the "machine" treatment in
-- Provider_Inbound_Matrix_v2 §12).
--
-- STAGING (v3 §5.3): this table is created + populated ALONGSIDE the live
-- craft_discipline_aliases. The orchestrator read paths still read the craft
-- table; they cut over in slice 4, when craft_discipline_aliases retires.
-- Nothing reads gear_discipline_aliases yet, so this migration changes no served
-- output (no cache version coordination needed — the new table is not yet in
-- _q_current_etl_version_set's per-table digest).
--
-- Idempotent: CREATE IF NOT EXISTS + delete-this-version-then-insert.

BEGIN;

CREATE TABLE IF NOT EXISTS layer0.gear_discipline_aliases (
    id            integer PRIMARY KEY,
    gear_id       text    NOT NULL,
    discipline_id text    NOT NULL,
    group_kind    text    NOT NULL,
    fidelity_rank integer NOT NULL DEFAULT 0,
    etl_version   text    NOT NULL,
    etl_run_at    timestamp with time zone NOT NULL,
    superseded_at timestamp with time zone
);

-- Re-runnable: drop this version's rows before re-seeding.
DELETE FROM layer0.gear_discipline_aliases WHERE etl_version = '0A-v1.9.1';

INSERT INTO layer0.gear_discipline_aliases
    (id, gear_id, discipline_id, group_kind, fidelity_rank, etl_version, etl_run_at)
VALUES
    -- Crafts (migrated 1:1 from craft_discipline_aliases; all rank 0).
    ( 1, 'kayak',          'D-010', 'paddle',    0, '0A-v1.9.1', now()),
    ( 2, 'canoe',          'D-011', 'paddle',    0, '0A-v1.9.1', now()),
    ( 3, 'packraft',       'D-009', 'paddle',    0, '0A-v1.9.1', now()),
    ( 4, 'road_bike',      'D-006', 'bike',      0, '0A-v1.9.1', now()),
    ( 5, 'gravel_bike',    'D-006', 'bike',      0, '0A-v1.9.1', now()),
    ( 6, 'gravel_bike',    'D-030', 'bike',      0, '0A-v1.9.1', now()),
    ( 7, 'gravel_bike',    'D-031', 'bike',      0, '0A-v1.9.1', now()),
    ( 8, 'mountain_bike',  'D-008', 'bike',      0, '0A-v1.9.1', now()),
    ( 9, 'mountain_bike',  'D-031', 'bike',      0, '0A-v1.9.1', now()),
    (10, 'tt_bike',        'D-007', 'bike',      0, '0A-v1.9.1', now()),
    (11, 'raft',           'D-019', 'paddle',    0, '0A-v1.9.1', now()),
    (12, 'sup',            'D-032', 'paddle',    0, '0A-v1.9.1', now()),
    -- Gear toggles (the §4 mapping; gated_discipline_ids → alias rows).
    (13, 'climbing_gear',  'D-012', 'climbing',  0, '0A-v1.9.1', now()),
    (14, 'climbing_gear',  'D-013', 'climbing',  0, '0A-v1.9.1', now()),
    (15, 'climbing_gear',  'D-014', 'climbing',  0, '0A-v1.9.1', now()),
    (16, 'snowshoes',      'D-017', 'snow',      0, '0A-v1.9.1', now()),
    (17, 'mountaineering', 'D-018', 'alpine',    0, '0A-v1.9.1', now()),
    (18, 'skimo_at',       'D-021', 'alpine',    0, '0A-v1.9.1', now()),
    (19, 'skimo_at',       'D-022', 'alpine',    0, '0A-v1.9.1', now()),
    -- D-028 ordinal ladder (Decision 8 + 10): real snow → rollerskis → (ski-erg INDOOR).
    (20, 'classic_xc_ski', 'D-028', 'ski',       0, '0A-v1.9.1', now()),
    (21, 'skate_xc_ski',   'D-028', 'ski',       1, '0A-v1.9.1', now()),
    (22, 'rollerskis',     'D-028', 'ski',       2, '0A-v1.9.1', now());

-- Verify: 22 active rows, and the D-028 ladder carries exactly ranks {0,1,2}.
DO $$
DECLARE
    n_rows int;
    n_d028 int;
BEGIN
    SELECT count(*) INTO n_rows
      FROM layer0.gear_discipline_aliases WHERE superseded_at IS NULL;
    IF n_rows <> 22 THEN
        RAISE EXCEPTION '0024 verify: expected 22 active alias rows, found %', n_rows;
    END IF;
    SELECT count(DISTINCT fidelity_rank) INTO n_d028
      FROM layer0.gear_discipline_aliases
     WHERE superseded_at IS NULL AND discipline_id = 'D-028';
    IF n_d028 <> 3 THEN
        RAISE EXCEPTION '0024 verify: D-028 ladder expected 3 fidelity ranks, found %', n_d028;
    END IF;
END $$;

COMMIT;
