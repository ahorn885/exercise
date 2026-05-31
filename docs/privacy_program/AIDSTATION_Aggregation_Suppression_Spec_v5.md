# AIDSTATION Aggregation & Suppression Logic — Design Spec

**Status:** v5 — cross-reference unversioning cleanup (no substantive change since the v3 Tier 2 lens pass) — inactivity-coupling terminology aligned to de-identification / pseudonymized (no threshold or method change)
**Companion docs:** Privacy Policy §§3, 5, RoPA PA-12 (research data sharing), Inactivity Automation Spec §5
**Implements:** Decision #5 (N=25 threshold), Decision #6 (pseudonymized + DPA + IRB + opt-out for research), Decision #4 (two-track consent for secondary use), Decision #13 (aggregated data survives deletion / de-identification)
**Lens applied:** May 20, 2026

---

## Lens Calibration Notes (v4)

Five positions in this spec are the lens-relevant judgment calls. Counsel should be directed here on review.

1. **N=25 baseline (§3 Threshold rationale, §6.1).** Selected as the industry-defensible middle, not the regulator-strictest position. The pure operator-favorable position is the lowest N that survives review (the more aggregates shippable, the more product value); the strictest-applicable position would bump baseline to N=50 or higher in line with the most aggressive EDPB technical-guidance hints. AIDSTATION's chosen baseline N=25 reflects that the real residual-risk lever in this spec is not the baseline number — it is §7 quasi-identifier handling and §7.5 sensitive-category bump to N=50, which already operate at the strictest defensible level. Bumping baseline from 25 to 30 or 50 would cascade through PP, RoPA, Inactivity Spec, and DPA-referenced positions; the marginal lens benefit is small relative to that coordination cost. The defensible position is N=25 baseline + N=50 sensitive + strict quasi-identifier discipline. Counsel may revisit if a specific jurisdiction signals dissatisfaction with N=25 as a baseline; reversal would be a coordinated edit, not a structural rework.

2. **§7.5 coupling with Inactivity Spec §5.4.** Sensitive-category flags are removed from pseudonymized athlete records at de-identification (Inactivity Spec §5.4). The population for sensitive-category aggregates therefore consists only of *living* accounts with active sensitive opt-in. The N=50 threshold becomes harder to achieve in some cohorts — particularly in the small underserved disciplines AIDSTATION targets (modern pentathlon, swimrun, skimo). Some sensitive-category aggregates will simply be unshippable. This is the deliberate consequence of the layered lens position across both specs; it is operator-favorable on the breach-exposure side (catastrophic-cost reduction) and product-cost-bearing on the aggregate-availability side (a few statistics we cannot publish). The cost-benefit math is in favor of the breach-side reduction. See Inactivity Spec Lens Calibration Note 2 for the upstream half of this trade.

3. **§9 research opt-out durability (v3 tightened).** Opt-out from research data sharing is durable across re-consent flows. A user who opts out, later updates account settings, or later re-consents to other things (e.g., marketing) does not re-opt-in to research sharing absent an explicit and separately captured re-opt-in. v2 spec was silent on the re-consent case; v3 closes that ambiguity. Operator-favorable: small loss of research dataset population. Lawful: aligns with EDPB guidance on consent specificity. Single global rule: applies regardless of jurisdiction.

4. **§10 audit log parameter signature hashing (v3 added).** Audit logs for aggregation queries currently store parameter values verbatim. v3 introduces parameter-signature hashing for sensitive cohort definitions (sensitive-category parameters, top-N performer parameters, sub-state geographic parameters) — full values retained verbatim only when the corresponding cohort N ≥ 100. Rationale: an internal log-store breach should not leak which narrow cohorts were queried, even where the queries themselves were suppressed at the service boundary. This is an operational engineering tightening; the substantive privacy commitment is unchanged.

5. **§11.3 internal-viewer parity (v3 promoted to explicit).** Internal viewers (founder, board, analysts, product team) are subject to the same suppression rules as external consumers. Privacy/security team override is permitted only via a documented pathway: time-bounded grant, recorded reason, dual-control approval, mandatory audit-log entry. v2 implied this as a footnote; v3 makes it an explicit policy.

---

## 1. Purpose and Scope

This spec defines how AIDSTATION constructs, queries, and shares aggregate statistics derived from athlete data so that no individual is identifiable through the aggregates. The N=25 minimum and small-cell suppression are the primary safeguards. The spec also addresses the harder problem: re-identification risk in longitudinal training data and combined-attribute risk that may make N=25 insufficient in narrow subpopulations.

In scope:

- Architecture: where in the stack aggregation and suppression live
- Implementation pattern (pre-aggregation views, query rewriting, post-query suppression)
- Suppression response (silent vs. annotated)
- Re-identification risk model and mitigations
- Combined-attribute / quasi-identifier handling
- Audit logging of suppressed queries
- Integration with research data sharing (PA-12)
- Future-state options (differential privacy)

Out of scope:

- Internal access to raw (non-aggregated) data — governed by the access control matrix in the RoPA, not by this spec
- Specific analytics provider choice — covered by the Cookie Banner Spec
- Data warehouse vs. operational database trade-offs — implementation detail
- **Whether AIDSTATION publishes user-facing aggregates at v1 launch.** This is a product decision, not a privacy decision. This spec applies whenever aggregates are published. The v1-publication question is tracked in the Privacy Program Backlog as a product gate. The privacy commitments in PP §§3, 5 reference "aggregate statistics, when shared" — the conditional wording is intentional and remains accurate whether v1 publishes or defers.

---

## 2. Inherited Decisions

| Item | Decision | Source |
|---|---|---|
| Minimum aggregate group size (baseline) | N=25 | #5 |
| Minimum aggregate group size (sensitive-category cohorts) | N=50 | #5, this spec §7.5 |
| Small-cell suppression | Applied to every shared aggregate | #5 |
| Aggregates survive deletion | Yes | #13 |
| Research data is pseudonymized + DPA + IRB + opt-out | Yes | #6, #7 |
| Research opt-out is durable across re-consent (v3 added) | Yes | This spec §9 |
| Two-track consent: pseudonymized requires consent; true anonymized aggregates outside personal data scope | Yes | #4 |

---

## 3. What Counts as an "Aggregate"

An aggregate is a statistic computed across multiple users in a way that does not return any individual's data. Examples:

- Median training volume per week for athletes preparing for a 100-mile ultramarathon
- Distribution of injury types reported in the last 12 months across all users
- Average heart-rate-zone time for a given age band

Non-aggregates (governed by access control, not by this spec):

- An individual user's training log
- A teammate's view of another teammate's data (governed by sharing permissions in the eventual team-based feature, which is athlete-to-athlete only — no human-coach role; see T&C §10)
- A user's own export of their own data

The aggregation/suppression layer applies to any query that produces summary statistics intended to be shown to anyone other than the user themselves or a specifically authorized internal role.

### 3.1 Threshold Rationale (v3 added)

The N=25 baseline + N=50 sensitive-category pair was selected as the position most defensible across all applicable jurisdictions, not the operator-maximum and not the regulator-strictest. The reasoning:

- **Baseline at N=25.** Industry-recognized middle. Survives review under GDPR, CCPA/CPRA, Quebec Law 25, and the major sectoral frameworks AIDSTATION encounters. A baseline lift to N=30 or N=50 is defensible but creates cascading edits across the doc set (Privacy Policy, RoPA, DPA references, this spec, Inactivity Spec) for marginal regulator-defense improvement. The upstream lever for residual re-identification risk in this spec is §7 quasi-identifier handling, not the baseline N.
- **Sensitive cohorts at N=50.** Higher threshold reflects the asymmetric exposure cost on Art. 9 / sensitive-category data (DPA §7(d)(ii) uncapped liability; Breach Playbook §7.2 default-toward-Art. 34 notification; regulatory penalty multiplier). The lens position here is unambiguously stricter than baseline.
- **N=100 floor for time-series.** §8.1 longitudinal mitigations apply N=100 to weekly granularity. Longitudinal data is fingerprint-like; the strict floor reflects that.

The single global rule applies: same thresholds across all jurisdictions, calibrated to defend everywhere.

---

## 4. Use Cases

| Use Case | Audience | Aggregation Layer Applies? |
|---|---|---|
| Marketing-site "athletes who trained for X reported Y" statistics | Public | Yes |
| In-app peer benchmarks (e.g., "your weekly volume vs. similar athletes") | Authenticated user | Yes |
| Research dataset shared with university partners | Researchers under DPA | Yes (plus pseudonymization) |
| Internal product metrics (DAU, retention, feature usage) | Internal product team | Yes |
| Operational health metrics (error rates, latency) | Internal eng | No (these don't contain personal data) |
| Customer support viewing a specific user's account | Support agent under access control | No (this is direct access, not aggregate) |
| Individual user viewing their own data | The user | No |

---

## 5. Architecture

The aggregation and suppression layer lives between the primary database (Postgres on Neon) and any consumer of aggregate statistics. It is implemented as:

```
┌─────────────────────────────────────────────────────┐
│ Consumers                                            │
│  - Marketing site stats endpoint                     │
│  - In-app peer benchmark UI                          │
│  - Research export pipeline                          │
│  - Internal product analytics                        │
└─────────────────────────────────────────────────────┘
                       │
                       ▼
┌─────────────────────────────────────────────────────┐
│ Aggregation Service                                  │
│  - Whitelist of pre-aggregated queries (views)       │
│  - Suppression layer (N<25 → suppress / annotate)    │
│  - Combined-attribute check (Section 7)              │
│  - Audit log (with parameter signature hashing —     │
│    v3 §10.1)                                         │
└─────────────────────────────────────────────────────┘
                       │
                       ▼
┌─────────────────────────────────────────────────────┐
│ Pre-Aggregation Views in Postgres                    │
│  - Materialized views with N counts attached         │
│  - Refreshed on a schedule (nightly)                 │
└─────────────────────────────────────────────────────┘
                       │
                       ▼
┌─────────────────────────────────────────────────────┐
│ Primary database (Postgres / Neon)                   │
│  - Full athlete data, access controlled              │
└─────────────────────────────────────────────────────┘
```

Key properties:

- No consumer queries the primary database directly for aggregate purposes. The aggregation service is the only path.
- The aggregation service does not support arbitrary SQL. It supports a whitelist of named, parameterized queries — each of which is reviewed when added and stored as a materialized view with an attached row count.
- The suppression layer is applied at the service boundary, not at the database. Even if a materialized view exposes N<25, the service refuses to return it.
- All queries are logged regardless of outcome, with sensitive cohort parameters hashed in the log per §10.1.

This design rejects the alternative of "let analysts run arbitrary SQL and apply suppression at query time" because:

- Arbitrary SQL is the source of most re-identification incidents in practice. Even well-intentioned analysts construct queries that join attributes in re-identifying ways.
- Suppression at query time is hard to make correct against composed queries (the analyst runs many small queries and combines their answers).
- A whitelist forces deliberate review of every new aggregate before it goes live.

The cost is friction: adding a new aggregate requires a code change. This is acceptable at our scale and is consistent with the data minimization principle.

---

## 6. Suppression Behavior

When a query returns a row (or set of rows) where N<25 (baseline; N<50 for sensitive-category cohorts per §7.5; N<100 for weekly time-series per §8.1):

### 6.1 Action: Annotated Suppression

The row is returned with the values replaced by a suppression marker, not silently dropped, and not surfaced as an error. Example:

```json
{
  "cohort": "100-mile ultra, female, 40-49",
  "median_weekly_volume_km": "<suppressed: n<25>",
  "n": "<suppressed>"
}
```

Reasoning:

- Silent drop makes it impossible for the consumer to know whether the cohort is empty or suppressed. This is misleading.
- Returning an error is too disruptive for the in-app peer-benchmark UI; users would see "request failed" when the real meaning is "we don't have enough peers like you to show useful stats."
- Annotated suppression is honest: the cohort exists, but we don't have enough data points to show statistics safely.

### 6.2 The N Itself Is Suppressed

We do not return the actual N for suppressed cells, only that it is below the applicable threshold. This prevents the cohort-size attack where an attacker can iterate through dimension values and recover the underlying distribution of cohort sizes.

For non-suppressed cells (N at or above the applicable threshold), we return either:

- The exact N, when N is large enough that revealing it does not enable re-identification (typically when N ≥ 100), or
- A binned N ("25–49", "50–99", "100+") for smaller cells

### 6.3 Suppression of Derived Cells (v3 generalized)

If a result set has multiple cohorts (e.g., a breakdown by age band), suppression on one cell can sometimes be reversed by subtraction if the total across cohorts is also reported. The suppression layer must check:

- **General rule (v3).** No linear combination of returned cells, totals, or sub-totals shall recover the value of any suppressed cell to within the applicable suppression threshold. The suppression layer evaluates each result set as a linear system and suppresses additional cells until no suppressed cell is uniquely recoverable.
- **Operational shorthand for the common case.** When any cell in a breakdown is suppressed and a total is reported, suppress the second-smallest cell as well unless that cell is also already protected. This is the "complementary suppression" rule from official statistics and is correct for single-row breakdowns with one suppressed cell.
- **Multi-row case.** Where multiple cells are suppressed across multiple breakdowns or hierarchical levels (e.g., breakdowns by age within sex within sport), suppression coverage is computed iteratively until the linear-recovery property holds across the whole result set. The aggregation service implements this as a post-query check, not a query-time guarantee.

The shift from v2 to v3 is generalizing from "second-smallest cell in the breakdown" to "no linear combination recovers a suppressed value." v2 covers the basic case correctly; v3 catches the harder multi-row recoverability problem.

### 6.4 The "Empty Cohort" Distinction

If a cohort has 0 athletes (genuinely empty), we may report N=0 explicitly. The user-relevant signal is "there are no athletes in this cohort," not a privacy concern. The distinction:

- N=0: report as 0
- 1 ≤ N < applicable threshold: suppress
- N ≥ applicable threshold: report

The N=0 case is permitted because reporting an empty cohort does not narrow any individual's identifiability — it confirms the absence of athletes meeting the criteria. Where the enumeration of "absent cohorts" could itself leak (e.g., systematically querying all (sport, region, year-band) combinations to map sparse populations), the audit-log analysis in §10.2 surfaces the pattern for review.

---

## 7. Combined-Attribute / Quasi-Identifier Risk

The N=25 (or N=50 for sensitive) threshold protects against the simplest re-identification attack. It does not protect against attacks that combine multiple attributes to narrow a cohort to a single person.

Example: a cohort defined as "60-year-old female pentathletes located in Wyoming" may have N ≥ 25 nationally for some other sport, but in pentathlon specifically with that age band and that state, the cohort may be 1 or 2 people, both of whom are publicly identifiable as competitors in their region.

### 7.1 Quasi-Identifier List

The following attributes are treated as quasi-identifiers — combinations of them are tracked for cohort-size impact:

- Sex
- Year of birth (or age band)
- Country (or, more granular: state/province)
- Primary sport / discipline
- Race targets (specific named races are highly identifying)
- Body composition extremes (top/bottom 1% of weight, height, etc.)
- Performance-stat extremes (top 1% in a metric)
- Disability or adaptive-sport status
- Specific health conditions

### 7.2 K-Anonymity on Quasi-Identifiers

For any aggregate that includes quasi-identifier breakdowns, the suppression layer additionally requires k-anonymity ≥ 25 within the combination (≥ 50 for sensitive-category cohorts per §7.5). That is:

- "Athletes preparing for the Cocodona 250" is a cohort defined by a specific named race. If fewer than 25 athletes are in that cohort, the whole row is suppressed — even if the parent set is large.
- Named races below the N=25 threshold are aggregated to a broader category ("ultras 200+ miles in North America").

### 7.3 Geographic Granularity

The default location granularity for aggregates is country. State/province is permitted only when the resulting cohort is N ≥ 25 even at that granularity. ZIP code, city, or finer location is never permitted in shared aggregates.

For research datasets (Section 9), the same rule applies, with state allowed when justified by the research question and approved under IRB.

### 7.4 Temporal Granularity

Aggregating by week is fine. Aggregating by specific date is fingerprinting — an attacker who knows when a user trained can pick them out. Default temporal granularity is week or coarser. Specific date is allowed only for race-day aggregates where the race itself is the public event.

### 7.5 Sensitive-Category Cohorts

Aggregates that cohort by a sensitive category (specific health condition, biometric extremes) require N ≥ 50, not N ≥ 25, and are subject to a privacy-team review before being added to the whitelist.

**v3 coordination with Inactivity Spec §5.4.** Sensitive-category flags are removed from pseudonymized athlete records at de-identification (Inactivity Spec §5.4). The population for sensitive-category aggregates therefore consists only of living accounts with active sensitive opt-in. The N=50 threshold becomes harder to satisfy in small populations — particularly in the underserved disciplines AIDSTATION targets. Where N=50 cannot be reached even after broadening the cohort along non-sensitive dimensions, the aggregate is unshippable. This is the deliberate consequence of the layered lens position and is operator-favorable on the breach-exposure side (see Lens Calibration Note 2).

---

## 8. Re-Identification Risk in Longitudinal Data

Training data over time is fingerprint-like even at modest N. Two athletes with similar profiles may have nearly identical weekly volumes, but their week-by-week patterns will diverge. An attacker who observes (publicly, e.g., from Strava) a user's weekly volume pattern over several weeks can match it against an "anonymized" research dataset and re-identify with high confidence.

### 8.1 Longitudinal Risk Mitigations

For any aggregate that exposes time-series structure:

- Default temporal granularity is monthly, not weekly. Weekly is permitted only when cohort N ≥ 100.
- Specific values are rounded to coarse buckets (e.g., weekly volume rounded to nearest 25 km; weekly TSS rounded to nearest 50).
- "Top performers" cohorts are particularly risky because top performance is publicly visible. Top-1% or top-5% cohorts are not permitted to be sub-cohorted by quasi-identifiers in shared aggregates.

### 8.2 Pseudonymized Research Datasets

For research datasets (Section 9), longitudinal data is shared with full granularity because the research question often requires it. The protections are different:

- Pseudonymization (per Decision #6) — direct identifiers replaced with research IDs
- DPA constrains what the researcher may do
- IRB approval scopes the research question
- Opt-out lets users exclude their data; opt-out is durable across re-consent flows (§9)

The shared dataset is documented as "pseudonymized," not "anonymized," in the DPA and consent flow. We do not represent these datasets as immune to re-identification — the safeguards are contractual and procedural, not mathematical.

This is consistent with Decision #4's two-track consent model.

---

## 9. Integration with PA-12 (Research Data Sharing)

The research-data-sharing pathway adds:

- Pseudonymization is the primary safeguard; aggregation is secondary
- Research datasets include longitudinal data with full granularity
- N=25 / k-anonymity rules still apply to any published aggregates from research output, not to the raw research dataset itself
- IRB approval is required before a dataset is shared
- DPA constrains researcher use
- Users have opt-out (Decision #7); opted-out users are excluded from the dataset before it is generated

### 9.1 Opt-Out Durability (v3 added)

Research-sharing opt-out is durable across re-consent flows. Specifically:

- A user who opts out of research sharing remains opted out across all subsequent re-consent prompts, marketing-preference changes, or account-setting updates, unless the user explicitly and separately re-opts-in to research sharing.
- An explicit re-opt-in must be a specifically-labeled consent action; it cannot be bundled with other consent items or implied by accepting an updated Privacy Policy.
- The system retains an opt-out audit trail. If a user re-opts-in after a prior opt-out, the trail records both events and the timestamp of each.
- De-identification at inactivity (per Inactivity Spec §5) does not reset opt-out — the pseudonymized athlete record carries forward the opt-out state via the tombstone link, and the pseudonymized data is excluded from research exports regardless.

This closes a v2 ambiguity. Operator-favorable cost: marginal reduction in research dataset population. Lawful: aligns with EDPB guidance on consent specificity and granularity. Single global rule: applies everywhere.

The aggregation service supports a "research export" path that performs the pseudonymization and emits the dataset to a controlled destination. The same suppression/k-anonymity checks are applied when the research dataset is used to publish summary statistics (which the researcher commits to under the DPA).

---

## 10. Audit Logging

Every query to the aggregation service is logged:

| Column | Notes |
|---|---|
| `query_id` | UUID |
| `consumer` | `marketing_site`, `in_app_benchmark`, `research_export`, `internal_analytics`, etc. |
| `caller_principal` | Service identity (not end-user) |
| `query_name` | The named whitelisted query |
| `parameters_or_signature` | Parameter values (verbatim if cohort N ≥ 100) or parameter signature (hash) — see §10.1 |
| `result_n` | Bin: `n<25`, `25-49`, `50-99`, `100+`, or `0` |
| `suppression_applied` | Boolean; reason if true |
| `quasi_identifier_check` | Boolean (passed / failed) |
| `timestamp` | UTC |

### 10.1 Parameter Signature Hashing (v3 added)

The `parameters_or_signature` column stores parameter values according to the following rule:

- If the cohort the query targets has N ≥ 100 (verified at materialized-view level), parameters are stored verbatim. Verbatim storage at this size has acceptable re-identification risk.
- If the cohort has N < 100, OR if any parameter is a sensitive-category attribute (regardless of cohort size), OR if any parameter is a top-N performer selector or sub-state geographic selector, parameters are stored as a deterministic salted hash signature (`HMAC(audit_log_pepper, query_name || parameter_tuple)`). The verbatim values are not retained in the log.
- A separate, more restrictively access-controlled "parameter resolution" table holds the (signature → verbatim) mapping for at most 30 days, accessible only to the privacy and security teams under the §11.3 override pathway. After 30 days the mapping is hard-deleted; signatures in the audit log remain searchable by signature equality but cannot be resolved back to parameter values.

Rationale: an internal log-store breach should not leak which narrow cohorts were queried, even where the queries themselves were suppressed at the service boundary. The 30-day mapping window preserves operational debugging value (a real privacy or security incident in that window can be investigated by resolving signatures); after that, the parameter values are not recoverable from the audit log.

### 10.2 Retention and Analysis

Logs are retained for 18 months for tuning and audit. Aggregate analysis of these logs (which queries are most often suppressed, which parameter combinations trigger quasi-identifier failures) feeds back into curating the whitelist and tightening the aggregation views.

Log analysis findings to surface periodically:

- Queries that are suppressed >50% of the time should be redesigned (the cohort is too narrow)
- Quasi-identifier checks failing on common parameter combinations should prompt revisions to the parameter constraints
- Patterns of "enumeration" queries (e.g., systematic sweeps across all parameter combinations) are flagged for human review even if individually suppressed — this catches attacker behavior that the per-query suppression check cannot

---

## 11. Specific Implementation Notes

### 11.1 Materialized Views with Embedded N

Each whitelisted aggregate has a corresponding materialized view in Postgres. The view includes the result columns plus an `n_count` column representing the cohort size. The aggregation service reads the view, applies the suppression check on `n_count`, applies the quasi-identifier check on the cohort definition, and returns the result.

Materialized views are refreshed nightly (low traffic period). For aggregates where freshness matters (in-app peer benchmarks), refresh can be more frequent. Caching at the service layer reduces database load.

### 11.2 Parameter Constraints

Each whitelisted query has constrained parameters:

- Allowed values for categorical parameters
- Allowed bin ranges for numeric parameters (no narrow custom ranges that effectively select an individual)
- Maximum number of dimension breakdowns in a single query (recommend: max 3)

These constraints are part of the query definition and are enforced before the underlying view is consulted.

### 11.3 Internal Viewers and Privacy/Security Override (v3 promoted to explicit policy)

Internal viewers — founder, board members, product analysts, support — query the aggregation service under the same suppression rules as external consumers. There is no "internal eyes" bypass. Suppressed cells are suppressed in internal dashboards exactly as in user-facing surfaces.

A privacy-team or security-team principal may be granted access to non-suppressed query output for a specific audit or investigation purpose. The override pathway is:

- **Grant.** A documented reason, including the specific suspected issue or audit objective.
- **Approval.** Dual control: two privacy-team or security-team principals must approve, neither acting alone.
- **Time bound.** The grant expires after 72 hours by default; longer durations require re-approval.
- **Scope bound.** The grant applies to a specific named query or query family, not blanket access.
- **Logging.** The grant itself is logged in the audit log with the principal, reason, dual-approver IDs, and expiration. All queries executed under the grant are logged with explicit reference to the grant ID.
- **Review.** The privacy team reviews all overrides at each batch boundary (alongside the §10.2 log analysis).

v2 implied this via a footnote ("Exception: a privacy-team or security-team principal may be granted access … logged and reviewed separately"). v3 makes it an explicit policy.

### 11.4 Performance

Aggregation queries are fast because they read materialized views. Latency budget: p99 < 200ms for in-app benchmark queries. The suppression layer adds negligible overhead. The §10.1 parameter signature hashing adds approximately one HMAC computation per query — negligible.

---

## 12. Future-State Options

### 12.1 Differential Privacy

Differential privacy adds calibrated noise to aggregate statistics such that the presence or absence of any single individual does not measurably change the output. This is a stronger guarantee than k-anonymity and is now industry-deployed (US Census, Apple, Google).

We are not implementing differential privacy at v1 because:

- It adds substantial implementation complexity for limited initial benefit
- N=25 + k-anonymity + quasi-identifier checks cover the common attack model
- It is much easier to add as a wrapper around the existing aggregation service in v2 if needed

Re-evaluate when:

- We have a research collaboration that requires it as a condition
- A regulator suggests it as part of an enforcement action or guidance
- A re-identification incident occurs that would have been mitigated by it

### 12.2 Synthetic Data Generation

For research-data-sharing use cases, synthetic-data techniques can produce datasets that preserve statistical structure without sharing real records. This is a future option for cases where pseudonymized real data is too sensitive to share even under DPA. Out of scope for v1.

---

## 13. Open TBDs

- Specific list of whitelisted queries to ship at launch (depends on which marketing-site stats and in-app benchmark features ship)
- Refresh cadence per materialized view (operational tuning)
- Privacy-team review process for adding new whitelisted queries (defer to operational SOPs)
- IRB partner identification for research datasets (operational, not privacy decision)
- Whether to expose the suppression status in user-facing UI ("not enough peers to show benchmarks") — recommend yes, friendly version
- **v3 follow-up: Audit log `parameter_resolution` table 30-day deletion job.** Engineering ticket — automated job to expire and hard-delete entries in the parameter resolution mapping table after 30 days. Should ship before the aggregation service serves production traffic.
- **v3 follow-up: Privacy-team override SOP.** Operational document defining the dual-control approval interface for §11.3 overrides — who has the override credentials, how the dual-control is captured in tooling, the standard review cadence at batch boundaries.
- **v3 follow-up: §6.3 multi-row linear-combination suppression — reference implementation.** The general rule "no linear combination shall recover a suppressed value" needs a reference implementation in the aggregation service. The basic "second-smallest cell" heuristic covers single-row breakdowns; multi-row recoverability requires solving a small linear system per result set. Engineering review needed.

---

## 14. Gut Check

**Risks.**

- The §6.3 generalization to "no linear combination shall recover a suppressed value" is correct in principle but operationally trickier than v2's single-row "suppress the second-smallest cell" heuristic. The reference implementation called out in §13 needs to be built before the aggregation service ships. If left as a principle without a reference implementation, individual aggregate queries will rely on ad-hoc analyst judgment about which extra cells to suppress, and that is exactly the failure mode the spec's whitelist-only design is supposed to prevent.
- The §7.5 + Inactivity Spec §5.4 coupling means some sensitive-category aggregates that v2 contemplated will not be shippable under v3 (sensitive flags removed at de-identification shrinks the cohort). This is intentional but it is a real product cost. If the v1 publication decision (§1 out of scope) includes sensitive-category aggregates, that subset of aggregates may have to be designed without the pseudonymized-population contribution. Coordinate with product on which v1 aggregates rely on sensitive flags.
- The N=25 baseline remains the most exposed lens position. The single-global-rule lens calibrates to the strictest applicable framework, and N=25 sits in the industry middle, not at the strictest hint. If counsel returns with a specific jurisdiction case for N=30 or N=50 baseline, the lift is a coordinated edit across this spec, PP, RoPA, Inactivity Spec, and any other documents that name the baseline. Reversal cost is non-trivial but bounded; structural rework is not needed.
- The §10.1 parameter signature hashing introduces an operational dependency on the 30-day resolution-table deletion job. If that job fails silently, parameter values remain recoverable indefinitely, and the privacy commitment is degraded without anyone noticing. The deletion job needs alerting on failure as a first-class operational concern.

**What might be missing.**

- A documented procedure for handling a re-identification incident — what if a user contacts us and demonstrates that they can identify themselves in a published aggregate? Currently nothing. Should be added to the Breach Response Playbook (operational item).
- Adversarial testing: do we ever run a red-team exercise that tries to re-identify users from our own aggregates? Probably not at v1 scale. Worth scheduling annually after launch.
- The opt-out durability rule (§9.1) is correctly stated but does not specify the user-facing mechanism for re-opting-in. The implication is "there is no re-opt-in flow until product builds one"; that should be stated explicitly so that re-consent flows don't accidentally bundle research opt-in by default.

**Best argument against the current trajectory.**

The "publish no aggregates at v1" alternative remains real. The §1 out-of-scope expansion moves the publication decision out of this spec, but it does not resolve it — the privacy commitment in PP §§3, 5 is conditional ("aggregates, when shared"), so deferring publication keeps that wording accurate. If v1 ships without published aggregates, this entire engineering build (whitelist service, materialized views, suppression layer, parameter signature hashing, dual-control overrides) can move to the post-launch backlog. The infrastructure is genuinely substantial; the user-value case at v1 (a hundred-user platform cannot produce meaningful in-app peer benchmarks anyway because cohorts are too small) is weak.

**Counter:** the research-data-sharing pathway under PA-12 has its own value independent of user-facing aggregates. If we want any research collaborations at v1, parts of the spec (pseudonymization, opt-out durability, IRB integration, audit logging) need to be live. The whitelist suppression service for *user-facing* aggregates can defer; the *research-export pathway* may not be able to. This argues for a phased build: research pathway first (with simpler internal aggregation suppression for the publication checks the researcher commits to), user-facing aggregate service second.

This phasing decision is product-shaped, not privacy-shaped. The spec is correctly silent on the timing; the privacy commitments survive either ordering.

---

## 15. Change Log

| Version | Date | Changes | Author |
|---|---|---|---|
| v1 (Batch 4) | (Batch 4 date) | Initial draft. Established N=25 baseline, N=50 for sensitive cohorts, whitelist-only architecture, quasi-identifier handling, longitudinal mitigations, integration with PA-12 research sharing. Internal label "Draft v1, Batch 4." | Privacy Lead |
| v2 | (Batch 8 cycle) | File bumped to v2 in filename only; internal status label remained "Draft v1, Batch 4." Companion-doc references still pointed at PP / RoPA / Inactivity Spec. No substantive changes recorded. | Privacy Lead |
| v3 | May 20, 2026 | Tier 2 lens pass (operator-favorable + lawful + single global rule). Internal label reconciled to v3. Companion-doc references updated to PP, RoPA, Inactivity Spec. Lens Calibration Notes added (five counsel-risk callouts). Substantive lens edits: **§6.3 complementary suppression generalized from "second-smallest cell in the breakdown" to "no linear combination shall recover a suppressed value"; multi-row recoverability problem now explicitly addressed**. **§9.1 added: research opt-out is durable across re-consent flows; explicit re-opt-in required, with audit trail**. **§10.1 added: parameter signature hashing for sensitive cohort definitions; verbatim parameters retained only when cohort N ≥ 100; separate 30-day parameter resolution table under privacy/security override pathway**. **§11.3 internal-viewer override promoted from footnote to explicit policy with dual control, time bound (72h default), scope bound, logging, batch-boundary review**. §3.1 threshold rationale subsection added documenting why N=25 baseline + N=50 sensitive + N=100 time-series remain the chosen positions. §7.5 v3 coordination paragraph added: sensitive-category cohort population now excludes anonymized records per Inactivity Spec §5.4 — some sensitive-category aggregates become unshippable. §1 expanded: v1-publication question is product-decision out of scope; spec applies when aggregates ship. §10.2 enumeration-pattern detection added to log-analysis findings. §13 v3 follow-ups added: 30-day deletion job, override SOP, multi-row suppression reference implementation. §14 Gut Check updated to reflect v3 changes; "publish no aggregates at v1" counter-argument refined to a phased-build framing. (Privacy Program Backlog: Tier 2 lens batch — Aggregation Spec lens pass per Track A G2 Closing Handoff §5.4, D-119.) | Privacy Lead |
| v5 | May 30, 2026 | Terminology alignment (Andy's directive): references to the inactivity-outcome population reworded from "anonymous/anonymized" to **de-identification / pseudonymized**, matching Inactivity Spec v6 and the Privacy Policy. Genuine irreversible-aggregate language ("true anonymized aggregates outside personal data scope," §6.2-type) and the deliberate "pseudonymized, not anonymized" contrast are unchanged. No threshold, suppression-logic, or methodology change. | Privacy Lead |

---

*Cross-reference cleanup (v4, 2026-05-30): inline references to companion documents were converted to unversioned logical names per Rule #12, so they no longer go stale when a companion document is revised. No substantive content changes. See `Privacy_Program_Consistency_Sweep_Report_v1.md`.*

