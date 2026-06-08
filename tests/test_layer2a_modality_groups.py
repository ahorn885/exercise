"""Tests for X1b.2 — Layer 2A modality-group pool/redistribute.

Per `Modality_Group_Spec_v1.md` §5.1 algorithm + §13 test scenarios.

Uses the same `_FakeConn` pattern as `tests/test_layer2a.py`. Each test
queues TWO responses:
  1. The disciplines SELECT result (bridge rows for the sport)
  2. The `discipline_modality_membership` SELECT result

`weekly_total_hours_by_phase` query falls through to empty.
"""

from __future__ import annotations

import pytest

from layer4 import InMemoryCacheBackend  # noqa: F401 — break circular import

from layer2a import q_layer2a_discipline_classifier_payload


# ─── Fakes ────────────────────────────────────────────────────────────────


class _FakeRow(dict):
    def __getitem__(self, key):
        if isinstance(key, int):
            return list(self.values())[key]
        return super().__getitem__(key)


class _FakeCursor:
    def __init__(self, rows=None):
        self._rows = rows or []

    def fetchall(self):
        return [_FakeRow(r) for r in self._rows]

    def fetchone(self):
        return _FakeRow(self._rows[0]) if self._rows else None


class _FakeConn:
    def __init__(self):
        self.calls: list[tuple[str, tuple]] = []
        self.responses: list[list] = []

    def queue(self, rows):
        self.responses.append(rows)

    def execute(self, sql, params=()):
        self.calls.append((sql, params))
        rows = self.responses.pop(0) if self.responses else []
        return _FakeCursor(rows=rows)

    def commit(self):
        pass


# ─── Row helpers ──────────────────────────────────────────────────────────


def _disc_row(disc_id: str, name: str, low: float, high: float) -> dict:
    """Build a Layer 2A SELECT result row mirroring `_load_disciplines` shape."""
    return {
        "discipline_id": disc_id,
        "discipline_name": name,
        "applicability": "INCLUDED",
        "role": "Primary",
        "endurance_profile": None,
        "primary_movement": None,
        "race_time_pct_low": low,
        "race_time_pct_high": high,
        "sport_specific_context": None,
        "phase_load_text": None,
        "base_pct_low": None, "base_pct_high": None,
        "build_pct_low": None, "build_pct_high": None,
        "peak_pct_low": None, "peak_pct_high": None,
        "taper_pct_low": None, "taper_pct_high": None,
        "pla_role": None,
        "notes_conditions": None,
        "gap_type": None, "gap_notes": None,
        "multi_substitute_candidate": None,
    }


def _mem(discipline_id: str, group_id: str) -> dict:
    return {"discipline_id": discipline_id, "group_id": group_id}


_ETL = {"0A": "v1.5.0", "0B": "v1.5.0", "0C": "v1.5.0"}


# ─── §13 scenarios ────────────────────────────────────────────────────────


class TestNoMembership:
    """Empty membership table (pre-v1.5.0 state) = behavior identical to pre-X1b.2."""

    def test_no_membership_no_allocations(self):
        conn = _FakeConn()
        conn.queue([
            _disc_row("D-001", "Trail Running", 15, 25),
            _disc_row("D-008", "Mountain Biking", 10, 20),
        ])
        conn.queue([])  # empty membership

        payload = q_layer2a_discipline_classifier_payload(
            conn, "Adventure Racing", etl_version_set=_ETL,
        )

        assert payload.modality_group_allocations == []
        # Old behavior intact: TR 20 / MTB 15 → normalize to 20/35, 15/35
        weights = {d.discipline_id: d.load_weight.value for d in payload.disciplines}
        assert abs(weights["D-001"] - (20 / 35)) < 0.001
        assert abs(weights["D-008"] - (15 / 35)) < 0.001


class TestSingletonGroup:
    """One included member per group = no pooling, no allocation diagnostic."""

    def test_singleton_per_group_no_allocation(self):
        conn = _FakeConn()
        conn.queue([
            _disc_row("D-001", "Trail Running", 20, 30),       # → foot
            _disc_row("D-008", "Mountain Biking", 35, 55),     # → bike_offroad
        ])
        conn.queue([
            _mem("D-001", "foot"),
            _mem("D-008", "bike_offroad"),
        ])

        payload = q_layer2a_discipline_classifier_payload(
            conn, "Adventure Racing", etl_version_set=_ETL,
        )

        # Each group has 1 included member → singletons. No allocations emitted.
        assert payload.modality_group_allocations == []


class TestMultiMemberGroupBridgeOnly:
    """Two members in same group, no race/athlete signal → bridge midpoints preserved."""

    def test_foot_group_two_members_bridge(self):
        conn = _FakeConn()
        # TR midpoint 25, Trekking midpoint 25 — both in `foot` group
        conn.queue([
            _disc_row("D-001", "Trail Running", 20, 30),
            _disc_row("D-003", "Hiking", 20, 30),
        ])
        conn.queue([
            _mem("D-001", "foot"),
            _mem("D-003", "foot"),
        ])

        payload = q_layer2a_discipline_classifier_payload(
            conn, "Adventure Racing", etl_version_set=_ETL,
        )

        # One allocation diagnostic for the foot group
        assert len(payload.modality_group_allocations) == 1
        alloc = payload.modality_group_allocations[0]
        assert alloc.group_id == "foot"
        assert sorted(alloc.members) == ["D-001", "D-003"]
        assert alloc.pool_race == 0.0
        assert alloc.pool_athlete == 0.0
        assert alloc.pool_base == 50.0  # 25 + 25
        # Both members keep their bridge share
        assert alloc.per_member_final["D-001"] == 25.0
        assert alloc.per_member_final["D-003"] == 25.0


class TestRaceOverridePerMember:
    """Race tags both members of a group with explicit percentages."""

    def test_race_per_member_wins(self):
        conn = _FakeConn()
        conn.queue([
            _disc_row("D-001", "Trail Running", 15, 25),   # midpoint 20
            _disc_row("D-003", "Hiking", 10, 20),          # midpoint 15
        ])
        conn.queue([
            _mem("D-001", "foot"),
            _mem("D-003", "foot"),
        ])

        payload = q_layer2a_discipline_classifier_payload(
            conn, "Adventure Racing",
            race_discipline_overrides={"D-001": 8, "D-003": 27},
            etl_version_set=_ETL,
        )

        alloc = payload.modality_group_allocations[0]
        assert alloc.pool_race == 35.0
        assert alloc.per_member_final["D-001"] == 8.0
        assert alloc.per_member_final["D-003"] == 27.0
        # Source stamped as race_override
        sources = {d.discipline_id: d.load_weight.source for d in payload.disciplines}
        assert sources["D-001"] == "race_override"
        assert sources["D-003"] == "race_override"


class TestRedirectSemantics:
    """Race tags D-010 (kayak, not in included set); athlete only owns D-009
    (packraft). Per §5.3 REDIRECT, the race tag flows to D-009 + a
    `craft_substitution_via_group` flag fires."""

    def test_kayak_tag_redirects_to_packraft(self):
        conn = _FakeConn()
        conn.queue([
            _disc_row("D-009", "Packrafting", 5, 15),     # midpoint 10; included
            _disc_row("D-008", "Mountain Biking", 35, 55),
        ])
        # D-009 + D-010 both in paddle_flatwater, but D-010 NOT in included set
        conn.queue([
            _mem("D-009", "paddle_flatwater"),
            _mem("D-010", "paddle_flatwater"),
            _mem("D-008", "bike_offroad"),
        ])

        payload = q_layer2a_discipline_classifier_payload(
            conn, "Adventure Racing",
            race_discipline_overrides={"D-010": 20},  # tag kayak (not included)
            etl_version_set=_ETL,
        )

        # D-009 should now carry the redirected 20% race weight
        weights_raw = {d.discipline_id: d.load_weight for d in payload.disciplines}
        assert weights_raw["D-009"].source == "race_override"
        # No pool diagnostic for paddle_flatwater (only 1 included member); the
        # redirect lives in the singleton-handling tail.
        # But sometimes a singleton group still gets a diagnostic if there's a
        # group-pool diagnostic; check we did not crash.
        # The post-normalize weight should reflect 20 redirected to D-009.


class TestAthleteOverrideInGroup:
    """Athlete weighting on a group member overrides bridge default."""

    def test_athlete_in_group(self):
        conn = _FakeConn()
        conn.queue([
            _disc_row("D-001", "Trail Running", 15, 25),
            _disc_row("D-003", "Hiking", 10, 20),
        ])
        conn.queue([
            _mem("D-001", "foot"),
            _mem("D-003", "foot"),
        ])

        payload = q_layer2a_discipline_classifier_payload(
            conn, "Adventure Racing",
            athlete_discipline_overrides={
                "D-001": {"weight": 60},
                "D-003": {"weight": 40},
            },
            etl_version_set=_ETL,
        )

        alloc = payload.modality_group_allocations[0]
        assert alloc.per_member_final["D-001"] == 60.0
        assert alloc.per_member_final["D-003"] == 40.0
        sources = {d.discipline_id: d.load_weight.source for d in payload.disciplines}
        assert sources["D-001"] == "athlete_override"
        assert sources["D-003"] == "athlete_override"


class TestPrecedenceRaceWinsOverAthlete:
    """Race override on one member, athlete override on another in same group.
    Both win per-member; precedence applies only when both signals exist on
    the SAME discipline."""

    def test_per_member_precedence(self):
        conn = _FakeConn()
        conn.queue([
            _disc_row("D-001", "Trail Running", 15, 25),
            _disc_row("D-003", "Hiking", 10, 20),
        ])
        conn.queue([
            _mem("D-001", "foot"),
            _mem("D-003", "foot"),
        ])

        payload = q_layer2a_discipline_classifier_payload(
            conn, "Adventure Racing",
            race_discipline_overrides={"D-001": 30},
            athlete_discipline_overrides={
                "D-001": {"weight": 999},  # ignored — race wins for D-001
                "D-003": {"weight": 45},   # used — no race tag for D-003
            },
            etl_version_set=_ETL,
        )

        sources = {d.discipline_id: d.load_weight.source for d in payload.disciplines}
        assert sources["D-001"] == "race_override"
        assert sources["D-003"] == "athlete_override"

        alloc = payload.modality_group_allocations[0]
        assert alloc.per_member_final["D-001"] == 30.0
        assert alloc.per_member_final["D-003"] == 45.0
