# AIDSTATION AI Safety Logging Decision

**Status:** Decision document v2 (contact-address consolidation; otherwise unchanged since the Batch 8 v1)
**Owner:** Privacy Lead
**Last Updated:** May 30, 2026
**Companion docs:** `AIDSTATION_Privacy_Policy_v2.md` §4 and §7; `AI_System_Prompt_Restrictions_v2.md` §7; `AIDSTATION_Breach_Response_Playbook_v2.md`; `AIDSTATION_RoPA_v2.md`; `AIDSTATION_Acceptable_Use_Policy_v1.md` §7 (security research carve-out)

---

## 0. Scope and Status

This document resolves a single tension surfaced in Batches 5–7: how AIDSTATION investigates AI-output safety incidents given that Privacy Policy v2 §4 and §7 commit to not retaining raw AI conversation transcripts. The decision is non-trivial because the commitment is real (regulator- and user-visible) and the operational need is also real (the Breach Response Playbook anticipates investigating incidents that, for AI-output incidents specifically, are currently uninvestigable beyond aggregate refusal/validator counts).

**In scope.**
- Define the investigation gap created by §4 / §7
- Enumerate options, with tradeoffs
- Pick one
- Specify the implementation guidelines (architecture, data flow, retention, access controls) that follow from the pick — no code
- Specify the Privacy Policy text changes (if any) that follow from the pick
- Identify the downstream documents that need to be touched (RoPA, Breach Playbook, AUP, DPIA Template Appendix A)

**Out of scope.**
- Actual implementation of the captured-snapshot UX or storage system (engineering)
- Coaching-flag policy for inferred sensitive attributes — separate doc (Privacy Program item #1)
- Background quality monitoring of all conversations (explicitly rejected; see §6)
- Any change to refusal / validator event logging — that infrastructure is already documented in AI System Prompt Restrictions v2 §7 and is unaffected by this decision

---

## 1. The Tension

### 1.1 The commitment

Privacy Policy v2 §4 and §7 read (paraphrased):

> Anthropic does not train on AIDSTATION user data. AIDSTATION may use user content to train its own coaching models, with explicit opt-in for sensitive categories. **Raw conversation transcripts are not retained beyond the session**; only parsed coaching notes and structured outputs derived from interactions are stored.

This is publicly disclosed, repeated in T&C v2 §8 ("AI output retention = parsed coaching notes only, no raw transcripts"), and serves as a privacy-by-default differentiator. It is also a real engineering posture — the conversational pipeline is designed to extract structured signal and discard the conversational content.

### 1.2 The investigation gap

The Breach Response Playbook v2 §10 assumes investigators can perform "detailed log review" and "scope confirmation" — verify which accounts and which data categories were affected. For traditional data breaches (DB exfiltration, credential compromise) this works: logs of access, logs of queries, logs of network flow.

For AI-output safety incidents, however — defined here as cases where the AI itself caused or contributed to a harm — the available investigative artifacts are narrow:

| Artifact | What it tells you | What it doesn't |
|---|---|---|
| Refusal event log (per Restrictions §7.1) | Category was triggered, refusal template used, timestamp, athlete ID | What the athlete said, what specifically triggered the refusal |
| Validator catch log (per Restrictions §7.1) | Output was suppressed, category, layer | What the original LLM output was, what athlete input produced it |
| Parsed coaching notes | The structured plan / recommendation that was generated | The conversational context around it, any pushback, any nuance the structured output dropped |
| Aggregate counts | Patterns at the cohort level | Anything specific to an individual incident |

For incidents like "the AI refused appropriately but the refusal text was upsetting" (UX issue, not safety) — aggregate counts may be enough. For incidents like "the AI gave dangerous training advice that contributed to an athlete's injury" or "the AI was jailbroken and engaged with a restricted topic" or "the AI memorized and surfaced another user's data" — none of the four artifacts above tells the investigator what the AI actually said in that specific case.

### 1.3 Why this matters now, before launch

- **Regulatory.** Under GDPR Art. 22 and equivalent provisions, when an AI system produces decisions affecting individuals, the controller is expected to maintain enough audit information to investigate and remediate harms. "We chose not to log" is a defensible posture only if alternative investigation paths are documented.
- **Liability.** Under product-liability frameworks (US tort, EU Product Liability Directive 2024/2853), the absence of incident-specific evidence cuts both ways — it can protect against discovery, or it can be construed as willful blindness. Counsel will want a written, deliberate choice in either direction.
- **Operational.** First reportable AI-safety incident is a bad time to invent the response. The Breach Playbook needs to know what's available.
- **User trust.** Users who file reports about AI behavior reasonably expect investigation. If we have no path to investigate, that reasonable expectation is unmet.

---

## 2. Options Considered

### 2.1 Option A — Short-TTL redacted transcript capture for safety review

**Description.** All conversations capture raw transcripts to an encrypted, separate-from-production storage tier with a short retention window (e.g., 7 or 14 days). Stored content is redacted at capture time (PII tokens replaced with deterministic pseudonyms) and accessible only via dual-approval incident-response flow. After TTL, deleted automatically.

**Investigation capability.** High. Most AI-safety incidents become investigable. Pattern detection across users is possible during the retention window.

**Privacy posture.** Materially weaker than the current commitment. Even with redaction and short TTL, "we retain raw transcripts" is what the storage actually does — the §4 / §7 commitment as currently written becomes false.

**PP v2 §4 / §7 impact.** Significant rewrite required. Both sections currently say "raw conversation transcripts are not retained." Option A makes that statement inaccurate.

**Tradeoffs.**
- Pro: Maximum investigative capability; covers user-non-reported incidents
- Pro: Defensible posture for regulatory inquiries (we can answer "what did the AI say?")
- Con: Material privacy posture downgrade
- Con: Standing pool of raw conversation content is a high-value target — increased breach risk and impact
- Con: Trust narrative gets harder ("zero retention" → "short-window retention")
- Con: Sensitive content stored at scale needs explicit opt-in in some jurisdictions
- Con: Standing access path means even rare misuse is feasible — administrative risk
- Con: Counsel will want detailed access-logging, dual-approval, and retention enforcement, all of which add operational overhead

### 2.2 Option B — User-initiated feedback bundled with content snapshot

**Description.** Background capture is unchanged from current posture — no raw transcripts retained. A "Report this conversation" affordance is added to the conversational coach UI. When the user invokes it, AIDSTATION captures a bounded snapshot: the user message that triggered the report, the AI response, N preceding turns (proposed: 5), plus a structured report reason. The captured bundle is submitted with the report, stored separately from production data, and accessible to the privacy/safety review team.

The user's act of reporting is consent for that specific capture, disclosed in the report flow.

**Investigation capability.** Moderate. User-reported incidents become fully investigable; non-reported incidents remain investigable only via aggregate counts and parsed coaching notes. Critically, the highest-signal incidents — those where the user was upset enough to flag — are exactly the ones covered.

**Privacy posture.** Substantially preserves the current commitment. Background retention is still zero; the only retention is explicit, consent-based, and limited to reports the user themselves submitted.

**PP v2 §4 / §7 impact.** Light. The "no raw transcripts" sentence can stand with a clarifying clause: "except where you explicitly submit conversation excerpts as part of a user-initiated safety report." The §7 entry can mirror.

**Tradeoffs.**
- Pro: Privacy posture survives intact, with a narrow, defensible exception
- Pro: Consent model aligns with GDPR Art. 6(1)(a) — no shoehorning into legitimate interests
- Pro: Captured content has a clear purpose (this report) and clear retention rationale
- Pro: No standing pool of conversation content — the dataset is small and incident-bounded
- Pro: User trust narrative remains "we don't retain conversations unless you explicitly send us one"
- Con: Non-reported incidents stay uninvestigable (e.g., user didn't realize the AI gave bad advice until later when the data is gone)
- Con: Users may underreport — UX friction or unfamiliarity with the reporting affordance
- Con: For systemic incidents affecting many users, the data is sparse and slow to accumulate
- Con: Cohort pattern detection is limited to whatever subset of users reported

### 2.3 Option C — Accept no post-hoc investigation

**Description.** Status quo. PP v2 §4 / §7 unchanged. Investigation of AI-output incidents is restricted to refusal/validator counts and parsed coaching notes. The Breach Playbook is amended to document that for AI-output incidents the available investigative path is limited.

**Investigation capability.** Lowest. Only aggregate patterns and the structured output are available. No way to reproduce or examine specific incidents.

**Privacy posture.** Strongest. Zero retention, no exceptions, no consent-based exception. The commitment is absolute.

**PP v2 §4 / §7 impact.** None.

**Tradeoffs.**
- Pro: Cleanest privacy posture; defensible as principled
- Pro: Lowest engineering and operational overhead
- Pro: No new attack surface (no encrypted-snapshot store, no access controls to maintain)
- Pro: No retention period to enforce, no DSR complexity (no transcripts to export or delete on request)
- Con: When the first reportable AI-safety incident occurs, investigation will be visibly inadequate
- Con: Regulator may treat the absence of any investigation capability as willful — particularly in EU product-liability context
- Con: User trust narrative may flip: "we can't investigate your complaint because we don't keep transcripts" sounds principled in the abstract and evasive in practice
- Con: Closes the door to even the most narrowly-scoped consent-based capture

### 2.4 Option D — Hybrid: Option B as default + narrow Tier 1/2 emergency capture

**Description.** Option B (user-initiated reporting with snapshot) is the operational default. In addition, the Breach Playbook gains a documented emergency capture mechanism: when a confirmed Tier 1 or Tier 2 safety incident is in progress and the Incident Commander, Privacy Lead, and Engineering Lead jointly determine that forward-looking capture is necessary to scope the incident or remediate the cause, a time-bounded, narrowly-scoped forward-looking capture can be enabled.

Constraints on the emergency mechanism:
- Forward-looking only — no retroactive capture (because the data doesn't exist to be captured)
- Time-bounded — explicit termination date, default 72 hours, extendable in 72-hour windows with re-approval
- Scope-limited — specific user cohort if identifiable (e.g., users matching the affected feature path) or specific conversation IDs, not blanket platform-wide
- User notice — affected users receive an in-app banner that capture is active and why (high-level)
- Audit log — every approval, every access, every termination logged separately
- Automatic termination on incident closure
- Disclosed in Privacy Policy and Breach Playbook as an emergency mechanism

**Investigation capability.** High in the narrow set of cases where it's invoked; moderate (Option B level) in all other cases.

**Privacy posture.** Slightly weaker than Option B because of the emergency mechanism, but the mechanism is constrained, audited, transparent, and tied to incident severity.

**PP v2 §4 / §7 impact.** Moderate. The "no raw transcripts" language needs a two-part exception:
1. User-submitted reports (B)
2. Emergency capture during confirmed safety incidents (D's addition)

**Tradeoffs.**
- Pro: Preserves the privacy posture in normal operation
- Pro: Avoids the worst case of Option C (visible investigation failure during a serious incident)
- Pro: Constrains the worst case of Option A (no standing pool, no routine access)
- Pro: Forces the rare exception to be deliberate, dual-approved, and time-bounded
- Pro: Transparent to users when invoked
- Con: Most complex to specify, document, and operationalize
- Con: Emergency mechanism could be misused if approval controls fail — high-trust controls required
- Con: Discloses the existence of a capture capability, which on the margin weakens the differentiator (no longer "we never capture conversations under any circumstance")
- Con: Forward-looking constraint means truly novel one-time incidents may still be unreviewable

---

## 3. Decision

**Selected: Option D — Hybrid (Option B operational default + emergency Tier 1/2 capture mechanism).**

### 3.1 Rationale

Option B is the right operational default. It preserves the privacy posture, aligns with GDPR Art. 6(1)(a) consent, and covers the highest-signal cases (user-reported incidents). It is the path that does the most privacy work with the least retention.

The emergency mechanism is added because Option B alone has a single weak point: a serious AI-output incident affecting users who do not report. The first time AIDSTATION needs to scope a confirmed Tier 1 or Tier 2 AI-output incident and cannot — because no transcript exists and no user reported — the privacy posture will not survive the incident response. Option C accepts that outcome by design. Option D refuses to accept it but constrains the alternative to a transparent, audited, deliberately-rare mechanism rather than the standing pool of Option A.

The cost of Option D over Option B is the documentation and operational overhead of the emergency mechanism. That cost is manageable: the approval is dual, the audit is small, and the mechanism activates rarely. The benefit over Option B is the difference between "we have no capability to investigate severe incidents" and "we have a capability we very rarely use, with controls."

### 3.2 What is rejected

- **Background capture of any kind.** Option A is rejected. No transcript is captured in normal operation, full stop.
- **Pre-emptive capture without confirmed Tier 1/2 incident.** The emergency mechanism is not a tool for routine quality monitoring or general curiosity. It activates only on a confirmed Tier 1/2 incident.
- **Retroactive capture.** Capture is forward-looking only — the architecture does not retain data that hasn't been captured yet.
- **Indefinite emergency capture.** The mechanism is time-bounded with explicit re-approval required.

---

## 4. Privacy Policy v2 Reinterpretation

### 4.1 §4 — AI Coaching

Current language (paraphrased): "Anthropic does not train on user data. AIDSTATION may use content to train its own models, with sensitive-category safeguards. Raw conversation transcripts are not retained beyond the session."

Proposed amendment, added at the end of the section:

> **Exceptions to raw transcript retention.** We retain raw conversation excerpts only in two limited cases: (1) when you submit a conversation as part of a safety report through the in-app reporting flow, in which case the excerpts you choose to submit are retained as part of your report; and (2) during the investigation of a confirmed safety incident, where short-term forward-looking capture may be enabled for the duration of the incident, with affected users notified through an in-app banner. Both cases are described in our Safety Logging Notice. We do not perform background capture of conversations in normal operation.

### 4.2 §7 — How Long We Keep Your Data ("Raw AI Conversations" subsection)

Current language: "We do not retain raw conversation transcripts. Only the parsed coaching notes and structured outputs derived from your interactions are stored."

Proposed amendment:

> **Raw AI Conversations.** We do not retain raw conversation transcripts in normal operation. Only parsed coaching notes and structured outputs derived from your interactions are stored. We retain raw excerpts only when you explicitly submit them through a safety report, or temporarily during the investigation of a confirmed safety incident under the conditions described in our Safety Logging Notice.

### 4.3 New supporting document

A short, public-facing **Safety Logging Notice** is added to the customer-facing trio's surrounding documents (along with the Health and Safety Notice and the Partners Page). It describes both mechanisms in plain language. Draft scope:

- What user reporting captures, where it goes, who can see it, how long it's kept
- What emergency capture is, when it activates, how users are notified, when it ends
- How to request deletion of safety reports under DSR rights
- Contact path for safety reports

Spec for this notice is **not** in this document. It is a deliverable item to be added to the privacy program backlog as a Batch 8 or later artifact.

---

## 5. Implementation Guidelines

These are guidelines for engineering. They specify architecture, data flow, control structure, and constraints. They do not specify code, framework, language, library, or schema.

### 5.1 User-Report Path (operational default — Option B layer)

**5.1.1 Entry point.** Every conversational coach surface exposes a "Report this conversation" affordance reachable from the conversation UI. Discoverable but not prominent (intent is for genuine safety reports, not a feedback survey).

**5.1.2 Report flow.** Three steps:

1. **Reason category.** Single-select from a controlled list: dangerous training advice; inappropriate refusal of legitimate question; inappropriate engagement with restricted topic; harassment or hostility; bias or discrimination; output appears to contain another user's data; other.
2. **Optional free-text description.** User may explain in their own words.
3. **Capture scope confirmation.** Show the user exactly what content will be submitted: the AI's most recent response, the user message that triggered it, and the N preceding turns from the same session. User confirms or cancels.

**5.1.3 Snapshot contents.** Bundle includes:
- Conversation excerpts as shown to the user in step 3 (no expansion past the displayed scope)
- Timestamps for each excerpted turn
- Conversation ID (system-generated, pseudonymous)
- Athlete ID (pseudonymized at storage)
- Report reason category
- Report free-text (if provided)
- System metadata: app version, layer that produced the AI response (L3, L4, L5, conversational coach), any refusal or validator events that fired during the captured window
- Submission timestamp

Excludes: anything outside the displayed scope (no expanding the window post-hoc), anything from other sessions, anything from other users.

**5.1.4 Storage.**
- Separate logical storage tier from production conversation pipeline
- Encrypted at rest (per security standards in TOMs Annex)
- Access controlled — see §5.1.6
- Not part of any analytics or ML training pipeline by default; if any specific report's contents are to be used for training, that requires separate review (and is governed by the AI training opt-in posture in T&C §8.2 / PP §4)

**5.1.5 Retention.**
- Default: 12 months from report submission
- Extended retention permitted if the report is part of an active incident investigation (until investigation closure + 24 months, per Breach Playbook §12.2 — incidents are retained 5 years; safety reports tied to an incident inherit that timeline)
- User-initiated deletion: the report is included in account-deletion scope. User can also delete a single report through the Safety Reports view (see §5.1.7) at any time, subject to litigation hold

**5.1.6 Access.**
- Read access limited to designated Privacy/Safety Review role
- Bulk export or downstream processing requires dual approval (Privacy Lead + Engineering Lead)
- Every access logged: who, when, which reports, purpose stated
- Quarterly access audit by Privacy Lead

**5.1.7 User-side affordances.**
- Confirmation email at report submission (no transcript content in email; just acknowledgment + report ID + link to manage)
- A "Safety Reports" view under Account → Privacy showing the user's own submitted reports, allowing them to view the captured content and delete the report
- Reports are included in data export (DSR portability), exported as a structured bundle including the captured excerpts

**5.1.8 Notice at point of capture.**
- Step 3 of the report flow contains a clear, plain-language notice of what is being captured, where it goes, how long it is kept, and who can access it
- This notice is the consent record for GDPR Art. 6(1)(a) basis

### 5.2 Emergency Capture Path (constrained exception — Option D addition)

**5.2.1 Trigger criteria.** All four must hold:
- Confirmed Tier 1 or Tier 2 AI-output incident per Breach Playbook §2 severity definitions
- Investigative information cannot be obtained from existing logs (refusal events, validator catches, parsed coaching notes) or from user reports submitted to date
- Forward-looking capture is reasonably likely to surface the information needed to scope or remediate the incident
- The expected forward-looking capture window is reasonably bounded (≤ 14 days total, broken into 72-hour re-approval intervals)

**5.2.2 Approval.** Joint approval required from:
- Incident Commander (per Breach Playbook §3)
- Privacy Lead
- Engineering Lead

Approval is documented in the incident log with rationale, scope, and expected duration. Approval expires automatically at the end of each 72-hour window unless explicitly extended (re-approval requires the same three roles).

**5.2.3 Scope.**
- User cohort: specific user IDs if identifiable, OR specific conversation patterns/feature paths if cohort is not yet known, OR all conversations within a specific time window if neither
- Capture window: forward-looking only; starts from approval timestamp
- Data captured: same shape as user-report snapshots (turns + metadata + refusal/validator events) but full session, not bounded to N preceding turns

**5.2.4 User notice.**
- In-app banner shown to all users within the capture scope, indicating that capture is active and pointing to the Safety Logging Notice for detail
- Banner text approved by Privacy Lead; consistent template across incidents
- Banner persists for the duration of capture; removed automatically at termination

**5.2.5 Storage and access.**
- Same separate storage tier as user-report snapshots, with a distinct retention tag indicating "emergency capture"
- Access locked to incident response team for the duration of the incident
- Every access logged

**5.2.6 Termination.**
- Automatic at end of approved window
- Manual termination available at any time by any of the three approval roles
- On termination: capture stops immediately; captured data retained per §5.2.7

**5.2.7 Retention.**
- Tied to incident closure (Breach Playbook §12)
- Standard incident documentation retention applies (5 years from closure, longer if litigation foreseeable)
- After incident closure, the captured data is reclassified as incident documentation, not active safety logging

**5.2.8 Audit and review.**
- Every invocation of emergency capture is reviewed in the post-incident review (Breach Playbook §13)
- Annual review of all emergency capture invocations during the year, included in any internal compliance audit
- If transparency reporting is published (see §7), invocation counts (not contents) are included

### 5.3 What both paths share

- Captured data is **never** routed to AI training datasets by default. If any captured content is proposed for training (e.g., a particularly informative refusal failure case), it requires separate review under the AI training framework (T&C §8.2, PP §4), and counts as a use beyond the original safety-investigation purpose.
- Captured data is treated as Sensitive Data for purposes of the Breach Playbook, regardless of content. Treat any incident involving the safety storage tier as Tier 1 or Tier 2 by default.
- Both paths share the same access-logging infrastructure and the same Privacy/Safety Review role definition.
- Both paths produce data that is subject to DSR rights (access, deletion, portability) — implementation must wire these into the existing DSR fulfillment flow (Deletion Flow Spec v2, Authorized Agent Process Spec v2).

---

## 6. What This Decision Does NOT Cover

For clarity, the following are explicitly out of scope and are governed by other documents:

| Area | Governed by |
|---|---|
| Refusal event logging (category + template ID, no content) | AI System Prompt Restrictions v2 §7 |
| Validator catch logging (category + layer, no content) | AI System Prompt Restrictions v2 §7 |
| Parsed coaching notes retention | PP v2 §7 |
| Background continuous monitoring of conversations | **Explicitly rejected.** See §3.2. |
| Quality assurance review of conversation samples | Not implemented. If introduced later, requires its own decision document and consent framework. |
| Training data selection from conversations | T&C §8.2, PP §4 (opt-in, sensitive-category safeguards) |

---

## 7. Cross-Spec Touchpoints

Documents that need updates if this decision is adopted:

| Document | Change required |
|---|---|
| `AIDSTATION_Privacy_Policy_v2.md` §4 | Add exceptions clause per §4.1 above |
| `AIDSTATION_Privacy_Policy_v2.md` §7 (Raw AI Conversations) | Add exception language per §4.2 above |
| `AIDSTATION_Privacy_Policy_v2.md` §9 (Your Rights) | Confirm Safety Reports view is included in Access / Deletion / Portability paths (likely already covered by existing language but worth a check) |
| `AIDSTATION_Breach_Response_Playbook_v2.md` | New section on AI-output incident investigation, including emergency capture trigger criteria, approval, and audit |
| `AIDSTATION_Breach_Response_Playbook_v2.md` §10 | Cross-reference emergency capture as one path in investigation |
| `AIDSTATION_RoPA_v2.md` | New processing activity **PA-16 Safety Logging and Incident Investigation** (data subjects, categories of data, legal basis (consent for B / legitimate interest for D), retention, international transfers, security measures) |
| `AIDSTATION_DPIA_Template_v2.md` Appendix A | Add new item: DPIA for PA-16 prior to launch of the safety reporting flow |
| `AI_System_Prompt_Restrictions_v2.md` §7 | Cross-reference to this document — the existing event-logging behavior is unchanged; the safety reporting and emergency capture are separate, complementary mechanisms |
| `AIDSTATION_Acceptable_Use_Policy_v1.md` | No change required, but the AUP "good-faith security research" carve-out (§7) is the natural place to confirm that submitting a safety report is encouraged and protected |
| `AIDSTATION_Terms_and_Conditions_v2.md` §8.2 | Confirm the AI training license language doesn't accidentally sweep in safety-report content; explicit carve-out recommended |
| **New file:** `AIDSTATION_Safety_Logging_Notice_v1.md` | Customer-facing notice describing both mechanisms in plain language. Spec to be drafted as a Batch 8/9 deliverable. |

---

## 8. Implementation Sequencing

When this decision moves from spec to build, the order:

1. **Document chain first.** PP v2 → v3 amendment, Breach Playbook v2 → v3 amendment, RoPA v2 → v3 with PA-16 added, DPIA Appendix A updated, Safety Logging Notice v1 drafted. None of these require engineering; they require this decision being signed off + counsel review.
2. **User-report flow second.** Step 1 unblocks publishing; step 2 is engineering work in Claude Code. UI affordance + storage tier + access controls + DSR wiring.
3. **Emergency capture mechanism third.** Lower-priority engineering. Operational documentation (Breach Playbook update) is more important than the engineering build at launch — the mechanism can be a manual operational capability initially (e.g., enable capture via direct database flag) and become a built UI later.

Step 1 is in scope for the privacy program threads. Steps 2 and 3 are out of scope (build work).

---

## 9. Open Items

| ID | Description | Disposition |
|---|---|---|
| SL-1 | Retention period for user-reported safety reports — 12 months proposed; confirm with counsel | Counsel review |
| SL-2 | Whether to publish safety report counts in a future transparency report — Batch 4 §7 transparency report deliverable | Defer to transparency report design |
| SL-3 | Whether the user-report snapshot scope of "N preceding turns" should be configurable by user (e.g., expand to 10 turns) | Engineering / UX decision |
| SL-4 | What the in-app banner text for emergency capture should be, exact wording | Customer-facing copy review |
| SL-5 | Whether emergency capture should be possible across the entire customer base (e.g., if the incident pattern is truly platform-wide) or whether there's an absolute cohort ceiling | Counsel review |
| SL-6 | Whether the Safety Logging Notice should be linked from the conversational coach UI by default (passive disclosure) or only surfaced at report time (active disclosure) | UX decision; lean toward passive |
| SL-7 | Handling of safety reports that arrive for accounts under deletion cooling-off — preserve report through cooling-off and delete on final deletion, or delete report at deletion confirmation | Likely: preserve through cooling-off, delete on final |

These should not block adoption of the decision. They are implementation- and copy-level questions, scoped for resolution as the document chain is updated and the Safety Logging Notice is drafted.

---

## 10. Gut Check

### 10.1 Risks

- **Emergency capture risk.** The mechanism is constrained but it does exist. A determined insider with all three approval roles could in principle abuse it. The mitigation is the audit log, the dual-approval requirement, and the in-app banner notice — none individually sufficient, all together strong. Counsel may want a fourth control (e.g., board-level oversight for emergency capture > N hours).
- **User-report flow risk.** Even with snapshot scope confirmation, users may report and later regret it. The deletion path mitigates this, but the social risk is real — particularly if reports contain sensitive content the user later wants suppressed. The "you can delete this report at any time" affordance is essential.
- **Banner notice risk.** Emergency capture's user-notice requirement is operationally tricky: the banner discloses an incident is in progress, which is information regulators or affected users may want before the incident is contained. There's a tension between user transparency and incident containment. Defaulting to "transparent during capture" is the right call but may produce uncomfortable timing.
- **Privacy posture narrative.** The product can no longer say "we never retain conversations" without qualifier. The qualifier is honest and narrow, but marketing will need to adapt the messaging.
- **Counsel may rewrite.** This is a decision document presented for counsel review. Specific elements (retention periods, emergency-capture controls, banner-vs-notice timing) may be revised. The structure should survive that revision; the specifics may not.

### 10.2 What might be missing

- **Whistleblower / employee-side incidents.** This document covers AI-output incidents detected through users or through systems. It doesn't cover incidents where an AIDSTATION employee notices something concerning in a conversation they have legitimate access to (e.g., during a support case). Worth a brief amendment to PA-16 covering employee-detected incidents.
- **Third-party reports.** A non-user (e.g., a friend or family member of a user) may want to report concerning AI behavior. The user-report flow assumes the reporter is the conversation participant. Third-party reporting is a separate path — probably routed through help@aidstation.pro with manual review.
- **Cross-jurisdictional disclosure.** Emergency capture may produce evidence that triggers a notification obligation in a jurisdiction where the captured user is located. The Breach Playbook covers notification timelines but the interaction with this mechanism specifically should be made explicit.
- **Counter-monitoring.** The emergency capture mechanism could be invoked, then deliberately fail to detect a pattern, then be cited as "we looked, we didn't find anything." Mitigation: emergency capture invocations are externally reviewable as part of incident closure; counsel can review the audit log.
- **DPIA scope.** Adding PA-16 to RoPA will require a DPIA for the new processing activity. That DPIA should be drafted before the user-report flow is launched. Tracked as a downstream deliverable.

### 10.3 Best argument against this decision

Option C (no investigation capability at all) is principled and clean, and its strongest argument is: AIDSTATION is a small operation pre-launch, and adding any AI-conversation retention mechanism creates a capability that will be hard to remove later. Capabilities accrete. Option B's user-report path is hard to retire once it exists. Option D's emergency mechanism is harder still. Once you have a capability, organizational pressure to use it grows over time.

The counter-argument that wins is: when the first reportable AI-safety incident occurs, the privacy posture under Option C will be visibly inadequate to regulators, to users, and to counsel. The principled position will be characterized as careless. Option D builds a narrow, audited, transparent capability that holds up better in the moment. The capability-accretion risk is real but the worst case under C is worse than the worst case under D.

The decision stands.

---

## Change Log

| Version | Date | Changes | Author |
|---|---|---|---|
| v1 | May 19, 2026 | Initial decision document. Option D selected. Document chain touchpoints enumerated; Safety Logging Notice flagged as new deliverable. | Privacy Lead |
| v2 | May 30, 2026 | Contact-address consolidation to the two approved addresses: `help@aidstation.pro` for user support (including privacy / data-rights requests) and `info@aidstation.pro` for formal, legal, security, and DMCA correspondence. No other changes. | Privacy Lead |
