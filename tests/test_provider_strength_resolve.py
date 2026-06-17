"""Tests for the #679 Garmin strength name → layer0 EX-id resolver
(`provider_strength_resolve.resolve_strength_ex_id`).

Covers the three-step chain (design §3.1): exact alias (specificity preserved),
coarse category-collapse backstop, and the bucket-3 record-don't-drop fallback.
The category step is exercised both with an injected reverse map (hermetic) and
against the real `garmin_fit_parser` map (end-to-end name→category→EX-id guard).
"""

from __future__ import annotations

from provider_strength_resolve import (
    resolve_strength_ex_id,
    GARMIN_STRENGTH_ALIASES,
)
from layer0_progression import NAME_TO_EX_ID


class TestAliasStep:
    def test_curated_coarse_name_resolves_via_alias(self):
        # NAME_TO_EX_ID coarse entries fold into the alias map.
        assert resolve_strength_ex_id("Squat") == ("EX001", "alias")
        assert resolve_strength_ex_id("Bench Press") == ("EX229", "alias")

    def test_garmin_specific_resolves_to_specific_ex_id(self):
        assert resolve_strength_ex_id("Single Arm Dumbbell Bench Press") == ("EX242", "alias")
        assert resolve_strength_ex_id("Wide Grip Lat Pulldown") == ("EX080", "alias")

    def test_alias_preserves_specificity_over_coarse_collapse(self):
        # "Dumbbell Hammer Curl" must hit the specific hammer-curl EX234 via the
        # alias step, NOT collapse to the coarse "Curl" -> EX247.
        ex_id, kind = resolve_strength_ex_id("Dumbbell Hammer Curl")
        assert (ex_id, kind) == ("EX234", "alias")
        assert NAME_TO_EX_ID["Curl"] == "EX247"  # the coarse home it must beat

    def test_alias_step_wins_even_if_a_category_map_would_match(self):
        # Inject a reverse map that would route the name elsewhere; alias wins.
        ex_id, kind = resolve_strength_ex_id(
            "Seated Calf Raise",
            subtype_to_category={"Seated Calf Raise": "Squat"},
        )
        assert (ex_id, kind) == ("EX026", "alias")


class TestCategoryStep:
    def test_specific_subtype_collapses_to_coarse_ex_id(self):
        # No alias for "Barbell Bench Press"; its FIT category is "Bench Press",
        # which has a coarse home (EX229).
        ex_id, kind = resolve_strength_ex_id(
            "Barbell Bench Press",
            subtype_to_category={"Barbell Bench Press": "Bench Press"},
        )
        assert (ex_id, kind) == ("EX229", "category")

    def test_category_with_no_coarse_home_falls_to_bucket3(self):
        # "Calf Raise" category has no coarse NAME_TO_EX_ID home → bucket-3.
        ex_id, kind = resolve_strength_ex_id(
            "Standing Calf Raise",
            subtype_to_category={"Standing Calf Raise": "Calf Raise"},
        )
        assert ex_id is None and kind == "bucket3"

    def test_real_garmin_map_collapses_barbell_bench_press(self):
        # End-to-end against the real garmin_fit_parser reverse map (fit_tool):
        # a specific bench-press subtype with no alias collapses to EX229.
        ex_id, kind = resolve_strength_ex_id("Barbell Bench Press")
        assert (ex_id, kind) == ("EX229", "category")


class TestBucket3Step:
    def test_unknown_name_is_bucket3(self):
        assert resolve_strength_ex_id("Totally Made Up Lift",
                                      subtype_to_category={}) == (None, "bucket3")

    def test_empty_name_is_bucket3(self):
        assert resolve_strength_ex_id("") == (None, "bucket3")
        assert resolve_strength_ex_id(None) == (None, "bucket3")


class TestSeedIntegrity:
    def test_seed_aliases_do_not_silently_shadow_a_different_curated_entry(self):
        # Any key that also exists in NAME_TO_EX_ID must map to the same EX-id
        # (the merge lets a Garmin entry win, so a divergence would be a silent
        # override — guard against authoring one by accident).
        for name, ex_id in GARMIN_STRENGTH_ALIASES.items():
            if name in NAME_TO_EX_ID:
                assert NAME_TO_EX_ID[name] == ex_id, name

    def test_seed_excludes_redundant_name_to_ex_id_duplicates(self):
        # Entries already verbatim in NAME_TO_EX_ID are intentionally omitted.
        for name in ("Dead Bug", "Side Plank", "Sit Up"):
            assert name not in GARMIN_STRENGTH_ALIASES
