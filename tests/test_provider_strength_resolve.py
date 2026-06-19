"""Tests for the #679 Garmin strength name → layer0 EX-id resolver
(`provider_strength_resolve.resolve_strength_ex_id`).

Covers the three-step chain (design §3.1): exact alias (specificity preserved),
coarse category-collapse backstop, and the bucket-3 record-don't-drop fallback.
The category step is exercised both with an injected reverse map (hermetic) and
against the real `garmin_fit_parser` map (end-to-end name→category→EX-id guard).
"""

from __future__ import annotations

from provider_strength_resolve import resolve_strength_ex_id

# The strength maps now live in the consolidated provider seed (#681 §4); the
# coarse map is aliased to its former name to keep these assertions unchanged.
from provider_value_map_seed import (
    GARMIN_STRENGTH_ALIASES,
    LOGGED_NAME_ALIASES,
    STRENGTH_COARSE_NAME_TO_EX_ID as NAME_TO_EX_ID,
)


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

    def test_new_exercise_names_resolve_to_new_ex_ids(self):
        # The 40 exercises minted in migrations 0012-0015 resolve from their
        # logged/Garmin names (alias step). Spot-check across all four slices.
        cases = {
            "Walking Lunge": "EX250",            # 0012
            "Barbell Hack Squat": "EX252",       # 0012 (Garmin name)
            "KB Sumo Deadlift": "EX254",         # 0012 (current_rx name)
            "Single-Leg Glute Bridge": "EX255",  # 0013
            "Front Lever Progression": "EX264",  # 0013
            "Dip": "EX268",                      # 0014
            "KB Snatch": "EX273",                # 0014
            "Bear-Hug carry source": None,       # placeholder removed below
        }
        cases.pop("Bear-Hug carry source")
        for name, ex_id in cases.items():
            assert resolve_strength_ex_id(name) == (ex_id, "alias"), name

    def test_part3_repoints_and_drops(self):
        # The 5 Part-3 promotions now point at their new EX-ids, not the old
        # nearest-canonical; the 2 drops fall through to bucket-3.
        assert resolve_strength_ex_id("Towel Pull-Up") == ("EX267", "alias")
        assert resolve_strength_ex_id("Plank with Rotation") == ("EX285", "alias")
        assert resolve_strength_ex_id("Sandbag / Pack Carry (Bear Hug)") == ("EX279", "alias")
        # Dropped — no longer aliased (Andy: delete).
        assert resolve_strength_ex_id("1,000 Step-Up Challenge",
                                      subtype_to_category={}) == (None, "bucket3")
        assert resolve_strength_ex_id("Single-Leg Stance Eyes Closed",
                                      subtype_to_category={}) == (None, "bucket3")

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
        # "Calf Raise" category has no coarse NAME_TO_EX_ID home → bucket-3
        # (use a subtype with no specific alias of its own).
        ex_id, kind = resolve_strength_ex_id(
            "Donkey Calf Raise",
            subtype_to_category={"Donkey Calf Raise": "Calf Raise"},
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


class TestProviderValueMapSeed:
    """The consolidated seed (#681 §4 Slice 1) that both the resolver imports and
    init_db materializes into the `provider_value_map` table."""

    def test_rows_cover_every_strength_and_cardio_entry(self):
        from provider_value_map_seed import (
            provider_value_map_rows,
            STRENGTH_NAME_TO_EX_ID,
            GARMIN_TYPE_TO_PLAN_SPORT,
        )
        rows = list(provider_value_map_rows())
        strength = {r[3]: r for r in rows if r[1] == "strength"}
        # Cardio now spans multiple providers (Slice 2 CARDIO_DISCIPLINE_MAP);
        # the Garmin coarse map (Slice 1) is the garmin-provider subset.
        garmin_cardio = {r[3]: r for r in rows if r[1] == "cardio" and r[0] == "garmin"}
        assert set(strength) == set(STRENGTH_NAME_TO_EX_ID)
        assert set(garmin_cardio) == set(GARMIN_TYPE_TO_PLAN_SPORT)
        for name, ex_id in STRENGTH_NAME_TO_EX_ID.items():
            assert strength[name] == (
                "garmin", "strength", "in", name, "ex_id", ex_id, "manual", 1.0, False, None)
        for type_key, sport in GARMIN_TYPE_TO_PLAN_SPORT.items():
            assert garmin_cardio[type_key] == (
                "garmin", "cardio", "in", type_key, "modality", sport, "manual", 1.0, False, None)

    def test_rows_are_unique_on_the_table_primary_key(self):
        from provider_value_map_seed import provider_value_map_rows
        pks = [(r[0], r[1], r[2], r[3]) for r in provider_value_map_rows()]
        assert len(pks) == len(set(pks)), "duplicate (provider,data_type,direction,source_value)"

    def test_merged_strength_map_matches_resolver(self):
        # The map the resolver reads IS the seed's merged map (no drift).
        from provider_value_map_seed import STRENGTH_NAME_TO_EX_ID
        for name, ex_id in STRENGTH_NAME_TO_EX_ID.items():
            assert resolve_strength_ex_id(name) == (ex_id, "alias"), name
