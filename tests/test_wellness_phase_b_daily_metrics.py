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
    assert chart['hrv'] == [
        {'x': '2026-05-28', 'y': 54.0},
        {'x': '2026-05-29', 'y': 61.5},
    ]
    # has_any_data finds the HRV series even with everything else empty.
    assert _has_any_data(chart) is True


def test_phase_b_followup_keys_still_empty_until_their_file_types_land():
    chart = _build_chart_data([], [], [], [], [], [], [])
    for k in ('training_readiness', 'vo2max_running', 'vo2max_cycling',
              'active_minutes'):
        assert chart[k] == [], (
            f'{k} stays empty until TRAINING_STATUS / SPO2 / VO2max file '
            f'types are added in a follow-up'
        )


def test_build_chart_data_default_daily_metric_rows_is_empty():
    # Existing call sites (and tests) that don't pass daily_metric_rows
    # still work — Phase A signature compat.
    chart = _build_chart_data([], [], [], [], [], [])
    assert chart['sleep_score'] == {'self': [], 'device': []}
    assert chart['hrv'] == []


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
