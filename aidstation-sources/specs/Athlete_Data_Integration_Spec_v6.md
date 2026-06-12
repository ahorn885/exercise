# Athlete Data Integration Spec — v6

**Version:** 6.0
**Status:** Draft v6. Cross-cutting spec — not a Layer N spec; follows its own structure rather than the 14-section node-spec depth standard (Control_Spec §8.3, post-v6 amendment).
**Last updated:** 2026-05-19 (v6: §7.6 gap-summary annotated with D-51 design-wave resolution — see `Layer1_D51_Design_v1.md` for the table-by-table storage design closing each §7.6 gap-row.)
**Supersedes:** `Athlete_Data_Integration_Spec_v5.md` (2026-05-16)
**Source decisions:**
- `L3_Discovery_Closing_Handoff_v1.md` §2.3–§2.5 (integration architecture, deployment timing, new spec doc)
- L3-Spec-Trio pre-step session 2026-05-13 (catalog reconciliation Option A, heat acclim derivation, PG-only, Garmin onto `provider_auth`)
- L3-Spec-Trio feedback round 2 (2026-05-13) — Garmin not live; new retention rule
- Reconciliation pass 2026-05-14 — single-repo correction; Garmin API access temporarily closed by Garmin → D-55 paused, integration architecture decision unchanged
- `D50_Phase1_Schema_Review_v1.md` (2026-05-14) — review of D-50 Phase 1 ship surfaced the SQLite-freeze override; Andy ratified retroactively (Option A) and chose to reaffirm the freeze going forward
- `V5_Implementation_PR13_Closing_Handoff_v1.md` (2026-05-16) — SQLite + TrueNAS retirement; freeze retired by definition since the path it was freezing no longer exists
**Cross-references** (all live in this repo):
- `DATABASE.md` (app schema source of truth; repo root)
- `Layer0_ETL_Spec_v7.md` (`layer0.*` schema source of truth; `aidstation-sources/`)
- `PROVIDERS_SCHEMA.md` (producer-side integration design; repo root)
- `HANDOFF-2026-05-13.md` and `HANDOFF-2026-05-13-stub-batch.md` (provider stub deployment playbooks; repo root)
- `L3-Discovery_Pre-Spec-Trio_Inventory` (schema dump informing this spec)
- `Layer1_D51_Design_v1.md` (2026-05-19) — D-51 design wave; closes the §7.6 gap summary with table-by-table storage design

## What changed in v6 vs v5

1. **§7.6 gap summary annotated with D-51 resolution.** The §7.6 "Gap summary — onboarding fields with no app-table home" bullet list documented the inventory of v5 §A-§L fields that needed new `public.*` storage. D-51 design wave (`Layer1_D51_Design_v1.md`, 2026-05-19) closes each gap-row with a specific table-by-table design — most §A-§L sections resolve to either new columns on `athlete_profile` or new sub-tables. §7.6 carries a new closing block enumerating the per-section design pointers. **Substantial schema infrastructure is already shipped** — D-58 + D-59 + D-60 + D-61 + D-66 closed the largest pieces (`athlete_profile_field_provenance`, `gym_profiles`, `locale_equipment_overrides`, `locale_toggle_overrides`, `account_nudges`, `race_events` + companions, `wellness_self_report`) so D-51's residual scope is narrower than originally framed in v5 §7.6 ("dozens of fields with no app-table home" → ~15 new columns + ~12 new tables, mostly small).

2. **No other changes.** §1, §2.1–§2.7, §3, §4, §5, §6, §7.1–§7.5, §8, §9, §10, §11, §12 byte-identical to v5. Field mappings, query signatures, retention rule, consumer regimes unchanged.

## What changed in v5 vs v4

1. **§2.5 SQLite freeze retired.** PR13 (2026-05-16, merge `5776cef`) stripped the SQLite path from the codebase entirely — `SQLITE_SCHEMA`, `_SQLITE_MIGRATIONS`, `init_sqlite`, `sqlite_path`, and all 13 `_is_postgres()` runtime guards across 6 route files + `athlete.py`. The freeze the §2.5 carve-out preserved is now moot: there is no `_SQLITE_MIGRATIONS` list to freeze. §2.5's body is retained as historical context (the D-50 Phase 1 carve-out narrative still explains why the SQLite block was inert during 2026-05-14 → 2026-05-16) but flagged **Retired** at the section header.

2. **D-54 status flipped.** v4 framed D-54 as the eventual sweep that would resolve the SQLite-block tension; D-54 ✅ Resolved 2026-05-16 (PR13). The phrasing in §2.5 referencing "the D-54 PG-only collapse sweeps it" is now a past-tense fact rather than a future plan.

3. **No other changes.** §1, §2.1–§2.4, §2.6–§2.7, §3, §4, §5, §6, §7, §8, §9, §10, §11, §12 byte-identical to v4. Field mappings, query signatures, retention rule, consumer regimes unchanged.

## What changed in v4 vs v3

1. **§2.5 SQLite freeze — D-50 Phase 1 carve-out.** The D-50 Phase 1 schema ship (2026-05-14, commit `909dc17`) added 147 lines + 7 ALTERs to `_SQLITE_MIGRATIONS` despite the v3 §2.5 freeze. Review (`D50_Phase1_Schema_Review_v1.md`) surfaced the override; Andy ratified retroactively. Runtime audit confirmed the SQLite block is inert when `DATABASE_URL` is set (the dev path Andy uses against Neon), so the lines have no operational cost. **The freeze remains in force going forward** — no further SQLite migrations. The D-50 block stays in place until the D-54 PG-only collapse sweeps it along with the rest of the SQLite path.

2. **No other changes.** §1, §2.1–§2.4, §2.6–§2.7, §3, §4, §5, §6, §7, §8, §9, §10, §11, §12 are byte-identical to v3. Field mappings, query signatures, retention rule, consumer regimes unchanged.

## What changed in v3 vs v2

1. **Single-repo reconciliation.** v1/v2 cross-refs said `PROVIDERS_SCHEMA.md` and `HANDOFF-2026-05-13*.md` "live in the Vercel-app codebase" as if it were a separate repository. Wrong — those files live in this repo at the root, alongside the v1 Flask app code (`app.py`, `init_db.py`, `routes/`, etc.) and the `aidstation-sources/` design track. Cross-refs updated. §1 producer-vs-consumer framing kept (it's still useful) but stripped of the "different codebase" implication.

2. **Garmin pause noted.** Garmin has temporarily closed new API access (per Andy 2026-05-14). The architectural decision in v2 §2.3 stands — drop `garmin_auth`, build Garmin onto `provider_auth` with `session_blob` — but **implementation is paused** until Garmin reopens. D-55 status flipped Deferred → Paused in `Project_Backlog_v12`. D-50 (the rest of `provider_auth` for Polar / Wahoo / COROS / etc.) is NOT paused.

3. **`PROVIDERS_SCHEMA.md` reconciled in same pass.** Pre-v3, that doc said *"`garmin_auth` itself stays as-is (legacy)"* — contradicting v2's drop plan. Reconciled in this v3 reconciliation pass so the two documents now agree on the target state (`garmin_auth` dropped, Garmin moves to `provider_auth` with `session_blob` once API access reopens).

No structural changes to §2 (other than the §2.3 Garmin reframe being slightly clarified), §3, §4, §5, §6, §7, §8, §9, §10, §11, §12. Field mappings, query signatures, retention rule (§2.7), and consumer regimes unchanged from v2.

## What changed in v2 vs v1

1. **Garmin reframed — not live, build from scratch.** v1 assumed Garmin was live ingestion and described a one-shot data migration from `garmin_auth` to `provider_auth`. Reality (per Andy 2026-05-13): the Garmin connector never functioned in production. There's no live data to migrate and no users to re-authenticate. §2.3 rewritten: drop migration narrative; Garmin is built onto `provider_auth` from scratch like any other new provider. The legacy `garmin_auth` table is still dropped (cleanup, not migration). D-55 reframed in Project_Backlog v11.

2. **No-user-preservation note.** Production data state: 1–2 test accounts only. Any ETL or schema migration can destroy and rebuild these accounts without concern. This removes the "breaking change for existing users" cost language that appeared throughout v1.

3. **New athlete-integration-data retention rule.** v1 had retention guidance only for `webhook_events` (90-day operational audit). It implicitly assumed athlete data tables (`polar_*`, `wahoo_*`, `coros_*`, FIT-derived data in `cardio_log` / `training_log` / `wellness_log`) were retain-indefinitely. New §2.7 codifies a "both conditions" rule: a record is retained until BOTH (a) a newer record of the same type exists AND (b) 90+ days have passed since the record was written. Either condition alone → retained. Designed for endurance athletes who may have only one A-race per year — pre-race performance data must survive a multi-month off-season.

No structural changes to §3, §4, §5, §6, §7, §8, §9, §10, §11, §12 beyond the Garmin-specific reframing and the retention reference. Field mappings, query signatures, and consumer regimes unchanged.

---

## 1. Purpose

Defines the consumer-side data model for AIDSTATION pipeline access to athlete integration data. Where `PROVIDERS_SCHEMA.md` (this repo, root) is the *producer* spec (what the app's integration layer writes to Neon), this is the *consumer* spec (what Layer 1 sourcing, Layer 3 nodes, and downstream layers see when they query that data). Both producer and consumer live in this repo — split is by role, not by codebase.

The spec also locks the integration architecture for AIDSTATION as a whole — single Neon DB, two schemas, Layer 1 as conceptual aggregation, no bridge — and forward-points to the Catalog Migration Plan that resolves the parallel-catalogs reality discovered during the L3-Spec-Trio pre-step.

This is a cross-cutting spec, not a per-layer node spec. It does not follow the 14-section node-spec depth standard (`Layer2C_Spec.md`). It is consumed by:
- The Layer 1 sourcing pattern (Control_Spec §3)
- Layer 3A's input contract (athlete state evaluation)
- Future Layer 4 plan-generation (when integration-derived load and recovery data feed plan adjustments)
- The query layer's function signatures (`q_layer3A_*`)

---

## 2. Architectural context

### 2.1 Single Neon Postgres database, two schemas

Both the Vercel app and the AIDSTATION pipeline run against one Neon Postgres database. Two schemas partition the data:

- **`layer0.*`** — platform reference data: sport rule sets, exercise database, equipment catalog, terrain types, recovery modalities, environmental modifiers, supplement vocabulary. Versioned per ETL load (`etl_version_set` pinning). Supersede-on-update — old versions remain queryable until garbage-collected.
- **`public.*`** — application tables: user identity and auth, athlete profile, training/cardio/wellness logs, body metrics, injuries, plans and plan items, equipment selections, coaching chat, integration tables (after deployment). Standard mutable rows with `created_at`/`updated_at`. No version stack.

This is documented in Control_Spec_v6 §2 (post-v6 amendment). Within this spec, the boundary is enforced as a hard rule: AIDSTATION pipeline reads both schemas (via the query layer); the app reads both schemas (post catalog migration — see §2.4).

### 2.2 Layer 1 is a conceptual aggregation, not a separate schema

There is no `layer1.*` schema. Layer 1 (athlete profile, per Athlete_Onboarding_Data_Spec_v3) is assembled at runtime by the query layer from:

- **`public.*` app tables** — `athlete_profile`, `body_metrics`, `wellness_self_report`, `injury_log`, `training_log`, `cardio_log`, `locale_profiles`, `locale_equipment`, etc.
- **`public.*` integration tables** — `provider_auth`, `webhook_events`, `polar_*`, `wahoo_*`, `coros_*` (after deployment).
- **Onboarding-specific fields** — fields named in `Athlete_Onboarding_Data_Spec_v3.md` that don't yet have a home in `public.*`. These get added to existing tables (preferred) or new onboarding-specific tables as the spec is realized.

The Layer 1 payload is a typed Python dataclass (or equivalent) populated by query-layer functions; nothing is materialized to a `layer1` schema.

### 2.3 Garmin onto `provider_auth` (built from scratch); legacy `garmin_auth` dropped as cleanup

`PROVIDERS_SCHEMA.md` originally exempted `garmin_auth` from the new generic pattern on the basis that the `garth` library uses username/password (not OAuth) and didn't fit. **This spec reverses that decision.** Garmin gets a row in `provider_auth` like every other provider.

**Garmin status reality (confirmed 2026-05-13):** the Garmin connector was scoped and partially built but never functioned in production. There is no live ingestion to preserve and no migration to perform. Garmin is built onto `provider_auth` from scratch as a normal provider; the legacy `garmin_auth` table exists in `init_db.py` but has no production data to carry forward. It is dropped as cleanup, not as a migration step.

**Garmin implementation paused (2026-05-14):** Garmin has temporarily closed new API access. We cannot build a working Garmin integration until access reopens. The architectural decision above stands — drop `garmin_auth`, build onto `provider_auth` with `session_blob` — but D-55 implementation is paused. D-50 (the rest of `provider_auth` for Polar, Wahoo, COROS, etc.) is unaffected and proceeds.

The `garth` session JSON blob — what would have lived in `garmin_auth.garth_session` had the connector functioned — is stored on the unified `provider_auth` row. Two options for where:

- **Option I (recommended): Add `session_blob TEXT` to `provider_auth`.** Non-OAuth providers stash their session state here; OAuth providers leave it NULL. Cleaner separation than overloading `access_token`.
- **Option II: Reuse `access_token`** for the session blob on Garmin rows. Smaller schema change; some semantic awkwardness.

Recommend Option I. See §5.1 below for the proposed `provider_auth` columns including `session_blob`.

**No-user-preservation note (applies to this entire spec, not just §2.3).** Production user state at the time of this spec is 1–2 test accounts. Any ETL, schema migration, or table drop can destroy and rebuild these accounts without concern. v1's language about "breaking change for existing Garmin-connected users — they re-authenticate once" is moot — there are no Garmin-connected users.

**Deployment order (now build-from-scratch, not migration):**

1. Deploy `provider_auth` (with `session_blob` column) and `webhook_events` (per §5).
2. Drop `garmin_auth` from `init_db.py`'s migration list. Drop the table from the deployed database.
3. Build `routes/garmin.py` and `garmin_connect.py` to read/write `provider_auth` from the start. (Existing code referencing `garmin_auth` is presumably broken; treat it as scaffold rather than working integration.)
4. Wire `garth` session capture/refresh against `provider_auth.session_blob`.

Backlog row D-55 captures the work, reframed in Project_Backlog v11 as "build" rather than "migrate."

### 2.4 Catalog migration (Option A) — long-term target state

**Current state.** The Vercel app reads catalogs (`exercise_inventory`, `equipment_items`, `exercise_equipment`, `training_modalities`) exclusively from `public.*`. The AIDSTATION ETL pipeline populates parallel catalogs in `layer0.*` (different shape — `TEXT[]` arrays for `equipment`, `muscles_worked`, etc., versus scalar TEXT in `public.*`). These two catalogs are not synced; they overlap but diverge.

**Target state (Option A, confirmed 2026-05-13).** The app migrates to read all catalogs from `layer0.*`. The AIDSTATION pipeline is the source of truth; the app is a consumer. `public.*` catalogs are deprecated and eventually dropped.

The migration is non-trivial: route-file FROM clauses change, type-compat work is required (the app currently treats `equipment` as a comma-separated TEXT string; it must learn `TEXT[]`), and the `tag → canonical_name` mapping must be specified for equipment because `locale_equipment` references `tag` and there's no current join key into `layer0.equipment_items`.

**This spec does not own the migration.** It is captured in Backlog row D-52 with `Catalog_Migration_Plan.md` as the placeholder destination doc. Until that migration is complete, this spec describes the *target* state where the AIDSTATION pipeline does not read `public.*` catalogs at all — but acknowledges in §8 that the current-state app continues to use `public.*` and must be supported through the transition.

**Implication for this spec:** The field-mapping section (§7) assumes the target state — where 3A consumes `layer0.*` for any catalog-resolution needs and `public.*` for per-user log/profile data only.

### 2.5 PG-only — SQLite backend deprecated [RETIRED 2026-05-16, PR13]

**🟢 Retired by definition (v5, 2026-05-16).** PR13 (`5776cef`) stripped the SQLite path from the codebase entirely — `SQLITE_SCHEMA`, `_SQLITE_MIGRATIONS`, `init_sqlite`, `sqlite_path`, all `_is_postgres()` runtime guards. There is no `_SQLITE_MIGRATIONS` list to freeze. D-54 ✅ Resolved. The section body below is preserved as historical context for anyone tracing why the D-50 Phase 1 SQLite block existed in the 2026-05-14 → 2026-05-16 window; it has no forward-looking force.

---

*Historical (v3 — v4):* Confirmed 2026-05-13. The dual-backend pattern in `init_db.py` (parallel `_PG_MIGRATIONS` and `_SQLITE_MIGRATIONS` lists, dual-type strategy in DATABASE.md §3) collapses to PG-only as part of the catalog migration (Option A). The `layer0.*` schema uses PG-specific types (`TEXT[]` arrays, server-side defaults via `NOW()`) that SQLite cannot represent without lossy conversion.

*Historical implication:* Integration table CREATE statements use PG types directly. No SQLite variants are specified. The `_SQLITE_MIGRATIONS` list in `init_db.py` is frozen — no new entries — and eventually removed as part of the Option A migration.

Backlog row D-54 ✅ Resolved 2026-05-16 (PR13).

*Historical documented exception (v4, 2026-05-14):* The D-50 Phase 1 ship (commit `909dc17`) added 147 lines + 7 ALTERs to `_SQLITE_MIGRATIONS` covering `provider_auth`, `webhook_events`, the four `polar_*`, `wahoo_plans`, the three `coros_*`, and the seven `cardio_log`/`training_log` foreign-id columns. This was an override of the freeze and should have been a stop-and-ask under CLAUDE.md triggers #5 and #8. Surfaced in `D50_Phase1_Schema_Review_v1.md`. Andy ratified retroactively under Option A:

- The override stayed in place (the lines were inert when `DATABASE_URL` was set, which was the dev path).
- The freeze rule remained in force for all subsequent integration tables and any other schema additions. No further `_SQLITE_MIGRATIONS` entries.
- The D-50 SQLite block aged out with the rest of the SQLite path at PR13 — no separate cleanup needed.

### 2.6 Heat acclimation state — derived, not stored

Confirmed 2026-05-13. Heat acclimation state (referenced in Control_Spec_v5 §3 line 160 as a 2E input) is **not** stored as a profile field. It is derived at read time from:

- `public.conditions_log.temp_f` history (the athlete's recent training conditions)
- Future: integration-sourced ambient temperature, sleep environment temp, etc. (when those data shapes are pinned down)
- §J Locale Profile climate context (locale climate seasonality)

The derivation logic is owned by Layer 2E (or its consumer in plan-gen) and is not in scope here. Backlog row D-53 captures the derivation spec.

**Implication for this spec:** No new column or table for heat acclim state. Field mapping in §7 omits it.

### 2.7 Retention policy for athlete integration data

Athlete training and physiological data — once ingested from a provider or computed from FIT files — is **retained until BOTH of the following are true:**

1. **A newer record of the same logical type exists** for the same athlete (where "same type" is defined per-table; see below).
2. **At least 90 days have elapsed** since the record was originally written.

If either condition alone is false, the record is retained. Practical consequence: an old record is purged only after it has been superseded by a newer comparable record AND has aged past 90 days. A 5-year-old record with no successor stays. A 2-day-old record with a successor stays for 90 days.

**Motivation.** AIDSTATION serves endurance athletes whose primary competition cycle may be annual — one A-race per year is common in ultra running, expedition adventure racing, marathon paddle sports, and long-course triathlon. Pre-race performance baselines and the training data behind them are the highest-value reference for next year's plan generation. A blanket 90-day TTL would purge July 2025 race-prep data before the July 2026 plan begins.

**Per-table "same logical type" definitions:**

| Table | "Same type" key | Notes |
|---|---|---|
| `polar_sleep`, `coros_daily_summary` (sleep block), `whoop_sleep` | (user_id, date) | One sleep record per night per user. Each night is a distinct record; no two share a "type." Effectively retain-indefinitely. |
| `polar_nightly_recharge`, `coros_hrv_samples` (daily aggregate) | (user_id, date) | Same — daily aggregate, no two share a type. Retain-indefinitely in practice. |
| `polar_cardio_load`, `coros_daily_summary` (training load block) | (user_id, date, metric_name) | Daily load score; today's value doesn't supersede yesterday's. Retain-indefinitely. |
| `wahoo_workouts`, `garmin_workouts` (activities) | (user_id, provider_activity_id) | Each activity is unique; no superseding. Retain-indefinitely. |
| Per-athlete summary or derived aggregates (e.g., 28-day rolling load, latest VO2max estimate) | (user_id, metric_name) | Today's rolling-28d window supersedes yesterday's. Both-conditions rule applies cleanly: retain until newer + 90+ days old. |
| `provider_auth` | (user_id, provider) | Not athlete data; not subject to this rule. Lifecycle is auth-state-driven. |
| `webhook_events` | n/a | Operational audit trail; different concern. Existing §4.2 90-day rule stands. |

For tables not enumerated above, default to retain-indefinitely until per-table policy is specified during that table's deployment spec.

**Implementation note.** This is a policy, not a deployment requirement. No pruning cron is required for v1 deployment of integration tables; retain-indefinitely is the safe default. The both-conditions rule becomes operative only when (a) per-table policy is specified AND (b) a cron is scheduled. Document any per-table retention deviation in the table's deployment spec.

**Cross-reference.** This rule is consumed by Layer 3A's `recent_trajectory` calculations (Layer3_3A_Spec.md §3 input contract) — 3A may read data points well outside a 90-day window for an athlete with sparse historical signal. The rule guarantees that data remains available.

---

## 3. Provider list and stub status

Status definitions:

- **Live ingestion** — production code in `routes/*.py` reads from provider APIs and writes to the DB.
- **Stub deployed** — OAuth callback or webhook stub is deployed (returns 200/501 as appropriate), no data ingestion logic, no DB writes.
- **Spec only** — schema and integration approach are documented; no code shipped.
- **Not started** — listed in roadmap but not yet designed.

| Provider | Status | Auth model | Data shape | Notes |
|---|---|---|---|---|
| Garmin | Scaffold only (never functioned); build onto `provider_auth` from scratch | `garth` session (user/pass) | FIT files: cardio activities + wellness samples (planned) | D-55 build onto `provider_auth`; legacy `garmin_auth` dropped as cleanup |
| Polar | Spec only | OAuth (no refresh; tokens don't expire) | Sleep, Nightly Recharge (ANS charge / HRV RMSSD / breathing), Cardio Load (daily TRIMP / acute/chronic / strain), continuous HR (opt-in 24/7, downsampled to 1-min) | `PROVIDERS_SCHEMA.md` §5.2 |
| Wahoo | Spec only | OAuth (refresh every ~2 hr) | Plans pushed via POST /v1/plans (mirrors `garmin_workouts`); inbound activities TBD | Per-user `webhook_token` rotates on every event |
| COROS | Spec only | OAuth (refresh never expires; access valid 30 days) | Daily summary (rhr / calories / steps / overnight HRV / sleep summary), HRV samples (timestamp/hrv/hr triples), plans (mirrors `wahoo_plans`) | Uses `labelId` not `id` for plan IDs |
| Ride With GPS | Stub deployed | OAuth | Trip metadata + activity ingestion → `cardio_log` | No sub-table planned; data flows into `cardio_log` only |
| Strava | Stub deployed | OAuth | TBD per Strava API (activities, segments, athlete profile) | Data shape filling deferred — D-48 |
| Whoop | Stub deployed | OAuth | TBD per Whoop API (recovery, strain, sleep, HRV) | Data shape filling deferred — D-48 |
| TrainingPeaks | Stub deployed | OAuth | Plan import/export (mirrors `garmin_workouts` / `wahoo_plans`) | Wave-2 priority |
| Zwift | Stub deployed | OAuth | Indoor ride activities → `cardio_log` | Wave-2; data flow TBD |
| Apple Health | Not started | iOS-side (HealthKit) | Comprehensive (sleep, HR, workouts, etc.) | Requires iOS companion app; out of scope for v1 spec |
| Samsung Health | Not started | Android-side | Similar to Apple Health | Out of scope for v1 spec |

**Wave-1 priority for AIDSTATION pipeline consumers:** Garmin, Polar, COROS, Wahoo. These four cover the strength/wellness/recovery axis (Polar + COROS for HRV-driven recovery, Garmin for training load, Wahoo for plan push) and unlock the highest-confidence 3A `recent_trajectory` outputs. Garmin is built from scratch — there is no existing live ingestion (see §2.3).

**Wave-2:** Strava, Whoop, TrainingPeaks, Zwift, RWGPS.

**Out of scope for current spec:** Apple Health, Samsung Health (require platform-specific iOS / Android clients beyond the Flask/Vercel server architecture).

---

## 4. Generic integration tables

Two tables serve all providers. Schemas reconstructed from `PROVIDERS_SCHEMA.md` §5.1 plus the `session_blob` addition per §2.3 of this spec.

### 4.1 `provider_auth`

Per-user, per-provider credentials and registration state.

```sql
CREATE TABLE IF NOT EXISTS provider_auth (
    id                SERIAL PRIMARY KEY,
    user_id           INTEGER NOT NULL REFERENCES users(id),
    provider          TEXT NOT NULL,
        -- Matches a slug in oauth_callbacks._PROVIDERS plus 'garmin' for the
        -- migrated garth-based connector.
    access_token      TEXT,
        -- OAuth access token. NULL for non-OAuth providers (Garmin).
    refresh_token     TEXT,
        -- OAuth refresh token. NULL for Polar (tokens don't expire) and
        -- Garmin. Rotates for Wahoo; valid 30d for COROS.
    token_expires_at  TIMESTAMP,
        -- Polar: NULL. Wahoo: now + 2h. COROS: now + 30d.
        -- Garmin: NULL.
    session_blob      TEXT,
        -- Non-OAuth providers stash session state here. Garmin: the garth
        -- session JSON. OAuth providers: NULL.
    provider_user_id  TEXT,
        -- Polar: x_user_id. Wahoo: user.id. COROS: openId. Garmin: NULL
        -- (the garth session contains the identifier).
    scopes            TEXT,
        -- Space-separated scopes as returned by the provider.
    webhook_token     TEXT,
        -- Wahoo: per-user webhook_token, rotates on every event.
    status            TEXT,
        -- active / revoked / error / pending_backfill / migrating
        -- 'migrating' is used during the garmin_auth → provider_auth one-shot.
    registered_at     TIMESTAMP,
        -- Polar: timestamp of successful POST /v3/users registration.
        -- Other providers: NULL until first successful auth.
    created_at        TIMESTAMP DEFAULT NOW(),
    updated_at        TIMESTAMP DEFAULT NOW(),
    UNIQUE (user_id, provider)
);

CREATE INDEX IF NOT EXISTS provider_auth_status_idx
    ON provider_auth (status)
    WHERE status IN ('error', 'pending_backfill');
```

**Diff from `PROVIDERS_SCHEMA.md` §5.1:** Adds `session_blob TEXT` for Garmin migration. Adds the partial index on `status` for error/backfill scans. Other columns unchanged.

**Cascade-delete placement:** `provider_auth` joins the user-data cascade chain in `routes/admin.py:_delete_user_and_data` immediately before the `users` delete itself, alongside other user-scoped catalog tables. FK order doesn't constrain placement here (no FKs from app tables point to `provider_auth`); convention is to group identity/auth tables together.

**Open: webhook_token rotation strategy.** Wahoo rotates `webhook_token` on every event. Two patterns:

- **Pattern A: UPSERT on every event** — every successful event handler writes the current `webhook_token` back to `provider_auth`, even if it's identical to the prior value. Idempotent; one DB write per event.
- **Pattern B: UPSERT only when rotated** — webhook handler compares incoming token to stored; UPSERT only on mismatch. Saves a write per event but adds a read.

Recommend Pattern A. The write cost is negligible (single row, indexed); Pattern B's correctness depends on the comparison logic being right, which is one more thing to get wrong.

### 4.2 `webhook_events`

Append-only audit log and dedup table.

```sql
CREATE TABLE IF NOT EXISTS webhook_events (
    id                SERIAL PRIMARY KEY,
    provider          TEXT NOT NULL,
    event_type        TEXT,
    provider_user_id  TEXT,
    entity_id         TEXT,
        -- Provider-side workout/exercise/route ID. Used for dedup.
    user_id           INTEGER REFERENCES users(id),
        -- NULL while pending dispatch resolution. Populated once the
        -- provider_user_id is mapped to a local user.
    payload           TEXT,
        -- Raw JSON body as received. PG could use JSONB for richer queries;
        -- TEXT chosen for portability with the dispatch logic.
    signature_ok      BOOLEAN,
    received_at       TIMESTAMP DEFAULT NOW(),
    processed_at      TIMESTAMP,
        -- NULL = pending. Non-NULL = dispatched (success or error).
    error             TEXT
);

CREATE INDEX IF NOT EXISTS idx_webhook_events_lookup
    ON webhook_events (provider, provider_user_id, entity_id, event_type);

CREATE INDEX IF NOT EXISTS idx_webhook_events_pending
    ON webhook_events (received_at)
    WHERE processed_at IS NULL;
```

**Open: retention strategy.** The table grows monotonically. Recommend pruning `processed_at IS NOT NULL AND received_at < NOW() - INTERVAL '90 days'` on a daily cron. Captured as backlog item.

**Open: signature_ok semantics.** Convention: `signature_ok = FALSE` rows are written for audit but never dispatched (the event handler returns 401 without processing). The row exists so signature failures are visible in the audit log, not just dropped silently. Capture in handler implementation.

**Cascade-delete placement:** `webhook_events` rows with `user_id IS NOT NULL` are deleted as part of the user-cascade. Rows with `user_id IS NULL` (unresolved-dispatch state) are left alone — they're orphaned events not associated with any user.

---

## 5. Per-provider integration tables

Schemas reconstructed from `PROVIDERS_SCHEMA.md` §5.2 plus column inference from each provider's documented payload. Where the producer spec did not pin every column ("Polar Sleep stages stored as JSON column"), this spec proposes column shapes that the next deployment iteration can confirm against actual API responses.

All tables are user-scoped. All include the user-cascade FK. All use `IF NOT EXISTS` for idempotency.

### 5.1 Polar tables

#### `polar_sleep`

```sql
CREATE TABLE IF NOT EXISTS polar_sleep (
    id                  SERIAL PRIMARY KEY,
    user_id             INTEGER NOT NULL REFERENCES users(id),
    date                TEXT NOT NULL,                  -- ISO 8601 date
    sleep_start_time    TIMESTAMP,
    sleep_end_time      TIMESTAMP,
    total_sleep_min     INTEGER,
    continuity          REAL,                           -- Polar's 1-5 score
    light_sleep_min     INTEGER,
    deep_sleep_min      INTEGER,
    rem_sleep_min       INTEGER,
    unknown_sleep_min   INTEGER,
    stages_json         TEXT,                           -- Detailed per-stage timeline
    raw_payload         TEXT,                           -- Audit
    fetched_at          TIMESTAMP DEFAULT NOW(),
    UNIQUE (user_id, date)
);
```

**Note:** Polar sleep records can be updated by Polar's servers post-fact (re-analysis after morning sync). This spec accepts that — UPSERT on `(user_id, date)` is the write pattern. Consumers must accept that today's `polar_sleep` row may change in the next 24 hours.

#### `polar_nightly_recharge`

```sql
CREATE TABLE IF NOT EXISTS polar_nightly_recharge (
    id                      SERIAL PRIMARY KEY,
    user_id                 INTEGER NOT NULL REFERENCES users(id),
    date                    TEXT NOT NULL,
    ans_charge              INTEGER,                    -- Polar's autonomic nervous system charge score
    ans_charge_status       TEXT,                       -- enum (very_low / low / normal / high / very_high)
    hrv_rmssd_ms            REAL,
    breathing_rate          REAL,
    recovery_indicator      TEXT,
    raw_payload             TEXT,
    fetched_at              TIMESTAMP DEFAULT NOW(),
    UNIQUE (user_id, date)
);
```

#### `polar_cardio_load`

```sql
CREATE TABLE IF NOT EXISTS polar_cardio_load (
    id                  SERIAL PRIMARY KEY,
    user_id             INTEGER NOT NULL REFERENCES users(id),
    date                TEXT NOT NULL,
    daily_load          REAL,                           -- TRIMP score
    acute_load          REAL,                           -- 7-day average
    chronic_load        REAL,                           -- 28-day average
    cardio_load_status  TEXT,                           -- detraining / maintaining / productive / overreaching
    strain              REAL,
    raw_payload         TEXT,
    fetched_at          TIMESTAMP DEFAULT NOW(),
    UNIQUE (user_id, date)
);
```

**Note for consumers:** `acute_load / chronic_load` is Polar's ACWR equivalent. AIDSTATION's combined-load ACWR (per-discipline + cross-discipline) computed by 3A may differ — Polar's load is HR-derived and single-source. Don't substitute directly; treat Polar's numbers as one input among many.

#### `polar_continuous_hr_samples`

```sql
CREATE TABLE IF NOT EXISTS polar_continuous_hr_samples (
    id              SERIAL PRIMARY KEY,
    user_id         INTEGER NOT NULL REFERENCES users(id),
    timestamp_ms    BIGINT NOT NULL,
    heart_rate      INTEGER,
    UNIQUE (user_id, timestamp_ms)
);

CREATE INDEX IF NOT EXISTS idx_polar_hr_user_time
    ON polar_continuous_hr_samples (user_id, timestamp_ms);
```

**Note:** Opt-in only. Downsampled to 1-minute resolution per Polar's API contract.

### 5.2 Wahoo tables

#### `wahoo_plans`

```sql
CREATE TABLE IF NOT EXISTS wahoo_plans (
    id                      SERIAL PRIMARY KEY,
    user_id                 INTEGER NOT NULL REFERENCES users(id),
    plan_item_id            INTEGER REFERENCES plan_items(id),
    wahoo_plan_id           TEXT,
    wahoo_workout_id        TEXT,
    external_id             TEXT,
    provider_updated_at     TIMESTAMP,
    status                  TEXT,                       -- pushed / completed / cancelled / error
    push_payload            TEXT,                       -- The body we sent
    created_at              TIMESTAMP DEFAULT NOW(),
    updated_at              TIMESTAMP DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_wahoo_plans_plan_item
    ON wahoo_plans (plan_item_id);
```

**Note:** This is the outbound push path. Inbound Wahoo activities (rides synced from a Wahoo head unit) flow into `cardio_log` with `cardio_log.wahoo_workout_id` set; no separate `wahoo_activities` table.

### 5.3 COROS tables

#### `coros_daily_summary`

```sql
CREATE TABLE IF NOT EXISTS coros_daily_summary (
    id                  SERIAL PRIMARY KEY,
    user_id             INTEGER NOT NULL REFERENCES users(id),
    happen_day          TEXT NOT NULL,                  -- COROS field name (ISO date)
    rhr                 INTEGER,
    calories            INTEGER,
    steps               INTEGER,
    ppg_hrv             INTEGER,                        -- overnight HRV
    sleep_avg_hr        INTEGER,
    sleep_start_ms      BIGINT,
    sleep_end_ms        BIGINT,
    raw_payload         TEXT,
    fetched_at          TIMESTAMP DEFAULT NOW(),
    UNIQUE (user_id, happen_day)
);
```

#### `coros_hrv_samples`

```sql
CREATE TABLE IF NOT EXISTS coros_hrv_samples (
    id              SERIAL PRIMARY KEY,
    user_id         INTEGER NOT NULL REFERENCES users(id),
    timestamp_s     BIGINT NOT NULL,
    hrv             INTEGER,
    hr              INTEGER,
    UNIQUE (user_id, timestamp_s)
);
```

#### `coros_plans`

```sql
CREATE TABLE IF NOT EXISTS coros_plans (
    id              SERIAL PRIMARY KEY,
    user_id         INTEGER NOT NULL REFERENCES users(id),
    plan_item_id    INTEGER REFERENCES plan_items(id),
    coros_label_id  TEXT,                               -- COROS uses labelId not id
    push_payload    TEXT,
    status          TEXT,
    created_at      TIMESTAMP DEFAULT NOW(),
    updated_at      TIMESTAMP DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_coros_plans_plan_item
    ON coros_plans (plan_item_id);
```

### 5.4 Garmin (build-from-scratch)

No new per-provider table for Garmin — existing `garmin_workouts` and `wellness_log` schemas remain as the deployment targets when the connector is built. The only schema change is the `garmin_auth` → `provider_auth` cleanup per §2.3 (drop the legacy table; build new code against `provider_auth` with `session_blob`). No production data to preserve.

### 5.5 Strava / Whoop — TBD

Schemas not specified at v1. Strava activity data may flow into `cardio_log` only (with `cardio_log.strava_activity_id`) if the activity shape fits; Whoop recovery/strain/sleep data may need per-provider tables analogous to Polar. Backlog row D-48 tracks the deferred design.

### 5.6 RWGPS

No per-provider table. Trip metadata flows into `cardio_log` with `cardio_log.rwgps_trip_id` set.

---

## 6. New columns on existing app tables

Per `PROVIDERS_SCHEMA.md` §5.3. Adding foreign-id columns to `cardio_log` and `training_log` for dedup against provider re-syncs.

| Table | Column | Type | Source provider | Use |
|---|---|---|---|---|
| `cardio_log` | `polar_exercise_id` | TEXT | Polar | Activity dedup; backref to Polar |
| `cardio_log` | `wahoo_workout_id` | TEXT | Wahoo | Activity dedup; backref to Wahoo |
| `cardio_log` | `coros_label_id` | TEXT | COROS | Activity dedup; backref to COROS |
| `cardio_log` | `rwgps_trip_id` | TEXT | Ride With GPS | Trip dedup |
| `cardio_log` | `strava_activity_id` | TEXT | Strava (TBD) | Activity dedup — added at Strava integration time |
| `training_log` | `polar_exercise_id` | TEXT | Polar | Strength-session dedup if Polar exports strength activities |
| `training_log` | `wahoo_workout_id` | TEXT | Wahoo | Strength-session dedup |
| `training_log` | `coros_label_id` | TEXT | COROS | Strength-session dedup |

**Migration:**

```sql
ALTER TABLE cardio_log ADD COLUMN IF NOT EXISTS polar_exercise_id TEXT;
ALTER TABLE cardio_log ADD COLUMN IF NOT EXISTS wahoo_workout_id TEXT;
ALTER TABLE cardio_log ADD COLUMN IF NOT EXISTS coros_label_id TEXT;
ALTER TABLE cardio_log ADD COLUMN IF NOT EXISTS rwgps_trip_id TEXT;
-- strava_activity_id deferred until Strava integration designed
ALTER TABLE training_log ADD COLUMN IF NOT EXISTS polar_exercise_id TEXT;
ALTER TABLE training_log ADD COLUMN IF NOT EXISTS wahoo_workout_id TEXT;
ALTER TABLE training_log ADD COLUMN IF NOT EXISTS coros_label_id TEXT;
```

**Note on RWGPS asymmetry:** `rwgps_trip_id` only on `cardio_log`. RWGPS is cycling-only and doesn't push strength activities. Consistent with `PROVIDERS_SCHEMA.md`.

---

## 7. Field mapping — onboarding fields to data sources

This is the largest section. For each Athlete_Onboarding_Data_Spec_v3 field that can be sourced from integration data or app log tables (not just self-report), this maps the source.

**Convention:**

- *Self-report only* — no integration source. Onboarding form is the only input.
- *Self-report at onboarding; integration-derived ongoing* — initial seed from the onboarding form; post-launch, the query layer derives the field from log/integration tables continuously.
- *Integration-only* — the field has no athlete-facing onboarding equivalent and is derived purely from integration data.

The "Source today" column reflects the current state (pre-integration-deployment) — i.e., what Layer 3A sees against the deployed schema. The "Source post-integration" column reflects the state after the Wave-1 deployment (Polar/COROS/Wahoo plus the new columns above).

### 7.1 Section C — Training History & Fitness Baseline

| Field | Type | Source today | Source post-integration |
|---|---|---|---|
| Years of Structured Training | Integer | `athlete_profile` (new column needed — D-51) | Same |
| Primary Sport | Single-select | `athlete_profile.primary_sport` | Same |
| Secondary Sports / Disciplines | Multi-select | (new table needed — D-51) | Same |
| Discipline Weighting | Per-discipline % | (new table needed — D-51) | Same |
| Current Weekly Training Volume | Number + breakdown | Self-report at onboarding; ongoing from `SUM(cardio_log.duration_min) + SUM(training_sessions.duration)` over rolling 7d | Same query; plus `polar_cardio_load.daily_load` cross-reference; plus per-discipline breakdown via `cardio_log.activity` aggregation |
| Peak Historical Weekly Volume | Number + year | Self-report only | Self-report only |
| Longest Event Completed | Text | Self-report only | Self-report only |
| Most Recent Race Results | Structured list | `cardio_log` filtered by activity flag (TBD: needs `cardio_log.is_race BOOLEAN` — new column D-56) | Same; plus `polar_*` / `coros_*` activity-level data when sourced |
| Training Consistency (12 mo) | Number + cause | Self-report; can be derived from `cardio_log.date` gap analysis | Same; provider activity gaps reinforce confidence |
| Pack Load Training History | Pack Training Record | Self-report only (no integration source for pack weight) | Same |
| Previous Coaching/Plans | Single-select | Self-report only | Same |

**Note on Current Weekly Training Volume:** The integration confidence improves post-Wave-1. Pre-integration, the query depends on whether the athlete logged activities (manual or FIT upload). Post-integration, Polar/Wahoo/COROS push activities directly. Confidence tag on 3A's `recent_trajectory.confidence` reflects this — drops to `low` when self-reported volume diverges from logged volume by >25%.

### 7.2 Section D — Discipline-Specific Baselines

#### D.1 Running

| Field | Source today | Source post-integration |
|---|---|---|
| Easy Run Pace | Self-report; can be derived from `cardio_log.avg_pace` filtered by HR Z2 | Same; plus Polar HR Z2 from activity samples |
| Recent Race Paces (5K/10K/HM/Mar) | `cardio_log.avg_pace` filtered to race activities | Same; plus provider activities |
| Trail Running Experience | Self-report | Self-report (terrain category isn't reliably derived from GPS) |
| Downhill Running Adaptation | Self-report; partial derivation possible from `cardio_log.elev_loss_ft / duration` | Same |
| Vertical Gain Tolerance | `SUM(cardio_log.elev_gain_ft)` over rolling 7d | Same; plus provider data with higher fidelity |
| Night Running Experience | Self-report; can be derived from `cardio_log.start_time` if collected (TBD column D-56) | Same |
| Gut Training History | Self-report only | Self-report only |

#### D.2 Cycling

| Field | Source today | Source post-integration |
|---|---|---|
| Bike Types Available | Self-report; lives in `locale_equipment` joined to `equipment_items` filtered to cycling category | Same; post-Option-A migration: `locale_equipment.equipment_id → layer0.equipment_items` |
| MTB Technical Skill | Self-report only | Same |
| Longest Ride (12 mo) | `MAX(cardio_log.distance_mi)` filtered to cycling activities last 12 mo | Same |
| Saddle Endurance | Self-report only | Same |
| Aero Position Endurance | Self-report only | Same |

#### D.3-D.7 (Swimming, Paddling, Skiing, Navigation, Technical)

Similar pattern. Most fields are self-report; volume / longest-session fields derive from `cardio_log` filtered by activity type. Tech disciplines (rock climbing, abseiling, fencing, shooting) are entirely self-report — no provider data shape covers them.

**General rule:** activity-volume fields derive from `cardio_log` (or `polar_*`/`coros_*` post-integration); experience/skill fields are self-report only.

### 7.3 Section E — Strength, Core & Balance Benchmarks

**All fields are manual entry only.** No integration source. Per the spec: "Manual entry only — these don't FIT-fill or Connected-Service-fill."

Note that `training_log` does store strength-session actuals, but the benchmark fields (Front plank hold time, Push-ups max single set, etc.) are calibration tests, not workout logs. They live in their own onboarding-result fields (TBD column or table — D-51).

### 7.4 Section F — Performance Testing Baselines

| Field | Source today | Source post-integration |
|---|---|---|
| HRmax | Self-report; FIT-fillable from cardio_log max_hr aggregates | Same; plus `polar_*` HR aggregates |
| Lactate Threshold HR | Self-report or lab test | Same |
| VO2max Estimate | Self-report; FIT-fillable | Same; plus integration if provider exposes |
| Cycling FTP | Self-report (TT/ramp test result) | Same; plus future provider integration (Wahoo's FTP API) |
| Running Threshold Pace | Self-report (TT result) | Same |
| Critical Swim Speed (CSS) | Self-report (TT result) | Same |

### 7.5 Section I — Lifestyle & Recovery

| Field | Source today | Source post-integration |
|---|---|---|
| Average Nightly Sleep | `wellness_self_report.sleep_hours` (1+ records) | Plus `polar_sleep.total_sleep_min`, `coros_daily_summary` sleep fields, Garmin `wellness_log` sleep entries |
| Work / Life Stress Level | Self-report only | Plus `polar_nightly_recharge.ans_charge_status` as a derived signal (informative, not a replacement) |
| Dietary Pattern | Self-report only | Self-report only |
| Current Supplement Protocol | Self-report only | Self-report only |
| Caffeine Tolerance & Strategy | Self-report only | Self-report only |
| Altitude Acclimatization History | Self-report; partial derivation possible from `cardio_log` activity locations with elevation | Same |

**Note on sleep signal:** Post-integration, the query layer can return both self-reported sleep (`wellness_self_report.sleep_hours`) and provider-measured sleep (`polar_sleep.total_sleep_min` / `coros_daily_summary`). 3A may need both — self-report captures subjective quality; provider measures objective duration. These should be exposed as separate fields, not collapsed.

### 7.6 Gap summary — onboarding fields with no app-table home

The following onboarding-spec fields have no current `public.*` storage. They must be added (Backlog D-51) before Layer 1 v3 sourcing can resolve them.

**§A Demographics** — most fields fit in `athlete_profile` already. Missing: A.1 Disclosures (acknowledgment timestamps).

**§B Health Conditions** — `injury_log` covers injuries but not chronic conditions. A new `health_conditions_log` table is likely needed, parallel in shape to `injury_log`.

**§C Training History** — Years of Structured Training, Secondary Sports list, Discipline Weighting, Peak Historical Volume, Longest Event Completed, Pack Load Training History, Previous Coaching all need new fields/tables.

**§D Discipline-Specific Baselines** — every "experience / skill" field needs storage. The activity-volume fields derive from `cardio_log` and don't need new columns.

**§E Strength Benchmarks** — All nine fields need storage (likely a single onboarding-benchmarks table or a JSONB column on `athlete_profile`).

**§F Performance Testing Baselines** — HRmax, LT HR, VO2max are partially on `body_metrics`; FTP, Running Threshold Pace, CSS need new fields (likely on `athlete_profile` or a `performance_baselines` table with re-test dates).

**§G Schedule & Availability** — needs storage (no current home).

**§H Target Events** — `athlete_profile` has `target_event_name` / `target_event_date` as scalar columns; the v3 spec models multiple events with rich substructure. A new `target_events` table is needed.

**§I Lifestyle & Recovery** — Average Nightly Sleep partially in `wellness_self_report.sleep_hours`; all other I fields need new storage.

**§J Locales** — `locale_profiles` exists; expand columns per v3 spec (climate, gym chain, seasonality overrides).

**§K Locale Schedule** — `plan_travel` exists as a close proxy; expand or replace per v3 spec.

**§L Athlete Network** — new table needed.

**Bottom line:** D-51 (Layer 1 §C/§D/§E/§F field-by-field inventory) is bigger than originally scoped. There are dozens of fields with no app-table home. The Catalog Migration Plan (D-52) and the Layer 1 v4+ onboarding-tables design are entwined — both need to land before the AIDSTATION pipeline can read the full Layer 1 payload from the deployed schema.

This is real work, not glue. The integration spec assumes it gets done; this section flags the dependency rather than resolving it.

### 7.6.1 D-51 design-wave resolution (2026-05-19)

**Status:** 🟢 Design wave shipped — see `Layer1_D51_Design_v1.md` for the table-by-table storage design closing each gap-row above.

Substantial schema infrastructure was already shipped between this v5 gap-summary draft (2026-05-13) and the D-51 design wave (2026-05-19) — D-58 + D-59 + D-60 + D-61 + D-66 closed the largest pieces. The residual D-51 scope is narrower than originally framed. Per-section resolution summary:

| §7.6 gap row | D-51 design resolution | Reference |
|---|---|---|
| §A Demographics → A.1 Disclosures (acknowledgment timestamps) | New table `disclosure_acknowledgments` per v5 §A.1 closed enum | `Layer1_D51_Design_v1.md` §3.1 |
| §B Health Conditions → new `health_conditions_log` table | New table (parallel to `injury_log`); plus `medications_log` + `food_allergies` companion tables | `Layer1_D51_Design_v1.md` §3.2 |
| §C Training History → many gaps | 7 new columns on `athlete_profile` (`years_structured_training`, `peak_weekly_volume_hrs` + `_year`, `longest_event_completed`, `training_consistency_*`, `previous_coaching`) + 4 new multi-row tables (`athlete_secondary_sports`, `athlete_discipline_weighting`, `recent_race_results`, `pack_load_history`) | `Layer1_D51_Design_v1.md` §3.3 |
| §D Discipline-Specific Baselines → every "experience / skill" field | 7 new per-discipline tables (`discipline_baseline_running` through `_technical`) sparse 1:1 with `athlete_profile`; volume fields stay derived from `cardio_log` | `Layer1_D51_Design_v1.md` §3.4 |
| §E Strength Benchmarks → all 9 fields | New 1:1 table `strength_benchmarks` with 9 columns + `last_tested_at` re-test cadence | `Layer1_D51_Design_v1.md` §3.5 |
| §F Performance Testing Baselines → HRmax/LT/VO2max partial on `body_metrics`; FTP/Threshold Pace/CSS need new fields | New scalar columns on `athlete_profile` (`running_threshold_pace_sec_per_km`, `css_swim_sec_per_100m`, `hrmax_source`, `lt_method`, `vo2max_source`, `cycling_ftp_test_date`); HRmax/LT/VO2max/FTP stay on `athlete_profile` (already present) | `Layer1_D51_Design_v1.md` §3.6 |
| §G Schedule & Availability → needs storage | New table `daily_availability_windows` per v5 §G.1; drop legacy `athlete_profile.training_window`; keep `long_session_*` + `doubles_feasible` + `preferred_rest_days` scalar columns | `Layer1_D51_Design_v1.md` §3.7 |
| §H Target Events → new `target_events` table | ✅ Already shipped (D-66 DB foundation 2026-05-18) — `race_events` + `race_route_locales` + `race_route_locale_equipment`. Adds `plan_duration_weeks_no_event` + `non_event_goal_type` scalars to `athlete_profile` for §H.3 no-event mode | `Layer1_D51_Design_v1.md` §3.8 |
| §I Lifestyle & Recovery → sleep partial in `wellness_self_report`; all other I fields need new storage | New scalar columns on `athlete_profile` covering work_stress + dietary_pattern + caffeine + altitude + I.2 race-day fueling + I.3 sleep-deprivation experience | `Layer1_D51_Design_v1.md` §3.9 |
| §J Locales → expand columns | ✅ Already shipped (D-59 + D-60 2026-05-18) — `locale_profiles` + `gym_profiles` + `locale_equipment_overrides` + `locale_toggle_overrides`. No new tables. | `Layer1_D51_Design_v1.md` §3.10 |
| §K Locale Schedule → expand or replace `plan_travel` | Deferred — v1 doesn't exercise §K.2 joint-training or §K.3 recurrence shape; carry-forward as Layer 1 builder open item | `Layer1_D51_Design_v1.md` §3.11 |
| §L Athlete Network → new table | New table `athlete_network_links` covering §L Athlete Link + Race Teammate conditional fields; companion `linked_partner_consents` deferred to first multi-athlete case | `Layer1_D51_Design_v1.md` §3.12 |

**Migration sequencing.** D-51 implementation lands in 3 sessions (1.2A / 1.2B / 1.2C per `Layer1_D51_Design_v1.md` §4) per `Upstream_Implementation_Plan_v1.md` Phase 1.2. Each ceiling-clean (≤5 files); ordering is athlete_profile column extensions + bundled-scalar sub-tables → multi-row tables for §B/§C/§L → per-discipline §D tables.

**D-52 sequencing decision (catalog migration vs Layer 2A-E builder reads).** Per `Upstream_Implementation_Plan_v1.md` architect-pick (f), deferred to Phase 2 kickoff /plan-mode gate. Layer 2A-E builders can ship reading `public.*` initially with a paired refactor when D-52 lands, OR D-52 lands first. D-51 design does not pre-commit.

**D-56 (`cardio_log.is_race` + `start_time` additions).** Sequenced to Phase 1.4 per the plan; small migration; can fold into 1.2A if the migration batch is favored larger. Out of D-51 design scope (existing table, not new storage).

---

## 8. Two-regime consumer model

Layer 3A (and other future consumers) operate in one of two regimes depending on what data is available for the user.

### 8.1 Pre-integration regime

**Data sources available:**
- `public.*` app tables: `athlete_profile`, `body_metrics`, `wellness_self_report`, `injury_log`, `training_log`, `cardio_log`, etc.
- Onboarding self-report fields (when added per D-51).
- `garmin_auth` users: legacy Garmin FIT data flowing through `wellness_log` and `cardio_log`.

**Confidence tag behavior:**
- 3A `recent_trajectory.confidence` defaults to `medium` when `cardio_log` has 4+ weeks of consistent entries.
- Drops to `low` when log gaps exceed 2 weeks or self-reported volume diverges from logged volume by >25%.
- Never `high` — pre-integration, there is no objective recovery signal (HRV, sleep stages, ANS charge) to reach high confidence.

### 8.2 Post-integration regime

**Data sources available:** all of the above, plus the `provider_auth` row indicating which providers are connected, plus the per-provider tables (`polar_sleep`, `polar_nightly_recharge`, `polar_cardio_load`, `coros_daily_summary`, etc.).

**Confidence tag behavior:**
- `high` requires: at least one HRV-capable provider (Polar or COROS) connected for 14+ days; recent sleep data within last 7 days; recent activity within last 14 days.
- `medium` for partial coverage (one of HRV / sleep / activity missing or stale).
- `low` for connected-but-empty (provider authorized but no data flowing — typically the day-1 state after first connect).

**Query layer behavior:** When 3A asks for "recent sleep," the query layer returns the freshest record across all sources (`wellness_self_report.sleep_hours`, `polar_sleep`, `coros_daily_summary`, Garmin `wellness_log`). The LLM in 3A is responsible for weighing them when they conflict; the query layer doesn't conflict-resolve.

### 8.3 Mixed regime (partial provider connection)

The realistic state for most athletes: one provider connected (say, Polar) plus self-report. Polar covers sleep + HRV + cardio load; doesn't cover training history (unless Polar is also the activity sync source). Self-report covers everything Polar doesn't.

This is *not* a separate regime in the spec — it's a mixed-source 8.2 case. The confidence tags handle it.

---

## 9. Mutability and caching

### 9.1 Mutability classes

| Schema | Class | Update pattern | Cache invalidation |
|---|---|---|---|
| `layer0.*` | Versioned, supersede-on-update | New `etl_version_set` writes new rows; old rows remain until GC | Layer 0 query layer cache invalidates on new version |
| `public.*` app tables | Mutable | Standard `UPDATE` / `INSERT` with `created_at`/`updated_at` | Per-table; specific to consumer |
| `public.*` integration tables | Mutable; provider-driven | UPSERT on natural keys (`UNIQUE (user_id, date)` etc.); provider may rewrite history (e.g., Polar updates a sleep record 12 hours after first push) | 3A re-runs on integration-data ingestion within rolling window |

### 9.2 Cache invalidation for 3A specifically

3A's cache invalidates on:
1. New row in any of `cardio_log` / `training_log` / `wellness_self_report` / `body_metrics` / `injury_log` for the user.
2. UPDATE to any onboarding field in `athlete_profile` or related onboarding tables (post-D-51).
3. New row OR UPDATE in any provider integration table for the user.
4. New `webhook_events` row with `processed_at` set for the user.
5. New 2A output (Layer 2 phase context changes).

In practice: 3A is unlikely to re-run more often than nightly outside of acute events (race result, severe injury report, integration first-connect). The cache invalidation set is permissive; the run cadence is policy on top.

### 9.3 What doesn't invalidate 3A

- New rows in `coaching_chat` (text discussion, not state).
- Changes to `coaching_preferences` (preferences, not state).
- Changes to `equipment_items` or `exercise_inventory` catalogs (handled by 2A-2E reruns; 3A consumes 2A's output, not the catalogs directly).

---

## 10. Query layer access patterns

Function signatures parallel the Layer 0 query layer pattern. Detailed contracts deferred to Layer 3 spec writing; this section locks the surface area.

```python
# Layer 1 sourcing — assemble the full Layer 1 payload from public.* + integration tables
def q_layer1_payload(user_id: int, as_of: datetime | None = None) -> Layer1Payload:
    """Assemble the full Layer 1 dataclass from public.* tables + integration tables.

    `as_of` defaults to NOW(). For historical replay or determinism testing,
    pass a fixed timestamp; queries respect created_at/updated_at boundaries.
    """

# 3A-specific accessors
def q_layer3A_recent_workouts(user_id: int, since_days: int = 28) -> list[WorkoutRecord]:
    """Union of cardio_log + training_log + provider activity tables.

    Returns workouts in chronological order, with `source` tagged per row
    (manual / fit / polar / wahoo / coros / garmin).
    """

def q_layer3A_recent_sleep(user_id: int, since_days: int = 14) -> list[SleepRecord]:
    """Union of wellness_self_report.sleep_* + polar_sleep + coros_daily_summary
    + Garmin wellness_log sleep entries.

    Returns per-night records, source-tagged. LLM in 3A resolves conflicts.
    """

def q_layer3A_recent_hrv(user_id: int, since_days: int = 14) -> list[HRVRecord]:
    """Polar nightly_recharge + COROS daily_summary.ppg_hrv + COROS hrv_samples
    (downsampled to nightly).

    Returns per-night HRV records, source-tagged.
    """

def q_layer3A_combined_load(user_id: int, as_of: datetime, window_days: int = 28) -> CombinedLoadReport:
    """ACWR computation across all logged disciplines.

    Acute = last 7 days, chronic = last 28 days. Per-discipline plus combined.
    Polar's `cardio_load` is exposed as a cross-reference, not the primary number.
    """

def q_layer3A_connected_providers(user_id: int) -> list[ProviderStatus]:
    """List of providers the user has authorized, with status, last_sync, and
    a coverage summary (which data types are flowing).

    Used by 3A to set confidence tags per §8.
    """
```

**Note on cross-schema queries:** `q_layer1_payload` and 3A accessors read both `public.*` and (post-Option-A migration) `layer0.*`. The DB session must have `search_path` set to include both, or queries must be schema-qualified. Recommend schema-qualification for clarity (`FROM public.cardio_log` / `FROM layer0.exercises`).

---

## 11. Open items and forward references

Tracked in `Project_Backlog_v10.md` (next session). Captured here for spec-completeness:

| ID | Item | Affects |
|---|---|---|
| D-48 | Per-provider data-shape filling for Strava/Whoop integration tables | Integration spec §5 |
| D-49 | 3C conflict-rule enumeration revisit if patterns harder to enumerate than expected | 3C spec |
| D-50 | Phase 1 integration deployment (schema migration + app code promotion) | Production |
| D-51 | Layer 1 §A-§L field-by-field inventory against `public.*` — what's missing, what needs new tables | Layer 1 v4+ |
| D-52 | Catalog migration plan (Option A): app FROM clauses migrate to `layer0.*` | Catalog Migration Plan doc |
| D-53 | Heat acclim derivation logic from conditions_log + integration ambient data | Layer 2E or plan-gen consumer |
| D-54 | SQLite backend deprecation: `_SQLITE_MIGRATIONS` freeze and eventual removal | `init_db.py` |
| D-55 | Garmin migration onto `provider_auth`: drop `garmin_auth`, port `garth` session to `session_blob` | Vercel app `routes/garmin.py` + `garmin_connect.py` |
| D-56 | `cardio_log` schema additions for AIDSTATION needs: `is_race`, `start_time`, possibly more | App schema |

**Forward pointers:**
- **Catalog_Migration_Plan.md** (new spec doc, owner: D-52) — describes the app's migration from `public.*` catalogs to `layer0.*`. Includes mapping spec for `public.equipment_items.tag → layer0.equipment_items.canonical_name`, type-compat strategy for `TEXT` vs `TEXT[]`, route file change list, and migration sequencing. Not started.
- **Layer3_Spec.md** — consumes this spec's §10 query signatures plus the §8 two-regime model when writing 3A.
- **Layer 4 plan generation** — consumes 3A output plus provider plan-push patterns (Wahoo / COROS plans) when designing plan delivery.

---

## 12. References

**Within this project:**
- `Athlete_Onboarding_Data_Spec_v3.md` (Layer 1 field definitions)
- `Control_Spec_v6.md` (forthcoming — architectural framing)
- `Layer0_ETL_Spec_v7.md` (layer0 schema source of truth)
- `Layer2A_Spec.md` through `Layer2E_Spec.md` (Layer 2 nodes consuming Layer 1)
- `L3_Discovery_Closing_Handoff_v1.md` (architectural decisions origin)

**App-track (repo root — same repo, different documentation set):**
- `DATABASE.md` (app schema documentation)
- `PROVIDERS_SCHEMA.md` (producer-side integration design)
- `HANDOFF-2026-05-13.md` (provider stub playbook)
- `HANDOFF-2026-05-13-stub-batch.md` (four-stub batch + Strava challenge)

**Schema inventory (this session):**
- `L3-Discovery_Pre-Spec-Trio_Inventory` (full `public.*` schema dump + planned integration tables + catalog drift findings)

---

*End of Athlete_Data_Integration_Spec v1.*
