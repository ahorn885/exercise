"""Layer 0 ETL — Postgres connection + versioned-INSERT helpers.

Postgres-only. Reads `DATABASE_URL` from the environment. The dual-backend
SQLite shim in the existing app's `database.py` is intentionally not
reused — Layer 0 is being written for the v2 architecture which is
Postgres-only.
"""
from __future__ import annotations

import json
import os
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable, Iterator, Sequence

import psycopg2
from psycopg2.extras import Json, execute_values

SCHEMA_PATH = Path(__file__).parent / "schema.sql"


def _database_url() -> str:
    url = os.environ.get("DATABASE_URL")
    if not url:
        raise RuntimeError(
            "DATABASE_URL is not set. Layer 0 ETL requires a Postgres "
            "connection string (e.g. the Neon URL used by the existing app)."
        )
    return url


@contextmanager
def connect() -> Iterator[psycopg2.extensions.connection]:
    conn = psycopg2.connect(_database_url())
    try:
        yield conn
    finally:
        conn.close()


def apply_schema(conn: psycopg2.extensions.connection) -> None:
    """Run schema.sql. Idempotent — every CREATE uses IF NOT EXISTS."""
    sql = SCHEMA_PATH.read_text(encoding="utf-8")
    with conn.cursor() as cur:
        cur.execute(sql)
    conn.commit()


def now_utc() -> datetime:
    return datetime.now(timezone.utc)


def _adapt(value: Any) -> Any:
    """Wrap dicts/lists destined for JSONB columns."""
    if isinstance(value, (dict, list)) and not _is_pg_array_target(value):
        # heuristic: lists meant for TEXT[] are passed as Python list and
        # psycopg2 handles them; dicts always become JSON. The JSONB columns
        # are explicitly wrapped at call sites via to_jsonb().
        return value
    return value


def _is_pg_array_target(value: Any) -> bool:
    return isinstance(value, list) and all(
        v is None or isinstance(v, (str, int, float, bool)) for v in value
    )


def to_jsonb(value: Any) -> Json:
    """Wrap a Python dict/list for insertion into a JSONB column."""
    return Json(value)


def insert_versioned(
    conn: psycopg2.extensions.connection,
    table: str,                       # fully qualified, e.g. "layer0.sports"
    columns: Sequence[str],           # data columns (excluding etl_*, superseded_at)
    rows: Iterable[Sequence[Any]],
    etl_version: str,
    etl_run_at: datetime,
    *,
    source_family: str,               # "0A" | "0B" | "0C" — for supersede scoping
    version_prefix: str | None = None,  # e.g. "0A-v" — used to scope supersede
) -> int:
    """Insert rows for a new version.

    Steps:
      1. Delete existing rows of this `etl_version` (idempotent re-run).
      2. Mark prior versions of the same source family as superseded
         (sets superseded_at where it was NULL and version != current).
      3. Insert new rows with etl_version, etl_run_at, superseded_at=NULL.

    Supersede MUST run before the insert: tables with a partial-unique
    index on active rows (e.g. layer0.equipment_items'
    `equipment_items_active_ci_name_idx` on lower(canonical_name) WHERE
    superseded_at IS NULL) would otherwise see two active versions of the
    same key coexist during the insert and raise a UniqueViolation.

    Source-family scoping prevents (e.g.) a 0A re-run from superseding
    0C vocabulary rows that haven't changed.

    Returns the number of rows inserted.
    """
    rows = list(rows)
    prefix = version_prefix or _default_prefix(source_family)
    full_columns = list(columns) + ["etl_version", "etl_run_at"]

    with conn.cursor() as cur:
        # 1. Idempotent delete
        cur.execute(
            f"DELETE FROM {table} WHERE etl_version = %s",
            (etl_version,),
        )

        # 2. Supersede older rows of the same source family. Done BEFORE
        #    the insert so a partial-unique-on-active index never sees two
        #    active versions of the same key at once.
        cur.execute(
            f"""
            UPDATE {table}
               SET superseded_at = %s
             WHERE superseded_at IS NULL
               AND etl_version <> %s
               AND etl_version LIKE %s
            """,
            (etl_run_at, etl_version, prefix + "%"),
        )

        # 3. Insert new rows
        if rows:
            values = [tuple(list(r) + [etl_version, etl_run_at]) for r in rows]
            placeholders = "(" + ",".join(["%s"] * len(full_columns)) + ")"
            execute_values(
                cur,
                f"INSERT INTO {table} ({','.join(full_columns)}) VALUES %s",
                values,
                template=placeholders,
            )

    conn.commit()
    return len(rows)


def _default_prefix(source_family: str) -> str:
    sf = source_family.upper()
    if sf not in {"0A", "0B", "0C"}:
        raise ValueError(f"Unknown source family: {source_family!r}")
    return f"{sf}-v"


def count_current(conn: psycopg2.extensions.connection, table: str) -> int:
    with conn.cursor() as cur:
        cur.execute(f"SELECT COUNT(*) FROM {table} WHERE superseded_at IS NULL")
        return int(cur.fetchone()[0])
