"""Tests for the pure-craft discipline display-name overlay.

The overlay now derives from the discipline canon
(`etl/layer0/discipline_canon.py`) — single source of truth.
"""

import re

from discipline_display_names import (
    DISCIPLINE_DISPLAY_NAMES,
    discipline_display_name,
)

_ID_RE = re.compile(r"^D-\d{3}$")


class TestDisciplineDisplayNameMap:
    def test_map_covers_every_canonical_discipline(self):
        # 21 surviving disciplines after the canon: 29 ids minus D-005/D-016
        # (merged into D-004 "Swimming"), D-020 (Swimrun -> sport), D-023
        # (Ski Transitions -> dropped), D-015 (Orienteering -> folded into D-003
        # "Trekking"), and D-025/D-026/D-029 (Pentathlon/Biathlon-only, removed
        # with those sports). Pins the count so a drift is loud.
        assert len(DISCIPLINE_DISPLAY_NAMES) == 21

    def test_all_keys_are_valid_discipline_ids(self):
        for did in DISCIPLINE_DISPLAY_NAMES:
            assert _ID_RE.match(did), f"bad id format: {did}"

    def test_all_values_are_nonempty_strings(self):
        for did, label in DISCIPLINE_DISPLAY_NAMES.items():
            assert isinstance(label, str) and label.strip(), did

    def test_no_terrain_qualifier_parens_in_labels(self):
        for did, label in DISCIPLINE_DISPLAY_NAMES.items():
            assert "(" not in label, f"{did} label still bundles a qualifier: {label!r}"

    def test_merged_and_removed_ids_absent(self):
        for gone in ("D-005", "D-016", "D-020", "D-023"):
            assert gone not in DISCIPLINE_DISPLAY_NAMES

    def test_known_mislabel_is_fixed(self):
        assert DISCIPLINE_DISPLAY_NAMES["D-006"] == "Road Cycling"

    def test_overlay_corrections(self):
        # The old overlay had drifted on these; the canon corrects them.
        assert DISCIPLINE_DISPLAY_NAMES["D-021"] == "Uphill Skinning"
        assert DISCIPLINE_DISPLAY_NAMES["D-022"] == "Alpine Descent"

    def test_collapsed_pairs_single_label(self):
        assert DISCIPLINE_DISPLAY_NAMES["D-010"] == "Kayaking"
        assert DISCIPLINE_DISPLAY_NAMES["D-024"] == "Mountain Running"


class TestDisciplineDisplayName:
    def test_canonical_id_returns_pure_craft_label(self):
        assert discipline_display_name("D-006", "XC Cycling (Road/Gravel)") == "Road Cycling"

    def test_canonical_label_overrides_bridge_name(self):
        assert discipline_display_name("D-001", "Trail run") == "Trail Running"

    def test_merged_id_resolves_to_survivor(self):
        # Former D-005 / D-016 now resolve to D-004 "Swimming".
        assert discipline_display_name("D-005", "Pool Sprint Swimming") == "Swimming"
        assert discipline_display_name("D-016", "Swimming (Pool + OW)") == "Swimming"

    def test_composite_id_falls_back_to_bridge_name(self):
        # Composite "D-006 + D-007" can't pick one craft label -> fallback.
        assert discipline_display_name("D-006 + D-007", "Road Cycling (+ TT/Tri Bike)") == \
            "Road Cycling (+ TT/Tri Bike)"

    def test_removed_id_falls_back_to_bridge_name(self):
        assert discipline_display_name("D-020", "Swimrun (Combined)") == "Swimrun (Combined)"

    def test_uncurated_id_with_no_fallback_returns_id(self):
        assert discipline_display_name("D-997") == "D-997"

    def test_uncurated_id_with_empty_fallback_returns_id(self):
        assert discipline_display_name("D-997", "") == "D-997"
