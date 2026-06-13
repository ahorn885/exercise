"""Tests for the deterministic craft-feasibility resolver (#540 slice 2c.2c).

`resolve_craft_feasibility` is the craft axis: owns a craft for the discipline's
group → owned; owns a same-`group_kind` craft in another group → swap (road bike
for MTB); owns no craft of the kind → strength. Pure, no DB. Fixtures mirror the
live `layer0` data (modality membership + craft aliases).
"""
from __future__ import annotations

from layer4.session_feasibility import CraftResolution, resolve_craft_feasibility

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
# craft → discipline(s) + craft → group_kind (live craft_discipline_aliases)
_CRAFT_DISC = {
    "road_bike": ["D-006"],
    "gravel_bike": ["D-006", "D-030", "D-031"],
    "mountain_bike": ["D-008", "D-031"],
    "cycling_trainer": ["D-006", "D-007", "D-008", "D-030", "D-031"],
    "kayak": ["D-010"],
    "canoe": ["D-011"],
    "packraft": ["D-009"],
}
_CRAFT_KIND = {
    c: ("paddle" if c in ("kayak", "canoe", "packraft") else "bike")
    for c in _CRAFT_DISC
}


def _resolve(discipline_id, owned):
    return resolve_craft_feasibility(
        discipline_id,
        owned_crafts=owned,
        craft_disciplines=_CRAFT_DISC,
        craft_group_kind=_CRAFT_KIND,
        discipline_groups=_DISC_GROUPS,
        group_kind=_GROUP_KIND,
    )


class TestNonCraft:
    def test_foot_discipline_returns_none(self):
        # Foot has no craft vessel → terrain axis owns it.
        assert _resolve("D-001", ["road_bike"]) is None

    def test_unknown_discipline_returns_none(self):
        assert _resolve("D-999", ["road_bike"]) is None


class TestOwned:
    def test_exact_craft_owned(self):
        r = _resolve("D-008", ["mountain_bike"])
        assert r == CraftResolution("D-008", "owned", "D-008", owned_craft="mountain_bike")

    def test_same_group_craft_owned(self):
        # Gravel bike aliases to D-031 (bike_offroad) — same group as MTB D-008.
        r = _resolve("D-008", ["gravel_bike"])
        assert r.tier == "owned" and r.effective_discipline_id == "D-008"
        assert r.owned_craft == "gravel_bike"

    def test_trainer_trains_any_bike(self):
        r = _resolve("D-008", ["cycling_trainer"])
        assert r.tier == "owned"

    def test_paddle_same_group_owned(self):
        # Own a kayak (D-010), race wants packraft (D-009) — both paddle_flatwater.
        r = _resolve("D-009", ["kayak"])
        assert r.tier == "owned" and r.owned_craft == "kayak"

    def test_road_bike_for_road_discipline(self):
        assert _resolve("D-006", ["road_bike"]).tier == "owned"


class TestSwap:
    def test_road_bike_for_mtb_swaps_to_road(self):
        # Own only a road bike (bike_pavement); race wants MTB (bike_offroad).
        r = _resolve("D-008", ["road_bike"])
        assert r.tier == "swap"
        assert r.effective_discipline_id == "D-006"
        assert r.owned_craft == "road_bike"

    def test_swap_target_is_deterministic(self):
        # Multiple owned same-kind crafts → first (sorted) wins, stable.
        a = _resolve("D-008", ["road_bike", "cycling_trainer"])
        # cycling_trainer aliases D-008 → that's actually OWNED, not swap.
        assert a.tier == "owned"


class TestStrength:
    def test_no_bike_owned_is_strength(self):
        r = _resolve("D-008", [])
        assert r.tier == "strength" and r.effective_discipline_id == "D-008"
        assert "no bike craft" in r.note

    def test_paddle_craft_owned_does_not_satisfy_bike(self):
        # Owns a kayak only; race wants MTB → no bike craft → strength.
        r = _resolve("D-008", ["kayak"])
        assert r.tier == "strength"

    def test_no_paddle_owned_is_strength(self):
        assert _resolve("D-009", ["road_bike"]).tier == "strength"


def test_pure_and_stable():
    out = [_resolve("D-008", ["road_bike"]) for _ in range(3)]
    assert out[0] == out[1] == out[2]


# ─── Slice V5: craft ownership from the equipment inventory ──────────────────


class TestCraftSlugsFromEquipment:
    """`craft_slugs_from_equipment` bridges the equipment-inventory canonical
    names → craft slugs, so listing a bike/boat as equipment counts as owning
    the craft (the decided single-source-of-truth fix)."""

    def test_canonical_names_map_to_slugs(self):
        from layer4.session_feasibility import craft_slugs_from_equipment

        got = craft_slugs_from_equipment(
            {"Mountain bike", "Road bike", "Packraft", "Kayak"}
        )
        assert got == {"mountain_bike", "road_bike", "packraft", "kayak"}

    def test_parenthetical_label_and_casing_tolerated(self):
        from layer4.session_feasibility import craft_slugs_from_equipment

        assert craft_slugs_from_equipment({"Mountain Bike (MTB)"}) == {"mountain_bike"}
        assert craft_slugs_from_equipment({"GRAVEL BIKE"}) == {"gravel_bike"}

    def test_non_craft_equipment_ignored(self):
        from layer4.session_feasibility import craft_slugs_from_equipment

        # Indoor machines + generic gear are NOT craft ownership.
        assert craft_slugs_from_equipment(
            {"Cycling trainer", "Paddle ergometer", "Treadmill", "Barbell", "Bodyweight"}
        ) == set()

    def test_empty(self):
        from layer4.session_feasibility import craft_slugs_from_equipment

        assert craft_slugs_from_equipment(set()) == set()

    def test_set_in_sync_with_athlete_enums(self):
        # Recurrence guard (#558 coverage-guard pattern): the equipment craft
        # set is exactly the bike + paddle vessel enums minus the indoor trainer.
        from athlete import BIKE_TYPES, PADDLE_CRAFT_TYPES
        from layer4.session_feasibility import _EQUIPMENT_CRAFT_SLUGS

        expected = (set(BIKE_TYPES) | set(PADDLE_CRAFT_TYPES)) - {"cycling_trainer"}
        assert set(_EQUIPMENT_CRAFT_SLUGS) == expected
