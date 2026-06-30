"""Tests for `athlete_crafts_repo.py` (Track 2 slice 2c.2b, #540) + the two
guards that keep craft capture and the craft-substitution path in lockstep.
Uses a `_FakeConn` (no real DB), mirroring test_athlete_discipline_weighting_repo.
"""
from __future__ import annotations

import pytest
from pydantic import ValidationError

from athlete import BIKE_TYPES, PADDLE_CRAFT_TYPES
from athlete_crafts_repo import (
    CraftSelectionError,
    get_athlete_crafts,
    load_craft_catalog,
    replace_athlete_crafts,
)
from layer4.context import CyclingBaseline


class _FakeRow(dict):
    def __getitem__(self, key):
        if isinstance(key, int):
            return list(self.values())[key]
        return super().__getitem__(key)


class _FakeCursor:
    def __init__(self, rows):
        self._rows = rows

    def fetchall(self):
        return [_FakeRow(r) for r in self._rows]

    def fetchone(self):
        return _FakeRow(self._rows[0]) if self._rows else None


class _FakeConn:
    def __init__(self):
        self.calls: list[tuple[str, tuple]] = []
        self.responses: list[list] = []

    def queue_response(self, rows=None):
        self.responses.append(rows or [])

    def execute(self, sql, params=()):
        self.calls.append((sql, params))
        rows = self.responses.pop(0) if self.responses else []
        return _FakeCursor(rows)


# ─── load_craft_catalog ──────────────────────────────────────────────────────

class TestCatalog:
    def test_groups_by_family_with_labels(self):
        cat = load_craft_catalog()
        assert [c["slug"] for c in cat["cycling"]] == list(BIKE_TYPES)
        assert [c["slug"] for c in cat["paddling"]] == list(PADDLE_CRAFT_TYPES)
        assert all(c["label"] for c in cat["cycling"] + cat["paddling"])


# ─── get_athlete_crafts ──────────────────────────────────────────────────────

class TestGet:
    def test_splits_both_families(self):
        conn = _FakeConn()
        conn.queue_response(rows=[{"bike_types_available": "mountain_bike,gravel_bike"}])
        conn.queue_response(rows=[{"paddle_craft_types": "packraft"}])
        assert get_athlete_crafts(conn, 1) == {
            "bike_types": ["mountain_bike", "gravel_bike"],
            "paddle_crafts": ["packraft"],
        }

    def test_empty_when_rows_absent_or_null(self):
        conn = _FakeConn()
        conn.queue_response(rows=[])              # no cycling row
        conn.queue_response(rows=[{"paddle_craft_types": None}])
        assert get_athlete_crafts(conn, 1) == {"bike_types": [], "paddle_crafts": []}


# ─── replace_athlete_crafts ──────────────────────────────────────────────────

class TestReplace:
    def test_valid_upserts_both_families_in_enum_order(self):
        conn = _FakeConn()
        # submitted out of order + duplicated → stored in enum order, deduped.
        replace_athlete_crafts(
            conn, 1,
            bike_types=["gravel_bike", "road_bike", "road_bike"],
            paddle_crafts=["packraft"],
        )
        # First two calls are the discipline-baseline upserts (the craft contract).
        baseline_calls = conn.calls[:2]
        assert all("ON CONFLICT (user_id)" in c[0] for c in baseline_calls)
        assert baseline_calls[0][1] == (1, "road_bike,gravel_bike")   # enum order
        assert baseline_calls[1][1] == (1, "packraft")
        # #884 slice 4 — the same write forward-syncs athlete_gear (bike/paddle
        # kinds only): a scoped DELETE then one INSERT per owned craft, so the
        # feasibility cascade (which reads athlete_gear as of slice 4a) never sees
        # a stale store between a craft edit and slice 6.
        gear_calls = conn.calls[2:]
        assert any(
            "DELETE FROM athlete_gear" in c[0] and "group_kind IN" in c[0]
            for c in gear_calls
        )
        inserted = {
            c[1][1] for c in gear_calls if "INSERT INTO athlete_gear" in c[0]
        }
        assert inserted == {"road_bike", "gravel_bike", "packraft"}

    def test_access_by_slug_syncs_per_craft_access_default_own(self):
        # #884 slice 6a — the unified "Your gear" surface passes per-craft access;
        # the baseline CSVs still carry the full available set (own ∪ access),
        # athlete_gear carries the refinement. An unmapped slug defaults to 'own'.
        conn = _FakeConn()
        replace_athlete_crafts(
            conn, 1,
            bike_types=["road_bike", "gravel_bike"],
            paddle_crafts=["packraft"],
            access_by_slug={"road_bike": "access", "packraft": "own"},
        )
        # Baselines unchanged — the full available set regardless of access.
        assert conn.calls[0][1] == (1, "road_bike,gravel_bike")
        assert conn.calls[1][1] == (1, "packraft")
        # athlete_gear INSERTs carry the per-craft access (param index 3);
        # gravel_bike was unmapped → 'own'.
        gear_inserts = {
            c[1][1]: c[1][3]
            for c in conn.calls if "INSERT INTO athlete_gear" in c[0]
        }
        assert gear_inserts == {
            "road_bike": "access", "gravel_bike": "own", "packraft": "own",
        }

    def test_empty_lists_clear_each_family(self):
        conn = _FakeConn()
        replace_athlete_crafts(conn, 1, bike_types=[], paddle_crafts=[])
        assert conn.calls[0][1] == (1, "")
        assert conn.calls[1][1] == (1, "")

    def test_unknown_bike_slug_raises_and_writes_nothing(self):
        conn = _FakeConn()
        with pytest.raises(CraftSelectionError):
            replace_athlete_crafts(conn, 1, bike_types=["tandem"], paddle_crafts=[])
        assert conn.calls == []  # validation precedes any write

    def test_unknown_paddle_slug_raises_and_writes_nothing(self):
        conn = _FakeConn()
        with pytest.raises(CraftSelectionError):
            replace_athlete_crafts(conn, 1, bike_types=[], paddle_crafts=["surfski"])
        assert conn.calls == []


# ─── closed-enum guard (the Literal tightening) ──────────────────────────────

class TestModelGuard:
    def test_cycling_baseline_accepts_canonical_slugs(self):
        b = CyclingBaseline(bike_types_available=list(BIKE_TYPES))
        assert b.bike_types_available == list(BIKE_TYPES)

    def test_cycling_baseline_rejects_unknown_bike_type(self):
        with pytest.raises(ValidationError):
            CyclingBaseline(bike_types_available=["tandem"])


# ─── recurrence guard: capture enums cover every craft-alias key ─────────────
# Seeded from the live craft_discipline_aliases active set. The craft-substitution
# lookup is exact-match on these snake_case keys, so a capture slug that drifts
# from an alias key (or vice versa) silently breaks narrowing — this fails loudly
# instead (the craft-domain analogue of V4c's equipment-token coverage guard).
# cycling_trainer retired as a craft (WS-I, #586) — it is equipment, not a mobile
# vessel; its alias rows superseded in etl/migrations/layer0/0004_*.
# tt_bike / sup / raft added as crafts (#622) — relocated out of the equipment
# vocabulary; their alias rows land in etl/migrations/layer0/0007_*.
_ALIAS_CRAFT_NAMES = {
    "kayak", "canoe", "packraft", "sup", "raft",
    "road_bike", "gravel_bike", "mountain_bike", "tt_bike",
}


def test_capture_enums_cover_every_craft_alias_key():
    assert _ALIAS_CRAFT_NAMES <= (set(BIKE_TYPES) | set(PADDLE_CRAFT_TYPES))
