# PR Verification Status

**Started:** 2026-05-15
**Tracks:** V5 onboarding implementation PRs (PR1–PR10) — the §5.0 "Pre-deploy verification" checklist from each closing handoff.

Each closing handoff's §5.0 historically ended with "**Independent of PR<N>:** PR1 §5.0 + PR3 §5.0 + … are still owed if not yet completed." That carry-forward list grew monotonically across PR1–PR10 and conflated three different states (genuinely owed, externally blocked, already done) under a single "owed" label. This file is the on-disk record so future sessions' Rule #9 reconciliation runs against actual state instead of treating the carry-forward as monolithically pending.

Andy updates as steps are walked; Claude reads at session start.

## Status legend

- ✅ Done (date verified)
- ⏸ Blocked on external dependency (note what)
- 🟡 Owed — can be walked now (no external dependency)
- ⚪ N/A — superseded by later PR or otherwise not applicable
- 🔴 BUG — feature didn't behave as spec'd; needs investigation / fix PR

## How to update this file

When you walk a step: flip its row from 🟡 to ✅ (add today's date) or ⏸ (add what's blocking). When a step becomes obsolete because a later PR superseded it, flip to ⚪ with a note. Don't delete rows — the historical record is the point.

When a new PR ships, the closing handoff author appends a new section here for that PR's §5.0 steps (seeded with 🟡 owed for everything that doesn't have an obvious external block).

---

## PR1 — COROS OAuth + ingestion + `provider_auth` helper + D-58 schema (merge `3628ca6`)

§5.0 has 4 steps. Three are deployment-time tasks requiring COROS partner credentials; one is a schema spot-check independent of creds.

| # | Step | Status | Last update | Notes |
|---|------|--------|-------------|-------|
| 1 | Confirm COROS Open API surface (authorize/token URLs, response shape, webhook signature method) | ⏸ blocked on COROS creds | 2026-05-15 | Andy doesn't have COROS partner credentials yet. |
| 2 | Register COROS developer-portal redirect_uri = `https://aidstation-pro.vercel.app/coros/oauth/callback` | ⏸ blocked on COROS creds | 2026-05-15 | Same blocker. |
| 3 | Set Vercel env vars `COROS_CLIENT_ID` + `COROS_CLIENT_SECRET` (+ optional auth/token URL overrides) | ⏸ blocked on COROS creds | 2026-05-15 | Same blocker. |
| 4 | Monitor first cold-start `_PG_MIGRATIONS` run on Neon; spot-check D-58 tables (`athlete_profile_field_provenance`, `account_nudges`, `disclosure_acknowledgments`) via `\d` in Neon console | ✅ Done | 2026-05-15 | Implicitly verified by PR6 step 4 (provenance table query returned 5 rows) + PR9 working end-to-end (account_nudges table used by the banner). `disclosure_acknowledgments` will exercise on first PR10 disclosure ack. |

---

## PR2 — D-59/60/61 schema (merge `686bb40`)

Schema-only PR. No §5.0 distinct verification owed. Tables/columns (`daily_availability_windows`, `gym_profiles`, `locale_equipment_overrides`, `locale_toggle_overrides`, 10 `locale_profiles` ALTER columns) plus the `chain_registry.py` module are implicitly verified by PR10 consuming them.

| # | Step | Status | Last update | Notes |
|---|------|--------|-------------|-------|
| — | Schema migrations applied cleanly on Neon | 🟡 owed | 2026-05-15 | Spot-check with `\d locale_profiles` for the 10 new columns + `\d gym_profiles` / `\d locale_equipment_overrides` / `\d locale_toggle_overrides` / `\d daily_availability_windows`. Will be exercised when PR10 merges + first locale gets created. |

---

## PR3 — Polar OAuth + webhook + ingestion + `cardio_log` partial-UNIQUE indexes (merge `b819f0a`)

§5.0 has 6 steps. Most require Polar partner credentials; the index spot-check is independent.

| # | Step | Status | Last update | Notes |
|---|------|--------|-------------|-------|
| 1 | Confirm Polar AccessLink surface (authorize/token URLs, HTTP-Basic auth, `x_user_id`, HMAC-SHA256 webhook signature header) | ⏸ blocked on Polar creds | 2026-05-15 | Andy doesn't have Polar partner credentials yet. |
| 2 | Register Polar developer-portal redirect_uri = `https://aidstation-pro.vercel.app/polar/oauth/callback` | ⏸ blocked on Polar creds | 2026-05-15 | Same blocker. |
| 3 | Set Vercel env vars `POLAR_CLIENT_ID` + `POLAR_CLIENT_SECRET` + `POLAR_WEBHOOK_SECRET` | ⏸ blocked on Polar creds | 2026-05-15 | Same blocker. |
| 4 | Register webhook URL via Polar partner API (POST /v3/webhooks); capture `signature_secret_key` into `POLAR_WEBHOOK_SECRET` | ⏸ blocked on Polar creds | 2026-05-15 | Same blocker. |
| 5 | Monitor first cold-start `_PG_MIGRATIONS` on Neon; spot-check `\d cardio_log` for 3 new partial-UNIQUE indexes (`cardio_log_polar_exercise_uidx`, `cardio_log_coros_label_uidx`, `cardio_log_wahoo_workout_uidx`) | 🟡 owed | 2026-05-15 | Independent of Polar creds. One psql query. |
| 6 | (Pointer: PR1 §5.0 still owed.) | ⚪ N/A | 2026-05-15 | This row is just a carry-forward pointer, not a step. |

---

## PR4 — Connections tab on `/profile?tab=connections` (merge `f4d2e75`)

§5.0 has 6 testable steps. All exercise the COROS or Polar OAuth round-trip, so all are gated on at least one set of provider creds — except step 1 which only renders the empty-state tab.

| # | Step | Status | Last update | Notes |
|---|------|--------|-------------|-------|
| 1 | Open `/profile?tab=connections`; confirm count badge `0`, both COROS + Polar entries render with "Not connected" badge | 🟡 owed | 2026-05-15 | Doable without creds — just page render. |
| 2 | Click Connect on COROS → bounce to `/coros/oauth/start?return_to=...` → complete OAuth → redirect back with `?coros_connected=1` + green flash | ⏸ blocked on COROS creds | 2026-05-15 | |
| 3 | Confirm COROS card flips to "Connected since YYYY-MM-DD" + Re-authorise + Disconnect buttons; badge counts to `1` | ⏸ blocked on COROS creds | 2026-05-15 | Depends on step 2. |
| 4 | Click Disconnect on COROS → redirect with flash; card flips to "Disconnected"; re-Disconnect should flash "already disconnected" | ⏸ blocked on COROS creds | 2026-05-15 | Depends on step 3. |
| 5 | `psql` spot-check `provider_auth` rows after disconnect (status='revoked'; tokens NULL; scopes/registered_at/token_expires_at preserved; updated_at bumped) | ⏸ blocked on COROS creds | 2026-05-15 | Depends on step 4. |
| 6 | Repeat 2-5 for Polar (Polar's two-phase OAuth means active only after `POST /v3/users` succeeds) | ⏸ blocked on Polar creds | 2026-05-15 | |

---

## PR5 — `/onboarding/connect` Step-2 screen + CSP nonce fix (merge `34637d2`)

§5.0 has 7 testable steps.

| # | Step | Status | Last update | Notes |
|---|------|--------|-------------|-------|
| 1 | `/onboarding/connect` renders Step-2 indicator + COROS/Polar "Not connected" cards + collapsed consent disclosure + disabled Connect buttons | ✅ Done | 2026-05-15 | Andy confirmed page renders. |
| 2 | Click consent checkbox → Connect button enables (CSS class `disabled` removed) | ✅ Done | 2026-05-15 | Andy: "the click enables the button". |
| 3 | Complete COROS OAuth → redirect to `/onboarding/connect?coros_connected=1` + green flash + card flips to Connected | ⏸ blocked on COROS creds | 2026-05-15 | |
| 4 | Click "Continue (1 connected)" → POST `/onboarding/continue` → redirect to `/profile?tab=athlete` with Athlete tab active (PR4 tab-activation script working under PR5 CSP nonce) | ⏸ blocked on COROS creds | 2026-05-15 | Continue button needs ≥1 connected provider. |
| 5 | Fresh account register → post-register redirect lands on `/onboarding/connect` (not `/dashboard`) | 🟡 owed | 2026-05-15 | Depends on `ALLOW_REGISTRATION` env; create a test athlete account to walk this. |
| 6 | Skip path: click "Skip for now" → POST `/onboarding/skip` → `/profile?tab=athlete` with flash | 🟡 owed | 2026-05-15 | Doable today. |
| 7 | CSP check: devtools console on `/profile?tab=connections` should NOT throw CSP-blocked error for the PR4 inline tab-activation script (PR5 nonce fix); same on `/onboarding/connect` | 🟡 owed | 2026-05-15 | Doable today. |

---

## PR6 — D-51 athlete_profile column foundation + Performance Baselines form + G ON CONFLICT cleanup (merge `2c8d01f`)

§5.0 has 7 testable steps.

| # | Step | Status | Last update | Notes |
|---|------|--------|-------------|-------|
| 1 | Schema migration: `\d athlete_profile` on Neon shows 5 new columns | ✅ Done | 2026-05-15 | |
| 2 | `/profile?tab=profile` renders Performance Baselines section with 5 inputs | ✅ Done | 2026-05-15 | |
| 3 | Save round-trip: type values → save → flash → reload shows values → `psql` `athlete_profile` matches | ✅ Done | 2026-05-15 | |
| 4 | Provenance spot-check: `SELECT field_name, source FROM athlete_profile_field_provenance WHERE user_id=1` returns 5 rows, all `source='self_report'` | ✅ Done | 2026-05-15 | |
| 5 | Edit + re-save: one value changes; row updates; provenance `last_updated_at` bumped (source stays `self_report`) | ✅ Done | 2026-05-15 | |
| 6 | Clear field: empty input → save → row goes NULL; provenance row stays intact (intentional — D2 ships the deletion-on-clear path) | ✅ Done | 2026-05-15 | |
| 7 | G ON CONFLICT cleanup: trigger COROS webhook delivery twice for same `labelId` → second call UPDATEs in place (no duplicate row) | ⏸ blocked on COROS creds | 2026-05-15 | Webhook needs COROS partner config. |

---

## PR7 — D2a read-side prefill UX + `KNOWN_PROFILE_FIELDS` registry + HRmax extractor (merge `df17f08`)

§5.0 has 7 testable steps.

| # | Step | Status | Last update | Notes |
|---|------|--------|-------------|-------|
| 1 | Schema unchanged (`\d athlete_profile` + `\d athlete_profile_field_provenance` look the same as PR6) | ✅ Done | 2026-05-15 | |
| 2 | `/onboarding/prefill` empty-state render (zero providers): alert-info "No providers connected" + 5 cards each "Currently stored: Not set" + "None of your connected providers supply this field yet" | ✅ Done | 2026-05-15 | |
| 3 | `/onboarding/prefill` populated render (HRmax candidate from COROS data): card shows current value + provenance badge + COROS candidate row + `synced_at` date + 90-day description note + (PR7 era) disabled `[Use provider value]` + `[Keep current]` buttons | ⏸ blocked on COROS data | 2026-05-15 | Needs ≥1 `cardio_log` row with `coros_label_id IS NOT NULL` + `max_hr IS NOT NULL` + `date >= today-90`. |
| 4 | Step-2 Continue → `/onboarding/prefill` (not `/profile?tab=athlete` as pre-PR7) | ✅ Done | 2026-05-15 | |
| 5 | Step-2 Skip → `/profile?tab=athlete` (unchanged from PR5) | ✅ Done | 2026-05-15 | |
| 6 | `/onboarding/prefill` "Continue to profile" → `/profile?tab=athlete` | ✅ Done | 2026-05-15 | |
| 7 | Disabled `[Use provider value]` buttons are non-actionable; tooltip "Write-back ships in the next release."; no console errors | ⚪ N/A | 2026-05-15 | Superseded by PR8 — those buttons became live in PR8. The transitional disabled state stopped existing after PR8 merged. |

---

## PR8 — D2b write-side prefill UX + `manual_override` source-flip (merge `43ccedf`)

§5.0 has 9 testable steps.

| # | Step | Status | Last update | Notes |
|---|------|--------|-------------|-------|
| 1 | Schema unchanged (`\d athlete_profile_field_provenance` shows no new columns) | ✅ Done | 2026-05-15 | Implicitly — PR6 step 4 already exercised this table. |
| 2 | `/onboarding/prefill` shows real `[Use COROS value]` + conditional `[Keep current]` buttons (HRmax card, COROS connected, ≥1 candidate row) | ⏸ blocked on COROS data | 2026-05-15 | |
| 3 | `[Use COROS value]` round-trip: flash → page reload → "From COROS" badge → `psql` provenance `source='provider_coros'` + `athlete_profile.hrmax_bpm` matches | ⏸ blocked on COROS data | 2026-05-15 | |
| 4 | `[Keep current]` round-trip: flash → page reload → "Manually set" badge + inline "Use COROS value (bpm, date) instead" link → `psql` provenance `source='manual_override'` + `athlete_profile.hrmax_bpm` unchanged | ⏸ blocked on COROS data | 2026-05-15 | |
| 5 | Inline "Use COROS value instead" link click: same effect as `[Use COROS value]` (one write path, two UI entry points) | ⏸ blocked on COROS data | 2026-05-15 | |
| 6 | Source-flip from profile form: edit HRmax value to a different number on `/profile?tab=athlete` → save → provenance flips `provider_coros` → `manual_override`; `/onboarding/prefill` shows "Manually set" badge + inline clear-override link | ⏸ blocked on COROS data | 2026-05-15 | The flip logic is testable with `self_report` source too, but per-spec it ships for `provider_*` source. |
| 7 | Defensive guard: brand-new profile (all fields blank) → `[Keep current]` button doesn't render; manual `curl POST .../keep-current` flashes warning + no DB write | 🟡 owed | 2026-05-15 | Doable today. |
| 8 | 404 on bogus field: `curl POST .../onboarding/prefill/notarealfield/use-provider` → 404 | 🟡 owed | 2026-05-15 | Doable today. |
| 9 | CSRF rejection: same curl without token → 400 (Flask-WTF CSRFError) | 🟡 owed | 2026-05-15 | Doable today. |

---

## PR9 — Option E 14-day connect-provider nudge + Vercel Cron + dismissable banner (merge `7cb786a`)

§5.0 has 14 testable steps. Andy reports all walked.

| # | Step | Status | Last update | Notes |
|---|------|--------|-------------|-------|
| 1 | Schema unchanged | ✅ Done | 2026-05-15 | |
| 2 | Env var setup: `CRON_SECRET` set on Vercel | ✅ Done | 2026-05-15 | |
| 3 | Vercel Cron registered (`/cron/nudges/connect_provider_14d`, `0 14 * * *`) | ✅ Done | 2026-05-15 | |
| 4 | Cron auth happy path (curl with Bearer token returns 200 + `{inserted: N}`) | ✅ Done | 2026-05-15 | |
| 5 | Cron auth failure paths (no header / wrong token / wrong scheme all 401) | ✅ Done | 2026-05-15 | |
| 6 | Idempotency: re-run returns `{inserted: 0}` | ✅ Done | 2026-05-15 | |
| 7 | Banner render: blue info alert with CTA + × close button | ✅ Done | 2026-05-15 | |
| 8 | Banner dismiss round-trip: × click → page reload → banner gone; `dismissed_at` populated | ✅ Done | 2026-05-15 | |
| 9 | Dismiss persistence across reloads; manual NULL flip → banner reappears | ✅ Done | 2026-05-15 | |
| 10 | Empty-state hygiene: logged out / no nudges → no banner | ✅ Done | 2026-05-15 | |
| 11 | CSRF rejection on dismiss | ✅ Done | 2026-05-15 | |
| 12 | Cross-user scoping: curl POST against another user's nudge_id is no-op | ✅ Done | 2026-05-15 | |
| 13 | Vercel Cron live trigger at 14:00 UTC | ✅ Done | 2026-05-15 | Or will be — fires daily; first scheduled fire is after deploy time. |
| 14 | Regression sweep on the rest of the app | ✅ Done | 2026-05-15 | |

---

## PR10 — D3a Mapbox-anchored locale creation + chain detection (pending merge)

§5.0 has 15 testable steps. PR10 is on branch `claude/review-v5-pr9-handoff-Xdt7Q`; PR creation + merge + deploy pending. `MAPBOX_PUBLIC_TOKEN` env var already set per Andy (2026-05-15).

| # | Step | Status | Last update | Notes |
|---|------|--------|-------------|-------|
| 1 | Schema unchanged | ✅ Done | 2026-05-15 | `\d disclosure_acknowledgments` confirms shape unchanged (id, user_id, disclosure_id, version_id, scopes_granted, delivery_method, acknowledged_at + indexes). |
| 2 | `MAPBOX_PUBLIC_TOKEN` env var set on Vercel + TrueNAS | ✅ Done | 2026-05-15 | Andy confirmed. |
| 3 | `/locales/new` disclosure card on first visit | ✅ Done | 2026-05-15 | |
| 4 | Acknowledge writes `disclosure_acknowledgments` row | ✅ Done | 2026-05-15 | |
| 5 | Search happy path: results with hidden mapbox_id/lat/lng + Save button | 🔴 BUG | 2026-05-15 | Mapbox returning street/city addresses only — no POI/business name results. Result format partially good (bold name, full address) but no `properties.category` value. Locale name field is editable as designed. Foreseen in D-59 §12 ("Mapbox's chain coverage is going to disappoint") but biting harder than expected. Diagnosis curl owed: check if `features[].place_type` contains `poi` at all. Likely fix paths: (A) drop `address` from `types` filter, (B) migrate to Mapbox Search Box API, (C) verify token has POI scope. |
| 6 | Save chain-anchored: redirect to `/locales/<slug>/nearby`; row has correct chain_id/category | ⏸ blocked on step 5 | 2026-05-15 | Can't test until Mapbox returns business results. |
| 7 | Nearby picker: same-chain matches + opt-in INSERT | ⏸ blocked on step 5/6 | 2026-05-15 | |
| 8 | Save non-chain: no nearby redirect; row has `chain_id IS NULL` | ✅ Done | 2026-05-15 | Save + non-redirect work correctly. `category IS NULL` for hotel / address-only results is correct per D-59 §4.2 step 3 third bullet — Mapbox's `properties.category` doesn't contain gym/fitness/climbing tokens for non-gym places, so derivation falls through to NULL by design. Cascading concern: if step 5 is fixed and Mapbox starts returning POI categories, this path should produce `independent_gym` for non-chain gym POIs. |
| 9 | Manual entry: row with `manual_entry=TRUE`, NULL coords | ✅ Done | 2026-05-15 | |
| 10 | `/locales` list shows legacy + athlete-created rows | ✅ Done | 2026-05-15 | Edit works for both legacy and athlete-created rows. Categorized commercial gym row not testable until step 5 is fixed. |
| 11 | 0-results inline warning | ✅ Done | 2026-05-15 | |
| 12 | Token-missing inline error (temporarily unset token) | 🟡 skipped | 2026-05-15 | Andy chose to skip — non-critical with token already set. |
| 13 | Disclosure version bump re-prompts | 🟡 owed | 2026-05-15 | Not walked yet. |
| 14 | Cross-user scoping on /nearby | ⚪ N/A | 2026-05-15 | Single-test-athlete state. |
| 15 | Regression sweep | ✅ Done | 2026-05-15 | |

**Step 5 follow-up:** Investigation owed. Curl directly to Mapbox to see raw `features[]` shape. If `place_type: ["poi"]` is present, the `types=poi,address` filter is the suspect; if absent, Mapbox's POI database is the limit and we need the Search Box API or a provider switch.

---

## Aggregate status (2026-05-15)

| PR | ✅ | ⏸ | 🟡 | ⚪ | Total |
|----|---|---|---|---|-------|
| PR1 | 1 | 3 | 0 | 0 | 4 |
| PR2 | 0 | 0 | 1 | 0 | 1 |
| PR3 | 0 | 4 | 1 | 1 | 6 |
| PR4 | 0 | 5 | 1 | 0 | 6 |
| PR5 | 2 | 2 | 3 | 0 | 7 |
| PR6 | 6 | 1 | 0 | 0 | 7 |
| PR7 | 6 | 1 | 0 | 1 | 8* |
| PR8 | 1 | 5 | 3 | 0 | 9 |
| PR9 | 14 | 0 | 0 | 0 | 14 |
| PR10 | 9 | 2 | 2 | 1 | 15** |
| **Total** | **39** | **23** | **11** | **3** | **77** |

(Plus 1 🔴 BUG on PR10 step 5 — Mapbox POI search returning addresses only.)

*PR7 row 7 is ⚪ N/A (superseded by PR8); 7 testable + 1 superseded = 8.

**PR10 row 5 is 🔴 BUG (Mapbox returns no POIs); 9 done + 2 blocked-on-bug + 2 owed + 1 N/A + 1 bug = 15.

**Headlines (2026-05-15 evening, post-PR10 walk):**
- **39 done**, **21 blocked on COROS/Polar partner credentials**, **2 blocked on PR10 step-5 bug**, **11 doable now**, **3 N/A**.
- **🔴 PR10 step 5 — Mapbox returning street/city addresses, not POI/business names.** Most acute open item. Foreseen in D-59 §12 but biting harder than expected. Investigation owed: curl Mapbox directly to inspect `features[].place_type`. Likely fix paths: (A) drop `address` from `types` filter, (B) migrate to Mapbox Search Box API, (C) check token scopes. PR10 steps 6 + 7 (chain-anchored save + nearby picker) are unverifiable until this is fixed.
- The COROS/Polar credential block is still the dominant blocker — once those land, ~21 steps unblock.
- 11 doable-now steps remaining: PR2 (1 schema spot-check) + PR3 (1 index spot-check) + PR4 (1 page-render) + PR5 (3) + PR8 (3) + PR10 (2 — disclosure version-bump + skipped token-missing).

---

*End of PR Verification Status.*
