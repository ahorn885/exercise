"""Track 2 slice 2c.2 (issue #540) — deterministic terrain-feasibility cascade.

Pure-function coverage of `layer4.session_feasibility.resolve_terrain_feasibility`:
each cascade tier (exact / proxy / indoor / strength / reallocate), cluster-vs-
home routing, the D-018 three-terrain match, the MTB→road proxy case, and the
climbing-with-no-gym strength substitute.
"""

from __future__ import annotations

from layer4.session_feasibility import (
    TerrainResolution,
    enrich_resolution_display,
    feasibility_line,
    indoor_machines,
    required_terrains,
    resolve_terrain_feasibility,
    surface_purpose,
)


def _resolve(discipline_id, **kw):
    base = dict(
        locale_order=["home"],
        cluster_terrain_by_locale={},
        cluster_equipment_by_locale={},
        gap_rules={},
        discipline_exercise_ids=[],
    )
    base.update(kw)
    return resolve_terrain_feasibility(discipline_id, **base)


class TestUnconstrained:
    def test_discipline_without_terrain_requirement_returns_none(self):
        # D-027 OCR carries no required terrain → nothing to constrain.
        assert _resolve("D-027") is None
        assert _resolve("D-999-unknown") is None


class TestExactTier:
    def test_required_terrain_at_home(self):
        r = _resolve(
            "D-012",  # Rock Climbing needs TRN-013/014
            cluster_terrain_by_locale={"home": {"TRN-014"}},
        )
        assert r is not None
        assert r.tier == "exact"
        assert r.locale_id == "home"
        assert r.terrain_id == "TRN-014"

    def test_routes_to_nearby_cluster_locale_not_home(self):
        # Home lacks climbing terrain; a nearby cluster locale has the gym.
        r = _resolve(
            "D-012",
            locale_order=["home", "gym_downtown"],
            cluster_terrain_by_locale={"home": {"TRN-001"}, "gym_downtown": {"TRN-014"}},
        )
        assert r.tier == "exact"
        assert r.locale_id == "gym_downtown"
        assert r.terrain_id == "TRN-014"

    def test_home_wins_when_both_match(self):
        r = _resolve(
            "D-001",  # Trail Running TRN-002/003/004
            locale_order=["home", "other"],
            cluster_terrain_by_locale={"home": {"TRN-003"}, "other": {"TRN-002"}},
        )
        assert r.tier == "exact"
        assert r.locale_id == "home"

    def test_d018_mountaineering_matches_any_of_four(self):
        # D-018 = Mountain/Alpine OR Technical Rock/Scree OR Snow OR Off-Trail
        # (TRN-018 added per #340).
        for trn in ("TRN-005", "TRN-007", "TRN-012", "TRN-018"):
            r = _resolve("D-018", cluster_terrain_by_locale={"home": {trn}})
            assert r.tier == "exact"
            assert r.terrain_id == trn


class TestProxyTier:
    def test_mtb_with_no_offroad_becomes_road_proxy(self):
        # Mountain Biking (TRN-002/003/015) — none present; gap rule says
        # TRN-015 → TRN-001 (road) @ 0.55. Athlete has road terrain.
        r = _resolve(
            "D-008",
            cluster_terrain_by_locale={"home": {"TRN-001"}},
            gap_rules={"TRN-015": [("TRN-001", 0.55)]},
        )
        assert r.tier == "proxy"
        assert r.locale_id == "home"
        assert r.terrain_id == "TRN-001"
        assert r.proxy_fidelity == 0.55

    def test_proxy_below_floor_is_skipped(self):
        r = _resolve(
            "D-008",
            cluster_terrain_by_locale={"home": {"TRN-001"}},
            gap_rules={"TRN-015": [("TRN-001", 0.10)]},  # below floor
        )
        # No usable proxy → falls through to indoor (trainer) if available,
        # else strength; here no equipment → strength pool empty → reallocate.
        assert r.tier == "reallocate"

    def test_highest_fidelity_proxy_wins(self):
        r = _resolve(
            "D-008",
            locale_order=["home", "far"],
            cluster_terrain_by_locale={"home": {"TRN-001"}, "far": {"TRN-020"}},
            gap_rules={
                "TRN-003": [("TRN-001", 0.40)],
                "TRN-015": [("TRN-020", 0.70)],
            },
        )
        assert r.tier == "proxy"
        assert r.terrain_id == "TRN-020"
        assert r.locale_id == "far"
        assert r.proxy_fidelity == 0.70


class TestIndoorTier:
    def test_cycling_falls_back_to_trainer(self):
        # Road Cycling (TRN-001) absent; no proxy; home has a cycling trainer.
        r = _resolve(
            "D-006",
            cluster_equipment_by_locale={"home": {"Cycling trainer", "Barbell"}},
        )
        assert r.tier == "indoor"
        assert r.machine == "Cycling trainer"
        assert r.locale_id == "home"

    def test_trekking_uses_stair_climber(self):
        r = _resolve(
            "D-003",
            cluster_equipment_by_locale={"home": {"Stair climber"}},
        )
        assert r.tier == "indoor"
        assert r.machine == "Stair climber"

    def test_paddling_uses_erg(self):
        r = _resolve(
            "D-010",
            cluster_equipment_by_locale={"home": {"Paddle ergometer"}},
        )
        assert r.tier == "indoor"
        assert r.machine == "Paddle ergometer"

    def test_indoor_preferred_machine_order(self):
        # When several machines are present, the first listed wins.
        r = _resolve(
            "D-006",
            cluster_equipment_by_locale={"home": {"Spin bike", "Cycling trainer"}},
        )
        assert r.machine == "Cycling trainer"


class TestStrengthTerminal:
    def test_climbing_with_no_gym_substitutes_strength(self):
        # The pv=65 case: Rock Climbing, no climbing terrain, no machine, but
        # mapped climbing exercises are equipment-feasible → strength session.
        r = _resolve(
            "D-012",
            discipline_exercise_ids=["EX-PULLUP", "EX-HANGBOARD", "EX-DEADHANG"],
        )
        assert r.tier == "strength"
        assert r.locale_id == "home"
        assert r.substitute_exercise_ids == ["EX-PULLUP", "EX-HANGBOARD", "EX-DEADHANG"]

    def test_strength_routes_to_the_equipment_bearing_locale(self):
        # Home has no gear; the gym (a nearby cluster locale) does → the
        # strength session is placed at the gym, not home.
        r = _resolve(
            "D-012",
            locale_order=["home", "home_gym"],
            cluster_equipment_by_locale={"home": set(), "home_gym": {"Pull-up bar"}},
            discipline_exercise_ids=["EX-PULLUP"],
        )
        assert r.tier == "strength"
        assert r.locale_id == "home_gym"

    def test_strength_falls_back_to_home_when_no_locale_lists_equipment(self):
        # Bodyweight-feasible: no locale carries equipment → home.
        r = _resolve(
            "D-012",
            locale_order=["home", "park"],
            cluster_equipment_by_locale={},
            discipline_exercise_ids=["EX-PUSHUP"],
        )
        assert r.tier == "strength"
        assert r.locale_id == "home"

    def test_strength_preferred_over_reallocate(self):
        r_with = _resolve("D-012", discipline_exercise_ids=["EX-1"])
        r_without = _resolve("D-012", discipline_exercise_ids=[])
        assert r_with.tier == "strength"
        assert r_without.tier == "reallocate"


class TestReallocateTerminal:
    def test_nothing_anywhere_reallocates(self):
        r = _resolve("D-012")  # no terrain, no machine, no exercises
        assert r.tier == "reallocate"
        assert r.locale_id is None


class TestCascadeOrder:
    def test_exact_beats_proxy_and_indoor(self):
        r = _resolve(
            "D-008",
            cluster_terrain_by_locale={"home": {"TRN-002"}},  # real MTB terrain
            cluster_equipment_by_locale={"home": {"Cycling trainer"}},
            gap_rules={"TRN-015": [("TRN-001", 0.9)]},
        )
        assert r.tier == "exact"
        assert r.terrain_id == "TRN-002"

    def test_proxy_beats_indoor(self):
        r = _resolve(
            "D-008",
            cluster_terrain_by_locale={"home": {"TRN-020"}},
            cluster_equipment_by_locale={"home": {"Cycling trainer"}},
            gap_rules={"TRN-003": [("TRN-020", 0.65)]},
        )
        assert r.tier == "proxy"


class TestDeterministicVenueDisplay:
    """#624 / #618-7 — the EXACT venue menu names the NEAREST saved locale per
    terrain (display name + distance), so the synthesizer can't claim 'no nearby
    groomed trail' or invent a farther park, and cites the locale by its display
    name rather than its slug ('509 Williams Avenue' not 'Williams')."""

    # pv=71's real cluster shape (distance-sorted as cluster_locale_ids returns):
    # home has hills only; groomed trail (TRN-002) lives at the nearer Cleburne,
    # not the farther Dinosaur Valley.
    _ORDER = ["509_williams_avenue", "cleburne_state_park", "dinosaur_valley_state_park"]
    _TERRAIN = {
        "509_williams_avenue": {"TRN-001", "TRN-004"},          # Road, Hill/Rolling
        "cleburne_state_park": {"TRN-002", "TRN-003", "TRN-004"},  # Groomed/Tech/Hill
        "dinosaur_valley_state_park": {"TRN-002", "TRN-003"},
    }
    _META = {
        "509_williams_avenue": {"name": "509 Williams Avenue", "distance_km": 0.0},
        "cleburne_state_park": {"name": "Cleburne State Park", "distance_km": 18.0},
        "dinosaur_valley_state_park": {"name": "Dinosaur Valley State Park", "distance_km": 40.0},
    }
    _NAMES = {"TRN-002": "Groomed Trail", "TRN-003": "Technical Trail", "TRN-004": "Hill / Rolling"}

    # Surface attributes (#624) — from layer0.terrain_types: Groomed flat/non-tech
    # (aerobic), Technical Trail non-elev/tech (technical), Hill/Rolling elevation
    # (vert).
    _ATTRS = {
        "TRN-002": {"requires_elevation": False, "technical_surface": False},
        "TRN-003": {"requires_elevation": False, "technical_surface": True},
        "TRN-004": {"requires_elevation": True, "technical_surface": False},
    }

    def _enrich(self, resolution, terrain_attrs=None):
        return enrich_resolution_display(
            resolution,
            locale_order=self._ORDER,
            locale_meta=self._META,
            terrain_names=self._NAMES,
            terrain_by_locale=self._TERRAIN,
            terrain_attrs=terrain_attrs,
        )

    def test_exact_menu_names_nearest_venue_per_terrain(self):
        # Trail Running (D-001 needs TRN-002/003/004): home wins EXACT on hills,
        # but the menu must surface groomed trail at the NEARER Cleburne (18 km),
        # never the farther Dinosaur Valley (40 km).
        r = resolve_terrain_feasibility(
            "D-001",
            locale_order=self._ORDER,
            cluster_terrain_by_locale=self._TERRAIN,
            cluster_equipment_by_locale={},
            gap_rules={},
            discipline_exercise_ids=[],
        )
        r = self._enrich(r)
        venues = dict((tn, (ln, d)) for tn, ln, d in r.terrain_venues)
        assert venues["Groomed Trail"] == ("Cleburne State Park", 18.0)
        assert venues["Hill / Rolling"] == ("509 Williams Avenue", 0.0)
        # Dinosaur Valley (farther) is never the chosen venue for any terrain.
        assert all(ln != "Dinosaur Valley State Park" for ln, _d in venues.values())

        line = feasibility_line(r, discipline_name="Trail Running")
        assert "Groomed Trail at \"Cleburne State Park\" (18 km away)" in line
        assert "Hill / Rolling at \"509 Williams Avenue\" (home)" in line
        assert "never name or suggest a location not in this list" in line
        # No slug / TRN-id leak in the athlete-facing line.
        assert "509_williams_avenue" not in line and "TRN-" not in line

    def test_surface_routing_sends_each_purpose_to_its_nearest_surface(self):
        # #624: with terrain attrs, Trail Running routes easy/long aerobic to the
        # nearest FLAT trail (Groomed at Cleburne, 18 km — home has only hills),
        # hill/vert work to the home hills, technical to the nearest tech trail.
        r = resolve_terrain_feasibility(
            "D-001",
            locale_order=self._ORDER,
            cluster_terrain_by_locale=self._TERRAIN,
            cluster_equipment_by_locale={},
            gap_rules={},
            discipline_exercise_ids=[],
        )
        r = self._enrich(r, terrain_attrs=self._ATTRS)
        routes = {purpose: (ln, d) for purpose, _tn, ln, d in r.surface_routes}
        assert routes["easy / long aerobic"] == ("Cleburne State Park", 18.0)
        assert routes["hill / vert work"] == ("509 Williams Avenue", 0.0)
        assert routes["technical / skill work"] == ("Cleburne State Park", 18.0)

        line = feasibility_line(r, discipline_name="Trail Running")
        assert "routed by session purpose" in line
        assert 'easy / long aerobic on "Cleburne State Park" (18 km away)' in line
        assert 'hill / vert work on "509 Williams Avenue" (home)' in line
        assert "do not collapse every session onto the nearest one" in line
        assert "509_williams_avenue" not in line and "TRN-" not in line

    def test_no_routing_without_attrs_falls_back_to_menu(self):
        # Backward-compat: no terrain_attrs → surface_routes empty, the existing
        # nearest-venue MENU renders unchanged.
        r = resolve_terrain_feasibility(
            "D-001",
            locale_order=self._ORDER,
            cluster_terrain_by_locale=self._TERRAIN,
            cluster_equipment_by_locale={},
            gap_rules={},
            discipline_exercise_ids=[],
        )
        r = self._enrich(r)  # no attrs
        assert r.surface_routes == ()
        line = feasibility_line(r, discipline_name="Trail Running")
        assert "routed by session purpose" not in line
        assert 'Groomed Trail at "Cleburne State Park" (18 km away)' in line

    def test_no_routing_when_surfaces_share_one_locale(self):
        # Not meaningful: every required surface (and purpose) sits at home → no
        # routing, the single/menu rendering is used instead.
        order = ["home"]
        terrain = {"home": {"TRN-002", "TRN-003", "TRN-004"}}
        meta = {"home": {"name": "Home", "distance_km": 0.0}}
        r = resolve_terrain_feasibility(
            "D-001",
            locale_order=order,
            cluster_terrain_by_locale=terrain,
            cluster_equipment_by_locale={},
            gap_rules={},
            discipline_exercise_ids=[],
        )
        r = enrich_resolution_display(
            r, locale_order=order, locale_meta=meta, terrain_names=self._NAMES,
            terrain_by_locale=terrain, terrain_attrs=self._ATTRS,
        )
        assert r.surface_routes == ()

    def test_display_name_used_not_slug_all_tiers(self):
        # #618-7: the strength tier cites the locale display name, not the slug.
        r = TerrainResolution(
            "D-012", "strength", "509_williams_avenue",
            substitute_exercise_ids=["EX-1"],
        )
        r = self._enrich(r)
        line = feasibility_line(r, discipline_name="Rock Climbing")
        assert '"509 Williams Avenue" (home)' in line
        assert "509_williams_avenue" not in line


class TestCraftSurfaceRouting:
    """#624 Slice 3 — craft own/proxy EXACT resolutions get the per-purpose
    surface routing too, but constrained to the resolved craft's rideable
    terrains so a bike/paddle session is never routed to a required surface its
    craft can't traverse. The SWAP tier (sport changes) is left untouched."""

    # MTB (D-008) requires TRN-002 Groomed (aerobic) / TRN-003 Technical
    # (technical) / TRN-015 Pump Track (vert). Each at a different locale.
    _ORDER = ["home", "park", "faraway"]
    _TERRAIN = {"home": {"TRN-002"}, "park": {"TRN-003"}, "faraway": {"TRN-015"}}
    _META = {
        "home": {"name": "Home", "distance_km": 0.0},
        "park": {"name": "Park", "distance_km": 10.0},
        "faraway": {"name": "Faraway", "distance_km": 80.0},
    }
    _NAMES = {"TRN-002": "Groomed Trail", "TRN-003": "Technical Trail", "TRN-015": "Pump Track"}
    _ATTRS = {
        "TRN-002": {"requires_elevation": False, "technical_surface": False},
        "TRN-003": {"requires_elevation": False, "technical_surface": True},
        "TRN-015": {"requires_elevation": True, "technical_surface": True},
    }
    # The owned mountain bike rides groomed + technical, but NOT the pump track.
    _CRAFT_TERRAIN = {"mountain_bike": {"TRN-002", "TRN-003"}}

    def _enrich(self, resolution, *, craft_terrain=None):
        return enrich_resolution_display(
            resolution,
            locale_order=self._ORDER,
            locale_meta=self._META,
            terrain_names=self._NAMES,
            terrain_by_locale=self._TERRAIN,
            terrain_attrs=self._ATTRS,
            craft_terrain=craft_terrain,
        )

    def test_own_craft_routing_excludes_unrideable_surface(self):
        # Tier 1: own the MTB on a required terrain. Pump Track (TRN-015) is a
        # required surface present in-cluster but the bike can't ride it → it must
        # NOT appear in the routing or the venue menu.
        r = TerrainResolution("D-008", "exact", "home", terrain_id="TRN-002", owned_craft="mountain_bike")
        r = self._enrich(r, craft_terrain=self._CRAFT_TERRAIN)
        routes = {purpose: ln for purpose, _tn, ln, _d in r.surface_routes}
        assert routes == {
            "easy / long aerobic": "Home",
            "technical / skill work": "Park",
        }
        assert "hill / vert work" not in routes
        assert all(tn != "Pump Track" for tn, _ln, _d in r.terrain_venues)

    def test_proxy_craft_tier_gets_constrained_routing(self):
        # Tier 3: a proxy craft rides the required terrain — now routed too,
        # constrained the same way.
        r = TerrainResolution(
            "D-008", "exact", "home", terrain_id="TRN-002",
            craft_tier="proxy", owned_craft="mountain_bike",
        )
        r = self._enrich(r, craft_terrain=self._CRAFT_TERRAIN)
        routes = {purpose for purpose, _tn, _ln, _d in r.surface_routes}
        assert routes == {"easy / long aerobic", "technical / skill work"}
        line = feasibility_line(r, discipline_name="Mountain Biking")
        assert "routed by session purpose" in line

    def test_swap_tier_gets_no_routing(self):
        # Tier 4 SWAP: the sport itself changes (train as the proxy's discipline),
        # so the original discipline's purpose routing would be wrong → left empty.
        r = TerrainResolution(
            "D-008", "exact", "home", terrain_id="TRN-002",
            craft_tier="swap", owned_craft="road_bike", craft_swap_to_name="Road Cycling",
        )
        r = self._enrich(r, craft_terrain=self._CRAFT_TERRAIN)
        assert r.surface_routes == ()
        assert r.terrain_venues == ()

    def test_noncraft_unchanged_when_craft_terrain_supplied(self):
        # A non-craft resolution (owned_craft None) is byte-identical whether or
        # not craft_terrain is passed — the constraint only applies to crafts.
        r = TerrainResolution("D-008", "exact", "home", terrain_id="TRN-002")
        with_ct = self._enrich(r, craft_terrain=self._CRAFT_TERRAIN)
        without_ct = self._enrich(r, craft_terrain=None)
        assert with_ct.surface_routes == without_ct.surface_routes
        # Unconstrained → Pump Track's vert purpose IS present (no craft to gate it).
        assert "hill / vert work" in {p for p, _tn, _ln, _d in with_ct.surface_routes}


class TestMaps:
    def test_required_terrains_lookup(self):
        assert required_terrains("D-018") == frozenset({"TRN-005", "TRN-007", "TRN-012", "TRN-018"})
        assert required_terrains("D-001") == frozenset({"TRN-002", "TRN-003", "TRN-004", "TRN-018"})
        assert required_terrains("D-027") == frozenset()

    def test_indoor_machines_lookup(self):
        assert "Treadmill" in indoor_machines("D-001")
        assert "Ski erg" in indoor_machines("D-028")
        assert indoor_machines("D-012") == ()  # climbing has no machine

    def test_surface_purpose_classifier(self):
        # #624: derived from layer0.terrain_types attrs, elevation dominates.
        assert surface_purpose(False, False) == "easy / long aerobic"   # Groomed/Road
        assert surface_purpose(True, False) == "hill / vert work"        # Hill/Rolling
        assert surface_purpose(False, True) == "technical / skill work"  # Technical Trail
        assert surface_purpose(True, True) == "hill / vert work"         # Mtn/Alpine, Fell
