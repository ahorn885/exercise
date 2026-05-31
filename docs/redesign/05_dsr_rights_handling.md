# Control 05 — Data-Subject Rights (DSR) & Authorized-Agent Handling

**Source of truth (authoritative):** `AIDSTATION_Privacy_Policy` §9 and §14; `AIDSTATION_Authorized_Agent_Process_Spec`.
**Constants:** `DSR_RESPONSE` (30 days), `DSR_COMPLEX_EXTENSION` (+2 months).

## Purpose
Let users exercise access, export, correction, and deletion themselves, and handle requests submitted by an authorized agent without becoming the conduit of a fraudulent or adverse request.

## Requirements
- **R1 — Self-service rights.** In-app access, export, correction, and deletion (PP §9; deletion routes to control 02). Account → Privacy.
- **R2 — Response clock.** Respond within `DSR_RESPONSE` (30 days), extendable by `DSR_COMPLEX_EXTENSION` for genuinely complex requests **with notice to the user**. Track the clock per request in UTC.
- **R3 — Agent identity verification (mandatory baseline).** Always verify an authorized agent's authority at a baseline tier; escalate to a **heightened tier** for deletion and sensitive-category requests. (CCPA §1798.140(d)/.130 and GDPR Art. 12(6) permit verifying agent authority.)
- **R4 — User confirmation (low-friction).** The user is verified via low-friction account-control confirmation (§5.3); verification burden is placed on the **agent**, not the user, to respect CCPA's anti-friction rule.
- **R5 — Delivery destination.** Deliver access/portability results to the **user's account-of-record by default**; deliver to the agent only on explicit, separately-stated user authorization (§5.6).
- **R6 — Retention split (§10).** Keep a **minimal DSR-log record** for the full defense window; retain the high-PII authorization document only for the statutory record period, then reduce it to a **one-way hash + metadata** proving a valid authorization existed.
- **R7 — Deceased / incapacity (§12.7–§12.8).** No affirmative post-mortem data rights except where a specific applicable law grants them; default to **account closure, not disclosure** to relatives; require death + estate-authority documentation. For incapacity, replace user confirmation with heightened documentary verification of the POA/guardianship instrument and construe scope narrowly. (Jurisdiction-specific — flag for counsel; do not hard-code a permissive default.)
- **R8 — GPC & appeal.** Honor Global Privacy Control as an opt-out signal; support opt-out of sale/targeted advertising/profiling and the right to appeal a denied request (PP §14).

## Data model (sketch)
- `dsr_requests(id, type, subject_ref, agent_ref?, opened_at, due_at, status, complex_extension_at?, delivery_target enum(user|agent))`.
- `agent_authorizations(id, agent_verified_tier, user_confirmed, doc_hash, doc_metadata, purge_after)`.

## Triggers / jobs
- DSR intake → set `due_at = opened_at + 30d`; complex → extend with notice.
- Agent intake → R3/R4 verification gates before fulfillment.
- Retention job → R6 purge of authorization documents to hash after the statutory period.

## Acceptance criteria
1. A self-service access/export/correction/deletion completes from the account UI.
2. Each DSR has a tracked `due_at`; responses land within 30 days, or within the extension with a recorded notice.
3. An agent request without baseline verification is blocked; deletion/sensitive requests require the heightened tier.
4. Access/portability output goes to the user unless explicit agent-delivery authorization is on file.
5. After the statutory period, the authorization document is a one-way hash + metadata, not the signed image.
6. A GPC signal is honored as opt-out; a denied request exposes an appeal path.

## Out of scope
- The substantive legal sufficiency of post-mortem/incapacity handling (counsel) — build the gate and the flags, not the jurisdiction matrix.

## Dependencies
- Deletion executes via control 02; opt-out state shared with controls 01/04.
