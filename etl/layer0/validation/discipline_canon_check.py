"""Discipline-canon conformance validator.

Belt-and-suspenders guard: after load, every discipline-bearing row must carry
a canonical id and the matching canonical name. The ETL transforms in
`discipline_canon` guarantee this at build time; this check fails loudly at
ERROR level if anything ever bypasses them (manual SQL, a stale migration, a
new source variant slipping through).
"""
from __future__ import annotations

from typing import Any

from etl.layer0.discipline_canon import CANONICAL_NAMES

# (table, id_column, name_column). NULL id rows are skipped for id/name checks
# (they are the kept non-discipline phase-load rows).
_ID_NAME_TABLES: tuple[tuple[str, str, str], ...] = (
    ("layer0.disciplines", "discipline_id", "discipline_name"),
    ("layer0.sport_discipline_map", "discipline_id", "discipline_name"),
    ("layer0.sport_discipline_bridge", "discipline_id", "discipline_name"),
    ("layer0.phase_load_allocation", "discipline_id", "discipline_name"),
    ("layer0.discipline_training_gaps", "discipline_id", "discipline_name"),
    ("layer0.discipline_substitutes", "target_id", "target_name"),
    ("layer0.discipline_substitutes", "substitute_id", "substitute_name"),
)


def run_discipline_canon_conformance(conn) -> dict[str, Any]:
    errors: list[dict[str, Any]] = []
    rows_checked = 0
    for table, id_col, name_col in _ID_NAME_TABLES:
        with conn.cursor() as cur:
            cur.execute(
                f"SELECT {id_col}, {name_col} FROM {table} "
                f"WHERE superseded_at IS NULL AND {id_col} IS NOT NULL"
            )
            rows = cur.fetchall()
        for disc_id, disc_name in rows:
            rows_checked += 1
            expected = CANONICAL_NAMES.get(disc_id)
            if expected is None:
                errors.append({
                    "table": table, "column": id_col,
                    "discipline_id": disc_id, "discipline_name": disc_name,
                    "problem": "non-canonical id",
                })
            elif disc_name != expected:
                errors.append({
                    "table": table, "column": name_col,
                    "discipline_id": disc_id, "discipline_name": disc_name,
                    "expected": expected, "problem": "non-canonical name",
                })
    return {
        "rows_checked": rows_checked,
        "pass_count": rows_checked - len(errors),
        "error_count": len(errors),
        "errors": errors,
    }
