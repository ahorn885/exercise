"""Tests for `plan_sessions_repo.py` — Phase 5.2 caller-side substrate.

Coverage:
- `allocate_plan_version_row`: happy path + input validation (created_via /
  pattern enum + scope_start <= scope_end) + RETURNING id round-trip +
  notes JSONB serialization.
- `persist_layer4_sessions`: stamps natural-key columns + payload_json
  per session; empty sessions list is a no-op; does NOT commit.
- `load_plan_sessions_by_version`: ordering by (date, session_index_in_day);
  JSONB → PlanSession round-trip; dual-path JSONB hydration (dict + str).
- `load_prior_plan_session_window`: tier-tied default mapping (T1/T2/T3
  → 2/7/28 days) + explicit days override + ValueError when both None +
  cutoff window `[today - days, today - 1]` inclusive + ORDER BY clause
  for per-day version pointer resolver.

The fake `db` echoes the SQL + params + queued response shape per the
`_FakeConn` pattern shared with `tests/test_layer4_orchestrator.py`.
"""

from __future__ import annotations

import json
from datetime import date
from typing import Any

import pytest

from layer4.payload import (
    CardioBlock,
    HRTarget,
    Layer4Payload,
    PlanSession,
    ValidatorResult,
)
from plan_sessions_repo import (
    _PRIOR_WINDOW_DAYS_BY_TIER,
    allocate_plan_version_row,
    load_plan_sessions_by_version,
    load_prior_plan_session_window,
    persist_layer4_sessions,
)


_USER_ID = 42


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


def _make_plan_session(
    *,
    session_id: str = "ps-1",
    plan_version_id: int = 1,
    d: date = date(2026, 6, 1),
    session_index_in_day: int = 0,
    day_of_week: str = "Mon",
) -> PlanSession:
    return PlanSession(
        session_id=session_id,
        plan_version_id=plan_version_id,
        date=d,
        day_of_week=day_of_week,  # type: ignore[arg-type]
        session_index_in_day=session_index_in_day,
        time_of_day="morning",
        kind="cardio",
        discipline_id="D-run",
        discipline_name="Running",
        locale_id="home",
        locale_name="Home",
        duration_min=45,
        intensity_summary="easy",
        cardio_blocks=[
            CardioBlock(
                block_kind="main_set",
                duration_min=45,
                intensity_zone="Z2",
                intensity_target=HRTarget(hr_bpm_low=125, hr_bpm_high=140),
                instructions="Steady easy.",
            )
        ],
        session_notes="Easy aerobic.",
        coaching_intent="Aerobic base.",
        coaching_flags=[],
        is_ad_hoc=False,
    )


def _make_layer4_payload(
    *,
    plan_version_id: int = 1,
    sessions: list[PlanSession] | None = None,
) -> Layer4Payload:
    return Layer4Payload(
        user_id=_USER_ID,
        mode="plan_refresh",
        plan_version_id=plan_version_id,
        scope_start_date=date(2026, 6, 1),
        scope_end_date=date(2026, 6, 8),
        model_synthesizer="claude-sonnet-4-6",
        temperature=0.4,
        pattern="B",
        latency_ms_total=5000,
        input_tokens_total=3000,
        output_tokens_total=1500,
        llm_call_count=1,
        etl_version_set={"0A": "v7", "0B": "v7", "0C": "v7"},
        sessions=sessions if sessions is not None else [],
        phase_structure=None,
        seam_reviews=None,
        validator_results=[
            ValidatorResult(
                pass_index=0,
                accepted=True,
                rule_failures=[],
                retried_phase_names=[],
            )
        ],
        notable_observations=[],
    )


# ─── allocate_plan_version_row ──────────────────────────────────────────────


class TestAllocatePlanVersionRow:
    def test_happy_path_returning_id(self):
        conn = _FakeConn()
        conn.queue(row={"id": 42})

        result = allocate_plan_version_row(
            conn,
            _USER_ID,
            created_via="plan_create",
            scope_start_date=date(2026, 6, 1),
            scope_end_date=date(2026, 8, 24),
            pattern="A",
        )

        assert result == 42
        # INSERT happens with the right params + RETURNING id at the seam.
        assert len(conn.calls) == 1
        sql, params = conn.calls[0]
        assert "INSERT INTO plan_versions" in sql
        assert "RETURNING id" in sql
        # params: (user_id, created_via, scope_start, scope_end, pattern, notes)
        assert params == (
            _USER_ID,
            "plan_create",
            date(2026, 6, 1),
            date(2026, 8, 24),
            "A",
            None,  # notes is None → NULL
        )
        # Caller owns the transaction — repo does not commit.
        assert conn.committed is False

    def test_notes_serialized_to_json(self):
        conn = _FakeConn()
        conn.queue(row={"id": 17})

        allocate_plan_version_row(
            conn,
            _USER_ID,
            created_via="plan_refresh_t2",
            scope_start_date=date(2026, 6, 1),
            scope_end_date=date(2026, 6, 7),
            pattern="B",
            notes={"refresh_reason": "athlete-tired", "tier": "T2"},
        )

        sql, params = conn.calls[0]
        # Notes serialized as JSON string for JSONB column.
        assert params[-1] == json.dumps(
            {"refresh_reason": "athlete-tired", "tier": "T2"}
        )

    def test_rejects_unknown_created_via(self):
        conn = _FakeConn()
        with pytest.raises(ValueError) as exc:
            allocate_plan_version_row(
                conn,
                _USER_ID,
                created_via="bogus_mode",
                scope_start_date=date(2026, 6, 1),
                scope_end_date=date(2026, 6, 8),
                pattern="B",
            )
        assert "bogus_mode" in str(exc.value)
        # Fails BEFORE the SQL goes through.
        assert conn.calls == []

    def test_rejects_unknown_pattern(self):
        conn = _FakeConn()
        with pytest.raises(ValueError) as exc:
            allocate_plan_version_row(
                conn,
                _USER_ID,
                created_via="plan_create",
                scope_start_date=date(2026, 6, 1),
                scope_end_date=date(2026, 6, 8),
                pattern="C",  # invalid
            )
        assert "C" in str(exc.value)
        assert conn.calls == []

    def test_rejects_inverted_scope_dates(self):
        conn = _FakeConn()
        with pytest.raises(ValueError) as exc:
            allocate_plan_version_row(
                conn,
                _USER_ID,
                created_via="plan_create",
                scope_start_date=date(2026, 6, 8),
                scope_end_date=date(2026, 6, 1),  # end < start
                pattern="A",
            )
        assert "scope_end_date" in str(exc.value)
        assert conn.calls == []

    def test_raises_on_no_returning_row(self):
        conn = _FakeConn()
        # Don't queue a response — fetchone() returns None.
        with pytest.raises(RuntimeError) as exc:
            allocate_plan_version_row(
                conn,
                _USER_ID,
                created_via="plan_create",
                scope_start_date=date(2026, 6, 1),
                scope_end_date=date(2026, 8, 24),
                pattern="A",
            )
        assert "RETURNING id" in str(exc.value)


# ─── persist_layer4_sessions ────────────────────────────────────────────────


class TestPersistLayer4Sessions:
    def test_inserts_each_session_with_natural_key_columns(self):
        conn = _FakeConn()
        sessions = [
            _make_plan_session(
                session_id="ps-mon-am",
                plan_version_id=7,
                d=date(2026, 6, 1),
                session_index_in_day=0,
                day_of_week="Mon",
            ),
            _make_plan_session(
                session_id="ps-tue-am",
                plan_version_id=7,
                d=date(2026, 6, 2),
                session_index_in_day=0,
                day_of_week="Tue",
            ),
        ]
        payload = _make_layer4_payload(plan_version_id=7, sessions=sessions)

        persist_layer4_sessions(conn, payload)

        assert len(conn.calls) == 2
        for call, sess in zip(conn.calls, sessions):
            sql, params = call
            assert "INSERT INTO plan_sessions" in sql
            assert params[0] == sess.plan_version_id  # plan_version_id
            assert params[1] == _USER_ID  # user_id (from payload)
            assert params[2] == sess.session_id
            assert params[3] == sess.date
            assert params[4] == sess.session_index_in_day
            # payload_json is the full PlanSession dump.
            assert isinstance(params[5], str)
            parsed = json.loads(params[5])
            assert parsed["session_id"] == sess.session_id
            assert parsed["plan_version_id"] == sess.plan_version_id

        # Caller owns the transaction — repo does not commit.
        assert conn.committed is False

    def test_stale_session_plan_version_id_forced_to_payload_id(self):
        """Regression (prod pv=45): a per-block cached payload that escaped the
        §9.4 cache rebind leaked an OLDER plan's id (pv=39) into a NEWER plan's
        sessions, colliding with the older plan's rows on the natural-key UNIQUE
        -> UniqueViolation that failed generation at persist. The persist
        boundary must force the natural-key column AND the stored payload_json
        to the payload's plan_version_id, so a stale per-session id can never
        reach the table."""
        conn = _FakeConn()
        # Sessions still carry the STALE id 39; the plan being persisted is 45.
        sessions = [
            _make_plan_session(
                session_id="ps-stale",
                plan_version_id=39,
                d=date(2026, 6, 27),
                session_index_in_day=0,
                day_of_week="Sat",
            ),
        ]
        payload = _make_layer4_payload(plan_version_id=45, sessions=sessions)

        persist_layer4_sessions(conn, payload)

        sql, params = conn.calls[0]
        # Natural-key column is the PAYLOAD's id, not the session's stale 39.
        assert params[0] == 45
        # ...and the stored JSON blob is re-stamped consistently.
        parsed = json.loads(params[5])
        assert parsed["plan_version_id"] == 45

    def test_empty_sessions_is_noop(self):
        conn = _FakeConn()
        payload = _make_layer4_payload(plan_version_id=7, sessions=[])

        persist_layer4_sessions(conn, payload)

        assert conn.calls == []
        assert conn.committed is False

    def test_user_id_from_payload_threads_to_every_row(self):
        """user_id is denormalized from Layer4Payload, not from each PlanSession
        (PlanSession doesn't carry user_id). All rows share the payload's
        user_id even if sessions span multiple dates."""
        conn = _FakeConn()
        sessions = [
            _make_plan_session(
                session_id=f"ps-{i}",
                plan_version_id=9,
                d=date(2026, 6, 1 + i),
                day_of_week=["Mon", "Tue", "Wed"][i],
            )
            for i in range(3)
        ]
        payload = _make_layer4_payload(plan_version_id=9, sessions=sessions)

        persist_layer4_sessions(conn, payload)

        for call in conn.calls:
            _, params = call
            assert params[1] == _USER_ID


# ─── load_plan_sessions_by_version ──────────────────────────────────────────


class TestLoadPlanSessionsByVersion:
    def test_round_trips_payload_json_to_plan_session(self):
        conn = _FakeConn()
        sess = _make_plan_session(plan_version_id=3, d=date(2026, 6, 1))
        # psycopg2 path: JSONB hydrated as dict directly.
        conn.queue(rows=[{"payload_json": json.loads(sess.model_dump_json())}])

        result = load_plan_sessions_by_version(conn, plan_version_id=3)

        assert len(result) == 1
        assert isinstance(result[0], PlanSession)
        assert result[0].session_id == sess.session_id
        assert result[0].plan_version_id == 3

        # SELECT against plan_version_id with ORDER BY (date, slot).
        sql, params = conn.calls[0]
        assert "FROM plan_sessions" in sql
        assert "plan_version_id = ?" in sql
        assert "ORDER BY date, session_index_in_day" in sql
        assert params == (3,)

    def test_hydrates_payload_from_json_string_path(self):
        """SQLite shim returns JSONB columns as JSON strings; the repo
        tolerates both psycopg2 (dict) + shim (str) shapes."""
        conn = _FakeConn()
        sess = _make_plan_session(plan_version_id=3)
        conn.queue(rows=[{"payload_json": sess.model_dump_json()}])

        result = load_plan_sessions_by_version(conn, plan_version_id=3)

        assert len(result) == 1
        assert result[0].session_id == sess.session_id

    def test_empty_rows_returns_empty_list(self):
        conn = _FakeConn()
        conn.queue(rows=[])

        result = load_plan_sessions_by_version(conn, plan_version_id=99)
        assert result == []


# ─── load_prior_plan_session_window ─────────────────────────────────────────


class TestLoadPriorPlanSessionWindow:
    def test_tier_t1_default_2_day_lookback(self):
        conn = _FakeConn()
        conn.queue(rows=[])

        load_prior_plan_session_window(
            conn,
            _USER_ID,
            today=date(2026, 6, 10),
            tier="T1",
        )

        # T1 → 2-day window: [today-2, today-1] = [June 8, June 9]
        sql, params = conn.calls[0]
        assert params == (_USER_ID, date(2026, 6, 8), date(2026, 6, 9))

    def test_tier_t2_default_7_day_lookback(self):
        conn = _FakeConn()
        conn.queue(rows=[])

        load_prior_plan_session_window(
            conn,
            _USER_ID,
            today=date(2026, 6, 10),
            tier="T2",
        )

        sql, params = conn.calls[0]
        assert params == (_USER_ID, date(2026, 6, 3), date(2026, 6, 9))

    def test_tier_t3_default_28_day_lookback(self):
        conn = _FakeConn()
        conn.queue(rows=[])

        load_prior_plan_session_window(
            conn,
            _USER_ID,
            today=date(2026, 6, 28),
            tier="T3",
        )

        sql, params = conn.calls[0]
        assert params == (_USER_ID, date(2026, 5, 31), date(2026, 6, 27))

    def test_days_kwarg_overrides_tier_default(self):
        """When `days` is passed explicitly, the tier-tied default is ignored.
        (Caller picks a custom lookback — e.g., race_week_brief wanting
        a 6-week window regardless of any tier.)"""
        conn = _FakeConn()
        conn.queue(rows=[])

        load_prior_plan_session_window(
            conn,
            _USER_ID,
            today=date(2026, 6, 10),
            tier="T1",
            days=42,  # override — 6 weeks
        )

        sql, params = conn.calls[0]
        # 42-day window: [today-42, today-1]
        assert params == (_USER_ID, date(2026, 4, 29), date(2026, 6, 9))

    def test_raises_when_both_tier_and_days_none(self):
        conn = _FakeConn()
        with pytest.raises(ValueError) as exc:
            load_prior_plan_session_window(
                conn,
                _USER_ID,
                today=date(2026, 6, 10),
            )
        assert "tier" in str(exc.value) or "days" in str(exc.value)
        assert conn.calls == []

    def test_raises_when_days_non_positive(self):
        conn = _FakeConn()
        with pytest.raises(ValueError) as exc:
            load_prior_plan_session_window(
                conn,
                _USER_ID,
                today=date(2026, 6, 10),
                days=0,
            )
        assert "days" in str(exc.value)
        assert conn.calls == []

    def test_per_day_version_pointer_resolver_distinct_on(self):
        """SQL applies `DISTINCT ON (date, session_index_in_day)` ordered
        by `plan_version_id DESC` per D-64 §6.3 — newest version wins per
        slot when multiple plan_version_id rows cover the same slot."""
        conn = _FakeConn()
        conn.queue(rows=[])

        load_prior_plan_session_window(
            conn,
            _USER_ID,
            today=date(2026, 6, 10),
            tier="T2",
        )

        sql, _ = conn.calls[0]
        assert "DISTINCT ON (date, session_index_in_day)" in sql
        assert "plan_version_id DESC" in sql

    def test_returns_empty_when_no_prior_sessions(self):
        """First plan_create — athlete has no prior versions; resolver
        returns empty. Caller (route handler) decides whether non-empty
        is required (Layer 4 plan_refresh's _validate_inputs enforces)."""
        conn = _FakeConn()
        conn.queue(rows=[])

        result = load_prior_plan_session_window(
            conn,
            _USER_ID,
            today=date(2026, 6, 10),
            tier="T2",
        )
        assert result == []

    def test_hydrates_plan_session_from_rows(self):
        conn = _FakeConn()
        sess = _make_plan_session(plan_version_id=5, d=date(2026, 6, 8))
        conn.queue(
            rows=[{"payload_json": json.loads(sess.model_dump_json())}]
        )

        result = load_prior_plan_session_window(
            conn,
            _USER_ID,
            today=date(2026, 6, 10),
            tier="T1",
        )

        assert len(result) == 1
        assert isinstance(result[0], PlanSession)
        assert result[0].session_id == sess.session_id


class TestTierDefaultMapping:
    def test_mapping_matches_refresh_scope_shape(self):
        """Sanity-pin the tier-tied default mapping. If the policy changes,
        this test surfaces the diff."""
        assert _PRIOR_WINDOW_DAYS_BY_TIER == {"T1": 2, "T2": 7, "T3": 28}
