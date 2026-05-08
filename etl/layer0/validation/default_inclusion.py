"""Validate `phase_load_allocation.default_inclusion` against the v10 enum.

Allowed values: `included`, `excluded`, `prompt_required`. Aggregator
(`WEEKLY TOTAL TARGET`) rows are exempt and excluded from the check.

Mismatch → ERROR.
"""
from __future__ import annotations

from typing import Any

ALLOWED = {"included", "excluded", "prompt_required"}


def run_default_inclusion(conn) -> dict[str, Any]:
    errors: list[dict[str, Any]] = []
    pass_count = 0
    with conn.cursor() as cur:
        cur.execute(
            """
            SELECT sport_name, discipline_id, discipline_name, default_inclusion
              FROM layer0.phase_load_allocation
             WHERE superseded_at IS NULL
            """
        )
        rows = cur.fetchall()
    for sport, did, disc, di in rows:
        # Aggregator rows ("WEEKLY TOTAL TARGET") may legitimately have
        # default_inclusion populated or NULL — exempt them.
        if disc and "WEEKLY TOTAL TARGET" in str(disc).upper():
            pass_count += 1
            continue
        if di is None or str(di).strip() in ALLOWED:
            pass_count += 1
            continue
        errors.append({
            "sport_name": sport,
            "discipline_id": did,
            "discipline_name": disc,
            "default_inclusion": di,
        })
    return {
        "rows_checked": len(rows),
        "pass_count": pass_count,
        "error_count": len(errors),
        "errors": errors,
    }
