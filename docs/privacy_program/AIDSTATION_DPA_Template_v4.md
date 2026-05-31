# Data Processing Agreement
## Template — AIDSTATION as Controller

**Status:** v4 — contact-address consolidation (no substantive change since the v3 Tier 2 lens pass). Template requiring legal review before execution.
**Use Cases:** Service providers (subprocessors) and university research partners engaged by AIDSTATION
**Last Updated:** May 30, 2026

---

## Important Notes Before Use

This template is drafted for the most common scenario: **AIDSTATION acts as data controller** and the counterparty acts as data processor. Where the counterparty already has a strong DPA they require you to sign (Anthropic, Vercel, Stripe, etc.), use their DPA after reviewing for material conflicts with this template's principles — paying particular attention to Section 4.7 (Security Incident timing), Section 4.12 (No Secondary Use), Section 7 (Liability carve-outs), and Section 8 (cure periods).

This is a legal contract. **Have counsel review before execution.** This template provides a strong starting point but is not a substitute for legal advice. Specific deal terms (term, fees, jurisdiction, liability caps) should be negotiated in the underlying services agreement, not in the DPA.

The values in this template reflect AIDSTATION's preferred opening positions under the operator-favorable + lawful + single-global-rule lens. Counterparties will commonly push back on the 24-hour breach notification (Section 4.7), the 5-business-day DSR assistance window (Section 4.5), and the 14-day cure period (Section 8). The template states the position AIDSTATION asks for; negotiated outcomes are documented in the executed DPA.

---

## Data Processing Agreement

This Data Processing Agreement ("**DPA**") forms part of the agreement between:

- **AIDSTATION Pro, LLC**, a Texas limited liability company (the "**Controller**"), and
- **[Counterparty Name]** (the "**Processor**"),

each a "**Party**" and together the "**Parties**."

It is effective on the **Effective Date** of the underlying Services Agreement, Research Data Use Agreement, or similar instrument (the "**Principal Agreement**") between the Parties, and applies whenever the Processor processes Personal Data on behalf of the Controller.

---

## 1. Definitions

Capitalized terms used in this DPA have the meanings set out below. Terms not defined here have the meanings given in Applicable Data Protection Laws.

**Applicable Data Protection Laws** means all laws and regulations applicable to the processing of Personal Data under this DPA, including but not limited to: the EU General Data Protection Regulation (2016/679) ("**GDPR**"), the United Kingdom GDPR and Data Protection Act 2018 ("**UK GDPR**"), the California Consumer Privacy Act and California Privacy Rights Act ("**CCPA/CPRA**"), other US state privacy laws, Canada's Personal Information Protection and Electronic Documents Act ("**PIPEDA**") and Quebec's Law 25, Australia's Privacy Act 1988, New Zealand's Privacy Act 2020, and South Africa's Protection of Personal Information Act ("**POPIA**").

**Controller Personal Data** means Personal Data that is supplied by, generated for, or otherwise made available to the Processor by or on behalf of the Controller for Processing under this DPA, and includes any derivatives thereof in the Processor's possession or under the Processor's control.

**Personal Data**, **Processing**, **Controller**, **Processor**, **Sub-processor**, **Data Subject**, and **Supervisory Authority** have the meanings given in the GDPR.

**Sensitive Personal Data** means Personal Data that is "special category" data under GDPR/UK GDPR, "sensitive personal information" under CCPA/CPRA, or analogous categories under other Applicable Data Protection Laws. For AIDSTATION, this includes health data, biometric data, precise location data, and any other categories described in Annex 1.

**Security Incident** means any breach of security leading to the accidental or unlawful destruction, loss, alteration, unauthorized disclosure of, or access to, Personal Data processed under this DPA.

**Standard Contractual Clauses** or "**SCCs**" means the standard contractual clauses approved by the European Commission (Commission Implementing Decision (EU) 2021/914) and, where applicable, the UK International Data Transfer Addendum.

---

## 2. Subject Matter, Duration, and Scope

### 2.1 Subject Matter
The Processor processes Personal Data on the Controller's behalf to perform the services described in the Principal Agreement.

### 2.2 Duration
This DPA is effective on the Effective Date of the Principal Agreement and remains in force for as long as the Processor processes Personal Data on the Controller's behalf, plus any post-termination period required to return or delete Personal Data under Section 4.10.

### 2.3 Scope of Processing
The nature, purpose, types of Personal Data, categories of Data Subjects, frequency, and retention of Processing are set out in **Annex 1**.

---

## 3. Roles of the Parties

The Controller is the controller of the Personal Data processed under this DPA. The Processor is a processor (and, where applicable, a service provider under the CCPA/CPRA) acting on documented instructions from the Controller.

The Processor shall not act as a controller, sell, share, or otherwise use Personal Data for its own purposes. The Processor shall not combine Personal Data received under this DPA with data from other sources, except as strictly necessary to provide the contracted services. The restrictions in Section 4.12 (No Secondary Use; No Training on Controller Data) further constrain how the Processor may use Controller Personal Data.

---

## 4. Processor Obligations

### 4.1 Processing on Instructions
The Processor shall process Personal Data only on the documented instructions of the Controller, including with regard to transfers of Personal Data to a third country.

The Principal Agreement, this DPA (including Annex 1), and any subsequent written instructions issued by the Controller constitute documented instructions.

The Processor shall promptly inform the Controller if, in the Processor's opinion, an instruction infringes Applicable Data Protection Laws. The Processor is not required to follow an unlawful instruction.

### 4.2 Confidentiality
The Processor shall ensure that all personnel authorized to process Personal Data:

(a) are committed to confidentiality, whether by contract or under statutory obligation;
(b) access Personal Data only on a need-to-know basis; and
(c) receive appropriate training in data protection.

### 4.3 Security
The Processor shall implement and maintain appropriate technical and organizational measures to ensure a level of security appropriate to the risk, as set out in **Annex 2**.

Measures shall include, at minimum:

(a) encryption of Personal Data in transit and at rest where appropriate;
(b) the ability to ensure ongoing confidentiality, integrity, availability, and resilience of processing systems;
(c) the ability to restore the availability of and access to Personal Data in a timely manner in the event of an incident;
(d) a process for regularly testing, assessing, and evaluating the effectiveness of measures;
(e) role-based access controls and authentication;
(f) logging and monitoring of access to Personal Data; and
(g) personnel training on data protection and security.

### 4.4 Sub-processing

(a) The Processor shall not engage any Sub-processor to process Personal Data without prior general or specific authorization from the Controller.

(b) The Controller hereby provides general authorization for the Sub-processors listed in **Annex 3**, with the right to object as described below.

(c) The Processor shall give the Controller at least **30 days' prior written notice** of any intended addition or replacement of Sub-processors. The notice shall identify the proposed Sub-processor, its location, the services it will provide, and a summary of its data protection and security posture sufficient for the Controller to evaluate the engagement. The Controller may object within that period on any reasonable grounds, including data protection, security, regulatory, or commercial considerations. If the Controller objects and the Parties cannot reach a resolution, the Controller may, at its discretion, (i) terminate the Principal Agreement (or the affected portion) without liability, or (ii) require the Processor to continue providing the services without engaging the proposed Sub-processor.

(d) The Processor shall impose data protection obligations on any Sub-processor that are at least as protective as those in this DPA, including the SCCs where applicable, and including the restrictions in Section 4.12.

(e) The Processor remains fully liable to the Controller for the performance of its Sub-processors.

### 4.5 Assistance with Data Subject Rights
The Processor shall, taking into account the nature of the Processing, assist the Controller by appropriate technical and organizational measures, insofar as possible, in responding to requests from Data Subjects to exercise their rights under Applicable Data Protection Laws.

If a Data Subject contacts the Processor directly, the Processor shall promptly forward the request to the Controller and shall not respond except on the Controller's instructions or as required by law.

The Processor shall respond to the Controller's reasonable requests for assistance within **5 business days**. Where a request cannot be fully addressed within 5 business days, the Processor shall provide a status update within that window and shall complete the requested assistance without further delay.

### 4.6 Assistance with Compliance Obligations
The Processor shall assist the Controller in ensuring compliance with the Controller's obligations regarding:

(a) security of Processing;
(b) notification of Personal Data Breaches to Supervisory Authorities and Data Subjects;
(c) Data Protection Impact Assessments (DPIAs); and
(d) prior consultation with Supervisory Authorities.

### 4.7 Security Incident Notification

The Processor shall notify the Controller of any Security Incident affecting Personal Data in two stages:

(a) **Preliminary notification — within 12 hours of becoming aware of the Security Incident.** Preliminary notification shall identify that an incident has occurred and the affected systems or data sets, even if full investigation has not yet been completed. Preliminary notification is required even where the Processor is still verifying that the incident in fact involves Personal Data.

(b) **Full notification — without undue delay and in any event within 24 hours of becoming aware of the Security Incident.** Full notification shall include, to the extent known:

(i) a description of the nature of the Security Incident, including categories and approximate number of Data Subjects and records affected;
(ii) the name and contact details of a point of contact for further information;
(iii) the likely consequences of the Security Incident;
(iv) the measures taken or proposed to address the Security Incident and mitigate its possible adverse effects.

Information not available at initial notification shall be provided in phases as it becomes available. The Processor shall cooperate fully with the Controller's incident response. The Controller's 72-hour notification clock under GDPR Art. 33(1) begins when the Controller becomes aware of the Security Incident, which may be triggered by either the preliminary or the full notification under this Section 4.7.

### 4.8 Records of Processing
The Processor shall maintain a record of all categories of Processing activities carried out on behalf of the Controller, as required by Article 30(2) GDPR and equivalent provisions of other Applicable Data Protection Laws.

### 4.9 Audits and Inspections

(a) The Processor shall make available to the Controller, on reasonable request, all information necessary to demonstrate compliance with this DPA. The Controller may conduct or commission audits of the Processor's compliance with this DPA no more than once per calendar year, except where:

(i) a Security Incident has occurred;
(ii) the Controller has documented reasonable concern regarding the Processor's compliance with this DPA, Applicable Data Protection Laws, or material security or privacy obligations; or
(iii) audit is required by a Supervisory Authority or by Applicable Data Protection Laws.

In any of the circumstances in (i)–(iii), additional audits are permitted as reasonably required.

(b) Audits may be conducted by the Controller or by an independent third-party auditor of the Controller's choice (bound by confidentiality). The Controller shall give at least **30 days' written notice** before an audit, except in cases of suspected non-compliance or following a Security Incident, where notice may be shorter as is reasonable given the circumstances.

(c) Audits shall be conducted during regular business hours, with minimum disruption to the Processor's operations.

(d) **Desk audit substitution.** In lieu of an on-site audit, the Processor may provide current independent audit reports (SOC 2 Type II, ISO 27001, or equivalent) that adequately demonstrate compliance. The Controller may submit reasonable follow-up questions arising from such reports and may require the Processor to provide remediation plans and timelines for any material findings. The Controller's acceptance of a desk audit in one cycle does not waive its right to require an on-site audit in any subsequent cycle, or in the same cycle where the desk audit reveals matters that the Controller reasonably believes require on-site verification.

(e) **Cost allocation.** Each Party bears its own costs in connection with audits, except that the Processor shall reimburse the Controller's reasonable audit costs (including third-party auditor fees) where the audit reveals material non-compliance with this DPA or with Applicable Data Protection Laws.

### 4.10 Return and Deletion
On termination of the Principal Agreement, or at any time on the Controller's written request, the Processor shall, at the Controller's choice:

(a) return all Personal Data to the Controller in a commonly used machine-readable format; or
(b) delete all Personal Data and certify deletion in writing.

The Processor may retain copies only to the extent required by applicable law, and shall continue to apply this DPA (including Section 4.12) to any retained data.

Return or deletion shall be completed within **30 days** of termination or request, unless a different period is required by law or specified in writing by the Controller.

### 4.11 Data Localization
The Processor shall not transfer Personal Data to any jurisdiction outside the locations specified in Annex 1 without the Controller's prior written consent. International transfers, where authorized, are governed by Section 5.

### 4.12 No Secondary Use; No Training on Controller Data

(a) **Restricted use.** The Processor shall not use, copy, retain, transfer, or otherwise process Controller Personal Data for any purpose other than performing the services set out in the Principal Agreement under the Controller's documented instructions.

(b) **No model training by Processor.** The Processor shall not use Controller Personal Data, or any derivative thereof (including embeddings, features, statistical summaries, model weights, or any other transformation), to train, fine-tune, develop, evaluate, validate, benchmark, or improve any machine learning model, artificial intelligence model, or other learning system that is owned, licensed, or operated by the Processor or any third party.

(c) **Controller-instructed training carve-out.** Section 4.12(b) does not prohibit the Processor from running, on the Processor's infrastructure and under the Controller's documented instructions, training, fine-tuning, evaluation, or inference operations on Controller Personal Data for the development or operation of models owned by the Controller. In such cases:

(i) the resulting model weights, embeddings, fine-tuned models, and any other derived artifacts are owned by the Controller;
(ii) the Processor shall not retain copies of such derived artifacts after termination of the relevant Processing, except as required by law or as expressly instructed by the Controller in writing;
(iii) the Processor shall not use such derived artifacts, or any information derived from the training process, for any purpose other than performing the Controller-instructed services.

(d) **No derivative products.** The Processor shall not create, retain, or distribute any aggregated, anonymized, pseudonymized, or otherwise derivative data products from Controller Personal Data, except as expressly instructed by the Controller in writing.

(e) **No combination.** The Processor shall not combine Controller Personal Data with data from other sources, except as strictly necessary to provide the services under the Principal Agreement on the Controller's documented instructions.

(f) **No commercial use.** The Processor shall not market, sell, license, lease, or otherwise commercialize Controller Personal Data or any derivative thereof.

(g) **Survival.** This Section 4.12 survives termination of this DPA and the Principal Agreement, and applies to any Controller Personal Data the Processor retains after termination under Section 4.10.

---

## 5. International Data Transfers

### 5.1 Transfer Mechanism
Where the Processor transfers Personal Data outside the European Economic Area, the United Kingdom, Switzerland, or any other jurisdiction requiring a transfer mechanism, the Parties shall use the Standard Contractual Clauses (with the UK Addendum where applicable) as the transfer mechanism, incorporated into this DPA by reference and completed as set out in **Annex 4**.

### 5.2 Module
The applicable module of the SCCs depends on the role of each Party:

(a) Module Two (Controller to Processor) applies where AIDSTATION (as Controller in the EEA) transfers Personal Data to the Processor (in a third country).
(b) Module Three (Processor to Processor) applies where AIDSTATION (as Processor for another party) transfers Personal Data to this Processor (as Sub-processor).

### 5.3 Transfer Impact Assessment
The Processor shall cooperate with the Controller in conducting and documenting Transfer Impact Assessments for international transfers, including by providing information about the legal regime applicable to the Processor in the receiving jurisdiction and any supplementary technical or organizational measures applied.

### 5.4 Government Access Requests
If the Processor receives a legally binding request from a public authority for disclosure of Personal Data, it shall:

(a) notify the Controller before responding, where legally permitted;
(b) challenge the request where there are reasonable grounds to do so;
(c) provide the minimum amount of information required; and
(d) document the request and its response, and make documentation available to the Controller on request.

---

## 6. Controller Obligations

The Controller represents and warrants that:

(a) it has a lawful basis to process Personal Data and to instruct the Processor to process Personal Data as described in this DPA;
(b) it has provided required notices to Data Subjects;
(c) where consent is the lawful basis, it has obtained valid consent;
(d) its instructions to the Processor comply with Applicable Data Protection Laws.

---

## 7. Liability and Indemnification

Each Party's liability arising from this DPA is governed by the liability provisions of the Principal Agreement, except that:

(a) the limitations of liability in the Principal Agreement shall apply on an aggregate basis across the Principal Agreement and this DPA, **subject to the carve-outs in subsection (d) below**;

(b) each Party shall indemnify the other against fines, penalties, or third-party claims arising from the indemnifying Party's breach of this DPA, subject to the limitations of liability in the Principal Agreement and the carve-outs in subsection (d);

(c) liability arising under the SCCs is determined under the SCCs themselves;

(d) **the limitations of liability in the Principal Agreement do not apply to the Processor's liability arising from:**

(i) breach of Section 4.2 (Confidentiality) of this DPA;
(ii) breach of any obligation under this DPA relating to Sensitive Personal Data, including unauthorized access, disclosure, or use;
(iii) breach of Section 4.12 (No Secondary Use; No Training on Controller Data) of this DPA;
(iv) intentional or grossly negligent breach of this DPA;
(v) fraud or willful misconduct; or
(vi) infringement of third-party intellectual property rights arising from Processor's processing in breach of this DPA.

**Processor indemnity scope.** The Processor shall indemnify, defend, and hold harmless the Controller from and against any third-party claims, supervisory authority fines, settlement amounts, reasonable attorneys' fees, and other losses arising from the Processor's breach of this DPA. This indemnity is uncapped with respect to the matters listed in subsection (d)(i)–(vi) above, and is otherwise subject to the limitations of liability in the Principal Agreement.

---

## 8. Term and Termination

This DPA terminates automatically on termination of the Principal Agreement, subject to the post-termination obligations in Section 4.10 and the survival of Section 4.12.

The Controller may terminate this DPA and the Principal Agreement immediately for cause if:

(a) the Processor materially breaches this DPA and fails to cure within **14 days** of written notice (or such shorter period as is reasonable given the nature of the breach); or

(b) the Processor breaches any obligation relating to the confidentiality or security of Sensitive Personal Data, or any obligation under Section 4.12 — in which case the Controller may terminate immediately without any cure period.

---

## 9. Miscellaneous

### 9.1 Order of Precedence
If there is a conflict between this DPA and the Principal Agreement, this DPA prevails on matters of data protection. If there is a conflict between this DPA and the SCCs, the SCCs prevail.

### 9.2 Amendments
This DPA may be amended only by written agreement of the Parties, except that the Controller may unilaterally update this DPA where necessary to comply with changes in Applicable Data Protection Laws, provided that no such update materially diminishes the protection of Personal Data.

### 9.3 Severability
If any provision of this DPA is held invalid, the remainder shall continue in effect.

### 9.4 Notices
Notices under this DPA shall be given in writing to the addresses set out in the Principal Agreement, with a copy to **help@aidstation.pro**.

### 9.5 Governing Law
This DPA is governed by the law specified in the Principal Agreement, except where Applicable Data Protection Laws require otherwise.

---

## Annex 1: Description of Processing

| Item | Detail |
|---|---|
| **Subject matter** | [To be completed per Principal Agreement — e.g., "Provision of AI inference services," "Provision of email delivery services," "Academic research on endurance training outcomes"] |
| **Duration** | Coterminous with the Principal Agreement |
| **Nature of processing** | [Storage, transmission, computation, analytical processing, etc.] |
| **Purpose of processing** | [Specific business purpose served] |
| **Types of Personal Data** | [Select all that apply: account identifiers, contact details, training and activity data, biometric/health data (where opt-in by Data Subject), communications, technical and usage data, payment details, GPS/location data] |
| **Sensitive Personal Data** | [If applicable: heart rate, HRV, sleep, body composition, VO2 max, injury and condition information, precise location] |
| **Categories of Data Subjects** | AIDSTATION users (endurance and multi-sport athletes); AIDSTATION personnel where relevant |
| **Frequency of transfer** | [Continuous / batch / on request] |
| **Retention period** | [As per Principal Agreement and AIDSTATION Privacy Policy; in any event, no longer than necessary for the Processing] |
| **Locations of processing** | [Specify country/region of processing and storage] |
| **Controller-instructed training (Section 4.12(c))** | [If applicable: identify the Controller-owned models or training operations the Processor is instructed to support, the scope of training data permitted, and the location(s) where training will occur] |

---

## Annex 2: Technical and Organizational Measures

The Processor implements at minimum the following measures. Specific implementations are described in [the Processor's security documentation], which shall be made available to the Controller on request.

### Access Control
- Role-based access control with least-privilege principles
- Multi-factor authentication for personnel accessing Personal Data
- Unique user accounts; no shared credentials
- Quarterly access reviews
- Prompt revocation of access on personnel changes

### Encryption
- TLS 1.2 or higher for data in transit
- AES-256 or equivalent for data at rest
- Key management with appropriate rotation and protection

### Pseudonymization
- Where supported by the service, separation of identifying information from operational data

### System Integrity
- Vulnerability management with regular scanning and patching
- Hardened production configurations
- Code review processes for changes to production systems
- Separation of production and non-production environments
- Logging and monitoring with retention sufficient to support incident investigation

### Availability and Resilience
- Backup and disaster recovery procedures
- Documented restoration objectives (RTO/RPO)
- Periodic testing of restoration procedures

### Incident Response
- Documented incident response procedures
- 24/7 incident notification capability
- Coordination procedures with the Controller

### Personnel
- Background screening where permitted by law
- Confidentiality obligations in employment terms
- Annual security and privacy training
- Defined process for personnel termination

### Sub-processor Management
- Due diligence before engagement
- Contractual data protection obligations (including Section 4.12 pass-through)
- Ongoing monitoring

### Secondary Use Controls (per Section 4.12)
- Technical and procedural controls preventing use of Controller Personal Data for Processor-owned or third-party model training
- Segregation of Controller-instructed training operations from Processor's own ML/AI development activities
- Audit-ready logging of training data flows where Controller-instructed training operations are performed under Section 4.12(c)

### Physical Security (where applicable)
- Restricted access to facilities housing Processing systems
- Visitor logs and escort policies
- Environmental controls

---

## Annex 3: Authorized Sub-processors

The following Sub-processors are pre-authorized as of the Effective Date:

| Sub-processor | Service Provided | Location |
|---|---|---|
| [To be completed by Processor] | | |

New Sub-processors are added subject to the procedure in Section 4.4(c).

A current list of Sub-processors is available at [link or on request].

---

## Annex 4: Standard Contractual Clauses

Where the Parties rely on the SCCs as a transfer mechanism under Section 5.1, the SCCs are incorporated by reference and completed as follows:

| SCC Element | Completion |
|---|---|
| **Module** | [Module Two or Module Three, per Section 5.2] |
| **Clause 7 (Docking clause)** | [Included / Not included — operator default: not included] |
| **Clause 9 (Sub-processors)** | Option 2 (general written authorization). Notice period: 30 days, per DPA Section 4.4(c). |
| **Clause 11 (Redress)** | [Independent dispute resolution body — operator default: not selected] |
| **Clause 17 (Governing law)** | [Member State law providing for third-party beneficiary rights; default: Ireland] |
| **Clause 18 (Choice of forum and jurisdiction)** | [Member State of the EU — default: Ireland] |
| **Annex I.A (Parties)** | As set out in this DPA |
| **Annex I.B (Description of transfer)** | As set out in Annex 1 of this DPA |
| **Annex I.C (Competent supervisory authority)** | [Per the Controller's lead supervisory authority or, where none, the supervisory authority of the Member State in which the data exporter is established] |
| **Annex II (Technical and organizational measures)** | As set out in Annex 2 of this DPA |
| **Annex III (List of sub-processors)** | As set out in Annex 3 of this DPA |
| **UK Addendum** | Incorporated where transfers involve UK Personal Data. Table 4 ("Ending the Addendum"): Importer and Exporter may end the Addendum. |

---

## Change Log

| Version | Date | Changes | Author |
|---|---|---|---|
| v1 | (superseded) | Initial DPA template for AIDSTATION as Controller. | Privacy Lead |
| v2 | May 19, 2026 | Controller entity set to "AIDSTATION Pro, LLC, a Texas limited liability company"; §9.4 notices address updated from `privacy@aidstation.app` to `help@aidstation.pro`. No substantive obligation changes. | Privacy Lead |
| v3 | May 20, 2026 | Tier 2 lens pass (operator-favorable + lawful + single global rule). Substantive lens edits: §4.4(c) sub-processor notice expanded (security/posture summary required) and objection grounds broadened to any reasonable grounds; §4.5 DSR-assistance window tightened from 10 to 5 business days; §4.7 Security Incident notification restructured into 12-hour preliminary + 24-hour full notification (previously 48 hours, single-stage); §4.9 audit trigger broadened (Security Incident OR documented reasonable concern OR supervisory authority requirement), cost allocation added (Processor reimburses on material non-compliance), desk-audit substitution preserved with right-to-escalate-to-on-site language; §7 liability cap carve-outs added for confidentiality, Sensitive Personal Data, Section 4.12, intentional/grossly negligent breach, fraud, IP infringement; uncapped processor indemnity for the same matters; §8 material-breach cure period tightened from 30 to 14 days, with no cure period for Sensitive Personal Data confidentiality breach or Section 4.12 breach. Gap-fill: new **§4.12 No Secondary Use; No Training on Controller Data** with explicit carve-out at §4.12(c) for Controller-instructed training of Controller's own models on Processor infrastructure; survives termination per §4.12(g). Annex 2 updated with new "Secondary Use Controls" subsection. Annex 4 (SCCs) filled out with operator-favorable defaults for completion. New "Controller Personal Data" definition added to §1. Cross-refs added at §3, §4.4(d), §4.10, §7, §8. Important Notes updated to flag the four sections most likely to attract counterparty pushback. (Privacy Program Backlog: Tier 2 lens batch — DPA Template as first item per Track A G2 Closing Handoff §5.1.) | Privacy Lead |
| v4 | May 30, 2026 | Contact-address consolidation to the two approved addresses: `help@aidstation.pro` for user support (including privacy / data-rights requests) and `info@aidstation.pro` for formal, legal, security, and DMCA correspondence. No other changes. | Privacy Lead |
