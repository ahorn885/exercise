"""Tests for `routes/dashboard.py` helpers.

Currently exercises the `_has_plan_version` helper that drives the
dashboard Refresh-CTA enable/disable state. End-to-end Flask test-client
walkthrough of the rendered dashboard captured in the §5.0 manual
verification steps.

Mirrors `tests/test_routes_plan_refresh.py` test-double patterns for
the in-memory `_FakeConn` substrate.
"""

from __future__ import annotations

from datetime import date
from types import SimpleNamespace

from routes.dashboard import _has_plan_version, _v2_session_card
from plan_sessions_repo import load_scheduled_sessions_for_window


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


def _fake_session(**overrides):
    """Lightweight stand-in for a v2 `PlanSession` carrying only the
    attributes `_v2_session_card` reads (avoids constructing a fully-valid
    pydantic model with kind-specific block invariants)."""
    base = dict(
        kind="cardio",
        discipline_name="Mountain Biking",
        discipline_id="D-006",
        duration_min=90,
        intensity_summary="moderate",
        locale_name="Home",
        plan_version_id=65,
        date=date(2026, 6, 12),
    )
    base.update(overrides)
    return SimpleNamespace(**base)


class TestV2SessionCard:
    """`_v2_session_card` normalizes a v2 PlanSession into the legacy
    `plan_items` card shape so both models render through one template,
    with `is_v2` flipping links/actions to the v2 plan view."""

    def test_cardio_uses_discipline_name(self):
        card = _v2_session_card(_fake_session())
        assert card["is_v2"] is True
        assert card["workout_name"] == "Mountain Biking"
        assert card["sport_type"] == "cardio"
        assert card["target_duration_min"] == 90
        assert card["intensity"] == "moderate"
        assert card["plan_version_id"] == 65
        assert card["item_date"] == "2026-06-12"
        assert card["plan_name"] == "Generated plan"

    def test_strength_prefixes_sport(self):
        card = _v2_session_card(
            _fake_session(kind="strength", discipline_name="Trail Running")
        )
        assert card["workout_name"] == "Strength · Trail Running"
        assert card["sport_type"] == "strength"

    def test_strength_without_sport(self):
        card = _v2_session_card(
            _fake_session(kind="strength", discipline_name=None)
        )
        assert card["workout_name"] == "Strength"

    def test_rest_has_no_intensity(self):
        card = _v2_session_card(
            _fake_session(kind="rest", discipline_name=None)
        )
        assert card["workout_name"] == "Rest"
        assert card["intensity"] is None

    def test_cardio_falls_back_to_discipline_id(self):
        card = _v2_session_card(
            _fake_session(discipline_name=None, discipline_id="D-006")
        )
        assert card["workout_name"] == "D-006"


class _FakeListCursor:
    def __init__(self, rows):
        self._rows = rows

    def fetchall(self):
        return self._rows


class _FakeListConn:
    def __init__(self):
        self.calls: list[tuple[str, tuple]] = []

    def execute(self, sql, params=()):
        self.calls.append((sql, params))
        return _FakeListCursor([])


class TestLoadScheduledSessionsForWindow:
    """The dashboard Today/Tomorrow read must (a) resolve the per-day version
    pointer and (b) restrict to active plan versions — otherwise a shelved or
    in-flight version could surface a session as 'scheduled'."""

    def test_query_invariants_and_params(self):
        db = _FakeListConn()
        out = load_scheduled_sessions_for_window(
            db, 42, start=date(2026, 6, 12), end=date(2026, 6, 13)
        )
        assert out == []
        assert len(db.calls) == 1
        sql, params = db.calls[0]
        # Per-day version pointer (latest active version wins per date/slot).
        assert "DISTINCT ON (s.date, s.session_index_in_day)" in sql
        assert "plan_version_id DESC" in sql
        # Active-only restriction.
        assert "generation_status = 'ready'" in sql
        assert "pv.archived_at IS NULL" in sql
        assert "pv.completed_at IS NULL" in sql
        # We deliberately do NOT filter superseded_at (see helper docstring).
        assert "superseded_at" not in sql
        # User + inclusive date-window scoping.
        assert "s.user_id = ?" in sql
        assert "s.date BETWEEN ? AND ?" in sql
        assert params == (42, date(2026, 6, 12), date(2026, 6, 13))
