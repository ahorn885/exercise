-- verify_drift_specifics.sql
-- Purpose:
--   Resolve whether D-05, D-07, D-08 in Layer0_Drift_Backlog.md need to be
--   promoted to BLOCKER status for Layer 2 design, or stay DEFERRED.
--
-- Read-only. Three independent checks, A/B/C, each self-contained.
--
-- Run:
--   psql $DATABASE_URL -f verify_drift_specifics.sql > drift_verification.txt
--
-- Then paste drift_verification.txt back. Diff is computed inline against
-- xlsx-side data captured in comments below (Sports_Framework_v10.xlsx).

\pset pager off

\echo '##############################################################'
\echo '# CHECK A — sport_discipline_map: are any of the 3 missing rows AR?'
\echo '##############################################################'
\echo ''
\echo '-- Xlsx side (from Sports_Framework_v10.xlsx, "Sport × Discipline Map" sheet):'
\echo '--   AR has 15 disciplines:'
\echo '--     D-001 Trail Running | INCLUDED | Primary'
\echo '--     D-003 Hiking (Weighted) | INCLUDED | Primary'
\echo '--     D-005 XC Cycling (Road/Gravel) | INCLUDED | Primary'
\echo '--     D-006 Mountain Biking | INCLUDED | Primary'
\echo '--     D-007 Packrafting | INCLUDED | Primary'
\echo '--     D-008a Flat-water Kayaking | INCLUDED | Primary'
\echo '--     D-008b Whitewater Kayaking | INCLUDED | Minor (*Conditional)'
\echo '--     D-009 Canoeing | INCLUDED | Primary (race-dependent)'
\echo '--     D-010 Rock Climbing | INCLUDED | Secondary'
\echo '--     D-011 Abseiling | INCLUDED | Minor'
\echo '--     D-012 Fixed Rope / Via Ferrata | INCLUDED | Minor'
\echo '--     D-013 Orienteering/Nav (Cross-discipline) | INCLUDED | Primary'
\echo '--     D-014 Swimming | INCLUDED | Minor'
\echo '--     D-015 Snowshoeing | INCLUDED | Minor'
\echo '--     D-016 Mountaineering | INCLUDED | Minor'
\echo ''
\echo '-- Deployed side:'

SELECT
  discipline_id,
  discipline_name,
  applicability,
  role
FROM layer0.sport_discipline_map
WHERE superseded_at IS NULL
  AND sport_name = 'Adventure Racing'
ORDER BY discipline_id;

\echo ''
\echo '-- Row count check across ALL sports — identifies which sport is short:'
\echo '-- (Xlsx totals: 21 sports, 73 rows; AR=15, plus 20 other sports — see comment below)'
\echo ''
\echo '-- Xlsx per-sport row counts (for comparison):'
\echo '--   Adventure Racing: 15           Marathon (Trail): 2'
\echo '--   Aquabike: 2                    Modern Pentathlon: 4'
\echo '--   Aquathlon: 2                   Mountain Running / Skyrunning: 4'
\echo '--   Biathlon: 2                    Off-Road / Adventure Multisport: 6'
\echo '--   Canoe / Kayak Marathon: 2      Open Water Marathon Swimming: 1'
\echo '--   Cross-Country / Nordic Skiing: 1   Skimo: 3'
\echo '--   Duathlon: 2                    Swimrun: 3'
\echo '--   Fell Running: 4                Triathlon: 5'
\echo '--   Long Distance / Endurance Cycling: 5   Ultramarathon (Road): 1'
\echo '--   Marathon (Mountain): 3         Ultramarathon (Trail): 5'
\echo '--   Marathon (Road): 1'

SELECT sport_name, COUNT(*) AS deployed_rows
FROM layer0.sport_discipline_map
WHERE superseded_at IS NULL
GROUP BY sport_name
ORDER BY sport_name;

\echo ''
\echo '##############################################################'
\echo '# CHECK B — phase_load_weekly_totals: is AR among the 4 missing sports?'
\echo '##############################################################'
\echo ''
\echo '-- Xlsx side: 33 distinct sports each have a WEEKLY TOTAL TARGET row'
\echo '-- Deployed: only 29 distinct sports (4 missing)'
\echo ''
\echo '-- Direct check: does AR have weekly totals deployed?'

SELECT sport_name, phase, weekly_low_hours, weekly_high_hours
FROM layer0.phase_load_weekly_totals
WHERE superseded_at IS NULL
  AND sport_name = 'Adventure Racing'
ORDER BY
  CASE phase WHEN 'Base' THEN 1 WHEN 'Build' THEN 2 WHEN 'Peak' THEN 3 WHEN 'Taper' THEN 4 ELSE 5 END;

\echo ''
\echo '-- Full list of deployed sports — diff against the 33 xlsx sports to identify the missing 4:'
\echo '-- (Xlsx has all 33 sports with WEEKLY TOTAL TARGET rows; deployed has only 29)'
\echo ''
\echo '-- Xlsx 33 sports with WEEKLY TOTAL TARGET (alphabetical):'
\echo '--   Adventure Racing, Aquabike, Aquathlon, Biathlon, Canoe / Kayak Marathon,'
\echo '--   Cross-Country / Nordic Skiing, Duathlon, Fell Running, Ironman 70.3 Triathlon,'
\echo '--   Ironman Triathlon, Long Distance / Endurance Cycling, Marathon (Mountain),'
\echo '--   Marathon (Road), Marathon (Trail), Modern Pentathlon,'
\echo '--   Mountain Running / Skyrunning, Off-Road / Adventure Multisport (Non-Nav),'
\echo '--   Open Water Marathon Swimming, Rogaining, Skimo, Sprint Triathlon, Stand-Up Paddleboard,'
\echo '--   Swimrun, Triathlon, Ultramarathon (Road), Ultramarathon (Trail),'
\echo '--   plus ~7 more (run the query for the full deployed list and diff)'

SELECT DISTINCT sport_name
FROM layer0.phase_load_weekly_totals
WHERE superseded_at IS NULL
ORDER BY sport_name;

\echo ''
\echo '##############################################################'
\echo '# CHECK C — phase_load_allocation aggregators: confirm AR is polluted'
\echo '##############################################################'
\echo ''
\echo '-- Spec says ETL filters WEEKLY TOTAL TARGET rows. ETL is not filtering.'
\echo '-- This check confirms the pollution exists in AR rows specifically.'

SELECT
  sport_name,
  discipline_name,
  role,
  base_pct_low,
  base_pct_high,
  build_pct_low,
  build_pct_high,
  peak_pct_low,
  peak_pct_high,
  taper_pct_low,
  taper_pct_high
FROM layer0.phase_load_allocation
WHERE superseded_at IS NULL
  AND sport_name = 'Adventure Racing'
  AND discipline_name ILIKE '%WEEKLY TOTAL%'
ORDER BY discipline_name;

\echo ''
\echo '-- Also count aggregators across all sports to confirm scale of D-05:'

SELECT COUNT(*) AS aggregator_rows_in_phase_load_allocation
FROM layer0.phase_load_allocation
WHERE superseded_at IS NULL
  AND discipline_name ILIKE '%WEEKLY TOTAL%';

\echo ''
\echo '-- Per-sport aggregator presence (for the missing-4 cross-reference):'

SELECT
  sport_name,
  COUNT(*) FILTER (WHERE discipline_name ILIKE '%WEEKLY TOTAL%') AS aggregator_rows_in_pla,
  COUNT(*) FILTER (WHERE discipline_name NOT ILIKE '%WEEKLY TOTAL%') AS discipline_rows
FROM layer0.phase_load_allocation
WHERE superseded_at IS NULL
GROUP BY sport_name
HAVING COUNT(*) FILTER (WHERE discipline_name ILIKE '%WEEKLY TOTAL%') > 0
ORDER BY sport_name;

\echo ''
\echo '##############################################################'
\echo '# END VERIFICATION'
\echo '##############################################################'
