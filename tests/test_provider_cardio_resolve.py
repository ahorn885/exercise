"""Tests for the cardio activity-type → canonical discipline resolver (#681 §4 Slice 2).

Covers the matrix-v2 §1 option-C resolution (fine D-id + deterministic coarse
collapse), the seed crosswalk's transcription fidelity (every authored D-id is a
real canonical discipline), and the `provider_value_map` row shape.
"""

from etl.layer0.discipline_canon import CANONICAL_NAMES

from provider_value_map_seed import CARDIO_DISCIPLINE_MAP, provider_value_map_rows
from provider_cardio_resolve import (
    DISCIPLINE_TO_PLAN_SPORT,
    CardioResolution,
    resolve_cardio_discipline,
)

# The 6 coarse `_plan_sport_type` values (garmin_connect / GARMIN_TYPE_TO_PLAN_SPORT).
COARSE_VALUES = {"running", "cycling", "swimming", "strength_training", "hiking", "walking"}


class TestResolveCardioDiscipline:
    def test_strava_fine_discipline_with_coarse_collapse(self):
        # TrailRun → D-001 (fine) → running (coarse), bucket 1.
        assert resolve_cardio_discipline("strava", "TrailRun") == CardioResolution(
            "D-001", "running", 1, "manual")

    def test_fine_only_discipline_has_no_coarse(self):
        # Kayaking → D-010, no coarse home (the paddle signal the 6-value set drops).
        assert resolve_cardio_discipline("strava", "Kayaking") == CardioResolution(
            "D-010", None, 1, "manual")
        # BackcountrySki → D-021 (the skimo signal), fine-only.
        assert resolve_cardio_discipline("strava", "BackcountrySki") == CardioResolution(
            "D-021", None, 1, "manual")

    def test_coarse_only_modality(self):
        # Walk → no race D-id, coarse 'walking' only, bucket 1.
        assert resolve_cardio_discipline("strava", "Walk") == CardioResolution(
            None, "walking", 1, "manual")
        assert resolve_cardio_discipline("strava", "WeightTraining") == CardioResolution(
            None, "strength_training", 1, "manual")

    def test_explicit_bucket3_records_match_kind(self):
        # Rowing — mint reversed (§6/§12): explicitly known-unmapped, bucket 3.
        assert resolve_cardio_discipline("strava", "Rowing") == CardioResolution(
            None, None, 3, "manual")

    def test_unmapped_type_is_bucket3_with_no_match_kind(self):
        # Anything not in the seed → bucket 3, record-don't-drop, never raises.
        assert resolve_cardio_discipline("strava", "Pickleball") == CardioResolution(
            None, None, 3, None)
        assert resolve_cardio_discipline("strava", None) == CardioResolution(
            None, None, 3, None)
        assert resolve_cardio_discipline("nonesuch", "Run") == CardioResolution(
            None, None, 3, None)

    def test_provider_key_is_case_insensitive(self):
        assert resolve_cardio_discipline("STRAVA", "Run").discipline_id == "D-002"

    def test_rwgps_namespaced_and_walking_split(self):
        assert resolve_cardio_discipline("rwgps", "cycling:gravel").discipline_id == "D-030"
        assert resolve_cardio_discipline("rwgps", "walking:hiking").discipline_id == "D-003"
        # walking:generic is a coarse-only walk, not Trekking.
        assert resolve_cardio_discipline("rwgps", "walking:generic") == CardioResolution(
            None, "walking", 1, "manual")

    def test_wahoo_numeric_id_keys(self):
        assert resolve_cardio_discipline("wahoo", "4").discipline_id == "D-001"   # RUNNING_TRAIL
        assert resolve_cardio_discipline("wahoo", "13").discipline_id == "D-008"  # BIKING_MOUNTAIN
        assert resolve_cardio_discipline("wahoo", "39") == CardioResolution(
            None, None, 3, "manual")                                              # ROWING

    def test_trainingpeaks_workout_type(self):
        assert resolve_cardio_discipline("trainingpeaks", "mtb").discipline_id == "D-008"
        # No road/trail split → run collapses to road running D-002, not trail D-001.
        assert resolve_cardio_discipline("trainingpeaks", "run").discipline_id == "D-002"

    def test_garmin_fine_discipline(self):
        # The wired path (Slice 2b): typeKey / FIT-refined token → fine D-id.
        assert resolve_cardio_discipline("garmin", "trail_running").discipline_id == "D-001"
        assert resolve_cardio_discipline("garmin", "mountain_biking").discipline_id == "D-008"
        assert resolve_cardio_discipline("garmin", "gravel_cycling").discipline_id == "D-030"
        assert resolve_cardio_discipline("garmin", "walking") == CardioResolution(
            None, "walking", 1, "manual")
        assert resolve_cardio_discipline("garmin", "rowing") == CardioResolution(
            None, None, 3, "manual")


class TestGarminCoarsePathConsistency:
    def test_fine_collapse_agrees_with_legacy_coarse_dict(self):
        # GARMIN_TYPE_TO_PLAN_SPORT still drives `_plan_sport_type` (live plan
        # matching); the new fine D-id must collapse back to the SAME coarse value
        # for every Garmin typeKey, or the two paths would disagree.
        from provider_value_map_seed import GARMIN_TYPE_TO_PLAN_SPORT
        for type_key, coarse in GARMIN_TYPE_TO_PLAN_SPORT.items():
            res = resolve_cardio_discipline("garmin", type_key)
            assert res.plan_sport_type == coarse, (type_key, res.plan_sport_type, coarse)

    def test_fit_sub_sport_refines_to_fine_token(self):
        from garmin_fit_parser import _garmin_disc_token
        assert _garmin_disc_token("running", "trail_running") == "trail_running"
        assert _garmin_disc_token("running", "treadmill") == "running"
        assert _garmin_disc_token("cycling", "mountain") == "mountain_biking"
        assert _garmin_disc_token("cycling", "gravel_cycling") == "gravel_cycling"
        assert _garmin_disc_token("cycling", "spin") == "indoor_cycling"
        assert _garmin_disc_token("swimming", "open_water") == "open_water_swimming"
        assert _garmin_disc_token("hiking", "") == "hiking"
        # A trail run resolves all the way to D-001 (the signal coarse would drop).
        assert resolve_cardio_discipline(
            "garmin", _garmin_disc_token("running", "trail_running")).discipline_id == "D-001"


class TestSeedTranscriptionIntegrity:
    def test_every_authored_discipline_is_a_real_canonical_id(self):
        # Guards the matrix→seed transcription against a typo'd / retired D-id.
        for provider, mapping in CARDIO_DISCIPLINE_MAP.items():
            for source_value, (kind, value) in mapping.items():
                if kind == "discipline":
                    assert value in CANONICAL_NAMES, f"{provider}:{source_value}={value}"

    def test_modality_values_are_known_coarse(self):
        for provider, mapping in CARDIO_DISCIPLINE_MAP.items():
            for source_value, (kind, value) in mapping.items():
                if kind == "modality":
                    assert value in COARSE_VALUES, f"{provider}:{source_value}={value}"

    def test_bucket3_entries_carry_no_value(self):
        for provider, mapping in CARDIO_DISCIPLINE_MAP.items():
            for source_value, (kind, value) in mapping.items():
                if kind == "bucket3":
                    assert value is None, f"{provider}:{source_value}"

    def test_collapse_targets_and_values_are_valid(self):
        # Every collapse key is a real D-id; every coarse target is a known value.
        for d_id, coarse in DISCIPLINE_TO_PLAN_SPORT.items():
            assert d_id in CANONICAL_NAMES, d_id
            assert coarse in COARSE_VALUES, coarse

    def test_running_cycling_swimming_disciplines_collapse(self):
        # Any authored discipline whose coarse home exists must resolve to it
        # (no fine running/cycling/swimming/hiking activity left coarse-less).
        for provider, mapping in CARDIO_DISCIPLINE_MAP.items():
            for source_value, (kind, value) in mapping.items():
                if kind != "discipline":
                    continue
                res = resolve_cardio_discipline(provider, source_value)
                assert res.discipline_id == value
                assert res.bucket == 1


class TestProviderValueMapRows:
    def test_cardio_discipline_rows_are_present_and_shaped(self):
        rows = [r for r in provider_value_map_rows()
                if r[1] == "cardio" and r[0] != "garmin"]
        by_key = {(r[0], r[3]): r for r in rows}
        # bucket-1 fine discipline
        assert by_key[("strava", "TrailRun")] == (
            "strava", "cardio", "in", "TrailRun", "discipline", "D-001",
            "manual", 1.0, False, None)
        # coarse-only modality
        assert by_key[("strava", "Walk")] == (
            "strava", "cardio", "in", "Walk", "modality", "walking",
            "manual", 1.0, False, None)
        # explicit bucket-3 → no_canonical_match True, canonical_value None
        assert by_key[("strava", "Rowing")] == (
            "strava", "cardio", "in", "Rowing", "discipline", None,
            "manual", 1.0, True, None)

    def test_cardio_rows_unique_per_provider(self):
        keys = [(r[0], r[1], r[2], r[3]) for r in provider_value_map_rows()
                if r[1] == "cardio"]
        assert len(keys) == len(set(keys))
