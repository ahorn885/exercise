"""Unit tests for `routes.wellness._build_headline_strip` (#527) — the
"what changed" strip that flags the metrics moving most vs their 7-day average.
"""
from __future__ import annotations

from routes.wellness import _build_headline_strip


def _pts(ys):
    return [{'x': f'2026-06-{i + 1:02d}', 'y': y} for i, y in enumerate(ys)]


def test_hrv_up_is_a_good_move():
    strip = _build_headline_strip({'hrv': {'overnight': _pts([50, 50, 50, 60])}})
    assert len(strip) == 1
    h = strip[0]
    assert h['name'] == 'HRV'
    assert h['direction'] == 'up'
    assert h['tone'] == 'good'          # HRV up = good
    assert h['delta_abs'] == '+10'
    assert h['delta_pct'] == 20
    assert h['unit'] == ' ms'


def test_resting_hr_up_is_a_concerning_move():
    strip = _build_headline_strip({'heart_rate': {'resting': _pts([50, 50, 50, 60])}})
    assert strip[0]['tone'] == 'bad'    # resting HR up = bad
    assert strip[0]['direction'] == 'up'


def test_resting_hr_down_is_a_good_move():
    strip = _build_headline_strip({'heart_rate': {'resting': _pts([60, 60, 60, 50])}})
    assert strip[0]['tone'] == 'good'
    assert strip[0]['direction'] == 'down'
    assert strip[0]['delta_abs'] == '-10'


def test_excluded_without_enough_baseline():
    # 3 points = only 2 prior < MIN_BASELINE(3) → no baseline, excluded.
    assert _build_headline_strip({'hrv': {'overnight': _pts([50, 55, 60])}}) == []


def test_excluded_when_no_meaningful_move():
    assert _build_headline_strip({'hrv': {'overnight': _pts([50, 50, 50, 50])}}) == []


def test_baseline_window_caps_at_seven_prior_days():
    # 10 points: baseline = mean of the 7 before the latest (not all 9).
    ys = [10, 10, 10, 10, 10, 100, 100, 100, 100, 30]
    strip = _build_headline_strip({'hrv': {'overnight': _pts(ys)}})
    # prior 7 = ys[2:9] = [10,100,100,100,100,100,100] → mean 87.14; latest 30.
    assert strip and strip[0]['direction'] == 'down'


def test_sorted_by_pct_deviation_and_capped_at_five():
    strip = _build_headline_strip({
        'hrv':              {'overnight':       _pts([100, 100, 100, 110])},  # +10%
        'heart_rate':       {'resting':         _pts([50, 50, 50, 75])},      # +50%
        'sleep_score':      {'device':          _pts([80, 80, 80, 88])},      # +10%
        'body_battery':     {'overnight_delta': _pts([20, 20, 20, 40])},      # +100%
        'restless_moments': _pts([4, 4, 4, 8]),                              # +100%
    })
    assert len(strip) == 5
    # Largest % deviations lead.
    assert strip[0]['name'] in ('BB recovery', 'Restless')
    assert abs(strip[0]['delta_pct']) >= abs(strip[-1]['delta_pct'])
