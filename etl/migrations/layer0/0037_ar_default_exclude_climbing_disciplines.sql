-- 0037_ar_default_exclude_climbing_disciplines.sql
--
-- #1061 — Rock Climbing (D-012), Abseiling (D-013), and Via Ferrata (D-014)
-- carry `default_inclusion = 'included'` on their Adventure Racing
-- `phase_load_allocation` rows, so Layer 2A's curator-default fallback
-- (`_resolve_inclusion`, layer2a/builder.py) defaults all three into every AR
-- plan whether or not the athlete's race involves them. The planner then
-- warns these disciplines aren't trainable at the athlete's saved locations
-- (no climbing gym / crag / via ferrata site nearby) even when the athlete
-- never said their race included climbing.
--
-- `_resolve_inclusion`'s precedence is race demand > athlete weighting >
-- curator default (#509), so flipping the curator default to `excluded`
-- changes nothing for an athlete who actually specifies these disciplines —
-- race-derived terrain overrides or an explicit athlete discipline list both
-- still win and include them. Only the silent default-everyone-in behavior
-- goes away.
--
-- Serving-relevant edit (README §"Two edit shapes", shape 2): this changes
-- which disciplines Layer 2A serves by default, so the affected rows are
-- superseded and re-inserted at a bumped `phase_load_allocation` table
-- version (current AR active max is `0A-v1.6.8`) to advance the 0A digest
-- and invalidate plan-gen caches.
--
-- Idempotent: UNIQUE (sport_name, discipline_name, etl_version) +
-- ON CONFLICT DO NOTHING make a re-run a clean no-op; the supersede UPDATE
-- only matches rows still active at the old version.

BEGIN;

INSERT INTO layer0.phase_load_allocation
  (sport_name, discipline_id, discipline_name, role,
   base_pct_low, base_pct_high, build_pct_low, build_pct_high,
   peak_pct_low, peak_pct_high, taper_pct_low, taper_pct_high,
   notes_conditions, etl_version, etl_run_at, superseded_at,
   default_inclusion, prescription_note, audit_log, raw_notes, row_category)
SELECT
   sport_name, discipline_id, discipline_name, role,
   base_pct_low, base_pct_high, build_pct_low, build_pct_high,
   peak_pct_low, peak_pct_high, taper_pct_low, taper_pct_high,
   notes_conditions, '0A-v1.6.9', now(), NULL,
   'excluded', prescription_note, audit_log, raw_notes, row_category
  FROM layer0.phase_load_allocation
 WHERE superseded_at IS NULL
   AND sport_name = 'Adventure Racing'
   AND discipline_id IN ('D-012', 'D-013', 'D-014')
ON CONFLICT (sport_name, discipline_name, etl_version) DO NOTHING;

UPDATE layer0.phase_load_allocation
   SET superseded_at = now()
 WHERE superseded_at IS NULL
   AND sport_name = 'Adventure Racing'
   AND discipline_id IN ('D-012', 'D-013', 'D-014')
   AND etl_version <> '0A-v1.6.9';

COMMIT;
