"""Tests for `routes/dashboard.py` helpers.

Currently exercises the `_has_plan_version` helper that drives the
dashboard Refresh-CTA enable/disable state. End-to-end Flask test-client
walkthrough of the rendered dashboard captured in the §5.0 manual
verification steps.

Mirrors `tests/test_routes_plan_refresh.py` test-double patterns for
the in-memory `_FakeConn` substrate.
"""

from __future__ import annotations

from datetime import date, timedelta
from types import SimpleNamespace

from routes.dashboard import (
    _fill_rest_days,
    _has_plan_version,
    _rest_day_card,
    _supplement_summary,
    _v2_session_card,
)
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
        session_index_in_day=0,
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
        # Deep-link key (#956): the session's slot within its day pairs with
        # item_date to target `#s-2026-06-12-0` on the plan page.
        assert card["session_index"] == 0
        # No race name supplied → the plain fallback label (#620).
        assert card["plan_name"] == "Training plan"

    def test_plan_name_uses_supplied_name(self):
        card = _v2_session_card(
            _fake_session(), plan_name="Pocket Gopher Extreme 2026 — 16-week build"
        )
        assert card["plan_name"] == "Pocket Gopher Extreme 2026 — 16-week build"

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

    def test_rest_surfaces_reason_matching_daily_view(self):
        # An explicit rest session carries its reason onto the home card the
        # same way the daily view renders it ("Rest — Taper drop"), so the two
        # surfaces read consistently (#888).
        card = _v2_session_card(
            _fake_session(kind="rest", discipline_name=None,
                          rest_reason="taper_drop")
        )
        assert card["workout_name"] == "Rest — Taper drop"
        assert card["sport_type"] == "rest"
        assert card["intensity"] is None


class TestRestDayCard:
    """`_rest_day_card` synthesizes the Today/Tomorrow card for a date inside an
    active plan's scope that carries no session — the v2 generator encodes
    ordinary rest days as the absence of a session, so this keeps the home card
    from falling through to the 'No session scheduled' empty state (#888)."""

    def test_shape_matches_v2_rest_card(self):
        card = _rest_day_card(65, "Pocket Gopher Extreme 2026", date(2026, 6, 22))
        assert card["is_v2"] is True
        assert card["plan_version_id"] == 65
        assert card["workout_name"] == "Rest"
        assert card["sport_type"] == "rest"
        assert card["target_duration_min"] is None
        assert card["intensity"] is None
        assert card["plan_name"] == "Pocket Gopher Extreme 2026"
        assert card["item_date"] == "2026-06-22"
        # No session row to slot into → deep-link to the day group, not a
        # session anchor (#956): the template renders `#day-<iso>`.
        assert card["session_index"] is None

    def test_plan_name_falls_back_when_missing(self):
        card = _rest_day_card(65, None, date(2026, 6, 22))
        assert card["plan_name"] == "Training plan"


class TestFillRestDays:
    """`_fill_rest_days` is the home Today/Tomorrow rest-day backfill (#888): a
    covered-but-session-less `DayPlan` (and no legacy item on the list) becomes
    an explicit rest card; a no-plan day (DayPlan None) stays empty, and a
    legacy item is never shadowed."""

    _PLAN = {
        "id": 65,
        "scope_start_date": date(2026, 6, 1),
        "scope_end_date": date(2026, 8, 31),
    }
    TODAY = date(2026, 6, 22)
    TOMORROW = date(2026, 6, 23)

    def _rest_dp(self, d):
        from plan_sessions_repo import DayPlan
        return DayPlan(d, d.strftime("%a"), [], dict(self._PLAN))

    def _session_dp(self, d):
        from plan_sessions_repo import DayPlan
        return DayPlan(d, d.strftime("%a"), [SimpleNamespace(plan_version_id=65)], None)

    def test_noop_when_both_days_have_sessions(self, monkeypatch):
        # Fast path: no race-name lookup when neither day is a rest gap.
        from routes import dashboard as dash
        calls = []
        monkeypatch.setattr(
            dash, "target_race_name", lambda db, uid: calls.append(1) or "X")
        today = [{"workout_name": "Run"}]
        tomorrow = [{"workout_name": "Ride"}]
        out_today, out_tomorrow = _fill_rest_days(
            None, 42,
            today_dp=self._session_dp(self.TODAY),
            tomorrow_dp=self._session_dp(self.TOMORROW),
            today_workouts=today, tomorrow_workouts=tomorrow,
        )
        assert out_today is today and out_tomorrow is tomorrow
        assert calls == []

    def test_empty_today_inside_scope_becomes_rest(self, monkeypatch):
        from routes import dashboard as dash
        monkeypatch.setattr(
            dash, "target_race_name", lambda db, uid: "Pocket Gopher 2026")
        out_today, out_tomorrow = _fill_rest_days(
            None, 42,
            today_dp=self._rest_dp(self.TODAY),
            tomorrow_dp=self._session_dp(self.TOMORROW),
            today_workouts=[], tomorrow_workouts=[{"workout_name": "Ride"}],
        )
        assert len(out_today) == 1
        assert out_today[0]["workout_name"] == "Rest"
        assert out_today[0]["sport_type"] == "rest"
        assert out_today[0]["plan_version_id"] == 65
        assert out_today[0]["plan_name"] == "Pocket Gopher 2026 — 13-week build"
        assert out_tomorrow == [{"workout_name": "Ride"}]

    def test_no_active_plan_stays_empty(self, monkeypatch):
        # DayPlan None → no active plan covers the day → genuine "no session".
        from routes import dashboard as dash
        monkeypatch.setattr(dash, "target_race_name", lambda db, uid: "X")
        out_today, out_tomorrow = _fill_rest_days(
            None, 42, today_dp=None, tomorrow_dp=None,
            today_workouts=[], tomorrow_workouts=[],
        )
        assert out_today == []
        assert out_tomorrow == []

    def test_legacy_item_not_shadowed_by_rest(self, monkeypatch):
        # A legacy plan_item already fills the day → no rest card, even though
        # the (v2) DayPlan would otherwise be a rest gap.
        from routes import dashboard as dash
        monkeypatch.setattr(dash, "target_race_name", lambda db, uid: "X")
        legacy = [{"workout_name": "Imported run"}]
        out_today, _ = _fill_rest_days(
            None, 42,
            today_dp=self._rest_dp(self.TODAY), tomorrow_dp=None,
            today_workouts=legacy, tomorrow_workouts=[],
        )
        assert out_today is legacy

    def test_both_empty_inside_scope_both_become_rest(self, monkeypatch):
        from routes import dashboard as dash
        monkeypatch.setattr(dash, "target_race_name", lambda db, uid: "X")
        out_today, out_tomorrow = _fill_rest_days(
            None, 42,
            today_dp=self._rest_dp(self.TODAY),
            tomorrow_dp=self._rest_dp(self.TOMORROW),
            today_workouts=[], tomorrow_workouts=[],
        )
        assert out_today[0]["sport_type"] == "rest"
        assert out_today[0]["item_date"] == "2026-06-22"
        assert out_tomorrow[0]["sport_type"] == "rest"
        assert out_tomorrow[0]["item_date"] == "2026-06-23"

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


class TestSupplementSummary:
    """`_supplement_summary` resolves the home-page Standard + today's Daily
    supplement blocks (#621). Best-effort — any miss returns None so the card
    omits rather than breaking the dashboard."""

    def test_returns_standard_and_today_daily(self, monkeypatch):
        from routes import dashboard as dash
        today = date(2026, 6, 1)
        today_day = SimpleNamespace(date=today, supplement_recs=["electrolytes"])
        other_day = SimpleNamespace(date=date(2026, 6, 2), supplement_recs=[])
        nutrition = SimpleNamespace(
            standing_supplements=["creatine"], days=[other_day, today_day])
        monkeypatch.setattr(
            "plan_nutrition_repo.load_plan_nutrition_by_version",
            lambda db, pv: nutrition,
        )
        sessions = [SimpleNamespace(plan_version_id=5)]
        out = dash._supplement_summary(_FakeConn(), 42, sessions, today)
        assert out["standard"] == ["creatine"]
        assert out["daily"] == ["electrolytes"]

    def test_none_when_no_plan_at_all(self):
        from routes import dashboard as dash
        # No today sessions and no plan_versions row → None (no crash).
        out = dash._supplement_summary(_FakeConn(), 42, [], date(2026, 6, 1))
        assert out is None

    def test_none_when_nutrition_has_no_standing(self, monkeypatch):
        from routes import dashboard as dash
        nutrition = SimpleNamespace(standing_supplements=[], days=[])
        monkeypatch.setattr(
            "plan_nutrition_repo.load_plan_nutrition_by_version",
            lambda db, pv: nutrition,
        )
        sessions = [SimpleNamespace(plan_version_id=5)]
        out = dash._supplement_summary(
            _FakeConn(), 42, sessions, date(2026, 6, 1))
        assert out is None


# ─── home-route render (#888) ───────────────────────────────────────────────


class _DashRow(dict):
    def __getitem__(self, key):
        if isinstance(key, int):
            vals = list(self.values())
            return vals[key] if vals else 0
        return super().__getitem__(key)


class _DashCursor:
    def __init__(self, one=None, many=None):
        self._one = one
        self._many = many or []

    def fetchone(self):
        return self._one

    def fetchall(self):
        return self._many


class _DashConn:
    """SQL-aware fake connection for the home-route render tests: benign rows
    for the dashboard's COUNT / user / has-plan-version reads, empty lists for
    every list query, so `index()` renders without a real DB."""

    def execute(self, sql, params=()):
        s = ' '.join(sql.split())
        if 'COUNT(*)' in s:
            return _DashCursor(one=_DashRow(n=0))
        if 'FROM users' in s:
            return _DashCursor(one=_DashRow(
                id=1, username='owner', email='o@x.test', display_name='Owner'))
        if 'FROM plan_versions' in s:  # _has_plan_version → truthy
            return _DashCursor(one=_DashRow(present=1))
        return _DashCursor(one=None, many=[])

    def commit(self):
        pass


class TestHomeRouteRestDayRender:
    """End-to-end: the home route ('/') renders an empty-but-in-scope day as an
    explicit rest day rather than the 'No session scheduled' empty state — the
    #888 symptom. Verifies the full wiring (route → `_fill_rest_days` → card →
    template), not just the helpers."""

    def _client(self, monkeypatch, *, plan_covers_today):
        import os
        import sys

        os.environ.setdefault('SECRET_KEY', 'test-secret-key-for-render-tests')
        os.environ['DATABASE_URL'] = ''

        import app as _appmod
        import plan_notifications
        from routes import dashboard as dash

        from plan_sessions_repo import DayPlan

        for mod in list(sys.modules.values()):
            if mod is not None and getattr(mod, 'get_db', None) is not None:
                monkeypatch.setattr(
                    mod, 'get_db', lambda: _DashConn(), raising=False)

        # The dashboard resolves Today/Tomorrow via the shared rest-aware window
        # resolver. Covered case → both days come back as explicit rest DayPlans
        # (no sessions); no-plan case → empty window (genuine "no session").
        pv = {'id': 65, 'scope_start_date': date(2026, 6, 1),
              'scope_end_date': date(2026, 8, 31)}

        def _fake_window(db, uid, *, start, end):
            if not plan_covers_today:
                return []
            out, d = [], start
            while d <= end:
                out.append(DayPlan(d, d.strftime('%a'), [], dict(pv)))
                d += timedelta(days=1)
            return out

        monkeypatch.setattr(dash, 'load_active_window_with_rest', _fake_window)
        monkeypatch.setattr(dash, '_get_weather', lambda db: None)
        monkeypatch.setattr(
            dash, '_supplement_summary', lambda db, uid, ts, td: None)
        monkeypatch.setattr(
            plan_notifications, 'get_unseen_plan_notifications',
            lambda db, uid: [])

        _appmod.app.config['TESTING'] = True
        c = _appmod.app.test_client()
        with c.session_transaction() as sess:
            sess['user_id'] = 1
        return c

    def test_rest_day_renders_as_recovery_not_empty_state(self, monkeypatch):
        client = self._client(monkeypatch, plan_covers_today=True)
        resp = client.get('/')
        assert resp.status_code == 200
        html = resp.get_data(as_text=True)
        # The rest day surfaces as a recovery day, NOT the no-plan empty state.
        assert 'Recovery day' in html
        assert 'No session scheduled' not in html
        # CSP discipline preserved on the rendered card.
        assert 'onclick=' not in html

    def test_no_active_plan_keeps_empty_state(self, monkeypatch):
        # Genuine no-plan day → the empty state stays (the fill must not fire).
        client = self._client(monkeypatch, plan_covers_today=False)
        resp = client.get('/')
        assert resp.status_code == 200
        html = resp.get_data(as_text=True)
        assert 'No session scheduled' in html
        assert 'Recovery day' not in html
