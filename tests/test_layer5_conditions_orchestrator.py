"""Tests for `layer5.conditions_orchestrator.generate_and_persist_plan_conditions`.

A `_FakeConn` serves the queries in order — load sessions (fetchall), per-locale
coordinate lookups (fetchone), then the persist INSERT — so the full assembly
path runs without a real DB. A stub `fetcher` feeds `weather_client` canned
climate data so no network is touched. Also covers the return-None "can't run"
guards (no sessions / no coordinates) the route relies on.
"""

from __future__ import annotations

from datetime import date

from layer4.payload import CardioBlock, HRTarget, PlanSession
from layer5.conditions_builder import CONDITIONS_MODEL_NAME
from layer5.conditions_orchestrator import generate_and_persist_plan_conditions

USER_ID = 7
PVID = 99
SESSION_DATE = date(2026, 7, 1)
TODAY = date(2026, 6, 20)


# ─── fake connection ─────────────────────────────────────────────────────────


class _FakeCursor:
    def __init__(self, row=None, rows=None):
        self._row = row
        self._rows = rows or []

    def fetchone(self):
        return self._row

    def fetchall(self):
        return self._rows


class _FakeConn:
    def __init__(self):
        self.calls: list[tuple[str, tuple]] = []
        self.responses: list[tuple] = []

    def queue(self, row=None, rows=None):
        self.responses.append((row, rows or []))

    def execute(self, sql, params=()):
        self.calls.append((sql, params))
        row, rows = self.responses.pop(0) if self.responses else (None, [])
        return _FakeCursor(row=row, rows=rows)


# ─── fixtures ────────────────────────────────────────────────────────────────


def _session() -> PlanSession:
    return PlanSession(
        session_id="c-1",
        plan_version_id=PVID,
        date=SESSION_DATE,
        day_of_week="Wed",
        session_index_in_day=0,
        time_of_day="morning",
        kind="cardio",
        discipline_id="run",
        discipline_name="Running",
        locale_id="park",
        locale_name="City Park",
        duration_min=60,
        intensity_summary="moderate",
        cardio_blocks=[
            CardioBlock(
                block_kind="main_set",
                duration_min=60,
                intensity_zone="Z2",
                intensity_target=HRTarget(hr_bpm_low=120, hr_bpm_high=140),
                instructions="steady",
            )
        ],
        session_notes="",
        coaching_intent="",
        coaching_flags=[],
    )


def _fetcher(url, params):
    """Canned Open-Meteo archive response (warm + occasionally wet)."""
    return {
        "daily": {
            "temperature_2m_max": [25.0, 26.0, 24.0],
            "temperature_2m_min": [14.0, 13.0, 15.0],
            "precipitation_sum": [0.0, 2.0, 0.0],
        }
    }


# ─── tests ───────────────────────────────────────────────────────────────────


def test_happy_path_builds_and_persists():
    conn = _FakeConn()
    conn.queue(rows=[{"payload_json": _session().model_dump(mode="json")}])  # sessions
    conn.queue(row={"lat": 51.5, "lng": -0.12})  # coords for "park"

    result = generate_and_persist_plan_conditions(
        conn, USER_ID, PVID, today=TODAY, fetcher=_fetcher
    )

    assert result is not None
    assert result.plan_version_id == PVID
    assert result.model_meta.model == CONDITIONS_MODEL_NAME
    assert len(result.days) == 1
    day = result.days[0]
    assert day.locale_id == "park"
    assert day.thermal_band == "warm"  # 25°C high from the canned data
    assert day.wet_day_probability_pct == 33  # 1 of 3 sample days ≥ 1 mm

    # The persist INSERT fired last with the artifact + user + denormalized model.
    insert_sql, params = conn.calls[-1]
    assert "INSERT INTO plan_conditions" in insert_sql
    assert params[0] == PVID
    assert params[1] == USER_ID
    assert params[2] == CONDITIONS_MODEL_NAME


def test_returns_none_when_no_sessions():
    conn = _FakeConn()  # first execute → no rows → load sessions returns []
    assert (
        generate_and_persist_plan_conditions(conn, USER_ID, PVID, today=TODAY, fetcher=_fetcher)
        is None
    )
    assert len(conn.calls) == 1  # only the sessions load was attempted


def test_returns_none_when_no_coordinates():
    conn = _FakeConn()
    conn.queue(rows=[{"payload_json": _session().model_dump(mode="json")}])  # sessions
    conn.queue(row=None)  # coords lookup for "park" → missing

    assert (
        generate_and_persist_plan_conditions(conn, USER_ID, PVID, today=TODAY, fetcher=_fetcher)
        is None
    )
    # Sessions load + one coord lookup; no persist.
    assert not any("INSERT INTO plan_conditions" in c[0] for c in conn.calls)


def test_returns_none_when_only_localeless_sessions():
    conn = _FakeConn()
    rest = PlanSession(
        session_id="r-1",
        plan_version_id=PVID,
        date=SESSION_DATE,
        day_of_week="Wed",
        session_index_in_day=0,
        time_of_day="unspecified",
        kind="rest",
        duration_min=0,
        intensity_summary="rest",
        rest_reason="planned_recovery",
        session_notes="",
        coaching_intent="",
        coaching_flags=[],
    )
    conn.queue(rows=[{"payload_json": rest.model_dump(mode="json")}])  # sessions, no locale

    assert (
        generate_and_persist_plan_conditions(conn, USER_ID, PVID, today=TODAY, fetcher=_fetcher)
        is None
    )
    # No coord lookup, no persist — bailed on the empty locale set.
    assert len(conn.calls) == 1
