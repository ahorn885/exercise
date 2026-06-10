"""Tests for `athlete_discipline_weighting_repo.py` + the orchestrator unpack
(X2, 2026-06-10). Uses the `_FakeConn` pattern (no real DB)."""
from __future__ import annotations

from types import SimpleNamespace

import pytest

from athlete_discipline_weighting_repo import (
    DisciplineWeightingError,
    get_discipline_weighting,
    load_discipline_catalog,
    replace_discipline_weighting,
)
from layer4.context import DisciplineWeightRecord
from layer4.orchestrator import _athlete_discipline_overrides


class _FakeRow(dict):
    def __getitem__(self, key):
        if isinstance(key, int):
            return list(self.values())[key]
        return super().__getitem__(key)


class _FakeCursor:
    def __init__(self, rows=None):
        self._rows = rows or []

    def fetchall(self):
        return [_FakeRow(r) for r in self._rows]


class _FakeConn:
    def __init__(self):
        self.calls: list[tuple[str, tuple]] = []
        self.responses: list[list] = []

    def queue_response(self, rows=None):
        self.responses.append(rows or [])

    def execute(self, sql, params=()):
        self.calls.append((sql, params))
        rows = self.responses.pop(0) if self.responses else []
        return _FakeCursor(rows=rows)


# ─── load_discipline_catalog ─────────────────────────────────────────────────

class TestLoadCatalog:
    def test_dedupes_by_discipline_id_across_sports(self):
        conn = _FakeConn()
        # D-006 appears under two sports — collapse to one picker entry.
        conn.queue_response(rows=[
            {"discipline_id": "D-006", "discipline_name": "Road Cycling"},
            {"discipline_id": "D-006", "discipline_name": "Bike (Tri)"},
            {"discipline_id": "D-001", "discipline_name": "Trail Running"},
        ])
        out = load_discipline_catalog(conn)
        ids = [d["id"] for d in out]
        assert ids == ["D-006", "D-001"]
        assert all("label" in d for d in out)
        assert "FROM layer0.sport_discipline_bridge" in conn.calls[0][0]
        assert "superseded_at IS NULL" in conn.calls[0][0]


# ─── get_discipline_weighting ────────────────────────────────────────────────

class TestGetWeighting:
    def test_returns_id_to_pct_map(self):
        conn = _FakeConn()
        conn.queue_response(rows=[
            {"discipline_slug": "D-006", "weight_pct": 60},
            {"discipline_slug": "D-008", "weight_pct": 40},
        ])
        assert get_discipline_weighting(conn, 1) == {"D-006": 60, "D-008": 40}

    def test_empty_when_unset(self):
        conn = _FakeConn()
        conn.queue_response(rows=[])
        assert get_discipline_weighting(conn, 1) == {}


# ─── replace_discipline_weighting ────────────────────────────────────────────

class TestReplaceWeighting:
    def test_valid_sum_100_deletes_then_inserts(self):
        conn = _FakeConn()
        replace_discipline_weighting(conn, 1, {"D-006": 60, "D-008": 40})
        kinds = [c[0].split()[0] for c in conn.calls]
        assert kinds == ["DELETE", "INSERT", "INSERT"]

    def test_sum_not_100_raises_and_writes_nothing(self):
        conn = _FakeConn()
        with pytest.raises(DisciplineWeightingError):
            replace_discipline_weighting(conn, 1, {"D-006": 60, "D-008": 30})
        assert conn.calls == []  # validation precedes any write

    def test_empty_clears_only(self):
        conn = _FakeConn()
        replace_discipline_weighting(conn, 1, {})
        assert len(conn.calls) == 1
        assert conn.calls[0][0].startswith("DELETE")

    def test_zero_weights_filtered_then_validated(self):
        # zeros drop out; the remaining {D-006:100} sums to 100 → valid.
        conn = _FakeConn()
        replace_discipline_weighting(conn, 1, {"D-006": 100, "D-008": 0})
        kinds = [c[0].split()[0] for c in conn.calls]
        assert kinds == ["DELETE", "INSERT"]
        # the lone INSERT carries D-006 = 100
        ins = [c for c in conn.calls if c[0].startswith("INSERT")][0]
        assert ins[1] == (1, "D-006", 100)

    def test_weight_over_100_raises(self):
        conn = _FakeConn()
        with pytest.raises(DisciplineWeightingError):
            replace_discipline_weighting(conn, 1, {"D-006": 140})
        assert conn.calls == []


# ─── orchestrator unpack ─────────────────────────────────────────────────────

class TestUnpack:
    def _payload(self, records):
        return SimpleNamespace(
            training_history=SimpleNamespace(discipline_weighting=records)
        )

    def test_unpacks_to_2a_override_shape(self):
        p = self._payload([
            DisciplineWeightRecord(discipline_slug="D-006", weight_pct=60),
            DisciplineWeightRecord(discipline_slug="D-008", weight_pct=40),
        ])
        assert _athlete_discipline_overrides(p) == {
            "D-006": {"weight": 60.0},
            "D-008": {"weight": 40.0},
        }

    def test_empty_weighting_yields_empty_overrides(self):
        assert _athlete_discipline_overrides(self._payload([])) == {}
