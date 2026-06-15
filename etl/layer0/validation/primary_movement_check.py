"""Discipline `primary_movement` coverage validator.

Every active `layer0.disciplines` row must carry a `primary_movement` drawn
from Layer 0 `ENUM_MOVEMENTS`. The movement axis is read by Layer 2E nutrition
(plumbed via Layer 2A) for the §5.4.3 sport-profile CHO modifier and §5.3.3
protein band; a NULL silently degrades every discipline to the generic
`multi_sport` fuelling profile.

This is the standing guard against the exact regression that prompted migration
`0006`: the column is populated by a migration, but a full ETL re-extraction of
the disciplines dimension drops it (the canon normalizer stamps
`endurance_profile` but not `primary_movement`). If that ever recurs — or a new
discipline lands without a movement — this check fails the gate loudly instead
of letting movement-blind fuelling ship.
"""
from __future__ import annotations

from typing import Any

# Layer 0 movement vocabulary (locked). Source of truth: ENUM_MOVEMENTS in
# etl/_frozen_xlsx_authoring/extractors/sports_framework.py; the same set keyed
# by layer2e.builder._MOVEMENT_SPORT_PROFILE.
ENUM_MOVEMENTS: frozenset[str] = frozenset(
    {
        "running", "cycling", "swimming", "paddling", "skiing",
        "climbing", "hiking", "navigation", "other_skill",
    }
)


def run_primary_movement(conn) -> dict[str, Any]:
    errors: list[dict[str, Any]] = []
    with conn.cursor() as cur:
        cur.execute(
            "SELECT discipline_id, discipline_name, primary_movement "
            "FROM layer0.disciplines "
            "WHERE superseded_at IS NULL AND discipline_id IS NOT NULL"
        )
        rows = cur.fetchall()
    for disc_id, disc_name, movement in rows:
        if movement is None:
            errors.append({
                "discipline_id": disc_id, "discipline_name": disc_name,
                "primary_movement": None, "problem": "missing primary_movement",
            })
        elif movement not in ENUM_MOVEMENTS:
            errors.append({
                "discipline_id": disc_id, "discipline_name": disc_name,
                "primary_movement": movement, "problem": "non-enum primary_movement",
            })
    return {
        "rows_checked": len(rows),
        "pass_count": len(rows) - len(errors),
        "error_count": len(errors),
        "errors": errors,
    }
