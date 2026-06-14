"""Tests for the unified craft/terrain feasibility cascade (#586 WS-I).

`resolve_craft_terrain_feasibility` walks ONE ordered cascade for a craft
(bike/paddle) discipline, composing craft ownership with terrain off the explicit
`layer0.craft_terrain_compatibility` grid (design §3/§4):

  1 own craft + required terrain → 2 own craft + alternate terrain →
  3 proxy craft + desired terrain → 4 proxy craft + its own terrain (swap) →
  5 indoor machine → 6 strength → 7 reallocate.

Pure, no DB. Fixtures mirror the live `layer0` data (modality membership, craft
aliases, and the Andy-ratified craft→terrain grid).
"""
from __future__ import annotations

from layer4.session_feasibility import resolve_craft_terrain_feasibility

# discipline → modality group(s) (subset of live discipline_modality_membership)
_DISC_GROUPS = {
    "D-001": ["foot"],
    "D-006": ["bike_pavement"],
    "D-007": ["bike_pavement"],
    "D-008": ["bike_offroad"],
    "D-030": ["bike_offroad", "bike_pavement"],
    "D-031": ["bike_offroad"],
    "D-009": ["paddle_flatwater", "paddle_whitewater"],
    "D-010": ["paddle_flatwater", "paddle_whitewater"],
    "D-011": ["paddle_flatwater"],
}
_GROUP_KIND = {
    "foot": "foot",
    "bike_pavement": "bike",
    "bike_offroad": "bike",
    "paddle_flatwater": "paddle",
    "paddle_whitewater": "paddle",
}
# craft → discipline(s) (live craft_discipline_aliases, post-0004: no cycling_trainer)
_CRAFT_DISC = {
    "road_bike": ["D-006"],
    "gravel_bike": ["D-006", "D-030", "D-031"],
    "mountain_bike": ["D-008", "D-031"],
    "kayak": ["D-010"],
    "canoe": ["D-011"],
    "packraft": ["D-009"],
}
_CRAFT_KIND = {
    c: ("paddle" if c in ("kayak", "canoe", "packraft") else "bike")
    for c in _CRAFT_DISC
}
# craft → usable terrain (the 0004 Andy-ratified grid).
_CRAFT_TERRAIN = {
    "road_bike": {"TRN-001", "TRN-004"},
    "gravel_bike": {"TRN-001", "TRN-002", "TRN-004", "TRN-020"},
    "mountain_bike": {"TRN-001", "TRN-002", "TRN-003", "TRN-004", "TRN-015", "TRN-020"},
    "kayak": {"TRN-009", "TRN-010", "TRN-011", "TRN-017"},
    "canoe": {"TRN-009", "TRN-017"},
    "packraft": {"TRN-009", "TRN-011", "TRN-017"},
}
_DISC_NAMES = {
    "D-006": "Road Cycling", "D-008": "Mountain Biking", "D-009": "Packrafting",
    "D-010": "Kayaking", "D-030": "Gravel Cycling", "D-031": "Cross Country Cycling",
}


def _resolve(
    discipline_id, owned, *, terrain=None, equipment=None, pool=None, locales=("Home",)
):
    terrain = terrain or {}
    equipment = equipment or {}
    return resolve_craft_terrain_feasibility(
        discipline_id,
        owned_crafts=owned,
        craft_disciplines=_CRAFT_DISC,
        craft_group_kind=_CRAFT_KIND,
        discipline_groups=_DISC_GROUPS,
        group_kind=_GROUP_KIND,
        craft_terrain=_CRAFT_TERRAIN,
        locale_order=list(locales),
        cluster_terrain_by_locale={loc: set(terrain.get(loc, ())) for loc in locales},
        cluster_equipment_by_locale={loc: set(equipment.get(loc, ())) for loc in locales},
        discipline_exercise_ids=list(pool or []),
        discipline_names=_DISC_NAMES,
    )


class TestNonCraft:
    def test_foot_discipline_returns_none(self):
        # Foot has no craft vessel → caller runs the terrain-only cascade.
        assert _resolve("D-001", ["road_bike"], terrain={"Home": ["TRN-001"]}) is None

    def test_unknown_discipline_returns_none(self):
        assert _resolve("D-999", ["road_bike"]) is None


class TestTier1Exact:
    def test_own_craft_on_required_terrain(self):
        # Own the MTB, the cluster carries technical trail → real terrain, train it.
        r = _resolve("D-008", ["mountain_bike"], terrain={"Home": ["TRN-003"]})
        assert r.tier == "exact" and r.craft_tier == ""
        assert r.owned_craft == "mountain_bike" and r.terrain_id == "TRN-003"

    def test_paddle_own_craft_exact(self):
        # Kayak (D-010) is a same-group craft for Packrafting (D-009): owned, exact.
        r = _resolve("D-009", ["kayak"], terrain={"Home": ["TRN-009"]})
        assert r.tier == "exact" and r.owned_craft == "kayak"
        assert r.terrain_id == "TRN-009"


class TestTier2OwnAlternate:
    def test_own_craft_substitute_surface(self):
        # Own MTB but only road in cluster — ride the MTB on the road (alt terrain),
        # NOT a gap-rule proxy (no fidelity number; the craft itself qualifies).
        r = _resolve("D-008", ["mountain_bike"], terrain={"Home": ["TRN-001"]})
        assert r.tier == "proxy" and r.craft_tier == ""
        assert r.owned_craft == "mountain_bike" and r.terrain_id == "TRN-001"
        assert r.proxy_fidelity is None


class TestTier3ProxyDesired:
    def test_proxy_craft_rides_desired_terrain(self):
        # Own a proxy craft (different group) that CAN ride the discipline's own
        # required terrain → ride the REAL terrain on the proxy (tier 3 > tier 4).
        r = resolve_craft_terrain_feasibility(
            "D-008",  # required {TRN-002, TRN-003, TRN-015}
            owned_crafts=["odd_bike"],
            craft_disciplines={"odd_bike": ["D-006"]},  # pavement alias → proxy for offroad
            craft_group_kind={"odd_bike": "bike"},
            discipline_groups={"D-008": ["bike_offroad"], "D-006": ["bike_pavement"]},
            group_kind={"bike_offroad": "bike", "bike_pavement": "bike"},
            craft_terrain={"odd_bike": {"TRN-001", "TRN-003"}},
            locale_order=["Home"],
            cluster_terrain_by_locale={"Home": {"TRN-001", "TRN-003"}},
            cluster_equipment_by_locale={"Home": set()},
            discipline_exercise_ids=[],
            discipline_names={"D-006": "Road Cycling"},
        )
        assert r.tier == "exact" and r.craft_tier == "proxy"
        assert r.owned_craft == "odd_bike"
        # TRN-003 (required, tier 3) beats TRN-001 (proxy's own terrain, tier 4).
        assert r.terrain_id == "TRN-003"


class TestTier4Swap:
    def test_proxy_craft_swaps_to_its_own_sport(self):
        # Own only a road bike; want MTB. Road can't ride any MTB terrain (tier 3
        # misses) → ride it on the road and train as Road Cycling (tier 4 swap).
        r = _resolve("D-008", ["road_bike"], terrain={"Home": ["TRN-001"]})
        assert r.tier == "exact" and r.craft_tier == "swap"
        assert r.owned_craft == "road_bike"
        assert r.craft_swap_to_name == "Road Cycling"
        assert r.terrain_id == "TRN-001"


class TestTier5Indoor:
    def test_craftless_with_trainer_is_indoor_not_strength(self):
        # THE BUG (design §1b): a craftless athlete with a trainer used to be sent
        # to STRENGTH because the craft axis short-circuited ahead of INDOOR. The
        # unified cascade falls through tiers 1–4 and lands on the trainer.
        r = _resolve("D-008", [], equipment={"Home": ["Cycling trainer"]})
        assert r.tier == "indoor" and r.craft_tier == ""
        assert r.machine == "Cycling trainer"

    def test_owned_craft_no_rideable_terrain_falls_to_indoor(self):
        # Own a road bike but the cluster has only alpine terrain it can't ride;
        # a trainer is present → indoor (tiers 1–4 all miss).
        r = _resolve(
            "D-008", ["road_bike"],
            terrain={"Home": ["TRN-005"]}, equipment={"Home": ["Cycling trainer"]},
        )
        assert r.tier == "indoor" and r.machine == "Cycling trainer"


class TestTier6Strength:
    def test_craftless_no_machine_is_craft_strength(self):
        # Craftless, no rideable terrain, no machine, but a mapped pool → strength
        # flagged as a CRAFT terminal (the reason is "no craft", not "no terrain").
        r = _resolve("D-008", [], pool=["EX-1", "EX-2"])
        assert r.tier == "strength" and r.craft_tier == "strength"
        assert r.craft_kind == "bike"
        assert r.substitute_exercise_ids == ["EX-1", "EX-2"]

    def test_owned_craft_no_terrain_is_terrain_strength(self):
        # Own the craft but no rideable terrain AND no machine → strength, flagged
        # as a TERRAIN terminal (craft_tier="") so the reason line stays accurate.
        r = _resolve("D-008", ["mountain_bike"], terrain={"Home": ["TRN-008"]}, pool=["EX-1"])
        assert r.tier == "strength" and r.craft_tier == ""
        assert r.craft_kind == ""


class TestTier7Reallocate:
    def test_nothing_available_reallocates(self):
        r = _resolve("D-008", [])
        assert r.tier == "reallocate" and r.locale_id is None


def test_pure_and_stable():
    out = [
        _resolve("D-008", ["road_bike"], terrain={"Home": ["TRN-001"]}) for _ in range(3)
    ]
    assert out[0] == out[1] == out[2]
