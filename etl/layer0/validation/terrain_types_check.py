"""Terrain-types structural integrity over `layer0.terrain_types`.

Rebuilds, DB-side, the integrity coverage that the frozen
`tests/test_bucket_c_terrain_vocab_audit.py` provided over the code-side
`_TERRAIN_STRUCTURED_ROWS` constant — retired with the xlsx-authoring freeze
(2026-06-11, epic #488). The spreadsheet source is gone; the DB is canonical, so
the guard moves onto the active terrain set.

Checks (growth-tolerant — no row-count or specific-id snapshot assertions; those
suited a frozen constant, not a living table):

1. **`terrain_id` well-formed** — every active row's `terrain_id` matches
   `TRN-NNN` (3 digits). Catches a NULL or malformed id (e.g. a row inserted
   before the `terrain_id` column, or a typo).
2. **`terrain_id` unique** within the active set — the DB UNIQUE is on
   `(terrain_id, etl_version)`, so a per-table version bump could leave two
   active rows sharing an id; this catches that.
3. **`canonical_name` unique** within the active set — same reasoning.

Layer 2B's terrain classifier resolves race/locale terrain by `terrain_id`, so a
malformed or duplicate id silently corrupts gap lookups.

Severity: ERROR (decision C — every `validate_layer0` check FAILs; no waiver).
"""
from __future__ import annotations

import re
from collections import Counter
from typing import Any

_TRN_PATTERN = re.compile(r"^TRN-\d{3}$")
_NULL = "<null>"


def check_terrain_rows(rows: list[dict]) -> dict[str, Any]:
    """Pure logic over active terrain rows (`[{terrain_id, canonical_name}, ...]`).

    Returns `{rows_checked, pass_count, error_count, malformed_ids,
    duplicate_ids, duplicate_names}`.
    """
    malformed_ids = sorted(
        {(r["terrain_id"] or _NULL) for r in rows
         if not (r["terrain_id"] and _TRN_PATTERN.match(r["terrain_id"]))}
    )

    id_counts = Counter(r["terrain_id"] for r in rows if r["terrain_id"])
    duplicate_ids = sorted(tid for tid, c in id_counts.items() if c > 1)

    name_counts = Counter(r["canonical_name"] for r in rows if r["canonical_name"])
    duplicate_names = sorted(n for n, c in name_counts.items() if c > 1)

    error_count = len(malformed_ids) + len(duplicate_ids) + len(duplicate_names)
    return {
        "rows_checked": len(rows),
        "pass_count": len(rows) - error_count,
        "error_count": error_count,
        "malformed_ids": malformed_ids,
        "duplicate_ids": duplicate_ids,
        "duplicate_names": duplicate_names,
    }


def run_terrain_types(conn) -> dict[str, Any]:
    """Check structural integrity of the active `layer0.terrain_types` set."""
    with conn.cursor() as cur:
        cur.execute(
            """
            SELECT terrain_id, canonical_name
              FROM layer0.terrain_types
             WHERE superseded_at IS NULL
            """
        )
        rows = [{"terrain_id": r[0], "canonical_name": r[1]} for r in cur.fetchall()]
    return check_terrain_rows(rows)
