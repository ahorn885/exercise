-- 0031_sport_sub_format_map.sql
--
-- #254 / D-17 slice A — the Sheet 3 / Sheet 5 sport-naming bridge for onboarding.
--
-- Five sports name themselves TOP-LEVEL in sport_discipline_map +
-- sport_discipline_bridge ("Triathlon") but SUB-FORMAT in
-- phase_load_allocation + phase_load_weekly_totals ("Triathlon (Standard /
-- Olympic)"). So an onboarding pick of the bare parent joins zero PLA rows ->
-- silent NULL phase-load -> a no-volume plan (the D-17 bug). The capture-side
-- fix (Onboarding_SportSubFormat_D17_254_Design_v1.md, ratified 2026-06-29)
-- asks the athlete WHICH sub-format, defaulting to a curated one.
--
-- This table is that option source + the curated default. One row per PLA
-- sub-format, grouped by its top-level parent, with is_default marking exactly
-- one variant per parent (the pre-selected option in the race-event form).
--
-- The five parents are NOT hard-coded: by construction they are exactly the
-- sport_discipline_bridge framework_sports that have NO same-named
-- phase_load_allocation row (PLA carries only their sub-formats). The verify
-- blocks below assert the seed matches that data-derived set, so the migration
-- fails loudly if Layer 0's sport vocabulary drifts out from under it.
--
-- Read by: onboarding/profile race-event form (options + default) and the
-- Layer 4 orchestrator (composing the resolved PLA name for Layer 2A) — both
-- land in slice B. Nothing reads it yet, so this changes no served output and
-- needs no cache-version coordination: the athlete's *chosen* sub-format is
-- stored on race_events (slice B) and drives their plan, so the table's default
-- is a lookup, not a cached plan input — deliberately NOT registered in
-- orchestrator._LAYER0_TABLE_FAMILY.
--
-- Idempotent: CREATE IF NOT EXISTS + delete-this-version-then-insert.

BEGIN;

CREATE TABLE IF NOT EXISTS layer0.sport_sub_format_map (
    id               integer PRIMARY KEY,
    parent_sport     text    NOT NULL,   -- top-level (matches sport_discipline_bridge.framework_sport)
    sub_format_sport text    NOT NULL,   -- full PLA sport_name (matches phase_load_allocation.sport_name)
    is_default       boolean NOT NULL DEFAULT false,
    display_label    text,               -- athlete-facing short label (the parenthetical content)
    etl_version      text    NOT NULL,
    etl_run_at       timestamp with time zone NOT NULL,
    superseded_at    timestamp with time zone
);

-- Re-runnable: drop this version's rows before re-seeding.
DELETE FROM layer0.sport_sub_format_map WHERE etl_version = '0A-v1.9.3';

INSERT INTO layer0.sport_sub_format_map
    (id, parent_sport, sub_format_sport, is_default, display_label, etl_version, etl_run_at)
VALUES
    -- Triathlon (default: Standard / Olympic — the canonical reference distance)
    ( 1, 'Triathlon', 'Triathlon (Sprint)',                          false, 'Sprint',                  '0A-v1.9.3', now()),
    ( 2, 'Triathlon', 'Triathlon (Standard / Olympic)',              true,  'Standard / Olympic',      '0A-v1.9.3', now()),
    ( 3, 'Triathlon', 'Triathlon (Half / 70.3)',                     false, 'Half / 70.3',             '0A-v1.9.3', now()),
    ( 4, 'Triathlon', 'Triathlon (Full / Ironman 140.6)',           false, 'Full / Ironman 140.6',    '0A-v1.9.3', now()),
    -- Skimo (default: Individual / Team — the standard mass-start format)
    ( 5, 'Skimo', 'Skimo (Sprint)',                                  false, 'Sprint',                  '0A-v1.9.3', now()),
    ( 6, 'Skimo', 'Skimo (Vertical / VK)',                           false, 'Vertical / VK',           '0A-v1.9.3', now()),
    ( 7, 'Skimo', 'Skimo (Individual / Team)',                       true,  'Individual / Team',       '0A-v1.9.3', now()),
    ( 8, 'Skimo', 'Skimo (Long Distance / Grand Traverse)',          false, 'Long Distance / Grand Traverse', '0A-v1.9.3', now()),
    -- Long Distance / Endurance Cycling (default: Road / Gran Fondo)
    ( 9, 'Long Distance / Endurance Cycling', 'Long Distance / Endurance Cycling (Road / Gran Fondo)', true,  'Road / Gran Fondo',  '0A-v1.9.3', now()),
    (10, 'Long Distance / Endurance Cycling', 'Long Distance / Endurance Cycling (Gravel)',            false, 'Gravel',             '0A-v1.9.3', now()),
    (11, 'Long Distance / Endurance Cycling', 'Long Distance / Endurance Cycling (Enduro)',            false, 'Enduro',             '0A-v1.9.3', now()),
    (12, 'Long Distance / Endurance Cycling', 'Long Distance / Endurance Cycling (Time Trial)',        false, 'Time Trial',         '0A-v1.9.3', now()),
    (13, 'Long Distance / Endurance Cycling', 'Long Distance / Endurance Cycling (XC Mountain Biking)',false, 'XC Mountain Biking', '0A-v1.9.3', now()),
    -- Canoe / Kayak Marathon (default: ICF Competition — the standardized marathon format)
    (14, 'Canoe / Kayak Marathon', 'Canoe / Kayak Marathon (ICF Competition)',  true,  'ICF Competition', '0A-v1.9.3', now()),
    (15, 'Canoe / Kayak Marathon', 'Canoe / Kayak Marathon (Ultra-Distance)',   false, 'Ultra-Distance',  '0A-v1.9.3', now()),
    -- Open Water Marathon Swimming (default: 10km / Olympic Distance — the standard marathon-swim distance)
    (16, 'Open Water Marathon Swimming', 'Open Water Marathon Swimming (10km / Olympic Distance)', true,  '10km / Olympic Distance', '0A-v1.9.3', now()),
    (17, 'Open Water Marathon Swimming', 'Open Water Marathon Swimming (25km / Ultra Distance)',   false, '25km / Ultra Distance',   '0A-v1.9.3', now());

-- Verify the seed against Layer 0's live vocabulary.
DO $$
DECLARE
    n_rows           int;
    n_bad_default    int;
    n_orphan_subfmt  int;
    n_parent_mismatch int;
BEGIN
    SELECT count(*) INTO n_rows
      FROM layer0.sport_sub_format_map WHERE superseded_at IS NULL;
    IF n_rows <> 17 THEN
        RAISE EXCEPTION '0031 verify: expected 17 active rows, found %', n_rows;
    END IF;

    -- (a) Exactly one default per parent.
    SELECT count(*) INTO n_bad_default FROM (
        SELECT parent_sport
          FROM layer0.sport_sub_format_map
         WHERE superseded_at IS NULL
         GROUP BY parent_sport
        HAVING count(*) FILTER (WHERE is_default) <> 1
    ) bad;
    IF n_bad_default <> 0 THEN
        RAISE EXCEPTION '0031 verify: % parent(s) lack exactly one default', n_bad_default;
    END IF;

    -- (b) Every sub_format_sport is a real active PLA sport_name.
    SELECT count(*) INTO n_orphan_subfmt
      FROM layer0.sport_sub_format_map m
     WHERE m.superseded_at IS NULL
       AND NOT EXISTS (
           SELECT 1 FROM layer0.phase_load_allocation p
            WHERE p.superseded_at IS NULL
              AND p.sport_name = m.sub_format_sport
       );
    IF n_orphan_subfmt <> 0 THEN
        RAISE EXCEPTION '0031 verify: % sub_format_sport(s) absent from phase_load_allocation', n_orphan_subfmt;
    END IF;

    -- (c) parent_sport set == the data-derived mismatched-parent set:
    --     bridge framework_sports with NO same-named PLA row. Symmetric-diff = 0.
    SELECT count(*) INTO n_parent_mismatch FROM (
        SELECT DISTINCT parent_sport AS s FROM layer0.sport_sub_format_map WHERE superseded_at IS NULL
        EXCEPT
        SELECT DISTINCT b.framework_sport
          FROM layer0.sport_discipline_bridge b
         WHERE b.superseded_at IS NULL
           AND NOT EXISTS (
               SELECT 1 FROM layer0.phase_load_allocation p
                WHERE p.superseded_at IS NULL AND p.sport_name = b.framework_sport)
        UNION ALL
        SELECT DISTINCT b.framework_sport
          FROM layer0.sport_discipline_bridge b
         WHERE b.superseded_at IS NULL
           AND NOT EXISTS (
               SELECT 1 FROM layer0.phase_load_allocation p
                WHERE p.superseded_at IS NULL AND p.sport_name = b.framework_sport)
        EXCEPT
        SELECT DISTINCT parent_sport FROM layer0.sport_sub_format_map WHERE superseded_at IS NULL
    ) symdiff;
    IF n_parent_mismatch <> 0 THEN
        RAISE EXCEPTION '0031 verify: parent_sport set differs from the bridge/PLA mismatch set by % entr(ies)', n_parent_mismatch;
    END IF;
END $$;

COMMIT;
