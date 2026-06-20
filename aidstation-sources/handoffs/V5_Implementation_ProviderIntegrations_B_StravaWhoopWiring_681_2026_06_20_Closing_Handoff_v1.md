# V5 Implementation — #681 (B) live-provider wiring: Strava + Whoop OAuth connect + Strava ingest — Closing Handoff (2026-06-20)

**Branch:** `claude/provider-integrations-api-kickoff-3poeuw` · **PR:** pending Andy's go (PR-gated) · **Suite:** 2859 passed / 30 skipped. Continues the same session as the §4 wellness-row transcription (handoff `..._WellnessRowTranscription_681_...`).

## 1. What this session did (the B arc)

Andy: "continue in this session on (B)" → "keep going". (B) = turn the Phase-0 stubs into real inbound syncs, landing data through the #681 translation store. Shipped two slices for **Strava + Whoop** (the highest-value first targets).

### B1 — Strava + Whoop OAuth connect (commit `29c5a59`)
The unambiguous mirror of `routes/coros.py`; the piece gated only on Andy's external app registration.
- `routes/strava.py`: `oauth_start` + `oauth_callback`. Comma-separated scopes (`activity:read_all,profile:read_all`); token response carries `athlete.id` (→ `provider_user_id`) + absolute `expires_at`; the callback `scope` param is the *granted* set (athletes can deselect). Rule #15 connect log (no token material).
- `routes/whoop.py`: `oauth_start` + `oauth_callback`. Space-separated scopes + `offline` (required for a refresh token); the token response has **no** user id, so the callback fetches `GET /v2/user/profile/basic` for `provider_user_id` (needed for the webhook reverse-lookup). Preserves the manual-CSV writer + webhook stub.
- `routes/profile.py`: added `('strava', …)` + `('whoop', …)` to `CONNECTION_PROVIDERS`.
- `routes/connections.py`: removed strava/whoop from `STUB_PROVIDERS` → the hub shows **Connect**, not "Not available yet".

### B2a — Strava live ingest (commit `428e5a2`)
Strava webhooks are thin pointers (`{object_type, object_id, owner_id, aspect_type}`) → an `activity` `create`/`update` triggers a REST fetch + write.
- `routes/provider_auth.py`: `refresh_access_token` + `get_fresh_access_token` — the OAuth2 refresh-token grant Integration v4 §4.1 sketched but **no provider had exercised** (COROS/Polar are long-lived; Strava ~6h, Whoop ~1h). Handles both expiry shapes (Strava `expires_at` absolute, Whoop `expires_in` relative); flips the row to `error` on failure (re-auth prompt). **Reused by Whoop next.**
- `routes/strava_ingest.py` (NEW): `normalize_strava_activity` (matrix §2.1 unit conversions: distance m→mi, elevation m→ft, time s→min; HR/power/calories canonical; discipline via `resolve_cardio_discipline('strava', sport_type)` → fine D-id or bucket-3; indoor-machine flag in `_provider_raw`) + `fetch_and_ingest_activity` (dedup → fresh token → `GET /activities/{id}` → write through the shared `garmin._bulk_insert_cardio(source='strava')`). Rule #15 decision logs throughout.
- `routes/strava.py`: webhook POST records the event → `webhook_events`, maps `owner_id` → local user, and **synchronously** fetches + ingests on activity create/update. Always returns 200 (Strava retries non-2xx → would re-record); a failed ingest is recorded on the event row. `subscription_id` is the only authenticity check Strava offers.
- `init_db.py`: `cardio_log_strava_activity_uidx` (partial-unique idempotency guard; mirrors coros/polar/wahoo).

**Architecture decision (stated explicitly, not silently chosen):** synchronous ingest, **not** the record-and-defer cron I'd floated. Rationale: simplicity-first for a single-user app; the ingest is idempotent on `(user_id, strava_activity_id)`, so a missed-2s-ack Strava retry is harmless (re-fetch → skip-existing); a synchronous path avoids standing up cron + `vercel.json` infra that can't be verified from the container. Record-and-defer (the `idx_webhook_events_pending` index already anticipates it) is the documented upgrade if retry churn ever appears. *If Andy prefers deferred or hybrid, only Strava is built — Whoop hasn't replicated it yet.*

## 2. Tests
- `tests/test_provider_oauth_connect.py` (+7): start-redirect shape (scopes/state), token-exchange persist, state-mismatch 400, Whoop profile fetch, hub wiring.
- `tests/test_strava_ingest.py` (+13): normalization (units/discipline/indoor/bucket-3), refresh helper (not-expiring/expiring/persist-rotated/error), fetch-and-ingest (skip-existing/no-token/writes-via-shared-writer), webhook dispatch (ingest on activity create/update; record-only on athlete event + unmapped owner).
- Full suite **2859 passed / 30 skipped**.

## 3. GATED on Andy (external — the container can't do these)
1. Register the **Strava** OAuth app (redirect_uri = `…/strava/oauth/callback`) → set `STRAVA_CLIENT_ID` / `STRAVA_CLIENT_SECRET`; create the **push subscription** pointing at `…/strava/webhook` → set `STRAVA_SUBSCRIPTION_ID`.
2. Register the **Whoop** OAuth app (redirect_uri = `…/whoop/oauth/callback`) → set `WHOOP_CLIENT_ID` / `WHOOP_CLIENT_SECRET`.
3. Then **live-verify** (Rule #14): Connect Strava on the hub → `/admin/logs` `[strava-oauth] connected …`; complete a Strava activity → `[strava-ingest] activity=… -> cardio_log discipline=…` + the row in `cardio_log` with `strava_activity_id` + a `provider_raw_record` corroboration row. The OAuth URLs are env-overridable with documented defaults; confirm them against current provider docs before creating the subscription.

## 4. NEXT — B2b Whoop live ingest (needs a design call; do NOT guess)
Whoop's webhooks (`recovery.updated` / `sleep.updated` / `workout.updated`) are **separate per-domain events**, each carrying only PART of the Layer-3A `daily_summary` (recovery → `hrv_rmssd_ms` + `resting_hr`; sleep → `total_sleep_min` from the stage-sum, per the §3.2 Σstages decision). So the ingest must:
1. **Merge-partial into the existing day's `provider_raw_record` row** (read-modify-write the subset this event provides — a sleep event must not clobber the recovery event's hrv/rhr, and vice versa). The CSV path already writes the exact target shape (`total_sleep_min`/`hrv_rmssd_ms`/`resting_hr`, keyed on the ISO date in `external_id`).
2. **Derive the daily date** for a recovery/sleep (cycle calendar day / sleep wake date).
3. **Verify HMAC-SHA256** over the raw body with `WHOOP_CLIENT_SECRET` (base64 in `X-WHOOP-Signature`) + the `X-WHOOP-Signature-Timestamp` window.
4. Reuse `provider_auth.get_fresh_access_token` (already built) + the §2.3/§3 `WELLNESS_VALUE_MAP` rows transcribed this session.

This is fiddly against Whoop's live payloads and Rule #14 says don't guess unverifiable API specifics — bring the merge-semantics + date-derivation to Andy (or build against a real captured payload) rather than blind. Then Wahoo/Oura/RWGPS connect+ingest; then (C) #682 API.

## 6.3 Read order for next session (Rule #13)
1. `CLAUDE.md`. 2. `CURRENT_STATE.md` (last-shipped = this B arc). 3. `CARRY_FORWARD.md` *"Provider integrations & API — ACTIVE THREAD"* → (B) sub-bullets (B1/B2a ✅, B2b ⏭). 4. This handoff. 5. `routes/strava_ingest.py` + `routes/provider_auth.py` (the refresh helper) as the pattern Whoop mirrors. 6. `./scripts/verify-handoff.sh`.

## 7. Session-end verification (Rule #10) — anchor table

| Area | Path | Anchor / check |
|---|---|---|
| Strava connect | `routes/strava.py` | `def oauth_start` + `def oauth_callback`; `_STRAVA_SCOPES = 'activity:read_all,profile:read_all'`; redirect `?strava_connected=1` |
| Whoop connect | `routes/whoop.py` | `def oauth_start` + `def oauth_callback`; `'offline'` in `_WHOOP_SCOPES`; fetches `_WHOOP_PROFILE_URL` for `user_id` |
| Hub wiring | `routes/profile.py` / `routes/connections.py` | `('strava','Strava','strava.oauth_start')` + whoop in `CONNECTION_PROVIDERS`; strava/whoop NOT in `STUB_PROVIDERS` |
| Token refresh | `routes/provider_auth.py` | `def refresh_access_token` + `def get_fresh_access_token`; `_REFRESH_SKEW`; `_expiry_from_response` (expires_at/expires_in) |
| Strava ingest | `routes/strava_ingest.py` | `normalize_strava_activity` (m→mi `_M_TO_MI`, resolver, indoor `_CYCLING_DISCIPLINES`) + `fetch_and_ingest_activity` (dedup SELECT → token → GET → `_bulk_insert_cardio(source='strava')`) |
| Webhook dispatch | `routes/strava.py` | webhook POST: `INSERT INTO webhook_events`, `get_auth_by_provider_user_id`, dispatch on `object_type=='activity'` + `aspect_type in (create,update)`, always 200 |
| Dedup index | `init_db.py` | `cardio_log_strava_activity_uidx ON cardio_log (user_id, strava_activity_id) WHERE strava_activity_id IS NOT NULL` |
| Tests | `tests/test_provider_oauth_connect.py` + `tests/test_strava_ingest.py` | +7 / +13 |
| Suite | — | `/tmp/venv/bin/python -m pytest tests/ -q` → 2859 passed / 30 skipped |
| Issue | #681 | comment: B1 + B2a shipped; gated on OAuth registrations; B2b Whoop next |
