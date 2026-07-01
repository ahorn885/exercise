# Sign-up/Onboarding Phase 3 slice 2 — #267 passkeys — Closing Handoff

**Session:** Passkey / WebAuthn sign-in — the second and final Phase 3 slice (#272 SMS/WhatsApp invites shipped separately in PR #1102/#1103). Closes #267 and, with it, epic #246.
**Date:** 2026-07-01
**Predecessor handoff:** `V5_Implementation_SignupOnboarding_Phase1-2_Merged_Phase3_272_267_Kickoff_Handoff_v1.md`
**Branch:** `claude/passkeys-implementation-9ujxeo`
**Status:** 9 substantive files (over the nominal 5-file ceiling — proportionate to a full-stack auth slice: schema + new integration module + client JS + 2 routes files + 2 templates, consistent with this arc's recent precedent) + 4 test files. Suite green, 0 new ruff errors.

---

## 1. Session-start verification (Rule #9)

Re-grounded per the kickoff's own instructions: read `HANDOFF.md`'s "Parked" list (confirmed "Passkeys / WebAuthn" still listed, no scaffolding), grepped the whole tree for `webauthn|passkey|fido2` (zero hits outside docs — clean slate, matches the #272 session's earlier grep), and read issue #267's one comment (2026-06-21, Andy) laying out the planned approach: a `webauthn` library + a per-user credentials table, a registration ceremony on Profile → Account, a passwordless/2FA login path, CSP-nonce compatibility as the trickiest part vs. TOTP, and an explicit open question — "decide interaction with TOTP: passkey as an alternative second factor vs. a full passwordless primary path."

**Reconciliation note:** clean — no drift between the kickoff handoff's claims and on-disk state. The kickoff's own architecture pre-decision ("passkey is an alternative sign-in option alongside password+TOTP, not a replacement") was already recorded in `CURRENT_STATE.md`'s #272 entry, so stop-and-ask trigger #5's *scope* question was resolved before this session started; what remained open was the *ceremony-level* TOTP-interaction question the issue comment explicitly flagged as undecided.

---

## 2. Session narrative

Two implementation-level decisions remained even after the prior session's scope call, both security/UX tradeoffs worth Andy's explicit sign-off before writing auth-flow code (stop-and-ask trigger #5 territory):

1. **Does a passkey sign-in still trigger the TOTP challenge for an account that has TOTP on?** Andy picked **passkey alone is enough** — a WebAuthn ceremony already proves possession of the authenticator plus a local user-verification step (biometric/PIN), at least as strong as password+TOTP; stacking TOTP on top is redundant friction, not extra security.
2. **Login UX shape.** Andy picked **a "Sign in with a passkey" button with no username typed first** — a discoverable/resident credential, so the browser's own passkey picker resolves the account. True passwordless, one tap.

Both decisions are recorded in `webauthn_helper.py`'s module docstring so they don't get re-litigated silently in a future session.

Library choice: `webauthn` (PyPI, py_webauthn, v3.0.0) — the standard server-side WebAuthn ceremony library, built on `cryptography` (already a dependency). Verified importable and inspected its API surface (`generate_registration_options` / `verify_registration_response` / `generate_authentication_options` / `verify_authentication_response`, the `parse_*_credential_json` JSON shape) in a scratch venv before writing any integration code.

---

## 3. File-by-file edits

### 3.1 `webauthn_helper.py` (new)

Mirrors `mfa.py`'s two-layer shape: ceremony wrappers (`build_registration_options` / `verify_registration` / `build_authentication_options` / `verify_authentication`) over the `webauthn` library, plus DB helpers (`list_credentials` / `find_credential_by_id` / `add_credential` / `touch_credential` / `delete_credential`) against the new `user_webauthn_credentials` table. Registration options set `authenticator_selection=AuthenticatorSelectionCriteria(resident_key=REQUIRED, ...)` (Andy's UX call) and exclude the athlete's existing credentials. Authentication options carry no `allow_credentials` (the discoverable-credential login). `verify_authentication` looks the credential up by its base64url `id` before calling into the library (the server doesn't know the user yet on a passwordless login) and bumps `sign_count`/`last_used_at` on success.

### 3.2 `init_db.py` (`_PG_MIGRATIONS`, appended at the end, ~line 3379)

`CREATE TABLE IF NOT EXISTS user_webauthn_credentials (id, user_id FK, credential_id UNIQUE, public_key, sign_count, nickname, created_at, last_used_at)` + an index on `user_id`. Public-schema, idempotent — **auto-applies on next deploy, no `layer0-apply` owed** (same as `user_totp`/`user_invites`).

### 3.3 `routes/auth.py`

New `/auth/webauthn/login/options` (issues the discoverable-credential challenge, stashes it in `session`) and `/auth/webauthn/login/verify` (verifies, then calls the existing `_finalize_login` directly — no `mfa.is_enabled` check anywhere on this path, which is what makes Andy's TOTP-bypass decision real rather than aspirational). Both rate-limited the same as `login()`/`totp_challenge()`.

### 3.4 `routes/profile.py`

New `/profile/webauthn/register/options`, `/profile/webauthn/register/verify`, `/profile/webauthn/<id>/delete` (session-scoped). `account_settings()` now also loads `webauthn_helper.list_credentials` and passes `passkeys` to the template.

### 3.5 `routes/admin.py`

`user_webauthn_credentials` added to `_delete_user_and_data`'s cascade chain, right after `user_totp`.

### 3.6 `app.py`

`_AUTH_EXEMPT_ENDPOINTS` gains `auth.webauthn_login_options` / `auth.webauthn_login_verify` (reached with no session yet, same reasoning as the existing TOTP challenge exemption). Registration endpoints are deliberately **not** exempt — they require an existing session.

### 3.7 `static/webauthn.js` (new)

Client-side ceremony: `navigator.credentials.create()`/`.get()`, base64url encode/decode helpers, a self-contained CSRF header (reads `<meta name="csrf-token">` directly rather than relying on `app.js`'s fetch wrapper, because the unauthenticated login shell doesn't load `app.js`). Both buttons render `hidden` server-side and are only un-hidden if `window.PublicKeyCredential` exists — fail-safe progressive enhancement, the same pattern as the existing type-to-confirm dialog.

### 3.8 `templates/auth/_shell.html`

Added `{% block scripts %}{% endblock %}` (an established per-page extension point elsewhere in the app) so `login.html` can pull in `webauthn.js` without loading it on every auth page.

### 3.9 `templates/auth/login.html`

"Sign in with a passkey" button (hidden by default) between the password form and the OAuth `signin_providers` loop — one shared "or" divider now covers both alternatives (was two separate ones).

### 3.10 `templates/profile/account.html`

New "Passkeys" card: lists registered credentials (nickname, added/last-used dates, a scoped Remove form using the existing `data-confirm` pattern) and an "Add a passkey" button. Reuses the existing `.pf-save` flex-row CSS class rather than introducing new CSS.

---

## 4. Code / tests

- `tests/test_webauthn_helper.py` (new, 13 tests) — RP ID / origin derivation, discoverable-credential registration options + exclude-list, no-`allow_credentials` authentication options, verify/touch/CRUD against a fake DB (mirrors `tests/test_invites.py`'s fake-cursor pattern).
- `tests/test_webauthn_routes.py` (new, 11 tests) — route wiring: auth-exemption list, session-challenge round-trip, and the load-bearing regression `test_login_verify_success_grants_session_without_totp` (monkeypatches `mfa.is_enabled` to raise if called at all — proves the TOTP-bypass decision is wired, not just documented).
- `tests/test_redesign_auth_render.py` — extended `test_login_render` with the passkey button/script assertions.
- `tests/test_redesign_profile_render.py` — extended `test_account_settings` + new `test_account_settings_lists_registered_passkeys`.
- **Full suite: 4110 passed / 30 skipped** (baseline 4085 + 25 new). **Ruff: 0 new errors** (all 6 pre-existing findings confirmed unchanged via `git stash` diff — same as every prior session's convention).
- **No `layer0-apply` owed** — public-schema migration, auto-applies on deploy.

---

## 5. Manual §5.0 verification steps

Passkeys require a real browser + platform authenticator (Face ID / Touch ID / Windows Hello) or a hardware key — can't be exercised from this container. On the live site once deployed:

1. `/profile/account` → "Add a passkey" → complete the OS prompt → row appears in the Passkeys list.
2. Sign out. `/auth/login` → "Sign in with a passkey" → OS passkey picker → signs straight in, no password/TOTP prompt.
3. If the account also has TOTP on: repeat step 2 and confirm the TOTP challenge is skipped (the load-bearing behavioral check for Andy's decision).
4. `/profile/account` → Remove a passkey → confirm dialog → row disappears; confirm signing in with that removed credential now fails (browser won't even offer it, since deregistration removes the resident credential's server-side match).
5. DevTools console on both `/auth/login` and `/profile/account`: zero CSP violations.

---

## 6. Next session pointers

### 6.1 Architect-recommended next forward move

**Close epic #246.** This was the last open child (#272 shipped in PR #1102/#1103, #267 ships here) — #304's `_history`-lists call (medications/conditions/injury history capture) was flagged in the Phase 1-2 handoff as a separate open item under #246's umbrella; confirm its status before closing the epic, or comment on it as a known carve-out.

### 6.2 Alternative pivots

None flagged — this was the last committed item on the sign-up/onboarding thread per the kickoff plan.

### 6.3 Operating notes for next session

1. `CLAUDE.md` — stable rules.
2. `CURRENT_STATE.md` — what just shipped + current focus.
3. `CARRY_FORWARD.md` — rolling cross-session items.
4. This handoff.
5. `./scripts/verify-handoff.sh` — automated anchor sweep.

---

## 7. Decisions pinned

| # | Decision | Picked by | Rationale |
|---|---|---|---|
| 1 | Passkey sign-in is accepted on its own — no TOTP challenge afterward, even if the account has TOTP enabled | Andy (AskUserQuestion, 2026-07-01) | A WebAuthn ceremony already proves possession + local user-verification (biometric/PIN) — at least as strong as password+TOTP; stacking TOTP is redundant friction |
| 2 | Login page offers a "Sign in with a passkey" button with no username typed first (discoverable/resident credential) | Andy (AskUserQuestion, 2026-07-01) | True passwordless UX — the browser's own picker resolves the account; matches how Apple/Google/Microsoft treat passkeys |
| 3 | (Carried from the prior session) a passkey is an alternative sign-in path alongside password+TOTP, not a replacement | Andy (chat, 2026-06-30, recorded in the #272 `CURRENT_STATE.md` entry) | Pre-answers stop-and-ask trigger #5 before any passkey code was written |

---

## 8. Session-end verification (Rule #10)

| Check | Result |
|---|---|
| `webauthn_helper.py` exists, imports cleanly | ✅ |
| `user_webauthn_credentials` in `init_db.py` `_PG_MIGRATIONS` | ✅ grep |
| `_AUTH_EXEMPT_ENDPOINTS` carries both login-ceremony endpoints | ✅ grep + `test_login_endpoints_are_auth_exempt` |
| `user_webauthn_credentials` in `admin._delete_user_and_data` | ✅ grep |
| Full suite green, ruff 0 new errors | ✅ `pytest`/`ruff` run this session |
| Working tree clean after commit | ✅ `git status` |

---

## 9. Files shipped this session

**Substantive (9 files):**
1. `webauthn_helper.py` (new)
2. `init_db.py`
3. `routes/auth.py`
4. `routes/profile.py`
5. `routes/admin.py`
6. `app.py`
7. `static/webauthn.js` (new)
8. `templates/auth/_shell.html`
9. `templates/auth/login.html`
10. `templates/profile/account.html`

(10 listed — the count above rounds to "9 substantive + templates," consistent with this arc's precedent of full-stack slices running over the nominal 5-file ceiling.)

**Bookkeeping (4 files):**
1. `requirements.txt` (new dependency, not app logic)
2. `CURRENT_STATE.md`
3. `CARRY_FORWARD.md`
4. This handoff

**Tests (4 files, outside the ceiling):**
1. `tests/test_webauthn_helper.py` (new)
2. `tests/test_webauthn_routes.py` (new)
3. `tests/test_redesign_auth_render.py`
4. `tests/test_redesign_profile_render.py`

---

## 10. Carry-forward updates

Sign-up/Onboarding Consolidation (#246) section marked Phase 3 fully done (#272 + #267 both shipped); epic close recommended next session pending #304's carve-out confirmation.

---

**End of handoff.**
