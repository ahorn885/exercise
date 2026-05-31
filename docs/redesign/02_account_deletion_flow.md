# Control 02 — Account Deletion Flow

**Source of truth (authoritative):** `AIDSTATION_Deletion_Flow_Spec`; `AIDSTATION_Privacy_Policy` §7; `AIDSTATION_RoPA` PA-13 (deletion-event logging), PA-16 (DMCA records survive); `AIDSTATION_LIA_PA15` §4.5.2 (trained-weights irreversibility).
**Constants:** `RECOVER_WINDOW`, `ERASURE_DEADLINE`, `BACKUP_PURGE_WINDOW`, `DSR_COMPLEX_EXTENSION`.

## Purpose
Implement self-service account deletion that is reversible for a short window, completes active-system erasure inside the GDPR one-month limit, and handles backups as a recognized beyond-use exception.

## Requirements
- **R1 — Request.** On delete, mark the account for deletion, sign the user out, and enter `recover_window`. Record `deletion_requested_at` (UTC).
- **R2 — Recover.** Logging in during `RECOVER_WINDOW` (14 days) cancels the deletion and restores the account to `active`.
- **R3 — Erasure.** After the recover window the account moves to `deletion_in_progress`, login is disabled, and the backend cascade runs so that **active-system erasure completes within `ERASURE_DEADLINE` (30 days of the original request)** — *not* a fresh 30-day clock after the window. `DSR_COMPLEX_EXTENSION` applies only to genuinely complex requests, with notice.
- **R4 — Cascade + tombstone.** Erase personal data across all tables; reduce the account to a tombstone row retained indefinitely: `tombstone_id` (random, **not** derived from any user identifier) + deletion metadata only. The tombstone supports audit/statistics without identifying data.
- **R5 — Backups.** Backups are not selectively edited; data in them is purged on the rolling cycle within `BACKUP_PURGE_WINDOW` (90 days) and is treated as beyond-use until then. If a backup is restored, the deletion ledger is consulted and the deletion is re-applied before the data is live.
- **R6 — Logging.** Deletion events are logged **without preserving deleted content** (RoPA PA-13); post-deletion log entries reference `tombstone_id`, never the original user ID.
- **R7 — Trained weights.** Deletion stops new use of the user's data in future training (coordinate with control 01); weights already trained are not unwound. User-facing copy must reflect this (PP §7, LIA §4.5.2) — do not imply weight-level removal.
- **R8 — Legal retention.** Retain the minimum required by law (tax, fraud) outside the erasure scope; document each exception.
- **R9 — DMCA carry-through.** Deletion does not reverse DMCA actions; PA-16 notice records persist (control 07).

## Data model (sketch)
- `accounts.lifecycle_state enum(active|recover_window|deletion_in_progress|tombstone)`, `deletion_requested_at timestamptz`.
- `tombstones(tombstone_id, deleted_at, reason)`.
- `deletion_ledger(tombstone_id|account_ref, applied_at, scope)` — consulted on backup restore.

## Triggers / jobs
- Delete handler → set `recover_window`, sign out, schedule transition.
- Recover handler → login in window cancels.
- Erasure job (flagged, idempotent) → window-expiry → cascade → tombstone, all within `ERASURE_DEADLINE`.
- Backup-restore hook → re-apply deletion ledger before data goes live.

## Acceptance criteria
1. Login within 14 days of request restores the account to `active`.
2. After 14 days login is disabled and the cascade runs; active-system erasure completes ≤30 days from the **original request** (verify the clock is anchored to request, not window-expiry).
3. The tombstone contains no value derivable from a user identifier.
4. A restored backup has the user's data re-erased before it is reachable.
5. Deletion events are logged with `tombstone_id` and no deleted content.
6. Re-running the erasure job is idempotent.

## Out of scope
- Category-level (partial) deletion — deferred per the Deletion Flow Spec gut check.

## Dependencies
- Lifecycle states shared with controls 01 and 03; DMCA records in control 07.
