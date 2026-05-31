# Privacy Program Backlog

**File revision:** v17 — May 30, 2026 (D-90 resolved: de-id = rule- and pattern-based redaction; D-95 provider provisionally Anthropic; pseudonymized terminology locked corpus-wide)
**Purpose:** Single rolling tracker for privacy program deferred work — items surfaced during privacy program design that need follow-up, parallel deliverables, engineering builds, or consistency-pass edits. Maintained alongside the engineering `Project_Backlog_v11.md`, which tracks pipeline and data-architecture work; the two are deliberately separate (per Batch 7 §9).
**Categories:** Blocker / Deferred / Cleanup
**Source:** Privacy program handoff chain (Batches 1–8), Batch 8 v1 drafts (LIA, DPIA, DMCA)

---

## Categorization rule

**Blocker** — must complete before a specific launch milestone (named in the item). Triggers:
- Gates a customer-facing feature launch
- Gates EU/UK or other regulated jurisdiction launch
- Gates scaled AI training on user data
- Required to maintain a regulatory safe harbor

**Deferred** — documentation, design, or build that does not gate current work. Carried for periodic review; may promote to Blocker when scope intersects new work.

**Cleanup** — known doc/spec drift, cross-reference additions, or consistency-pass edits. Pure documentation work. Folded into the planned consistency-pass batch.

---

## Status legend

- 🔴 Blocker — fix before the named gate
- 🟡 Deferred — verify on each batch boundary; promote if scope intersects new work
- 🟢 Cleanup — pure doc/cosmetic, consistency-pass batch only
- ✅ Resolved
- ⚪ Wont-Fix (intentional, with reason)

---

## Carryover from Batch 7

| # | Description | Status | Source |
|---|---|---|---|
| D-74 | Deletion Flow Spec — add cross-reference to PP §7 disclosing future-vs-past training removal (trained-weights tension) | ✅ Resolved — `AIDSTATION_Deletion_Flow_Spec_v3.md` shipped May 19, 2026 (Track A Group 1) | Batch 6 §3, Batch 7 §4 |
| D-75 | LIA for PA-15 (AI training under Art. 6(1)(f)) — written before scaled training | ✅ Resolved (Batch 8) — `AIDSTATION_LIA_PA15_v1.md` shipped May 19, 2026 | Batch 6 §3, Batch 7 §4 |
| D-76 | AI Training DPIA — DPIA Template v2 Appendix A item 4 against PA-15 | ✅ Resolved (Batch 8) — `AIDSTATION_DPIA_PA15_v1.md` shipped May 19, 2026 | Batch 6 §3, Batch 7 §4 |
| D-77 | TOMs Annex — accept DPA Annex 2 as canonical TOMs (update RoPA references) or extract to standalone doc | ✅ Resolved — RoPA v5 points all TOMs references to standalone `AIDSTATION_TOMs_v2.md`; stale "[TOMs Annex — to be created]" placeholder removed (May 30, 2026) | Batch 6 §3, Batch 7 §4 |
| D-78 | DMCA designated agent process — publication blocker for crowdsourced facility feature | ✅ Resolved (Batch 8) — `AIDSTATION_DMCA_Designated_Agent_Spec_v2.md` shipped May 19, 2026 | Batch 6 §3, Batch 7 §4 |

---

## Health Screening UX items (Batch 7)

These items belong to the Health Screening flow design and remain open. Most are engineering deliverables that surface when the Health Screening UI is built; tracked here because they originated in the privacy program work.

| # | Description | Priority | Source |
|---|---|---|---|
| D-79 | Locale-aware "physician" terminology — "doctor" / "GP" / locale equivalents in plain-language strings | 🟡 Deferred — cosmetic until international rollout | Batch 7 §3 |
| D-80 | Free-text detail prompt UX — explicit indicator that field is sensitive and storage is opt-in-gated | 🟡 Deferred — user-trust impact, pre-launch | Batch 7 §3 |
| D-81 | Layer 3 design alignment — confirm `health_screening` data contract in §6 when L3 spec writing reaches it; revise if needed | 🔴 Blocker — gates L3 | Batch 7 §3 |
| D-82 | Mid-cycle self-reported condition update — voluntary path exists; auto-detection from chat or sensors deferred to post-v1 | 🟡 Deferred | Batch 7 §3 |
| D-83 | Reassessment overdue UX — banner persistence rules; user dismissal model | 🟡 Deferred | Batch 7 §3 |
| D-84 | Anti-skim guard for acknowledgment — possible brief delay before button activates when flags present | 🟡 Deferred | Batch 7 §3 |
| D-85 | Settings read-view of current screening — define the summary view UI | 🟡 Deferred | Batch 7 §3 |

---

## New from Batch 8

### LIA PA-15 v1 — consistency-pass edits

| # | Description | Status | Source |
|---|---|---|---|
| D-86 | LIA v1 → v2 surgical edits — combined consistency-pass batch covering: (a) §3.3 consent-vs-LI framing rewrite, acknowledging the controller-side benefit explicitly per §10.3; (b) §4.3 reasonable-expectation argument tightening (currently borderline circular); (c) §4.5 power asymmetry — add explicit acknowledgment of irreversibility (data incorporated into model weights survives departure); (d) §5 operational-validity gating language parallel to DPIA §7.3 (LIA does not authorize Art. 6(1)(f) reliance until safeguards are operational); (e) §8.1 default-opt-in-for-new-users decision — counsel-level call required; recommend default-opt-out; (f) cross-jurisdictional scope clarification — LIA is GDPR-specific while doc claims worldwide coverage; (g) substantive engagement with EDPB Opinion 28/2024 rather than gestural mention; (h) approval block placeholder; (i) LIA retention statement (how long the LIA itself is retained) | ✅ Resolved — `AIDSTATION_LIA_PA15_v2.md` shipped May 19, 2026. D-86(e) resolved as default opt-in for new users (option A — clean LI, operator-favorable, single global rule) per user decision. | LIA v1 review |

### DPIA PA-15 v1 — engineering prerequisites for scaled training

Each item below is a real engineering deliverable that must be operational before AIDSTATION may scale training on user data under the LIA's Art. 6(1)(f) basis. All of these together constitute the "operational validity gate" in DPIA §7.3.

| # | Description | Status | DPIA risk ref | Gate |
|---|---|---|---|---|
| D-87 | Free-text scrubbing pipeline for training ingest — classifier reusing AI System Prompt Restrictions §3.1/§3.2 categories; performance audit-validated before claim of implementation | 🔴 Blocker | R-03, R-10 | Before scaled training |
| D-88 | Sensitive-category two-class ingest gate — sensitive data routes to a separate dataset only if dual opt-in present; never to default training | 🔴 Blocker | R-03 | Before scaled training |
| D-89 | Training data lineage manifest — per-dataset-version manifest of contributing user-data versions; model artifact registry tying each weight to source dataset versions | 🔴 Blocker | R-05 | Before scaled training |
| D-90 | De-identification methodology — **RESOLVED: rule- and pattern-based redaction** (deterministic identifier removal/generalization + pattern/NER free-text scrubbing + manual review of flagged content). Best-effort, not formal; de-identified data is therefore pseudonymized and remains personal data. Differential privacy / k-anonymity explicitly not in use; aggregate suppression (N-floors) is the statistical safeguard for published aggregates. Reflected in Inactivity Spec v6 §5.3, compliance control 01 R6, INVARIANTS. | ✅ Resolved | R-02 | Done |
| D-91 | Memorization mitigation suite — deduplication, sensitive-content filter, adversarial probing protocol with documented cadence | 🔴 Blocker | R-01 | Before scaled training |
| D-92 | Fairness evaluation methodology + release threshold criteria — sport, experience level, sex demographic slices; documented thresholds for model release | 🔴 Blocker | R-06 | Before first model generation release |
| D-93 | Account-settings opt-out toggle for AI training — timestamped logging; default state per consistency-pass decision in D-86(e) | 🔴 Blocker | R-04 | Before scaled training |
| D-94 | In-product onboarding callout distinguishing AI training role from runtime coaching — supports the R-04 reasonable-expectation mitigation more salient than buried policy text | ✅ Resolved — `AIDSTATION_AITraining_Onboarding_Callout_Spec_v1.md` shipped May 19, 2026 (Track A Group 1). Spec only; engineering implementation tracked separately via the pre-flight checklist condition D-3. | R-04 | Before scaled training (light build) |
| D-95 | ML processor selection + DPA execution — **provider provisionally Anthropic** (already the named inference subprocessor); DPA execution, SCC-compatible posture, no-training-on-our-data + no-derivative-use terms, and audit rights remain to be executed/confirmed. | 🔴 Blocker | R-07, R-11 | Before scaled training |
| D-96 | Pre-flight checklist sign-off process for first scaled training run — Privacy Lead + Engineering Lead confirm each §7.3 condition; binding, not advisory | ✅ Resolved — `AIDSTATION_PreFlight_Checklist_PA15_v1.md` shipped May 19, 2026 (Track A Group 1). Fifteen conditions across engineering / disclosure / process. | DPIA §8.2 | Before first scaled training run |
| D-97 | DPO appointment decision — needed for EU/UK launch posture | 🔴 Blocker | LIA §3.1, DPIA Cover Page | Before EU/UK launch |
| D-98 | EU AI Act parallel assessment — DPIA is GDPR-structured; AI Act adds transparency, risk management, post-market monitoring obligations | 🟡 Deferred | DPIA §10.2 | When EU launch is closer |

### DMCA Designated Agent Process — operational deliverables

| # | Description | Status | Gate |
|---|---|---|---|
| D-99 | USCO Designated Agent registration — `dmca.copyright.gov`, $6 fee, valid 3 years; pre-condition: named agent (Privacy Lead in DMCA capacity), mailbox live, phone number procured, public DMCA page live | 🔴 Blocker | Before crowdsourced facility feature ships |
| D-100 | Stand up the two approved mailboxes: `info@aidstation.pro` (formal/legal/security/**DMCA designated-agent** correspondence, two-person routing — Privacy Lead + one backup) and `help@aidstation.pro` (user support, incl. data-rights requests). Per Andy's 2026-05-30 directive the DMCA agent address is now `info@`, not `dmca@`. | 🔴 Blocker | info@ before USCO registration; both before launch |
| D-101 | Phone number procurement for USCO directory — virtual number with business-hours routing acceptable | 🔴 Blocker | Before USCO registration |
| D-102 | Public DMCA page content at `aidstation.pro/dmca` — agent contact, procedural information per §512, repeat-infringer policy disclosure (statutory-style language only per DMCA Spec v2 §6.3), notice and counter-notice template links | 🔴 Blocker | Before USCO registration goes live |
| D-103 | Template documents — DMCA notice form, counter-notice form, user-notification template (for takedown), optional intake-acknowledgment template | 🟢 Cleanup | Pre-launch; not blocking USCO registration itself |
| D-104 | T&C copyright section addition — reference to DMCA process, agent contact, user representation re: non-infringing content, repeat-infringer policy acknowledgment | ✅ Resolved — `AIDSTATION_Terms_and_Conditions_v3.md` shipped May 19, 2026 (Track A Group 2). Added as §8.6 subsection within "Your Content"; no top-level renumbering required. | Consistency pass |
| D-105 | RoPA v3 PA-16 entry — DMCA notice processing as a distinct processing activity (legitimate interest Art. 6(1)(f) for safe-harbor compliance and litigation defense) | ✅ Resolved — `AIDSTATION_RoPA_v4.md` shipped May 19, 2026 (Track A Group 2). PA-16 added; summary table row added; Art. 6(1)(c) flagged for counsel review re: DSA Art. 16 transposition jurisdictions; retention 7 years parallel to PA-14. | Consistency pass |
| D-106 | Internal repeat-infringer threshold guideline (unpublished) — supports "reasonable implementation" under §512(i)(1)(A) without exposing AIDSTATION to a published commitment; recommended starting point ~3 strikes/12 months for internal review, ~5 for termination; lives in an internal operations doc, not in the public DMCA spec | 🟢 Cleanup | Before scaled UGC volume |

### Cross-document consistency-pass items

| # | Description | Status | Source |
|---|---|---|---|
| D-107 | DMCA spec cross-references to Deletion Flow Spec, Privacy Policy §7, and Breach Response Playbook — surgical edits adding the references in the named docs | ✅ Resolved — three files shipped May 19, 2026 (Track A Group 2): `AIDSTATION_Deletion_Flow_Spec_v4.md` (new §6.5 DMCA-Removed Content), `AIDSTATION_Privacy_Policy_v4.md` (new §7 Copyright Notices subsection), `AIDSTATION_Breach_Response_Playbook_v3.md` (new §2 "Not a Personal Data Breach" subsection). | Consistency pass |

### Track A Group 1 — lens-driven consistency-pass items (operator-favorable + lawful + single global rule)

Surfaced during the Cross-Document Lens Review v1 (May 19, 2026) while applying the operator-favorable / lawful / single-global-rule lens to LIA v2 companion docs.

| # | Description | Status | Source |
|---|---|---|---|
| D-108 | PP v2 §14.2 response-time alignment — change "within 45 days (extendable to 90 with notice)" to "within 30 days (extendable by up to a further two months for complex requests, with notice to you)" per single-global-rule analysis. 30 days globally is the answer (matches GDPR Art. 12(3) "one month"; within US state law allowances). | ✅ Resolved — `AIDSTATION_Privacy_Policy_v3.md` shipped May 19, 2026 | Cross-Doc Lens Review §1.2 P1 |
| D-109 | DPIA PA-15 v1 — add single-global-rule statement mirroring LIA v2 §0.1, in the §0 status block. | ✅ Resolved — `AIDSTATION_DPIA_PA15_v2.md` shipped May 19, 2026 | Cross-Doc Lens Review §1.1 D1 |
| D-110 | DPIA PA-15 v1 — companion-reference update LIA v1 → v2 in header companion-docs list and in §9 Cross-Spec Touchpoints table; also RoPA v2 → v3 and PP v2 → v3 references updated to track this session's revisions. Section-level references (LIA §2, §3, §4.6, §8.2, §10.1) preserved verbatim — LIA v2 retains the same structural sectioning. | ✅ Resolved — `AIDSTATION_DPIA_PA15_v2.md` shipped May 19, 2026 | Cross-Doc Lens Review §1.1 D2 |
| D-111 | DPIA PA-15 v1 — §4.4 rights table, explicit default-opt-in-for-new-users statement per LIA v2 §8.1 in the Restriction and Objection rows. | ✅ Resolved — `AIDSTATION_DPIA_PA15_v2.md` shipped May 19, 2026 | Cross-Doc Lens Review §1.1 D3 |
| D-112 | DPIA PA-15 v1 — §4.1 lawful basis, cross-reference to LIA v2 §4.8 EDPB Opinion 28/2024 mapping. | ✅ Resolved — `AIDSTATION_DPIA_PA15_v2.md` shipped May 19, 2026 | Cross-Doc Lens Review §1.1 D4 |
| D-113 | RoPA v2 PA-15 — Legal Basis paragraph updated with explicit LIA v2 reference and default-opt-in-for-new-users statement per LIA v2 §8.1; cross-reference to PP v3 §4 / §9. **Note for D-105 (Group 2):** RoPA was bumped to v3 in this session for the D-113 alignment; D-105's PA-16 entry deliverable will produce RoPA v4. | ✅ Resolved — `AIDSTATION_RoPA_v3.md` shipped May 19, 2026 | Cross-Doc Lens Review §1.4 R1+R2 |
| D-114 | PP v2 §4 — optional one-line addition surfacing default-inclusion-for-training with opt-out at the user-facing PP level. Lower priority because the D-94 in-product onboarding callout is the principal salience mechanism; revisit after D-94 lands and observe whether the PP gap is meaningful. | ✅ Resolved — PP v5 §4 now states AI-training use is on by default with opt-out (section 9), May 30, 2026 | Cross-Doc Lens Review §1.2 P2 |
| D-115 | LIA v2 §5.1 cross-ref drift — text reads "referenced in `AIDSTATION_DPIA_PA15_v1.md` §8.2" but DPIA was bumped to v2 in this session cycle for D-109–D-112. Also: LIA v2 §5.1 references "PP v2 §4 / §7 / §9, T&C v2 §8.2" — PP is now v3 (T&C is now v3 as of Track A Group 2). Content survives in current versions, so cross-refs are not broken; only version numbers are stale. Defer to next LIA revision (likely after counsel review) to avoid a fresh v3 cycle for token-level edits. | ✅ Resolved — LIA v3 inline cross-refs converted to unversioned logical names per Rule #12; companion header updated to current filenames (May 30, 2026) | Flagged in Track A Group 1 Closing Handoff §4 |
| D-124 | Anonymize/pseudonymize user-facing terminology alignment. PP v5 §7 fixed (inactivity outcome described as de-identification + pseudonymized retention; "no longer personal data" scoped to genuine irreversible aggregation only). REMAINING: Inactivity Automation Spec v3 §4.2 user-facing email still says "anonymize" — align on next Inactivity touch. Counsel to confirm whether any output reaches the legal anonymization threshold; v5 takes the conservative lower-claim position. | ✅ Resolved (drafting) — PP authoritative; Inactivity Spec v5 AND RoPA v7 aligned to de-identification/pseudonymized-retention framing (May 30, 2026). Residual: counsel to confirm anonymization threshold; all docs move together if it changes. | This session (flagged from Inactivity Spec v3 Lens Note 3) |
| D-126 | DSR extension period inconsistency — Authorized Agent Spec response letter commits to "+30 days" extension; PP §9.1/§14.2 commit to "+60 days / two months" (GDPR Art.12(3) max). Recommendation: align Authorized Agent to +60 days/two months. | ✅ Resolved — Authorized Agent Spec v5 response letter extension aligned to +60 days/two months (operator-favorable, matches PP), May 30, 2026 | Deep Consistency Pass (this session) |
| D-127 | Deletion timeline inconsistency — PP §7 says "processed within 30 days" (flat); Deletion Flow Spec describes 30-day cancellation grace THEN deletion within an additional 30 days (~up to 60 days active-system purge). User-facing mismatch. Recommendation: PP discloses the grace-then-delete model. | ✅ Resolved — PP v6 §7 adopted the Deletion Flow grace-then-delete model (30-day reversible window, then deletion within a further 30 days, backups 90 days), May 30, 2026. See D-129 for the Art.12 counsel flag. | Deep Consistency Pass (this session) |
| D-128 | DMCA notice retention trigger inconsistency — Designated Agent Spec: "7 years from the date of the notice"; RoPA PA-16: "7 years from final action on the matter." Duration agrees, start point differs. Recommendation: conform DMCA Spec to RoPA's "from final action." | ✅ Resolved — DMCA Spec v4 notice-retention trigger changed to "from final action" matching RoPA PA-16, May 30, 2026 | Deep Consistency Pass (this session) |
| D-129 | Deletion-timeline statutory check — PP v6 §7 (per D-127) describes a 30-day reversible cancellation window then deletion within a further 30 days (~up to 60 days to active-system erasure). Confirm compatibility with the GDPR Art. 12(3) one-month erasure window (extendable), or confirm the reversible-grace design / disclosure is defensible. | ✅ Resolved — Deletion Flow Spec v6 + PP v7 now use a 14-day recover window with active-system erasure within 30 days of the request (GDPR Art. 12(3) one-month limit; extendable for genuinely complex requests). Backups stay on the ≤90-day rolling cycle (beyond-use; restores re-apply). May 30, 2026 | Raised when resolving D-127 (this session) |

### Track A Group 1 — closed

All Group 1 items closed. Three remaining items from the prior partial close (D-74, D-94, D-96) were closed in the same session: see the §"Resolved this batch" table below.

| # | Description | Resolution |
|---|---|---|
| D-74 | Deletion Flow Spec edit — add cross-reference to PP §7 disclosing future-vs-past training removal (trained-weights tension) | ✅ `AIDSTATION_Deletion_Flow_Spec_v3.md` shipped May 19, 2026 |
| D-94 | In-product onboarding callout distinguishing AI training role from runtime coaching | ✅ `AIDSTATION_AITraining_Onboarding_Callout_Spec_v1.md` shipped May 19, 2026 (spec only; engineering implementation gated by pre-flight checklist condition D-3) |
| D-96 | Pre-flight checklist sign-off process for first scaled training run | ✅ `AIDSTATION_PreFlight_Checklist_PA15_v1.md` shipped May 19, 2026 |

### Track A Group 2 — closed

All Group 2 items closed in the same session as Group 2 kickoff.

| # | Description | Resolution |
|---|---|---|
| D-104 | T&C copyright/DMCA section addition | ✅ `AIDSTATION_Terms_and_Conditions_v3.md` shipped May 19, 2026 (added as §8.6 within "Your Content"; no top-level renumbering) |
| D-105 | RoPA PA-16 entry — DMCA notice processing | ✅ `AIDSTATION_RoPA_v4.md` shipped May 19, 2026 |
| D-107 | DMCA cross-references in Deletion Flow Spec, PP §7, Breach Playbook | ✅ Three files shipped May 19, 2026: `AIDSTATION_Deletion_Flow_Spec_v4.md`, `AIDSTATION_Privacy_Policy_v4.md`, `AIDSTATION_Breach_Response_Playbook_v3.md` |

Track A (Groups 1 + 2) fully closed. Counsel review of the Track A deliverables can proceed as a single batch.

### Tier 2 — lens-driven internal-spec items (operator-favorable + lawful + single global rule)

Surfaced during the Track A Group 2 closing handoff §5 sequencing. Tier 2 covers internal-spec and contract-template documents; Tier 1 (user-facing T&C / AUP / Health & Safety Notice full lens pass) follows Tier 2 per Memory #14.

| # | Description | Status | Source |
|---|---|---|---|
| D-116 | DPA Template v2 → v3 lens pass — sub-processor objection grounds broadening; DSR-assistance 10 → 5 business days; Security Incident 48h → 12h preliminary + 24h full; audit trigger broadened with cost allocation; §7 liability cap carve-outs (uncapped on confidentiality / Sensitive PD / §4.12 / intentional-gross / fraud / IP); §8 cure period 30 → 14 days with no-cure for Sensitive PD or §4.12 breach; new §4.12 No Secondary Use / No Training on Controller Data with §4.12(c) Controller-instructed-training carve-out | ✅ Resolved — `AIDSTATION_DPA_Template_v3.md` shipped May 20, 2026 | Track A G2 Closing Handoff §5.1 |
| D-117 | Breach Response Playbook v3 → v4 lens pass — §5.3 initial classification tightened (4h target / 8h outer); §6 split into matrix + T+24h notification decision waypoint + Art. 33(1) risk carve-out analysis; §7.1 decision principle rewritten (legal-standard default; uncertainty still defaults to notify); §7.2 expanded with Art. 33 vs Art. 34 distinction, Art. 34(3) mitigation conditions, AIDSTATION default policy ties to legal threshold with IC discretion to override; §7.3 subprocessor reference updated to 12h preliminary + 24h full per DPA v3 §4.7; §12.1 Art. 33(5) record-keeping recognition added | ✅ Resolved — `AIDSTATION_Breach_Response_Playbook_v4.md` shipped May 20, 2026 | Track A G2 Closing Handoff §5.2 |
| D-118 | Inactivity Automation Spec v2 → v3 lens pass — variables to audit: inactivity threshold periods (months before warning, before auto-delete), notification cadence and method, opt-out mechanism, retention of inactivity-related metadata after deletion. Single-global-rule analysis on the threshold values. | ✅ Resolved — `AIDSTATION_Inactivity_Automation_Spec_v3.md` shipped May 20, 2026 (backlog status was stale in v5) | Track A G2 Closing Handoff §5.3 |
| D-119 | Aggregation Suppression Spec v2 → v3 lens pass — variables: minimum-cell N threshold (current N=25), suppression rules for small cells, recombination rules, audit logging on aggregate queries. Cross-reference to PP v4 aggregation policy. | ✅ Resolved — `AIDSTATION_Aggregation_Suppression_Spec_v3.md` shipped May 20, 2026 (backlog status was stale in v5) | Track A G2 Closing Handoff §5.4 |
| D-120 | Authorized Agent Process Spec v2 → v3 lens pass — variables: identity verification standard, agent-credentials retention, scope of authorized-agent rights, edge cases (minor's parent; spouse acting under POA; deceased estate). Single-global-rule analysis on verification standard. | ✅ Resolved — `AIDSTATION_Authorized_Agent_Process_Spec_v3.md` shipped May 30, 2026 | Track A G2 Closing Handoff §5.5 |
| D-121 | TOMs v1 → v2 lens pass — variables: logging retention default, access review cadence, vendor due-diligence requirements, incident-response capability commitments. May surface follow-ups to DPA Annex 2 (TOMs reference). Cross-check no-secondary-use controls section against DPA v3 §4.12. Update §8 reference from Breach Playbook v2 to v4 (currently two versions behind). | ✅ Resolved — `AIDSTATION_TOMs_v2.md` shipped May 30, 2026 | Track A G2 Closing Handoff §5.6 |
| D-122 | DPIA Template v2 → v3 lens pass — variables: necessity threshold for DPIA trigger, risk-rating methodology calibration, residual-risk acceptance threshold, consultation-with-supervisory-authority trigger. Cross-reference DPIA PA-15 v2 as the worked example. | ✅ Resolved — `AIDSTATION_DPIA_Template_v3.md` shipped May 30, 2026 | Track A G2 Closing Handoff §5.7 |
| D-123 | Tier 1 lens batch — full T&C v3 lens pass + AUP v1 lens pass + Health & Safety Notice v1 lens pass. Tier 1 unblocked per Memory #14 (no longer held pending counsel return on Track A). Follows Tier 2 completion (D-118 through D-122). | ✅ Resolved — T&C v4, AUP v2, Health & Safety Notice v2 shipped May 30, 2026 | Memory #14; Track A G2 Closing Handoff §6 (hold lifted) |

---

## Resolved this batch (Batch 8 + Track A Group 1 full close)

| # | Description | Resolution |
|---|---|---|
| D-75 | LIA for PA-15 | `AIDSTATION_LIA_PA15_v1.md` shipped May 19, 2026 |
| D-76 | AI Training DPIA | `AIDSTATION_DPIA_PA15_v1.md` shipped May 19, 2026 |
| D-78 | DMCA designated agent process | `AIDSTATION_DMCA_Designated_Agent_Spec_v2.md` shipped May 19, 2026 (v1 → v2 in same session per operator-favorable revision pass) |
| D-86 | LIA v1 → v2 consistency-pass edits | `AIDSTATION_LIA_PA15_v2.md` shipped May 19, 2026 (Track A Group 1, D-86(e) resolved as option A: default opt-in for new users, clean LI, operator-favorable, single global rule) |
| D-108 | PP §14.2 response-time inconsistency with §9.1 | `AIDSTATION_Privacy_Policy_v3.md` shipped May 19, 2026 (Track A Group 1) |
| D-109, D-110, D-111, D-112 | DPIA v1 alignment with LIA v2 (single-global-rule statement, companion-reference sweep, default-opt-in mention, EDPB Opinion 28/2024 cross-reference) | `AIDSTATION_DPIA_PA15_v2.md` shipped May 19, 2026 (Track A Group 1) |
| D-113 | RoPA PA-15 LIA v2 reference + default-opt-in mention | `AIDSTATION_RoPA_v3.md` shipped May 19, 2026 (Track A Group 1; D-105 now produces RoPA v4) |
| D-74 | Deletion Flow Spec — trained-weights irreversibility bullet in §6.2 | `AIDSTATION_Deletion_Flow_Spec_v3.md` shipped May 19, 2026 (Track A Group 1) |
| D-94 | In-product onboarding callout copy + UX spec | `AIDSTATION_AITraining_Onboarding_Callout_Spec_v1.md` shipped May 19, 2026 (Track A Group 1; spec only — engineering implementation tracked via pre-flight checklist condition D-3) |
| D-96 | Pre-flight checklist for first scaled training run | `AIDSTATION_PreFlight_Checklist_PA15_v1.md` shipped May 19, 2026 (Track A Group 1; 15 conditions; binding-not-advisory framing) |
| D-104 | T&C copyright/DMCA section | `AIDSTATION_Terms_and_Conditions_v3.md` shipped May 19, 2026 (Track A Group 2; added as §8.6 subsection, no top-level renumbering) |
| D-105 | RoPA PA-16 entry (DMCA notice processing) | `AIDSTATION_RoPA_v4.md` shipped May 19, 2026 (Track A Group 2; Art. 6(1)(f) LI basis; 7-year retention parallel to PA-14) |
| D-107 | DMCA cross-references in Deletion Flow Spec / PP / Breach Playbook | Three files shipped May 19, 2026 (Track A Group 2): `AIDSTATION_Deletion_Flow_Spec_v4.md`, `AIDSTATION_Privacy_Policy_v4.md`, `AIDSTATION_Breach_Response_Playbook_v3.md` |

---

## Open question — backlog scope

The privacy program backlog (this file, D-66 through D-107) and the engineering `Project_Backlog_v11.md` (D-01 through D-61+) are deliberately separate (per Batch 7 §9). The two share a `D-NN` numbering namespace by convention but are otherwise independent rolling trackers.

Whether to merge them remains an open call. Arguments for merging: single source of truth for all deferred work. Arguments for keeping separate: privacy items are scoped to the privacy/compliance workstream and rarely interact with the pipeline backlog; merging would dilute both. Recommendation: keep separate through v1 launch; revisit if cross-workstream items multiply.

---

## Process notes

1. At every batch boundary (end of Batch 8, Batch 9, ...):
   - Re-read this backlog
   - Mark resolved items
   - Add new findings from the batch
   - Re-categorize as needed (Blocker may demote to Deferred if its gate moves; Deferred may promote to Blocker if scope intersects new work)

2. The "Blocker" status is sticky-up but not sticky-down. Once promoted to blocker, stays blocker until the named gate is met or the gate moves. A blocker is resolved only by a fix, not by deciding to ignore it.

3. Engineering deliverables under DPIA §7.3 (D-87 through D-95) are blockers for scaled AI training. They are not blockers for v1 product launch in general — evaluation-only and synthetic-only training work may proceed in parallel. The distinction matters for sequencing: do not let the privacy gates be conflated with general launch gates, and do not let general launch gates absorb the privacy-specific ones.

4. Consistency-pass items that were previously listed for a "combined consistency-pass batch after all v1 drafts are complete" have been folded into the Track A workstream. Track A (Groups 1 + 2) is now fully closed: D-74, D-86, D-94, D-96 in Group 1; D-104, D-105, D-107 in Group 2. D-77, D-103, D-106 remain as unscheduled consistency-pass items to address when the surrounding files are next revised. D-115 (LIA v2 §5.1 cross-ref drift) is deferred to the next LIA touch. Tier 2 lens batch: D-116 (DPA Template v3) and D-117 (Breach Playbook v4) resolved May 20, 2026; D-118 (Inactivity Spec v3) and D-119 (Aggregation Spec v3) also resolved May 20 but were left mis-marked as pending in Backlog v5 — reconciled to ✅ in v6. D-120 (Authorized Agent Spec v3), D-121 (TOMs v2), and D-122 (DPIA Template v3) resolved May 30, 2026. **Tier 2 lens batch is now COMPLETE (D-116 through D-122).** Tier 1 lens batch (D-123 — full T&C / AUP / Health & Safety Notice lens pass) is also **COMPLETE** as of May 30, 2026: T&C v4, AUP v2, Health & Safety Notice v2 shipped. **The entire lens program (D-116 through D-123) is resolved and the full Track A + Tier 2 + Tier 1 document set is package-ready for the single counsel forward pass (Memory #14).** Remaining non-lens items (DMCA operational standup, DPIA engineering prerequisites, DPO decision, App Store compliance) are tracked separately and are not chat-shaped.

---

## Change Log

| Version | Date | Changes | Author |
|---|---|---|---|
| v1 | May 19, 2026 | Initial file. Consolidates carryover privacy program items from Batch 7 (D-74 through D-85). Closes D-75, D-76, D-78 against Batch 8 v1 drafts. Adds D-86 through D-107 from LIA, DPIA, and DMCA work. Establishes categorization rule, status legend, and process notes. | Privacy Lead |
| v2 | May 19, 2026 | Track A Group 1 partial close. New durable principle captured to user memory: AIDSTATION privacy/legal/commercial defaults rule (operator-favorable + lawful + single global rule). Closes D-86 (LIA v2 shipped with D-86(e) resolved as default opt-in). Closes D-108–D-113 (Cross-Doc Lens Review surgical edits to PP, DPIA, RoPA). D-114 deferred. Track A Group 1 remaining open: D-74, D-94, D-96. Track A Group 2 (D-104, D-105, D-107) unchanged; note D-105's deliverable is now RoPA v4 since v3 was used in this session. | Privacy Lead |
| v3 | May 19, 2026 | Track A Group 1 full close. Closes D-74 (`AIDSTATION_Deletion_Flow_Spec_v3.md`), D-94 (`AIDSTATION_AITraining_Onboarding_Callout_Spec_v1.md`), D-96 (`AIDSTATION_PreFlight_Checklist_PA15_v1.md`). Track A Group 2 (D-104, D-105, D-107) unchanged. Process note 4 updated to reflect that the previously-planned "combined consistency-pass batch" has been folded into Track A. | Privacy Lead |
| v4 | May 19, 2026 | Track A Group 2 full close. Closes D-104 (T&C v3), D-105 (RoPA v4 with PA-16), D-107 (Deletion Flow Spec v4, PP v4, Breach Playbook v3). Adds D-115 (LIA v2 §5.1 cross-ref drift flagged for next LIA touch). Track A (Groups 1 + 2) fully closed. Next planned workstream per Track A G1 closing handoff §7: hold Tier 1 lens work pending counsel; use wait time for Tier 2 lens batch (DPA Template, Breach Playbook lens pass, Inactivity Spec, Aggregation Spec, Authorized Agent Spec, TOMs, DPIA Template). | Privacy Lead |
| v5 | May 20, 2026 | Tier 2 lens batch partial close. D-116 (DPA Template v3) and D-117 (Breach Playbook v4) resolved this session. D-118 through D-123 added as new backlog items covering remaining Tier 2 lens passes (Inactivity Spec, Aggregation Spec, Authorized Agent Spec, TOMs, DPIA Template) and the Tier 1 lens batch (full T&C lens / AUP / Health & Safety Notice). Memory #14 captured: counsel review process — ship complete cleaned-up doc set for single forward pass, no iterative back-and-forth; Tier 1 lens batch no longer held pending counsel return. Process Note 4 updated. Internal header reconciled from stale "v2" string to v5 (filename had been ahead of header text since v3). | Privacy Lead |
| v6 | May 30, 2026 | Tier 2 lens batch continued. D-120 (Authorized Agent Process Spec v3) and D-121 (TOMs v2) resolved this session. Reconciled D-118 (Inactivity Spec v3) and D-119 (Aggregation Spec v3) from stale Blocker/Deferred status to Resolved — both files shipped May 20 but Backlog v5 was not updated to match (session-start verification per Rule #9 caught the drift). D-122 (DPIA Template v2 → v3) set to Blocker as the sole remaining Tier 2 item; D-123 Tier 1 batch follows. Process Note 4 updated. | Privacy Lead |
| v7 | May 30, 2026 | Tier 2 lens batch COMPLETE. D-122 (DPIA Template v3) resolved — the final Tier 2 item. All of D-116 through D-122 now resolved. D-123 (Tier 1 lens batch: full T&C v3 / AUP v1 / Health & Safety Notice v1 lens pass) promoted to active Blocker as the next session's work. Process Note 4 updated to reflect Tier 2 completion and package-readiness for counsel once Tier 1 ships. | Privacy Lead |
| v8 | May 30, 2026 | Tier 1 lens batch COMPLETE — closes D-123 and the full lens program. T&C v3→v4, AUP v1→v2, Health & Safety Notice v1→v2 lens passes shipped. Tier 1 passes were deliberately light (the user-facing docs were already mature operator-favorable-but-lawful instruments); main substantive items were a corrected placeholder address in the Health & Safety Notice, a DMCA cross-ref consistency fix in the AUP, a tightened security-research safe harbor, strengthened inherent-risk assumption language, and Privacy-Policy lawful-basis anchoring of the T&C AI-training grant. All of D-116 through D-123 now resolved; doc set is counsel-package-ready. | Privacy Lead |
| v9 | May 30, 2026 | Cleanup pass + consistency sweep. Resolved D-77 (RoPA v5 TOMs references → standalone TOMs doc), D-114 (PP v5 §4 explicit default-on AI-training + opt-out), D-115 (LIA v3 cross-refs converted to unversioned logical names per Rule #12). Added D-124 tracking the anonymize/pseudonymize terminology alignment (PP v5 §7 fixed; Inactivity email §4.2 still to align; counsel to confirm anonymization-threshold characterization). Consistency sweep run across the current document set (findings in the sweep report). | Privacy Lead |
| v10 | May 30, 2026 | Corpus-wide cross-reference unversioning migration (the durable fix recommended in the consistency sweep report). Stripped version tokens from inline cross-references across 17 documents, converting them to unversioned logical names per Rule #12 so they no longer go stale when a companion doc is revised. Files bumped: DMCA Designated Agent Spec v3, PreFlight Checklist v2, DPIA PA-15 v3, Inactivity Spec v4, AITraining Onboarding Callout v2, Aggregation Spec v4, TOMs v3, Deletion Flow Spec v5, Authorized Agent Spec v4, RoPA v6, DPIA Template v4, LIA PA-15 v4, AI System Prompt Restrictions v3, DMCA Public Page v2, Repeat Infringer Guideline v2, Breach Playbook v5, DMCA Templates v2. The 5 user-facing/contract docs (T&C v4, PP v5, AUP v2, Health & Safety Notice v2, DPA Template v3) already used unversioned references and were not touched. Acceptance test: re-ran the consistency sweep against the migrated corpus — 0 genuine stale cross-references remaining. Closes the D-115 drift class corpus-wide. Each migrated doc has only inline-cross-ref changes, a corrected Status/version header line, and an EOF cleanup note; no substantive content changes. | Privacy Lead |
| v11 | May 30, 2026 | Deep consistency pass (section-number survival + substantive contradictions). Part 1: 171 cross-doc section references checked, 0 broken/renumbered (family-level check; caveat in report). Part 2: confirmed consistency on inactivity thresholds, deletion processing, backups, DSR base window, copyright duration, min age, aggregation N, breach windows, governing law, training-data retention, contacts; flagged 4 substantive contradictions — D-124 (anonymize vs de-identify, reconfirmed substantive), D-126 (DSR extension +30 vs +60), D-127 (deletion 30 vs grace+30), D-128 (DMCA retention trigger). Flagged not auto-fixed: each is a policy commitment requiring a decision. Part 3 (byproduct): the earlier version-token sweep was pattern-limited — Health Screening Spec and Cookie Banner Spec were outside its file list, and bare shorthands (DPA v#, DPIA v#, Designated Agent Spec v#, Inactivity v#, Restrictions v#) were unmatched. All now closed in place; Health Screening Spec→v2, Cookie Banner Spec→v3 added. Broad re-scan: 0 live residual versioned cross-refs corpus-wide. Report: Privacy_Program_Deep_Consistency_Report_v1.md. | Privacy Lead |
| v12 | May 30, 2026 | Resolved the four contradictions from the deep pass per Andy's decisions. A (D-124): PP authoritative; Inactivity Spec v5 aligned to de-identification/pseudonymization (residual: counsel anonymization-threshold confirm). B (D-126): Authorized Agent Spec v5 DSR extension → +60 days/two months (more operator-favorable). C (D-127): PP v6 adopted the Deletion Flow grace-then-delete model. D (D-128): DMCA Spec v4 retention trigger → "from final action." Added D-129 (deletion-timeline Art.12 counsel flag). Current versions: PP v6, Inactivity Spec v5, Authorized Agent Spec v5, DMCA Designated Agent Spec v4. | Privacy Lead |
| v13 | May 30, 2026 | Resolved D-129 (deletion GDPR compliance). The Deletion Flow Spec's own model was internally inconsistent (decision table said "30 days from confirmation" while the user copy/cascade said 30-day cooling-off THEN a further 30 days, ~60 total). Now: 14-day recover window + active-system erasure within 30 days of the request (Art. 12(3) one-month limit, complex-request extension preserved); backups on ≤90-day rolling cycle. Deletion Flow Spec→v6, PP→v7 (mirrored). Also completed the D-124 alignment across all docs: RoPA→v7 (inactivity outcome "anonymized"→"de-identified (pseudonymized retention)"). Current versions: PP v7, Deletion Flow Spec v6, RoPA v7, Inactivity Spec v5, Authorized Agent Spec v5, DMCA Designated Agent Spec v4. | Privacy Lead |
| v14 | May 30, 2026 | Contact-address consolidation per Andy's directive: every email in the live corpus now uses only `help@aidstation.pro` (user support, incl. privacy/data-rights requests) and `info@aidstation.pro` (formal/legal/security/DMCA). Mapping applied: support@→help@; dmca@/legal@/security@→info@. This-session draft outputs updated in place; 7 prior-session docs bumped — AUP v3, T&C v5, Cookie Policy v3, DPA Template v4, Health & Safety Notice v3, Partners Page v4, AI Safety Logging Decision v2. D-100 updated (DMCA designated-agent mailbox is now info@; help@ also to be stood up). Memory updated. Session-record docs (handoffs, lens review, this backlog's history rows) left as historical. | Privacy Lead |
| v15 | May 30, 2026 | Semantic cross-document consistency review (the content-equivalence + wider-constant pass the prior consistency report deferred). Verified that cited "Doc §X" references host the claimed content, not just exist (118 claim-bearing refs + cross-cutting policy statements). Found and fixed 2 wrong-section cross-references: athlete-to-athlete/no-human-coach cited T&C §10 → corrected to §9 (AI System Prompt Restrictions); 16+ age cited T&C §1 → corrected to §2 (TOMs). Cleared 3 suspected mismatches as correct (HSN→T&C §17 liability carve-out; LIA §8.1 default-opt-in; PreFlight→PP §14.2 DSR window). Verified consistent: lawful bases, default-opt-in, no-third-party-training, raw-transcript non-retention, subprocessor single-source model, rights enumeration. Report: Privacy_Program_Semantic_Consistency_Review_v1.md. Caveats and residual blind spots documented in the report. | Privacy Lead |
| v16 | May 30, 2026 | Wrote the Claude Code implementation spec package (`compliance/`): organizing index (00_OVERVIEW), shared constants (INVARIANTS), and 8 per-control build specs (01 AI-training governance, 02 deletion, 03 inactivity, 04 aggregation suppression, 05 DSR/authorized-agent, 06 breach logging, 07 DMCA, 08 consent/cookies). Specs are thin and point back to the finalized privacy docs as source of truth; each maps requirements to the source spec, with data-model sketches and testable acceptance criteria. Decision/contract prerequisites flagged out-of-code-scope: de-identification methodology (D-90), fairness thresholds (D-92), ML-processor DPA (D-95), USCO registration + mailbox standup (D-99–D-102). Organizing tool is a self-contained package, NOT CLAUDE.md (per Andy — repo already has one). The engineering blockers D-87–D-93 etc. remain open until built but now have build specs. | Privacy Lead |
| v17 | May 30, 2026 | Per Andy: (1) de-identification terminology locked corpus-wide — individual-record de-identification is consistently `pseudonymized` (Inactivity Spec→v6 with identifiers renamed; Aggregation→v5 coupling refs; DPIA v4 + Deletion v6 risk/label refs), while genuine irreversible-aggregate and legal-threshold language deliberately keeps `anonymized`. (2) D-90 **RESOLVED** = rule- and pattern-based redaction (reflected in Inactivity v6 §5.3, control 01 R6, INVARIANTS). (3) D-92 kept **open** (fairness thresholds). (4) D-95 kept **open**, provider noted **provisionally Anthropic** (control 01 R9, OVERVIEW). | Privacy Lead |
