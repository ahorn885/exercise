# AIDSTATION Partners

**Last Updated:** May 30, 2026

This page lists the third parties involved in delivering AIDSTATION. We separate them into two categories with different legal roles and relationships to your data.

AIDSTATION is operated by AIDSTATION Pro, LLC, a Texas limited liability company. If you have questions about any partner listed here, contact help@aidstation.pro.

---

## How AIDSTATION Is Built

AIDSTATION operates as two coordinated environments:

- The **marketing and information website** (the public site where you read about AIDSTATION, find this page, and contact us) is hosted on WordPress.com.
- The **application** (where you train, manage your account, and interact with the AI coach) runs on Vercel with data stored in a managed Postgres database.

These environments process different categories of data and are described separately below.

---

## Service Providers (Subprocessors)

Service providers process data **on our behalf** to operate AIDSTATION. They are contractually bound to confidentiality, data protection, and limited-purpose use. They cannot use your data for their own purposes.

We require all service providers to sign a Data Processing Agreement before we share data with them. We review their security practices and certifications and monitor their performance throughout the relationship.

| Provider | Role | Categories of Data | Hosting Location |
|---|---|---|---|
| **Vercel** | Application hosting, serverless compute, content delivery | All application data in transit; ephemeral compute state | United States |
| **Neon** | Managed Postgres database (primary application data store) | All persistent service data — account, training, derived data | United States |
| **Anthropic** | AI inference for coaching plan generation, recommendations, and conversational features | Coaching prompts and outputs | United States |
| **SendGrid** (Twilio) | Transactional email and, with consent, marketing email | Email address, message content, delivery metadata | United States |
| **WordPress.com** (Automattic) | Hosting of the marketing and information website | Website visitor data — IP address, browser and device info, page views, form submissions on the marketing site | United States |
| [TBD Payment processor] | Subscription billing and payment processing | Payment method (last four digits and confirmation only; we do not retain full card numbers) | [TBD] |
| [TBD Analytics provider for the application] | Aggregate usage measurement within the app | Pseudonymous usage and event data | [TBD] |
| [TBD Error monitoring] | Application performance and error reporting | Technical logs and error traces | [TBD] |
| [TBD Customer support platform] | Support ticket management | Support communications | [TBD] |

**Notes:**

- **Anthropic** provides AI inference under their commercial API terms. Anthropic does not use AIDSTATION data to train their models. AIDSTATION itself develops and improves its own AI coaching models using user content under the safeguards described in Privacy Policy section 4 and the user content license in our Terms and Conditions. We do not retain raw conversation transcripts long-term; we retain parsed coaching notes and derived data only.
- **WordPress.com** processes visitor data for the marketing site only. The application itself does not run on WordPress. WordPress.com may use cookies and analytics on the marketing site; see our Cookie Policy.
- **Vercel** and **Neon** host the core application and the data you generate while using it. Both are US-based with data stored in US regions.
- **SendGrid** handles all email we send, including account verification, password resets, billing receipts, important service notices, and (if you opt in) marketing communications.

This list is current as of the "Last Updated" date above. We update it as our technology stack changes.

---

## Integration Partners

Integration partners are third-party services **you can connect** to AIDSTATION. Your relationship with them is governed by their own privacy policies and terms.

When you authorize an integration, you authorize specified data flows between the partner and AIDSTATION. Data flowing into AIDSTATION becomes subject to our Privacy Policy. Data flowing out to the partner becomes subject to their policies.

| Partner | Type of Integration | Data Direction | What's Shared |
|---|---|---|---|
| **Garmin Connect** | Fitness device platform | Incoming | Activities, heart rate, training data |
| **Strava** | Activity platform | Incoming and optional outgoing | Activities, performance data |
| **Wahoo** | Fitness device platform | Incoming | Activities, heart rate, training data |
| **Whoop** | Recovery and biometric platform | Incoming | HRV, sleep, recovery data |
| **Apple Health** | Health data aggregator | Incoming | Health and activity data, varies by your permissions |
| **Samsung Health** | Health data aggregator | Incoming | Health and activity data, varies by your permissions |

Integration availability is subject to change. You can authorize or revoke integrations at any time from **Settings → Integrations**.

### When You Revoke an Integration

Revoking an integration stops new data flows. Data we have already received remains in your AIDSTATION account and continues to be governed by our Privacy Policy. You can delete that data at any time using the standard data controls in your account.

---

## How We Choose Partners

We evaluate partners on:

- Demonstrated security practices and incident history
- Contractual commitments meeting or exceeding our obligations under this policy and applicable law
- Relevant certifications (SOC 2, ISO 27001, GDPR compliance documentation) where available
- Sub-processing chains we have reviewed
- Geographic location of processing and applicable data transfer mechanisms

For service providers in jurisdictions outside the US that send or receive data across borders, we rely on Standard Contractual Clauses or other appropriate transfer mechanisms.

---

## Changes to Our Partners

We update this page as we add, change, or remove partners.

Material changes that affect how your personal data is processed — for example, the addition of a new category of subprocessor, or a change in the location of data processing — are also reflected in our Privacy Policy. Where required, we notify users in advance.

You can request notification of subprocessor changes by emailing help@aidstation.pro.

---

## Contact

- **Email:** help@aidstation.pro
- **Postal:** AIDSTATION Pro, LLC, 509 Williams Avenue, Cleburne, TX 76033, United States
- **Website:** [www.aidstation.pro](https://www.aidstation.pro)

See our [Privacy Policy](./AIDSTATION_Privacy_Policy.md) for the full description of how we process data.

---

*Contact-address consolidation (v4, 2026-05-30): all email addresses use only the two approved addresses — `help@aidstation.pro` (user support, incl. data-rights requests) and `info@aidstation.pro` (formal/legal/security/DMCA). No other changes.*
