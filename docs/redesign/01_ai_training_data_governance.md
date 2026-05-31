# Control 01 — AI-Training Data Governance

**Source of truth (authoritative):** `AIDSTATION_LIA_PA15` §4.6 (binding safeguards) and §8.1 (engineering deliverables); `AIDSTATION_Privacy_Policy` §4 and §7; `AIDSTATION_RoPA` PA-15; `AIDSTATION_AITraining_Onboarding_Callout_Spec`; `AI_System_Prompt_Restrictions` §3 (scrubbing categories); `AIDSTATION_Inactivity_Automation_Spec` §5.4 (sensitive scrub at de-identification); `AIDSTATION_Aggregation_Suppression_Spec`.
**Backlog:** D-87 (scrubbing), D-88 (sensitive two-class gate), D-89 (lineage), D-90 (de-id methodology — **RESOLVED: rule- and pattern-based redaction**), D-91 (memorization), D-92 (fairness), D-93 (opt-out toggle), D-95 (ML-processor DPA — *contract prerequisite; provider provisionally Anthropic*).

> The legitimate-interest basis for training is valid **only while the §4.6 safeguards are in place**. Every requirement below maps to a §4.6 safeguard; if one is removed or bypassed, the lawful basis lapses. Treat these as invariants, not features.

---

## Purpose

Govern which user data may enter AIDSTATION's own model-training pipeline and under what controls. This control is the gate between the production data store and any training dataset. It does **not** train models; it decides what is eligible and records the lineage.

---

## Requirements

### R1 — Opt-out toggle (D-93, §4.6.1, §8.1)
- Account-settings boolean: "Allow my data to improve AIDSTATION coaching models." Default state = **`AI_TRAINING_DEFAULT`** (opt-in/on) for new users; existing users at feature launch are opt-in with a grandfathering notification and a clear path to the toggle.
- Every toggle change writes an append-only audit row: `{account_id, old_value, new_value, changed_at (UTC), actor}`.
- Opt-out applies **prospectively to all future training pulls** and to ongoing inclusion. It does not (and cannot) remove contributions already baked into deployed model weights — see R8.

### R2 — Training-ingest gate (§8.1)
The job that assembles a training dataset must, per candidate record, verify **all** of:
- (a) account training opt-out is **false**;
- (b) for any special-category field (PP §2.3), the separate **sensitive opt-in is true** (else that field is excluded — see R3);
- (c) account age status is **≥ `MIN_AGE`**;
- (d) deletion status is clear — account is **not** in the `RECOVER_WINDOW` and **not** deleted/de-identified.
A record failing any check is excluded from the dataset. The gate is the only path into a dataset; there is no bypass.

### R3 — Sensitive two-class ingest (D-88, §4.6.2/.3)
- Special-category data never enters a default/general training dataset.
- It may enter a **segregated** sensitive dataset only when **both** the training opt-in (R1) **and** the sensitive opt-in are present (dual opt-in), and only after de-identification or aggregation (R6 / control 04). Raw sensitive data is never used.

### R4 — Free-text scrubbing (D-87, §4.6, §8.1)
- Free-text fields routed to training pass through a redaction pipeline that strips named entities, PII tokens, and restricted-category terms using the categories defined in `AI_System_Prompt_Restrictions` §3.1/§3.2.
- The scrubber's recall must be measured and recorded before any claim of "implemented"; a stated performance threshold (set with the §3 owner) gates go-live.

### R5 — Lineage manifest (D-89, §4.6.6)
- Each training dataset version stores a manifest of contributing records by **pseudonymous ID + version timestamp** (never raw user ID).
- The manifest must answer, by query: *"If user X opts out or is deleted today, which dataset versions include their contributions?"* This supports disgorgement scenarios.

### R6 — De-identification before training (§4.6.3)
- Where used in training, sensitive data is de-identified or aggregated first.
- **Methodology (locked, D-90 resolved): rule- and pattern-based redaction.** Deterministic removal/generalization of identifiers plus pattern/NER-based scrubbing of free-text (this is the same redaction pipeline as R4), with manual review of flagged high-risk content. This is best-effort de-identification, not a formal guarantee — so de-identified training inputs are treated as **pseudonymized** (still personal data), and the lawful basis rests on the §4.6 safeguards, not on an anonymization claim. Build the redaction pipeline and the gate; differential privacy / k-anonymity are explicitly **not** in use at this time.

### R7 — Memorization mitigation & fairness (D-91, D-92, §4.6.5)
- Pipeline applies deduplication and sensitive-content filtering.
- A periodic adversarial memorization probe (held-out data probed for verbatim regurgitation) runs on a documented cadence; results logged.
- A fairness evaluation across sport / experience-level / sex slices runs before model release, against documented release-threshold criteria (D-92). These thresholds are a decision input, not invented here.

### R8 — Irreversibility disclosure (§4.5.2)
- Opt-out / deletion stops **new** use only. Already-trained weights are not unwound. Any user-facing copy describing opt-out or deletion effects on training must reflect this (coordinate with controls 02/03); do not imply weight-level removal.

### R9 — Recipients & processor (§4.6.7) — **contract prerequisite (D-95)**
- Training data is accessible only to ML/engineering roles under role-based access, **logged**.
- **Provider (provisional): Anthropic** — already the named AI inference subprocessor. The ML provider is bound by DPA with **no-training-on-our-data**, **no-derivative-use**, and audit-rights terms; executing that DPA and confirming the SCC-compatible posture remain **open (D-95)**. This is procurement/contract, not code — but the access-logging and role-gating *are* in scope here.

### R10 — Retention boundary (§4.6.8)
- Training datasets are retained for **`TRAINING_DATA_RETENTION`** (model-generation lifetime + ~24-month reproducibility window), then purged. Not indefinite. A scheduled job enforces this.

---

## Data model (sketch — adapt to repo schema)
- `accounts`: `ai_training_opt_out boolean`, `sensitive_opt_in boolean`, `age_verified_16plus boolean`, `lifecycle_state enum` (active / recover_window / deleted / deidentified).
- `training_datasets`: `dataset_version`, `created_at`, `class enum(general|sensitive)`, `retention_expires_at`.
- `training_dataset_manifest`: `dataset_version`, `pseudonymous_id`, `record_version_ts`.
- `audit_log` (append-only): training-toggle changes, ingest-gate decisions (counts, not content), access events.

## Triggers / jobs
- **Toggle handler** → writes audit row, takes effect on next pull.
- **Ingest job** (flagged) → runs R2 gate per record, R3 routing, R4 scrub, R6 de-id hook, writes R5 manifest.
- **Retention job** → enforces R10.
- **Probe/fairness jobs** → R7 on cadence / pre-release.

---

## Acceptance criteria
1. A user with `ai_training_opt_out = true` appears in **no** dataset manifest produced after the toggle change; the toggle change has an audit row with a UTC timestamp.
2. A special-category field never appears in a `class=general` dataset; it appears in a `class=sensitive` dataset **only** when both opt-ins are true and only post-de-identification.
3. A record for an account under `MIN_AGE` is never ingested.
4. A record for an account in `RECOVER_WINDOW` or deleted/de-identified is never ingested.
5. Given a `pseudonymous_id`, a single query returns every `dataset_version` that includes it (R5).
6. Free-text routed to training contains no entities/PII tokens from the `AI_System_Prompt_Restrictions` §3 categories above the agreed recall threshold (R4).
7. Datasets past `retention_expires_at` are purged by the retention job; purge is logged.
8. Access to training data without the ML/engineering role is denied and logged (R9).
9. Re-running any job is idempotent (no duplicate manifest rows, no double-purge errors).

## Out of scope (do not build here)
- Model training itself.
- Fairness thresholds (R7 / D-92) — decision input, still open. (De-identification methodology is now locked — see R6.)
- DPA execution and SCC-posture confirmation with the provider (R9 / D-95) — procurement/contract; provider provisionally Anthropic.

## Dependencies
- Account lifecycle states from control 02 (deletion) and control 03 (inactivity).
- Aggregation/de-identification primitives shared with control 04.
- Open decision D-92 (fairness thresholds); open contract D-95 (DPA execution; provider provisionally Anthropic). D-90 de-identification methodology is resolved (rule- and pattern-based redaction).
