# AIDSTATION DPIA — PA-15 AI Model Training and Development

**Status:** v3 — cross-reference unversioning cleanup (no substantive change since the v2 Track A consistency-pass alignment with the LIA)
**Owner:** Privacy Lead
**Last Updated:** May 19, 2026
**Supersedes:** `AIDSTATION_DPIA_PA15_v1.md`
**Processing activity covered:** PA-15 (per `AIDSTATION_RoPA`) — AI Model Training and Development
**Lawful basis under assessment:** Art. 6(1)(f) legitimate interest (non-special category) + Art. 9(2)(a) explicit consent (special category, where opted in)
**Companion docs:** `AIDSTATION_LIA_PA15_v2.md` (parallel LIA, legal-basis analysis; v3 supersedes v1), `AIDSTATION_RoPA_v3.md` (PA-15 entry), `AIDSTATION_Privacy_Policy_v3.md` §4 / §7 / §9, `AIDSTATION_Terms_and_Conditions_v2.md` §8.2, `AIDSTATION_Acceptable_Use_Policy_v1.md` §4, `AIDSTATION_AI_Safety_Logging_Decision_v1.md`, `AIDSTATION_DPIA_Template_v2.md` (parent template; Appendix A item 4)

---

## 0. Scope and Status

This DPIA assesses the privacy risks of PA-15 (AI Model Training and Development) and the adequacy of the mitigations committed to in PA-15, the LIA, and the surrounding privacy program. It is required by DPIA Template Appendix A item 4 and by the LIA §9 cross-reference.

The DPIA and the LIA are companion documents:

- The **LIA** assesses *legal basis* — whether Art. 6(1)(f) is the appropriate ground for non-special-category training data.
- This **DPIA** assesses *risk* — what could go wrong for data subjects, how likely and severe each scenario is, what mitigations apply, and what residual risk remains.

Where the LIA's analysis applies directly (data inventory, recipients, retention, lawful basis), this DPIA cites it rather than restating.

**Status of this document.** Draft for counsel review. Risk scorings are author judgments; counsel and the DPO (when appointed) should confirm or revise. Mitigations include both implemented controls and committed-but-not-yet-built controls — the latter are flagged. **This DPIA recommends Conditional Proceed**: PA-15 may proceed only as the §7.3 mitigations become operational. Until then, training on user data at scale is not authorized by this DPIA.

**Jurisdictional scope and single-global-rule design.** This DPIA is structured under UK/EU GDPR. AIDSTATION's operational behavior — opt-in default for new users, continuous opt-out availability, the §7 mitigation set, and the §7.3 operational-validity gate — is a single global rule applied to all users worldwide, calibrated to GDPR as the strictest applicable framework. The legal basis differs by jurisdiction (legitimate interest in GDPR; other bases in non-LI jurisdictions); the operational behavior does not. Country-specific overlays for non-GDPR jurisdictions are addressed at country-launch readiness review. See LIA §0.1 for the parallel statement and the rationale for single-global-rule design.

---

## DPIA Cover Page

| Field | Value |
|---|---|
| DPIA Title | AIDSTATION AI Model Training and Development DPIA |
| Project / Processing Activity | RoPA PA-15 |
| DPIA Author | Privacy Lead (draft) |
| DPIA Date Started | May 19, 2026 |
| DPIA Date Completed | TBD (post counsel review) |
| Review Date | Annual + on material change (see §8.4) |
| Sign-off — Privacy Lead | Pending |
| Sign-off — DPO (where appointed) | Pending |
| Sign-off — Executive | Pending |

---

## Step 1: Screening — Is a DPIA Required?

### 1.1 Art. 35(3) triggers

- [ ] Systematic and extensive evaluation of personal aspects based on automated processing (including profiling) producing legal or similarly significant effects
- [X] Processing on a large scale of special categories of data — **applies when the sensitive-category opt-in is in effect** (PA-03 sourcing, with additional training opt-in)
- [ ] Systematic monitoring of publicly accessible areas on a large scale

### 1.2 Additional triggers from supervisory authority guidance

- [X] Evaluation or scoring (including profiling) — training feeds models that produce coaching evaluations
- [ ] Automated decision-making with legal or similarly significant effects — PA-15 itself is preparatory; PA-04 inference is the ADM-adjacent activity
- [ ] Systematic monitoring — not applicable
- [X] Sensitive or highly personal data — health-adjacent at minimum; special category where opted in
- [X] Data processed on a large scale — intended at scale; pre-launch
- [X] Matching or combining datasets — training datasets aggregate per-user data across many sessions and many users
- [ ] Data concerning vulnerable data subjects — 16+ floor; not adolescent-specific
- [X] Innovative use of technology — LLM training on user content is a contested practice with evolving regulatory expectations (EDPB Opinion 28/2024 and successors)
- [X] Cross-border transfers outside the EU/UK — US storage and training infrastructure
- [ ] Processing that prevents data subjects from exercising a right — opt-out and deletion mechanisms available (per PP §9)

### 1.3 Screening conclusion

**DPIA required: Yes.** One Art. 35(3) trigger and six additional triggers apply. Independently, DPIA Template Appendix A item 4 lists PA-15 as a required-DPIA activity for AIDSTATION.

---

## Step 2: Description of the Processing

### 2.1 Nature, scope, context, and purposes

| Field | Detail |
|---|---|
| What is the processing? | Training, fine-tuning, evaluating, and indexing AI coaching models for the AIDSTATION pipeline. Four operational categories: (a) evaluation datasets to measure pipeline output quality; (b) retrieval-augmented generation (RAG) indexes over coaching content; (c) prompt tuning datasets; (d) fine-tuned model variants where applicable. |
| Why is it being done? | To improve AIDSTATION's coaching outputs in endurance and multi-sport domains beyond what foundation models alone deliver. Full legitimate-interest analysis: LIA §2. |
| How is it carried out? | User-content data ingested from the application database into a separate training data store; passed through redaction and de-identification pipelines; assembled into versioned training datasets with lineage manifests; consumed by fine-tuning, RAG index build, or eval jobs on infrastructure provider [TBD]. |
| Who carries it out? | AIDSTATION ML and engineering personnel with role-based access; ML infrastructure provider [TBD] as processor under DPA. |
| What is the scale? | Pre-launch. Intended scale: all consenting users in the production user base (initially low thousands; scales with adoption). Special-category data only included for users who have opted in twice (collection opt-in + training-use opt-in). |
| Who are the data subjects? | Active AIDSTATION users; users of deleted accounts whose data was incorporated into a prior model generation (per PP §7 "AI Models and Derivatives"). |
| What categories of data are involved? | **Non-special:** training plans and modifications, parsed coaching notes (not raw transcripts), activity/performance/progression data, user feedback signals (thumbs up/down, edits, follow-through), profile context (goals, sport, experience level). **Special (opt-in only, de-identified or aggregated):** health metrics, biometrics, where the user has separately opted in to training use. See RoPA PA-15 for inventory. |
| Where does the data come from? | RoPA sources: PA-01 (profile), PA-02 (training data), PA-03 (sensitive — opt-in only with additional training opt-in), PA-04 (plan outputs and follow-through), PA-05 (parsed coaching notes; raw transcripts not retained). |
| Where does the data go? | US-based training infrastructure (provider TBD); accessed by limited ML engineering staff with role-based controls. No third-party sharing for advertising or sale. SCCs for EU/UK transfers. |
| How long is data retained? | Training datasets: lifetime of model generation + 24 months reproducibility window after retirement. Model weights themselves: no defined retirement schedule; subject to algorithmic disgorgement obligations if ordered. Aggregated training signals (loss curves, eval metrics): indefinite as research artifacts. See PP §7 and RoPA PA-15 retention. |

### 2.2 Data flow

Source systems → application database → ETL into training data store → redaction and de-identification pipeline → versioned training datasets with lineage manifests → training infrastructure → model artifacts and eval reports → PA-04 production inference.

A formal diagram is a separate engineering deliverable; the text flow above is sufficient for this DPIA's level. The diagram should distinguish RAG ingest (which retains per-record retrievability) from fine-tuning ingest (which does not).

### 2.3 Relationship to other processing

- **PA-04 (Runtime AI Inference).** PA-15 produces the models PA-04 uses; runtime inference is downstream. Runtime-specific ADM risks are addressed in PA-04, not here.
- **PA-05 (Conversational Interface).** Raw transcripts are not retained per PA-05; only parsed coaching notes flow to PA-15.
- **PA-01 / PA-02 / PA-03.** Source activities per RoPA. PA-03 (sensitive data) requires both collection opt-in and the separate training-use opt-in.
- **AI Safety Logging Decision Batch 8.** Safety-report content is excluded from PA-15 by default (carve-out in that document §7). Reinforced here.

---

## Step 3: Consultation

### 3.1 Internal consultation

| Stakeholder | Role | Input |
|---|---|---|
| Engineering Lead | Technical feasibility of redaction, lineage tracking, memorization mitigations | Pending — captured during pre-launch engineering planning |
| Privacy Lead | Compliance posture | Draft author |
| Product Lead | Opt-out UX, onboarding callout on AI training role | Pending |
| Legal Counsel | Legal advice; LIA and this DPIA for review | Pending |
| DPO (where appointed) | Independent oversight | DPO not yet appointed; appointment is a tracked open item before EU/UK launch |

### 3.2 Data subject consultation

- [ ] Not yet conducted at v1. Rationale: pre-launch service; no live user base to consult. Beta-phase feedback collection on AI training disclosure is a tracked post-launch deliverable. The current disclosure (PP §4, §7, §9; T&C §8.2) is the principal articulation pending live feedback.

### 3.3 External experts

- Independent security review: not required at v1; security baseline per TOMs annex
- Independent privacy review: counsel review of LIA + this DPIA is the equivalent at this stage
- Industry/academic experts: not engaged at v1

---

## Step 4: Necessity and Proportionality

### 4.1 Lawful basis

- **Non-special category:** Art. 6(1)(f) legitimate interest. Analysis: LIA §2–§5. The LIA's three-stage analysis is mapped explicitly against EDPB Opinion 28/2024 in LIA §4.8; this DPIA does not duplicate that mapping but its risk assessment (§5–§7) operates within the Opinion's framework.
- **Special category (where opted in):** Art. 9(2)(a) explicit consent, obtained separately from the collection opt-in.

### 4.2 Necessity

Per LIA §3: training on user data is necessary; public/synthetic/licensed data cannot substitute for AIDSTATION-format coaching data and real-user feedback signals. Minimum-data discipline is applied via category-level exclusions (raw transcripts not retained; non-coaching-relevant metadata not ingested; special-category data excluded by default unless dual opt-in is in effect).

### 4.3 Proportionality

| Element | Assessment | Notes |
|---|---|---|
| Data minimization | Yes | Excluded by default: raw transcripts; non-coaching-relevant metadata; sensitive data without dual opt-in |
| Storage limitation | Yes | Training datasets retained per model generation + 24 months; aggregated artifacts indefinite, defensible given de-identification |
| Purpose limitation | Yes, with risk | Stated purpose: improve AIDSTATION coaching models. R-12 (purpose creep) is a tracked risk; no current secondary uses planned |
| Accuracy | Partial | Training data accuracy depends on upstream data quality. User-corrected plans and feedback signals serve as the accuracy mechanism. No formal accuracy verification of training datasets at v1 |
| Transparency | Yes | PP §4 explicit; T&C §8.2 license language; PP §9 right-to-object; front-summary clarifies AIDSTATION-vs-Anthropic training distinction |

### 4.4 Data subject rights

| Right | Mechanism |
|---|---|
| Access | Profile, training data, plan history, feedback signals available via export (PP §9). What the user contributed to training is recoverable via the lineage manifest when specifically requested (R-13 mitigation). |
| Rectification | User corrects profile data and feedback signals via the app; corrections flow into future training datasets but not back into already-produced model weights |
| Erasure | Account deletion removes future training use; already-incorporated data in produced models continues to operate (disclosed PP §7) |
| Portability | PP §9 — tabular training data in CSV; other stored data in machine-readable format; raw AI conversations not stored |
| Restriction | Account-settings opt-out for AI training (PP §9). Default state for new users is opt-in per LIA §8.1; opt-out toggle is available continuously. |
| Objection | Same — account-settings opt-out honored prospectively; default-in posture is consistent with the Art. 6(1)(f) basis (LI does not require opt-in). |
| Withdraw consent (special category only) | Separate opt-out for sensitive-category training use; collection opt-in remains independent unless also withdrawn |
| Not subject to automated decisions | PA-15 itself is preparatory; PA-04 (inference) governed by its own controls |

---

## Step 5: Risk Identification

For each risk: what it is, who is affected, what could cause it. Sources include the LIA risks register (LIA-1 through LIA-10) plus DPIA-specific engineering and operational risks.

| ID | Risk | To whom | Source / cause |
|---|---|---|---|
| R-01 | Trained model regurgitates verbatim user-specific content (memorization leak) | All users contributing to training data | LLM training dynamics; insufficient deduplication; rare-string memorization in fine-tuned variants |
| R-02 | De-identified training data is re-identified via linkage attack | Users in de-identified training sets | Insufficient de-identification methodology; linkage with external datasets |
| R-03 | Sensitive data leaks into the non-sensitive training pipeline through misclassification | Users with sensitive data | Free-text fields that pass the ingest filter but contain effectively sensitive content; parser failure on edge cases |
| R-04 | Trained models continue operating post-opt-out; user expectation gap | Users who opt out expecting full removal | Algorithmic disgorgement infeasibility at v1; disclosure may not be salient enough to overcome the natural reading of "opt-out" |
| R-05 | Algorithmic disgorgement order cannot be met | All users | Incomplete training data lineage; model weights not tied to dataset versions |
| R-06 | Discriminatory or biased coaching outputs from biased training data | Underrepresented demographic groups (sex, sport, experience level) | Training data composition reflecting active user base biases; absence of explicit fairness threshold criteria |
| R-07 | Cross-border training data transfer to US without adequate safeguards | EU/UK users | SCC implementation gap; processor location selection |
| R-08 | Insider misuse of training datasets (privileged personnel access) | All users contributing | Excessive ML personnel access; insufficient logging or review |
| R-09 | Underage user data enters training despite 16+ policy | Underage users who circumvented age verification | Age verification limited to self-attestation at signup |
| R-10 | Parsed coaching notes contain reconstructable PII | Users whose conversational AI use surfaced personal context | Parse pipeline insufficient redaction; free-text scrubbing gaps |
| R-11 | ML infrastructure provider trains on or retains AIDSTATION data outside contract | All users | Processor contractual breach; absent or insufficient audit |
| R-12 | Purpose creep: training datasets later used for purposes beyond coaching model improvement | All users | Internal pressure to monetize training assets (research publication, partner case studies, marketing); absence of binding internal control |
| R-13 | Inability to answer right-of-access for training data contributions | Requesting users | Lineage manifest gaps; query tooling not built |
| R-14 | Training dataset breach (unauthorized external access) | Users in the affected dataset version | Security incident on the training data store |

---

## Step 6: Risk Assessment

Pre-mitigation scoring using the Likelihood × Severity matrix in DPIA Template §6.

| ID | Risk | Likelihood | Severity | Overall | Notes |
|---|---|---|---|---|---|
| R-01 | Memorization leak | Medium | High | **High** | LLM memorization is documented in literature; severity high because leaked content can include health-adjacent context. Reduces with controls. |
| R-02 | Re-identification of de-identified data | Low | High | Medium | Requires linkage with external datasets; possible but effortful |
| R-03 | Sensitive data leaks into non-sensitive pipeline | Medium | High | **High** | Free-text classification is imperfect; recognized weak spot in any redaction pipeline |
| R-04 | Post-opt-out continued operation; user expectation gap | High | Medium | **High** | Likelihood high because the user-side mental model of "opt-out" naturally includes full removal; disclosure helps but does not eliminate. Severity medium because data is preparatory and outputs are de-identified by design. |
| R-05 | Algorithmic disgorgement cannot be met | Low (pre-launch) | High | Medium | Low at v1; rises post-launch if lineage tracking is not built |
| R-06 | Biased outputs | Medium | Medium | Medium | Likely to manifest in some form; outputs are advisory not consequential, but biased coaching is reputationally and ethically meaningful |
| R-07 | Cross-border transfer without safeguards | Low | Medium | Low | SCCs in DPA template; processor selection still TBD |
| R-08 | Insider misuse | Low | High | Medium | Small team, role-based access; severity high if exfiltration |
| R-09 | Underage data in training | Low | Medium | Low | 16+ policy at signup; remediation procedure exists |
| R-10 | Reconstructable PII in parsed notes | Medium | Medium | Medium | Realistic given free-text parsing limitations; severity moderated by de-identification |
| R-11 | Processor contractual breach | Low | High | Medium | DPA template + audit rights; severity high if it happens |
| R-12 | Purpose creep | Low | Medium | Low | Currently bound by RoPA + LIA stated purpose; risk rises with organizational growth |
| R-13 | Cannot fulfill RoA for training contributions | Medium | Low | Low | Likely at v1 if lineage tooling lags; severity low because data subjects retain access to upstream sources |
| R-14 | Training dataset breach | Low | High | Medium | Same posture as any data breach; severity high |

**Highest pre-mitigation risks: R-01, R-03, R-04.** R-04 is the LIA's identified "soft spot" (LIA §10.1).

---

## Step 7: Mitigation Measures

Mitigations map to the LIA §4.6 safeguards (#1–#12) plus DPIA-specific engineering controls. Status column: **I** = Implemented; **C** = Committed but not yet built.

### 7.1 Mitigation register

| Risk | Mitigation | Type | Reduces | Owner | Status |
|---|---|---|---|---|---|
| R-01 | Deduplication of high-frequency strings in training datasets | Technical | Likelihood | Engineering | C |
| R-01 | Sensitive-content filter at training ingest (reuses AI System Prompt Restrictions §3.1/§3.2 categories) | Technical | Likelihood + severity | Engineering | C |
| R-01 | Periodic adversarial memorization probing of trained models with documented cadence | Technical / Organizational | Detection of residual likelihood | Engineering + Privacy Lead | C |
| R-01 | Output validator at PA-04 inference time (defense in depth) | Technical | Severity | Engineering | C — partially specified per AI System Prompt Restrictions |
| R-02 | De-identification methodology aligned with NIST/ISO de-identification frameworks (specific methodology TBD) | Technical | Likelihood | Engineering | C |
| R-02 | Restriction on linkage-friendly identifiers (e.g., consistent cross-user pseudonyms forbidden where unnecessary) | Technical | Likelihood | Engineering | C |
| R-03 | Two-class ingest gate: sensitive-category data flows to a separate dataset only if dual opt-in present; never to default training pipeline | Technical | Likelihood | Engineering | C |
| R-03 | Pre-ingest free-text scrubbing for restricted-category terms | Technical | Likelihood | Engineering | C |
| R-03 | Manual sampling audit of training-dataset slices for misclassification | Organizational | Detection | Privacy Lead | C |
| R-04 | PP §7 disclosure of "AI Models and Derivatives" continuing operation post-deletion | Organizational | Expectation gap | Privacy Lead | I |
| R-04 | Account-settings opt-out toggle with timestamped logging | Technical / Organizational | Severity (limits prospective scope) | Engineering + Product | C |
| R-04 | In-product onboarding callout distinguishing AI training role from runtime coaching | Organizational | Expectation gap | Product | C |
| R-05 | Training dataset lineage manifest per dataset version, contributing user data versions traceable | Technical | Severity | Engineering | C |
| R-05 | Model artifact registry tying each weight to source dataset versions | Technical | Severity | Engineering | C |
| R-06 | Fairness evaluation suite covering sport, experience level, and (where data permits) sex demographic slices, run per model generation | Technical / Organizational | Likelihood | Engineering + Privacy Lead | C |
| R-06 | Documented fairness threshold criteria for model release | Organizational | Likelihood | Privacy Lead + Product | C |
| R-07 | SCCs in DPA template; processor selection requires SCC-compatible posture | Organizational | Likelihood | Privacy Lead | I (template) / C (processor selection) |
| R-08 | Role-based access; access logging; periodic access review | Technical / Organizational | Likelihood | Engineering + Privacy Lead | C (partial — baseline access controls apply; ML-specific RBAC pending) |
| R-09 | 16+ minimum age (PP §11, T&C §1); underage account discovery and remediation procedure (LIA §8.2); training dataset purge of removed-account contributions where lineage allows | Organizational | Likelihood + severity | Privacy Lead | I (policy) / C (procedure operationalization) |
| R-10 | Parsing pipeline applies free-text scrubbing pre-ingest (overlaps with R-03 mitigations) | Technical | Likelihood + severity | Engineering | C |
| R-10 | Periodic manual review of parsed-notes samples for residual PII | Organizational | Detection | Privacy Lead | C |
| R-11 | DPA includes no-training-on-our-data and no-derivative-use restrictions; audit rights | Organizational | Likelihood + severity | Privacy Lead | I (template) / C (processor execution) |
| R-12 | RoPA + LIA bind purpose; PP §4 discloses purpose; any new use requires RoPA amendment and LIA re-assessment | Organizational | Likelihood | Privacy Lead | I |
| R-13 | RoA query tooling against training data lineage | Technical | Likelihood | Engineering | C |
| R-14 | Training data store under same TOMs as production; restricted access; encryption at rest | Technical | Likelihood | Engineering | C (TOMs apply; training-store-specific posture pending) |

### 7.2 Residual risk assessment

After §7.1 mitigations are operational:

| ID | Original | Mitigated | Acceptable? |
|---|---|---|---|
| R-01 | High | Medium | Yes — with adversarial probing on documented cadence |
| R-02 | Medium | Low | Yes |
| R-03 | High | Medium | Yes — conditional on free-text scrubbing performance verified by audit |
| R-04 | High | Medium | Yes — residual is structural to LLM training; disclosure + onboarding callout do load-bearing work |
| R-05 | Medium | Low | Yes — provided lineage manifest is built |
| R-06 | Medium | Low | Yes — provided fairness suite is operating with documented thresholds |
| R-07 | Low | Low | Yes |
| R-08 | Medium | Low | Yes |
| R-09 | Low | Low | Yes |
| R-10 | Medium | Low–Medium | Yes — depends on scrubbing performance |
| R-11 | Medium | Low | Yes |
| R-12 | Low | Low | Yes |
| R-13 | Low | Low | Yes |
| R-14 | Medium | Low | Yes |

**Pre-mitigation profile** includes three High risks (R-01, R-03, R-04). **Post-mitigation profile** has no High or Critical risks remaining. Threshold per Template §7.3 (Medium or lower) is met.

### 7.3 Operational validity gate

The residual-risk acceptability in §7.2 **assumes the §7.1 "C"-status mitigations become operational before scaled training begins.** Scaled training on user data is not authorized under this DPIA until:

1. Free-text scrubbing pipeline (R-03, R-10) is implemented and audit-validated
2. Sensitive-category two-class ingest gate (R-03) is implemented
3. Training dataset lineage manifest (R-05) is implemented
4. Memorization mitigation suite (R-01) — deduplication, sensitive-content filter, adversarial probing — is implemented with a documented probing cadence
5. Fairness evaluation suite (R-06) is implemented with documented release threshold criteria
6. Account-settings opt-out toggle (R-04) is live and timestamped-logged
7. ML processor selection (R-07, R-11) is concluded with SCC-compatible DPA executed

Until those are in place, evaluation-only and synthetic-only work may proceed; training on user data at scale may not. A pre-flight checklist confirming each item must be signed off by the Privacy Lead and Engineering Lead before the first scaled training run.

---

## Step 8: Outcome and Sign-Off

### 8.1 Conclusion

- [ ] Proceed
- [X] **Conditional Proceed** — PA-15 may proceed subject to the operational validity gate in §7.3. Once those conditions are met, residual risks fall within the acceptable threshold (Medium or lower across the register).
- [ ] Redesign Required
- [ ] Prior Consultation Required
- [ ] Do Not Proceed

### 8.2 Conditions and action items

| Action | Owner | Deadline | Status |
|---|---|---|---|
| Counsel review of LIA + this DPIA | Privacy Lead → Counsel | Before scaled training | Pending |
| Engineering build: free-text scrubbing pipeline | Engineering | Before scaled training | Not started |
| Engineering build: two-class sensitive-category ingest gate | Engineering | Before scaled training | Not started |
| Engineering build: training data lineage manifest | Engineering | Before scaled training | Not started |
| Engineering build: memorization mitigation suite + adversarial probing | Engineering | Before scaled training | Not started |
| Engineering build: fairness evaluation suite + threshold criteria | Engineering + Privacy Lead | Before first model generation release | Not started |
| Product build: account-settings opt-out toggle with logging | Product + Engineering | Before scaled training | Not started |
| Product build: in-product onboarding callout on AI training role | Product | Before scaled training | Not started |
| ML processor selection + DPA execution | Privacy Lead + Engineering | Before scaled training | Not started |
| DPO appointment decision | Privacy Lead → Executive | Before EU/UK launch | Open |
| Pre-flight checklist sign-off for first scaled training run | Privacy Lead + Engineering Lead | At pre-flight | Not yet relevant |

### 8.3 Sign-off

| Role | Name | Date | Signature |
|---|---|---|---|
| Privacy Lead | | | |
| DPO (where appointed) | | | |
| Engineering Lead | | | |
| Executive Sponsor | | | |

### 8.4 Review schedule

| Trigger | Next review |
|---|---|
| Annual | May 2027 |
| On material change (new data category, new training objective, new processor, new transfer mechanism) | As needed |
| On regulatory development (new EDPB AI training guidance, EU AI Act implementing acts, US state regulation) | As needed |
| On security incident affecting the training data store | Within 30 days |
| Before first scaled training run | Mandatory pre-flight review confirming §7.3 conditions met |

---

## 9. Cross-Spec Touchpoints

| Document | Relationship |
|---|---|
| `AIDSTATION_LIA_PA15` | Companion. Legal basis; this DPIA assesses risk and mitigation. Read together. |
| `AIDSTATION_RoPA` PA-15 | Definitive description of the processing activity; source of data inventory and retention. |
| `AIDSTATION_Privacy_Policy` §4 / §7 / §9 | Disclosure and rights. §7 "AI Models and Derivatives" underpins R-04. |
| `AIDSTATION_Terms_and_Conditions` §8.2 | User-content license enabling training use. Necessity test depends on this. |
| `AIDSTATION_Acceptable_Use_Policy` §4 | Prohibits user-side training data manipulation — supports R-12 mitigation. |
| `AIDSTATION_DPIA_Template` | Parent template; Appendix A item 4 lists this DPIA as required. |
| `AIDSTATION_AI_Safety_Logging_Decision` | Safety-report content excluded from PA-15 by carve-out; reinforced here. |
| `AIDSTATION_DPA_Template` Annex 2 (TOMs) | Source of technical and organizational measures referenced by R-08, R-11, R-14. |
| `AIDSTATION_Breach_Response_Playbook` | Applies if training data store is breached; includes algorithmic-disgorgement scenario. |
| `AI_System_Prompt_Restrictions` §3.1 / §3.2 | Category list reused for R-03 free-text scrubbing classifier. |

---

## 10. Gut Check

### 10.1 Risks

- **The whole DPIA is operationally weak until the §7.3 mitigations land.** Conditional Proceed with an explicit gate is the right shape, but it depends on operational discipline at the moment of scaling. If shipping pressure builds, the gate may quietly stretch. The pre-flight checklist sign-off in §8.2 is the mechanical defense; treat it as binding, not advisory.
- **R-01 memorization severity may be understated.** Rated High pre-mitigation, Medium post-mitigation. A parsed coaching note that captures a free-text reconstructable health context (e.g., "user mentioned recent surgery for X") leaked verbatim in a future output could move severity to Severe for the individual. Adversarial probing schedule must be aggressive enough to find this before it surfaces in production.
- **R-06 fairness evaluation is the most under-specified mitigation.** "Fairness suite per generation" is committed without a methodology. EU AI Act and emerging guidance will tighten the bar; methodology should be drafted before first scaled training, not after.
- **R-04 disclosure-mediated mitigation is fragile.** A future regulator or court could find that a reasonable user does not actually understand "trained models continue to operate after deletion," and order more aggressive controls. The plain-language onboarding callout (R-04 mitigation #3) is the best defense; do not let it slip in product priorities.
- **R-12 purpose creep is rated Low but moves fast.** Once training datasets exist, internal pressure to use them for other purposes (research publication, partnership case studies, marketing) will exist. Bind the purpose now while it is easy.

### 10.2 What might be missing

- **A specific de-identification methodology.** Mitigations reference "NIST/ISO de-identification frameworks" but no chosen approach (k-anonymity parameters, differential privacy parameters, redaction-only with manual review). Engineering needs a specific spec before R-02 mitigation can be claimed implemented.
- **A formal training data lineage schema.** The manifest is committed; the data model is not specified. Should be drafted as a separate engineering spec before training scales.
- **RAG vs fine-tuning vs evaluation distinction.** This DPIA treats them together; the mitigations are mostly the same, but RAG can offer per-record removal in ways fine-tuning cannot. If opt-out is to be granular at all, RAG removal should be honored immediately while fine-tuning removal defers to the next model generation. Worth a dedicated subsection in DPIA.
- **EU AI Act obligations.** This DPIA is structured for GDPR. The EU AI Act adds obligations for AI systems training: transparency, risk management, post-market monitoring. Some PA-15 work may fall under the Act. Should be covered in a parallel assessment or in DPIA once Act implementing rules stabilize.
- **A definition of "material change" for §8.4 trigger.** Step 8.4 names "material change" as a re-review trigger but does not define what counts. EDPB Opinion 28/2024 and successors are obviously material; new data categories, new processors, and major shifts in training objective should also qualify explicitly.

### 10.3 Best argument against this DPIA's outcome

A persuasive counter-position: **Conditional Proceed is too permissive** for a processing activity with three High pre-mitigation risks. Alternative outcomes:

- **Do Not Proceed** until all §7.3 conditions are operational — move the operational validity gate from a §7.3 caveat to a Step 8.1 hard block. Same end state in practice, more conservative in writing. Arguably the right framing given that the safeguards are *necessary* for the LIA balancing test to come out the way it does.
- **Prior Consultation Required** under GDPR Art. 36 if R-01, R-03, or R-04 are deemed High residual rather than Medium residual. The residual scoring is the author's judgment and could be challenged.

The defense for Conditional Proceed:

- The mitigation set is comprehensive and substantive, not nominal
- The operational validity gate is explicit and binding via §8.2 pre-flight sign-off, not soft
- The §8.2 action items put accountability on specific owners with deadlines
- Counsel review is the cross-check; a stricter conclusion is a counsel-directed revision, not a problem with the document

**The conclusion stands as a draft for counsel review.** A revision to Do Not Proceed (treating §7.3 as a Step 8.1 block) or to Prior Consultation Required is a meaningful change to project sequencing and is well within the kind of revision counsel may direct.

---

## Change Log

| Version | Date | Changes | Author |
|---|---|---|---|
| v1 | May 19, 2026 | Initial DPIA for PA-15. Eight-step assessment executed. Outcome: Conditional Proceed subject to §7.3 operational validity gate. Pre-mitigation High risks (R-01 memorization, R-03 sensitive-data crossover, R-04 post-opt-out continuation) all reduced to Medium or Low post-mitigation. Companion to LIA v1. Draft for counsel review. | Privacy Lead |
| v2 | May 19, 2026 | Track A consistency-pass alignment with LIA v2. Header status bumped + supersedes reference added. Companion-doc paths updated (LIA v1→v2, RoPA v2→v3, PP v2→v3). New jurisdictional scope / single-global-rule paragraph in §0 status block, mirroring LIA v2 §0.1 (D-109). §4.1 lawful basis cross-references LIA v2 §4.8 EDPB Opinion 28/2024 mapping (D-112). §4.4 rights table Restriction and Objection rows expanded with explicit default-opt-in-for-new-users statement per LIA v2 §8.1 (D-111). §9 Cross-Spec Touchpoints table updated to companion file v2/v3 references (D-110). No risk scoring changes, no mitigation set changes, no Step 8 conclusion change. | Privacy Lead |

---

*Cross-reference cleanup (v3, 2026-05-30): inline references to companion documents were converted to unversioned logical names per Rule #12, so they no longer go stale when a companion document is revised. No substantive content changes. See `Privacy_Program_Consistency_Sweep_Report_v1.md`.*

