"""Tests for `routes/dashboard.py` helpers.

Currently exercises the `_has_plan_version` helper that drives the
dashboard Refresh-CTA enable/disable state. End-to-end Flask test-client
walkthrough of the rendered dashboard captured in the §5.0 manual
verification steps.

Mirrors `tests/test_routes_plan_refresh.py` test-double patterns for
the in-memory `_FakeConn` substrate.
"""

from __future__ import annotations

from routes.dashboard import _has_plan_version


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
    def __init__(self):
        self.calls: list[tuple[str, tuple]] = []
        self.responses: list[dict | None] = []

    def queue_response(self, row=None):
        self.responses.append(row)

    def execute(self, sql, params=()):
        self.calls.append((sql, params))
        row = self.responses.pop(0) if self.responses else None
        return _FakeCursor(row=row)


class TestHasPlanVersion:
    def test_returns_true_when_row_present(self):
        db = _FakeConn()
        db.queue_response(row={"?column?": 1})
        assert _has_plan_version(db, user_id=42) is True

    def test_returns_false_when_no_row(self):
        db = _FakeConn()
        db.queue_response(row=None)
        assert _has_plan_version(db, user_id=42) is False

    def test_query_is_user_scoped(self):
        db = _FakeConn()
        db.queue_response(row=None)
        _has_plan_version(db, user_id=42)
        assert len(db.calls) == 1
        sql, params = db.calls[0]
        assert "FROM plan_versions" in sql
        assert "WHERE user_id = ?" in sql
        assert "LIMIT 1" in sql
        assert params == (42,)
