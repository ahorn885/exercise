"""Vocab alignment validation per spec §6.4.

Two checks (both informational — never fail the ETL):

(a) For every `contraindicated_parts[]` entry on `layer0.exercises`, verify
    each entry exists in `layer0.body_parts.canonical_name`.

(b) For every `sport_name` on `layer0.sport_exercise_map`, verify it exists
    in `layer0.sport_discipline_bridge.exercise_db_sport`. (Resolves spec
    Open Item #5.)
"""
from __future__ import annotations

from typing import Any


def run_vocab_alignment(conn) -> dict[str, Any]:
    body_parts_canon = _load_canonical_set(conn, "layer0.body_parts", "canonical_name")
    bridge_sports = _load_canonical_set(
        conn, "layer0.sport_discipline_bridge", "exercise_db_sport"
    )

    # Check (a) — exercises × body_parts
    exercise_warnings: list[dict[str, Any]] = []
    pass_count = 0
    with conn.cursor() as cur:
        cur.execute(
            """
            SELECT exercise_id, exercise_name, contraindicated_parts
              FROM layer0.exercises
             WHERE superseded_at IS NULL
            """
        )
        rows = cur.fetchall()
    for ex_id, ex_name, parts in rows:
        if not parts:
            pass_count += 1
            continue
        unknown = [p for p in parts if p.lower() not in body_parts_canon]
        if unknown:
            exercise_warnings.append({
                "exercise_id": ex_id,
                "exercise_name": ex_name,
                "unknown_parts": unknown,
            })
        else:
            pass_count += 1
    exercises_checked = len(rows)

    # Check (b) — sport_exercise_map × bridge
    sport_warnings: list[dict[str, Any]] = []
    sport_pass = 0
    with conn.cursor() as cur:
        cur.execute(
            """
            SELECT DISTINCT sport_name
              FROM layer0.sport_exercise_map
             WHERE superseded_at IS NULL
            """
        )
        sport_names = [r[0] for r in cur.fetchall()]
    for sn in sport_names:
        if sn.lower() in bridge_sports:
            sport_pass += 1
        else:
            sport_warnings.append({"sport_name": sn})

    return {
        "exercises_checked": exercises_checked,
        "pass_count": pass_count,
        "warn_count": len(exercise_warnings),
        "exercise_warnings": exercise_warnings,
        "sport_names_checked": len(sport_names),
        "sport_pass": sport_pass,
        "sport_warn": len(sport_warnings),
        "sport_warnings": sport_warnings,
    }


def _load_canonical_set(conn, table: str, column: str) -> set[str]:
    out: set[str] = set()
    with conn.cursor() as cur:
        cur.execute(
            f"SELECT {column} FROM {table} WHERE superseded_at IS NULL"
        )
        for (val,) in cur.fetchall():
            if val is not None:
                out.add(str(val).strip().lower())
    return out
