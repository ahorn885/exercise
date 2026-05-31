# AIDSTATION Record of Processing Activities (RoPA)

**Status:** Internal compliance register — v7 (inactivity-outcome terminology aligned to de-identification/pseudonymization per the D-124 resolution; v6 was the cross-reference unversioning cleanup)
**Legal basis:** GDPR Article 30 (and analogous provisions of UK GDPR, POPIA, Quebec Law 25, Australia APPs, NZ Privacy Act)
**Owner:** [Privacy Lead]
**Last Updated:** May 30, 2026
**Review Cycle:** Quarterly, plus on material change to any processing activity

---

## Purpose of This Register

This document records the processing activities AIDSTATION carries out as a data controller. It is the central reference for what data we process, why, on what legal basis, where it goes, how long we keep it, and how we protect it.

The RoPA is **not user-facing**. It is maintained for:
- Demonstrating compliance to supervisory authorities on request
- Internal coordination on data protection obligations
- Foundation for DPIAs, breach response, data subject rights handling
- Onboarding new processing activities

Each material change to a processing activity must be reflected here within 30 days of the change taking effect.

---

## Controller Information

| Field | Value |
|---|---|
| Name of controller | AIDSTATION Pro, LLC (Texas limited liability company) |
| Address | 509 Williams Avenue, Cleburne, TX 76033, United States |
| Privacy contact | help@aidstation.pro |
| Data Protection Officer (DPO) | [TBD when appointed; required if processing health data at scale per GDPR Art. 37] |
| EU Representative (Art. 27) | [TBD when appointed] |
| UK Representative | [TBD when appointed] |
| POPIA Information Officer | [TBD when appointed] |

---

## Summary of Processing Activities

| ID | Activity | Sensitive Data? | Primary Legal Basis (EU/UK) | Notes |
|---|---|---|---|---|
| PA-01 | Account management | No | Contract | Core service |
| PA-02 | Activity and training data processing | No | Contract | Core service |
| PA-03 | Sensitive health data processing | **Yes** | Explicit Consent | Opt-in required |
| PA-04 | AI training plan generation (L0-L5 pipeline) | Includes sensitive where opted in | Contract + Explicit Consent | Automated processing |
| PA-05 | Conversational AI coach | Includes sensitive where shared in chat | Contract + Explicit Consent | LLM-mediated |
| PA-06 | Third-party integration data ingestion | Includes sensitive where applicable | Consent (integration authorization) | Garmin, Strava, etc. |
| PA-07 | Payment processing | No (financial, not "special category") | Contract | Via processor |
| PA-08 | Customer support | Potentially | Contract | As needed |
| PA-09 | Marketing communications | No | Consent | Separate opt-in |
| PA-10 | Product analytics | No (pseudonymized) | Consent | Cookie banner |
| PA-11 | Crowdsourced facility database | No | Consent | User contributions |
| PA-12 | Research data sharing | Pseudonymized, may include sensitive | Consent | Opt-out available |
| PA-13 | Security and fraud prevention | Potentially | Legitimate Interest | Required for operation |
| PA-14 | Legal compliance (tax, records) | As required | Legal Obligation | Limited |
| PA-15 | AI model training and development (AIDSTATION's own models) | Where opted in for sensitive | Legitimate Interest + Explicit Consent (sensitive) | New in v2; DPIA required |
| PA-16 | Copyright notice processing (DMCA + parallel non-U.S. claims) | No (not by design) | Legitimate Interest | New in v4; § 512 safe-harbor compliance |

---

## Detailed Processing Activities

### PA-01 — Account Management

**Purpose.** Create and maintain user accounts, authenticate users, manage account settings, enable users to use AIDSTATION.

**Categories of data subjects.** AIDSTATION users (athletes).

**Categories of personal data.**
- Name, email address
- Hashed password and authentication tokens
- Date of birth, biological sex (used for training calculations)
- Country, time zone
- Account creation metadata, last login timestamps
- Account preferences and settings

**Special categories.** None.

**Legal basis (EU/UK GDPR).** Performance of a contract (Art. 6(1)(b)).
**Other jurisdictions.** Necessary to provide the requested service.

**Categories of recipients.**
- AIDSTATION personnel with role-based access
- Service providers operating the platform (Vercel, Neon, SendGrid, WordPress.com — for marketing site interactions)

**International transfers.** Data stored in US. SCCs apply for EU/UK transfers.

**Retention.** Duration of account + 24 months inactivity, then de-identified (pseudonymized retention). Deletion on request within 30 days. Backups purged on 90-day rolling cycle.

**Security measures.** Per the TOMs document (`AIDSTATION_TOMs`). Encryption in transit and at rest, MFA available, password hashing, access logging.

**Source.** Directly from the user at sign-up and during account use.

---

### PA-02 — Activity and Training Data Processing

**Purpose.** Store, organize, and process the activity and training data athletes generate or sync to AIDSTATION; provide athletes with their training history and progress.

**Categories of data subjects.** AIDSTATION users.

**Categories of personal data.**
- Workouts logged or synced (pace, speed, cadence, distance, duration, elevation, power)
- Training volume and frequency
- Subjective ratings (perceived exertion, fatigue, soreness)
- Plan adherence
- Performance test results
- Goal and race information
- Equipment and training location information

**Special categories.** None at this layer (sensitive data handled separately in PA-03).

**Legal basis.** Performance of a contract.
**Other jurisdictions.** Necessary to provide the service.

**Categories of recipients.** AIDSTATION personnel with role-based access; service providers operating the platform.

**International transfers.** US storage. SCCs for EU/UK.

**Retention.** Account active duration + 24 months inactivity. Deletion on request.

**Security measures.** Per the TOMs document (`AIDSTATION_TOMs`).

**Source.** Directly from user input and from authorized third-party integrations.

---

### PA-03 — Sensitive Health Data Processing

**Purpose.** Where explicitly opted in by the user, collect and process sensitive health and biometric data to provide personalized training recommendations.

**Categories of data subjects.** AIDSTATION users who have opted in to specific sensitive categories.

**Categories of personal data (special category under GDPR Art. 9).**
- Heart rate and heart rate variability (HRV)
- Sleep duration and quality
- Weight, body composition, body fat percentage
- VO2 max and other derived health metrics
- Resting and exercise blood pressure (if user chooses to record)
- Injury history and rehabilitation status
- Medical conditions affecting training
- Precise physical address (sensitive under CPRA)
- GPS route data (sensitive under CPRA)

**Legal basis (EU/UK GDPR Art. 9(2)(a)).** Explicit consent of the data subject.
**Other jurisdictions.** Explicit, separate, opt-in consent for each category; revocable at any time.

**Categories of recipients.** AIDSTATION personnel with elevated access (limited; logged); service providers operating the platform; Anthropic for AI inference (no training on data); research partners under PA-12 if user has not opted out.

**International transfers.** US storage. SCCs for EU/UK.

**Retention.** Same as account data. Disabling a category stops new collection; existing data is retained until account deletion or de-identification unless the user requests earlier deletion.

**Security measures.** Per the TOMs document (`AIDSTATION_TOMs`). Elevated access controls on sensitive data; access logging; pseudonymization at rest where compatible with service requirements.

**Source.** Directly from user input, from authorized third-party integrations, or derived from other data (e.g., VO2 max estimated from heart rate and pace).

**Special note.** Privacy-by-default applies. Each sensitive category defaults to OFF. Users must affirmatively enable each.

---

### PA-04 — AI Training Plan Generation (L0-L5 Pipeline)

**Purpose.** Generate personalized training plans, recommendations, and rationale through the multi-layer LLM pipeline. Includes profile classification (L1-L2), athlete evaluation (L3), HITL gate (L3.5), plan generation and validation (L4), and supplemental outputs (L5).

**Categories of data subjects.** AIDSTATION users.

**Categories of personal data.** All categories from PA-01, PA-02, and PA-03 (where opted in) flow through the pipeline. Plan outputs are derived data.

**Special categories.** Where users have opted in to sensitive categories.

**Legal basis.** Performance of a contract (for plan generation as a core service feature) + Explicit Consent (for sensitive data inputs).

**Automated processing note.** Plan generation is automated processing under GDPR Art. 22. AIDSTATION's position is that coaching recommendations are advisory and do not produce legal or similarly significant effects on data subjects. Users may disable AI features.

**Categories of recipients.** Anthropic (AI inference provider, no training on data); AIDSTATION personnel for system maintenance and quality review; service providers operating the platform.

**International transfers.** US storage and inference. SCCs for EU/UK.

**Retention.** Plan outputs retained with account. Raw conversation transcripts not retained; parsed coaching notes are retained.

**Security measures.** Per the TOMs document (`AIDSTATION_TOMs`). System prompt restrictions per the AI System Prompt Restrictions spec; output validator before delivery to user.

**Source.** Inputs from PA-01, PA-02, PA-03, PA-06.

---

### PA-05 — Conversational AI Coach

**Purpose.** Provide conversational coaching interface where users can ask questions and discuss their training with the AI.

**Categories of data subjects.** AIDSTATION users who engage with the conversational coach.

**Categories of personal data.** User messages (potentially including any of the categories above, depending on what the user volunteers); AI responses; conversation metadata.

**Special categories.** Where users share sensitive information in chat. The AI is instructed to refuse pregnancy, menstrual, gender identity, and other categories per the AI System Prompt Restrictions spec.

**Legal basis.** Performance of a contract; Explicit Consent for any sensitive data shared in conversation.

**Categories of recipients.** Anthropic (inference); AIDSTATION personnel for quality review (limited access, logged).

**International transfers.** US. SCCs for EU/UK.

**Retention.** Raw conversation transcripts are not retained beyond the session. Parsed coaching notes and structured outputs are retained with the account.

**Security measures.** Three-layer defense from AI System Prompt Restrictions spec: input pre-filter, LLM system prompt, output validator. Refusal events logged by category, not content.

**Source.** Directly from user during conversational interaction.

---

### PA-06 — Third-Party Integration Data Ingestion

**Purpose.** Receive data from authorized third-party fitness platforms (Garmin, Strava, Wahoo, Whoop, Apple Health, Samsung Health) to populate the user's training and biometric records.

**Categories of data subjects.** AIDSTATION users who have authorized integrations.

**Categories of personal data.** Activity data, biometric data, recovery data, and other categories per the authorized integration scope.

**Special categories.** Where the integration provides health and biometric data and the user has opted in to those categories in AIDSTATION.

**Legal basis.** Consent (the user authorizes the integration, which constitutes both consent under GDPR and authorization to transfer data from the third party).

**Categories of recipients.** AIDSTATION operations; service providers operating the platform; downstream uses per PA-04 and PA-05.

**International transfers.** Data flows from third-party platforms (location depends on the platform) to AIDSTATION in US. SCCs for EU/UK in onward processing.

**Retention.** Same as PA-02 / PA-03.

**Security measures.** OAuth-based authorization; secure API connections; token storage with encryption.

**Source.** Third-party platforms with the user's explicit authorization.

---

### PA-07 — Payment Processing

**Purpose.** Process subscription payments for AIDSTATION services.

**Categories of data subjects.** Paying users.

**Categories of personal data.** Billing name, email, last four digits of card, billing country, subscription status. Full card details are not stored by AIDSTATION; they are processed by the payment processor.

**Legal basis.** Performance of a contract.

**Categories of recipients.** Payment processor [TBD]; AIDSTATION personnel with finance role access.

**International transfers.** Per payment processor location. SCCs for EU/UK.

**Retention.** Transaction records retained per applicable tax and accounting law (typically 7 years). Card last-four retained for chargeback and dispute handling per contract term.

**Security measures.** Payment processor handles full card data under PCI-DSS. AIDSTATION uses tokenized references only.

**Source.** Directly from user at subscription / payment update.

---

### PA-08 — Customer Support

**Purpose.** Respond to user support inquiries, troubleshoot issues, manage feedback.

**Categories of data subjects.** Users who contact support.

**Categories of personal data.** Support communications; account context; technical details shared by the user; any other personal data the user includes.

**Special categories.** Potentially, if the user shares health-related context.

**Legal basis.** Performance of a contract (resolving service issues).

**Categories of recipients.** AIDSTATION support personnel; customer support platform [TBD when implemented].

**International transfers.** US. SCCs for EU/UK.

**Retention.** Support tickets retained 24 months after resolution.

**Security measures.** Per the TOMs document (`AIDSTATION_TOMs`).

**Source.** Directly from user.

---

### PA-09 — Marketing Communications

**Purpose.** Send newsletters, product announcements, and promotional content to users who have opted in.

**Categories of data subjects.** Users who have provided marketing opt-in consent.

**Categories of personal data.** Email address, name, basic profile metadata (sport, goals) for personalization.

**Legal basis (EU/UK).** Consent.
**Other jurisdictions.** Express opt-in consent (per CASL, Australia Spam Act, etc.).

**Categories of recipients.** SendGrid for delivery; AIDSTATION marketing personnel.

**International transfers.** US. SCCs for EU/UK.

**Retention.** While opt-in remains active. Opt-out is processed immediately; unsubscribe records retained to honor the opt-out.

**Security measures.** Per the TOMs document (`AIDSTATION_TOMs`).

**Source.** User opt-in at signup or in settings.

---

### PA-10 — Product Analytics

**Purpose.** Measure usage patterns, feature adoption, performance, and errors to improve the service.

**Categories of data subjects.** Users (and visitors to the marketing site).

**Categories of personal data.** Pseudonymous usage events, technical metadata (browser, device, OS), interaction patterns.

**Special categories.** None.

**Legal basis.** Consent (set via cookie banner).

**Categories of recipients.** Analytics provider [TBD]; APM/error monitoring provider [TBD]; AIDSTATION engineering and product personnel.

**International transfers.** Per provider location. SCCs for EU/UK.

**Retention.** Per provider configuration, typically 13 months.

**Security measures.** Pseudonymization at source; no advertising identifiers; GPC honored.

**Source.** User interaction with the service.

---

### PA-11 — Crowdsourced Facility Database

**Purpose.** Maintain a database of public and commercial gyms, training facilities, and exercise areas, populated by user contributions, available to AIDSTATION users for plan personalization.

**Categories of data subjects.** Users who contribute facility data; users who view facility data.

**Categories of personal data.** Identity of contributing user is associated internally but not exposed to other users (contributions are presented anonymously). Facility data itself (location, equipment, amenities) is not personal data about the contributing user.

**Legal basis.** Consent (the user voluntarily contributes); contractual license for the contributed content (governed by T&Cs).

**Categories of recipients.** AIDSTATION users (viewing facility data); AIDSTATION personnel.

**International transfers.** US. SCCs for EU/UK.

**Retention.** Facility data retained indefinitely (separated from contributor identity). Contributor identity linkage removed on account deletion; facility data itself persists.

**Security measures.** Per the TOMs document (`AIDSTATION_TOMs`).

**Source.** User contributions.

---

### PA-12 — Research Data Sharing

**Purpose.** Share pseudonymized data with academic research partners for sport science research, under DPAs with appropriate safeguards.

**Categories of data subjects.** Users who have not opted out of research participation.

**Categories of personal data.** Pseudonymized training, activity, and (where users have opted in) sensitive data.

**Legal basis.** Consent (default opt-in disclosed in Privacy Policy with prominent opt-out).
**Other jurisdictions.** Same. Opt-out is accessible in account settings.

**Categories of recipients.** Approved academic research partners under DPA and Research Data Use Agreement; IRB or equivalent ethics approval required.

**International transfers.** Per research partner location. SCCs where transferring to third countries.

**Retention.** Research partners retain data for the duration of the study with destruction at study end. Opt-out prevents new sharing but does not retract data already shared with an active study (disclosed in Privacy Policy).

**Security measures.** Pseudonymization before sharing; lookup table held by AIDSTATION only; contractual no-re-identification obligation on researchers; minimum data shared for each study.

**Source.** Derived from existing AIDSTATION data; pseudonymized for sharing.

---

### PA-13 — Security and Fraud Prevention

**Purpose.** Maintain the security of AIDSTATION systems, detect and respond to fraudulent activity, investigate security incidents.

**Categories of data subjects.** All users; security event-related individuals.

**Categories of personal data.** Authentication logs, IP addresses, device information, access patterns, security event details.

**Legal basis (EU/UK).** Legitimate interest (Art. 6(1)(f)) — securing the service and preventing fraud is necessary for the service to operate and benefits all users.
**Other jurisdictions.** Necessary for the legitimate operation of the service.

**Categories of recipients.** AIDSTATION engineering and security personnel; APM/security tooling [TBD]; law enforcement only where legally required.

**International transfers.** US. SCCs for EU/UK.

**Retention.** Security logs retained 12 months unless extended for active investigation.

**Security measures.** Access controls; logging integrity; alerting.

**Source.** Derived from system activity and user interactions.

---

### PA-14 — Legal Compliance and Record-Keeping

**Purpose.** Maintain records required by law (financial, tax, regulatory) and respond to legal obligations.

**Categories of data subjects.** As required by the applicable obligation.

**Categories of personal data.** As required.

**Legal basis (EU/UK).** Legal Obligation (Art. 6(1)(c)).

**Categories of recipients.** Tax authorities, regulators, courts, as legally required.

**International transfers.** As required by law.

**Retention.** As required by applicable law (typically 7 years for financial records).

**Security measures.** Per the TOMs document (`AIDSTATION_TOMs`).

**Source.** Derived from other processing activities as required.

---

### PA-15 — AI Model Training and Development

**Purpose.** Develop and improve AIDSTATION's own AI coaching models — including prompt tuning, retrieval-augmented generation indexes, fine-tuned model variants where applicable, and evaluation datasets. Distinct from PA-04 (which is runtime inference using already-trained models) and PA-05 (which is the conversational interface). This activity is the upstream training and evaluation work that produces the models PA-04 and PA-05 use.

**Categories of data subjects.** AIDSTATION users.

**Categories of personal data.**
- Training plans and modifications generated for users
- Parsed coaching notes derived from conversational AI interactions (raw transcripts are not retained per PA-05 and are not used for training)
- Activity, performance, and progression data
- User feedback signals on plans and recommendations (thumbs up/down, edits, follow-through)
- Profile context relevant to plan quality (goals, sport, experience level)

**Special categories.** Where users have opted in to sensitive categories, sensitive data is used in training only after de-identification or aggregation. Raw sensitive data is not used in training without explicit, additional consent obtained separately from the collection opt-in.

**Legal basis (EU/UK GDPR).**
- Non-sensitive content: Legitimate interest (Art. 6(1)(f)). Improving the coaching product is a reasonable expectation of users engaging with an AI coaching service, balanced by opt-out availability, de-identification/aggregation safeguards for sensitive categories, and the disclosure in Privacy Policy §4. Default state for new users: opt-in, with unconditional right to object via account settings (per LIA §8.1 and PP §9). Legitimate Interests Assessment documented separately in `AIDSTATION_LIA_PA15`.
- Special category data (where included): Explicit consent (Art. 9(2)(a)), obtained separately from the collection opt-in.

**Other jurisdictions.** Disclosed in Privacy Policy §4 with opt-out for general training data and explicit, separate opt-in for sensitive categories.

**Automated processing note.** Model training is preparatory to the automated processing in PA-04. It does not itself produce decisions about individuals. The trained model is then used in PA-04 and PA-05.

**Categories of recipients.** AIDSTATION ML and engineering personnel with role-based access to training datasets (limited; logged); ML training infrastructure provider [TBD when selected] under DPA with no-training-on-our-data and no-derivative-use restrictions.

**International transfers.** US storage and training. SCCs for EU/UK transfers to training infrastructure.

**Retention.** Training datasets retained for the lifetime of the model generation that uses them, plus a reasonable reproducibility window (typically 24 months after the model generation is retired). User content can be removed from future training runs on request, but model weights from already-completed training runs are not retrained on each removal — model unlearning is not technically feasible at v1. This limitation is disclosed in Privacy Policy §7 ("AI Models and Derivatives"). Aggregated and de-identified training signals (loss curves, eval metrics) may be retained indefinitely as research artifacts.

**Security measures.** Per the TOMs document (`AIDSTATION_TOMs`). De-identification or pseudonymization before training where compatible with the training objective. Elevated access controls and access logging on training datasets. Periodic adversarial memorization tests on output to detect identifiable data regurgitation, per the commitment in Privacy Policy §7. Training data lineage documentation maintained to support algorithmic disgorgement orders if ever issued.

**Source.** Derived from PA-01 (profile context), PA-02 (training data), PA-03 (sensitive data, opt-in only, with additional consent for training use), PA-04 (plan outputs and user follow-through signals), PA-05 (parsed coaching notes only).

**Special note.** This processing activity is the subject of a required DPIA (see DPIA Template Appendix A). DPIA must be completed before scaled training begins.

---

### PA-16 — Copyright Notice Processing

**Purpose.** Process notices and counter-notifications of alleged copyright infringement to maintain eligibility for the safe harbor under 17 U.S.C. § 512(c), to defend against potential copyright litigation, and to handle parallel non-U.S. copyright claims under applicable law. Includes intake, triage, location and classification of allegedly-infringing material, takedown/restore action, complainant correspondence, repeat-infringer tracking, and recordkeeping. Distinct from PA-08 (general support), PA-09 (general DSR fulfillment), and PA-14 (general legal compliance recordkeeping).

**Categories of data subjects.**
- Complaining parties (rights holders or persons authorized to act on their behalf)
- Users whose content is alleged to infringe (alleged infringers; AIDSTATION account holders)
- Counter-notifiers (users submitting counter-notifications under § 512(g)(3))

**Categories of personal data.**
- Complaining party identification, signature, and contact information per § 512(c)(3)(A)(i), (iv)
- Identification of the copyrighted work claimed to be infringed per § 512(c)(3)(A)(ii)
- Identification of the allegedly-infringing material per § 512(c)(3)(A)(iii)
- Statements made under § 512(c)(3)(A)(v) and (vi), including statements under penalty of perjury
- Alleged-infringer account identification (derived from the affected content's attribution within AIDSTATION's systems)
- Counter-notice content per § 512(g)(3): signature, identification of removed material, statement under penalty of perjury, contact information, consent to jurisdiction
- Correspondence between AIDSTATION and any party to a notice or counter-notice
- AIDSTATION's records of action taken (tracking ID per `AIDSTATION_DMCA_Designated_Agent_Spec` §4.1, triage outcome, action taken, dates)

**Special categories.** Not collected by design. If a notice or counter-notice incidentally contains special-category personal data (e.g., health information mentioned in a complainant's correspondence), it is handled per the data-minimization commitment in the TOMs and is not retained beyond what is necessary for safe-harbor compliance or litigation defense.

**Legal basis (EU/UK GDPR).** Art. 6(1)(f) Legitimate Interest. AIDSTATION's interest is in maintaining eligibility for the § 512(c) safe harbor (a substantial operational interest) and in defending against potential copyright litigation. Rights and freedoms of data subjects are not unduly impacted: complainants and counter-notifiers are voluntary participants in a legal dispute they initiated; alleged infringers' identifying information is disclosed only as § 512(g)(2)(B) requires (i.e., to the counter-notifier in the event of a counter-notification). Counsel may also consider Art. 6(1)(c) Legal Obligation in jurisdictions that have transposed a parallel notice-and-action obligation into national law (e.g., EU Digital Services Act Art. 16 host-service obligations, EU Copyright Directive Art. 17). Art. 6(1)(c) is currently flagged for counsel review and is not yet asserted as a basis here.

**Other jurisdictions.** § 512 is U.S.-specific. Non-U.S. copyright claims are processed under the applicable national law and AIDSTATION's internal procedures; the Designated Agent address serves as a single global intake point. EU DSA Art. 16 notice-and-action obligations are out of scope until EU launch and are tracked separately in the privacy program.

**Automated processing note.** No automated individual decision-making in the Art. 22 sense. Triage and takedown decisions are made by the Designated Agent or designee. Repeat-infringer termination decisions are made under §6 of `AIDSTATION_DMCA_Designated_Agent_Spec`, with discretion preserved at AIDSTATION based on factors AIDSTATION considers relevant.

**Categories of recipients.**
- Counter-notifier (receives a copy of the original notice per § 512(g)(2)(B))
- Complainant (receives a copy of any counter-notification per § 512(g)(2)(B))
- Designated Agent and backup; Privacy Lead; outside counsel where engaged
- U.S. Copyright Office (agent registration only — not transmission of notice contents)
- Courts and litigants in any copyright proceeding involving AIDSTATION

**International transfers.** Notices and counter-notifications may originate from any jurisdiction. Stored in U.S. infrastructure. SCCs applied to any EU/UK-originated personal data transferred to U.S. infrastructure.

**Retention.** Notices, counter-notices, and AIDSTATION's records of action are retained for **7 years from final action on the matter**, parallel to PA-14 (Legal Compliance and Record-Keeping). Retention duration reflects the longest of (a) the U.S. federal copyright statute of limitations (3 years from accrual under 17 U.S.C. § 507(b)), (b) safe-harbor compliance documentation needs, and (c) operational repeat-infringer tracking. Records may be retained longer where an active dispute, litigation, or regulatory inquiry requires it.

**Security measures.** Per the TOMs document (`AIDSTATION_TOMs`). Restricted access to `info@aidstation.pro` intake and case-tracking records. Access logged. Disclosure of alleged-infringer information to a complainant is limited to what § 512(g)(2)(B) requires (i.e., transmission of the counter-notification). Discretionary acknowledgments to complaining parties (per § 4.1 of the DMCA Spec) do not include alleged-infringer information.

**Source.** Notices intake at `info@aidstation.pro` or postal address per `AIDSTATION_DMCA_Designated_Agent_Spec` §2.4. Counter-notifications intake at the same channel. Internal correlation with affected user accounts derived from AIDSTATION's content-attribution systems.

**Special note.** This processing activity is documented in `AIDSTATION_DMCA_Designated_Agent_Spec`. Repeat-infringer policy is in §6 of that spec. Operational standup of agent registration, mailbox, postal, and phone is tracked at Privacy Program Backlog D-99 through D-102.

---

## Joint Controllership and Third-Party Controllers

AIDSTATION has no joint controllership arrangements at present. Where users authorize third-party integrations (Garmin, Strava, Whoop, etc.), those services act as independent controllers under their own privacy policies; AIDSTATION is not a joint controller with them.

If joint controllership arrangements are established in the future (e.g., team-based training with team organizations as joint controllers), they will be documented here.

---

## Technical and Organizational Measures Reference

The technical and organizational security measures applied across processing activities are documented in the standalone Technical and Organizational Measures document (`AIDSTATION_TOMs`). The same measures are referenced in the DPA template (Annex 2) for partner agreements.

---

## Maintenance and Review

This RoPA is reviewed:

- **Quarterly** by the Privacy Lead, with confirmation of accuracy
- **On material change** to any processing activity (new data category, new recipient, new transfer mechanism, change in retention, new legal basis)
- **Annually** in full, in conjunction with the broader privacy program review

Changes are recorded in the change log below with date, summary, and author.

---

## Change Log

| Version | Date | Changes | Author |
|---|---|---|---|
| v1 | (superseded) | Initial register based on launch architecture | [Privacy Lead] |
| v2 | May 19, 2026 | Controller entity set to AIDSTATION Pro, LLC; postal address and privacy contact updated; PA-15 (AI Model Training and Development) added as a distinct processing activity to reflect Privacy Policy v2 §4 and T&C v2 §8.2 | [Privacy Lead] |
| v3 | May 19, 2026 | Track A consistency-pass alignment with LIA v2. PA-15 Legal Basis paragraph updated: explicit default-opt-in-for-new-users statement per LIA v2 §8.1; specific reference to `AIDSTATION_LIA_PA15_v2.md` replacing generic "documented separately" wording; cross-reference to PP v3 §4 / §9 (D-113). No data inventory changes, no recipient changes, no retention changes. | [Privacy Lead] |
| v4 | May 19, 2026 | Track A Group 2 — PA-16 (Copyright Notice Processing) added as a new processing activity covering DMCA notice handling and parallel non-U.S. copyright claims. Legal basis: Art. 6(1)(f) Legitimate Interest (safe-harbor compliance and litigation defense); Art. 6(1)(c) flagged for counsel review re: DSA Art. 16 transposition jurisdictions. Retention: 7 years from final action, parallel to PA-14. Summary table row added. Cross-references to `AIDSTATION_DMCA_Designated_Agent_Spec_v2.md`. (D-105) | [Privacy Lead] |
| v5 | May 30, 2026 | Cleanup pass. D-77 resolved: the "Technical and Organizational Measures Reference" section and all per-activity "Security measures" rows now point to the standalone `AIDSTATION_TOMs_v2.md` (the stale "[TOMs Annex — to be created]" placeholder and "Per TOMs Annex" phrasing predated the standalone TOMs doc). Stale "Privacy Policy v2 §" cross-references in PA-15 updated to v4 (body only; historical changelog rows left as-is). No data-inventory, recipient, legal-basis, or retention changes. | [Privacy Lead] |
| v7 | May 30, 2026 | Inactivity-outcome terminology aligned to the D-124 resolution: the 24-month inactivity outcome is described as **de-identification (pseudonymized retention)** rather than "anonymized" (PA-04 retention, and the sensitive-category retention note), matching the Privacy Policy and Inactivity Spec. No inventory, recipient, legal-basis, or retention-duration changes. | Privacy Lead |
| v7 | May 30, 2026 | Contact-address consolidation to the two approved addresses: `help@aidstation.pro` for user support (including privacy / data-rights requests) and `info@aidstation.pro` for formal, legal, security, and DMCA correspondence. No other changes. | Privacy Lead |

---

*Cross-reference cleanup (v6, 2026-05-30): inline references to companion documents were converted to unversioned logical names per Rule #12, so they no longer go stale when a companion document is revised. No substantive content changes. See `Privacy_Program_Consistency_Sweep_Report_v1.md`.*

