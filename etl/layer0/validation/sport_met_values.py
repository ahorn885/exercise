"""Verify sport_met_values has all 4 phases × 4 volume tiers (#233).

The table is seeded by migration 0036 with 16 rows (Base/Build/Peak/Taper ×
tier-index 0–3). A missing row means _compute_activity_multiplier() falls back
to the hardcoded constant for that cell — the fallback is intentional during
the migration window, but a permanent gap is a curation error that should fail
the gate.
"""
from __future__ import annotations

from typing import Any

_EXPECTED_PHASES = ("Base", "Build", "Peak", "Taper")
_EXPECTED_TIERS = (0, 1, 2, 3)


def run_sport_met_values(conn) -> dict[str, Any]:
    errors: list[dict[str, Any]] = []
    with conn.cursor() as cur:
        cur.execute(
            """
            SELECT phase, volume_tier_index
              FROM layer0.sport_met_values
             WHERE superseded_at IS NULL
            """
        )
        rows = cur.fetchall()
    present = {(r[0], r[1]) for r in rows}
    for phase in _EXPECTED_PHASES:
        for tier in _EXPECTED_TIERS:
            if (phase, tier) not in present:
                errors.append({
                    "id": f"{phase}/tier_{tier}",
                    "detail": (
                        f"sport_met_values missing active row for "
                        f"phase={phase!r} volume_tier_index={tier} "
                        f"(migration 0036 should have seeded it)"
                    ),
                })
    return {
        "rows_checked": len(rows),
        "pass_count": 0 if errors else 1,
        "error_count": len(errors),
        "errors": errors,
    }
