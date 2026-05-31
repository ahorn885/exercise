# AIDSTATION Technical and Organizational Measures (TOMs)

**Status:** v3 — cross-reference unversioning cleanup (no substantive change since the v2 Tier 2 lens pass)
**Owner:** Privacy Lead (operational responsibility shared with Engineering Lead)
**Last Updated:** May 30, 2026
**Companion docs:** `AIDSTATION_DPA_Template` (Annex 2 references this document), `AIDSTATION_RoPA` ("Technical and Organizational Measures Reference" section), `AIDSTATION_LIA_PA15` §4.6 safeguards #5/#7, `AIDSTATION_DPIA_PA15` R-08/R-11/R-14 mitigations, `AIDSTATION_Breach_Response_Playbook`, `AIDSTATION_Privacy_Policy` §8
**Closes:** D-77 (TOMs Annex — accept DPA Annex 2 as canonical or extract to standalone; resolved by extracting to standalone)
**Backlog refs:** `Privacy_Program_Backlog_v5.md`

---

## Lens Calibration Notes (v3)

This section names the positions most likely to attract counsel pushback under the operator-favorable + lawful + single-global-rule lens. Counsel should be directed here on review.

**The lens runs in reverse for a TOMs document.** For most privacy-program documents, operator-favorable means asserting the strongest position. A TOMs document is the opposite: it is representable to counterparties through DPA Annex 2, so every measure stated as **Current State** is a representation that creates liability if a breach later reveals the claim was aspirational. The operator-favorable position is therefore to commit to **exactly what is true and the Art. 32 "appropriate measures" floor — no more — with maximal reservation of rights**, not to claim the strongest controls. v1 already understood this (the Current/Committed/Target framing and §15 reservation are the structural expression of it). v2's lens edits push the principle slightly further.

1. **§6 informal RTO de-committed.** v1 stated an "informal" 4-hour restoration target. §17.1 of v1 itself flagged that an informal number read by a counterparty becomes a de-facto commitment. The lens-correct move is to remove the representable number: v2 states that AIDSTATION holds no formal RTO/RPO commitment at this stage and does not publish an internal target in this document. Removing the number removes the liability without changing the underlying capability.

2. **§7.2 logging retention reframed to the minimum appropriate, tied to forensic and Art. 33(5) need.** Data minimization is both lawful and operator-favorable here — shorter retention of high-volume operational logs reduces both breach surface and storage-limitation exposure, while security-relevant logs are retained for their forensic and accountability value (the Breach Playbook §12.1 Art. 33(5) record-keeping obligation). The single global rule: one defensible retention posture, not per-counterparty tuning.

3. **§9 vendor controls tied to DPA §4.12.** The no-training / no-secondary-use restriction is now anchored to the specific clause (`AIDSTATION_DPA_Template` §4.12) rather than a general phrase, and vendor due diligence explicitly includes confirming a prospective ML-infrastructure vendor's own terms preserve AIDSTATION's §4.12(c) controller-instructed-training carve-out. This closes the gap the DPA close flagged: the carve-out is worthless if a vendor template overrides it.

4. **§8 incident-response cross-refs point to the playbook, not to restated numbers.** v2 fixes the v1 bracketed placeholders with real Breach Playbook section numbers, but deliberately does **not** restate the playbook's specific internal timing targets in this document. Restating numbers here would create an independent commitment that could drift from the playbook. The TOMs commits to *having* a response capability and *governing* it by the playbook; the numeric commitments live in one place.

---

---

## 0. Scope and Status

This document is the canonical record of AIDSTATION's technical and organizational measures protecting personal data. It serves as:

- The reference document for **DPA Annex 2** (technical and organizational security measures) in agreements with processors and partners
- The **TOMs Reference** in RoPA's "Technical and Organizational Measures Reference" section
- The substrate for **LIA §4.6 safeguards #5 / #7** (AI training context) and **DPIA risk mitigations** (R-08 insider misuse, R-11 processor breach, R-14 training data breach, and others)
- The starting point for **breach scope analysis** under the Breach Response Playbook

**Posture.** This document distinguishes **Current State** (measures in place today) from **Committed State** (measures binding under this document but not yet operational) and **Target State** (aspirational measures not yet committed). Distinguishing the three honestly is more useful than a single composite picture, both for internal sequencing and for external counterparties evaluating AIDSTATION's posture.

**Calibration to scale.** AIDSTATION is a pre-launch SaaS operating on a small team. The TOMs are calibrated to what is reasonably implementable at this scale; they are not modeled on enterprise SOC 2 / ISO 27001 control sets, which would substantially exceed what is achievable or auditable today. As scale and resource grow, this document evolves; the categories below are stable, the specifics within them tighten.

**What this document is not.** Not a security policy document for personnel (separate operational deliverable). Not a vendor questionnaire response template (those reference this document but are not it). Not a guarantee of any specific outcome — the standard under GDPR Art. 32 is "appropriate" technical and organizational measures, taking into account state of the art, costs, and risk; this document operationalizes that standard for AIDSTATION's context.

**Status of this document.** Draft for counsel review. Specific commitments below (cadences, retention windows, vendor-specific details) are author judgments for counsel and Engineering Lead to confirm or revise.

---

## 1. Inherited Decisions

| Item | Decision | Source |
|---|---|---|
| Standalone document, not DPA Annex 2 embedded | Resolved D-77 in favor of standalone for multi-spec referencing | Privacy Program Backlog v1 |
| Hosting region for production data | US-based (Neon hosting); SCCs for EU/UK transfers | RoPA PA-04 / PA-15 |
| Raw conversational transcripts not retained | Privacy Policy §7; AI System Prompt Restrictions framing | PP |
| AI provider (Anthropic) operates under commercial terms with no-training-on-our-data | RoPA PA-04 | RoPA |
| 16+ minimum user age | T&C §2, PP §11 | T&C / PP |

---

## 2. Encryption

### 2.1 In transit

| Surface | Current State |
|---|---|
| User → AIDSTATION web application | HTTPS / TLS 1.2+ enforced; HSTS where supported by deployment platform |
| AIDSTATION → Anthropic API | TLS as provided by Anthropic API client; AIDSTATION enforces no plaintext fallback |
| AIDSTATION → Neon PostgreSQL | TLS-required connection strings; non-TLS connections rejected at the database level |
| AIDSTATION ↔ third-party integrations (Garmin, Strava, etc., when implemented) | TLS-required; OAuth flows over HTTPS |

### 2.2 At rest

| Surface | Current State |
|---|---|
| Production database (Neon) | Encryption at rest provided by Neon's infrastructure (AES-256, AWS-backed); AIDSTATION does not manage the keys |
| Application file storage (when implemented) | Cloud provider default encryption at rest; specific provider TBD per the deployment platform |
| Backups | Encryption at rest per the backup provider's default; specific configuration documented per provider |
| Training data store (when stood up — DPIA §7.3 gate) | Encryption at rest with elevated access controls relative to the production database; specific design tracked in `Privacy_Program_Backlog_v1.md` |

**Committed.** Application-level encryption of specifically sensitive fields (e.g., sensitive opt-in data under PA-03) is committed when the sensitive-category collection flow goes live, in addition to provider-level encryption at rest.

**Not committed.** AIDSTATION does not currently operate a customer-managed-key (CMK) model. CMK is a Target State item that may become relevant for enterprise B2B if that channel develops; not currently on the roadmap.

---

## 3. Access Controls

### 3.1 Personnel access

| Control | Current State |
|---|---|
| Role-based access | Engineering personnel have access scoped to systems required for their role; non-engineering personnel do not have production database or API key access |
| Least privilege | Default deny; access granted on request with named justification; revoked at end of role need |
| Multi-factor authentication | Required for administrative access to deployment platform, code repository, database management console, and AI provider account |
| Shared credentials | Not permitted for production systems; each named person has individually-attributed credentials |
| Privileged role review | Privileged accounts and their permissions reviewed at least every 6 months; ad hoc on role change or departure |
| Departure procedure | Access revocation on the day of departure; documented checklist |

### 3.2 Training data access (specific to PA-15)

| Control | Current State / Committed |
|---|---|
| ML personnel access to training data store | Committed — DPIA R-08 mitigation; role-based, logged, periodic review |
| Production-to-training data flow | Mediated by the ETL pipeline only; no direct human access path that bypasses the pipeline |
| Training data store administrative access | Limited to a smaller named subset than general engineering production access |

### 3.3 User authentication

| Control | Current State |
|---|---|
| Password requirements | Minimum length and complexity per deployment platform defaults; not less than 12 characters; common-password blocklist on signup |
| Account lockout | Rate-limited login attempts; lockout after repeated failures |
| MFA for users | Not required at v1; recommended option available where the auth provider supports it |
| Session management | Sessions expire after defined inactivity period; explicit logout invalidates session immediately |
| Password reset | Email-based with time-limited single-use tokens |

**Committed.** Mandatory MFA option available for users by general availability launch; user-initiated, not enforced for all users at v1.

---

## 4. Network and Infrastructure

| Control | Current State |
|---|---|
| Network segmentation | Production / development / test environments separated; cross-environment data flow restricted |
| Firewall / perimeter | Provided by deployment platform (Vercel) and database host (Neon); inbound access restricted to documented surfaces |
| API rate limiting | Implemented at the application layer for authenticated endpoints |
| DDoS protection | Provided by deployment platform's CDN / edge layer |
| Bot mitigation | Provided by deployment platform; supplemented at application layer where needed (signup flow) |

---

## 5. Vulnerability and Patch Management

| Control | Current State / Committed |
|---|---|
| Dependency scanning | Automated scans on dependency changes via repository tooling; high-severity findings remediated promptly |
| Operating system / platform patching | Delegated to managed-service providers (Vercel, Neon); AIDSTATION verifies provider patching cadence as part of due diligence |
| Application patching | Continuous deployment; security fixes shipped on detection, not on a fixed schedule |
| Penetration testing | Committed — engaged before public general-availability launch; cadence thereafter at AIDSTATION's discretion based on risk and resources |
| Bug bounty / vulnerability disclosure | Not committed at v1; an informal disclosure path via `info@aidstation.pro` is available |

---

## 6. Backups, Resilience, and Continuity

| Control | Current State |
|---|---|
| Database backups | Provided by Neon (continuous backup with point-in-time recovery within the platform's retention window) |
| Application code | Version-controlled with off-platform mirror |
| Configuration / secrets | Managed via deployment platform's secrets management; access controls per §3.1 |
| Restoration testing | Backup restoration validated by Engineering Lead; cadence at AIDSTATION's discretion, no less than annually |
| Failover / high availability | Provided by managed-service providers' regional posture; AIDSTATION does not currently operate active-active across regions |
| Recovery objectives | No formal RTO / RPO commitment at this stage. AIDSTATION does not publish an internal restoration-time target in this document; recovery is best-effort using the managed-service providers' point-in-time recovery and the off-platform code mirror. |

**Not committed.** Formal RTO / RPO targets backed by tested runbooks. This is a Target State item that scales with paying-customer obligations. (v2 lens change: the v1 "informal 4-hour" target was removed — an informal number in a counterparty-representable document becomes a de-facto commitment, as v1 §17.1 itself flagged. Removing the number removes the liability without changing the underlying capability.)

---

## 7. Logging and Monitoring

### 7.1 What is logged

| Surface | Current State |
|---|---|
| Application access | Authenticated requests logged with user identifier, timestamp, action |
| Administrative actions | Privileged actions on production systems logged |
| Database access | Provider-level logging (Neon) at the connection and query level; AIDSTATION-side logging at the application layer |
| Failed authentication | Logged with rate-limit and lockout trigger |
| Data export and deletion | Logged per Deletion Flow Spec |
| AI training data ingest | Will be logged at the dataset version level per DPIA R-05; pending implementation |

### 7.2 Retention

Logs are retained for the **minimum period appropriate to their forensic and accountability value**, consistent with GDPR data minimization and storage limitation:

- High-volume operational logs (application access, request traces): retained for a short window — typically 30–90 days — then purged. Shorter retention reduces both breach surface and storage-limitation exposure; these logs have little forensic value past the operational window.
- Security-relevant logs (administrative actions, failed-authentication and lockout events, data export/deletion events): retained for approximately 1 year, calibrated to forensic-investigation need and to the breach-record obligation under `AIDSTATION_Breach_Response_Playbook` §12.1 (GDPR Art. 33(5) documentation). Where a specific incident is under investigation or legal hold, the relevant logs are preserved beyond the default window for the duration of the matter.

Specific retentions per category are set by Engineering Lead within this posture and reviewed in the §13 annual review. This is a single global retention posture, not per-counterparty tuning (v2 lens change — see Lens Calibration Note 2).

### 7.3 Alerting and review

| Control | Current State / Committed |
|---|---|
| Real-time alerting | Limited to critical failures (service availability, authentication anomalies above threshold) |
| Periodic log review | Engineering Lead reviews security-relevant logs on a cadence appropriate to risk; not formalized at v1 |
| Anomaly detection | Provider-level baseline detection where available; no AIDSTATION-side ML anomaly detection at v1 |

---

## 8. Incident Response

Incident response is governed by `AIDSTATION_Breach_Response_Playbook`. This TOMs document specifies the foundational controls; the Playbook specifies the response process.

| Control | Reference |
|---|---|
| Incident detection | §7 above (logging/monitoring) plus Breach Playbook §4 (Detection) |
| Triage and containment | Breach Playbook §5.2 |
| Severity classification | Breach Playbook §5.3 |
| Assessment | Breach Playbook §6 (matrix §6.1; notification-decision waypoint §6.2) |
| Notification to regulators / affected persons | Breach Playbook §7 (regulators §7.1; affected persons §7.2) |
| Investigation and root-cause analysis | Breach Playbook §10 |
| Remediation | Breach Playbook §11 |
| Post-incident review | Breach Playbook §13 |
| Breach record-keeping (Art. 33(5)) | Breach Playbook §12.1 |
| Training data store incidents | Breach Playbook + DPIA R-14 specific mitigations |

**v2 lens note.** This document commits to *having* an incident-response capability and to governing it by the Breach Response Playbook; it deliberately does not restate the playbook's specific timing targets (the v1 "72-hour GDPR window" line was removed here). Numeric notification commitments live in the playbook alone, so the two cannot drift apart — restating them in a counterparty-representable document would create an independent, separately-bindable commitment (see Lens Calibration Note 4).

---

## 9. Vendor and Processor Management

| Control | Current State |
|---|---|
| DPA required | All processors handling personal data must execute a DPA before processing begins; template per `AIDSTATION_DPA_Template` |
| Due diligence | Vendor security posture assessed before engagement; assessment depth scaled to data exposure and processing volume. For a prospective ML-infrastructure vendor (PA-15), due diligence specifically confirms that the vendor's own terms do not override AIDSTATION's controller-instructed-training carve-out at `AIDSTATION_DPA_Template` §4.12(c) — the carve-out is worthless if a vendor template overrides it. |
| No-secondary-use / no-training restriction | Processors handling AIDSTATION user data are bound by the No Secondary Use; No Training on Controller Data terms at `AIDSTATION_DPA_Template` §4.12 (and its survival clause §4.12(g)), not merely a general phrase. Where a processor requires its own DPA (Anthropic, Vercel, Neon), due diligence reviews that DPA for material conflict with the §4.12 principle. |
| Audit rights | DPA template includes audit rights; exercise of audit rights is at AIDSTATION's discretion based on risk |
| Sub-processor approval | Processors must obtain AIDSTATION's prior approval before engaging sub-processors |
| Vendor list maintenance | Active processors are listed in the public Partners Page (`AIDSTATION_Partners_Page`); the list is reviewed when processors change |
| Termination / data return | DPA template specifies data return and deletion at end of processing relationship |

### 9.1 Current production processors

| Processor | Role | DPA status |
|---|---|---|
| Anthropic (Claude API) | AI inference for PA-04 and PA-05 | Commercial terms include no-training-on-our-data; AIDSTATION-side DPA pending Anthropic's standard terms |
| Neon | Database hosting | DPA pending standard terms; SOC 2 attestation referenced in Neon documentation |
| Vercel | Application hosting / deployment | DPA pending standard terms |
| Email service provider | Transactional and support email | TBD per provider selection |
| ML training infrastructure provider | PA-15 training data storage and compute | Selection pending (DPIA D-95 gate) |

---

## 10. Personnel

| Control | Current State / Committed |
|---|---|
| Confidentiality agreement | Required for all personnel with access to user data; signed before access is granted |
| Background checks | Not formally required at v1; Target State item if personnel scale meaningfully |
| Security awareness training | Informal at v1; formal annual training is a Committed item for general-availability launch |
| Role separation | Where staffing permits, sensitive operations require role separation (e.g., security-relevant changes reviewed by a second engineer); at current size, role separation is a goal, not always practical |
| Departure | Access revocation per §3.1; return of devices and credentials; confidentiality obligations survive departure |

---

## 11. Data Lifecycle Controls

These overlap with — and are governed primarily by — `AIDSTATION_Deletion_Flow_Spec` and `AIDSTATION_Inactivity_Automation_Spec`. Summarized here for completeness.

| Control | Reference |
|---|---|
| Collection minimization | RoPA-driven; only data with a stated purpose is collected |
| Retention enforcement | Automated where feasible; manual triggers documented |
| Deletion on request | Deletion Flow Spec |
| Inactivity-driven cleanup | Inactivity Automation Spec |
| Raw transcript non-retention | PP §7; AI Safety Logging Decision v1 §4.2 reinforces |
| Training data lineage | DPIA R-05 mitigation (committed; pending engineering build) |
| AI Models and Derivatives | PP §7 — trained models continue post-deletion; disclosed |

---

## 12. Pseudonymization, De-Identification, and Aggregation

These measures support multiple GDPR Art. 32 obligations and are referenced specifically by LIA #3 and DPIA R-02.

| Measure | Application |
|---|---|
| Pseudonymization | Applied where it preserves utility — e.g., training data assembled with user pseudonyms rather than account-keyed identifiers where the user-key is not required |
| De-identification (for training) | Special-category data (where opted in) is de-identified or aggregated before inclusion in training datasets; methodology selection is a Committed item per DPIA D-90 |
| Aggregation suppression | Per `AIDSTATION_Aggregation_Suppression_Spec` — small-cell suppression for any output derived from aggregated user data |
| Re-identification testing | Committed periodically once training datasets are live; methodology folded into DPIA D-91 memorization probing protocol |

---

## 13. Testing and Evaluation of TOMs

Under GDPR Art. 32(1)(d), measures must be subject to regular testing and evaluation. AIDSTATION's posture:

- **Annual review** of this document by the Privacy Lead, in conjunction with Engineering Lead, to assess whether each measure remains appropriate to the current risk posture
- **Pre-launch review** before public general-availability launch, with counsel input
- **Ad hoc review** on material change — new processor, new data category, new processing activity, new threat intelligence affecting AIDSTATION
- **Post-incident review** — incidents trigger a re-examination of the relevant control category
- **No formal third-party audit** at v1; counsel review and the periodic internal reviews are the v1 cadence. SOC 2 or ISO 27001 attestation is a Target State item that depends on commercial demand

---

## 14. Mapping to External Frameworks

For counterparties expecting a recognizable framework mapping, the following is a directional rather than literal alignment.

| Framework | AIDSTATION posture |
|---|---|
| GDPR Art. 32 — appropriate technical and organizational measures | This document implements |
| ISO 27001 control families | Directional alignment across A.5 (organizational), A.6 (people), A.7 (physical — delegated to providers), A.8 (technological); no certification |
| SOC 2 Trust Services Criteria | Directional alignment across Security; no attestation |
| NIST CSF | Identify / Protect / Detect / Respond / Recover — directional alignment; no formal mapping |
| HIPAA | Not in scope — AIDSTATION is not a covered entity or business associate |
| CCPA / CPRA technical safeguards | Aligned through GDPR-equivalent measures |

A counterparty requiring formal attestation under any of the above frameworks should be advised that AIDSTATION does not currently hold such attestation; the underlying controls in this document are available for review under NDA.

---

## 15. Reservation of Rights

This document is an internal operational record of AIDSTATION's technical and organizational measures. It does not:

- Create third-party rights or warranties beyond what is committed in the executed DPA or other applicable agreement
- Constitute a guarantee that any specific measure will prevent any specific incident — the standard is "appropriate" measures, not absolute prevention
- Limit AIDSTATION's discretion to modify, add, remove, or substitute measures as the business and risk landscape evolve

Material changes will be reflected in a subsequent version of this document. Counterparties operating under DPAs that reference this document by version should expect to be notified of material changes affecting their processing.

---

## 16. Cross-Spec Touchpoints

| Document | Relationship |
|---|---|
| `AIDSTATION_DPA_Template` | Annex 2 references this document as canonical TOMs |
| `AIDSTATION_RoPA` | "Technical and Organizational Measures Reference" section points here |
| `AIDSTATION_LIA_PA15` §4.6 #5, #7 | AI training-specific safeguards reference §3 access controls and §7 logging |
| `AIDSTATION_DPIA_PA15` | R-08 (insider misuse) → §3.1, §3.2, §7; R-11 (processor breach) → §9; R-14 (training data breach) → §2.2, §3.2, §7 |
| `AIDSTATION_Breach_Response_Playbook` | §8 above; foundational controls here, response process there |
| `AIDSTATION_Privacy_Policy` §8 | User-facing summary of security measures; this document is the underlying detail |
| `AIDSTATION_Deletion_Flow_Spec` | §11 references; deletion process detail lives there |
| `AIDSTATION_Inactivity_Automation_Spec` | §11 references |
| `AIDSTATION_Aggregation_Suppression_Spec` | §12 references |
| `AIDSTATION_Partners_Page` | §9 — public processor list |

---

## 17. Gut Check

### 17.1 Risks

- **The Current/Committed/Target distinction is the most important design choice in this document and the most likely to drift.** As measures are built out, the temptation will be to silently promote Committed items to Current without auditing whether the build actually meets the commitment. The §13 annual review must specifically verify the Current State claims against operational reality. If it doesn't, this document becomes aspirational rather than descriptive.
- **The directional-mapping in §14 will get pressed by enterprise B2B prospects.** "Directional alignment" with SOC 2 is not SOC 2. Sales conversations will create pressure to overclaim. The §15 reservation language plus the explicit no-attestation note in §14 are the protection; sales materials must mirror this language, not improve on it.
- **The processor list in §9.1 is incomplete and will be challenged in counsel review.** Several processors are listed with DPA-pending status. Pending status is fine for an internal draft but becomes a liability if the document is shared externally with that gap.
- **The 4-hour informal RTO in §6 is a real commitment even though labeled informal.** Customers reading this document will treat the 4-hour figure as a baseline expectation. If reality is 8 hours, change the document; do not let an informal expectation become a de-facto commitment we can't keep.
- **No formal personnel background-check process is a known weakness for B2B sales.** Many enterprise prospects will require it before engagement. Either lock the Target State decision (we will not do this at current scale) or move it to Committed with a trigger condition.

### 17.2 What might be missing

- **Specific cryptographic standards** beyond "AES-256, TLS 1.2+." Some counterparties will want explicit standards references (FIPS 140-2 / 140-3 module use, etc.). The cloud providers' attestations cover this indirectly but a counterparty doing real due diligence will want the link.
- **Data residency commitments.** §2.2 names US-based hosting and SCC posture but does not commit to specific regions or forbid migration. Enterprise prospects will ask.
- **Geographic personnel exclusions.** Whether AIDSTATION personnel based in specific regions have access to user data may matter for some counterparties. Not addressed.
- **Encryption key rotation cadence.** Not addressed; relies on provider defaults.
- **Specific incident response timing internal to the team** (versus the 72-hour external regulator window). Playbook should fill this; if not, this is a gap.

### 17.3 Best argument against this document's posture

A counter-position: **the Current/Committed/Target framing is too candid for an externally-shared document.** Many TOMs documents in the wild present a single composite picture without distinguishing "what we do today" from "what we plan to do." This makes them more salesworthy and harder to argue against in due diligence.

The defense for the candid framing:

- Misrepresenting Current State as Target State (or vice versa) creates legal exposure if a breach later reveals the gap. Honest framing is the legally safer posture.
- Counterparties doing real due diligence will detect the gap regardless; presenting candidly is more credible than the alternative.
- The §15 reservation of rights provides protection against the document being read as a warranty; the candid framing makes that reservation more credible, not less.

If counsel takes the more polished-presentation view, the structural revision is straightforward: remove the Committed and Target columns, restate everything as Current with footnotes for items in progress. The underlying control inventory does not change.

**v1 stands with the Current/Committed/Target framing.** A revision to a single-state presentation is a counsel-directed change that does not require rebuilding the document.

### 17.4 v2 Lens Pass Addendum

**What v2 changed and why it is low-risk.** The v2 lens edits are deliberately conservative because the lens runs in reverse for a TOMs document — the operator's exposure here is over-commitment, not under-assertion. v2 *reduced* representable commitments (removed the §6 RTO number, declined to restate the playbook's timing numbers in §8) and tightened the language around vendor no-secondary-use (§9 → DPA §4.12). None of these claim a control AIDSTATION does not have; they remove liability surface and fix cross-reference drift.

**Residual risks.**

- The §9.1 processor list still carries "DPA pending standard terms" for Anthropic, Neon, and Vercel. That is honest for an internal draft but is the single most likely thing a counterparty doing real due diligence will press. Not a lens issue — a standing operational item (resolve the actual DPAs) flagged again here.
- v2's §7.2 ties security-log retention to the Art. 33(5) obligation. That is correct but means the retention claim is now load-bearing for the breach-record posture: if logs are actually purged earlier than stated, the gap is now a documented inconsistency rather than a silent one. The §13 annual review must verify the actual retention against this claim.

**Best argument against the v2 edits.** Removing the §6 RTO number could be read as *weakening* the document for sales — enterprise prospects like to see a restoration target. The counter: an unbacked, untested number is a liability that a single missed restoration converts into a misrepresentation claim. A real RTO belongs in Committed/Target with a tested runbook behind it, not as an "informal" figure in a representable document. When AIDSTATION can back a number, it gets added as a commitment; until then, silence is the operator-favorable position.

---

## Change Log

| Version | Date | Changes | Author |
|---|---|---|---|
| v1 | May 19, 2026 | Initial document. Establishes standalone TOMs reference (resolves D-77 in favor of standalone). 13 control categories. Current / Committed / Target framing for honest sequencing. External framework mapping in §14 is directional, no formal attestation. §17 gut check flags the most likely areas for counsel-directed revision. | Privacy Lead |
| v2 | May 30, 2026 | Tier 2 lens pass (operator-favorable + lawful + single global rule). Lens runs in reverse for a TOMs document — over-commitment is the operator risk — so v2 reduces representable commitments rather than asserting stronger controls. Lens Calibration Notes added (four callouts). Substantive edits: **§6 informal 4-hour RTO removed** (de-committed; an informal number in a counterparty-representable document is a de-facto commitment, as v1 §17.1 flagged); **§7.2 logging retention reframed to minimum-appropriate, security-log retention tied to Breach Playbook v4 §12.1 Art. 33(5) record-keeping**; **§8 bracketed incident-response placeholders replaced with real Breach Playbook v4 section numbers (§4/§5.2/§5.3/§6/§7/§10/§11/§12.1/§13); restated "72-hour" numeric commitment removed** so numbers live only in the playbook; **§9 no-secondary-use control anchored to DPA Template v3 §4.12 and §4.12(g), and vendor due diligence extended to confirm a prospective ML-infra vendor preserves the §4.12(c) controller-instructed-training carve-out**. All companion-doc references updated to current versions (DPA v3, Breach Playbook v4, RoPA v4, PP v4, Deletion Flow Spec v4, Inactivity Spec v3, Aggregation Spec v3, LIA PA-15 v2, DPIA PA-15 v2; AI System Prompt Restrictions left at v2 as correct). §17.4 v2 Gut Check addendum added. (Privacy Program Backlog: Tier 2 lens batch — TOMs lens pass per Track A G2 Closing Handoff §5.6, D-121.) | Privacy Lead |
| v3 | May 30, 2026 | Contact-address consolidation to the two approved addresses: `help@aidstation.pro` for user support (including privacy / data-rights requests) and `info@aidstation.pro` for formal, legal, security, and DMCA correspondence. No other changes. | Privacy Lead |

---

*Cross-reference cleanup (v3, 2026-05-30): inline references to companion documents were converted to unversioned logical names per Rule #12, so they no longer go stale when a companion document is revised. No substantive content changes. See `Privacy_Program_Consistency_Sweep_Report_v1.md`.*



*Content-equivalence fix (2026-05-30): minimum-age cross-reference corrected from T&C §1 to T&C §2 (Eligibility).*
