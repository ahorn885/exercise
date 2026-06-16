"""Exercises-graph foreign-key validator.

Every exercise reference on an *active* `layer0.exercises` row — its
`progression_exercise_id`, its `regression_exercise_id`, and each
`physical_proxies[].exercise_id` — must resolve to another *active* exercise.
Likewise every active `sport_exercise_map.exercise_id` must resolve to an active
exercise. A dangling reference would surface at serve time: Tier-3 proxy
resolution and progression/regression display read these ids straight through.

This is the standing guard the cull migrations (`0007`/`0008`/`0009`) each had to
hand-roll in their own DO-block, because `validate_layer0` previously FK-checked
only the disciplines family (`fk_checks.py`). Retiring/superseding an exercise
can orphan a kept exercise that still points at it; the 2C/2D readers filter
`superseded_at IS NULL` on the *direct* exercises join, so a stale
`sport_exercise_map` row goes inert on its own — but a dangling
`physical_proxies`/progression/regression ref on an active row would NOT, and
nothing caught it before this check. Fix-not-waive (mirrors the `0006`
`primary_movement_check` precedent): a dangling reference fails the gate loudly.
"""
from __future__ import annotations

from typing import Any


def _load_active_exercise_ids(conn) -> set[str]:
    with conn.cursor() as cur:
        cur.execute(
            "SELECT exercise_id FROM layer0.exercises WHERE superseded_at IS NULL"
        )
        return {row[0] for row in cur.fetchall()}


def run_exercises_fk(conn) -> dict[str, Any]:
    active_ids = _load_active_exercise_ids(conn)
    errors: list[dict[str, Any]] = []
    rows_checked = 0

    with conn.cursor() as cur:
        # progression / regression on active exercises
        cur.execute(
            """
            SELECT exercise_id, exercise_name,
                   progression_exercise_id, regression_exercise_id
              FROM layer0.exercises
             WHERE superseded_at IS NULL
            """
        )
        for ex_id, ex_name, prog_id, regr_id in cur.fetchall():
            for kind, target in (("progression", prog_id), ("regression", regr_id)):
                if not target:  # NULL or '' → no reference
                    continue
                rows_checked += 1
                if target not in active_ids:
                    errors.append({
                        "ref_kind": kind, "holder": ex_id,
                        "holder_name": ex_name, "missing_id": target,
                    })

        # physical_proxies[].exercise_id on active exercises
        cur.execute(
            """
            SELECT e.exercise_id, e.exercise_name, p->>'exercise_id' AS proxy_id
              FROM layer0.exercises e,
                   jsonb_array_elements(e.physical_proxies) p
             WHERE e.superseded_at IS NULL
               AND jsonb_typeof(e.physical_proxies) = 'array'
            """
        )
        for ex_id, ex_name, proxy_id in cur.fetchall():
            if not proxy_id:
                continue
            rows_checked += 1
            if proxy_id not in active_ids:
                errors.append({
                    "ref_kind": "physical_proxy", "holder": ex_id,
                    "holder_name": ex_name, "missing_id": proxy_id,
                })

        # active sport_exercise_map rows must map an active exercise
        cur.execute(
            """
            SELECT exercise_id, sport_name
              FROM layer0.sport_exercise_map
             WHERE superseded_at IS NULL
            """
        )
        for ex_id, sport_name in cur.fetchall():
            rows_checked += 1
            if ex_id not in active_ids:
                errors.append({
                    "ref_kind": "sport_exercise_map",
                    "holder": f"sport_exercise_map[{sport_name}]",
                    "holder_name": sport_name, "missing_id": ex_id,
                })

    return {
        "rows_checked": rows_checked,
        "pass_count": rows_checked - len(errors),
        "error_count": len(errors),
        "errors": errors,
    }
