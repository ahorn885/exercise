"""Layer 0 ETL — SQL emitter.

Variant of `etl/layer0/run.py` that captures all SQL statements instead
of executing them. Output: a single .sql file you can paste into Neon's
SQL editor.

Usage:
    python -m etl.layer0.emit_sql --version-tag 1.4.0
    → writes etl/output/layer0_etl_v{tag}.sql

Reuses the same Excel parsing, canon transforms, and insert_versioned
logic as `run.py` — only the DB connection is faked. SQL is emitted
with all parameters inlined so the file is standalone.

Validators are skipped (no-op'd). They're read-only QA — run them
manually if needed after applying the SQL.
"""
from __future__ import annotations

import argparse
import json
import sys
from contextlib import contextmanager
from datetime import datetime
from pathlib import Path
from typing import Any

from psycopg2.extras import Json


# ─── SQL literal formatter ────────────────────────────────────────────


def lit(v: Any) -> str:
    """Inline a Python value as a SQL literal."""
    if v is None:
        return "NULL"
    if isinstance(v, bool):
        return "TRUE" if v else "FALSE"
    if isinstance(v, (int, float)):
        return str(v)
    if isinstance(v, datetime):
        return f"'{v.isoformat()}'::timestamptz"
    if isinstance(v, Json):
        payload = json.dumps(v.adapted, default=str)
        return "'" + payload.replace("'", "''") + "'::jsonb"
    if isinstance(v, str):
        return "'" + v.replace("'", "''") + "'"
    if isinstance(v, list):
        if not v:
            return "ARRAY[]::TEXT[]"
        elems = [lit(e) for e in v]
        return f"ARRAY[{','.join(elems)}]"
    if isinstance(v, dict):
        payload = json.dumps(v, default=str)
        return "'" + payload.replace("'", "''") + "'::jsonb"
    raise TypeError(f"Unhandled literal type: {type(v).__name__}: {v!r}")


def inline_params(sql: str, params: tuple | list) -> str:
    """Substitute %s placeholders with literal values."""
    parts = sql.split("%s")
    expected = len(parts) - 1
    if expected != len(params):
        raise ValueError(
            f"placeholder mismatch: SQL has {expected} %s, got {len(params)} params\n"
            f"SQL: {sql[:200]}"
        )
    out = ""
    for i, p in enumerate(parts):
        out += p
        if i < len(params):
            out += lit(params[i])
    return out


# ─── Fake psycopg2 connection ─────────────────────────────────────────


class FakeCursor:
    def __init__(self, sql_buf: list[str]):
        self.sql_buf = sql_buf
        self._rowcount = 0

    def __enter__(self):
        return self

    def __exit__(self, *args):
        return False

    def execute(self, sql: str, params: tuple | list | None = None) -> None:
        if params:
            stmt = inline_params(sql, params)
        else:
            stmt = sql
        stmt = stmt.strip()
        if stmt.upper().startswith("SELECT"):
            # Read-only QA query (validators). Drop on the floor — irrelevant
            # to SQL emission. Caller's fetchone()/fetchall() returns empty.
            return
        if not stmt.endswith(";"):
            stmt += ";"
        self.sql_buf.append(stmt + "\n")

    def fetchone(self) -> tuple:
        return (0,)

    def fetchall(self) -> list:
        return []

    @property
    def rowcount(self) -> int:
        return 0


class FakeConn:
    def __init__(self, sql_buf: list[str]):
        self.sql_buf = sql_buf
        self._cursor = FakeCursor(sql_buf)

    def cursor(self) -> FakeCursor:
        return self._cursor

    def commit(self) -> None:
        pass

    def close(self) -> None:
        pass


# ─── execute_values shim ──────────────────────────────────────────────


def fake_execute_values(cur, sql: str, argslist, template: str | None = None) -> None:
    """Mimic psycopg2.extras.execute_values for the FakeCursor.

    Expands `argslist` into multi-row VALUES, replacing the `%s` in `sql`.
    `template` is a per-row format like `(%s,%s,%s)`.
    """
    if not argslist:
        return
    if template is None:
        # Default template = (%s, %s, ..., %s) matching arity
        n = len(argslist[0])
        template = "(" + ",".join(["%s"] * n) + ")"

    rows_sql = []
    for args in argslist:
        rows_sql.append(inline_params(template, args))

    final_sql = sql.replace("%s", ",\n  ".join(rows_sql))
    cur.execute(final_sql.strip() + ";")


# ─── Validators — skip ───────────────────────────────────────────────


def _noop_validator(*args, **kwargs) -> dict:
    return {
        "sports_checked": 0, "pass_count": 0, "warn_count": 0,
        "exercises_checked": 0, "sport_names_checked": 0,
        "sport_pass": 0, "sport_warn": 0,
        "rows_checked": 0, "error_count": 0,
    }


def _noop_report(*args, **kwargs) -> str:
    return "(SQL-emit mode: no validation report)"


# ─── Main ────────────────────────────────────────────────────────────


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Emit Layer 0 ETL as a single .sql file."
    )
    parser.add_argument("--version-tag", required=True)
    parser.add_argument(
        "--output",
        default=None,
        help="Output .sql path (default: etl/output/layer0_etl_v{tag}.sql)",
    )
    args = parser.parse_args(argv)
    tag = args.version_tag.strip()

    sql_buf: list[str] = []

    # ── Header
    sql_buf.append(f"-- Layer 0 ETL — emitted SQL for Neon SQL editor\n")
    sql_buf.append(f"-- Version tag: {tag}\n")
    from etl.layer0.run import SPORTS_XLSX as _sports_xlsx
    sql_buf.append(f"-- Source: etl/sources/{_sports_xlsx.name}\n")
    sql_buf.append(f"-- Emitted at: {datetime.utcnow().isoformat()}Z\n")
    sql_buf.append("-- Paste this entire file into Neon's SQL editor.\n")
    sql_buf.append("-- Idempotent: re-runs under the same --version-tag refresh in place.\n")
    sql_buf.append("\n")
    sql_buf.append("BEGIN;\n")
    sql_buf.append("\n")

    # ── Schema (idempotent CREATE IF NOT EXISTS)
    schema_path = Path(__file__).parent / "schema.sql"
    if schema_path.exists():
        sql_buf.append("-- ── Schema (idempotent — CREATE IF NOT EXISTS) ──\n")
        sql_buf.append(schema_path.read_text(encoding="utf-8"))
        sql_buf.append("\n\n")

    # ── Patch db.connect() + validators + report
    import etl.layer0.db as db_mod
    import etl.layer0.run as run_mod
    from etl.layer0.validation import (
        contraindicated_conditions, default_inclusion,
        discipline_canon_check, fk_checks, report, sum_to_100, vocab_alignment,
    )

    fake_conn = FakeConn(sql_buf)

    @contextmanager
    def fake_connect():
        yield fake_conn

    db_mod.connect = fake_connect
    db_mod.apply_schema = lambda conn: None  # schema already emitted above

    # Patch execute_values used by insert_versioned
    db_mod.execute_values = fake_execute_values
    run_mod.insert_versioned.__globals__["execute_values"] = fake_execute_values

    # Patch validators to no-ops
    run_mod.run_sum_to_100 = _noop_validator
    run_mod.run_vocab_alignment = _noop_validator
    run_mod.run_substitution_fks = _noop_validator
    run_mod.run_training_gap_fks = _noop_validator
    run_mod.run_contraindicated_conditions = _noop_validator
    run_mod.run_default_inclusion = _noop_validator
    run_mod.run_discipline_canon_conformance = _noop_validator
    run_mod.build_report = _noop_report

    # Run the ETL
    sql_buf.append("-- ── Data inserts (Phase 1 vocab + Phase 2 sports + Phase 3 bridge + 0B) ──\n")
    rc = run_mod.main(["--version-tag", tag])
    if rc != 0:
        print(f"ETL exit code: {rc}", file=sys.stderr)
        return rc

    sql_buf.append("\nCOMMIT;\n")

    # ── Write output
    out_path = (
        Path(args.output)
        if args.output
        else Path(__file__).parent.parent / "output" / f"layer0_etl_v{tag}.sql"
    )
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text("".join(sql_buf), encoding="utf-8")
    print(f"Wrote {out_path}")
    print(f"  {len(sql_buf)} segments, {out_path.stat().st_size:,} bytes")
    return 0


if __name__ == "__main__":
    sys.exit(main())
