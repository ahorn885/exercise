# Provider Data Translation Layer — canonical model + bidirectional connector framework (#681) — Spec v1

**Status:** Draft v1, 2026-06-17. **Architecture wave (Wave 1 of N).** This wave establishes the canonical model, the bidirectional connector/adapter framework, the unified storage schema (replace + consolidate the bespoke per-provider tables), the provider mechanism taxonomy, the map-authoring workflow, and a **seed inbound mapping matrix** for Garmin (strength + cardio) and the wired wellness providers (Polar, COROS). The **full per-provider matrix** (all ~18 providers) and the **outbound serializers** (calendars + native training-platform workout formats) are deferred to later waves (§12). Spec only — no code ships from this doc.

**Type:** Reference + schema (canonical-key SSOT) with an integration-architecture contract. The canonical keys defined here in §2 are the shared contract for ingest (this epic) **and** the AIDSTATION API (`AIDSTATION_API_Spec` / #682) — defined once, here.

**Purpose:** Turn third-party provider data into our canonical model across many providers × many data types, **mapping where we can and recording-don't-dropping the rest**, and (bidirectionally) serialize our canonical plan/workout data back out to providers (calendars + training platforms). One canonical model, one pipeline, surfaced cleanly through the API.

**North-star (Andy):** *"the MuleSoft of athlete data."* We are the canonical integration hub between every athlete-data system: a canonical model + per-provider connectors (inbound parse→normalize, outbound serialize→native), bidirectional. **High-fidelity transformation is the core value** — lossy mapping that writes "crap data" into a connected platform is a product failure, not an acceptable degradation.

**Source decisions (planning session, 2026-06-17; Andy):**
- **D-1 (direction):** #681 is **bidirectional** — inbound (provider→canonical) and outbound (canonical→provider). The issue text is inbound-only today; the charter amendment is recorded on #681 as bookkeeping.
- **D-2 (breadth):** full provider roster (~18, §3), full per-(provider×data_type) matrix authored from provider docs (across waves).
- **D-4 (metric vocabulary):** mint our **own** canonical metric-key registry (SI units canonical; convert at the edge per `units.py`); **always preserve the raw provider value** (raw-passthrough first-class).
- **D-5 (HR zones):** adopt a generally-accepted **5-zone** model as canonical; normalize each provider's zones onto it. (No canonical zone model exists today — this mints one; Trigger #2.)
- **D-6 (outbound, two fidelity tiers):** Tier 1 calendars = lightweight event (title + description + locale location); Tier 2 training platforms = **full native structured-workout fidelity** (planned + finished).
- **D-7 (bucket-3):** non-prescribed completed activities render **inline** in completed history, provider-tagged (data + API + UI).
- **D-8 (storage):** **replace + consolidate** the bespoke per-provider tables (`polar_*`, `coros_*`) into the unified canonical store + a generic raw-passthrough store. Their ingest is wired (`routes/polar_ingest.py`, `routes/coros_ingest.py`) and they carry `raw_payload`, so this is a real migration that rewrites those routes — gated on a zero-row check; the rewrite is future build, not this spec.
- **D-12 (security):** API security + secret encryption + published API + developer application/issuance flow → specced in `AIDSTATION_API_Security_and_Developer_Platform_Spec` (#682 wave). This spec only flags the current gap (provider tokens are plaintext today).

**Cross-references:**
- `AIDSTATION_API_Spec` (#682) — the API over this canonical model; references §2 for keys, does not redefine them.
- `Athlete_Data_Integration_Spec` (#430/v6) — the existing **consumer-side** data model this spec reconciles with and supersedes for the provider-mapping/storage portions (§9).
- `PROVIDERS_SCHEMA.md` — the existing **producer-side** provider-table reference (§9 reconciliation).
- `Catalog_Migration_Plan_v3.md` (#430) — the fuzzy + HITL alias authoring pattern reused in §7.
- `rx_engine_spec.md` — the strength rx write path; the strength inbound slice (#679) inserts at `rx_engine.apply_session_outcome`.
- `ProviderTranslation_GarminStrength_679_Design` — the first concrete inbound slice (#679) built on this spec.

---

## 1. Purpose, scope, and the three-bucket inbound model

### 1.1 The core principle (from #681): map where possible, record-don't-drop otherwise

Every inbound provider field/value falls into exactly one of three buckets:

| Bucket | Name | Rule | Example |
|---|---|---|---|
| **1** | **Mapped** | The provider value has a canonical counterpart → translate to it. | FIT `"Barbell Back Squat"` → layer0 `EX001`; a provider HR-zone scheme → our 5-zone model; `weight_kg` → canonical `body_mass_kg`. |
| **2** | **Proprietary / unmodeled metric** | **Record raw, attributed to provider; may sit dormant** and never surface in UI or the pipeline. Kept so we never lose it and can light it up later. | Whoop "recovery score", Polar "ANS charge", a vendor stress index we don't model. |
| **3** | **Real activity we don't prescribe** | **Record raw AND surface it** — it must appear in the athlete's **completed** history (they did it), even though *we* don't prescribe it. | A Strava pickleball game; a logged exercise not in `layer0.exercises`; a sport/modality we don't program. |

**The bucket-2 vs bucket-3 asymmetry is load-bearing and deliberate:** a proprietary *number* can stay dormant; a *workout the athlete performed* must show up. D-7 makes bucket-3 render inline alongside prescribed work (§6.4), provider-tagged.

### 1.2 Why a layer (not scattered dicts)

The mapping is per `(provider, data_type, source_value)` and accretes over time. Today it is scattered and hardcoded:
- `garmin_fit_parser.py` — `_EXERCISE_CATEGORY_MAP` (33 categories) + `_EXERCISE_SUBTYPE_MAP` (built dynamically from `fit_tool` enums; ~1,261 distinct emittable names).
- `layer0_progression.NAME_TO_EX_ID` — 20 curated strength-name → EX-id entries.
- `garmin_connect.GARMIN_TYPE_TO_PLAN_SPORT` / `normalize_activity` — Garmin activity type → our sport.
- Ad-hoc per-route logic in `routes/polar_ingest.py`, `routes/coros_ingest.py`.

This spec consolidates them behind one schema (§4) with real seed data, a confidence/source column, and a "no canonical match — record raw" state.

### 1.3 What this layer does NOT do (boundaries)

1. It does **not** own provider OAuth/connection plumbing, token refresh, or webhook receipt — that is the `#241` provider-integration track (`provider_auth`, `webhook_events`). This layer consumes already-received provider payloads and produces outbound payloads; it does not authenticate.
2. It does **not** design the API endpoints — that is `AIDSTATION_API_Spec` (#682). This layer defines the canonical model the API speaks.
3. It does **not** build UI surfaces for **bucket-2** proprietary metrics (record now; surface later if/when modeled). Bucket-3 inline surfacing **is** in scope as a data/API/UX contract (§6.4) but its UI build is a later wave (`Bucket3_InlineCompleted_Surfacing_Design`).
4. It does **not** design the secret-encryption / key-issuance / published-API mechanics — that is the security spec (#682 wave). It only flags the current plaintext-token gap (§5.3).
5. It does **not** re-open the Layer 0 catalog. New EX-ids/metric keys are **identified and flagged for Andy ratification** (Trigger #2), never padded in (§7.4, the no-padding rule).
6. It does **not** define cardio HR-zone *physiology thresholds* beyond establishing the canonical 5-zone target model and the per-provider normalization contract; deriving an athlete's actual zone boundaries (LTHR/%HRmax/FTP anchors) is a Layer 4 concern flagged in §2.4.

---

## 2. Canonical model & keys (DEFINED ONCE — the shared contract)

This is the single definition of the canonical vocabulary. `AIDSTATION_API_Spec` references this section; it must not redefine these keys.

### 2.1 Canonical key families

| Family | Canonical identifier | SSOT today | Notes |
|---|---|---|---|
| **Strength exercise identity** | layer0 **EX-id** (`EX001`…`EX249`, TEXT) | `layer0.exercises.exercise_id` (#335) | The rx write path already keys off this. Qualified names like `Back Squat (Barbell)`. |
| **Discipline / sport** | discipline id / `_plan_sport_type` | `discipline_display_names.py`, layer0 discipline vocab | `GARMIN_TYPE_TO_PLAN_SPORT` is the seed crosswalk. |
| **Modality** | modality id | `layer2_modality/` | Cardio/strength/mobility modality. |
| **Metric keys** | **minted SI registry** (§2.3) | NEW (this spec) | e.g. `hrv_rmssd_ms`, `resting_hr_bpm`. |
| **Units** | SI canonical (§2.2) | `units.py` (kg, cm) | Convert at the display/entry edge. |
| **HR-intensity zones** | **5-zone model** (§2.4) | NEW (this spec) | No canonical model exists today. |

### 2.2 Units — SI canonical, convert at the edge

Canonical storage is SI, conversion applied at the form/display boundary — the established `units.py` pattern (kg for weight, cm for height; `display_weight`/`entered_weight_to_kg`). Canonical units by dimension:

| Dimension | Canonical unit | Edge conversions |
|---|---|---|
| Mass / load | **kg** | lb (`units.kg_to_lb`/`lb_to_kg`) |
| Distance | **m** | mi, km |
| Duration | **s** | min, h |
| Heart rate | **bpm** | — |
| HRV | **ms** (RMSSD unless noted) | provider may emit SDNN — key disambiguates (§2.3) |
| Speed | **m/s** | pace (min/mi, min/km) |
| Power | **W** | — |
| Temperature | **°C** | °F |
| Energy | **kcal** | kJ |

**Reconciliation note:** `body_metrics.weight_lbs` is legacy-lb (pre-#469); the canonical store normalizes to kg on read/write. Flag for the migration (§8).

### 2.3 Canonical metric-key registry (minted — D-4)

Minted in-house (Option B), seeded from metrics the app **already surfaces** on `/wellness` and stores in `body_metrics`/`wellness_*` — strict no-padding: only keys we consume. Each key is `snake_case` with an explicit unit suffix. Raw provider value is **always** preserved alongside the canonical value (§4.3), regardless of bucket.

**Seed registry (v1 — Andy ratifies; Trigger #2):**

| Canonical key | Unit | Meaning | Seeded from |
|---|---|---|---|
| `resting_hr_bpm` | bpm | resting heart rate | `/wellness` resting HR, `body_metrics.resting_hr` |
| `hr_avg_bpm`, `hr_peak_bpm` | bpm | daily avg / peak HR | `/wellness` heart_rate.avg/.peak |
| `hrv_rmssd_ms` | ms | overnight HRV (RMSSD) | `/wellness` hrv.overnight, `polar_nightly_recharge.hrv_rmssd_ms`, `coros_*.ppg_hrv` |
| `sleep_total_min` | min | total sleep | `polar_sleep.total_sleep_min`, self-report `sleep_hours` |
| `sleep_deep_min`, `sleep_rem_min`, `sleep_light_min` | min | sleep stages | `polar_sleep.*`, Garmin daily metrics |
| `sleep_score` | 0–100 | composite sleep score | `/wellness` sleep_score.device |
| `body_mass_kg` | kg | body weight | `body_metrics.weight_lbs` (→kg) |
| `body_fat_pct` | % | body fat | `body_metrics.body_fat_pct` |
| `vo2max_running`, `vo2max_cycling` | ml/kg/min | VO₂max (scaffold today) | `/wellness` (undecoded scaffold) |
| `ftp_w` | W | functional threshold power | (cardio/cycling — not yet surfaced) |
| `resting_metabolic_rate_kcal` | kcal | RMR | `/wellness` resting_metabolic_rate |
| `respiration_rate_brpm` | breaths/min | respiration | `/wellness` respiration |
| `spo2_pct` | % | blood oxygen | `/wellness` spo2 |
| `body_battery` *(bucket-2 candidate)* | 0–100 | Garmin proprietary | dormant unless modeled |

Proprietary metrics with no canonical key (Whoop recovery, Polar ANS charge, stress index) are **bucket-2**: stored raw + provider-attributed, **no canonical key minted** until we model them.

### 2.4 Canonical HR-zone model (minted — D-5)

No canonical zone model exists today (only `Z1–Z5` output labels in `fit_workout_generator.py` regex inference and a `layer4` `intensity_zone` enum). This spec mints the canonical target: a **generally-accepted 5-zone model**.

- Canonical zones: **`Z1`…`Z5`** (recovery / endurance / tempo / threshold / VO₂max), the standard 5-band model.
- The **anchor** (the physiology that converts an athlete's HR/power to a zone — %HRmax vs %HRR/Karvonen vs %LTHR vs %FTP) is **per-athlete** and is a **Layer 4 / capacity concern**, not the translation layer's. This spec defines: (a) the canonical 5 zones, and (b) the **per-provider normalization contract** — map each provider's native zone scheme (Polar's 5-zone %HRmax, Garmin's, Whoop strain bands, power zones) onto `Z1–Z5`, recording the provider's native scheme + boundaries as raw (bucket-2) so nothing is lost.
- **Open item (§11):** ratify the canonical anchor default. Until then, zone normalization that requires an anchor we don't have is recorded raw, not force-mapped (record-don't-drop).

---

## 3. Bidirectional connector / adapter framework (the iPaaS)

### 3.1 Shape

```
                         ┌─────────────────────────────┐
   provider payloads ──▶ │  INBOUND ADAPTER (parse →    │ ──▶  canonical store (§4)
   (webhook / FIT / SDK) │  normalize → canonical;      │       (+ raw_payload always kept)
                         │  3-bucket; raw always kept)  │
                         └─────────────────────────────┘
                         ┌─────────────────────────────┐
   canonical plan/    ──▶│  OUTBOUND ADAPTER (serialize │ ──▶  provider (calendar event /
   workout (§6)          │  canonical → native payload) │       native workout doc)
                         └─────────────────────────────┘
                            value-map table = enum/name normalization (§4.2)
                            serializers     = structure/shape/fidelity (§3.3, §6)
```

The **value-map table** handles *enum/name normalization* (the part field-mapping solves). **Serializers** handle *structure/shape/fidelity* (the part field-mapping can't) — both directions, but especially outbound Tier 2.

### 3.2 Per-provider connector = {inbound adapter, outbound adapter?}

A connector is defined by its **mechanism** (§5) and the data types + directions it supports (§3 roster). Not every connector has both directions (a watch is inbound; a calendar is outbound; a training platform is both).

### 3.3 Outbound — two fidelity tiers (D-6)

| Tier | Target | Payload | Fidelity bar |
|---|---|---|---|
| **Tier 1** | Calendars (Google Calendar API, Outlook/MS Graph, Apple EventKit) | **Lightweight event**: title + description (the workout, human-readable) + start/end time + **location ← session's assigned locale** (`locale_profiles.city`, when the session has a `chosen_locale` via `layer4/locale_assign.py`). No structured workout data crammed in. | Event is clean and readable. |
| **Tier 2** | Training platforms (TrainingPeaks, Garmin, Zwift, Wahoo) | **Native structured-workout document** — detailed **planned** workouts (intervals/targets/sets-reps) **and finished** workouts — serialized to each platform's native format (TrainingPeaks structured workout, Garmin/Zwift `.zwo`-class workout, Wahoo plan). | **No lossy field-stuffing.** A valid native doc the athlete sees as a first-class workout in that platform — the "MuleSoft bar." |

**Common to both tiers:** manual export + opt-in **auto-sync on plan create/refresh** (idempotent); a per-`(session, provider)` **external-ref** is stored so we **upsert on change** and **delete on session/plan removal**. (Tier-2 native serializers are designed in `Wave 3b`; Tier-1 in `Wave 3a`. This spec fixes the architecture + the external-ref/idempotency contract.)

---

## 4. Storage schema (replace + consolidate — D-8)

### 4.1 Decision and migration framing

The bespoke per-provider data tables (`polar_sleep`, `polar_nightly_recharge`, `polar_cardio_load`, `polar_continuous_hr_samples`, `coros_daily_summary`, `coros_hrv_samples`; plus stub `wahoo_plans`, `coros_plans`) are **consolidated** into:
- the **core landing tables** (`training_log`, `cardio_log`, `body_metrics`, `wellness_*`) for canonical/mapped values, and
- a **generic raw-passthrough store** for the raw provider value (every bucket).

These per-provider tables' ingest is **wired today** (`routes/polar_ingest.py`, `routes/coros_ingest.py`) and they carry `raw_payload`, so consolidation is a **real migration that rewrites those routes** to write canonical + generic-raw — gated on a **zero-row check** before any drop. The route rewrite + drop is future build; this spec defines the target schema and the migration contract (§8).

**Kept as-is:** the generic substrate `provider_auth` and `webhook_events` (out of scope per §1.3 #1), and the core app tables.

### 4.2 The value-map table (enum/name normalization)

One generic table, seed-extensible, replacing the scattered dicts:

```
provider_value_map(
    provider        TEXT,        -- 'garmin' | 'polar' | 'coros' | 'strava' | ...
    data_type       TEXT,        -- 'strength' | 'cardio' | 'sleep' | 'wellness' | 'body' | 'nutrition' | 'zone'
    direction       TEXT,        -- 'in' | 'out'
    source_value    TEXT,        -- the provider token (FIT name, sport key, metric name, zone label)
    canonical_kind  TEXT,        -- 'ex_id' | 'discipline' | 'modality' | 'metric_key' | 'unit' | 'zone'
    canonical_value TEXT,        -- the canonical target (EX001, running, hrv_rmssd_ms, Z3, ...)
    match_kind      TEXT,        -- 'exact' | 'fuzzy' | 'manual'      (authoring provenance)
    confidence      REAL,        -- 0..1 (fuzzy score or 1.0 for manual/exact)
    no_canonical_match BOOLEAN,  -- TRUE → bucket-2/3, record raw, do not force-map
    notes           TEXT,
    PRIMARY KEY (provider, data_type, direction, source_value)
)
```

`NAME_TO_EX_ID`, `GARMIN_TYPE_TO_PLAN_SPORT`, and the provider metric/zone maps all become rows here. The strength slice (#679) is the first population (`provider='garmin', data_type='strength', direction='in'`).

### 4.3 Raw-passthrough store (buckets 2 & 3, and raw-alongside-canonical)

A generic, provider-attributed store preserving the original value so nothing is lost on ingest and dormant metrics can light up later without a schema break:

```
provider_raw_record(
    id, user_id,
    provider        TEXT,
    data_type       TEXT,
    external_id     TEXT,        -- provider's id for this record (dedup; mirrors existing *_exercise_id cols)
    observed_at     TIMESTAMP,
    raw_payload     JSONB,       -- the original value(s), verbatim (the existing raw_payload columns generalize to this)
    bucket          SMALLINT,    -- 1 | 2 | 3
    canonical_ref   TEXT,        -- FK-ish link to the canonical row it normalized into (NULL for bucket-2)
    fetched_at      TIMESTAMP,
    UNIQUE (user_id, provider, data_type, external_id)
)
```

This generalizes the existing `raw_payload` columns and the existing per-table dedup keys (`cardio_log.polar_exercise_id`, `coros_label_id`, `wahoo_workout_id`, `rwgps_trip_id`) into one provider-agnostic shape.

### 4.4 Outbound external-ref store (idempotent push — D-6)

```
provider_outbound_ref(
    id, user_id,
    provider        TEXT,        -- 'google_calendar' | 'outlook' | 'apple' | 'trainingpeaks' | 'garmin' | 'zwift' | 'wahoo'
    session_id      TEXT,        -- our plan-session id
    external_id     TEXT,        -- the calendar event id / platform workout id we created
    tier            SMALLINT,    -- 1 (calendar) | 2 (workout)
    pushed_payload_hash TEXT,    -- to detect change → upsert vs no-op
    status          TEXT,        -- 'pushed' | 'updated' | 'deleted' | 'error'
    created_at, updated_at
)
```

Enables upsert-on-change and delete-on-removal. (The stub `wahoo_plans`/`coros_plans` tables are early instances of this idea; they fold into this generic table.)

---

## 5. Provider mechanism taxonomy

Mechanism decides how the API (#682) ingests (server-side vs native client) and whether outbound push is possible.

| Mechanism | Providers | Inbound flow | Outbound |
|---|---|---|---|
| **OAuth REST + webhook** | Garmin (Health/Activity API — *currently closed*, §3 note), COROS, Polar AccessLink, Strava, Whoop, Wahoo, Ride With GPS, TrainingPeaks, Zwift, Oura, MyFitnessPal, Google (REST) | webhook → `webhook_events` → inbound adapter → canonical + raw | Garmin/Wahoo/TP/Zwift workout push; RWGPS route push |
| **SDK on-device (native client)** | Apple HealthKit (iOS), Samsung Health (Android), Google Health Connect (Android) | native app reads SDK → posts to our API → inbound adapter. **This is why #682 names a native client as the prerequisite.** | HealthKit/Health Connect can write workouts |
| **Calendar / workout push** | Google Calendar (REST), Outlook/MS Graph (REST), Apple EventKit (on-device) | n/a (outbound-only) | Tier-1 events |

**§5.3 Security gap (flag only — designed in the security spec):** `provider_auth.access_token` / `refresh_token` are stored **plaintext** today. Encryption-at-rest + rotation is the provider-secret plane of `AIDSTATION_API_Security_and_Developer_Platform_Spec` (#682 wave / D-12). Garmin currently uses `provider_auth.session_blob` (garth session) because its public API access is closed; the strength inbound slice (#679) works off **FIT files**, not the live API, so it is unaffected.

---

## 6. Inbound mapping matrix — seed (Wave 1)

Full roster matrix is Wave 2 (§12). This wave seeds the wired/highest-impact providers. Each cell: provider source → canonical target, with bucket behavior.

### 6.1 Garmin — strength (data_type=`strength`, the #679 slice)

- **Source:** `garmin_fit_parser._exercise_name` → name string (subtype-preferred, e.g. `"Barbell Back Squat"`; ~1,261 emittable).
- **Target:** layer0 EX-id via `provider_value_map` (replaces/extends `NAME_TO_EX_ID`).
- **Fallback:** category-collapse **through the name** (cat 28 → `"Squat"` → `EX001`) — there is no direct category→EX-id map; this is a coarse backstop only.
- **No match → bucket-3:** recorded + surfaced in completed as "logged, not prescribed" (NULL EX-id, the `first_exposure`-class state made explicit, §6.4).
- Authored per §7. Detailed design: `ProviderTranslation_GarminStrength_679_Design`.

### 6.2 Garmin — cardio (data_type=`cardio`)

- **Source:** Garmin activity `typeKey` (`running`, `trail_running`, `indoor_cycling`, …).
- **Target:** our discipline / `_plan_sport_type` — seeded directly from `garmin_connect.GARMIN_TYPE_TO_PLAN_SPORT` (15 entries) → `provider_value_map(provider='garmin', data_type='cardio', direction='in')`.
- **No match → bucket-3:** activity recorded in `cardio_log`, surfaced in completed, discipline left unresolved (raw `typeKey` kept).

### 6.3 Polar & COROS — sleep / wellness / recovery / body (data_type=`sleep`/`wellness`/`body`)

Seeded from the wired ingest (the consolidation target for D-8). Representative mappings:

| Provider field | Canonical key | Bucket |
|---|---|---|
| `polar_sleep.total_sleep_min` / `deep/rem/light` | `sleep_total_min` / `sleep_deep_min` / … | 1 |
| `polar_nightly_recharge.hrv_rmssd_ms` | `hrv_rmssd_ms` | 1 |
| `polar_nightly_recharge.ans_charge` | *(none)* | **2** (proprietary, record raw) |
| `polar_cardio_load.daily_load` (TRIMP) / `cardio_load_status` | *(none yet — training-load model TBD)* | **2** |
| `coros_daily_summary.rhr` | `resting_hr_bpm` | 1 |
| `coros_daily_summary.ppg_hrv` / `coros_hrv_samples.hrv` | `hrv_rmssd_ms` | 1 |
| `coros_daily_summary.steps` / `calories` | `steps` / energy `kcal` | 1 |

### 6.4 Bucket-3 inline surfacing contract (D-7)

Non-prescribed completed activities/exercises (Garmin strength with no EX-id; a cardio sport we don't program; a future Strava pickleball game) must appear **inline** in the athlete's completed history alongside prescribed work, **flagged "not prescribed"** and **provider-tagged**. This spec fixes the data contract (a completed record with `prescribed=false`, `provider`, `canonical_ref` possibly NULL, raw retained); the API exposes it (§ `AIDSTATION_API_Spec`); the UI build is `Bucket3_InlineCompleted_Surfacing_Design` (later wave). It replaces the ambiguous `first_exposure` rendering with an explicit, intentional state.

---

## 7. Map-authoring workflow (fuzzy + HITL)

Provider vocabularies are large (Garmin FIT alone ~1,261 strength names); maps are authored offline and committed as seed data — the `Catalog_Migration_Plan_v3.md` Phase-1 pattern.

1. **Candidate generation** — offline `rapidfuzz` over the provider vocabulary × the canonical vocabulary (e.g. Garmin names × ~250 layer0 qualified names). High-frequency-first (the athlete's actual data).
2. **HITL review** — Andy confirms/edits; `match_kind` records provenance (`exact`/`fuzzy`/`manual`), `confidence` records the score.
3. **Commit as seed** — rows land in `provider_value_map`. (Generalizes the curated `NAME_TO_EX_ID`.)
4. **Preserve specificity** — `Barbell Back Squat` → the barbell-back-squat EX-id, not collapsed to generic Squat. Category-collapse is a backstop, never the default (§6.1).

### 7.4 New canonical entries — identify, do not pad (Trigger #2)

When a provider value has no canonical home and is common/legitimate, **identify it as a candidate** new EX-id / metric key / discipline and **flag it for Andy ratification** — never auto-add. Precedent: EX246–EX249 (migration `0011`, ratified 2026-06-16). The strict no-padding rule (CLAUDE.md) governs: add a vocabulary entry only when no existing one covers the same stimulus/technique. Until ratified, the value is recorded raw (record-don't-drop), not force-mapped.

---

## 8. Consolidation / migration plan (contract, not build)

1. Create `provider_value_map`, `provider_raw_record`, `provider_outbound_ref`.
2. Backfill `provider_value_map` from the scattered dicts (`NAME_TO_EX_ID`, `GARMIN_TYPE_TO_PLAN_SPORT`, Polar/COROS field maps) — provenance `manual`/`exact`.
3. Repoint `routes/polar_ingest.py`, `routes/coros_ingest.py` (and future provider ingest) to write **canonical (core tables) + raw (`provider_raw_record`)** instead of bespoke tables.
4. **Zero-row guard:** confirm the bespoke per-provider tables hold no athlete rows (or back them up into `provider_raw_record`) **before** dropping them.
5. Normalize the `body_metrics.weight_lbs` legacy-unit on read/write to canonical kg.
6. Each step is reversible and gated; none ship from this spec.

---

## 9. Reconciliation with existing specs

- **`Athlete_Data_Integration_Spec` (v6, consumer-side):** v6 §4–§6 define `provider_auth`/`webhook_events` (kept) and the per-provider tables + foreign-id columns (consolidated here). v6 §8's two-regime confidence model (pre-/post-integration) maps onto our `match_kind`/`confidence` + bucket model. This spec **supersedes v6's per-provider-table/storage portions**; v6's onboarding-field mapping (§7) stands.
- **`PROVIDERS_SCHEMA.md` (producer-side):** the per-provider table definitions there are the consolidation source; after migration it documents the unified store. Reconcile in the build wave.
- v6 records Garmin's public API as closed and Polar/Wahoo/COROS as spec-only/stub — consistent with §5's mechanism notes.

---

## 10. Instrumentation (Rule #15)

Every inbound resolution emits a `print()` carrying the decision inputs + outcome: `provider`, `data_type`, `source_value`, resolved `canonical_value` or `bucket`, `match_kind`, `confidence`. Bar: if a provider value silently failed to map in prod, the logs alone must say which value, for which provider, and which bucket it fell to. Outbound push emits the `(session, provider, external_id, action=upsert|delete)` decision.

---

## 11. Open items (for Andy / later waves)

1. **Canonical metric registry ratification** (§2.3) — confirm the seed key list + units (Trigger #2).
2. **Canonical HR-zone anchor** (§2.4) — ratify the default anchor (%HRmax vs %HRR vs %LTHR/FTP) or confirm it stays a per-athlete Layer 4 concern with record-raw until then.
3. **Training-load model** — Polar `cardio_load`/TRIMP, Garmin acute load: bucket-2 now; do we mint a canonical load model? (Probably its own design.)
4. **Nutrition canonical model** — MyFitnessPal (food/macros) ties Layer 2E, which has no nutrition table today; canonical nutrition keys are a Wave-2 + Layer-2E question.
5. **Outbound anchor for Tier-2 fidelity** — confirm per-platform native formats at Wave-3b authoring (TrainingPeaks/Garmin/Zwift/Wahoo).
6. **Bucket-3 surfacing depth** — data/API contract here; UI build deferred (`Bucket3_InlineCompleted_Surfacing_Design`).

---

## 12. Wave plan (this spec is Wave 1)

- **Wave 1 (this doc):** canonical model (§2), bidirectional framework (§3), unified schema (§4), mechanism taxonomy (§5), seed inbound matrix (§6: Garmin strength+cardio, Polar/COROS wellness), authoring (§7), migration contract (§8). Plus `AIDSTATION_API_Spec` (#682 contract) and `ProviderTranslation_GarminStrength_679_Design` (#679).
- **Wave 2:** full inbound matrix — Strava, Whoop, Wahoo, Oura, MyFitnessPal (nutrition), RWGPS, TrainingPeaks, Zwift, Apple/Samsung/Google Health (SDK).
- **Wave 3a:** outbound Tier-1 calendar serializer (Google/Outlook/Apple).
- **Wave 3b:** outbound Tier-2 native workout serializers (TrainingPeaks/Garmin/Zwift/Wahoo).
- **Wave 4:** bucket-3 inline UI surfacing.
- **Wave 5:** API security & developer platform (#682 wave). **Wave 6:** MCP server.

---

## 13. Gut check (what might be missing / best argument against)

- **Biggest risk — outbound Tier-2 fidelity.** Each platform's native workout format is real, finicky work (TrainingPeaks structured-workout JSON, Zwift `.zwo` XML, Garmin workout API, Wahoo plans). Mediocre serialization writes exactly the "crap data" Andy ruled out. Mitigation: Tier-2 is its own wave with per-platform round-trip validation; calendars (Tier-1) ship first as the low-risk win.
- **Best argument against the generic value-map table:** a single wide table over per-provider tables can hide type errors and make per-provider constraints awkward. Counter: the scattered-dicts status quo is worse for accretion; the `canonical_kind` discriminator + seed-authoring workflow keeps it disciplined, and per-provider validity is enforced at authoring (HITL), not schema.
- **Replace + consolidate risk:** rewriting wired Polar/COROS ingest has regression surface even at zero rows. Mitigation: gated migration (§8), zero-row guard, instrumentation (§10).
- **Canonical-key churn:** if the API (#682) and this spec drift on key names, we redefine twice — the exact failure mode #681's comment warns about. Mitigation: §2 is the single definition; the API spec references it.
- **Did I model the right buckets?** The 3-bucket model is taken verbatim from #681 and confirmed against the issue; the asymmetry (2 dormant / 3 must-surface) is the subtle part and is encoded in §6.4.
