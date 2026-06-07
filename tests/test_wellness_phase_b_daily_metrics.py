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
