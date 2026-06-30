-- 0036_nutrition_fueling_tables.sql
--
-- #229 + #233 (Phase 4) — promote Layer 2E hardcoded nutrition/fueling
-- constants into Layer 0 tables so they are curated data rather than
-- hardcoded logic.
--
-- Four new tables (all family 0A):
--   sport_met_values        (#233) — activity-multiplier band by phase×tier
--   race_fueling_bands      (#229) — race-day CHO/Na/fluid/protein by duration tier
--   sport_profile_cho_mod   (#229) — sport-profile CHO modifier
--   dietary_pattern_flags   (#229) — per-pattern deficiency/concern flags
--
-- Behavior-preserving: seeds are verbatim transcriptions of the constants
-- in layer2e/builder.py (_MULTIPLIER_BANDS, _FUELING_BANDS,
-- _SPORT_PROFILE_CHO_MOD, _dietary_pattern_adjustments). No existing row
-- or output changes.
--
-- New tables → initial etl_version 0A-v1.0. The 0A digest advances once
-- these tables are registered and loaded, triggering a one-time cache
-- invalidation (expected, architecturally correct).
--
-- Idempotent: every table has UNIQUE (key_col(s), etl_version) + ON CONFLICT
-- DO NOTHING, so a re-run inserts 0 rows cleanly.

BEGIN;

-- ─── 1. sport_met_values (#233) ──────────────────────────────────────────────
-- Activity-multiplier lookup table: Phase × volume_tier_index → multiplier.
-- volume_tier_index 0=<6hr/wk  1=6-10hr  2=10-15hr  3=15+hr (mid of PLA band).
-- Seeds from _MULTIPLIER_BANDS in layer2e/builder.py.

CREATE TABLE IF NOT EXISTS layer0.sport_met_values (
    id                 SERIAL PRIMARY KEY,
    phase              TEXT NOT NULL,   -- 'Base','Build','Peak','Taper'
    volume_tier_index  INT  NOT NULL,   -- 0,1,2,3
    volume_tier_label  TEXT NOT NULL,   -- 'low','mid','high','very_high'
    multiplier         NUMERIC NOT NULL,
    etl_version        TEXT NOT NULL,
    etl_run_at         TIMESTAMPTZ NOT NULL,
    superseded_at      TIMESTAMPTZ,
    UNIQUE (phase, volume_tier_index, etl_version)
);

INSERT INTO layer0.sport_met_values
  (phase, volume_tier_index, volume_tier_label, multiplier, etl_version, etl_run_at, superseded_at)
VALUES
  ('Base',  0, 'low',       1.40, '0A-v1.0', '2026-06-30 00:00:00+00', NULL),
  ('Base',  1, 'mid',       1.55, '0A-v1.0', '2026-06-30 00:00:00+00', NULL),
  ('Base',  2, 'high',      1.70, '0A-v1.0', '2026-06-30 00:00:00+00', NULL),
  ('Base',  3, 'very_high', 1.85, '0A-v1.0', '2026-06-30 00:00:00+00', NULL),
  ('Build', 0, 'low',       1.60, '0A-v1.0', '2026-06-30 00:00:00+00', NULL),
  ('Build', 1, 'mid',       1.75, '0A-v1.0', '2026-06-30 00:00:00+00', NULL),
  ('Build', 2, 'high',      1.90, '0A-v1.0', '2026-06-30 00:00:00+00', NULL),
  ('Build', 3, 'very_high', 2.05, '0A-v1.0', '2026-06-30 00:00:00+00', NULL),
  ('Peak',  0, 'low',       1.75, '0A-v1.0', '2026-06-30 00:00:00+00', NULL),
  ('Peak',  1, 'mid',       1.90, '0A-v1.0', '2026-06-30 00:00:00+00', NULL),
  ('Peak',  2, 'high',      2.10, '0A-v1.0', '2026-06-30 00:00:00+00', NULL),
  ('Peak',  3, 'very_high', 2.30, '0A-v1.0', '2026-06-30 00:00:00+00', NULL),
  ('Taper', 0, 'low',       1.55, '0A-v1.0', '2026-06-30 00:00:00+00', NULL),
  ('Taper', 1, 'mid',       1.70, '0A-v1.0', '2026-06-30 00:00:00+00', NULL),
  ('Taper', 2, 'high',      1.85, '0A-v1.0', '2026-06-30 00:00:00+00', NULL),
  ('Taper', 3, 'very_high', 2.00, '0A-v1.0', '2026-06-30 00:00:00+00', NULL)
ON CONFLICT (phase, volume_tier_index, etl_version) DO NOTHING;


-- ─── 2. race_fueling_bands (#229) ────────────────────────────────────────────
-- Race-day base bands by duration tier. Seeds from _FUELING_BANDS in
-- layer2e/builder.py.  protein_after_hr_threshold / _flat / _initial columns
-- encode the tuple (threshold_hr, g_per_hr_flat, g_per_hr_initial) stored as
-- protein_g_per_hr_after_hr_n on RaceDayFueling; NULL columns mean no protein
-- supplement at this tier.

CREATE TABLE IF NOT EXISTS layer0.race_fueling_bands (
    id                          SERIAL PRIMARY KEY,
    duration_tier               TEXT    NOT NULL,  -- 'tier_short' .. 'tier_extended_expedition'
    cho_low                     NUMERIC NOT NULL,  -- g/hr
    cho_high                    NUMERIC NOT NULL,
    na_low                      NUMERIC NOT NULL,  -- mg/hr
    na_high                     NUMERIC NOT NULL,
    fluid_low                   NUMERIC,           -- ml/hr; NULL at expedition tiers
    fluid_high                  NUMERIC,
    protein_after_hr_threshold  INT,               -- hour after which protein supplemented
    protein_g_per_hr_flat       NUMERIC,           -- flat g/hr rate after threshold
    protein_g_initial           NUMERIC,           -- initial serving (may differ from flat)
    etl_version                 TEXT    NOT NULL,
    etl_run_at                  TIMESTAMPTZ NOT NULL,
    superseded_at               TIMESTAMPTZ,
    UNIQUE (duration_tier, etl_version)
);

INSERT INTO layer0.race_fueling_bands
  (duration_tier, cho_low, cho_high, na_low, na_high, fluid_low, fluid_high,
   protein_after_hr_threshold, protein_g_per_hr_flat, protein_g_initial,
   etl_version, etl_run_at, superseded_at)
VALUES
  ('tier_short',
   60.0, 90.0, 500.0, 800.0, 500.0, 750.0,
   NULL, NULL, NULL,
   '0A-v1.0', '2026-06-30 00:00:00+00', NULL),
  ('tier_mid',
   60.0, 90.0, 600.0, 1000.0, 400.0, 700.0,
   NULL, NULL, NULL,
   '0A-v1.0', '2026-06-30 00:00:00+00', NULL),
  ('tier_long',
   50.0, 80.0, 500.0, 800.0, 400.0, 700.0,
   8, 5.0, 5.0,
   '0A-v1.0', '2026-06-30 00:00:00+00', NULL),
  ('tier_expedition',
   40.0, 70.0, 400.0, 700.0, NULL, NULL,
   8, 5.0, 10.0,
   '0A-v1.0', '2026-06-30 00:00:00+00', NULL),
  ('tier_extended_expedition',
   40.0, 70.0, 400.0, 700.0, NULL, NULL,
   8, 5.0, 10.0,
   '0A-v1.0', '2026-06-30 00:00:00+00', NULL)
ON CONFLICT (duration_tier, etl_version) DO NOTHING;


-- ─── 3. sport_profile_cho_mod (#229) ─────────────────────────────────────────
-- Sport-profile CHO modifier (§5.4.3). Seeds from _SPORT_PROFILE_CHO_MOD in
-- layer2e/builder.py. 'default' row is the fallback for unrecognised profiles.

CREATE TABLE IF NOT EXISTS layer0.sport_profile_cho_mod (
    id             SERIAL PRIMARY KEY,
    sport_profile  TEXT    NOT NULL,  -- 'running','cycling','swimming',... or 'default'
    cho_modifier   NUMERIC NOT NULL,
    etl_version    TEXT    NOT NULL,
    etl_run_at     TIMESTAMPTZ NOT NULL,
    superseded_at  TIMESTAMPTZ,
    UNIQUE (sport_profile, etl_version)
);

INSERT INTO layer0.sport_profile_cho_mod
  (sport_profile, cho_modifier, etl_version, etl_run_at, superseded_at)
VALUES
  ('running',     0.85, '0A-v1.0', '2026-06-30 00:00:00+00', NULL),
  ('cycling',     1.0,  '0A-v1.0', '2026-06-30 00:00:00+00', NULL),
  ('swimming',    0.6,  '0A-v1.0', '2026-06-30 00:00:00+00', NULL),
  ('paddling',    0.9,  '0A-v1.0', '2026-06-30 00:00:00+00', NULL),
  ('multi_sport', 0.95, '0A-v1.0', '2026-06-30 00:00:00+00', NULL),
  ('skimo',       0.9,  '0A-v1.0', '2026-06-30 00:00:00+00', NULL),
  ('default',     1.0,  '0A-v1.0', '2026-06-30 00:00:00+00', NULL)
ON CONFLICT (sport_profile, etl_version) DO NOTHING;


-- ─── 4. dietary_pattern_flags (#229) ─────────────────────────────────────────
-- Per-pattern dietary-concern flags. Seeds from _dietary_pattern_adjustments()
-- in layer2e/builder.py. sort_order determines flag order within a pattern.
-- suggested_supplement_id and race_day_format_adjustment may be NULL.

CREATE TABLE IF NOT EXISTS layer0.dietary_pattern_flags (
    id                          SERIAL PRIMARY KEY,
    pattern                     TEXT    NOT NULL,  -- e.g. 'Vegan', 'Low-FODMAP'
    concern                     TEXT    NOT NULL,  -- e.g. 'b12_deficiency_risk'
    severity                    TEXT    NOT NULL,  -- 'low','moderate','high'
    rationale                   TEXT    NOT NULL,
    suggested_supplement_id     TEXT,
    race_day_format_adjustment  TEXT,
    requires_medical_guidance   BOOLEAN NOT NULL DEFAULT FALSE,
    sort_order                  INT     NOT NULL DEFAULT 0,
    etl_version                 TEXT    NOT NULL,
    etl_run_at                  TIMESTAMPTZ NOT NULL,
    superseded_at               TIMESTAMPTZ,
    UNIQUE (pattern, concern, etl_version)
);

INSERT INTO layer0.dietary_pattern_flags
  (pattern, concern, severity, rationale,
   suggested_supplement_id, race_day_format_adjustment, requires_medical_guidance,
   sort_order, etl_version, etl_run_at, superseded_at)
VALUES
  ('Vegan', 'b12_deficiency_risk', 'moderate',
   'Vegan diet without B12 supplementation creates measurable deficiency risk within 6–18 months. Verify B12 in athlete''s supplement protocol.',
   'vitamin_b12', NULL, FALSE, 0,
   '0A-v1.0', '2026-06-30 00:00:00+00', NULL),

  ('Vegan', 'iron_status_risk', 'low',
   'Non-heme iron absorption is lower than heme; surveillance via periodic ferritin testing recommended for endurance athletes on plant-only diets.',
   'iron', NULL, TRUE, 1,
   '0A-v1.0', '2026-06-30 00:00:00+00', NULL),

  ('Vegan', 'epa_dha_conversion', 'low',
   'ALA→EPA/DHA conversion is inefficient; algae-derived EPA/DHA supplementation closes the gap.',
   'omega_3', NULL, FALSE, 2,
   '0A-v1.0', '2026-06-30 00:00:00+00', NULL),

  ('Low-FODMAP', 'race_fueling_format_constraint', 'moderate',
   'High-FODMAP gels (fructose-rich, polyol-containing) may trigger GI distress. Maltodextrin-dominant formats preferred for race-day fueling.',
   NULL, 'prefer_maltodextrin_dominant', FALSE, 0,
   '0A-v1.0', '2026-06-30 00:00:00+00', NULL)
ON CONFLICT (pattern, concern, etl_version) DO NOTHING;

COMMIT;
