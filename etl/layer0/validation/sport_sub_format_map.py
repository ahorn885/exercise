"""Validate `layer0.sport_sub_format_map` (#254 / D-17).

The table maps the five top-level sports whose `phase_load_allocation` rows are
sub-format-named (Triathlon, Skimo, LDC, Canoe/Kayak Marathon, OWMS) to their
PLA sub-formats, with one curated default per parent. Three invariants:

  (a) exactly one `is_default` per `parent_sport`;
  (b) every `sub_format_sport` is a live `phase_load_allocation.sport_name`;
  (c) the `parent_sport` set equals the data-derived mismatched-parent set —
      `sport_discipline_bridge` framework_sports with NO same-named PLA row.

Any breach → ERROR. Mirrors the in-migration verify in 0033; this is the
CI-gate guard against later drift (a new sub-format PLA row, a renamed sport).
"""
from __future__ import annotations

from typing import Any


def run_sport_sub_format_map(conn) -> dict[str, Any]:
    errors: list[dict[str, Any]] = []
    with conn.cursor() as cur:
        # The table is introduced by migration 0033; tolerate its absence so the
        # gate still runs against a pre-0033 baseline (returns a clean pass).
        cur.execute(
            "SELECT to_regclass('layer0.sport_sub_format_map') IS NOT NULL"
        )
        if not cur.fetchone()[0]:
            return {"rows_checked": 0, "pass_count": 0, "error_count": 0,
                    "errors": [], "skipped": True}

        # (a) exactly one default per parent
        cur.execute(
            """
            SELECT parent_sport, count(*) FILTER (WHERE is_default) AS n_default
              FROM layer0.sport_sub_format_map
             WHERE superseded_at IS NULL
             GROUP BY parent_sport
            HAVING count(*) FILTER (WHERE is_default) <> 1
            """
        )
        for parent, n_default in cur.fetchall():
            errors.append({"id": parent,
                           "detail": f"has {n_default} defaults, expected exactly 1"})

        # (b) every sub_format_sport exists in PLA
        cur.execute(
            """
            SELECT m.sub_format_sport
              FROM layer0.sport_sub_format_map m
             WHERE m.superseded_at IS NULL
               AND NOT EXISTS (
                   SELECT 1 FROM layer0.phase_load_allocation p
                    WHERE p.superseded_at IS NULL
                      AND p.sport_name = m.sub_format_sport)
            """
        )
        for (sub_format,) in cur.fetchall():
            errors.append({"id": sub_format,
                           "detail": "absent from phase_load_allocation.sport_name"})

        # (c) parent set == bridge framework_sports lacking a same-named PLA row
        cur.execute(
            """
            WITH mapped AS (
                SELECT DISTINCT parent_sport AS s
                  FROM layer0.sport_sub_format_map WHERE superseded_at IS NULL
            ),
            derived AS (
                SELECT DISTINCT b.framework_sport AS s
                  FROM layer0.sport_discipline_bridge b
                 WHERE b.superseded_at IS NULL
                   AND NOT EXISTS (
                       SELECT 1 FROM layer0.phase_load_allocation p
                        WHERE p.superseded_at IS NULL
                          AND p.sport_name = b.framework_sport)
            )
            SELECT s, 'mapped but not a mismatched parent' AS detail FROM mapped
             WHERE s NOT IN (SELECT s FROM derived)
            UNION ALL
            SELECT s, 'mismatched parent not mapped' AS detail FROM derived
             WHERE s NOT IN (SELECT s FROM mapped)
            """
        )
        for s, detail in cur.fetchall():
            errors.append({"id": s, "detail": detail})

        cur.execute(
            "SELECT count(*) FROM layer0.sport_sub_format_map WHERE superseded_at IS NULL"
        )
        rows_checked = cur.fetchone()[0]

    return {
        "rows_checked": rows_checked,
        "pass_count": rows_checked - len(errors),
        "error_count": len(errors),
        "errors": errors,
    }
