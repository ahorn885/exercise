-- 0028_drop_modality_group_kind.sql
--
-- #884 slice 4b (taxonomy normalization, Andy 2026-06-29) — drop the now-unused
-- `group_kind` column from `layer0.modality_groups`.
--
-- The cascade was generalized to gate on the GEAR-side kind
-- (`gear_discipline_aliases.group_kind` via `discipline_gear_kind`) this slice, so
-- the modality-side `group_kind` (the discipline stimulus family) has no remaining
-- reader: `_q_modality_group_kind` and the `group_kind_by_group` plumbing were
-- removed in the same PR. Layer 2A pooling keys on group MEMBERSHIP
-- (`discipline_modality_membership` → group_id), not the kind; `validate_layer0`
-- never read it. Dropping the column removes the second, divergent taxonomy at the
-- source, leaving the gear taxonomy as the single `group_kind` vocabulary.
--
-- This is the column-drop half of the taxonomy normalization (the value rename
-- `climbing`→`climb` is migration 0027 on the gear table). Lands in the same
-- `layer0-apply` run.
--
-- Idempotent: DROP COLUMN IF EXISTS (a no-op after the first apply, and after a
-- future redump whose baseline already lacks the column).

\set ON_ERROR_STOP on

BEGIN;

ALTER TABLE layer0.modality_groups DROP COLUMN IF EXISTS group_kind;

-- Verify (atomic): the column is gone.
DO $$
DECLARE
    n_col int;
BEGIN
    SELECT count(*) INTO n_col
      FROM information_schema.columns
     WHERE table_schema = 'layer0'
       AND table_name = 'modality_groups'
       AND column_name = 'group_kind';
    IF n_col <> 0 THEN
        RAISE EXCEPTION '0028 verify: modality_groups.group_kind still present (% col)', n_col;
    END IF;

    RAISE NOTICE '0028: OK — modality_groups.group_kind dropped (gear taxonomy is now the single group_kind vocab)';
END $$;

COMMIT;

-- End of 0028_drop_modality_group_kind.sql
