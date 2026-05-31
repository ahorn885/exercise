# AIDSTATION Compliance Controls — Implementation Specs

**Audience:** Claude Code (and human engineers).
**Purpose:** Turn the finalized AIDSTATION privacy/compliance rules into buildable engineering specs. Each control is one spec under `controls/`. This package is self-contained: it does not modify or depend on the repo's root `CLAUDE.md`.

---

## How to use this package

1. **Read this file and `INVARIANTS.md` first.** They carry the shared context and the locked constants every control depends on.
2. **Implement one control at a time** by reading its spec in `controls/` and building to its **Acceptance Criteria**. Invoke as, e.g., *"implement `compliance/controls/01_ai_training_data_governance.md`."*
3. **The source-of-truth document named in each spec is authoritative.** These specs are thin on purpose — they state engineering requirements and point back to the policy/legal doc that defines the rule, rather than restating it (restating would create a second copy that drifts). If a build spec and its source document ever disagree, **the source document wins — stop and flag it** rather than guessing.
4. **Do not change the locked values in `INVARIANTS.md`** to make an implementation convenient. They are policy commitments. If one seems wrong, flag it; don't edit it.

---

## Non-negotiable invariants (apply to every control)

These hold across the whole system. A change that violates one is a compliance regression, not a refactor.

- **Two contact addresses only.** `help@aidstation.pro` (user support, incl. privacy/data-rights requests) and `info@aidstation.pro` (formal/legal/security/DMCA). No other outbound or published address.
- **Opt-out is always honored.** AI-training is on by default, but a user opt-out must take effect prospectively on every subsequent training pull. There is no state in which opt-out is ignored.
- **Sensitive categories never train without explicit, separate opt-in.** Special-category data (PP §2.3) must never reach a default training dataset. Dual opt-in (account training opt-in *and* sensitive opt-in) is required, and even then only to a segregated dataset.
- **Deleted and cooling-off data is never ingested.** Any record whose account is in the deletion recover window or past it is excluded from training pulls, exports for reuse, and aggregation populations.
- **Pseudonymized ≠ anonymized.** De-identified/pseudonymized records are still personal data and remain subject to the Privacy Policy. Do not treat a pseudonymized record as out of scope.
- **Aggregation suppression thresholds are hard floors**, not targets. Output below the threshold is suppressed, not rounded or approximated.
- **Every state transition that affects a user's data rights is logged** with a timestamp and an actor (system or user), in an append-only audit trail. Logs reference pseudonymous/tombstone IDs after de-identification, never the original user ID.
- **All times are UTC.** All windows (recover, erasure, DSR, retention) are computed in UTC.
- **Raw conversation transcripts are never retained**, and therefore are never available to any control here. Only parsed coaching notes exist downstream.

---

## Control inventory

Build order is roughly by dependency and risk. Status reflects whether the engineering spec in this package is written yet — not whether the feature is built.

| # | Control | Implements | Source of truth | Backlog | Spec status |
|---|---|---|---|---|---|
| 01 | AI-training data governance | opt-out + default-opt-in, ingest gate, sensitive two-class gate, lineage, scrubbing, memorization/fairness | LIA §4.6/§8.1, PP §4, RoPA PA-15, AITraining Onboarding Callout, AI System Prompt Restrictions §3 | D-87–D-93, D-95 | ✅ written |
| 02 | Account deletion flow | recover window, erasure cascade, deletion ledger, backup re-apply | Deletion Flow Spec, PP §7 | D-74 (built spec) | ✅ written |
| 03 | Inactivity automation | 18/24-mo lifecycle, de-identification, §5.4 sensitive scrub, tombstone, paid carve-out, reactivation | Inactivity Automation Spec, PP §7 | — | ✅ written |
| 04 | Aggregation suppression engine | N=25/50/100 thresholds, complementary suppression, parameter-signature controls | Aggregation Suppression Spec | — | ✅ written |
| 05 | DSR / rights handling | access/export/correct/delete, 30-day clock (+60 complex), authorized-agent verification | PP §9/§14, Authorized Agent Process Spec | — | ✅ written |
| 06 | Breach logging & record-keeping | Art. 33(5) incident log, assessment waypoints, retention | Breach Response Playbook §6/§7/§12.1 | — | ✅ written |
| 07 | DMCA handling | notice intake, repeat-infringer counter, 7-yr-from-final-action retention, takedown excludes from training | DMCA Designated Agent Spec, Repeat Infringer Guideline | D-99–D-103, D-106 | ✅ written |
| 08 | Consent & cookie mechanics | cookie consent (12-mo expiry), GPC honoring, opt-out state model | Cookie Policy §4, Cookie Banner Spec | — | ✅ written |

Some items have non-code prerequisites. For control 01: the de-identification methodology is now **locked to rule- and pattern-based redaction** (D-90 resolved); the ML-processor is **provisionally Anthropic** with DPA execution still open (D-95); and the fairness-release thresholds remain open (D-92). Control 07 needs USCO registration. These are called out in each spec's **Dependencies** and are not things Claude Code builds.

---

## Stack & conventions (assumed from project context — adjust to the actual repo)

- **Backend:** Python; **PostgreSQL with JSONB**, Neon-hosted.
- **Migrations:** additive, reversible, one migration per schema change; never edit a shipped migration.
- **Idempotency:** all scheduled jobs (inactivity, erasure cascade, ingest gating) must be safe to re-run; use explicit state columns, not implicit "did this already" inference.
- **Feature flags:** AI-training ingest and inactivity automation run behind flags so they can be enabled per-environment.
- **Audit logging:** append-only; see the per-control logging requirements and the global invariant above.
- **Time:** UTC everywhere; store timestamps as `timestamptz`.

This package is referenced *from* the repo's existing `CLAUDE.md` (a one-line pointer is enough); it does not duplicate or replace it.
