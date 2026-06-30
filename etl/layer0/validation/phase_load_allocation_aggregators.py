"""Validate that no aggregator rows survive in the active phase_load_allocation
set (#269).

The "WEEKLY TOTAL TARGET" rows are zero-weight per-sport summaries, not real
disciplines — the per-sport weekly total lives in
`layer0.phase_load_weekly_totals`. Left in the active set they pollute Layer 2A's
discipline load, which is exactly why the loader carried the defensive D-05
`discipline_name NOT LIKE '%WEEKLY TOTAL%'` filter. Migration 0034 supersedes
them; this check makes their reappearance a gate FAIL so the cleanup is durable
and the standing filter can retire.

The predicate is the same `LIKE '%WEEKLY TOTAL%'` the D-05 filter and migration
0034 use, so a clean active set (post-0034) reports zero here.

Any active aggregator row → ERROR (fix-the-data, not waivable).
"""
from __future__ import annotations

from typing import Any


def run_phase_load_allocation_aggregators(conn) -> dict[str, Any]:
    errors: list[dict[str, Any]] = []
    with conn.cursor() as cur:
        cur.execute(
            """
            SELECT sport_name, discipline_id, discipline_name
              FROM layer0.phase_load_allocation
             WHERE superseded_at IS NULL
               AND discipline_name LIKE '%WEEKLY TOTAL%'
             ORDER BY sport_name
            """
        )
        rows = cur.fetchall()
    for sport, did, disc in rows:
        errors.append({
            "id": f"{sport}/{did or '-'}",
            "detail": f"aggregator row {disc!r} still active in "
                      "phase_load_allocation — should be superseded (migration 0034)",
        })
    return {
        "rows_checked": len(rows),
        "pass_count": 0 if errors else 1,
        "error_count": len(errors),
        "errors": errors,
    }
