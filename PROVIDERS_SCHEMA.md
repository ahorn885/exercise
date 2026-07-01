# Provider Integration Schema

Reference for the conventions we use when integrating a third-party
fitness/data provider (Polar, Wahoo, COROS, Ride With GPS, Strava,
Whoop, TrainingPeaks, Zwift, etc.). Covers URL layout, env-var naming,
slug rules, and the planned database tables.

This is a **schema reference** — what the abstractions look like and
why. For the step-by-step process of shipping a new provider stub, see
[`HANDOFF-2026-05-13.md`](HANDOFF-2026-05-13.md). For the live database
schema (what's currently in production), see
[`DATABASE.md`](DATABASE.md). For the multi-phase build roadmap, see
`/root/.claude/plans/will-this-make-changes-peaceful-boot.md`.

**Live in production (Phase 0):** URL layout, env-var convention, slug
naming, and the route stubs for COROS and Ride With GPS.

**Designed but not yet shipped (Phase 1+):** the database tables, the
generic `provider_auth.py` helper module, real OAuth code exchanges,
real webhook verification.

---

## 1. Slug naming

Every provider has a stable, URL-safe slug. The slug is the **only**
identifier you need to know — every URL, file name, and env-var name
derives from it.

| Rule | Example |
|---|---|
| Lowercase ASCII | `polar`, not `Polar` |
| Hyphenated multi-word | `ride-with-gps`, not `ridewithgps` or `ride_with_gps` |
| Match the brand's canonical short name | `coros`, `wahoo`, `whoop` |
| Special characters dropped or replaced | `vo2` (for V.O2), `adidas-running` |

Slug is registered exactly once in `routes/oauth_callbacks.py:_PROVIDERS`
as a `(slug, display_name)` tuple. Display name preserves brand
casing (`'adidas Running'`, `'COROS'`).

---

## 2. URL layout

Two endpoints per provider, both on the production domain
`aidstation-pro.vercel.app`:

| Purpose | Path | Methods | Auth-exempt? | CSRF-exempt? |
|---|---|---|---|---|
| Incoming webhook from provider's servers | `/<slug>/webhook` | GET, POST | yes | yes |
| OAuth redirect URI (where the provider sends the user's browser back after consent) | `/auth/<slug>/callback` | GET, POST | yes (single `oauth_callbacks.callback` endpoint covers all slugs) | no (browser-initiated) |

Plus one app-wide endpoint reused by every provider's application form:

| Purpose | Path | Methods |
|---|---|---|
| Liveness + DB readiness probe | `/status` | GET |

**Why these paths:** the webhook lives under the provider slug so all
push handlers are co-located in a single blueprint file
(`routes/<module>.py`). The OAuth callback lives under `/auth/` because
that's where every other auth-related route lives (login, register,
forgot, reset, logout) and the existing `oauth_callbacks` blueprint
already mounts the entire family with `url_prefix='/auth'`.

**Browser-initiated callback vs. server-to-server webhook:** the OAuth
callback is hit by the user's browser as a redirect after they consent
on the provider's site, so it's a normal Flask route subject to CSRF
on POST (rare — most providers redirect with GET). The webhook is hit
by the provider's servers with no session cookie, so it needs both
auth-exempt and CSRF-exempt treatment.

### Probe-friendly callback

Some providers' developer portals probe the OAuth redirect URI at
form-save (HEAD or GET). The default 501 response would fail their
validation. The slug goes into the
`_PROBED_AT_REGISTRATION: frozenset[str]` set in
`routes/oauth_callbacks.py` to flip the response to 200 while keeping
the same plain-text body. Once the real OAuth exchange ships for that
provider, the slug drops out of the set.

Known members today: `ride-with-gps`. Others speculatively safe to add
if uncertain — no downside.

---

## 3. Env-var convention

**Default (one credential pair per provider):**

```
<PROVIDER>_CLIENT_ID
<PROVIDER>_CLIENT_SECRET
```

`<PROVIDER>` is the uppercase, underscore-separated form of the slug:
`coros` → `COROS`, `ride-with-gps` → `RIDE_WITH_GPS`.

**Split (originally designed for providers that issue separate API and
OAuth pairs):**

```
<PROVIDER>_API_CLIENT_ID         # identifies us on outgoing API + matched against
                                 #   the api-key header on incoming webhooks
<PROVIDER>_API_CLIENT_SECRET     # HMAC-SHA256 signing key for verifying
                                 #   incoming webhook signatures
<PROVIDER>_OAUTH_CLIENT_ID       # used in authorize URL + token exchange
<PROVIDER>_OAUTH_CLIENT_SECRET   # used in token exchange to get user access tokens
```

Neither shipped provider actually needed this split: RWGPS and Polar
both ended up on the plain `<PROVIDER>_CLIENT_ID` / `<PROVIDER>_CLIENT_SECRET`
pair (see `.env.example` and `routes/ride_with_gps.py` /
`routes/polar.py`) — Polar's distinct piece is only the webhook HMAC
key, covered below. Reach for the split form only if a future provider
genuinely issues separate API and OAuth credential pairs.

**Provider-specific webhook secrets (Polar's HMAC key):**

```
<PROVIDER>_WEBHOOK_SECRET        # only when distinct from the API/OAuth pair
```

Polar AccessLink is the canonical example: the OAuth client_secret and
the webhook HMAC secret are two different values issued at different
points (the HMAC key is server-generated and returned exactly once
during `POST /v3/webhooks` registration).

**Where to set:** Vercel Production + Preview, marked Sensitive. Never
commit values to `.env.example` — names only, empty.

**Naming gotcha:** when a webhook handler uses an HMAC, document
*which* secret is the signing key in the route-file docstring. It's
the kind of detail that gets miswired six months later when the real
handler ships.

---

## 4. File layout

Per provider:

| File | Purpose | Shipped when |
|---|---|---|
| `routes/<module>.py` | Flask blueprint with `/webhook` (stub or real) and later `/connect`, `/disconnect`, `/sync`, `/dashboard`, `/push/<plan_item_id>` routes | Phase 0 (stub), Phase 1+ (real surface) |
| `<module>_connect.py` | OAuth code exchange, refresh handling, typed API fetchers, normalizers into DB tables | Phase 1+ |
| `<module>_plan_builder.py` | Convert a `plan_items` row into the provider's planned-workout format | Phase 4 (Wahoo) / Phase 6 (COROS) |

`<module>` is the slug with hyphens replaced by underscores
(`ride-with-gps` → `ride_with_gps`). The blueprint name inside
`routes/<module>.py` matches `<module>` so `url_for` works as
`<module>.webhook`, `<module>.connect`, etc.

Single OAuth-callback blueprint at `routes/oauth_callbacks.py`
parameterized over slug — no per-provider callback file. Adding a
provider only requires editing `_PROVIDERS` (and optionally
`_PROBED_AT_REGISTRATION`).

---

## 5. Database tables (planned — Phase 1+)

None of these exist yet. They are the target shape the master plan
will land in `init_db.py`. Cross-reference `DATABASE.md` for the
conventions every new table must follow (`?` placeholders, branch on
`_is_postgres()` where SQL diverges, both `_PG_MIGRATIONS` and
`_SQLITE_MIGRATIONS` updated, cascade-delete chain in
`routes/admin.py:_delete_user_and_data`).

### 5.1 Generic — shared by all providers

**`provider_auth`** — one row per (user, provider) pair.

| Column | Type | Notes |
|---|---|---|
| `id` | SERIAL/INTEGER PK | |
| `user_id` | INTEGER NOT NULL FK | |
| `provider` | TEXT NOT NULL | matches a slug in `oauth_callbacks._PROVIDERS` |
| `access_token` | TEXT | |
| `refresh_token` | TEXT NULL | Polar leaves NULL (no refresh); Wahoo rotates on every use; COROS never expires |
| `token_expires_at` | TIMESTAMP NULL | Polar leaves NULL (non-expiring); Wahoo = `now + 2h`; COROS = `now + 30d` |
| `provider_user_id` | TEXT | Polar `x_user_id`; Wahoo `user.id`; COROS `openId` |
| `scopes` | TEXT | space-separated, as returned by provider |
| `webhook_token` | TEXT NULL | Wahoo per-user webhook_token (NULL for others) |
| `status` | TEXT | `active` / `revoked` / `error` / `pending_backfill` |
| `registered_at` | TIMESTAMP NULL | Polar: when `POST /v3/users` succeeded; others NULL |
| `created_at` | TIMESTAMP | |
| `updated_at` | TIMESTAMP | |

Constraint: `UNIQUE (user_id, provider)` — UPSERT target.

Replaces the per-provider `garmin_auth` pattern. **Done (2026-07-01,
T-5.1/#249):** Garmin now stores its `garth` session JSON in this
table's `session_blob TEXT` column (provider `'garmin'`) —
`garmin_connect.py` + `routes/garmin.py`'s auth-import endpoints go
through `routes/provider_auth.py`'s `upsert_auth`/`get_auth`, same as
every other provider. This landed ahead of the original "wait for
Garmin API access to reopen" plan — the migration is storage-layer
only (garth is not OAuth, so the API closure doesn't block it); a
read-only `neon-query` confirmed 0 rows in `garmin_auth` before the
cutover, so no data migration was needed. The legacy `garmin_auth`
table itself is **not yet dropped** (kept as a harmless unused table
pending a separate DDL follow-up) — nothing reads or writes it
anymore. All providers (Polar, Wahoo, COROS, RWGPS, Strava, Whoop,
Garmin, TrainingPeaks, Zwift, etc.) now go through `provider_auth`.

Reconciled with `aidstation-sources/Athlete_Data_Integration_Spec_v3`
§2.3 in the 2026-05-14 single-repo reconciliation pass — both
documents now agree on the target state.

**`webhook_events`** — generic audit + dedup for incoming pushes.

| Column | Type | Notes |
|---|---|---|
| `id` | SERIAL/INTEGER PK | |
| `provider` | TEXT NOT NULL | slug |
| `event_type` | TEXT | provider-specific (e.g. `EXERCISE`, `workout.created`, `route.added`) |
| `provider_user_id` | TEXT | from the push body |
| `entity_id` | TEXT | provider-side workout/exercise/route id |
| `user_id` | INTEGER NULL FK | resolved during dispatch; NULL while pending |
| `payload` | TEXT | raw JSON body as received |
| `signature_ok` | BOOLEAN | HMAC / token verification result |
| `received_at` | TIMESTAMP | |
| `processed_at` | TIMESTAMP NULL | NULL until dispatched |
| `error` | TEXT NULL | non-NULL if dispatch failed |
| `dead_lettered_at` | TIMESTAMP NULL | stamped (#250) when a failed delivery ages past its retry window; the dead-letter path is `WHERE dead_lettered_at IS NOT NULL` |

Index: `(provider, provider_user_id, entity_id, event_type)` for dedup
and replay queries; partial `(received_at) WHERE dead_lettered_at IS NOT NULL`
for the dead-letter path.

**Housekeeping (#250):** the daily cron `/integrations/webhooks/cron/maintenance`
(`routes/webhook_maintenance.py`, Bearer-`CRON_SECRET`) dead-letters failed
deliveries that aged past their retry window, then prunes rows older than 90 days.

### 5.2 Provider-specific tables

One sub-namespace per provider, prefixed with the slug (with hyphens
stripped). Tables exist only when the provider exposes data that
doesn't fit the existing `cardio_log` / `training_log` / `wellness_log`
shape.

**Polar (AccessLink):** the per-provider wellness tables were retired in
#681 §4 Slice 3 — sleep / nightly-recharge / cardio-load now record into the
canonical `provider_raw_record` (`provider='polar'`, `data_type` ∈
`sleep`/`hrv`/`cardio_load`), and continuous HR into `wellness_log`
(`source='polar'`). Layer-3A reads them back filtered to `provider='polar'`.

**Wahoo (Cloud API):**

| Table | For | Uniqueness |
|---|---|---|
| `wahoo_plans` | Plans pushed via `POST /v1/plans` (mirrors existing `garmin_workouts`) — columns: `id`, `user_id`, `plan_item_id` FK, `wahoo_plan_id`, `wahoo_workout_id`, `external_id`, `provider_updated_at`, `status`, `created_at` | `id` PK |

**COROS (Open API):**

| Table | For | Uniqueness |
|---|---|---|
| `coros_plans` | Plans pushed via `/coros/tp/list/push` (mirrors `wahoo_plans`) | `id` PK |

COROS wellness was retired in #681 §4 Slice 3: `coros_daily_summary` records into
`provider_raw_record` (`provider='coros'`, `data_type='daily_summary'`) and the
per-sample HR into `wellness_log` (`source='coros'`); `coros_hrv_samples` was
dropped (the per-second HRV value has no consumer).

**RWGPS, Strava, Whoop, etc.:** TBD per provider — add a sub-table
only when the data doesn't fit an existing log.

### 5.3 New columns on existing tables

| Table | Column | Type | Purpose |
|---|---|---|---|
| `cardio_log` | `polar_exercise_id` | TEXT | Mirrors `garmin_activity_id` |
| `cardio_log` | `wahoo_workout_id` | TEXT | |
| `cardio_log` | `coros_label_id` | TEXT | COROS uses `labelId`, not `id` |
| `cardio_log` | `rwgps_trip_id` | TEXT | |
| `training_log` | `polar_exercise_id` | TEXT | |
| `training_log` | `wahoo_workout_id` | TEXT | |
| `training_log` | `coros_label_id` | TEXT | |

Add a column when the provider has an opaque external identifier that
needs round-tripping for dedup, idempotent re-imports, and webhook
update routing.

### 5.4 Cascade-delete chain

Every user-scoped table above (`provider_auth`, all `polar_*`, all
`coros_*`, `wahoo_plans`, `webhook_events` where `user_id IS NOT NULL`)
must be added to `_delete_user_and_data` in `routes/admin.py`,
ordered before the final `users` delete. This is the live convention
documented in `DATABASE.md` — any new user-scoped table that isn't in
the chain is a bug.

---

## 6. Slug → file/route/env-var quick reference

Worked example for `slug = "whoop"`:

| Asset | Value |
|---|---|
| Display name | `Whoop` (set in `_PROVIDERS` tuple) |
| Module | `whoop` |
| Blueprint object | `routes/whoop.py::bp` (`Blueprint('whoop', __name__, url_prefix='/whoop')`) |
| Webhook URL | `https://aidstation-pro.vercel.app/whoop/webhook` |
| OAuth callback URL | `https://aidstation-pro.vercel.app/auth/whoop/callback` |
| Auth-exempt endpoint | `whoop.webhook` |
| CSRF exempt | `csrf.exempt(whoop_bp)` |
| Env vars (default) | `WHOOP_CLIENT_ID`, `WHOOP_CLIENT_SECRET` |
| Future connect file | `whoop_connect.py` |
| `provider_auth.provider` value | `'whoop'` |
| `webhook_events.provider` value | `'whoop'` |
| Foreign id column on logs | `whoop_workout_id` (or whatever Whoop calls their primary id) |
| Sub-tables | `whoop_recovery`, `whoop_strain` — only if data doesn't fit `wellness_log` |

Worked example for `slug = "ride-with-gps"`:

| Asset | Value |
|---|---|
| Display name | `Ride With GPS` |
| Module | `ride_with_gps` (underscore-separated) |
| Blueprint object | `routes/ride_with_gps.py::bp` (`Blueprint('ride_with_gps', __name__, url_prefix='/ride-with-gps')`) |
| Webhook URL | `https://aidstation-pro.vercel.app/ride-with-gps/webhook` |
| OAuth callback URL | `https://aidstation-pro.vercel.app/auth/ride-with-gps/callback` |
| Auth-exempt endpoint | `ride_with_gps.webhook` |
| Env vars (split pairs — RWGPS issues two) | `RIDE_WITH_GPS_API_CLIENT_ID`, `RIDE_WITH_GPS_API_CLIENT_SECRET`, `RIDE_WITH_GPS_OAUTH_CLIENT_ID`, `RIDE_WITH_GPS_OAUTH_CLIENT_SECRET` |
| Webhook HMAC key | `RIDE_WITH_GPS_API_CLIENT_SECRET` (note: API secret, not OAuth secret) |
| Probe-friendly redirect | yes — `'ride-with-gps'` in `_PROBED_AT_REGISTRATION` |
| Foreign id columns | `rwgps_trip_id`, `rwgps_route_id` (abbreviation for the column-name budget) |

---

## 7. What stays out of this schema

- **`garmin_auth`** — pre-OAuth, `garth` username/password flow.
  **Retired as of 2026-07-01 (T-5.1/#249):** Garmin now stores its
  session in `provider_auth.session_blob` like every other provider
  (§5.1 above); `init_db.py` and `routes/garmin.py` no longer read or
  write this table. The table itself is still physically present
  (empty; not yet dropped — that DDL is a separate follow-up).
- **Per-provider migration files** — all schema changes are additive
  via `_PG_MIGRATIONS` / `_SQLITE_MIGRATIONS` lists in `init_db.py`.
  No Alembic, no per-table migration files.
- **Background-worker schema** — webhook dispatch processing happens
  inline at first; if/when we add a queue table (Celery / RQ /
  Postgres-backed), it lives in its own doc.
- **Provider-specific UI templates** — covered by the per-phase plan
  in the master plan, not this schema doc.
