"""Unified multi-metric wellness dashboard.

One card per metric, with device readings and self-report overlaid where they
measure the same thing (sleep score, energy / body battery). Reads pull from:

  - `wellness_self_report` — self-reported sleep, energy, soreness, mood
  - `body_metrics`         — weight, body fat %, resting HR
  - `wellness_log`         — Garmin per-second wellness (`_WELLNESS.fit`)
  - `cardio_log`           — cardio activities (count + duration)
  - `training_log`         — strength activities (count + duration)

Sleep score and energy charts overlay self-report (normalized to 0–100) against
the device reading on a single axis. Device-side data for sleep score / HRV /
VO2max / training readiness comes from `_METRICS.fit`, which is not parsed yet
(#283 Phase B, blocked on #196 Phase 1) — those series render as empty
scaffolds.
"""
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
        'SELECT date, weight_lbs, body_fat_pct, resting_hr '
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
    # `_WELLNESS.fit`. Body-battery min (the trough is the meaningful value,
    # not the average) feeds the Energy overlay; HR avg and stress peak get
    # their own cards.
    garmin_rows = db.execute(
        'SELECT date, '
        '  AVG(heart_rate)    AS avg_hr, '
        '  MAX(stress_level)  AS peak_stress, '
        '  MIN(body_battery)  AS min_bb '
        'FROM wellness_log WHERE user_id=? AND date >= ? '
        'GROUP BY date ORDER BY date',
        (uid, cutoff)
    ).fetchall()

    chart_data = _build_chart_data(
        self_report_rows, body_rows,
        cardio_load, strength_load, strength_counts,
        garmin_rows,
    )

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


def _build_chart_data(self_rows, body_rows, cardio_rows, strength_rows,
                      strength_count_rows, garmin_rows):
    self_by_date = {_d(r['date']): r for r in self_rows}
    garmin_by_date = {_d(r['date']): r for r in garmin_rows}

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
        # Garmin sleep score lives in _METRICS.fit — Phase B (#283).
        'device': [],
    }
    energy = {
        'self': [
            {'x': d, 'y': float(r['energy']) * _SELF_REPORT_TO_100}
            for d, r in self_by_date.items() if r['energy'] is not None
        ],
        # Body battery is bucketed daily as the trough (`MIN`) — recovery
        # bottoms out at the lowest reading, not the average.
        'device': [
            {'x': d, 'y': float(r['min_bb'])}
            for d, r in garmin_by_date.items() if r['min_bb'] is not None
        ],
    }

    body = {'weight_lbs': [], 'body_fat_pct': [], 'resting_hr': []}
    for r in body_rows:
        d = _d(r['date'])
        for f in body:
            if r[f] is not None:
                body[f].append({'x': d, 'y': float(r[f])})

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

    avg_hr = [
        {'x': _d(r['date']), 'y': float(r['avg_hr'])}
        for r in garmin_rows if r['avg_hr'] is not None
    ]
    peak_stress = [
        {'x': _d(r['date']), 'y': float(r['peak_stress'])}
        for r in garmin_rows if r['peak_stress'] is not None
    ]

    return {
        'sleep_hours':  sleep_hours,
        'sleep_score':  sleep_score,
        'energy':       energy,
        'soreness':     soreness,
        'mood':         mood,
        'body':         {k: v for k, v in body.items() if v},
        'training':     training,
        'activities':   activities,
        'avg_hr':       avg_hr,
        'peak_stress':  peak_stress,
        # Phase B (#283) — empty scaffolds for the device-only metrics that
        # need _METRICS.fit parsing. Template renders the cards as "no
        # device data yet" until the parser lands.
        'hrv':              [],
        'training_readiness': [],
        'vo2max_running':   [],
        'vo2max_cycling':   [],
        'active_minutes':   [],
    }


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
