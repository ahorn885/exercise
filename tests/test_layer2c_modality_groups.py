"""Tests for X1b.3 — Layer 2C `craft_substitution_via_group` flag.

Per `Modality_Group_Spec_v1.md` §6 + §13 scenario 7.

`_FakeConn` queues four ordered SELECTs per call:
  1. toggle defs (gear)
  2. skill-capability toggles (pattern-matched into its own queue)
  3. discipline info
  4. exercises
  5. modality membership (pattern-matched into its own queue)

Tests that don't exercise membership just don't queue any membership
rows; the pattern-match returns `[]` and the flag emitter no-ops
(pre-v1.5.0 substrate behavior).
"""

from __future__ import annotations

from typing import Any

import pytest

from layer4 import InMemoryCacheBackend  # noqa: F401 — break circular import

from layer2c import q_layer2c_equipment_mapper_payload


# ─── Fakes ────────────────────────────────────────────────────────────────


class _FakeRow(dict):
    def __getitem__(self, key):
        if isinstance(key, int):
            return list(self.values())[key]
        return super().__getitem__(key)


class _FakeCursor:
    def __init__(self, rows: list[dict[str, Any]]):
        self._rows = rows

    def fetchone(self):
        return _FakeRow(self._rows[0]) if self._rows else None

    def fetchall(self):
        return [_FakeRow(r) for r in self._rows]


class _FakeConn:
    def __init__(self):
        self.calls: list[tuple[str, tuple]] = []
        self.batches: list[list[dict[str, Any]]] = []
        self._skill_cap_batches: list[list[dict[str, Any]]] = []
        self._membership_batches: list[list[dict[str, Any]]] = []

    def queue(self, *rows: dict[str, Any]) -> None:
        self.batches.append(list(rows))

    def queue_skill_capability_toggles(self, *rows: dict[str, Any]) -> None:
        self._skill_cap_batches.append(list(rows))

    def queue_modality_membership(self, *rows: dict[str, Any]) -> None:
        self._membership_batches.append(list(rows))

    def execute(self, sql, params=()):
        self.calls.append((sql, params))
        if "skill_capability_toggles" in sql:
            rows = (
                self._skill_cap_batches.pop(0)
                if self._skill_cap_batches
                else []
            )
            return _FakeCursor(rows)
        if "discipline_modality_membership" in sql:
            rows = (
                self._membership_batches.pop(0)
                if self._membership_batches
                else []
            )
            return _FakeCursor(rows)
        rows = self.batches.pop(0) if self.batches else []
        return _FakeCursor(rows)

    def commit(self):
        pass


_ETL = {"0A": "v1.5.0", "0B": "v1.5.0", "0C": "v1.5.0"}


# ─── Row helpers ──────────────────────────────────────────────────────────


def _sdb(disc_id: str, name: str, sport: str = "Adventure Racing") -> dict:
    return {
        "discipline_id": disc_id,
        "discipline_name": name,
        "exercise_db_sport": sport,
    }


def _ex(
    exercise_id: str,
    exercise_name: str,
    discipline_id: str,
    discipline_name: str,
    equipment_required: list[str],
    *,
    priority: str = "High",
) -> dict:
    """Build a row matching the shape `_load_exercises` SELECTs."""
    return {
        "exercise_id": exercise_id,
        "exercise_name": exercise_name,
        "exercise_type": "Cardio",
        "sport_name": "Adventure Racing",
        "sport_relevance_note": "",
        "priority": priority,
        "equipment_required": equipment_required,
        "equipment_substitutes_structured": None,
        "physical_proxies": None,
        "terrain_required": None,
        "contraindicated_parts": None,
        "contraindicated_conditions": None,
        "movement_patterns": [],
        "discipline_id": discipline_id,
        "discipline_name": discipline_name,
        "exercise_db_sport": "Adventure Racing",
    }


def _mem(discipline_id: str, group_id: str) -> dict:
    return {"discipline_id": discipline_id, "group_id": group_id}


def _call(conn, included_ids: list[str], pool: list[str]):
    return q_layer2c_equipment_mapper_payload(
        conn,
        "loc-home",
        pool,
        ["loc-home"],
        {},
        included_ids,
        etl_version_set=_ETL,
    )


# ─── Scenarios ────────────────────────────────────────────────────────────


class TestNoMembership:
    """Pre-v1.5.0 substrate (empty membership) = no new flags."""

    def test_no_membership_no_substitution_flag(self):
        conn = _FakeConn()
        conn.queue()  # toggle defs (empty)
        conn.queue(_sdb("D-010", "Kayaking"))  # discipline info
        conn.queue(_ex("EX-A", "Kayak interval", "D-010", "Kayaking", ["Kayak"]))

        payload = _call(conn, ["D-010"], pool=[])  # locale has nothing

        flags = [
            f for f in payload.coaching_flags
            if f.flag_type == "craft_substitution_via_group"
        ]
        assert flags == []


class TestSubstitutionCandidateSurfaced:
    """§13 scenario 7 — locale doesn't have kayak gear, has packraft.
    D-010 (kayak) coverage 0%, D-009 (packraft) coverage 100%. Same
    paddle_flatwater group → one flag with both ids."""

    def test_kayak_low_packraft_high_emits_flag(self):
        conn = _FakeConn()
        conn.queue()  # toggle defs
        conn.queue(
            _sdb("D-010", "Kayaking"),
            _sdb("D-009", "Packrafting"),
        )
        conn.queue(
            _ex("EX-K", "Kayak interval", "D-010", "Kayaking", ["Kayak"]),
            _ex("EX-P", "Packraft session", "D-009", "Packrafting", ["Packraft"]),
        )
        conn.queue_modality_membership(
            _mem("D-010", "paddle_flatwater"),
            _mem("D-009", "paddle_flatwater"),
        )

        payload = _call(conn, ["D-010", "D-009"], pool=["Packraft"])

        # D-010 is in the included set but locale has no kayak → coverage 0
        # D-009 has Packraft in the pool → coverage 100
        coverage_by_id = {c.discipline_id: c for c in payload.discipline_coverage}
        assert coverage_by_id["D-010"].coverage_pct == 0.0
        assert coverage_by_id["D-009"].coverage_pct == 1.0

        flags = [
            f for f in payload.coaching_flags
            if f.flag_type == "craft_substitution_via_group"
        ]
        assert len(flags) == 1
        f = flags[0]
        assert f.discipline_id == "D-010"
        assert f.discipline_name == "Kayaking"
        assert f.metadata["candidate_discipline_id"] == "D-009"
        assert f.metadata["candidate_discipline_name"] == "Packrafting"
        assert f.metadata["group_id"] == "paddle_flatwater"
        assert f.metadata["target_coverage_pct"] == 0.0
        assert f.metadata["candidate_coverage_pct"] == 1.0
        assert "Kayaking" in f.message and "Packrafting" in f.message


class TestBothLowNoCandidate:
    """Both group members low coverage → no candidate, no flag."""

    def test_both_low_no_flag(self):
        conn = _FakeConn()
        conn.queue()
        conn.queue(
            _sdb("D-010", "Kayaking"),
            _sdb("D-009", "Packrafting"),
        )
        conn.queue(
            _ex("EX-K", "Kayak interval", "D-010", "Kayaking", ["Kayak"]),
            _ex("EX-P", "Packraft session", "D-009", "Packrafting", ["Packraft"]),
        )
        conn.queue_modality_membership(
            _mem("D-010", "paddle_flatwater"),
            _mem("D-009", "paddle_flatwater"),
        )

        payload = _call(conn, ["D-010", "D-009"], pool=[])  # nothing in pool

        flags = [
            f for f in payload.coaching_flags
            if f.flag_type == "craft_substitution_via_group"
        ]
        assert flags == []


class TestDifferentGroupsNoFlag:
    """Low-coverage target + high-coverage candidate but different groups → no flag."""

    def test_cross_group_no_flag(self):
        conn = _FakeConn()
        conn.queue()
        conn.queue(
            _sdb("D-010", "Kayaking"),
            _sdb("D-001", "Trail Running"),
        )
        conn.queue(
            _ex("EX-K", "Kayak interval", "D-010", "Kayaking", ["Kayak"]),
            _ex("EX-R", "Trail run", "D-001", "Trail Running", []),  # bodyweight
        )
        conn.queue_modality_membership(
            _mem("D-010", "paddle_flatwater"),
            _mem("D-001", "foot"),
        )

        payload = _call(conn, ["D-010", "D-001"], pool=[])

        # D-001 has empty equipment_required → tier 1 (bodyweight) → coverage 1.0
        # D-010 has Kayak missing → coverage 0
        coverage_by_id = {c.discipline_id: c for c in payload.discipline_coverage}
        assert coverage_by_id["D-001"].coverage_pct == 1.0
        assert coverage_by_id["D-010"].coverage_pct == 0.0

        flags = [
            f for f in payload.coaching_flags
            if f.flag_type == "craft_substitution_via_group"
        ]
        assert flags == []


class TestMultipleCandidates:
    """Low target + two high candidates in same group → two flags, sorted by candidate id."""

    def test_two_candidates_two_flags(self):
        conn = _FakeConn()
        conn.queue()
        conn.queue(
            _sdb("D-010", "Kayaking"),
            _sdb("D-009", "Packrafting"),
            _sdb("D-011", "Canoeing"),
        )
        conn.queue(
            _ex("EX-K", "Kayak interval", "D-010", "Kayaking", ["Kayak"]),
            _ex("EX-P", "Packraft session", "D-009", "Packrafting", ["Packraft"]),
            _ex("EX-C", "Canoe session", "D-011", "Canoeing", ["Canoe"]),
        )
        conn.queue_modality_membership(
            _mem("D-010", "paddle_flatwater"),
            _mem("D-009", "paddle_flatwater"),
            _mem("D-011", "paddle_flatwater"),
        )

        payload = _call(
            conn, ["D-010", "D-009", "D-011"], pool=["Packraft", "Canoe"]
        )

        flags = [
            f for f in payload.coaching_flags
            if f.flag_type == "craft_substitution_via_group"
        ]
        # D-010 → both D-009 and D-011 as candidates; sorted by candidate id
        assert len(flags) == 2
        assert [f.metadata["candidate_discipline_id"] for f in flags] == [
            "D-009", "D-011",
        ]
        assert all(f.discipline_id == "D-010" for f in flags)


class TestTargetNotInMembership:
    """Target discipline has no membership row → no flag (legit per spec §4)."""

    def test_target_outside_membership(self):
        conn = _FakeConn()
        conn.queue()
        conn.queue(
            _sdb("D-099", "Hypothetical"),
            _sdb("D-009", "Packrafting"),
        )
        conn.queue(
            _ex("EX-H", "Some session", "D-099", "Hypothetical", ["MissingGear"]),
            _ex("EX-P", "Packraft session", "D-009", "Packrafting", ["Packraft"]),
        )
        # D-099 NOT in membership map
        conn.queue_modality_membership(
            _mem("D-009", "paddle_flatwater"),
        )

        payload = _call(conn, ["D-099", "D-009"], pool=["Packraft"])

        flags = [
            f for f in payload.coaching_flags
            if f.flag_type == "craft_substitution_via_group"
        ]
        assert flags == []
