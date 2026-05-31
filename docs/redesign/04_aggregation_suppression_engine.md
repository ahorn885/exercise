# Control 04 — Aggregation & Suppression Engine

**Source of truth (authoritative):** `AIDSTATION_Aggregation_Suppression_Spec`. Couples with control 03 (§5.4 sensitive-flag removal) and control 01 (opt-out exclusion).
**Constants:** `AGG_MIN_COHORT` (25), `AGG_MIN_COHORT_SENSITIVE` (50), `AGG_MIN_COHORT_TIMESERIES` (100).

## Purpose
Construct, query, and share aggregate statistics so no individual is identifiable. Thresholds are **hard floors**, not targets: output below a floor is suppressed, not rounded.

## Requirements
- **R1 — Cohort floors.** Baseline `AGG_MIN_COHORT` (25); special-category cohorts `AGG_MIN_COHORT_SENSITIVE` (50); longitudinal/time-series cohorts `AGG_MIN_COHORT_TIMESERIES` (100). The lower of "applies" never wins — sensitive or time-series classification raises the floor.
- **R2 — Small-cell suppression.** Applied to every shared aggregate.
- **R3 — Complementary suppression.** When a cell is suppressed, suppress enough additional cells that the suppressed value cannot be recovered from row/column margins or complements.
- **R4 — Quasi-identifier discipline (§7).** Evaluate combined-attribute (quasi-identifier) risk; suppress narrow subpopulations where the attribute combination makes the floor insufficient. This — not the baseline number — is the real residual-risk lever.
- **R5 — Population exclusion.** Records with training/research opt-out, and de-identified records whose sensitive flags were removed (control 03 §5.4), are excluded from the relevant aggregate populations. Consequence: some sensitive-category aggregates in small disciplines are simply unshippable — that is intended.
- **R6 — Research opt-out durability (§9).** Research opt-out is durable across re-consent: a later settings change or unrelated re-consent does **not** re-opt-in to research sharing absent an explicit, separately captured re-opt-in.
- **R7 — Internal-viewer parity (§11.3).** Internal viewers (founder, board, analysts, product) are subject to the same suppression as external consumers. Override only via a documented pathway: time-bounded grant, recorded reason, dual-control approval, mandatory audit-log entry.
- **R8 — Audit-log parameter-signature hashing (§10).** Aggregation-query audit logs hash the parameter signature for sensitive cohort definitions (sensitive-category, top-N performer, sub-state geographic); verbatim parameter values retained only when the cohort `N ≥ 100`. Suppressed queries are themselves logged.

## Architecture (per §… implementation pattern)
Choose among pre-aggregation views, query rewriting, and post-query suppression; suppression must occur at the service boundary regardless of internal path.

## Data model (sketch)
- Aggregation runs against pseudonymous records; `research_opt_out`, `training_opt_out` flags propagate from controls 01/03.
- `aggregation_audit_log`: query, cohort size, suppressed?(bool), parameter signature (hashed unless N≥100), viewer, override-grant ref.

## Acceptance criteria
1. Any output cohort below its applicable floor is suppressed (25 baseline / 50 sensitive / 100 time-series).
2. Suppressed cells cannot be back-derived from published margins (complementary suppression verified).
3. Opted-out and sensitive-flag-removed records are absent from the relevant populations.
4. A research opt-out survives a subsequent unrelated re-consent.
5. An internal viewer sees the same suppression as an external consumer; an override exists only with a dual-control, time-bounded, audited grant.
6. Sensitive cohort query logs store a hashed parameter signature unless N≥100; suppressed queries are logged.

## Out of scope
- The baseline-N policy choice (locked at 25 per the spec gut check) — do not re-tune.

## Dependencies
- Opt-out/de-identified population flags from controls 01 and 03.
