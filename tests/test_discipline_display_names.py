"""Tests for the curated pure-craft discipline display-name overlay."""

import re

from discipline_display_names import (
    DISCIPLINE_DISPLAY_NAMES,
    discipline_display_name,
)

_ID_RE = re.compile(r"^D-\d{3}[a-z]?$")


class TestDisciplineDisplayNameMap:
    def test_all_keys_are_valid_discipline_ids(self):
        for did in DISCIPLINE_DISPLAY_NAMES:
            assert _ID_RE.match(did), f"bad id format: {did}"

    def test_all_values_are_nonempty_strings(self):
        for did, label in DISCIPLINE_DISPLAY_NAMES.items():
            assert isinstance(label, str) and label.strip(), did

    def test_no_terrain_qualifier_parens_in_labels(self):
        # Pure-craft labels drop the Sheet-3 "(Road/Gravel)" style qualifiers.
        for did, label in DISCIPLINE_DISPLAY_NAMES.items():
            assert "(" not in label, f"{did} label still bundles a qualifier: {label!r}"

    def test_known_mislabel_is_fixed(self):
        # D-005 surfaced as "XC Cycling (Road/Gravel)" via the bridge.
        assert DISCIPLINE_DISPLAY_NAMES["D-005"] == "Road Cycling"

    def test_kayak_pair_kept_distinct_this_slice(self):
        # Collapse to one "Kayaking" is deferred to Slice 3.
        assert DISCIPLINE_DISPLAY_NAMES["D-008a"] != DISCIPLINE_DISPLAY_NAMES["D-008b"]

    def test_mountain_running_pair_kept_distinct_this_slice(self):
        # Collapse to "Mountain Running" is deferred to Slice 3.
        assert DISCIPLINE_DISPLAY_NAMES["D-022"] != DISCIPLINE_DISPLAY_NAMES["D-023"]


class TestDisciplineDisplayName:
    def test_curated_id_returns_pure_craft_label(self):
        assert discipline_display_name("D-005", "XC Cycling (Road/Gravel)") == "Road Cycling"

    def test_curated_label_overrides_bridge_name(self):
        # Even when the bridge passes a different name, the overlay wins.
        assert discipline_display_name("D-001", "Trail run") == "Trail Running"

    def test_uncurated_id_falls_back_to_bridge_name(self):
        # e.g. the combined "D-005 + D-005a" bridge rows.
        assert discipline_display_name("D-005 + D-005a", "Road Cycling (+ TT/Tri Bike)") == \
            "Road Cycling (+ TT/Tri Bike)"

    def test_uncurated_id_with_no_fallback_returns_id(self):
        assert discipline_display_name("D-997") == "D-997"

    def test_uncurated_id_with_empty_fallback_returns_id(self):
        assert discipline_display_name("D-997", "") == "D-997"
