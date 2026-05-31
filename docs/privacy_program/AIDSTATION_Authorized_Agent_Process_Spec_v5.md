# AIDSTATION Authorized Agent Process — Design Spec

**Status:** v5 — DSR extension period in the response letter aligned to +60 days / two months (resolves D-126); v4 was the cross-reference unversioning cleanup
**Companion docs:** Privacy Policy §7, RoPA PA-09 (DSR fulfillment), Deletion Flow Spec, DPA Template §4.10 (return/deletion of vendor-held data), Breach Response Playbook §7–§8 (suspected-fraud escalation)
**Implements:** Decision #27 (authorized agent process), Decision #28 (identity verification), Decision #26 (30-day DSR response time)
**Lens applied:** May 30, 2026

---

## Lens Calibration Notes (v4)

This section names the positions in this spec most likely to attract counsel pushback or regulator scrutiny under the operator-favorable + lawful + single-global-rule lens. Counsel should be directed here on review.

1. **Agent identity verification is now mandatory at a baseline tier (§5.2), not optional.** v2 left agent identity verification optional for "routine" matters. That is operator-*unfavorable*: the catastrophic failure mode of an agent process is a fraudulent or social-engineered agent request producing wrongful disclosure or wrongful deletion of a user's data — a self-inflicted breach. The lens-correct position is the *stronger* verification posture, because CCPA (Cal. Civ. Code §1798.140(d), 1798.130) and GDPR Art. 12(6) both expressly permit verifying an agent's authority, and no applicable jurisdiction forbids it. The single global rule: always verify agent authority at the baseline tier; escalate to the heightened tier (§6) for deletion and sensitive-category requests. The only lawful constraint pulling the other way is CCPA's anti-friction rule against imposing *unreasonable* verification burdens that effectively deny a right — so the burden is placed on verifying the **agent**, while the **user** is verified through the low-friction account-control confirmation (§5.3), which CCPA explicitly contemplates.

2. **Authorization-document retention is split from DSR-log retention (§10), with documents purged to a hash after the defense window.** This is a genuine judgment call. Longer retention of signed authorization documents improves litigation/regulatory defense but is a standing breach surface (agent PII + user signatures) and an Art. 5(1)(e) storage-limitation exposure. The cost-benefit-weighted operator-favorable position — the same reasoning the Inactivity Spec applied to sensitive data — is: retain the **minimal DSR-log record** for the full defense window, but retain the **high-PII authorization document** only for the statutory record period, then reduce it to a one-way hash plus metadata that proves a valid authorization existed without holding the signature image. Counsel may prefer to retain full documents for the entire limitation period; if so, that is a single edit to §10.

3. **Default delivery destination is the user's account-of-record, not the agent (§5.6).** New in v3. An access/portability fulfillment delivered to an agent who later proves adverse to the user makes AIDSTATION the conduit of the harm. The operator-favorable + lawful position is to deliver to the user by default and to the agent only on explicit, separately-stated user authorization. CCPA permits delivering to the consumer; nothing requires delivery to the agent.

4. **Deceased-user and incapacity (POA) handling (§12.7–§12.8).** Post-mortem data rights are not harmonized — GDPR Recital 27 leaves them to member states (France, Spain, Italy grant them; most do not), CCPA applies only to living consumers, and most US law is silent. The operator-favorable + lawful single-global default is: **no affirmative post-mortem data rights except where a specific applicable law grants them**, default to account closure rather than disclosure of the deceased's data to relatives (disclosure can itself harm the deceased and third parties whose data is entangled), and require death + estate-authority documentation. For incapacity, where the user cannot perform the §5.3 confirmation, user-confirmation is replaced by heightened documentary verification of the POA/guardianship instrument plus narrowest-scope construction. Both are flagged for counsel because they touch jurisdiction-specific civil-capacity law.

5. **30-day DSR clock is the regulator-safe single-global number, not the operator-maximum (§5.5).** CCPA allows 45 days; GDPR allows one month. v3 keeps 30 days as the single cross-jurisdiction value rather than running the longer CCPA window where only CCPA applies, for the same reason the Inactivity Spec chose the regulator-safe middle: a single defensible global number beats a per-jurisdiction maximum that invites scrutiny. The lawful extension to 60 days for genuinely complex matters is preserved and made explicit.

---

## 1. Purpose and Scope

This spec defines how AIDSTATION accepts, verifies, and fulfills data-subject requests (DSRs) submitted by an authorized agent acting on behalf of a user. The process applies to all DSR types — access, portability, correction, deletion, restriction, objection — across jurisdictions.

The driver is the California Consumer Privacy Act (CPRA), which explicitly permits authorized agents. The same workflow generalizes to other jurisdictions that recognize agent-mediated requests (Colorado, Connecticut, Virginia, Utah, others) and to ad hoc requests from people acting under legal authority (guardians, attorneys-in-fact) where applicable law permits.

In scope:

- Intake channels
- Required documentation
- Verification workflow (agent identity + user authorization + user confirmation)
- DSR processing timing relative to direct requests
- Refusal grounds
- Logging
- Templates the user / agent receive

Out of scope:

- Deceased-user requests are not handled through the authorized-agent workflow (which is for living data subjects); they follow the minimal default in §12.8
- Court-ordered disclosure (legal process, not authorized-agent process)
- Internal-employee requests on behalf of users for support purposes (these are not third-party agent requests; they are internal data access governed by access control, not by this spec)

---

## 2. Inherited Decisions

| Item | Decision | Source |
|---|---|---|
| Documentation | Signed written authorization + direct confirmation from user | #27 |
| Agent ID | Optional verification of agent identity | #27 |
| Standard verification | Email confirmation for low-risk; additional check for deletion | #28 |
| DSR clock | 30 days (extendable to 60 with notice for complex) | #26 |

---

## 3. Intake Channels

Agents may submit requests via:

| Channel | Use | Notes |
|---|---|---|
| `help@aidstation.pro` | Primary | Monitored, ticketed |
| Postal mail to AIDSTATION Pro, LLC, 509 Williams Avenue, Cleburne, TX 76033, USA | Required for CCPA compliance | Use "Attn: Privacy Lead" |
| Web form at `aidstation.pro/privacy/agent-request` | Secondary | Lower friction; same workflow downstream |

The web form is preferred operationally because it captures structured fields. Email and postal mail are accepted because they are required by law in some jurisdictions and because some agents (law firms, advocacy groups) operate on traditional intake channels.

There is no in-app authorized-agent flow. Agents do not authenticate to the app on behalf of the user.

---

## 4. Required Documentation

To accept an agent request, AIDSTATION requires:

### 4.1 From the Agent

Mandatory:

- The agent's name and contact information (email and phone)
- The relationship to the user (e.g., "authorized agent under California Civil Code § 1798.140(d)")
- The specific request being made (access / portability / correction / deletion / etc.)
- The categories of data the request covers (full account or specific categories)
- The user's identifying information sufficient to locate the account (typically the account email; account ID if the user has provided it)
- Written authorization signed by the user (Section 4.3)

Optional but encouraged:

- Agent business identification (law firm registration, advocacy organization listing, etc.)

### 4.2 From the User

The user must directly confirm the agent's authority before AIDSTATION proceeds. This confirmation happens out-of-band (Section 5.3), not in the initial submission.

### 4.3 Signed Written Authorization

AIDSTATION provides a template (Section 11) but accepts any signed writing that contains:

- The user's full name
- The user's account email (or other identifying information sufficient to bind the authorization to the AIDSTATION account)
- The agent's name and contact information
- A clear statement of authorization (e.g., "I authorize [agent] to submit a [type] request to AIDSTATION on my behalf")
- The scope of the authorization (specific request or ongoing)
- The user's signature and date

Electronic signatures are acceptable. Notarization is not required.

### 4.4 What We Do Not Accept

- Verbal authorization
- Authorization where the user is identified only by name and no AIDSTATION-specific identifier (we cannot locate the account)
- Open-ended authorizations with no scope (we treat as scoped to the specific request mentioned)
- Authorizations dated more than 12 months prior to submission (unless the request is part of an ongoing, documented matter)

---

## 5. Verification Workflow

### 5.1 Intake

Within 3 business days of receipt:

1. Acknowledge receipt to the agent and to the user's account email (Section 11).
2. Begin verification.
3. Start the 30-day DSR clock.

### 5.2 Agent Verification (Mandatory baseline; heightened tier for deletion / sensitive)

**v3 lens change:** agent identity verification is no longer optional. v2 left it optional for "routine" matters; that left a social-engineering gap that runs against the operator's own interest (see Lens Calibration Note 1). Every agent request is verified at the baseline tier before processing. Deletion and sensitive-category requests escalate to the heightened tier (§6).

**Baseline tier (all agent requests):**

- Confirm the agent's identity by replying to the request through the agent's own listed channel (a callback to the listed phone number, or a confirmation reply to the listed email address that the agent must acknowledge) — establishing that the contact details belong to a reachable party, not just an assertion in the submission.
- Record the verification step and its outcome in the DSR log (§10).

**Heightened tier (deletion, or any sensitive-category data — see §6):**

- A live callback to the agent's listed phone number to confirm the request.
- Verification of the agent's stated affiliation where claimed (e.g., bar registration for an attorney; organizational listing for an advocacy group).
- For an attorney submitting on firm letterhead in lieu of the user template, confirmation of the attorney's active registration.

AIDSTATION may apply the heightened tier to any request, at its discretion, where the agent's contact information is anomalous (free email with no verifiable presence) or where a single agent's request volume shows abuse patterns.

This places the verification burden on the **agent**, not the user. The user's identity is established through the low-friction account-control confirmation in §5.3, which is the least-burdensome lawful method and avoids CCPA's prohibition on imposing unreasonable identity-verification burdens that effectively deny a consumer's right.

### 5.3 User Confirmation (Required)

Always required, regardless of request type. AIDSTATION sends an email to the user's account-of-record email:

> Subject: Confirm a request submitted on your behalf
>
> Hello,
>
> We received a request to [access / delete / etc.] data associated with your AIDSTATION account. The request was submitted by [agent name] on [date] and authorized by you in writing dated [date].
>
> **If you authorized this request:** click the button below to confirm. We will then process the request.
>
> [Confirm request]
>
> **If you did not authorize this request:** click the button below. We will not process the request and will investigate.
>
> [I did not authorize this]
>
> If you do nothing within 15 days, we will treat the request as unverified and not process it. The agent and you will both be notified.
>
> — The AIDSTATION privacy team

The confirmation link is a one-time token tied to the request, expires in 15 days, and requires the user to be logged in to the account or to authenticate via email magic link.

### 5.4 Verification Outcomes

| User Action | Outcome |
|---|---|
| Confirms within 15 days | Verification complete; processing proceeds |
| Denies authorization | Request is refused; both agent and user notified; suspected-fraud workflow may trigger (Section 8) |
| No response within 15 days | Request is refused as unverified; both agent and user notified |
| User confirms but the agent verification (if invoked) failed | Request is held pending agent verification resolution; user is notified |

### 5.5 The 30-Day Clock vs. The 15-Day User Window

If the user confirms within 5 days, AIDSTATION has 25 days remaining on the 30-day clock. If the user confirms on day 14, AIDSTATION has 16 days. In a complex case, the 30-day clock may be extended to 60 with notice to both the agent and the user.

If the user has not confirmed by day 25 of the DSR clock, AIDSTATION sends a reminder to the user and notifies the agent that the request is at risk of being refused for non-verification.

**Single-global-rule rationale (v3).** The 30-day substantive-response window is the regulator-safe single value, not the operator-maximum. CCPA permits 45 days and GDPR permits one month; rather than running the longer CCPA window where only CCPA applies, AIDSTATION uses one defensible global number (30 days) calibrated to the tightest applicable framework (see Lens Calibration Note 5). The lawful extension to 60 days is preserved for genuinely complex matters and is invoked with written notice to both the agent and the user, stating the reason for the extension. The clock starts on receipt; time spent awaiting user confirmation is part of the window, which is why the §5.3 confirmation is time-boxed to 15 days against a 30-day clock.

### 5.6 Delivery Destination Default

**v3 lens addition.** Where a request produces output to be delivered (access copy, portability export), the default delivery destination is the **user's account-of-record**, not the agent. The agent receives notice that the request is complete; the user receives the data.

Delivery to the agent occurs only where the user's signed authorization (§4.3) or the §5.3 confirmation **explicitly** states that the output may be delivered to the agent. A general authorization to "submit a request on my behalf" is not, by itself, authorization to receive the user's data — these are construed separately (consistent with the narrowest-scope rule in §4.4 and §12.4).

Rationale: an access or portability fulfillment delivered to an agent who later proves adverse to the user makes AIDSTATION the conduit of the resulting harm. Delivering to the user by default is operator-favorable (removes that conduit risk), lawful (CCPA permits delivery to the consumer; nothing requires delivery to the agent), and requires no per-jurisdiction variant.

---

## 6. Sensitive-Category Considerations

For requests touching sensitive-category data (health, biometric):

- The heightened agent-verification tier (Section 5.2) applies — a live callback and affiliation check, not just the baseline contact confirmation.
- The user confirmation email is more explicit about which categories are in scope.
- If the request is for deletion of sensitive-category data only, the user is given an in-app option to perform the deletion themselves and is informed that they may prefer to do so directly.

---

## 7. Deletion Requests Via Agent

Deletion requests submitted via agent follow the same cooling-off and cascade model as self-service deletion (Deletion Flow Spec). Differences:

- The 30-day cooling-off begins when verification completes, not when the agent first submits.
- During cooling-off, the user can cancel the deletion by logging into the app — same mechanism as self-service.
- The agent is notified of both the start of cooling-off and the completion of deletion (or cancellation).
- The Deletion Flow Spec inventory (Section 6 of that spec) applies. Crowdsourced contributions are unlinked; aggregates survive.

If the agent is requesting deletion of less than the full account, the same v1 limitation applies: full-account-only at launch. The agent is informed that AIDSTATION does not support category-level deletion at v1 and is asked whether to proceed as full-account deletion or to withdraw the request.

---

## 8. Refusal Grounds

AIDSTATION may refuse an agent request when:

| Ground | Action |
|---|---|
| Authorization document is missing, unsigned, or insufficient | Refuse; advise agent to resubmit with adequate documentation |
| User cannot be located in our records | Refuse; advise agent that no account matches the identifiers provided (this is not a confirmation of non-existence — see 8.1) |
| User denies authorization | Refuse; trigger fraud investigation (Section 8.2) |
| User does not confirm within 15 days | Refuse as unverified; both parties notified |
| Agent has filed an unusual volume of requests showing patterns of abuse | Refuse and consult counsel |
| Legal hold on the account | Refuse for deletion; access requests may still proceed with scope limited by the hold order |
| Request is for data we do not hold | Respond truthfully (the request is fulfilled by saying "we do not have what you have asked for") |

### 8.1 Non-Existence Responses

If we cannot find an account, the response to the agent is intentionally neutral:

> We have not been able to locate an AIDSTATION account matching the identifiers you provided. If you believe this is in error, please verify the account email or other identifying information with the user and resubmit.

We do not affirmatively say "this person has no AIDSTATION account." That would itself be a disclosure about the user (i.e., that they are not a customer) that the agent may not be authorized to receive.

### 8.2 Fraud Investigation

If the user denies authorization:

1. The request is refused immediately.
2. The user's account is flagged for review (no automatic lock, but a privacy team review).
3. The agent's contact details are added to a watchlist for repeated patterns.
4. If the denied authorization document itself shows signs of forgery (mismatched signature, forged email headers), legal counsel is consulted. `AIDSTATION_Breach_Response_Playbook` is invoked where the incident represents a data-handling concern beyond a single request — a forged-authorization attempt that touches Personal Data is assessed as a potential Security Incident under that playbook's §5–§7.

---

## 9. CCPA-Specific Notes

CCPA imposes specific requirements that drive much of this spec:

- **Permission for agents:** A business "shall not require a consumer to verify their identity directly with the business" — but may require the business to verify both the agent's authority and (separately) the consumer's identity. Our process meets both requirements via Sections 4.3 and 5.3.
- **Notice to agent:** All agent communications include the user's account email cc'd. The user is always in the loop.
- **No fee:** CCPA prohibits charging for DSR fulfillment in most cases. We do not charge.
- **Recordkeeping:** Records are retained for the period required by CCPA (24 months minimum). See Section 10.

### 9.1 California-Resident Specifics

Agents acting on behalf of California residents specifically may use power-of-attorney documents in lieu of the AIDSTATION authorization template. We accept these provided they meet the requirements in Section 4.3.

### 9.2 Generalization to Other States

Colorado, Connecticut, Virginia, Utah, and others have analogous (and in some cases identical) authorized-agent provisions. The CCPA-shaped workflow satisfies these by being more permissive than the strictest state. No state-specific variation in the workflow is required at v1.

---

## 10. Logging

Every authorized-agent request generates a record in the `dsr_requests` table:

| Column | Notes |
|---|---|
| `request_id` | UUID |
| `request_type` | `access`, `portability`, `correction`, `deletion`, `restriction`, `objection` |
| `submitted_by` | `direct` or `agent` |
| `agent_name`, `agent_email`, `agent_phone` | If agent-submitted |
| `agent_authority_doc_id` | Reference to the stored authorization document |
| `user_id` | If located |
| `user_account_email` | At time of submission |
| `submitted_at`, `verified_at`, `completed_at` | Timestamps |
| `outcome` | `fulfilled`, `refused`, `withdrawn`, `unverified` |
| `outcome_reason` | If refused |
| `jurisdiction_basis` | E.g., `CCPA`, `GDPR`, `LGPD` |
| `complexity_extension` | Boolean (30 → 60 day extension flag) |

### 10.1 Retention (v3 — split model)

**DSR-log record** (the `dsr_requests` row above — minimal PII): retained for the full defense window. The window is the longer of (a) the CCPA 24-month recordkeeping floor and (b) the limitation period for a claim that could arise from the request's handling. AIDSTATION sets a single global default of **6 years** for the log record, which covers the longest commonly applicable contract/statutory limitation periods without per-jurisdiction tuning. This is operator-favorable for defense (proof that a request was handled correctly), lawful (accountability records are expected under both CCPA and GDPR Art. 5(2)), and minimal-PII so the retained surface is small.

**Authorization document** (the signed instrument — agent PII + the user's signature, a higher breach surface): retained for **24 months** (the CCPA record floor), then reduced to a one-way hash of the document plus structured metadata (document type, signer name, signature date, scope, verification outcome). The hash + metadata proves a valid authorization existed and what it covered, without holding the signature image indefinitely.

Rationale for the split (see Lens Calibration Note 2): the authorization document's marginal defense value past the statutory record period is low — agent-request complaints surface quickly — while its breach-surface and storage-limitation liability are ongoing. Reducing it to a hash after 24 months keeps the proof and drops the liability. Counsel may prefer to retain full documents for the entire 6-year window; that is a single edit to this section if so.

### 10.2 Storage

Authorization documents and their post-24-month hashes are stored in encrypted object storage with access limited to the privacy team. Where the document or any DSR output is held by a processor (storage vendor, support-platform vendor), the processor is bound by the No-Secondary-Use and return/deletion terms of `AIDSTATION_DPA_Template` §4.10 and §4.12.

---

## 11. Templates

### 11.1 User Authorization Template

A downloadable template at `aidstation.pro/privacy/agent-authorization-template`:

> # Authorization for Authorized Agent
>
> I, [user full name], with an AIDSTATION account associated with the email address [user account email], hereby authorize:
>
> [Agent name]
> [Agent contact email]
> [Agent contact phone]
>
> to submit the following data-subject request to AIDSTATION on my behalf:
>
> [ ] Access (copy of my data)
> [ ] Portability (machine-readable export)
> [ ] Correction
> [ ] Deletion
> [ ] Restriction of processing
> [ ] Objection to processing
>
> Scope:
> [ ] Full account
> [ ] Specific categories: ______________________
>
> This authorization is valid for the specific request above and expires 12 months from the date below unless I withdraw it sooner.
>
> Signed: ____________________ Date: ____________
>
> [User signature]

### 11.2 Intake Acknowledgement (to Agent)

> Subject: We received your privacy request on behalf of an AIDSTATION user
>
> Hello,
>
> We have received your request submitted on behalf of an AIDSTATION user on [date]. Reference number: [request_id].
>
> We are now verifying the request. We have sent a confirmation request to the user's account-of-record email. We will not process the request until the user confirms.
>
> We will respond fully within 30 days of receipt (today: [submitted_at + 30]). If the matter is complex, we may extend by up to a further 60 days (two months) with notice to you and the user.
>
> — The AIDSTATION privacy team

### 11.3 Intake Notice (to User)

Section 5.3 covers this.

### 11.4 Refusal Notice (to Agent)

> Subject: We are unable to process the privacy request — reference [request_id]
>
> Hello,
>
> We are unable to process the request you submitted on [date]. Reason: [refusal reason].
>
> If you believe this refusal is incorrect, you may [resubmit with corrected documentation / contact us with additional information / etc.]. The user may also file a direct request from within their AIDSTATION account at any time.
>
> — The AIDSTATION privacy team

### 11.5 Fulfillment Notice

Sent to both agent and user upon completion:

> Subject: Privacy request completed — reference [request_id]
>
> Hello,
>
> The privacy request submitted on [date] has been completed. [Specifics: data delivered / account deleted / correction applied / etc.]
>
> The user has been notified of this outcome at the account-of-record email.
>
> — The AIDSTATION privacy team

---

## 12. Edge Cases

### 12.1 Agent Requests Across Multiple Users

An agent representing multiple users files separate requests, one per user, even if the requests are identical. The verification workflow runs per user. We do not bulk-process agent requests across users — each is its own DSR.

### 12.2 User Authorization Mid-Process

A user may revoke an authorization while a request is in flight. Revocation is honored: the in-flight request stops, the agent and user are notified, and any data already gathered (e.g., export prepared but not yet delivered) is destroyed.

### 12.3 Agent Becomes Unreachable

If the agent stops responding mid-verification and the user has confirmed, AIDSTATION may continue processing. The user is still the data subject and is in the loop. The agent ceasing to respond does not invalidate the user's confirmed authorization.

### 12.4 Conflicting Information

If the agent's request and the user's confirmation disagree on the scope (e.g., agent says "delete account," user confirms "delete only health data"), the narrower interpretation is honored and both parties are notified.

### 12.5 Agent Identity Cannot Be Verified

Agent verification is mandatory at the baseline tier for every request (§5.2). Where verification fails — the agent cannot be reached at the listed channel, or refuses to complete the heightened tier for a deletion / sensitive-category request — the request is refused. The user is informed and may file directly.

### 12.6 Parent or Guardian of a Minor Accountholder

AIDSTATION's minimum age is 16 (Privacy Policy §11; T&C), so accountholders aged 16–17 exist and are minors in most jurisdictions. A parent or legal guardian may act as an authorized agent for such an accountholder where applicable law grants them that authority.

- Required documentation: proof of the parent/guardian relationship (and of guardianship where the relationship is not parental), in addition to the §4 documentation.
- User confirmation (§5.3): the minor controls the account, so the account-control confirmation still runs against the minor's account-of-record. This is deliberate — it prevents a non-custodial adult from exercising rights over a minor's account without the minor's knowledge, while still honoring a genuine custodial request the minor assents to.
- Where the minor lacks capacity to perform the confirmation, fall to §12.7 (documentary verification of guardianship + narrowest scope).
- This is distinct from a report that an under-16 has created an account, which is handled by the Privacy Policy §11 removal process, not this spec.

### 12.7 Power of Attorney / Attorney-in-Fact / Incapacity

A person acting under a power of attorney, conservatorship, or comparable legal authority is treated as an authorized agent under the **legal-authority branch**. The POA or guardianship instrument is accepted in lieu of the §4.3 user template (consistent with §9.1).

- Where the user is capable of confirming, the §5.3 user confirmation still runs — legal authority to act does not remove the user from the loop where they can still respond.
- Where the user is incapacitated (the usual reason a POA is invoked) and cannot perform the §5.3 confirmation, user confirmation is replaced by: (a) heightened documentary verification of the instrument and its current validity, (b) the heightened agent-verification tier (§5.2), and (c) narrowest-scope construction of the granted authority.
- The capacity question and the validity of a given instrument are jurisdiction-specific civil-capacity matters; ambiguous instruments are escalated to counsel rather than resolved operationally. This is flagged for counsel (Lens Calibration Note 4).

### 12.8 Deceased Accountholder

Requests concerning a deceased user are **out of the authorized-agent process** (that process is for living data subjects) and are handled under this minimal default:

- AIDSTATION recognizes **no affirmative post-mortem data rights except where a specific applicable law grants them.** Post-mortem rights are not harmonized — GDPR Recital 27 leaves them to member states (France, Spain, and Italy grant them; most do not), CCPA applies only to living consumers, and most US law is silent.
- Default action on a verified death is **account closure**, not disclosure of the deceased's data to relatives or the estate. Disclosure can itself harm the deceased's privacy interests and expose third parties whose data is entangled in the account (training partners, teammates, contacts).
- Required before any action: documentation of the death and of the requester's legal authority over the estate.
- Where a specific applicable law grants an estate representative a post-mortem right, AIDSTATION honors that right to the extent the law requires and no further, applying narrowest-scope construction.
- This default is flagged for counsel (Lens Calibration Note 4) and supersedes the v2 "separate process, not yet drafted" placeholder in §1.

---

## 13. Open TBDs

- Volume thresholds for "unusual" agent activity (operational tuning post-launch)
- Encryption-key management for authorization-document storage (operational; storage location is now specified — encrypted object storage, privacy-team access only, §10.2)
- Whether to publish request-volume statistics annually (transparency report — recommended)
- Coordination with the to-be-built customer support platform (when chosen) for agent intake routing

(The AIDSTATION legal entity and registered address are now specified in §3 — AIDSTATION Pro, LLC, Cleburne, TX — resolving the v2 placeholder.)

### 13.1 v3 Follow-Ups (from this lens pass)

- **Authorization-document hash job (§10.1):** implement the 24-month reduction of authorization documents to a one-way hash + metadata. Until built, full documents persist; not a launch blocker, but the storage-limitation benefit is unrealized until the job runs.
- **Delivery-default plumbing (§5.6):** the fulfillment workflow must default access/portability output to the user's account-of-record and gate agent delivery on an explicit authorization flag. Confirm the §4.3 template and the §5.3 confirmation capture that flag.
- **Template update for delivery destination:** the §11.1 user authorization template does not currently include an explicit "deliver output to the agent" checkbox. Add one so §5.6 has a clean capture point. (Deferred to a templates touch; flagged here.)
- **Deceased / incapacity process detail (§12.7–§12.8):** the defaults are set, but the operational steps (death-documentation standard, estate-authority verification) are sketched, not specified. Specify on first real occurrence or when counsel reviews the post-mortem position.

---

## 14. Gut Check

**Risks**

- The 15-day user confirmation window is generous and creates a long verification tail. Agents working on tight legal deadlines (e.g., 30-day class-action discovery windows) may find this frustrating. The alternative — shorter user windows — risks treating legitimate users who travel or are away from email as unauthorized. The 15-day choice is defensible but worth a re-evaluate after we see actual agent volume.
- The "no in-app agent flow" choice is deliberate but means an agent cannot easily verify they are dealing with the same account the user claims. We rely on the user's account email to bridge agent and user. If a user has multiple accounts (different emails), the agent must identify which one — adds friction but is correct.
- Authorized agent volume in the consumer SaaS space is generally low. The biggest near-term risk is that we over-engineer the process for a problem that occurs once a quarter, while under-engineering the direct self-service flow that occurs daily. Resource allocation: this spec's implementation can be lightweight (email templates + a ticketing workflow) rather than a custom UI.

**What might be missing**

- Coordination with legal counsel on the refusal-grounds language is worth a review pass before this goes live. Refusals are where most regulatory complaints come from.
- A standing decision on whether an attorney's letter on firm letterhead counts as adequate "signed authorization" without the formal template would be helpful — many real-world agent requests come in this form. Recommendation: yes, accept attorney letters on firm letterhead as authorization documents, subject to confirming with the user.
- The fraud investigation workflow (Section 8.2) is sketched but not specified. If forged authorizations become a real volume, this needs more operational detail.

**Best argument against the current trajectory**

The authorized-agent process is a real legal requirement, but it is also a low-volume operational item that adds significant documentation and process burden compared to what most consumer SaaS companies actually face. A simpler v1 would be: a documented privacy@ intake, a manual checklist, and no public agent template — and we generate the workflow when we get our first agent request. The downside is that operating reactively makes the first response slower and risks the user-facing email being inconsistent. The upside is we are not investing in an infrastructure for a use case that may produce 1–2 requests in our first year. Worth a deliberate decision on whether to ship the full template-and-workflow at v1 or to defer the formal infrastructure until the first real request, while ensuring the underlying decisions are documented.

---

### 14.1 Gut Check — v3 Lens Pass Addendum

**Risks introduced by v3.**

- Making baseline agent verification mandatory (§5.2) adds friction and a manual step to every agent request. Given the genuinely low volume of agent requests in consumer SaaS, this is cheap, but it does mean no agent request is fully self-service. That is the intended trade — the failure mode it closes (social-engineered wrongful disclosure/deletion) is far more expensive than the friction.
- The §10.1 retention split assumes the hash-reduction job actually gets built. If it does not, v3's storage-limitation benefit is theoretical and the spec describes a control that does not exist — worse than honestly stating "full documents retained for 6 years." The §13.1 follow-up must land before this can be claimed as implemented.
- The §12.8 deceased default (closure, not disclosure) is the most likely counsel pushback point. A grieving family asking for a deceased relative's training history is sympathetic, and "we closed the account and disclosed nothing" can read as harsh. The position is defensible on third-party-data and deceased-privacy grounds, but counsel and possibly product should sign off on the user-facing framing.

**What might be missing.**

- v3 does not add a user-facing explanation of why agent verification now always happens; an agent on a deadline who hits the mandatory callback may complain. A one-line note in the §11.2 intake acknowledgement explaining the verification step would soften that. Deferred to a templates touch.
- The interaction between §5.6 (deliver to user by default) and a legitimate access request where the *whole point* is that the agent — e.g., the user's lawyer — needs the data is real. The explicit-authorization gate handles it, but only if the §11.1 template captures the flag (the §13.1 follow-up). Until then, §5.6 defaults to user-delivery and the agent re-requests with explicit authorization, which is safe but adds a round trip.

**Best argument against the v3 calibration.**

The v2 "optional verification for routine matters" stance was arguably already lawful and lower-friction, and the volume of fraudulent agent requests against a 16+-only endurance-coaching app is plausibly near zero. v3 spends real operational friction to close a gap that may never be exploited. The counter — and the reason the lens points at mandatory verification — is that the cost of the friction is trivial at this volume while the cost of a single social-engineered deletion or health-data disclosure is catastrophic and exactly the kind of asymmetric downside the operator-favorable lens is meant to weight against. The calibration stands.

---

## 15. Change Log

| Version | Date | Changes | Author |
|---|---|---|---|
| v1 | Batch 4 cycle | Initial draft of the authorized-agent process — intake channels, required documentation, verification workflow, refusal grounds, logging, templates, edge cases. Status label "Draft v1, Batch 4." Companion-doc references pointed at PP / RoPA / Deletion Flow Spec. | Privacy Lead |
| v2 | Batch cycle | File bumped to v2 in filename; internal status label remained "Draft v1, Batch 4." No substantive changes recorded. | Privacy Lead |
| v3 | May 30, 2026 | Tier 2 lens pass (operator-favorable + lawful + single global rule). Internal status reconciled to v3. Companion-doc references updated to PP, RoPA, Deletion Flow Spec; DPA Template and Breach Playbook cross-refs added. Lens Calibration Notes added (five counsel-risk callouts). Substantive lens edits: **§5.2 agent identity verification changed from optional to mandatory baseline tier, with heightened tier for deletion / sensitive-category requests**; **§5.6 added — default delivery destination is the user's account-of-record, agent delivery only on explicit authorization**; **§10 retention split into §10.1 (DSR-log record retained 6 years for defense) and authorization document retained 24 months then reduced to a one-way hash + metadata**, §10.2 storage bound to DPA v3 §4.10/§4.12; **§12.6–§12.8 added — parent/guardian of a 16–17 minor accountholder, POA/incapacity, and deceased accountholder, with lens-calibrated defaults (closure-not-disclosure for deceased; no affirmative post-mortem rights except where a specific law grants them)**; §5.5 single-global-rule rationale paragraph added (30-day clock as regulator-safe number, lawful 60-day extension preserved); §6 updated to reference the heightened verification tier; §8.2 fraud escalation cites Breach Playbook §5–§7; §1 out-of-scope deceased placeholder replaced by §12.8 pointer; §13 Open TBDs updated (entity-name item resolved) with §13.1 v3 follow-ups; §14.1 Gut Check v3 addendum added. (Privacy Program Backlog: Tier 2 lens batch — Authorized Agent Spec lens pass per Track A G2 Closing Handoff §5.5, D-120.) | Privacy Lead |
| v5 | May 30, 2026 | Resolves D-126. The DSR response-letter template extension clause changed from "an additional 30 days" to "up to a further 60 days (two months)," matching the Privacy Policy §9.1/§14.2 commitment and the spec's own DSR-clock table (the operator-favorable and GDPR Art. 12(3)-aligned position). No other changes. | Privacy Lead |
| v5 | May 30, 2026 | Contact-address consolidation to the two approved addresses: `help@aidstation.pro` for user support (including privacy / data-rights requests) and `info@aidstation.pro` for formal, legal, security, and DMCA correspondence. No other changes. | Privacy Lead |

---

*Cross-reference cleanup (v4, 2026-05-30): inline references to companion documents were converted to unversioned logical names per Rule #12, so they no longer go stale when a companion document is revised. No substantive content changes. See `Privacy_Program_Consistency_Sweep_Report_v1.md`.*

