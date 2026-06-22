# Onboarding OAuth Sign-In Design — Hybrid Identity + Connect-First

**Version:** 1.0
**Date:** 2026-06-21
**Status:** Draft for Andy review. Extends `Onboarding_D58_Design_v1.md` (which explicitly excluded sign-in-via-OAuth — see D-58 §9). Implementation pending.
**Backlog row:** #251 (Onboarding: make sign-up OAuth-first), child of #246 (onboarding & athlete data capture, Layer 1).
**Affects:** `routes/auth.py` (login/register), `routes/onboarding.py` (D-58 connect step), `routes/{strava,wahoo,oura,garmin}.py` (OAuth callbacks gain a "no session" branch), `routes/provider_auth.py` (identity-link helpers), new `provider_identity` table, `users` table (password becomes optional).
**Cross-references:**
- `Onboarding_D58_Design_v1.md` — the connect-first onboarding flow already shipped in `routes/onboarding.py`. This design adds the identity layer D-58 punted on and composes the two.
- `Athlete_Data_Integration_Spec_v4.md` §3 (provider list), §4.1 (`provider_auth` shape + status enum).
- `routes/provider_auth.py` — `upsert_auth`, `get_auth_by_provider_user_id`, `disconnect` (the null-on-disconnect behavior this design must route around).

---

## 1. Purpose

#251 asks to make sign-up "OAuth-first — connect a provider via OAuth (the 'log in with provider' flow) first." There are two distinct readings, and Andy chose **both** (2026-06-21):

1. **Identity-OAuth** — the provider OAuth flow *authenticates* the athlete. "Sign up / sign in with Strava." No password required. This is what D-58 §9 explicitly left out.
2. **Integration-OAuth (D-58)** — connecting a provider is the first onboarding *step*, used for data sync + prefill. Already built in `routes/onboarding.py`.

The hybrid: **a provider sign-in doubles as the athlete's first connection.** One OAuth round-trip both creates/authenticates the account *and* establishes the `provider_auth` row that D-58's prefill step reads from. The athlete who signs up with Strava lands on the D-58 connect step already showing Strava connected, with prefill candidates ready.

This design specifies the identity layer and how it composes with D-58 — not the per-provider OAuth handshakes (those exist already in `routes/{provider}.py`).

---

## 2. Why `provider_auth` can't be the identity link

The instinct is "reverse-look-up `provider_auth` by `provider_user_id` on callback; if found, log that user in." It doesn't hold:

1. **`provider_user_id` is not unique.** `provider_auth` has only `UNIQUE (user_id, provider)`. Two user rows could carry the same `(provider, provider_user_id)` — nothing stops it. Identity sign-in *requires* "one provider identity → at most one account," which is a uniqueness invariant the table doesn't enforce.
2. **`disconnect()` nulls `provider_user_id`** (`routes/provider_auth.py:147-182`). If identity rode on that column, disconnecting a provider from the management screen would silently sever the athlete's ability to log back in — a lockout. Identity must survive disconnect; data-sync auth must not.
3. **Status churn.** `provider_auth.status` cycles through `error` / `revoked` / `migrating` on token failures. Login must not depend on whether the sync token is currently healthy.

**Decision: a dedicated `provider_identity` table** records the durable "this provider account is linked to this user for login" fact, separate from the revocable sync credential in `provider_auth`. Disconnecting sync leaves identity intact; deleting the identity link (a deliberate, separate action) is what unlinks login.

---

## 3. Decisions

| # | Decision | Choice | Rationale |
|---|---|---|---|
| 1 | Identity storage | **New `provider_identity` table**, separate from `provider_auth`. `UNIQUE (provider, provider_user_id)` enforces one-identity-one-account. | §2. Survives sync disconnect; enforces the uniqueness invariant `provider_auth` can't. |
| 2 | Account model | **Passwordless-capable.** `users.password_hash` becomes nullable; an account may have zero passwords and ≥1 provider identity, a password and no providers, or both. | "Sign in with Strava, no password" is the ask. Existing email/password path is untouched for athletes who want it. |
| 3 | Sign-up vs sign-in disambiguation | **Same callback, branch on identity match.** Provider callback with no active session: if `(provider, provider_user_id)` matches a `provider_identity` row → log that user in. If not → create a new account, link identity, log in. | One button ("Continue with Strava") serves both; the athlete never has to know whether they have an account. Mirrors how every consumer "sign in with" works. |
| 4 | Email handling | **Use provider email when offered; synthesize a placeholder when not.** Wahoo + Oura expose email → seed `users.email` (unverified flag). Strava + Garmin don't → leave `users.email` NULL; account is reachable only via the provider until the athlete adds an email in profile. | Email is not required for an account (username is the unique key). Not blocking on email keeps Strava (no email) a first-class sign-in provider. |
| 5 | Account collision on email | **Do NOT auto-merge on matching email.** If a provider offers an email that matches an existing password account, we link only after the athlete proves control (logged-in linking, or email-verify challenge) — never silently on callback. | Silent merge-on-email is the classic account-takeover vector (attacker creates a provider account with the victim's email). Provider-offered emails here are unverified by us. |
| 6 | Linking an additional provider to an existing account | **Logged-in linking is the only auto-link path.** From the management screen (D-58 Account Config 1), an authenticated athlete runs the provider OAuth; the callback sees a session → writes `provider_identity` for the current user (in addition to the `provider_auth` row D-58 already writes). | The athlete is already proven; adding identities is safe. This is also how a password user adds "sign in with Strava" to their account. |
| 7 | Identity link ↔ D-58 connection | **One callback does both.** A successful identity sign-in/sign-up also writes the `provider_auth` row (tokens, scopes, scope-ack) exactly as the D-58 connect path does today. The just-signed-up athlete arrives at the D-58 connect step with that provider already connected. | The hybrid payoff: zero extra clicks to get from "signed up with Strava" to "Strava data flowing + prefill ready." |
| 8 | Garmin | **Design the slot; mark it blocked.** Garmin is username/password via `garth` (`routes/garmin.py`), no OAuth. It gets a `provider_identity` provider slug reserved and the same flow *spec'd*, but the button is disabled until Garmin's OAuth API reopens (CLAUDE.md stack notes: "Garmin paused (API closed)"). | Honest: we can't "Sign in with Garmin" without Garmin OAuth. Reserving the slug avoids a schema change when it reopens. |
| 9 | Unlink safety | **Block removing the last login method.** An athlete can unlink a provider identity only if they retain another login method (another provider identity, or a password). Removing the last one is refused with a prompt to set a password first. | Prevents self-lockout — the passwordless analog of "don't delete your only SSH key." |
| 10 | Disconnect vs unlink are different actions | **D-58 "disconnect" (stop syncing) ≠ "unlink" (remove login).** Disconnect revokes `provider_auth` (existing behavior). Unlink removes `provider_identity`. The management screen surfaces both, clearly labeled. | §2.2. Disconnecting Strava sync must not log you out of an account you can only reach via Strava. |

---

## 4. Provider capability matrix (the four in scope)

What each provider's OAuth actually returns that's usable as identity. Grounded in the existing callbacks.

| Provider | OAuth today | Stable identity key | Name | Email | Sign-in readiness |
|----------|-------------|---------------------|------|-------|-------------------|
| **Wahoo** | ✅ `routes/wahoo.py` | `user.id` / `/v1/user` `id` (`wahoo.py:139-146`) | ✅ `/v1/user` first/last | ✅ `/v1/user` email | **Cleanest.** Id + name + email in one call. Reference implementation. |
| **Oura** | ✅ `routes/oura.py` | `personal_info` `id` | ✅ | ✅ explicit `email` scope | **Strong.** Only integrated provider with an `email` scope by design. |
| **Strava** | ✅ `routes/strava.py` | `athlete.id` (`strava.py:155`) | ✅ `athlete` first/last | ❌ none | **Profile-only.** Works as identity via `athlete.id`; account has no email until athlete adds one. |
| **Garmin** | ❌ garth user/pass | (would be OAuth sub) | — | — | **Blocked.** No OAuth; slot reserved, button disabled (decision #8). |

Implication for email (decision #4): Wahoo/Oura seed `users.email` unverified; Strava leaves it NULL. None of these emails are verified-by-us, so none trigger auto-merge (decision #5).

For Wahoo, confirm at go-live that `/v1/user` returns `email` + `first`/`last` under the existing `user_read` scope — the callback currently only reads `id` (`wahoo.py:146`); identity sign-in needs the name/email fields too. (Rule #14: verify against a live `/v1/user` payload, don't assume the shape.)

---

## 5. Schema additions

All on `_PG_MIGRATIONS` (SQLite path retired — CLAUDE.md stack).

### 5.1 New table — `provider_identity`

```sql
CREATE TABLE IF NOT EXISTS provider_identity (
    id                  SERIAL PRIMARY KEY,
    user_id             INTEGER NOT NULL REFERENCES users(id),
    provider            TEXT NOT NULL,
        -- Slug from CONNECTION_PROVIDERS (routes/profile.py): 'strava',
        -- 'wahoo', 'oura', 'garmin' (reserved, disabled). Same vocab as
        -- provider_auth.provider.
    provider_user_id    TEXT NOT NULL,
        -- The provider-side stable user id (Strava athlete.id, Wahoo
        -- user.id, Oura personal_info.id). The identity key.
    email_at_link       TEXT,
        -- Provider-offered email captured at link time, unverified.
        -- NULL for Strava. Informational; not an auth key.
    linked_at           TIMESTAMP NOT NULL DEFAULT NOW(),
    last_login_at       TIMESTAMP,
    UNIQUE (provider, provider_user_id),   -- one identity → one account
    UNIQUE (user_id, provider)             -- one identity per provider per user
);

CREATE INDEX IF NOT EXISTS provider_identity_user_idx
    ON provider_identity (user_id);
```

`provider_auth` is unchanged. The two tables share `(user_id, provider)` semantics but serve different lifecycles: `provider_auth` = revocable sync credential; `provider_identity` = durable login link.

### 5.2 `users` — password becomes optional

```sql
ALTER TABLE users ALTER COLUMN password_hash DROP NOT NULL;
ALTER TABLE users ADD COLUMN IF NOT EXISTS email_verified BOOLEAN DEFAULT FALSE;
```

`email_verified` is FALSE for provider-seeded emails (decision #4/#5) and for existing password accounts until a verification flow ships (out of scope here; the column is forward-compat). `_check_password` already returns False on an empty hash (`auth.py:78-84`), so a passwordless account simply can't log in via the password form — exactly right.

### 5.3 Account Config 3 scope acks

No change — the existing `oauth_scope_<provider>` disclosure rows (D-58 §7.3, `record_oauth_scope_ack`) already fire on every callback and cover the sign-in callback too.

---

## 6. Flows

### 6.1 Sign up / sign in with a provider (no active session)

Entry: "Continue with Strava / Wahoo / Oura" buttons on `/auth/login` and `/auth/register`.

```
1. GET /<provider>/oauth/start
   - No session: instead of redirect→login (current behavior, e.g.
     strava.py:76), set an `oauth_intent=signin` flag in session and
     proceed to the provider consent screen. return_to defaults to the
     post-signin target.
2. GET /<provider>/oauth/callback
   - Exchange code → tokens + provider_user_id (+ name/email where offered).
   - LOOK UP provider_identity by (provider, provider_user_id):
       a. MATCH  → existing account. Log in (session['user_id']).
                   Update last_login_at. Upsert provider_auth (refresh
                   tokens/scopes). Redirect to dashboard.
       b. NO MATCH → new athlete:
            - Create users row: username synthesized (see §6.4),
              password_hash NULL, email = provider email or NULL,
              email_verified FALSE.
            - Seed current_rx (mirror auth.register, auth.py:315).
            - Write provider_identity (the link).
            - Write provider_auth (tokens/scopes) + scope ack.
            - Log in. Redirect to Step 1 (§A.1 ack) → D-58 connect step,
              which now shows this provider already connected.
```

Both branches end with the `provider_auth` row written, so D-58 prefill works immediately (decision #7).

### 6.2 Link a provider to a logged-in account

Entry: D-58 management screen (Account Config 1) "Connect" button — unchanged URL.

```
1. GET /<provider>/oauth/start  — session present (current behavior).
2. GET /<provider>/oauth/callback — session present:
   - Exchange code → provider_user_id.
   - If provider_identity exists for (provider, provider_user_id):
       - belongs to THIS user → no-op link (refresh provider_auth only).
       - belongs to ANOTHER user → refuse with a flash ("That Strava
         account is already linked to a different AIDSTATION account").
   - Else write provider_identity for current user.
   - Upsert provider_auth + scope ack (D-58 path, unchanged).
```

This is also how a password-only athlete adds "sign in with Strava" later.

### 6.3 Unlink (decision #9)

Management screen "Remove sign-in" action, distinct from D-58 "Disconnect":
```
- Count the user's login methods = (provider_identity rows) +
  (1 if password_hash IS NOT NULL else 0).
- If removing this identity would drop the count to 0 → refuse, prompt
  "Set a password first so you don't lose access."
- Else DELETE the provider_identity row. provider_auth is untouched
  (sync continues unless they also disconnect).
```

### 6.4 Username synthesis (new passwordless accounts)

`users.username` is `NOT NULL UNIQUE` and the human-facing handle. For provider sign-ups with no chosen username:
- Seed from provider name (Strava `athlete.firstname`+lastname, Wahoo `first`/`last`) slugified, with a numeric suffix on collision (`alex`, `alex2`, …).
- Surface it on the D-58 connect step as an editable field ("Your handle: `alex` — change?") so the athlete isn't stuck with a synthesized one.

---

## 7. Edge cases

| Case | Handling |
|---|---|
| Provider returns no email (Strava, Garmin) | Account created with `email = NULL`. Athlete can add + verify an email in profile later. Password reset is unavailable until they do (no email to send to) — surfaced as a gentle prompt on the connect step. |
| Provider email collides with an existing password account | No auto-merge (decision #5). New account is created with `email = NULL` (we drop the colliding email rather than attach an unverified one to a second account) and a flash: "Already have an account? Log in and link Strava from settings." |
| Same person, two providers, signs up twice | Creates two separate accounts (we can't know they're the same person without a shared verified email). They consolidate by logging into one and linking the other; the second account's data is theirs to abandon or (future) merge. Documented limitation, not solved in v1. |
| Disconnect sync on a provider that's the only login | Allowed — disconnect ≠ unlink (decision #10). Identity row persists; they can still sign in, just no fresh data syncs. |
| Provider account is deleted on the provider side | Their token stops working (`provider_auth` flips to `error` via the refresh path, `provider_auth.py:240`). Identity row persists; sign-in still works (we don't re-validate the provider account on every login — the identity match is local). |
| `oauth_intent=signin` session flag leaks into a logged-in link | Callback checks `current_user_id()` first; a present session always takes the §6.2 link branch regardless of the flag. |
| CSRF on the no-session start | The existing `state` token + `hmac.compare_digest` check (`strava.py:84,116`) is unchanged and covers the signin start too. |

---

## 8. Security considerations

- **No silent merge-on-email (decision #5).** The one rule that prevents provider-email account takeover. Provider emails are unverified-by-us; treat them as display data, never as proof of control.
- **Uniqueness invariant (`provider_identity UNIQUE (provider, provider_user_id)`).** Guarantees one provider account can't authenticate two AIDSTATION accounts. The DB enforces it; the callback also checks-then-acts inside the request, but the constraint is the real backstop against a race.
- **Last-login-method guard (decision #9).** Prevents self-lockout.
- **Passwordless accounts can't be brute-forced** (no password to guess) but inherit the provider's auth posture — if the athlete's Strava is compromised, so is their AIDSTATION account. Acceptable and standard for SSO; documented.
- **Rate-limit the signin callbacks** the same way `auth.login` is (`@_limit('10 per 5 minutes')`, `auth.py:219`) to blunt account-creation spam via repeated OAuth.

---

## 9. Test plan (Andy's accounts: Strava, Wahoo, Garmin)

Container can't reach Neon; flows are exercised against a deploy + `/admin/logs` (Rule #14), with the OAuth client secrets set in Vercel env.

1. **Wahoo, cold sign-up.** Logged out → "Continue with Wahoo" → consent → expect: new account, `provider_identity` + `provider_auth` rows, email seeded unverified, landed on D-58 connect step with Wahoo connected. (Reference path — id+name+email all present.)
2. **Wahoo, returning sign-in.** Log out, "Continue with Wahoo" again → expect: same account, `last_login_at` bumped, no duplicate user row.
3. **Strava, cold sign-up.** Same as (1) but `email = NULL`, username synthesized from athlete name, no email-dependent features. Confirms the no-email path is first-class.
4. **Strava link to existing account.** Log in as the Wahoo account → management screen → connect Strava → expect: second `provider_identity` for the same user; now both buttons sign into that one account.
5. **Unlink guard.** From the password-less account, try to unlink the only identity → expect refusal + "set a password" prompt. Set password, retry → succeeds.
6. **Collision.** Create a password account with Wahoo's email; then "Continue with Wahoo" logged out → expect: NO merge, new account with NULL email, the "log in and link" flash.
7. **Garmin.** Confirm the button renders disabled with the "API access paused" tooltip; no callback path reachable.

Each path must emit a `print()` of the decision it made (match/create/link/refuse) per Rule #15 so the flow is legible in `/admin/logs`.

---

## 10. What this design does NOT cover

- **Account merge** (two accounts → one). §7's "same person twice" case is documented, not solved. Backlog candidate.
- **Email verification flow.** `email_verified` column lands here; the verify-by-link flow is separate work (and would let decision #5 relax to verified-email linking).
- **Garmin OAuth.** Blocked on Garmin reopening their API; slot reserved only.
- **Other providers** (COROS, Polar, Whoop, RWGPS, TrainingPeaks). The pattern generalizes — any provider with a stable `provider_user_id` can get a `provider_identity` slug — but only Strava/Wahoo/Oura are in scope for v1 (COROS/Polar expose opaque ids and no profile/email, weaker identity; add later if wanted).
- **The implementation PR(s).** Migration + auth-route changes + the four callbacks' no-session branch + management-screen unlink UI are substantial; scope into ≤5-file slices per the ceiling. Suggested first slice: schema + `provider_identity` helpers + Wahoo callback no-session branch (the reference provider), behind a feature flag.

---

## 11. Gut check

**What this gets right.**
- Separating identity (`provider_identity`) from sync auth (`provider_auth`) is the load-bearing call. It's the difference between "disconnect logs me out" (broken) and "disconnect just stops syncing" (correct), and it's the only way to enforce one-identity-one-account without contorting the existing table.
- The hybrid genuinely pays off: one OAuth round-trip yields both login and the first D-58 connection, so "sign up with Strava" lands the athlete on a connect step that's already useful.
- No-silent-merge is the right security default even though it produces the occasional duplicate account; the inverse (merge on unverified email) is a takeover hole.

**Risks.**
- **Duplicate accounts** for athletes who sign up with two providers separately, until a merge flow exists. For a solo-test product today this is theoretical; at real scale it's a support burden. Mitigation: prompt "already have an account? link instead" prominently.
- **Strava's missing email** means a Strava-only account has no recovery channel if the athlete loses Strava access. The "add an email" prompt mitigates but athletes will ignore it. Acceptable for v1; revisit.
- **Wahoo `/v1/user` shape is unverified** for name/email under `user_read` (Rule #14 owed). If those fields aren't there, Wahoo degrades to Strava-like (id-only) — still works, just no email seed.
- **Passwordless + provider-compromise** couples AIDSTATION account security to the provider's. Standard SSO tradeoff; nothing novel, but worth stating in the privacy program docs.

**Best argument against.** D-58 deliberately excluded sign-in-OAuth as a separate concern, and the connect-first flow already delivers most of #251's intent ("connect a provider before the rest") *without* touching auth. A leaner read of #251 is "ship D-58, done." The counter: Andy explicitly wants the literal "log in with provider" (2026-06-21), and the hybrid is where the leverage is — making the first connection *also* the login removes the password step entirely for provider-first athletes, which the connect-first-only flow can't do. The identity layer is the part of #251 that isn't already built.

---

*End. Next: Andy review → if approved, scope the first implementation slice (schema + Wahoo reference path) per the 5-file ceiling.*
