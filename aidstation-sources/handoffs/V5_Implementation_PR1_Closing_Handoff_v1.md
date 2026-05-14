# V5 Onboarding Implementation PR1 — Closing Handoff

**Session:** First substantive code session of the v5 onboarding implementation arc. Ships the §5.0 LOCKED 5-file backend bundle: D-58 schema additions + provider-agnostic `provider_auth` helper + COROS as the first real OAuth provider on `provider_auth`. This is also PR1 of the D-50 wiring track resumption (the A+B interleaved choice from `V5_Onboarding_Spec_Closing_Handoff_v1.md` §5.1).
**Date:** 2026-05-14
**Predecessor handoff:** `V5_Onboarding_Spec_Closing_Handoff_v1.md` (its §5.0 is the PR1 scope this session executes).
**Branch:** `claude/review-onboarding-spec-IbN7W`
**Commit:** `3628ca6` — *PR1: D-58 schema + provider_auth helper + first real COROS OAuth* (5 files, 778 insertions / 10 deletions).
**Status:** ✅ Code shipped + merged to `main`. 🟡 Frontend (connect step UI, prefill UX, §A.2.5 prompt, per-day windows, locale-creation flow), D-59/D-60/D-61 schema migrations, other-provider OAuth flows, and the 14-day nudge job are all PR2+.
**Time-on-task:** Single chat. Substantive files: **5** (init_db.py, routes/provider_auth.py [new], routes/coros.py [rewrite], routes/coros_ingest.py [new], routes/oauth_callbacks.py). At the 5-file ceiling. Plus this handoff (6 total — same one-over-ceiling pattern flagged in V5 spec handoff §7).

---

## 1. Session-start verification (Rule #9)

Verified the V5 spec handoff's claimed state before any new work.

| Claim | Anchor | Result |
|---|---|---|
| `Athlete_Onboarding_Data_Spec_v5.md` exists at 878 lines with §A.2 prefill mechanics + §G rewrite + §J locale-creation flow + Account Config 3 v5 enums | `wc -l` + section grep | ✅ Verified |
| `Onboarding_D58_Design_v1.md` §7.1 + §7.2 give complete DDL for `athlete_profile_field_provenance` + `account_nudges` | Read of §7 | ✅ Verified |
| `routes/coros.py` is a 19-line stub matching `D50_Phase1_Schema_Closing_Handoff_v1.md` description | `wc -l` + read | ✅ Verified |
| Branch `claude/review-onboarding-spec-IbN7W` exists; working tree clean | `git branch --show-current` + `git status --short` | ✅ Verified |
| `provider_auth` + `webhook_events` + COROS per-provider tables already in `_PG_MIGRATIONS` (from D-50 Phase 1) | Read of init_db.py §1655+ | ✅ Verified |
| Existing OAuth-callback pattern in `routes/oauth_callbacks.py` — single parameterized stub at `/auth/<slug>/callback`, COROS listed in `_PROVIDERS` | Read | ✅ Verified |

No drift between V5 spec handoff narrative and on-disk state.

---

## 2. Files shipped this turn

All on branch `claude/review-onboarding-spec-IbN7W`. Single commit (`3628ca6`).

| # | File | Type | Notes |
|---|---|---|---|
| 1 | `init_db.py` | Edit (+41 lines on `_PG_MIGRATIONS`) | Three new PG-only tables: `athlete_profile_field_provenance` (D-58 §7.1) with `apfp_user_idx` + partial `apfp_user_source_idx WHERE source = 'manual_override'`; `account_nudges` (D-58 §7.2); `disclosure_acknowledgments` (Account Config 3 storage, built inline per §5.0 sanity-check #2 — no existing helper existed) with composite descending index on `(user_id, disclosure_id, acknowledged_at DESC)` to support `MAX(acknowledged_at)` queries. SQLite block stays frozen per Integration v4 §2.5. |
| 2 | `routes/provider_auth.py` | New (~145 lines) | Provider-agnostic helper. Exports `STATUS_ACTIVE / STATUS_REVOKED / STATUS_ERROR / STATUS_PENDING_BACKFILL / STATUS_MIGRATING` constants matching Integration v4 §4.1. Functions: `upsert_auth` (column allow-list + status enum validation + `RETURNING id`), `get_auth`, `get_auth_by_provider_user_id` (for webhook user resolution), `set_status`, `rotate_webhook_token` (Pattern A — UPSERT on every event), `record_oauth_scope_ack` (writes Account Config 3 row). |
| 3 | `routes/coros.py` | Rewrite (19 → 341 lines) | Three routes: `GET /coros/oauth/start` (generates state token, stashes `return_to` with same-origin guard, redirects to COROS authorize URL); `GET /coros/oauth/callback` (constant-time state compare via `hmac.compare_digest` → POST token exchange → extract `access_token` + `refresh_token` + `openId` → `provider_auth.upsert_auth` with `status=active`, `token_expires_at=now+30d`, `registered_at=now` → `record_oauth_scope_ack(version_id='2026-05-14')` → redirect to `return_to?coros_connected=1` for the §A.2.5 prompt trigger); `POST /coros/webhook` (`client`/`secret` header verify with constant-time compare → row into `webhook_events` with `signature_ok` set + `user_id` resolved via `get_auth_by_provider_user_id` → dispatch to ingestion → record error in `webhook_events.error` if it throws but still 200 to avoid COROS retry storm). |
| 4 | `routes/coros_ingest.py` | New (~205 lines) | First-pass dispatcher on payload shape — `sportDataList` → `cardio_log` (defensive UPSERT on `coros_label_id` via SELECT-then-INSERT-or-UPDATE since no UNIQUE constraint), `dailyDataList` → `coros_daily_summary` (ON CONFLICT UPSERT on `(user_id, happen_day)`), `hrvDataList` → `coros_hrv_samples` (ON CONFLICT UPSERT on `(user_id, timestamp_s)`). 10 COROS sport-mode integers mapped to v1 `cardio_log.activity` vocabulary; unknowns fall through to `'other'`. Unit conversions m→mi, m→ft. |
| 5 | `routes/oauth_callbacks.py` | Edit (1-line removal + 3-line comment) | Drop `('coros', 'COROS')` from `_PROVIDERS`. Comment notes the real callback is now at `/coros/oauth/callback` and explains the redirect_uri requirement. |
| — | `aidstation-sources/handoffs/V5_Implementation_PR1_Closing_Handoff_v1.md` | New (this file) | Session-end book-keeping. |

**Files explicitly NOT touched:**

- `app.py` — no edits needed. `coros.webhook` is already in `_AUTH_EXEMPT_ENDPOINTS` (D-50 Phase 1 wiring). The new `coros.oauth_start` + `coros.oauth_callback` endpoints are session-required (read `current_user_id()`), so they correctly fall through to the auth gate.
- `routes/oauth_callbacks.py` `_AUTH_EXEMPT_ENDPOINTS` — no additions; the OAuth callback is browser-initiated with a session cookie.
- `Athlete_Onboarding_Data_Spec_v5.md` / `Onboarding_D58_Design_v1.md` — input contracts; specs don't edit from implementation rounds.
- `Project_Backlog_v15.md` — **deferred.** D-50 row's status flip (🟡 unblocked → 🟢 PR1 shipped) wants a v16 bump per Rule #12. Out of scope for this session's 5-file ceiling; lands at next session start.
- `DATABASE.md` — the three new tables (`athlete_profile_field_provenance`, `account_nudges`, `disclosure_acknowledgments`) are not documented in DATABASE.md yet. Deferred to PR2 alongside D-59/60/61 schema additions, so the DATABASE.md update is one consolidated edit.
- `PROVIDERS_SCHEMA.md` — its "Phase 1+ planned" framing is now partially obsolete for COROS, but the rewrite is a documentation pass that pairs naturally with shipping more providers; defer.

---

## 3. What landed

### 3.1 D-58 schema (PG-only)

```sql
CREATE TABLE IF NOT EXISTS athlete_profile_field_provenance (
    id SERIAL PRIMARY KEY,
    user_id INTEGER NOT NULL REFERENCES users(id),
    field_name TEXT NOT NULL,
    source TEXT NOT NULL,
    source_provider_id INTEGER REFERENCES provider_auth(id),
    source_synced_at TIMESTAMP,
    last_updated_at TIMESTAMP NOT NULL DEFAULT NOW(),
    UNIQUE (user_id, field_name)
);
CREATE INDEX apfp_user_idx ON athlete_profile_field_provenance (user_id);
CREATE INDEX apfp_user_source_idx ON athlete_profile_field_provenance (user_id, source) WHERE source = 'manual_override';

CREATE TABLE IF NOT EXISTS account_nudges (
    id SERIAL PRIMARY KEY,
    user_id INTEGER NOT NULL REFERENCES users(id),
    nudge_type TEXT NOT NULL,
    created_at TIMESTAMP NOT NULL DEFAULT NOW(),
    displayed_at TIMESTAMP,
    dismissed_at TIMESTAMP,
    UNIQUE (user_id, nudge_type)
);

CREATE TABLE IF NOT EXISTS disclosure_acknowledgments (
    id SERIAL PRIMARY KEY,
    user_id INTEGER NOT NULL REFERENCES users(id),
    disclosure_id TEXT NOT NULL,
    version_id TEXT,
    scopes_granted TEXT,
    delivery_method TEXT NOT NULL DEFAULT 'in_app',
    acknowledged_at TIMESTAMP NOT NULL DEFAULT NOW()
);
CREATE INDEX disclosure_acks_user_idx ON disclosure_acknowledgments (user_id, disclosure_id, acknowledged_at DESC);
```

Three rows of provenance behaviour are now achievable:

- The §A.2 prefill mechanics (track per-field source / sync timestamp / `manual_override` stickiness).
- The 14-day connect-provider nudge state (created → displayed → dismissed lifecycle).
- The Account Config 3 disclosure-ack writes for OAuth scope acknowledgments, Mapbox geocoding consent, gym-profile sharing consent, etc. (one row per ack event; query `MAX(acknowledged_at)` per `(user_id, disclosure_id)` for current state).

### 3.2 `routes/provider_auth.py` contract

Status convention (Integration v4 §4.1 + PROVIDERS_SCHEMA.md §5.1 §4.1):

```python
STATUS_ACTIVE = 'active'          # successfully connected
STATUS_REVOKED = 'revoked'        # athlete disconnected / provider revoked
STATUS_ERROR = 'error'            # last sync errored
STATUS_PENDING_BACKFILL = 'pending_backfill'  # connected but historical pull in progress
STATUS_MIGRATING = 'migrating'    # one-shot used during garmin_auth → provider_auth
```

The D-58 / v5 design docs use `'connected'` colloquially (e.g., D-58 §6.1, v5 §A.2.5). The on-disk schema does NOT have a `connected` value; readers should mentally substitute `STATUS_ACTIVE` whenever a design doc says "connected." Captured as a module docstring comment.

UPSERT contract:

```python
pa.upsert_auth(
    db, user_id=42, provider='coros',
    access_token='…', refresh_token='…',
    token_expires_at=now+timedelta(days=30),
    provider_user_id='openId-value', scopes='activity wellness sleep hr',
    status=pa.STATUS_ACTIVE, registered_at=now,
)
```

Unknown columns raise `ValueError` (typos surface loudly); invalid status raises `ValueError`. ON CONFLICT (`user_id`, `provider`) DO UPDATE updates only the supplied columns + `updated_at = NOW()`.

### 3.3 COROS OAuth flow

```
GET /coros/oauth/start?return_to=/account/connections
   → set session['coros_oauth_state'] = secrets.token_urlsafe(32)
   → set session['coros_oauth_return_to'] = return_to (same-origin guard)
   → 302 to {COROS_AUTH_URL}?client_id=…&redirect_uri=https://…/coros/oauth/callback
            &response_type=code&scope=activity wellness sleep hr&state=…

[user consents on COROS site]

GET /coros/oauth/callback?code=…&state=…
   → hmac.compare_digest(session.pop('coros_oauth_state'), received_state)
   → POST {COROS_TOKEN_URL} with code + client_id + client_secret + redirect_uri
   → extract access_token, refresh_token, openId (or data.openId)
   → pa.upsert_auth(status=active, token_expires_at=now+30d, …)
   → pa.record_oauth_scope_ack(version_id='2026-05-14')
   → 302 to {return_to}?coros_connected=1  [PR2 frontend reads this signal
                                            to trigger §A.2.5 prefill prompt]
```

Failure modes:
- Missing session state → 400.
- `code` missing → 400.
- COROS token endpoint 5xx / network error → 502.
- Missing env credentials → 503 with `current_app.logger.error`.
- User denied consent (`?error=…` from COROS) → 302 to `return_to?coros_oauth_error=…` so the UI can surface "connect cancelled" without a generic 4xx.

### 3.4 COROS webhook flow

```
POST /coros/webhook (headers: client, secret; body: COROS push JSON)
   → constant-time compare client+secret against env COROS_CLIENT_ID / COROS_CLIENT_SECRET
   → resolve user_id via pa.get_auth_by_provider_user_id('coros', openId)
   → INSERT webhook_events (provider='coros', event_type=inferred, provider_user_id=openId,
                           entity_id=labelId|happenDay, user_id, payload=raw_body,
                           signature_ok)
   → if NOT signature_ok: return 401 envelope, no dispatch  [§4.2: audit but don't dispatch]
   → if signature_ok: coros_ingest.ingest_event(db, event_id, user_id, payload)
                      UPDATE webhook_events SET processed_at = NOW()
                      [or: SET processed_at = NOW(), error = exc on ingestion failure]
   → return COROS success envelope {"result":"0000","message":"ok"} (always 200 on
     signature-OK paths so COROS doesn't retry-storm; durable copy in webhook_events)
```

`event_type` inference: presence of `sportDataList` / `dailyDataList` / `hrvDataList` keys, in that order. `entity_id` extraction prefers `labelId` (activity dedup key), falls back to `happenDay` for daily summaries.

### 3.5 COROS ingestion mapping

| Payload shape | Target table | Dedup key | Field mapping |
|---|---|---|---|
| `sportDataList[]` | `cardio_log` (with `coros_label_id` set) | `(user_id, coros_label_id)` via SELECT-then-INSERT-or-UPDATE | mode→activity (10 mapped: run/cycle/swim/triathlon/strength/trail_run/hike/ski/ski_touring/rowing; else 'other'); totalTime→duration_min; distance·0.000621371→distance_mi; ascent·3.28084→elev_gain_ft; descent→elev_loss_ft; avgHr/maxHr/calorie/avgCadence/maxCadence pass-through; startTime ms-epoch→ISO date UTC |
| `dailyDataList[]` | `coros_daily_summary` | `(user_id, happen_day)` via `ON CONFLICT DO UPDATE` | rhr / calories / steps / ppgHrv / sleepAvgHr / sleepStartTime → sleep_start_ms / sleepEndTime → sleep_end_ms; raw payload preserved in `raw_payload`; happenDay normalised from YYYYMMDD int form to ISO date if needed |
| `hrvDataList[]` | `coros_hrv_samples` | `(user_id, timestamp_s)` via `ON CONFLICT DO UPDATE` | hrv, hr pass-through |
| Unknown shape | webhook_events.payload only (raw JSON) | — | Ingestion no-ops; data is re-derivable on a future ingestion pass without a re-fetch from COROS |

---

## 4. Session-end verification (Rule #10)

Anchor checks against on-disk state before composing this handoff.

| Claim | Anchor | Result |
|---|---|---|
| `_PG_MIGRATIONS` totals 183 statements (was 176 pre-PR) | AST count via `ast.parse` | ✅ Verified |
| All 5 changed files parse clean | `ast.parse` over each | ✅ Verified |
| `provider_auth.STATUS_ACTIVE == 'active'` (not `'connected'`) | `python -c "import routes.provider_auth as p; print(p.STATUS_ACTIVE)"` | ✅ Verified (`active`) |
| `_UPSERTABLE_COLUMNS` count = 9 (matches the writable subset of `provider_auth`) | Same | ✅ Verified |
| `coros_ingest._SPORT_MODE` has 10 mappings | Same | ✅ Verified |
| `routes/oauth_callbacks.py` `_PROVIDERS` no longer contains `'coros'` | `grep "'coros'" routes/oauth_callbacks.py` returns 0 in `_PROVIDERS` block | ✅ Verified |
| Branch + commit pushed to origin | `git push -u` + `git log` | ✅ Verified (commit `3628ca6`) |
| Three new tables present in the migration list | `grep "CREATE TABLE.*\(athlete_profile_field_provenance\|account_nudges\|disclosure_acknowledgments\)" init_db.py` returns 3 matches | ✅ Verified |
| `cardio_log.coros_label_id` column exists (D-50 Phase 1 prerequisite) | `grep "coros_label_id" init_db.py` | ✅ Verified (D-50 Phase 1, line 1790) |

No drift between this handoff's narrative and on-disk state.

---

## 5. Mechanically-applicable instructions for next session (Rule #11)

### 5.0 Pre-deploy verification (must run before PR1 reaches production)

These three steps are owed to PR1 before the feature is real for any user. They are deployment-time tasks, not code edits.

1. **Confirm COROS Open API surface.** Hit current COROS partner docs and confirm:
   - Authorize URL = `https://open.coros.com/oauth2/authorize` (or update `COROS_AUTH_URL` env)
   - Token URL = `https://open.coros.com/oauth2/accesstoken` (or update `COROS_TOKEN_URL`)
   - Token response shape includes `access_token`, `refresh_token`, `openId` (the code accepts both top-level `openId` and nested `data.openId` — confirm one of these is what COROS returns)
   - Webhook signature method = `client` + `secret` HTTP headers, plaintext compare against the registered API client_id + client_secret (this matches the existing stub docstring; verify COROS hasn't moved to HMAC since)
2. **Register the COROS developer-portal redirect_uri.** Must be `https://aidstation-pro.vercel.app/coros/oauth/callback` (NOT `/auth/coros/callback`, which is no longer the COROS path).
3. **Set Vercel env vars** in Production + Preview (marked Sensitive):
   - `COROS_CLIENT_ID`
   - `COROS_CLIENT_SECRET`
   - Optionally `COROS_AUTH_URL` / `COROS_TOKEN_URL` if COROS rotates its public host or version path
4. **Monitor first cold-start `_PG_MIGRATIONS` run on Neon.** The migration loop catches per-statement exceptions silently; if `athlete_profile_field_provenance` / `account_nudges` / `disclosure_acknowledgments` fail to apply, no other symptom surfaces until a query hits a missing table. Spot-check with `\d` in the Neon console after deploy.

### 5.1 PR2 candidates — Andy's choice

The implementation arc has multiple natural follow-on PRs. They are largely independent and can sequence either way. Recommend reading CLAUDE.md fully first (Rule #13), then this §5.1.

**Pre-step reads (Rule #13 ordering, every candidate):**

1. **`aidstation-sources/CLAUDE.md` fully** — Rule #13 first re-read.
2. `aidstation-sources/handoffs/V5_Implementation_PR1_Closing_Handoff_v1.md` (this file).
3. `aidstation-sources/handoffs/V5_Onboarding_Spec_Closing_Handoff_v1.md` §5.0 + §5.1 (the locked PR1 + the candidate list).
4. `aidstation-sources/Project_Backlog_v15.md` — note the D-50 row's status flip is pending a v16 bump (see §5.4 below).

#### Option A — D-59 / D-60 / D-61 schema PR (recommended next backend PR)

The schema half of the rest of the v5 onboarding spec. Symmetric to PR1's D-58 schema half — PG-only additions, no frontend touch.

- `init_db.py` `_PG_MIGRATIONS` additions: `daily_availability_windows` (D-61); `gym_profiles` + `locale_equipment_overrides` + `locale_toggle_overrides` (D-60); `locale_profiles` ALTER ADD ×11 columns (D-59 + D-60 + D-61: `locale_name`, `mapbox_id`, `lat`, `lng`, `chain_id`, `chain_name`, `category`, `manual_entry`, `place_payload`, `place_fetched_at`, `gym_profile_id`, `sharing_opt_out`, `preferred`).
- `chain_registry.py` (new) — Python module with the ~30-entry chain seed (D-59 §2 decision #8). No DB table; loaded at import time.

Exact DDL per v5 §J.1 / §J.2 / §G and the source design docs. Expect 3–4 files; comfortably under ceiling.

#### Option B — COROS frontend + Account Config 1 management screen

The smallest frontend PR that makes PR1 user-facing. Athlete clicks "Connect COROS" → kicks `/coros/oauth/start` → completes the loop → lands on Account Config 1 with the new connection visible.

- New template + route for Account Config 1 management (status / disconnect / re-auth / scope display per v5 §Account Config 1).
- `/coros/oauth/start` is already wired; frontend just needs an anchor.
- Disconnect path: write `STATUS_REVOKED` + null out tokens via `provider_auth.set_status` + a new helper.
- v5 §A.2.7 passive-notification UI for `?coros_connected=1` query-param signal (skipping for now; can land in PR3 with the prefill UX).

Likely 3–5 files (template, route handler, possibly a partial render). Tight scope.

#### Option C — Next provider OAuth (Polar or Wahoo)

Repeats PR1's COROS pattern for one more provider. Validates that `provider_auth.py` is genuinely provider-agnostic — anything COROS-specific that leaked into the helper surfaces here.

- New `routes/polar.py` (or `wahoo.py`) — same three routes (start, callback, webhook) using `pa.upsert_auth` + `pa.record_oauth_scope_ack`.
- Polar specifics: tokens don't expire (token_expires_at = NULL); registration call `POST /v3/users` after token exchange (sets `registered_at`); webhook HMAC verification using a separate `POLAR_WEBHOOK_SECRET` env var (issued by Polar at webhook registration time).
- Wahoo specifics: token refresh every 2h via `refresh_token`; per-user `webhook_token` rotates on every event (Pattern A — `pa.rotate_webhook_token`).
- New `<provider>_ingest.py` for the per-provider tables already in PG (`polar_sleep`, `polar_nightly_recharge`, `polar_cardio_load`, etc.; or `wahoo_plans` outbound).
- Edit `routes/oauth_callbacks.py` to drop the slug from `_PROVIDERS` (same one-line pattern as PR1).

Expect 4–5 files. Same ceiling band as PR1.

#### Option D — v5 frontend onboarding flow (connect step at Step 2 + provenance UX)

The largest substantive frontend PR. Probably needs to split into sub-PRs (likely Option D would actually be D1 + D2 + D3 — see V5 spec handoff §5.1 Option A).

Defer until at least Options A + B + one provider beyond COROS land. Building the prefill UX against one connected provider is a thin demo; building it against three is closer to the v2 product premise.

#### Option E — 14-day connect-provider nudge background job

Small standalone job. Reads `users.created_at + 14 days < NOW()` AND `(SELECT COUNT(*) FROM provider_auth WHERE user_id = u.id AND status = 'active') = 0` AND no row in `account_nudges` yet. INSERTs a row with `nudge_type='connect_provider_14d'`. Frontend banner displays + dismisses.

Could land as a single ~50-line cron / scheduled-task module. Could also wait until Andy actually wants to ship the nudge UX.

### 5.2 Recommended sequence

**A → C → B → D**.

- A first: low-risk schema half; unblocks D-59 chain detection / D-60 shared gym profiles / D-61 windows whenever frontend lands.
- C second: validate the `provider_auth.py` helper is actually provider-agnostic. Best done on a second real provider before that surface gets users.
- B third: makes PR1's COROS connection visible to athletes; once two providers are real, the management screen has interesting content.
- D last: the full frontend reshape lands with at least two real providers and all v5 schema in place.

Andy may revise — this is a planning recommendation, not a locked schedule.

### 5.3 Standing items not on the critical path

- **D-52 Catalog Migration Phase 1** — fuzzy-match HITL alias audit. Independent.
- **D-54 SQLite collapse** — Catalog Migration Phase 5. Queued.
- **D-55 Garmin onto `provider_auth`** — paused until Garmin reopens API access. Pattern proven by PR1 + `session_blob` column already in schema; ready to wire when Garmin reopens.
- **D-57 Research re-evaluation cadence design.**
- **D-62 webhook_events retention prune** — should land alongside whichever provider's webhook handler accumulates the first real events (PR1's COROS webhook handler is the first; D-62 is now in scope for the next ops PR).
- **Open Item #17 — `KNOWN_PROFILE_FIELDS` registry** — `athlete_profile_field_provenance.field_name` is free-text TEXT. Lands with PR2 prefill UX work (frontend needs the registry too). Risk if deferred too long: typo-orphan provenance rows.
- **DATABASE.md update** — three new tables documented as part of PR2's D-59/60/61 schema additions (consolidated edit).
- **PROVIDERS_SCHEMA.md update** — "Phase 1+ planned" framing is partially obsolete for COROS now; consolidates naturally with Option C (second real provider).

### 5.4 Backlog row update (deferred to next session start)

`Project_Backlog_v15.md` D-50 row currently reads "🟡 unblocked; PR1 pending." Should flip to "🟢 PR1 shipped 2026-05-14 (commit `3628ca6`); 🟡 follow-on PRs pending." Per Rule #12 this is a v16 bump (`Project_Backlog_v16.md`).

Mechanical edit for the next session:

1. Copy `Project_Backlog_v15.md` → `Project_Backlog_v16.md`.
2. In v16, locate the D-50 row. Replace its status cell with `🟢 PR1 shipped 2026-05-14 (commit 3628ca6); 🟡 follow-on PRs pending`. Update the notes column to reference `V5_Implementation_PR1_Closing_Handoff_v1.md` and list the deferred PR2+ work (Options A/B/C/D/E above).
3. In `CLAUDE.md` "Authoritative current files," bump backlog reference v15 → v16.

---

## 6. Open items / honest flags

- **COROS API surface not verified offline.** Placeholders (`open.coros.com/oauth2/authorize` + `/accesstoken`) are best-effort against documented public surface as of 2026-05; env-var overrides exist (`COROS_AUTH_URL` / `COROS_TOKEN_URL`) so a rotation doesn't need a code change. The §5.0 pre-deploy verification block above is mandatory before this feature is real.
- **`/coros/oauth/callback` deviates from `/auth/<slug>/callback` convention.** Documented in `routes/coros.py` module docstring + the comment in `routes/oauth_callbacks.py`. The redirect_uri registered in COROS's developer portal must match. Future real OAuth flows can either follow the new `/coros/oauth/callback`-style pattern OR re-extend `routes/oauth_callbacks.py` into a per-slug dispatch table; either is fine, PR2's first non-COROS provider gets to pick.
- **`disclosure_acknowledgments` was built inline.** §5.0 sanity-check #2 explicitly authorised this. Side effect: PR1 grew File 1 (init_db.py) by one extra DDL block beyond the originally-scoped two D-58 tables. That said, the table is single-purpose, additive, and matches v5 Account Config 3's field list verbatim — no design surface created.
- **`field_name` is free-text TEXT** in `athlete_profile_field_provenance`. Risk: implementation typos produce orphan rows that don't tie to any real profile field. Mitigation lands with PR2's prefill UX work via the `KNOWN_PROFILE_FIELDS` registry (Open Item #17). Until then, the column accepts anything.
- **No `cardio_log` UNIQUE constraint on `coros_label_id`.** Ingestion uses defensive SELECT-then-INSERT-or-UPDATE to dedup. Race-safe at app level under low concurrency (Andy is sole user) but not under high webhook fan-out. Backlog candidate: add `UNIQUE (user_id, coros_label_id) WHERE coros_label_id IS NOT NULL` partial constraint at the same time `polar_exercise_id` and `wahoo_workout_id` get the same treatment.
- **§A.2.5 prompt trigger is just a query-param signal** (`?coros_connected=1` appended to `return_to`). PR1 commits to the protocol; PR2 frontend renders the prompt UI when the signal is present.
- **Token-refresh skeleton is in `provider_auth.py` but not exercised** in PR1 (COROS access tokens are valid 30 days; first refresh isn't needed immediately). PR2's Wahoo (2h refresh) or Strava (6h) will exercise the path; the helper signature exists but the actual refresh-call wiring lives in `routes/<provider>.py` per-provider since the token-refresh endpoint is provider-specific.
- **Cumulative session totals 6 files** with this handoff. Same one-over-ceiling pattern flagged in V5 spec handoff §7. Quality across the 5 substantive files: AST-parses clean, manual readthrough caught no logic gaps, type signatures consistent. Handoff is bookkeeping; not net-new design.

---

## 7. Gut check

**What this session got right.**

- **Scope-locked execution.** §5.0 specified the 5-file inventory; this session shipped exactly that set (plus one minor scope-broaden for `disclosure_acknowledgments` that was explicitly authorised by §5.0 sanity-check #2). Zero feature drift.
- **`provider_auth.py` is genuinely provider-agnostic.** Nothing COROS-specific leaked into the helper. The first real test of that claim is PR2's next provider; if Polar / Wahoo wiring forces edits to `provider_auth.py`, that's signal the helper had hidden COROS-shaped assumptions. Current expectation: zero edits to `provider_auth.py` in PR2 Option C.
- **Status convention reconciled, not glossed over.** The D-58 / v5 design docs use `'connected'` colloquially; the on-disk schema uses `'active'`. Captured in `provider_auth.py` module docstring + the STATUS_* constants are the writeable surface. A reader of either v5 spec or the helper code can resolve the mismatch.
- **URL convention deviation made explicit.** The `/coros/oauth/callback` path deviates from the `/auth/<slug>/callback` stub convention. Documented in code + this handoff. Future PRs decide whether to follow this pattern or re-extend `oauth_callbacks.py`; PR1 didn't paint over the choice.
- **Webhook handler is durably safe under failure.** Signature mismatch → 401, audit row, no dispatch. Ingestion failure → record error, still 200 to COROS so they don't retry-storm into duplicate webhook_events rows. Re-dispatch is a manual-or-cron operation against `webhook_events.processed_at IS NULL OR error IS NOT NULL`.
- **Defensive UPSERT in `coros_ingest._ingest_activity`.** No UNIQUE constraint on `(user_id, coros_label_id)` yet; SELECT-then-INSERT-or-UPDATE avoids the race-on-insert pattern. Flagged in §6 for follow-on schema work.

**Risks.**

- **No live COROS connection tested.** PR1 ships against the documented COROS Open API surface; if COROS has rotated anything (token endpoint shape, header names, payload field naming), it surfaces only at deploy time. Mitigation: env-var overrides for the URLs; pre-deploy verification block in §5.0.
- **PG migrations never exercised in this session.** Local dev typically runs on SQLite (per `database.py` fall-through), and the D-58 tables are PG-only. First real exercise is the next Vercel deploy + Neon cold start. Mitigation: the migration loop's per-statement try/except + `IF NOT EXISTS` makes failures non-blocking, but a malformed statement would silently roll back without any other symptom until something queried a missing table. Spot-check post-deploy.
- **Token-refresh path is skeleton-only.** Acceptable for COROS (30-day access) but the abstraction will get its first real workout against Wahoo's 2h refresh in PR2 Option C. If the skeleton turns out to have a hole (e.g., concurrent refresh attempts, refresh-on-401-retry), PR2 surfaces it.
- **Helper expansion happened in File 1.** The disclosure_acknowledgments DDL was scope-broaden authorised by §5.0 but it does mean File 1 carries a bit more than the literal spec text. Defensible (the alternative was a fragile placeholder write or a sixth substantive file); honestly flagged.
- **Backlog v16 bump deferred.** `Project_Backlog_v15.md` D-50 row still says "PR1 pending" on disk. The next session reading the backlog will see stale status. The first-action of that session should be the v16 bump per §5.4 mechanical instructions. Risk: if the next session reads `_v15.md` and doesn't run Rule #9 reconciliation, they might think PR1 hasn't shipped.

**What might be missing.**

- **Telemetry / observability.** PR1 logs token-exchange failures and ingestion exceptions via `current_app.logger`. There's no structured event emission, no metrics. Acceptable for v1 (Andy is sole user); a real production cohort needs structured logs at minimum.
- **Provider-disconnect path is in scope but not wired.** `provider_auth.set_status(STATUS_REVOKED)` + token nullout is one function call from Account Config 1's disconnect button — but PR1 doesn't wire the route. Falls naturally into Option B (frontend management screen).
- **Webhook dedup on `(provider, provider_user_id, entity_id, event_type)`.** PR1 inserts every webhook event into `webhook_events`; COROS retrying a delivery would create duplicate rows. The dedup index exists (`idx_webhook_events_lookup`) but no INSERT-side `ON CONFLICT DO NOTHING`. Acceptable trade-off — every retry is durably recorded, and ingestion's per-shape UPSERT keys absorb the duplicate before it reaches `cardio_log` etc. But the audit log grows linearly with COROS retry behaviour. Mitigation candidate alongside D-62 retention prune.
- **No test coverage.** Matches the v1 codebase pattern (zero tests). Correctness depends on (a) faithful spec mirror, (b) manual readthrough discipline, (c) Andy as sole live user surfacing bugs. PR2 might be a reasonable place to introduce a `tests/` directory with at least `test_provider_auth.py` — small unit surface, no live network, no DB needed if we use a stub.
- **No rate-limit handling on COROS token exchange.** `requests.post(timeout=10)` is the only protection. If COROS throttles, we get a 429 → `raise_for_status` → 502. Acceptable for now; backlog candidate if it becomes a real cohort behaviour.

**Best argument against this session's scope.**

PR1 ships the OAuth callback against a COROS API surface we haven't verified. The pre-deploy verification block in §5.0 catches this before the feature is real, but the code does carry placeholder assumptions until then. An alternative phasing: ship the schema + `provider_auth.py` helper as PR1-narrower; defer the COROS routes to PR1-extended once the COROS surface is verified. Counter: the helper has no shape until it has one real consumer; verifying the COROS surface offline is impossible (need credentials); pre-deploy verification is the right place for the verification, not pre-merge. The env-var overrides + the §5.0 pre-deploy checklist + the failure-mode comments in `routes/coros.py` are the protection.

Alternatively, the disclosure_acknowledgments addition could have been argued out of PR1 ("not on the literal §5.0 file inventory"). Counter: the OAuth callback's third step is the scope-ack write, and the spec explicitly authorises building one inline if no helper exists. Skipping it would have meant either a placeholder log line (works but silently broken until PR2 backfills) or a sixth substantive file (no helper for it). Inline DDL was the smallest honest path.

---

## 8. Forward pointers

- **Next session:** Andy's choice among PR2 candidates per §5.1. Recommend A (D-59/60/61 schema PR) as the path-of-least-resistance follow-on.
- **Before next code lands:** the §5.0 pre-deploy verification block (COROS API surface, redirect_uri registration, env vars).
- **First action of any next session:** Rule #9 reconciliation; specifically read `Project_Backlog_v15.md` D-50 row (stale — still says "PR1 pending"); execute the v16 bump per §5.4 as the first edit.

**Rules in force, unchanged:**

- #9 session-start verification
- #10 session-end verification
- #11 mechanically-applicable deferred edits
- #12 numeric version suffixes (backlog v15 → v16 owed)
- #13 every closing handoff names CLAUDE.md as the first re-read — **applied: §5.1 forward-pointer reads CLAUDE.md as item 1.**

---

*End of V5 Implementation PR1 closing handoff. First substantive code session of the v5 onboarding implementation arc shipped. Next: Andy's choice among PR2 candidates in §5.1.*
