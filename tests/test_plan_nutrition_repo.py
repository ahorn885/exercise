"""Tests for `plan_nutrition_repo` — persist/load of the Layer 5A artifact.

Uses a minimal `_FakeConn` (records `execute` calls + serves queued rows) in
the style of `tests/test_layer4_orchestrator.py`. The key risk this guards is
the JSONB round trip: tuple fields (e.g. race-day per-hour bands), the tz-aware
`generated_at`, and the nested macro / phase models must survive
`model_dump_json()` → store → `model_validate()` unchanged.
"""

from __future__ import annotations

from datetime import date, datetime, timezone

from layer4.context import (
    DailyNutritionBaseline,
    DailyPhaseTargets,
    MacroTargets,
    RaceDayFueling,
)
from layer4.payload import CardioBlock, HRTarget, PlanSession, SessionPhaseMetadata
from layer5 import build_plan_nutrition
from plan_nutrition_repo import (
    load_plan_nutrition_by_version,
    load_plan_nutrition_inputs,
    persist_plan_nutrition,
    persist_plan_nutrition_inputs,
)

BW = 70.0
USER_ID = 42


# ─── fake connection ─────────────────────────────────────────────────────────


class _FakeCursor:
    def __init__(self, row=None):
        self._row = row

    def fetchone(self):
        return self._row


class _FakeConn:
    def __init__(self):
        self.calls: list[tuple[str, tuple]] = []
        self.responses: list = []

    def queue(self, row=None):
        self.responses.append(row)

    def execute(self, sql, params=()):
        self.calls.append((sql, params))
        row = self.responses.pop(0) if self.responses else None
        return _FakeCursor(row=row)


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


def _baseline() -> DailyNutritionBaseline:
    targets = DailyPhaseTargets(
        activity_multiplier=1.7,
        activity_multiplier_source={"phase": "Base"},
        daily_calorie_target_kcal=3000,
        macros=_macros(),
    )
    return DailyNutritionBaseline(per_phase={"Base": targets})


def _session(d: date) -> PlanSession:
    return PlanSession(
        session_id=f"c-{d.isoformat()}",
        plan_version_id=99,
        date=d,
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
            intended_intensity_distribution={"Z2": 0.8, "Z3": 0.2},
        ),
        session_notes="",
        coaching_intent="",
        coaching_flags=[],
    )


def _race_fueling() -> RaceDayFueling:
    return RaceDayFueling(
        event_id="e1",
        event_name="Spring 100",
        duration_tier="tier_long",
        cho_g_per_hr_low=60.0,
        cho_g_per_hr_high=90.0,
        na_mg_per_hr_low=400.0,
        na_mg_per_hr_high=700.0,
        fluid_ml_per_hr_low=450.0,
        fluid_ml_per_hr_high=750.0,
        sport_modifier_applied=1.0,
        salt_tolerance_modifier_applied=1.0,
        heat_acclim_modifier_applied=1.0,
        recommended_formats=["gel", "drink_mix"],
        blocked_formats=["solid_bar"],
        sleep_dep_overlay_applies=False,
        notes=["practise in training"],
    )


def _build_nutrition() -> "object":
    race_date = date(2026, 6, 6)
    return build_plan_nutrition(
        plan_version_id=99,
        sessions=[_session(race_date)],
        baseline=_baseline(),
        bmr_kcal=1600.0,
        body_weight_kg=BW,
        race_day_fueling=[_race_fueling()],
        event_dates={"e1": race_date},
        generated_at=datetime(2026, 6, 8, 12, 0, tzinfo=timezone.utc),
    )


# ─── tests ───────────────────────────────────────────────────────────────────


def test_persist_issues_upsert_with_expected_columns():
    conn = _FakeConn()
    nutr = _build_nutrition()
    persist_plan_nutrition(conn, USER_ID, nutr)

    assert len(conn.calls) == 1
    sql, params = conn.calls[0]
    assert "INSERT INTO plan_nutrition" in sql
    assert "ON CONFLICT (plan_version_id) DO UPDATE" in sql
    # (plan_version_id, user_id, energy_model, payload_json, generated_at)
    assert params[0] == 99
    assert params[1] == USER_ID
    assert params[2] == "load_redistribution_v1"
    assert params[4] == nutr.generated_at
    assert isinstance(params[3], str) and '"plan_version_id":99' in params[3]


def test_persist_load_round_trip_preserves_bundle():
    conn = _FakeConn()
    nutr = _build_nutrition()
    persist_plan_nutrition(conn, USER_ID, nutr)
    payload_json = conn.calls[0][1][3]  # the stored JSONB blob

    # Reload from the stored blob (simulate psycopg2 string path).
    reader = _FakeConn()
    reader.queue(row={"payload_json": payload_json})
    loaded = load_plan_nutrition_by_version(reader, 99)

    assert loaded is not None
    assert loaded.model_dump() == nutr.model_dump()
    # Spot-check the round-trip-fragile bits survived.
    assert loaded.race_fueling[0].cho_g_per_hr == (60.0, 90.0)
    assert loaded.generated_at == nutr.generated_at
    assert loaded.days[0].macros.protein_g == nutr.days[0].macros.protein_g


def test_load_returns_none_when_absent():
    conn = _FakeConn()  # no queued row → fetchone() returns None
    assert load_plan_nutrition_by_version(conn, 12345) is None
    assert conn.calls[0][1] == (12345,)


def test_load_tolerates_dict_payload_from_jsonb_adapter():
    nutr = _build_nutrition()
    conn = _FakeConn()
    # psycopg2 JSONB adapter hands back a dict, not a string.
    conn.queue(row={"payload_json": nutr.model_dump(mode="json")})
    loaded = load_plan_nutrition_by_version(conn, 99)
    assert loaded is not None
    assert loaded.plan_version_id == 99


# ─── inputs snapshot ─────────────────────────────────────────────────────────


def test_inputs_persist_load_round_trip():
    conn = _FakeConn()
    l2e_json = {"daily_nutrition_baseline": {"per_phase": {}}, "bmr_kcal": 1600.0}
    persist_plan_nutrition_inputs(
        conn,
        USER_ID,
        99,
        layer2e_payload_json=l2e_json,
        body_weight_kg=70.0,
        event_dates={"1": "2026-06-06"},
    )
    sql, params = conn.calls[0]
    assert "INSERT INTO plan_nutrition_inputs" in sql
    assert "ON CONFLICT (plan_version_id) DO UPDATE" in sql
    assert params[0] == 99 and params[1] == USER_ID

    reader = _FakeConn()
    reader.queue(row={"payload_json": params[2]})  # the stored JSON blob
    blob = load_plan_nutrition_inputs(reader, 99)
    assert blob is not None
    assert blob["body_weight_kg"] == 70.0
    assert blob["event_dates"] == {"1": "2026-06-06"}
    assert blob["layer2e_payload"] == l2e_json


def test_inputs_load_returns_none_when_absent():
    conn = _FakeConn()
    assert load_plan_nutrition_inputs(conn, 404) is None
