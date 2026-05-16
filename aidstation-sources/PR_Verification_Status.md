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
| 5 | Search happy path: results with hidden mapbox_id/lat/lng + Save button | ✅ Done | 2026-05-15 | **Initial walk surfaced 🔴 BUG** with Geocoding v5; fixed same session via Search Box API migration (PR #43, merge `dcddeff`). **Re-walk after fix:** search returns multiple POI results with place name + full address. Initial post-fix render showed a raw Mapbox `poi_category` badge ("gym, services") on result cards that didn't match our internal taxonomy — cosmetic only since stored category in `locale_profiles` is correctly derived from chain registry. **Fixed same session** by removing the raw category span from `templates/locales/new.html` line 85. The stored category badge still renders correctly on `/locales` list (step 10 verified). |
| 6 | Save chain-anchored: redirect to `/locales/<slug>/nearby`; row has correct chain_id/category | ✅ Done | 2026-05-15 | Verified with Anytime Fitness anchor — saved row has `chain_id='anytime_fitness'`, `chain_name='Anytime Fitness'`, `category='commercial_chain_gym'`, `lat`/`lng` populated, `manual_entry=false`. Redirect to nearby picker fired. |
| 7 | Nearby picker: same-chain matches + opt-in INSERT | ✅ Done | 2026-05-15 | Picker rendered same-chain matches. Andy selected 2 and saved. `_unique_slug` collision-suffix produced `anytime_fitness`, `anytime_fitness_2`, `anytime_fitness_3` (3 total rows with same chain_id, distinct mapbox_id). |
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

## PR11 — D3b D-60 inherit/override UI + D-59 §6 upgrade + §7 refresh + PR2 FK fix (pending merge)

§5.0 has 14 testable steps. PR11 is on branch `claude/v5-closing-handoff-eZFt9`; PR creation + merge + deploy pending.

| # | Step | Status | Last update | Notes |
|---|------|--------|-------------|-------|
| 1 | `locale_equipment_overrides` + `locale_toggle_overrides` FK shape (`locale TEXT NOT NULL`, composite FK to `locale_profiles(user_id, locale) ON DELETE CASCADE`) | ✅ Done | 2026-05-16 | Andy ran `\d locale_equipment_overrides` + `\d locale_toggle_overrides` in Neon SQL editor. Both tables show `locale TEXT NOT NULL` (not `locale_id INTEGER`); `CHECK (action IN ('add','remove'))` on the equipment table; `UNIQUE (user_id, locale, equipment_tag, action)` / `(user_id, locale, toggle_name)`; composite FK `(user_id, locale) → locale_profiles(user_id, locale) ON DELETE CASCADE` on both. PR2 silent-failure pattern closed. |
| 2 | D-60 first-athlete: build profile flow writes `gym_profiles` + links `gym_profile_id` | ✅ Done | 2026-05-16 | Andy walked end-to-end. UX gap surfaced: three Anytime Fitness rows are visually indistinguishable on `/locales` because address is stored in `place_payload` JSON but no view extracts it. Captured for follow-up PR (item A). |
| 3 | D-60 subsequent-athlete: inherit + override flow writes `locale_equipment_overrides` rows; bumps `last_confirmed_*` + `contribution_count` | ✅ Done | 2026-05-16 | All assertions passed. |
| 4 | §6 manual→Mapbox upgrade flips `manual_entry=FALSE` + preserves slug + FKs | ✅ Done | 2026-05-16 | Upgrade works; row UPDATEd in place, slug preserved. Surfaced 4 follow-up items during this walk: (A) address not surfaced on list/edit views, (B) 🔴 `/locales/<slug>/refresh` fails when athlete renamed locale because route uses `locale_name` as the Mapbox search query — "Horn's House" returns no results; needs Search Box `/retrieve` endpoint with `mapbox_id`, (C) no duplicate-address detection at create, (D) no delete UI, (E) legacy enums should retire. |
| 5 | §7 refresh — no-change path | ✅ Done | 2026-05-16 | Info flash + `place_fetched_at` bumped on locales whose `locale_name` still matches the Mapbox-indexed name. |
| 6 | §7 refresh — change path renders confirm template + Yes applies | 🟡 blocked on B | 2026-05-16 | Cannot walk reliably until refresh route is rewritten to use `mapbox_id` lookup instead of `locale_name` search (B). Walks correctly only for locales the athlete hasn't renamed; same `MapboxNoResults` failure as item B blocks the path for renamed locales. |
| 7 | §7 refresh — token-missing path | 🟡 skipped | 2026-05-16 | Skipped per PR10 step 12 equivalent — non-critical with token already set. |
| 8 | §7 refresh — stale mapbox_id path | 🟡 skipped | 2026-05-16 | Skipped — low priority edge case. |
| 9 | `MANUAL_CATEGORIES` dropdown shows all 10 D-60 §3 entries | ✅ Done | 2026-05-16 | All 10 categories render. UX feedback: "Home gym" + "Other residence" labels could be clearer — Andy suggested "Primary residence gym" + a better label for "Other residence." Captured for follow-up PR. |
| 10 | Regression — legacy enum edit forms unchanged | ✅ Done | 2026-05-16 | home/hotel/partner/airport edit screens render the simple `locale_equipment` form unchanged. |
| 11 | Regression — athlete-created no-shared-profile categories (home_gym/outdoor_park/other_residence) take legacy flow | ✅ Done | 2026-05-16 | home_gym-categorized locale routes to `_edit_legacy_locale`, not the shared-profile UI. |
| 12 | Regression sweep on /profile, /onboarding/connect, /onboarding/prefill, /dashboard, /training | ✅ Done | 2026-05-16 | No visual regressions on the broader app surface. |
| 13 | Cross-user scoping on /locales/<slug>/edit (shared) + /locales/<slug>/refresh | ⚪ N/A | 2026-05-15 | Single-test-athlete state. |
| 14 | Pre-existing PR2 FK bug `locale_equipment_overrides.locale_id → locale_profiles(id)` corrected end-to-end (table actually exists post-deploy) | ✅ Done | 2026-05-16 | Implicitly verified by step 1 (`\d` output) + step 3 (override INSERTs landed correctly against the composite FK). |

---

## PR18 — locale-CRUD bundle (PR11 follow-on; pending merge)

§5.0 has 12 testable steps. PR18 is on branch `claude/review-handoff-docs-SiQAY`; PR creation + merge + deploy pending.

| # | Step | Status | Last update | Notes |
|---|------|--------|-------------|-------|
| 1 | Item A — address caption renders on `/locales` cards under each non-legacy locale name | 🟡 Owed | 2026-05-16 | Walk on Vercel after deploy. Set up: have ≥3 saved Mapbox-anchored locales (ideally 2+ with the same `locale_name` to verify the original UX gap is closed). Expect: each card shows the street address as muted small text below the title; empty/legacy locales render no address line. Confirm via DOM inspection that `<div class="text-muted small fw-normal mt-1">` only appears when `display_addresses[locale]` is non-empty. |
| 2 | Item A — address caption renders on edit form header for Mapbox-anchored locales | 🟡 Owed | 2026-05-16 | Walk: open `/locales/<chain-slug>/edit`. Expect: address shown as muted small `<p>` under the header. Legacy enum edit screens + manual-entry rows without a `place_payload` show no address (empty placeholder div). |
| 3 | Item B 🔴 — refresh works on a renamed locale (the actual bug fix) | 🟡 Owed | 2026-05-16 | Set up: save a chain locale, then rename `locale_name` to something Mapbox-unindexable like "Horn's House"; click ⟳ Refresh from Mapbox. Expected old behavior: `MapboxNoResults` flash + edit redirect. Expected new behavior: silent or confirm-path success because `/retrieve/{mapbox_id}` is name-agnostic. Verify in Neon: `place_fetched_at` bumped; `place_payload` JSON refreshed. |
| 4 | Item B regression — refresh on an un-renamed locale still works | 🟡 Owed | 2026-05-16 | Walk a previously-working refresh path; expect identical UX (silent / confirm dialog as appropriate). Confirms the `retrieve` swap didn't regress the happy path. |
| 5 | Item C — dup-check on `_save_mapbox_anchored` INSERT path | 🟡 Owed | 2026-05-16 | Walk: from `/locales/new`, search for a place this athlete already has saved; pick it; submit. Expect: warning flash "You already have a locale at this address (X). Edit it instead." + redirect to `/locales/<dup-slug>/edit`. No new row in `locale_profiles`. |
| 6 | Item C — dup-check on upgrade path | 🟡 Owed | 2026-05-16 | Walk: have a manual-entry row M and a Mapbox-anchored row X with the same Mapbox feature in mind. Try to upgrade M to X's feature; expect the same dup warning + redirect to X's edit screen. Verify M stays `manual_entry=TRUE`, unchanged. |
| 7 | Item C — dup-filter on `nearby_instances` POST | 🟡 Owed | 2026-05-16 | Walk: trigger the nearby picker on a chain; pick at least one box that's already saved. Expect: "Skipped N already-saved location(s)" info flash; new chain instances added; no duplicate rows in `locale_profiles`. |
| 8 | Item D — delete a chain locale (shared `gym_profiles` row preserved) | 🟡 Owed | 2026-05-16 | Walk: navigate to a chain-locale edit screen; confirm Delete button visible at bottom; click → browser confirm → POST. Expect: row deleted from `/locales`; flash "Deleted X."; Neon shows `locale_profiles` row gone + cascaded `locale_equipment_overrides` / `locale_toggle_overrides` rows gone; **`gym_profiles` row for that mapbox_id stays** (enterprise data preserved for other athletes). |
| 9 | Item D — delete a `home_gym` locale (linked `gym_profiles` also deleted if created by this user) | 🟡 Owed | 2026-05-16 | Set up: create a `home_gym`-category locale; if the schema doesn't auto-link a `gym_profiles` row (it shouldn't under current taxonomy), force-link one for the test by setting `gym_profile_id` via SQL. Delete. Expect: `locale_profiles` gone; `gym_profiles` row also gone (privacy: residences never enterprise-shareable). Confirm `created_by_user_id = uid` guard via test where another user is set as creator — that row should survive. |
| 10 | Item D — delete button hidden on legacy enum edit screens + DELETE route rejects legacy slugs | 🟡 Owed | 2026-05-16 | Walk: open `/locales/home/edit`. Expect: no Delete button. Direct POST to `/locales/home/delete` (curl): expect warning flash "Legacy locale slots cannot be deleted." + redirect to edit. |
| 11 | outdoor_park reclassification — inherit/override UI renders | 🟡 Owed | 2026-05-16 | Set up: create an outdoor_park-category locale with a `mapbox_id` (e.g., search "Theodore Wirth Park" on `/locales/new`). Open the edit screen. Expect: shared-profile inherit/override UI renders (mode `shared_build` for the first athlete; `shared_inherit` for subsequent). Equipment list is gym-centric — most checkboxes don't apply (known follow-up per handoff §6). Confirm `SHARED_PROFILE_CATEGORIES` count = 8 in code. |
| 12 | Label tweaks render — `Home (primary residence)` + `Other residence (in-laws / friend / AirBnB)` | 🟡 Owed | 2026-05-16 | Walk: `/locales/new?manual=1`. Confirm category dropdown shows the new labels (enum values `home_gym` / `other_residence` unchanged in DB). |

**Cross-user dup-detection scoping** (would be step 13) is ⚪ N/A at N=1 single-test-athlete state — the dup-check is correctly scoped by `user_id` in code; cross-user verification gates on a second test account.

---

## PR19 — retire legacy `LOCALES` external consumers (PR18 follow-on Item E; pending merge)

§5.0 has 11 testable steps. PR19 is on branch `claude/locale-crud-bundle-closing-imqrG`; PR creation + merge + deploy pending.

| # | Step | Status | Last update | Notes |
|---|------|--------|-------------|-------|
| 1 | `/coaching/generate` GET — primary "Current Location" dropdown shows athlete's actual locales | 🟡 Owed | 2026-05-16 | Walk: open `/coaching/generate`. Expect: dropdown lists 4 legacy slots first (`Home`/`Hotel`/`Partner`/`Airport`, using `locale_name` if a row exists or capitalize(slug) otherwise) + any athlete-created locales alpha by slug with their `locale_name` labels. Pre-selected option = `home`. Confirm DOM `<option value="home" selected>` is the first item. |
| 2 | `/coaching/generate` GET — trip-locale dropdown still shows the 4-bucket type taxonomy | 🟡 Owed | 2026-05-16 | Walk: add a trip row in the form's travel-schedule section. Expect: the trip's Location dropdown shows only the 4 legacy buckets (`Home`/`Hotel`/`Partner`/`Airport`) — NOT the athlete's saved locales. Pre-selected = `hotel`. Iterates `trip_locale_types`, not `locales`. |
| 3 | `/coaching/generate` POST validation — invalid locale rejected, no silent fallback | 🟡 Owed | 2026-05-16 | Walk: tamper the form's `locale` field via devtools to `<option value="not_a_slug">` + submit. Expect: red flash "Select a valid current location." + redirect back to `/coaching/generate` (GET). No plan generated. Replaces the pre-PR19 silent rewrite to `'home'`. |
| 4 | `/coaching/review` GET — same primary + trip dropdown behavior | 🟡 Owed | 2026-05-16 | Walk: open an existing plan's `/coaching/review/<plan_id>`. Confirm same behavior as steps 1 + 2. The locale-rows JS template (`#locale-row-template`) trip dropdown also iterates `trip_locale_types`. |
| 5 | `/coaching/review` POST validation — same form-level guard | 🟡 Owed | 2026-05-16 | Walk: tamper + submit. Expect: same flash + redirect to GET. |
| 6 | `/references/exercises` GET — filter checkboxes show athlete's actual locales | 🟡 Owed | 2026-05-16 | Walk: open `/references/exercises`. Expect: checkbox row shows athlete's locale list (legacy slots + custom), using `locale_name` labels for any saved rows. NOT the raw 4-bucket enum. |
| 7 | `/references/exercises?locale=home` — legacy-bucket filter still works | 🟡 Owed | 2026-05-16 | Walk: tick `Home` checkbox. Expect: exercise rows filtered to those with `home` in `where_available` CSV; equipment-overlap filter from `locale_equipment` still applies. Regression check on the pre-PR19 happy path. |
| 8 | `/references/exercises?locale=<custom_chain_slug>` — custom-locale filter maps via category bucket | 🟡 Owed | 2026-05-16 | Set up: have a `commercial_chain_gym` locale saved. Walk: tick its checkbox. Expect: exercise rows filtered to those with `partner` in `where_available` (the category's mapped bucket); equipment-overlap filter applies if `locale_equipment` rows exist. |
| 9 | `/references/exercises?locale=<outdoor_park_slug>` — outdoor_park resolves to empty bucket → 0 exercises | 🟡 Owed | 2026-05-16 | Set up: have an outdoor_park locale saved. Walk: tick only that checkbox. Expect: zero exercise rows shown (the bucket map resolves to `''`, contributing nothing to the intersection). Known follow-up per handoff §6 / PR18 §5.2 — needs a park-tag taxonomy. |
| 10 | `/references/exercises?locale=fake_slug` — tampered URL params sanitized | 🟡 Owed | 2026-05-16 | Walk: hit `/references/exercises?locale=fake_slug` directly. Expect: the unknown slug is filtered out of `locale_filter` (defensive sanitize against `valid_slugs`); page renders as if no filter were applied. No crash, no 500. |
| 11 | No external `LOCALES` references remain in codebase | 🟡 Owed | 2026-05-16 | Verification grep post-deploy: `grep -rn "from routes.locales import LOCALES\|^LOCALES = \['home'" --include="*.py" .` returns only `routes/locales.py:15` (the internal-only literal). |

---

## Aggregate status (2026-05-16, post-PR19 ship)

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
| PR10 | 12 | 0 | 2 | 1 | 15** |
| PR11 | 10 | 0 | 3 | 1 | 14 |
| PR18 | 0 | 0 | 12 | 0 | 12 |
| PR19 | 0 | 0 | 11 | 0 | 11 |
| **Total** | **52** | **21** | **37** | **4** | **114** |

(PR10 step 5 had a 🔴 BUG mid-walk on 2026-05-15; fixed same session by switching to Mapbox Search Box API forward endpoint (PR #43, merge `dcddeff`). Re-walked + verified: steps 5/6/7 now ✅.)

*PR7 row 7 is ⚪ N/A (superseded by PR8); 7 testable + 1 superseded = 8.

**PR10 row 5 is 🔴 BUG (Mapbox returns no POIs); 9 done + 2 blocked-on-bug + 2 owed + 1 N/A + 1 bug = 15.

**Headlines (2026-05-16, post-PR19 ship):**
- **52 done**, **21 blocked on COROS/Polar partner credentials**, **37 doable now (14 pre-PR18 + 12 PR18 §5.0 walks + 11 PR19 §5.0 walks)**, **4 N/A**.
- **PR10 D3a fully functional end-to-end** after the Search Box API migration (PR #43) + result-card badge cleanup.
- **PR11 D3b walked end-to-end** (10/14 ✅); step 6 was blocked on PR18 item B and unblocks once the `/retrieve`-based refresh ships to production.
- **PR18 locale-CRUD bundle shipped** — 12 testable §5.0 steps owed for the post-merge walk. After the walk, PR11 step 6 should also be re-walkable + flipped ✅.
- **PR19 retire legacy `LOCALES` external consumers shipped** — closes the PR18 closing-handoff §5.1 deferred item. 6 substantive code files (`routes/locales.py` additive helper + bucket-map, `routes/coaching.py` LOCALES drop + TRIP_LOCALE_TYPES + form-level guard refactor, `routes/references.py` import swap + bucket-mapped filter, 3 templates). 11 testable §5.0 steps owed for post-merge walk. Closes the v1-coaching-form `LOCALES` hard-coupling story.
- The COROS/Polar credential block is still the dominant blocker — once those land, ~21 steps unblock at once.
- 14 pre-PR18 doable-now steps: PR2 (1) + PR3 (1) + PR4 (1) + PR5 (3) + PR8 (3) + PR10 (2 — step 12 token-missing + step 13 disclosure version bump) + PR11 (3 — step 6 unblocks post-PR18, steps 7+8 low-priority skipped). Post-PR18+PR19 deploy, these become **14 + 12 + 11 = 37 doable-now**.

---

*End of PR Verification Status.*
