# Archived — Project Backlog (frozen 2026-05-27)

The `Project_Backlog.md` / `Project_Backlog_vN.md` chain (v1 → v62) is **frozen
here for historical reference only.** As of 2026-05-27, backlog, feature, and
bug tracking moved to **GitHub issues** in `ahorn885/exercise`.

**Do not edit or reopen these files.** File new work as a GitHub issue.

## Why

The doc-based backlog had accumulated 62 versioned snapshots and a verbose,
churning Notes column that was hard to query and easy to let drift from the
code and handoffs. Issues give visible, resilient, queryable tracking with
real parent→child (epic / sub-issue) structure.

## How the migration maps

- Each open `D-NN` finding became a GitHub issue whose title carries the
  `[D-NN]` id, so older specs and handoffs that cite `D-NN` still resolve.
- Items are grouped under **epics** (one per theme — plan-gen, Layer 3 HITL,
  Layer 2E nutrition, Layer 2D injury, upstream pipeline, onboarding, Layer 0
  reconciliation, integrations, notifications, and the v1 / post-launch
  iceboxes) with the individual items linked as **sub-issues**.
- Labels: `layer:*`, `area:*`, `type:*` (bug/feature/spec/cleanup/test/epic),
  `status:*` (in-progress/designed/deferred/blocked/done), `priority:*`, plus a
  `v1`/`v2` track and `icebox`.

The last live doc version was `Project_Backlog_v62.md`; read it for the full
pre-migration record of any `D-NN`.
