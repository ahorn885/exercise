# AIDSTATION Cookie Consent Banner & GPC Handler — Design Spec

**Status:** Draft v1, Batch 4 of the privacy program
**Companion docs:** Cookie Policy, Privacy Policy §§4 and 11
**Implements:** Decision #29 (strictly necessary + analytics only), Cookie Policy §4 (consent mechanics), Decision #9 (no ads / no sale / GPC honored)

---

## 1. Purpose and Scope

This spec defines the cookie consent banner, the in-app preferences screen, and the GPC handler that together implement the published Cookie Policy.

In scope:

- Banner UI requirements (web and in-app)
- Category presentation and the reject-button parity requirement
- Cross-domain consent coordination (marketing site, app)
- GPC signal detection and behavior
- Re-prompt cadence and re-prompt triggers
- WordPress.com / Jetpack handling (marketing site)
- Quebec Law 25 specifics
- Audit trail of consent decisions

Out of scope:

- Selection of the analytics provider (separate procurement decision)
- Selection of the APM/error-monitoring provider (same)
- Choice of consent management platform (CMP) vs. self-built (Section 11 makes a recommendation)

---

## 2. Inherited Decisions

| Item | Decision | Source |
|---|---|---|
| Categories | Strictly necessary + analytics only | #29, Cookie Policy §2 |
| No advertising cookies | Confirmed | Cookie Policy §2.3 |
| Consent expiry | 12 months | Cookie Policy §4 |
| Granular by category | Required | Cookie Policy §4 |
| GPC honored | Yes, app and marketing site | Cookie Policy §5.3 |
| Re-prompt on policy change | Yes | Cookie Policy §6 |

---

## 3. Cookie Surfaces

AIDSTATION operates two architecturally distinct surfaces, each needing the banner:

| Surface | Domain (assumed) | Stack | Notes |
|---|---|---|---|
| Marketing site | `aidstation.pro` | WordPress.com | Jetpack and WP defaults need to be controlled (Section 9) |
| Application | `app.aidstation.pro` | Vercel + Neon | First-party, full control |

The mobile app (planned post-launch) uses a different mechanism (Section 10), but stays consistent with the same category model.

A shared consent state across the two web surfaces is desirable — a user who declines analytics on the marketing site should not be re-prompted on the app, and vice versa. Section 7 specifies the coordination mechanism.

---

## 4. Banner UX Requirements

### 4.1 First-Visit Banner

Shown on the first visit to either domain when no consent record exists.

**Layout:** Bottom-fixed bar on desktop; bottom sheet on mobile. Non-blocking on the marketing site (the user can scroll and read). Blocking on the app prior to login (the user must make a choice before reaching authenticated screens) — this avoids loading analytics during login.

**Content:**

> We use cookies to make AIDSTATION work and to understand how it is used. Strictly necessary cookies are always on. Analytics cookies are off by default and only set with your consent.
>
> [Accept all] [Reject non-essential] [Customize]
>
> [Read our Cookie Policy]

**Button parity:** `Accept all` and `Reject non-essential` must be:

- Equally prominent (same size, same color weight, same position prominence)
- Reachable in the same number of clicks
- Labelled clearly — no dark patterns like "Reject" being smaller, lower-contrast, or hidden behind a "More options" menu

This is a hard requirement under Quebec Law 25 and is broadly considered best practice under GDPR. EDPB guidance is explicit that "Reject all" must be on the first layer at the same prominence as "Accept all."

### 4.2 Customize Screen

Triggered by the `Customize` button. Lists each category with:

- Category name (Strictly necessary, Analytics)
- One-line description
- Toggle (Strictly necessary toggle is disabled and shown ON; Analytics toggle defaults OFF)
- Link to the specific cookies in the Cookie Policy table

Buttons at the bottom:

- `Save preferences` (primary)
- `Reject all non-essential` (secondary, same prominence)
- `Accept all` (secondary, same prominence)

### 4.3 No Confirmshaming

Banner copy is neutral. No "Are you sure? You'll miss out on improvements" prompts. No nag screens.

### 4.4 Standing Access

A `Cookie Preferences` link is present in the footer of both surfaces and at Settings → Privacy → Cookie Preferences in the app. The link opens the Customize screen with the user's current choices pre-filled.

### 4.5 Accessibility

- Banner is keyboard navigable in tab order: `Accept all` → `Reject non-essential` → `Customize` → `Cookie Policy link`
- Screen reader labels are explicit ("Cookie consent: choose your preferences")
- Color contrast meets WCAG 2.1 AA
- Mobile banner does not obscure essential content; it can be dismissed without making a choice on the marketing site, but the absence of a choice is treated as "reject non-essential" (no consent for analytics)

---

## 5. Behavior Model

### 5.1 Pre-Consent State

Before the user makes a choice (and absent a GPC signal — see Section 8), only strictly necessary cookies are set. No analytics fire. No analytics scripts are even loaded.

Analytics scripts must be loaded lazily, gated on a consent check. They cannot be inlined in the page head.

### 5.2 On Accept All

- `cookie_consent` cookie is set with payload: `{ analytics: true, version: <policy-version>, set_at: <timestamp>, jurisdiction: <country-code> }`
- Analytics scripts load
- Consent record is written server-side (Section 12)

### 5.3 On Reject Non-Essential

- `cookie_consent` cookie is set with payload: `{ analytics: false, version, set_at, jurisdiction }`
- Analytics scripts do not load
- Consent record is written server-side

### 5.4 On Customize → Save

Same as Accept or Reject, with the user's actual choices.

### 5.5 On Dismiss Without Choice (Marketing Site Only)

Treated as reject non-essential. No analytics. No `cookie_consent` payload is set (so the banner re-appears on the next visit, until a choice is made).

---

## 6. Re-Prompt Cadence

The banner re-appears in the following cases:

1. **12 months elapsed** since the last `cookie_consent.set_at` — required by Cookie Policy §4.
2. **Policy version changed** — when the Cookie Policy is materially updated, the `version` field changes; any cookie with an older version triggers a re-prompt with a brief "we updated our cookie policy" header.
3. **New category added** — same mechanism as policy version change.
4. **User clears their cookies** — the consent record is gone, so the banner is shown as if first visit.
5. **User explicitly visits Cookie Preferences** — not technically a re-prompt; the preferences screen reflects the current state and allows changes.

The banner does not re-appear on every visit, on a new device, or on a different browser — each device/browser is independent (cookies are device-bound).

---

## 7. Cross-Domain Coordination

The marketing site and the app are on the same eTLD+1 (`aidstation.pro`). The `cookie_consent` cookie is set on the apex domain with `Domain=.aidstation.pro` so it is readable from both `aidstation.pro` and `app.aidstation.pro`.

Caveats:

- This works for first-party cookies in browsers that haven't disabled them broadly (most browsers in 2026 still allow first-party cookies; Safari ITP and similar treat them as partitioned but the same-eTLD+1 case is preserved).
- If `app.aidstation.pro` is served from a fundamentally different domain at any point (e.g., `aidstation.io` for the app), this no longer works and a server-side coordination layer is needed.
- Server-side consent record (Section 12) is the source of truth for authenticated app users — once the user is logged in, the server-stored consent state takes precedence over the cookie. The cookie is the source of truth pre-login and on the marketing site for anonymous visitors.

Recommended pattern:

- Marketing site (anonymous): cookie is source of truth
- App pre-login: cookie is source of truth
- App post-login: server record is source of truth, and the cookie is synced from the server record on login

---

## 8. GPC Signal Detection

### 8.1 Detection

On every page load (marketing site and app), check `navigator.globalPrivacyControl` first (JavaScript API), falling back to the `Sec-GPC: 1` request header.

If GPC is signaled:

- Treat as automatic "reject non-essential" for analytics, regardless of prior consent.
- Do not show the banner. Suppress the analytics scripts.
- Set `cookie_consent` payload to `{ analytics: false, version, set_at, jurisdiction, source: 'gpc' }`.
- Log the GPC-driven choice as a consent event (Section 12).

### 8.2 GPC vs. Prior Consent

If the user previously consented to analytics and then a GPC signal appears (new browser, GPC turned on later):

- The GPC signal takes precedence.
- Analytics stop. The server-side state is updated.
- Next time the user visits without GPC, the banner does not auto-reappear — the user can explicitly re-consent via Cookie Preferences. We do not assume the user wants to opt back in just because the signal went away. This is the more privacy-protective interpretation.

### 8.3 GPC and Sale / Share

AIDSTATION does not sell or share personal data (Decision #9). The GPC signal is honored anyway as a sale/share opt-out for consistency with U.S. state laws that treat GPC as a universal opt-out signal. No additional action is required beyond what is already described.

### 8.4 GPC Disclosure

The Privacy Policy and Cookie Policy already disclose that GPC is honored (Cookie Policy §5.3). No additional in-app disclosure is required, but if the user has GPC enabled and visits Cookie Preferences, show a non-blocking notice:

> Your browser is sending a Global Privacy Control signal. We have set your analytics preference to off. You can override this in your browser settings if you want to manage cookies manually.

---

## 9. WordPress.com / Jetpack Handling

The marketing site is on WordPress.com (Decision #31). WordPress.com defaults set Jetpack stats cookies and may set other first-party cookies depending on enabled features.

Before the banner can be honest about what is set, the marketing site configuration must:

- Disable Jetpack Stats (or migrate to a consent-gated stats configuration that is off by default).
- Disable any WordPress.com features that set cookies without consent (e.g., comment cookies, post-meta cookies tied to user identity).
- Confirm that the WordPress.com theme in use does not load third-party fonts or scripts that set cookies.

The Cookie Policy currently lists `[analytics_id]` as a placeholder for the analytics provider — that placeholder will be filled with a privacy-aligned provider (PostHog, Plausible, or similar). WordPress.com Jetpack stats are not a good fit because:

- They are on by default
- Their consent model does not integrate cleanly with our banner
- The aggregation and retention are controlled by Automattic, not us

Operational item: an explicit audit of the WordPress.com site's cookie footprint must happen before publishing the Cookie Policy. This is added to the followup tracker.

---

## 10. Mobile Application

When the mobile app ships, the same model applies with adjustments:

- "Cookie consent" on mobile means consent to analytics SDK initialization, local storage usage for non-essential identifiers, and any push token storage beyond what is required for the service.
- Strictly necessary always-on: device identifiers needed for authentication, secure storage of session tokens.
- Analytics opt-in: app analytics SDK, crash reporting if it includes identifying information.
- The first-launch screen presents the same choices as the web banner.
- Consent is stored server-side (the user is authenticated on first launch in most flows), with a local cache for performance.

Cookie Policy §5.4 already describes this at a user-facing level.

---

## 11. Implementation Choice: Build vs. Buy

**Recommendation: build a minimal first-party banner and skip a CMP for v1.**

Reasoning:

- The category model is narrow (strictly necessary + analytics). A CMP is overkill for two categories.
- Most CMPs are designed for advertising-heavy stacks with dozens of vendors. We have none.
- A custom banner avoids paying a CMP for IAB TCF (Transparency and Consent Framework) machinery we will not use.
- A custom banner gives us tight control over button parity, copy, and the GPC handler — these are areas where many CMPs underperform.

What we build:

- A small banner component (one for marketing site, one for the React app — share styling and copy)
- A server-side endpoint that records consent events and serves the current consent state for authenticated users
- A shared TypeScript module that wraps `navigator.globalPrivacyControl` detection, cookie read/write, and consent-state resolution

Estimated effort: 1–2 weeks of focused implementation. Cheaper than the cheapest CMP over the first 2 years.

Re-evaluate at the point that (a) we onboard a third advertising or marketing partner that would benefit from a TCF-style consent string, or (b) compliance complexity grows beyond two categories.

---

## 12. Audit Trail

Every consent event is written to a `consent_events` table:

| Column | Notes |
|---|---|
| `event_id` | UUID |
| `user_id` | Nullable (anonymous marketing site visitors) |
| `device_id_hash` | Hash of a device identifier; lets us de-duplicate without storing raw IDs |
| `event_type` | `accept_all`, `reject_non_essential`, `customize_save`, `gpc_applied`, `re_prompt_shown`, `re_prompt_dismissed` |
| `choices_json` | The category-by-category decisions |
| `policy_version` | The version of the Cookie Policy in effect |
| `source` | `banner`, `preferences_screen`, `gpc`, `policy_version_change` |
| `ip_country` | Derived from IP; only the country code is stored |
| `ip_hash` | Hashed IP, retained for the period required for audit (90 days max) |
| `user_agent_hash` | Hashed UA |
| `timestamp` | ISO 8601, UTC |

Retention: per RoPA PA-14 (consent records). Audit-only access.

This satisfies the EDPB guidance that consent must be demonstrable, and Quebec Law 25's traceability requirements.

---

## 13. Quebec Law 25 Specifics

Quebec Law 25 imposes a stricter banner standard than GDPR in several dimensions:

- **Equal prominence** of Accept and Reject — already met (Section 4.1)
- **Granular consent by purpose** — met (Section 4.2)
- **Plain-language descriptions** — banner copy and category descriptions must be in clear, non-legalistic French and English. Cookie Policy and banner copy must be translated for Quebec users.
- **Withdrawing consent must be as easy as giving it** — met by the standing access pattern (Section 4.4)
- **Special protection for sensitive personal information** — addressed at the data layer (sensitive categories are opt-in regardless of cookies); cookies themselves do not collect sensitive personal information

Implementation note: French translation is a follow-up item. The banner and Cookie Policy must be translated before active marketing in Quebec.

---

## 14. Edge Cases

### 14.1 User Has Cookies Disabled in Browser

The banner cannot persist the consent choice via cookie. The banner appears on every visit. The site continues to function (strictly necessary state is held in session memory). This is acceptable — the user has made a clear browser-level decision.

### 14.2 Embedded Content (Future)

If the marketing site embeds third-party content (YouTube video, etc.), each embed is potentially a third-party cookie source. Each embed must be consent-gated or replaced with a click-to-play placeholder. Add to followup tracker for marketing site review.

### 14.3 Email Tracking Pixels

Transactional email open tracking is not consent-gated under current rules in most jurisdictions when used for service emails. If marketing emails ever ship, open-rate pixels in those emails would be consent-gated (under the marketing communications opt-in per Decision #10). The cookie banner does not handle this; the email subscription model does.

### 14.4 Server-Side Analytics

If analytics moves to server-side collection (e.g., log-based metrics that do not require client-side cookies), the cookie banner does not apply. But the user-facing disclosure must still describe what is collected and on what basis. The Cookie Policy currently describes client-side cookies; if server-side analytics is added, the Privacy Policy must describe it.

### 14.5 Region Detection Failure

If we cannot determine the user's jurisdiction (no IP, blocked geolocation), default to the most protective jurisdiction's rules — i.e., behave as if the user is in the EU. This is the safe default.

---

## 15. Open TBDs

- Final analytics provider choice (PostHog, Plausible, similar) — drives the specific analytics cookie names in the Cookie Policy table
- Final APM/error-monitoring choice (Sentry standard) — same
- French translation of banner copy and Cookie Policy for Quebec
- Specific WordPress.com cookie footprint audit
- Whether to implement TCF-compliant consent strings (currently: no, per Section 11)
- Whether marketing-email subscription opt-in is integrated into the banner UX or separate (recommend separate — different consent class, different mechanics)

---

## 16. Gut Check

**Risks**

- The cross-domain coordination via apex-domain cookies works today but is fragile against future browser changes. Safari's ITP, increasing partition rules, and the broader trend toward third-party-style restrictions on first-party cookies in some contexts mean the same-eTLD+1 sharing may erode. The fallback (server-side consent record post-login) is solid; the pre-login marketing site / app coordination is where the fragility lives. Re-evaluate annually.
- WordPress.com Jetpack is genuinely a problem. Until that audit happens, we cannot say with confidence that the marketing site is honoring the policy. Recommend doing the audit before publishing the Cookie Policy.
- Building rather than buying a CMP is the right call for v1 but increases the implementation burden on the team. If the team is small and consent is not in someone's clear lane of responsibility, it can become a corner-cutting risk. Mitigation: scope this in alongside the analytics provider integration; the same engineer who wires up analytics also owns the consent gate.

**What might be missing**

- A pre-banner "we use cookies" inline notice at the top of marketing-site articles is sometimes layered with the banner in heavily-trafficked sites; we are skipping this because it conflicts with the cleanest UX and is not legally required when the banner itself is compliant.
- A consent receipt feature (the user can download proof of what they consented to and when) is a privacy-trust gesture some users appreciate; defer to v2.
- The "your browser is sending GPC" notice (Section 8.4) could be more prominent — some users do not know their browser is doing this. Worth a brief in-app educational touch in Settings → Privacy.

**Best argument against the current trajectory**

The two-category model (strictly necessary + analytics) is intentionally narrow but it does close off some product growth paths. If, post-launch, we want to add a customer support chat widget, a community forum embed, or a learning resource video host, each of those likely sets cookies that fall outside the current categories. We will either need to add categories (re-prompt all users), implement those features cookie-free (constrains vendor choice), or accept that some features will require consent-gating that complicates the UX. Worth being deliberate about how we evaluate new vendors against the cookie model going forward.

---

*Cross-reference cleanup (v3, 2026-05-30): inline references to companion documents converted to unversioned logical names per Rule #12 (this document was outside the earlier cross-reference unversioning batch). No substantive content changes.*
