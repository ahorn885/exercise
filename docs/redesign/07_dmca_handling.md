# Control 07 — DMCA Notice Handling

**Source of truth (authoritative):** `AIDSTATION_DMCA_Designated_Agent_Spec`; `AIDSTATION_Repeat_Infringer_Internal_Guideline`; `AIDSTATION_RoPA` PA-16.
**Constants:** `DMCA_RETENTION` (7 years from final action), `CONTACT_FORMAL` (info@).

## Purpose
Process copyright notices and counter-notices under §512, track repeat infringers, and retain the records — within the §512 safe-harbor framework.

## Requirements
- **R1 — Notice intake.** Validate the notice against the §512(c)(3) elements; may request additional information where reasonably necessary. An invalid notice is not actioned as a valid takedown trigger.
- **R2 — Takedown.** Default action on a valid notice is takedown, typically within **72 hours** of validating compliance (may extend when the matter warrants). Mark the content removed.
- **R3 — User notification (§512(g)(2)(A)).** On takedown, promptly notify the uploading user with: (a) a copy of the notice (complainant contact may be redacted on documented request), (b) a summary of the action, (c) counter-notification instructions, (d) a statement that the repeat-infringer policy applies.
- **R4 — Counter-notice + put-back.** Validate the four §512(g)(3) elements; a counter-notice missing any element is not valid and is not entitled to restoration (no obligation to advise on correction). On a valid counter-notice, run the §512(g) put-back process.
- **R5 — Repeat-infringer counter.** Track strikes per user; terminate repeat infringers in appropriate circumstances per the internal guideline. The **threshold is internal and unpublished** — implement the counter and the determination workflow, not a public number.
- **R6 — Training exclusion.** Content removed under DMCA is excluded from training datasets going forward (coordinate with control 01's ingest gate). If the content was already incorporated into a model generation before takedown, handle under PA-15 derivatives.
- **R7 — Retention.** Retain notice + handling records for `DMCA_RETENTION` (7 years from final action on the matter; covers the 17 U.S.C. §507(b) limitation plus margin). These records are litigation-adjacent and are **not** part of the user's general data export (PP §9), and they survive account deletion (PA-16).
- **R8 — Agent & contact.** The designated agent is the Privacy Lead in DMCA capacity; the contact address is `CONTACT_FORMAL` (info@).

## Data model (sketch)
- `dmca_notices(id, received_at, complainant, target_content_ref, validity, action, final_action_at, retain_until)`.
- `dmca_counter_notices(notice_id, received_at, elements_valid, putback_at?)`.
- `infringer_strikes(user_ref, notice_id, counted_at)`.

## Triggers / jobs
- Notice intake → R1 validation → R2 takedown + R3 notification.
- Counter-notice intake → R4 validation → put-back schedule.
- Strike accrual → R5 determination workflow.
- Takedown → flag content for R6 training exclusion.
- Retention job → enforce R7 (`retain_until = final_action_at + 7y`).

## Acceptance criteria
1. A notice missing a §512(c)(3) element is not actioned as a valid takedown.
2. A valid notice produces a takedown and a user notification containing all four §512(g)(2)(A) elements.
3. A counter-notice missing any of the four §512(g)(3) elements is rejected as invalid.
4. Repeat-infringer strikes accrue per user and feed the termination workflow; no public threshold is exposed.
5. Taken-down content is excluded from subsequent training pulls (control 01).
6. Notice records are retained 7 years from final action, excluded from PP §9 export, and survive account deletion.

## Out of scope (operational, not code)
- USCO designated-agent registration, public DMCA page publication, and mailbox standup (D-99–D-102).

## Dependencies
- Training exclusion enforced by control 01; deletion carry-through from control 02.
