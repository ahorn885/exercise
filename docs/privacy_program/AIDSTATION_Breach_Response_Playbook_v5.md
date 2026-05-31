# AIDSTATION Breach Response Playbook

**Status:** Internal operational document — v5 (cross-reference unversioning cleanup; no substantive change since v4)
**Audience:** AIDSTATION personnel responding to data security incidents
**Owner:** [Privacy Lead]
**Last Updated:** May 20, 2026
**Review Cycle:** Annual + after every Tier 1 or 2 incident

---

## 1. Purpose

This playbook is what you follow when a data security incident occurs. It exists so that the response is fast, consistent, and compliant — even at 2am, even if the person on call hasn't responded to a breach before, even if multiple jurisdictions are in play.

The playbook covers detection, triage, containment, notification, investigation, remediation, documentation, and post-incident review. It includes specific timelines, decision criteria, and templates.

**The playbook is mandatory.** Departures from it require approval from the Incident Commander and must be documented in the incident log with rationale.

---

## 2. Definitions

**Security Incident.** Any event that compromises or appears to compromise the confidentiality, integrity, or availability of AIDSTATION systems or data. Includes suspected incidents pending confirmation.

**Personal Data Breach.** A Security Incident leading to the accidental or unlawful destruction, loss, alteration, unauthorized disclosure of, or access to Personal Data. The legal trigger for many notification obligations.

**Sensitive Data.** Personal Data classified as sensitive under applicable law — health and biometric data, precise location, sensitive personal information under CCPA/CPRA. AIDSTATION processes Sensitive Data at scale; incidents involving Sensitive Data are presumed higher severity.

**Affected Person.** A natural person whose Personal Data is affected by the incident.

### Not a Personal Data Breach

The following matters are not Personal Data Breaches in themselves and are handled outside this playbook, even when their workflows touch breach-adjacent surfaces:

- **Copyright disputes.** A DMCA notice, counter-notification, or repeat-infringer matter is a copyright matter, not a Personal Data Breach. These are handled under `AIDSTATION_DMCA_Designated_Agent_Spec` and the PA-16 processing activity in `AIDSTATION_RoPA`. If a copyright matter surfaces alongside a Security Incident (for example, a complainant alleging unauthorized use of identifiable personal data in a training dataset raises both copyright and privacy concerns), the Security Incident is classified and handled under this playbook; the copyright matter is handled in parallel under the DMCA process. The two processes do not block each other.
- **Data subject rights (DSR) requests.** Access, correction, deletion, and similar rights requests under PP §9 are handled per the DSR process. A high volume of DSR requests does not by itself indicate a breach.
- **Acceptable Use Policy violations.** AUP suspension or termination decisions are handled per T&C §11 and §14. An AUP violation is not by itself a Personal Data Breach.
- **Routine operational errors.** Misdirected emails, incorrect form-letter content, and similar low-impact errors are handled per the operational triage process. These may, in specific circumstances, escalate to Tier 4 or higher under this playbook; that escalation is the decision point.

When in doubt about whether a matter is a Personal Data Breach, classify it under this playbook and let the §6 assessment refine the classification. The "when in doubt, classify higher" principle below applies to the breach-vs-not-breach boundary as well.

### Severity Tiers

| Tier | Description | Examples |
|---|---|---|
| **Tier 1 — Critical** | Confirmed unauthorized access to Sensitive Data of multiple users, or unauthorized exfiltration of any user data, or active ongoing attack | Database breach with confirmed data exfiltration; ransomware with access to user data; insider data theft |
| **Tier 2 — High** | Confirmed Personal Data Breach not meeting Tier 1; suspected Tier 1 pending confirmation | Unauthorized access to a single user account leading to data exposure; subprocessor breach affecting AIDSTATION users; lost device with unencrypted data |
| **Tier 3 — Medium** | Security Incident affecting systems but no confirmed Personal Data Breach | Compromised employee credentials (no confirmed data access); successful phishing attack contained before data access |
| **Tier 4 — Low** | Security event without breach implications | Unsuccessful intrusion attempts; minor misconfigurations identified and corrected |

Severity is initially assessed at detection and refined as information becomes available. **When in doubt, classify higher** — under-classification is the more dangerous error.

---

## 3. Roles and Responsibilities

Roles can be combined in a small team. The minimum is one person responsible for each role, identifiable in any incident.

| Role | Responsibilities | Initial Holder |
|---|---|---|
| **Incident Commander (IC)** | Overall incident response coordination; severity classification; final decisions; chairs incident calls | [Privacy Lead or Engineering Lead] |
| **Privacy Lead** | Notification decisions; regulator engagement; legal coordination; user communications | [TBD] |
| **Engineering Lead** | Technical containment; forensic preservation; root cause analysis; remediation | [TBD] |
| **Communications Lead** | Drafting user and public communications; press response if needed | [TBD or Privacy Lead] |
| **Counsel** | Legal advice on notification obligations and external communications | [External counsel] |
| **DPO** | Where appointed, advises on GDPR obligations and supervisory authority engagement | [TBD when appointed] |
| **External Stakeholders** | EU Representative, UK Representative, POPIA Information Officer | [TBD when appointed] |

Contact details for all roles, including out-of-hours numbers, are maintained in the on-call rotation document. **Verify this list quarterly.**

---

## 4. Detection

Incidents can originate from any of the following. The first responder must immediately escalate to the on-call Incident Commander.

**Internal sources:**
- Monitoring alerts (intrusion detection, anomaly detection, error rate spikes)
- Engineering team observation during normal work
- Audit log review

**External sources:**
- User reports (help@aidstation.pro, support channels)
- Subprocessor notifications (under their DPA obligations — see §7.3)
- Researcher disclosures (responsible disclosure submissions)
- Public reports (security blogs, social media)
- Law enforcement notification

**On detection, the first responder:**

1. Does not attempt to investigate alone if the situation is ambiguous or escalating.
2. Contacts the on-call Incident Commander immediately (phone, not email).
3. Writes down what they know: what was observed, when, how they became aware.
4. Preserves evidence — does not delete logs, alerts, emails, or messages related to the incident.
5. Does not communicate externally about the incident until the IC authorizes.

---

## 5. Initial Response (T+0 to T+24 hours)

The IC activates response procedures on receiving the initial report.

### 5.1 Activate Response Team (T+0 to T+1h)
- IC convenes incident call with Privacy Lead, Engineering Lead, Communications Lead
- Establishes communication channel (dedicated Slack channel or call bridge)
- Assigns scribe to maintain real-time incident log
- Notifies counsel if Tier 1 or 2

### 5.2 Initial Triage and Containment (T+0 to T+4h)
**Engineering Lead and team:**
- Confirm the incident is real (rule out false positive)
- Contain immediately if active (revoke credentials, isolate systems, block network paths)
- Preserve evidence: snapshot affected systems, capture logs before retention windows expire
- Begin scope assessment: what systems, what data, how many users

**Containment principles:**
- Containment takes priority over investigation
- Preserve evidence while containing — don't destroy logs in the process of stopping the attack
- Document every action taken with timestamps

### 5.3 Severity Classification (Target T+4h; outer bound T+8h)
The IC assigns initial severity based on available information. **Target initial classification within 4 hours of awareness; outer bound 8 hours for complex cases requiring forensic confirmation.** Severity is re-evaluated continuously and adjusted as facts emerge. Initial classification triggers the response timeline below and the §6 assessment cadence; getting it on the record early creates cushion against the §6.2 T+24h notification-decision waypoint and the 72-hour Art. 33 clock.

### 5.4 Communication Hold (T+0 to T+24h, longer if needed)
- No external communications about the incident until authorized by IC
- Internal communications limited to the response team
- Status updates to broader organization only on need-to-know basis

### 5.5 Subprocessor Coordination
If the incident originated at or involves a subprocessor (Anthropic, Vercel, Neon, SendGrid, WordPress.com, etc.):
- Open incident channel with subprocessor under their DPA obligations
- Request all available information on scope and timing
- Coordinate user-facing communications to avoid contradictions

---

## 6. Assessment

### 6.1 Assessment Matrix (T+24h to T+72h)

By 72 hours from detection, the response team must have a clear answer to each of the following. If the answer is still "unknown," that itself is information for notification decisions.

| Question | Answer |
|---|---|
| Is this a Personal Data Breach? | Yes / No / Likely / Unknown |
| What categories of Personal Data are involved? | [list] |
| Is Sensitive Data involved? | Yes / No |
| How many Affected Persons (approximate)? | [number] |
| Which jurisdictions are affected (where do Affected Persons live)? | [list] |
| What is the likely cause? | [hypothesis] |
| Is the incident contained? | Yes / Partially / No |
| Is there evidence of malicious actor activity (exfiltration, sale, public disclosure)? | Yes / No / Unknown |
| What is the risk of harm to Affected Persons? | Low / Medium / High |

The risk assessment in the final row drives most notification decisions. **High risk** generally means: identity theft potential, financial harm, physical safety risk, significant reputational harm, or unauthorized disclosure of Sensitive Data that the person would not have chosen to share.

### 6.2 Notification Decision Waypoint (T+24h)

By **T+24h** from awareness, the response team must reach a working notification decision: notify, do not notify, or still gathering information. This waypoint is binding — it gives 48 hours of cushion before the 72-hour Art. 33 clock and the parallel jurisdictional clocks in §7.1 expire.

A working "do not notify" decision at T+24h must be supported by a §6.3 carve-out analysis. A working "still gathering information" decision at T+24h must specify what is being gathered, who is gathering it, and when the working decision will be reconverged — typically within 24 more hours, leaving 24 hours of remaining cushion against the 72-hour clock.

The T+24h decision is working, not final. New information through T+72h may move the decision. Every change of working decision is documented in the incident log with rationale.

### 6.3 Art. 33(1) Risk Carve-Out Analysis

GDPR Art. 33(1) requires supervisory-authority notification *unless the Personal Data Breach is unlikely to result in a risk to the rights and freedoms of natural persons.* The "unlikely to result in risk" carve-out is a real lawful position — but invoking it requires a documented analysis. This subsection operationalizes that analysis.

**Inputs to the analysis:**

1. **Nature of the data.** Is it Sensitive Data (presumed higher risk)? Identifiers alone, or combined with content? Free-text content that may include unstructured Sensitive Data?
2. **Volume and scope.** Single record, single user, or many?
3. **Effectiveness of technical mitigations.** Was the data encrypted with keys not compromised by the incident? Pseudonymized in a form not reversible by an attacker with the breached data set? Otherwise rendered unintelligible to unauthorized recipients?
4. **Likelihood of misuse.** Is there evidence of actor capability or motivation to exploit the data (criminal actor with exfiltration capability vs. accidental internal exposure)?
5. **Reversibility.** Has the exposure been remediated? Was the data deleted before it could be retained or shared by an unauthorized party?
6. **Categories of affected persons.** Are minors involved? Other vulnerable categories?

**Decision rule:** If the answer to each of the relevant factors above supports "no realistic prospect of risk to data subjects' rights and freedoms," the Art. 33(1) carve-out is available. The IC documents the analysis in the incident log per §12.1, including each input and the reasoning, and records a "do not notify supervisory authority" decision. If *any* relevant factor is uncertain, the carve-out is not available and the breach is notified.

**Default posture.** The carve-out is meaningful but narrow. Most breaches involving Sensitive Data — including most realistic AIDSTATION breach scenarios (health data, biometric data, precise location) — do not meet the carve-out. The carve-out is most likely to apply to: low-volume internal misroutes contained before exfiltration; encrypted-at-rest breaches where the attacker did not obtain decryption keys; cases where pseudonymization was robust enough that the breached data is not reasonably linkable to identifiable persons.

**Documentation discipline.** Invoking the Art. 33(1) carve-out without documented analysis converts a defensible decision into a regulatory exposure. The analysis must exist in writing before the no-notification decision is final.

---

## 7. Notification Decision Matrix

This matrix is the operational core of the playbook. Notification obligations vary by jurisdiction and by the nature of the incident.

### 7.1 Regulator Notifications

| Jurisdiction | When Required | Timeline | Authority |
|---|---|---|---|
| **EU (GDPR Art. 33)** | Personal Data Breach unless unlikely to result in risk to rights and freedoms (see §6.3) | 72 hours from awareness | Lead supervisory authority |
| **UK (UK GDPR Art. 33)** | Same as EU | 72 hours from awareness | ICO |
| **California (CCPA + civil code)** | If unencrypted personal information acquired; AG notification if 500+ residents affected | "Most expedient time possible without unreasonable delay"; AG notice on consumer notification | California AG |
| **Other US states** | Varies — most require notification on confirmed acquisition of personal info | Varies — most "without unreasonable delay"; some specific (e.g., NY 30 days) | State AG or designated authority |
| **Canada (PIPEDA)** | If "real risk of significant harm" | "As soon as feasible" | Office of the Privacy Commissioner of Canada |
| **Quebec (Law 25)** | Confidentiality incident with risk of serious injury | Promptly | Commission d'accès à l'information |
| **Australia (Privacy Act)** | "Eligible data breach" — likely to result in serious harm | 30 days from awareness to assess; notification "as soon as practicable" | Office of the Australian Information Commissioner |
| **New Zealand (Privacy Act 2020)** | "Notifiable privacy breach" — likely to cause serious harm | "As soon as practicable" (typically within 72 hours) | Privacy Commissioner |
| **South Africa (POPIA)** | Reasonable grounds to believe personal information has been compromised | "As soon as reasonably possible" | Information Regulator |

**Decision principle.** Notify when the applicable jurisdiction's legal standard is met (see matrix above). Where the standard is *not* met after the §6.3 Art. 33(1) risk carve-out analysis — or its jurisdictional equivalent (e.g., the "real risk of significant harm" threshold under PIPEDA; the "serious harm" threshold under Australia's Privacy Act) — document the analysis supporting the no-notification conclusion in the incident log per §12.1, and proceed without notification to that authority.

Genuine uncertainty about whether the legal standard is met defaults to notifying — do not let optimism substitute for analysis. Every notification decision, whether to notify or not, is documented with rationale per §12.1. Under-notification of a notifiable breach is a violation; over-notification of a non-notifiable breach is a manageable operational cost.

### 7.2 Affected Person Notifications

| Jurisdiction | When Required | Timeline |
|---|---|---|
| **EU/UK** | If **high risk** to rights and freedoms (Art. 34 GDPR) — note this is a tighter standard than Art. 33 supervisory authority notification | Without undue delay |
| **California** | If unencrypted personal info, SSN/financial/medical data | Without unreasonable delay |
| **Other US states** | Varies — typically required for confirmed breach involving SSN/financial data | Varies |
| **Canada / Quebec** | If real risk of significant harm | As soon as feasible |
| **Australia** | If eligible data breach | As soon as practicable |
| **New Zealand** | If notifiable privacy breach | As soon as practicable |
| **South Africa** | If reasonable grounds to believe compromise | As soon as reasonably possible |

**Art. 33 vs. Art. 34 — distinct standards.** Affected Person notification (Art. 34) triggers on *high risk* — a tighter standard than supervisory authority notification (Art. 33), which triggers on *risk*. A breach can require Art. 33 notification to the supervisory authority without triggering Art. 34 notification to data subjects.

**Art. 34(3) mitigation conditions.** The high-risk threshold for Affected Person notification can be defeated by any of:

(a) appropriate technical and organizational protection measures applied to the affected Personal Data, in particular those that render the data unintelligible to any unauthorized person (e.g., strong encryption with keys not compromised by the incident);
(b) subsequent measures taken by the controller that ensure the high risk to data subjects' rights and freedoms is no longer likely to materialize;
(c) notification would involve disproportionate effort, in which case a public communication or similar measure equally effective in informing data subjects is acceptable instead.

Where any Art. 34(3) condition applies, the controller documents the analysis and is not required to notify individual data subjects.

**AIDSTATION policy.** Affected Person notification follows the Art. 34 high-risk standard (or jurisdictional equivalent). Where the high-risk threshold is met after assessment and Art. 34(3) mitigation conditions do not apply, notify Affected Persons without undue delay using §9.2. Where the threshold is not met after documented analysis — including where Art. 34(3) mitigation conditions defeat the high-risk standard — do not notify on reflex.

**IC discretion.** The Incident Commander retains discretion to notify Affected Persons even where not legally required, on reputational, trust, communications-management, or other strategic grounds. Such discretionary notifications are documented in the incident log with rationale.

**Realistic AIDSTATION posture.** AIDSTATION processes Sensitive Data (health, biometric, precise location) at scale. In most realistic breach scenarios involving Sensitive Data, the high-risk threshold will be met and Art. 34 will require notification. The practical effect of the lens-aware default above is to:

(i) ensure that notification decisions go through documented analysis rather than reflex;
(ii) preserve the Art. 34(3) mitigation path where it genuinely applies (e.g., encrypted-at-rest data where decryption keys remain uncompromised);
(iii) make IC discretion to over-notify an explicit, documented choice rather than a hidden default.

### 7.3 Subprocessor-Originated Breaches
If the breach originated at a subprocessor, AIDSTATION (as controller) is responsible for notifying authorities and Affected Persons. Under the AIDSTATION DPA template (`AIDSTATION_DPA_Template` §4.7), the subprocessor's obligation is to notify AIDSTATION within **12 hours of becoming aware (preliminary notification) and 24 hours of becoming aware (full notification)**. AIDSTATION's 72-hour Art. 33 clock to regulators starts when AIDSTATION becomes aware, which may be triggered by either the preliminary or the full notification from the subprocessor.

Subprocessors operating under their own DPA (e.g., Anthropic, Vercel, Neon under their standard terms) may have different notification windows. The IC verifies the applicable window from the executed DPA on activation of the subprocessor coordination process (§5.5) and tracks the AIDSTATION-side awareness timestamp accordingly.

---

## 8. Notification Content

### 8.1 To Supervisory Authorities (GDPR Art. 33(3) framework)

Required content:
- Nature of the Personal Data Breach (categories of Personal Data and Affected Persons; approximate numbers)
- Name and contact details of DPO or other contact point
- Likely consequences
- Measures taken or proposed

If information is incomplete at the 72-hour mark, notify with what you have and supplement as more becomes known. **Do not delay the initial notification to gather complete information.**

### 8.2 To Affected Persons

Required and recommended content:
- Description of the incident in plain language
- Categories of data affected (specific to the individual where possible)
- Likely consequences for them
- Measures AIDSTATION has taken
- Recommended steps the person can take
- Contact for questions
- Where to find further information

**Tone:** Direct, honest, non-defensive. Avoid corporate-speak. Match the AIDSTATION coaching voice — say what happened, what we're doing about it, what they should do.

---

## 9. Communication Templates

These are starting points. Adapt for the specific incident. Counsel review before sending.

### 9.1 Supervisory Authority Notification (Template)

```
Subject: Personal Data Breach Notification — AIDSTATION

To: [Supervisory Authority]

Pursuant to [Article 33 GDPR / equivalent provision], AIDSTATION provides notice of the following Personal Data Breach.

1. Nature of the Breach
[Concise description of what occurred, including the type of incident — unauthorized access, accidental disclosure, ransomware, etc.]

2. Date and Time
Date of incident (if known): [date]
Date of detection: [date]
Date of this notification: [date]

3. Affected Personal Data
Categories: [list]
Number of records affected (approximate): [number]
Categories of Data Subjects affected: AIDSTATION users
Number of Data Subjects affected (approximate): [number]

4. Likely Consequences
[Description of risk to Data Subjects]

5. Measures Taken
[Containment, investigation, remediation steps]

6. Contact Point
[Name, title, email, phone]

Additional information will be provided as the investigation continues.
```

### 9.2 Affected Person Notification (Template)

```
Subject: An important update about your AIDSTATION account

Hi [first name],

We're writing to let you know about a security incident that may have affected your AIDSTATION account.

What happened
On [date], we [discovered / were notified of] [brief description in plain language].

What information was involved
The incident affected the following types of information associated with your account: [list]. [Note any types of data that were not affected, if relevant.]

What we're doing about it
[Specific steps: contained, investigated, remediated, additional security measures]

What you can do
[Specific actions: change password, review activity, watch for phishing, etc.]

We're sorry this happened. If you have questions, contact us at help@aidstation.pro and we'll respond as quickly as we can.

[Sign-off — from a real person, with name and title]
```

### 9.3 Public Statement Template (if needed)

Only published when the incident is public knowledge or the IC determines proactive disclosure is appropriate. Coordinate with counsel.

```
On [date], AIDSTATION [discovered / was notified of] a security incident affecting [scope]. We have [contained / are investigating / have notified affected users].

We take the security and privacy of athlete data seriously. We are conducting a full investigation and have engaged [external security firm if applicable] to assist.

Affected users are being notified directly. Users with questions can contact help@aidstation.pro.

We will update this page as the investigation progresses.
```

---

## 10. Investigation and Root Cause Analysis

Parallel to notification, the Engineering Lead conducts forensic investigation:

- **Forensic preservation:** Snapshots, log captures, malware samples (if applicable). Chain of custody maintained for any evidence that may be needed for law enforcement or litigation.
- **Scope confirmation:** Verify the initial scope assessment with detailed log review. Are there other accounts affected that weren't initially identified? Other data categories? Other time windows?
- **Root cause analysis:** What technical and process failures allowed this? What controls failed? What did not work as designed?

Investigation findings inform both the notification content and the remediation plan.

---

## 11. Remediation

Remediation occurs in two phases.

### 11.1 Immediate (during incident)
- Stop the bleeding: patch the vulnerability, revoke credentials, isolate compromised systems
- Restore service: bring affected systems back online safely
- User-facing remediation: forced password resets, security review prompts, account reviews

### 11.2 Long-term (post-incident)
- Address root cause systemically (not just the specific instance)
- Update monitoring to detect similar incidents earlier
- Update access controls, encryption, or other technical controls
- Update procedures if the cause was procedural
- Training if the cause was personnel error

Remediation plans have owners and deadlines. The IC tracks them through completion.

---

## 12. Documentation

### 12.1 Incident Log
Maintained from initial detection through final resolution. Includes:
- Timeline of events with timestamps
- Decisions made and rationale — including the §6.3 risk carve-out analysis where a no-notification decision is reached, and the §7.2 Art. 34(3) mitigation analysis where Affected Person notification is not given
- Communications sent (to whom, when, content)
- Investigation findings
- Remediation actions
- Notification records (which authorities, which users) — including documented "no notification" decisions where applicable

**Art. 33(5) record-keeping.** This incident log satisfies the controller's documentation obligation under GDPR Art. 33(5) and equivalent provisions. The obligation applies to *every* Personal Data Breach, including those that do not trigger notification under §7.1 or §7.2 — the documentation must be sufficient to allow a supervisory authority to verify compliance after the fact. A no-notification decision without an incident log is a more serious exposure than a notified breach.

### 12.2 Retention
Incident documentation is retained for **at least 5 years** from incident closure. Required for regulatory inquiries and lessons-learned reference. May be retained longer if litigation is foreseeable.

### 12.3 Confidentiality
Incident documentation is confidential. Internal access is limited to the response team, executives with need to know, and legal counsel. External sharing requires IC approval.

---

## 13. Post-Incident Review

Within **30 days** of incident closure, conduct a blameless post-incident review.

### Agenda
- Timeline review: what happened and when
- Detection: how did we know? Could we have known sooner?
- Response: what went well? What didn't?
- Notification: were timelines met? Were communications effective?
- Root cause: confirmed and addressed?
- Process improvements: what changes to the playbook, technical controls, or training are warranted?

### Output
A written post-incident report covering the above. Reviewed by the IC, Privacy Lead, and Engineering Lead. Action items tracked through completion.

Updates to this playbook flowing from post-incident reviews are documented in the change log at the bottom of this document.

---

## 14. Training and Testing

### Annual Tabletop Exercise
Once per year, the response team runs a tabletop simulation of a Tier 1 or 2 incident. Goals:
- Test that on-call procedures work
- Test that contact lists are current
- Test decision-making under time pressure
- Surface gaps in the playbook

### Onboarding
All new personnel with roles in incident response review this playbook within their first 30 days. Role-specific briefings for IC, Privacy Lead, and Engineering Lead candidates.

### Quarterly Verification
- Contact lists verified current
- On-call rotation confirmed
- Subprocessor incident contact details verified

---

## 15. Reference Lists

### 15.1 Supervisory Authority Contacts

| Jurisdiction | Authority | Submission Channel |
|---|---|---|
| EU (lead authority per Art. 56) | [Determined based on lead authority] | [Authority's portal] |
| UK | ICO | ico.org.uk/report |
| California | California AG | oag.ca.gov |
| Other US states | State AGs | State-specific |
| Canada | Office of the Privacy Commissioner | priv.gc.ca |
| Quebec | Commission d'accès à l'information | cai.gouv.qc.ca |
| Australia | OAIC | oaic.gov.au |
| New Zealand | Privacy Commissioner | privacy.org.nz |
| South Africa | Information Regulator | inforegulator.org.za |

### 15.2 Subprocessor Incident Contacts
[To be maintained by Privacy Lead based on current DPAs.]

### 15.3 External Counsel
[Name, firm, phone, email of designated privacy/data security counsel.]

### 15.4 Forensic Investigation Vendor
[Pre-identified vendor for incidents requiring third-party forensics. Engaged in advance with a retainer agreement so they can be activated quickly.]

---

## Change Log

| Version | Date | Changes | Author |
|---|---|---|---|
| v1 | (superseded) | Initial version | [Privacy Lead] |
| v2 | May 19, 2026 | Privacy contact email updated to help@aidstation.pro across detection sources and user/public notification templates | [Privacy Lead] |
| v3 | May 19, 2026 | Track A Group 2 cross-reference edit (D-107). New "Not a Personal Data Breach" subsection added to §2 Definitions, before Severity Tiers. Covers DMCA copyright matters, DSR requests, AUP violations, and routine operational errors as not-by-themselves Personal Data Breaches. Includes parallel-process rule for copyright matters surfacing alongside Security Incidents and preserves the "when in doubt, classify higher" default. No changes to detection, response, notification, or remediation logic. | [Privacy Lead] |
| v4 | May 20, 2026 | Tier 2 lens pass (operator-favorable + lawful + single global rule). §5.3 initial severity classification timeline tightened to a 4-hour target with 8-hour outer bound (was T+0–T+8h flat), to build cushion against the §6.2 T+24h notification waypoint and the 72-hour Art. 33 clock. §6 restructured: existing assessment matrix retained as §6.1; new §6.2 "Notification Decision Waypoint (T+24h)" added, making the 24-hour internal decision an explicit, documented waypoint; new §6.3 "Art. 33(1) Risk Carve-Out Analysis" added, operationalizing the lawful "unlikely to result in risk" carve-out with structured inputs, decision rule, and documentation discipline. §7.1 decision principle rewritten — replaces "default to notifying" reflex with a legal-standard default plus documented no-risk analysis where the standard is not met; uncertainty still defaults to notify. §7.2 expanded: explicit Art. 33 vs. Art. 34 standard distinction; Art. 34(3) mitigation conditions named; AIDSTATION default policy rewritten from "always notify on Sensitive Data" to "notify when the high-risk threshold is met (or genuinely uncertain), with documented analysis where it is not"; IC discretion to over-notify explicit; honest framing of realistic AIDSTATION posture (Sensitive Data scenarios usually meet the high-risk threshold anyway, so practical effect is small). §7.3 subprocessor breach notification window updated from 48 hours to 12 hours preliminary + 24 hours full, aligning with `AIDSTATION_DPA_Template_v3.md` §4.7. §12.1 incident log expanded to record §6.3 and §7.2 analyses, and explicit Art. 33(5) record-keeping recognition added — the incident log doubles as the Art. 33(5) record, including for non-notified breaches. No changes to detection, containment, investigation, remediation, post-incident review, training, or reference list sections. (Privacy Program Backlog: Tier 2 lens batch — Breach Playbook lens pass per Track A G2 Closing Handoff §5.2.) | [Privacy Lead] |
| v5 | May 30, 2026 | Contact-address consolidation to the two approved addresses: `help@aidstation.pro` for user support (including privacy / data-rights requests) and `info@aidstation.pro` for formal, legal, security, and DMCA correspondence. No other changes. | Privacy Lead |

---

*Cross-reference cleanup (v5, 2026-05-30): inline references to companion documents were converted to unversioned logical names per Rule #12, so they no longer go stale when a companion document is revised. No substantive content changes. See `Privacy_Program_Consistency_Sweep_Report_v1.md`.*

