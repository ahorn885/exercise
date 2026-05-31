# AIDSTATION Privacy & Compliance — Canonical Document Index

**As of:** 2026-05-30. Each entry is the current canonical version. Cross-references inside the documents use logical names (no version), resolved to the highest version per the project's versioning rule. De-identified individual-record data is labeled **pseudonymized** throughout; de-identification method is **rule- and pattern-based redaction**.

## Public-facing policies
- **Privacy Policy — v7** — The user-facing notice: what data is collected, why, the lawful bases, retention, sharing, and how users exercise their rights. The hub the other documents point to.
- **Terms and Conditions — v5** — The use contract: eligibility (16+, §2), AI-coaching nature and limits (§5), content license (§8), health/safety (§6), liability (§17), team scope/no-human-coach (§9), governing law (§19).
- **Acceptable Use Policy — v3** — What users may and may not do; prohibited conduct and content.
- **Cookie Policy — v3** — Cookie categories (strictly-necessary vs analytics), consent, and how to change preferences.
- **Health and Safety Notice — v3** — The exertion/medical-risk disclaimer specific to endurance training; assumption of inherent risks.
- **DMCA Public Page — v2** — Public copyright notice-and-takedown page and the designated-agent contact (info@).
- **Partners Page — v4** — Public list of third-party providers/subprocessors and their roles; the single source of truth for the vendor list.

## User-facing specs / UX
- **Health Screening Spec — v2** — The PAR-Q-style intake screening design: questions, gating, contraindication handling.
- **Cookie Banner Spec — v3** — Consent-banner behavior: first-visit prompt, accept/reject/manage, GPC, 12-month expiry.
- **AI-Training Onboarding Callout Spec — v2** — The onboarding disclosure that AI-training is on by default with an opt-out.

## GDPR accountability / governance
- **RoPA — v7** — Record of Processing Activities (Art. 30): every processing activity (PA-xx), its basis, recipients, and retention.
- **TOMs — v3** — Technical and Organizational Measures: the security controls AIDSTATION commits to.
- **DPIA Template — v4** — Reusable Data Protection Impact Assessment template for high-risk processing.
- **DPIA PA-15 — v3** — Completed DPIA for the AI-model-training activity.
- **LIA PA-15 — v4** — Legitimate Interests Assessment justifying the lawful basis for AI training, with the binding §4.6 safeguards.
- **DPA Template — v4** — Data Processing Agreement template for processors/subprocessors (incl. no-training/no-derivative terms).
- **Breach Response Playbook — v5** — Incident-response runbook: assessment matrix, notification windows (72h/24h/12h), record-keeping.
- **PreFlight Checklist PA-15 — v2** — Pre-launch readiness checklist for the AI-training activity.

## Data-lifecycle specs
- **Deletion Flow Spec — v6** — Account deletion: 14-day recover window, erasure within 30 days, backups (≤90-day beyond-use), tombstone.
- **Inactivity Automation Spec — v6** — Inactivity lifecycle: 18-month notice, 24-month de-identification via rule-/pattern-based redaction, pseudonymized retention, paid carve-out, reactivation.
- **Aggregation Suppression Spec — v5** — How aggregate statistics are produced without re-identifying anyone: N=25/50/100 floors, small-cell + complementary suppression.
- **Authorized Agent Process Spec — v5** — How DSRs submitted by an authorized agent are verified (mandatory baseline, heightened for deletion/sensitive) and fulfilled (deliver-to-user by default).

## AI safety / governance
- **AI System Prompt Restrictions — v3** — Guardrails on the coaching AI's behavior, including athlete-to-athlete scope (T&C §9) and the redaction/scrubbing categories.
- **AI Safety Logging Decision — v2** — Decision on what AI-safety events are logged and how.

## DMCA / copyright
- **DMCA Designated Agent Spec — v4** — The §512 notice/counter-notice process and the designated-agent role (Privacy Lead in DMCA capacity; contact info@).
- **DMCA Templates — v2** — Standard notice / counter-notice / user-notification templates.
- **Repeat Infringer Internal Guideline — v2** — Internal, unpublished repeat-infringer determination guideline.

## Implementation specs for Claude Code (`compliance/` package)
- **compliance/00_OVERVIEW** — Index, cross-cutting invariants, control inventory; the package entry point (not part of the repo CLAUDE.md).
- **compliance/INVARIANTS** — Locked constants (windows, thresholds, ages, contacts) + the de-identification-method note.
- **compliance/controls/01–08** — Per-control build specs: 01 AI-training data governance · 02 account deletion · 03 inactivity automation · 04 aggregation suppression · 05 DSR/authorized-agent · 06 breach logging · 07 DMCA · 08 consent/cookies.

## Program tracking
- **Privacy Program Backlog — v17** — Rolling tracker of open/resolved items (blockers, deferred, cleanup). Current open blockers include D-92 (fairness thresholds) and D-95 (ML-processor DPA; provider provisionally Anthropic). D-90 (de-id methodology) is resolved.
- **Semantic Consistency Review — v1** — This session's content-equivalence audit of cross-references.

---

### Two contact addresses (corpus-wide)
- **help@aidstation.pro** — user support, including privacy/data-rights requests.
- **info@aidstation.pro** — formal/legal/security/DMCA correspondence.
