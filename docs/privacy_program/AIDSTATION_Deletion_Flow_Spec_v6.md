# AIDSTATION Self-Service Deletion Flow — Design Spec

**Status:** v6 — deletion flow made GDPR-compliant: recover window + active-system erasure within the Art. 12(3) one-month limit (resolves D-129); v5 was the cross-reference unversioning cleanup
**Companion docs:** `AIDSTATION_Privacy_Policy` §6 / §7, `AIDSTATION_RoPA` PA-09 (DSR fulfillment) and PA-16 (DMCA), `AIDSTATION_LIA_PA15` §4.5.2 / §8.1 (trained-weights irreversibility and opt-out behavior), `AIDSTATION_DMCA_Designated_Agent_Spec` (DMCA process), `AIDSTATION_Breach_Response_Playbook` (logging conventions)
**Implements:** Decision #12 (self-service deletion in app), Decision #11 (retention model), Decision #13 (aggregated data survives), Decision #8 (crowdsourced facility carve-out), Decisions #27–28 (verification)

---

## 1. Purpose and Scope

This spec defines the in-app self-service deletion flow that AIDSTATION provides to all users in all launch jurisdictions. The flow satisfies the published commitment in the Privacy Policy that users can delete their account directly from the app without filing a request.

In scope:

- UX flow and screen content
- Cooling-off mechanics
- What survives deletion and what does not
- Authorization checks and verification
- Backup handling
- Logging and audit
- Operational fallback when self-service fails

Out of scope:

- Authorized agent deletion (Spec 4 of Batch 4 covers this)
- Inactivity-triggered de-identification (Spec 2 covers this)
- Backend implementation language, framework, or library choices

---

## 2. Inherited Decisions

The following are locked from the privacy program and not re-derived here:

| Item | Decision | Source |
|---|---|---|
| Mechanism | Self-service in app, not request-only | #12 |
| Cooling-off (recover window) | 14 days — cancel by logging back in | Privacy Policy §7 |
| Max processing time | Active-system erasure within 30 days of the request (GDPR Art. 12(3) one-month limit; extendable up to two further months for genuinely complex requests, with notice) | #26 |
| Backup purge | 90-day rolling | #11 |
| Survives deletion | Aggregated/de-identified data, crowdsourced facility content (identity unlinked) | #13, #8 |
| Raw AI conversations | Not stored, nothing to delete | #13 |
| Identity verification | Email confirmation for low-risk; additional check for deletion | #27, #28 |
| Logging | Deletion events logged without preserving deleted content | Privacy Policy §7, RoPA PA-13 |

---

## 3. Deletion Scope Decision

**Decision needed:** category-level deletion (delete only HR data, only training logs, etc.) or full-account-only at launch?

**Recommendation: full-account only at v1.** Reasoning:

- Category-level deletion is a substantial engineering effort: each category needs an identified set of tables/columns, a tested cascade, and UI to explain consequences. Doing this badly produces a confusing user state (e.g., training plans referencing deleted body composition entries).
- The privacy commitments do not require category-level deletion. Users have the right to deletion of their personal data — granularity inside the account is a product choice, not a legal requirement.
- Sensitive-category opt-out (health data, biometric data) at toggle level already covers the most common reason a user would want partial deletion. Switching a sensitive category off stops collection and triggers deletion of that category's data per the toggle behavior.
- Full-account deletion is straightforward to implement, easy to audit, and easy to explain.

**Defer to v2:** category-level deletion, when there is signal that users actually want it and the engineering cost can be justified.

This spec proceeds on the full-account-only assumption.

---

## 4. User Flow

### 4.1 Entry Point

Settings → Account → Delete Account. Located at the bottom of the Account section, after billing and below "Export My Data."

### 4.2 Confirmation Screen

The user lands on a confirmation screen with the following content blocks:

**Header**

> Delete your AIDSTATION account

**What happens body copy**

> When you confirm deletion:
>
> - Your account will be marked for deletion and you will be signed out.
> - You have **14 days** to change your mind. Log in within that window to cancel.
> - If you don't cancel, your personal data is permanently erased from our active systems, and the whole process completes within **30 days** of your request — the maximum period allowed under data-protection law. Anything in routine backups is purged within 90 days as those backups roll over.
> - **What we keep:** statistical aggregates that include data points from your account but do not identify you, and gym/facility entries you contributed to our crowdsourced database (no longer linked to your name).
> - **What we do not keep:** your profile, training history, body composition entries, performance stats, plan history, and account credentials.
> - If you have an active paid subscription, we will cancel it. You will not be billed further. Refunds for unused time follow our billing policy.

**Choice block** — two buttons of equal visual weight:

- `Cancel` (primary tone, low risk)
- `Continue to delete`

### 4.3 Verification Screen

Triggered by `Continue to delete`. The user must:

1. Re-authenticate by entering their password (or completing the second-factor challenge if 2FA is enabled).
2. Type the literal string `DELETE` into a confirmation field. This is a friction step and is intentional.
3. Tick a checkbox: "I understand my account will be permanently deleted after the 30-day cancellation window."

The `Confirm deletion` button is disabled until all three steps are satisfied.

If the user is on a federated login (Google, Apple), they re-authenticate through the identity provider before reaching this screen.

### 4.4 Post-Confirmation State

On `Confirm deletion`:

1. Account status flips to `pending_deletion` with a timestamp.
2. The user is signed out of all sessions across all devices.
3. A confirmation email is sent to the account-of-record address (template below).
4. The account cannot be used to log in normally — login attempts surface a recovery screen instead.

### 4.5 Recovery During Cooling-Off

If the user attempts to log in during the 30-day window:

> Your account is scheduled for deletion on [date].
>
> If this was a mistake, you can cancel deletion and restore full access.
>
> [Cancel deletion] [Sign out]

Cancel deletion re-authenticates the user, flips status back to `active`, logs the cancellation, and sends a confirmation email.

After the 14-day recover window, the account moves to `deletion_in_progress` and login is no longer possible.

### 4.6 Final Deletion

`deletion_in_progress` triggers the backend cascade. Erasure completes within 30 days of the original request — i.e., the cascade runs within the time remaining after the 14-day recover window, not a fresh 30-day clock (typically much sooner):

- Personal data is hard-deleted from primary stores per the deletion inventory (Section 6).
- Backups containing the data continue to exist until their rotation window (≤90 days) expires; they are not selectively edited.
- Deletion completion is logged and a final confirmation email is sent to the account-of-record address.

After deletion completion, the account record itself is reduced to a tombstone (Section 7).

---

## 5. Email Templates

### 5.1 Deletion Confirmed (sent at confirmation)

> Subject: Your AIDSTATION account is scheduled for deletion
>
> Hello,
>
> We have received your request to delete your AIDSTATION account. Your account is now marked for deletion and you have been signed out.
>
> **You have until [date, 14 days from now] to change your mind.** Log in any time before that date to cancel the deletion.
>
> If you do not log in by [date], we will permanently delete your personal data from our active systems. Routine backups containing your data will be purged within 90 days as backups roll over.
>
> If you did not request this deletion, log in immediately and cancel.
>
> — The AIDSTATION team

### 5.2 Deletion Cancelled

> Subject: Your AIDSTATION account deletion has been cancelled
>
> Hello,
>
> You cancelled the deletion of your AIDSTATION account. Your account is fully active again. No data was deleted.

### 5.3 Deletion Completed

> Subject: Your AIDSTATION account has been deleted
>
> Hello,
>
> As requested, your AIDSTATION account has been deleted. Your personal data has been removed from our active systems. Any data remaining in routine backups will be purged within 90 days as those backups roll over.
>
> We are sorry to see you go. If you change your mind, you are welcome to create a new account at any time, but you will not be able to recover the data from this account.

---

## 6. Deletion Inventory

Authoritative list of data classes and their disposition. This list must stay in sync with RoPA PA-09 and the actual schema. Any new table holding personal data must be added here as part of its migration.

### 6.1 Hard-deleted

- User profile (name, email, sex, DOB, location)
- Authentication credentials (password hashes, federated identity links, refresh tokens)
- Training plans, plan history, plan revisions
- Workout logs, performance stats, body composition entries
- Health condition flags and injury logs
- AI coaching session summaries (parsed coaching notes only — raw transcripts are not stored)
- Equipment inventory and locations
- Goals, race targets, race results
- Sensitive-category toggle states
- Consent records (except: legal basis records may be retained for limitation period — see 6.3)
- Cookie consent records tied to the user account
- DSR request records tied to the user (except aggregated DSR metrics)

### 6.2 Unlinked but Retained

- Crowdsourced gym/facility entries: the row is preserved (it is community data) but the `contributed_by_user_id` foreign key is nulled. A `contributed_by_user_deleted_at` timestamp is recorded.
- Aggregate statistics that include the user's data: continue to exist; per Decision #5, all shared aggregates are subject to N=25 suppression so the user's data is not individually exposed.
- Pseudonymized research datasets that have already been transmitted to research partners under DPA: cannot be recalled. The Privacy Policy and consent flow disclose this.
- **Trained AI model weights and derivatives.** Account deletion stops new use of the user's data in future training runs (per PA-15 / LIA §8.1 opt-out behavior). Model weights from training runs already completed are not selectively edited or retrained on deletion — model unlearning is not technically feasible at v1. This is structurally identical to a consent-withdrawal scenario and is not a side-effect of the LI basis. The asymmetry is disclosed at PP §7 "AI Models and Derivatives" and re-acknowledged at LIA §4.5.2. The deletion flow does not modify model weights.

### 6.3 Retained for Compliance

The following are retained only to the extent and duration required by law, then deleted. Each must have a documented retention period and an automated purge job.

- Financial records related to paid subscriptions (tax law — typically 7 years per jurisdiction)
- Records demonstrating that a DSR was fulfilled (typically retained for the limitation period for regulatory complaints — varies by jurisdiction, commonly 2–3 years)
- Logs of consent given/withdrawn (retained for the period required by applicable law)

These records contain the minimum data needed for the compliance purpose (e.g., a hashed user identifier and timestamps), not full profile data.

### 6.4 Tombstone

After deletion completes, a tombstone row is retained indefinitely:

- `tombstone_id` (random, not derived from user identifiers)
- `deleted_at` timestamp
- `deletion_reason` (`self_service`, `dsr_request`, `authorized_agent`, `inactivity`)
- `jurisdiction_at_deletion` (for audit)

The tombstone allows audit and statistical reporting without retaining identifying information.

### 6.5 DMCA-Removed Content (Independent of User Deletion)

Content that has been removed in response to a DMCA notice (per `AIDSTATION_DMCA_Designated_Agent_Spec`) follows the DMCA process, not the user-initiated deletion flow described in this spec.

- Content removed under a DMCA takedown remains removed even if the contributing user later deletes their account or attempts to restore the content through deletion-flow mechanisms. Restoration occurs only through a successful counter-notification under § 512(g).
- **Crowdsourced facility entries removed under DMCA** follow the DMCA outcome: the row is removed, not unlinked-and-preserved per §6.2. The §6.2 unlinking pattern does not apply because the content itself is the subject of the takedown, not the contributor's identity.
- A user-initiated account deletion does not by itself reverse any DMCA action against content the user contributed. Past DMCA notices and counter-notices about that user's content remain in the PA-16 records per their own retention schedule (see RoPA PA-16), independent of the account's deletion status.
- A pending DMCA matter against a user's content does not block user-initiated account deletion. The account is deleted per the standard flow; the DMCA matter continues under the DMCA process, with affected content removed (or restored, where a counter-notification succeeds) under §512.

The DMCA process and the user-deletion process operate on different timelines, with different triggers, under different legal frameworks. They are deliberately not interlocked: an action under one does not by itself unwind an action under the other.

---

## 7. Backup Interaction

Backups are not selectively edited. When deletion completes:

1. The deletion event is recorded with the user's previously stable identifier in a deletion ledger.
2. As each backup rotates out (≤90 days), it is purged in its entirety per normal lifecycle.
3. If a restore from backup is ever performed during the 90-day window, the restore process consults the deletion ledger and re-applies any deletions that occurred since the backup was taken.

This is the standard pattern and matches what the Privacy Policy commits to.

---

## 8. Authorization and Anti-Abuse

- A user can only initiate deletion for their own account.
- Re-authentication is required (Section 4.3) regardless of session age.
- Federated login users re-authenticate via the identity provider.
- Account deletion requests during an open billing dispute or fraud investigation are flagged and the cooling-off period is extended pending resolution. The user is notified.
- Rate limiting: a user cannot initiate, cancel, and re-initiate deletion more than 3 times in 24 hours.

---

## 9. Audit and Logging

Every state transition is logged with: timestamp, event type, source IP (hashed after 30 days per retention policy), user agent, jurisdiction, outcome.

Event types:

- `deletion.initiated`
- `deletion.cancelled`
- `deletion.cooling_off_expired`
- `deletion.cascade_started`
- `deletion.cascade_completed`
- `deletion.cascade_failed` (operational alert)
- `deletion.restore_reapplied` (after a backup restore)

Logs are retained for the period required by law and then purged. Logs do not contain the deleted personal data itself.

---

## 10. Operational Fallback

If the self-service flow fails for any reason (bug, account in an inconsistent state, federated identity provider unavailable), the user is presented with a manual fallback:

> If you cannot complete deletion in the app, email help@aidstation.pro from your account email address. We will fulfill your request within 30 days.

Privacy team SOP for manual deletion is covered in the Breach Playbook companion process docs (not yet drafted; tracked as operational item).

---

## 11. Edge Cases

### 11.1 Active Paid Subscription

- Subscription is cancelled at deletion confirmation.
- Final billing reconciliation runs.
- Refund (if any) is processed per billing policy and the financial record retention applies.
- The user does not need to cancel the subscription separately.

### 11.2 Team-Based Training (Future Feature)

When the team-based training feature ships, deletion of an athlete who is a team member needs additional handling: the team's shared plan history may reference the athlete's data. Recommended approach: the athlete's identifiers are scrubbed from shared records (replaced with `[former member]`), and the records remain for the other team members. This must be added to the inventory when the feature ships.

### 11.3 User Re-Creates an Account With Same Email

After deletion, the email address is freed. A new account can be created with the same email. The new account has no relationship to the deleted one. This is explicit in the completion email.

### 11.4 Death of Account Holder

Out of scope for self-service. Next-of-kin requests are handled through the manual privacy@ channel and require death certificate plus proof of authority. Not covered in this spec; tracked as operational item.

### 11.5 Court Order or Legal Hold

If an account is subject to a legal hold, the deletion request is acknowledged but execution is paused. The user is notified to the extent permitted by the hold order. Tracked as operational item.

### 11.6 Mid-Cascade Failure

If the cascade partially completes (some tables succeeded, others failed):

- The account stays in `deletion_in_progress`.
- The operational alert fires.
- The cascade is idempotent — retrying skips already-deleted rows.
- The user does not need to do anything.

---

## 12. Open TBDs

- Operational SOP for manual privacy@ deletion requests (drafted alongside breach playbook companion docs)
- Death-of-account-holder process (tracked separately)
- Legal hold workflow (tracked separately)
- Specific retention periods for compliance-retained records per jurisdiction (general principle is "minimum required by law"; specifics need legal review)
- Choice of refund policy for active paid subscriptions (product decision, not privacy decision)
- Whether to expose deletion status via API (currently in-app only; defer)

---

## 13. Gut Check

**Risks**

- The biggest risk is the gap between the documented inventory in Section 6 and what the actual schema turns into as the product grows. If a new table is added that holds personal data and is not added to the inventory, deletion silently leaves data behind. Mitigation: every migration that adds personal-data columns must update Section 6 as part of the PR review, and a periodic schema audit (quarterly is reasonable) checks for drift.
- The 14-day recover window plus active-system erasure within 30 days of the request, plus the ≤90-day backup rotation, means a worst case of roughly 120 days from request to the last backup byte being purged. The important point for compliance: active-system erasure is always within the one-month statutory window (Art. 12(3)); the backup tail is the recognized beyond-use exception, with restores re-applying the deletion. The Privacy Policy discloses this and the email templates reflect it.
- Federated login deletion has a subtle hole: if the user deletes their AIDSTATION account but keeps their Google account active, the user's Google identifier was previously linked. We hard-delete the link. But Google can still tell us "this user signed in here once" via OAuth history on their side. We have no control over Google's records. Disclose this in the email template? Probably overkill.

**What might be missing**

- A "download my data before deleting" prompt on the confirmation screen would be user-friendly and reduce regret. Cost is small; recommend adding to the UX.
- An option to retain some specific data (e.g., "keep my facility contributions but delete everything else") would be the most user-friendly possible flow. This is essentially category-level deletion of a single category and runs into the same complexity argument. The unlinking happens automatically per Section 6.2 so the user does not need to opt in.

**Best argument against the current trajectory**

The recover window is now 14 days, reduced from 30 so that total active-system erasure stays inside the GDPR Art. 12(3) one-month deadline (the prior 30-day cooling-off could not coexist with a separate cascade period within one month). 14 days balances deletion-regret protection against the statutory limit; a shorter 7-day window would be more standard for a flow the user reached through three friction steps and remains an option if user research surfaces friction.

---

## 14. Change Log

| Version | Date | Changes | Author |
|---|---|---|---|
| v1 | Batch 4 of privacy program | Initial self-service deletion flow spec. Implements Decisions #5, #8, #11, #12, #13, #27, #28. | Privacy Lead |
| v2 | Prior session | Revisions applied during privacy program batches. (Pre-existing v2 file content; this row is recorded for continuity — original v2 change description not captured in a change log section at the time.) | Privacy Lead |
| v3 | May 19, 2026 | Track A Group 1 consistency-pass edit (D-74). §6.2 expanded to include a trained-AI-model-weights bullet, cross-referencing PP v3 §7 and LIA v2 §4.5.2. Status header bumped v1 → v3 (previously stale at v1 in file; v2 existed as a filename only). Companion docs list updated to current versions (PP v3, RoPA v3, LIA v2, Breach Playbook v2). No other changes to deletion behavior, retention rules, DSR timelines, or any other operational logic. | Privacy Lead |
| v4 | May 19, 2026 | Track A Group 2 cross-reference edit (D-107). New §6.5 "DMCA-Removed Content (Independent of User Deletion)" added before §7, covering: DMCA takedowns survive user deletion; community facility entries under DMCA are removed (not §6.2-unlinked); user deletion does not reverse DMCA actions; pending DMCA matters do not block account deletion. Companion docs list updated to PP / RoPA / Breach Playbook (cross-references this session) plus DMCA Designated Agent Spec v2. No changes to existing §6.1-§6.4 deletion behavior. | Privacy Lead |
| v6 | May 30, 2026 | Deletion flow brought into GDPR compliance (resolves D-129). The prior model (30-day cooling-off **then** a further 30 days for the cascade) could push active-system erasure to ~60 days, past the Art. 12(3) one-month limit. Now: a **14-day** recover window (cancel by logging in), with active-system erasure completing **within 30 days of the request** (extendable up to two further months only for genuinely complex requests, with notice). Decision table, user-facing copy, cooling-off email, state-model timing, and Gut Check updated; the worst-case timeline note revised (~120 days to last backup byte, with active erasure always inside one month). Backups remain on the ≤90-day rolling cycle (beyond-use; restores re-apply the deletion). Stale "Privacy Policy §6" table references corrected to §7. Privacy Policy mirrored in PP v7. | Privacy Lead |
| v6 | May 30, 2026 | Contact-address consolidation to the two approved addresses: `help@aidstation.pro` for user support (including privacy / data-rights requests) and `info@aidstation.pro` for formal, legal, security, and DMCA correspondence. No other changes. | Privacy Lead |

---

*Cross-reference cleanup (v5, 2026-05-30): inline references to companion documents were converted to unversioned logical names per Rule #12, so they no longer go stale when a companion document is revised. No substantive content changes. See `Privacy_Program_Consistency_Sweep_Report_v1.md`.*

