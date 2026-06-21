"""Tests for `routes/race_week_brief.py` — #732 slice 3 caller-side route.

Exercises the inline helpers (`_orchestration_error_message`,
`_owns_plan_version`) directly against the in-memory `_FakeConn` substrate,
plus a Jinja parse check on the display template. End-to-end Flask
test-client walkthrough is captured in the PR's manual verification steps,
mirroring `tests/test_routes_ad_hoc_workouts.py` / `tests/test_routes_plan_refresh.py`.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import jinja2

from layer4 import OrchestrationError
from routes.race_week_brief import _orchestration_error_message, _owns_plan_version


_USER_ID = 42
_PLAN_VERSION_ID = 314


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


# ─── _orchestration_error_message ───────────────────────────────────────────


class TestOrchestrationErrorMessage:
    def test_known_codes_map_to_friendly_copy(self):
        for code in (
            "no_target_event",
            "race_week_brief_too_early",
            "no_active_plan",
            "etl_version_set_undiscoverable",
            "primary_locale_missing",
            "framework_sport_missing",
        ):
            msg = _orchestration_error_message(OrchestrationError(code, "detail"))
            assert msg
            assert code not in msg  # friendly copy, not the raw code

    def test_unknown_code_falls_back_with_code(self):
        msg = _orchestration_error_message(OrchestrationError("weird_new_code", "d"))
        assert "weird_new_code" in msg


# ─── _owns_plan_version ─────────────────────────────────────────────────────


class TestOwnsPlanVersion:
    def test_true_when_row_present(self):
        conn = _FakeConn()
        conn.queue(row={"ok": 1})

        assert _owns_plan_version(conn, _USER_ID, _PLAN_VERSION_ID) is True
        _, params = conn.calls[0]
        assert params == (_PLAN_VERSION_ID, _USER_ID)

    def test_false_when_no_row(self):
        conn = _FakeConn()
        conn.queue(row=None)

        assert _owns_plan_version(conn, _USER_ID, _PLAN_VERSION_ID) is False

    def test_scopes_query_to_user_id(self):
        conn = _FakeConn()
        conn.queue(row=None)

        _owns_plan_version(conn, _USER_ID, _PLAN_VERSION_ID)

        sql, _ = conn.calls[0]
        assert "user_id = ?" in sql
        assert "FROM plan_versions" in sql


# ─── template parses ────────────────────────────────────────────────────────


class TestTemplateParses:
    def test_race_week_brief_template_has_no_jinja_syntax_errors(self):
        root = Path(__file__).resolve().parent.parent
        source = (
            root / "templates" / "plans" / "v2" / "race_week_brief.html"
        ).read_text()
        # parse() compiles the template AST without rendering, so runtime-only
        # globals (url_for, csrf_token) are irrelevant — this catches Jinja
        # syntax errors in the new display surface.
        jinja2.Environment().parse(source)

    def test_plan_view_template_has_no_jinja_syntax_errors(self):
        root = Path(__file__).resolve().parent.parent
        source = (root / "templates" / "plan_create" / "view.html").read_text()
        jinja2.Environment().parse(source)
