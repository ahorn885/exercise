"""Tests for the wellness/sleep/body/zone metric-key crosswalk (#681 §4).

Transcribed from `specs/Provider_Inbound_Matrix_v2.md` §2.3 (Strava body), §3
(WHOOP), §4 (Oura) into `provider_value_map_seed.WELLNESS_VALUE_MAP`. These rows
are dormant until the providers are live-wired (workstream B); the tests guard
transcription fidelity + the three matrix-flagged build decisions + the
`provider_value_map` row shape.
"""

from provider_value_map_seed import WELLNESS_VALUE_MAP, provider_value_map_rows

# The ratified §2.3 canonical metric-key registry (parent
# Provider_Data_Translation_Layer_Spec §2.3) + the §6 reconciliation that adds
# `steps` (consumed in §6.3 COROS but omitted from the §2.3 table). No code-level
# registry module exists, so this set is the test's SSOT for "is a real key" —
# the metric analogue of the cardio test's CANONICAL_NAMES D-id check.
METRIC_KEY_REGISTRY = {
    "resting_hr_bpm", "hr_avg_bpm", "hr_peak_bpm", "hrv_rmssd_ms",
    "sleep_total_min", "sleep_deep_min", "sleep_rem_min", "sleep_light_min",
    "sleep_score", "body_mass_kg", "body_fat_pct",
    "vo2max_running", "vo2max_cycling", "ftp_w",
    "resting_metabolic_rate_kcal", "respiration_rate_brpm", "spo2_pct",
    "steps",
}

ZONE_LABELS = {"Z1", "Z2", "Z3", "Z4", "Z5"}

WELLNESS_DATA_TYPES = {"sleep", "wellness", "body", "zone"}


def _wellness_rows():
    return [r for r in provider_value_map_rows() if r[1] in WELLNESS_DATA_TYPES]


class TestWellnessRowShape:
    def test_every_bucket1_metric_key_is_a_real_registry_key(self):
        for prov, dtype, src, kind, val, conf, _notes in WELLNESS_VALUE_MAP:
            if val is None:
                continue  # bucket-2 (proprietary) — no canonical target
            if kind == "metric_key":
                assert val in METRIC_KEY_REGISTRY, f"{prov}/{src} → unknown key {val}"
            elif kind == "zone":
                assert val in ZONE_LABELS, f"{prov}/{src} → bad zone {val}"
            else:
                raise AssertionError(f"unexpected canonical_kind {kind}")

    def test_generated_rows_match_table_columns_and_direction(self):
        rows = _wellness_rows()
        assert rows, "no wellness rows generated"
        for r in rows:
            assert len(r) == 10
            provider, data_type, direction = r[0], r[1], r[2]
            kind, value, match_kind, conf, no_match = r[4], r[5], r[6], r[7], r[8]
            assert direction == "in"
            assert match_kind == "manual"
            assert kind in {"metric_key", "zone"}
            # no_canonical_match is TRUE iff there's no canonical target (bucket-2)
            assert no_match is (value is None)

    def test_rows_unique_on_primary_key(self):
        # PK = (provider, data_type, direction, source_value). Guards against a
        # collision with the strength/cardio rows too (full generator scanned).
        pks = [(r[0], r[1], r[2], r[3]) for r in provider_value_map_rows()]
        assert len(pks) == len(set(pks))


class TestFlaggedBuildDecisions:
    """The three decisions the matrix left for the build (§3.2, §3.4, §5)."""

    def test_whoop_sleep_total_is_derived_not_mapped_from_in_bed(self):
        by_src = {(r[0], r[1], r[3]): r for r in provider_value_map_rows()}
        # in-bed is recorded raw (bucket-2), NOT mapped to sleep_total_min
        in_bed = by_src[("whoop", "sleep", "total_in_bed_time_milli")]
        assert in_bed[5] is None and in_bed[8] is True
        # the three stages ARE mapped (sleep_total_min derived from their sum)
        for src, key in [
            ("total_slow_wave_sleep_time_milli", "sleep_deep_min"),
            ("total_rem_sleep_time_milli", "sleep_rem_min"),
            ("total_light_sleep_time_milli", "sleep_light_min"),
        ]:
            assert by_src[("whoop", "sleep", src)][5] == key
        # no WHOOP row maps directly to sleep_total_min
        assert not any(r[5] == "sleep_total_min" for r in provider_value_map_rows()
                       if r[0] == "whoop")

    def test_sleep_score_comes_from_oura_not_whoop(self):
        rows = list(provider_value_map_rows())
        oura = next(r for r in rows if r[0] == "oura" and r[3] == "daily_sleep.score")
        assert oura[5] == "sleep_score"
        whoop_perf = next(r for r in rows
                          if r[0] == "whoop" and r[3] == "sleep_performance_percentage")
        assert whoop_perf[5] is None and whoop_perf[8] is True
        # WHOOP never maps anything to sleep_score
        assert not any(r[5] == "sleep_score" for r in rows if r[0] == "whoop")

    def test_whoop_hr_zone_binding_is_flagged_as_inference(self):
        zone_rows = [r for r in provider_value_map_rows()
                     if r[0] == "whoop" and r[1] == "zone" and r[5] in ZONE_LABELS]
        assert len(zone_rows) == 5
        for r in zone_rows:
            assert r[7] == 0.9, "zone_one..five=Z1..Z5 is an inference → confidence 0.9"
        # zone_zero has no canonical zone
        z0 = next(r for r in provider_value_map_rows()
                  if r[0] == "whoop" and r[3] == "zone_zero_milli")
        assert z0[5] is None and z0[8] is True


class TestTranscriptionFidelity:
    def test_representative_bucket1_rows(self):
        by_key = {(r[0], r[1], r[3]): r for r in provider_value_map_rows()}
        # WHOOP HRV: ms despite the _milli suffix
        assert by_key[("whoop", "wellness", "hrv_rmssd_milli")][5] == "hrv_rmssd_ms"
        # Oura RHR is sleep.lowest_heart_rate (NOT the readiness contributor)
        assert by_key[("oura", "sleep", "lowest_heart_rate")][5] == "resting_hr_bpm"
        # Strava is the ftp_w source
        assert by_key[("strava", "body", "ftp")][5] == "ftp_w"
        # body mass arrives from three providers (one canonical key, precedence at read)
        mass = [r for r in provider_value_map_rows() if r[5] == "body_mass_kg"]
        assert {r[0] for r in mass} >= {"strava", "whoop", "oura"}

    def test_oura_vo2max_fills_running_only(self):
        by_key = {(r[0], r[3]): r for r in provider_value_map_rows()}
        assert by_key[("oura", "vO2_max.vo2_max")][5] == "vo2max_running"
        assert not any(r[5] == "vo2max_cycling" for r in provider_value_map_rows())

    def test_proprietary_scores_are_bucket2(self):
        rows = list(provider_value_map_rows())
        for prov, src in [("whoop", "recovery_score"), ("whoop", "strain"),
                          ("oura", "daily_readiness.score"), ("oura", "efficiency")]:
            r = next(x for x in rows if x[0] == prov and x[3] == src)
            assert r[5] is None and r[8] is True, f"{prov}/{src} should be bucket-2"
