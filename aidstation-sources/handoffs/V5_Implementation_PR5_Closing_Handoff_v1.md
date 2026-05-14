# V5 Onboarding Implementation PR5 — Closing Handoff

**Session:** Fifth substantive code session of the v5 onboarding implementation arc. Executes PR4 §5.1 Option D1 — the v5 Step 2 "Connect your fitness providers" onboarding screen. Pairs with a one-line drive-by CSP nonce fix on the PR4 tab-activation script. D2 (per-field prefill UX), D3 (locale-creation), E (14-day nudge), F (Polar refresh-on-401), G (coros_ingest ON CONFLICT cleanup), and H (more providers) remain out of scope.
**Date:** 2026-05-14
**Predecessor handoff:** `V5_Implementation_PR4_Closing_Handoff_v1.md` (its §5.1 Option D1 is what this session executes; its §5.2 recommended sequence D1 → E → D2 → D3 is what Andy chose).
**Branch:** `claude/review-v5-connections-wKFIv` (new PR5 feature branch off `main`; PR4 was already merged to `main` via `f4d2e75` before this session started).
**Status:** 🟡 Code shipped to feature branch; 🟡 push pending; 🟡 live `/onboarding/connect` page-load + click-through verification owed at deploy time (no Flask in sandbox, same gap as PR1–PR4).
**Time-on-task:** Single chat. Substantive files: **5** (`routes/profile.py`, `routes/onboarding.py` [new], `templates/onboarding/connect.html` [new], `app.py`, `routes/auth.py`) plus a 1-line CSP-nonce fix on `templates/profile/edit.html`. Plus this handoff (6 total — same one-over-ceiling pattern PR1, PR3, PR4 hit).

---

## 1. Session-start verification (Rule #9)

Verified the PR4 handoff's claimed state before any new work.

| Claim | Anchor | Result |
|---|---|---|
| Branch `claude/review-v5-connections-wKFIv` clean off `main`; PR4 merged to `main` as `f4d2e75` (commit `fecf9be`) | `git status` + `git log --oneline -10` | ✅ Verified |
| `routes/provider_auth.py` exports `disconnect(db, user_id, provider) -> bool` at line 123 | `grep "^def disconnect"` | ✅ Verified |
| `routes/profile.py` defines `CONNECTION_PROVIDERS` (L50), `_load_connections` (L68), `disconnect_provider` route (L229) | grep | ✅ Verified |
| `templates/profile/edit.html` has `#tab-connections` pane (L101), `just_connected_label` alert, `profile.disconnect_provider` form action | grep | ✅ Verified |
| `Project_Backlog_v17.md` exists; predecessor v16 block intact | sed + grep | ✅ Verified |
| `aidstation-sources/CLAUDE.md` "Authoritative current files" backlog line reads v17 | grep | ✅ Verified |
| Andy's manual `/profile?tab=connections` click-through (PR4 §5.0 spot-check) passed | Andy in chat | ✅ Reported |

**Drift found (one item):** PR4's tab-activation `<script>` in `templates/profile/edit.html` at L389 was missing the `nonce="{{ csp_nonce() }}"` attribute. The app's CSP (`app.py:_csp_for_nonce`) sets `script-src 'self' 'nonce-<value>' https://cdn.jsdelivr.net` with no `'unsafe-inline'`, so the inline script would be blocked in production unless `CSP_REPORT_ONLY=1`. Andy's manual click-through likely landed without triggering the failing path (the script auto-activates the Connections tab after OAuth redirect; manually navigating to `?tab=connections` works regardless of whether the script runs because Bootstrap's `data-bs-toggle="tab"` handles direct tab clicks via the bundled CSP-nonced script tag in `base.html`). One-line fix landed this PR (see §3.4).

The v17 file-revision header narrative on `Project_Backlog_v17.md` line 5 also reads "🟢 PR1 + PR2 + PR3 shipped" — missing PR4 in the header *narrative* (the D-50 row body correctly reads PR1 + PR2 + PR3 + PR4 per PR4 handoff §4). This is a minor cosmetic drift in the predecessor's bookkeeping; left unfixed this PR (not on the critical path; would be a v18 bump that's pure cosmetic and adds a file off the budget). Flagged in §6.

The PR4 handoff's branch name `claude/review-v5-pr3-handoff-PwMfn` and this PR's branch `claude/review-v5-connections-wKFIv` are both per-session feature branches; PR4 is merged to `main`, PR5 starts fresh off `main`.

---

## 2. Files shipped this turn

All on branch `claude/review-v5-connections-wKFIv`.

| # | File | Type | Notes |
|---|---|---|---|
| 1 | `routes/profile.py` | Edit (rename + signature change) | (a) `_load_connections` → `load_connections` (drop the leading underscore — now imported by `routes/onboarding.py`). (b) Added optional `return_to` param defaulting to `/profile?tab=connections` so the PR4 Connections-tab caller keeps working unchanged. (c) The single in-file call site at the `edit()` GET render path updated to the new name. `CONNECTION_PROVIDERS` and `_STATUS_DISPLAY` stay in this module; both are imported by `routes/onboarding.py` (the second consumer). A third consumer would justify extracting to a shared `routes/provider_registry.py`, but premature now. |
| 2 | `routes/onboarding.py` | New (3 routes + 1 module-scope constant + module docstring) | New `onboarding` blueprint at `/onboarding`. **`GET /onboarding/connect`** — Step 2 connect screen. Calls `load_connections(db, uid, return_to=/onboarding/connect)` and reads `?<slug>_connected=1` / `?<slug>_oauth_error=…` / `?<slug>_register_error=1` flags into `just_connected_label` / `oauth_error_label` (first-hit-wins, same pattern as PR4 `profile.edit`). **`POST /onboarding/skip`** — flashes "You can connect providers any time from Profile → Connections.", redirects to `_POST_STEP2_TARGET`. No DB write; the 14-day nudge (Option E) keys off `provider_auth` rowcount + account age, not off a skip event. **`POST /onboarding/continue`** — same redirect target as skip; kept as a separate endpoint so future analytics can tell the two apart by intent. `_POST_STEP2_TARGET = '/profile?tab=athlete'` — the closest existing v1 surface to v5 §A entry; D2 will swap this to the prefill comparison page when it lands. |
| 3 | `templates/onboarding/connect.html` | New (~150 lines) | Step-2 onboarding UI. (a) Step indicator (Step 1 ✓ → **Step 2** → Step 3). (b) `<details>` block with v5 §A.1 Connected Service consent disclosure — draft copy explicitly naming activity / wellness / sleep / account-profile data classes plus the revocation pointer; explicitly marked "Draft copy — final wording is product/legal-owned per v5 spec §A.1." (c) Post-OAuth success / error alerts (same pattern as PR4 `profile.edit`, copy adjusted for onboarding context: "Connect another service below, or click Continue when you're done."). (d) Provider list-group reusing `c.status_label` / `c.badge_class` / `c.connect_url` from `load_connections`. For *not-connected* providers each card includes a per-provider consent checkbox ("I agree to the data sharing above") that gates the Connect link via a small inline `<script nonce="{{ csp_nonce() }}">` — the link starts with `.disabled` + `aria-disabled="true"` + `tabindex="-1"` (Bootstrap 5 disabled-link pattern) and the JS toggles those attributes on checkbox change. (e) Re-authorise button for connected providers (no consent gate — the athlete already consented when they originally connected). (f) Skip-for-now and Continue forms at the bottom; Continue's button label dynamically reads "Continue (N connected)" when at least one provider is connected, "Continue without connecting" otherwise. Both POST forms include `{{ csrf_token() }}`. |
| 4 | `app.py` | Edit (+2 lines) | (a) `from routes.onboarding import bp as onboarding_bp` next to the existing `from routes.profile import bp as profile_bp`. (b) `app.register_blueprint(onboarding_bp)` right after the profile-blueprint registration. No `_AUTH_EXEMPT_ENDPOINTS` entry (onboarding requires login — the global gate handles it). No `csrf.exempt` call (onboarding POSTs use the default Flask-WTF gate; both forms render `csrf_token`). |
| 5 | `routes/auth.py` | Edit (+1 line, +6 comment lines) | Post-register redirect target changed from `dashboard.index` to `onboarding.connect`. Comment block explains the rationale: new athletes drop on the connect screen first; the connect screen is itself skippable; no `onboarded_at` flag column — existing athletes (Andy) can revisit `/onboarding/connect` directly any time. |
| — | `templates/profile/edit.html` | Edit (1-attribute drive-by fix) | Added `nonce="{{ csp_nonce() }}"` to the tab-activation `<script>` tag at L389. PR4 shipped this without a nonce; the CSP would block it in production unless `CSP_REPORT_ONLY=1`. Surgical one-line fix; bundled here because PR5 is the natural follow-on and the same template now hosts an analogous PR5 script (in `templates/onboarding/connect.html`) which gets the nonce right. |
| — | `aidstation-sources/handoffs/V5_Implementation_PR5_Closing_Handoff_v1.md` | New (this file) | Session-end bookkeeping. |

**Files explicitly NOT touched:**

- `routes/coros.py` / `routes/polar.py` / `routes/oauth_callbacks.py` — **zero edits.** PR5 reuses both `oauth_start` endpoints unchanged; the onboarding Connect buttons link to `coros.oauth_start` / `polar.oauth_start` with `?return_to=/onboarding/connect` and rely on the existing same-origin guard (`return_to.startswith('/')` and `not startswith('//')`).
- `init_db.py` — unchanged. No new schema. PR5 does not add an `onboarded_at` flag on `users`; the onboarding screen is visit-able any time by any logged-in user, and the spec doesn't require a one-time-only firing point.
- `routes/provider_auth.py` — unchanged. `disconnect`, `record_oauth_scope_ack`, and the rest of the PR1+PR4 helper surface are reused as-is.
- `Project_Backlog_v17.md` — unchanged. No v17→v18 bump deferred or owed (PR4 closed the v16→v17 catchup; PR5 lives on the v1-cadence). The v18 bump for PR5 lands in PR6 per Rule #11.
- `aidstation-sources/CLAUDE.md` — unchanged. Backlog version reference still reads v17.
- `DATABASE.md` / `PROVIDERS_SCHEMA.md` — same "deferred to consolidated docs PR" framing PR1–PR4 used. PR5 ships no schema; the 8 undocumented additions count holds.
- `templates/base.html` — unchanged. Onboarding lives at `/onboarding/connect`, not a top-level nav entry (the nav-bar would only confuse already-onboarded athletes; the URL is reachable directly).

---

## 3. What landed

### 3.1 `routes/onboarding.py` blueprint

Three routes, all under `/onboarding`, all behind the global `_require_login` gate.

```python
@bp.route('/connect', methods=['GET'])
def connect():
    # render Step 2 with load_connections(..., return_to='/onboarding/connect')

@bp.route('/skip', methods=['POST'])
def skip():
    # flash + redirect to /profile?tab=athlete; no DB write

@bp.route('/continue', methods=['POST'])
def continue_():
    # redirect to /profile?tab=athlete; same target as skip, kept separate for intent-tracking
```

Three design choices worth flagging:

- **No `onboarded_at` column / no one-time-only gate.** PR5 deliberately doesn't track "this athlete has completed onboarding." Existing athletes (Andy) hitting `/onboarding/connect` directly see the same surface as a fresh signup; for them it functions as a duplicate of the Connections tab with a different URL and slightly different chrome. The cost of adding a column + a gate would be (a) a new schema migration, (b) deciding what "onboarded" means (skipped Step 2 with 0 connections counts? clicked Continue with N connections counts?), and (c) a per-request check on every authenticated request. None of that earns its keep for a sole-test-athlete app.
- **Continue and Skip share the redirect target.** Both land on `/profile?tab=athlete`. Continue is *currently* a duplicate of Skip in observable behavior; the two are kept as separate endpoints so a future analytics layer can read POST request volumes and tell "athlete chose to skip with 0 connected" apart from "athlete connected N and chose to advance." When D2 ships the prefill comparison page, this target swaps to whatever D2's URL is.
- **No DB write on Skip.** The 14-day connect-provider nudge (Option E in PR4 §5.1) keys off `provider_auth` rowcount + account age, not off a skip event. If a future PR wants to differentiate "skipped explicitly during onboarding" from "never visited the page," it can add an `account_nudges` row with `nudge_type='step2_skipped'` in the skip handler. Not in PR5 scope.

### 3.2 Step 2 template (`templates/onboarding/connect.html`)

**Layout.** Extends `base.html`. Single-column page (no tab nav — Step 2 is a standalone screen, not a sub-tab of /profile). Step indicator at the top renders Step 1 ✓ (Account) → **Step 2** (Connect providers) → Step 3 (Profile) as a single-line breadcrumb-style ordered list.

**Consent disclosure (v5 §A.1).** Collapsible `<details>` block with header "What you're consenting to when you connect a service — click to expand." Body names the four data classes that COROS + Polar actually read (activity, wellness, sleep, account profile) and points at the revocation path (Profile → Connections). Footer reads "Draft copy — final wording is product/legal-owned per v5 spec §A.1." so Andy has something concrete to redline pre-launch.

**Per-provider consent gate.** Each not-yet-connected provider card includes a checkbox ("I agree to the data sharing above") with the Connect link starting `disabled` (Bootstrap 5 disabled-link pattern: class `disabled` + `aria-disabled="true"` + `tabindex="-1"`). A small inline `<script nonce="{{ csp_nonce() }}">` listens for checkbox change events and toggles those attributes. Connected providers (Re-authorise button) have no consent gate — the athlete already consented at original connect time.

**Post-OAuth callback handling.** Same `?<provider>_connected=1` / `?<provider>_oauth_error=…` / `?<provider>_register_error=1` flag pattern as PR4. Success alert copy adjusted for onboarding context: "Connect another service below, or click Continue when you're done." (vs PR4's "We'll start pulling..."). Both alerts have a `btn-close` link back to `/onboarding/connect` with the query params cleared.

**Continue button copy.** Reads `Continue (N connected)` when `connected_count > 0`, `Continue without connecting` otherwise. Honest about the state; doesn't pretend the athlete connected something when they didn't.

### 3.3 New-user post-register redirect

`routes/auth.py:register` previously redirected newly-registered users to `dashboard.index`. PR5 redirects to `onboarding.connect`. Existing-account users hit `/auth/login` (unchanged) and continue to land where they were going. Andy's existing test account is unaffected — he can revisit `/onboarding/connect` by typing the URL directly any time.

### 3.4 Drive-by: PR4 CSP nonce fix on `templates/profile/edit.html`

PR4's tab-activation `<script>` at L389 was missing `nonce="{{ csp_nonce() }}"`. The app's CSP (`app.py:344-353`) sets `script-src 'self' 'nonce-<value>' https://cdn.jsdelivr.net` with no `'unsafe-inline'`, so the inline script would be blocked under enforced CSP. One-line addition: `<script>` → `<script nonce="{{ csp_nonce() }}">`. Same nonce mechanism PR5's onboarding script uses correctly from the start.

**Why bundle this with PR5 rather than a separate PR:** the fix is one attribute, directly related to the same tab-activation flow PR5 builds on, and is the kind of issue Rule #9 reconciliation should catch + fix in the next PR rather than defer. The alternative (a separate one-line PR) would be more bookkeeping cost than the fix is worth.

---

## 4. Session-end verification (Rule #10)

Anchor checks against on-disk state before composing this handoff.

| Claim | Anchor | Result |
|---|---|---|
| All 4 edited Python files AST-parse clean (`routes/profile.py`, `routes/onboarding.py`, `routes/auth.py`, `app.py`) | `ast.parse` over each | ✅ Verified |
| `routes/profile.py` exposes `load_connections` (renamed from `_load_connections`) and `CONNECTION_PROVIDERS` (unchanged) | grep | ✅ Verified |
| No file in the repo still references the old `_load_connections` name | `grep -rn "_load_connections\b"` returns no hits | ✅ Verified |
| `routes/onboarding.py` defines `connect`, `skip`, `continue_` routes and imports `CONNECTION_PROVIDERS, load_connections` from `routes.profile` | grep | ✅ Verified |
| `routes/auth.py:register` redirects to `url_for('onboarding.connect')` | grep | ✅ Verified |
| `app.py` imports + registers the new blueprint | grep | ✅ Verified |
| `templates/onboarding/connect.html` Jinja parses cleanly | `Environment.parse()` | ✅ Verified |
| `templates/profile/edit.html` Jinja parses cleanly (drive-by edit didn't break syntax) | `Environment.parse()` | ✅ Verified |
| Stub render of `onboarding/connect.html` covers happy-path (1 connected COROS, not-connected Polar, just_connected_label='COROS') | inline `Environment.from_string(...).render(...)` with mocked `url_for` + `csrf_token` + `csp_nonce` + stub base.html | ✅ Verified — 10 render anchors present: `Step 2 — Connect providers`, `COROS connected`, `Connect Polar`, `Skip for now`, `Continue (1 connected)`, `consent-polar`, `nonce="NONCE_STUB"`, `data-target-link="connect-link-polar"`, `csrf_token` input. The `consent-coros` checkbox is correctly absent (COROS already connected → no consent gate). |
| Render variant: 0 connected (both providers `is_connected=False`) | inline render | ✅ Verified — `Continue without connecting` present, `COROS connected` absent, `consent-coros` + `consent-polar` both present |
| Render variant: oauth_error_label='Polar' | inline render | ✅ Verified — `Polar did not connect` alert renders |
| Flask not installed in sandbox — full app import not exercisable | python3 import check | ⚠️ Same gap as PR1–PR4. Live `/onboarding/connect` page-load owed at deploy time |
| `templates/profile/edit.html` script tag has `nonce="{{ csp_nonce() }}"` after drive-by fix | grep | ✅ Verified |

No drift between this handoff's narrative and on-disk state.

The same "can't exec the Flask app without Flask" gap PR1 §6 + PR2 §4 + PR3 §4 + PR4 §4 flagged applies. AST + Jinja parse + stub-render are the offline guards. The PR5 §5.0 live-check (open `/onboarding/connect`, click Connect on each provider after checking the consent box, complete OAuth, return, verify the success alert + Continue button copy) is mandatory before this PR is "real."

---

## 5. Mechanically-applicable instructions for next session (Rule #11)

### 5.0 Pre-deploy verification (must run before PR5 reaches production)

Lighter than PR3 §5.0 because PR5 ships no schema changes or new env vars. Just live-page verification.

1. **Open `/onboarding/connect`** as a logged-in user. Confirm:
   - Step indicator renders "Step 2 — Connect providers" in bold.
   - Both COROS and Polar entries render with "Not connected" badge (assuming you've disconnected them via PR4's tab first, or use a fresh account).
   - The consent disclosure `<details>` block is collapsed by default; expanding it shows the four data-class bullet list.
   - Each not-connected provider card shows a consent checkbox + a *disabled* Connect button (the link should have CSS class `disabled` + `aria-disabled="true"`; cursor visually disabled).
2. **Click the consent checkbox** for COROS. Confirm the Connect button enables (CSS class `disabled` removed, click bounces to OAuth).
3. **Complete COROS OAuth.** Confirm redirect to `/onboarding/connect?coros_connected=1` with the green "COROS connected." alert visible and the COROS card flipped to "Connected" with a Re-authorise button (no consent gate this time).
4. **Click the "Continue (1 connected)" button.** Confirm POST to `/onboarding/continue` → redirect to `/profile?tab=athlete`. The Athlete tab should be active (per PR4's tab-activation script — which now has the CSP nonce per PR5 §3.4).
5. **Register a fresh test account** (if you can — depends on `ALLOW_REGISTRATION`). Confirm post-register redirect lands on `/onboarding/connect` instead of `/dashboard`. Confirm the success flash "Account created — welcome, …" carries over.
6. **Spot-check Skip path.** Open `/onboarding/connect` again as a connected athlete; click "Skip for now". Confirm POST to `/onboarding/skip` → redirect to `/profile?tab=athlete` with "You can connect providers any time from Profile → Connections." flash.
7. **CSP check.** Open browser devtools → Console on `/profile?tab=connections`. Confirm the inline tab-activation script no longer throws a CSP-blocked error (PR5 §3.4 fix). Same check on `/onboarding/connect` (script should run; consent-gate toggling should work end-to-end).
8. **Independent of PR5:** PR1 §5.0 COROS pre-deploy + PR3 §5.0 Polar pre-deploy + PR4 §5.0 Connections-tab spot-check are still owed if not yet completed.

### 5.1 PR6+ candidates — Andy's choice

**Pre-step reads (Rule #13 ordering, every candidate):**

1. **`aidstation-sources/CLAUDE.md` fully** — Rule #13 first re-read.
2. `aidstation-sources/handoffs/V5_Implementation_PR5_Closing_Handoff_v1.md` (this file).
3. `aidstation-sources/handoffs/V5_Implementation_PR4_Closing_Handoff_v1.md` (predecessor; carries the §5.1 candidate menu PR5 partially executed).
4. `aidstation-sources/Project_Backlog_v17.md` — still current; PR6 may need to bump to v18 (see §5.4).

The candidate menu carries forward from PR4 §5.1 with one slot filled (D1 = Step-2 connect screen shipped). Recommended next is D2 per PR4 §5.2 sequence; alternatives unchanged.

#### Option D2 — Per-field prefill UX + `KNOWN_PROFILE_FIELDS` registry (recommended next)

Carries forward from PR4 §5.1 unchanged. Now the highest-value follow-up because *both* onboarding paths (Step-2 connect → /profile?tab=athlete via PR5, and Account-Config-1 connect via PR4) currently flash a passive prompt that defers the actual prefill walkthrough to D2. Scope:

- `KNOWN_PROFILE_FIELDS` registry (Open Item #17 from PR3 §5.3) — the canonical list of profile fields eligible for provider prefill, keyed by `athlete_profile_field_provenance.field_name`.
- Per-field comparison UI: provider value vs. current stored value, with `[Use provider] [Keep current]` buttons. Per v5 §A.2.5 the prompt is per-field opt-in.
- Writes to `athlete_profile_field_provenance` table (D-58 schema; already shipped).
- Manual-override stickiness: once a field is `manual_override=true` (v5 §A.2.6), the prefill UX shows the override popover instead of the swap buttons.
- **Replace the `_POST_STEP2_TARGET` in `routes/onboarding.py`** from `/profile?tab=athlete` to whatever D2's prefill comparison page URL is. The hardcoded redirect is the single line that needs to change — easily greppable.

Probably 5+ files. Possibly splits into D2a (read-side: query provenance + render comparison cards) + D2b (write-side: opt-in form processor + manual-override clear path). At or over ceiling depending on split.

#### Option D3 — Locale-creation flow with Mapbox chain detection

Carries forward from PR4 §5.1 unchanged. Independent of D1/D2.

#### Option E — 14-day connect-provider nudge background job

Carries forward from PR1 §5.1 + PR3 §5.1 + PR4 §5.1 unchanged. Now even better-positioned: the nudge email/banner can deep-link athletes to `/onboarding/connect` (PR5 ships this URL) instead of `/profile?tab=connections` — onboarding context is a better match for "you skipped Step 2; come back."

#### Option F — Polar refresh-on-401

Carries forward unchanged. Watch item only.

#### Option G — `coros_ingest._ingest_activity` ON CONFLICT cleanup

Carries forward unchanged. ~30-line mechanical rewrite against PR3's `cardio_log_coros_label_uidx`. Opportunistic drop-in alongside D2 (different file area).

#### Option H — Provider blueprint roster expansion (Wahoo / Strava / Whoop / TrainingPeaks / Zwift / RWGPS)

Carries forward unchanged. Per-provider PR. Free upgrade from PR5: a one-tuple append to `CONNECTION_PROVIDERS` in `routes/profile.py` lights up the new provider on BOTH the Connections tab AND the onboarding Step-2 screen (one registry, two consumers).

### 5.2 Recommended sequence (revised post-PR5)

**D2 → E → D3**, with **G** as an opportunistic drop-in (free cleanup; could land alongside D2 because D2 doesn't touch `coros_ingest.py`); **F** as a watch item; **H** providers as opportunistic adds whenever an integration partner is ready.

D2 is now the natural next step. Both onboarding paths (PR4 management + PR5 Step 2) flash a "the prefill walkthrough ships next release" promise; D2 fulfills that promise. After D2 ships, E (the 14-day nudge) becomes the next-highest because the v5 §A.2.4 dormant-athlete signal is the missing piece for athletes who skip Step 2.

### 5.3 Standing items not on the critical path (carried from PR4 §5.3, updated)

- **D-52 Catalog Migration Phase 1** — unchanged. Independent.
- **D-54 SQLite collapse** — unchanged. Catalog Migration Phase 5.
- **D-55 Garmin onto `provider_auth`** — paused. Onboarding screen silently skips Garmin (not in `CONNECTION_PROVIDERS`); when Garmin reopens, the one-tuple append lights up both surfaces.
- **D-57 Research re-evaluation cadence design** — unchanged.
- **D-62 webhook_events retention prune** — still overdue. Two real webhook handlers (COROS + Polar) write to `webhook_events`. PR5 doesn't touch the webhook path at all.
- **Open Item #17 — `KNOWN_PROFILE_FIELDS` registry** — unchanged. Lands with Option D2 (now critical-path).
- **DATABASE.md update** — unchanged. PR5 didn't add schema, so the 8+ undocumented additions count holds.
- **PROVIDERS_SCHEMA.md update** — unchanged. Two real providers visible on TWO surfaces now (Connections tab + onboarding); "Phase 1+ planned" framing increasingly stale.
- **lat/lng precision** (carry-over) — unchanged.
- **Polar refresh-on-401** — Option F. Watch item.
- **`coros_ingest._ingest_activity` ON CONFLICT cleanup** — Option G. Cleanup candidate.
- **Provider-agnostic OAuth-start signature** (carry-over from PR4 §5.3) — `load_connections` builds `connect_url = url_for(endpoint, return_to=…)` assuming every provider's `oauth_start` accepts `?return_to=…`. COROS + Polar both do. When Wahoo / Strava / etc. land, they need to mirror this. Worth a docstring note in whatever provider-OAuth template (if any) emerges; not in PR5 scope.
- **Connect-from-onboarding-flow shape** (carry-over from PR4 §5.3) — PR5 EXECUTED the predicted shape: import `CONNECTION_PROVIDERS` + `load_connections` from `routes/profile.py`. Trade-off noted in PR4: "keep private to `routes/profile.py` to avoid premature abstraction; extract when D1's needs are concrete." D1 came along and the cleanest path was just to drop the leading underscore (private → public) without extracting. A third consumer (Account Config 3 acknowledgments? a dedicated provider-registry module?) would justify extraction. Item closes; new item below replaces it.
- **`_POST_STEP2_TARGET` hardcoded to `/profile?tab=athlete`** (new this PR) — single hardcoded redirect path in `routes/onboarding.py` that D2 will need to flip to the new prefill comparison page URL. Documented inline + in §5.1 D2 above. Easily greppable.
- **v17 backlog header cosmetic drift** (new this PR) — `Project_Backlog_v17.md` line 5 file-revision header narrative reads "🟢 PR1 + PR2 + PR3 shipped" (missing PR4). The D-50 row body is correct; only the header prose is stale. Not on the PR6 critical path; if v18 lands in PR6 (likely — see §5.4) the v18 file-revision header should read PR1 + PR2 + PR3 + PR4 + PR5 + PR6 and the v17 header drift becomes archived history.

### 5.4 Backlog row update (next PR's first action)

PR5 didn't bump v17 → v18 because no D-row state changed (D-50 still reads PR1+PR2+PR3+PR4 + frontend follow-on pending; PR5 is part of the "frontend follow-on" but doesn't yet close that bucket — D2 and onward remain). PR6 will need to bump to v18 if and only if it lands a state-changing event (e.g. D2 = prefill UX shipped, which closes the "full prefill UX" half of the frontend-follow-on bucket).

**For PR6, owed v17 → v18 bump (mechanically-applicable per Rule #11):**

1. Copy `aidstation-sources/Project_Backlog_v17.md` to `aidstation-sources/Project_Backlog_v18.md`.
2. **Replace** the file-revision header on line 5:
   - Old text:
     ```
     **File revision:** v17 — 2026-05-14 (D-50 row status flip catching up PR2 + PR3 + PR4: D-50 status cell now reads 🟢 PR1 + PR2 + PR3 shipped 2026-05-14 (commits `3628ca6`, `686bb40`, `b819f0a`); 🟡 frontend (Option B partial — Account Config 1 Connections tab shipped PR4; full prefill UX D2 + step-2 connect D1 still pending). PR3 added Polar OAuth + webhook + ingestion + three `cardio_log` partial-UNIQUE indexes per `V5_Implementation_PR3_Closing_Handoff_v1.md`. PR4 ships the COROS+Polar management screen as a Connections tab on `/profile` + `provider_auth.disconnect` helper + `?<provider>_connected=1` passive-prefill prompt, bundled with this v16→v17 bump per PR3 §5.4 mechanical instructions. No new D-row work this revision — pure status tracking)
     ```
   - New text (assuming PR6 = D2):
     ```
     **File revision:** v18 — 2026-05-14 (D-50 row status flip catching up PR5 + PR6: D-50 status cell now reads 🟢 PR1 + PR2 + PR3 + PR4 + PR5 + PR6 shipped 2026-05-14 (commits `3628ca6`, `686bb40`, `b819f0a`, `<PR4-merge-commit-f4d2e75>`, `<PR5-merge-commit>`, `<PR6-merge-commit>`); 🟢 frontend Option B full coverage (Account Config 1 management + Step-2 connect + per-field prefill walkthrough); 🟡 D3 locale-creation + E 14-day nudge + F refresh-on-401 + G ON CONFLICT cleanup + H more providers still pending. PR5 ships the v5 Step-2 onboarding connect screen per `V5_Implementation_PR5_Closing_Handoff_v1.md`. PR6 ships the per-field prefill UX + `KNOWN_PROFILE_FIELDS` registry closing Open Item #17 per `V5_Implementation_PR6_Closing_Handoff_v1.md`. No new D-row work this revision — pure status tracking)
     ```
3. **Prepend** to the predecessor revisions block (line 7-ish):
   ```
   - v17 — 2026-05-14 (D-50 row status flip catching up PR2 + PR3 + PR4: …)  [verbatim from current v17 line 5 narrative]
   ```
4. **Update** the D-50 row (search for `D-50 ` near the body of the table) status cell from:
   ```
   🟢 PR1 + PR2 + PR3 + PR4 shipped 2026-05-14 (commits `3628ca6`, `686bb40`, `b819f0a`, PR4-on-branch `claude/review-v5-pr3-handoff-PwMfn`); 🟡 frontend follow-on (D1 step-2 connect + D2 prefill UX + D3 locale-creation) pending
   ```
   to:
   ```
   🟢 PR1 + PR2 + PR3 + PR4 + PR5 + PR6 shipped 2026-05-14 (commits `3628ca6`, `686bb40`, `b819f0a`, `f4d2e75`, `<PR5-merge>`, `<PR6-merge>`); 🟢 frontend Option B full coverage (Account Config 1 management + Step-2 connect + per-field prefill walkthrough); 🟡 D3 locale-creation + E nudge + F refresh-on-401 + G cleanup + H more providers pending
   ```
5. **Bump** `aidstation-sources/CLAUDE.md` "Authoritative current files" backlog line from `Project_Backlog_v17.md` to `Project_Backlog_v18.md` (single-line edit, same shape as PR4 did v16→v17).

**If PR6 is something other than D2**, the narrative text changes but the file mechanics are identical (copy → header replace → predecessor prepend → D-50 row update → CLAUDE.md bump). Write the v18 header narrative to reflect what actually shipped.

The v17 header cosmetic drift (PR4 missing from the v17 header prose) gets archived when v17 moves to the predecessor block — no separate fix needed.

---

## 6. Open items / honest flags

- **No live page-render verification.** Same risk class as PR1 / PR2 / PR3 / PR4. Flask isn't installed in the sandbox, so `/onboarding/connect` can only be exercised at deploy time. AST-parse + Jinja-parse + stub-render with mocked `url_for` + `csrf_token` + `csp_nonce` confirmed all template variables wire and the consent-gate script attaches correctly. The PR5 §5.0 manual click-through is mandatory before this is real.
- **No `onboarded_at` flag column.** A future PR could add one if v2 needs strict "athlete completed Step 2" enforcement. For now `/onboarding/connect` is a screen anyone can visit; new-account signup redirects there once but isn't constrained to it.
- **Consent disclosure copy is draft.** v5 spec §A.1 calls the copy product/legal-owned. PR5 ships honest draft text (not `[PLACEHOLDER]`) so Andy has something concrete to refine. The four data classes named (activity, wellness, sleep, account profile) match what COROS + Polar actually read per the existing OAuth scope grants; the language is accurate. Pre-launch redline is owed by product/legal.
- **Per-provider scope acknowledgment recording is unchanged.** Spec §A.1 row "Per-provider OAuth scope acknowledgment" records via the existing `pa.record_oauth_scope_ack` helper (PR1) that's already called by both `routes/coros.py:209` and `routes/polar.py:241` in the OAuth callback path. PR5 doesn't add a new recording mechanism; the on-screen consent checkbox is the *disclosure* slot, not a second persistence path.
- **Disconnect button absent from onboarding screen.** Intentional. PR4's Connections tab has Disconnect; the onboarding Step-2 screen is for *connecting*, not managing. An athlete who connected and then changed their mind during onboarding can either (a) Skip / Continue and disconnect from the management tab, or (b) just not click Continue and close the browser — the redirect side-effects only fire on form submission. If this turns out to be confusing in practice, adding a Disconnect button to the connected-provider cards is a one-template-edit change.
- **Skip path doesn't record anything.** No `account_nudges` row, no `users.skipped_onboarding_at` column. The 14-day nudge keys off `provider_auth` rowcount + account age (per Option E spec). If a future PR needs "explicit skip vs unvisited page" telemetry, it adds the column then. Out of PR5 scope.
- **Tab-activation script CSP nonce drift fixed (PR4 carryover).** Drive-by one-line addition. Andy's PR4 manual check didn't catch this because (a) the failing path was the auto-tab-activation after OAuth redirect, not the manual click path, and (b) the manual click path uses Bootstrap's data-attribute-driven tab handler (bundled in a CSP-nonced script tag from `base.html`), which works regardless of the inline script. The fix is in PR5 because PR5 is the natural follow-on and the cost is one attribute. Flagged here so the PR5 §5.0 spot-check explicitly verifies it (step 7).
- **v17 backlog header cosmetic drift.** Flagged in §1 (Rule #9 reconciliation). Not fixed in PR5 because the right fix lands when PR6 bumps to v18 (the v17 header moves to the predecessor block where its drift becomes archived history). Not on the critical path.
- **Two POST endpoints differ only by intent.** `/onboarding/skip` and `/onboarding/continue` both redirect to `/profile?tab=athlete`. Today's only observable difference is the flash message on skip. Future analytics could read POST traffic; today, the two endpoints are functionally equivalent. The cost of merging them (a single `/onboarding/proceed?intent=skip|continue` endpoint with a query param) is roughly equal to the cost of keeping them separate, and the separation reads cleaner in route logs. Kept separate.
- **No tests added.** Inline `python3` execution of Jinja stub-render against three context variants is the closest this PR comes to test infrastructure. Same framing as PR1–PR4: a real `tests/` directory still doesn't exist; the right time to add one is whichever PR first hits a non-trivial integration test surface (probably D2 — the prefill UX is the first PR where unit tests against `athlete_profile_field_provenance` writes are clearly higher-value than offline inline exercises).
- **5 substantive code files + 1 drive-by + 1 handoff = 7 total counting everything.** Strictly the ceiling is 5 substantive; PR5 is 5 substantive + 1 trivial 1-attribute fix + 1 handoff. Same overage pattern PR1, PR3, PR4 ran. Cleaner alternative would be to defer the CSP drive-by to a separate PR (cost: more bookkeeping than the fix), or skip the handoff (cost: Rule #10/#11 noncompliance). Neither is better.

---

## 7. Gut check

**What this session got right.**

- **Reused PR4's `CONNECTION_PROVIDERS` + `load_connections` cleanly.** D1 was always going to need the same provider roster + status badge + connect-URL plumbing PR4 built; PR4 explicitly flagged this in its §5.3 ("Connect-from-onboarding-flow shape" item). PR5 executed the predicted shape: rename one private helper to public, add a `return_to` param, import. No new abstraction layer; no duplicated code.
- **Step 2 placement is a standalone screen, not a tab.** This is the *opposite* trade-off PR4 made (PR4 chose tab-on-/profile over standalone /account-config to stay at ceiling). PR5 went standalone because Step 2 is a *single-purpose, single-visit* surface — wrapping it in tab chrome would dilute the "connect, then move on" affordance and require a different layout pattern (no tabs to switch to). Different decisions for different contexts; both defensible.
- **Drive-by CSP fix.** Caught the missing nonce on PR4's tab-activation script during Rule #9 reconciliation, fixed it as a one-line addition. The kind of issue Rule #9 exists for — handoff narrative said "everything works"; on-disk state had a latent CSP issue Andy's manual click-through happened not to exercise.
- **Honest "draft copy" footer on the consent disclosure.** v5 spec §A.1 calls the wording product/legal-owned. PR5 doesn't pretend the copy is final; it doesn't hide behind `[PLACEHOLDER]` markers either. Andy gets something concrete to refine; the implementation cost is one footer line that gets removed pre-launch.

**Risks.**

- **Live page-render unexercised offline.** Same risk profile as every prior v5 implementation PR. Bootstrap 5 disabled-link behavior + the consent-gate script's interaction with the OAuth Connect link can only be verified in a real browser. The §5.0 spot-check is the protection.
- **The consent-gate is bypassable via direct URL.** An athlete (or an attacker) can navigate directly to `/coros/oauth/start?return_to=/onboarding/connect` without ever ticking the checkbox; the OAuth flow proceeds. The checkbox is a *disclosure-and-acknowledge* affordance, not a security gate. The actual consent recording fires in the OAuth callback via `pa.record_oauth_scope_ack` and would happen regardless of whether the checkbox was ticked. For a v1 app with a sole test athlete this is fine; for a launched product the disclosure copy can simply state the implicit consent ("Clicking Connect indicates you agree to the data sharing above"). Flagging for visibility.
- **Existing-athlete revisit weirdness.** Andy revisiting `/onboarding/connect` directly sees a screen titled "Step 2 — Connect providers" and an indicator showing Step 1 ✓ → Step 2 → Step 3. For a fresh signup this is accurate. For Andy (who passed through this screen weeks ago in the v1 onboarding flow that didn't exist) the framing is a little off. Cost of fixing (e.g. detecting that the user has any `provider_auth` rows or any age > N days and rendering a different header) is real; benefit is small (only Andy sees it; he knows what's going on). Deferred.
- **Continue redirect target is a placeholder.** `/profile?tab=athlete` is the v1 athlete tab, not the v5 §A entry surface. When D2 ships and the prefill comparison page exists, PR5's `_POST_STEP2_TARGET` is the single line that has to change. Flagged in §5.1 D2 and §5.3 as the carry-forward item.

**What might be missing.**

- **No "view what we'll pull" preview.** The consent disclosure names the four data classes; it doesn't show an athlete what specific *fields* will be prefilled (Body Weight from Polar, HRmax from COROS, etc.). That's D2's surface — and the v5 spec §A.2.5 prefill-prompt evaluation runs at the moment of *connect* (not before), so a pre-connect preview would require duplicating logic. Defer to D2.
- **No "I changed my mind" affordance on the consent gate.** Athletes can uncheck the consent box after ticking it (the script handles both directions), but they can't *undo* a connection from the onboarding screen — they have to go to Profile → Connections to disconnect. Flagged in §6.
- **Tab indicator hardcodes 3 steps.** v5 spec §Step sequence lists Steps 0–6 (Auth, §A.1 ack, Step 2 connect, Step 3 §A entry, Steps 4 §B–L, Step 5 Account Config, Step 6 Plan creation). PR5's indicator collapses everything past Step 3 because the rest of the flow doesn't exist yet. When D2+ land, the indicator should grow accordingly; doing it now would be aspirational chrome.
- **No back button to Step 1.** Step 1 (account creation acknowledgment) is a one-shot event at signup; there's no surface to "go back to" once you've created an account. The Step 1 ✓ badge is purely informational. If a future PR adds a profile-edit path for the §A.1 acknowledgment (e.g., re-acknowledge when copy changes), the indicator can become navigable.

**Best argument against this session's scope.**

PR5 chose D1 (Step-2 onboarding connect) over D2 (per-field prefill UX). The counter: D2 fulfills the explicit promise PR4 made ("the per-field prefill walkthrough ships in the next release"), which means PR4's success alert promise is now a *two-release* deferral instead of a *one-release* deferral. An athlete who connects via PR4's tab today gets a passive prompt about a release that's still in the future after PR5 lands.

Counter to the counter: the recommended sequence in PR4 §5.2 was explicitly D1 → E → D2 → D3 *because* PR5 D1's natural artifact (Step-2 screen) makes D2's prefill comparison page a more natural shape — D2 can render the prefill cards inside the onboarding flow shell PR5 just built, instead of as a standalone /profile sub-tab. Doing D2 first would have meant building the prefill UX in a context (post-connect tab landing) that gets repurposed when D1 lands, then refactoring. The order matters; the order chosen is the one PR4 explicitly recommended.

Alternatively, PR5 could have bundled the CSP nonce drive-by as its own PR. Counter: the one-line fix is closer to a typo correction than a feature; the bookkeeping cost of a separate PR (handoff doc, branch, commit, merge) is multiple orders of magnitude greater than the cost of the fix. Drive-by absorbed.

---

## 8. Forward pointers

- **Next session:** PR6 = Option D2 (per-field prefill UX, recommended) or any of the other PR4 §5.1 carry-forward candidates. PR5's `_POST_STEP2_TARGET` redirect is the single line D2 must flip.
- **Before next code lands:** PR5 §5.0 spot-check on the deployed app (Connect / Skip / Continue round-trip; CSP nonce verification on both /profile?tab=connections and /onboarding/connect inline scripts). PR1 §5.0 + PR3 §5.0 + PR4 §5.0 are still owed if not yet completed.
- **First action of next session:** Rule #9 reconciliation. Specifically: confirm PR5 commit landed on `claude/review-v5-connections-wKFIv` (or merged to main with its own merge commit); confirm `routes/onboarding.py` exists with three routes; confirm `routes/profile.py:load_connections` (no leading underscore) takes a `return_to` param; confirm `templates/onboarding/connect.html` exists with consent disclosure + consent-gate script; confirm `routes/auth.py:register` redirects to `onboarding.connect`; confirm `templates/profile/edit.html` script tag has `nonce="{{ csp_nonce() }}"`; confirm `Project_Backlog_v17.md` unchanged and `CLAUDE.md` still references v17.

**Rules in force, unchanged:**

- #9 session-start verification
- #10 session-end verification
- #11 mechanically-applicable deferred edits — **PR5 has one deferred mechanical edit:** the v17 → v18 backlog bump for PR6's first action, spec'd verbatim in §5.4
- #12 numeric version suffixes (backlog still at v17; v18 lands in PR6 per §5.4)
- #13 every closing handoff names CLAUDE.md as the first re-read — **applied: §5.1 forward-pointer reads CLAUDE.md as item 1.**

---

*End of V5 Implementation PR5 closing handoff. v5 onboarding Step 2 connect screen shipped at `/onboarding/connect`; reuses PR4's `CONNECTION_PROVIDERS` + `load_connections` (renamed from private to public); new-user post-register redirect points at it; drive-by CSP nonce fix on PR4's tab-activation script. Next: Andy's choice among PR6 candidates in §5.1 (D2 recommended); v17 → v18 backlog bump mechanically spec'd for PR6's first action.*
