# V5 Implementation — #681 Wave 3b: provider OUTBOUND (structured-workout export) — Closing Handoff (2026-06-20)

**Branch:** `claude/strava-whoop-integrations-h4durs` (PR pending Andy's go — PR-gated). **Suite:** 2994 passed / 30 skipped. Continues the #681 provider arc directly from the (B) live-wiring closing handoff (`..._ProviderIntegrations_B_StravaWhoopWiring_681_...`). **Slices: Slice 1 (serializer core + Zwift `.zwo` export + `provider_outbound_ref`) + Slice 2 (TrainingPeaks OAuth connect + structured push).**

## 1. What this session did

Andy pointed at the (B) closing handoff → "let's work". Rule #9 verified: the **entire B arc is already merged** (PR #799, commit `52d1806`) and this branch sits at `origin/main` (`6060d66`) with zero diff. Reported state; Andy's AskUserQuestion call = **Wave 3b** → then **"full Wave 3b as scoped."**

**Scope-challenge (recorded, Trigger #5 + #3):** I flagged that Wave 3b as literally scoped is mostly blocked/premature — **TrainingPeaks** is partner-access-gated (no personal use, reportedly paused → can't get credentials, untestable), **Zwift** has no push API (outbound = a `.zwo` file download, no OAuth, no idempotency table needed), and **`provider_outbound_ref`** has no consumer until a push connector exists (its real first consumer is the #682 Tier-1 calendar export). Recommended Zwift-export-only or pivot to #682. **Andy chose to build the full literal Wave 3b regardless**, accepting the TP connector + empty table are speculative until partner access opens. Built per that call; slicing isolates the real/testable core (Slice 1) from the gated connector (Slice 2).

### Slice 1 — serializer core + Zwift `.zwo` + `provider_outbound_ref` (commit `5860c68`)
The unblocked, fully-testable foundation.
- `routes/outbound_workout.py` (NEW): pure serializers.
  - `session_to_steps(session_dict)` — flattens a cardio `PlanSession`'s `cardio_blocks` into provider-agnostic `Step`s (expands `interval_set` reps; `transition`/`mixed` handled; non-cardio raises).
  - `to_zwo(session)` — Zwift `.zwo` XML. `sportType` from coarse discipline (cycling→`bike`, running→`run`; **other disciplines raise** — Zwift has no other sport). `Power` = fraction of FTP from the zone→%FTP band; warmup/cooldown = ramp bands, main/transition = SteadyState midpoint, interval_set = `IntervalsT`.
  - `to_tp_structure(session)` — TP `Structure` JSON (consumed by Slice 2). `PercentOfFtp` for cycling, `PercentOfThresholdHr` otherwise; `Length.Unit='Second'`; `interval_set`→`Repetition`.
  - **Anchor decision (load-bearing):** TP + Zwift both take *percent-of-threshold*, never absolute. The athlete FTP/LTHR extractors (`profile_extractors.extract_cycling_ftp_w_*`) are **`_EMPTY` stubs**, so the `intensity_zone` (Z1–Z5) is the serialization anchor via fixed tables: power `_ZONE_TO_PCT_FTP` (Coggan/British-Cycling), HR `_ZONE_TO_PCT_LTHR` (Friel). Tunable module constants, verify-owed; the absolute `intensity_target` is intentionally NOT used for the %.
- `routes/zwift.py`: `GET /zwift/export/<int:plan_version_id>/<date>/<int:idx>.zwo` — login-gated (global wall; not in `_AUTH_EXEMPT_ENDPOINTS`), GET (no CSRF). 404 unknown/foreign session, 400 non-cardio or non-bike/run discipline, else 200 `application/octet-stream` attachment. Webhook stub preserved.
- `plan_sessions_repo.load_plan_session_payload(db, user_id, pv, date, idx)` — natural-key, user-scoped reader returning the decoded payload dict (reused by Slice 2 + Slice 1b).
- `init_db.py`: `provider_outbound_ref` table (verbatim from the StorageSchema design §3.3 / translation spec §4.4) in the public-schema multi-statement block. **No Slice-1 consumer** (Zwift is a file download with no external id). ⚠️ *watch-out resolved:* a `;` inside the SQL comment first broke the `PG_SCHEMA.split(';')` statement splitter (the #742 gotcha) — reworded to comma.
- Design: `designs/ProviderOutbound_StructuredWorkout_681_Wave3b_BuildDesign_v1.md`.
- `tests/test_outbound_workout.py` (+21).

### Slice 2 — TrainingPeaks outbound connector (commit `f179313`) — GATED/SPECULATIVE
TP is a *push destination* → OAuth connect + a structured-workout push (the symmetric counterpart to Zwift's download).
- `routes/trainingpeaks.py` (stub → full):
  - `oauth_start`/`oauth_callback` — mirrors Wahoo; the token response carries no athlete id so the callback fetches `/v1/athlete/profile` for `provider_user_id`. Scopes `athlete:profile workouts:plan`.
  - `POST /trainingpeaks/push/<int:pv>/<date>/<int:idx>` — login-gated. Loads the session, builds `to_tp_structure` → the `/v2/workouts/plan` body, gets a fresh token (`pa.get_fresh_access_token`), POSTs. **Idempotent via `provider_outbound_ref`** keyed `(user, 'trainingpeaks', session_id)`: same `pushed_payload_hash` → no-op (no POST); changed → re-push + `UPDATE`; new → `INSERT`, `status` pushed/updated/error, `tier=2`. 404 unknown / 400 non-exportable / 409 not-connected.
  - Webhook stub kept (inbound partner-gated; keeps the `trainingpeaks.webhook` auth-exempt reference live).
- `routes/profile.py` (`CONNECTION_PROVIDERS` += trainingpeaks) + `routes/connections.py` (removed from `STUB_PROVIDERS`) → TP shows **Connect** on the hub. **Zwift stays the only STUB** (its export is per-session, not an OAuth connect).
- `tests/test_trainingpeaks_outbound.py` (+9: start-redirect, callback persist w/ fetched id, state-mismatch 400, push records, unchanged-no-op, changed-update, non-cardio 400, not-connected 409, missing 404).

## 2. GATED / VERIFY-OWED (Rule #14 — the container can't do these)
- **TrainingPeaks** is partner-access-gated (approval, reportedly paused to new partners). The connector is **untestable against live TP** — the auth/token/profile/`/plan` URLs (`TP_AUTH_URL`/`TP_TOKEN_URL`/`TP_PROFILE_URL`/`TP_PLAN_URL`) + the `/v2/workouts/plan` body shape + the `Structure` field names are the documented form, env-overridable, owed a live verify if/when access opens. Go-live also needs `TP_CLIENT_ID`/`TP_CLIENT_SECRET`.
- **Zwift `.zwo`** is testable end-to-end in-container (pure serializer + a download route) — verify-owed only that real Zwift imports our `.zwo` (well-formed XML asserted; the block/attribute names are the community-doc form).
- **Zone→% tables** are documented standard 5-zone models (power Coggan / HR Friel); tunable constants — Andy may retune.

### Slice 1b — surface the `.zwo` download link (commit `<this session>`) — SHIPPED
The route was built but unsurfaced; now linked on the plan view.
- `routes/outbound_workout.is_zwift_exportable(discipline_id)` — bike/run gate.
- `routes/plan_create.view_plan` passes `zwift_exportable=is_zwift_exportable` into the template.
- `templates/plan_create/view.html` — a `↓ Zwift .zwo` download link under each bike/run cardio session's blocks, gated `{% if zwift_exportable is defined and zwift_exportable(...) %}` (the `is defined` guard keeps the isolated-template render tests green).
- `tests/test_outbound_workout.py` +2 (`is_zwift_exportable` true/false).

## 3. NEXT (4-tier order)
1. **(C) #682 AIDSTATION API (tier 4):** the documented next epic — Trigger #5 design pass (surface + auth model). The **Tier-1 calendar export** there is the other real `provider_outbound_ref` consumer.
2. Later outbound: Wahoo `plan.json` Tier-2 push (matrix §10.2).

## 6.3 Read order for next session (Rule #13)
1. `CLAUDE.md`. 2. `CURRENT_STATE.md` (last-shipped = this Wave-3b entry). 3. `CARRY_FORWARD.md` *"Provider integrations & API — ACTIVE THREAD"* → **(D) Wave 3b**. 4. This handoff. 5. `routes/outbound_workout.py` (the serializer core) + `designs/ProviderOutbound_StructuredWorkout_681_Wave3b_BuildDesign_v1.md`. 6. `./scripts/verify-handoff.sh`.

## 7. Session-end verification (Rule #10) — anchor table

| Area | Path | Anchor / check |
|---|---|---|
| Serializer core | `routes/outbound_workout.py` | `session_to_steps` + `to_zwo` (`_ZONE_TO_PCT_FTP`, `_COARSE_TO_ZWIFT_SPORT`, raises for non-bike/run) + `to_tp_structure` (`PercentOfFtp`/`PercentOfThresholdHr`, `Length.Unit='Second'`) |
| Zone anchor | `routes/outbound_workout.py` | `_ZONE_TO_PCT_FTP` (Z1 0.50–0.55 … Z5 1.06–1.20) + `_ZONE_TO_PCT_LTHR` (Friel); `_MIXED_FALLBACK='Z2'` |
| Zwift export | `routes/zwift.py` | `def export_zwo`; route `/export/<int:plan_version_id>/<date>/<int:idx>.zwo`; `application/octet-stream` attachment; 404/400 guards |
| Session reader | `plan_sessions_repo.py` | `def load_plan_session_payload` (natural-key, user-scoped, `_decode_payload`) |
| Outbound ledger | `init_db.py` | `CREATE TABLE IF NOT EXISTS provider_outbound_ref` (UNIQUE `(user_id, provider, session_id)`; `pushed_payload_hash`, `tier`, `status`) — no `;` in the comment |
| TP connect | `routes/trainingpeaks.py` | `def oauth_start` + `def oauth_callback`; `_TP_SCOPES='athlete:profile workouts:plan'`; fetches `_TP_PROFILE_URL` for `provider_user_id`; redirect `?trainingpeaks_connected=1` |
| TP push | `routes/trainingpeaks.py` | `def push_session` (POST `/push/<pv>/<date>/<idx>`); `to_tp_structure` → `_TP_PLAN_URL`; idempotent via `provider_outbound_ref` (`pushed_payload_hash`); `_record_outbound` upsert tier=2 |
| Hub wiring | `routes/profile.py` / `routes/connections.py` | `('trainingpeaks','TrainingPeaks','trainingpeaks.oauth_start')` in `CONNECTION_PROVIDERS`; `STUB_PROVIDERS` = zwift only |
| Slice 1b link | `routes/outbound_workout.py` / `routes/plan_create.py` / `templates/plan_create/view.html` | `is_zwift_exportable`; `zwift_exportable=is_zwift_exportable` in `view_plan`; `↓ Zwift .zwo` link gated `{% if zwift_exportable is defined and ... %}` |
| Tests | `test_outbound_workout` + `test_trainingpeaks_outbound` | +23 / +9 |
| Suite | — | `/tmp/venv/bin/python -m pytest tests/ -q` → 2996 passed / 30 skipped |
| Issue | #681 | comment: Wave 3b outbound (Zwift `.zwo` + TP push + `provider_outbound_ref`) shipped; TP partner-gated verify-owed; epic stays open |
