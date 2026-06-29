"""Tests for `sport_sub_format_repo.default_sub_format` (#254 / D-17 slice B).

The Layer-0 default lookup the orchestrator composes the Layer 2A sport from.
Uses the same `_FakeConn` ordered-queue pattern as the other repo tests — no
real DB.
"""

from __future__ import annotations

from sport_sub_format_repo import (
    default_sub_format,
    parent_options_map,
    sub_format_options,
)


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


# ─── sub_format_options / parent_options_map (slice B2 — form option lists) ──


class _FakeRowsCursor:
    def __init__(self, rows):
        self._rows = rows

    def fetchall(self):
        return [_FakeRow(r) for r in self._rows]


class _FakeRowsConn:
    def __init__(self, rows):
        self.calls: list[tuple[str, tuple]] = []
        self._rows = rows

    def execute(self, sql, params=()):
        self.calls.append((sql, params))
        return _FakeRowsCursor(self._rows)


def test_sub_format_options_returns_shaped_dicts_in_order():
    conn = _FakeRowsConn(rows=[
        {"sub_format_sport": "Triathlon (Sprint)", "display_label": "Sprint",
         "is_default": False},
        {"sub_format_sport": "Triathlon (Standard / Olympic)",
         "display_label": "Standard / Olympic", "is_default": True},
    ])
    out = sub_format_options(conn, "Triathlon")
    assert out == [
        {"sub_format_sport": "Triathlon (Sprint)", "display_label": "Sprint",
         "is_default": False},
        {"sub_format_sport": "Triathlon (Standard / Olympic)",
         "display_label": "Standard / Olympic", "is_default": True},
    ]
    # Keyed on the parent, current mapping, seed order.
    sql, params = conn.calls[0]
    assert "layer0.sport_sub_format_map" in sql
    assert "superseded_at IS NULL" in sql
    assert "ORDER BY id" in sql
    assert params == ("Triathlon",)


def test_sub_format_options_empty_for_single_format_sport():
    # No rows → [] → the form hides the Sub-format select.
    conn = _FakeRowsConn(rows=[])
    assert sub_format_options(conn, "Adventure Racing") == []
    assert len(conn.calls) == 1


def test_sub_format_options_short_circuits_on_falsy_parent():
    conn = _FakeRowsConn(rows=[{"sub_format_sport": "x", "display_label": "x",
                                "is_default": True}])
    assert sub_format_options(conn, None) == []
    assert sub_format_options(conn, "") == []
    assert conn.calls == []


def test_parent_options_map_groups_by_parent_preserving_order():
    conn = _FakeRowsConn(rows=[
        {"parent_sport": "Skimo", "sub_format_sport": "Skimo (Sprint)",
         "display_label": "Sprint", "is_default": False},
        {"parent_sport": "Skimo", "sub_format_sport": "Skimo (Individual / Team)",
         "display_label": "Individual / Team", "is_default": True},
        {"parent_sport": "Triathlon", "sub_format_sport": "Triathlon (Sprint)",
         "display_label": "Sprint", "is_default": False},
    ])
    out = parent_options_map(conn)
    assert list(out.keys()) == ["Skimo", "Triathlon"]
    assert out["Skimo"] == [
        {"sub_format_sport": "Skimo (Sprint)", "display_label": "Sprint",
         "is_default": False},
        {"sub_format_sport": "Skimo (Individual / Team)",
         "display_label": "Individual / Team", "is_default": True},
    ]
    assert out["Triathlon"] == [
        {"sub_format_sport": "Triathlon (Sprint)", "display_label": "Sprint",
         "is_default": False},
    ]
    sql, params = conn.calls[0]
    assert "superseded_at IS NULL" in sql
    assert "ORDER BY parent_sport, id" in sql
    assert params == ()


def test_parent_options_map_empty_when_no_rows():
    conn = _FakeRowsConn(rows=[])
    assert parent_options_map(conn) == {}
