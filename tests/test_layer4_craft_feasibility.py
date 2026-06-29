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

# discipline → modality group(s) (subset of live discipline_modality_membership).
# #884 slice 4b: the gear-toggle disciplines join — note their MODALITY group_kind
# (snow/climb) DIVERGES from their GEAR kind (ski/snow/climbing/alpine), which is
# exactly why the cascade now gates on the gear-side `discipline_gear_kind`.
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
    "D-028": ["snow_glide"],   # XC skiing — modality 'snow', gear 'ski'
    "D-017": ["snow_travel"],  # snowshoeing — modality 'snow', gear 'snow'
    "D-012": ["climb"],        # rock climbing — modality 'climb', gear 'climbing'
    "D-018": ["snow_travel"],  # mountaineering — modality 'snow', gear 'alpine'
    "D-021": ["snow_glide"],   # skinning — modality 'snow', gear 'alpine'
    "D-022": ["snow_glide"],   # alpine descent — modality 'snow', gear 'alpine'
}
# gear → discipline(s) (live gear_discipline_aliases, 0024) — crafts + toggles.
_CRAFT_DISC = {
    "road_bike": ["D-006"],
    "gravel_bike": ["D-006", "D-030", "D-031"],
    "mountain_bike": ["D-008", "D-031"],
    "kayak": ["D-010"],
    "canoe": ["D-011"],
    "packraft": ["D-009"],
    "classic_xc_ski": ["D-028"],
    "skate_xc_ski": ["D-028"],
    "rollerskis": ["D-028"],
    "snowshoes": ["D-017"],
    "climbing_gear": ["D-012", "D-013", "D-014"],
    "mountaineering": ["D-018"],
    "skimo_at": ["D-021", "D-022"],
}
# gear → group_kind (gear_discipline_aliases.group_kind / GEAR_REGISTRY).
_CRAFT_KIND = {
    "road_bike": "bike", "gravel_bike": "bike", "mountain_bike": "bike",
    "kayak": "paddle", "canoe": "paddle", "packraft": "paddle",
    "classic_xc_ski": "ski", "skate_xc_ski": "ski", "rollerskis": "ski",
    "snowshoes": "snow", "climbing_gear": "climbing",
    "mountaineering": "alpine", "skimo_at": "alpine",
}
# discipline → gear kind, derived off the alias table exactly as the orchestrator
# does (`_gather_feasibility_inputs`). D-028 → ski, D-017 → snow, etc.
_DISC_GEAR_KIND = {
    d: _CRAFT_KIND[g] for g, discs in _CRAFT_DISC.items() for d in discs
}
# gear → fidelity_rank (gear_discipline_aliases, 0 = best). The D-028 ski ladder
# is the only non-zero case; everything else defaults to 0.
_FIDELITY_RANK = {"classic_xc_ski": 0, "skate_xc_ski": 1, "rollerskis": 2}
# gear → usable terrain (the Andy-ratified grid: 0004 crafts + 0026 toggles).
_CRAFT_TERRAIN = {
    "road_bike": {"TRN-001", "TRN-004"},
    "gravel_bike": {"TRN-001", "TRN-002", "TRN-004", "TRN-020"},
    "mountain_bike": {"TRN-001", "TRN-002", "TRN-003", "TRN-004", "TRN-015", "TRN-020"},
    "kayak": {"TRN-009", "TRN-010", "TRN-011", "TRN-017"},
    "canoe": {"TRN-009", "TRN-017"},
    "packraft": {"TRN-009", "TRN-011", "TRN-017"},
    "classic_xc_ski": {"TRN-012"},
    "skate_xc_ski": {"TRN-012"},
    "rollerskis": {"TRN-001"},
    "snowshoes": {"TRN-012"},
    "climbing_gear": {"TRN-013", "TRN-014"},
    "mountaineering": {"TRN-005", "TRN-007", "TRN-012"},
    "skimo_at": {"TRN-012"},
}
_DISC_NAMES = {
    "D-006": "Road Cycling", "D-008": "Mountain Biking", "D-009": "Packrafting",
    "D-010": "Kayaking", "D-030": "Gravel Cycling", "D-031": "Cross Country Cycling",
    "D-028": "Cross-Country Skiing", "D-017": "Snowshoeing", "D-012": "Rock Climbing",
    "D-018": "Mountaineering", "D-021": "Uphill Skinning",
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
        discipline_gear_kind=_DISC_GEAR_KIND,
        craft_fidelity_rank=_FIDELITY_RANK,
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
            discipline_gear_kind={"D-008": "bike", "D-006": "bike"},
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


class TestGearToggleSkiLadder:
    """#884 slice 4b — the D-028 ski ladder walks owned gear by ascending
    fidelity_rank (classic 0 → skate 1 → rollerskis 2), best-first."""

    def test_classic_wins_over_skate_and_rollerskis_on_snow(self):
        # Own all three; snow in cluster → EXACT on the rank-0 gear (classic).
        r = _resolve(
            "D-028", ["rollerskis", "skate_xc_ski", "classic_xc_ski"],
            terrain={"Home": ["TRN-012"]},
        )
        assert r.tier == "exact" and r.craft_tier == ""
        assert r.owned_craft == "classic_xc_ski" and r.terrain_id == "TRN-012"

    def test_skate_wins_when_no_classic(self):
        # Own skate + rollerskis only; snow present → EXACT on skate (rank 1),
        # NOT rollerskis (rank 2, can't ride snow anyway).
        r = _resolve(
            "D-028", ["rollerskis", "skate_xc_ski"], terrain={"Home": ["TRN-012"]}
        )
        assert r.tier == "exact" and r.owned_craft == "skate_xc_ski"
        assert r.terrain_id == "TRN-012"

    def test_rollerskis_do_not_resolve_snow_exact(self):
        # Own ONLY rollerskis; snow present but no pavement → rollerskis can't ride
        # snow (dryland gear), so NOT EXACT. No ski-erg/pool → strength.
        r = _resolve("D-028", ["rollerskis"], terrain={"Home": ["TRN-012"]}, pool=["EX-1"])
        assert r.tier == "strength"

    def test_rollerskis_dryland_proxy_carveout(self):
        # The carve-out: own rollerskis, no snow, pavement present → PROXY on the
        # alternate terrain (TRN-001) the gear is compatible with (tier 2, own-gear
        # alternate surface; no gap-rule fidelity number).
        r = _resolve("D-028", ["rollerskis"], terrain={"Home": ["TRN-001"]})
        assert r.tier == "proxy" and r.craft_tier == ""
        assert r.owned_craft == "rollerskis" and r.terrain_id == "TRN-001"
        assert r.proxy_fidelity is None

    def test_rollerskis_carveout_even_with_snow_present(self):
        # Snow present but the athlete owns only rollerskis (dryland): they resolve
        # on pavement, NOT silently on the snow they can't ski.
        r = _resolve(
            "D-028", ["rollerskis"], terrain={"Home": ["TRN-001", "TRN-012"]}
        )
        assert r.tier == "proxy" and r.owned_craft == "rollerskis"
        assert r.terrain_id == "TRN-001"

    def test_ski_erg_indoor_below_owned_gear(self):
        # Own classic, no snow, no pavement, but a ski-erg in the pool → INDOOR
        # (gear tiers 1–4 miss, the gear-independent machine catches it).
        r = _resolve(
            "D-028", ["classic_xc_ski"], equipment={"Home": ["Ski erg"]}
        )
        assert r.tier == "indoor" and r.machine == "Ski erg"


class TestGearToggleGatesDiscipline:
    """#884 slice 4b — owning the gear now GATES the discipline: no gear → the
    cascade can't reach EXACT even with the real surface present (the intended
    served-output change; the snowshoe/ski cases that PR-1's capture unblocks)."""

    def test_no_ski_gear_does_not_ski_on_snow(self):
        # Snow present but no ski gear owned → not EXACT; ski-erg present → INDOOR.
        r = _resolve("D-028", [], terrain={"Home": ["TRN-012"]},
                     equipment={"Home": ["Ski erg"]})
        assert r.tier == "indoor" and r.machine == "Ski erg"

    def test_snowshoes_owned_resolves_snow_exact(self):
        r = _resolve("D-017", ["snowshoes"], terrain={"Home": ["TRN-012"]})
        assert r.tier == "exact" and r.owned_craft == "snowshoes"
        assert r.terrain_id == "TRN-012"

    def test_no_snowshoes_gated_off_snow(self):
        # Snow present but no snowshoes → not EXACT; the snowshoe indoor machine
        # (treadmill/stair climber) catches it instead.
        r = _resolve("D-017", [], terrain={"Home": ["TRN-012"]},
                     equipment={"Home": ["Treadmill"]})
        assert r.tier == "indoor" and r.machine == "Treadmill"


class TestGearToggleClimbAlpine:
    """#884 slice 4b — climbing/alpine gear resolve on their real terrain (these
    disciplines reach the cascade only when their skill toggle is ON; the skill
    gate is applied by the caller before this resolver)."""

    def test_climbing_gear_on_rock_wall_exact(self):
        r = _resolve("D-012", ["climbing_gear"], terrain={"Home": ["TRN-013"]})
        assert r.tier == "exact" and r.owned_craft == "climbing_gear"
        assert r.terrain_id == "TRN-013"

    def test_climbing_gear_on_indoor_wall_exact(self):
        r = _resolve("D-012", ["climbing_gear"], terrain={"Home": ["TRN-014"]})
        assert r.tier == "exact" and r.terrain_id == "TRN-014"

    def test_mountaineering_gear_on_alpine_exact(self):
        # Mountaineering (alpine gear) on Mountain/Alpine terrain (TRN-005).
        r = _resolve("D-018", ["mountaineering"], terrain={"Home": ["TRN-005"]})
        assert r.tier == "exact" and r.owned_craft == "mountaineering"
        assert r.terrain_id == "TRN-005"

    def test_alpine_proxy_gear_rides_desired_terrain(self):
        # Own skimo gear but not mountaineering gear; doing D-018 (skilled). skimo
        # is a same-kind PROXY (alpine) that can ride D-018's snow → tier-3 proxy.
        r = _resolve("D-018", ["skimo_at"], terrain={"Home": ["TRN-012"]})
        assert r.tier == "exact" and r.craft_tier == "proxy"
        assert r.owned_craft == "skimo_at" and r.terrain_id == "TRN-012"

    def test_gearless_climber_strength_flags_gear_kind(self):
        # Skilled climber owns NO climbing gear, no machine → the gear STRENGTH
        # terminal, flagged by the gear kind ('climbing', not 'craft'/'bike').
        r = _resolve("D-012", [], pool=["EX-9"])
        assert r.tier == "strength" and r.craft_tier == "strength"
        assert r.craft_kind == "climbing"

    def test_climbing_gear_no_climb_terrain_is_terrain_strength(self):
        # Owns the gear but no crag/wall/machine in cluster → a TERRAIN strength
        # terminal (craft_tier="" — the reason is "no terrain", not "no gear").
        r = _resolve("D-012", ["climbing_gear"], terrain={"Home": ["TRN-001"]},
                     pool=["EX-9"])
        assert r.tier == "strength" and r.craft_tier == "" and r.craft_kind == ""


def test_pure_and_stable():
    out = [
        _resolve("D-008", ["road_bike"], terrain={"Home": ["TRN-001"]}) for _ in range(3)
    ]
    assert out[0] == out[1] == out[2]
