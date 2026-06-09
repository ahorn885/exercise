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

from plan_sessions_repo import (
    load_plan_sessions_as_blocks,
    load_progress_blocks,
    snapshot_progress_blocks,
)


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


# ─── load_plan_sessions_as_blocks ────────────────────────────────────────────


def _payload_for_session(
    *,
    session_id: str,
    d: str,
    phase_name: str | None = "Base",
    week_in_phase: int = 1,
    discipline_id: str = "D-run",
    discipline_name: str = "Running",
    intensity_summary: str = "easy",
    duration_min: int = 45,
    coaching_intent: str = "Easy aerobic.",
) -> str:
    """Round-trippable PlanSession JSON for the load-as-blocks fallback test.
    Built as a string (the same shape `plan_sessions.payload_json` carries
    on the SQLite shim path) so the hydration path inside
    `load_plan_sessions_by_version` is exercised end-to-end."""
    pm = (
        {
            "phase_name": phase_name,
            "week_in_phase": week_in_phase,
            "total_weeks_in_phase": 4,
            "intended_volume_band": [5.0, 7.0],
            "intended_intensity_distribution": {"Z2": 1.0},
        }
        if phase_name is not None
        else None
    )
    payload = {
        "session_id": session_id,
        "plan_version_id": 46,
        "date": d,
        "day_of_week": "Mon",
        "session_index_in_day": 0,
        "time_of_day": "morning",
        "kind": "cardio",
        "discipline_id": discipline_id,
        "discipline_name": discipline_name,
        "locale_id": "home",
        "locale_name": "Home",
        "duration_min": duration_min,
        "intensity_summary": intensity_summary,
        "cardio_blocks": [
            {
                "block_kind": "main_set",
                "duration_min": duration_min,
                "intensity_zone": "Z2",
                "intensity_target": {"hr_bpm_low": 125, "hr_bpm_high": 140},
                "instructions": "Steady easy.",
            }
        ],
        "strength_exercises": None,
        "rest_reason": None,
        "phase_metadata": pm,
        "session_notes": "n",
        "coaching_intent": coaching_intent,
        "coaching_flags": [],
        "is_ad_hoc": False,
        "ad_hoc_request_payload": None,
    }
    return json.dumps(payload)


def test_load_as_blocks_groups_by_phase_and_week():
    """#333 — sessions group into one block per (phase_name, week_in_phase);
    blocks preserve session-emission order (first-seen wins in dict)."""
    conn = _FakeConn()
    conn.queue(rows=[
        {"payload_json": _payload_for_session(
            session_id="s1", d="2026-06-01",
            phase_name="Base", week_in_phase=1)},
        {"payload_json": _payload_for_session(
            session_id="s2", d="2026-06-03",
            phase_name="Base", week_in_phase=1)},
        {"payload_json": _payload_for_session(
            session_id="s3", d="2026-06-08",
            phase_name="Base", week_in_phase=2)},
        {"payload_json": _payload_for_session(
            session_id="s4", d="2026-06-15",
            phase_name="Build", week_in_phase=1)},
    ])

    blocks = load_plan_sessions_as_blocks(conn, plan_version_id=46)

    assert [b["phase_name"] for b in blocks] == [
        "Base · week 1", "Base · week 2", "Build · week 1",
    ]
    assert [b["phase_idx"] for b in blocks] == [0, 1, 2]
    assert [len(b["sessions"]) for b in blocks] == [2, 1, 1]
    # Per-session shape matches what plan_inspect.html reads off
    # plan_progress_blocks.sessions_json entries.
    s0 = blocks[0]["sessions"][0]
    assert s0["date"] == "2026-06-01"
    assert s0["discipline_name"] == "Running"
    assert s0["kind"] == "cardio"
    assert s0["duration_min"] == 45
    assert s0["intensity_summary"] == "easy"
    assert s0["coaching_intent"] == "Easy aerobic."
    # Per-pass signals are absent from this path — the template guards on them.
    assert blocks[0]["synthesis_metadata"] is None
    assert blocks[0]["snapshot_at"] is None


def test_load_as_blocks_no_sessions_returns_empty():
    """No persisted sessions → empty list; route surfaces the "even the fallback
    table is empty" copy."""
    conn = _FakeConn()
    conn.queue(rows=[])
    assert load_plan_sessions_as_blocks(conn, plan_version_id=999) == []


def test_load_as_blocks_buckets_no_phase_metadata_last():
    """Sessions with phase_metadata=None (Pattern B refresh / single_session_
    synthesize / ad-hoc) get one trailing `(no phase metadata)` block — not
    dropped, but not promoted ahead of named phases either."""
    conn = _FakeConn()
    conn.queue(rows=[
        {"payload_json": _payload_for_session(
            session_id="s1", d="2026-06-01", phase_name="Base", week_in_phase=1)},
        {"payload_json": _payload_for_session(
            session_id="s2", d="2026-06-02", phase_name=None)},
        {"payload_json": _payload_for_session(
            session_id="s3", d="2026-06-03", phase_name=None)},
    ])

    blocks = load_plan_sessions_as_blocks(conn, plan_version_id=46)

    assert [b["phase_name"] for b in blocks] == [
        "Base · week 1", "(no phase metadata)",
    ]
    assert len(blocks[1]["sessions"]) == 2


# ─── determinism guardrail ───────────────────────────────────────────────────


def test_progress_blocks_never_feeds_a_cache_key():
    # #321/#199/#202/#294 — the durable progress table is a WRITE-ONLY
    # observability side effect. If it ever appears in the cache-key module,
    # it could reintroduce per-pass non-determinism.
    import layer4.hashing as hashing
    src = inspect.getsource(hashing)
    assert "plan_progress_blocks" not in src
    assert "progress_block" not in src
