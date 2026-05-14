# V5 Onboarding Implementation PR4 — Closing Handoff

**Session:** Fourth substantive code session of the v5 onboarding implementation arc. Executes PR3 §5.1 Option B (partial) — the Account Config 1 management screen for COROS + Polar — bundled with PR3 §5.4 mechanical instructions (v16→v17 backlog bump). The frontend-PR work begins; D1/D2/D3 (Step-2 connect, per-field prefill UX, locale-creation flow) remain out of scope.
**Date:** 2026-05-14
**Predecessor handoff:** `V5_Implementation_PR3_Closing_Handoff_v1.md` (its §5.1 Option B + §5.4 v17 bump are what this session executes).
**Branch:** `claude/review-v5-pr3-handoff-PwMfn` (new PR4 feature branch; PR3 was already merged to `main` via `b819f0a` before this session started).
**Status:** 🟡 Code shipped to feature branch; 🟡 push pending; 🟡 live `/profile?tab=connections` page-load + click-through verification owed at deploy time (no Flask in sandbox, same gap as PR1–PR3).
**Time-on-task:** Single chat. Substantive files: **5** (`Project_Backlog_v17.md` [new], `aidstation-sources/CLAUDE.md`, `routes/provider_auth.py`, `routes/profile.py`, `templates/profile/edit.html`). Plus this handoff (6 total — same one-over-ceiling pattern PR1 and PR3 hit).

---

## 1. Session-start verification (Rule #9)

Verified the PR3 handoff's claimed state before any new work.

| Claim | Anchor | Result |
|---|---|---|
| Branch `claude/review-v5-pr3-handoff-PwMfn` clean; PR3 merged to `main` as `b819f0a`; PR3 commit `ff4bd24` | `git status` + `git log --oneline -10` | ✅ Verified |
| All 5 PR3 files AST-parse clean (`init_db.py`, `routes/polar.py`, `routes/polar_ingest.py`, `routes/oauth_callbacks.py`, `app.py`) | `ast.parse` over each | ✅ Verified |
| `_PG_MIGRATIONS` totals 207 statements (PR3 added 3 partial-UNIQUE indexes on top of PR2's 204) | AST `len(value.elts)` | ✅ Verified |
| `_SQLITE_MIGRATIONS` totals 140 statements (unchanged from PR2) | AST count | ✅ Verified |
| 3 partial UNIQUE indexes landed in `_PG_MIGRATIONS` at lines 1927–1929 | region grep | ✅ Verified |
| `routes/oauth_callbacks.py` `_PROVIDERS` no longer contains `('polar',` (PR3 dropped it; replaced with a pointer comment to `/polar/oauth/callback`) | `grep "polar" routes/oauth_callbacks.py` | ✅ Verified |
| `app.py` has 5 polar wiring lines (import, register, comment, csrf.exempt, exempt-set entry) | grep | ✅ Verified |
| `routes/polar.py` + `routes/polar_ingest.py` exist with documented handler/exporter shape | grep + line numbers | ✅ Verified |
| `routes/provider_auth.py` last touched at PR1 commit `3628ca6` (unchanged across PR2 + PR3) | `git log routes/provider_auth.py` | ✅ Verified |
| `Project_Backlog_v16.md` D-50 row still reads `🟢 PR1 shipped … 🟡 follow-on PRs pending` — stale (PR2 + PR3 also shipped) | region grep | ✅ Verified (stale as predicted) |

No drift between PR3 handoff narrative and on-disk state. The owed v16→v17 backlog bump is real (D-50 status cell two PRs behind reality) and executes as this PR's first edit per PR3 §5.4 step 2.

The PR3 handoff's `<PR3-merge-commit>` placeholder gets filled with `b819f0a` (the merge commit `Merge pull request #35 from ahorn885/claude/review-v5-handoff-t7KBL`).

---

## 2. Files shipped this turn

All on branch `claude/review-v5-pr3-handoff-PwMfn`.

| # | File | Type | Notes |
|---|---|---|---|
| 1 | `aidstation-sources/Project_Backlog_v17.md` | New (copy of v16 + 2 surgical edits) | Per PR3 §5.4 mechanical instructions. **File revision** header bumped v16→v17 with full narrative: PR2 + PR3 + PR4 status flip. **Predecessor revisions** block prepends a v16 entry. **D-50 status cell** rewritten from `🟢 PR1 shipped 2026-05-14 (commit \`3628ca6\`); 🟡 follow-on PRs pending` to `🟢 PR1 + PR2 + PR3 + PR4 shipped 2026-05-14 (commits \`3628ca6\`, \`686bb40\`, \`b819f0a\`, PR4-on-branch \`claude/review-v5-pr3-handoff-PwMfn\`); 🟡 frontend follow-on (D1 step-2 connect + D2 prefill UX + D3 locale-creation) pending`. **Notes column** rewritten with the PR-by-PR breakdown of D-50 progress (PR1 helper + COROS, PR2 schema + chains, PR3 Polar + partial-UNIQUE, PR4 Connections tab) and the PR5+ candidate menu carrying forward from PR3 §5.1 (Option B partial + D1 + D2 + D3 + E + F + G; recommended sequence D1 → E → D2 → D3 with F + G as opportunistic drop-ins). |
| 2 | `aidstation-sources/CLAUDE.md` | Edit (1-line) | "Authoritative current files" line bumped `Project_Backlog_v16.md` → `Project_Backlog_v17.md`. Exactly the surgical edit PR3 §5.4 step 5 specified. |
| 3 | `routes/provider_auth.py` | Edit (+39 lines, new `disconnect` function) | New `disconnect(db, user_id, provider) -> bool`. UPDATE-only (not UPSERT) — sets `status=revoked` + nulls `access_token`, `refresh_token`, `session_blob`, `webhook_token`, `provider_user_id` + bumps `updated_at = NOW()`. Preserves `scopes` + `registered_at` (audit) and `token_expires_at` (informational; will be overwritten on re-connect). Returns True on row-updated, False on no-row (double-tap race or stale UI). Lives between `set_status` and `rotate_webhook_token` in the existing helper module — no other PR4 work touched `provider_auth.py`. |
| 4 | `routes/profile.py` | Edit (+~90 lines: new module-scope tables + helper + render plumbing + new route) | Six additions. (a) `import routes.provider_auth as pa`. (b) `CONNECTION_PROVIDERS` tuple — slug + label + connect-endpoint for COROS and Polar; rendering order = listing order. (c) `_STATUS_DISPLAY` dict mapping `pa.status` → (badge label, Bootstrap badge class) covering all 5 status values (active/revoked/error/pending_backfill/migrating) plus the no-row "Not connected" fallback. (d) `_load_connections(db, uid)` helper that fetches `provider_auth` rows for the user, joins them against `CONNECTION_PROVIDERS`, pre-computes display fields + `connect_url` (with URL-encoded `return_to=/profile?tab=connections`). (e) In the existing `edit()` GET render: load connections, read `?<slug>_connected=1` / `?<slug>_oauth_error` / `?<slug>_register_error` query flags into `just_connected_label` / `oauth_error_label` (the first hit wins; per-provider so multi-provider re-auth racing the same render is rare-enough-to-ignore), pass `active_tab` from `request.args.get('tab')` plus the new context dict entries to the template. (f) New `POST /profile/connections/<provider>/disconnect` handler — slug-whitelisted against `CONNECTION_PROVIDERS` (unknown 404), scoped on `current_user_id()`, calls `pa.disconnect`, flashes "<Label> disconnected." or "<Label> was already disconnected." depending on rowcount, redirects to `/profile?tab=connections`. CSRF on the disconnect form lands via the existing global Flask-WTF gate (no exempt). |
| 5 | `templates/profile/edit.html` | Edit (+~95 lines across 3 sites) | (a) New "Connections" tab button in the nav-tabs, inserted between "Athlete" and "Coach memory" with a `connection_count` badge (active connections only — uses `selectattr('is_connected')`). (b) New `<div id="tab-connections">` pane with: post-OAuth success alert (when `just_connected_label` is set — copy explicitly says the per-field prefill walkthrough lands in the next release; no fake buttons), OAuth error alert (when `oauth_error_label` is set), list-group of provider cards each rendering label / status badge / "Connected since YYYY-MM-DD" / scopes / last-activity timestamp / action buttons (Connect for not-connected, Re-authorise + Disconnect for connected), and a trailing "More providers ship as their OAuth blueprints come online; Garmin is paused" disclaimer. Disconnect form uses the existing `data-confirm` JS pattern. (c) Inline `<script>` at the bottom that activates the right tab based on (priority order): `active_tab` from the route handler → `?tab=…` URL param → `?<provider>_connected=1` / `?<provider>_oauth_error=…` / `?<provider>_register_error=1` (jinja-iterates `connections` so new providers slot in automatically). Uses `window.bootstrap.Tab.getOrCreateInstance` which exists on Bootstrap 5; if Bootstrap somehow isn't loaded the script no-ops silently. |
| — | `aidstation-sources/handoffs/V5_Implementation_PR4_Closing_Handoff_v1.md` | New (this file) | Session-end bookkeeping. |

**Files explicitly NOT touched:**

- `routes/coros.py` / `routes/polar.py` — **zero edits.** PR4 reuses both `oauth_start` endpoints unchanged; the connect buttons link to `coros.oauth_start` / `polar.oauth_start` with `?return_to=/profile?tab=connections` and rely on the existing same-origin guard in each handler (`if not return_to.startswith('/') or return_to.startswith('//'): return_to = '/'`).
- `routes/oauth_callbacks.py` — unchanged. Already updated by PR3.
- `app.py` — unchanged. The new disconnect route lives under the existing `profile` blueprint (already registered).
- `init_db.py` — unchanged. No new schema; `provider_auth` already has every column the Connections tab reads.
- `DATABASE.md` / `PROVIDERS_SCHEMA.md` — same "deferred to consolidated docs PR" framing PR1/PR2/PR3 used. Now 8 undocumented additions across PR1+PR2+PR3 plus zero schema-touches from PR4 — count unchanged.
- `templates/base.html` — unchanged. No nav-bar edits (Connections lives as a tab inside `/profile`, not a top-level nav entry). The user-experience trade-off was discussed mid-session; the at-ceiling Option A won over the standalone-screen Option B.

---

## 3. What landed

### 3.1 v16 → v17 backlog bump

Per PR3 §5.4 mechanical instructions. Three substantive edits to the v17 copy:

1. **File revision header** (line 5) — bumped v16 → v17 with a narrative that catches up PR2 + PR3 + PR4 in one rev. References the predecessor handoffs by filename so a future Rule #9 reconciliation can trace provenance.
2. **Predecessor revisions block** (line 7) — prepended a v16 entry preserving the v16 narrative verbatim.
3. **D-50 row** (line 92) — status cell + notes column rewritten to reflect PR1 + PR2 + PR3 + PR4 shipped, with PR-by-PR commit references and the PR5+ candidate menu carrying forward. The `<PR3-merge-commit>` placeholder PR3 §5.4 step 2 left blank now reads `b819f0a` (the actual `Merge pull request #35` commit on `main`).

**CLAUDE.md** "Authoritative current files" line bumped `Project_Backlog_v16.md` → `Project_Backlog_v17.md` per PR3 §5.4 step 5.

Bump-pattern lag closes: PR4 catches up the two-PR backlog gap PR3 left. Future PRs are back on the v1 cadence (one bump per substantive PR, executed at start of next session per Rule #11).

### 3.2 `provider_auth.disconnect` helper

```python
def disconnect(db, user_id, provider) -> bool:
    """UPDATE provider_auth SET status='revoked',
       access_token=NULL, refresh_token=NULL, session_blob=NULL,
       webhook_token=NULL, provider_user_id=NULL, updated_at=NOW()
       WHERE user_id=? AND provider=?"""
```

Three design choices worth flagging:

- **UPDATE-only, not UPSERT.** Disconnect on a non-existent row is a no-op (returns False); the caller can flash "already disconnected" instead of silently inserting a revoked row. Insert-shaped semantics would create empty `provider_auth` rows for athletes who clicked Disconnect without ever connecting, which is noise in the audit table.
- **Null `provider_user_id`.** Polar + COROS webhook handlers use `get_auth_by_provider_user_id` to map provider-side identifiers to local users; neither gates on `status`. Nulling the reverse-lookup column causes any in-flight webhook to land in the unmapped-event branch (audit row written with explanatory error, no ingest dispatch) without needing to thread a status check through every handler. The raw provider-side id is still preserved in `webhook_events.payload` if forensic recovery is ever needed.
- **Preserve `scopes` + `registered_at` + `token_expires_at`.** These are audit fields, not secrets. On re-connect the OAuth callback path overwrites them via `upsert_auth`. Keeping them across the revoked period lets the management screen render "Connected since YYYY-MM-DD" with the *original* registration date once the row is back to `active`.

**Unit-tested offline** against an in-memory SQLite (the `pa.disconnect` happy path, missing-row case, and idempotent re-disconnect on already-revoked row). The function itself is provider-agnostic; the next provider OAuth blueprint that lands inherits a working disconnect path automatically.

### 3.3 Account Config 1 — Connections tab on `/profile`

**Placement.** Tab on the existing `/profile` page, not a standalone `/account-config` blueprint. The v5 spec §Account Config 1 frames it as a logical screen, not a URL boundary; v1's existing flat-/profile pattern (Athlete / Coach memory / Account / API access) accommodates "Connections" as a fifth tab cleanly. A future v2 PR can extract a standalone `/account-config` area when the screen-set is fleshed out; for now this minimises the file-count cost (3 substantive code files instead of 7 if a new blueprint + template + nav-link route were added).

**Status badge mapping** (mirrors v5 §Account Config 1 "Connection Status" enum):

| `pa.status` | Display | Badge class |
|---|---|---|
| `active` | Connected | `bg-success` |
| `revoked` | Disconnected | `bg-secondary` |
| `error` | Auth error | `bg-danger` |
| `pending_backfill` | Setup in progress | `bg-warning text-dark` |
| `migrating` | Migrating | `bg-info text-dark` |
| (no row) | Not connected | `bg-light text-dark border` |

**Action button matrix:**

| Status | Buttons |
|---|---|
| `active` | Re-authorise (link → `<provider>.oauth_start?return_to=…`) + Disconnect (POST form → `pa.disconnect`) |
| Anything else (revoked / error / pending_backfill / migrating / no-row) | Connect (link → `<provider>.oauth_start?return_to=…`) |

Re-authorise on `pending_backfill` is intentional — it's the recovery path for "OAuth succeeded but `POST /v3/users` registration failed" that PR3's two-phase Polar flow can land in.

**Post-OAuth passive prompts.** The COROS + Polar OAuth callbacks redirect to `return_to?<slug>_connected=1` on success or `return_to?<slug>_oauth_error=…` / `return_to?<slug>_register_error=1` on failure. The Connections tab template renders:

- Success: `<alert class="alert-success">` with copy "{{ Label }} connected. We'll start pulling your activity, sleep, and heart-rate data on the next provider sync. The per-field prefill walkthrough (which {{ Label }} values to pull into your profile) ships in the next release." — explicitly defers the actual prefill UX to D2.
- Failure: `<alert class="alert-danger">` with copy "{{ Label }} did not connect. The OAuth handshake or partner-user registration failed. Try the Connect button again; if it keeps failing, the provider's auth surface may be down."

Both alerts have a `btn-close` link that drops back to `/profile?tab=connections` with the query params cleared, dismissing the alert.

**Tab-activation script.** Inline `<script>` at the bottom of `edit.html` reads (in priority order):

1. `active_tab` passed in from the route handler (set when `?tab=…` is in the request)
2. `?tab=…` URL param (handles deep links + the disconnect POST redirect)
3. `?<provider>_connected=1` / `?<provider>_oauth_error=…` / `?<provider>_register_error=1` (handles post-OAuth returns) — Jinja-iterates the `connections` list so a new provider in `CONNECTION_PROVIDERS` slots in automatically without a template edit.

If `requested` matches one of the tab ids, calls `window.bootstrap.Tab.getOrCreateInstance(target).show()`. Bootstrap 5's `getOrCreateInstance` API is the official path; the script no-ops silently if Bootstrap isn't loaded (which shouldn't happen — `base.html` loads it — but defensive).

**Adding providers** is now a one-line edit. Append a `(slug, 'Label', '<slug>.oauth_start')` tuple to `CONNECTION_PROVIDERS` in `routes/profile.py`; the helper, the template, and the tab-activation script all pick it up automatically. Pre-condition: the provider's OAuth blueprint must have an `oauth_start` endpoint that accepts `?return_to=…`. (COROS + Polar both do; the next provider added needs to mirror that shape, which it should anyway per PR1 §5.1 architectural consistency.)

---

## 4. Session-end verification (Rule #10)

Anchor checks against on-disk state before composing this handoff.

| Claim | Anchor | Result |
|---|---|---|
| All 3 changed code files AST-parse clean | `ast.parse` over each | ✅ Verified |
| `routes/provider_auth.py` exports new `disconnect(db, user_id, provider) -> bool` | `grep "^def disconnect"` | ✅ Verified (line 123) |
| `routes/profile.py` defines `CONNECTION_PROVIDERS`, `_load_connections`, new `disconnect_provider` route | `grep -n "CONNECTION_PROVIDERS\|_load_connections\|disconnect_provider"` | ✅ Verified (3 anchors) |
| `templates/profile/edit.html` adds `#tab-connections` pane + `just_connected_label` alert + `c.connect_url` link + `profile.disconnect_provider` form + tab-activation `<script>` | grep | ✅ Verified |
| Jinja template parses cleanly | `Environment.parse()` | ✅ Verified |
| Stub render covers happy path (one connected, one not-connected, just_connected_label set) without missing-variable errors | inline `jinja2.Environment.from_string(...).render(...)` with mocked `url_for` + `csrf_token` | ✅ Verified — 10 render anchors present including `id="tab-connections"`, `badge bg-success`, `Connected since 2026-05-14`, `Polar connected`, `/profile/connections/polar/disconnect`, `accesslink.read_all`, `Connect`, `Disconnect`, `Re-authorise` |
| Render variants: no-prompt (just_connected_label=None), oauth-error (oauth_error_label='COROS') | inline render | ✅ Verified — `Polar connected` absent in no-prompt variant; `COROS did not connect` present in error variant |
| `pa.disconnect` unit test against in-memory SQLite: status flips, all 5 credential columns null out, scopes/registered_at/token_expires_at preserved, missing-row returns False, idempotent re-disconnect returns True | inline `python3` | ✅ Verified (3 cases pass) |
| `Project_Backlog_v17.md` exists; v17 file revision header references PR4; D-50 status cell reads "🟢 PR1 + PR2 + PR3 + PR4 shipped" | `sed -n 5,7p` + grep | ✅ Verified |
| `aidstation-sources/CLAUDE.md` "Authoritative current files" backlog line reads v17 | grep | ✅ Verified |
| `Project_Backlog_v16.md` unchanged (Rule #12: prior versions retain as in-project history) | spot diff | ✅ Verified |
| `routes/provider_auth.py` still exports all PR1 helpers (upsert_auth, get_auth, get_auth_by_provider_user_id, set_status, rotate_webhook_token, record_oauth_scope_ack) — disconnect added without breaking existing surface | grep | ✅ Verified |

No drift between this handoff's narrative and on-disk state.

The same "can't exec the Flask app without Flask" gap PR1 §6 + PR2 §4 + PR3 §4 flagged applies: the live render of `/profile?tab=connections` (with real `provider_auth` rows + real session + Bootstrap 5 JS) can only be exercised at deploy time. AST + Jinja parse + stub-render + the unit test against `pa.disconnect` are the offline guards. The PR4 §5.0 live-check (open `/profile`, click Connect on each provider, complete OAuth, return, click Disconnect, confirm row updates) is mandatory before this PR is "real."

---

## 5. Mechanically-applicable instructions for next session (Rule #11)

### 5.0 Pre-deploy verification (must run before PR4 reaches production)

Lighter than PR3 §5.0 because PR4 ships no schema changes or new env vars. Just live-page verification.

1. **Open `/profile?tab=connections`** as a logged-in user. Confirm the Connections tab badge shows `0` (no provider_auth rows yet) and both COROS + Polar entries render with "Not connected" badge.
2. **Click Connect on COROS.** Confirm bounce to `/coros/oauth/start?return_to=%2Fprofile%3Ftab%3Dconnections`. Complete OAuth. Confirm redirect back to `/profile?tab=connections&coros_connected=1` with the Connections tab auto-activated (not Athlete) and the green "COROS connected." passive prompt visible.
3. **Confirm COROS card now shows "Connected since YYYY-MM-DD" + Re-authorise + Disconnect buttons.** Connection count badge bumps to `1`.
4. **Click Disconnect on COROS.** Confirm POST to `/profile/connections/coros/disconnect` → redirect back to `/profile?tab=connections` with "COROS disconnected." flash. Card status flips to "Disconnected" + Connect button. Re-click Disconnect should not be reachable (button gone); manual POST should flash "COROS was already disconnected."
5. **Spot-check `provider_auth` on Neon:**
   ```sql
   SELECT user_id, provider, status,
          access_token IS NULL AS tok_null,
          refresh_token IS NULL AS ref_null,
          provider_user_id IS NULL AS pui_null,
          scopes, registered_at, token_expires_at, updated_at
     FROM provider_auth WHERE user_id = <andy_id>;
   ```
   After disconnect: `status='revoked'`, `tok_null=t`, `ref_null=t`, `pui_null=t`, `scopes`/`registered_at`/`token_expires_at` preserved, `updated_at` bumped.
6. **Repeat for Polar.** Same flow, but Polar's two-phase OAuth means the success case lands `status='active'` only after the `POST /v3/users` registration call succeeds. If the partner-user registration is rejected, expect `polar_register_error=1` on the redirect and a red alert.
7. **Independent of PR4:** PR1 §5.0 COROS pre-deploy verification + PR3 §5.0 Polar pre-deploy verification (env vars, redirect_uri, webhook URL registration, Neon spot-check of the partial-UNIQUE indexes) are still owed if not yet completed.

### 5.1 PR5+ candidates — Andy's choice

**Pre-step reads (Rule #13 ordering, every candidate):**

1. **`aidstation-sources/CLAUDE.md` fully** — Rule #13 first re-read.
2. `aidstation-sources/handoffs/V5_Implementation_PR4_Closing_Handoff_v1.md` (this file).
3. `aidstation-sources/handoffs/V5_Implementation_PR3_Closing_Handoff_v1.md` (predecessor; carries the §5.1 candidate menu PR4 partially executed).
4. `aidstation-sources/Project_Backlog_v17.md` — D-50 row now current; first Rule #9 anchor for the next session.

The candidate menu carries forward from PR3 §5.1 with one slot partially filled (Option B partial = Connections tab shipped; full re-onboarding UX = D2 still owed) and the recommended sequence updated.

#### Option D1 — v5 frontend onboarding flow Step 2 connect (recommended next)

Now substantially more valuable than after PR3: Connections tab exists, so D1 can reuse the same `_load_connections` + status-badge + connect-button rendering on the Step-2 connect screen. Scope:

- New onboarding-flow template (or extension to whatever onboarding routes already exist; verify before designing).
- Step-2 connect screen lists the same providers, renders the same status badges, and includes the v5 §A.1 Connected Service consent disclosure firing before the Connect button is enabled.
- Skip-for-now path that records nothing and lets the athlete proceed to §A manual entry.
- `?<provider>_connected=1` callback handling that, after connect, lands the athlete *in the onboarding flow* not on `/profile`.

The Connect-button + `return_to` plumbing is already proven by PR4; the new work is the onboarding-flow shell and the consent-disclosure gate. Likely 4–5 files (template + route + possibly a new blueprint + handoff). At ceiling.

#### Option D2 — Per-field prefill UX + `KNOWN_PROFILE_FIELDS` registry

The actual "Use COROS values" / "Keep current" walkthrough that PR4's passive prompt promised "ships in the next release." Scope:

- `KNOWN_PROFILE_FIELDS` registry (Open Item #17 from PR3 §5.3) — the canonical list of profile fields eligible for provider prefill, keyed by `athlete_profile_field_provenance.field_name`.
- Per-field comparison UI: provider value vs. current stored value, with `[Use provider] [Keep current]` buttons. Per v5 §A.2.5 the prompt is per-field opt-in.
- Writes to `athlete_profile_field_provenance` table (D-58 schema; already shipped).
- Manual-override stickiness: once a field is `manual_override=true` (v5 §A.2.6), the prefill UX shows the override popover instead of the swap buttons.

Probably 5+ files. Possibly splits into D2a (read-side: query provenance + render comparison cards) + D2b (write-side: opt-in form processor + manual-override clear path). At or over ceiling depending on split.

#### Option D3 — Locale-creation flow with Mapbox chain detection

Carries forward from PR3 §5.1 unchanged. Independent of D1/D2 — locale management is a separate v5 §J area.

#### Option E — 14-day connect-provider nudge background job

Carries forward from PR1 §5.1 + PR3 §5.1 unchanged. Small standalone. After PR4 the Connections tab exists, so the nudge email can deep-link athletes directly to `/profile?tab=connections` instead of needing its own landing page.

#### Option F — Polar refresh-on-401

Carries forward from PR3 §5.1 unchanged. Watch item only.

#### Option G — `coros_ingest._ingest_activity` ON CONFLICT cleanup

Carries forward from PR3 §5.1 unchanged. ~30-line mechanical rewrite against the `cardio_log_coros_label_uidx` PR3 shipped.

#### Option H (new) — Provider blueprint roster expansion to Wahoo / Strava / Whoop / TrainingPeaks / Zwift / RWGPS

Same shape as PR1 (COROS) + PR3 (Polar) per the provider-agnostic helper claim that PR3 confirmed. Each new provider is roughly: new `routes/<provider>.py` (OAuth start + callback + webhook) + new `routes/<provider>_ingest.py` + `app.py` wiring + one-tuple-append to `CONNECTION_PROVIDERS` in `routes/profile.py` (free upgrade — PR4 set this up). Each provider is a separate PR (probably PR-shaped). Per Integration v4 §3 the priority order is Wahoo → Strava → Whoop → TrainingPeaks → Zwift → RWGPS-OAuth-upgrade.

### 5.2 Recommended sequence (revised post-PR4)

**D1 → E → D2 → D3**, with **G** as an opportunistic drop-in (free cleanup; could land alongside D1 because D1 doesn't touch `coros_ingest.py`); **F** as a watch item; **H** providers as opportunistic adds whenever an integration partner is ready.

D1 is the natural next step because PR4 just shipped the post-onboarding management screen; the natural pair is the *during-onboarding* connect surface. Once D1 ships, D2 (prefill UX) becomes the highest-value follow-up because both onboarding paths (Step-2 connect + Account-Config-1 connect) currently flash a passive prompt that defers to D2.

### 5.3 Standing items not on the critical path (carried from PR3 §5.3, updated)

- **D-52 Catalog Migration Phase 1** — unchanged. Independent.
- **D-54 SQLite collapse** — unchanged. Catalog Migration Phase 5.
- **D-55 Garmin onto `provider_auth`** — paused. The Connections tab silently skips Garmin (it's not in `CONNECTION_PROVIDERS`); when Garmin reopens, append one tuple to the list and the management surface lights up.
- **D-57 Research re-evaluation cadence design** — unchanged.
- **D-62 webhook_events retention prune** — still overdue. Two real webhook handlers (COROS + Polar) now write to `webhook_events`. The Connections tab disconnect path is unrelated (it doesn't touch `webhook_events`), but every Disconnect-then-Connect-then-Webhook race writes audit rows that accumulate.
- **Open Item #17 — `KNOWN_PROFILE_FIELDS` registry** — unchanged. Lands with Option D2.
- **DATABASE.md update** — unchanged. PR4 didn't add schema, so the 8+ undocumented additions count holds.
- **PROVIDERS_SCHEMA.md update** — unchanged. Two real providers visible on a management screen now; "Phase 1+ planned" framing increasingly stale.
- **lat/lng precision** (carry-over) — unchanged.
- **Polar refresh-on-401** — Option F. Watch item.
- **`coros_ingest._ingest_activity` ON CONFLICT cleanup** — Option G. Cleanup candidate.
- **Provider-agnostic OAuth-start signature** (new this session) — `_load_connections` builds `connect_url = url_for(endpoint, return_to=…)` assuming every provider's `oauth_start` accepts `?return_to=…`. COROS + Polar both do. When Wahoo / Strava / etc. land, they need to mirror this. Worth a docstring note in whatever provider-OAuth template (if any) emerges; not in PR4 scope.
- **Connect-from-onboarding-flow shape** (new this session) — D1 will need its own connect surface that reuses `_load_connections` from `routes/profile.py` or extracts it to a shared `routes/provider_auth.py` helper. PR4 deliberately kept it private to `routes/profile.py` to avoid premature abstraction; extract when D1's needs are concrete.

### 5.4 Backlog row update (this PR)

Already executed in v17. No deferred edits owed.

---

## 6. Open items / honest flags

- **No live page-render verification.** Same risk class as PR1 / PR2 / PR3. Flask isn't installed in the sandbox, so the `/profile?tab=connections` page can only be exercised at deploy time. AST-parse + Jinja-parse + stub-render with mocked `url_for` + `csrf_token` confirmed all template variables wire and the disconnect-form action URL renders correctly. The PR4 §5.0 manual click-through is mandatory before this is real.
- **Tab placement on /profile is a UX decision Andy approved mid-session over the spec's framing.** v5 §Account Config 1 frames it as a separate screen; PR4 ships it as a tab on the existing /profile page to stay at the 5-file ceiling. The trade-off + the path to extracting it later (when v2 fleshes out the Account Config screen-set) was discussed in chat and is documented in §8 "Best argument against." A future PR that lifts it into a standalone `/account-config` blueprint can do so without breaking PR4's URL surface — the `/profile/connections/<provider>/disconnect` POST endpoint can be moved or aliased.
- **`pa.disconnect` nulls `provider_user_id`.** Trade-off: the rebound row's "Connected since" date will show the *original* `registered_at` (preserved on disconnect) but the `provider_user_id` will be the *new* one from the re-OAuth handshake. Consistent with the spec's "one record per integrated third-party service" framing (same row, same identity). If a future maintenance flow needs the *previous* `provider_user_id` for forensic recovery, it's in `webhook_events.payload` for any webhook that fired during the connected window.
- **Disconnect doesn't notify the provider.** PR4 only flips local state; the OAuth grant on COROS / Polar's side stays alive until it naturally expires or until the athlete revokes it from the provider's app. v1 limitation — no athlete will notice (Andy is the only test athlete). Per v5 spec a future "revoke at provider" flow would land in §Account Config 1 alongside disconnect; PR4 explicitly scoped to local revocation only.
- **The "just-connected" passive prompt defers to D2.** Honest copy: "The per-field prefill walkthrough ships in the next release." If D2 slips, the prompt stays as-is — informational, not deceptive. The alternative (no prompt at all) would lose the signal that something happened on connect; the alternative (a fake [Use values] [Keep] button that no-ops) would be worse.
- **Tab-activation script runs at script-tag eval time, not on DOMContentLoaded.** Bootstrap 5's `getOrCreateInstance` can be called before `DOMContentLoaded` as long as the target element is already in the DOM (which it is — the script is at the bottom). If a future template re-org moves the script higher, it'd need a DOMContentLoaded wrapper.
- **CSRF on the disconnect form lands via Flask-WTF's global gate.** No exempt — the form-token is included via `{{ csrf_token() }}`. Race: if the form is loaded long before submission and the user's session rotates, the disconnect POST would fail with a CSRF error and the user would see Flask-WTF's default error page. Acceptable for v1; the same race exists on every other POST form on `/profile`.
- **No new env vars; no new schema; no new partner-API calls.** PR4 is the cheapest substantive PR in the v5 implementation arc so far. The deploy-time risk surface is the smallest of any PR in the arc.
- **5 substantive files counting the v17 bump + CLAUDE.md edit; 6 total counting handoff.** Same one-over pattern PR1 + PR3 hit. PR2 was on-ceiling (4 substantive). The Option B partial scope (just the Connections-tab management screen, deferring the per-field prefill UX) is genuinely the smallest the work decomposes to that ships a usable surface — landing just the disconnect helper without the screen, or just the screen without the disconnect helper, would each be lower-value than the combined PR.
- **No tests added.** Inline `python3` execution of `pa.disconnect` against in-memory SQLite + Jinja stub-render are the closest this PR comes to test infrastructure. Same framing as PR1/PR2/PR3: a real `tests/` directory still doesn't exist; the right time to add one is whichever PR first hits a non-trivial integration test surface (probably D2 — the prefill UX is the first PR where unit tests against `athlete_profile_field_provenance` writes are clearly higher-value than offline inline exercises).

---

## 7. Gut check

**What this session got right.**

- **v17 bump executed with the predecessor's spec'd edits.** PR3 §5.4 left mechanical instructions (copy v16 → v17; replace specific text in two places; bump CLAUDE.md line); PR4 ran exactly those edits with the actual merge-commit hash filled in. The Rule #11 chain (PR3 specs the edit, PR4 executes it) worked as designed.
- **`provider_auth.py` extension stayed minimal.** One new function, 39 lines, no other helper touched. The "this helper is provider-agnostic" claim that PR3 confirmed continues to hold — disconnect is provider-agnostic by construction (it takes the slug as a parameter).
- **Connections tab `CONNECTION_PROVIDERS` registry is the right abstraction shape for D1 and Option H.** Adding the next provider is a single tuple append; the template, the route handler, the badge mapping, and the tab-activation script all pick it up automatically. PR4 spent the keystrokes to set this up because Option H (six more providers) is on the horizon; the abstraction earns its keep on the first re-use.
- **Honest deferral of the prefill UX.** PR4's "just-connected" prompt explicitly says the per-field walkthrough lands in D2. No fake buttons; no dead UI. The signal that "connect succeeded; we're working on the next thing" lands; the implementation cost is one Bootstrap alert.
- **Tab-vs-standalone-screen decision was surfaced as a real architectural fork before any code.** Stop-and-ask trigger #8 fired (architectural alternatives with real tradeoffs); Andy chose tab-on-/profile after the UX consequence was explained in plain language. The decision is documented in §8 and can be reversed cheaply later.

**Risks.**

- **Live page-render is unexercised offline.** Same risk profile as every prior v5 implementation PR. The stub-render covers Jinja variable wiring but not Bootstrap 5 tab behavior, not real browser CSP rules, not real form-POST CSRF round-trip. The §5.0 spot-check is the protection.
- **Disconnect-then-immediate-Connect race.** If athlete clicks Disconnect on COROS, then the COROS OAuth callback handler races to write the new `access_token` (somehow — they'd have to have a stale OAuth flow in progress), the UPSERT in `coros.oauth_callback` would resurrect the row with the new token. That's actually correct behavior (the new connect should overwrite the revoked row); flagging only because it's a non-obvious interaction.
- **Tab-activation script no-ops if Bootstrap doesn't load.** Defensive feature-detect (`window.bootstrap && window.bootstrap.Tab`), but a CSP or CDN failure would surface as "Connections tab is visible but never activates from the URL." Athletes can still click the tab manually. Low-probability; documented in §6.
- **Connections badge counts only `is_connected`** (i.e., `status='active'`). If Polar's two-phase flow lands at `status='pending_backfill'`, the badge stays at `0` until the registration call succeeds and the status flips. Could surface confusion ("I just connected, why does the badge say 0?"). The success alert ("{{ Label }} connected") fires only on the actual `?<slug>_connected=1` callback param though — which the OAuth callback only writes on the success path — so the user-visible signal is consistent.

**What might be missing.**

- **No "revoke at provider" call.** PR4 only updates local state. A future PR could call Polar's `DELETE /v3/users` or COROS's equivalent. Defer until v2 — Andy is sole user and won't notice.
- **No re-onboarding prompt yet** (deferred to D2). The passive prompt acknowledges this; the next PR's first action is the per-field comparison UX.
- **No deep-link to the disconnect-confirm UX.** Disconnect is a single click + JS `data-confirm` dialog. If Andy wants a per-disconnect explanation page ("Here's what happens when you disconnect: …") that's a v2 UX polish item, not PR4 scope.
- **Connections tab doesn't show last successful sync time.** Renders `updated_at` as "Last activity" — but `updated_at` bumps on every webhook delivery, not just successful syncs. A future PR that wires per-provider "last successful sync" tracking (probably via a `last_sync_at` column on `provider_auth`, or a query into `webhook_events` for the latest `processed_at IS NOT NULL` row) would surface a more useful signal. Not in PR4 scope.

**Best argument against this session's scope.**

PR4 chose Option B partial (Connections management tab) over Option D1 (Step-2 onboarding connect). The counter: D1 is the more user-visible win because it touches the actual onboarding flow that v5 reframes; Account Config 1 management is a *post-onboarding* surface that only matters once an athlete has already been through the flow. PR4 ships management first, before onboarding-time connect even works in v5's reframed flow.

Counter to the counter: D1 needs the post-OAuth callback to render some UI surface that confirms "you just connected." Without PR4's tab, that UI surface doesn't exist (the `?<slug>_connected=1` flag would be dropped on the floor or pasted into a temporary onboarding-flow shim). PR4 builds the connect-result surface that D1 will reuse. The connect-button + return-URL plumbing PR4 ships also unblocks D1 — same code path, just rendered inside the onboarding flow shell.

Alternatively, PR4 could have skipped the v17 backlog bump entirely (deferring it again as PR1 / PR2 / PR3 did). Counter: the bump-pattern lag was already two PRs deep; deferring a third time would push v17 to PR5 with a three-PR catchup, and the §5.4 mechanical instructions PR3 left would need to be rewritten with three commit hashes instead of one. The marginal cost of executing the bump *now* (one new file copy + two small edits) was well under the marginal cost of recompositing the deferred-bump spec a third time.

---

## 8. Forward pointers

- **Next session:** PR5 = Option D1 (Step-2 onboarding connect screen, recommended) or any of the other PR3 §5.1 carry-forward candidates. The §5.4 backlog-bump-deferred owed item *does not exist* — v17 is current, future PRs catch up one-at-a-time per Rule #11.
- **Before next code lands:** PR4 §5.0 spot-check on the deployed app (Connect / Disconnect / Re-authorise round-trip for COROS + Polar; verify provider_auth row state on Neon). PR1 §5.0 COROS pre-deploy + PR3 §5.0 Polar pre-deploy are still owed if not yet completed.
- **First action of next session:** Rule #9 reconciliation. Specifically: confirm PR4 commit landed on `claude/review-v5-pr3-handoff-PwMfn` (or merged to main with its own merge commit); confirm `routes/provider_auth.py` exports `disconnect`; confirm `CONNECTION_PROVIDERS` + `_load_connections` + `disconnect_provider` route exist in `routes/profile.py`; confirm `templates/profile/edit.html` has `#tab-connections` pane; confirm `Project_Backlog_v17.md` exists and D-50 row reflects PR1+PR2+PR3+PR4; confirm `CLAUDE.md` references v17.

**Rules in force, unchanged:**

- #9 session-start verification
- #10 session-end verification
- #11 mechanically-applicable deferred edits — **PR4 has no deferred mechanical edits**; v17 bump catchup is complete
- #12 numeric version suffixes (backlog now at v17; v16 retained as in-project history)
- #13 every closing handoff names CLAUDE.md as the first re-read — **applied: §5.1 forward-pointer reads CLAUDE.md as item 1.**

---

*End of V5 Implementation PR4 closing handoff. Account Config 1 management screen shipped as a Connections tab on `/profile`; `provider_auth.disconnect` helper proven against in-memory SQLite; v16 → v17 backlog catchup executed against PR3 §5.4's mechanical spec. Next: Andy's choice among PR5 candidates in §5.1 (D1 recommended); no v17 bump deferred — back on the one-PR-per-bump cadence.*
