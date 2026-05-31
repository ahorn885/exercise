# Control 08 — Consent & Cookie Mechanics

**Source of truth (authoritative):** `AIDSTATION_Cookie_Policy` §4; `AIDSTATION_Cookie_Banner_Spec`.
**Constants:** `COOKIE_CONSENT_EXPIRY` (12 months).

## Purpose
Implement the cookie consent model: strictly-necessary cookies without consent, analytics only on consent, no advertising and no sale, with GPC honored.

## Requirements
- **R1 — Categories.** Two only: **strictly necessary** (authentication, security, session, and the consent-preference cookie — no consent required) and **analytics** (consent required). No advertising cookies, no sale/share for ads.
- **R2 — Banner.** On first visit (web or app open), present a consent banner with **accept / reject / manage**. Analytics cookies are set **only** after consent.
- **R3 — Consent storage + expiry.** Store the choice in the `cookie_consent` strictly-necessary cookie. The choice persists until changed or until `COOKIE_CONSENT_EXPIRY` (12 months) elapses, after which re-prompt.
- **R4 — GPC.** Treat a Global Privacy Control signal as an opt-out; do not set analytics cookies when GPC is present.
- **R5 — Withdraw / change.** Provide control via **Settings → Privacy → Cookie Preferences**. Disabling a category stops new collection in that category; previously collected data is handled per the Privacy Policy.
- **R6 — Gating.** No analytics script fires before consent. "Reject" leaves only strictly-necessary cookies active.

## Data model (sketch)
- `cookie_consent` cookie: `{analytics: bool, set_at, expires_at}` (12-month expiry).
- No server-side PII required; consent state lives client-side in the strictly-necessary cookie.

## Triggers / jobs
- First-visit detection → render banner.
- Consent change / GPC detection → set or clear analytics; gate analytics loader on the stored/derived state.
- Expiry check → re-prompt after 12 months.

## Acceptance criteria
1. No analytics cookie or script is present before the user consents.
2. "Reject" leaves only strictly-necessary cookies; "Accept" enables analytics.
3. The consent choice persists for 12 months, then the banner re-prompts.
4. With a GPC signal present, analytics is not set regardless of banner state.
5. Disabling analytics in Settings → Privacy → Cookie Preferences stops new analytics collection.

## Out of scope
- Selecting/integrating a specific analytics vendor (procurement); the Partners-page subprocessor listing (handled in the policy docs).

## Dependencies
- None cross-control; consent state is self-contained.
