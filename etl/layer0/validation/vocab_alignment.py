"""Vocab alignment validation per spec §6.4.

Two checks (both informational — never fail the ETL):

(a) For every `contraindicated_parts[]` entry on `layer0.exercises`, verify
    each entry exists in `layer0.body_parts.canonical_name`.

(b) For every `sport_name` on `layer0.sport_exercise_map`, verify it exists
    in `layer0.sport_discipline_bridge.exercise_db_sport`. (Resolves spec
    Open Item #5.)

For (b), each unmapped sport name also gets:
    - the count of exercises tagged with that sport
    - up to 3 fuzzy-match candidates from the bridge vocabulary
    - the candidates' bridge framework_sport names
…so the human reconciliation can act from the report alone.
"""
from __future__ import annotations

from difflib import SequenceMatcher
from typing import Any


def run_vocab_alignment(conn) -> dict[str, Any]:
    body_parts_canon = _load_canonical_set(conn, "layer0.body_parts", "canonical_name")
    bridge_sports = _load_alias_exercise_sports(conn)
    bridge_framework_for = _load_alias_framework_lookup(conn)
    sport_exercise_counts = _load_sport_exercise_counts(conn)

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
            sport_warnings.append({
                "sport_name": sn,
                "exercise_count": sport_exercise_counts.get(sn, 0),
                "candidates": _suggest_candidates(sn, bridge_sports, bridge_framework_for),
            })

    # Sort warnings most-impactful first (highest exercise count)
    sport_warnings.sort(key=lambda w: -w["exercise_count"])

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


def _load_bridge_framework_lookup(conn) -> dict[str, list[str]]:
    """exercise_db_sport (lowercased) → list of distinct framework_sport names."""
    out: dict[str, list[str]] = {}
    with conn.cursor() as cur:
        cur.execute(
            """
            SELECT DISTINCT exercise_db_sport, framework_sport
              FROM layer0.sport_discipline_bridge
             WHERE superseded_at IS NULL
            """
        )
        for ex_sport, framework in cur.fetchall():
            key = ex_sport.strip().lower()
            out.setdefault(key, []).append(framework)
    return out


def _load_sport_exercise_counts(conn) -> dict[str, int]:
    out: dict[str, int] = {}
    with conn.cursor() as cur:
        cur.execute(
            """
            SELECT sport_name, COUNT(*)
              FROM layer0.sport_exercise_map
             WHERE superseded_at IS NULL
             GROUP BY sport_name
            """
        )
        for sport, count in cur.fetchall():
            out[sport] = int(count)
    return out


def _suggest_candidates(
    sport_name: str,
    bridge_sports: set[str],
    bridge_framework_for: dict[str, list[str]],
    max_candidates: int = 3,
    min_ratio: float = 0.55,
) -> list[dict[str, Any]]:
    """Return up to N closest bridge sports by string similarity, with the
    framework_sport(s) each maps to. Only suggestions ≥ min_ratio.
    """
    target = sport_name.lower()
    scored: list[tuple[float, str]] = []
    for candidate in bridge_sports:
        ratio = SequenceMatcher(None, target, candidate).ratio()
        if ratio >= min_ratio:
            scored.append((ratio, candidate))
    scored.sort(key=lambda t: -t[0])
    out: list[dict[str, Any]] = []
    for ratio, candidate in scored[:max_candidates]:
        out.append({
            "candidate": candidate,
            "ratio": round(ratio, 2),
            "framework_sports": sorted(bridge_framework_for.get(candidate, [])),
        })
    return out


def _load_alias_exercise_sports(conn) -> set[str]:
    """All exercise_db_sport values currently in the alias map (lowercased)."""
    out: set[str] = set()
    with conn.cursor() as cur:
        cur.execute(
            """
            SELECT DISTINCT exercise_db_sport
              FROM layer0.sport_name_aliases
             WHERE superseded_at IS NULL
            """
        )
        for (val,) in cur.fetchall():
            if val:
                out.add(val.strip().lower())
    return out


def _load_alias_framework_lookup(conn) -> dict[str, list[str]]:
    """exercise_db_sport (lowercased) → list of framework_sport names,
    sourced from the alias map."""
    out: dict[str, list[str]] = {}
    with conn.cursor() as cur:
        cur.execute(
            """
            SELECT DISTINCT exercise_db_sport, framework_sport
              FROM layer0.sport_name_aliases
             WHERE superseded_at IS NULL
            """
        )
        for ex_sport, framework in cur.fetchall():
            key = ex_sport.strip().lower()
            out.setdefault(key, []).append(framework)
    return out
