"""Tests for `sport_sub_format_repo.default_sub_format` (#254 / D-17 slice B).

The Layer-0 default lookup the orchestrator composes the Layer 2A sport from.
Uses the same `_FakeConn` ordered-queue pattern as the other repo tests — no
real DB.
"""

from __future__ import annotations

from sport_sub_format_repo import default_sub_format


class _FakeRow(dict):
    def __getitem__(self, key):
        if isinstance(key, int):
            return list(self.values())[key]
        return super().__getitem__(key)


class _FakeCursor:
    def __init__(self, row=None):
        self._row = row

    def fetchone(self):
        return _FakeRow(self._row) if self._row else None


class _FakeConn:
    def __init__(self, row=None):
        self.calls: list[tuple[str, tuple]] = []
        self._row = row

    def execute(self, sql, params=()):
        self.calls.append((sql, params))
        return _FakeCursor(row=self._row)


def test_returns_default_sub_format_for_parent():
    conn = _FakeConn(row={"sub_format_sport": "Triathlon (Standard / Olympic)"})
    assert (
        default_sub_format(conn, "Triathlon") == "Triathlon (Standard / Olympic)"
    )
    # Reads the live mapping, keyed on the parent.
    sql, params = conn.calls[0]
    assert "layer0.sport_sub_format_map" in sql
    assert "is_default = TRUE" in sql
    assert "superseded_at IS NULL" in sql
    assert params == ("Triathlon",)


def test_returns_none_when_parent_has_no_rows():
    # A single-format sport (no map rows) → no row → None → caller keeps the
    # bare parent name.
    conn = _FakeConn(row=None)
    assert default_sub_format(conn, "Adventure Racing") is None
    assert len(conn.calls) == 1


def test_short_circuits_on_falsy_parent():
    # None / empty parent never hits the DB.
    conn = _FakeConn(row={"sub_format_sport": "x"})
    assert default_sub_format(conn, None) is None
    assert default_sub_format(conn, "") is None
    assert conn.calls == []
