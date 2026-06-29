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
    GEAR_TOGGLE_LABELS,
    GearSelectionError,
    _GEAR_TOGGLE_KINDS,
    delete_gear_locale,
    get_athlete_gear,
    get_owned_gear_toggles,
    load_gear_locales,
    load_gear_toggle_catalog,
    parse_gear_toggle_form,
    replace_athlete_gear,
    replace_gear_locale,
    replace_owned_gear_for_kinds,
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
# Drill-gating swim gear (slice 3b) — group_kind 'swim', NOT in gear_discipline_
# aliases (it gates cardio drills, not disciplines). pull_buoy/kickboard map to
# EX126/EX128 in layer0.cardio_drill_gear_requirements (migration 0025); paddles/
# fins are seeded vocab with no gated drill yet (Andy 2026-06-23).
_SWIM_GEAR = {"pull_buoy", "kickboard", "paddles", "fins"}
_GROUP_KINDS = {"bike", "paddle", "ski", "snow", "climb", "alpine", "swim"}


class TestKeyspace:
    def test_discipline_unlocking_subset_matches_layer0_keyspace(self):
        # The non-swim (discipline-unlocking) gear must match migration 0024.
        unlocking = {g for g, kind in GEAR_REGISTRY.items() if kind != "swim"}
        assert unlocking == _KEYSPACE_0024

    def test_swim_gear_vocab(self):
        swim = {g for g, kind in GEAR_REGISTRY.items() if kind == "swim"}
        assert swim == _SWIM_GEAR

    def test_group_kinds_are_the_closed_set(self):
        assert set(GEAR_REGISTRY.values()) == _GROUP_KINDS

    def test_craft_slugs_route_to_their_family(self):
        assert GEAR_REGISTRY["road_bike"] == "bike"
        assert GEAR_REGISTRY["kayak"] == "paddle"
        assert GEAR_REGISTRY["rollerskis"] == "ski"  # Decision 10 — owned dryland gear
        assert GEAR_REGISTRY["pull_buoy"] == "swim"  # Decision 11 — drill-gating gear


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


# ─── replace_owned_gear_for_kinds (#884 slice 4 — per-surface scoped write) ───

class TestReplaceForKinds:
    def test_scoped_delete_then_inserts_only_those_kinds(self):
        conn = _FakeConn()
        replace_owned_gear_for_kinds(
            conn, 1, {"gravel_bike": "own", "kayak": "own"}, {"bike", "paddle"}
        )
        # DELETE is scoped to the surface's kinds (sorted), preserving other kinds.
        assert conn.calls[0][0].startswith("DELETE FROM athlete_gear")
        assert "group_kind IN (?,?)" in conn.calls[0][0]
        assert conn.calls[0][1] == (1, "bike", "paddle")
        # INSERTs in GEAR_REGISTRY order, group_kind derived.
        inserted = [(c[1][1], c[1][2]) for c in conn.calls[1:]]
        assert inserted == [("gravel_bike", "bike"), ("kayak", "paddle")]

    def test_empty_clears_only_those_kinds(self):
        conn = _FakeConn()
        replace_owned_gear_for_kinds(conn, 1, {}, {"ski", "snow", "climb", "alpine"})
        assert len(conn.calls) == 1
        assert conn.calls[0][1] == (1, "alpine", "climb", "ski", "snow")

    def test_off_surface_gear_raises_and_writes_nothing(self):
        # A craft surface ({bike,paddle}) cannot write a ski-kind gear_id.
        conn = _FakeConn()
        with pytest.raises(GearSelectionError):
            replace_owned_gear_for_kinds(
                conn, 1, {"rollerskis": "own"}, {"bike", "paddle"}
            )
        assert conn.calls == []

    def test_unknown_gear_id_raises_and_writes_nothing(self):
        conn = _FakeConn()
        with pytest.raises(GearSelectionError):
            replace_owned_gear_for_kinds(conn, 1, {"jetski": "own"}, {"bike"})
        assert conn.calls == []


# ─── gear-toggle capture surface (slice 4b) ──────────────────────────────────

class TestGearToggleCapture:
    def test_labels_cover_exactly_the_toggle_kinds(self):
        # Lockstep guard: GEAR_TOGGLE_LABELS keys == the discipline-unlocking
        # toggle slugs (group_kind ∈ _GEAR_TOGGLE_KINDS). No craft, no swim gear.
        toggle_slugs = {g for g, k in GEAR_REGISTRY.items() if k in _GEAR_TOGGLE_KINDS}
        assert set(GEAR_TOGGLE_LABELS) == toggle_slugs
        assert _GEAR_TOGGLE_KINDS == {"ski", "snow", "climb", "alpine"}

    def test_catalog_is_toggle_slugs_in_keyspace_order(self):
        catalog = load_gear_toggle_catalog()
        slugs = [item["slug"] for item in catalog]
        # GEAR_REGISTRY (== _GEAR_IDS) order; crafts + swim excluded.
        assert slugs == [
            "classic_xc_ski", "skate_xc_ski", "rollerskis", "snowshoes",
            "climbing_gear", "mountaineering", "skimo_at",
        ]
        assert all(GEAR_REGISTRY[s] in _GEAR_TOGGLE_KINDS for s in slugs)
        assert catalog[0]["label"] == GEAR_TOGGLE_LABELS["classic_xc_ski"]

    def test_parse_checked_become_own_unchecked_omitted(self):
        form = {
            "gear__rollerskis": "1",
            "gear__climbing_gear": "1",
            # snowshoes unchecked → omitted; a non-gear field is ignored
            "bike_types": "road_bike",
        }
        assert parse_gear_toggle_form(form) == {
            "rollerskis": "own",
            "climbing_gear": "own",
        }

    def test_parse_ignores_unknown_and_off_surface_keys(self):
        # Only catalog slugs are considered — a bike (off-surface) or bogus slug
        # in a malformed POST can't be injected.
        form = {"gear__road_bike": "1", "gear__jetski": "1", "gear__pull_buoy": "1"}
        assert parse_gear_toggle_form(form) == {}

    def test_parse_empty_form_clears(self):
        assert parse_gear_toggle_form({}) == {}

    def test_owned_toggles_filtered_to_toggle_kinds_in_order(self):
        conn = _FakeConn()
        # athlete_gear holds crafts + toggles + swim; only toggles surface here.
        conn.queue_response(rows=[
            {"gear_id": "road_bike", "group_kind": "bike", "access": "own"},
            {"gear_id": "rollerskis", "group_kind": "ski", "access": "own"},
            {"gear_id": "climbing_gear", "group_kind": "climb", "access": "own"},
            {"gear_id": "pull_buoy", "group_kind": "swim", "access": "own"},
        ])
        # _GEAR_IDS order: rollerskis precedes climbing_gear.
        assert get_owned_gear_toggles(conn, 1) == ["rollerskis", "climbing_gear"]

    def test_owned_toggles_empty_when_none(self):
        conn = _FakeConn()
        conn.queue_response(rows=[])
        assert get_owned_gear_toggles(conn, 1) == []


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
