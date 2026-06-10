"""Unified multi-metric wellness dashboard.

One card per metric, with device readings and self-report overlaid where they
measure the same thing (sleep score, energy / body battery). Reads pull from:

  - `wellness_self_report`   — self-reported sleep, energy, soreness, mood
  - `body_metrics`           — weight, body fat %, resting HR
  - `wellness_log`           — Garmin per-second wellness (`_WELLNESS.fit`)
  - `garmin_daily_metrics`   — Garmin daily-derived metrics from
                               `_METRICS.fit` / `_SLEEP_DATA.fit` /
                               `_HRV_STATUS.fit` (sleep score, HRV, …)
  - `cardio_log`             — cardio activities (count + duration)
  - `training_log`           — strength activities (count + duration)

Sleep score and energy charts overlay self-report (normalized to 0–100) against
the device reading on a single axis. VO2max / training readiness / active
minutes still render as empty scaffolds — they live in FIT file types we
haven't seen yet (#283 follow-up).
"""
import json
from datetime import date, datetime, timedelta

from flask import Blueprint, render_template, request, redirect, url_for, flash

from database import get_db
from routes.auth import current_user_id
from routes.oauth_callbacks import provider_slugs

bp = Blueprint('wellness', __name__)

_RANGE_CHOICES = {'7': 7, '30': 30, '90': 90}
_DEFAULT_RANGE_DAYS = 30
_RATING_FIELDS = ('sleep_quality', 'energy', 'soreness', 'mood')

# Self-report ratings are captured 1–5. Multiply by 20 to overlay against
# device metrics that live on a 0–100 scale (sleep score, body battery).
_SELF_REPORT_TO_100 = 20


def _parse_range_days() -> int:
    raw = (request.args.get('range') or str(_DEFAULT_RANGE_DAYS)).strip()
    return _RANGE_CHOICES.get(raw, _DEFAULT_RANGE_DAYS)


def _parse_picked_date(raw: str | None, *, today: date) -> date:
    """Parse a self-report date from the form/querystring. Returns today on
    invalid input, and clamps future dates to today (callers should never let
    the athlete log a session that hasn't happened yet)."""
    if not raw:
        return today
    try:
        d = datetime.strptime(raw.strip(), '%Y-%m-%d').date()
    except ValueError:
        return today
    if d > today:
        return today
    return d


def _parse_int(value, *, lo: int, hi: int) -> int | None:
    """Bound int parser for the 1–5 ratings. Empty/invalid → None."""
    if value is None or value == '':
        return None
    try:
        n = int(value)
    except (TypeError, ValueError):
        return None
    if n < lo or n > hi:
        return None
    return n


def _parse_float(value) -> float | None:
    if value is None or value == '':
        return None
    try:
        f = float(value)
    except (TypeError, ValueError):
        return None
    if f < 0 or f > 24:
        return None
    return f


@bp.route('/wellness', methods=['GET', 'POST'])
def index():
    db = get_db()
    uid = current_user_id()

    if request.method == 'POST':
        return _save_self_report(db, uid)

    range_days = _parse_range_days()
    today = date.today()
    cutoff = (today - timedelta(days=range_days - 1)).isoformat()

    # `picked` is the date the form acts on — defaults to today, can be set
    # by `?date=YYYY-MM-DD` so an athlete can backfill a missed prior day.
    # `today_iso` stays around as the `max=` ceiling on the picker.
    today_iso = today.isoformat()
    picked_iso = _parse_picked_date(request.args.get('date'), today=today).isoformat()
    picked_row = db.execute(
        'SELECT * FROM wellness_self_report WHERE user_id=? AND date=?',
        (uid, picked_iso)
    ).fetchone()

    self_report_rows = db.execute(
        'SELECT date, sleep_hours, sleep_quality, energy, soreness, mood '
        'FROM wellness_self_report WHERE user_id=? AND date >= ? '
        'ORDER BY date',
        (uid, cutoff)
    ).fetchall()

    body_rows = db.execute(
        'SELECT date, weight_kg, body_fat_pct, resting_hr '
        'FROM body_metrics WHERE user_id=? AND date >= ? ORDER BY date',
        (uid, cutoff)
    ).fetchall()

    # Training load — cardio.duration_min + strength training_log.actual_duration
    # (sec → min) per day. Strength sessions without an actual_duration
    # contribute 0 minutes; we'd rather under-count than guess.
    cardio_load = db.execute(
        'SELECT date, COALESCE(SUM(duration_min), 0) AS minutes, COUNT(*) AS n '
        'FROM cardio_log WHERE user_id=? AND date >= ? '
        'GROUP BY date ORDER BY date',
        (uid, cutoff)
    ).fetchall()
    strength_load = db.execute(
        'SELECT date, COALESCE(SUM(actual_duration), 0)/60.0 AS minutes, COUNT(*) AS n '
        'FROM training_log WHERE user_id=? AND date >= ? '
        'AND actual_duration IS NOT NULL '
        'GROUP BY date ORDER BY date',
        (uid, cutoff)
    ).fetchall()
    # Activity counts include strength rows even without a recorded duration,
    # since the count reflects "did the athlete train today?" not load.
    strength_counts = db.execute(
        'SELECT date, COUNT(*) AS n FROM training_log '
        'WHERE user_id=? AND date >= ? GROUP BY date ORDER BY date',
        (uid, cutoff)
    ).fetchall()

    # Garmin wellness daily aggregates — `wellness_log` is per-second from
    # `_WELLNESS.fit`. Body-battery extremes feed the Energy overlay (min)
    # and the standalone "Body battery" card (high+low). HR / stress /
    # respiration aggregations get their own combined cards.
    #
    # Steps / active_calories / distance arrive in MonitoringMessage as
    # **cumulative running totals** (each new row > the previous), so the
    # daily total is MAX(...) per day, not SUM — summing would double-count.
    #
    # Stress bucketing: Garmin samples stress every ~3 minutes; we COUNT(*)
    # the samples in each stress-level band (Garmin's standard cutoffs:
    # Rest 0-25 / Low 26-50 / Medium 51-75 / High 76-100) and multiply by
    # the sample interval to surface "minutes spent in each band" on the
    # chart, mirroring what Garmin Connect's daily stress page shows.
    garmin_rows = db.execute(
        'SELECT date, '
        '  AVG(heart_rate)        AS avg_hr, '
        '  MIN(heart_rate)        AS resting_hr, '
        '  MAX(heart_rate)        AS peak_hr, '
        '  AVG(stress_level)      AS avg_stress, '
        '  MAX(stress_level)      AS peak_stress, '
        '  AVG(respiration_rate)  AS avg_resp, '
        '  MIN(respiration_rate)  AS min_resp, '
        '  MAX(body_battery)      AS bb_high, '
        '  MIN(body_battery)      AS bb_low, '
        '  MAX(steps)             AS daily_steps, '
        '  MAX(active_calories)   AS daily_active_cal, '
        '  MAX(distance_m)        AS daily_distance_m, '
        '  SUM(CASE WHEN stress_level BETWEEN 0  AND 25  THEN 1 ELSE 0 END) AS stress_rest_samples, '
        '  SUM(CASE WHEN stress_level BETWEEN 26 AND 50  THEN 1 ELSE 0 END) AS stress_low_samples, '
        '  SUM(CASE WHEN stress_level BETWEEN 51 AND 75  THEN 1 ELSE 0 END) AS stress_med_samples, '
        '  SUM(CASE WHEN stress_level BETWEEN 76 AND 100 THEN 1 ELSE 0 END) AS stress_high_samples '
        'FROM wellness_log WHERE user_id=? AND date >= ? '
        'GROUP BY date ORDER BY date',
        (uid, cutoff)
    ).fetchall()

    # Body battery charged / drained — walk the per-second series with
    # LAG() and sum the positive and negative deltas separately. Returns one
    # row per day; missing days drop out cleanly via the LEFT-join in
    # `_build_chart_data`. Done as a separate query because window-function
    # aggregation can't sit alongside plain GROUP BY columns in the main
    # rollup above without a CTE / subquery.
    bb_delta_rows = db.execute(
        'WITH deltas AS ('
        '  SELECT date, body_battery - LAG(body_battery) OVER ('
        '    PARTITION BY user_id, date ORDER BY timestamp_ms'
        '  ) AS delta '
        '  FROM wellness_log WHERE user_id=? AND date >= ? AND body_battery IS NOT NULL'
        ') '
        'SELECT date, '
        '  SUM(CASE WHEN delta > 0 THEN delta ELSE 0 END)  AS charged, '
        '  SUM(CASE WHEN delta < 0 THEN -delta ELSE 0 END) AS drained '
        'FROM deltas GROUP BY date ORDER BY date',
        (uid, cutoff)
    ).fetchall()

    # Body battery overnight delta (#283 follow-up) — BB value at sleep_end
    # minus BB value at sleep_start. This is the cleanest single-number
    # "how well did this sleep recover you?" signal: it's directly visible
    # in the wellness_log time-series, anchored to the per-night sleep
    # window from `garmin_daily_metrics.sleep_start_ms / sleep_end_ms`.
    # ROW_NUMBER() picks the first BB sample at/after sleep_start and the
    # last sample at/before sleep_end so partial-coverage nights still
    # land an honest delta. Partitioned by dm.date (the sleep-night
    # anchor) so a sleep window that crosses midnight still groups as
    # one night.
    bb_overnight_rows = db.execute(
        'WITH bb_in_sleep AS ( '
        '  SELECT dm.date AS sleep_date, wl.body_battery, wl.timestamp_ms, '
        '    ROW_NUMBER() OVER (PARTITION BY dm.date ORDER BY wl.timestamp_ms ASC)  AS rn_start, '
        '    ROW_NUMBER() OVER (PARTITION BY dm.date ORDER BY wl.timestamp_ms DESC) AS rn_end '
        '  FROM garmin_daily_metrics dm '
        '  JOIN wellness_log wl ON wl.user_id = dm.user_id '
        '    AND wl.body_battery IS NOT NULL '
        '    AND wl.timestamp_ms BETWEEN dm.sleep_start_ms AND dm.sleep_end_ms '
        '  WHERE dm.user_id=? AND dm.date >= ? '
        '    AND dm.sleep_start_ms IS NOT NULL AND dm.sleep_end_ms IS NOT NULL '
        ') '
        'SELECT sleep_date AS date, '
        '  MAX(CASE WHEN rn_start = 1 THEN body_battery END) AS bb_start, '
        '  MAX(CASE WHEN rn_end   = 1 THEN body_battery END) AS bb_end '
        'FROM bb_in_sleep GROUP BY sleep_date ORDER BY sleep_date',
        (uid, cutoff)
    ).fetchall()

    # Garmin daily-derived metrics from `_METRICS.fit` / `_SLEEP_DATA.fit` /
    # `_HRV_STATUS.fit` (#283 Phase B). One row per (user, date); UPSERT lands
    # whichever columns the source file knows about, so this select gets the
    # merged best-of view.
    daily_metric_rows = db.execute(
        'SELECT date, sleep_score, hrv_overnight_avg_ms, hrv_highest_5min_ms, '
        '  resting_metabolic_rate, resting_hr, resting_hr_7day_avg, '
        '  heat_acclimation_pct, acute_training_load, '
        '  restless_moments, floors_climbed, floors_descended, '
        '  intensity_minutes, spo2_avg, spo2_low, '
        '  sleep_deep_min, sleep_stress_avg, sleep_wake_count, '
        '  sleep_light_sub_score, sleep_rem_sub_score, '
        '  sleep_stress_sub_score, sleep_awake_sub_score, '
        '  sleep_stress_above_resting_pct '
        'FROM garmin_daily_metrics WHERE user_id=? AND date >= ? ORDER BY date',
        (uid, cutoff)
    ).fetchall()

    # #469 — surface athlete's display unit so body-weight series renders
    # in their chosen unit.
    from units import normalize_unit_preference
    from athlete import get_athlete_profile
    profile = get_athlete_profile(db, uid) or {}
    unit_pref = normalize_unit_preference(profile.get('unit_preference'))

    chart_data = _build_chart_data(
        self_report_rows, body_rows,
        cardio_load, strength_load, strength_counts,
        garmin_rows, daily_metric_rows, bb_delta_rows,
        bb_overnight_rows=bb_overnight_rows,
        unit_pref=unit_pref,
    )
    # Surface the body-series unit label to the chart JS without polluting
    # `chart_data` (the `_has_any_data` walker would treat any non-empty
    # value as data and break the empty-state UI).
    from units import weight_unit_label as _wt_lbl
    chart_data['body_units'] = {'weight': _wt_lbl(unit_pref)} if chart_data.get('body') else {}

    return render_template(
        'wellness/index.html',
        today_iso=today_iso,
        picked_iso=picked_iso,
        picked_row=dict(picked_row) if picked_row else {},
        range_days=range_days,
        range_choices=sorted(_RANGE_CHOICES.values()),
        chart_data=chart_data,
        has_any_data=_has_any_data(chart_data),
        provider_count=len(provider_slugs()),
    )


def _save_self_report(db, uid):
    today = date.today()
    submitted_date = (request.form.get('date') or today.isoformat()).strip()
    try:
        parsed = datetime.strptime(submitted_date, '%Y-%m-%d').date()
    except ValueError:
        flash('Invalid date.', 'danger')
        return redirect(url_for('wellness.index'))
    if parsed > today:
        flash('Cannot log a wellness report for a future date.', 'danger')
        return redirect(url_for('wellness.index'))

    sleep_hours   = _parse_float(request.form.get('sleep_hours'))
    sleep_quality = _parse_int(request.form.get('sleep_quality'), lo=1, hi=5)
    energy        = _parse_int(request.form.get('energy'),        lo=1, hi=5)
    soreness      = _parse_int(request.form.get('soreness'),      lo=1, hi=5)
    mood          = _parse_int(request.form.get('mood'),          lo=1, hi=5)
    notes         = (request.form.get('notes') or '').strip() or None

    # UPSERT on (user_id, date). database.py's `?` placeholder handles
    # the parameter style.
    existing = db.execute(
        'SELECT id FROM wellness_self_report WHERE user_id=? AND date=?',
        (uid, submitted_date)
    ).fetchone()
    if existing:
        db.execute(
            'UPDATE wellness_self_report SET '
            'sleep_hours=?, sleep_quality=?, energy=?, soreness=?, mood=?, notes=?, '
            'updated_at=NOW() '
            'WHERE id=?',
            (sleep_hours, sleep_quality, energy, soreness, mood, notes,
             existing['id'])
        )
    else:
        db.execute(
            'INSERT INTO wellness_self_report '
            '(user_id, date, sleep_hours, sleep_quality, energy, soreness, mood, notes) '
            'VALUES (?,?,?,?,?,?,?,?)',
            (uid, submitted_date, sleep_hours, sleep_quality, energy,
             soreness, mood, notes)
        )
    db.commit()
    flash('Wellness report saved.', 'success')
    # Preserve the picked date on redirect so the form stays anchored to the
    # day the athlete just saved (matters for prior-day backfill).
    return redirect(url_for(
        'wellness.index',
        range=request.form.get('range') or '',
        date=submitted_date if parsed != today else None,
    ))


# ─── Chart-data builder ───────────────────────────────────────────────────────
# Each metric gets one entry. Overlay charts (sleep_score, energy) carry both
# `self` and `device` series so the template can stack them on one canvas.

def _d(value) -> str:
    """Stringify a date that may arrive as datetime.date (PG) or str (SQLite)."""
    return str(value)[:10] if value is not None else ''


_STRESS_SAMPLE_MIN = 3.0  # Garmin samples stress ~every 3 minutes


def _build_chart_data(self_rows, body_rows, cardio_rows, strength_rows,
                      strength_count_rows, garmin_rows, daily_metric_rows=(),
                      bb_delta_rows=(), bb_overnight_rows=(), unit_pref=None):
    self_by_date = {_d(r['date']): r for r in self_rows}
    garmin_by_date = {_d(r['date']): r for r in garmin_rows}
    daily_by_date = {_d(r['date']): r for r in daily_metric_rows}
    bb_delta_by_date = {_d(r['date']): r for r in bb_delta_rows}
    bb_overnight_by_date = {_d(r['date']): r for r in bb_overnight_rows}

    sleep_hours = [
        {'x': d, 'y': float(r['sleep_hours'])}
        for d, r in self_by_date.items() if r['sleep_hours'] is not None
    ]
    soreness = [
        {'x': d, 'y': float(r['soreness'])}
        for d, r in self_by_date.items() if r['soreness'] is not None
    ]
    mood = [
        {'x': d, 'y': float(r['mood'])}
        for d, r in self_by_date.items() if r['mood'] is not None
    ]

    sleep_score = {
        'self': [
            {'x': d, 'y': float(r['sleep_quality']) * _SELF_REPORT_TO_100}
            for d, r in self_by_date.items() if r['sleep_quality'] is not None
        ],
        'device': _maybe_series(daily_by_date, 'sleep_score'),
    }
    energy = {
        'self': [
            {'x': d, 'y': float(r['energy']) * _SELF_REPORT_TO_100}
            for d, r in self_by_date.items() if r['energy'] is not None
        ],
        # Body battery is bucketed daily as the trough (`MIN`) — recovery
        # bottoms out at the lowest reading, not the average.
        'device': [
            {'x': d, 'y': float(r['bb_low'])}
            for d, r in garmin_by_date.items() if r['bb_low'] is not None
        ],
    }

    # #469 — chart-side conversion: storage is canonical kg, but imperial-pref
    # athletes see lb-shaped y-values + a "lb" unit label on the chart.
    from units import (
        normalize_unit_preference, display_weight, weight_unit_label,
    )
    unit_pref = normalize_unit_preference(unit_pref)
    wt_label = weight_unit_label(unit_pref)

    body = {'weight': [], 'body_fat_pct': [], 'resting_hr': []}
    body_units = {'weight': wt_label}
    for r in body_rows:
        d = _d(r['date'])
        if r['weight_kg'] is not None:
            v = display_weight(r['weight_kg'], unit_pref)
            if v is not None:
                body['weight'].append({'x': d, 'y': round(float(v), 1)})
        if r['body_fat_pct'] is not None:
            body['body_fat_pct'].append({'x': d, 'y': float(r['body_fat_pct'])})
        if r['resting_hr'] is not None:
            body['resting_hr'].append({'x': d, 'y': float(r['resting_hr'])})

    cardio_min = {_d(r['date']): float(r['minutes']) for r in cardio_rows}
    strength_min = {_d(r['date']): float(r['minutes']) for r in strength_rows}
    load_dates = sorted(set(cardio_min) | set(strength_min))
    training = {
        'cardio_min':   [{'x': d, 'y': cardio_min.get(d, 0.0)}   for d in load_dates],
        'strength_min': [{'x': d, 'y': strength_min.get(d, 0.0)} for d in load_dates],
    } if load_dates else {}

    # Activities-done — count cardio + strength sessions per day. Strength
    # rows without a duration still count (different question from training
    # load).
    cardio_n = {_d(r['date']): int(r['n']) for r in cardio_rows}
    strength_n = {_d(r['date']): int(r['n']) for r in strength_count_rows}
    activity_dates = sorted(set(cardio_n) | set(strength_n))
    activities = [
        {'x': d, 'y': cardio_n.get(d, 0) + strength_n.get(d, 0)}
        for d in activity_dates
    ]

    # Heart-rate card: resting (MIN, the overnight low) + avg + peak, all on
    # one chart so the daily spread is visible at a glance.
    heart_rate = {
        'resting': _series(garmin_rows, 'resting_hr'),
        'avg':     _series(garmin_rows, 'avg_hr'),
        'peak':    _series(garmin_rows, 'peak_hr'),
    }
    # Stress: AVG + peak. The user's Garmin Connect shows a single 0–100
    # daily-average stress number; we add peak so the page also surfaces the
    # spike days.
    stress = {
        'avg':  _series(garmin_rows, 'avg_stress'),
        'peak': _series(garmin_rows, 'peak_stress'),
    }
    respiration = {
        'avg':  _series(garmin_rows, 'avg_resp'),
        'low':  _series(garmin_rows, 'min_resp'),
    }
    body_battery = {
        'high': _series(garmin_rows, 'bb_high'),
        'low':  _series(garmin_rows, 'bb_low'),
    }
    # Daily activity from cumulative MonitoringMessage — distance comes out
    # in metres; convert to miles for the chart so it reads alongside cardio
    # mileage on the rest of the app.
    daily_activity = {
        'steps':       _series(garmin_rows, 'daily_steps'),
        'active_cal':  _series(garmin_rows, 'daily_active_cal'),
        'distance_mi': [{'x': p['x'], 'y': round(p['y'] * 0.000621371, 2)}
                        for p in _series(garmin_rows, 'daily_distance_m')],
    }

    hrv = {
        'overnight':    _maybe_series(daily_by_date, 'hrv_overnight_avg_ms'),
        'highest_5min': _maybe_series(daily_by_date, 'hrv_highest_5min_ms'),
    }
    resting_calories = _maybe_series(daily_by_date, 'resting_metabolic_rate')

    # Heart-rate card already pulls min/avg/max from wellness_log; if
    # garmin_daily_metrics has the authoritative resting HR from [211],
    # that wins over wellness_log's MIN (which can catch brief dips and
    # under-report). Render both — the rest line on the HR card swaps to
    # Garmin's value when present.
    garmin_resting_hr = _maybe_series(daily_by_date, 'resting_hr')
    if garmin_resting_hr:
        heart_rate['resting'] = garmin_resting_hr
    heart_rate['resting_7day_avg'] = _maybe_series(
        daily_by_date, 'resting_hr_7day_avg'
    )

    heat_acclimation = _maybe_series(daily_by_date, 'heat_acclimation_pct')
    acute_load = _maybe_series(daily_by_date, 'acute_training_load')
    restless_moments = _maybe_series(daily_by_date, 'restless_moments')
    floors = {
        'climbed':   _maybe_series(daily_by_date, 'floors_climbed'),
        'descended': _maybe_series(daily_by_date, 'floors_descended'),
    }
    intensity_minutes = _maybe_series(daily_by_date, 'intensity_minutes')
    spo2 = {
        'avg': _maybe_series(daily_by_date, 'spo2_avg'),
        'low': _maybe_series(daily_by_date, 'spo2_low'),
    }
    # New device fields decoded in PR #489 — see `garmin_fit_parser` for
    # the field mappings + verification days. Each lights up its own card
    # when there's at least one day with data.
    sleep_deep_min   = _maybe_series(daily_by_date, 'sleep_deep_min')
    sleep_stress_avg = _maybe_series(daily_by_date, 'sleep_stress_avg')
    sleep_wake_count = _maybe_series(daily_by_date, 'sleep_wake_count')
    # `[346]` sleep contributor sub-scores — all 4 locked Jun 10 2026.
    # Surfaced as a single multi-line chart so the operator can see
    # which contributor is dragging the night's score down at a glance.
    sleep_sub_scores = {
        'light':  _maybe_series(daily_by_date, 'sleep_light_sub_score'),
        'rem':    _maybe_series(daily_by_date, 'sleep_rem_sub_score'),
        'stress': _maybe_series(daily_by_date, 'sleep_stress_sub_score'),
        'awake':  _maybe_series(daily_by_date, 'sleep_awake_sub_score'),
    }
    # `[384] field_18` best-guess — % of overnight stress samples above
    # Garmin's "resting" threshold. Tracks "how much of the night was
    # stress-elevated" — complement to body-battery overnight recovery.
    sleep_stress_above_resting = _maybe_series(
        daily_by_date, 'sleep_stress_above_resting_pct'
    )

    # Stress time-in-zone — sample counts × ~3 min interval. Garmin Connect
    # displays the same buckets on the stress page.
    stress_minutes = {
        'rest':   [], 'low':  [], 'medium': [], 'high': [],
    }
    bucket_columns = {
        'rest':   'stress_rest_samples',
        'low':    'stress_low_samples',
        'medium': 'stress_med_samples',
        'high':   'stress_high_samples',
    }
    for r in garmin_rows:
        d = _d(r['date'])
        for bucket, col in bucket_columns.items():
            # SELECT returns these always, but unit-test fixtures may omit
            # them — Row objects raise on missing keys, so guard with a get.
            try:
                n = r[col]
            except (KeyError, IndexError):
                continue
            if n:
                stress_minutes[bucket].append(
                    {'x': d, 'y': round(int(n) * _STRESS_SAMPLE_MIN, 1)}
                )

    # Body battery charged / drained — separately summed positive and
    # negative deltas across the day.
    body_battery['charged'] = [
        {'x': d, 'y': float(r['charged'])}
        for d, r in bb_delta_by_date.items() if r['charged'] is not None
    ]
    body_battery['drained'] = [
        {'x': d, 'y': float(r['drained'])}
        for d, r in bb_delta_by_date.items() if r['drained'] is not None
    ]
    # Body battery overnight delta — the BB jump during the per-night sleep
    # window (sleep_end value − sleep_start value). Cleaner "how restful
    # was this sleep?" signal than the raw sleep score, especially
    # surfaced against May 30 (+47, score 65) vs Jun 2 (+27, score 58)
    # where the lower-score-but-higher-BB-gain night was actually the
    # better recovery (#283 follow-up).
    body_battery['overnight_delta'] = [
        {'x': d, 'y': int(r['bb_end']) - int(r['bb_start'])}
        for d, r in bb_overnight_by_date.items()
        if r['bb_start'] is not None and r['bb_end'] is not None
    ]

    return {
        'sleep_hours':   sleep_hours,
        'sleep_score':   sleep_score,
        'energy':        energy,
        'soreness':      soreness,
        'mood':          mood,
        'body':          {k: v for k, v in body.items() if v},
        'training':      training,
        'activities':    activities,
        'heart_rate':    heart_rate,
        'stress':        stress,
        'respiration':   respiration,
        'body_battery':  body_battery,
        'daily_activity': daily_activity,
        'hrv':              hrv,
        'resting_calories': resting_calories,
        'stress_minutes':   stress_minutes,
        'heat_acclimation': heat_acclimation,
        'acute_load':       acute_load,
        'restless_moments': restless_moments,
        'floors':           floors,
        'intensity_minutes': intensity_minutes,
        'spo2':             spo2,
        'sleep_deep_min':   sleep_deep_min,
        'sleep_stress_avg': sleep_stress_avg,
        'sleep_wake_count': sleep_wake_count,
        'sleep_sub_scores': sleep_sub_scores,
        'sleep_stress_above_resting': sleep_stress_above_resting,
        # #283 follow-up — these still need their own FIT file types or a
        # field map we haven't decoded. `active_minutes` was retired in
        # favour of `intensity_minutes` (Garmin's published metric =
        # moderate + 2 × vigorous, already wired from MonitoringMessage).
        'training_readiness': [],
        'vo2max_running':     [],
        'vo2max_cycling':     [],
    }


def _series(rows, column: str) -> list:
    """{x: date, y: value} from a SELECT result, skipping NULLs."""
    out = []
    for r in rows:
        v = r[column]
        if v is not None:
            out.append({'x': _d(r['date']), 'y': float(v)})
    return out


def _maybe_series(by_date: dict, column: str) -> list:
    """Like `_series` but reads from the {date: row} dict shape and tolerates
    rows that don't carry the column at all (older SELECTs, unit fixtures)."""
    out = []
    for d, r in by_date.items():
        try:
            v = r[column]
        except (KeyError, IndexError):
            continue
        if v is not None:
            out.append({'x': d, 'y': float(v)})
    return out


def _has_any_data(chart_data) -> bool:
    """True if any chart has at least one point."""
    for v in chart_data.values():
        if isinstance(v, list) and v:
            return True
        if isinstance(v, dict):
            for sub in v.values():
                if sub:
                    return True
    return False
