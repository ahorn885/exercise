# Data Protection Impact Assessment (DPIA) Template

**Status:** v4 — cross-reference unversioning cleanup (no substantive change since the v3 Tier 2 lens pass). Reusable template for high-risk processing assessments.
**Legal basis:** GDPR Article 35 (UK GDPR Art. 35; analogous frameworks under POPIA, Quebec Law 25)
**Owner:** [Privacy Lead]
**Last Updated:** May 30, 2026
**Companion docs:** `AIDSTATION_RoPA` (each DPIA references the relevant PA entry), `AIDSTATION_DPIA_PA15` (completed worked example using this methodology), `AIDSTATION_TOMs` (mitigation control inventory), `AIDSTATION_Breach_Response_Playbook` (post-incident review feeds this template's §8.4 incident-driven review trigger), `AIDSTATION_Privacy_Policy`, `AIDSTATION_Terms_and_Conditions`

---

## Lens Calibration Notes (v4)

A DPIA template is an internal methodology, not a counterparty-representable document, so the lens here is about calibrating the discretionary thresholds the methodology uses — the DPIA trigger, the risk matrix, the residual-acceptance threshold, and the Art. 36 consultation trigger. The aim is a methodology that is lawful and audit-defensible while not over-triggering costly full DPIAs or inviting the supervisory authority in earlier than the law requires. Counsel should be directed here on review.

1. **Tiered screening (Step 1).** v2 said "if unclear, conduct one anyway." For the bright-line Art. 35(3) mandatory triggers that conservative default is kept. But for genuinely ambiguous discretionary cases, v4 adds a lightweight **threshold assessment** — a short documented record concluding whether a full DPIA is required — rather than defaulting every ambiguous case to a full DPIA. This is operator-favorable (a full DPIA is real work; the threshold assessment resolves ambiguity cheaply) and lawful (the threshold assessment is itself the documented Art. 35 consideration and the accountability record for a no-DPIA conclusion).

2. **Inherent vs. residual risk separated (Steps 6–7).** v2's matrix and the Art. 36 trigger were not cleanly separated. v3 states explicitly that the §6 matrix rates **inherent** risk, while the Art. 36 prior-consultation obligation is keyed to **residual** risk after mitigation. An inherent-High risk that strong mitigations reduce to Medium does **not** trigger Art. 36 — this is the single most operationally important calibration, and it is exactly the legal standard (Art. 36 is about residual risk).

3. **Residual-acceptance threshold deliberately held at ≤ Medium (Step 7.3), tighter than the strict legal line.** The strict GDPR line is "not high." v3 keeps the self-imposed ≤ Medium acceptance threshold rather than loosening to the legal minimum. For an operator processing Art. 9 health data, the marginal value of pushing a residual-High through with documented justification is far outweighed by the enforcement and regulator-attention exposure — the same regulator-safe-middle reasoning the Inactivity Spec applied to retention. Holding the conservative threshold is the cost-benefit-weighted operator-favorable position here, not loosening it.

4. **Art. 36 consultation framed as a last resort (Steps 7.3, 8).** The ordering is sharpened to redesign → decline → consult. Reaching the Art. 36 trigger should be read as a signal that the processing design needs rework first. Consultation remains available and mandatory where residual high risk genuinely cannot be mitigated — but the methodology's job is to drive risk below the threshold so that Art. 36 is rarely reached. Operator-favorable (avoid inviting the regulator in); lawful (Art. 36 preserved).

5. **GDPR methodology as the single global standard.** The template runs the GDPR Art. 35/36 method as the one global standard; calibrating to the strictest framework satisfies the analogous regimes (POPIA, Quebec Law 25) without a per-jurisdiction DPIA variant.

---

---

## How to Use This Template

A DPIA is required under GDPR Article 35 when processing is "likely to result in a high risk to the rights and freedoms of natural persons." It is also required as good practice for any significant new processing activity affecting personal data.

For AIDSTATION specifically, a DPIA is **required** for:

- The core processing of sensitive health and biometric data of users at scale
- The AI-driven automated profiling that generates training plans
- Any major change to data sharing arrangements (new research partnership, new integration, etc.)

This template walks through the assessment in eight steps. Complete each step in order. The output is a written DPIA document that can be presented to a supervisory authority if requested. For a completed example applying this methodology end-to-end, see `AIDSTATION_DPIA_PA15` (AI model training and development).

This template runs the GDPR Art. 35/36 methodology as AIDSTATION's single global standard. Calibrating to the strictest applicable framework satisfies analogous regimes (POPIA, Quebec Law 25) without a per-jurisdiction variant. Where a specific jurisdiction imposes a requirement GDPR does not, that is noted in the individual DPIA rather than forked into a separate template.

Not every new processing activity needs a full DPIA. Where it is genuinely unclear whether the Art. 35 threshold is met, complete the lightweight **threshold assessment** in Step 1 rather than defaulting to a full eight-step DPIA — the threshold assessment is itself the documented Art. 35 consideration and stands as the accountability record if the conclusion is that no DPIA is required.

**The DPIA must be conducted before the processing begins** (not retroactively, except where the obligation is being formalized after the fact for processing that pre-exists the obligation).

For high-risk processing where mitigations cannot adequately reduce risk, **prior consultation with the supervisory authority is required** before processing begins (GDPR Art. 36). This is a last resort — see Step 7.3 for the redesign → decline → consult ordering.

---

## DPIA Cover Page

| Field | Value |
|---|---|
| DPIA Title | [e.g., "DPIA for Sensitive Health Data Processing in AIDSTATION Core Service"] |
| Project / Processing Activity | [Reference to the RoPA entry or processing initiative] |
| DPIA Author | [Name, title] |
| DPIA Date Started | [Date] |
| DPIA Date Completed | [Date] |
| Review Date | [Date — typically annual or on material change] |
| Sign-off — Privacy Lead | [Name, date] |
| Sign-off — DPO (where appointed) | [Name, date] |
| Sign-off — Executive | [Name, date] |

---

## Step 1: Screening — Is a DPIA Required?

Before proceeding, document whether a DPIA is mandatory. For the bright-line Art. 35(3) triggers below, when one applies the DPIA is mandatory — no judgment call. Where it is genuinely unclear (discretionary triggers, novel processing), complete the **threshold assessment** at the end of this step: a short documented determination, rather than defaulting straight to a full DPIA. When the threshold assessment itself is ambiguous, resolve toward conducting the DPIA — the cost is low and the protection is real.

### Triggers for Mandatory DPIA (GDPR Art. 35(3))

Mark each that applies. If **any** apply, DPIA is mandatory.

- [ ] Systematic and extensive evaluation of personal aspects based on automated processing (including profiling) producing legal or similarly significant effects
- [ ] Processing on a large scale of special categories of data or data relating to criminal convictions
- [ ] Systematic monitoring of publicly accessible areas on a large scale

### Additional Triggers from Supervisory Authority Guidance

Mark each that applies. Two or more typically indicate DPIA is required even if Art. 35(3) does not directly apply.

- [ ] Evaluation or scoring (including profiling)
- [ ] Automated decision-making with legal or similarly significant effects
- [ ] Systematic monitoring
- [ ] Sensitive or highly personal data
- [ ] Data processed on a large scale
- [ ] Matching or combining datasets
- [ ] Data concerning vulnerable data subjects
- [ ] Innovative use of technology
- [ ] Cross-border transfers outside the EU/UK
- [ ] Processing that prevents data subjects from exercising a right or using a service or contract

### Conclusion of Screening

DPIA required: [ ] Yes [ ] No

Path taken:
- [ ] **Mandatory** — one or more Art. 35(3) bright-line triggers apply → full DPIA (Steps 2–8)
- [ ] **Discretionary, threshold met** — two or more supervisory-authority criteria apply → full DPIA (Steps 2–8)
- [ ] **Threshold assessment — no DPIA required** — complete the record below; retain as the accountability record

Rationale: [Brief explanation]

### Threshold Assessment Record (where no full DPIA is conducted)

Complete this only where the conclusion is that a full DPIA is **not** required. This short record is the documented Art. 35 consideration and is retained per Appendix B; it is what demonstrates to a supervisory authority that the question was lawfully considered.

| Field | Detail |
|---|---|
| Processing activity | [Reference / RoPA entry] |
| Art. 35(3) triggers considered | [Which were checked; why none apply] |
| Supervisory-authority criteria met | [Count and which — fewer than two] |
| Special-category data involved? | [Yes/No; if yes, why the activity is nonetheless below the high-risk threshold] |
| Conclusion | No DPIA required because: [rationale] |
| Re-evaluation trigger | [What change would move this above the threshold and require a DPIA] |
| Recorded by / date | [Name, date] |

If special-category (Art. 9) data is involved at any meaningful scale, a "no DPIA required" conclusion should be rare and well-justified — AIDSTATION's core health-data processing meets the threshold and a threshold assessment is not a route around it.

---

## Step 2: Description of the Processing

Provide a clear, complete description. Reviewers must be able to understand what is being done without prior context.

### 2.1 Nature, Scope, Context, and Purposes

| Field | Detail |
|---|---|
| What is the processing? | [Concise description of what occurs] |
| Why is it being done? | [Purpose] |
| How is it carried out? | [Technical and operational mechanism] |
| Who carries it out? | [AIDSTATION teams; service providers] |
| What is the scale? | [Approximate number of data subjects; volume; geographic scope] |
| Who are the data subjects? | [Categories] |
| What categories of data are involved? | [List, with sensitive categories flagged] |
| Where does the data come from? | [Sources] |
| Where does the data go? | [Recipients, including international transfers] |
| How long is data retained? | [Retention period and basis] |

### 2.2 Data Flow Diagram

Include or attach a data flow diagram showing:
- Sources of data
- Storage locations
- Processing systems
- Recipients (internal and external)
- International transfers

### 2.3 Relationship to Other Processing

How does this processing relate to other AIDSTATION processing activities? Cross-reference the RoPA entries involved.

---

## Step 3: Consultation

Document who was consulted and what their input was.

### 3.1 Internal Consultation

| Stakeholder | Role | Input |
|---|---|---|
| Engineering Lead | Technical feasibility, security | [Notes] |
| Privacy Lead | Compliance posture | [Notes] |
| Product Lead | User experience implications | [Notes] |
| Legal Counsel | Legal advice | [Notes] |
| DPO (if appointed) | Independent oversight | [Notes] |

### 3.2 Data Subject Consultation

GDPR requires that the controller "seek the views of data subjects or their representatives" where appropriate.

How were data subjects consulted (or why was consultation not done)?

- [ ] User research / interviews
- [ ] Survey
- [ ] Beta testing with feedback collection
- [ ] Privacy preference data from existing users
- [ ] Public consultation
- [ ] No direct consultation — rationale: [explanation]

### 3.3 External Experts (where applicable)

- Independent security review: [yes / no / not required]
- Independent privacy review: [yes / no / not required]
- Industry/academic experts: [list]

---

## Step 4: Assessment of Necessity and Proportionality

### 4.1 Lawful Basis

What is the lawful basis under GDPR (and analogous frameworks)?

- [ ] Consent (Art. 6(1)(a) + Art. 9(2)(a) for special category)
- [ ] Contract (Art. 6(1)(b))
- [ ] Legal Obligation (Art. 6(1)(c))
- [ ] Vital Interests (Art. 6(1)(d))
- [ ] Public Task (Art. 6(1)(e))
- [ ] Legitimate Interests (Art. 6(1)(f))

For special category data, additional condition under Art. 9(2): [specify]

### 4.2 Necessity

Is the processing necessary to achieve the stated purpose? Could the purpose be achieved with less data or less intrusive means?

[Analysis]

### 4.3 Proportionality

Is the scope of the processing proportionate to the purpose?

| Element | Question | Assessment |
|---|---|---|
| Data minimization | Are we processing only what is needed? | [Yes / Could be reduced / No] |
| Storage limitation | Is retention only as long as needed? | [Yes / Should be shorter / No] |
| Purpose limitation | Is data used only for stated purposes? | [Yes / Some scope creep / No] |
| Accuracy | Are accuracy mechanisms in place? | [Yes / Partial / No] |
| Transparency | Have we been clear with data subjects? | [Yes / Could be clearer / No] |

### 4.4 Data Subject Rights

How are data subject rights supported under this processing?

| Right | Mechanism |
|---|---|
| Access | [How users can access their data] |
| Rectification | [How users can correct data] |
| Erasure | [How users can delete data] |
| Portability | [Format and process] |
| Restriction | [Mechanism] |
| Objection | [Mechanism] |
| Withdraw consent | [Mechanism] |
| Not to be subject to automated decisions | [Where applicable] |

---

## Step 5: Risk Identification

Identify risks to the rights and freedoms of data subjects. Consider both direct privacy risks and broader rights impacts.

For each risk, identify:
- **What** the risk is
- **To whom** (which data subjects)
- **Source** (what could cause the risk to materialize)

### 5.1 Risk Categories to Consider

Use the following checklist to prompt risk identification. Not all will apply to every processing activity.

**Confidentiality risks:**
- Unauthorized access by personnel
- Unauthorized access by third parties (breach)
- Re-identification of de-identified (pseudonymized) data
- Exposure through sharing arrangements
- Government access requests

**Integrity risks:**
- Inaccurate data leading to wrong decisions
- Data corruption
- Unauthorized modification

**Availability risks:**
- Data loss
- Service disruption affecting user access to their data

**Rights and freedoms risks:**
- Discrimination (algorithmic or otherwise)
- Loss of control over personal information
- Financial loss
- Reputational damage
- Physical or emotional harm
- Inability to exercise rights
- Restriction of fundamental rights (privacy, autonomy, dignity)

**Compliance risks:**
- Failure to meet legal obligations
- Failure to honor data subject rights
- Inadequate consent mechanisms

### 5.2 Identified Risks Register

| ID | Risk | To Whom | Source | Notes |
|---|---|---|---|---|
| R-01 | [Risk description] | [Data subjects affected] | [Source / cause] | [Notes] |
| R-02 | | | | |
| R-03 | | | | |

---

## Step 6: Risk Assessment

For each identified risk, assess likelihood and severity, then determine overall risk level.

**Calibration (v3).** The rating produced here is the **inherent** risk — the risk before the Step 7 mitigations are credited. This matters because the Art. 36 prior-consultation obligation (Step 7.3) is keyed to **residual** risk after mitigation, not to inherent risk. An inherent-High risk that strong mitigations reduce to Medium is acceptable and does not trigger consultation. Do not deflate the inherent rating to avoid a downstream trigger — that is both unlawful and self-defeating on audit; the lawful place to lower risk is real mitigation in Step 7, not optimistic scoring here.

For **special-category (Art. 9) data** — AIDSTATION's recurring case — severity is rated at the higher end by default: re-identification or exposure of health, biometric, or injury data is treated as at least High severity, and Severe where it could lead to physical, financial, or significant emotional harm. This tracks both regulator expectations and the asymmetric downstream exposure (Breach Playbook §7.2 default-toward-Art. 34 notification; DPA §7(d) uncapped liability categories). See `AIDSTATION_DPIA_PA15` for worked ratings.

### 6.1 Likelihood Scale

| Level | Description |
|---|---|
| Low | Unlikely to occur in normal operation; would require unusual combination of failures |
| Medium | Could plausibly occur; requires specific failure or attack |
| High | Reasonably foreseeable given current state and threat environment |

### 6.2 Severity Scale

| Level | Description |
|---|---|
| Low | Minor inconvenience; easily reversible; no lasting impact |
| Medium | Notable harm; some difficulty or cost to remedy; temporary impact |
| High | Significant harm; difficult or impossible to remedy; lasting impact |
| Severe | Major harm; physical safety, severe financial loss, or fundamental rights violation |

### 6.3 Risk Matrix

| | Low Severity | Medium Severity | High Severity | Severe |
|---|---|---|---|---|
| **Low Likelihood** | Low | Low | Medium | High |
| **Medium Likelihood** | Low | Medium | High | High |
| **High Likelihood** | Medium | High | High | Critical |

### 6.4 Risk Assessment Table

| ID | Risk | Likelihood | Severity | Overall | Notes |
|---|---|---|---|---|---|
| R-01 | | | | | |
| R-02 | | | | | |
| R-03 | | | | | |

---

## Step 7: Mitigation Measures

For each identified risk, document measures to reduce likelihood, reduce severity, or both.

### 7.1 Mitigation Register

| Risk ID | Mitigation | Type | Reduces | Owner | Status |
|---|---|---|---|---|---|
| R-01 | [Description of mitigation] | Technical / Organizational / Both | Likelihood / Severity / Both | [Owner] | [Planned / Implemented] |
| R-02 | | | | | |

### 7.2 Residual Risk Assessment

After mitigations are applied, re-assess each risk to determine residual risk.

| ID | Original Overall | Mitigated Overall | Acceptable? |
|---|---|---|---|
| R-01 | | | [Yes / No / Conditional] |
| R-02 | | | |

### 7.3 Acceptable Risk Threshold

The threshold for acceptable **residual** risk (after Step 7 mitigations are credited) is **Medium or lower** for any single risk, with no High or Critical risks remaining after mitigation.

**Why ≤ Medium and not the strict legal line (v3).** The strict GDPR line for the Art. 36 obligation is "not high." AIDSTATION holds a tighter self-imposed line — residual must be Medium or lower — deliberately. For an operator processing Art. 9 health data, the marginal value of pushing a documented-acceptable residual-High through is far outweighed by the enforcement and regulator-attention exposure. Holding the conservative threshold is the cost-benefit-weighted operator-favorable position here; it is not a place to loosen.

**Inherent vs. residual (v3).** A risk rated High or Critical at Step 6 (inherent) is fully acceptable if Step 7 mitigations bring its residual rating to Medium or lower. The threshold applies to the **mitigated** column of the Step 7.2 table, never to the inherent rating.

Where a risk cannot be mitigated to Medium or lower, work the following in order — consultation is the last resort, not the first move:

1. **Redesign the processing** to eliminate or further reduce the risk. Reaching this point is a signal the design needs rework before anything else.
2. **Decline to proceed** with the processing (or the high-risk component of it) if redesign cannot bring residual risk within threshold.
3. **Consult the supervisory authority** under GDPR Art. 36 — mandatory where, after best mitigation and with redesign and decline genuinely considered, residual **high** risk still remains. Reaching Art. 36 should be rare; if a DPIA routinely reaches it, the upstream design or mitigation approach is the problem.

---

## Step 8: Outcome and Sign-Off

### 8.1 Conclusion

[ ] **Proceed** — Processing may begin / continue. Residual risks are acceptable. Mitigations to be implemented per plan.

[ ] **Conditional Proceed** — Processing may begin / continue subject to specific conditions: [list conditions]

[ ] **Redesign Required** — Processing as currently described creates unacceptable risk. Specific changes required: [list]

[ ] **Prior Consultation Required** — Residual high risk remains after best mitigation, and redesign and decline have been considered and documented as not viable; supervisory authority must be consulted before proceeding (GDPR Art. 36).

[ ] **Do Not Proceed** — Risk to data subjects outweighs the benefit of the processing.

### 8.2 Conditions and Action Items

| Action | Owner | Deadline | Status |
|---|---|---|---|
| | | | |

### 8.3 Sign-Off

| Role | Name | Date | Signature |
|---|---|---|---|
| Privacy Lead | | | |
| DPO (where appointed) | | | |
| Engineering Lead | | | |
| Executive Sponsor | | | |

### 8.4 Review Schedule

| Review Trigger | Next Review Date |
|---|---|
| Annual review | [Date] |
| On material change to processing | As-needed |
| On change in legal landscape | As-needed |
| On security incident affecting this processing | Within 30 days |

---

## Appendix A: Reference DPIA Topics for AIDSTATION

The following are known processing areas where AIDSTATION will need DPIAs. This list will grow.

1. **Sensitive health data processing** — Core opt-in flow; cross-platform integration ingestion. **Highest priority.**
2. **AI-driven training plan generation** — Automated profiling implications, even if not producing "legal or significant effects" under Art. 22.
3. **Conversational AI coach** — User-volunteered sensitive information; refusal mechanism efficacy.
4. **AI model training and development** (RoPA PA-15) — AIDSTATION's training of its own coaching models on user content. Distinct from runtime inference. **Required before scaled training begins.** Covers: de-identification adequacy, sensitive-category consent flow, memorization-leak risk, deletion-vs-trained-weights tension, training data lineage for algorithmic disgorgement exposure. A completed DPIA for this activity exists at `AIDSTATION_DPIA_PA15` and serves as the worked example for this template.
5. **Research data sharing** — Pseudonymization adequacy; re-identification risk in longitudinal training data.
6. **Crowdsourced facility database** — Cross-contamination risk with user identity.
7. **Team-based training feature** (when designed) — Data sharing model; teammate visibility scope. **Athlete-to-athlete only per T&C §9**; no human-coach data model.
8. **Athlete data integration architecture** (when finalized) — Multi-source data conflicts; OAuth scope risk.

Each will need its own completed DPIA before the relevant processing scales up or before EU/UK launch.

---

## Appendix B: Maintenance and Documentation

Completed DPIAs are retained as part of the AIDSTATION compliance documentation:

- Stored in [TBD location] with restricted access
- Retention: for the life of the processing activity plus a defense tail (the limitation period for a claim arising from the processing), then reviewed for disposal. "Indefinite" is avoided as the default — a completed DPIA is an accountability artifact, but open-ended retention is not the minimization-aligned position; tie disposal to the processing ending plus the defense window. Where the processing is ongoing, the DPIA is retained and kept current.
- Referenced in the RoPA entry for each processing activity
- Available to supervisory authorities on request
- Updated on material change to the processing or the legal landscape

---

## Appendix C: Template Design Gut Check (v3)

**Risks in the v3 calibration.**

- The tiered threshold-assessment (Step 1) creates a route that, if misused, becomes a way to talk past a required DPIA. The guardrail is the explicit note that special-category processing at scale meets the threshold and a threshold assessment is not a path around it. If the threshold assessment starts getting used to wave through Art. 9 processing, that is a misuse to catch in the §13/annual review, not a defect in the template.
- Holding residual acceptance at ≤ Medium (tighter than the legal line) is the conservative call, but it means a legitimately mitigable processing could get blocked or sent to redesign where the strict law would have allowed it through with documentation. That is the intended trade for a health-data operator; counsel may want the option to relax to the legal line for a specific non-sensitive activity, which is a per-DPIA deviation, not a template change.

**What might be missing.**

- The template still has no quantified scale anchors ("large scale" is left to judgment). EDPB guidance is deliberately non-numeric, so this is defensible, but a worked internal heuristic (e.g., data-subject counts that AIDSTATION treats as "large scale") would make screening more consistent. Deferred — better set once real user numbers exist.
- The risk matrix (§6.3) is a 3×4 inherent-risk grid; it does not encode the special-category severity floor described in the Step 6 calibration text. The text governs, but a future revision could bake the floor into the matrix itself.

**Best argument against the v3 changes.** The v2 template was already lawful and simpler; v3 adds calibration prose that a small team may not internalize under time pressure, and an under-trained user might apply the tiered screening or the inherent/residual distinction incorrectly. The counter: the distinctions v3 adds (inherent vs residual; trigger as last resort) are exactly the ones that, if gotten wrong, cause either unlawful under-assessment or needless regulator consultations — they are worth the added words. The worked example (`AIDSTATION_DPIA_PA15`) is the antidote to abstract prose; a user follows the example, not the theory.

---

## Change Log (for this template)

| Version | Date | Changes | Author |
|---|---|---|---|
| v1 | (superseded) | Initial template | [Privacy Lead] |
| v2 | May 19, 2026 | Appendix A item 4 added (AI model training and development) to reflect RoPA v2 PA-15 and PP v2 §4; Appendix A item 7 (team-based training) updated to athlete-to-athlete only per T&C v2 §10 | [Privacy Lead] |
| v3 | May 30, 2026 | Tier 2 lens pass (operator-favorable + lawful + single global rule). Lens Calibration Notes added (five callouts). Substantive calibration: **Step 1 tiered screening** — added lightweight threshold-assessment path and a Threshold Assessment Record for documented no-DPIA conclusions, keeping Art. 35(3) bright-lines mandatory; **Step 6 inherent-vs-residual separation** plus special-category severity floor (health/biometric/injury exposure rated High+ by default); **Step 7.3 residual-acceptance threshold** held deliberately at ≤ Medium (tighter than the strict "not high" legal line, with rationale) and Art. 36 reframed as last resort with redesign → decline → consult ordering; **Step 8** prior-consultation outcome sharpened to require redesign/decline documentation first. "How to Use" adds single-global-standard statement and worked-example pointer. Appendix A cross-refs corrected (RoPA v2 → v4 PA-15; **T&C v2 §10 → T&C v3 §9** for the athlete-to-athlete clause, which moved sections) and DPIA PA-15 v2 named as the worked example. Appendix B retention reframed from "indefinite" to processing-life + defense tail. Companion-doc header added (RoPA v4, DPIA PA-15 v2, TOMs v2, Breach Playbook v4, PP v4, T&C v3). Appendix C Template Design Gut Check added. (Privacy Program Backlog: Tier 2 lens batch — DPIA Template lens pass per Track A G2 Closing Handoff §5.7, D-122; final Tier 2 item.) | [Privacy Lead] |

---

*Cross-reference cleanup (v4, 2026-05-30): inline references to companion documents were converted to unversioned logical names per Rule #12, so they no longer go stale when a companion document is revised. No substantive content changes. See `Privacy_Program_Consistency_Sweep_Report_v1.md`.*

