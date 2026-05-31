# AIDSTATION Pre-Flight Checklist — First Scaled AI Training Run (PA-15)

**Status:** v2 — cross-reference unversioning cleanup; draft for counsel review (no substantive change since v1)
**Owner:** Privacy Lead
**Date:** May 19, 2026
**Purpose:** Verifies that all `AIDSTATION_DPIA_PA15` §7.3 and `AIDSTATION_LIA_PA15` §5.1 conditions are operationally in place before authorizing the first scaled training run under PA-15.
**Binding nature:** This checklist is binding, not advisory. Sign-off by Privacy Lead AND Engineering Lead is required before the first scaled training run on real user data may proceed. The DPIA's Conditional Proceed outcome and the LIA's Art. 6(1)(f) reliance both depend on this sign-off. Documentation alone — including this checklist completed in name only — does not authorize scaled training.

**Companion docs:** `AIDSTATION_DPIA_PA15` (§7.3 operational-validity gate, §8.2 conditions and action items), `AIDSTATION_LIA_PA15` (§5.1 operational-validity gate), `Privacy_Program_Backlog_v2.md` (D-87 through D-95 engineering deliverables, D-94 onboarding callout, D-96 this checklist).

---

## 1. Scope and Trigger Conditions

### 1.1 When this checklist runs

- Before the first scaled training run on real user data under PA-15.
- Before resuming scaled training after any §5–§7 condition has lapsed (e.g., a processor change, a disclosure regression, a §4.6 safeguard degradation).
- On any material change in PA-15 data inventory, purpose, or population — re-run required regardless of prior sign-off.

### 1.2 What "scaled training" means here

- **Not gated** by this checklist: evaluation-only work; synthetic-data-only work; small-scale internal experiments that do not ingest real user data; any work covered by separately-bounded Art. 9(2)(a) special-category opt-in flows.
- **Gated** by this checklist: any training run that ingests non-special-category user data at production scale, where "production scale" means a population larger than that needed for a documented evaluation experiment, or any run where the output is intended to be deployed to users.
- The boundary between "small-scale evaluation" and "scaled training" is not absolute. If the question arises whether a planned run is gated or not, the default is gated — re-run this checklist.

### 1.3 What "operationally in place" means

For each condition, "operational" means:
- The capability exists in the production system, not a development or staging environment alone.
- It is documented sufficiently that a different engineer could verify it.
- It has been exercised at least once in production-like conditions (smoke test, dry run, or live operation) within the last 90 days.

"Documented but not verified in production-like conditions" is not operational.

---

## 2. Sign-Off Required From

| Role | Name | Date | Signature |
|---|---|---|---|
| Privacy Lead | | | |
| Engineering Lead | | | |
| DPO (where appointed for EU/UK launch) | | | |

Sign-off block is completed in this file at the time of authorization. A snapshot of the file (with completed sign-offs and condition statuses) is retained in the privacy program file set. The retained snapshot version is referenced from the training run record.

Sign-off is single-shot, not standing. A subsequent training run requires a re-run of this checklist; an existing sign-off does not carry forward across condition changes or material PA-15 changes.

---

## 3. Pre-Flight Conditions — Engineering (from DPIA §7.3)

For each condition: status, evidence reference (document, log, or system), verifier initials, date verified.

Status legend: ✅ Operational, ⚠️ Partially Operational (must be resolved before proceeding), ❌ Not Met.

### 3.1 Condition E-1: Free-text scrubbing pipeline (D-87, R-03 / R-10)

- **Verification standard:** Pipeline implemented. Audit run on a representative sample of training-bound free-text records confirms scrubbing of identifier categories listed in `AI_System_Prompt_Restrictions` §3.1 / §3.2. False-negative rate in sample audit is at or below documented acceptable bound (initial bound TBD by engineering; recorded in Engineering Pre-Flight Notes).
- **Evidence:** sample-audit report, scrubbing pipeline code/config version, false-negative rate.

| Status | Evidence ref | Verifier | Date |
|---|---|---|---|
| | | | |

### 3.2 Condition E-2: Sensitive-category two-class ingest gate (D-88, R-03)

- **Verification standard:** Ingest gate classifies records into a default "non-special" path and a separate "special-category opt-in" path. Routing verified in non-production environment with synthetic-data tests covering each special category named in `AIDSTATION_RoPA` PA-15. Any record without an active special-category opt-in is rejected from the special-category path.
- **Evidence:** test-run logs, ingest gate code/config version, routing test pass record.

| Status | Evidence ref | Verifier | Date |
|---|---|---|---|
| | | | |

### 3.3 Condition E-3: Training dataset lineage manifest (D-89, R-05)

- **Verification standard:** Manifest exists for the planned training dataset version. Manifest names per-source provenance (which RoPA source activities supplied each record category), the as-of timestamp of each source extract, the scrubbing pipeline version applied, and the opt-out cohort snapshot used for exclusion. The manifest is queryable for right-of-access requests.
- **Evidence:** manifest file location, manifest schema version, last manifest regeneration timestamp.

| Status | Evidence ref | Verifier | Date |
|---|---|---|---|
| | | | |

### 3.4 Condition E-4: Memorization mitigation suite (D-91, R-01)

- **Verification standard:** Deduplication, sensitive-content filter, and adversarial probing protocol are all implemented. Adversarial probing has been run against a representative model checkpoint at the documented cadence (initial cadence TBD; recorded in Engineering Pre-Flight Notes). Probing results are within the documented acceptable bound.
- **Evidence:** dedup config, sensitive-content filter config, latest adversarial probing report.

| Status | Evidence ref | Verifier | Date |
|---|---|---|---|
| | | | |

### 3.5 Condition E-5: Fairness evaluation suite (D-92, R-06)

- **Verification standard:** Evaluation suite implemented. Release threshold criteria documented. Suite has been run against a representative model checkpoint within the last 90 days; results recorded.
- **Evidence:** evaluation suite code/config version, release threshold doc, latest run report.

| Status | Evidence ref | Verifier | Date |
|---|---|---|---|
| | | | |

### 3.6 Condition E-6: Account-settings opt-out toggle (D-93, R-04)

- **Verification standard:** Toggle is live in production. Default state for new users is opt-in per `AIDSTATION_LIA_PA15` §8.1. Toggle changes are timestamped and logged. End-to-end dry run confirms that a toggle change to off stops ingest of the user's data into the next training dataset version (verified via lineage manifest cohort comparison).
- **Evidence:** toggle production version, toggle log location, dry-run verification report.

| Status | Evidence ref | Verifier | Date |
|---|---|---|---|
| | | | |

### 3.7 Condition E-7: ML processor selection and DPA (D-95, R-07 / R-11)

- **Verification standard:** ML processor (or in-house infrastructure) selected. SCC-compatible DPA executed where a processor is engaged. Contract includes no-training-on-our-data and no-derivative-use restrictions. Transfer mechanism documented for any cross-border transfer.
- **Evidence:** executed DPA reference, processor identity, transfer mechanism note.

| Status | Evidence ref | Verifier | Date |
|---|---|---|---|
| | | | |

---

## 4. Pre-Flight Conditions — Disclosure and Rights (from LIA §5.1)

### 4.1 Condition D-1: Disclosure live to users

- **Verification standard:** `AIDSTATION_Privacy_Policy` §4 / §7 / §9 and `AIDSTATION_Terms_and_Conditions` §8.2 are published with effective dates that precede the planned training run. Live URLs accessible.
- **Evidence:** PP live version, T&C live version, effective dates.

| Status | Evidence ref | Verifier | Date |
|---|---|---|---|
| | | | |

### 4.2 Condition D-2: Opt-out functional end-to-end

- **Verification standard:** A user-initiated toggle change to off propagates to the training dataset cohort exclusion within the documented latency bound. Verified via dry run with a test account; the test account's data does not appear in the next training dataset version's lineage manifest.
- **Evidence:** dry-run report, latency bound document, test account ID/timestamp.

| Status | Evidence ref | Verifier | Date |
|---|---|---|---|
| | | | |

### 4.3 Condition D-3: In-product onboarding callout (D-94)

- **Verification standard:** Onboarding callout per `AIDSTATION_AITraining_Onboarding_Callout_Spec` is implemented in the signup flow for new users. Copy reviewed against the spec (lane selected, irreversibility acknowledgment present, opt-out toggle on the same screen). Salience tested — i.e., the callout is on its own screen, not buried in a TOS scroll, not interstitial during an unrelated flow.
- **Evidence:** signup flow screenshot/screen-recording reference, copy version, salience test note.

| Status | Evidence ref | Verifier | Date |
|---|---|---|---|
| | | | |

### 4.4 Condition D-4: Right-of-access tooling for training lineage

- **Verification standard:** Tooling exists to answer a right-of-access request about whether a specific user's data was included in a specific training dataset version, within the DSR response window (30 days globally per PP §14.2). Backed by the lineage manifest from E-3. Operational capacity has been smoke-tested at request volume that exceeds expected steady-state DSR rate.
- **Evidence:** tooling location, smoke-test report, capacity bound.

| Status | Evidence ref | Verifier | Date |
|---|---|---|---|
| | | | |

---

## 5. Pre-Flight Conditions — Documentation and Process

### 5.1 Condition P-1: LIA reviewed by counsel; sign-off recorded

- **Verification standard:** `AIDSTATION_LIA_PA15` §11 Approval Block is signed by counsel. Sign-off date precedes the planned training run.
- **Evidence:** signed LIA reference.

| Status | Evidence ref | Verifier | Date |
|---|---|---|---|
| | | | |

### 5.2 Condition P-2: DPIA reviewed by counsel; sign-off recorded

- **Verification standard:** `AIDSTATION_DPIA_PA15` §8.3 sign-off table completed by Privacy Lead and Engineering Lead at minimum; DPO sign-off recorded where DPO is appointed; counsel review noted.
- **Evidence:** signed DPIA reference.

| Status | Evidence ref | Verifier | Date |
|---|---|---|---|
| | | | |

### 5.3 Condition P-3: No material change since last LIA/DPIA review

- **Verification standard:** No material change has occurred since the LIA / DPIA sign-off in: PA-15 data inventory (per RoPA PA-15), purposes of processing, population of data subjects, sensitive-category opt-in mechanism, or transfer destinations. Verifier reviews the PA-15 entry in current RoPA against the version cited by LIA / DPIA and confirms no diff.
- **Evidence:** RoPA version check, diff log (or "no diff" attestation).

| Status | Evidence ref | Verifier | Date |
|---|---|---|---|
| | | | |

### 5.4 Condition P-4: Annual review schedule on file

- **Verification standard:** Next LIA review date and next DPIA review date are recorded in the privacy program file set. Both dates are within 12 months of the prior review date or sooner per `AIDSTATION_LIA_PA15` §7.
- **Evidence:** review calendar entry references.

| Status | Evidence ref | Verifier | Date |
|---|---|---|---|
| | | | |

---

## 6. Outcome

### 6.1 If all 15 conditions are ✅ Operational

Authorize first scaled training run under PA-15. Sign-off block in §2 is completed and dated. A snapshot of this completed checklist is retained in the privacy program file set and referenced from the training run record. Engineering proceeds with the planned run.

### 6.2 If any condition is ⚠️ Partially Operational or ❌ Not Met

Authorize NOT given. Document the specific gap in §7 Engineering Pre-Flight Notes. State the remediation plan and owner. Re-run this checklist when remediation is complete. **No partial authorization is available.** The LIA's Art. 6(1)(f) reliance and the DPIA's Conditional Proceed outcome are joint — partial readiness does not yield partial reliance.

### 6.3 Outcome record

| Outcome | | |
|---|---|---|
| Decision | ☐ Authorize ☐ Not authorized | |
| Decision date | | |
| Snapshot file reference | | |
| Training run record reference | | |

---

## 7. Engineering Pre-Flight Notes

A free-form section for the engineering lead and privacy lead to record context for the sign-off:

- Bounds chosen for E-1 false-negative rate, E-4 probing cadence, D-2 opt-out propagation latency.
- Open variances and how they were resolved (or why they're considered acceptable for this run).
- Any condition where evidence is borderline — what tipped it to ✅ vs ⚠️.
- Anything the next pre-flight reader should know.

---

## 8. Operational Discipline Notes

- **This checklist is binding, not advisory.** Treat any pressure to soft-launch as a re-run trigger. "Small-scale test that's almost scaled" is gated.
- **Sign-off carries the weight of Art. 6(1)(f) reliance.** If conditions are signed off as met when they are not, the LIA's reliance becomes structurally invalid even if every other document says otherwise. The exposure is not paper; it is a real legal basis problem.
- **A failed pre-flight is the gate working as designed.** The cost of failing is delay. The cost of bypassing is a structurally invalid LI basis and an unprovable DPIA conclusion. Delay is cheaper.
- **Re-run on material change.** Material changes between scheduled annual reviews trigger an ad-hoc re-assessment of LIA + DPIA + this checklist before the next scaled training run.

---

## 9. Cross-Spec Touchpoints

| Document | Relationship |
|---|---|
| `AIDSTATION_DPIA_PA15` §7.3 / §8.2 | Source of engineering conditions E-1 through E-7. Conditional Proceed outcome conditioned on this checklist. |
| `AIDSTATION_LIA_PA15` §5.1 / §8.1 | Source of disclosure/rights conditions D-1 through D-4 and the default-opt-in posture verified in E-6 / D-3. |
| `AIDSTATION_RoPA` PA-15 | Definitive data inventory for P-3 no-material-change check. |
| `AIDSTATION_Privacy_Policy` §4 / §7 / §9 / §14.2 | Disclosure baseline (D-1) and 30-day DSR window referenced by D-4. |
| `AIDSTATION_AITraining_Onboarding_Callout_Spec` | Spec for the D-3 in-product callout. |
| `AIDSTATION_Deletion_Flow_Spec` §6.2 | Trained-weights irreversibility statement that the §5.1 / DPIA §7.3 / this checklist together back-stop. |
| `AI_System_Prompt_Restrictions` §3.1 / §3.2 | Category list reused by the E-1 scrubbing pipeline. |
| `Privacy_Program_Backlog_v2.md` D-87 through D-95 | Engineering deliverables that produce the E-1 through E-7 capabilities. |

---

## 10. Change Log

| Version | Date | Changes | Author |
|---|---|---|---|
| v1 | May 19, 2026 | Initial pre-flight checklist for PA-15 first scaled training run. Operationalizes the validity gate referenced from DPIA v2 §7.3 / §8.2 and LIA §5.1. Eleven engineering / disclosure conditions plus four documentation / process conditions, totaling fifteen. Binding-not-advisory framing. Outcome is all-or-nothing — no partial authorization. | Privacy Lead |

---

*Cross-reference cleanup (v2, 2026-05-30): inline references to companion documents were converted to unversioned logical names per Rule #12, so they no longer go stale when a companion document is revised. No substantive content changes. See `Privacy_Program_Consistency_Sweep_Report_v1.md`.*

