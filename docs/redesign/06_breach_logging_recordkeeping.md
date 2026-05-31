# Control 06 — Breach Logging & Record-Keeping

**Source of truth (authoritative):** `AIDSTATION_Breach_Response_Playbook` §5 (timeline), §6 (assessment + waypoints), §7 (notification matrix), §12.1 (incident log); `AIDSTATION_DPA_Template` §4.7 (subprocessor windows).

> Scope note: the Playbook is mostly a **human runbook** and is not code. The buildable parts are the **incident log**, the **deadline/waypoint tracking**, and **record retention**. This control builds those; it does not automate human response or draft notifications.

## Purpose
Provide the append-only incident record and the deadline tracking that make the breach process auditable and Art. 33(5)-compliant.

## Requirements
- **R1 — Incident log (append-only, Art. 33(5)).** Capture the facts of the breach, its effects, and remedial action. Every change of working decision is appended with rationale — entries are never edited or deleted.
- **R2 — Waypoint / deadline tracking (UTC, from awareness).** Track and surface: severity classification target **T+4h (outer bound T+8h)**; the **T+24h notification-decision waypoint** (notify / do-not-notify / still-gathering, with the §6.3 carve-out required for do-not-notify); and the **72-hour Art. 33 regulator clock**. Show remaining cushion against each deadline.
- **R3 — Subprocessor breach intake (DPA §4.7).** Record subprocessor-originated breaches with the **12h preliminary / 24h full** notification timestamps and surface them into the same timeline.
- **R4 — Notification decision records.** Record regulator notifications (§7.1, 72h Art. 33) and affected-person notifications (§7.2, Art. 34), each with its decision basis; record the §6.3 risk carve-out analysis when "do not notify" is chosen.
- **R5 — Retention.** Retain breach records per the Playbook's record-keeping requirement (Art. 33(5)); minimize beyond what the forensic and statutory need requires (TOMs §7.2).

## Data model (sketch)
- `incidents(id, detected_at, severity, status)`.
- `incident_log(incident_id, at, actor, entry, decision_change?, rationale?)` — append-only.
- `incident_deadlines(incident_id, kind enum(severity|notify_waypoint|art33|subproc_prelim|subproc_full), due_at, met_at?)`.
- `notification_records(incident_id, audience enum(regulator|affected), decided_at, basis, carveout_ref?)`.

## Triggers / jobs
- Incident open → compute deadlines from `detected_at` (UTC) and surface cushion.
- Append-only writers for log + decision changes.
- Retention job → enforce R5.

## Acceptance criteria
1. The incident log is append-only; an attempt to edit/delete an entry is rejected.
2. Deadlines (T+4h/8h, T+24h, 72h, subprocessor 12h/24h) are computed from awareness in UTC, with remaining cushion shown.
3. A "do not notify" decision cannot be recorded without an attached §6.3 carve-out reference.
4. Subprocessor-breach intake timestamps appear in the same incident timeline.
5. Breach records are retained for the required period and not beyond the minimized window.

## Out of scope
- The human response runbook, containment, and forensics (not code).
- Drafting the actual regulator/affected-person notifications.

## Dependencies
- Subprocessor obligations reference the DPA; no cross-control data dependency.
