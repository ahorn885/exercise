"""Tests for the curated pure-craft discipline display-name overlay."""

import re

from discipline_display_names import (
    DISCIPLINE_DISPLAY_NAMES,
    discipline_display_name,
)

_ID_RE = re.compile(r"^D-\d{3}[a-z]?$")


class TestDisciplineDisplayNameMap:
    def test_map_covers_every_current_bridge_discipline(self):
        # 29 = D-001..D-029, contiguous (no suffixes, no gaps) after the R6
        # renumber + the two collapses (kayak -> D-010, mtn-running -> D-024).
        # Pins the count so an accidental add/drop is loud rather than silent.
        assert len(DISCIPLINE_DISPLAY_NAMES) == 29

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
        # D-006 surfaced as "XC Cycling (Road/Gravel)" via the bridge.
        assert DISCIPLINE_DISPLAY_NAMES["D-006"] == "Road Cycling"

    def test_kayak_pair_collapsed_to_single_label(self):
        # R6: flat-water + whitewater kayak collapsed to one D-010 "Kayaking".
        assert DISCIPLINE_DISPLAY_NAMES["D-010"] == "Kayaking"

    def test_mountain_running_pair_collapsed_to_single_label(self):
        # R6: uphill + downhill mountain-running collapsed to one D-024.
        assert DISCIPLINE_DISPLAY_NAMES["D-024"] == "Mountain Running"


class TestDisciplineDisplayName:
    def test_curated_id_returns_pure_craft_label(self):
        assert discipline_display_name("D-006", "XC Cycling (Road/Gravel)") == "Road Cycling"

    def test_curated_label_overrides_bridge_name(self):
        # Even when the bridge passes a different name, the overlay wins.
        assert discipline_display_name("D-001", "Trail run") == "Trail Running"

    def test_uncurated_id_falls_back_to_bridge_name(self):
        # e.g. the combined "D-006 + D-007" bridge rows.
        assert discipline_display_name("D-006 + D-007", "Road Cycling (+ TT/Tri Bike)") == \
            "Road Cycling (+ TT/Tri Bike)"

    def test_uncurated_id_with_no_fallback_returns_id(self):
        assert discipline_display_name("D-997") == "D-997"

    def test_uncurated_id_with_empty_fallback_returns_id(self):
        assert discipline_display_name("D-997", "") == "D-997"
