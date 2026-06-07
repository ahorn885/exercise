"""Unit tests for the /wellness chart-data builder.

Covers the Phase-A reshape (issue #283):

  - sleep_hours / soreness / mood read from `wellness_self_report`
  - sleep_score overlay: self-report quality is normalized ×20 to 0–100; the
    device series stays empty until _METRICS.fit parsing lands (Phase B)
  - energy overlay: self ×20 + body-battery min from `wellness_log`
  - activities-per-day counts both cardio_log and training_log rows
  - Phase-B scaffold keys (hrv, training_readiness, vo2max_running,
    vo2max_cycling, active_minutes) stay present but empty so the template
    can render the "device data pending" placeholder cards consistently.
"""

from __future__ import annotations

from routes.wellness import _build_chart_data, _has_any_data


def _r(**kw):
    return dict(kw)


def test_overlays_normalize_self_report_to_100_scale():
    self_rows = [
        _r(date='2026-06-01', sleep_hours=7.5, sleep_quality=4, energy=3,
           soreness=2, mood=5),
        _r(date='2026-06-02', sleep_hours=6.0, sleep_quality=2, energy=1,
           soreness=4, mood=3),
    ]
    garmin_rows = [
        _r(date='2026-06-01', avg_hr=58.0, resting_hr=48, peak_hr=120,
           avg_stress=22, peak_stress=42,
           avg_resp=14.0, min_resp=8.0,
           bb_high=92, bb_low=35,
           daily_steps=8200, daily_active_cal=210, daily_distance_m=5400.0),
        _r(date='2026-06-02', avg_hr=61.0, resting_hr=50, peak_hr=128,
           avg_stress=31, peak_stress=70,
           avg_resp=15.0, min_resp=9.0,
           bb_high=88, bb_low=20,
           daily_steps=9100, daily_active_cal=245, daily_distance_m=6100.0),
    ]

    chart = _build_chart_data(self_rows, [], [], [], [], garmin_rows)

    # Sleep hours stays in native hours.
    assert chart['sleep_hours'] == [
        {'x': '2026-06-01', 'y': 7.5},
        {'x': '2026-06-02', 'y': 6.0},
    ]
    # Self-report quality 4 / 2 → 80 / 40 on the 0–100 axis.
    assert chart['sleep_score']['self'] == [
        {'x': '2026-06-01', 'y': 80.0},
        {'x': '2026-06-02', 'y': 40.0},
    ]
    # Garmin sleep score stays empty until Phase B lands.
    assert chart['sleep_score']['device'] == []

    # Energy: self 3 / 1 → 60 / 20; device = min body battery 35 / 20.
    assert chart['energy']['self'] == [
        {'x': '2026-06-01', 'y': 60.0},
        {'x': '2026-06-02', 'y': 20.0},
    ]
    assert chart['energy']['device'] == [
        {'x': '2026-06-01', 'y': 35.0},
        {'x': '2026-06-02', 'y': 20.0},
    ]

    # Soreness / mood stay 1–5 on their own axis.
    assert chart['soreness'] == [
        {'x': '2026-06-01', 'y': 2.0},
        {'x': '2026-06-02', 'y': 4.0},
    ]
    assert chart['mood'] == [
        {'x': '2026-06-01', 'y': 5.0},
        {'x': '2026-06-02', 'y': 3.0},
    ]


def test_activities_count_combines_cardio_and_strength():
    # Cardio on 06-01 + 06-02; strength on 06-02 + 06-03. The 06-02 overlap
    # is intentional — same day with both should count as two activities.
    cardio_rows = [
        _r(date='2026-06-01', minutes=45.0, n=1),
        _r(date='2026-06-02', minutes=30.0, n=1),
    ]
    strength_rows = [
        _r(date='2026-06-02', minutes=20.0, n=1),
        _r(date='2026-06-03', minutes=25.0, n=2),
    ]
    chart = _build_chart_data([], [], cardio_rows, strength_rows,
                              strength_rows, [])

    assert chart['activities'] == [
        {'x': '2026-06-01', 'y': 1},
        {'x': '2026-06-02', 'y': 2},
        {'x': '2026-06-03', 'y': 2},
    ]
    assert chart['training']['cardio_min'] == [
        {'x': '2026-06-01', 'y': 45.0},
        {'x': '2026-06-02', 'y': 30.0},
        {'x': '2026-06-03', 'y': 0.0},
    ]


def test_phase_b_scaffold_keys_present_but_empty():
    chart = _build_chart_data([], [], [], [], [], [])
    for k in ('training_readiness', 'vo2max_running',
              'vo2max_cycling', 'active_minutes'):
        assert chart[k] == [], f'{k} should be an empty list until Phase B lands'
    # HRV is now an overlay (overnight + highest_5min) — both sides empty
    # when there's no _HRV_STATUS.fit.
    assert chart['hrv'] == {'overnight': [], 'highest_5min': []}
    assert chart['sleep_score']['device'] == []
    # No data anywhere → empty-state path on the page.
    assert _has_any_data(chart) is False


def test_has_any_data_detects_overlay_self_series():
    # Self-report quality but no device data should still light the page up.
    chart = _build_chart_data(
        [_r(date='2026-06-01', sleep_hours=None, sleep_quality=4,
            energy=None, soreness=None, mood=None)],
        [], [], [], [], [],
    )
    assert _has_any_data(chart) is True


def test_wellness_log_aggregations_surface_as_combined_cards():
    """`/wellness` reads daily aggregates off `wellness_log` and groups
    them into combined cards (HR resting+avg+peak together, etc.). Verify
    each aggregate column lands in the expected card slot, and that the
    distance series gets m → mi converted."""
    garmin_rows = [
        _r(date='2026-05-28', avg_hr=58.0, resting_hr=44, peak_hr=89,
           avg_stress=24.0, peak_stress=70,
           avg_resp=13.0, min_resp=6.0,
           bb_high=99, bb_low=24,
           daily_steps=5438, daily_active_cal=106, daily_distance_m=4250.0),
    ]
    chart = _build_chart_data([], [], [], [], [], garmin_rows)
    assert chart['heart_rate']['resting'] == [{'x': '2026-05-28', 'y': 44.0}]
    assert chart['heart_rate']['avg']     == [{'x': '2026-05-28', 'y': 58.0}]
    assert chart['heart_rate']['peak']    == [{'x': '2026-05-28', 'y': 89.0}]
    assert chart['stress']['avg']         == [{'x': '2026-05-28', 'y': 24.0}]
    assert chart['stress']['peak']        == [{'x': '2026-05-28', 'y': 70.0}]
    assert chart['respiration']['avg']    == [{'x': '2026-05-28', 'y': 13.0}]
    assert chart['respiration']['low']    == [{'x': '2026-05-28', 'y': 6.0}]
    assert chart['body_battery']['high']  == [{'x': '2026-05-28', 'y': 99.0}]
    assert chart['body_battery']['low']   == [{'x': '2026-05-28', 'y': 24.0}]
    assert chart['daily_activity']['steps']      == [{'x': '2026-05-28', 'y': 5438.0}]
    assert chart['daily_activity']['active_cal'] == [{'x': '2026-05-28', 'y': 106.0}]
    # 4250 m × 0.000621371 = 2.64 mi (2 decimals)
    assert chart['daily_activity']['distance_mi'] == [{'x': '2026-05-28', 'y': 2.64}]


def test_aggregation_series_skip_null_rows():
    """A day with no body battery sample shouldn't put a NULL on the chart.
    Verifies the per-column NULL skip in `_series`."""
    garmin_rows = [
        _r(date='2026-05-28', avg_hr=58.0, resting_hr=44, peak_hr=89,
           avg_stress=24.0, peak_stress=70,
           avg_resp=13.0, min_resp=6.0,
           bb_high=None, bb_low=None,
           daily_steps=5438, daily_active_cal=106, daily_distance_m=4250.0),
        _r(date='2026-05-29', avg_hr=None, resting_hr=None, peak_hr=None,
           avg_stress=None, peak_stress=None,
           avg_resp=None, min_resp=None,
           bb_high=80, bb_low=18,
           daily_steps=None, daily_active_cal=None, daily_distance_m=None),
    ]
    chart = _build_chart_data([], [], [], [], [], garmin_rows)
    # 28th had no battery; 29th did → only 29th lands.
    assert chart['body_battery']['high'] == [{'x': '2026-05-29', 'y': 80.0}]
    # 29th had no steps; 28th did → only 28th lands.
    assert chart['daily_activity']['steps'] == [{'x': '2026-05-28', 'y': 5438.0}]
