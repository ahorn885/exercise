# AIDSTATION AI Training Onboarding Callout — Copy and UX Spec

**Status:** v2 — cross-reference unversioning cleanup; draft for counsel review (no substantive change since v1)
**Owner:** Privacy Lead (copy and constraints) + Product (UX implementation)
**Date:** May 19, 2026
**Purpose:** Specifies the in-product onboarding callout that surfaces, at signup, how AIDSTATION uses new-user training data to train its coaching AI, and how the user can opt out. This callout is the salience mechanism that backs the §4.3 reasonable-expectation argument in `AIDSTATION_LIA_PA15` and the R-04 mitigation in `AIDSTATION_DPIA_PA15`.
**Binding constraints from companion docs:**
- LIA §3.3 — honest framing (no dressing the practice as a user benefit; controller-side considerations stated honestly).
- LIA §4.3 — salience at signup (category norms + disclosure-quality bridge).
- LIA §4.5.2 — irreversibility of past contributions to trained model weights, in plain language, not buried.
- LIA §8.1 — default opt-in for new users with continuous opt-out availability; counter-position of default opt-out considered and rejected.
- Memory #13 — single global rule. No per-jurisdiction copy variants in v2.

---

## 1. Purpose and Scope

### 1.1 What this callout exists to do

The callout is the principal salience mechanism by which AIDSTATION informs new users, at the time of account creation, that:

1. The user's training data will be used by default to train AIDSTATION's coaching AI.
2. The user can turn this off at any time, including immediately, from the same screen.
3. Data already incorporated into trained model weights cannot be removed from those models after the fact, even on opt-out or account deletion.

### 1.2 What this callout does not do

- It does not substitute for the Privacy Policy or Terms — those remain the authoritative disclosures.
- It does not capture Art. 9(2)(a) explicit consent for special-category data. That is a separate flow.
- It is not a marketing surface or a feature pitch. It is a salience and rights-disclosure surface.

### 1.3 Why a callout instead of inline-disclosure-only

`AIDSTATION_LIA_PA15` §4.3 argues that a reasonable user expects AI services to train on user-supplied data (category-norms anchor) and that AIDSTATION's disclosure quality is sufficient to confirm that expectation. The disclosure-quality leg of that argument depends on something more than a Privacy Policy clause that most users do not read. The onboarding callout is that something more.

---

## 2. UX Placement

### 2.1 When the callout is shown

- After the account is created (i.e., after email/password is established and the account exists).
- Before the first plan generation or any first use of AI-driven features.
- Once. The callout is not re-shown except per §5 re-prompt conditions.

### 2.2 What screen the callout occupies

- **Its own dedicated screen.** Not an interstitial during an unrelated flow. Not a banner over a busy page. Not a Terms-of-Service scroll-acknowledge step.
- The screen contains the callout copy, the opt-out toggle (default on / "training enabled"), a link to Privacy Policy §4, and a single primary action button to continue.

### 2.3 What the screen does not do

- It does not require the user to acknowledge a checkbox before continuing. Continuing past the screen is the acknowledgment.
- It does not scroll-gate (no "scroll to bottom to enable continue").
- It does not gate continuation on the toggle position — the user may continue with the toggle in either state.
- It does not auto-advance after a timer.

### 2.4 Screen elements (component-level)

| Element | Behavior |
|---|---|
| Headline | One line, ≤8 words, plain language. |
| Body copy | The selected copy lane from §3, verbatim. |
| Toggle | Labeled "Use my data to improve coaching AI" or similar (final label per Product). Default state: on. Toggling off here is equivalent to setting the account-settings opt-out toggle (D-93) to off — the state is propagated to a single source of truth. |
| Link | "Learn more about how we use your data" → Privacy Policy §4. Opens in-app or in a new tab; does not exit the signup flow. |
| Primary action | "Continue" (or product-standard signup-flow continue label). |
| Secondary action | None. No "skip" button — there is nothing to skip. |

---

## 3. Copy Candidates

Three lanes are written below. Lane A is recommended. Final selection is a counsel review item before D-96 sign-off (per `AIDSTATION_PreFlight_Checklist_PA15` §4.3 condition D-3).

### 3.1 Lane A — Plain transparent (recommended)

> AIDSTATION uses your training data to improve our coaching AI, for you and future athletes. You can turn this off at any time, including right now.
>
> Data that has already been used in models we have built cannot be removed from those models afterward, even if you turn this off or delete your account.

**Why this is the recommended lane.**
- Plain language. No legal hedging beyond what is honest about irreversibility.
- Acknowledges the irreversibility of trained weights up front, not buried (LIA §4.5.2).
- Does not dress the practice as a user benefit (the "for you and future athletes" is descriptive — the data does in fact serve both — but it is not framed as a thing the user is getting in exchange).
- Single global rule — works in GDPR jurisdictions, US states, and elsewhere without per-jurisdiction variation.
- Names the opt-out and its immediacy ("including right now").

### 3.2 Lane B — Matter-of-fact, short

> AIDSTATION trains its coaching AI on your data by default. Toggle off here if you'd prefer we didn't.
>
> Models we have already trained cannot be retrained to exclude data that was used to build them, even if you turn this off or delete your account later.

**Why not the recommended lane.**
- Terser. Easier to read. Loses the small amount of contextual framing that helps a non-lawyer user understand why the default is opt-in.
- "Trains its coaching AI on your data" without a why makes the practice look more aggressive than Lane A's framing. That is not necessarily bad (and is arguably more honest), but it raises the rate of opt-outs and degrades the §4.3 reasonable-expectation argument by reducing the disclosure's clarity about what the practice actually accomplishes.
- Defensible. Tied for second choice with Lane C; usable if Lane A is rejected at counsel review.

### 3.3 Lane C — Legal-aligned, longer

> AIDSTATION processes the training data you provide to train and improve our coaching AI under our legitimate interest in delivering and improving the service (see Privacy Policy §4).
>
> By default, your data is included in model training. You have an unconditional right to object — toggle off below, or change this any time in account settings. Your data will be excluded from future training datasets.
>
> Data already incorporated into trained models cannot be removed from those models after the fact. This applies even after you opt out or delete your account.

**Why not the recommended lane.**
- Legal-register copy. Names the Art. 6(1)(f) basis and the right to object explicitly. Some counsel will prefer this — particularly EU/UK counsel — because it pre-empts a regulator argument that the disclosure was non-legal-register and therefore insufficient.
- Longer. Harder to read at signup speed. May reduce salience by appearing as boilerplate (a category-norm where legal copy is skimmed). The §4.3 argument can be weakened if the callout reads as Terms-shaped rather than as information.
- Use if counsel directs legal-register language at v2.

### 3.4 Copy that was considered and rejected

- Anything beginning with "We respect your privacy" or similar reassurance opener — fails LIA §3.3 honest framing standard.
- Anything framing the practice as a user benefit alone ("Help us help you with better coaching") — fails LIA §3.3.
- Anything that buries the irreversibility statement (e.g., behind a "Learn more" link only) — fails LIA §4.5.2 salience requirement.
- Anything with per-jurisdiction variation in the visible copy (e.g., "If you are in the EU, …") — fails Memory #13 single-global-rule design. (The legal basis itself differs by jurisdiction; the disclosure language does not need to.)

---

## 4. Default State

- Toggle default: **on** (training enabled).
- Rationale: clean Art. 6(1)(f) legitimate-interest position per LIA §8.1. The counter-position (default opt-out for new users) was considered and rejected at LIA §8.1; the counter-position would functionally operate as consent for new users while the LI basis is invoked, producing a worse defensive position than the clean default-on.
- The user may toggle off on this screen and continue with training disabled from account creation.
- Toggle position at the moment of "Continue" is what is recorded for the account.

### 4.1 What "recorded" means

- Single source of truth in the account record: a boolean `ai_training_opt_in` with a `last_changed_at` timestamp.
- Initial signup state and timestamp are logged (D-93 logging requirement). The signup callout flow records that the value was set via the signup callout (vs. account settings) so analytics can attribute initial-state distribution to this screen.
- The same account-settings toggle (D-93) is the continuous opt-out mechanism after signup. They are not separate states.

---

## 5. Re-Prompt Behavior

The callout is **not re-shown** under normal operation. Once the user passes the screen at signup, the account state controls the behavior until the user changes it via account settings.

Re-prompt is required only in these situations:

| Trigger | Re-prompt content |
|---|---|
| Material change to AI training scope (new data categories, new training purpose, new processor in scope of PA-15) | A revised callout briefly stating the change, with toggle position preserved. User may re-toggle. |
| User account was created before this callout was deployed (migration cohort) | One-time backfill callout shown on next sign-in. Default position is the user's existing setting (or default-on if no setting exists). |
| Material legal-basis change (e.g., counsel directs migration from Art. 6(1)(f) to Art. 6(1)(a) consent) | New consent flow, not a callout re-prompt. Outside this spec. |

The callout is **not** re-shown:
- Periodically (no annual nudge).
- When the user has previously toggled off and is still toggled off.
- On marketing or feature-launch occasions.

---

## 6. Telemetry

### 6.1 What is recorded

- Toggle state at "Continue" (boolean).
- The fact that the signup callout was the source of the initial state (vs. account settings, vs. migration backfill).
- Timestamp.

### 6.2 What is not recorded

- Time spent on the screen.
- Whether the user clicked the Privacy Policy link.
- Any A/B testing of copy variants without a separate Privacy Lead sign-off — copy testing on this surface affects the §4.3 argument and requires explicit governance.

### 6.3 Aggregated reporting

- Weekly count of initial-state toggle positions (opt-in / opt-out at signup) is recorded as a single aggregate. Per `AIDSTATION_Aggregation_Suppression_Spec`, individual values below the N=25 suppression threshold are suppressed.
- The aggregate is used to monitor whether the default-opt-in posture is producing disproportionately high opt-out rates, which would be a signal to revisit the LIA §4.3 argument.

---

## 7. Accessibility

- Screen reader compatible. Headline, body, toggle state, and primary action are all reachable by keyboard / assistive technology.
- Toggle state is announced (e.g., "Use my data to improve coaching AI, switch, on" / "off").
- Text contrast meets WCAG 2.1 AA.
- No scroll-to-acknowledge gating.
- No timed auto-advance.
- The Privacy Policy link is descriptive ("Learn more about how we use your data"), not "click here".

---

## 8. Localization

- v1 is English only.
- Localization is deferred until launch readiness in non-English markets. When localized, the source-of-truth copy is the lane selected at v1; localized variants are translations of the same copy, not re-drafts.
- Single global rule applies to all localizations — same content, translated.

---

## 9. Open Items for Counsel Review

1. **Lane selection.** Recommendation is Lane A. Counsel may direct Lane C if legal-register language is preferred for EU/UK launch.
2. **"Toggle off" wording.** "Use my data to improve coaching AI" vs. "Allow AIDSTATION to train on my data" vs. another phrasing. The product label affects how users read the underlying practice. Product to propose; Privacy Lead to confirm against LIA §3.3.
3. **Migration cohort behavior.** §5 specifies a one-time backfill callout. If counsel directs that pre-deployment users were already covered by Privacy Policy disclosure and require no re-prompt, this can be removed; the cleaner posture is to surface it once to all users.
4. **Whether to require an affirmative tap on "Continue" with the toggle visible** (current design) vs. a more passive disclosure (e.g., toast notification). Current design is more salient and supports LIA §4.3 better; counsel may prefer it as-is.

---

## 10. Cross-Spec Touchpoints

| Document | Relationship |
|---|---|
| `AIDSTATION_LIA_PA15` §4.3 / §4.5.2 / §3.3 / §8.1 | Constraints on copy and default state. |
| `AIDSTATION_DPIA_PA15` §7.3 (R-04) | This callout is the R-04 mitigation surface. |
| `AIDSTATION_Privacy_Policy` §4 / §7 / §9 | Linked from the callout; authoritative disclosure. |
| `AIDSTATION_PreFlight_Checklist_PA15` §4.3 condition D-3 | This spec must be implemented and salience-tested before the pre-flight checklist can authorize the first scaled training run. |
| `Privacy_Program_Backlog_v2.md` D-93 | Account-settings toggle that this callout surfaces and writes to. |
| `AIDSTATION_Aggregation_Suppression_Spec` | N=25 floor for the aggregate reporting in §6.3. |

---

## 11. Change Log

| Version | Date | Changes | Author |
|---|---|---|---|
| v1 | May 19, 2026 | Initial copy and UX spec for the AI training onboarding callout (D-94). Three copy lanes drafted and ranked; Lane A recommended. Default-on per LIA §8.1. Single global rule applied — no per-jurisdiction copy. Open items deferred to counsel review. | Privacy Lead |

---

*Cross-reference cleanup (v2, 2026-05-30): inline references to companion documents were converted to unversioned logical names per Rule #12, so they no longer go stale when a companion document is revised. No substantive content changes. See `Privacy_Program_Consistency_Sweep_Report_v1.md`.*

