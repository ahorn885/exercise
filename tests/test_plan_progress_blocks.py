"""Tests for the #321 plan-gen observability progress-block substrate
(`plan_sessions_repo.snapshot_progress_blocks` / `load_progress_blocks`).

Uses the `_FakeConn` echo pattern shared with `tests/test_plan_sessions_repo.py`
(SQL + params recorded; queued responses returned FIFO) — no live DB.

Covers:
- snapshot: one upsert per cached block; the windowed `layer4_cache` SELECT;
  sessions/metadata copied verbatim to JSONB; None metadata → NULL; empty → no-op.
- load: phase_idx ordering; dual-path JSONB hydration (list, JSON-string, None).
- guardrail: the progress table is never referenced by the cache-key module.
"""
from __future__ import annotations

import inspect
import json

from plan_sessions_repo import load_progress_blocks, snapshot_progress_blocks


class _FakeRow(dict):
    def __getitem__(self, key):
        if isinstance(key, int):
            return list(self.values())[key]
        return super().__getitem__(key)


class _FakeCursor:
    def __init__(self, row=None, rows=None):
        self._row = row
        self._rows = rows or []

    def fetchone(self):
        return _FakeRow(self._row) if self._row else None

    def fetchall(self):
        return [_FakeRow(r) for r in self._rows]


class _FakeConn:
    def __init__(self):
        self.calls: list[tuple[str, tuple]] = []
        self.responses: list[tuple] = []

    def queue(self, row=None, rows=None):
        self.responses.append((row, rows or []))

    def execute(self, sql, params=()):
        self.calls.append((sql, params))
        if self.responses:
            row, rows = self.responses.pop(0)
        else:
            row, rows = None, []
        return _FakeCursor(row=row, rows=rows)

    def commit(self):
        pass


# ─── snapshot_progress_blocks ────────────────────────────────────────────────


def test_snapshot_upserts_one_row_per_cached_block():
    conn = _FakeConn()
    conn.queue(rows=[
        {"phase_idx": 0, "phase_name": "Base",
         "payload_json": {"sessions": [{"session_id": "S1"}],
                          "synthesis_metadata": {"accepted": True}}},
        {"phase_idx": 1, "phase_name": "Build",
         "payload_json": {"sessions": [], "synthesis_metadata": None}},
    ])

    n = snapshot_progress_blocks(
        conn, user_id=7, plan_version_id=42, seam_phase_idx_base=10000
    )

    assert n == 2
    # First call: the windowed read from layer4_cache (NOT the progress table).
    sql0, params0 = conn.calls[0]
    assert "FROM layer4_cache" in sql0
    assert "entry_point = 'plan_create'" in sql0
    assert params0 == (42, 7, 7, 10000)
    # Then one idempotent upsert per block.
    assert len(conn.calls) == 3
    sql1, params1 = conn.calls[1]
    assert "INSERT INTO plan_progress_blocks" in sql1
    assert "ON CONFLICT (plan_version_id, phase_idx) DO UPDATE" in sql1
    assert params1[:4] == (42, 7, 0, "Base")
    assert json.loads(params1[4]) == [{"session_id": "S1"}]
    assert json.loads(params1[5]) == {"accepted": True}
    # Block with no metadata → NULL (not the string "null").
    _, params2 = conn.calls[2]
    assert params2[5] is None
    assert json.loads(params2[4]) == []


def test_snapshot_no_cached_blocks_is_noop():
    conn = _FakeConn()
    conn.queue(rows=[])  # the SELECT returns nothing
    n = snapshot_progress_blocks(
        conn, user_id=1, plan_version_id=2, seam_phase_idx_base=10000
    )
    assert n == 0
    assert len(conn.calls) == 1  # only the SELECT, no upserts


# ─── load_progress_blocks ────────────────────────────────────────────────────


def test_load_hydrates_orders_and_tolerates_json_string():
    conn = _FakeConn()
    conn.queue(rows=[
        {"phase_idx": 0, "phase_name": "Base",
         "sessions_json": [{"date": "2026-06-01"}],          # native list (psycopg2)
         "synthesis_metadata_json": {"accepted": True},
         "snapshot_at": "t0"},
        {"phase_idx": 1, "phase_name": "Build",
         "sessions_json": "[]",                               # JSON string (shim path)
         "synthesis_metadata_json": None,
         "snapshot_at": "t1"},
    ])

    blocks = load_progress_blocks(conn, plan_version_id=42)

    assert [b["phase_idx"] for b in blocks] == [0, 1]
    assert blocks[0]["phase_name"] == "Base"
    assert blocks[0]["sessions"] == [{"date": "2026-06-01"}]
    assert blocks[0]["synthesis_metadata"] == {"accepted": True}
    # JSON-string column + None metadata both tolerated.
    assert blocks[1]["sessions"] == []
    assert blocks[1]["synthesis_metadata"] is None

    sql, params = conn.calls[0]
    assert "FROM plan_progress_blocks" in sql
    assert "ORDER BY phase_idx" in sql
    assert params == (42,)


# ─── determinism guardrail ───────────────────────────────────────────────────


def test_progress_blocks_never_feeds_a_cache_key():
    # #321/#199/#202/#294 — the durable progress table is a WRITE-ONLY
    # observability side effect. If it ever appears in the cache-key module,
    # it could reintroduce per-pass non-determinism.
    import layer4.hashing as hashing
    src = inspect.getsource(hashing)
    assert "plan_progress_blocks" not in src
    assert "progress_block" not in src
