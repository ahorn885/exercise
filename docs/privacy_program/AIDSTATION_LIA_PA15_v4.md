# AIDSTATION Legitimate Interests Assessment — PA-15 AI Model Training and Development

**Status:** v4 — cross-reference unversioning cleanup (no substantive change since the v3 D-115 cross-reference fix)
**Owner:** Privacy Lead
**Last Updated:** May 30, 2026
**Supersedes:** `AIDSTATION_LIA_PA15_v2.md`
**Processing activity covered:** PA-15 (per the RoPA) — AI Model Training and Development
**Legal basis under assessment:** Art. 6(1)(f) UK/EU GDPR (legitimate interest) for non-special-category personal data used to train AIDSTATION's own coaching models
**Companion docs:** `AIDSTATION_RoPA` (PA-15 definition), `AIDSTATION_Privacy_Policy` §4 / §7 / §9 (disclosure and opt-out), `AIDSTATION_Terms_and_Conditions` §8.2 (license language), `AIDSTATION_DPIA_PA15` §7.3 / §8.2 (operational validity gate + pre-flight checklist), `Privacy_Program_Backlog` (engineering and operational deliverables under this LIA). Inline cross-references below cite logical names without version numbers per the project's cross-reference convention.

---

## 0. Scope and Status

This LIA evaluates whether **Article 6(1)(f) GDPR (legitimate interest)** is an appropriate legal basis for AIDSTATION to process **non-special-category personal data** of its users for the purpose of training and improving its own AI coaching models, as documented in RoPA PA-15.

**In scope.**
- The three-part test (purpose, necessity, balancing) under Art. 6(1)(f)
- The specific safeguards committed to in support of the balancing test
- The conditions under which the legitimate interest basis is valid
- The signal AIDSTATION provides to the data subject (transparency, opt-out, reasonable expectation)
- Substantive mapping against EDPB Opinion 28/2024 on AI training (§4.8)

**Out of scope.**
- Special-category data (Art. 9). Special-category data used in training is handled under **Art. 9(2)(a) explicit consent**, not under legitimate interest. PA-15 already documents this carve-out: raw sensitive data is not used in training without a separate opt-in obtained in addition to the original collection opt-in. This LIA does not extend a legitimate-interest basis to special-category processing.
- Anthropic's processing (PA-04 inference). Anthropic, as a processor, does not train on AIDSTATION user data under commercial terms; that is a contractual constraint, not a legitimate interest of AIDSTATION's.
- Other PA-15-adjacent processing activities (PA-04 runtime inference, PA-05 conversational interface) — those have separate legal bases per the RoPA.
- Whether to do the training at all. That is a business decision. This LIA presumes the activity is going forward and assesses whether legitimate interest is the appropriate basis.

### 0.1 Jurisdictional scope and the single-global-rule design

This LIA is structured under UK/EU GDPR. It does not constitute a legal-basis assessment for jurisdictions that do not recognize legitimate interest as a separate lawful basis (notably Quebec Law 25, China PIPL, and certain other consent-primary regimes).

AIDSTATION's **operational behavior is a single global rule**: opt-in by default for new users with continuous opt-out availability, paired with the §4.6 safeguards, applied to all users worldwide. This rule is calibrated to satisfy GDPR — the strictest framework in which LI is the applicable basis — and is then applied unmodified in other jurisdictions. The legal basis differs by jurisdiction; the operational behavior does not.

- The PP §4 disclosure and §9 right-to-object are global.
- The Art. 6(1)(f) legal basis applies in GDPR/UK GDPR jurisdictions.
- In other jurisdictions, the applicable basis is determined by that jurisdiction's law. Where a non-GDPR jurisdiction requires consent for specific processing categories, country-specific overlays are addressed at the country-launch readiness review for that jurisdiction; this LIA does not pre-determine those overlays.

The single-global-rule design is a deliberate operator choice: maintaining per-jurisdiction operational variants would multiply engineering complexity and increase the chance of misapplication. A single rule calibrated to the strictest applicable framework is simpler to implement, simpler to audit, and reduces the risk of a jurisdiction-routing error producing a compliance gap.

**Status of this document.** This is a draft LIA for counsel review. The structure follows ICO and EDPB-recognized guidance and explicitly maps to EDPB Opinion 28/2024. Specific judgments (particularly the balancing test conclusions) are assertions for counsel to verify and may be revised.

---

## 1. Identification of the Processing

| Item | Value |
|---|---|
| Activity | PA-15 — AI Model Training and Development |
| Controller | AIDSTATION Pro, LLC (Texas LLC), 509 Williams Avenue, Cleburne, TX 76033, US |
| Categories of data subjects | Active AIDSTATION users; users of deleted accounts whose data was incorporated into a model generation prior to deletion (per PP §7 "AI Models and Derivatives") |
| Categories of personal data (non-special) | Training plans and modifications; parsed coaching notes (not raw transcripts); activity, performance, and progression data; user feedback signals (thumbs up/down, edits, follow-through); profile context relevant to plan quality (goals, sport, experience level) |
| Categories of personal data (special — out of scope of this LIA) | Health data, biometric data, and other Art. 9 categories — only where the user has opted in to sensitive data collection AND has opted in separately to use of that data in training. These are processed under Art. 9(2)(a) explicit consent and are not within this LIA's scope. |
| Geographic scope | Worldwide users; data stored and trained in the US; SCCs for EU/UK transfers |
| Disclosure to data subjects | PP §4 (AI training disclosure), §7 (AI Models and Derivatives retention), §9 (right to object), T&C §8.2 (license including AI training rights), D-94 in-product onboarding callout (Privacy Program Backlog) |

---

## 2. Purpose Test

> Is there a legitimate interest behind the processing?

### 2.1 The interest

AIDSTATION's legitimate interest is to **develop, evaluate, and improve coaching models that are differentiated for endurance and multi-sport athletes underserved by general-purpose AI coaching tools**. This interest has three components:

1. **Product quality.** General-purpose foundation models (used at runtime via PA-04) do not have specialized depth in the AIDSTATION target disciplines — ultramarathons, skimo, modern pentathlon, Ironman triathlon, swimrun, marathon paddle sports, multi-sport, and adventure racing. AIDSTATION's coaching outputs are improved by training on AIDSTATION-generated coaching data, athlete feedback signals, and discipline-specific plan structures.
2. **Pipeline reliability.** AIDSTATION operates a multi-layer LLM pipeline (Layers 0–5) with specific structured outputs at each layer. Improving the reliability of structured outputs — validator pass rates, periodization correctness, refusal accuracy — requires evaluation datasets and, where used, fine-tuned models trained on AIDSTATION-internal data. This is not achievable using third-party data alone.
3. **Business model viability.** AIDSTATION's positioning depends on coaching quality that compounds with use. Without the ability to train on user-generated coaching data and feedback, AIDSTATION cannot improve its offering beyond the general-purpose tier already accessible to athletes without the service.

These are commercial interests, not strictly necessary for contract performance (Art. 6(1)(b)). They are nonetheless legitimate: they correspond to recognized categories of legitimate interest under ICO and EDPB guidance — improving products and services, ensuring product reliability, and developing analytics for direct business benefit.

### 2.2 Is the interest specific and real?

Yes.

- **Specific.** The interest is constrained to model development for the AIDSTATION coaching product; it is not generalized data accumulation. The data is processed for clearly enumerated downstream uses (prompt tuning, RAG index construction, fine-tuned variants where applicable, evaluation datasets) and not for resale, ad targeting, profiling, or other secondary purposes.
- **Real.** The processing is necessary to deliver the product capability that distinguishes AIDSTATION from a baseline LLM. Without the ability to learn from athlete plans and feedback, coaching outputs stagnate at the foundation-model baseline; the product loses differentiation. This is not a speculative or future-tense interest; it is the operational basis of product development.

### 2.3 Is the interest legal and ethical?

Yes.

- **Legal.** Training proprietary AI models on user data is a recognized commercial activity under EU, UK, and US law, subject to disclosure, opt-out, and special-category restrictions, all of which are addressed in PA-15's documented safeguards.
- **Ethical.** The training does not produce decisions about individuals adverse to them (PA-15 is preparatory; PA-04 is the inference activity). Outputs are intended to benefit the data subjects whose data is used (better future coaching plans) and the population of users at large.

### 2.4 Who benefits

- **AIDSTATION**: improved product, improved retention, business viability
- **Existing users**: improved coaching outputs over time as models improve
- **New users**: benefit from improvements derived from earlier cohorts' data
- **The wider category of endurance athletes**: indirect benefit through proof-of-concept of AI coaching that handles extreme endurance disciplines

**No third party with a competing interest exists.** Anthropic does not train on AIDSTATION user data (contractual constraint). No data is sold or shared for advertising. There is no "data broker" downstream of PA-15.

### 2.5 Purpose test — outcome

**Pass.** AIDSTATION has a specific, real, legal, and ethical legitimate interest in training its own coaching models.

---

## 3. Necessity Test

> Is the processing necessary to achieve that interest? Could the interest be achieved by less data, by less intrusive processing, or by a different lawful basis?

### 3.1 Is training on user data necessary?

The legitimate interest is to improve AIDSTATION's own coaching models. The relevant question: can that be achieved without using AIDSTATION user data?

| Alternative | Sufficient? | Why / Why not |
|---|---|---|
| Use only public datasets | No | Public training datasets do not contain AIDSTATION-format coaching plans, AIDSTATION-format athlete profiles, or AIDSTATION-format pipeline outputs. They cannot teach a model the structural and content patterns the pipeline depends on. |
| Use synthetic data only | Partially, not sufficient | Synthetic data is useful for evaluation augmentation and as a complement, but real-user feedback signals (what plans athletes actually completed, what they edited, what they thumbed down) cannot be synthesized. The high-value training signal is grounded in real athlete behavior. |
| Buy or license third-party endurance training data | No realistic source | No commercial dataset exists at the intersection of: AR / ultra / skimo / modern pentathlon disciplines, AIDSTATION's structured plan format, and athlete feedback signals. Licensing aggregated competitor data is not commercially or contractually available. |
| Use a third-party LLM without fine-tuning | Already happening (PA-04) but insufficient alone | The foundation model serves at runtime via PA-04. The legitimate interest at issue here is improving outputs beyond what the foundation model alone delivers. This requires training on AIDSTATION data. |
| Train only on aggregated statistics, not personal data | Insufficient for many training objectives | Aggregated statistics support some product improvements (e.g., distribution-aware defaults) but do not provide the sequence-level patterns needed for fine-tuning or RAG index construction. |

**Conclusion: yes, processing of personal data is necessary.** No realistic alternative achieves the interest.

### 3.2 Is the minimum amount of data processed?

Yes, by design.

- **Excluded by default.** Raw conversation transcripts are not retained at all (per PP §7). The training pipeline cannot use what is not stored.
- **Excluded by category.** Special-category data is not used in training without the user's separate opt-in obtained in addition to the original collection opt-in. The default is exclusion.
- **Excluded by purpose.** Data not relevant to plan quality (e.g., billing metadata, support ticket logs) is not used in training. PA-15's data inventory specifies the categories used.
- **De-identified or aggregated where possible.** Per the PA-15 safeguard, sensitive data used in training (where consent is given) is de-identified or aggregated. Where non-sensitive training data can be pseudonymized without quality loss, it is.

### 3.3 Is a different lawful basis available?

Considered alternatives:

| Alternative basis | Suitable? | Why / Why not |
|---|---|---|
| Art. 6(1)(a) consent | Suitable but not optimal | See discussion below — consent and LI are not interchangeable, and AIDSTATION's preference for LI is partly controller-side. |
| Art. 6(1)(b) contract performance | Not suitable | Training is not necessary to perform the contract with the individual user. The user receives the service via PA-04 (inference) regardless of whether their data is used in PA-15 (training). Conflating the two would overreach the contract-performance basis. |
| Art. 6(1)(c) legal obligation | Not applicable | No legal obligation requires training proprietary AI coaching models. |
| Art. 6(1)(d) vital interests | Not applicable | Not a life-or-death scenario. |
| Art. 6(1)(e) public interest | Not applicable | AIDSTATION is a private commercial entity; no public interest task. |

**Conclusion: Art. 6(1)(f) legitimate interest is the most appropriate basis for non-special-category training data.**

The decision to rely on Art. 6(1)(f) rather than Art. 6(1)(a) consent is, in part, a controller-side preference, and this LIA names it as such rather than presenting the choice as primarily data-subject benefit. The relevant controller-side considerations are:

- **Algorithmic-disgorgement transparency.** Consent-based training carries an implicit promise of withdrawal that LI does not. A user who withdraws consent reasonably expects their contributions to be removed; in practice, contributions already incorporated into a deployed model generation cannot be selectively removed without retraining the entire model. The PP §7 disclosure of this reality fits more cleanly under LI ("right to object stops new use; deployed models continue") than under consent ("withdrawal ends processing, except for the model weights, which are retained"). LI matches the operational reality without dressing it.
- **Operational continuity.** LI permits the training pipeline to operate on existing user data without re-collecting consent at each model generation. This is a controller-side benefit. The alternative — consent obtained anew for each generation — is operationally costly and produces user-experience friction without delivering meaningful additional protection (because the disclosure and right-to-object are already in place).
- **Compatibility with the single-global-rule design (§0.1).** A consent-based primary basis would have to be implemented as an opt-in flow that varies in salience across jurisdictions and could in some jurisdictions be rendered ineffective (e.g., consent fatigue, dark-pattern concerns). The LI basis with opt-out is a stable global rule across the jurisdictions where it applies, and degrades cleanly to consent-only in jurisdictions that do not recognize LI.

These are honest controller-side considerations and do not by themselves answer whether LI is appropriate. That depends on the balancing test (§4) and the safeguards (§4.6). The honest framing is: AIDSTATION prefers LI over consent for the reasons above; the LI basis is appropriate if and only if the balancing test passes and the safeguards are operational.

Consent (Art. 6(1)(a)) is retained as the basis for special-category data per Art. 9(2)(a). The opt-in mechanism is operationally maintained for that data class regardless of the LI basis for non-sensitive data.

### 3.4 Necessity test — outcome

**Pass.** Processing user personal data for AIDSTATION model training is necessary to achieve the legitimate interest; the minimum amount of data is processed; and Art. 6(1)(f) is the most appropriate legal basis among those available, with the controller-side considerations named honestly.

---

## 4. Balancing Test

> Do the interests, rights, and freedoms of data subjects override the legitimate interest?

This is the substantive test. The purpose and necessity tests establish that AIDSTATION may rely on legitimate interest; the balancing test determines whether, in practice, the data subjects' rights and reasonable expectations override that reliance.

### 4.1 Nature of the data subjects' interests

Users have interests in:
- Privacy of their training and health data
- Control over secondary uses of their data
- Not being subject to opaque automated decision-making
- Not having their data used to train models that may regurgitate it
- Being able to leave the service and have their data cease being processed
- Being able to object to specific uses (notably, training)

### 4.2 Nature of the personal data

| Data category | Sensitivity assessment |
|---|---|
| Training plans and modifications | Low. Coaching content; not by itself sensitive. |
| Parsed coaching notes (not raw transcripts) | Low–medium. Derived from conversations; structured outputs only; sensitive content already filtered upstream by AI System Prompt Restrictions §3.1/§3.2 (hard refuse / soft redirect). |
| Activity, performance, and progression data | Low–medium. Health-adjacent — heart rate, training load, distances — but largely behavioral / performance data rather than diagnostic. |
| User feedback signals | Low. Thumbs up/down, edits, follow-through — high-value training signal, low sensitivity. |
| Profile context (goals, sport, experience level) | Low. Self-declared context, not sensitive. |
| Special-category data (if opted in) | **Out of scope of this LIA.** Special-category data uses Art. 9(2)(a) consent. |

Overall sensitivity of in-scope data: **low to low–medium**. The most sensitive items (raw conversational content, special-category data, raw biometrics without context) are excluded by PA-15's data inventory or covered by separate consent.

### 4.3 Reasonable expectations of the data subject

Do AIDSTATION users reasonably expect their data to be used to train AIDSTATION's own coaching models?

The reasonable-expectation inquiry asks what a typical user — one who understands the category of service they are using but has not necessarily read every disclosure document — would directionally expect about how the service handles their data. Disclosure quality is relevant to this inquiry but not constitutive of it: a disclosure can support an expectation that exists for other reasons, but a disclosure that goes unread does not by itself create reasonable expectation.

#### 4.3.1 Category norms (primary support)

A user signing up for a personalized AI coaching service in 2026 enters a market in which:
- Mainstream personalized AI services (coaching, tutoring, writing assistance, conversational AI) widely train on user interactions to improve outputs. This is the dominant operating pattern across the AI services category.
- "Personalization" in AI services is broadly understood to involve learning from user inputs over time. The technical distinction between runtime adaptation (PA-04) and training-pool inclusion (PA-15) is not naturally salient to users, but the directional pattern — the service learns from its users — is part of mainstream public understanding of AI services.
- Public discourse, regulatory attention (including EDPB Opinion 28/2024), platform privacy notices, and reporting on AI training have collectively raised baseline user awareness that AI services train on user data, independent of whether individual users have read individual privacy policies.

A reasonable user joining a personalized AI coaching service in this environment directionally expects that the service will use their interactions to improve future outputs. The expectation is supported by category norms independent of any specific AIDSTATION disclosure.

#### 4.3.2 Disclosure quality (supporting condition)

Disclosure is the supporting condition that confirms, rather than constitutes, the expectation:

- PP §4 explicitly names AIDSTATION-controlled training as a processing purpose, distinguished from Anthropic's no-training posture.
- PP §9 includes a specific mention of AI training opt-out.
- The front-summary of PP surfaces the AI providers note.
- T&C §8.2 includes the user-content license for AI training rights.
- The D-94 in-product onboarding callout (Privacy Program Backlog) places the training-role acknowledgment at the point of signup, reducing the gap between baseline category expectation and individual-user awareness.

A user who reads any of these confirms — rather than learns for the first time — the expectation already supported by category norms.

#### 4.3.3 Counter-arguments considered

- Some users may understand "personalization" as runtime-only adaptation and may not include training-pool inclusion in their mental model. The D-94 onboarding callout is the specific safeguard against this gap.
- Health-adjacent data may carry stronger expectations of confidentiality than general behavioral data. The data in scope of this LIA (§4.2) excludes raw sensitive data, raw conversation transcripts, and special-category data unless separately consented; the training-pool data is health-adjacent only at the low-to-low-medium sensitivity level.
- Users whose mental model is anchored to older fitness/training apps (which generally did not train AI models) may have a weaker baseline expectation. The category norms argument relies on AI services generally, not on fitness apps specifically; for users anchored to the older category, the disclosure-quality argument carries more of the load.

#### 4.3.4 Conclusion

Reasonable expectation is supported primarily by category norms (the pattern of personalized AI services in 2026) and confirmed by AIDSTATION-specific disclosure. The disclosure is substantive and accessible enough to support a user who has read it; the category norms support directional expectation for users who have not.

The reasonable-expectation argument is supported but not unconditional. It is among the more sensitive components of the balancing test (§4.7) and depends on category norms that may evolve. The §7 annual review specifically re-assesses whether category norms have shifted in a way that weakens this argument; the D-94 onboarding callout is the engineering safeguard that makes the argument less dependent on outside-the-product disclosure documents.

### 4.4 Impact of the processing

| Dimension | Impact assessment |
|---|---|
| Direct impact on the individual | Minimal. PA-15 is preparatory; the model trained is then used (via PA-04) on behalf of all users including the data subject. No adverse decision is made about the individual from PA-15 itself. |
| Indirect impact via outputs | Trained models could in principle produce outputs that affect users adversely (bad coaching advice). This is the risk addressed by PA-04 controls (System Prompt Restrictions, validators) and the Health Safety framework — not by PA-15 specifically. |
| Memorization risk | LLMs can in some cases memorize training inputs and surface them in later outputs. The risk is mitigated by: (a) using parsed coaching notes rather than raw conversation transcripts; (b) standard memorization mitigations in training (deduplication, data filtering, periodic adversarial testing per Batch 5 §7.2); (c) the output validator at PA-04 inference time. The risk is not zero. |
| Algorithmic disgorgement | FTC has on occasion ordered destruction of models trained on improperly collected data. Mitigation: conservative scope (this LIA), opt-out availability, training data lineage tracking. The risk is bounded by the integrity of consent/opt-out controls. |
| Profiling / automated decision-making | PA-15 itself does not perform profiling or ADM. PA-04 may; PA-15 is preparatory only. |
| Discrimination | Trained models could produce biased outputs based on training data bias. Mitigation: evaluation datasets specifically include fairness testing across athlete demographics (sport, experience level, sex) — committed as part of PA-15 safeguards. Specific evaluation methodology is a separate engineering deliverable (D-92). |
| Children | AIDSTATION enforces a 16+ minimum age (PP §11, T&C §1). Training data from underage users should not occur in normal operation; if discovered, the data is removed from training datasets and the relevant account is closed per the age verification process. |
| Identity theft / fraud risk | Low. Training outputs do not directly produce identifying credentials, financial information, or fraud-relevant artifacts. |

Overall impact assessment: **low**, with the memorization risk being the most material residual.

### 4.5 Power asymmetry

The data-subject relationship to AIDSTATION presents two distinct asymmetries that are assessed together.

#### 4.5.1 Runtime relationship (low)

- The user is a paying customer (or trial user) of AIDSTATION. The relationship is voluntary and the user can leave at any time.
- The user can object to AI training specifically via account settings (PP §9 commitment); this is more granular than account-wide opt-out.
- The user can delete their account, which removes future use of their data in training.
- No employment, healthcare, or housing relationship; no captive-audience dynamic.

At the runtime level, power asymmetry is **low**. The user has multiple substantive controls available.

#### 4.5.2 Irreversibility of past contributions (substantive, disclosed)

A user who has been in the training pool — under default opt-in or by virtue of having previously been a user before objecting — has contributed to model generations that are deployed and operational at the time the user departs the service or exercises the right to object. The user can stop **new** use of their data in future training; the user **cannot** remove contributions already incorporated into deployed model weights. This is a substantive irreversibility that operates separately from the runtime relationship and that survives the user's departure.

This irreversibility is:

- **Disclosed.** PP §7 ("AI Models and Derivatives") explicitly names that already-produced models continue to operate after a user opts out or deletes their account. The disclosure is plain-language and surfaces at signup-relevant locations, not buried.
- **Not unique to LI as the basis.** A consent-with-withdrawal framework faces the same operational reality: contributions already in deployed model weights cannot be selectively removed. The LI basis is more transparent about this reality than a consent-with-withdrawal framework would be (per §3.3).
- **Bounded by safeguards.** Training data lineage tracking (§4.6 safeguard #6) supports algorithmic-disgorgement scenarios at the model-generation level. A future regeneration can exclude the departed user's contributions; the past generation cannot be selectively edited.

The irreversibility is a real cost to the data subject. It is disclosed, bounded by safeguards, and structurally identical to the operational reality of any AI training framework — not a unique feature of the LI basis. It is treated as an honest cost rather than concealed.

#### 4.5.3 Combined assessment

Runtime power asymmetry is low. Irreversibility of past contributions is substantive but disclosed and operationally bounded. The balancing test (§4.7) accounts for both. The disclosed irreversibility does not by itself override the legitimate interest; it does sharpen the salience of the D-94 onboarding callout (so the user encounters the irreversibility at the point of signup, not only in the back of the PP).

### 4.6 Safeguards committed to (and binding via this LIA)

These safeguards must be in place for the legitimate interest basis to remain valid:

1. **Opt-out.** Account-settings-level toggle to object to AI training. Opt-out applies prospectively and to ongoing training-data inclusion. Disclosed in PP §9.
2. **Sensitive-category gating.** Special-category data is not used in training without separate, additional opt-in. Documented in PA-15 and PP §4.
3. **De-identification / aggregation.** Where used, sensitive data is de-identified or aggregated before training. Raw sensitive data is not used.
4. **Raw transcript exclusion.** Raw conversation transcripts are not retained at all and therefore not available for training. Only parsed coaching notes are used.
5. **Memorization mitigations.** Training pipeline applies standard memorization-prevention measures (deduplication, sensitive content filters, training data lineage tracking). Periodic adversarial testing for memorization risk per Batch 5 §7.2 and Privacy Program Backlog D-91.
6. **Training data lineage tracking.** Every training dataset version is traceable to the user data versions that contributed to it. Supports algorithmic disgorgement scenarios. Engineering deliverable D-89.
7. **Limited recipients.** Training data is accessible only to AIDSTATION ML and engineering personnel with role-based access, logged. The ML training infrastructure provider (when selected, per D-95) is bound under DPA with no-training-on-our-data and no-derivative-use restrictions.
8. **Retention boundary.** Training datasets are retained for the lifetime of the model generation that uses them plus a reasonable reproducibility window (per PA-15: typically 24 months after model generation retirement). Not indefinite.
9. **Transparency.** PP §4 explicitly distinguishes AIDSTATION's training role from Anthropic's no-training role. Front-summary clarifies. AUP §4 prohibits user-side manipulation of training data. D-94 onboarding callout supports salience.
10. **Right to object honored.** PP §9 commits to honoring the right to object; opt-out stops new training use.
11. **No advertising, no sale, no share for ads.** Decision #9 in the original lock-list. Reinforced here.
12. **Children protection.** 16+ minimum age; underage data is removed if discovered.

If any of these safeguards lapses, the legitimate interest basis must be re-evaluated.

### 4.7 Balancing — outcome

The data is low-to-low-medium sensitivity. The processing is preparatory (no direct adverse decision). Reasonable expectation is supported by category norms and confirmed by direct disclosure (§4.3). Power asymmetry at the runtime level is low; irreversibility of past contributions is substantive but disclosed and operationally bounded (§4.5). Impact is low overall, with memorization as the residual risk addressed by specific safeguards (§4.4, §4.6). Children are excluded by age policy.

The interests, rights, and freedoms of the data subjects do **not** override the legitimate interest, **provided** the §4.6 safeguards are in place and operationally maintained.

### 4.8 Mapping against EDPB Opinion 28/2024 on AI training

EDPB Opinion 28/2024 (adopted December 17, 2024) addresses the use of personal data in AI model development and deployment under Art. 6(1)(f) legitimate interest. The Opinion structures its analysis around the standard three-stage LI test, with specific guidance on AI training contexts. This subsection maps PA-15 against the Opinion's framework.

#### 4.8.1 Stage 1 — Legitimate interest

The Opinion requires that the interest be lawful, specific, real, present, and not speculative. AIDSTATION's interest in training its own coaching models (§2.1) meets these criteria:
- **Lawful.** Training proprietary AI coaching models is not prohibited and is subject to documented safeguards (§4.6).
- **Specific.** The interest is constrained to model development for the AIDSTATION coaching product, with enumerated downstream uses (§2.2).
- **Real and present.** Model training is the active basis of product development, not speculative (§2.2).

#### 4.8.2 Stage 2 — Necessity

The Opinion requires that processing be necessary to achieve the interest, with no less intrusive alternative reasonably available. §3 establishes:
- Public datasets, synthetic data, third-party licensed datasets, and aggregated statistics each fail to achieve the interest (§3.1).
- Minimum-data principles are applied: raw transcripts excluded, special-category data excluded by default, purpose-relevant data only (§3.2).
- Art. 6(1)(f) is the appropriate basis among those available, with controller-side considerations named honestly (§3.3).

#### 4.8.3 Stage 3 — Balancing and Opinion-aligned mitigations

The Opinion gives specific attention to mitigations that affect the balancing test in AI training contexts. The mitigations present in PA-15 map as follows:

| Opinion-named mitigation | PA-15 safeguard |
|---|---|
| Opt-out mechanism, accessible and unconditional | §4.6 #1, §4.6 #10 |
| Transparency at the point of collection | §4.6 #9 (PP §4, AUP §4), supported by D-94 onboarding callout |
| Exclusion of special-category data from default training | §4.6 #2, §4.6 #3 |
| Exclusion of children's data | §4.6 #12 |
| Memorization mitigations | §4.6 #5 (engineering deliverable D-91) |
| Training data lineage tracking | §4.6 #6 (engineering deliverable D-89) |
| Limited recipients and processor controls | §4.6 #7 (engineering deliverable D-95) |
| Retention boundary | §4.6 #8 |
| Prohibition on data sale / share for advertising | §4.6 #11 |

#### 4.8.4 Opinion-named AI-training-specific risks, addressed in PA-15

- **Memorization and regurgitation.** Addressed by safeguard #5 and engineering deliverable D-91. Acknowledged in §4.4 and Risk LIA-2 as the most material residual.
- **Anonymization difficulty for trained models.** PA-15 does not claim that trained models are anonymized; it claims that training inputs are de-identified or aggregated where possible (§4.6 #3) and that lineage is tracked (§4.6 #6). The Opinion's concern that models may retain identifiable information in weights is addressed by safeguards #5 and #6 rather than by an anonymization claim.
- **Cross-controller flows and processor obligations.** Anthropic does not train on AIDSTATION data (contractual constraint, §2.4). The ML training infrastructure provider (to be selected per D-95) is bound under DPA with no-training-on-our-data and no-derivative-use restrictions (§4.6 #7).
- **Algorithmic disgorgement scenarios.** Addressed by lineage tracking (§4.6 #6) and the operational discipline in §7 annual review.

#### 4.8.5 Operational validity per the Opinion

The Opinion emphasizes that documented safeguards are insufficient if not operationally in place. PA-15's safeguards are committed in writing under this LIA but several depend on engineering deliverables that are not yet built (Privacy Program Backlog D-87 through D-95). The operational-validity gate in §5 of this LIA mirrors the Opinion's emphasis: Art. 6(1)(f) reliance is not authorized until the safeguards are operationally in place, as verified by the pre-flight checklist (D-96).

#### 4.8.6 Conclusion of mapping

PA-15's LI assessment, with the §4.6 safeguards, is consistent with EDPB Opinion 28/2024's framework. The Opinion-named residual risks (memorization, anonymization difficulty in models, processor obligations, algorithmic disgorgement) are each addressed by a specific safeguard. The operational-validity gate (§5) is the structural defense ensuring the safeguards exist in practice, not only on paper.

---

## 5. Overall Outcome and Operational-Validity Gate

**Article 6(1)(f) legitimate interest is a valid legal basis for PA-15 (AI Model Training and Development), limited to non-special-category personal data, subject to the §4.6 safeguards.**

Special-category data continues to require Art. 9(2)(a) explicit consent obtained separately from the collection opt-in, per PA-15's documented restriction. This LIA does not extend to special-category processing.

### 5.1 Operational-validity gate

**Documentation of safeguards in this LIA does not by itself authorize reliance on Art. 6(1)(f).** Reliance is authorized only when **all** of the following conditions are met:

- All §4.6 safeguards are **operationally in place**, as verified by the pre-flight checklist deliverable (Privacy Program Backlog D-96, referenced in `AIDSTATION_DPIA_PA15` §8.2).
- Disclosure (PP §4 / §7 / §9, T&C §8.2) is live to users.
- Opt-out is functional and honored end-to-end (toggle present in account settings, change logged, ingest pipeline respects current state).
- The D-94 in-product onboarding callout is implemented, to support the §4.3 reasonable-expectation argument.
- No material change has occurred in the categories of data, the purposes of processing, or the population of data subjects since this LIA's last review.

If any of these conditions is not met, reliance on Art. 6(1)(f) is **not** authorized, regardless of what this LIA says on paper. This gate parallels the gate in `AIDSTATION_DPIA_PA15` §7.3 and §8.2: the two documents share the structural commitment that pre-launch documentation is not a substitute for pre-launch operational readiness.

### 5.2 Re-assessment trigger

If any condition above changes, this LIA must be re-evaluated before continued reliance on Art. 6(1)(f). The §7 annual review is the standing re-assessment cadence; material changes between annual reviews trigger an ad-hoc re-assessment.

---

## 6. Risks Identified, with Disposition

| ID | Risk | Severity | Disposition |
|---|---|---|---|
| LIA-1 | User has not actually read PP / T&C and is surprised by the training disclosure | Medium | §4.3 reasonable-expectation argument relies primarily on category norms; D-94 in-product onboarding callout strengthens salience independent of disclosure-reading |
| LIA-2 | Memorization causes a trained model to regurgitate user-specific content | Medium | Mitigated by §4.6 #5 + adversarial testing per D-91; not zero |
| LIA-3 | Trained models continue to operate after a user has opted out; the user understands "opt-out" as full removal | Medium | Disclosed in PP §7 ("AI Models and Derivatives") — already-produced models continue. §4.5.2 makes the irreversibility a distinct asymmetry, not a parenthetical. D-94 onboarding callout makes this salient at signup. |
| LIA-4 | Algorithmic disgorgement risk if training data lineage is incomplete | Low–medium | Committed safeguard #6 addresses; engineering D-89 builds the lineage tracking |
| LIA-5 | Sensitive data inadvertently leaks into training (e.g., via free-text coaching notes that summarize a chat about a restricted topic) | Medium | Pipeline-level filter on training data ingest (D-87); defer specifics to AI Training DPIA |
| LIA-6 | Children's data ends up in training despite the 16+ age policy | Low | Age verification at signup; remediation procedure when underage account is discovered; training datasets purged of removed account contributions where lineage allows |
| LIA-7 | A jurisdiction that does not recognize legitimate interest (e.g., Quebec Law 25, China PIPL) | Low–medium | LIA is GDPR-specific (§0.1); operational behavior is global (single-global-rule design); country-specific overlays addressed at country-launch readiness review |
| LIA-8 | Material change in processing (e.g., new data categories, new training objectives) invalidates this LIA | N/A — process risk | Annual review; pre-change re-evaluation requirement built into PP-policy-change controls |
| LIA-9 | Anthropic's commercial terms change such that they begin to retain or train on AIDSTATION data | Low | Contractual constraint with audit rights; addressed in DPA Template Annexes. If breached, separate response. |
| LIA-10 | Counsel disagrees with one or more of the §4.6 safeguards being sufficient | Process risk | Resolved at counsel review; LIA may be revised |
| LIA-11 | Category norms shift away from "AI services train on user data" being expected default; §4.3 weakens | Medium | §7 annual review specifically re-assesses category norms; D-94 onboarding callout shifts load from disclosure-reading to in-product salience |
| LIA-12 | Operational-validity gate (§5.1) is treated as advisory rather than binding; reliance begins before safeguards are in place | High if mismanaged | Pre-flight checklist (D-96) is the structural defense; sign-off required from Privacy Lead + Engineering Lead before first scaled training run |

---

## 7. Review and Re-Assessment

This LIA is reviewed:

- **Annually**, by the Privacy Lead, as part of the privacy program annual review cycle
- **On material change** to: the categories of data processed in PA-15, the purposes of training, the recipients of training data, the geographic scope of users, the operation of safeguards
- **On regulatory development**, such as a new EDPB opinion, ICO guidance, or jurisdictional rule affecting AI training
- **On request from counsel**

Re-assessment uses this template structure. Each review produces a dated version (v3, v4, ...) in the privacy program file set.

### 7.1 LIA retention

This LIA, including all superseded versions in the change log, is retained for:
- The lifetime of PA-15 (the processing activity it documents), plus
- Six years after PA-15 retirement, to support regulatory inquiries, audit response, and litigation defense within the statute-of-limitations envelope typical for GDPR-related claims.

Storage: privacy program file set with version-controlled history. Superseded versions remain accessible; redactions to past versions are not performed — only addenda and version-bumps. This retention boundary applies to the LIA document itself; it does not affect retention of operational training data (governed by §4.6 #8) or retention of user account data (governed by PP §7).

---

## 8. Implementation Guidelines

These are guidelines for engineering, operations, and counsel to deliver the safeguards committed to in §4.6. They do not specify code.

### 8.1 For engineering

- **Opt-out mechanism.** Account-settings toggle: "Allow my data to improve AIDSTATION coaching models." Toggle change is logged with timestamp against the account.
- **Default state for new users: opt-in.** New users joining after the AI training feature is live are in the training pool by default, subject to the unconditional right to object via the account-settings toggle. This default is consistent with the Art. 6(1)(f) basis (which does not require opt-in) and with the single-global-rule operational posture (§0.1). The reasonable-expectation argument (§4.3) and the D-94 onboarding callout together support the salience of the default at signup. Engineering deliverable: D-93.
- **Default state for existing users at feature launch:** opt-in, with grandfathering notice. PP §4 disclosure is already live; users on the service before the feature launch receive a notification of the activation and a clear path to the opt-out toggle.
- **Why not default opt-out for new users:** considered and rejected. Defaulting new users to opt-out would functionally operate as consent for new users while the LI basis is invoked. The hybrid creates a worse defensive position than either coherent alternative (clean LI default-opt-in, or full consent under Art. 6(1)(a)). The clean LI default is operator-favorable and structurally coherent. If counsel directs a different basis (Art. 6(1)(a) consent), §8.1 is rewritten to opt-in-only and the LIA scope is narrowed.
- **Training data ingest gating.** When pulling user data into a training dataset, the ingest must check (a) account opt-out status, (b) sensitive-category opt-in for any special-category data, (c) account age status (16+), (d) deletion status (not in cooling-off, not deleted).
- **Lineage tracking.** Each training dataset version maintains a manifest of contributing user data versions (by pseudonymous ID + version timestamp). Sufficient to answer: "if user X opts out today, which training datasets include their contributions?" Engineering deliverable: D-89.
- **Sensitive-category filter on training ingest.** Pipeline-level filter excludes data flagged as special-category unless the separate training opt-in is on. Engineering deliverable: D-88.
- **Free-text scrubbing.** Free-text fields ingested into training pass through a redaction pipeline that strips named entities, PII tokens, and restricted-category terms detected by the AI System Prompt Restrictions pre-filter. Engineering deliverable: D-87.
- **Adversarial testing.** Periodic memorization probe — held-out data is probed against trained models to detect verbatim regurgitation. Schedule, methodology, and reporting cadence are a separate engineering deliverable: D-91.

### 8.2 For operations

- **Opt-out handling.** Opt-out requests via help@aidstation.pro processed within 30 days (matches DSR timeline). Opt-out is recorded against the account and applied to future training pulls.
- **Underage account discovery procedure.** When an account is identified as underage post-signup (via support contact, parental notification, or platform signal), the account is closed and any training dataset versions that include the account's contributions are flagged. Future regenerations exclude the account. Existing model weights are not retrained for this case alone (per algorithmic disgorgement considerations) unless the discovery is at scale.
- **Pre-flight checklist sign-off.** Before the first scaled training run, the pre-flight checklist (D-96) is reviewed and signed off by the Privacy Lead and the Engineering Lead. Sign-off is recorded in the privacy program file set and is required to invoke Art. 6(1)(f) reliance per §5.1.
- **Annual review.** Privacy Lead schedules and conducts the §7 annual review. Output is a written re-assessment, retained with this LIA's version history.

### 8.3 For counsel

- **Confirm balancing test.** Counsel review of §4 is the critical sign-off. Specific points to confirm: §3.3 honest framing of controller-side considerations; reasonable expectation argument (§4.3) including the category-norms-as-primary framing; irreversibility framing (§4.5.2); §4.8 EDPB Opinion 28/2024 mapping.
- **Confirm scope exclusions.** Special-category and child data exclusions are sufficient; no other categories require explicit exclusion.
- **Confirm jurisdictional sufficiency.** This LIA is structured for UK/EU GDPR (§0.1). Counsel should confirm applicability to other jurisdictions (Canada PIPEDA, Australia Privacy Act, South Africa POPIA, US state laws, Brazil LGPD, Quebec Law 25, China PIPL) — most do not require an LIA but the substantive analysis often applies. The single-global-rule design (§0.1) is intended to be acceptable globally; counsel should validate.
- **Confirm default-opt-in for new users.** The §8.1 default is a counsel-confirmable choice. The alternatives considered and rejected are stated in §8.1; if counsel directs a different position, the LIA is revised.

---

## 9. Cross-Spec Touchpoints

| Document | Relationship |
|---|---|
| `AIDSTATION_RoPA` PA-15 | PA-15 references "Legitimate Interests Assessment (LIA) documented separately" — this is that document. |
| `AIDSTATION_DPIA_PA15` | The AI Training DPIA references this LIA's safeguards and balancing-test outcome. §7.3 / §8.2 of the DPIA establish the operational-validity gate that §5.1 of this LIA mirrors. |
| `AIDSTATION_Privacy_Policy` §4 / §7 / §9 | The disclosures and rights this LIA depends on. Any future PP amendment that touches AI training language must trigger an LIA re-assessment. |
| `AIDSTATION_Terms_and_Conditions` §8.2 | The user-content license including AI training rights. This LIA's necessity test relies on the license existing. |
| `AIDSTATION_Acceptable_Use_Policy` §4 | Prohibition on user-side training data manipulation — supports safeguard #9. |
| `AIDSTATION_AI_Safety_Logging_Decision` | Captured safety-report content carries a carve-out from training use by default. The carve-out is consistent with this LIA — safety-report content is not part of PA-15's data inventory and should remain excluded. |
| `AIDSTATION_TOMs` | Technical and organizational measures referenced by safeguard #5 and #7. |
| `AIDSTATION_Breach_Response_Playbook` | If a breach involves training data, the playbook applies; specific consideration for whether breach scope includes model weights themselves (algorithmic disgorgement). |
| `Privacy_Program_Backlog_v1.md` | Engineering and operational deliverables under this LIA (D-87 through D-96) and pre-flight checklist (D-96). |

---

## 10. Gut Check

### 10.1 Risks

- **The operational-validity gate is binding only if treated as binding.** §5.1 says reliance is not authorized until safeguards are operationally in place. If a future engineer or operator proceeds before the pre-flight checklist is signed off, the LIA's defense weakens and the entire Art. 6(1)(f) reliance becomes shaky. The pre-flight checklist (D-96) is the structural defense; its sign-off discipline is load-bearing.
- **The category-norms argument for reasonable expectation depends on category norms not regressing.** §4.3 makes the case that personalized AI services in 2026 are widely understood to train on user data. If a high-profile incident, regulatory action, or shift in public discourse pushes the norm in the other direction, §4.3.4 weakens and the disclosure-quality and D-94 onboarding callout carry more load. The §7 annual review specifically tests this.
- **The irreversibility framing in §4.5.2 is honest but uncomfortable.** Naming that contributions to deployed models cannot be removed is the right framing; it is also the framing most likely to draw user attention if a counterparty audit surfaces it. The defense is that the alternative — concealing the irreversibility or stating it parenthetically — produces worse outcomes when the irreversibility is discovered.
- **EDPB Opinion 28/2024 mapping is current as of LIA drafting; the Opinion may be supplemented or interpreted in ways that require re-mapping.** §7 annual review is the standing trigger; specific Opinion guidance from EDPB or member-state DPAs may require ad-hoc re-mapping between annual reviews.
- **Single-global-rule design assumes the strictest framework (GDPR) is binding worldwide; this is a deliberate operator choice (§0.1).** If a jurisdiction with a stricter framework emerges (e.g., a future US federal AI Act, an Australian sector-specific rule), the rule may need to be re-calibrated. The country-launch readiness review is the standing mechanism.

### 10.2 What might be missing

- **A formal evaluation methodology for fairness/bias in trained outputs.** §4.4 mentions this; D-92 is the engineering deliverable. The LIA's balancing test implicitly assumes the evaluation happens; the LIA does not specify acceptance criteria.
- **A position on retention of opt-out signals after account deletion.** When a user deletes their account, their opt-out preference is also deleted. If the user later signs up again, the new account starts with a fresh default. Not necessarily a problem but worth noting; the alternative is to retain opt-out signals at the user-pseudonym level after account deletion, which is itself a retention question.
- **Cross-jurisdictional parallel assessments.** §0.1 acknowledges other jurisdictions are out of scope. The LIA does not name which jurisdictions have been formally cleared at country-launch readiness review. As markets are added, a parallel assessment register may be needed.
- **The "training" boundary is not crisp.** Fine-tuning, RAG index construction, prompt-tuning datasets, evaluation datasets — these are all "training" for purposes of this LIA. If the engineering distinguishes them in practice (e.g., evaluation data is treated differently from fine-tuning data), the LIA may need to be revised to reflect the actual operational categories.
- **A user-facing explanation of irreversibility.** §4.5.2 acknowledges the irreversibility; PP §7 discloses it. A short in-product explanation at the opt-out toggle (something like: "Turning this off stops new use of your data; data already used in current AIDSTATION models cannot be removed") would close the gap between the LIA position and the user-facing experience.

### 10.3 Best argument against this LIA's outcome

A persuasive counter-position remains available: the use of personal training and health-adjacent data to train proprietary commercial models, even with opt-out, disclosure, and the §4.6 safeguards, should require explicit opt-in consent under Art. 6(1)(a), not legitimate interest. The arguments:

- AI training on user-generated data is a contested area of EU practice. EDPB Opinion 28/2024 tightened expectations; legitimate interest is harder to rely on than it was in earlier guidance.
- Health-adjacent data, even when not strictly Art. 9 sensitive, attracts heightened user expectation of confidentiality. The "low-to-low-medium sensitivity" framing in §4.2 may understate the user's view.
- The §3.3 acknowledgment that LI is partly a controller-side preference is honest, but a regulator may read that as a candid admission that the data-subject benefits do not, on their own, justify LI over consent.
- For a small pre-launch service, the cost of an opt-in flow is low; the cost of getting the legal basis wrong post-launch is high.

The arguments that support this LIA's outcome:

- Disclosure is substantive and prominent; reasonable expectation is supported by category norms independent of disclosure (§4.3.1).
- Already-existing models continue to operate post-opt-out under both consent and legitimate-interest frameworks — the algorithmic disgorgement problem is the same regardless of basis. Legitimate interest is more honest about this (§3.3, §4.5.2).
- The safeguards in §4.6 are substantive and binding under this LIA. They are not weaker than what consent would require.
- The single-global-rule design (§0.1) is more cleanly implementable under LI with opt-out than under consent with opt-in.
- Counsel can revise this conclusion. If counsel takes the opt-in position, the LIA is rewritten and the PP/T&C are amended accordingly.

**The decision stands as a draft for counsel review.** A revision to opt-in basis is a meaningful change to the user signup flow and the privacy posture, and is well within the kind of revision this LIA expects counsel may direct. The architecture of the LIA — particularly §4.6 safeguards and §5.1 operational-validity gate — survives a basis change with minimal restructuring.

---

## 11. Approval Block

This LIA becomes binding on AIDSTATION Pro, LLC when signed by the parties below. The signing parties indicate concurrence that: the analysis is sound; the §4.6 safeguards are committed to; and the §5.1 operational-validity gate is acknowledged as the precondition for Art. 6(1)(f) reliance.

| Role | Name | Signature | Date |
|---|---|---|---|
| Privacy Lead | _________________ | _________________ | _________________ |
| Engineering Lead | _________________ | _________________ | _________________ |
| Counsel | _________________ | _________________ | _________________ |

Approval is recorded with the version of this document signed. Subsequent versions require re-approval; minor edits within a version are tracked in the change log without re-approval.

---

## Change Log

| Version | Date | Changes | Author |
|---|---|---|---|
| v1 | May 19, 2026 | Initial LIA for PA-15. Three-part test executed. Outcome: Art. 6(1)(f) valid for non-special-category training data, conditional on §4.6 safeguards. Special-category data continues under Art. 9(2)(a) consent. Draft for counsel review. | Privacy Lead |
| v2 | May 19, 2026 | Consistency-pass edits per Privacy Program Backlog D-86: §0.1 cross-jurisdictional scope clarification and single-global-rule design statement; §3.3 honest framing of controller-side considerations (algorithmic-disgorgement transparency, operational continuity, single-global-rule compatibility) replacing the v1 "operational coherence and transparency" framing; §4.3 restructure (category norms as primary support, disclosure as supporting condition, D-94 onboarding callout bridging the two) addressing v1 circularity; §4.5 irreversibility of past contributions promoted to distinct subsection (§4.5.2); new §4.8 EDPB Opinion 28/2024 mapping; §5.1 operational-validity gate strengthened with explicit "documentation does not authorize reliance" language and listed pre-conditions; new §7.1 LIA retention statement (PA-15 lifetime + 6 years); §8.1 default-opt-in for new users (clean LI position, with counter-position rejected and named); new Risk LIA-11 (category-norms regression) and LIA-12 (operational-validity gate non-binding mismanagement); new §11 Approval Block. | Privacy Lead |
| v3 | May 30, 2026 | Cleanup pass resolving D-115 (cross-reference drift). Inline cross-references converted from stale versioned tokens (PP v2, RoPA v2, T&C v2) to unversioned logical names per the project's cross-reference convention (Rule #12), so they no longer go stale on companion-doc bumps. Companion-docs header updated to current filenames (RoPA v5, PP v5, T&C v4, DPIA PA-15 v2). No analytical, three-part-test, safeguard, or outcome changes. | Privacy Lead |
| v4 | May 30, 2026 | Contact-address consolidation to the two approved addresses: `help@aidstation.pro` for user support (including privacy / data-rights requests) and `info@aidstation.pro` for formal, legal, security, and DMCA correspondence. No other changes. | Privacy Lead |

---

*Cross-reference cleanup (v4, 2026-05-30): inline references to companion documents were converted to unversioned logical names per Rule #12, so they no longer go stale when a companion document is revised. No substantive content changes. See `Privacy_Program_Consistency_Sweep_Report_v1.md`.*

