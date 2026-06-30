-- 0035_trn018_off_trail_gap_rules.sql
--
-- #340 (Phase 3) — terrain_gap_rules proxy/adaptation guidance for TRN-018
-- "Off Trail / Bushwhack".
--
-- TRN-018 already exists in the live vocab (genesis 0C-v1.6.7) and covers the
-- off-trail / trackless stimulus. It is now a required terrain for D-001 Trail
-- Running, D-024 Mountain Running, and D-018 Mountaineering (alongside the
-- existing D-003 Trekking) — see `_DISCIPLINE_REQUIRED_TERRAINS` in
-- `layer4/session_feasibility.py`. But TRN-018 had NO terrain_gap_rules row, so
-- an athlete whose locale lacks trackless terrain got no proxy/adaptation
-- guidance for it. This adds three bridgeable proxies, best-to-worst:
--   TRN-003 Technical Trail  — moderate (0.50): closest footing analog.
--   TRN-007 Technical Rock / Scree — low (0.45): strong unstable-footing
--                              transfer, but rock surface, no vegetation.
--   TRN-002 Groomed Trail    — low (0.40): aerobic base / unpaved gait only.
--
-- Serving-relevant (new athlete-facing guidance) → inserted at a bumped
-- table version `0C-v2.5` so the terrain-gap digest advances and plan-gen
-- caches invalidate (per etl/migrations/layer0/README.md "Two edit shapes").
-- Idempotent: the (target_terrain_id, proxy_terrain_id, etl_version) UNIQUE +
-- ON CONFLICT DO NOTHING make a re-run a clean no-op.

BEGIN;

INSERT INTO layer0.terrain_gap_rules
  (target_terrain_id, target_terrain_name, proxy_terrain_id, proxy_terrain_name,
   gap_severity, adaptation_weeks_low, adaptation_weeks_high, proxy_fidelity,
   proxy_methods, uncoverable_stimulus, prescription_note, audit_log,
   etl_version, etl_run_at, superseded_at)
VALUES
  ('TRN-018', 'Off Trail / Bushwhack', 'TRN-003', 'Technical Trail',
   'medium', 4, 8, 0.50,
   ARRAY[
     'Run or hike the roughest, least-maintained technical trail available — rocky, root-crossed, uneven surface (closest footing analog)',
     'Add genuine off-trail sessions on any unmaintained ground (scrub, tall grass, deadfall) where access and safety permit',
     'Continuous map-and-compass route-finding practice on any terrain, ideally under fatigue',
     'Single-leg and lateral stability work for footing micro-adjustment on unstable ground'
   ],
   ARRAY['cognitive_navigation', 'balance_dynamic'],
   'Technical trail transfers the footing and proprioceptive load well, but tracked terrain removes the continuous route-finding and vegetation resistance that define trackless travel. Prioritize the roughest unmaintained ground you can reach, and treat navigation as a trainable skill — no marked surface reproduces continuous route-finding.',
   'Proprioceptive surface adaptation: Myer et al. (2006), J Athl Train — same basis as the TRN-003 technical-trail rule. Route-finding under fatigue: Dyer et al. (2016) — same basis as the TRN-006 Fell / Moorland rule. Proxy fidelity 0.50 — footing and aerobic load transfer high; route-finding and vegetation resistance uncovered.',
   '0C-v2.5', '2026-06-30 00:00:00+00', NULL),

  ('TRN-018', 'Off Trail / Bushwhack', 'TRN-007', 'Technical Rock / Scree',
   'high', 4, 8, 0.45,
   ARRAY[
     'Scree and loose-rock locomotion sessions — boulder fields, talus, unstable rock (strong transfer for footing micro-adjustment)',
     'Pair with any vegetated off-trail ground available to add the brush resistance and soft, hidden footing scree lacks',
     'Continuous route-finding practice — scree slopes are pathless but lack the vegetation-navigation load'
   ],
   ARRAY['cognitive_navigation'],
   'Loose scree demands the same constant footing micro-adjustment as trackless ground and transfers the proprioceptive stimulus strongly. What it misses is vegetation resistance and the soft, hidden footing of bushwhack terrain. Use scree for the unstable-footing load and add any vegetated off-trail ground for the rest.',
   'Proprioceptive and footing adaptation on unstable surface: Myer et al. (2006), J Athl Train. Proxy fidelity 0.45 — unstable-footing transfer strong; vegetation resistance and soft-ground navigation uncovered.',
   '0C-v2.5', '2026-06-30 00:00:00+00', NULL),

  ('TRN-018', 'Off Trail / Bushwhack', 'TRN-002', 'Groomed Trail',
   'high', 6, 10, 0.40,
   ARRAY[
     'Groomed singletrack for aerobic base and unpaved-surface gait — the only stimulus it covers well',
     'Off-trail sessions on any unmaintained ground wherever access permits — the primary tool for the uncovered footing and navigation load',
     'Map-and-compass route-finding practice on any terrain',
     'Single-leg, lateral stability, and agility work to compensate for the missing unstable-footing stimulus'
   ],
   ARRAY['cognitive_navigation', 'balance_dynamic'],
   'Groomed trail covers aerobic load and unpaved-surface gait only — its smooth, maintained surface gives almost no footing-instability or route-finding transfer. Treat it as base maintenance and put real off-trail and navigation work everywhere access allows.',
   'Aerobic and gait transfer high, surface-specific adaptation negligible on a groomed surface: Myer et al. (2006), J Athl Train; route-finding non-transferable from marked terrain: Dyer et al. (2016) — same basis as the TRN-006 Fell / Moorland to Groomed Trail rule. Proxy fidelity 0.40 — aerobic base only.',
   '0C-v2.5', '2026-06-30 00:00:00+00', NULL)
ON CONFLICT (target_terrain_id, proxy_terrain_id, etl_version) DO NOTHING;

COMMIT;
