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
    LOGGED_NAME_ALIASES,
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

    def test_batch_a_ratified_aliases_resolve(self):
        # Andy's Batch A sign-off (2026-06-17). Spot-checks across the set,
        # including the ones whose coarse category-collapse would otherwise
        # flatten specificity (Goblet/Front Squat → Squat; Good Morning → no
        # coarse home; Wall Slide → no coarse home).
        cases = {
            "Goblet Squat": "EX002",
            "Barbell Front Squat": "EX231",
            "Thoracic Rotation": "EX016",
            "Face Pull": "EX081",
            "Seated Barbell Good Morning": "EX061",
            "Single Leg Barbell Good Morning": "EX061",
            "Barbell Reverse Wrist Curl": "EX111",
            "Weighted Bicycle Crunch": "EX224",
            "Barbell Bulgarian Split Squat": "EX021",
            "Wall Slide": "EX065",
        }
        for name, ex_id in cases.items():
            assert resolve_strength_ex_id(name) == (ex_id, "alias"), name


class TestLoggedVocabularyAliases:
    """Andy's current_rx vocabulary → EX-id, mapped on the "map them all"
    greenlight (2026-06-17). These resolve via the alias step."""

    def test_logged_vocab_resolves_via_alias(self):
        cases = {
            "Bent-Over Barbell Row": "EX246",
            "Front Squat": "EX231",
            "Romanian Deadlift": "EX003",
            "Good Morning": "EX061",
            "Lat Pulldown": "EX080",
            "Pallof Press": "EX011",
            "Push-Up": "EX228",
            "Pull-Up": "EX006",
            "Deadlift (Standard)": "EX230",
            "Turkish Get-Up": "EX239",
        }
        for name, ex_id in cases.items():
            assert resolve_strength_ex_id(name) == (ex_id, "alias"), name

    def test_keyspaces_are_disjoint_or_agree(self):
        # A name appearing in more than one alias map must map to the SAME EX-id,
        # so the merge order in _alias_map() can never silently override.
        maps = {"NAME_TO_EX_ID": NAME_TO_EX_ID,
                "GARMIN": GARMIN_STRENGTH_ALIASES,
                "LOGGED": LOGGED_NAME_ALIASES}
        seen: dict[str, str] = {}
        for label, m in maps.items():
            for name, ex_id in m.items():
                if name in seen:
                    assert seen[name] == ex_id, f"{name}: {seen[name]} vs {ex_id} ({label})"
                seen[name] = ex_id


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
