"""Validate `phase_load_allocation.default_inclusion` against the v10 enum.

Allowed values: `included`, `excluded`, `prompt_required`.

Mismatch → ERROR.

#269 (2026-06-30): the `WEEKLY TOTAL TARGET` aggregator rows were retired by
migration 0034 (superseded; `WHERE superseded_at IS NULL` already excludes
them), so the former aggregator exemption is removed.
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
