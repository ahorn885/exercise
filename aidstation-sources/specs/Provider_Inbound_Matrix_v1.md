# Provider Inbound Mapping Matrix (#681 Wave 2) — v1

**Status:** DRAFT — awaiting Andy ratification of the §1 discipline-target decision + the §6 candidate new canonical entries (Trigger #2/#5). **Spec/reference only — no code ships from this doc.**

**Type:** Reference (seed data for the future `provider_value_map`). This doc is the **full-roster extension of `Provider_Data_Translation_Layer_Spec` §6** (which seeded only Garmin strength+cardio and Polar/COROS wellness as Wave 1). Every mapping row here is a future `provider_value_map(provider, data_type, direction='in', source_value, canonical_kind, canonical_value, match_kind, confidence, no_canonical_match)` seed row (parent §4.2).

**Parent:** `specs/Provider_Data_Translation_Layer_Spec` (RATIFIED v1) — owns the canonical model (§2: metric keys, SI units, disciplines, HR zones), the 3-bucket inbound model (§1.1), the storage schema (§4), and the authoring workflow (§7). This doc does **not** redefine any of that; it populates the matrix against it.

**This batch (Batch 1):** **Strava, Oura, WHOOP** — the three highest-value non-Garmin consumer providers. They span both canonical targets (Strava → discipline crosswalk + activity metrics; Oura/WHOOP → the §2.3 metric registry + §2.4 HR zones) and exercise all three buckets (Strava's `Pickleball` → bucket-3; WHOOP `recovery_score` / Oura readiness → bucket-2). Remaining providers (Wahoo, RWGPS, TrainingPeaks, Zwift, MyFitnessPal, Apple/Samsung/Google Health) are subsequent batches — §7.

**All provider field names, units, and enum values below are sourced from each provider's official developer docs (URLs in each provider's "Sources" line), fetched 2026-06-17. Anything not confirmable against an official doc is flagged inline.**

---

## 0. How to read a mapping row

Each row records: the **provider source value** → the **canonical target** (one of parent §2's key families) → the **bucket** (parent §1.1):

- **Bucket 1 — Mapped:** the provider value has a canonical counterpart → `no_canonical_match=false`, `canonical_value` set.
- **Bucket 2 — Proprietary/unmodeled:** record raw, attributed to provider, **may never surface** (`no_canonical_match=true`, dormant). E.g. WHOOP `recovery_score`, Oura readiness score.
- **Bucket 3 — Real activity we don't prescribe:** record raw **AND surface in completed history** (`no_canonical_match=true`, surfaced). E.g. a Strava `Pickleball` game.

`match_kind` = authoring provenance (`exact` enum/field match · `manual` curated judgment · `fuzzy` rapidfuzz candidate, parent §7). The unit column gives the **edge conversion** to canonical SI (parent §2.2); "—" = already canonical.

---

## 1. DECISION (needs Andy) — the cardio-activity discipline target: fine D-id vs coarse `_plan_sport_type`

**The question:** when a provider reports a completed cardio activity type (`TrailRun`, `BackcountrySki`, `Kayaking`), what canonical value do we store?

We have **two** discipline representations, and parent §2.1 names both ("discipline id / `_plan_sport_type`") without resolving which the inbound target is:

| Representation | Vocabulary | Source |
|---|---|---|
| **Fine layer0 discipline canon** | 24 ids — D-001 Trail Running, D-002 Road Running, D-003 Trekking, D-004 Swimming, D-006 Road Cycling, D-007 TT Cycling, D-008 MTB, D-009 Packrafting, D-010 Kayaking, D-011 Canoeing, D-012 Rock Climbing, D-013 Abseiling, D-014 Via Ferrata, D-017 Snowshoeing, D-018 Mountaineering, D-019 Paddle Rafting, D-021 Uphill Skinning, D-022 Alpine Descent, D-024 Mountain Running, D-027 OCR, D-028 XC Skiing, D-030 Gravel Cycling, D-031 XC Cycling, D-032 SUP | `etl/layer0/discipline_canon.CANONICAL_NAMES` |
| **Coarse `_plan_sport_type`** | 6 values — `running`, `cycling`, `swimming`, `strength_training`, `hiking`, `walking` | `garmin_connect.GARMIN_TYPE_TO_PLAN_SPORT` targets (the wired Garmin path; parent §6.2's named seed) |

**The tension is load-bearing for this app.** The coarse set is a Garmin-era artifact with **no skiing, paddling, or climbing** — yet those are exactly AIDSTATION's market thesis (skimo, AR, marathon paddle, swimrun). The fine canon **has** them (D-021 skinning, D-010 kayak, D-012 climb, D-017 snowshoe, D-032 SUP). Mapping a Strava `BackcountrySki` or `Kayaking` to bucket-3 — because the thin coarse target lacks it — would throw away the multisport signal the product exists to capture.

**Options:**

- **(A) Coarse `_plan_sport_type` target.** Consistent with the wired Garmin path (parent §6.2) and semantically "activity modality." But thin (6 values) → skiing/paddling/climbing/rowing all fall to bucket-3, losing real endurance signal.
- **(B) Fine layer0 D-id target.** High-fidelity (the parent's "MuleSoft" north star); faithful for the multisport disciplines. Cost: D-ids carry race-classification semantics (they drive Layer 2A composition), so reusing them as an *activity*-ingest target is a slight semantic stretch, and some provider activities (Walk, Elliptical, Rowing) still have no D-id → bucket-3.
- **(C) Fine D-id primary + a deterministic D-id→coarse collapse (RECOMMENDED).** Store the fine D-id where one exists (faithful, lossless); derive the coarse `_plan_sport_type` for plan-item matching via a one-time ~6-bucket collapse table (D-001/002/024→`running`; D-006/007/008/030/031→`cycling`; D-004→`swimming`; D-003/017→`hiking`; etc.). Provider types with no D-id but a coarse home (Walk→`walking`) map coarse-only. Types with neither (Rowing, Snowboard, Elliptical) → bucket-3 (+ §6 candidate-new-discipline flag where legit).

**Recommendation: (C).** It mirrors the #679 strength principle exactly — *preserve specificity, collapse is a backstop* (subtype-preferred EX-id, category-collapse only when no specific home) — and it's the only option that doesn't discard the skimo/paddle/climb signal. The collapse is mechanical and lossless (fine→coarse is deterministic; the reverse isn't, so storing fine loses nothing). The matrix below is authored **assuming (C)** — each cardio row gives both the fine D-id and the coarse collapse, so if you pick (A) the coarse column is already there.

**Gut check:** (C)'s cost is that no current inbound path *consumes* a fine D-id for a completed activity (the wired Garmin path stores coarse), so the build wave that lands `provider_value_map` also has to teach `cardio_log` ingest to carry the D-id — slightly more than a like-for-like swap. If you'd rather ship the smallest thing first, (A) is defensible and the fine ids become a later fidelity upgrade. Either way the provider's **raw** sub-type is kept (record-don't-drop), so fidelity is never *lost* — the only question is whether it's mapped-canonical or sits raw.

---

## 2. Strava — `activity` (cardio) + `body`

**Mechanism:** OAuth2 REST + Webhook Events API (one push subscription/app; webhook is a lightweight `{object_type, object_id, aspect_type, owner_id, ...}` event — must 200 within 2s — then you GET the activity over REST). Read scopes: `activity:read[_all]` (activities + webhooks), `profile:read_all` (the `/athlete/zones` endpoint). Rate limit 200/15min, 2000/day (upgradable). Mechanism class = OAuth REST + webhook (parent §5).

**Data types Strava provides:** `cardio` (rich) + `body` (two single profile fields only). **Strava has NO sleep / HRV / resting-HR / recovery / SpO2 / respiration / VO2max / body-fat data** — those data types are **N/A for Strava** (confirmed against the `DetailedAthlete` model; Strava is an activity platform, not a wellness device). This matters: Strava is a cardio+body connector only.

### 2.1 Activity metrics — `DetailedActivity` / `SummaryActivity` (data_type=`cardio`)

| Strava field | Unit | Canonical target | Bucket | Notes |
|---|---|---|---|---|
| `distance` | m | distance (m) | 1 | — (verbatim "in meters") |
| `moving_time` / `elapsed_time` | s | duration (s) | 1 | — |
| `total_elevation_gain`, `elev_high`, `elev_low` | m | elevation (m) | 1 | no canonical elevation key yet (raw) |
| `average_speed` / `max_speed` | m/s | speed (m/s) | 1 | — |
| `average_watts` / `weighted_average_watts` / `max_watts` | W | power (W) | 1 | rides w/ power meter only; `weighted_average_watts` = Strava's NP estimate |
| `device_watts` | bool | power provenance flag | 1 | false = estimated |
| `calories` | kcal | energy (kcal) | 1 | "kilocalories" — already canonical |
| `kilojoules` | **kJ** | energy (kcal) | 1 | **÷4.184** — rides only; mechanical work, NOT the same as `calories` |
| `average_heartrate` / `max_heartrate` | bpm | `hr_avg_bpm` / `hr_peak_bpm` | 1 | ⚠️ **observed-not-guaranteed** — present in real responses but absent from Strava's documented `SummaryActivity`/`DetailedActivity` schema (formally documented only on segment-effort/lap). Map, but don't assume schema guarantees. |
| `average_cadence`, `average_temp` | spm/rpm, °C | cadence / temp | 1 | same observed-not-guaranteed caveat; units unverified at activity level |
| `suffer_score` | — | **bucket-2** (Relative Effort) | 2 | HR-derived training-load number; often `null`; no canonical home → record raw |
| `sport_type` | enum | **discipline** (§2.2) | 1/3 | the primary discipline signal |
| `type` | enum (deprecated) | discipline (legacy) | — | key off `sport_type`; `type` collapses the new sub-types — fallback only |

### 2.2 `sport_type` enum → discipline (the key deliverable; 56 values, mapped to our canon per §1 option C)

`match_kind=manual` for every row (curated judgment). Fine D-id + coarse collapse + bucket:

| Strava `sport_type` | Fine D-id | Coarse | Bucket | Note |
|---|---|---|---|---|
| `Run` | D-002 Road Running | running | 1 | |
| `TrailRun` | D-001 Trail Running | running | 1 | |
| `VirtualRun` | D-002 (closest) | running | 1 | treadmill/virtual — no distinct canon; raw kept |
| `Ride` | D-006 Road Cycling | cycling | 1 | |
| `VirtualRide` | D-006 (closest) | cycling | 1 | indoor/Zwift — no indoor-cycling canon; raw kept |
| `MountainBikeRide` | D-008 MTB | cycling | 1 | |
| `EMountainBikeRide` | D-008 MTB | cycling | 1 | e-assist — flag in raw |
| `GravelRide` | D-030 Gravel Cycling | cycling | 1 | |
| `EBikeRide` | D-006 Road Cycling | cycling | 1 | e-assist — flag in raw |
| `Handcycle` | D-006 (closest) | cycling | 1 | adaptive — flag in raw |
| `Velomobile` | D-006 (closest) | cycling | 1 | |
| `Swim` | D-004 Swimming | swimming | 1 | Strava has no pool/open-water split (raw kept) |
| `Hike` | D-003 Trekking | hiking | 1 | our "Trekking" absorbed Hiking |
| `Snowshoe` | D-017 Snowshoeing | hiking | 1 | we have this discipline |
| `Kayaking` | D-010 Kayaking | — | 1 | no coarse home; fine-only |
| `Canoeing` | D-011 Canoeing | — | 1 | fine-only |
| `StandUpPaddling` | D-032 SUP | — | 1 | fine-only |
| `RockClimbing` | D-012 Rock Climbing | — | 1 | fine-only |
| `AlpineSki` | D-022 Alpine Descent | — | 1 | fine-only |
| `NordicSki` | D-028 XC Skiing | — | 1 | fine-only |
| `BackcountrySki` | D-021 Uphill Skinning | — | 1 | fine-only (the skimo signal) |
| `RollerSki` | D-028 (closest, dryland) | — | 1 | flag in raw |
| `WeightTraining` | — | strength_training | 1 | coarse-only; strength is the EX-id/rx world, not a race discipline |
| `Walk` | — | walking | 1 | coarse-only (no race-discipline equivalent) |
| `Crossfit`, `HighIntensityIntervalTraining` | — | strength_training (low-conf) | 3→1? | **judgment call** — collapse to strength_training, or bucket-3? (recommend bucket-3: not a barbell-strength stimulus) |
| `Rowing`, `VirtualRow` | *(none)* | *(none)* | 3 | **candidate-new-discipline "Rowing"** (§6) — legit endurance; flag for Andy |
| `Snowboard` | *(none)* | *(none)* | 3 | not in market vocab → bucket-3 |
| `Workout`, `Elliptical`, `StairStepper`, `Wheelchair` | *(none)* | *(none)* | 3 | generic/indoor-machine → record + surface |
| `Surfing`, `Kitesurf`, `Windsurf`, `Sail`, `IceSkate`, `InlineSkate`, `Skateboard` | *(none)* | *(none)* | 3 | not programmed → bucket-3 |
| `Golf`, `Yoga`, `Pilates`, `PhysicalTherapy`, `Soccer`, `Basketball`, `Volleyball`, `Cricket`, `Tennis`, `TableTennis`, `Badminton`, `Squash`, `Racquetball`, `Pickleball`, `Padel`, `Dance` | *(none)* | *(none)* | 3 | "real activity we don't prescribe" — the parent §1.1 bucket-3 exemplar (Pickleball) |

### 2.3 Strava `body` (data_type=`body`)

| Strava field | Unit | Canonical | Bucket | Note |
|---|---|---|---|---|
| `DetailedAthlete.weight` | kg **or** lb | `body_mass_kg` | 1 | unit follows `measurement_preference` (`meters`→kg, `feet`→lb); **current value only, not a time series**; `profile:write` can set it |
| `DetailedAthlete.ftp` | W | `ftp_w` | 1 | "Functional Threshold Power"; current value only; settable via `profile:write` |

> Strava is the **only Batch-1 provider that sources `ftp_w`** — worth noting for the registry (parent §2.3 had `ftp_w` as "not yet surfaced").

### 2.4 Strava HR/power zones (data_type=`zone`)

`GET /athlete/zones` (needs `profile:read_all`) → `{heart_rate:{custom_zones, zones:[{min,max}...]}, power:{zones:[{min,max}...]}}`. Ordered `{min,max}` boundary arrays (HR bpm / power W), **no semantic labels**, count **not** contractually 5 (athlete `custom_zones`). **Normalize:** map array index→Z1…Z5 by position, **guard zone count ≠ 5** (don't force). Per-activity time-in-zone (`ActivityZone`/`TimedZoneRange`) is a paid (Summit) feature → bucket-2 raw when present.

### 2.5 Strava bucket-2 (record raw, dormant)

`suffer_score` (Relative Effort) · per-activity time-in-zone distributions (Summit) · `segment_efforts`/`best_efforts` (`pr_rank`/`kom_rank`/achievements) · social counters (`kudos_count`, `achievement_count`, …). **Fitness/Freshness/Form (CTL/ATL/TSB) is NOT exposed by the public API** — unavailable, not bucket-2.

**Sources:** developers.strava.com/docs/reference, /swagger/swagger.json, /docs/webhooks, /docs/authentication, /docs/getting-started, /docs/changelog (fetched 2026-06-17).

---

## 3. WHOOP — `recovery` / `sleep` / `cycle` / `workout` / `body`

**Mechanism:** OAuth2 REST **v2** (`/v2/...`; v1 unsupported as of the v2 launch 2025-07-01 — v1 webhooks removed, sleep/workout ids are now **UUIDs**). Webhooks for `workout.updated/deleted`, `sleep.updated/deleted`, `recovery.updated/deleted` (creates arrive as "updated"; **no** cycle/body webhooks — poll those). Scopes: `read:recovery`, `read:sleep`, `read:workout`, `read:cycles`, `read:body_measurement`, `offline`. Score objects appear only when `score_state == SCORED`. Mechanism class = OAuth REST + webhook (parent §5).

> **Unit corrections vs the parent's assumptions (verified against official sample payloads):** WHOOP HRV `hrv_rmssd_milli` is **already milliseconds** (sample `31.81`) → maps **1:1** to `hrv_rmssd_ms`, **no conversion**. Sleep stages **are** milliseconds (ms→min needed). Energy is **kilojoules** (kJ→kcal needed).

### 3.1 Recovery (data_type=`wellness`) — `recovery.score`

| WHOOP field | Unit | Canonical | Bucket | Note |
|---|---|---|---|---|
| `resting_heart_rate` | bpm | `resting_hr_bpm` | 1 | — |
| `hrv_rmssd_milli` | **ms** | `hrv_rmssd_ms` | 1 | **no conversion** — despite the `_milli` suffix the value is ms |
| `spo2_percentage` | % | `spo2_pct` | 1 | WHOOP 4.0+ only; nullable |
| `skin_temp_celsius` | °C | **bucket-2** | 2 | no canonical skin-temp key; record raw |
| `recovery_score` | 0–100% | **bucket-2** | 2 | proprietary recovery composite |
| `user_calibrating` | bool | **bucket-2** | 2 | new-user calibration flag |

### 3.2 Sleep (data_type=`sleep`) — `sleep.score`

| WHOOP field | Unit | Canonical | Bucket | Note |
|---|---|---|---|---|
| `stage_summary.total_slow_wave_sleep_time_milli` | **ms** | `sleep_deep_min` | 1 | **÷60000**; "slow wave" = deep |
| `stage_summary.total_rem_sleep_time_milli` | **ms** | `sleep_rem_min` | 1 | ÷60000 |
| `stage_summary.total_light_sleep_time_milli` | **ms** | `sleep_light_min` | 1 | ÷60000 |
| `stage_summary.total_in_bed_time_milli` | **ms** | `sleep_total_min` | 1 | ÷60000. ⚠️ **DECISION:** WHOOP has no single "asleep total" field — `sleep_total_min` = time-in-bed, **or** derive asleep = in_bed − awake − no_data (= light+sws+rem). Pick one convention (recommend **asleep** = Σstages, matching Polar/COROS "total sleep"). |
| `respiratory_rate` | brpm | `respiration_rate_brpm` | 1 | — |
| `sleep_performance_percentage` | % | **bucket-2** (WHOOP's "sleep score") | 2 | proprietary % vs sleep-need; **NOT** the §2.3 `sleep_score` (which is a 0–100 device composite — different scale/meaning). Map to `sleep_score` only if you accept the proprietary %. |
| `sleep_efficiency_percentage`, `sleep_consistency_percentage`, `disturbance_count`, `sleep_cycle_count`, `sleep_needed.*` | various | **bucket-2** | 2 | proprietary sleep model; record raw |

### 3.3 Cycle / strain (data_type=`wellness`) — `cycle.score`

| WHOOP field | Unit | Canonical | Bucket | Note |
|---|---|---|---|---|
| `average_heart_rate` | bpm | `hr_avg_bpm` | 1 | — |
| `max_heart_rate` | bpm | `hr_peak_bpm` | 1 | — |
| `kilojoule` | **kJ** | energy (kcal) | 1 | **÷4.184** — total daily energy expenditure. ⚠️ **NOT** `resting_metabolic_rate_kcal` (WHOOP exposes no RMR). |
| `strain` | 0–21 | **bucket-2** ("Day Strain") | 2 | proprietary |

### 3.4 Workout (data_type=`cardio`) — `workout` + `workout.score`

- **Sport:** `sport_name` (v2 string, e.g. `"running"`; key off this — `sport_id` int is legacy, gone after 2025-09-01). Representative map to our canon (per §1 option C): `running`→D-002·running · `cycling`→D-006·cycling · `swimming`→D-004·swimming · `hiking`/`rucking`→D-003·hiking · `walking`→walking(coarse) · `weightlifting`/`powerlifting`/`strength trainer`→strength_training · `spin`→D-006·cycling (indoor). WHOOP has **no trail-running or distinct indoor-cycling sport** (trail comes through as `running`; "Spin" ≈ indoor). The full enum is **~140 sports** (Yoga, Pickleball, HIIT, Functional Fitness, Elliptical, Sauna, …) — anything without a canonical discipline → **bucket-3**.
- **Metrics:** `average_heart_rate`→`hr_avg_bpm`, `max_heart_rate`→`hr_peak_bpm`, `distance_meter`→distance (m, —), `kilojoule`→energy (kJ→kcal ÷4.184), `altitude_gain_meter`/`altitude_change_meter`→elevation (m, raw). `strain`, `percent_recorded` → bucket-2.
- **Zones:** `zone_durations.zone_one_milli`…`zone_five_milli` → **Z1…Z5** (clean 1:1, ms→min/s). `zone_zero_milli` (sub-Z1, <50% maxHR) → **no canonical zone** (drop/bucket-2). ⚠️ The zone_one=Z1 binding is a **high-confidence inference** from WHOOP's published 5-zone (%maxHR / HRR-personalized) framework, not a verbatim API statement.

### 3.5 Body measurement (data_type=`body`) — `GET /v2/user/measurement/body`

| WHOOP field | Unit | Canonical | Bucket | Note |
|---|---|---|---|---|
| `weight_kilogram` | kg | `body_mass_kg` | 1 | **already kg** — no conversion |
| `height_meter` | m | height (m) | 1 | no canonical height key (raw) |
| `max_heart_rate` | bpm | **bucket-2** (user-level WHOOP-calc'd max) | 2 | reference value, not a measured peak |

> **WHOOP has NO source for** `body_fat_pct`, `vo2max_running`, `vo2max_cycling`, `ftp_w`, `resting_metabolic_rate_kcal` (body measurement = height/weight/maxHR only; `kilojoule` is total energy, not RMR). Mark those keys unmapped for WHOOP.

### 3.6 WHOOP bucket-2 (record raw, dormant)

`recovery_score`, `user_calibrating`, `skin_temp_celsius`, cycle/workout `strain`, `percent_recorded`, `sleep_performance/efficiency/consistency_percentage`, `disturbance_count`, `sleep_cycle_count`, `sleep_needed.*`, user-level `max_heart_rate`, `zone_zero` time.

**Sources:** developer.whoop.com/docs/developing/user-data/{recovery,sleep,workout,cycle,user}, /oauth, /webhooks, /v1-v2-migration, /api-changelog (fetched 2026-06-17).

---

## 4. Oura — `sleep` / `daily_sleep` / `daily_readiness` / `daily_activity` / `daily_spo2` / `vO2_max` / `workout`

**Mechanism:** OAuth2 REST v2 (base `https://api.ouraring.com/v2`; per-day "document" collections at `/v2/usercollection/{type}`, each a 24h scored summary from 4 a.m.) + optional webhooks (`create`/`update`/`delete` per data_type). Scopes: `email`, `personal`, `daily`, `heartrate`, `workout`, `tag`, `session`, `spo2`. Mechanism class = OAuth REST + webhook (parent §5).

**Oura's shape:** it's the **cleanest bucket-1 wellness source of Batch 1** — sleep stages, resting HR, HRV, respiration all map directly — but **almost everything Oura *scores* is bucket-2** (readiness/sleep/activity scores + their 1–100 contributors are composites, not physiology). **All durations are in SECONDS → ÷60 to the `*_min` keys** (parent assumed minutes for some sources). Oura has **no HR-zone model** (workout `intensity` is `easy/moderate/hard`, *not* Z1–Z5) and **never reports absolute temperature** (deviation only — §4.4).

### 4.1 Sleep (data_type=`sleep`) — `sleep` (detailed period) + `daily_sleep` (score)

| Oura field | Unit | Canonical | Bucket | Note |
|---|---|---|---|---|
| `sleep.total_sleep_duration` | **s** | `sleep_total_min` | 1 | **÷60** ("Total sleep duration in seconds") — this is asleep total, matching Polar/COROS convention |
| `sleep.deep_sleep_duration` | **s** | `sleep_deep_min` | 1 | ÷60 |
| `sleep.rem_sleep_duration` | **s** | `sleep_rem_min` | 1 | ÷60 |
| `sleep.light_sleep_duration` | **s** | `sleep_light_min` | 1 | ÷60 |
| `sleep.lowest_heart_rate` | bpm | `resting_hr_bpm` | 1 | **the real RHR source** (NOT the readiness `resting_heart_rate` contributor, which is a 1–100 score) |
| `sleep.average_heart_rate` | bpm | `hr_avg_bpm` | 1 | sleep avg; spec warns it differs from the app (30s vs 5-min samples) |
| `sleep.average_hrv` | ms | `hrv_rmssd_ms` | 1 | ⚠️ spec says only `integer` + "Average HRV"; **rMSSD-in-ms is confirmed by Oura's *consumer* docs, not the API contract** — note this |
| `sleep.average_breath` | brpm | `respiration_rate_brpm` | 1 | — |
| `daily_sleep.score` | 0–100 | `sleep_score` | 1 | the genuine device composite (parent §2.3's `sleep_score.device`) — **better source than WHOOP's proprietary %** |
| `sleep.efficiency` | 1–100 **rating** | **bucket-2** | 2 | ⚠️ a 1–100 rating, **NOT a percentage** — don't treat as a fraction |
| `sleep.awake_time`, `time_in_bed`, `latency`, `heart_rate[]`/`hrv[]` samples | s / series | raw | — | no canonical key; `raw_payload` |
| `daily_sleep.contributors.*` (deep_sleep, efficiency, latency, rem_sleep, restfulness, timing, total_sleep) | 1–100 | **bucket-2** | 2 | proprietary sub-scores |

### 4.2 Readiness / recovery (data_type=`wellness`) — `daily_readiness`

**Entirely bucket-2.** `score` (readiness composite) and **all 9 contributors** — `activity_balance`, `body_temperature`, `hrv_balance`, `previous_day_activity`, `previous_night`, `recovery_index`, `resting_heart_rate`, `sleep_balance`, `sleep_regularity` — are 1–100 *contribution scores*, not raw values. **Trap:** the contributor literally named `resting_heart_rate` is the RHR's contribution to the score, **not a bpm** — the real RHR is `sleep.lowest_heart_rate` (§4.1). Record all raw. `temperature_deviation` / `temperature_trend_deviation` → §4.4.

### 4.3 Activity / SpO2 / VO₂max / other daily docs

| Oura field | Unit | Canonical | Bucket | Note |
|---|---|---|---|---|
| `daily_activity.total_calories` / `active_calories` | kcal | energy (kcal) | 1 | already kcal ("expended in kilocalories") |
| `daily_activity.steps` | count | `steps` | 1 | ⚠️ `steps` is a canonical target in parent §6.3 (COROS) but is **missing from the §2.3 registry table** — registry omission to reconcile |
| `daily_activity.equivalent_walking_distance` / `target_meters` | m | distance (m) | 1 | raw (derived metric) |
| `daily_spo2.spo2_percentage.average` | % | `spo2_pct` | 1 | ⚠️ value is **nested at `.average`**, not the object itself |
| `vO2_max.vo2_max` | ml/kg/min | `vo2max_running` | 1 | ⚠️ **ONE undifferentiated value — Oura does NOT split running vs cycling**; fills `vo2max_running` only (or a generic), `vo2max_cycling` stays unmapped from Oura. Endpoint casing is literally `/v2/usercollection/vO2_max`. |
| `daily_activity.score` + 6 contributors; `daily_resilience`; `daily_stress`; `daily_cardiovascular_age.vascular_age`; `daily_spo2.breathing_disturbance_index` | 1–100 / enum / sec | **bucket-2** | 2 | proprietary composites/indices — record raw, dormant |

**No Oura source for:** `ftp_w`, `resting_metabolic_rate_kcal`, `vo2max_cycling`, `body_fat_pct`. `body_mass_kg` exists **only as a static `personal_info.weight` (kg)** profile field — not a daily time series (like Strava's `athlete.weight`).

### 4.4 Body temperature — DEVIATION only (do not map to absolute)

Oura never reports absolute body/skin temperature in v2. The only temp fields — `daily_readiness.temperature_deviation` and `temperature_trend_deviation` (both °C, both a **delta from the user's personal baseline**) — have no canonical home → **bucket-2, record raw** (preserve the sign; it's a °C-delta, not a temperature). Do **not** map to any absolute-temperature key.

### 4.5 Workout (data_type=`cardio`) — `workout`

- **`activity` is a FREE-FORM string, NOT an enum** — Oura publishes no closed activity list (the only API-verified literal is `"cycling"`, lowercase). **Map dynamically:** match the `activity` string against our discipline ids (per §1 option C — `running`→D-002, `cycling`→D-006, `swimming`→D-004, `hiking`→D-003, `walking`→walking, `strength_training`→strength_training, …); **any unrecognized string → bucket-3.** Don't hardcode an enum — exact spellings for multi-word activities are unverifiable.
- **Metrics:** `calories`→energy (kcal, —), `distance`→distance (m, —). `intensity` (`easy`/`moderate`/`hard`) → **bucket-2 / coarse label — NOT Z1–Z5** (Oura has no zone model). `source` (`manual`/`autodetected`/`confirmed`/`workout_heart_rate`) → provenance flag. `tag`/`enhanced_tag` → free-form user labels (raw).

### 4.6 Oura bucket-2 (record raw, dormant)

readiness `score` + 9 contributors · `temperature_deviation` / `temperature_trend_deviation` · `daily_sleep.score` + 7 contributors · `daily_activity.score` + 6 contributors · `sleep.efficiency` (1–100 rating) · `daily_resilience` (level + 3 contributors) · `daily_stress` (stress_high/recovery_high/day_summary) · `daily_cardiovascular_age.vascular_age` · `daily_spo2.breathing_disturbance_index` · `workout.intensity`.

**Sources:** Oura official OpenAPI v2 spec (parsed verbatim); cloud.ouraring.com/v2/docs; support.ouraring.com (HRV=rMSSD/ms, temperature-deviation) (fetched 2026-06-17). *Flagged unverified against the API contract: exact multi-word `activity` spellings (only `cycling` confirmed); the SpO2 scope literal (`spo2` vs `spo2Daily`); that `average_hrv` is specifically rMSSD/ms (true per consumer docs, not the field definition).*

---

## 5. Cross-provider canonical coverage (Batch 1)

Which canonical metric keys each provider can source (1 = mapped, 2 = proprietary/raw, — = N/A):

| Canonical key | Strava | Oura | WHOOP |
|---|---|---|---|
| `resting_hr_bpm` | — | 1 (sleep.lowest_hr) | 1 |
| `hr_avg_bpm` | 1 (activity) | 1 (sleep avg) | 1 (cycle/workout) |
| `hr_peak_bpm` | 1 (activity) | — | 1 (cycle/workout) |
| `hrv_rmssd_ms` | — | 1 | 1 |
| `sleep_total_min` + stages | — | 1 (s→min) | 1 (ms→min) |
| `sleep_score` | — | **1 (device composite)** | 2 (proprietary %) |
| `respiration_rate_brpm` | — | 1 | 1 |
| `spo2_pct` | — | 1 | 1 |
| `body_mass_kg` | 1 (current only) | 1 (static profile) | 1 |
| `ftp_w` | **1** | — | — |
| `vo2max_running` | — | 1 (no disc split) | — |
| `vo2max_cycling` | — | — | — |
| `body_fat_pct`, `resting_metabolic_rate_kcal` | — | — | — |
| discipline (cardio) | 1 (56-enum) | 1 (free-form string) | 1 (~140-enum) |
| HR zones Z1–Z5 | 1 (positional) | **— (no zone model)** | 1 (zone_one–five) |

Takeaways: **Strava = cardio + ftp/weight, zero wellness. Oura = the wellness/sleep/RHR/HRV bucket-1 anchor, zero zones/ftp. WHOOP = wellness + workout cardio + zones, zero ftp/bodyfat/VO2max.** Three providers, three near-disjoint coverage footprints — which is the case *for* a unified canonical store (parent §4) over per-provider tables: an athlete on all three fills a picture no one covers alone, and `sleep_score`/`resting_hr_bpm` arrive from two sources needing one canonical home + a precedence rule.

---

## 6. Candidate NEW canonical entries (Trigger #2 — Andy ratifies; identify, do not pad)

Per parent §7.4 + the CLAUDE.md no-padding rule, these are **flagged, not added**. Until ratified, the value is recorded raw (record-don't-drop):

- **New discipline "Rowing"** — Strava `Rowing`/`VirtualRow` (and WHOOP rowing sports) have no D-id. Rowing is a legitimate endurance modality (erg + on-water). **Recommend: mint a Rowing D-id.** Gut check: it's not in AIDSTATION's named target markets, but it's a mainstream endurance sport an athlete will log; bucket-3 record-and-surface is an acceptable interim.
- **No new sleep/recovery metric keys needed** — the §2.3 registry covers everything WHOOP/Oura map to bucket-1; their extra numbers (strain, recovery %, readiness, sleep performance %) are correctly **bucket-2** (proprietary composites we don't model), not missing keys.
- **Possible new raw-but-unkeyed dimensions** (not registry keys; just raw columns we don't have): `skin_temp_celsius` (WHOOP), Oura `temperature_deviation` (°C-**delta**, never absolute), `elevation_gain_m` (Strava/WHOOP), `height_m` (WHOOP/Oura body), per-activity `cadence`. These ride in `provider_raw_record.raw_payload` (parent §4.3) — no registry change needed.

**Registry reconciliations the matrix surfaced (parent §2.3 fixes, not new padding):**
- **`steps` is missing from the §2.3 registry table** but is already used as a canonical target in parent §6.3 (COROS) and is sourced by Oura `daily_activity.steps`. Add `steps` (count, no SI conversion) to the §2.3 registry — it's a consumed key the table omits.
- **`vo2max_running` / `vo2max_cycling` split doesn't always map:** Oura emits **one undifferentiated `vo2_max`** (no discipline). The split is fine for Garmin (which does distinguish), but the registry/ingest must tolerate a single-value provider filling only `vo2max_running` (or a generic). Not a new key — a fill-rule note.

**New architectural need the matrix surfaced — multi-source precedence (for the build wave, parent §4):** `sleep_score` arrives from **Oura (device composite)** *and* WHOOP (proprietary %); `resting_hr_bpm` from **Oura (sleep.lowest_hr)** *and* WHOOP; `body_mass_kg` from Strava/Oura/WHOOP. One canonical key, multiple providers → the canonical store needs a **per-(user, metric) source-precedence rule** (e.g. prefer the dedicated wellness device over an activity platform, or most-recent-wins). Flag for the §4 build; not a vocabulary change.

---

## 7. Batch plan (remaining roster — subsequent sessions)

| Batch | Providers | Why grouped | Notes |
|---|---|---|---|
| **1 (this doc)** | Strava, Oura, WHOOP | highest-value consumer; spans cardio + wellness + all 3 buckets | — |
| **2** | Wahoo, RWGPS | cycling/activity; **RWGPS is already shipped**, Wahoo is "next" to wire | extends the cardio crosswalk; RWGPS routes → discipline + GPS |
| **3** | TrainingPeaks, Zwift | structured-workout platforms | mostly **outbound** (parent Wave 3b) — inbound is completed-workout import |
| **4** | MyFitnessPal | nutrition | **blocked** — ties Layer 2E, which has no nutrition table (parent §11.4); canonical nutrition keys are a Layer-2E co-design, not a like-for-like matrix row |
| **5** | Apple Health, Samsung Health, Google Health Connect | SDK on-device | needs a native client (parent §5); their data model is HealthKit/Health-Connect *types*, not a REST enum — different authoring shape |

Authoring order tracks **wiring reality** (parent §1.3 #1: this layer consumes already-received payloads): map what we can actually ingest first. Unwired providers (TP/Zwift/MFP/SDK) are real future rows but lower-priority than the wired/next ones.

---

## 8. Instrumentation (parent §10, Rule #15)

When the build wave wires these maps, every inbound resolution emits a `print()` carrying `provider`, `data_type`, `source_value`, resolved `canonical_value` or `bucket`, `match_kind`, `confidence` — so a silent mis-map in prod says *which* value, *which* provider, *which* bucket from the logs alone. (No code this doc; flag for the build.)

---

## 9. Gut check (what might be missing / best argument against)

- **The §1 discipline decision is the load-bearing call** — get it wrong and either we discard skimo/paddle signal (option A) or we add ingest plumbing no current consumer reads (option C). I recommend C on fidelity grounds, but it's genuinely Andy's call and it gates every cardio row here.
- **"Observed-not-guaranteed" Strava HR.** Activity-level HR is in real payloads but not Strava's documented schema. If we hard-depend on it and Strava tightens the schema, it breaks. Low risk (it's been stable for years), but the matrix flags it rather than assuming.
- **WHOOP `sleep_total_min` convention** (in-bed vs asleep) and the **zone_one=Z1 inference** are the two places WHOOP's docs don't hand us an exact answer — both flagged inline; both need a one-line decision at build, not more research.
- **Am I authoring rows for a table that doesn't exist?** Yes — by design (Path A, Andy's pick). The risk is the matrix drifts from `provider_value_map`'s final shape. Mitigation: every row here is written in that table's exact column vocabulary (parent §4.2), so the build is a transcription, not a re-derivation.
- **Three providers, not eleven.** Deliberate — a shallow 11-provider pass would be lower-value than three deep, sourced ones. The §7 batch plan sequences the rest by wiring reality. Best argument against: if Andy wanted the *breadth* (a thin all-roster skeleton) over depth, this isn't that — but depth is what makes these rows build-ready.
