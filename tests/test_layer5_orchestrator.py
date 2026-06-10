"""Tests for `layer5.orchestrator.generate_and_persist_plan_nutrition`.

Exercises the assembly glue with a `_FakeConn` that serves the three queries in
order — load inputs (fetchone), load sessions (fetchall), persist (insert) —
so the full path runs without a real DB: stashed Layer 2E payload + persisted
sessions → `build_plan_nutrition` → `persist_plan_nutrition`. Also the
return-None "can't run" guards (no inputs / no sessions) the route relies on.
"""

from __future__ import annotations

from datetime import date, datetime, timezone

from layer4.context import (
    DailyNutritionBaseline,
    DailyPhaseTargets,
    Layer2EPayload,
    MacroTargets,
    RaceDayFueling,
    SupplementIntegrationPayload,
)
from layer4.payload import CardioBlock, HRTarget, PlanSession, SessionPhaseMetadata
from layer5.orchestrator import generate_and_persist_plan_nutrition

USER_ID = 7
PVID = 99
RACE_DATE = date(2026, 6, 6)


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


def _macros() -> MacroTargets:
    return MacroTargets(
        cho_g=420,
        cho_g_per_kg=6.0,
        cho_kcal=420 * 4,
        protein_g=119,
        protein_g_per_kg=1.7,
        protein_kcal=119 * 4,
        fat_g=70,
        fat_kcal=70 * 9,
        fat_floor_constrained=False,
    )


def _layer2e_payload() -> Layer2EPayload:
    targets = DailyPhaseTargets(
        activity_multiplier=1.7,
        activity_multiplier_source={"phase": "Base"},
        daily_calorie_target_kcal=3000,
        macros=_macros(),
    )
    rdf = RaceDayFueling(
        event_id="1",
        event_name="Spring 100",
        duration_tier="tier_long",
        cho_g_per_hr_low=60.0,
        cho_g_per_hr_high=90.0,
        na_mg_per_hr_low=400.0,
        na_mg_per_hr_high=700.0,
        sport_modifier_applied=1.0,
        salt_tolerance_modifier_applied=1.0,
        heat_acclim_modifier_applied=1.0,
        recommended_formats=["gel"],
        blocked_formats=[],
        sleep_dep_overlay_applies=False,
        notes=[],
    )
    return Layer2EPayload(
        athlete_id="7",
        etl_version_set={"0A": "0A-v7.0"},
        computed_at=datetime(2026, 6, 1, tzinfo=timezone.utc),
        bmr_method="mifflin_st_jeor",
        bmr_kcal=1600.0,
        daily_nutrition_baseline=DailyNutritionBaseline(per_phase={"Base": targets}),
        race_day_fueling=[rdf],
        supplement_integration=SupplementIntegrationPayload(
            integrated=[],
            race_day_suggestions=[],
            contraindication_flags=[],
            contraindication_hitl_items=[],
        ),
        dietary_pattern_adjustments=[],
        heat_acclim_adjustments=[],
        coaching_flags=[],
        hitl_items=[],
        hitl_required=False,
    )


def _session() -> PlanSession:
    return PlanSession(
        session_id="c-1",
        plan_version_id=PVID,
        date=RACE_DATE,
        day_of_week="Sat",
        session_index_in_day=0,
        time_of_day="morning",
        kind="cardio",
        discipline_id="run",
        discipline_name="Running",
        duration_min=120,
        intensity_summary="moderate",
        cardio_blocks=[
            CardioBlock(
                block_kind="main_set",
                duration_min=120,
                intensity_zone="Z3",
                intensity_target=HRTarget(hr_bpm_low=130, hr_bpm_high=150),
                instructions="steady",
            )
        ],
        phase_metadata=SessionPhaseMetadata(
            phase_name="Base",
            week_in_phase=1,
            total_weeks_in_phase=4,
            intended_volume_band=(8.0, 10.0),
            intended_intensity_distribution={"Z3": 1.0},
        ),
        session_notes="",
        coaching_intent="",
        coaching_flags=[],
    )


def _inputs_blob() -> dict:
    return {
        "layer2e_payload": _layer2e_payload().model_dump(mode="json"),
        "body_weight_kg": 70.0,
        "event_dates": {"1": RACE_DATE.isoformat()},
    }


# ─── tests ───────────────────────────────────────────────────────────────────


def test_happy_path_builds_and_persists():
    conn = _FakeConn()
    conn.queue(row={"payload_json": _inputs_blob()})  # load inputs
    conn.queue(rows=[{"payload_json": _session().model_dump(mode="json")}])  # sessions

    result = generate_and_persist_plan_nutrition(conn, USER_ID, PVID)

    assert result is not None
    assert result.plan_version_id == PVID
    # The race date was threaded through and flagged.
    assert result.days[0].is_race_day is True
    assert result.race_fueling[0].event_id == "1"
    # The persist INSERT fired last with the artifact + user.
    insert_sql, params = conn.calls[-1]
    assert "INSERT INTO plan_nutrition" in insert_sql
    assert params[0] == PVID
    assert params[1] == USER_ID


def test_returns_none_when_inputs_absent():
    conn = _FakeConn()  # first execute → no row → load_inputs returns None
    assert generate_and_persist_plan_nutrition(conn, USER_ID, PVID) is None
    # Only the inputs lookup was attempted; no sessions load, no persist.
    assert len(conn.calls) == 1


def test_returns_none_when_no_sessions():
    conn = _FakeConn()
    conn.queue(row={"payload_json": _inputs_blob()})  # inputs present
    conn.queue(rows=[])  # but no sessions
    assert generate_and_persist_plan_nutrition(conn, USER_ID, PVID) is None
    # No persist call.
    assert not any("INSERT INTO plan_nutrition" in c[0] for c in conn.calls)


def test_returns_none_when_body_weight_nonpositive():
    conn = _FakeConn()
    blob = _inputs_blob()
    blob["body_weight_kg"] = 0.0
    conn.queue(row={"payload_json": blob})
    assert generate_and_persist_plan_nutrition(conn, USER_ID, PVID) is None
