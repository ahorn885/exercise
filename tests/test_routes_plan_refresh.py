"""Tests for `routes/plan_refresh.py` D-64 plan-refresh caller-side
helpers.

Exercises the inline helpers (`_parse_tier`, `_resolve_scope_dates`,
`_orchestration_error_message`, `_latest_plan_version`,
`_athlete_locale_slugs`, `_athlete_active_injury_summary`,
`_run_parser`, `_write_refresh_log`, `_diff_sessions_against_parent`,
`_latest_parent_for_refresh`) directly. End-to-end Flask test-client
walkthrough captured in the §5.0 manual verification steps.

Mirrors `tests/test_routes_plan_create.py` + `tests/test_routes_ad_hoc_workouts.py`
test-double patterns for the in-memory `_FakeConn` substrate.
"""

from __future__ import annotations

from datetime import date, datetime, timedelta, timezone
from typing import Any

import pytest

from layer4 import OrchestrationError
from layer4.context import ParsedIntent
from layer4.payload import PlanSession
from nl_parser import NLParserError
from routes.plan_refresh import (
    _TIER_CAP_LIMITS,
    _athlete_active_injury_summary,
    _athlete_locale_slugs,
    _check_frequency_cap,
    _count_recent_refreshes,
    _diff_sessions_against_parent,
    _latest_parent_for_refresh,
    _latest_plan_version,
    _orchestration_error_message,
    _parse_tier,
    _resolve_prefill,
    _resolve_scope_dates,
    _run_parser,
    _write_refresh_log,
)


# ─── Test doubles ───────────────────────────────────────────────────────────


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
    """In-memory connection that queues canned responses, recording every
    `execute(sql, params)` call. Commit/rollback counters mirror the
    test_routes_plan_create.py pattern."""

    def __init__(self):
        self.calls: list[tuple[str, tuple]] = []
        self.commits: int = 0
        self.rollbacks: int = 0
        self.responses: list[tuple] = []

    def queue_response(self, row=None, rows=None):
        self.responses.append((row, rows or []))

    def execute(self, sql, params=()):
        self.calls.append((sql, params))
        if self.responses:
            row, rows = self.responses.pop(0)
        else:
            row, rows = None, []
        return _FakeCursor(row=row, rows=rows)

    def commit(self):
        self.commits += 1

    def rollback(self):
        self.rollbacks += 1


def _rest_session(
    *,
    plan_version_id: int,
    d: date,
    session_index_in_day: int = 0,
    rest_reason: str = "planned_recovery",
    coaching_intent: str = "Recovery day.",
) -> PlanSession:
    return PlanSession.model_validate(
        {
            "session_id": f"rest-{d.isoformat()}-{session_index_in_day}",
            "plan_version_id": plan_version_id,
            "date": d.isoformat(),
            "day_of_week": d.strftime("%a"),
            "session_index_in_day": session_index_in_day,
            "time_of_day": "unspecified",
            "kind": "rest",
            "duration_min": 0,
            "intensity_summary": "rest",
            "rest_reason": rest_reason,
            "session_notes": "",
            "coaching_intent": coaching_intent,
            "coaching_flags": [],
        }
    )


# ─── _parse_tier ────────────────────────────────────────────────────────────


class TestParseTier:
    def test_tier_field_t1(self):
        tier, err = _parse_tier({"tier": "T1"})
        assert err is None
        assert tier == "T1"

    def test_tier_field_normalized(self):
        tier, err = _parse_tier({"tier": "t2"})
        assert err is None
        assert tier == "T2"

    def test_named_submit_button(self):
        tier, err = _parse_tier({"submit_t3": "1"})
        assert err is None
        assert tier == "T3"

    def test_named_submit_preferred_over_invalid_tier_field(self):
        tier, err = _parse_tier({"tier": "", "submit_t1": "1"})
        assert err is None
        assert tier == "T1"

    def test_unknown_tier_rejected(self):
        tier, err = _parse_tier({"tier": "T4"})
        assert tier is None
        assert err is not None

    def test_empty_form_rejected(self):
        tier, err = _parse_tier({})
        assert tier is None
        assert err is not None


# ─── _resolve_scope_dates ───────────────────────────────────────────────────


class TestResolveScopeDates:
    def test_t1_two_days(self):
        today = date(2026, 5, 21)
        start, end = _resolve_scope_dates("T1", today)
        assert start == today
        assert end == today + timedelta(days=1)

    def test_t2_seven_days(self):
        today = date(2026, 5, 21)
        start, end = _resolve_scope_dates("T2", today)
        assert start == today
        assert end == today + timedelta(days=6)

    def test_t3_twenty_eight_days(self):
        today = date(2026, 5, 21)
        start, end = _resolve_scope_dates("T3", today)
        assert start == today
        assert end == today + timedelta(days=27)


# ─── _orchestration_error_message ───────────────────────────────────────────


class TestOrchestrationErrorMessage:
    def test_known_code(self):
        msg = _orchestration_error_message(
            OrchestrationError("primary_locale_missing")
        )
        assert "home locale" in msg

    def test_unknown_code_fallback(self):
        msg = _orchestration_error_message(
            OrchestrationError("bogus_code")
        )
        assert "bogus_code" in msg


# ─── _latest_plan_version ───────────────────────────────────────────────────


class TestLatestPlanVersion:
    def test_returns_dict_on_hit(self):
        db = _FakeConn()
        db.queue_response(
            row={
                "id": 17,
                "created_at": "2026-05-20",
                "created_via": "plan_create",
                "scope_start_date": date(2026, 5, 20),
                "scope_end_date": date(2026, 11, 20),
                "pattern": "A",
            }
        )
        result = _latest_plan_version(db, user_id=1)
        assert result is not None
        assert result["id"] == 17
        assert result["created_via"] == "plan_create"
        assert result["pattern"] == "A"

    def test_returns_none_on_miss(self):
        db = _FakeConn()
        db.queue_response(row=None)
        assert _latest_plan_version(db, user_id=1) is None

    def test_user_id_scoped_in_sql(self):
        db = _FakeConn()
        db.queue_response(row=None)
        _latest_plan_version(db, user_id=99)
        sql, params = db.calls[0]
        assert "WHERE user_id = ?" in sql
        assert params == (99,)


# ─── _athlete_locale_slugs ──────────────────────────────────────────────────


class TestAthleteLocaleSlugs:
    def test_happy_path(self):
        db = _FakeConn()
        db.queue_response(
            rows=[{"locale": "home"}, {"locale": "in_laws_mn"}]
        )
        result = _athlete_locale_slugs(db, user_id=1)
        assert result == ("home", "in_laws_mn")

    def test_empty(self):
        db = _FakeConn()
        db.queue_response(rows=[])
        assert _athlete_locale_slugs(db, user_id=1) == ()

    def test_drops_empty_locales(self):
        db = _FakeConn()
        db.queue_response(rows=[{"locale": "home"}, {"locale": ""}])
        assert _athlete_locale_slugs(db, user_id=1) == ("home",)


# ─── _athlete_active_injury_summary ─────────────────────────────────────────


class TestAthleteActiveInjurySummary:
    def test_body_part_with_description(self):
        db = _FakeConn()
        db.queue_response(
            rows=[
                {"body_part": "left wrist", "description": "chronic-managed", "status": "Active"},
                {"body_part": "lower back", "description": "recovering", "status": "Active"},
            ]
        )
        result = _athlete_active_injury_summary(db, user_id=1)
        assert result == (
            "left wrist — chronic-managed",
            "lower back — recovering",
        )

    def test_body_part_without_description(self):
        db = _FakeConn()
        db.queue_response(
            rows=[{"body_part": "right knee", "description": None, "status": "Active"}]
        )
        result = _athlete_active_injury_summary(db, user_id=1)
        assert result == ("right knee",)

    def test_drops_missing_body_part(self):
        db = _FakeConn()
        db.queue_response(
            rows=[
                {"body_part": "", "description": "noise", "status": "Active"},
                {"body_part": "left wrist", "description": "", "status": "Active"},
            ]
        )
        result = _athlete_active_injury_summary(db, user_id=1)
        assert result == ("left wrist",)

    def test_sql_filters_active_status(self):
        db = _FakeConn()
        db.queue_response(rows=[])
        _athlete_active_injury_summary(db, user_id=42)
        sql, params = db.calls[0]
        assert "status = 'Active'" in sql
        assert params == (42,)

    def test_empty(self):
        db = _FakeConn()
        db.queue_response(rows=[])
        assert _athlete_active_injury_summary(db, user_id=1) == ()


# ─── _run_parser ────────────────────────────────────────────────────────────


class TestRunParser:
    def test_success_path(self, monkeypatch):
        db = _FakeConn()
        db.queue_response(rows=[{"locale": "home"}])
        db.queue_response(rows=[])

        fake_intent = ParsedIntent(fatigue_signal="tired")

        def fake_parse_intent(parser_input, *, user_id, **kwargs):
            assert parser_input.nl_text == "I'm tired"
            assert parser_input.tier == "T1"
            assert parser_input.athlete_locales == ("home",)
            assert user_id == 42
            return fake_intent

        monkeypatch.setattr(
            "routes.plan_refresh.nl_parser.parse_intent", fake_parse_intent
        )

        parsed, degraded = _run_parser(db, 42, nl_text="I'm tired", tier="T1")
        assert degraded is False
        assert parsed.fatigue_signal == "tired"

    def test_parser_error_falls_back_to_default(self, monkeypatch):
        db = _FakeConn()
        db.queue_response(rows=[])
        db.queue_response(rows=[])

        def fake_parse_intent(parser_input, *, user_id, **kwargs):
            raise NLParserError("network", detail="timeout")

        monkeypatch.setattr(
            "routes.plan_refresh.nl_parser.parse_intent", fake_parse_intent
        )

        parsed, degraded = _run_parser(db, 1, nl_text="x", tier="T1")
        assert degraded is True
        assert parsed.parser_confidence == "low"
        assert parsed.ambiguity_notes is not None


# ─── _write_refresh_log ─────────────────────────────────────────────────────


class TestWriteRefreshLog:
    def test_success_insert_shape(self):
        db = _FakeConn()
        _write_refresh_log(
            db,
            user_id=42,
            tier="T2",
            nl_text="I'm tired",
            parsed_intent_json='{"foo":"bar"}',
            layers_run=("3A", "3B", "Layer4"),
            scope_start_date=date(2026, 5, 21),
            scope_end_date=date(2026, 5, 27),
            plan_version_id_before=10,
            plan_version_id_after=11,
            duration_ms=12345,
            sessions_changed=3,
            success=True,
            failure_reason=None,
        )
        assert len(db.calls) == 1
        sql, params = db.calls[0]
        assert "INSERT INTO plan_refresh_log" in sql
        assert params[0] == 42  # user_id
        assert params[1] == "T2"  # tier
        assert params[2] == "I'm tired"  # nl_text
        assert params[4] == ["3A", "3B", "Layer4"]  # layers_run
        assert params[7] == 10  # plan_version_id_before
        assert params[8] == 11  # plan_version_id_after
        assert params[11] is True  # success

    def test_empty_nl_text_stored_as_null(self):
        db = _FakeConn()
        _write_refresh_log(
            db,
            user_id=1,
            tier="T1",
            nl_text="",
            parsed_intent_json=None,
            layers_run=("3A", "3B", "Layer4"),
            scope_start_date=date(2026, 5, 21),
            scope_end_date=date(2026, 5, 22),
            plan_version_id_before=1,
            plan_version_id_after=2,
            duration_ms=100,
            sessions_changed=0,
            success=True,
            failure_reason=None,
        )
        _, params = db.calls[0]
        assert params[2] is None  # empty string normalized to NULL

    def test_failure_row_shape(self):
        db = _FakeConn()
        _write_refresh_log(
            db,
            user_id=1,
            tier="T3",
            nl_text="oops",
            parsed_intent_json='{"x":1}',
            layers_run=("2A", "2B", "2C", "2D", "2E", "3A", "3B", "Layer4"),
            scope_start_date=date(2026, 5, 21),
            scope_end_date=date(2026, 6, 17),
            plan_version_id_before=1,
            plan_version_id_after=None,
            duration_ms=500,
            sessions_changed=None,
            success=False,
            failure_reason="layer4:periodization_invalid",
        )
        _, params = db.calls[0]
        assert params[8] is None  # plan_version_id_after
        assert params[11] is False  # success
        assert params[12] == "layer4:periodization_invalid"

    def test_cap_overridden_defaults_to_false(self):
        db = _FakeConn()
        _write_refresh_log(
            db,
            user_id=1,
            tier="T1",
            nl_text="hi",
            parsed_intent_json='{"x":1}',
            layers_run=("3A", "3B", "Layer4"),
            scope_start_date=date(2026, 5, 21),
            scope_end_date=date(2026, 5, 22),
            plan_version_id_before=1,
            plan_version_id_after=2,
            duration_ms=100,
            sessions_changed=0,
            success=True,
            failure_reason=None,
        )
        sql, params = db.calls[0]
        assert "cap_overridden" in sql
        assert params[13] is False

    def test_cap_overridden_true_passed_through(self):
        db = _FakeConn()
        _write_refresh_log(
            db,
            user_id=1,
            tier="T1",
            nl_text="hi",
            parsed_intent_json='{"x":1}',
            layers_run=("3A", "3B", "Layer4"),
            scope_start_date=date(2026, 5, 21),
            scope_end_date=date(2026, 5, 22),
            plan_version_id_before=1,
            plan_version_id_after=2,
            duration_ms=100,
            sessions_changed=0,
            success=True,
            failure_reason=None,
            cap_overridden=True,
        )
        _, params = db.calls[0]
        assert params[13] is True


# ─── _diff_sessions_against_parent ──────────────────────────────────────────


class TestDiffSessionsAgainstParent:
    def test_unchanged_when_payload_identical(self):
        d = date(2026, 5, 21)
        new = [_rest_session(plan_version_id=2, d=d)]
        parent = [_rest_session(plan_version_id=2, d=d)]
        badges, changed = _diff_sessions_against_parent(new, parent)
        assert badges[(d, 0)] == "unchanged"
        assert changed == 0

    def test_updated_when_payload_differs(self):
        d = date(2026, 5, 21)
        new = [
            _rest_session(plan_version_id=2, d=d, coaching_intent="New coaching note.")
        ]
        parent = [
            _rest_session(plan_version_id=2, d=d, coaching_intent="Old coaching note.")
        ]
        badges, changed = _diff_sessions_against_parent(new, parent)
        assert badges[(d, 0)] == "updated"
        assert changed == 1

    def test_new_when_slot_absent_from_parent(self):
        d = date(2026, 5, 21)
        new = [_rest_session(plan_version_id=2, d=d)]
        badges, changed = _diff_sessions_against_parent(new, [])
        assert badges[(d, 0)] == "new"
        assert changed == 1

    def test_mixed_slots(self):
        d1 = date(2026, 5, 21)
        d2 = date(2026, 5, 22)
        d3 = date(2026, 5, 23)
        new = [
            _rest_session(plan_version_id=2, d=d1, coaching_intent="Same."),
            _rest_session(plan_version_id=2, d=d2, coaching_intent="New."),
            _rest_session(plan_version_id=2, d=d3, coaching_intent="Extension."),
        ]
        parent = [
            _rest_session(plan_version_id=1, d=d1, coaching_intent="Same."),
            _rest_session(plan_version_id=1, d=d2, coaching_intent="Old."),
        ]
        badges, changed = _diff_sessions_against_parent(new, parent)
        assert badges[(d1, 0)] == "unchanged"
        assert badges[(d2, 0)] == "updated"
        assert badges[(d3, 0)] == "new"
        assert changed == 2

    def test_session_index_in_day_distinguishes_slots(self):
        d = date(2026, 5, 21)
        new = [
            _rest_session(plan_version_id=2, d=d, session_index_in_day=0),
            _rest_session(plan_version_id=2, d=d, session_index_in_day=1),
        ]
        parent = [_rest_session(plan_version_id=2, d=d, session_index_in_day=0)]
        badges, changed = _diff_sessions_against_parent(new, parent)
        assert badges[(d, 0)] == "unchanged"
        assert badges[(d, 1)] == "new"
        assert changed == 1

    def test_diff_ignores_rebound_plan_version_id(self):
        # Sessions in `new` carry the new plan_version_id; sessions in
        # `parent` carry the prior one. The diff excludes the rebound
        # identity fields (plan_version_id, session_id), so structurally
        # identical sessions across versions compare as 'unchanged'.
        d = date(2026, 5, 21)
        new = [_rest_session(plan_version_id=99, d=d)]
        parent = [_rest_session(plan_version_id=1, d=d)]
        badges, changed = _diff_sessions_against_parent(new, parent)
        assert badges[(d, 0)] == "unchanged"
        assert changed == 0


# ─── _latest_parent_for_refresh ─────────────────────────────────────────────


class TestLatestParentForRefresh:
    def test_uses_refresh_log_when_present(self):
        db = _FakeConn()
        db.queue_response(row={"plan_version_id_before": 7})
        result = _latest_parent_for_refresh(db, user_id=1, plan_version_id=8)
        assert result == 7

    def test_falls_back_to_prior_plan_versions_row(self):
        db = _FakeConn()
        db.queue_response(row=None)  # no log row
        db.queue_response(row={"id": 5})  # fallback row
        result = _latest_parent_for_refresh(db, user_id=1, plan_version_id=8)
        assert result == 5

    def test_returns_none_when_no_prior_anywhere(self):
        db = _FakeConn()
        db.queue_response(row=None)
        db.queue_response(row=None)
        assert _latest_parent_for_refresh(db, user_id=1, plan_version_id=8) is None


# ─── D-63 §3.5 — _resolve_prefill (T1 hook query-param prefill) ─────────────


class TestResolvePrefill:
    def test_returns_empty_when_no_args(self):
        nl, tier = _resolve_prefill({})
        assert nl == ""
        assert tier is None

    def test_nl_context_passes_through(self):
        nl, tier = _resolve_prefill({"nl_context": "Did an unscheduled 60min Running (hard) at home"})
        assert nl == "Did an unscheduled 60min Running (hard) at home"
        assert tier is None

    def test_valid_tier_uppercased(self):
        _, tier = _resolve_prefill({"tier": "t1"})
        assert tier == "T1"

    def test_unknown_tier_collapses_to_none(self):
        _, tier = _resolve_prefill({"tier": "T9"})
        assert tier is None

    def test_blank_tier_collapses_to_none(self):
        _, tier = _resolve_prefill({"tier": "   "})
        assert tier is None

    def test_nl_context_truncated_at_soft_cap(self):
        from routes.plan_refresh import _NL_TEXT_SOFT_CAP_CHARS

        nl, _ = _resolve_prefill({"nl_context": "x" * (_NL_TEXT_SOFT_CAP_CHARS + 50)})
        assert len(nl) == _NL_TEXT_SOFT_CAP_CHARS

    def test_t1_hook_full_pattern(self):
        # End-to-end pattern: T1 hook auto-fills nl_context + tier=T1.
        nl, tier = _resolve_prefill({
            "nl_context": "Did an unscheduled 45min MTB (moderate) at home",
            "tier": "T1",
        })
        assert nl == "Did an unscheduled 45min MTB (moderate) at home"
        assert tier == "T1"


# ─── D-64 §8 — frequency caps ──────────────────────────────────────────────


class TestTierCapLimits:
    def test_t1_three_per_twenty_four_hours(self):
        assert _TIER_CAP_LIMITS["T1"] == (3, 24)

    def test_t2_one_per_forty_eight_hours(self):
        assert _TIER_CAP_LIMITS["T2"] == (1, 48)

    def test_t3_one_per_seven_days(self):
        assert _TIER_CAP_LIMITS["T3"] == (1, 24 * 7)


class TestCountRecentRefreshes:
    def test_returns_count_from_row(self):
        db = _FakeConn()
        db.queue_response(row={"n": 2})
        now = datetime(2026, 5, 21, 12, 0, tzinfo=timezone.utc)
        result = _count_recent_refreshes(
            db, user_id=1, tier="T1", window_hours=24, now=now
        )
        assert result == 2

    def test_zero_when_no_row(self):
        db = _FakeConn()
        db.queue_response(row={"n": 0})
        now = datetime(2026, 5, 21, 12, 0, tzinfo=timezone.utc)
        assert (
            _count_recent_refreshes(
                db, user_id=1, tier="T2", window_hours=48, now=now
            )
            == 0
        )

    def test_filters_user_tier_and_success(self):
        db = _FakeConn()
        db.queue_response(row={"n": 0})
        now = datetime(2026, 5, 21, 12, 0, tzinfo=timezone.utc)
        _count_recent_refreshes(
            db, user_id=42, tier="T3", window_hours=168, now=now
        )
        sql, params = db.calls[0]
        assert "FROM plan_refresh_log" in sql
        assert "WHERE user_id = ?" in sql
        assert "tier = ?" in sql
        assert "success = TRUE" in sql
        assert "triggered_at >= ?" in sql
        assert params[0] == 42
        assert params[1] == "T3"
        assert params[2] == now - timedelta(hours=168)

    def test_default_now_uses_utc(self, monkeypatch):
        db = _FakeConn()
        db.queue_response(row={"n": 0})
        captured: dict[str, datetime] = {}

        class _FrozenDatetime:
            @staticmethod
            def now(tz):
                captured["tz"] = tz
                return datetime(2026, 5, 21, 12, 0, tzinfo=tz)

        monkeypatch.setattr("routes.plan_refresh.datetime", _FrozenDatetime)
        _count_recent_refreshes(db, user_id=1, tier="T1", window_hours=24)
        assert captured["tz"] == timezone.utc


class TestCheckFrequencyCap:
    def test_under_cap(self):
        db = _FakeConn()
        db.queue_response(row={"n": 2})  # T1 limit = 3
        now = datetime(2026, 5, 21, 12, 0, tzinfo=timezone.utc)
        exceeded, count = _check_frequency_cap(db, user_id=1, tier="T1", now=now)
        assert exceeded is False
        assert count == 2

    def test_at_cap_is_exceeded(self):
        # Cap is reached when count >= limit; the next attempt would be
        # the (count+1)th in-window row.
        db = _FakeConn()
        db.queue_response(row={"n": 3})  # T1 limit = 3
        now = datetime(2026, 5, 21, 12, 0, tzinfo=timezone.utc)
        exceeded, count = _check_frequency_cap(db, user_id=1, tier="T1", now=now)
        assert exceeded is True
        assert count == 3

    def test_t2_at_cap(self):
        db = _FakeConn()
        db.queue_response(row={"n": 1})  # T2 limit = 1
        now = datetime(2026, 5, 21, 12, 0, tzinfo=timezone.utc)
        exceeded, count = _check_frequency_cap(db, user_id=1, tier="T2", now=now)
        assert exceeded is True
        assert count == 1

    def test_t3_window_hours_threaded(self):
        db = _FakeConn()
        db.queue_response(row={"n": 0})
        now = datetime(2026, 5, 21, 12, 0, tzinfo=timezone.utc)
        _check_frequency_cap(db, user_id=1, tier="T3", now=now)
        _, params = db.calls[0]
        # T3 window is 168h
        assert params[2] == now - timedelta(hours=168)
