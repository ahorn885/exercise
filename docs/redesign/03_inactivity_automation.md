# Control 03 — Inactivity Automation

**Source of truth (authoritative):** `AIDSTATION_Inactivity_Automation_Spec`; `AIDSTATION_Privacy_Policy` §7. Couples with control 04 (aggregation) via §5.4.
**Constants:** `INACTIVITY_NOTIFY`, `INACTIVITY_DEIDENTIFY`.

## Purpose
Automate the inactivity lifecycle: warn at 18 months, de-identify at 24 months. De-identification here is **pseudonymization with strong-identifier removal — not anonymization**; the result is still personal data.

## Requirements
- **R1 — Clock.** Drive off `last_active_at`. For paid subscribers the clock starts from the **later of** `last_active_at` **or** the subscription end date (an active subscription itself counts as activity).
- **R2 — 18-month notice.** At `INACTIVITY_NOTIFY` of inactivity, send the de-identification warning to the user.
- **R3 — 24-month de-identification.** A **daily idempotent batch** processes accounts where `last_active_at` is older than `INACTIVITY_DEIDENTIFY` **AND** the account is not in `recover_window`/`deletion_in_progress` **AND** no active paid subscription exists.
- **R4 — Strong-identifier scrub.** Remove name, email, contact fields; **hard-delete** `auth_credentials_*` (password hashes, federated links, refresh tokens); truncate `date_of_birth` to year (to a 5-year band if sensitive-category data was present — see R5).
- **R5 — Sensitive-category scrub (§5.4).** Remove sensitive-category flags from the anonymous athlete record at de-identification. (Asymmetric cost-benefit: marginal aggregate value vs. catastrophic re-identification exposure on Art. 9 data.)
- **R6 — Retained, re-linked.** Activity data continues to exist, no longer linked to a person, joined to a stable `pseudonymous_athlete_id` derived from a **one-way hash**. It remains personal data under the Privacy Policy until/unless genuinely anonymized.
- **R7 — Opt-out carry-forward.** Training/research opt-out state carries forward via the tombstone link so de-identified records stay excluded from training (control 01) and aggregation populations (control 04).
- **R8 — Reactivation.** Logging in before de-identification resets the clock (account returns to active); the scheduled de-identification is cancelled.
- **R9 — Logging.** After de-identification, log entries for the account use `tombstone_id`/`pseudonymous_athlete_id`, never the original user ID.

## Data model (sketch)
- `accounts.last_active_at`, `subscription_end_at`, `lifecycle_state` (shares enum with control 02; add `deidentified`).
- `pseudonymous_athlete_id` (one-way hash); `inactivity_notified_at`.

## Triggers / jobs
- Daily inactivity batch (flagged, idempotent): R2 notices, R3 eligibility, R4–R6 scrub/re-link, R9 logging.
- Login handler → R8 reset.

## Acceptance criteria
1. The 18-month notice fires once per eligible account; not re-sent on every batch run.
2. De-identification runs only when the account is >24 months inactive, not in a deletion state, and not a paying subscriber.
3. After de-identification: name/email/contact gone, `auth_credentials_*` hard-deleted, DOB truncated (5-year band if sensitive was present), sensitive-category flags removed.
4. Retained activity data is reachable only via `pseudonymous_athlete_id`; no path back to the original identity.
5. A login before de-identification resets the clock and cancels the scheduled job.
6. An opted-out user's de-identified record is excluded from training and aggregation populations.
7. The batch is idempotent.

## Out of scope
- Genuine anonymization (irreversible) — not claimed; this is pseudonymized retention.

## Dependencies
- Lifecycle states from control 02; aggregation population rules in control 04; opt-out semantics from control 01.
