# V5 Implementation — #681 (B) live-provider wiring: Strava + Whoop OAuth connect + Strava ingest — Closing Handoff (2026-06-20)

**Branch:** `claude/provider-integrations-api-kickoff-3poeuw` · **PR:** pending Andy's go (PR-gated) · **Suite:** 2886 passed / 30 skipped. Continues the same session as the §4 wellness-row transcription (handoff `..._WellnessRowTranscription_681_...`). **Slices: B1 (Strava+Whoop connect) + B2a (Strava ingest) + B2b (Whoop ingest) + B3 (Wahoo) + B4 (Oura).** Four providers now have OAuth connect + inbound ingest through the #681 store (on top of the pre-existing COROS + Polar).

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

### B2b — Whoop live ingest (commit `a669fd3`) — BUILT (Andy: "build B2b now")
Built per the design this handoff had flagged, against Whoop's documented v2 schema (best-effort, env-overridable, verify-owed — same posture as Strava/COROS).
- `routes/whoop_ingest.py` (NEW): `verify_signature` (HMAC-SHA256 over `timestamp + raw_body`, base64, vs `X-WHOOP-Signature`; the signed timestamp is in the MAC input — no separate age-reject, units unverified). `process_event` dispatches `.updated` events; per-domain ingesters — recovery → `{hrv_rmssd_ms` (already ms), `resting_hr}` + bucket-2 corroboration (`recovery_score`/`spo2`/`skin_temp`); sleep → `total_sleep_min` = Σ(deep+rem+light)/60000 (the §3.2 asleep decision, in-bed NOT used); workout → `provider_raw_record` raw (no `cardio_log` whoop id column yet). **`_merge_daily`** is the read-modify-write that lets recovery + sleep (separate events, same day) coexist — writing the exact shape the CSV path writes + `layer3a/integration.py` reads (`total_sleep_min`/`hrv_rmssd_ms`/`resting_hr`, keyed on the ISO date). Reuses `get_fresh_access_token`.
- `routes/whoop.py`: webhook POST verifies the signature, records → `webhook_events`, maps `user_id` → local user, ingests synchronously on `.updated` (always 200; failure recorded on the event row).
- `tests/test_whoop_ingest.py` (+11), incl. the recovery+sleep-coexist merge case.

**VERIFY-OWED at go-live (Rule #14):** the v2 endpoint paths (`WHOOP_RECOVERY_PATH`/`WHOOP_SLEEP_PATH`/`WHOOP_WORKOUT_PATH`), the signature scheme, and the date derivation are the documented form, env-overridable, unverified against live payloads.

### B3 — Wahoo (commit `82b29f6`)
- `routes/wahoo.py` (NEW): `oauth_start`/`oauth_callback` (fetches `/v1/user` for the id) + webhook. Wahoo pushes the `workout_summary` inline, so ingest is **synchronous-from-payload** (no thin-pointer fetch). `normalize_wahoo_summary` per matrix §10.2: `workout_type_id` → discipline; distance m→mi, ascent m→ft, duration s→min; `work_accum` joules ÷4184 → kcal (`calories_accum` fallback). Writes via the shared cardio writer (source='wahoo', `wahoo_workout_id` dedup — column + uidx already existed). Configured `WAHOO_WEBHOOK_TOKEN` is the webhook auth gate.
- `app.py` register + csrf/auth-exempt; `routes/profile.py` `CONNECTION_PROVIDERS`. `tests/test_wahoo_ingest.py` (+9).

### B4 — Oura (commit `7f6e72c`)
- `routes/oura.py` (NEW): `oauth_start`/`oauth_callback` (fetches `personal_info` for the id) + webhook (GET subscription-`challenge` handshake; POST thin event → on a `sleep` create/update GET the doc → `daily_summary` merge). `_ingest_sleep` per matrix §4.1: `total_sleep_duration` s→min, `lowest_heart_rate`→`resting_hr` (the real RHR, not the readiness contributor), `average_hrv`→`hrv_rmssd_ms`. Same merge-partial pattern as Whoop (record-don't-drop).
- **NOT yet read by Layer-3A** — the coalesce reads garmin/whoop/polar/coros; Oura data lands but doesn't reach coaching until wired (see §4 decision 2).
- `app.py` register + csrf/auth-exempt; `routes/profile.py` `CONNECTION_PROVIDERS`. `tests/test_oura_ingest.py` (+7).

## 4. NEXT — two open decisions (surfaced, not guessed) + (C)
1. **RWGPS ingest** — `routes/ride_with_gps.py` is still a stub. Its webhook is **1s-ack, no-retry** (RWGPS docs), so a synchronous fetch is genuinely lossy (a slow fetch → the event is gone for good). This is the case that justifies the **record-and-defer cron processor** (the `idx_webhook_events_pending` index + the every-minute Vercel cron already exist) — which would also be the shared reliability upgrade for Strava/Whoop/Wahoo/Oura. Decide the processor (new `/cron/webhooks/process` route + `vercel.json` cron) before wiring RWGPS.
2. **Oura → Layer-3A coalesce** — add an `'oura'` reader branch in `layer3a/integration.py` + its rank in `_WELLNESS_SOURCE_PRIORITY` (currently garmin>whoop>polar>coros) so Oura sleep/HRV/RHR reaches coaching. Bounded (mirrors #757 for whoop), but the precedence rank is a judgment call (Oura is a dedicated recovery device → likely high, near whoop).
3. Then **(C) #682 API** (Trigger #5 design pass). `provider_outbound_ref` + outbound serializers remain Wave 3b.

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
| Whoop ingest | `routes/whoop_ingest.py` | `verify_signature` (timestamp+body HMAC); `_merge_daily` (read-modify-write daily_summary); recovery `hrv_rmssd_milli`→`hrv_rmssd_ms`; sleep Σstages→`total_sleep_min` |
| Whoop webhook | `routes/whoop.py` | webhook POST: `verify_signature`, `INSERT INTO webhook_events`, dispatch on `(event_type).endswith('.updated')`, always 200 |
| Wahoo | `routes/wahoo.py` | `oauth_start`/`oauth_callback`; `normalize_wahoo_summary` (`work_accum`*`_J_TO_KCAL`); webhook ingests `workout_summary` → `_ingest_workout_summary` source='wahoo' |
| Oura | `routes/oura.py` | `oauth_start`/`oauth_callback`; webhook GET echoes `challenge`; `_ingest_sleep` → `_merge_daily` provider='oura'; total_sleep_duration/60, lowest_heart_rate→resting_hr |
| Registration | `app.py` / `routes/profile.py` | `wahoo_bp`/`oura_bp` registered + csrf/auth-exempt; `('wahoo',…)`/`('oura',…)` in `CONNECTION_PROVIDERS` |
| Tests | `test_provider_oauth_connect` + `test_strava_ingest` + `test_whoop_ingest` + `test_wahoo_ingest` + `test_oura_ingest` | +7 / +13 / +11 / +9 / +7 |
| Suite | — | `/tmp/venv/bin/python -m pytest tests/ -q` → 2886 passed / 30 skipped |
| Issue | #681 | comment: B1–B4 (Strava/Whoop/Wahoo/Oura) shipped; gated on OAuth registrations; RWGPS + Oura-coalesce decisions + (C) next |
