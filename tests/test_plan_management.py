"""Tests for `plan_management.py` — `Plan_Management_Spec_v1.md` §5.1
`derive_current_phase` + §5.2 `derive_heat_acclim_state` (#221).

§5.3 `expected_race_temp_c` (forecast leg) + the 2E §5.8 overlay wiring land
with #220 and are tested there.
"""

from __future__ import annotations

from datetime import date, datetime, timedelta

import pytest

from layer4.context import GoalViability, HeatAcclimState, Layer3BPayload, PeriodizationShape
from layer4.errors import Layer4InputError
from plan_management import (
    derive_current_phase,
    derive_expected_race_temp_c,
    derive_heat_acclim_state,
)


# ─── Fixtures ────────────────────────────────────────────────────────────────


_PLAN_START = date(2026, 1, 1)


def _layer3b(
    *,
    mode: str = "standard",
    start_phase: str = "Base",
    phase_weeks: dict[str, int] | None = None,
    time_to_event_weeks: int | None = None,
) -> Layer3BPayload:
    # Mirrors tests/test_layer4_phase_structure.py::_layer3b.
    top_mode = "event" if time_to_event_weeks is not None else "no-event"
    return Layer3BPayload(
        user_id=42,
        as_of=datetime(2026, 1, 1, 10, 0, 0),
        model="claude-opus-4-7",
        temperature=0.0,
        prompt_hash="abc",
        latency_ms=1500,
        input_tokens=3000,
        output_tokens=800,
        etl_version_set={"layer0": "v7"},
        mode=top_mode,  # type: ignore[arg-type]
        time_to_event_weeks=time_to_event_weeks,
        goal_viability=GoalViability(
            viability="achievable",
            confidence="high",
            reasoning_text="solid base",
            evidence_basis=["e"],
            suggested_adjustments=[],
        ),
        periodization_shape=PeriodizationShape(
            mode=mode,  # type: ignore[arg-type]
            start_phase=start_phase,  # type: ignore[arg-type]
            phase_weeks=phase_weeks,  # type: ignore[arg-type]
            reasoning_text="r",
            evidence_basis=["e"],
        ),
        hitl_surface=[],
        notable_observations=[],
    )


class _FakeCursor:
    def __init__(self, row):
        self._row = row

    def fetchone(self):
        return self._row


class _FakeConn:
    """Single-query fake — returns one queued conditions_log aggregate row."""

    def __init__(self, row):
        self._row = row
        self.calls: list[tuple[str, tuple]] = []

    def execute(self, sql, params=()):
        self.calls.append((sql, params))
        return _FakeCursor(self._row)


# ─── §5.1 derive_current_phase ───────────────────────────────────────────────


# 20-week standard from Base (open-ended → no terminal floor):
# 50/30/15/5 = Base 10 / Build 6 / Peak 3 / Taper 1, dated from 2026-01-01:
#   Base  2026-01-01..2026-03-11   Build 2026-03-12..2026-04-22
#   Peak  2026-04-23..2026-05-13   Taper 2026-05-14..2026-05-20
_TW = 20


class TestDeriveCurrentPhase:
    def test_mid_plan_returns_active_phase(self):
        # today inside the Build window.
        phase = derive_current_phase(
            _layer3b(), _PLAN_START, date(2026, 3, 15), total_weeks=_TW
        )
        assert phase == "Build"

    def test_base_window(self):
        phase = derive_current_phase(
            _layer3b(), _PLAN_START, date(2026, 2, 1), total_weeks=_TW
        )
        assert phase == "Base"

    def test_taper_window(self):
        phase = derive_current_phase(
            _layer3b(), _PLAN_START, date(2026, 5, 18), total_weeks=_TW
        )
        assert phase == "Taper"

    def test_before_plan_start_clamps_to_first_block(self):
        phase = derive_current_phase(
            _layer3b(), _PLAN_START, date(2025, 12, 1), total_weeks=_TW
        )
        assert phase == "Base"

    def test_past_plan_end_clamps_to_last_block(self):
        # 2026-08-01 is well past the Taper end (2026-05-20) → last block.
        phase = derive_current_phase(
            _layer3b(), _PLAN_START, date(2026, 8, 1), total_weeks=_TW
        )
        assert phase == "Taper"

    def test_non_base_start_clamps_before_to_first_surviving_block(self):
        # start_phase=Build drops Base; first surviving block is Build.
        phase = derive_current_phase(
            _layer3b(start_phase="Build"),
            _PLAN_START,
            date(2025, 12, 1),
            total_weeks=_TW,
        )
        assert phase == "Build"

    def test_custom_mode_uses_phase_weeks_verbatim(self):
        # custom: Base 2 / Build 2 / Peak 2 / Taper 2 → 8 weeks from 2026-01-01.
        #   Base 01-01..01-14  Build 01-15..01-28  Peak 01-29..02-11  Taper 02-12..02-25
        l3b = _layer3b(
            mode="custom",
            phase_weeks={"Base": 2, "Build": 2, "Peak": 2, "Taper": 2},
        )
        assert derive_current_phase(l3b, _PLAN_START, date(2026, 1, 20)) == "Build"
        assert derive_current_phase(l3b, _PLAN_START, date(2026, 2, 13)) == "Taper"

    def test_degenerate_shape_raises(self):
        # total_weeks=0 → phase_structure_from_3b raises (a phase with no plan
        # is a contract violation, not a default — spec §9).
        with pytest.raises(Layer4InputError):
            derive_current_phase(_layer3b(), _PLAN_START, date(2026, 3, 1), total_weeks=0)


# ─── §5.2 derive_heat_acclim_state ───────────────────────────────────────────


_TODAY = date(2026, 6, 29)


def _state_for(total_days: int, hot_days: int) -> tuple[HeatAcclimState, bool, _FakeConn]:
    db = _FakeConn({"total_days": total_days, "hot_days": hot_days})
    state, sparse = derive_heat_acclim_state(db, user_id=42, today=_TODAY)
    return state, sparse, db


class TestDeriveHeatAcclimState:
    def test_low_band(self):
        state, sparse, _ = _state_for(total_days=10, hot_days=2)
        assert state.level == "low"
        assert state.days_at_temp_last_30 == 2
        assert state.last_assessment == _TODAY
        assert sparse is False

    def test_moderate_band(self):
        state, sparse, _ = _state_for(total_days=20, hot_days=8)
        assert state.level == "moderate"
        assert sparse is False

    def test_high_band(self):
        state, sparse, _ = _state_for(total_days=25, hot_days=16)
        assert state.level == "high"
        assert sparse is False

    @pytest.mark.parametrize(
        "hot_days,expected",
        [(4, "low"), (5, "moderate"), (13, "moderate"), (14, "high")],
    )
    def test_band_boundaries(self, hot_days, expected):
        # total_days kept >=5 so the sparse override doesn't mask the band.
        state, sparse, _ = _state_for(total_days=20, hot_days=hot_days)
        assert state.level == expected
        assert sparse is False

    def test_sparse_data_forces_low_and_flags(self):
        # <5 logged condition-days total → low + sparse advisory (§5.2.4).
        state, sparse, _ = _state_for(total_days=3, hot_days=1)
        assert state.level == "low"
        assert state.days_at_temp_last_30 == 1
        assert sparse is True

    def test_no_conditions_logged(self):
        # Empty log → {low, 0, today} + sparse (§5.2.4 / edge §9).
        state, sparse, _ = _state_for(total_days=0, hot_days=0)
        assert state.level == "low"
        assert state.days_at_temp_last_30 == 0
        assert sparse is True

    def test_null_aggregate_row_is_safe(self):
        # COUNT over an empty set can surface NULLs through some drivers —
        # treat as zero rather than crash.
        db = _FakeConn({"total_days": None, "hot_days": None})
        state, sparse = derive_heat_acclim_state(db, user_id=42, today=_TODAY)
        assert state.level == "low"
        assert state.days_at_temp_last_30 == 0
        assert sparse is True

    def test_query_uses_77f_threshold_and_30day_window(self):
        _, _, db = _state_for(total_days=10, hot_days=3)
        sql, params = db.calls[0]
        assert "conditions_log" in sql
        assert params[0] == 77.0
        assert params[1] == 42
        assert params[2] == (_TODAY - timedelta(days=30)).isoformat()


# ─── §5.3 derive_expected_race_temp_c ────────────────────────────────────────


class _Ev:
    """Minimal event satisfying the §5.3 read surface (event_id + event_date)."""

    def __init__(self, event_id: str, event_date: date):
        self.event_id = event_id
        self.event_date = event_date


_COORDS = {"e1": (44.32, -93.20)}


def _weather_fetcher(normal_high: float | None, forecast_high: float | None):
    """One fetcher serving both legs — archive URL → climate-normal sample,
    forecast URL → single-day high. ``None`` on either → that leg fails."""

    def fetch(url, params):
        if "archive" in url:
            if normal_high is None:
                return None
            return {
                "daily": {
                    "temperature_2m_max": [normal_high],
                    "temperature_2m_min": [normal_high - 10.0],
                    "precipitation_sum": [0.0],
                }
            }
        if forecast_high is None:
            return None
        return {"daily": {"temperature_2m_max": [forecast_high]}}

    return fetch


class TestDeriveExpectedRaceTempC:
    def test_no_coords_is_none_without_fetching(self):
        # §13.3 — locale with no coordinates → None, no weather call.
        def fetch(url, params):  # pragma: no cover - must not be called
            raise AssertionError("should not fetch without coords")

        ev = _Ev("nocoord", date(2026, 7, 17))
        out = derive_expected_race_temp_c([ev], {}, _TODAY, fetcher=fetch)
        assert out == {"nocoord": None}

    def test_far_out_uses_climate_normal_only(self):
        # >14 days out → normal leg only (forecast not consulted).
        ev = _Ev("e1", _TODAY + timedelta(days=40))
        out = derive_expected_race_temp_c(
            [ev], _COORDS, _TODAY,
            fetcher=_weather_fetcher(normal_high=26.0, forecast_high=99.0),
        )
        assert out == {"e1": 26.0}

    def test_inside_horizon_blends_normal_and_forecast(self):
        # §13.2 — 10 days out, normal 29, forecast 33 →
        # w_forecast = 1 - 10/14 ≈ 0.2857 → 0.2857·33 + 0.7143·29 ≈ 30.1.
        ev = _Ev("e1", _TODAY + timedelta(days=10))
        out = derive_expected_race_temp_c(
            [ev], _COORDS, _TODAY,
            fetcher=_weather_fetcher(normal_high=29.0, forecast_high=33.0),
        )
        assert out["e1"] == 30.1

    def test_forecast_failure_inside_horizon_falls_back_to_normal(self):
        ev = _Ev("e1", _TODAY + timedelta(days=5))
        out = derive_expected_race_temp_c(
            [ev], _COORDS, _TODAY,
            fetcher=_weather_fetcher(normal_high=24.0, forecast_high=None),
        )
        assert out["e1"] == 24.0

    def test_no_normal_sample_trusts_forecast(self):
        ev = _Ev("e1", _TODAY + timedelta(days=5))
        out = derive_expected_race_temp_c(
            [ev], _COORDS, _TODAY,
            fetcher=_weather_fetcher(normal_high=None, forecast_high=31.0),
        )
        assert out["e1"] == 31.0

    def test_both_legs_fail_is_none(self):
        ev = _Ev("e1", _TODAY + timedelta(days=5))
        out = derive_expected_race_temp_c(
            [ev], _COORDS, _TODAY,
            fetcher=_weather_fetcher(normal_high=None, forecast_high=None),
        )
        assert out["e1"] is None
