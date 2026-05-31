# AIDSTATION DMCA Designated Agent Process — Design Spec

**Status:** v4 — notice-record retention trigger aligned to "from final action" matching RoPA PA-16 (resolves D-128); v3 was the cross-reference unversioning cleanup
**Owner:** Privacy Lead (also serving as DMCA Designated Agent at v1)
**Last Updated:** May 19, 2026
**Companion docs:** `AIDSTATION_Terms_and_Conditions` (copyright section — pending consistency-pass edit), `AIDSTATION_Acceptable_Use_Policy` §4, `AIDSTATION_Privacy_Policy` (contact section), `AIDSTATION_RoPA` (PA-16 to be added in v3), `AIDSTATION_Deletion_Flow_Spec`, `AIDSTATION_DPIA_PA15`, `AIDSTATION_LIA_PA15`
**Closes:** D-78 (DMCA designated agent process — publication blocker for crowdsourced facility feature, Batch 7 §4)
**Backlog refs:** `Privacy_Program_Backlog_v1.md` D-99 through D-105

---

## 0. Scope and Status

This spec defines AIDSTATION's process for receiving, evaluating, and acting on notices of claimed copyright infringement under the United States Digital Millennium Copyright Act (DMCA), 17 USC §512, and for handling counter-notifications and repeat-infringer determinations.

The DMCA §512(c) safe harbor protects online service providers from secondary liability for user-uploaded infringing content, provided the provider designates an agent to receive infringement notices, registers that agent with the US Copyright Office, publishes the agent's contact information, acts expeditiously on valid notices, and maintains a repeat-infringer termination policy.

AIDSTATION currently has minimal user-generated-content exposure: raw conversational input is not retained (PP §7); profile data and feedback signals are not infringeable content. Exposure increases materially when the **crowdsourced facility database feature** ships (DPIA Template Appendix A item 6). This spec establishes the process *before* that exposure rather than reactively after the first notice.

**In scope.** US DMCA process; designated agent identity, registration, and publication; notice handling; takedown procedure; counter-notification; repeat-infringer policy; records retention.

**Out of scope.** Trademark infringement (separate process, not yet drafted); patent issues; right-of-publicity claims; defamation (handled under T&C content rules, not DMCA); full implementation of EU Digital Services Act Art. 16 — named in §9 for awareness; full DSA compliance is a separate workstream gated on EU launch.

**Posture.** This spec is calibrated to the most operator-favorable position permitted under §512 and applicable case law. Where the statute permits discretion, AIDSTATION retains discretion. Where the statute imposes an obligation, AIDSTATION meets it without going beyond it.

**Status of this document.** Draft for counsel review. Operational defaults below (72-hour typical takedown, discretionary repeat-infringer determination, statutory-minimum disclosures) are author judgments for counsel to confirm or revise.

---

## 1. Statutory Basis

### 1.1 US — DMCA §512(c) safe harbor

To qualify for the safe harbor, AIDSTATION must:

1. Designate an agent to receive notifications of claimed infringement [§512(c)(2)]
2. Register the agent with the US Copyright Office via the online directory [§512(c)(2); 37 CFR §201.38]
3. Make the agent's name and contact information available through the service [§512(c)(2)]
4. Maintain a policy of terminating repeat infringers in appropriate circumstances and inform subscribers of that policy [§512(i)(1)(A)]
5. Accommodate and not interfere with standard technical measures used by copyright holders [§512(i)(1)(B)]

The safe harbor only protects against secondary liability for user-uploaded content. AIDSTATION-generated outputs (training plans, coaching recommendations, AI-generated derivative works) are not user-uploaded content and are not within §512(c)'s scope; they are governed by separate IP analysis outside this spec.

### 1.2 Non-US equivalents — informational only

| Jurisdiction | Mechanism | Treatment in this spec |
|---|---|---|
| EU | Digital Services Act, Art. 16 notice-and-action | Required before EU launch; broader scope than DMCA (includes hate speech, illegal content beyond IP); separate workstream |
| UK | e-Commerce Regulations 2002, Reg. 19 | Similar to DSA; light obligation; covered by EU workstream |
| Canada | Copyright Modernization Act, s. 41.25–41.27 (notice-and-notice) | Light obligation: service provider forwards notices to user; no takedown obligation. Foldable into this process with a Canadian forwarding template. |
| Australia | Copyright Act safe-harbor reforms (limited scope) | Light obligation; addressable when launch is on the roadmap |

This spec implements the US DMCA only. Non-US equivalents are tracked and will be added as launch markets require.

---

## 2. Designated Agent

### 2.1 Identity

At v1, the Designated Agent is **the Privacy Lead in their DMCA-agent capacity**. The two roles are functionally separable but operationally combined at AIDSTATION's current size. The DMCA agent's responsibilities (receiving infringement notices, processing takedowns) are distinct from the Privacy Lead's privacy-program responsibilities; this spec governs only the DMCA role.

### 2.2 Contact information

| Field | Value |
|---|---|
| Designated Agent name | [Name — assigned at registration] |
| Title | DMCA Designated Agent |
| Address | AIDSTATION Pro, LLC, 509 Williams Avenue, Cleburne, TX 76033, United States |
| Email | `info@aidstation.pro` |
| Phone | [TBD — required by USCO directory; virtual number with business-hours routing acceptable] |

`info@aidstation.pro` is the canonical intake address. Physical mail to the registered address and the published phone number are also accepted, but email is the expected channel.

### 2.3 USCO registration

- **Registry:** US Copyright Office DMCA Designated Agent Directory (`dmca.copyright.gov`)
- **Cost:** $6 per registration, valid 3 years
- **Renewal:** Required every 3 years; lapse forfeits §512(c) safe harbor until renewed
- **Owner:** Privacy Lead is responsible for initial registration and renewal tracking; calendar reminder set at 30 months out
- **Trigger for initial registration:** Before the first user-generated-content surface ships in production, and no later than first beta release of the crowdsourced facility database

### 2.4 Publication

The agent's contact information must be available "through the service" (§512(c)(2)). At v1, publication is achieved by:

1. A dedicated public **DMCA Notices** page at `aidstation.pro/dmca`, listing agent contact and the procedural information required by §512
2. Reference link in the Terms and Conditions copyright section (pending consistency-pass edit)
3. Reference link in the website footer

This is sufficient under §512(c)(2). An in-app reference may be added once the in-app surface exists; it is not required.

---

## 3. What Counts as a Valid Notice

Under §512(c)(3)(A), a notice of claimed infringement must include all six of:

1. A physical or electronic signature of the complaining party (or person authorized to act for the owner)
2. Identification of the copyrighted work claimed to have been infringed — or a representative list, if multiple works are involved
3. Identification of the material claimed to be infringing, with information sufficient for AIDSTATION to locate it (URL, in-product path, or screenshot with context)
4. Contact information for the complaining party (address, phone, email)
5. A good-faith statement that the use is not authorized by the owner, agent, or law
6. A statement of accuracy, and a statement under penalty of perjury that the complaining party is authorized to act for the owner of the right claimed to be infringed

**Compliance triage.**

- A notice missing items **2, 3, or 6** is treated as **substantially non-compliant**. AIDSTATION may decline to act and request a corrected notice; the user whose content is alleged to infringe is not notified at this stage. AIDSTATION is under no obligation to chase down a substantially non-compliant notice.
- A notice missing items **1, 4, or 5** is treated as **technically non-compliant**. AIDSTATION may attempt to contact the complaining party for cure (per §512(c)(3)(B)(ii)) or may decline to act; the decision is at AIDSTATION's discretion based on the substance of the claim and the practical ability to resolve the defect.
- AIDSTATION may request additional information beyond the statutory minimum where reasonably necessary to evaluate the notice (e.g., proof of copyright ownership, examples of the original work, clarification of disputed elements).

A template notice form is available at `aidstation.pro/dmca/notice-template`.

---

## 4. Internal Workflow on Receipt

### 4.1 Intake

- Notices arriving at `info@aidstation.pro` or via postal mail are timestamped at the moment of receipt
- Each notice is assigned a tracking ID (`DMCA-YYYY-NNNN`)
- Receipt is acknowledged to the complaining party at AIDSTATION's discretion; the §512 framework does not require acknowledgment to the complainant

### 4.2 Triage

The Designated Agent triages each notice promptly upon receipt. Triage activities include:

1. **Validation** of the notice against §3 (compliance check)
2. **Location** of the allegedly infringing material in the AIDSTATION service
3. **Classification** of the content type (user-uploaded text, user-uploaded photo, user-generated facility entry, AI-generated derivative work, etc.)
4. **Determination** of whether the content is in fact within AIDSTATION's storage and control

The pace of triage is set by AIDSTATION based on notice complexity, content volume, and team availability. Triage is not subject to a fixed external clock.

### 4.3 Decision

For a substantially compliant notice:

- **Default action: takedown.** §512(c)(1)(C) requires expeditious removal once the provider has actual knowledge or receives a valid notice. AIDSTATION's typical processing time is within **72 hours** of validating a notice as compliant. Actual timing depends on the complexity of the notice, the volume of content involved, and the availability of personnel — and may extend beyond 72 hours when the matter warrants additional review.
- **Discretionary review.** If the notice appears facially abusive — the complaining party is clearly not the right-holder, the material is plainly fair use or public domain, the notice targets criticism or commentary, the notice is materially deficient in a way not curable, or the notice appears retaliatory or harassing — the Agent may escalate to counsel before acting, defer action, or decline to act. Such determinations are made at AIDSTATION's discretion and recorded in the DMCA log.
- **Reservation.** Nothing in this spec creates an obligation to act on any specific notice within any specific time frame. AIDSTATION's commitment is to act expeditiously consistent with §512(c)(1)(C); the 72-hour figure above is a typical processing target and not a warranty.

### 4.4 Action and notification

When content is removed or disabled:

1. The user who uploaded the content is **promptly notified** consistent with §512(g)(2)(A). "Promptly" is determined by AIDSTATION based on the nature of the takedown and operational factors. The notification includes (a) a copy of the notice (the complaining party's contact information may be redacted on documented request, consistent with §512(c)(3) and applicable case law), (b) a summary of the action taken, (c) instructions for submitting a counter-notification under §5, (d) a statement that the AIDSTATION repeat-infringer policy applies
2. The complaining party may be notified that the action has been taken, at AIDSTATION's discretion
3. The Designated Agent records the action in the DMCA log per §7

---

## 5. Counter-Notification

### 5.1 What a counter-notice must include

Under §512(g)(3), a counter-notice must include all four of:

1. The user's physical or electronic signature
2. Identification of the material removed and its prior location
3. A statement under penalty of perjury that the user has a good-faith belief that the material was removed as a result of mistake or misidentification
4. The user's name, address, phone number, consent to jurisdiction in the federal district court for AIDSTATION's location (Northern District of Texas), and consent to accept service of process from the original complaining party

A counter-notice missing any of these elements is not a valid counter-notice under §512(g) and is not entitled to the restoration process. AIDSTATION is not obligated to advise the user on how to correct a defective counter-notice.

### 5.2 Process when a valid counter-notice is received

On receipt of a valid counter-notice:

1. AIDSTATION forwards a copy to the original complaining party in a timely manner consistent with §512(g)(2)(B)
2. AIDSTATION informs the complaining party that the material will be restored in **not less than 10, nor more than 14 business days** unless the complaining party notifies AIDSTATION of a lawsuit filed against the user to restrain the alleged infringement. AIDSTATION's typical practice is to wait toward the later end of that statutory window before restoring, allowing the complaining party the maximum time the statute permits to act.
3. If no notice of suit is received within the statutory window, AIDSTATION restores the material and notifies the user
4. If notice of suit is received, the material remains removed; the dispute proceeds outside this process

A counter-notice template is available at `aidstation.pro/dmca/counter-notice-template`.

---

## 6. Repeat Infringer Policy

§512(i)(1)(A) requires "a policy that provides for the termination in appropriate circumstances of subscribers and account holders... who are repeat infringers." The statute does not define "repeat infringer," does not set a numeric threshold, and does not require the provider to publish any threshold it may use internally. AIDSTATION's policy reflects this discretion.

### 6.1 Policy statement

**AIDSTATION may terminate the accounts of users determined to be repeat infringers, in appropriate circumstances.** Whether circumstances are appropriate is determined by AIDSTATION at its sole discretion, considering factors that may include:

- The number of DMCA notices that have resulted in takedown against the account
- The nature and severity of the alleged infringements
- The presence or absence of valid counter-notifications
- The outcome of any disputes following counter-notifications
- The user's overall conduct on the service, including any related AUP violations
- Any other context AIDSTATION considers relevant

### 6.2 Process

- AIDSTATION may, but is not required to, issue warnings to users when DMCA strikes accumulate
- AIDSTATION may, but is not required to, articulate to a user the specific factors leading to a termination decision beyond a general statement
- Termination, when invoked, removes service access. Account data is handled per the standard deletion policy (Deletion Flow Spec); content already removed under DMCA notices remains removed.
- A terminated user may contact `info@aidstation.pro` to request AIDSTATION's reconsideration of the decision. Reconsideration is at AIDSTATION's discretion; no timeline applies; the original termination remains in effect unless AIDSTATION decides otherwise.

### 6.3 Disclosure

This policy is published at `aidstation.pro/dmca` and referenced in T&C and AUP. The published version uses the policy statement in §6.1; AIDSTATION's internal application of the factors and any internal thresholds are not published and are not part of the user-facing commitment.

---

## 7. Records

### 7.1 What is logged

For each notice and counter-notice:

| Field | Notes |
|---|---|
| Tracking ID | `DMCA-YYYY-NNNN` |
| Date received | Timestamped at intake |
| Sender contact | Per §3 item 4 |
| Material identified | URL/path; preserved as evidentiary copy |
| Compliance assessment | Per §3 |
| Action taken | Takedown, refusal-pending-correction, decline-to-act, escalation to counsel |
| Action date | When acted |
| User notification | Date and content of notice to the uploader (when issued) |
| Counter-notice (if any) | Date received, validity, forwarding date to complaining party |
| Restoration (if any) | Date and basis |
| Strike count effect | Internal — whether this contributes to the discretionary repeat-infringer determination under §6 |

### 7.2 Retention

| Record type | Retention |
|---|---|
| Notice records (notice + handling history) | 7 years from final action on the matter — covers the federal copyright statute of limitations (3 years from accrual under 17 U.S.C. § 507(b)) plus a margin for related disputes and repeat-infringer tracking; parallel to RoPA PA-16 |
| Evidentiary copies of removed material | 1 year from removal, then deleted unless a litigation hold applies |
| Internal repeat-infringer logs | Indefinite while the account remains active; retained 3 years after account closure |

### 7.3 Confidentiality

DMCA notice records are not part of the user's general data export under PP §9. The records concern the user but are litigation-adjacent records under a statutory process, not personal data routinely shared on access request. Disclosure to the user is limited to what was already provided in the §4.4 notification. Records may be disclosed to counsel, to courts under valid legal process, and to the parties to a specific DMCA matter as required by §512(g)(2). AIDSTATION's internal repeat-infringer logs and the §6.1 factor application are confidential business records.

---

## 8. Interaction with Other AIDSTATION Processes

### 8.1 Acceptable Use Policy

AUP §4 prohibits uploading infringing content. A DMCA notice resulting in takedown is evidence of an AUP violation; repeat AUP violations may independently support termination on AUP grounds rather than DMCA repeat-infringer grounds. The two processes are independent — a user can be terminated under either, both, or neither, at AIDSTATION's discretion.

### 8.2 Terms and Conditions

T&C must include, as a consistency-pass edit (not in this spec):

- A reference to this DMCA process and the agent contact
- A user representation that uploaded content does not infringe
- An acknowledgment of the repeat-infringer policy
- The license terms for user-uploaded content (already covered in T&C §8.2)

A new T&C copyright section is tracked in the consistency pass (Privacy Program Backlog D-104).

### 8.3 Privacy Program

DMCA notices contain personal data about the complaining party (and identifying information about the uploading user). This processing is conducted under legitimate interest (Art. 6(1)(f)) for the purpose of §512(c) safe-harbor compliance and litigation defense. It is not a sub-activity of any existing RoPA entry and should be added as a new processing activity (**proposed PA-16 — Copyright Notice Processing**) in RoPA (Privacy Program Backlog D-105).

### 8.4 AI Training (PA-15)

Content removed under DMCA must be excluded from training datasets going forward. If the content was already incorporated into a model generation prior to takedown, see PA-15's "AI Models and Derivatives" disclosure (PP §7) and the algorithmic disgorgement considerations in the LIA and DPIA. A DMCA takedown does not by itself trigger algorithmic disgorgement; a court order to that effect would. Engineering must ensure that the training ingest pipeline (DPIA §7.1 mitigations) checks for current DMCA-takedown status of the underlying content version.

### 8.5 Crowdsourced Facility Database

This spec is a **launch prerequisite** for the crowdsourced facility database feature. The feature must not ship before §10 items 1–4 are complete.

---

## 9. Non-US Coverage — Future Work

| Jurisdiction | Mechanism | Status |
|---|---|---|
| EU | DSA Art. 16 notice-and-action | Required before EU launch; broader scope than DMCA; separate workstream |
| UK | e-Commerce Regulations Reg. 19 | Similar to DSA; covered by EU workstream when launched together |
| Canada | Copyright Modernization Act, s. 41.25–41.27 (notice-and-notice) | Light obligation; foldable into this process with a Canadian forwarding template |
| Australia | Copyright Act safe-harbor reforms | Light obligation; covered by adding a notice acceptance path |
| Other | Various | Addressed per market |

A single global "Report Infringement" page at `aidstation.pro/dmca` can serve as the user-facing entry, with intake routed to the appropriate process based on the claimed law.

---

## 10. Operational Sequencing

Before this spec is operationally live, the following must happen, in order:

1. **Designate the agent** — Privacy Lead in DMCA-agent capacity (per §2.1). Named individual confirmed before registration. (Backlog D-99)
2. **Set up `info@aidstation.pro`** — routes to Designated Agent + one backup; auto-acknowledgment template prepared if AIDSTATION chooses to send acknowledgments. (Backlog D-100)
3. **Procure phone number** for USCO directory (virtual with business-hours routing acceptable). (Backlog D-101)
4. **Publish the public DMCA page** at `aidstation.pro/dmca`. (Backlog D-102)
5. **Register with USCO** — `dmca.copyright.gov`; $6 fee; pre-launch and before any UGC-bearing feature ships. (Backlog D-99 — combined with agent designation)
6. **Add T&C copyright section** referencing this process (consistency-pass edit; not blocking). (Backlog D-104)
7. **Set calendar reminder** for USCO registration renewal at 30 months out.
8. **Add PA-16 to RoPA** (consistency-pass edit; not blocking). (Backlog D-105)

Until items 1–5 are complete, the §512(c) safe harbor is not in effect for AIDSTATION. **The crowdsourced facility database feature must not ship before items 1–5 are complete.**

---

## 11. Reservation of Rights

This spec is an internal operational document. It does not:

- Create third-party rights for complaining parties, users, or any other person
- Constitute a warranty that AIDSTATION will act within any specific time frame on any specific notice or counter-notice
- Waive any rights or defenses AIDSTATION may have under §512 or otherwise
- Constitute a fair-use determination or any other legal opinion about any specific content; AIDSTATION is a host, not an arbiter of copyright disputes
- Limit AIDSTATION's discretion to act, decline to act, or escalate to counsel in any particular matter

AIDSTATION may modify this process at any time. Material changes will be reflected in an updated version of this spec and at `aidstation.pro/dmca`. Users and complaining parties are responsible for consulting the current version. Use of the AIDSTATION service constitutes acceptance of the process as posted at the time of use.

---

## 12. Cross-Spec Touchpoints

| Document | Relationship |
|---|---|
| `AIDSTATION_Terms_and_Conditions` | Requires a copyright section referencing this process; user representation re: non-infringing content; repeat-infringer policy acknowledgment |
| `AIDSTATION_Acceptable_Use_Policy` §4 | Independent AUP violation grounds; can compound DMCA strikes |
| `AIDSTATION_Privacy_Policy` | Contact disclosure for DMCA agent; notice-processing as PA-16 (RoPA) |
| `AIDSTATION_RoPA` | Needs PA-16 entry in v3 for DMCA notice processing |
| `AIDSTATION_Deletion_Flow_Spec` | Repeat-infringer termination interacts with account deletion flow |
| `AIDSTATION_Breach_Response_Playbook` | If a DMCA notice surfaces evidence of an underlying security incident, the playbook applies in parallel |
| `AIDSTATION_DPIA_PA15` / `AIDSTATION_LIA_PA15` | DMCA-takedown exclusion from training datasets (§8.4) |
| `AIDSTATION_DPIA_Template` Appendix A item 6 | Crowdsourced facility database — the feature whose launch this spec gates |

---

## 13. Gut Check

### 13.1 Risks

- **No published repeat-infringer threshold is the right defensive posture but creates a small case-law risk.** A court reviewing safe-harbor eligibility may want to see evidence of "reasonable implementation" of the §512(i) policy. Without a published number, that evidence must come from internal records of consistent application. The §7.1 strike-count effect logging is what protects this position — it must actually be maintained.
- **The 72-hour typical takedown is a soft commitment, not a guarantee.** §4.3's "typical processing time" language is doing important work; if AIDSTATION publicly states 72 hours and routinely misses, the safe-harbor argument weakens. Internal practice should target 72; the written language preserves room.
- **No acknowledgment to complaining parties is operationally efficient but may produce more follow-up correspondence ("did you receive my notice?"). Decide pragmatically per matter; the spec permits either approach.**
- **The reservation-of-rights §11 language is defensive and helpful but does not override statutory obligations.** AIDSTATION still owes "expeditious" removal, "prompt" notice to users, and "reasonable implementation" of the repeat-infringer policy. §11 protects against extra-statutory claims, not statutory ones.
- **Discretionary appeal process (§6.2) means user grievances have nowhere clean to land.** Some terminated users will escalate publicly (social media, reviews) when no formal appeal path exists. This is a brand risk, not a legal risk. Worth tracking but the legal posture is right.

### 13.2 What might be missing

- **Template documents.** The notice form, counter-notice form, intake acknowledgment (if used), user-notification template — all named, none drafted yet. Backlog D-103.
- **Phone number for USCO directory.** Required field; needs procurement. Backlog D-101.
- **A trademark complaint process.** Out of scope here, but trademark notices will arrive eventually and there is no current process. Defer to first-notice or feature-driven trigger.
- **DSA preparation.** EU launch is a separate workstream, but DSA Art. 16 is broader than DMCA and will require a more general notice-and-action mechanism. Worth scoping the gap before EU launch is committed.
- **A documented internal threshold for repeat-infringer determination.** The published policy is discretionary, but internal application should be reasonably consistent. An internal — not published — rough guideline (e.g., "review at 3 strikes / 12 months; terminate at 5") would support "reasonable implementation" without exposing AIDSTATION to a published commitment.

### 13.3 Best argument against this spec

A counter-position: **the operator-favorable posture is too aggressive and risks losing safe-harbor protection.** Arguments:

- Courts have read §512(i)'s "reasonably implemented" requirement strictly. Providers that publish vague policies and apply them inconsistently have lost safe harbor in some cases (notable: *BMG v. Cox*, 2018).
- Removing published timing commitments and the published threshold puts more weight on internal practice records; if those records aren't maintained, the safe harbor weakens.
- A more conservative posture (e.g., the v1 spec's 24-hour, 3-strikes-published version) is more clearly defensible in the safe-harbor analysis.

The defense for v2's posture:

- §512 does not require publishing timing windows or numeric thresholds; the statutory text only requires informing subscribers of the existence of a policy
- The vast majority of large service providers publish similarly discretionary repeat-infringer policies; this is industry-standard, not outlier
- The case-law risk identified in *BMG v. Cox* was driven by Cox's actual failure to apply its policy, not by the policy's vagueness; reasonable implementation is the protection, regardless of what is published
- The 72-hour typical-not-guaranteed language is more defensible than a 24-hour written promise that is hard to keep
- Internal threshold guidance (per §13.2 missing-item) closes the implementation-consistency gap without exposing AIDSTATION to a published commitment

**v2 stands as the recommended posture for counsel review.** A revision toward more conservative publication (named thresholds, named timing) is a counsel-directed change that does not require redrafting the spec — only updating §4.3, §6.1, and §6.3 with specific numbers if counsel takes that view.

---

## Change Log

| Version | Date | Changes | Author |
|---|---|---|---|
| v1 | May 19, 2026 | Initial spec. Designates the DMCA agent process for §512(c) safe-harbor compliance. Establishes notice acceptance, takedown procedure (24-hour default), counter-notification, repeat-infringer policy (3 strikes / 12 months published), and records retention. USCO registration sequenced ahead of crowdsourced facility feature launch. Closes D-78. | Privacy Lead |
| v2 | May 19, 2026 | Operator-favorable revision across all commitments. §4.1 intake acknowledgment to complainant made discretionary (was: 1 business day required). §4.2 triage window removed (was: 2 business days); replaced with "promptly upon receipt" descriptive language. §4.3 takedown default changed from 24-hour hard target to 72-hour typical processing time with explicit reservation of timing discretion. §4.4 user notification language changed from "within 1 business day" to "promptly consistent with §512(g)(2)(A)." §5.2 counter-notice forwarding changed from "within 1 business day" to "in a timely manner consistent with §512(g)(2)(B)." §5.2 restoration timing now expressed as full statutory window (10–14 business days) with stated preference toward later end. §6.1 published repeat-infringer threshold removed (was: 3 strikes / 12 months); replaced with discretionary multi-factor policy. §6.2 warning cadence and termination triggers made discretionary. §6.2 30-day appeal window removed; replaced with discretionary reconsideration. §6.3 disclosure trimmed to statutory-style language only. §7.2 internal repeat-infringer logs retention extended (indefinite while active; 3 years post-closure). §11 Reservation of Rights added — no third-party rights, no timing warranty, no fair-use determinations, modification at will. Section numbers renumbered to accommodate §11. Backlog refs added throughout (D-99 through D-105). | Privacy Lead |
| v4 | May 30, 2026 | Resolves D-128. Notice-record retention trigger changed from "7 years from the date of the notice" to "7 years from final action on the matter," matching RoPA PA-16; citation updated to 17 U.S.C. § 507(b) accrual and repeat-infringer tracking rationale. Duration (7 years) unchanged. | Privacy Lead |
| v4 | May 30, 2026 | Contact-address consolidation to the two approved addresses: `help@aidstation.pro` for user support (including privacy / data-rights requests) and `info@aidstation.pro` for formal, legal, security, and DMCA correspondence. No other changes. | Privacy Lead |

---

*Cross-reference cleanup (v3, 2026-05-30): inline references to companion documents were converted to unversioned logical names per Rule #12, so they no longer go stale when a companion document is revised. No substantive content changes. See `Privacy_Program_Consistency_Sweep_Report_v1.md`.*

