"""Postgres-backed `CacheBackend` for Layer 4 cache rows.

Reads + writes against the `layer4_cache` table defined in
`init_db.py` `_PG_MIGRATIONS`. The table schema is:

    cache_key TEXT NOT NULL,
    phase_idx INTEGER NOT NULL DEFAULT -1,
    user_id INTEGER NOT NULL REFERENCES users(id),
    entry_point TEXT NOT NULL,
    phase_name TEXT,
    payload_json JSONB NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    last_hit_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    hit_count INTEGER NOT NULL DEFAULT 0,
    PRIMARY KEY (cache_key, phase_idx)

The backend accepts a `db_conn_factory` callable returning a connection
with `.execute(sql, params)` + `.commit()` matching the project's
`database._PgConn` shape. Tests inject a fake; production uses
`database.get_db`.

This module is import-safe without `psycopg2` installed — the connection
is acquired lazily through the injected factory.
"""

from __future__ import annotations

import json
from datetime import datetime
from typing import Callable

from layer4.cache import (
    PER_ENTRY_PHASE_IDX_SENTINEL,
    VALID_ENTRY_POINTS,
    CacheBackend,
    CacheEntry,
    EntryPoint,
)


DbConnFactory = Callable[[], "_DbConnProtocol"]
"""Returns an object with `.execute(sql, params)` + `.commit()`. Matches
`database._PgConn`. Tests pass a fake; production passes `database.get_db`.
"""


class _DbConnProtocol:
    """Structural protocol for the connection objects accepted by
    `PostgresCacheBackend`. NOT instantiated; documentation only."""

    def execute(self, sql: str, params: tuple = ()):  # type: ignore[empty-body]
        ...

    def commit(self) -> None:  # type: ignore[empty-body]
        ...


class PostgresCacheBackend(CacheBackend):
    """`layer4_cache` table-backed implementation.

    Each method opens a connection via the factory, runs its SQL, commits
    (for writes), and returns. The factory is responsible for connection
    lifecycle — `database.get_db()` reuses a per-request connection via
    `flask.g`; the test factory typically returns a fresh in-memory
    connection per call.
    """

    def __init__(self, db_conn_factory: DbConnFactory) -> None:
        self._factory = db_conn_factory

    def get(
        self,
        cache_key: str,
        phase_idx: int = PER_ENTRY_PHASE_IDX_SENTINEL,
    ) -> CacheEntry | None:
        db = self._factory()
        row = db.execute(
            "SELECT cache_key, phase_idx, user_id, entry_point, phase_name, "
            "payload_json, created_at, last_hit_at, hit_count "
            "FROM layer4_cache WHERE cache_key = ? AND phase_idx = ?",
            (cache_key, phase_idx),
        ).fetchone()
        if row is None:
            return None

        # Bump hit_count + last_hit_at as a side-effect of a successful read.
        db.execute(
            "UPDATE layer4_cache SET hit_count = hit_count + 1, "
            "last_hit_at = NOW() WHERE cache_key = ? AND phase_idx = ?",
            (cache_key, phase_idx),
        )
        db.commit()

        return CacheEntry(
            cache_key=row["cache_key"],
            phase_idx=row["phase_idx"],
            user_id=row["user_id"],
            entry_point=row["entry_point"],
            phase_name=row["phase_name"],
            payload_json=_payload_json_to_str(row["payload_json"]),
            created_at=_coerce_datetime(row["created_at"]),
            last_hit_at=_coerce_datetime(row["last_hit_at"]),
            hit_count=int(row["hit_count"]) + 1,  # reflect the bump above
        )

    def put(
        self,
        *,
        cache_key: str,
        phase_idx: int,
        user_id: int,
        entry_point: EntryPoint,
        phase_name: str | None,
        payload_json: str,
    ) -> None:
        if entry_point not in VALID_ENTRY_POINTS:
            raise ValueError(f"unknown entry_point={entry_point!r}")
        if phase_idx < 0 and phase_idx != PER_ENTRY_PHASE_IDX_SENTINEL:
            raise ValueError(
                f"phase_idx must be >= 0 or {PER_ENTRY_PHASE_IDX_SENTINEL}; got {phase_idx}"
            )
        if phase_idx >= 0 and phase_name is None:
            raise ValueError("phase_name required for per-phase rows (phase_idx >= 0)")
        if phase_idx == PER_ENTRY_PHASE_IDX_SENTINEL and phase_name is not None:
            raise ValueError("phase_name must be None for per-entry rows")

        db = self._factory()
        # Upsert via ON CONFLICT — re-run replaces the cached row.
        db.execute(
            "INSERT INTO layer4_cache "
            "(cache_key, phase_idx, user_id, entry_point, phase_name, payload_json) "
            "VALUES (?, ?, ?, ?, ?, ?::jsonb) "
            "ON CONFLICT (cache_key, phase_idx) DO UPDATE SET "
            "  user_id = EXCLUDED.user_id, "
            "  entry_point = EXCLUDED.entry_point, "
            "  phase_name = EXCLUDED.phase_name, "
            "  payload_json = EXCLUDED.payload_json, "
            "  created_at = NOW(), "
            "  last_hit_at = NOW(), "
            "  hit_count = 0",
            (cache_key, phase_idx, user_id, entry_point, phase_name, payload_json),
        )
        db.commit()

    def evict_for_user(
        self,
        user_id: int,
        *,
        entry_points: tuple[EntryPoint, ...] | None = None,
    ) -> int:
        db = self._factory()
        if entry_points is None:
            row = db.execute(
                "WITH d AS (DELETE FROM layer4_cache WHERE user_id = ? RETURNING 1) "
                "SELECT COUNT(*) AS deleted FROM d",
                (user_id,),
            ).fetchone()
        else:
            for ep in entry_points:
                if ep not in VALID_ENTRY_POINTS:
                    raise ValueError(f"unknown entry_point={ep!r}")
            # Build a (?, ?, ...) tuple for the IN clause.
            placeholders = ",".join(["?"] * len(entry_points))
            row = db.execute(
                f"WITH d AS (DELETE FROM layer4_cache WHERE user_id = ? AND entry_point IN ({placeholders}) RETURNING 1) "
                "SELECT COUNT(*) AS deleted FROM d",
                (user_id, *entry_points),
            ).fetchone()
        db.commit()
        return int(row["deleted"]) if row else 0

    def evict_entry_point(
        self,
        entry_point: EntryPoint,
        *,
        user_id: int | None = None,
    ) -> int:
        if entry_point not in VALID_ENTRY_POINTS:
            raise ValueError(f"unknown entry_point={entry_point!r}")
        db = self._factory()
        if user_id is None:
            row = db.execute(
                "WITH d AS (DELETE FROM layer4_cache WHERE entry_point = ? RETURNING 1) "
                "SELECT COUNT(*) AS deleted FROM d",
                (entry_point,),
            ).fetchone()
        else:
            row = db.execute(
                "WITH d AS (DELETE FROM layer4_cache WHERE entry_point = ? AND user_id = ? RETURNING 1) "
                "SELECT COUNT(*) AS deleted FROM d",
                (entry_point, user_id),
            ).fetchone()
        db.commit()
        return int(row["deleted"]) if row else 0

    def clear_all(self) -> int:
        db = self._factory()
        row = db.execute(
            "WITH d AS (DELETE FROM layer4_cache RETURNING 1) "
            "SELECT COUNT(*) AS deleted FROM d"
        ).fetchone()
        db.commit()
        return int(row["deleted"]) if row else 0


def _payload_json_to_str(value) -> str:
    """psycopg2's RealDictCursor returns JSONB columns as Python dicts —
    re-serialize to a string so `CacheEntry.payload_json` is always a
    canonical JSON string. Some drivers may return strings directly; pass
    those through.
    """
    if isinstance(value, str):
        return value
    return json.dumps(value, sort_keys=True, separators=(",", ":"))


def _coerce_datetime(value) -> datetime:
    """Postgres TIMESTAMPTZ → Python datetime (psycopg2 already coerces);
    accept ISO 8601 strings as a fallback for fake/test backends."""
    if isinstance(value, datetime):
        return value
    if isinstance(value, str):
        return datetime.fromisoformat(value)
    raise TypeError(f"cannot coerce {type(value).__name__} to datetime")
