"""Tests for `plan_conditions_repo` — persist/load of the Layer 5B artifact.

Uses a minimal `_FakeConn` (records `execute` calls + serves queued rows) in
the style of `tests/test_plan_nutrition_repo.py`. The key risk this guards is
the JSONB round trip: the tz-aware `generated_at`, the nested `model_meta`, the
date fields and the list fields (kit_items / advisory_flags / session_ids) must
survive `model_dump_json()` → store → `model_validate()` unchanged — through both
the psycopg2 (dict) and the SQLite-shim (JSON string) decode paths.
"""

from __future__ import annotations

import json
from datetime import date, datetime, timezone

from layer4.payload import CardioBlock, HRTarget, PlanSession
from layer5.conditions_builder import build_plan_conditions
from layer5.conditions_payload import PlanConditions
from plan_conditions_repo import (
    load_plan_conditions_by_version,
    persist_plan_conditions,
)
from weather_client import ExpectedConditions

USER_ID = 42
PVID = 99
D = date(2026, 7, 1)


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


# ─── fixture ─────────────────────────────────────────────────────────────────


def _session() -> PlanSession:
    return PlanSession(
        session_id="c-1",
        plan_version_id=PVID,
        date=D,
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


def _conditions() -> PlanConditions:
    ec = ExpectedConditions(
        temp_max_c=2.0, temp_min_c=-4.0, wet_day_probability_pct=55,
        sample_days=30, sample_years=5,
    )
    return build_plan_conditions(
        plan_version_id=PVID,
        sessions=[_session()],
        conditions_for=lambda _l, _d: ec,
        generated_at=datetime(2026, 6, 20, 12, 0, tzinfo=timezone.utc),
    )


# ─── tests ───────────────────────────────────────────────────────────────────


def test_persist_emits_upsert_with_denormalized_model():
    conn = _FakeConn()
    pc = _conditions()
    persist_plan_conditions(conn, USER_ID, pc)

    assert len(conn.calls) == 1
    sql, params = conn.calls[0]
    assert "INSERT INTO plan_conditions" in sql
    assert "ON CONFLICT (plan_version_id) DO UPDATE" in sql
    assert params[0] == PVID
    assert params[1] == USER_ID
    assert params[2] == pc.model_meta.model
    # payload_json is the full bundle as a JSON string; generated_at passed through.
    assert json.loads(params[3])["plan_version_id"] == PVID
    assert params[4] == pc.generated_at


def test_roundtrip_through_jsonb_dict_path():
    pc = _conditions()
    stored = json.loads(pc.model_dump_json())  # psycopg2 returns a dict

    reader = _FakeConn()
    reader.queue(row={"payload_json": stored})
    loaded = load_plan_conditions_by_version(reader, PVID)

    assert loaded is not None
    assert loaded.generated_at == pc.generated_at
    assert loaded.model_meta == pc.model_meta
    day = loaded.days[0]
    src = pc.days[0]
    assert day.date == src.date
    assert day.thermal_band == "cold"  # 2°C high
    assert day.kit_items == src.kit_items
    assert "waterproof layer" in day.kit_items  # wet 55% ≥ threshold
    assert day.advisory_flags == src.advisory_flags
    assert day.session_ids == ["c-1"]
    assert loaded.notes == pc.notes


def test_roundtrip_through_jsonb_string_path():
    pc = _conditions()
    stored = pc.model_dump_json()  # SQLite shim returns the raw JSON string

    reader = _FakeConn()
    reader.queue(row={"payload_json": stored})
    loaded = load_plan_conditions_by_version(reader, PVID)

    assert loaded is not None
    assert loaded == pc  # full structural equality across the string decode path


def test_load_returns_none_when_absent():
    conn = _FakeConn()  # no rows queued → fetchone returns None
    assert load_plan_conditions_by_version(conn, 12345) is None
