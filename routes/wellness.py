"""Unified multi-source wellness dashboard.

Combines four data domains on one page:

  1. Self-report (sleep, energy, soreness, mood) — `wellness_self_report`,
     entered via the form at the top of the page.
  2. Body composition (weight, body fat %, resting HR) — `body_metrics`.
  3. Training load (cardio + strength minutes per day) — `cardio_log` +
     `training_sessions` joined to `training_log`.
  4. Garmin wellness daily aggregates (avg HR, peak stress, min body
     battery) — `wellness_log`.

Each domain renders independently and degrades gracefully when there's
no data in the range. The provider-OAuth domain (Strava/Polar/Wahoo)
is referenced in the page footer but not yet wired — the OAuth callback
stubs return 501 today.
"""
from datetime import date, datetime, timedelta

from flask import Blueprint, render_template, request, redirect, url_for, flash

import database
from database import get_db
from routes.auth import current_user_id

bp = Blueprint('wellness', __name__)

_RANGE_CHOICES = {'7': 7, '30': 30, '90': 90}
_DEFAULT_RANGE_DAYS = 30
_RATING_FIELDS = ('sleep_quality', 'energy', 'soreness', 'mood')


def _parse_range_days() -> int:
    raw = (request.args.get('range') or str(_DEFAULT_RANGE_DAYS)).strip()
    return _RANGE_CHOICES.get(raw, _DEFAULT_RANGE_DAYS)


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
    cutoff = (date.today() - timedelta(days=range_days - 1)).isoformat()

    today_iso = date.today().isoformat()
    today_row = db.execute(
        'SELECT * FROM wellness_self_report WHERE user_id=? AND date=?',
        (uid, today_iso)
    ).fetchone()

    self_report_rows = db.execute(
        'SELECT date, sleep_hours, sleep_quality, energy, soreness, mood '
        'FROM wellness_self_report WHERE user_id=? AND date >= ? '
        'ORDER BY date',
        (uid, cutoff)
    ).fetchall()

    body_rows = db.execute(
        'SELECT date, weight_lbs, body_fat_pct, resting_hr '
        'FROM body_metrics WHERE user_id=? AND date >= ? ORDER BY date',
        (uid, cutoff)
    ).fetchall()

    # Training load — cardio.duration_min + strength training_log.actual_duration
    # (sec → min) per day. Strength sessions without an actual_duration
    # contribute 0 minutes; we'd rather under-count than guess.
    cardio_load = db.execute(
        'SELECT date, COALESCE(SUM(duration_min), 0) AS minutes '
        'FROM cardio_log WHERE user_id=? AND date >= ? '
        'GROUP BY date ORDER BY date',
        (uid, cutoff)
    ).fetchall()
    strength_load = db.execute(
        'SELECT date, COALESCE(SUM(actual_duration), 0)/60.0 AS minutes '
        'FROM training_log WHERE user_id=? AND date >= ? '
        'AND actual_duration IS NOT NULL '
        'GROUP BY date ORDER BY date',
        (uid, cutoff)
    ).fetchall()

    # Garmin wellness daily aggregates. wellness_log is a per-minute series
    # so we collapse to per-day stats: daytime avg HR, peak stress, lowest
    # body battery (the trough is the meaningful value, not the average).
    garmin_rows = db.execute(
        'SELECT date, '
        '  AVG(heart_rate)    AS avg_hr, '
        '  MAX(stress_level)  AS peak_stress, '
        '  MIN(body_battery)  AS min_bb '
        'FROM wellness_log WHERE user_id=? AND date >= ? '
        'GROUP BY date ORDER BY date',
        (uid, cutoff)
    ).fetchall()

    chart_data = {
        'self_report': _series_self_report(self_report_rows),
        'body':        _series_body(body_rows),
        'training':    _series_training(cardio_load, strength_load),
        'garmin':      _series_garmin(garmin_rows),
    }

    return render_template(
        'wellness/index.html',
        today_iso=today_iso,
        today_row=dict(today_row) if today_row else {},
        range_days=range_days,
        range_choices=sorted(_RANGE_CHOICES.values()),
        chart_data=chart_data,
        has_any_data=any(chart_data.values()),
    )


def _save_self_report(db, uid):
    submitted_date = (request.form.get('date') or date.today().isoformat()).strip()
    try:
        # Parse loose — reject obviously bad input but accept the common
        # YYYY-MM-DD form without further normalization.
        datetime.strptime(submitted_date, '%Y-%m-%d')
    except ValueError:
        flash('Invalid date.', 'danger')
        return redirect(url_for('wellness.index'))

    sleep_hours   = _parse_float(request.form.get('sleep_hours'))
    sleep_quality = _parse_int(request.form.get('sleep_quality'), lo=1, hi=5)
    energy        = _parse_int(request.form.get('energy'),        lo=1, hi=5)
    soreness      = _parse_int(request.form.get('soreness'),      lo=1, hi=5)
    mood          = _parse_int(request.form.get('mood'),          lo=1, hi=5)
    notes         = (request.form.get('notes') or '').strip() or None

    # UPSERT on (user_id, date). The UNIQUE constraint is the conflict
    # target on both backends; database.py's `?` placeholder handles the
    # parameter style.
    existing = db.execute(
        'SELECT id FROM wellness_self_report WHERE user_id=? AND date=?',
        (uid, submitted_date)
    ).fetchone()
    now_sql = 'NOW()' if database._is_postgres() else "datetime('now')"
    if existing:
        db.execute(
            f'UPDATE wellness_self_report SET '
            f'sleep_hours=?, sleep_quality=?, energy=?, soreness=?, mood=?, notes=?, '
            f'updated_at={now_sql} '
            f'WHERE id=?',
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
    return redirect(url_for('wellness.index', range=request.form.get('range') or ''))


# ─── Series builders ─────────────────────────────────────────────────────────
# Each returns either a list of {x, y} points (Chart.js linear scale) or
# {} when empty so the template can hide the section.

def _d(value) -> str:
    """Stringify a date that may arrive as datetime.date (PG) or str (SQLite)."""
    return str(value)[:10] if value is not None else ''


def _series_self_report(rows):
    if not rows:
        return {}
    out = {f: [] for f in ('sleep_hours',) + _RATING_FIELDS}
    for r in rows:
        d = _d(r['date'])
        for f in out:
            v = r[f]
            if v is not None:
                out[f].append({'x': d, 'y': float(v)})
    return out if any(out.values()) else {}


def _series_body(rows):
    if not rows:
        return {}
    out = {'weight_lbs': [], 'body_fat_pct': [], 'resting_hr': []}
    for r in rows:
        d = _d(r['date'])
        for f in out:
            v = r[f]
            if v is not None:
                out[f].append({'x': d, 'y': float(v)})
    return out if any(out.values()) else {}


def _series_training(cardio_rows, strength_rows):
    if not cardio_rows and not strength_rows:
        return {}
    cardio = {_d(r['date']): float(r['minutes']) for r in cardio_rows}
    strength = {_d(r['date']): float(r['minutes']) for r in strength_rows}
    all_dates = sorted(set(cardio) | set(strength))
    return {
        'cardio_min':   [{'x': d, 'y': cardio.get(d, 0.0)}   for d in all_dates],
        'strength_min': [{'x': d, 'y': strength.get(d, 0.0)} for d in all_dates],
    }


def _series_garmin(rows):
    if not rows:
        return {}
    out = {'avg_hr': [], 'peak_stress': [], 'min_bb': []}
    for r in rows:
        d = _d(r['date'])
        if r['avg_hr']      is not None: out['avg_hr'].append({'x': d, 'y': float(r['avg_hr'])})
        if r['peak_stress'] is not None: out['peak_stress'].append({'x': d, 'y': float(r['peak_stress'])})
        if r['min_bb']      is not None: out['min_bb'].append({'x': d, 'y': float(r['min_bb'])})
    return out if any(out.values()) else {}
