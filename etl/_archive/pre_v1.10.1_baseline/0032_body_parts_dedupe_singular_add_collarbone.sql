-- 0032_body_parts_dedupe_singular_add_collarbone.sql
--
-- #255 body-part half — Layer 0 canonical hygiene on layer0.body_parts so the
-- side-less injury picker (routes/injuries.py BODY_PART_GROUPS) and the
-- exercise contraindicated_parts vocab agree on one form per part.
--
-- 1. Retire the unused SINGULAR Bicep / Tricep. The table carries both singular
--    and plural (Biceps / Triceps); every exercise.contraindicated_parts
--    reference uses the PLURAL (Biceps:14, Triceps:14; Bicep/Tricep: 0), and the
--    injury picker matches the plural. The singular rows are dead dupes. (The v3
--    vocab audit listed the singular, but live data settled on the plural — the
--    deployed set wins.)
-- 2. Add Collarbone (audit §1 canonical, Shoulder region) — absent from live;
--    lets athletes log clavicle injuries (the MTB/AR crash pattern that drove
--    D-006). No exercise contraindicates on it yet, so this is additive only.
--
-- Edit shape: cache-NEUTRAL (README "Two edit shapes" #1) — no version bump.
-- Nothing in the serving path enumerates layer0.body_parts (it is reference /
-- validation vocab; Layer 2D matches injury body_part against an exercise's
-- contraindicated_parts, it does not read this table), and the retired singular
-- rows have zero references, so no served output changes.
--
-- Idempotent: the supersede predicate skips already-retired rows; the insert is
-- guarded by NOT EXISTS on an active Collarbone.

BEGIN;

UPDATE layer0.body_parts
   SET superseded_at = now()
 WHERE superseded_at IS NULL
   AND canonical_name IN ('Bicep', 'Tricep');

INSERT INTO layer0.body_parts
    (canonical_name, body_region, source_origin, notes, etl_version, etl_run_at, superseded_at)
SELECT 'Collarbone', 'Shoulder', 'D-23 (FC-1b)',
       'Clavicle — #255 canonical add (MTB/AR crash injury pattern)',
       (SELECT etl_version FROM layer0.body_parts
         WHERE canonical_name = 'Shoulder' AND superseded_at IS NULL
         LIMIT 1),
       now(), NULL
 WHERE NOT EXISTS (
       SELECT 1 FROM layer0.body_parts
        WHERE canonical_name = 'Collarbone' AND superseded_at IS NULL);

COMMIT;
