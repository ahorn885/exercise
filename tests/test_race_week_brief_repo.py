"""Tests for `race_week_brief_repo.py` — #732 slice 2 persistence.

Coverage:
- `persist_race_week_brief`: INSERT ... ON CONFLICT (plan_version_id) upsert;
  denormalized event_date + race_format; race_plan_json NULL for single-day
  and non-NULL for multi-day.
- `load_race_week_brief`: JSONB -> (RaceWeekBrief, RacePlan|None) round-trip;
  None when no row; dual-path JSONB hydration (dict + str).
- `persist_race_week_brief_result`: writes the merged Taper window in place
  (plan_sessions upsert) AND the structured brief (race_week_briefs upsert).

The fake `db` echoes SQL + params per the `_FakeConn` pattern shared with
`tests/test_plan_sessions_repo.py`.
"""

from __future__ import annotations

import json
from datetime import date, datetime

from layer4.payload import (
    Contingency,
    FuelingStrategy,
    Layer4Payload,
    PacingStrategy,
    RacePlan,
    RaceWeekBrief,
    ValidatorResult,
)
from race_week_brief_repo import (
    load_race_week_brief,
    persist_race_week_brief,
    persist_race_week_brief_result,
    write_race_week_brief_log,
)


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
        self.committed = False

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
        self.committed = True


# ─── factory helpers ────────────────────────────────────────────────────────


def _make_brief(*, race_format: str = "single_day") -> RaceWeekBrief:
    return RaceWeekBrief(
        days_to_event=7,
        event_name="Test Race 2026",
        event_date=date(2026, 6, 8),
        event_locale="home",
        race_format=race_format,  # type: ignore[arg-type]
        goal_outcome="Finish",
        pre_race_logistics="Arrive Friday, check in Saturday.",
        kit_manifest=[],
        kit_check_dates=[date(2026, 6, 6)],
        race_day_fueling_plan="60g cho/hr.",
        pre_race_meal_strategy="Oats 3h prior.",
        pacing_strategy_summary="Even effort.",
        contingencies=["If cramping, slow + salt."],
        mental_prep_cues=["Relax shoulders."],
    )


def _make_race_plan() -> RacePlan:
    return RacePlan(
        race_name="Test Expedition 2026",
        race_start_datetime=datetime(2026, 6, 8, 6, 0, 0),
        race_end_estimate_datetime=datetime(2026, 6, 10, 18, 0, 0),
        race_format="continuous_multi_day",
        locales=["home"],
        segments=[],
        transitions=[],
        pacing_strategy=PacingStrategy(
            overall_intensity_target="Z2",
            pacing_milestones=["CP1 by hour 6."],
            rationale_text="Conserve early.",
        ),
        fueling_strategy=FuelingStrategy(
            cho_g_per_hr_low=50,
            cho_g_per_hr_high=70,
            sodium_mg_per_hr=600,
            fluid_ml_per_hr=600,
            caffeine_strategy="100mg overnight.",
            rationale_text="Sustained low-intensity demand.",
        ),
        contingencies=[
            Contingency(
                trigger="Storm",
                action_plan="Shelter at CP2.",
                threshold_to_invoke="Lightning <5km.",
            )
        ],
    )


def _make_race_week_brief_payload(
    *, race_format: str = "single_day", with_race_plan: bool = False
) -> Layer4Payload:
    brief = _make_brief(race_format=race_format)
    return Layer4Payload(
        user_id=_USER_ID,
        mode="race_week_brief",
        plan_version_id=_PLAN_VERSION_ID,
        scope_start_date=date(2026, 6, 1),
        scope_end_date=date(2026, 6, 8),
        model_synthesizer="claude-sonnet-4-6",
        temperature=0.2,
        pattern="B",
        latency_ms_total=8000,
        input_tokens_total=4500,
        output_tokens_total=2500,
        llm_call_count=1,
        etl_version_set={"0A": "v7", "0B": "v7", "0C": "v7"},
        sessions=[],
        validator_results=[
            ValidatorResult(
                pass_index=0, accepted=True, rule_failures=[], retried_phase_names=[]
            )
        ],
        notable_observations=[],
        race_week_brief=brief,
        race_plan=_make_race_plan() if with_race_plan else None,
    )


# ─── persist_race_week_brief ────────────────────────────────────────────────


class TestPersistRaceWeekBrief:
    def test_upserts_single_day_with_null_race_plan(self):
        conn = _FakeConn()
        brief = _make_brief()

        persist_race_week_brief(conn, _USER_ID, _PLAN_VERSION_ID, brief)

        assert len(conn.calls) == 1
        sql, params = conn.calls[0]
        assert "INSERT INTO race_week_briefs" in sql
        assert "ON CONFLICT (plan_version_id) DO UPDATE" in sql
        # (plan_version_id, user_id, event_date, race_format, brief_json,
        #  race_plan_json, generated_at)
        assert params[0] == _PLAN_VERSION_ID
        assert params[1] == _USER_ID
        assert params[2] == brief.event_date
        assert params[3] == "single_day"
        assert json.loads(params[4])["event_name"] == "Test Race 2026"
        assert params[5] is None  # race_plan_json NULL for single-day
        assert not conn.committed  # caller owns the txn

    def test_upserts_multi_day_with_race_plan_json(self):
        conn = _FakeConn()
        brief = _make_brief(race_format="continuous_multi_day")
        race_plan = _make_race_plan()

        persist_race_week_brief(
            conn, _USER_ID, _PLAN_VERSION_ID, brief, race_plan
        )

        _, params = conn.calls[0]
        assert params[3] == "continuous_multi_day"
        assert params[5] is not None
        assert json.loads(params[5])["race_name"] == "Test Expedition 2026"


# ─── write_race_week_brief_log ──────────────────────────────────────────────


class TestWriteRaceWeekBriefLog:
    def test_success_row_carries_telemetry(self):
        conn = _FakeConn()

        write_race_week_brief_log(
            conn,
            user_id=_USER_ID,
            plan_version_id=_PLAN_VERSION_ID,
            days_to_event=7,
            duration_ms=8200,
            input_tokens=4500,
            output_tokens=2500,
            llm_call_count=1,
            success=True,
            failure_reason=None,
        )

        assert len(conn.calls) == 1
        sql, params = conn.calls[0]
        assert "INSERT INTO race_week_brief_log" in sql
        # (user_id, plan_version_id, days_to_event, duration_ms, input_tokens,
        #  output_tokens, llm_call_count, success, failure_reason)
        assert params == (_USER_ID, _PLAN_VERSION_ID, 7, 8200, 4500, 2500, 1, True, None)
        assert not conn.committed  # caller owns the txn

    def test_failure_row_has_null_telemetry_and_reason(self):
        conn = _FakeConn()

        write_race_week_brief_log(
            conn,
            user_id=_USER_ID,
            plan_version_id=None,
            days_to_event=None,
            duration_ms=None,
            input_tokens=None,
            output_tokens=None,
            llm_call_count=None,
            success=False,
            failure_reason="no_active_plan",
        )

        _, params = conn.calls[0]
        assert params[0] == _USER_ID
        assert params[1] is None  # plan_version_id unknown on failure
        assert params[7] is False  # success
        assert params[8] == "no_active_plan"  # failure_reason


# ─── load_race_week_brief ───────────────────────────────────────────────────


class TestLoadRaceWeekBrief:
    def test_returns_none_when_no_row(self):
        conn = _FakeConn()
        conn.queue(row=None)

        assert load_race_week_brief(conn, _PLAN_VERSION_ID) is None

    def test_round_trips_brief_single_day(self):
        conn = _FakeConn()
        brief = _make_brief()
        conn.queue(
            row={
                "brief_json": json.loads(brief.model_dump_json()),
                "race_plan_json": None,
            }
        )

        result = load_race_week_brief(conn, _PLAN_VERSION_ID)

        assert result is not None
        loaded_brief, loaded_plan = result
        assert isinstance(loaded_brief, RaceWeekBrief)
        assert loaded_brief.event_name == "Test Race 2026"
        assert loaded_plan is None

    def test_round_trips_brief_and_race_plan(self):
        conn = _FakeConn()
        brief = _make_brief(race_format="continuous_multi_day")
        race_plan = _make_race_plan()
        conn.queue(
            row={
                "brief_json": json.loads(brief.model_dump_json()),
                "race_plan_json": json.loads(race_plan.model_dump_json()),
            }
        )

        result = load_race_week_brief(conn, _PLAN_VERSION_ID)

        assert result is not None
        loaded_brief, loaded_plan = result
        assert loaded_brief.race_format == "continuous_multi_day"
        assert isinstance(loaded_plan, RacePlan)
        assert loaded_plan.race_name == "Test Expedition 2026"

    def test_tolerates_json_string_path(self):
        """SQLite shim path returns JSONB columns as strings, not dicts."""
        conn = _FakeConn()
        brief = _make_brief()
        conn.queue(
            row={
                "brief_json": brief.model_dump_json(),  # str, not dict
                "race_plan_json": None,
            }
        )

        result = load_race_week_brief(conn, _PLAN_VERSION_ID)

        assert result is not None
        assert result[0].event_name == "Test Race 2026"


# ─── persist_race_week_brief_result ─────────────────────────────────────────


class TestPersistRaceWeekBriefResult:
    def test_writes_sessions_in_place_and_structured_brief(self):
        conn = _FakeConn()
        payload = _make_race_week_brief_payload()

        persist_race_week_brief_result(conn, payload)

        # No sessions in this fixture, so plan_sessions sees no INSERT; the
        # structured brief upsert always fires.
        brief_calls = [c for c in conn.calls if "race_week_briefs" in c[0]]
        assert len(brief_calls) == 1
        assert "ON CONFLICT (plan_version_id) DO UPDATE" in brief_calls[0][0]
        assert not conn.committed

    def test_session_writes_use_on_conflict_upsert(self):
        from layer4.payload import CardioBlock, HRTarget, PlanSession

        conn = _FakeConn()
        payload = _make_race_week_brief_payload()
        session = PlanSession(
            session_id="ps-taper-1",
            plan_version_id=_PLAN_VERSION_ID,
            date=date(2026, 6, 5),
            day_of_week="Fri",
            session_index_in_day=0,
            time_of_day="morning",
            kind="cardio",
            discipline_id="D-run",
            discipline_name="Running",
            locale_id="home",
            locale_name="Home",
            duration_min=40,
            intensity_summary="easy",
            cardio_blocks=[
                CardioBlock(
                    block_kind="main_set",
                    duration_min=40,
                    intensity_zone="Z2",
                    intensity_target=HRTarget(hr_bpm_low=120, hr_bpm_high=135),
                    instructions="Easy shakeout.",
                )
            ],
            session_notes="Easy shakeout.",
            coaching_intent="Stay loose.",
            coaching_flags=[],
        )
        payload = payload.model_copy(update={"sessions": [session]})

        persist_race_week_brief_result(conn, payload)

        session_calls = [c for c in conn.calls if "INTO plan_sessions" in c[0]]
        assert len(session_calls) == 1
        assert (
            "ON CONFLICT (plan_version_id, date, session_index_in_day)"
            in session_calls[0][0]
        )
