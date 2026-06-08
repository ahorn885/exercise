"""Modality-group orphan validation per `Modality_Group_Spec_v1.md` §4 + §10.

Every discipline appearing in `layer0.disciplines` (post-canon) MUST belong
to ≥1 modality group via `layer0.discipline_modality_membership`. The spec
requires no orphans — Layer 2A relies on this invariant to keep the
discipline list non-empty after the pool-redistribute step.

Severity: ERROR (not WARN). An orphan represents a missing-data condition
that breaks Layer 2A allocation; the ETL surfaces it loudly so the spreadsheet
author can fix the membership Sheet rather than silently dropping the
discipline downstream.
"""
from __future__ import annotations

from typing import Any


def run_modality_group_orphan(conn) -> dict[str, Any]:
    """Check that every active discipline has ≥1 modality_group membership.

    Returns `{rows_checked, pass_count, error_count, orphans: [discipline_id...]}`.
    """
    with conn.cursor() as cur:
        # Active disciplines (current Layer 0 version, not superseded).
        cur.execute(
            """
            SELECT discipline_id
              FROM layer0.disciplines
             WHERE superseded_at IS NULL
            """
        )
        discipline_ids = [r[0] for r in cur.fetchall()]

        # Active memberships.
        cur.execute(
            """
            SELECT DISTINCT discipline_id
              FROM layer0.discipline_modality_membership
             WHERE superseded_at IS NULL
            """
        )
        grouped_ids = {r[0] for r in cur.fetchall()}

    orphans = sorted(d for d in discipline_ids if d not in grouped_ids)
    pass_count = len(discipline_ids) - len(orphans)

    return {
        "rows_checked": len(discipline_ids),
        "pass_count": pass_count,
        "error_count": len(orphans),
        "orphans": orphans,
    }
