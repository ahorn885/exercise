-- 0030_drop_craft_discipline_aliases.sql
--
-- #884 slice 4.3 — retire the legacy `layer0.craft_discipline_aliases` table.
-- It was generalized into `gear_discipline_aliases` (migration 0024) and the
-- slice-4a cutover repointed every reader (`_q_craft_discipline_aliases`,
-- `_q_craft_group_kind` in layer4/orchestrator.py) onto the unified table — the
-- craft rows migrated 1:1, verified byte-identical. As of slice 4b PR-3 (#993)
-- NOTHING in app code reads `craft_discipline_aliases`: a repo-wide grep finds
-- only docstrings/comments referencing it as the retired predecessor. The data
-- lives on in git history (every `etl/output/layer0_etl_v*.sql` baseline) and in
-- the active `gear_discipline_aliases` rows, so DROP loses no information.
--
-- DROP (not supersede) is deliberate: this table must leave the schema entirely
-- so it can leave `_LAYER0_TABLE_FAMILY` (layer4/orchestrator.py). A versioned
-- table that merely had all rows superseded would still carry its DDL (the
-- etl_version column) and the `TestLayer0TableFamilyMap` drift guard reads the
-- baseline DDL, so it could never exit the family map — leaving dead config and
-- an empty table the per-table digest query still hits. DROP is the honest
-- retire; the invalidate-not-overwrite convention is for ROWS in live tables,
-- not for a fully-replaced relation.
--
-- SEQUENCING (read before applying — there is a deploy-order hazard):
--   `_q_current_etl_version_set` runs `SELECT … FROM layer0.<table>` for EVERY
--   table in `_LAYER0_TABLE_FAMILY`. If this DROP lands on live while the
--   DEPLOYED code still maps `craft_discipline_aliases`, that query throws
--   (relation does not exist) and ALL plan-gen breaks. So the paired code change
--   (remove the map entry) MUST be deployed FIRST. Because Vercel deploys on
--   merge and `layer0-apply` is a separate manual Andy tap, the safe order is:
--   merge the PR (code map-removal deploys) → THEN tap `layer0-apply` (this DROP
--   runs against live, by which point nothing queries the table).
--
--   The committed baseline (etl/output/layer0_etl_v1.9.0.sql) still CONTAINS the
--   table, so removing it from the map would normally fail the drift guard; this
--   slice bridges that by listing `craft_discipline_aliases` in the guard's
--   `_FAMILY_MAP_EXCEPTIONS` (tests/test_layer4_orchestrator.py) until the
--   follow-up `layer0-redump` folds it out of the baseline — at which point both
--   the exception AND this migration are archived (README §"A re-dump … MUST be
--   paired with folding the now-baked migrations").
--
-- CASCADE drops the table's OWNED-BY sequence (craft_discipline_aliases_id_seq);
-- no other object references the table (no inbound FK — audited vs the v1.9.0
-- baseline: only its own PK + UNIQUE constraints).
--
-- Idempotent: DROP TABLE IF EXISTS is a clean no-op on a prod where the table is
-- already gone (re-run, or apply after the redump removed it).
--
-- Atomic: the verify DO block RAISEs (rolling back) if the table somehow still
-- exists after the DROP.

\set ON_ERROR_STOP on

BEGIN;

DROP TABLE IF EXISTS layer0.craft_discipline_aliases CASCADE;

-- ── Verify (atomic) ──────────────────────────────────────────────────────────
DO $$
DECLARE v_exists INT;
BEGIN
  SELECT count(*) INTO v_exists
    FROM information_schema.tables
   WHERE table_schema = 'layer0' AND table_name = 'craft_discipline_aliases';
  IF v_exists <> 0 THEN
    RAISE EXCEPTION '0030: layer0.craft_discipline_aliases still exists after DROP';
  END IF;
  RAISE NOTICE '0030: OK — layer0.craft_discipline_aliases retired (DROP TABLE CASCADE); readers cut over to gear_discipline_aliases in slice 4a';
END $$;

COMMIT;

-- End of 0030_drop_craft_discipline_aliases.sql
