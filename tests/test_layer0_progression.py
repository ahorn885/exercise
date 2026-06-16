"""Tests for the layer0 movement_patterns → rx progression-key crosswalk
(#335 Phase 2b identity slice). See `layer0_progression.py`."""

from calculations import PROGRESSION_RULES
from layer0_progression import (
    _LAYER0_TO_PROGRESSION,
    progression_pattern,
)


class TestProgressionPattern:
    def test_none_and_empty_fall_back_to_various(self):
        assert progression_pattern(None) == "Various"
        assert progression_pattern([]) == "Various"

    def test_single_squat(self):
        assert progression_pattern(["Squat"]) == "Squat"

    def test_hip_ext_maps_to_hinge(self):
        assert progression_pattern(["Hip-Ext"]) == "Hinge"

    def test_single_leg_maps_to_lunge(self):
        assert progression_pattern(["Single-Leg"]) == "Lunge"

    def test_vertical_and_horizontal_push_pull_collapse(self):
        assert progression_pattern(["Push-V"]) == "Push"
        assert progression_pattern(["Push-H"]) == "Push"
        assert progression_pattern(["Pull-V"]) == "Pull"
        assert progression_pattern(["Pull-H"]) == "Pull"

    def test_anti_family_and_isometric_map_to_core(self):
        for p in ("Anti-Rotation", "Anti-Extension", "Anti-Flexion",
                  "Anti-Lateral-Flexion", "Anti-Adduction", "Isometric"):
            assert progression_pattern([p]) == "Core", p

    def test_balance_and_stretch_and_locomotion(self):
        assert progression_pattern(["Balance / Proprioception"]) == "Balance"
        assert progression_pattern(["Stretch"]) == "Mobility"
        assert progression_pattern(["Locomotion"]) == "Locomotion"

    def test_unmapped_pattern_falls_back_to_various(self):
        # Abduction has no clean progression analogue → Various.
        assert progression_pattern(["Abduction"]) == "Various"

    def test_multi_pattern_picks_loadable_compound_first(self):
        # A Single-Leg + Anti-Rotation step-up loads as a Lunge, not Core.
        assert progression_pattern(["Anti-Rotation", "Single-Leg"]) == "Lunge"
        # Carry outranks Core.
        assert progression_pattern(["Anti-Rotation", "Carry"]) == "Carry"
        # Squat outranks everything.
        assert progression_pattern(["Core", "Hinge", "Squat"]) == "Squat"

    def test_all_unmapped_multi_falls_back(self):
        assert progression_pattern(["Abduction"]) == "Various"

    def test_every_crosswalk_target_is_a_real_progression_rule(self):
        # The crosswalk must only emit keys that PROGRESSION_RULES knows, else
        # the engine silently falls to Various and the mapping is dead.
        for target in set(_LAYER0_TO_PROGRESSION.values()):
            assert target in PROGRESSION_RULES, target

    def test_fallback_various_is_a_real_rule(self):
        assert "Various" in PROGRESSION_RULES
