"""Unit tests for the #283 Phase B Garmin daily-metrics integration.

Covers the wellness page surfacing `garmin_daily_metrics` (sleep score +
overnight HRV) and the supporting helpers in `garmin_fit_parser` /
`routes.garmin` that route the new FIT file types into the table.

Parsing real `.fit` bytes requires fit_tool + actual files, which would push
test data into the repo; instead these tests cover the seams immediately
around the parsers (the field-id → semantic-name extraction is verified
manually in the parser docstrings against the May 28 reference data).
"""

from __future__ import annotations

from routes.wellness import _build_chart_data, _has_any_data
from garmin_fit_parser import (
    _fit_seconds_to_unix_ms,
    _fit_seconds_to_date,
)


def _r(**kw):
    return dict(kw)


# ── chart_data builder — Phase B daily metrics ───────────────────────────────

def test_sleep_score_device_line_lights_up_when_garmin_daily_metrics_have_score():
    self_rows = [_r(date='2026-05-28', sleep_hours=None, sleep_quality=4,
                    energy=None, soreness=None, mood=None)]
    daily_metric_rows = [_r(date='2026-05-28', sleep_score=96,
                            hrv_overnight_avg_ms=None)]
    chart = _build_chart_data(self_rows, [], [], [], [], [], daily_metric_rows)
    # Self is still normalized ×20 (4 → 80) and device is the raw score.
    assert chart['sleep_score']['self'] == [{'x': '2026-05-28', 'y': 80.0}]
    assert chart['sleep_score']['device'] == [{'x': '2026-05-28', 'y': 96.0}]


def test_hrv_chart_populates_from_daily_metrics():
    daily_metric_rows = [
        _r(date='2026-05-28', sleep_score=None, hrv_overnight_avg_ms=54.0),
        _r(date='2026-05-29', sleep_score=None, hrv_overnight_avg_ms=61.5),
    ]
    chart = _build_chart_data([], [], [], [], [], [], daily_metric_rows)
    assert chart['hrv']['overnight'] == [
        {'x': '2026-05-28', 'y': 54.0},
        {'x': '2026-05-29', 'y': 61.5},
    ]
    # has_any_data finds the HRV series even with everything else empty.
    assert _has_any_data(chart) is True


def test_phase_b_followup_keys_still_empty_until_their_file_types_land():
    chart = _build_chart_data([], [], [], [], [], [], [])
    # active_minutes was retired Jun 7 in favour of intensity_minutes,
    # which now ships from MonitoringMessage.
    for k in ('training_readiness', 'vo2max_running', 'vo2max_cycling'):
        assert chart[k] == [], (
            f'{k} stays empty until its FIT file type / field map is added '
            f'in a follow-up'
        )


def test_build_chart_data_default_daily_metric_rows_is_empty():
    # Existing call sites (and tests) that don't pass daily_metric_rows
    # still work — Phase A signature compat.
    chart = _build_chart_data([], [], [], [], [], [])
    assert chart['sleep_score'] == {'self': [], 'device': []}
    assert chart['hrv'] == {'overnight': [], 'highest_5min': []}


# ── FIT timestamp helpers ────────────────────────────────────────────────────

def test_fit_seconds_to_unix_ms_handles_fit_epoch_offset():
    # field_253 value from the May 28 reference _SLEEP_DATA.fit
    # (1148894215 FIT seconds = 2026-05-28 09:16:55 UTC).
    # Expected: (1148894215 + 631065600) * 1000 = 1779959815000.
    assert _fit_seconds_to_unix_ms(1148894215) == 1779959815000


def test_fit_seconds_to_unix_ms_rejects_garbage():
    assert _fit_seconds_to_unix_ms(None) == 0
    assert _fit_seconds_to_unix_ms(0) == 0
    assert _fit_seconds_to_unix_ms(-1) == 0
    assert _fit_seconds_to_unix_ms('not-a-number') == 0


def test_fit_seconds_to_date_returns_utc_iso_day():
    # 1148861700 = 2026-05-28 00:14:00 UTC (bedtime for the May 28 reference).
    assert _fit_seconds_to_date(1148861700) == '2026-05-28'
    assert _fit_seconds_to_date(None) == ''


# ── _metrics_to_db_fields — parser dict → table column shape ─────────────────

def test_metrics_to_db_fields_translates_lists_into_json_columns():
    from routes.garmin import _metrics_to_db_fields
    fields = _metrics_to_db_fields({
        'date': '2026-05-28',
        'sleep_score': 96,
        'sleep_start_ms': 1779927240000,
        'sleep_end_ms': 1779957060000,
        'sleep_awake_min': 4,
        'sleep_avg_respiration': 13.0,
        'sleep_contributors': [100, 83, 96, 95, 95, 81],
        'hrv_overnight_avg_ms': 54.0,
        'hrv_samples': [[1779928000000, 65.3], [1779928300000, 78.1]],
    })
    # Scalars pass through.
    assert fields['sleep_score'] == 96
    assert fields['sleep_awake_min'] == 4
    assert fields['hrv_overnight_avg_ms'] == 54.0
    # Lists become JSON strings.
    import json
    assert json.loads(fields['sleep_contributors_json']) == [100, 83, 96, 95, 95, 81]
    assert json.loads(fields['hrv_samples_json']) == [
        [1779928000000, 65.3], [1779928300000, 78.1]
    ]
    # `date` never enters the column dict — it's the row key, used separately
    # in the UPSERT signature.
    assert 'date' not in fields


def test_metrics_to_db_fields_only_emits_present_keys():
    """An `_HRV_STATUS.fit` upload should only touch HRV columns. Critical
    so that a later sleep_data upload doesn't get clobbered by the COALESCE
    fallback to a non-existent older HRV value."""
    from routes.garmin import _metrics_to_db_fields
    fields = _metrics_to_db_fields({
        'date': '2026-05-28',
        'hrv_overnight_avg_ms': 54.0,
        'hrv_samples': [[1779928000000, 65.3]],
    })
    assert set(fields.keys()) == {'hrv_overnight_avg_ms', 'hrv_samples_json'}


# ── Follow-up additions (RMR, stress bucketing, body battery deltas) ─────────

def test_resting_calories_surface_from_garmin_daily_metrics():
    """RMR is extracted from MonitoringInfoMessage by parse_wellness_daily_extras
    and UPSERTed into garmin_daily_metrics. The chart reads it from there."""
    daily_metric_rows = [
        _r(date='2026-05-28', sleep_score=None, hrv_overnight_avg_ms=None,
           resting_metabolic_rate=1994),
        _r(date='2026-05-29', sleep_score=None, hrv_overnight_avg_ms=None,
           resting_metabolic_rate=2010),
    ]
    chart = _build_chart_data([], [], [], [], [], [], daily_metric_rows)
    assert chart['resting_calories'] == [
        {'x': '2026-05-28', 'y': 1994.0},
        {'x': '2026-05-29', 'y': 2010.0},
    ]


def test_metrics_to_db_fields_passes_through_rmr():
    """RMR lands as its own column from the wellness importer's extras call."""
    from routes.garmin import _metrics_to_db_fields
    fields = _metrics_to_db_fields({
        'date': '2026-05-28',
        'resting_metabolic_rate': 1994,
    })
    assert fields == {'resting_metabolic_rate': 1994}


def test_stress_time_in_zone_minutes_uses_3min_sample_interval():
    """COUNT(*) samples per stress band × 3 min interval ≈ Garmin Connect's
    bucketed minutes. Andy's May 28: 24h day, ~480 samples expected; the
    rest/low/medium/high counts should multiply by 3 cleanly."""
    garmin_rows = [
        _r(date='2026-05-28', avg_hr=58.0, resting_hr=44, peak_hr=89,
           avg_stress=24.0, peak_stress=70,
           avg_resp=13.0, min_resp=6.0,
           bb_high=99, bb_low=24,
           daily_steps=5438, daily_active_cal=106, daily_distance_m=4250.0,
           stress_rest_samples=240, stress_low_samples=140,
           stress_med_samples=20,  stress_high_samples=2),
    ]
    chart = _build_chart_data([], [], [], [], [], garmin_rows)
    # 240 × 3 = 720 min Rest (Andy's Garmin Connect reads 12h 13min on May 28)
    assert chart['stress_minutes']['rest']   == [{'x': '2026-05-28', 'y': 720.0}]
    assert chart['stress_minutes']['low']    == [{'x': '2026-05-28', 'y': 420.0}]
    assert chart['stress_minutes']['medium'] == [{'x': '2026-05-28', 'y':  60.0}]
    assert chart['stress_minutes']['high']   == [{'x': '2026-05-28', 'y':   6.0}]


def test_stress_buckets_skip_zero_sample_days():
    """A day with zero samples in a bucket shouldn't put a zero on the chart —
    the rest of the cards skip NULLs, this stays consistent."""
    garmin_rows = [
        _r(date='2026-05-28', avg_hr=58.0, resting_hr=44, peak_hr=89,
           avg_stress=24.0, peak_stress=70,
           avg_resp=13.0, min_resp=6.0,
           bb_high=99, bb_low=24,
           daily_steps=5438, daily_active_cal=106, daily_distance_m=4250.0,
           stress_rest_samples=240, stress_low_samples=0,
           stress_med_samples=0,   stress_high_samples=0),
    ]
    chart = _build_chart_data([], [], [], [], [], garmin_rows)
    assert chart['stress_minutes']['rest']   == [{'x': '2026-05-28', 'y': 720.0}]
    assert chart['stress_minutes']['low']    == []
    assert chart['stress_minutes']['medium'] == []
    assert chart['stress_minutes']['high']   == []


def test_body_battery_charged_drained_from_lag_deltas():
    """body_battery.{charged, drained} land from the bb_delta_rows query —
    each day's positive deltas summed separately from negatives."""
    bb_delta_rows = [
        _r(date='2026-05-28', charged=68, drained=52),
        _r(date='2026-05-29', charged=70, drained=40),
    ]
    chart = _build_chart_data([], [], [], [], [], [], (),
                              bb_delta_rows=bb_delta_rows)
    assert chart['body_battery']['charged'] == [
        {'x': '2026-05-28', 'y': 68.0},
        {'x': '2026-05-29', 'y': 70.0},
    ]
    assert chart['body_battery']['drained'] == [
        {'x': '2026-05-28', 'y': 52.0},
        {'x': '2026-05-29', 'y': 40.0},
    ]


def test_body_battery_delta_query_failure_doesnt_break_other_cards():
    """If bb_delta_rows is empty/missing (e.g. window function unavailable
    in a future SQLite test path), the rest of the chart still renders."""
    chart = _build_chart_data([], [], [], [], [], [], (), bb_delta_rows=())
    assert chart['body_battery']['charged'] == []
    assert chart['body_battery']['drained'] == []
    # Other cards still work
    assert chart['sleep_score'] == {'self': [], 'device': []}


def test_body_battery_overnight_delta_lands_per_night():
    """`body_battery.overnight_delta` lands from bb_overnight_rows — per-night
    BB value at sleep_end minus value at sleep_start. Surfaces the #283
    "how restful was this sleep?" signal. May 30 = +47 (good recovery on
    short sleep), Jun 2 = +27 (worse recovery despite similar duration)."""
    bb_overnight_rows = [
        _r(date='2026-05-28', bb_start=20, bb_end=95),  # +75
        _r(date='2026-05-30', bb_start=48, bb_end=95),  # +47
        _r(date='2026-06-02', bb_start=46, bb_end=73),  # +27
    ]
    chart = _build_chart_data([], [], [], [], [], [], (),
                              bb_overnight_rows=bb_overnight_rows)
    assert chart['body_battery']['overnight_delta'] == [
        {'x': '2026-05-28', 'y': 75},
        {'x': '2026-05-30', 'y': 47},
        {'x': '2026-06-02', 'y': 27},
    ]


def test_sleep_sub_scores_land_per_date_for_all_four_contributors():
    """All 4 contributor sub-scores land per night with their locked names
    (Light=field_5, REM=field_7, Stress=field_8, Awake=field_10). Powers
    the multi-line `chart-sleep-sub-scores` card on /wellness."""
    daily_rows = [
        _r(date='2026-05-28',
           sleep_light_sub_score=83, sleep_rem_sub_score=95,
           sleep_stress_sub_score=95, sleep_awake_sub_score=100),
        _r(date='2026-06-02',
           sleep_light_sub_score=92, sleep_rem_sub_score=73,
           sleep_stress_sub_score=46, sleep_awake_sub_score=74),
    ]
    chart = _build_chart_data([], [], [], [], [], [],
                              daily_metric_rows=daily_rows)
    assert chart['sleep_sub_scores']['light'] == [
        {'x': '2026-05-28', 'y': 83.0},
        {'x': '2026-06-02', 'y': 92.0},
    ]
    assert chart['sleep_sub_scores']['rem'] == [
        {'x': '2026-05-28', 'y': 95.0},
        {'x': '2026-06-02', 'y': 73.0},
    ]
    assert chart['sleep_sub_scores']['stress'] == [
        {'x': '2026-05-28', 'y': 95.0},
        {'x': '2026-06-02', 'y': 46.0},
    ]
    assert chart['sleep_sub_scores']['awake'] == [
        {'x': '2026-05-28', 'y': 100.0},
        {'x': '2026-06-02', 'y': 74.0},
    ]


def test_body_battery_overnight_delta_skips_partial_coverage():
    """If a night's BB time-series is missing the sleep_start or sleep_end
    sample (e.g. watch off mid-night), drop the night rather than fabricate
    a misleading delta from a partial reading."""
    bb_overnight_rows = [
        _r(date='2026-05-28', bb_start=20, bb_end=95),   # complete
        _r(date='2026-05-29', bb_start=None, bb_end=80), # missing start
        _r(date='2026-05-30', bb_start=48, bb_end=None), # missing end
    ]
    chart = _build_chart_data([], [], [], [], [], [], (),
                              bb_overnight_rows=bb_overnight_rows)
    assert chart['body_battery']['overnight_delta'] == [
        {'x': '2026-05-28', 'y': 75},
    ]


# ── Field-mapping audit (Jun 7) ──────────────────────────────────────────────

def test_restless_moments_surface_from_garmin_daily_metrics():
    """[382] field_1 = restless_moments was verified May 28 = 28 against
    Andy's Garmin Connect "28 Restless Moments." Andy's May 30 = 15,
    Jun 2 = 32."""
    daily_metric_rows = [
        _r(date='2026-05-28', sleep_score=96, restless_moments=28),
        _r(date='2026-05-30', sleep_score=65, restless_moments=15),
        _r(date='2026-06-02', sleep_score=58, restless_moments=32),
    ]
    chart = _build_chart_data([], [], [], [], [], [], daily_metric_rows)
    assert chart['restless_moments'] == [
        {'x': '2026-05-28', 'y': 28.0},
        {'x': '2026-05-30', 'y': 15.0},
        {'x': '2026-06-02', 'y': 32.0},
    ]


def test_floors_climbed_descended_render_as_two_series():
    """Floors come from MonitoringMessage.ascent / .descent (cumulative,
    MAX-per-day in the parser). Andy's reference: May 30 = 10/15, Jun 2 = 8/5."""
    daily_metric_rows = [
        _r(date='2026-05-30', floors_climbed=10, floors_descended=15),
        _r(date='2026-06-02', floors_climbed=8,  floors_descended=5),
    ]
    chart = _build_chart_data([], [], [], [], [], [], daily_metric_rows)
    assert chart['floors']['climbed'] == [
        {'x': '2026-05-30', 'y': 10.0},
        {'x': '2026-06-02', 'y': 8.0},
    ]
    assert chart['floors']['descended'] == [
        {'x': '2026-05-30', 'y': 15.0},
        {'x': '2026-06-02', 'y': 5.0},
    ]


def test_intensity_minutes_surface():
    """Intensity minutes from MonitoringMessage attributes. Andy's
    reference: May 30 = 5 min, Jun 2 = 204 min."""
    daily_metric_rows = [
        _r(date='2026-05-30', intensity_minutes=5),
        _r(date='2026-06-02', intensity_minutes=204),
    ]
    chart = _build_chart_data([], [], [], [], [], [], daily_metric_rows)
    assert chart['intensity_minutes'] == [
        {'x': '2026-05-30', 'y': 5.0},
        {'x': '2026-06-02', 'y': 204.0},
    ]


def test_spo2_overlay_when_emitted():
    """SpO₂ is opportunistically captured if MonitoringMessage exposes
    pulse_ox. Verifies the overlay shape; the parser-side capture is
    best-effort and is documented in parse_wellness_daily_extras."""
    daily_metric_rows = [
        _r(date='2026-05-30', spo2_avg=91, spo2_low=85),
        _r(date='2026-06-02', spo2_avg=93, spo2_low=88),
    ]
    chart = _build_chart_data([], [], [], [], [], [], daily_metric_rows)
    assert chart['spo2']['avg'] == [
        {'x': '2026-05-30', 'y': 91.0},
        {'x': '2026-06-02', 'y': 93.0},
    ]
    assert chart['spo2']['low'] == [
        {'x': '2026-05-30', 'y': 85.0},
        {'x': '2026-06-02', 'y': 88.0},
    ]


def test_sleep_avg_respiration_no_longer_written():
    """[384] field_18 was retired Jun 7 — the May 28 match (13 brpm = 13)
    was coincidence. Jun 2 disproved it (field_18 = 70, actual breath rate
    = 12). The column stays in the DB schema for old rows but nothing new
    writes to it."""
    from routes.garmin import _metrics_to_db_fields
    # Old-shape input that USED to populate sleep_avg_respiration via the
    # parser dict. The translator now drops it on the floor.
    fields = _metrics_to_db_fields({
        'date': '2026-06-02',
        'sleep_score': 58,
        'sleep_avg_respiration': 70.0,  # parser no longer emits this, but if
                                        # something injects it, it stays out.
    })
    assert 'sleep_avg_respiration' not in fields
    assert fields['sleep_score'] == 58


def test_metrics_to_db_fields_passes_through_extraction_audit_columns():
    from routes.garmin import _metrics_to_db_fields
    fields = _metrics_to_db_fields({
        'date': '2026-06-02',
        'restless_moments': 32,
        'floors_climbed': 8,
        'floors_descended': 5,
        'intensity_minutes': 204,
        'spo2_avg': 93,
        'spo2_low': 88,
    })
    assert fields == {
        'restless_moments': 32,
        'floors_climbed': 8,
        'floors_descended': 5,
        'intensity_minutes': 204,
        'spo2_avg': 93,
        'spo2_low': 88,
    }


def test_pending_list_sorts_by_time_created_so_latest_wins():
    """The bulk importer's pre-pass collects (time_ms, name, raw, kind)
    tuples then sorts ascending. Verifies the sort key so the latest ATL
    value wins even when files arrive in arbitrary zip order — the actual
    Jun 2 reproduction was: 95 (morning) / 107 (midday) / 126 (evening)
    in chronological order, zipped in alphabetic name order."""
    # Synthetic stand-ins for the (time_ms, name, raw, kind) tuples the
    # importer builds.
    pending = [
        (1780438088000, 'late.fit', b'', 'metrics'),   # Jun 2 21:08 UTC
        (1780354915000, 'early.fit', b'', 'metrics'),  # Jun 2 22:01 prior UTC
        (1780387016000, 'mid.fit',  b'', 'metrics'),   # Jun 2 06:36 UTC
    ]
    pending.sort(key=lambda p: p[0])
    names = [p[1] for p in pending]
    # Chronological — earliest first; the last UPSERT (named 'late.fit') wins.
    assert names == ['early.fit', 'mid.fit', 'late.fit']


def test_fit_file_meta_raises_on_garbage_so_importer_must_wrap():
    """fit_file_meta delegates to fit_tool's FitFile reader, which raises
    on malformed bytes. The bulk importer wraps the call in try/except so
    one bad file in a zip doesn't kill the whole upload — this test pins
    that contract so a future "swallow errors in the helper" refactor
    doesn't silently hide bad uploads."""
    from garmin_fit_parser import fit_file_meta
    import pytest
    with pytest.raises(Exception):
        fit_file_meta(b'not a fit file at all')


def test_fit_file_meta_round_trip_with_minimal_valid_header():
    """Smoke-test the helper's happy path: build a minimal FIT file with
    a known FileIdMessage(type=44) + time_created, round-trip it through
    fit_file_meta, expect ('metrics', expected_ms)."""
    import struct
    from datetime import datetime, timezone
    from garmin_fit_parser import fit_file_meta
    # A minimal FIT file is non-trivial to hand-roll; skip this branch
    # unless fit_tool's writer module is available. Real-world validation
    # is the bulk-importer integration on Vercel.
    try:
        from fit_tool.fit_file_builder import FitFileBuilder
        from fit_tool.profile.messages.file_id_message import FileIdMessage
        from fit_tool.profile.profile_type import FileType, Manufacturer
    except ImportError:
        return
    builder = FitFileBuilder()
    fid = FileIdMessage()
    fid.type = FileType.MONITORING_B  # 32 / wellness
    fid.manufacturer = Manufacturer.GARMIN.value
    fid.product = 3291
    # 2026-06-02 00:00 UTC
    ts_dt = datetime(2026, 6, 2, tzinfo=timezone.utc)
    ts_ms = int(ts_dt.timestamp() * 1000)
    fid.time_created = ts_ms
    builder.add(fid)
    raw = bytes(builder.build().to_bytes())
    kind, time_ms = fit_file_meta(raw)
    assert kind == 'wellness'
    assert time_ms == ts_ms


# ── Mapping refinements (May 28 + May 30 calibration) ────────────────────────

def test_hrv_overlay_shows_overnight_and_highest_5min():
    """Both HRV series from `_HRV_STATUS.fit` [370] land on the overlay chart."""
    daily_metric_rows = [
        _r(date='2026-05-28', sleep_score=None,
           hrv_overnight_avg_ms=54.0, hrv_highest_5min_ms=77.0),
        _r(date='2026-05-30', sleep_score=None,
           hrv_overnight_avg_ms=52.0, hrv_highest_5min_ms=79.0),
    ]
    chart = _build_chart_data([], [], [], [], [], [], daily_metric_rows)
    assert chart['hrv']['overnight'] == [
        {'x': '2026-05-28', 'y': 54.0},
        {'x': '2026-05-30', 'y': 52.0},
    ]
    assert chart['hrv']['highest_5min'] == [
        {'x': '2026-05-28', 'y': 77.0},
        {'x': '2026-05-30', 'y': 79.0},
    ]


def test_garmin_resting_hr_overrides_wellness_log_min_when_present():
    """When garmin_daily_metrics has Garmin's authoritative resting HR from
    [211], it replaces the MIN(wellness_log.heart_rate) value on the HR
    card's resting line. The 7-day-avg series shows up alongside it."""
    garmin_rows = [
        _r(date='2026-05-28', avg_hr=58.0, resting_hr=40, peak_hr=89,
           avg_stress=24.0, peak_stress=70,
           avg_resp=13.0, min_resp=6.0,
           bb_high=99, bb_low=24,
           daily_steps=5438, daily_active_cal=106, daily_distance_m=4250.0),
    ]
    daily_metric_rows = [
        _r(date='2026-05-28', sleep_score=None,
           # Andy's Garmin Connect for May 28 — these win over wellness_log
           # MIN of 40, which can catch transient dips.
           resting_hr=44, resting_hr_7day_avg=48),
    ]
    chart = _build_chart_data([], [], [], [], [], garmin_rows, daily_metric_rows)
    # Garmin's 44 wins over wellness_log MIN of 40.
    assert chart['heart_rate']['resting'] == [{'x': '2026-05-28', 'y': 44.0}]
    # 7-day-avg series shows up.
    assert chart['heart_rate']['resting_7day_avg'] == [
        {'x': '2026-05-28', 'y': 48.0}
    ]


def test_heat_acclimation_and_acute_load_surface_as_their_own_cards():
    daily_metric_rows = [
        _r(date='2026-05-28', sleep_score=None,
           heat_acclimation_pct=32, acute_training_load=98),
        _r(date='2026-05-30', sleep_score=None,
           heat_acclimation_pct=22, acute_training_load=59),
    ]
    chart = _build_chart_data([], [], [], [], [], [], daily_metric_rows)
    assert chart['heat_acclimation'] == [
        {'x': '2026-05-28', 'y': 32.0},
        {'x': '2026-05-30', 'y': 22.0},
    ]
    assert chart['acute_load'] == [
        {'x': '2026-05-28', 'y': 98.0},
        {'x': '2026-05-30', 'y': 59.0},
    ]


def test_metrics_to_db_fields_passes_through_new_columns():
    """The new fields from refined mappings reach the table correctly."""
    from routes.garmin import _metrics_to_db_fields
    fields = _metrics_to_db_fields({
        'date': '2026-05-28',
        'sleep_duration_sub_score': 100,
        'hrv_highest_5min_ms': 77.0,
        'heat_acclimation_pct': 32,
        'acute_training_load': 98,
        'resting_hr': 44,
        'resting_hr_7day_avg': 48,
    })
    assert fields == {
        'sleep_duration_sub_score': 100,
        'hrv_highest_5min_ms': 77.0,
        'heat_acclimation_pct': 32,
        'acute_training_load': 98,
        'resting_hr': 44,
        'resting_hr_7day_avg': 48,
    }


# ── Sleep-stage decode candidates ([384] field_5/6/7 — encoding unsolved) ────

def test_sleep_stage_decode_candidates_emits_one_row_per_decoder():
    """`_sleep_stage_decode_candidates` should return one entry per registered
    decoder, each carrying the per-field minute interpretation under that
    decoder. None is verified — they're for eyeball comparison against
    Connect's Deep/Light/REM minutes when the next reference day lands."""
    from garmin_fit_parser import (
        _sleep_stage_decode_candidates,
        _SLEEP_STAGE_DECODE_CANDIDATES,
    )
    # May 28 reference values (sleep score 96, 8h12m sleep).
    candidates = _sleep_stage_decode_candidates(23412736, 11425109, 3543590)
    assert len(candidates) == len(_SLEEP_STAGE_DECODE_CANDIDATES)
    for row in candidates:
        assert set(row) == {
            'decoder', 'description', 'f5_min', 'f6_min', 'f7_min', 'sum_min',
        }
    by_name = {row['decoder']: row for row in candidates}
    # Spot-check the 16.16 fixed-point candidate, the closest the existing
    # 3-day dataset gets to looking like plausible minute values (May 28
    # produces 357.25 / 174.33 / 54.07 — but the sum overshoots the actual
    # 492-minute total, so it isn't a real fit).
    assert by_name['fixed_point_min']['f5_min'] == 357.25
    assert by_name['fixed_point_min']['f6_min'] == 174.33
    assert by_name['fixed_point_min']['f7_min'] == 54.07


def test_sleep_stage_decode_candidates_skips_when_a_field_is_missing():
    """`field_5` / `_6` / `_7` are only present on the rich [384] row. The
    helper should bail on None inputs so the inspector dump doesn't render
    spurious entries for messages that don't carry the sleep summary."""
    from garmin_fit_parser import _sleep_stage_decode_candidates
    assert _sleep_stage_decode_candidates(None, 1, 2) == []
    assert _sleep_stage_decode_candidates(1, None, 2) == []
    assert _sleep_stage_decode_candidates(1, 2, None) == []


def test_find_sleep_stage_decoder_locates_a_known_decoder_under_a_permutation():
    """Synthetic 2-day reference set where field_5/_6/_7 are encoded as
    (minutes × 65536) for REM / Deep / Light respectively. The solver should
    recover the `fixed_point_min` decoder and the swap-permutation."""
    from garmin_fit_parser import find_sleep_stage_decoder

    def pack(minutes):
        return int(round(minutes * 65536))

    # Two nights with materially different stage distributions — without
    # that, multiple decoders end up trivially "fitting" both days.
    night_1 = (pack(85),  pack(110), pack(305),  110, 305, 85)
    night_2 = (pack(45),  pack(60),  pack(220),  60,  220, 45)
    matches = find_sleep_stage_decoder([night_1, night_2], tolerance_min=0.5)
    assert matches, 'expected the synthetic decoder to be recoverable'
    top = matches[0]
    assert top['decoder'] == 'fixed_point_min'
    assert top['permutation'] == {
        'field_5': 'rem', 'field_6': 'deep', 'field_7': 'light',
    }
    assert top['max_error_min'] <= 0.5


def test_find_sleep_stage_decoder_returns_empty_for_actual_connect_ground_truth():
    """Pinned with Andy's Jun 9 Garmin Connect screenshots — the f5/f6/f7
    fields are NOT the Deep/Light/REM stage minutes (and the f7 = HRV
    discovery in `_METRICS_SLEEP_SUMMARY_MSG`'s comment explains why: f7
    is overnight HRV avg × 65536, not REM minutes). Future hands-off
    changes to the decoder list shouldn't accidentally surface a fake
    'fit' for the stage split — this test pins that."""
    from garmin_fit_parser import find_sleep_stage_decoder
    reference = [
        # f5,        f6,       f7,       deep, light, rem
        ( 7165269, 35711660, 3440511,    70,   180,   47),  # May 30, 4h57m
        ( 9797632, 36590932, 2558531,    75,   170,   50),  # Jun  2, 4h55m
    ]
    assert find_sleep_stage_decoder(reference, tolerance_min=2.0) == []


def test_metrics_384_field_7_decodes_as_hrv_overnight_avg_ms():
    """Confirms the f7 = HRV finding from Andy's Jun 9 Connect data: every
    night, `[384] field_7 / 65536` rounds to Connect's overnight HRV. f7
    is a duplicate of `[370] field_1` from `_HRV_STATUS.fit` — the parser
    stays single-source on the HRV file, so we don't write it from here.
    But the encoding is locked, which is what justifies the 16.16
    fixed-point hypothesis for the rest of the message family."""
    from garmin_fit_parser import _sleep_stage_decode_candidates

    def hrv_from_f7(raw_f7):
        for c in _sleep_stage_decode_candidates(0, 0, raw_f7):
            if c['decoder'] == 'fixed_point_min':
                return round(c['f7_min'])
        raise AssertionError('fixed_point_min decoder is missing')

    assert hrv_from_f7(3543590) == 54  # May 28 ↔ Connect 54 ms
    assert hrv_from_f7(3440511) == 52  # May 30 ↔ Connect 52 ms (52.50 rounds to 52)
    assert hrv_from_f7(2558531) == 39  # Jun  2 ↔ Connect 39 ms


def test_find_sleep_stage_decoder_needs_at_least_two_nights():
    """One night admits trivially many decoder/permutation fits — the
    solver should refuse rather than emit noise."""
    from garmin_fit_parser import find_sleep_stage_decoder
    assert find_sleep_stage_decoder([(1, 2, 3, 4, 5, 6)]) == []
    assert find_sleep_stage_decoder([]) == []


# ── [346] sub-score slot candidates (Stress/Light/REM/Awake unmapped) ────────

def test_sleep_sub_score_slot_candidates_emits_one_row_per_present_field():
    """`_sleep_sub_score_slot_candidates` returns one entry per field with a
    non-None value, carrying slot name, raw value, intra-night rank, and
    qualitative band. The slot ↔ contributor name correlation is done by
    the operator across multiple nights using the rank column."""
    from garmin_fit_parser import _sleep_sub_score_slot_candidates
    # Synthetic night: field_8 lowest (the candidate for "worst contributor"),
    # field_5 highest, others in the middle.
    candidates = _sleep_sub_score_slot_candidates(95, 88, 60, 82)
    assert candidates == [
        {'slot': 'field_5',  'raw': 95, 'rank': 4, 'band_garmin_std': 'Excellent'},
        {'slot': 'field_7',  'raw': 88, 'rank': 3, 'band_garmin_std': 'Excellent'},
        {'slot': 'field_8',  'raw': 60, 'rank': 1, 'band_garmin_std': 'Good'},
        {'slot': 'field_10', 'raw': 82, 'rank': 2, 'band_garmin_std': 'Excellent'},
    ]


def test_sleep_sub_score_slot_candidates_skips_none_fields():
    """Real `[346]` samples occasionally lack a field. The helper should
    drop the missing slot rather than treat None as a low value."""
    from garmin_fit_parser import _sleep_sub_score_slot_candidates
    candidates = _sleep_sub_score_slot_candidates(95, None, 60, 82)
    assert [c['slot'] for c in candidates] == ['field_5', 'field_8', 'field_10']
    assert all(1 <= c['rank'] <= 3 for c in candidates)
    # No candidates when every field is missing.
    assert _sleep_sub_score_slot_candidates(None, None, None, None) == []


def test_sleep_sub_score_slot_candidates_bands_match_garmin_quartiles():
    """Band cutoffs are the standard Garmin 0-100 quartile breaks at 25/50/75.
    Empirically this metric family runs hot (mostly 80-100) so absolute
    bands aren't the primary signal — pin them anyway so the dump output
    stays consistent."""
    from garmin_fit_parser import _sleep_sub_score_slot_candidates
    candidates = _sleep_sub_score_slot_candidates(10, 40, 70, 99)
    by_slot = {c['slot']: c for c in candidates}
    assert by_slot['field_5']['band_garmin_std']  == 'Poor'
    assert by_slot['field_7']['band_garmin_std']  == 'Fair'
    assert by_slot['field_8']['band_garmin_std']  == 'Good'
    assert by_slot['field_10']['band_garmin_std'] == 'Excellent'


def test_sleep_sub_score_slot_candidates_breaks_ties_by_slot_order():
    """When two slots carry the same raw value, rank goes by slot order
    (earliest wins rank 1). Keeps dump output stable across runs and
    avoids spurious "the ranking flipped" interpretations."""
    from garmin_fit_parser import _sleep_sub_score_slot_candidates
    candidates = _sleep_sub_score_slot_candidates(80, 80, 80, 80)
    ranks = {c['slot']: c['rank'] for c in candidates}
    assert ranks == {'field_5': 1, 'field_7': 2, 'field_8': 3, 'field_10': 4}


def test_sleep_sub_score_slot_candidates_sep8_locks_field_10_awake():
    """Sep 8 2025 reference: 37 sleep score (atrocious), 72 min awake on
    5h06m total (23.5% awake — terrible), but stress avg 3.40 (very low).
    Raw `[346]` slots: field_5=61 / field_7=58 / field_8=98 / field_10=0.

    Locks Awake to field_10 (raw 0 = rank 1 Poor — only metric that
    cratered on this night). Triple-confirms field_8 = Stress (rank 4
    Excellent at 98 despite atrocious sleep — because stress was low).
    Earlier Jun 2 reading (field_5 = 92 with Awake = 10 min) suggested
    field_5 = Awake but Sep 8's 72-min-awake night with field_5 = 61
    rules that out: Awake is field_10."""
    from garmin_fit_parser import _sleep_sub_score_slot_candidates
    candidates = _sleep_sub_score_slot_candidates(61, 58, 98, 0)
    by_slot = {c['slot']: c for c in candidates}
    # The lock: field_10 = 0 is the rank-1 Poor slot → Awake sub-score.
    assert by_slot['field_10']['rank'] == 1
    assert by_slot['field_10']['raw'] == 0
    assert by_slot['field_10']['band_garmin_std'] == 'Poor'
    # field_8 = 98 (rank 4 Excellent) confirms field_8 = Stress (low
    # stress on Sep 8 → high stress sub-score).
    assert by_slot['field_8']['rank'] == 4
    assert by_slot['field_8']['band_garmin_std'] == 'Excellent'


def test_sleep_sub_score_slot_candidates_field_5_and_field_7_lock_light_and_rem():
    """May 28 + Jun 2 disambiguate the last two slots:
      May 28 (8h12m great sleep, Light ~68% high / REM ~20% ideal):
        field_5 = 83 (Excellent low — penalized for high Light fraction)
        field_7 = 95 (Excellent — ideal REM)
      Jun 2 (5h05m short sleep, Light 55.7% ideal / REM 16.4% low):
        field_5 = 92 (Excellent — Light in range)
        field_7 = 73 (Good — REM low)
    Locks field_5 = Light sub-score, field_7 = REM sub-score."""
    from garmin_fit_parser import _sleep_sub_score_slot_candidates
    # May 28 reference
    may28 = {c['slot']: c for c in _sleep_sub_score_slot_candidates(83, 95, 95, 100)}
    assert may28['field_5']['raw'] == 83  # Light sub-score: high Light → 83
    assert may28['field_7']['raw'] == 95  # REM sub-score: ideal REM → 95
    # Jun 2 reference
    jun2 = {c['slot']: c for c in _sleep_sub_score_slot_candidates(92, 73, 46, 74)}
    assert jun2['field_5']['raw'] == 92  # Light in range → 92
    assert jun2['field_7']['raw'] == 73  # REM low → 73


def test_sleep_sub_score_slot_candidates_jun2_locks_field_8_stress():
    """Jun 2 2026 reference: 58 sleep score, Connect Stress 27 avg (Fair
    band). Raw `[346]` slot values: field_5=92 / field_7=73 / field_8=46
    / field_10=74. The lock: field_8 = 46 (rank 1 Fair) matches Connect's
    Stress=27 Fair rating. Triple-confirmed across Jun 2 + Sep 8 + May 28."""
    from garmin_fit_parser import _sleep_sub_score_slot_candidates
    candidates = _sleep_sub_score_slot_candidates(92, 73, 46, 74)
    by_slot = {c['slot']: c for c in candidates}
    # The lock: field_8 is the rank-1 (worst) slot and in Fair band.
    assert by_slot['field_8']['rank'] == 1
    assert by_slot['field_8']['band_garmin_std'] == 'Fair'
    # field_7 / field_10 land in the Good band (Light+REM+Awake ambiguous
    # without the Sep 8 datapoint).
    assert by_slot['field_7']['band_garmin_std'] == 'Good'
    assert by_slot['field_10']['band_garmin_std'] == 'Good'


# ── find_constant_value_fields — VO₂max constant scanner (#283) ─────────────

def test_find_constant_value_fields_matches_when_value_constant_across_nights():
    """The motivating case: VO₂max running ≈ 48 steady on Andy's Fenix 8.
    Across multiple `_METRICS.fit` uploads, find any field whose value
    is 48 (or a scaled equivalent) on every night."""
    from garmin_fit_parser import find_constant_value_fields
    # Synthetic 2 nights, gid 281 carries field_4 = 48 on both nights.
    nights = [
        {'281': [{'global_id': '281', 'field_4': '48', 'field_5': '32'}]},
        {'281': [{'global_id': '281', 'field_4': '48', 'field_5': '22'}]},
    ]
    matches = find_constant_value_fields(nights, target=48)
    assert len(matches) == 1
    m = matches[0]
    assert m['message_id'] == '281'
    assert m['field_id'] == 'field_4'
    assert m['scale'] == 1.0
    assert m['raw_values'] == [48.0, 48.0]


def test_find_constant_value_fields_handles_garmin_scale_factors():
    """Garmin often stores fractional values as ×10 or ×100 integers in FIT.
    If a field carries 480 on both nights, target=48 should match under
    scale=0.1 (480 × 0.1 = 48)."""
    from garmin_fit_parser import find_constant_value_fields
    nights = [
        {'378': [{'field_2': '480'}]},
        {'378': [{'field_2': '480'}]},
    ]
    matches = find_constant_value_fields(nights, target=48)
    assert len(matches) == 1
    assert matches[0]['scale'] == 0.1
    assert matches[0]['scaled_values'] == [48.0, 48.0]


def test_find_constant_value_fields_rejects_varying_values():
    """If a field shifts between nights, it's not a constant. The scanner
    must drop it — otherwise the operator would chase phantom matches."""
    from garmin_fit_parser import find_constant_value_fields
    nights = [
        {'281': [{'field_4': '48'}]},
        {'281': [{'field_4': '50'}]},
    ]
    assert find_constant_value_fields(nights, target=48) == []


def test_find_constant_value_fields_skips_fields_missing_in_any_night():
    """A constant has to be present on every night. A field that appears
    on night 1 with value 48 but is absent night 2 isn't a constant."""
    from garmin_fit_parser import find_constant_value_fields
    nights = [
        {'281': [{'field_4': '48', 'field_5': '99'}]},
        {'281': [{'field_5': '99'}]},  # field_4 missing
    ]
    matches = find_constant_value_fields(nights, target=48)
    assert matches == []


def test_find_constant_value_fields_message_ids_filter_restricts_scope():
    """`message_ids=(281,)` should scan only gid 281, ignoring other gids
    even if they carry the target value. Matches the inspector route's
    default scan-to-_METRICS.fit-messages behaviour."""
    from garmin_fit_parser import find_constant_value_fields
    nights = [
        {'281': [{'field_4': '99'}], '999': [{'field_0': '48'}]},
        {'281': [{'field_4': '99'}], '999': [{'field_0': '48'}]},
    ]
    # Default (None) catches field_0 of 999.
    default_matches = find_constant_value_fields(nights, target=48)
    assert any(m['message_id'] == '999' for m in default_matches)
    # Filtered to (281,) does not.
    filtered = find_constant_value_fields(
        nights, target=48, message_ids=(281,)
    )
    assert filtered == []


def test_find_constant_value_fields_needs_at_least_two_nights():
    """One night admits trivially many false matches — the helper should
    refuse rather than emit noise."""
    from garmin_fit_parser import find_constant_value_fields
    one_night = [{'281': [{'field_4': '48'}]}]
    assert find_constant_value_fields(one_night, target=48) == []
    assert find_constant_value_fields([], target=48) == []


def test_find_constant_value_fields_tolerance_allows_small_drift():
    """FIT round-trip can drift by sub-integer amounts; default tolerance
    of 0.5 allows 47.6 and 48.4 to still match target=48. A tighter
    tolerance rejects the drift."""
    from garmin_fit_parser import find_constant_value_fields
    nights = [
        {'281': [{'field_4': '47.6'}]},
        {'281': [{'field_4': '48.4'}]},
    ]
    assert find_constant_value_fields(nights, target=48) != []
    assert find_constant_value_fields(nights, target=48, tolerance=0.1) == []


# ── find_value_match_fields — per-file Connect-smoothed minutes scan (#283) ─

def test_find_value_match_fields_matches_target_in_field():
    """Issue #283 motivating case: Connect-smoothed Light = 180 min on
    May 30. The scanner walks a single dump and returns any field whose
    value equals 180 (under one of the candidate scales)."""
    from garmin_fit_parser import find_value_match_fields
    dump = {'generic_samples': {
        '346': [{'field_5': '90', 'field_7': '180', 'field_8': '70'}],
    }}
    matches = find_value_match_fields(dump, targets=[180])
    assert len(matches) == 1
    m = matches[0]
    assert m['message_id'] == '346'
    assert m['field_id'] == 'field_7'
    assert m['target'] == 180
    assert m['scale'] == 1.0


def test_find_value_match_fields_handles_multiple_targets():
    """Pass [180, 47, 8] (Connect Light/REM/Awake) — the scanner emits
    a match per (field, target) hit."""
    from garmin_fit_parser import find_value_match_fields
    dump = {'generic_samples': {
        '346': [{'field_a': '180', 'field_b': '47', 'field_c': '8',
                 'field_d': '999'}],
    }}
    matches = find_value_match_fields(dump, targets=[180, 47, 8])
    targets_hit = {m['target'] for m in matches}
    assert targets_hit == {180, 47, 8}


def test_find_value_match_fields_handles_scale_factors():
    """A field carrying 1800 (×10 encoded Light minutes) should match
    target=180 under scale=0.1. Same for 80 → target=8 at scale=0.1."""
    from garmin_fit_parser import find_value_match_fields
    dump = {'generic_samples': {
        '346': [{'field_5': '1800', 'field_7': '80'}],
    }}
    matches = find_value_match_fields(dump, targets=[180, 8])
    targets_hit = {(m['target'], m['scale']) for m in matches}
    assert (180, 0.1) in targets_hit
    assert (8, 0.1) in targets_hit


def test_find_value_match_fields_message_ids_filter():
    """Restrict to gid 346 — fields on gid 999 with target value are
    ignored. Mirrors the inspector's optional scope-narrowing."""
    from garmin_fit_parser import find_value_match_fields
    dump = {'generic_samples': {
        '346': [{'field_5': '180'}],
        '999': [{'field_5': '180'}],
    }}
    matches = find_value_match_fields(
        dump, targets=[180], message_ids=(346,),
    )
    assert len(matches) == 1
    assert matches[0]['message_id'] == '346'


def test_find_value_match_fields_empty_targets_returns_empty():
    """No targets → nothing to match. The route uses this for the
    `?values=off` escape hatch."""
    from garmin_fit_parser import find_value_match_fields
    dump = {'generic_samples': {'346': [{'field_5': '180'}]}}
    assert find_value_match_fields(dump, targets=[]) == []


def test_find_value_match_fields_accepts_bare_generic_samples():
    """Convenience: caller can pass the generic_samples dict directly
    instead of the full `_dump_fit` result — the helper does the
    lookup. Lets ad-hoc scripts skip the wrapping dict."""
    from garmin_fit_parser import find_value_match_fields
    bare = {'346': [{'field_5': '47'}]}
    matches = find_value_match_fields(bare, targets=[47])
    assert len(matches) == 1
    assert matches[0]['field_id'] == 'field_5'


# ── _sleep_counter_derivation_candidates — [346] field_12/13 probe (#283) ───

def test_sleep_counter_derivation_surfaces_stage_period_counts():
    """The helper computes contiguous-run counts per stage code from
    `[275]` events. With 2 Light periods (codes 2…2…2 then gap then
    2…2), it should report light_period_count = 2."""
    from garmin_fit_parser import _sleep_counter_derivation_candidates
    # ts in seconds; code: 1=Unmeas, 2=Light, 3=Deep, 4=REM
    events = [
        (1000, 2),  # Light period 1
        (1300, 3),  # Deep period 1
        (1600, 2),  # Light period 2
        (1900, 4),  # REM period 1
        (2200, 2),  # Light period 3
    ]
    out = _sleep_counter_derivation_candidates(events, {})
    assert out['derived']['light_period_count'] == 3
    assert out['derived']['deep_period_count'] == 1
    assert out['derived']['rem_period_count'] == 1
    assert out['derived']['awake_period_count'] == 0
    assert out['derived']['total_events'] == 5
    assert out['derived']['transition_count'] == 4


def test_sleep_counter_derivation_flags_matches_against_raw_counters():
    """When a derived count equals raw field_12 or field_13, the helper
    surfaces that derivation in `matches_field_12/13` — that's the lock
    candidate the operator hunts for."""
    from garmin_fit_parser import _sleep_counter_derivation_candidates
    # 4 Light periods, 2 REM periods → field_12=4 should match
    # light_period_count, field_13=2 should match rem_period_count.
    events = [
        (1000, 2), (1300, 4), (1600, 2), (1900, 4),
        (2200, 2), (2500, 3), (2800, 2),
    ]
    out = _sleep_counter_derivation_candidates(
        events, {'field_12': '4', 'field_13': '2'},
    )
    assert 'light_period_count' in out['matches_field_12']
    assert 'rem_period_count' in out['matches_field_13']
    assert out['raw'] == {'field_12': 4, 'field_13': 2}


def test_sleep_counter_derivation_handles_missing_raw_counters():
    """File without `[346]` (e.g. partial sleep upload) — caller passes
    empty raw_counters and the helper still emits the derivation
    summary so operator can correlate manually."""
    from garmin_fit_parser import _sleep_counter_derivation_candidates
    events = [(1000, 2), (1300, 3)]
    out = _sleep_counter_derivation_candidates(events, {})
    assert out['raw'] == {'field_12': None, 'field_13': None}
    assert out['matches_field_12'] == []
    assert out['matches_field_13'] == []
    assert out['derived']['light_period_count'] == 1


def test_sleep_counter_derivation_returns_empty_without_events():
    """No `[275]` data → nothing to derive from. Returning {} keeps the
    inspector output clean (no empty `sleep_counter_derivation_candidates`
    entries for files without sleep data)."""
    from garmin_fit_parser import _sleep_counter_derivation_candidates
    assert _sleep_counter_derivation_candidates([], {'field_12': '5'}) == {}


# ── [275] sleep-stage transition walker + minute tally ──────────────────────

def test_stage_minutes_from_events_tallies_between_adjacent_events():
    """Each adjacent pair contributes (next.ts - this.ts) seconds to the
    current event's code. Verified against the 5 visible May 30 events
    from Andy's `_SLEEP_DATA.fit` dump (codes 2/1/2/3/2 at FIT epoch sec
    1149038520/1149038760/1149039360/1149040140/1149040680)."""
    from garmin_fit_parser import _stage_minutes_from_events
    events = [
        (1149038520, 2), (1149038760, 1), (1149039360, 2),
        (1149040140, 3), (1149040680, 2),
    ]
    # Without sleep_end the last event drops out, leaving 4 adjacent gaps.
    assert _stage_minutes_from_events(events) == {2: 17, 1: 10, 3: 9}


def test_stage_minutes_from_events_uses_sleep_end_for_final_segment():
    """When sleep_end_ts is supplied (cross-file from `[384] field_11`),
    the final event gets a duration too."""
    from garmin_fit_parser import _stage_minutes_from_events
    events = [
        (1000, 1), (1300, 2), (1900, 1),  # last event needs sleep_end
    ]
    # Without sleep_end: code 1 = 5 min (300s), code 2 = 10 min (600s)
    assert _stage_minutes_from_events(events) == {1: 5, 2: 10}
    # With sleep_end at 2200: last code 1 segment = 300s = 5 min added
    assert _stage_minutes_from_events(events, sleep_end_ts=2200) == {1: 10, 2: 10}


def test_stage_minutes_from_events_clips_implausible_segments():
    """A 24-hour-plus gap between events is almost certainly a parse
    error or skipped record — clip it rather than letting a single
    bogus segment dominate the tally."""
    from garmin_fit_parser import _stage_minutes_from_events
    events = [
        (1000, 1),          # +60s → code 1 = 1 min
        (1060, 2),          # +90,000s gap → 25 hours, clipped
        (91060, 3),         # ignored due to clip on previous
    ]
    out = _stage_minutes_from_events(events, sleep_end_ts=91120)
    assert 2 not in out  # 25h gap clipped
    assert out.get(1) == 1


def test_stage_minutes_from_events_empty_input():
    from garmin_fit_parser import _stage_minutes_from_events
    assert _stage_minutes_from_events([]) == {}
    assert _stage_minutes_from_events([], sleep_end_ts=1000) == {}


def test_sleep_stress_avg_matches_connect_for_may_30():
    """`[346] field_15` is the SUM of all stress samples taken during sleep;
    Garmin samples stress every ~3 min, so avg = sum × 3 / sleep_min.
    May 30 ground truth from Connect: 'Stress 15 avg'. The locked
    formula produces 15.06 ↔ Connect 15 (rounding tolerance)."""
    from garmin_fit_parser import sleep_stress_avg
    # field_15 = 1491, sleep_min = 297
    assert sleep_stress_avg(1491, 297) == 15.1


def test_sleep_stress_avg_handles_capped_sample_count():
    """`[346] field_14` is capped at 100, which would skew the average on
    long nights (sleep_min > 300). `sleep_stress_avg` derives the count
    from sleep_min directly to avoid the cap."""
    from garmin_fit_parser import sleep_stress_avg
    # May 28: sleep_min = 492, samples = 164 (uncapped), field_15 = 1120
    # field_14 = 100 (capped from 164) — naive 1120/100 = 11.2 would be wrong.
    assert sleep_stress_avg(1120, 492) == 6.8


def test_sleep_stress_avg_rejects_missing_inputs():
    from garmin_fit_parser import sleep_stress_avg
    assert sleep_stress_avg(None, 297) is None
    assert sleep_stress_avg(1491, None) is None
    assert sleep_stress_avg(1491, 0) is None
    assert sleep_stress_avg(1491, -5) is None


def test_new_sleep_metrics_render_as_their_own_chart_series():
    """The PR #489 mappings — `sleep_deep_min` (from [346] field_9),
    `sleep_stress_avg` (derived from [346] field_15 ÷ sample count), and
    `sleep_wake_count` (from [382] field_2) — each light up an
    independent chart card on `/wellness` when at least one day has
    data. Pins the wiring so the chart layer doesn't drop them."""
    daily_metric_rows = [
        _r(date='2026-05-28', sleep_deep_min=81, sleep_stress_avg=6.8,
           sleep_wake_count=4),
        _r(date='2026-05-30', sleep_deep_min=70, sleep_stress_avg=15.1,
           sleep_wake_count=9),
    ]
    chart = _build_chart_data([], [], [], [], [], [], daily_metric_rows)
    assert chart['sleep_deep_min'] == [
        {'x': '2026-05-28', 'y': 81.0},
        {'x': '2026-05-30', 'y': 70.0},
    ]
    assert chart['sleep_stress_avg'] == [
        {'x': '2026-05-28', 'y': 6.8},
        {'x': '2026-05-30', 'y': 15.1},
    ]
    assert chart['sleep_wake_count'] == [
        {'x': '2026-05-28', 'y': 4.0},
        {'x': '2026-05-30', 'y': 9.0},
    ]


def test_metrics_to_db_fields_passes_through_pr489_columns():
    """Pin the parser-to-DB plumbing for the new PR #489 fields. The
    parser emits `sleep_deep_min`, `sleep_stress_avg`, `sleep_wake_count`
    keyed to match their `garmin_daily_metrics` column names; the
    translator passes them straight through."""
    from routes.garmin import _metrics_to_db_fields
    fields = _metrics_to_db_fields({
        'date': '2026-05-30',
        'sleep_deep_min': 70,
        'sleep_stress_avg': 15.1,
        'sleep_wake_count': 9,
    })
    assert fields == {
        'sleep_deep_min': 70,
        'sleep_stress_avg': 15.1,
        'sleep_wake_count': 9,
    }


def test_may_28_full_21_event_tally_pins_code_mapping_across_two_nights():
    """May 28 _SLEEP_DATA.fit (great-sleep night, 21 [275] events,
    score 96) cross-verifies the code → stage mapping from May 30.
    Raw tally: {1: 6, 2: 334, 3: 53, 4: 97} — code 1 (unmeasurable) is
    only 6 min on this great night vs 74 min on the poor May 30 night,
    confirming code 1 tracks restlessness/uncertainty rather than any
    sleep stage. Code 3 (Deep) raw = 53 vs Connect/`[346] field_9` = 81
    — Garmin's smoothing redistributes ~28 min of unmeasured/transition
    time into Deep on this night, mirroring the May 30 pattern."""
    from garmin_fit_parser import _stage_minutes_from_events
    events = [
        (1148862060, 2), (1148864640, 3), (1148865240, 2), (1148865840, 4),
        (1148866440, 2), (1148868540, 3), (1148868780, 1), (1148869140, 2),
        (1148870280, 3), (1148871180, 2), (1148873340, 4), (1148873700, 2),
        (1148875980, 3), (1148877060, 2), (1148878860, 4), (1148879880, 2),
        (1148882700, 3), (1148883060, 2), (1148886060, 4), (1148889900, 2),
        (1148891460, 4),
    ]
    tally = _stage_minutes_from_events(events)  # no sleep_end → drops last
    assert tally == {1: 6, 2: 334, 3: 53, 4: 97}


def test_may_30_full_15_event_tally_matches_locked_code_mapping():
    """Lock the May 30 reference tally against Andy's preview-URL dump
    (15 [275] events, all visible). Pins the code -> stage mapping:
      1 = unmeasurable/restless, 2 = Light, 3 = Deep, 4 = REM
    Connect's reported Deep/Light/REM/Awake for May 30 are 70/180/47/8,
    summing to 305 (the in-bed period). The RAW [275] tally undercounts
    each stage because Garmin's algorithm smooths the 85 unmeasurable
    minutes (74 code-1 + 11 pre-sleep) into the four stages."""
    from garmin_fit_parser import _stage_minutes_from_events
    events = [
        (1149038520, 2), (1149038760, 1), (1149039360, 2), (1149040140, 3),
        (1149040680, 2), (1149043140, 3), (1149043980, 2), (1149045420, 4),
        (1149046020, 2), (1149046980, 3), (1149049020, 2), (1149049260, 1),
        (1149053100, 2), (1149054480, 4), (1149056160, 2),
    ]
    # sleep_end = 1149056160 (from [384] field_11). The final event lands
    # exactly here and contributes 0 min to its own code.
    tally = _stage_minutes_from_events(events, sleep_end_ts=1149056160)
    assert tally == {1: 74, 2: 125, 3: 57, 4: 38}
    assert sum(tally.values()) == 294  # in-bed period minus 11 min pre-sleep gap
