# Compliance Invariants — Locked Constants

Every value here is a policy commitment, not an implementation default. Control specs reference these by name (e.g., "RECOVER_WINDOW"). **Do not change a value to suit an implementation.** If a value looks wrong, flag it against its source document; don't edit it here.

| Name | Value | Applies to | Source of truth |
|---|---|---|---|
| `MIN_AGE` | 16 years | Eligibility; training ingest gate; underage removal | T&C §2, PP §11 |
| `AI_TRAINING_DEFAULT` | opt-in (on by default) | New and existing users, with always-available opt-out | LIA §8.1, PP §4 |
| `RECOVER_WINDOW` | 14 days | Account deletion — user can cancel by logging in | Deletion Flow Spec, PP §7 |
| `ERASURE_DEADLINE` | within 30 days of the deletion request | Active-system erasure (GDPR Art. 12(3) one-month limit) | Deletion Flow Spec, PP §7 |
| `DSR_COMPLEX_EXTENSION` | up to +2 months, with notice | Deletion/DSR for genuinely complex requests only | PP §9.1/§14.2 |
| `BACKUP_PURGE_WINDOW` | within 90 days (rolling) | Backups; beyond-use until purged; restore re-applies deletion | Deletion Flow Spec, PP §7 |
| `INACTIVITY_NOTIFY` | 18 months of inactivity | First de-identification warning to user | Inactivity Automation Spec, PP §7 |
| `INACTIVITY_DEIDENTIFY` | 24 months of inactivity | De-identification (pseudonymized retention, **not** anonymization) | Inactivity Automation Spec, PP §7 |
| `DSR_RESPONSE` | within 30 days (+`DSR_COMPLEX_EXTENSION`) | Data-subject rights responses | PP §9.1/§14.2 |
| `AGG_MIN_COHORT` | N = 25 | Aggregation suppression — baseline cohort floor | Aggregation Suppression Spec |
| `AGG_MIN_COHORT_SENSITIVE` | N = 50 | Aggregation suppression — special-category cohort floor | Aggregation Suppression Spec |
| `AGG_MIN_COHORT_TIMESERIES` | N = 100 | Aggregation suppression — time-series cohort floor | Aggregation Suppression Spec |
| `DMCA_RETENTION` | 7 years from final action on the matter | DMCA notice + handling records | DMCA Designated Agent Spec, RoPA PA-16 |
| `TRAINING_DATA_RETENTION` | model-generation lifetime + ~24 months reproducibility | Training datasets (not indefinite) | RoPA PA-15, LIA §4.6(8) |
| `COOKIE_CONSENT_EXPIRY` | 12 months | Cookie consent — re-prompt after expiry | Cookie Policy §4, Cookie Banner Spec |
| `CONTACT_SUPPORT` | `help@aidstation.pro` | User support incl. privacy/data-rights requests | (corpus-wide, 2026-05-30 directive) |
| `CONTACT_FORMAL` | `info@aidstation.pro` | Formal/legal/security/DMCA correspondence | (corpus-wide, 2026-05-30 directive) |
| `GOVERNING_LAW` | Texas; Johnson County venue | Disputes (general); DMCA federal = N.D. Tex. | T&C §19, T&C §8.6 |

**De-identification method (D-90, resolved).** De-identification across the program (inactivity retention, training inputs) is **rule- and pattern-based redaction** — best-effort, not a formal guarantee. De-identified records are therefore **pseudonymized** and remain personal data. Differential privacy and k-anonymity are not in use; aggregate suppression (control 04) provides the statistical safeguard for *published aggregates*.

**Breach windows** (see Breach Response Playbook for the full matrix): regulator notification within 72h of awareness (Art. 33); subprocessor → AIDSTATION 12h preliminary / 24h full (DPA §4.7). Encoded in control 06, not duplicated as single constants here.
