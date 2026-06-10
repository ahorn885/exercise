-- Vocabulary V4b — retire the 22 legacy equipment_items rows.
--
-- These rows (families 0A-v17.K / 0B-v19.K2 / 0B-v19.K3) were seeded by retired
-- one-shot populate_equipment_items_K*.sql scripts and never superseded (the live
-- 0C ETL's supersede sweep is scoped to etl_version LIKE '0C-v%'). Their content
-- has been reconciled into the 0C vocab in v1.6.4 (Climbing kit bundle,
-- Mountaineering kit, ski/gym-misc re-homed, TT Bike normalized to the existing
-- "TT / triathlon bike" vessel).
--
-- RUN THIS FIRST, then apply layer0_etl_v1.6.4.sql. Order matters: several
-- reconciled 0C names (Mountaineering kit, Touring ski kit, XC ski kit,
-- Rollerskis, Inline skates, Ab straps, Mini hurdles, Stairs, Mini trampoline,
-- Wobble board, Stick roller, Hyperextension bench) are case-insensitive
-- duplicates of these legacy rows; inserting them while the legacy rows are
-- still active would violate equipment_items_active_ci_name_idx. Retiring the
-- legacy rows first clears the index so v1.6.4 applies cleanly.
--
-- Idempotent: re-running is a no-op once the rows are superseded.

UPDATE layer0.equipment_items
   SET superseded_at = NOW()
 WHERE superseded_at IS NULL
   AND etl_version IN ('0A-v17.K', '0B-v19.K2', '0B-v19.K3');
