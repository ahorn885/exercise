# V5 Onboarding Implementation PR3 — Closing Handoff

**Session:** Third substantive code session of the v5 onboarding implementation arc. Executes PR2 §5.1 Option C (Polar OAuth) as the second real provider on `provider_auth`. Full end-to-end pipeline per Andy's scope-lock: OAuth start + token exchange + `/v3/users` registration + HMAC-verified webhook + transaction-fetch ingestion + per-pull direct reads + the partial-UNIQUE-index fixup flagged in PR1 §6.
**Date:** 2026-05-14
**Predecessor handoff:** `V5_Implementation_PR2_Closing_Handoff_v1.md` (its §5.1 Option C + §6 "cardio_log partial UNIQUE" item are what this session executes).
**Branch:** `claude/review-v5-handoff-t7KBL` (continued — same feature branch PR2 used).
**Status:** 🟡 Code shipped to feature branch; 🟡 push pending; 🟡 frontend (Polar `connect` button, Account Config 1 management screen, `?polar_connected=1` prompt) and the v16→v17 backlog bump are out of scope per the ceiling. PR4+ candidates: backlog bump, Polar refresh-on-401 if it surfaces, Option B (frontend) per PR2 §5.1.
**Time-on-task:** Single chat. Substantive files: **5** (init_db.py, routes/polar.py [new], routes/polar_ingest.py [new], routes/oauth_callbacks.py, app.py). Plus this handoff (6 total — same one-over-ceiling pattern PR1 hit; PR2 was 5 substantive + handoff because it was schema-only).

---

## 1. Session-start verification (Rule #9)

Verified the PR2 handoff's claimed state before any new work.

| Claim | Anchor | Result |
|---|---|---|
| Branch `claude/review-v5-handoff-t7KBL` clean; HEAD at `686bb40` (PR2: D-59/60/61 schema) | `git status` + `git log --oneline -3` | ✅ Verified |
| `aidstation-sources/Project_Backlog_v16.md` exists; D-50 row references PR1 commit `3628ca6` in 2 places | `grep -c` | ✅ Verified (2 matches) |
| `aidstation-sources/CLAUDE.md` Authoritative current files cites `Project_Backlog_v16.md` | `grep "Backlog: "` | ✅ Verified |
| `chain_registry.py` exists with 32 entries (24 commercial + 8 climbing) | importlib + `Counter` | ✅ Verified |
| `init_db.py` `_PG_MIGRATIONS` has 4 new tables from PR2 (`gym_profiles` / `locale_equipment_overrides` / `locale_toggle_overrides` / `daily_availability_windows`) | region grep | ✅ Verified |
| `_SQLITE_MIGRATIONS` untouched by PR2 (0 references to the 4 new tables) | region grep | ✅ Verified |
| `routes/oauth_callbacks.py` `_PROVIDERS` contains `('polar', 'Polar')` (PR3 will drop it) | grep | ✅ Verified |
| `routes/polar.py` does NOT exist (PR3 creates it) | `ls routes/polar.py` | ✅ Verified (no such file) |
| `cardio_log.polar_exercise_id` / `coros_label_id` / `wahoo_workout_id` columns exist (D-50 Phase 1) | grep | ✅ Verified |
| `provider_auth` helper exports `STATUS_PENDING_BACKFILL` (PR3 will use it for the registration-call two-phase) | `python3 -c "import importlib.util; …"` | ✅ Verified (constant present, value `'pending_backfill'`) |

No drift between PR2 handoff narrative and on-disk state.

---

## 2. Files shipped this turn

All on branch `claude/review-v5-handoff-t7KBL`.

| # | File | Type | Notes |
|---|---|---|---|
| 1 | `init_db.py` | Edit (+3 statements on `_PG_MIGRATIONS`) | Three partial-UNIQUE indexes on `cardio_log`: `cardio_log_polar_exercise_uidx (user_id, polar_exercise_id) WHERE polar_exercise_id IS NOT NULL`, plus the parallel `coros_label_uidx` and `wahoo_workout_uidx`. PR1 §6 flagged these as race-window holes — webhook fan-out could create duplicate `cardio_log` rows under the SELECT-then-INSERT-or-UPDATE pattern `coros_ingest._ingest_activity` uses. With the partial UNIQUE in place, both `polar_ingest._upsert_exercise` (new in PR3) and a future `coros_ingest._ingest_activity` rewrite can use `ON CONFLICT (user_id, <col>) WHERE <col> IS NOT NULL DO UPDATE` instead. NULL rows excluded so manual `cardio_log` entries (pre-provider-sync) don't collide with each other or with provider rows that just happen to share `(user_id, NULL)`. SQLite block stays frozen per Integration v4 §2.5. `_PG_MIGRATIONS` total: 204 → 207. |
| 2 | `routes/polar.py` | New (433 lines) | Three routes: `GET /polar/oauth/start` (state token + same-origin return_to + redirect to `https://flow.polar.com/oauth2/authorization`); `GET /polar/oauth/callback` (HMAC-state compare → POST `/v2/oauth2/token` with HTTP Basic auth → extract `access_token` + `x_user_id` → `provider_auth.upsert_auth` with `status=pending_backfill` → POST `/v3/users` with `{member-id: <user_id>}` → if 200/201/409 set `status=active` + `registered_at=NOW()`, else `status=error` → record OAuth scope ack → redirect to `return_to?polar_connected=1` or `polar_register_error=1`); `GET\|POST /polar/webhook` (GET=registration probe returns 200; POST=HMAC-SHA256 verify header `Polar-Webhook-Signature` against `POLAR_WEBHOOK_SECRET` → normalise single-event vs `available-notifications` batch → per-notification audit row → unmapped users marked-and-skipped → dispatch to `polar_ingest.ingest_event` with the stored access_token → mark processed or record error). |
| 3 | `routes/polar_ingest.py` | New (443 lines) | Five event types mapped against the four `polar_*` per-provider tables + `cardio_log`. `EXERCISE` follows Polar's transaction handshake: POST `/v3/users/{id}/exercise-transactions` → GET transaction URI → GET each exercise URL → UPSERT into `cardio_log` on the new `(user_id, polar_exercise_id)` partial-UNIQUE index → PUT transaction URI to commit. `SLEEP` / `NIGHTLY_RECHARGE` / `CARDIO_LOAD` / `CONTINUOUS_HEART_RATE` are direct pulls — read the notification's `url` (or construct one from `polar_user_id` + the event-type's canonical path), parse the AccessLink response, UPSERT into the matching per-provider table on `(user_id, date)` (or `(user_id, timestamp_ms)` for CHR samples). 17 Polar sport strings mapped to v1 `cardio_log.activity`; unknowns fall through to `'other'`. ISO-8601 `PT…H…M…S` duration parsing implemented inline (Polar's exercise `duration` field). |
| 4 | `routes/oauth_callbacks.py` | Edit (1-line removal + 4-line comment) | Drop `('polar', 'Polar')` from `_PROVIDERS`. Comment block updated to note both COROS (PR1) and Polar (PR3) now own their own callback under their provider blueprint at `/<slug>/oauth/callback` rather than the stub registry's `/auth/<slug>/callback`. Per the Option A architectural decision Andy locked: each provider's full lifecycle stays in one file; the slug-dispatch refactor (Option B) is deferred until provider count hits 5+. |
| 5 | `app.py` | Edit (4-line addition across 4 sites) | `from routes.polar import bp as polar_bp` (line 144); `app.register_blueprint(polar_bp)` (line 172); `csrf.exempt(polar_bp)` (line 186) with a docstring comment explaining the HMAC-instead-of-CSRF rationale; `'polar.webhook'` added to `_AUTH_EXEMPT_ENDPOINTS` (line 219). The OAuth start / callback routes are session-required (they call `current_user_id()`) so they correctly fall through to the auth gate — only the webhook needs the exemption. |
| — | `aidstation-sources/handoffs/V5_Implementation_PR3_Closing_Handoff_v1.md` | New (this file) | Session-end bookkeeping. |

**Files explicitly NOT touched:**

- `aidstation-sources/Project_Backlog_v16.md` — D-50 row's status flip (now "🟢 PR1 + PR2 + PR3 shipped") wants a v16→v17 bump per Rule #12. Deferred to PR4 (PR1's pattern, not PR2's) because PR3 already sits at one-over-ceiling and is the heavier code load of the three sessions. Mechanical edit in §5.4 below.
- `aidstation-sources/CLAUDE.md` — "Authoritative current files" still cites v16; flips to v17 in PR4 alongside the backlog bump.
- `routes/provider_auth.py` — **zero edits.** First real test of PR1's "provider-agnostic helper" claim; Polar's OAuth shape (HTTP Basic on token endpoint, two-phase status flip across registration call, separate webhook secret env var) was absorbed entirely in `routes/polar.py` without touching the helper. The helper held.
- `routes/coros.py` / `routes/coros_ingest.py` — unchanged. The new partial-UNIQUE index on `cardio_log_coros_label_uidx` is now in place, so `coros_ingest._ingest_activity`'s SELECT-then-INSERT-or-UPDATE pattern *could* be simplified to ON CONFLICT. Deferred to a future cleanup PR; not in PR3 scope and not regressing anything left as-is.
- `DATABASE.md` / `PROVIDERS_SCHEMA.md` — same "deferred to consolidated docs PR" framing PR1 §2 + PR2 §2 used. Now 8 undocumented additions across PR1+PR2+PR3 (3 D-58 tables + 4 D-59/60/61 tables + 1 disclosure_acks + 13 locale_profiles columns + 3 partial UNIQUE indexes). Consolidation candidate when the first frontend PR (Option B) makes any of this user-visible.
- `_SQLITE_MIGRATIONS` block — frozen per Integration v4 §2.5. The new partial-UNIQUE indexes are PG-only (SQLite's partial index syntax differs anyway; ON CONFLICT semantics also differ).

---

## 3. What landed

### 3.1 Partial-UNIQUE indexes on `cardio_log`

```sql
CREATE UNIQUE INDEX IF NOT EXISTS cardio_log_polar_exercise_uidx
    ON cardio_log (user_id, polar_exercise_id) WHERE polar_exercise_id IS NOT NULL;
CREATE UNIQUE INDEX IF NOT EXISTS cardio_log_coros_label_uidx
    ON cardio_log (user_id, coros_label_id) WHERE coros_label_id IS NOT NULL;
CREATE UNIQUE INDEX IF NOT EXISTS cardio_log_wahoo_workout_uidx
    ON cardio_log (user_id, wahoo_workout_id) WHERE wahoo_workout_id IS NOT NULL;
```

Closes the race window flagged in PR1 §6. Two design choices:

- **Partial (filtered by NOT NULL).** All three columns are TEXT and nullable. A non-filtered UNIQUE on `(user_id, polar_exercise_id)` would forbid more than one `polar_exercise_id IS NULL` row per user, breaking the case where Andy manually logs a workout *and* later imports another manual entry. The partial form excludes NULLs from the uniqueness contract entirely.
- **Composite with `user_id`.** Per Integration v4 §6 "provider IDs are partner-scoped." Two athletes can in principle have the same Polar exercise id (different Polar accounts); the partner-scoped uniqueness keeps tenant isolation.

### 3.2 `routes/polar.py` — OAuth + webhook

Three routes, same shape as `routes/coros.py` but with Polar-specific deltas:

**OAuth start (`GET /polar/oauth/start`).** Identical to COROS start except for the destination URL and scope value. Same `_OAUTH_STATE` / `_OAUTH_RETURN_TO` session-key pattern, different key names (`polar_oauth_state` / `polar_oauth_return_to`) so concurrent multi-provider connect flows can't clobber each other's state.

**OAuth callback (`GET /polar/oauth/callback`).**

```
GET /polar/oauth/callback?code=…&state=…
  → hmac.compare_digest(session.pop('polar_oauth_state'), received_state)
  → POST https://polarremote.com/v2/oauth2/token
         body: grant_type=authorization_code, code=…, redirect_uri=…
         auth: HTTP Basic client_id:client_secret    ← Polar deviation from COROS
  → extract access_token, x_user_id (or polar-user-id, or user_id)
  → upsert_auth(status=PENDING_BACKFILL, access_token=…, provider_user_id=…)
  → POST https://www.polaraccesslink.com/v3/users
         body: {"member-id": "<our_user_id>"}
         auth: Bearer <access_token>
  → if 200/201/409: upsert_auth(status=ACTIVE, registered_at=NOW())
    else:           upsert_auth(status=ERROR)
  → record_oauth_scope_ack(version_id='2026-05-14')
  → redirect return_to?polar_connected=1   (or polar_register_error=1)
```

**Two-phase auth row** is the key shape difference from COROS. Polar's `POST /v3/users` is a side-effect on Polar's servers (it activates the partner-user relationship); if it fails after a successful token exchange, we still want the `access_token` durably persisted so a retry can finish the relationship. `status=pending_backfill` between the two stages is the documented state-machine slot for "tokens OK, provider-side setup incomplete" per Integration v4 §4.1. 409 is treated as success because Polar emits it for the re-connect path (athlete revoked + re-authorised; their partner-user row still exists).

**Webhook (`POST /polar/webhook`).** HMAC-SHA256 of raw body using `POLAR_WEBHOOK_SECRET` (separate env var from `POLAR_CLIENT_SECRET` — Polar issues this when the webhook URL is registered via their partner API; mixing them up is a subtle wiring error this comment exists to flag). Notifications come in one of two shapes:

```json
// Documented current shape — single event per POST
{"event": "EXERCISE", "user_id": 12345, "entity_id": "abc", "url": "https://..."}

// Older shape — batch wrapper
{"available-notifications": [
    {"event": "SLEEP", "user_id": 12345, ...},
    {"event": "CARDIO_LOAD", "user_id": 12345, ...}
]}
```

`_extract_notifications` normalises both to a list. The webhook handler records one `webhook_events` row per notification (so the audit trail is per-event even when Polar batches) and dispatches each individually. An empty list (Polar's "is this endpoint alive" probe — distinct from the GET probe) records a single row with `event_type=NULL` and returns 200 on signed paths or 401 on unsigned.

Unmapped users (notification's `user_id` doesn't resolve to any `provider_auth` row via `get_auth_by_provider_user_id`) are recorded with `processed_at=NOW()` and an explanatory `error` so they aren't re-dispatched. The notification arrived in good faith — Polar pushed it because they have a `polar-user-id` we don't recognize — most likely a stale subscription. The audit row is durable; a maintenance route could later resolve and re-dispatch if needed.

### 3.3 `routes/polar_ingest.py` — transaction-fetch + direct pulls

Two structural patterns:

**Transaction-based (EXERCISE only).** Per Polar AccessLink §4.1:

```
POST /v3/users/{polar_user_id}/exercise-transactions
  → 204 if no new exercises (early return)
  → 201 with {transaction-id, resource-uri}

GET resource-uri
  → {exercises: [url1, url2, ...]}

for each url:
  GET url
    → {id, sport, start-time, duration, distance, heart-rate, calories, ...}
  → cardio_log UPSERT on (user_id, polar_exercise_id) WHERE polar_exercise_id IS NOT NULL

PUT resource-uri
  → 200 — Polar drops these exercises from the next transaction
```

The PUT commit is the crucial step. If we don't commit, Polar re-queues the same exercises in the next transaction (after their auto-discard timeout, default 30 minutes); we'd see them again. The `INSERT ... ON CONFLICT DO UPDATE` keeps re-delivery idempotent — overwriting the same row with the same field values is a no-op effect on the read surface.

**Direct pulls (SLEEP / NIGHTLY_RECHARGE / CARDIO_LOAD / CONTINUOUS_HEART_RATE).** No transaction step. Use the notification's `url` field when present (Polar's docs guarantee a complete resource URI for these event types); fall back to a constructed URL based on `polar_user_id` + the event-type's canonical path if `url` is missing.

Each pull's payload is normalised to a list (some Polar endpoints return `{"sleep": [...]}`, some return a bare object; defensive coercion handles both) and rows UPSERT on the per-table natural key:

| Event | Target | Natural key |
|---|---|---|
| EXERCISE | `cardio_log` | `(user_id, polar_exercise_id)` partial-UNIQUE |
| SLEEP (and `SLEEP_WISE_ALARM_OUTPUT`) | `polar_sleep` | `(user_id, date)` |
| NIGHTLY_RECHARGE | `polar_nightly_recharge` | `(user_id, date)` |
| CARDIO_LOAD | `polar_cardio_load` | `(user_id, date)` |
| CONTINUOUS_HEART_RATE | `polar_continuous_hr_samples` | `(user_id, timestamp_ms)` |
| Unknown event type | (no-op; logged) | — |

**Polar sport mapping** is 17 entries: `RUNNING`/`JOGGING`/`TRAIL_RUNNING`/`TREADMILL_RUNNING`/`ROAD_RUNNING` → run-family; `CYCLING`/`ROAD_BIKING`/`INDOOR_CYCLING`/`MOUNTAIN_BIKING` → cycle; `SWIMMING`/`POOL_SWIMMING`/`OPEN_WATER_SWIMMING` → swim; `TRIATHLON`, `STRENGTH_TRAINING`, `HIKING`, `SKIING`/`CROSS-COUNTRY_SKIING`, `SKI_TOURING`, `ROWING`/`INDOOR_ROWING`, `WALKING`. Mapping leans wider than COROS's 10 because Polar exposes more granular sport sub-types; the v1 `cardio_log.activity` vocabulary collapses them at the boundary.

### 3.4 `_AUTH_EXEMPT_ENDPOINTS` + CSRF exempt

`app.py` mirrors PR1's COROS wiring exactly:
- Import `polar_bp` alongside `coros_bp` and the wave-2 stub blueprints.
- Register the blueprint between COROS and Ride With GPS (no semantic ordering — alphabetical-ish by current provider arrival).
- CSRF-exempt the whole blueprint with the same docstring comment pattern explaining the HMAC-instead-of-CSRF rationale.
- Add `'polar.webhook'` to `_AUTH_EXEMPT_ENDPOINTS`. The OAuth start/callback routes call `current_user_id()` directly and redirect to `/auth/login` if unset, so they correctly stay session-required.

---

## 4. Session-end verification (Rule #10)

Anchor checks against on-disk state before composing this handoff.

| Claim | Anchor | Result |
|---|---|---|
| All 5 changed files AST-parse clean | `ast.parse` over each | ✅ Verified |
| `_PG_MIGRATIONS` totals 207 statements (was 204 after PR2, +3 partial UNIQUE indexes) | AST `len(value.elts)` over the `_PG_MIGRATIONS` assignment | ✅ Verified |
| 3 partial UNIQUE indexes landed in `_PG_MIGRATIONS` (`cardio_log_polar_exercise_uidx`, `cardio_log_coros_label_uidx`, `cardio_log_wahoo_workout_uidx`) | region grep + line numbers (1927–1929) | ✅ Verified |
| `_SQLITE_MIGRATIONS` totals 140 statements (unchanged from PR2) — no provider-dedup partial UNIQUE here per Integration v4 §2.5 freeze | AST count | ✅ Verified (140) |
| `routes/oauth_callbacks.py` `_PROVIDERS` no longer contains `('polar',` | `grep -c "('polar'," `region | ✅ Verified (0) |
| `app.py` has 5 polar wiring lines (import, register, CSRF comment, csrf.exempt, exempt-set entry) | `grep "polar" app.py` | ✅ Verified (5 matches) |
| `routes/polar.py` defines `bp = Blueprint('polar', …, url_prefix='/polar')` + 3 route handlers (`oauth_start`, `oauth_callback`, `webhook`) | grep + line numbers | ✅ Verified |
| `routes/polar_ingest.py` exports `ingest_event` + 5 per-event ingesters + the AccessLink `_get_json` helper | grep | ✅ Verified |
| Pure helpers `_iso_duration_to_min` + `_extract_notifications` behave on cases including `PT1H30M0S`, `PT45M`, `PT30S`, single-event payload, batched `available-notifications` payload | inline `python3` execution | ✅ Verified (all 12 cases pass) |
| `provider_auth.py` unchanged this session — first real test of the "provider-agnostic" claim from PR1 §7 holds | `git status routes/provider_auth.py` | ✅ Verified (not modified) |

No drift between this handoff's narrative and on-disk state.

The same "can't exec init_db.py without Flask" gap PR1 §6 + PR2 §4 flagged applies: behaviour of the migrations themselves can only be exercised at deploy time against a live PG connection. AST-parse + grep anchors are the pre-deploy guard. Same goes for `routes/polar.py` + `routes/polar_ingest.py` — module imports require Flask + requests, which the sandbox doesn't have; AST-parse confirms syntactic validity and the pure helpers exercise the logic that doesn't touch I/O.

---

## 5. Mechanically-applicable instructions for next session (Rule #11)

### 5.0 Pre-deploy verification (must run before PR3 reaches production)

Asymmetric with PR1 §5.0 + PR2 §5.0 — Polar has more pre-deploy ceremony than COROS because of the partner-user registration step + the separate webhook secret env var.

1. **Confirm Polar AccessLink surface.** Check current Polar partner docs and confirm:
   - Authorize URL = `https://flow.polar.com/oauth2/authorization` (or update `POLAR_AUTH_URL`)
   - Token URL = `https://polarremote.com/v2/oauth2/token` (or update `POLAR_TOKEN_URL`)
   - Token endpoint accepts HTTP Basic auth with `client_id:client_secret` (NOT body credentials — different from COROS)
   - Token response includes `access_token` + `x_user_id` (the code also accepts `polar-user-id` / `user_id` fallbacks; confirm Polar still emits `x_user_id`)
   - Webhook signature scheme = HMAC-SHA256 hex of raw body using a separate `POLAR_WEBHOOK_SECRET`, header `Polar-Webhook-Signature` (verify Polar hasn't changed header name since)
   - Exercise transaction endpoint shape matches: POST returns `{transaction-id, resource-uri}`, GET resource-uri returns `{exercises: [...]}`, PUT resource-uri commits

2. **Register the Polar developer-portal redirect_uri.** Must be `https://aidstation-pro.vercel.app/polar/oauth/callback` (mirrors PR1's COROS deviation from `/auth/<slug>/callback`).

3. **Set Vercel env vars** in Production + Preview (marked Sensitive):
   - `POLAR_CLIENT_ID`
   - `POLAR_CLIENT_SECRET`
   - `POLAR_WEBHOOK_SECRET` (issued by Polar at webhook-URL registration time — separate from `POLAR_CLIENT_SECRET`)
   - Optionally `POLAR_AUTH_URL` / `POLAR_TOKEN_URL` / `POLAR_API_URL` if Polar rotates its public host paths

4. **Register the webhook URL via Polar's partner API** *after* env vars are live: `POST https://www.polaraccesslink.com/v3/webhooks` with `{"events": ["EXERCISE", "SLEEP", "NIGHTLY_RECHARGE", "CARDIO_LOAD", "CONTINUOUS_HEART_RATE"], "url": "https://aidstation-pro.vercel.app/polar/webhook"}`. Polar's response includes the `signature_secret_key` — that's the value to set as `POLAR_WEBHOOK_SECRET` (in env, then redeploy).

5. **Monitor first cold-start `_PG_MIGRATIONS` run on Neon.** Three new statements (the partial UNIQUE indexes). Spot-check post-deploy:
   ```
   \d cardio_log     -- expect cardio_log_{polar_exercise,coros_label,wahoo_workout}_uidx
   ```

6. **PR1 §5.0 COROS pre-deploy verification** (env vars + redirect_uri + Open API surface) is still owed if not yet completed. Independent of PR3 but mentioned here because the live-deploy spot-check for PR3 will catch any cross-provider regression.

### 5.1 PR4+ candidates — Andy's choice

**Pre-step reads (Rule #13 ordering, every candidate):**

1. **`aidstation-sources/CLAUDE.md` fully** — Rule #13 first re-read.
2. `aidstation-sources/handoffs/V5_Implementation_PR3_Closing_Handoff_v1.md` (this file).
3. `aidstation-sources/handoffs/V5_Implementation_PR2_Closing_Handoff_v1.md` — the predecessor for the §5.1 candidate menu and the v16→v17 deferred-bump pattern.
4. `aidstation-sources/Project_Backlog_v16.md` — D-50 row currently reads "🟢 PR1 shipped" but is now stale: PR2 + PR3 also shipped; first PR4 action is the v16→v17 bump per §5.4 below.

The candidate menu carries forward from PR2 §5.1 with one slot filled (Option C = Polar = ✅ PR3) and one slot opened (the v16→v17 bump owed). Recommended sequence revised in §5.2.

#### Option B — COROS + Polar frontend + Account Config 1 management screen (recommended next)

Now substantially more valuable than after PR2: two real providers visible on the management screen. Scope from PR2 §5.1:

- New template + route for Account Config 1 (status / disconnect / re-auth / scope display per v5 §Account Config 1).
- Connect buttons for COROS (`/coros/oauth/start?return_to=…`) and Polar (`/polar/oauth/start?return_to=…`).
- Disconnect path: write `STATUS_REVOKED` + null tokens via a new `provider_auth.disconnect` helper.
- v5 §A.2.7 `?<provider>_connected=1` query-param handling (passive prompt for prefill UI).

Likely 4–5 files (template, route handler, possibly partial render + a `provider_auth.disconnect` helper + handoff). At ceiling.

#### Option D1 — v5 frontend onboarding flow (Step 2 connect + prefill provenance)

Largest substantive frontend PR. Now unblocked by having two real providers. The PR2 §5.1 framing held: D-58 schema (PR1) + D-59/60/61 schema (PR2) + a second real provider (PR3) means D can finally be built against a fully-stable backend surface.

Probably splits into D1 (connect step at Step 2 + `coros_connected=1` / `polar_connected=1` prompt) + D2 (`athlete_profile_field_provenance` prefill UX + KNOWN_PROFILE_FIELDS registry — Open Item #17 lands here) + D3 (locale-creation flow + Mapbox chain detection from `chain_registry.py`). 5+ files per sub-PR; can't fit in one.

#### Option E — 14-day connect-provider nudge background job

Unchanged from PR1 §5.1. Small standalone.

#### Option F (new) — Polar refresh-on-401 if it ever surfaces

Polar tokens are documented as long-lived (`_POLAR_DEFAULT_TTL = 10 years`) but if AccessLink ever returns 401 to a `polar_ingest._get_json` call, the current code just raises and the webhook handler records the error. A retry-with-re-auth-prompt path would need a one-time route (`/polar/oauth/start?return_to=/profile/connections`) that the error response redirects to. Defer until 401s actually show up in `webhook_events.error`. Tracker item only.

#### Option G (new) — Polar `coros_ingest` rewrite to use ON CONFLICT

Now that `cardio_log_coros_label_uidx` exists (PR3 added it for free while fixing Polar's race window), `coros_ingest._ingest_activity`'s SELECT-then-INSERT-or-UPDATE pattern can be simplified to a single `INSERT … ON CONFLICT (user_id, coros_label_id) WHERE coros_label_id IS NOT NULL DO UPDATE`. Mechanical rewrite, no behavior change at deploy time — just less code. ~30-line diff. Could be folded into Option B's PR or shipped standalone.

### 5.2 Recommended sequence (revised post-PR3)

**v17 bump (§5.4) → B → D1 → E → D2 → D3**, with **F** and **G** as opportunistic drop-ins.

Per PR1 §5.1 + PR2 §5.2: A and C are done (PR2 and PR3 respectively); B should follow now that two providers are real and visible; D unblocks once B's management screen exists; E is a small standalone whenever convenient. F is a watch item; G is a free cleanup.

The v17 bump should be the first action of the next session before any new code (mirrors PR2's first action being the v15→v16 bump executed at session start, except PR2 bundled it with a substantive PR; PR4 might either bundle with B as PR2 did, or ship standalone like PR1 nearly recommended).

### 5.3 Standing items not on the critical path (carried from PR2 §5.3, updated)

- **D-52 Catalog Migration Phase 1** — fuzzy-match HITL alias audit. Independent.
- **D-54 SQLite collapse** — Catalog Migration Phase 5. Queued.
- **D-55 Garmin onto `provider_auth`** — paused until Garmin reopens API access. The PR3 successful unmodified-pass on `provider_auth.py` confirms the helper is provider-agnostic; Garmin reopening would be ~PR1-shaped work (just slot `routes/garmin.py` into the same pattern).
- **D-57 Research re-evaluation cadence design.**
- **D-62 webhook_events retention prune** — now overdue. Both COROS (PR1) and Polar (PR3) webhook handlers will accumulate audit rows including signature-failed rows and unmapped-user rows. First real prune candidate in v1.
- **Open Item #17 — `KNOWN_PROFILE_FIELDS` registry** — `athlete_profile_field_provenance.field_name` still free-text TEXT. Lands with Option D2 prefill UX.
- **DATABASE.md update** — 8+ undocumented additions now. Frontend-PR companion (Option B is the natural anchor: once a management-screen UX exists, the right time to draft user-facing column descriptions is when there's a UX to anchor them to).
- **PROVIDERS_SCHEMA.md update** — two real providers now (COROS + Polar). The "Phase 1+ planned" framing is materially obsolete. Worth a docs-only pass alongside Option B.
- **lat/lng precision** (PR2 §6 carry-over) — `DOUBLE PRECISION` instead of D-59 §9's `REAL`. Still flagged; still defensible.
- **Polar refresh-on-401** (new this session) — Option F above. Watch item.
- **`coros_ingest._ingest_activity` ON CONFLICT cleanup** (new this session) — Option G above. Cleanup candidate.

### 5.4 Backlog row update (deferred to PR4)

`Project_Backlog_v16.md` D-50 row currently reads `🟢 PR1 shipped 2026-05-14 (commit \`3628ca6\`); 🟡 follow-on PRs pending`. Now stale — PR2 + PR3 also shipped. Per Rule #12 this is a v16→v17 bump.

Mechanical edits for PR4 to execute as its first action (same shape as PR2's executed v15→v16 bump):

1. **Copy** `aidstation-sources/Project_Backlog_v16.md` → `aidstation-sources/Project_Backlog_v17.md`.
2. **In v17**, locate the D-50 row. The status cell currently reads:
   ```
   🟢 PR1 shipped 2026-05-14 (commit `3628ca6`); 🟡 follow-on PRs pending
   ```
   Replace it verbatim with:
   ```
   🟢 PR1 + PR2 + PR3 shipped 2026-05-14 (commits `3628ca6`, `686bb40`, `<PR3-merge-commit>`); 🟡 frontend (Option B/D1) pending
   ```
   (the `<PR3-merge-commit>` placeholder gets the actual sha once PR3's merge commit lands on `main`; if PR3 is shipped via squash or merged-via-feature-branch, use that resulting commit hash).
3. **Update the notes column** for D-50 to reference `V5_Implementation_PR3_Closing_Handoff_v1.md` §5.1 and the PR4+ candidate menu (Option B/D1/E/F/G + recommended sequence B→D1→E→D2→D3 with F and G as opportunistic drop-ins). The PR3 §5.0 pre-deploy verification checklist (the partial UNIQUE indexes + Polar env vars + webhook-URL registration call) should also be cited.
4. **Update the predecessor-revisions list** in v17's top-of-file `**File revision:**` block — bump from v16 to v17 with a full provenance entry referencing this handoff.
5. **In `aidstation-sources/CLAUDE.md`** "Authoritative current files," bump backlog reference v16 → v17 (single-line edit, exactly the pattern PR2 executed for v15 → v16).

---

## 6. Open items / honest flags

- **Polar AccessLink surface not verified offline.** Same risk class as PR1's COROS. URL placeholders + payload field-name assumptions are documented-public-API best-effort; env-var overrides for the three URL bases exist so a Polar rotation doesn't need a code change. The §5.0 pre-deploy verification block is mandatory before this is real.
- **HTTP Basic on the token endpoint is a Polar deviation from COROS's body-credential pattern.** Captured in `routes/polar.py` lines around the `requests.post(_POLAR_TOKEN_URL, auth=(client_id, client_secret), …)` call. If a hypothetical PR4 provider also uses body credentials, the diversity here means the third provider gets to confirm whether body vs. Basic is the more common Polar-style or COROS-style choice across the cohort. Either is supported by `requests.post`; the per-provider module branches on the right call.
- **Two-phase `provider_auth` status flip (pending_backfill → active) is a Polar deviation.** COROS does the upsert with `status=active` atomically because COROS has no post-token registration call. Polar's registration call is a side-effect on Polar's servers; if it fails after a successful token exchange, leaving the row at `pending_backfill` (or flipping to `error`) keeps the token durably persisted for retry. The status enum is unchanged — both values were already in Integration v4 §4.1. If a future maintenance route ships to retry stuck `pending_backfill` rows, the same `_register_polar_user` helper can be called from there.
- **HMAC-SHA256 webhook verification on `POLAR_WEBHOOK_SECRET`.** Separate env var from `POLAR_CLIENT_SECRET`. This is the most error-prone wiring step in PR3 — they look interchangeable in environment-variable lists but they aren't; Polar issues `POLAR_WEBHOOK_SECRET` only when the webhook URL is registered via the partner API. The `routes/polar.py` docstring + the `app.py` comment block both flag this. If signature verification fails in deploy and the env var IS set, the most likely cause is having pasted `POLAR_CLIENT_SECRET` into the `POLAR_WEBHOOK_SECRET` slot.
- **Transaction-fetch commit on partial-ingest failure.** If any GET in the exercise-fetch loop raises, the PUT commit never runs — Polar will re-deliver those exercises in the next transaction (after their auto-discard timeout). The UPSERT path is idempotent, so re-delivery overwrites the same rows with the same values; no duplicate rows; no inconsistent state. The trade-off: a single bad exercise URL blocks commit for the whole transaction. Could be relaxed in a future PR (commit per-exercise rather than per-transaction) if Polar's transaction-discard latency causes operational pain.
- **Polar webhook delivery shape (single-event vs `available-notifications` batch) is doc-divergent across Polar revisions.** Both shapes are supported by `_extract_notifications`. The audit row inserts one per notification regardless of which shape arrived, so the audit log is per-event-uniform; this is a deliberate denormalization vs. recording the raw batch as a single row.
- **No `expires_at` enforcement for Polar tokens.** Default TTL `_POLAR_DEFAULT_TTL` is 10 years. Per Polar docs the tokens don't expire; the column value is informational only (mirrors Integration v4 §4.1 "store nominal TTL where provider supplies one"). If Polar starts honoring `expires_in` as a real value, the existing logic switches over automatically — we parse `expires_in` first and only fall back to the default when absent.
- **No refresh path exercised this session.** Polar tokens are long-lived. The `provider_auth.py` refresh helper signature exists but isn't called by `routes/polar.py`. First real refresh test is whichever provider lands next that DOES have short-lived tokens (Wahoo, 2h; Strava, 6h). Open Item until then.
- **`_PROVIDERS` ordering** — dropping `('polar', 'Polar')` mid-list (between Strava and Wahoo) leaves the comment block referencing Polar two slugs after where Polar used to live. Cosmetic; comment is still findable via grep. Could re-sort the list in a docs-only PR.
- **6 files this session counting the handoff** (5 substantive + handoff). One over CLAUDE.md ceiling, same one-over pattern PR1 hit. PR2 was on-ceiling (4 substantive). The Polar full-pipeline scope is genuinely heavier than the COROS shipping in PR1 (transaction-fetch handshake + 4 direct-pull event types + the partial-UNIQUE-index cleanup that PR1 left as a follow-up); 5 substantive files is the smallest the work decomposes to without splitting Polar across two PRs (which would have meant Polar OAuth in one PR and Polar webhook+ingest in another — fragile because the OAuth-only PR has no way to exercise the registration call without webhook traffic).
- **No tests added.** Inline `python3` execution of the two pure helpers (`_iso_duration_to_min`, `_extract_notifications`) is the closest this PR comes to test infrastructure. The PR1 §6 + PR2 §6 framing carries: `provider_auth.py` is still the natural first unit-test surface, with `polar_ingest._iso_duration_to_min` + `polar.py`'s `_extract_notifications` as obvious second-pass candidates.

---

## 7. Gut check

**What this session got right.**

- **Two architectural forks surfaced cleanly with options + tradeoffs before any code.** Callback URL convention (Option A vs B) and PR3 scope (webhook-only vs full pipeline) were both genuine architectural choices that would have shaped the file count and the PR4+ candidate menu. Stop-and-ask discipline let Andy pick A + full-pipeline; the resulting scope is exactly what the handoff §3 + §4 describe.
- **`provider_auth.py` held without edits.** PR1 §7's "this helper is provider-agnostic" claim was conjecture until a second real provider exercised it. PR3's Polar — with HTTP Basic on the token endpoint, two-phase status flip across a registration call, separate webhook secret env var — went through entirely without touching the helper. The provider-specific shape lives in `routes/polar.py`; the storage shape lives in `provider_auth.py`. The clean separation is real.
- **Partial-UNIQUE indexes shipped alongside the consumer that needs them.** PR1 §6 flagged the race window; PR2 didn't have a touch on `init_db.py` that made sense to fold them into; PR3 needed `cardio_log_polar_exercise_uidx` to use `ON CONFLICT` in `polar_ingest._upsert_exercise`, so adding the parallel `coros_label_uidx` + `wahoo_workout_uidx` "while we're touching the file" (per PR2 §5.1 Option C) was free. COROS's defensive SELECT-then-INSERT-or-UPDATE pattern can now be rewritten to `ON CONFLICT` as opportunistic cleanup (Option G).
- **HMAC vs plaintext-headers + transaction-fetch vs push-payload framed as the Polar-specific shape, not as "weird".** Both deviate from COROS's pattern; both are honest reflections of how Polar's API works. The handoff §3.2 + §3.3 are explicit about which choices are Polar idioms vs. AIDSTATION conventions, so a future PR4 provider can decide on a per-axis basis which one they look like.
- **Backlog v16→v17 deferred, not glossed.** §5.4 is the exact PR1-style mechanical instructions for PR4 to execute. The pattern of "PR1 deferred its own bump, PR2 executed it then deferred its own, PR3 deferred again because of one-over-ceiling load, PR4 executes it" is honest about how the bump cycle accumulates lag — not great, but explicit.

**Risks.**

- **First Neon migration run carries 3 statements that were never PG-validated locally.** Tiny risk surface vs. PR2's 21-statement run, but partial-UNIQUE-index syntax has more PG-specific corners than plain table DDL. The `WHERE … IS NOT NULL` predicate must be PG-side and immutable; the migration loop catches per-statement exceptions silently, so a syntax error would leave the index missing and `polar_ingest._upsert_exercise`'s `ON CONFLICT` would fail with a missing-constraint error on the first live exercise. Spot-check post-deploy (`\d cardio_log`) catches this.
- **Polar `/v3/users` registration is destructive on the partner-user relationship side.** A failed registration leaves a dangling Polar-side partner row that may or may not be auto-cleaned up — depends on Polar's internal state. 409 is treated as success because re-connect should be idempotent on Polar's side. If a future scenario surfaces where 409 means "already registered to a different partner-user-id" (theoretically possible if Polar allows re-mapping), the current code silently flips to status=active without revalidating. Acceptable for v1 (Andy is sole user) but worth a comment.
- **The transaction-fetch loop's all-or-nothing commit pattern is fragile under transient network errors.** A single timeout on one of the exercise GETs blocks the PUT commit for the whole transaction; Polar redelivers all exercises 30 minutes later. Idempotency keeps state consistent; the cost is a 30-minute latency on visible data for one bad fetch. Could split commit into per-exercise (commit after each successful upsert) but that requires a separate PUT per exercise, which Polar's transactional model doesn't support — would need a different ingestion path. Not in PR3 scope.
- **Two webhook secrets (`POLAR_CLIENT_SECRET` vs `POLAR_WEBHOOK_SECRET`) are easy to swap.** Documented in routes/polar.py docstring + app.py comment, but the actual mismatch only surfaces at the first webhook delivery (signature_ok=False, audit row written, 401 returned). Operationally low-cost to fix (correct the env var + redeploy) but the failure is silent in the sense that no athlete-facing UI notices.
- **Backlog v16→v17 lag.** The bump-pattern lag (PR1 deferred → PR2 executed PR1's + deferred its own → PR3 deferred PR2's + its own = PR4 owes a two-PR bump) accumulates. If PR4 also defers, the v17 backlog narrative will be three PRs behind the code state. The §5.4 mechanical instructions exist to make the bump trivially executable; the only risk is if a future session reads the stale v16 backlog and Rule #9-reconciliation fails to flag the gap.

**What might be missing.**

- **No `provider_auth.disconnect` helper.** The v5 Account Config 1 management screen will need it (write `STATUS_REVOKED` + null `access_token` / `refresh_token` / `provider_user_id` + bump `updated_at`). Trivial to add — 5-line function call. Could naturally land with Option B (frontend PR).
- **Polar webhook URL registration is a manual partner-API call.** The §5.0 §4 step describes it as a one-shot `POST /v3/webhooks` with curl; there's no in-app code path. v2's product premise (real cohort with self-serve provider connect) would need this to be a setup-time route. Defer to v2 entirely; in v1 it's a one-time operator step.
- **No retry strategy for the registration call.** If `POST /v3/users` returns 500-class transient errors, the user lands at `status=error` and the next OAuth retry has to redo the whole flow. A small retry-on-5xx loop (2–3 attempts with backoff) inside `_register_polar_user` would be honest robustness. Not added because failure-class is rare and the existing flow recovers on next OAuth attempt; flagged as opportunistic.
- **Polar AccessLink supports more event types than we handle.** `TRAINING_TARGET_NEW`, `TRAINING_TARGET_DELETED`, `USER_DELETED`, `BENCHMARK_NEW` aren't in the dispatcher. The default branch in `ingest_event` is a no-op + info-log; the raw payload is preserved in `webhook_events.payload`. Acceptable v1 surface; future PRs can extend.
- **No test for the `pending_backfill → active` two-phase flip under registration failure.** The code path is exercised in production if Polar's `/v3/users` ever 5xx's; offline I confirmed by reading. A unit test against a stub `requests` would be honest coverage.

**Best argument against this session's scope.**

PR3 chose the full pipeline (Option C-full) over webhook-only (Option C-narrow). The counter: webhook-only would have shipped Polar's auth + webhook recording in ~4 files (no `polar_ingest.py`), staying under ceiling, deferring all the per-event branch decisions to a PR4 that could re-evaluate after seeing real Polar webhook traffic in `webhook_events.payload`. The all-at-once approach codes against Polar's documented API surface without ever having seen real payloads; if Polar's actual responses differ from the documented shape (field naming variants, nested vs. flat, missing optional fields), `polar_ingest.py` would carry assumption mismatches that surface only at first real ingestion.

Counter to the counter: webhook-only would have left the per-provider tables empty until PR4 — `polar_sleep`, `polar_nightly_recharge`, etc. unwritten — and the partial-UNIQUE-index on `cardio_log_polar_exercise_uidx` would have been dead schema without a writer. Andy's "full pipeline" choice plus the COROS precedent (PR1 shipped both auth + ingest in one PR) make the all-at-once decision consistent. The pre-deploy verification block + the env-var URL overrides are the protection: if Polar's surface differs from documented, the overrides + the failure-mode logging surface the gap fast.

Alternatively, Polar could have shipped without the partial-UNIQUE-index fixup (saving 3 statements in `init_db.py`) by keeping `_upsert_exercise` on the SELECT-then-INSERT-or-UPDATE pattern `coros_ingest._ingest_activity` uses. Counter: the SELECT-then-INSERT race is documented in PR1 §6 as a real bug under high webhook fan-out; folding the fix in here costs 3 lines of SQL and unblocks future ON CONFLICT rewrites for both providers. The marginal scope cost is well under the marginal correctness benefit.

---

## 8. Forward pointers

- **Next session:** PR4 = either standalone v16→v17 backlog bump (small, ~2 files: backlog + CLAUDE.md) or Option B frontend bundled with the bump (the PR2 style). The §5.4 mechanical instructions are executable either way.
- **Before next code lands:** PR3 §5.0 pre-deploy spot-check on Neon + Polar env vars + webhook URL registration + Polar developer-portal redirect_uri. PR1 §5.0 COROS pre-deploy checklist is still owed if not yet completed.
- **First action of next session:** Rule #9 reconciliation. Specifically: confirm PR3 commit landed (this session's last commit on `claude/review-v5-handoff-t7KBL`); confirm `_PG_MIGRATIONS` totals 207 statements; confirm `routes/polar.py` + `routes/polar_ingest.py` + the polar wiring in app.py exist on disk; spot-check the v16 backlog D-50 row is stale (it is — that drives the v17 bump as PR4's first action).

**Rules in force, unchanged:**

- #9 session-start verification
- #10 session-end verification
- #11 mechanically-applicable deferred edits — §5.4 v16→v17 bump is the executable owed item
- #12 numeric version suffixes (backlog v16 → v17 owed)
- #13 every closing handoff names CLAUDE.md as the first re-read — **applied: §5.1 forward-pointer reads CLAUDE.md as item 1.**

---

*End of V5 Implementation PR3 closing handoff. Second real OAuth provider shipped with full pipeline; `provider_auth.py` confirmed provider-agnostic on its first real second-consumer test. Next: Andy's choice among PR4 candidates in §5.1 (Option B / D1 / E / F / G); v17 backlog bump owed as first PR4 action regardless of which substantive option is chosen.*
