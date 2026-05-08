"""Foreign-key validators for the v10 substitution + training-gap tables.

Both checks fail at ERROR level — these are curated artefacts, broken
references would silently corrupt downstream plan-gen logic.
"""
from __future__ import annotations

from typing import Any


def _load_discipline_ids(conn) -> set[str]:
    with conn.cursor() as cur:
        cur.execute(
            "SELECT discipline_id FROM layer0.disciplines WHERE superseded_at IS NULL"
        )
        return {row[0] for row in cur.fetchall()}


def run_substitution_fks(conn) -> dict[str, Any]:
    """Every (target_id, substitute_id) on `discipline_substitutes` must
    resolve to a current `layer0.disciplines.discipline_id`.
    """
    valid_ids = _load_discipline_ids(conn)
    errors: list[dict[str, Any]] = []
    pass_count = 0
    with conn.cursor() as cur:
        cur.execute(
            """
            SELECT target_id, target_name, substitute_id, substitute_name
              FROM layer0.discipline_substitutes
             WHERE superseded_at IS NULL
            """
        )
        rows = cur.fetchall()
    for target_id, target_name, sub_id, sub_name in rows:
        bad: list[str] = []
        if target_id not in valid_ids:
            bad.append(f"target_id={target_id!r}")
        if sub_id not in valid_ids:
            bad.append(f"substitute_id={sub_id!r}")
        if bad:
            errors.append({
                "target_id": target_id,
                "target_name": target_name,
                "substitute_id": sub_id,
                "substitute_name": sub_name,
                "broken": bad,
            })
        else:
            pass_count += 1
    return {
        "rows_checked": len(rows),
        "pass_count": pass_count,
        "error_count": len(errors),
        "errors": errors,
    }


def run_training_gap_fks(conn) -> dict[str, Any]:
    """Every `discipline_id` on `discipline_training_gaps` must resolve to
    a current `layer0.disciplines.discipline_id`.
    """
    valid_ids = _load_discipline_ids(conn)
    errors: list[dict[str, Any]] = []
    pass_count = 0
    with conn.cursor() as cur:
        cur.execute(
            """
            SELECT discipline_id, discipline_name, gap_type
              FROM layer0.discipline_training_gaps
             WHERE superseded_at IS NULL
            """
        )
        rows = cur.fetchall()
    for did, name, gap_type in rows:
        if did not in valid_ids:
            errors.append({
                "discipline_id": did,
                "discipline_name": name,
                "gap_type": gap_type,
            })
        else:
            pass_count += 1
    return {
        "rows_checked": len(rows),
        "pass_count": pass_count,
        "error_count": len(errors),
        "errors": errors,
    }
