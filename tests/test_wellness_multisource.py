"""Multi-source wiring for the /wellness charts (issue #283 expansion).

The dashboard historically only charted Garmin (`wellness_log` +
`daily_wellness_metrics`) plus internal self-report / body / training. These
tests cover the expansion that wires EVERY source into the charts:

  - external providers via `provider_raw_record` — Polar sleep / nightly-recharge
    HRV / cardio-load, COROS daily summary, Whoop daily cycle
  - the internal `body_metrics.vo2_max` into the (previously dead) VO₂max card

Overlapping metrics (sleep hours, overnight HRV, resting HR, VO₂max, steps,
calories) are coalesced per (day, metric) by device priority
(garmin>whoop>polar>coros>body), mirroring the Layer-3A coalesce, so whichever
device the athlete wears charts its data instead of leaving a Garmin-only blank.
"""

from __future__ import annotations

from routes.wellness import (
    _build_chart_data,
    _coalesce_series,
    _has_any_data,
    _provider_wellness_rows,
)


def _r(**kw):
    return dict(kw)


# ── _coalesce_series ─────────────────────────────────────────────────────────

def test_coalesce_series_priority_and_null_skip():
    cands = [
        ('2026-06-01', 50.0, 'coros'),    # lower priority
        ('2026-06-01', 60.0, 'garmin'),   # wins the day
        ('2026-06-01', None, 'whoop'),    # null never wins
        ('2026-06-02', 40.0, 'polar'),    # only source that day
    ]
    assert _coalesce_series(cands) == [
        {'x': '2026-06-01', 'y': 60.0},
        {'x': '2026-06-02', 'y': 40.0},
    ]


def test_coalesce_series_empty():
    assert _coalesce_series([]) == []
    assert _coalesce_series([('2026-06-01', None, 'garmin')]) == []


# ── _build_chart_data with provider rows ─────────────────────────────────────

def test_provider_rows_coalesce_across_sources():
    # Garmin daily metrics on 06-01 (HRV 50, resting 48, 7h sleep span, VO₂ 48).
    daily_rows = [
        _r(date='2026-06-01', hrv_overnight_avg_ms=50.0, resting_hr=48,
           sleep_start_ms=0, sleep_end_ms=7 * 3_600_000,
           vo2max_running=48.0, vo2max_cycling=None),
    ]
    provider_rows = [
        # Whoop owns 06-02 (no Garmin that day): sleep / HRV / RHR / recovery / strain.
        {'date': '2026-06-02', 'provider': 'whoop', 'sleep_hours': 7.5,
         'hrv_ms': 65.0, 'resting_hr': 52.0, 'recovery_score': 70.0,
         'strain': 14.0},
        # Polar on 06-01 — Garmin outranks it for HRV; recovery is Polar-only.
        {'date': '2026-06-01', 'provider': 'polar', 'hrv_ms': 99.0,
         'recovery_score': 80.0},
        # COROS on 06-02 — Whoop outranks it for resting HR; steps/cal are COROS-only.
        {'date': '2026-06-02', 'provider': 'coros', 'resting_hr': 99.0,
         'steps': 9000.0, 'calories': 500.0},
    ]
    chart = _build_chart_data([], [], [], [], [], [], daily_rows,
                              provider_rows=provider_rows)

    # Sleep hours device: Garmin span 7h (06-01) + Whoop 7.5h (06-02).
    assert chart['sleep_hours_device'] == [
        {'x': '2026-06-01', 'y': 7.0},
        {'x': '2026-06-02', 'y': 7.5},
    ]
    # Overnight HRV: Garmin wins 06-01 (50, not Polar's 99); Whoop fills 06-02.
    assert chart['hrv']['overnight'] == [
        {'x': '2026-06-01', 'y': 50.0},
        {'x': '2026-06-02', 'y': 65.0},
    ]
    # Resting HR: Garmin 48 (06-01); Whoop 52 outranks COROS 99 (06-02).
    assert chart['heart_rate']['resting'] == [
        {'x': '2026-06-01', 'y': 48.0},
        {'x': '2026-06-02', 'y': 52.0},
    ]
    # Recovery (0–100): Polar ANS charge 80 (06-01) + Whoop recovery 70 (06-02).
    assert chart['recovery'] == [
        {'x': '2026-06-01', 'y': 80.0},
        {'x': '2026-06-02', 'y': 70.0},
    ]
    # Strain only from Whoop.
    assert chart['strain'] == [{'x': '2026-06-02', 'y': 14.0}]
    # Steps / calories surface from COROS even with no Garmin wellness_log.
    assert chart['daily_activity']['steps'] == [{'x': '2026-06-02', 'y': 9000.0}]
    assert chart['daily_activity']['active_cal'] == [{'x': '2026-06-02', 'y': 500.0}]
    # VO₂max running from the Garmin daily metric.
    assert chart['vo2max_running'] == [{'x': '2026-06-01', 'y': 48.0}]


def test_polar_cardio_load_series():
    provider_rows = [
        {'date': '2026-06-01', 'provider': 'polar', 'daily_load': 120.0,
         'acute_load': 300.0, 'chronic_load': 280.0},
    ]
    chart = _build_chart_data([], [], [], [], [], [],
                              provider_rows=provider_rows)
    assert chart['cardio_load']['daily'] == [{'x': '2026-06-01', 'y': 120.0}]
    assert chart['cardio_load']['acute'] == [{'x': '2026-06-01', 'y': 300.0}]
    assert chart['cardio_load']['chronic'] == [{'x': '2026-06-01', 'y': 280.0}]


def test_vo2max_from_internal_body_metrics():
    # A manual body_metrics VO₂max lights up the previously-dead VO₂max card.
    body_rows = [
        _r(date='2026-06-01', weight_kg=None, body_fat_pct=None,
           resting_hr=None, vo2_max=52.0),
    ]
    chart = _build_chart_data([], body_rows, [], [], [], [])
    assert chart['vo2max_running'] == [{'x': '2026-06-01', 'y': 52.0}]


def test_garmin_vo2max_outranks_manual_body_metrics():
    daily_rows = [_r(date='2026-06-01', vo2max_running=49.0)]
    body_rows = [_r(date='2026-06-01', weight_kg=None, body_fat_pct=None,
                    resting_hr=None, vo2_max=40.0)]
    chart = _build_chart_data([], body_rows, [], [], [], [], daily_rows)
    assert chart['vo2max_running'] == [{'x': '2026-06-01', 'y': 49.0}]


def test_has_any_data_lights_up_for_provider_only():
    # A Whoop-only athlete (no Garmin, no self-report) still lights the page.
    provider_rows = [
        {'date': '2026-06-01', 'provider': 'whoop', 'recovery_score': 70.0},
    ]
    chart = _build_chart_data([], [], [], [], [], [],
                              provider_rows=provider_rows)
    assert _has_any_data(chart) is True


# ── _provider_wellness_rows (DB normalization) ───────────────────────────────

class _FakeCursor:
    def __init__(self, rows):
        self._rows = rows

    def fetchall(self):
        return self._rows


class _FakeDB:
    """Returns canned rows for the first matching predicate over the SQL."""
    def __init__(self, matchers):
        self._matchers = matchers
        self.queries = []

    def execute(self, sql, params=()):
        self.queries.append((sql, params))
        for pred, rows in self._matchers:
            if pred(sql):
                return _FakeCursor(rows)
        return _FakeCursor([])


def test_provider_wellness_rows_normalizes_each_source():
    coros_start = 1_000
    coros_end = coros_start + 7 * 3_600_000  # +7h
    db = _FakeDB([
        (lambda s: "data_type='sleep'" in s,
         [{'date': '2026-06-01', 'total_sleep_min': 402.0}]),
        (lambda s: "data_type='hrv'" in s,
         [{'date': '2026-06-01', 'hrv_ms': 62.0, 'ans_charge': 80.0}]),
        (lambda s: "data_type='cardio_load'" in s,
         [{'date': '2026-06-01', 'daily_load': 120.0, 'acute_load': 300.0,
           'chronic_load': 280.0}]),
        (lambda s: "provider='coros'" in s,
         [{'date': '2026-06-02', 'rhr': 48.0, 'ppg_hrv': 55.0, 'steps': 9000.0,
           'calories': 500.0, 'sleep_start_ms': coros_start,
           'sleep_end_ms': coros_end}]),
        (lambda s: "provider='whoop'" in s,
         [{'date': '2026-06-03', 'total_sleep_min': 420.0, 'hrv_ms': 70.0,
           'resting_hr': 50.0, 'recovery_score': 66.0, 'day_strain': 14.0}]),
    ])
    rows = _provider_wellness_rows(db, 1, '2026-05-01')

    # Polar sleep minutes → hours.
    assert {'date': '2026-06-01', 'provider': 'polar',
            'sleep_hours': 402 / 60.0} in rows
    # Polar nightly recharge → HRV + ANS-charge recovery.
    assert {'date': '2026-06-01', 'provider': 'polar', 'hrv_ms': 62.0,
            'recovery_score': 80.0} in rows
    # Polar cardio-load triplet.
    assert {'date': '2026-06-01', 'provider': 'polar', 'daily_load': 120.0,
            'acute_load': 300.0, 'chronic_load': 280.0} in rows
    # COROS daily summary: sleep span → 7h, resting HR, steps/cal, PPG HRV.
    coros = next(r for r in rows if r['provider'] == 'coros')
    assert coros['sleep_hours'] == 7.0
    assert coros['resting_hr'] == 48.0
    assert coros['hrv_ms'] == 55.0
    assert coros['steps'] == 9000.0 and coros['calories'] == 500.0
    # Whoop daily cycle: sleep minutes → hours + HRV + RHR + recovery + strain.
    whoop = next(r for r in rows if r['provider'] == 'whoop')
    assert whoop['sleep_hours'] == 7.0
    assert whoop['hrv_ms'] == 70.0 and whoop['resting_hr'] == 50.0
    assert whoop['recovery_score'] == 66.0 and whoop['strain'] == 14.0

    # Every provider/data_type was queried with the user id + cutoff bound.
    assert len(db.queries) == 5
    assert all(params == (1, '2026-05-01') for _, params in db.queries)
