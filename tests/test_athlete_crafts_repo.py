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
        assert len(conn.calls) == 2
        assert all("ON CONFLICT (user_id)" in c[0] for c in conn.calls)
        assert conn.calls[0][1] == (1, "road_bike,gravel_bike")   # enum order
        assert conn.calls[1][1] == (1, "packraft")

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
# Seeded from the live v1.6.7 layer0.craft_discipline_aliases rows. The
# craft-substitution lookup is exact-match on these snake_case keys, so a
# capture slug that drifts from an alias key (or vice versa) silently breaks
# narrowing — this fails loudly instead (the craft-domain analogue of V4c's
# equipment-token coverage guard).
_ALIAS_CRAFT_NAMES = {
    "kayak", "canoe", "packraft",
    "road_bike", "gravel_bike", "mountain_bike", "cycling_trainer",
}


def test_capture_enums_cover_every_craft_alias_key():
    assert _ALIAS_CRAFT_NAMES <= (set(BIKE_TYPES) | set(PADDLE_CRAFT_TYPES))
