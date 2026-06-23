"""Tests for `athlete_gear_repo.py` (#884 unified gear/craft model, slice 3).

Uses a `_FakeConn` (no real DB), mirroring test_athlete_crafts_repo. Covers the
§5.5 keyspace guard, the owned-gear read/write, the per-locale read/write/delete,
the closed-set validation, and the two eviction surfaces (§9).
"""
from __future__ import annotations

import pytest

import athlete_gear_repo as agr
from athlete_gear_repo import (
    GEAR_REGISTRY,
    GearSelectionError,
    delete_gear_locale,
    get_athlete_gear,
    load_gear_locales,
    replace_athlete_gear,
    replace_gear_locale,
)


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


# ─── §5.5 keyspace guard ─────────────────────────────────────────────────────
# The app-side gear_id keyspace must stay in lockstep with the Layer-0 set in
# etl/migrations/layer0/0024_gear_discipline_aliases.sql (design v3 §5.5). The
# craft-substitution + feasibility cascade (slice 4) exact-matches these keys, so
# an app/L0 drift would silently break gear→discipline resolution — this fails
# loudly instead (the gear analogue of the craft-alias coverage guard).
_KEYSPACE_0024 = {
    # crafts (rank-0 alias rows)
    "kayak", "canoe", "packraft", "raft", "sup",
    "road_bike", "gravel_bike", "mountain_bike", "tt_bike",
    # gear toggles
    "climbing_gear", "snowshoes", "mountaineering", "skimo_at",
    # D-028 ladder
    "classic_xc_ski", "skate_xc_ski", "rollerskis",
}
_GROUP_KINDS = {"bike", "paddle", "ski", "snow", "climbing", "alpine"}


class TestKeyspace:
    def test_registry_matches_layer0_keyspace(self):
        assert set(GEAR_REGISTRY) == _KEYSPACE_0024

    def test_group_kinds_are_the_closed_set(self):
        assert set(GEAR_REGISTRY.values()) == _GROUP_KINDS

    def test_craft_slugs_route_to_their_family(self):
        assert GEAR_REGISTRY["road_bike"] == "bike"
        assert GEAR_REGISTRY["kayak"] == "paddle"
        assert GEAR_REGISTRY["rollerskis"] == "ski"  # Decision 10 — owned dryland gear


# ─── get_athlete_gear ────────────────────────────────────────────────────────

class TestGet:
    def test_returns_rows_in_keyspace_order(self):
        conn = _FakeConn()
        # rows out of keyspace order → emitted in GEAR_REGISTRY order.
        conn.queue_response(rows=[
            {"gear_id": "kayak", "group_kind": "paddle", "access": "own"},
            {"gear_id": "road_bike", "group_kind": "bike", "access": "access"},
        ])
        assert get_athlete_gear(conn, 1) == [
            {"gear_id": "road_bike", "group_kind": "bike", "access": "access"},
            {"gear_id": "kayak", "group_kind": "paddle", "access": "own"},
        ]

    def test_empty_when_none(self):
        conn = _FakeConn()
        conn.queue_response(rows=[])
        assert get_athlete_gear(conn, 1) == []


# ─── replace_athlete_gear ────────────────────────────────────────────────────

class TestReplace:
    def test_valid_deletes_then_inserts_in_order_with_derived_group_kind(self):
        conn = _FakeConn()
        # submitted out of order → DELETE then INSERTs in GEAR_REGISTRY order.
        replace_athlete_gear(conn, 1, {"gravel_bike": "own", "road_bike": "access"})
        assert conn.calls[0][0].startswith("DELETE FROM athlete_gear")
        assert conn.calls[0][1] == (1,)
        # road_bike precedes gravel_bike in BIKE_TYPES order; group_kind derived.
        assert conn.calls[1][1] == (1, "road_bike", "bike", "access")
        assert conn.calls[2][1] == (1, "gravel_bike", "bike", "own")
        assert len(conn.calls) == 3

    def test_empty_dict_clears(self):
        conn = _FakeConn()
        replace_athlete_gear(conn, 1, {})
        assert len(conn.calls) == 1
        assert conn.calls[0][0].startswith("DELETE FROM athlete_gear")

    def test_unknown_gear_id_raises_and_writes_nothing(self):
        conn = _FakeConn()
        with pytest.raises(GearSelectionError):
            replace_athlete_gear(conn, 1, {"jetski": "own"})
        assert conn.calls == []

    def test_bad_access_raises_and_writes_nothing(self):
        conn = _FakeConn()
        with pytest.raises(GearSelectionError):
            replace_athlete_gear(conn, 1, {"road_bike": "borrowed"})
        assert conn.calls == []


# ─── load_gear_locales ───────────────────────────────────────────────────────

class TestLoadLocales:
    def test_groups_by_locale_in_keyspace_order(self):
        conn = _FakeConn()
        conn.queue_response(rows=[
            {"locale": "home", "gear_id": "kayak"},
            {"locale": "home", "gear_id": "road_bike"},
            {"locale": "cabin", "gear_id": "packraft"},
        ])
        assert load_gear_locales(conn, 1) == {
            "home": ["road_bike", "kayak"],   # GEAR_REGISTRY order
            "cabin": ["packraft"],
        }

    def test_empty_when_none(self):
        conn = _FakeConn()
        conn.queue_response(rows=[])
        assert load_gear_locales(conn, 1) == {}


# ─── replace_gear_locale ─────────────────────────────────────────────────────

class TestReplaceLocale:
    def test_valid_deletes_then_inserts(self):
        conn = _FakeConn()
        conn.queue_response(rows=[{"1": 1}])  # _locale_exists → row
        replace_gear_locale(conn, 1, "home", ["kayak", "road_bike", "kayak"])
        assert "locale_profiles" in conn.calls[0][0]          # existence check
        assert conn.calls[1][0].startswith("DELETE FROM athlete_gear_locale")
        # deduped + emitted in GEAR_REGISTRY order.
        assert conn.calls[2][1] == (1, "road_bike", "home")
        assert conn.calls[3][1] == (1, "kayak", "home")
        assert len(conn.calls) == 4

    def test_empty_list_clears_locale(self):
        conn = _FakeConn()
        conn.queue_response(rows=[{"1": 1}])
        replace_gear_locale(conn, 1, "home", [])
        assert conn.calls[1][0].startswith("DELETE FROM athlete_gear_locale")
        assert len(conn.calls) == 2  # existence check + delete only

    def test_foreign_locale_raises_before_writing(self):
        conn = _FakeConn()
        conn.queue_response(rows=[])  # _locale_exists → None
        with pytest.raises(GearSelectionError):
            replace_gear_locale(conn, 1, "stranger", ["kayak"])
        assert len(conn.calls) == 1  # only the existence check ran

    def test_unknown_gear_raises_after_locale_check(self):
        conn = _FakeConn()
        conn.queue_response(rows=[{"1": 1}])  # locale exists
        with pytest.raises(GearSelectionError):
            replace_gear_locale(conn, 1, "home", ["jetski"])
        assert len(conn.calls) == 1  # existence check only; no DELETE/INSERT

    def test_blank_locale_raises_before_any_db_call(self):
        conn = _FakeConn()
        with pytest.raises(GearSelectionError):
            replace_gear_locale(conn, 1, "  ", ["kayak"])
        assert conn.calls == []


# ─── delete_gear_locale ──────────────────────────────────────────────────────

class TestDeleteLocale:
    def test_deletes_user_scoped_locale(self):
        conn = _FakeConn()
        delete_gear_locale(conn, 1, "home")
        assert len(conn.calls) == 1
        assert conn.calls[0][0].startswith("DELETE FROM athlete_gear_locale")
        assert conn.calls[0][1] == (1, "home")


# ─── eviction (§9) ───────────────────────────────────────────────────────────
# Owned gear shares the craft eviction story (Layer 1 → all Layer 4 + Layer 3);
# gear↔locale evicts only the two synthesis entry points. Mirrors the two craft
# repos. Spy on the cache primitives the functions delegate to.

class TestEviction:
    def test_owned_gear_change_evicts_layer1(self, monkeypatch):
        captured = {}

        def _spy(cache, user_id, layer):
            captured.update(user_id=user_id, layer=layer)
            return 0

        monkeypatch.setattr(agr, "evict_on_layer_change", _spy)
        monkeypatch.setattr(agr, "Layer4Cache", lambda backend: object())
        monkeypatch.setattr(agr, "PostgresCacheBackend", lambda fn: object())
        agr.evict_layer1_on_gear_change(_FakeConn(), 7)
        assert captured == {"user_id": 7, "layer": "layer1"}

    def test_gear_locale_change_evicts_plan_entry_points(self, monkeypatch):
        captured = {}

        class _SpyCache:
            def __init__(self, backend):
                pass

            def invalidate_user(self, user_id, *, layer, entry_points):
                captured.update(user_id=user_id, layer=layer, entry_points=entry_points)
                return 0

        monkeypatch.setattr(agr, "Layer4Cache", _SpyCache)
        monkeypatch.setattr(agr, "PostgresCacheBackend", lambda fn: object())
        agr.evict_plan_caches_on_gear_locale_change(_FakeConn(), 7)
        assert captured["user_id"] == 7
        assert captured["layer"] == "gear_locale"
        assert captured["entry_points"] == ("plan_create", "plan_refresh")
