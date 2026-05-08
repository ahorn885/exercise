"""Validate `exercises.contraindicated_conditions[]` against the curated
`layer0.health_condition_categories.category_name` set.

Mismatch → WARN (informational). Per `1d_Exercise_DB_Audit.md`, only the
five canonical system categories (Cardiac / Respiratory / GI / Skin /
Neurological / Cognitive) are expected to appear; this validator flags
anything else for follow-up rather than failing the ETL.
"""
from __future__ import annotations

from typing import Any


def run_contraindicated_conditions(conn) -> dict[str, Any]:
    with conn.cursor() as cur:
        cur.execute(
            """
            SELECT category_name FROM layer0.health_condition_categories
             WHERE superseded_at IS NULL
            """
        )
        canonical = {row[0].strip().lower() for row in cur.fetchall() if row[0]}

    warnings: list[dict[str, Any]] = []
    pass_count = 0
    with conn.cursor() as cur:
        cur.execute(
            """
            SELECT exercise_id, exercise_name, contraindicated_conditions
              FROM layer0.exercises
             WHERE superseded_at IS NULL
            """
        )
        rows = cur.fetchall()
    for ex_id, ex_name, conditions in rows:
        if not conditions:
            pass_count += 1
            continue
        unknown = [c for c in conditions if c.strip().lower() not in canonical]
        if unknown:
            warnings.append({
                "exercise_id": ex_id,
                "exercise_name": ex_name,
                "unknown_conditions": unknown,
            })
        else:
            pass_count += 1
    return {
        "exercises_checked": len(rows),
        "pass_count": pass_count,
        "warn_count": len(warnings),
        "warnings": warnings,
    }
