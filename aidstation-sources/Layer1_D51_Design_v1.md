# Layer 1 — D-51 Design Wave v1

**Status:** 🟢 Design wave shipped 2026-05-19 — first pass of D-73 upstream implementation arc (Phase 1.1 per `Upstream_Implementation_Plan_v1.md` §4).

**Scope:** Full §A-§L field-by-field inventory of `Athlete_Onboarding_Data_Spec_v5.md` against on-disk `public.*` schema; per-field design decision (existing column / new column / new table); per-section migration plan. Output is implementation-ready storage design for Phase 1.2 (D-51 implementation) — the actual `_PG_MIGRATIONS` SQL appends land in that session, sequenced per §4 below.

**Architectural choice on the record (Andy 2026-05-19):** Table-heavy. Scalar fields → new columns on `athlete_profile` or 1:1 sub-table; multi-row data → new tables. No JSONB in this design. Rationale: §A.2 provenance tracking is column-driven (one row per scalar field in `athlete_profile_field_provenance`); §A.2.7 tolerance-based re-prefill needs per-field columns; long-term `Layer1Payload` typed promotion is cleaner against columnar storage.

**Predecessor:** D-73 upstream implementation arc plan shipped 2026-05-19 (`Upstream_Implementation_Plan_v1.md`).

---

## 1. Purpose & scope

D-51 is the long-standing blocker on Layer 1 builder implementation. Surfaced 2026-05-13 (`Athlete_Data_Integration_Spec_v5.md` §7.6 "Gap summary — onboarding fields with no app-table home"); promoted to Phase 1.1 hard blocker by D-73 (`Upstream_Implementation_Plan_v1.md` §4). The integration spec catalogues which v5 §A-§L fields have no `public.*` storage but does not design the storage shape; D-51 closes that gap.

**This document is the design wave** — it specifies the on-disk schema decisions. It does NOT ship migrations. Phase 1.2 (D-51 implementation, projected 2-3 sessions per plan §4) ships the actual `_PG_MIGRATIONS` SQL appends against this design.

**Out of scope** for the design wave:
- D-52 (catalog migration) sequencing — deferred to Phase 2 kickoff /plan-mode gate.
- D-56 (`cardio_log.is_race` + `start_time`) — covered as Phase 1.4 carry-forward; not folded into D-51 since the change is on an existing table, not new storage.
- Layer 1 builder code — Phase 2/3/4 work per the arc.
- Layer 1 prompt body — open question per plan §6 item 5; if §C free-text parsing needs LLM judgment, Layer 1 expands to an LLM-driven node; deferred until first §C real-athlete parsing case justifies it.
- Layer 1 typed payload (`Layer1Payload` pydantic model in `layer4/context.py`) — Phase 1.3 carry-forward per plan §4.

---

## 2. Current schema state (Rule #9 verification)

Verified against `init_db.py` at session start. Tables that already exist + cover their v5 spec section:

| Section | Existing table(s) | Coverage |
|---|---|---|
| §A.1 (most fields) | `athlete_profile` | ✅ Identity scalars covered: `date_of_birth`, `sex`, `height_cm`, `primary_sport`, `body_weight_kg` |
| §A.2 provenance | `athlete_profile_field_provenance` | ✅ D-58 shipped; `(user_id, field_name, source, source_synced_at, manual_override_at)` shape exists |
| §B.1 Current Injuries + Injury History | `injury_log` | ✅ Multi-row table with `body_part`, `severity`, `status`, `start_date`, `resolved_date`, `modifications_needed` |
| §F partial | `athlete_profile`, `body_metrics` | ✅ `hrmax_bpm`, `lactate_threshold_hr_bpm`, `vo2max`, `cycling_ftp_w` on athlete_profile; observation-grade VO2max + RHR on body_metrics |
| §G partial | `athlete_profile` | ✅ `long_session_available`, `long_session_days`, `long_session_max_hr`, `doubles_feasible`, `preferred_rest_days` exist as scalars (v4 shape — to be augmented by new daily-windows table per §3.7 below) |
| §H Target Events | `race_events` + `race_route_locales` + `race_route_locale_equipment` | ✅ D-66 shipped 2026-05-18; full §H.2 + §H.4 storage |
| §I Sleep | `wellness_self_report` | ✅ `sleep_hours` column exists for prefill source |
| §J Locales | `locale_profiles` + `gym_profiles` + `locale_equipment_overrides` + `locale_toggle_overrides` | ✅ D-59 + D-60 shipped; Mapbox anchoring + shared-profile model live |
| Disclosures + nudges (cross-section) | `account_nudges` | ✅ D-58 shipped; nudge_type-keyed UPSERT pattern in place |

**Result:** Substantial infrastructure already exists — D-58/D-59/D-60/D-61/D-66 closed the largest pieces. D-51 design wave scope is now narrower than originally framed in `Athlete_Data_Integration_Spec_v5.md` §7.6 (which catalogued the full gap before D-66 shipped).

---

## 3. Section-by-section design

**Convention:** every new column on `athlete_profile` adds a corresponding `KNOWN_PROFILE_FIELDS` registry entry (per v5 Open Item #17) for `athlete_profile_field_provenance` keying. New tables specify their per-row provenance shape inline (most multi-row tables don't use `athlete_profile_field_provenance` since they're not "fields" — they're records; per-record `source` column on the table itself is the canonical pattern).

### 3.1 §A — Athlete Identity + Disclosures (mostly existing)

**Existing fields stay verbatim** on `athlete_profile`. One gap to close: **A.1 disclosure acknowledgment storage**.

**New table: `disclosure_acknowledgments`**

| Column | Type | Notes |
|---|---|---|
| `id` | BIGSERIAL PK | |
| `user_id` | INTEGER NOT NULL REFERENCES users(id) | |
| `disclosure_type` | TEXT NOT NULL | Closed enum per v5 §A.1 (`account_creation_ack`, `connected_service_consent`, `oauth_scope_<provider>`, `sex_collection_inline`, `health_data_inline`, `hrt_inline`, `mapbox_geocoding_consent`, `gym_profile_sharing_consent`, `linked_partner_data_sharing`, `race_rules_paste_ack`). Application-code validates against `KNOWN_DISCLOSURE_TYPES` constant. |
| `version_seen` | TEXT NOT NULL | Per v5 Account Config 3 — disclosure copy version string; enables re-prompt on copy changes. |
| `acknowledged_at` | TIMESTAMP NOT NULL DEFAULT NOW() | |
| `delivery_method` | TEXT NOT NULL DEFAULT 'in_app' | Closed enum: `in_app` / `email`. |
| `subject_id` | BIGINT NULL | Optional FK target for disclosure-with-subject (e.g., `race_rules_paste_ack` → race_events.id; OAuth scope ack → provider_auth.id). Application-code interprets per `disclosure_type`. Not a hard FK constraint to keep the polymorphic shape simple. |

**Indexes:** `(user_id, disclosure_type, acknowledged_at DESC)` for the "what's the most recent ack of type X" query; `(user_id, version_seen)` for re-prompt-on-copy-change scans.

**Rationale for not using JSONB on `users`:** acknowledgment events are append-only (audit trail per v5 §A.1); JSONB array would require copy-on-write semantics + lose per-event timestamps + complicate re-prompt detection.

### 3.2 §B — Health Status

Three gaps:

**(a) `health_conditions_log` — new multi-row table parallel to `injury_log`.**

| Column | Type | Notes |
|---|---|---|
| `id` | BIGSERIAL PK | |
| `user_id` | INTEGER NOT NULL REFERENCES users(id) | |
| `system_category` | TEXT NOT NULL | Closed enum per v5 §B.4.1: `cardiac` / `respiratory` / `metabolic` / `neurological` / `gi_immune` / `musculoskeletal` / `endocrine` / `other`. |
| `condition_name` | TEXT NOT NULL | Free-text per v5 (e.g., "Type 1 diabetes", "Exercise-induced asthma"). |
| `severity` | INTEGER NULL | 1-5 per v5 §B.4 substructure. |
| `notes` | TEXT NULL | Athlete-entered free-text. |
| `status` | TEXT NOT NULL DEFAULT 'Active' | Closed enum: `Active` / `Resolved` / `Inactive` (parallel to `injury_log.status`). |
| `start_date` | DATE NULL | Onset; nullable since many chronic conditions have no precise onset. |
| `resolved_date` | DATE NULL | |
| `created_at` | TIMESTAMP DEFAULT NOW() | |
| `updated_at` | TIMESTAMP DEFAULT NOW() | |

**Indexes:** `(user_id, status)` for the active-conditions query (Layer 3A primary consumer); `(user_id, created_at DESC)` for history listing.

**(b) `medications_log` — new multi-row table.**

| Column | Type | Notes |
|---|---|---|
| `id` | BIGSERIAL PK | |
| `user_id` | INTEGER NOT NULL REFERENCES users(id) | |
| `medication_class` | TEXT NOT NULL | Closed enum (training-relevant only per v5 §B): `beta_blocker` / `diuretic` / `nsaid_chronic` / `hrt` / `ssri` / `stimulant_adhd` / `corticosteroid_chronic` / `anticoagulant` / `other`. Application-code validates against `KNOWN_MEDICATION_CLASSES` constant. |
| `medication_name` | TEXT NULL | Optional free-text (e.g., "metoprolol", "Adderall XR"). |
| `started_at` | DATE NULL | |
| `stopped_at` | DATE NULL | Nullable; current medication when NULL. |
| `notes` | TEXT NULL | |
| `created_at` | TIMESTAMP DEFAULT NOW() | |

**Indexes:** `(user_id, medication_class) WHERE stopped_at IS NULL` for the active-medications query.

**(c) `food_allergies` — new multi-row table.**

| Column | Type | Notes |
|---|---|---|
| `id` | BIGSERIAL PK | |
| `user_id` | INTEGER NOT NULL REFERENCES users(id) | |
| `allergen_category` | TEXT NOT NULL | Closed enum: `tree_nut` / `peanut` / `dairy` / `gluten` / `egg` / `shellfish` / `fish` / `soy` / `nightshade` / `fodmap` / `caffeine_sensitivity` / `other`. |
| `severity` | TEXT NOT NULL DEFAULT 'intolerance' | Closed enum: `intolerance` / `allergy` / `anaphylaxis`. Anaphylaxis-tier triggers the §B.4.2 auto-population rule for `system_category='gi_immune'`. |
| `notes` | TEXT NULL | Free-text. |
| `created_at` | TIMESTAMP DEFAULT NOW() | |

**Indexes:** `(user_id)` for the allergen-list query.

**(d) Resting Heart Rate** — already covered by `body_metrics.resting_hr` (existing). No change.

### 3.3 §C — Training History & Fitness Baseline

Six scalar fields → new columns on `athlete_profile`. Three multi-row data → new tables.

**Scalar additions to `athlete_profile`:**

| Column | Type | Default | Notes |
|---|---|---|---|
| `years_structured_training` | INTEGER NULL | NULL | §C row 1. Tier 1; not prefill-eligible. |
| `peak_weekly_volume_hrs` | REAL NULL | NULL | §C row 5. Tier 2; self-report only. |
| `peak_weekly_volume_year` | INTEGER NULL | NULL | Companion to row 5. |
| `longest_event_completed` | TEXT NULL | NULL | §C row 6. Tier 1; free-text (event + distance + time + year per v5). |
| `training_consistency_disrupted_weeks` | SMALLINT NULL | NULL | §C row 8 (last 12 mo); 0-52. |
| `training_consistency_cause` | TEXT NULL | NULL | Companion to row 8; free-text. |
| `previous_coaching` | TEXT NULL | NULL | §C row 10. Closed enum: `self` / `online_plan` / `coach` / `none`. |

**New multi-row tables:**

**`athlete_secondary_sports`** — §C row 2.

| Column | Type | Notes |
|---|---|---|
| `id` | BIGSERIAL PK | |
| `user_id` | INTEGER NOT NULL REFERENCES users(id) | |
| `sport_slug` | TEXT NOT NULL | FK-style to the 18-sport `Sports_Framework_v10.xlsx` (composite uniqueness `(user_id, sport_slug)`). |
| `experience_tier` | TEXT NOT NULL | Closed enum: `under_1yr` / `1_to_3yr` / `3plus_yr` per v5. |
| `created_at` | TIMESTAMP DEFAULT NOW() | |

**`athlete_discipline_weighting`** — §C row 3.

| Column | Type | Notes |
|---|---|---|
| `id` | BIGSERIAL PK | |
| `user_id` | INTEGER NOT NULL REFERENCES users(id) | |
| `discipline_slug` | TEXT NOT NULL | Composite UNIQUE `(user_id, discipline_slug)`. |
| `weight_pct` | SMALLINT NOT NULL | 0-100; per-user sum across rows = 100 (application-code invariant; not DB-enforced since intermediate states during edits are valid). |
| `updated_at` | TIMESTAMP DEFAULT NOW() | |

**`recent_race_results`** — §C row 7.

| Column | Type | Notes |
|---|---|---|
| `id` | BIGSERIAL PK | |
| `user_id` | INTEGER NOT NULL REFERENCES users(id) | |
| `event_name` | TEXT NOT NULL | |
| `event_date` | DATE NOT NULL | |
| `distance_km` | REAL NULL | Pre-D-56 storage; `cardio_log.is_race=TRUE` joinpoint is the long-term source per D-56. |
| `finish_time_seconds` | INTEGER NULL | |
| `result_notes` | TEXT NULL | Free-text (placement, conditions, etc.). |
| `source` | TEXT NOT NULL DEFAULT 'self_report' | Closed enum: `self_report` / `provider_<X>` per A.2 provenance shape (table-level provenance for record-shaped data). |
| `created_at` | TIMESTAMP DEFAULT NOW() | |

**Indexes:** `(user_id, event_date DESC)` for the recent-races query.

**`pack_load_history`** — §C row 9 (§C.1 substructure).

| Column | Type | Notes |
|---|---|---|
| `id` | BIGSERIAL PK | |
| `user_id` | INTEGER NOT NULL REFERENCES users(id) | |
| `pack_weight_kg` | REAL NOT NULL | |
| `session_count_4wk` | INTEGER NULL | Sessions at this pack weight in trailing 4 weeks. |
| `longest_session_hrs` | REAL NULL | |
| `terrain_type` | TEXT NULL | Free-text (e.g., "moorland", "alpine trail"). |
| `notes` | TEXT NULL | |
| `created_at` | TIMESTAMP DEFAULT NOW() | |

**Current Weekly Training Volume** (row 4) — derived field per `Athlete_Data_Integration_Spec_v5.md` §7.1: `SUM(cardio_log.duration_min) + SUM(training_sessions.duration)` over rolling 7d. No storage column needed; Layer 1 builder computes at read time. Provenance shape: derived (no `source` field).

### 3.4 §D — Discipline-Specific Baselines

Per v5 §D: "every field is nullable; null means 'not asked.'" Most fields are scalar per-discipline. Mixed-source: some prefill-eligible (Easy Run Pace, Vertical Gain Tolerance), most self-report.

**Architect-pick: per-discipline 1:1 tables** keyed on `user_id`, with `discipline_slug` as a row-shape identifier (NOT one row per discipline; one table per discipline, sparse rows). Rationale: §D fields are discipline-specific schemas, not parameterized — running has Easy Run Pace + Vertical Gain Tolerance + Downhill Adaptation + Night Running; cycling has Bike Types Available + MTB Skill + Aero Endurance; merging into a generic `discipline_baselines(user_id, discipline, field_name, value)` JSON-ish shape loses type fidelity.

**Seven new tables (1:1 to athlete_profile when populated):**

- `discipline_baseline_running` — `easy_run_pace_sec_per_km` (INTEGER NULL), `vertical_gain_weekly_m` (REAL NULL), `vertical_gain_peak_session_m` (REAL NULL), `trail_experience_terrain` (TEXT NULL — closed enum `moderate` / `technical` / `mountain` / `moorland` / multi-select), `downhill_adaptation` (BOOLEAN NULL), `downhill_sessions_3mo` (INTEGER NULL), `night_running` (BOOLEAN NULL), `gut_training_g_per_hr_cho` (SMALLINT NULL), `gut_training_issues` (TEXT NULL).
- `discipline_baseline_cycling` — `bike_types_available` (TEXT NULL — comma-separated closed enum subset), `mtb_skill` (TEXT NULL — `beginner`/`intermediate`/`advanced`), `longest_ride_distance_km` (REAL NULL), `longest_ride_hrs` (REAL NULL), `saddle_endurance_hrs` (REAL NULL), `aero_endurance_min` (INTEGER NULL).
- `discipline_baseline_swimming` — `pool_100m_pace_sec` (INTEGER NULL), `ow_experience` (TEXT NULL — `none`/`limited`/`experienced`), `wetsuit_experience` (BOOLEAN NULL), `cold_water_experience` (BOOLEAN NULL), `ow_feeding_experience` (BOOLEAN NULL), `weekly_swim_volume_km` (REAL NULL).
- `discipline_baseline_paddling` — `longest_paddle_km` (REAL NULL), `longest_paddle_hrs` (REAL NULL), `paddle_craft_types` (TEXT NULL — comma-separated: `kayak` / `canoe` / `packraft` / `surfski`).
- `discipline_baseline_skiing` — `ski_disciplines` (TEXT NULL — comma-separated: `classic_xc` / `skate_xc` / `skimo`), `weekly_ski_volume_hrs` (REAL NULL).
- `discipline_baseline_navigation` — `experience_level` (TEXT NULL — `none`/`map_only`/`map_compass`/`expert`), `night_nav_experience` (BOOLEAN NULL).
- `discipline_baseline_technical` — `rock_climbing_outdoor_grade` (TEXT NULL — Yosemite Decimal / French Sport / UIAA per Layer 4 Step 4a precedent), `rock_climbing_indoor_grade` (TEXT NULL), `abseiling_experience` (BOOLEAN NULL).

**Note:** §D.7 dropped shooting + fencing per v5 (out of scope). v5 spec calls out "every field is nullable; null means 'not asked.'" — 1:1 sub-table pattern preserves this; rows exist for the disciplines the athlete trains and nullable columns for the fields not yet entered.

### 3.5 §E — Strength, Core & Balance Benchmarks

**New table: `strength_benchmarks`** — 1:1 with `athlete_profile` when populated.

| Column | Type | Notes |
|---|---|---|
| `user_id` | INTEGER PRIMARY KEY REFERENCES users(id) | 1:1 shape. |
| `front_plank_sec` | INTEGER NULL | §E v5 carry-from-v4. |
| `dead_bug_max_reps` | INTEGER NULL | |
| `side_plank_left_sec` | INTEGER NULL | |
| `side_plank_right_sec` | INTEGER NULL | |
| `pushup_max_reps` | INTEGER NULL | |
| `bodyweight_squat_max_reps` | INTEGER NULL | |
| `single_leg_squat_left_max_reps` | INTEGER NULL | |
| `single_leg_squat_right_max_reps` | INTEGER NULL | |
| `pullup_max_reps` | INTEGER NULL | |
| `dead_hang_sec` | INTEGER NULL | |
| `grip_strength_left_kg` | REAL NULL | Right + left split per v5 (asymmetry signal). |
| `grip_strength_right_kg` | REAL NULL | |
| `last_tested_at` | DATE NULL | Re-test cadence per §F precedent. |
| `updated_at` | TIMESTAMP DEFAULT NOW() | |

**Note on Andy's wrist constraint:** pushup_max_reps is captured as "fist-position only" via a follow-on `pushup_position` TEXT column if the modality framework needs it later (D-69 framework currently doesn't require this granularity at the §E level). Deferred.

### 3.6 §F — Performance Testing Baselines (mostly existing)

Most §F fields already on `athlete_profile`. Two missing:

**Scalar additions to `athlete_profile`:**

| Column | Type | Notes |
|---|---|---|
| `running_threshold_pace_sec_per_km` | INTEGER NULL | §F row 5. Self-report (TT result) per `Athlete_Data_Integration_Spec_v5.md` §7.4. |
| `running_threshold_test_date` | DATE NULL | Companion. |
| `css_swim_sec_per_100m` | INTEGER NULL | §F row 6 (Critical Swim Speed). |
| `css_test_date` | DATE NULL | Companion. |
| `cycling_ftp_test_date` | DATE NULL | Companion for existing `cycling_ftp_w`. |
| `hrmax_source` | TEXT NULL | Closed enum: `measured` / `estimated_tanaka` / `provider_<X>`. v5 §F row 1 captures source per A.2 provenance. |
| `lt_method` | TEXT NULL | Companion for existing `lactate_threshold_hr_bpm`. Closed enum: `field_test_30min` / `lab` / `provider_<X>`. |
| `vo2max_source` | TEXT NULL | Closed enum: `cooper_test` / `lab` / `provider_<X>`. |

### 3.7 §G — Schedule & Availability (full rewrite per `Onboarding_D61_Design_v1.md`)

**New table: `daily_availability_windows`** — per-day-of-week window definition; replaces v4's `athlete_profile.training_window` scalar.

| Column | Type | Notes |
|---|---|---|
| `id` | BIGSERIAL PK | |
| `user_id` | INTEGER NOT NULL REFERENCES users(id) | |
| `day_of_week` | SMALLINT NOT NULL | 0-6 (Sunday=0 per v5 §G.1; ISO Monday=0 if Andy prefers — decision deferred to migration session). UNIQUE `(user_id, day_of_week)`. |
| `enabled` | BOOLEAN NOT NULL DEFAULT FALSE | §G.1. |
| `window_start_minute` | SMALLINT NULL | Minute-of-day 0-1440; NULL when not enabled. |
| `window_duration_min` | SMALLINT NULL | 30-360 per v5; NULL when not enabled. |
| `second_window_start_minute` | SMALLINT NULL | Gated on `doubles_feasible != 'no'`. |
| `second_window_duration_min` | SMALLINT NULL | Companion. |
| `updated_at` | TIMESTAMP DEFAULT NOW() | |

**CHECK constraints:** `(enabled = FALSE) OR (window_start_minute IS NOT NULL AND window_duration_min IS NOT NULL)`; `(second_window_start_minute IS NULL) = (second_window_duration_min IS NULL)` (paired non-null).

**Existing `athlete_profile` columns** (`long_session_available`, `long_session_days`, `long_session_max_hr`, `doubles_feasible`, `preferred_rest_days`, `training_window`) — keep `long_session_*`, `doubles_feasible`, `preferred_rest_days` (still load-bearing per §G.1); deprecate `training_window` (replaced by per-day windows; drop in Phase 1.2 with same idempotent-DROP-COLUMN-IF-EXISTS pattern from D-66 Scope B).

**§G.2 derived fields** (Available Training Hours per Week, Training Days Available, Typical Session Duration) — computed at read time by Layer 1 builder; no storage.

**§G.4 session-to-locale assignment** — runtime resolver, not stored state. No schema needed.

### 3.8 §H — Target Events (✅ existing per D-66)

**Already shipped:** `race_events` + `race_route_locales` + `race_route_locale_equipment` (D-66 DB foundation 2026-05-18). No new tables. §H.1 event-mode gate is derived (`SELECT EXISTS … WHERE is_target_event=TRUE`); §H.3 no-event mode plan duration captures in `athlete_profile.plan_duration_weeks_no_event` (new column).

**One scalar addition to `athlete_profile`:**

| Column | Type | Notes |
|---|---|---|
| `plan_duration_weeks_no_event` | SMALLINT NULL | §H.3 enum (8/12/16/20/24); NULL when athlete is in event mode. |
| `non_event_goal_type` | TEXT NULL | Closed enum per v5 §H.3: `endurance` / `general_fitness` / `strength` / `mixed`. Default `general_fitness`. |

### 3.9 §I — Lifestyle & Recovery

Sleep is covered by `wellness_self_report.sleep_hours` (existing). Five gap fields → new columns on `athlete_profile`.

**Scalar additions to `athlete_profile`:**

| Column | Type | Notes |
|---|---|---|
| `work_stress_level` | TEXT NULL | Closed enum: `low` / `moderate` / `high` / `variable`. |
| `dietary_pattern` | TEXT NULL | Comma-separated closed enum: `omnivore` / `vegetarian` / `vegan` / `pescatarian` / `paleo` / `keto` / `gluten_free` / `low_fodmap` / `other`. Multi-select per v5. |
| `supplement_protocol_notes` | TEXT NULL | Free-text per v5. |
| `caffeine_tolerance` | TEXT NULL | Closed enum: `none` / `low` / `moderate` / `high`. |
| `caffeine_daily_mg_estimate` | SMALLINT NULL | Optional companion. |
| `caffeine_race_day_strategy` | TEXT NULL | §I.1.1 sub-question; closed enum: `caffeine_loading` / `taper` / `maintain` / `avoid`; NULL when `caffeine_tolerance='none'`. |
| `altitude_acclimatization_history` | BOOLEAN NULL | §I.1 row 6 Y/N. |
| `altitude_max_exposure_m` | INTEGER NULL | Companion. |
| `altitude_exposure_count` | SMALLINT NULL | Companion (approximate). |
| `fueling_format_preference` | TEXT NULL | §I.2 (carry-from-v4). Comma-separated closed enum. |
| `gi_triggers_known` | TEXT NULL | §I.2 (free-text). |
| `salt_electrolyte_tolerance` | TEXT NULL | §I.2; closed enum: `low` / `moderate` / `high`. |
| `sleep_deprivation_max_hrs_continuous_awake` | SMALLINT NULL | §I.3 (conditional on §H race duration > 20hr); NULL otherwise. |
| `sleep_deprivation_strategy_notes` | TEXT NULL | §I.3 free-text. |

### 3.10 §J — Locales (✅ existing per D-59/D-60)

**Already shipped:** `locale_profiles` + `gym_profiles` + `locale_equipment_overrides` + `locale_toggle_overrides`. Closed Mapbox-anchoring + shared-profile + per-athlete-override model per D-59 + D-60. No new tables.

**§J.4 Terrain access** — currently `locale_profiles.notes` free-text per Andy's v4 carryover. If Layer 1 builder needs structured terrain types per locale, a `locale_terrain_access(user_id, locale, terrain_type, seasonality_months_bitmask)` table can land later; deferred since Layer 1 doesn't trip over it in v1.

### 3.11 §K — Locale Schedule

Currently approximated by `plan_travel` table (existing). Per v5 §K, three sub-types: self-overlays + joint-training overlays + recurrence templates. **Architect-pick: keep `plan_travel` as the v1 storage; defer richer §K modeling.** Rationale: v1 (single test athlete = Andy) doesn't exercise the K.2 joint-training or K.3 recurrence shape; expanding the table now is speculative. Phase 4 Layer 3B builder reads `plan_travel` as-is; v2 amends when first multi-athlete-team-training case lands.

**No new tables in this design wave for §K.** Carry-forward as Layer 1 builder open item.

### 3.12 §L — Athlete Network

**New table: `athlete_network_links`** — multi-row per athlete; covers §L Athlete Link entity.

| Column | Type | Notes |
|---|---|---|
| `id` | BIGSERIAL PK | |
| `user_id` | INTEGER NOT NULL REFERENCES users(id) | The athlete who owns this link. |
| `partner_name` | TEXT NOT NULL | Display label; required even if `linked_account_user_id` is set. |
| `linked_account_user_id` | INTEGER NULL REFERENCES users(id) | NULL = external partner (not an AIDSTATION user); non-NULL = consenting peer (triggers §A.1 linked-partner data-sharing disclosure). |
| `relationship_types` | TEXT NOT NULL | Comma-separated closed enum: `training_partner` / `race_teammate` / `coach` / `family` / `pacer` / `crew`. |
| `partner_specific_rules` | TEXT NULL | Free-text per v5. |
| `race_event_id` | BIGINT NULL REFERENCES race_events(id) ON DELETE SET NULL | §L Race Teammate conditional field. |
| `discipline_focus_on_team` | TEXT NULL | Companion when `relationship_types` includes `race_teammate`. |
| `created_at` | TIMESTAMP DEFAULT NOW() | |
| `updated_at` | TIMESTAMP DEFAULT NOW() | |

**Indexes:** `(user_id)`; `(linked_account_user_id) WHERE linked_account_user_id IS NOT NULL` for the reverse-lookup (who's linked to me).

**Linked-partner consent storage** — per §L the consent scope (None / Activity summaries / Full plan access) lives in Account Config 4 (Privacy and Linked-Partner Sharing). New table `linked_partner_consents(user_id, link_id, consent_scope, granted_at, revoked_at)`. Deferred to Phase 1.2 implementation session — v1 has no real multi-athlete-team-training exercise of this surface.

---

## 4. Migration ordering (Phase 1.2 session sequencing)

Phase 1.2 (D-51 implementation per `Upstream_Implementation_Plan_v1.md` §4) is projected as 2-3 sessions, ~15-20 files. This design slices into 3 implementation sessions, each ceiling-clean (≤5 files):

**Session 1.2A — Athlete profile column extensions + bundled-scalar sub-tables.**
- Append to `_PG_MIGRATIONS`: ~15 `ALTER TABLE athlete_profile ADD COLUMN IF NOT EXISTS …` per §3.3 + §3.6 + §3.8 + §3.9.
- New `strength_benchmarks` table per §3.5.
- New `daily_availability_windows` table per §3.7.
- Drop `athlete_profile.training_window` per §3.7 (idempotent `DROP COLUMN IF EXISTS` matching D-66 Scope B precedent).
- Update `KNOWN_PROFILE_FIELDS` registry in application code.
- ~5 files: `init_db.py` + `KNOWN_PROFILE_FIELDS` constant + 2 bookkeeping + handoff.

**Session 1.2B — Multi-row tables for §B + §C + §L.**
- New `health_conditions_log`, `medications_log`, `food_allergies` per §3.2.
- New `athlete_secondary_sports`, `athlete_discipline_weighting`, `recent_race_results`, `pack_load_history` per §3.3.
- New `athlete_network_links` per §3.12.
- New `disclosure_acknowledgments` per §3.1.
- ~4-5 files.

**Session 1.2C — Per-discipline §D tables.**
- New `discipline_baseline_running`, `_cycling`, `_swimming`, `_paddling`, `_skiing`, `_navigation`, `_technical` per §3.4.
- ~4-5 files.

**Triggers anticipated per session:** #5 (cross-layer contract — all 3 sessions ship schema migrations); #8 fires only if implementation surfaces a design ambiguity not caught here.

---

## 5. Cross-cutting concerns

### 5.1 Provenance shape consistency

Every new scalar column on `athlete_profile` registers in `KNOWN_PROFILE_FIELDS` (per v5 Open Item #17). Layer 1 builder reads `athlete_profile_field_provenance` for per-field source resolution per §A.2.2. Multi-row tables carry their own per-row `source` column (where prefill applies; `recent_race_results.source` is the canonical example) — provenance is per-record, not per-field, for record-shaped data.

### 5.2 Tolerance config (v5 Open Item #16)

Per-field tolerance values (body weight ±0.5 kg, RHR ±2 bpm, etc.) ship as an application-code constant (`FIELD_TOLERANCES` dict in `athlete.py` or similar) — not stored in DB. Phase 1.2 sessions populate the dict alongside the column additions.

### 5.3 §A.2.5 re-prefill prompt deferral

The §A.2.5 re-onboarding prompt for newly-connected providers reads from `KNOWN_PROFILE_FIELDS` + the provider's prefill-eligible field set per `Athlete_Data_Integration_Spec_v5.md` §7. Lives in route layer (`routes/onboarding.py` or `routes/account.py`), not schema. No D-51 design impact.

### 5.4 Layer 1 typed payload (Phase 1.3 carry-forward)

`Layer1Payload` pydantic model in `layer4/context.py` mirrors the columnar + table-relation shape from this design. ~70-90 fields projected (15 scalars on athlete_profile + bundled sub-table reads + multi-row table summaries). Layer 4 entry-point signatures keep `dict[str, Any]` for Layer 1 in v1 per `Upstream_Implementation_Plan_v1.md` architect-pick (d) — typed-payload promotion deferred to v2 to avoid ~10-15 test fixture rewrites.

### 5.5 Backwards-compatibility surface

All new columns are nullable; existing rows survive without backfill. No data loss. v1 reads (Layer 1 builder Phase 2.x onwards) tolerate NULL per `Athlete_Onboarding_Data_Spec_v5.md` §D ("every field is nullable; null means 'not asked.'"). No defense-in-depth migration gate needed (D-66 Scope B precedent — `ALTER TABLE … DROP COLUMN IF EXISTS` is idempotent + the column is unused).

---

## 6. Open questions / deferred

1. **Day-of-week numbering convention** (§3.7) — Sunday=0 per v5 §G.1 or ISO Monday=0? Defer to Session 1.2A /plan-mode gate.
2. **Sleep deprivation conditional gating** (§3.9 `sleep_deprivation_*` fields) — store regardless of §H race duration, or strict NULL-when-not-asked? Lean store-regardless (simpler); athlete can edit any time. Defer to Session 1.2A.
3. **§K Locale Schedule richer modeling** (§3.11) — out of scope for D-51 design wave; carry-forward as Layer 1 builder open item.
4. **§J.4 terrain access structured storage** (§3.10) — out of scope; carry-forward.
5. **`linked_partner_consents` table** (§3.12) — deferred to Session 1.2B unless v1 multi-athlete case lands sooner.
6. **Layer 1 prompt body necessity** (§C free-text parsing for "Longest Event Completed" etc.) — open question per `Upstream_Implementation_Plan_v1.md` plan §6 item 5. Defer to Layer 1 builder session (Phase 2.x).
7. **D-56 sequencing** — `cardio_log.is_race` + `start_time` migration lands in Phase 1.4 per plan §4. Can fold into Session 1.2A if Andy wants the migration batch to be larger; lean keep separate (small migration, distinct scope).

---

## 7. Gut check

### Risks

- **Column count on `athlete_profile`** — design adds ~25 new columns to a table that currently has 19. Post-D-51, `athlete_profile` carries ~44 columns. Still well under PG's 1600-column limit and tractable for the `KNOWN_PROFILE_FIELDS` registry, but it's the highest-fanout schema mutation in the v5 implementation arc so far. Mitigation: bundled-scalar sub-tables (`strength_benchmarks`, `daily_availability_windows`) absorb the 9 + 9 fields that don't belong on the master record.
- **§D per-discipline tables sparsity** — 7 tables for 7 disciplines, most athletes use 2-3 disciplines. Many empty tables in practice. Acceptable; the alternative (single `discipline_baselines` with `discipline_slug` + JSONB fields) loses type fidelity per §3.4 architect-pick rationale.
- **`linked_account_user_id` self-reference** — `athlete_network_links.linked_account_user_id REFERENCES users(id)` is correct but Andy's v1 has no second user; the consent + sharing surface (§A.1 linked-partner-data-sharing + Account Config 4) is exercised only at v2 when team-training activates. Defensive but unused storage.
- **§A.2 provenance scaling** — `athlete_profile_field_provenance` gets ~40 rows per active athlete post-D-51 (one row per `KNOWN_PROFILE_FIELDS` entry). Tractable; index `apfp_user_idx` handles single-user reads.

### Best argument against

The design is implementation-ready and per-section consistent, but it bakes in 1:1 sub-tables (`strength_benchmarks`, `daily_availability_windows`) plus 7 per-discipline tables. A leaner pass could use JSONB on `athlete_profile` for §E + §I + §D fields and save ~10 tables of schema surface. Counter: per-field provenance + per-field tolerances + Layer 2/3 query patterns + Layer 1 typed payload all push toward columns; JSONB-keyed provenance is a maintenance burden (path-typed keys, no DB-level type enforcement). The architect-pick lands long-term wins for short-term verbosity.

### What might be missing

- **No explicit `food_allergies` Layer 4 consumer hookup** — §I.2 nutrition planning consumes the allergens but no Layer 4 validator rule references them yet. Surface when Layer 5 (nutrition outputs) specs.
- **No Race-Day Caffeine separate row** — §I.1.1 race-day caffeine strategy is one column (`caffeine_race_day_strategy`); deferred any richer multi-event-strategy modeling.
- **No `Sports_Framework_v10.xlsx` reference loaded into PG as a closed enum table** — `sport_slug` + `discipline_slug` columns assume application-code validates against the spreadsheet. Layer 0 reference data already drives this; reconciliation lives in the catalog migration track (D-52) not D-51.
- **No backfill SQL** — D-51 columns are all-NULL on existing rows. Andy's `athlete_profile` row stays consistent; v5 onboarding implementation track populates as athletes touch the new surfaces. No defense-in-depth gate needed.
- **No partial-update invalidation rule additions** — §M.1 already enumerates "Athlete updates X" triggers per field; D-51 adds storage but no new invalidation rules (the `M.1` triggers re-validate against the new columns automatically when the route layer wires them up). Phase 2/3/4 builder sessions wire as needed.

---

## 8. Next forward move

D-73 Phase 1.2 — D-51 implementation Session 1.2A. Suggested session prompt:

> Open D-73 Phase 1.2 Session 1.2A per `Layer1_D51_Design_v1.md` §4. Athlete profile column extensions (~15 new columns per §3.3 + §3.6 + §3.8 + §3.9) + bundled-scalar sub-tables (`strength_benchmarks` §3.5, `daily_availability_windows` §3.7) + drop `athlete_profile.training_window`. ~5 files; under ceiling. Trigger #5 expected to fire (schema migration).

**Alternative pivots if Andy defers Phase 1.2:**

- Layer 4 Step 4f Pattern A orchestration (orthogonal; closes Layer 4 §14.3.4 Step 4 sub-arc; ~6-8 files).
- Layer 4 Step 7 env-gated smoke test scaffolding (needs ANTHROPIC_API_KEY path; ~3-4 files).
- Layer 3B caller-side rewire (cleanest D-66 follow-on; orchestrator currently doesn't exist; awaits Phase 5).

D-73 arc remains 🟡 Deferred (Phase 1.1 closes here; Phase 1.2 opens with Andy's next scope pick).

---

*End of `Layer1_D51_Design_v1.md`.*
