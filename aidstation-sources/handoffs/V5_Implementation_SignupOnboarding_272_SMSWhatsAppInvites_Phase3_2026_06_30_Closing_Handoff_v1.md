# Closing Handoff — Sign-up/Onboarding Phase 3, Slice 1: #272 SMS/WhatsApp Invites
**Date:** 2026-06-30
**Branch:** `claude/272-sms-whatsapp-invites`
**Commit:** `5624b4c`
**PR:** not yet opened — holding for Andy's go (standing rule, 2026-06-23)
**Epic:** [#246](https://github.com/ahorn885/exercise/issues/246)
**Kickoff:** `V5_Implementation_SignupOnboarding_Phase1-2_Merged_Phase3_272_267_Kickoff_Handoff_v1.md`

---

## §1 — What this closes

**#272 only.** Per the kickoff handoff's own flag (re-confirmed with Andy this session): #272 (SMS/WhatsApp invites) and #267 (passkeys) are unrelated mechanisms — Twilio sends SMS/WhatsApp, but passkeys are pure browser WebAuthn with no Twilio involvement. Andy confirmed: **two separate PRs**, SMS/WhatsApp first, and that a passkey (when built) is an **alternative sign-in option alongside password+TOTP, not a replacement**. #267 is unstarted — next session's work, on its own fresh branch.

## §2 — Re-grounding done first (per kickoff §3 instructions)

1. Read `HANDOFF.md` (root) — confirmed "SMS / WhatsApp invites" and "Passkeys / WebAuthn" are both listed under Parked, nothing built.
2. Grepped the whole repo for `twilio|webauthn|passkey|fido2` (case-insensitive) — zero hits outside docs/handoffs. Clean slate, as expected.
3. Mapped the existing invite + auth code via a research pass (see §3) before writing anything.
4. Re-confirmed scope with Andy (chat, this session): two PRs, SMS/WhatsApp first, passkey-as-alternative. Recorded in `CARRY_FORWARD.md`.

## §3 — What was already there (don't re-derive next session)

- **Invites were already fully built for email** — `user_invites` table (`init_db.py`), `routes/auth.py` (`issue_invite` / `lookup_invite` / `send_invite_email`), admin form + revoke (`routes/admin.py`), registration-bypass + auto-verify on accept (`routes/auth.register`). #272 only needed a new delivery channel, not new invite plumbing.
- **MFA (TOTP) is fully built and live** (`mfa.py`, `/profile/totp/*`, login challenge in `routes/auth.py`) — `HANDOFF.md`'s "parked" claim for MFA is stale; flagging for whoever next syncs that doc. Relevant to #267: a passkey will be a **third** auth path, not a second.
- **`email_helper.py`** hits SendGrid's HTTP API directly via `requests` — no SDK dependency for one POST. Mirrored exactly for Twilio (see §4).
- **No `users.phone` column exists.** SMS/WhatsApp invites only need a phone to deliver *to* — they don't capture a phone on the account. Left that capture out of scope (issue text is "send invites via SMS and WhatsApp," not "collect phone numbers").

## §4 — What shipped this session

**6 substantive code files + 2 test files** (`init_db.py`, `sms_helper.py` (new), `routes/auth.py`, `routes/admin.py`, `templates/admin/dashboard.html`, `templates/auth/register.html`, `tests/test_invites.py`, `tests/test_sms_helper.py` (new)).

- **`sms_helper.py` (new).** `send_sms` / `send_whatsapp`, plus `sms_configured()` / `whatsapp_configured()` gates. Raw `requests.post` against Twilio's REST Messages endpoint with HTTP Basic Auth (`AccountSid`/`AuthToken`) — same "no SDK for one POST" call Andy's `email_helper.py` already made for SendGrid. WhatsApp reuses the identical endpoint; Twilio just wants `whatsapp:` on both `To` and `From`. Unconfigured → stdout fallback (dev/preview), matching `email_helper`'s pattern exactly. Rule #15 logging: `[sms:sent|unconfigured|send_failed|twilio_rejected]` / `[whatsapp:...]`.
- **`user_invites` schema (`init_db.py`, `_PG_MIGRATIONS`).** Added `phone TEXT` and `channel TEXT NOT NULL DEFAULT 'email' CHECK (channel IN ('email','sms','whatsapp'))`; dropped `email`'s `NOT NULL` (a phone-channel invite has no email until the athlete enters one at registration). Idempotent — `ADD COLUMN IF NOT EXISTS` + a no-op-safe `DROP NOT NULL`. Public-schema → **auto-applies on next Vercel deploy, no `layer0-apply` owed** (this isn't a Layer 0 table).
- **`routes/auth.py`.** `issue_invite` generalized to keyword args (`email=`/`phone=`/`channel=`/`created_by=`); `lookup_invite`'s SELECT carries the two new columns. `send_invite_email` keeps its old call signature (no caller-visible break). New `send_invite_sms` / `send_invite_whatsapp`, same shape. `register()` now also resolves `invited_phone` from the invite row and passes it to the template (used only for the "you're invited" messaging, not pinned onto the account — there's nowhere to pin it without a `users.phone` column).
- **`routes/admin.py`.** `/admin/invite` now reads a `channel` field (`email`/`sms`/`whatsapp`, defaults to `email` for any stale cached form). Email path is byte-for-byte the old behavior. SMS/WhatsApp path validates the phone against `^\+[1-9]\d{7,14}$` (E.164-ish) and checks `sms_configured()` / `whatsapp_configured()` **before** sending — flashes a specific "isn't configured yet — set TWILIO_..." message rather than silently no-op'ing, since Andy won't have a server log open when he's just trying out the admin form.
- **`templates/admin/dashboard.html`.** Invite form gained a channel `<select>` + a phone `<input>` that toggles with the email field (CSP-nonce'd inline script, same pattern as `templates/locales/form.html`'s privacy-chip toggle — no inline event handlers). Pending-invite table shows `email or phone` + the channel.
- **`templates/auth/register.html`.** "You're invited" header now keys off `invite_token` (true for every channel) instead of `invited_email` (only true for email-channel invites) — a phone-channel invitee still sees invite messaging, just without a pinned address.

**VERIFIED:** full suite **4077 passed / 30 skipped** in a fresh `/tmp/venv` (baseline 4041 + 36 new: 7 `TestInviteHelpers` + 10 `TestAdminInvite` + 3 `TestRegisterInvite` additions in `tests/test_invites.py`, + 14 in the new `tests/test_sms_helper.py`; only the same 3 pre-existing unrelated warnings). Ruff: **0 new errors** (the 2 pre-existing `init_db.py`/`routes/auth.py` findings are untouched, confirmed via `git stash` diff — they predate this session). `tests/test_init_db_schema.py` (the migration-list sanity test) passes. `tests/test_redesign_auth_render.py` + `tests/test_redesign_admin_render.py` both green (template changes render clean).

## §5 — Owed to Andy (Twilio account setup — plain language, separate message)

Code is ready but inert until Twilio credentials are set as Vercel env vars. Full walkthrough given to Andy in chat this session, summarized here for the record:

1. Create a Twilio account, grab **Account SID** + **Auth Token** from the console dashboard → `TWILIO_ACCOUNT_SID`, `TWILIO_AUTH_TOKEN`.
2. Buy/use a Twilio phone number for SMS → `TWILIO_SMS_FROM` (E.164, e.g. `+15551234567`).
3. WhatsApp is a separate, heavier approval path through Meta (WhatsApp Business Platform) — not a quick env-var task like SendGrid's sender verification was. Twilio's WhatsApp Sandbox works immediately for **testing only** (recipients must first text a join code — unsuitable for real invitees); a production sender needs a Meta Business verification + an approved message template, which can take days and is gated by Meta, not engineering. → `TWILIO_WHATSAPP_FROM`.
4. Set all three (plus `TWILIO_SMS_FROM`/`TWILIO_WHATSAPP_FROM` as applicable) in Vercel project env vars, then redeploy (Vercel only applies env changes to new deployments, same gotcha as `SENDGRID_API_KEY`).
5. Spot-check: `/admin/` → Invite a user → channel SMS → a real phone number. Should arrive within seconds; `/admin/logs` will show `[sms:sent]` or `[sms:twilio_rejected]` with the rejection reason if Twilio 4xx's.

**No code changes owed for this — it's pure Twilio/Vercel console work.**

## §6 — Decisions recorded (Andy, this session)

- **Two separate PRs** for #272 and #267 (not one, despite D5 grouping "both via Twilio" together — passkeys don't touch Twilio at all).
- **Start order:** SMS/WhatsApp invites (#272) first — lower risk, no login-flow changes.
- **Passkey role (for #267, not yet built):** alternative sign-in option alongside password+TOTP, **not** a passwordless replacement. Password+TOTP stays the fallback/recovery path. This pre-answers the stop-and-ask trigger #5 question the kickoff flagged — Andy decided it before any passkey code gets written, per "don't implement first and ask forgiveness."

## §7 — Next: #267 passkeys, fresh session

Start on a **new branch off `main`**, post-#272-merge (not a continuation of this branch — same rule as the kickoff applied to this session). Needed before writing code:
- `user_passkeys` table design (credential_id, public_key, sign_count, user_id FK — standard WebAuthn relying-party shape).
- Server-side library choice (`webauthn`/`py_webauthn` — confirm current PyPI package name + maintenance status; none added to `requirements.txt` yet).
- Client-side: a small vanilla JS WebAuthn ceremony (`navigator.credentials.create`/`.get`) — check whether a CDN-free, CSP-nonce-compatible approach is feasible before reaching for `@simplewebauthn/browser`.
- Login-flow integration point: `routes/auth.py` `login()` (lines ~228–273) and `_finalize_login()` — add a passkey challenge path alongside the existing password/TOTP branches, gated the same way TOTP's `totp_pending_user_id` session pattern works.
- Recovery story: what happens if the only registered passkey is lost? (Password+TOTP recovery already covers this since passkey is additive, but worth stating explicitly in the per-feature spec before building.)

## §8 — Session-start reads for next session (Rule #13)

1. `CLAUDE.md`
2. `CURRENT_STATE.md`
3. `CARRY_FORWARD.md`
4. This handoff
5. `./scripts/verify-handoff.sh` if present
