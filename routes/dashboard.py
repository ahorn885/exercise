import os
import time

import requests
from flask import Blueprint, render_template
from database import get_db
from datetime import date, timedelta
from routes.auth import current_user_id
from plan_sessions_repo import load_scheduled_sessions_for_window

bp = Blueprint('dashboard', __name__)

_weather_cache = {}


def _v2_session_card(session) -> dict:
    """Normalize a v2 `PlanSession` into the dict shape the dashboard
    Today/Tomorrow cards render for legacy `plan_items` rows, so both models
    flow through the same template markup. `is_v2` flips the card's links +
    actions over to the v2 plan view (v2 has no per-session item routes).

    Labels mirror `plan_create/view.html` (rest → "Rest"; strength →
    "Strength · <sport>"; cardio → discipline name) so the dashboard reads
    consistently with the plan page.
    """
    kind = session.kind
    if kind == 'rest':
        name = 'Rest'
    elif kind == 'strength':
        name = 'Strength'
        if session.discipline_name:
            name += f' · {session.discipline_name}'
    else:
        name = session.discipline_name or session.discipline_id or kind.title()

    item_date = session.date
    return {
        'is_v2': True,
        'plan_version_id': session.plan_version_id,
        'workout_name': name,
        'sport_type': kind,
        'target_duration_min': session.duration_min,
        # Rest days carry no meaningful intensity; the template hides falsy.
        'intensity': None if kind == 'rest' else session.intensity_summary,
        'locale_name': session.locale_name,
        'plan_name': 'Generated plan',
        'item_date': item_date.isoformat() if hasattr(item_date, 'isoformat')
        else item_date,
    }


def _has_plan_version(db, user_id: int) -> bool:
    """True when the athlete has at least one `plan_versions` row.

    Drives the dashboard Refresh-CTA enable/disable state: with no prior plan,
    `/plans/v2/refresh` only renders an empty-state pointing back to
    `/plans/v2/new`, so we surface that signal up-front rather than bouncing
    the athlete through the route.
    """
    row = db.execute(
        "SELECT 1 FROM plan_versions WHERE user_id = ? LIMIT 1",
        (user_id,),
    ).fetchone()
    return row is not None


def _get_weather(db):
    today = date.today().isoformat()
    ts_now = time.time()
    uid = current_user_id()

    loc = ''
    # plan_travel is parent-JOIN scoped via training_plans
    trip = db.execute(
        "SELECT pt.city FROM plan_travel pt "
        "JOIN training_plans tp ON tp.id = pt.plan_id "
        "WHERE tp.user_id=? AND pt.start_date<=? AND pt.end_date>=? AND pt.city!='' LIMIT 1",
        (uid, today, today)).fetchone()
    if trip:
        loc = trip['city']
    else:
        home = db.execute(
            "SELECT city FROM locale_profiles WHERE preferred AND user_id=? LIMIT 1",
            (uid,)
        ).fetchone()
        if home and home['city']:
            loc = home['city']
    if not loc:
        loc = os.environ.get('WEATHER_LOCATION', '')

    cache_key = loc or '__auto__'
    cached = _weather_cache.get(cache_key)
    if cached and ts_now - cached['ts'] < 1800:
        return cached['data']
    try:
        r = requests.get(f'https://wttr.in/{loc}?format=j1', timeout=3)
        data = r.json()
        _weather_cache[cache_key] = {'data': data, 'ts': ts_now}
        return data
    except Exception:
        return None


@bp.route('/')
def index():
    db = get_db()
    uid = current_user_id()
    today = date.today().isoformat()
    tomorrow = (date.today() + timedelta(days=1)).isoformat()
    week_ago = (date.today() - timedelta(days=7)).isoformat()

    stats = {
        'training_total': db.execute(
            'SELECT COUNT(*) FROM training_log WHERE user_id = ?', (uid,)
        ).fetchone()[0],
        'cardio_total': db.execute(
            'SELECT COUNT(*) FROM cardio_log WHERE user_id = ?', (uid,)
        ).fetchone()[0],
        'active_injuries': db.execute(
            "SELECT COUNT(*) FROM injury_log WHERE user_id = ? AND status='Active'", (uid,)
        ).fetchone()[0],
        'exercises_progress': db.execute(
            "SELECT COUNT(*) FROM current_rx WHERE user_id = ? AND last_outcome='PROGRESS ↑'",
            (uid,)
        ).fetchone()[0],
        'latest_weight': None,
    }

    wt = db.execute(
        'SELECT weight_kg, date FROM body_metrics WHERE user_id = ? '
        'ORDER BY date DESC LIMIT 1',
        (uid,)
    ).fetchone()
    if wt:
        # #469 — surface body weight in the athlete's display unit. Storage
        # stays canonical kg.
        from units import (
            normalize_unit_preference, display_weight, weight_unit_label,
        )
        from athlete import get_athlete_profile
        profile = get_athlete_profile(db, uid) or {}
        unit_pref = normalize_unit_preference(profile.get('unit_preference'))
        d = display_weight(wt['weight_kg'], unit_pref)
        stats['latest_weight'] = round(d, 1) if d is not None else None
        stats['latest_weight_unit'] = weight_unit_label(unit_pref)
        stats['weight_date'] = wt['date']

    today_workouts = db.execute(
        "SELECT pi.*, tp.name as plan_name FROM plan_items pi "
        "JOIN training_plans tp ON tp.id = pi.plan_id "
        "WHERE tp.user_id=? AND pi.item_date=? AND pi.status='scheduled' AND tp.status!='archived'",
        (uid, today)).fetchall()

    tomorrow_workouts = db.execute(
        "SELECT pi.*, tp.name as plan_name FROM plan_items pi "
        "JOIN training_plans tp ON tp.id = pi.plan_id "
        "WHERE tp.user_id=? AND pi.item_date=? AND pi.status='scheduled' AND tp.status!='archived'",
        (uid, tomorrow)).fetchall()

    # AI-generated (v2) plans live in `plan_versions`/`plan_sessions`, NOT the
    # legacy `plan_items` model the queries above read — so without this an
    # active v2 plan's sessions never show on the dashboard. Resolve "what's
    # scheduled today/tomorrow" via the same per-day version pointer the plan
    # view + refresh use (latest active version wins per date), then normalize
    # each PlanSession into the card shape the template already renders. Legacy
    # rows and v2 cards coexist in the same lists; `is_v2` switches the links.
    today_d = date.today()
    tomorrow_d = today_d + timedelta(days=1)
    today_workouts = list(today_workouts) + [
        _v2_session_card(s)
        for s in load_scheduled_sessions_for_window(
            db, uid, start=today_d, end=today_d
        )
    ]
    tomorrow_workouts = list(tomorrow_workouts) + [
        _v2_session_card(s)
        for s in load_scheduled_sessions_for_window(
            db, uid, start=tomorrow_d, end=tomorrow_d
        )
    ]

    missed_workouts = db.execute(
        "SELECT pi.*, tp.name as plan_name FROM plan_items pi "
        "JOIN training_plans tp ON tp.id = pi.plan_id "
        "WHERE tp.user_id=? AND pi.item_date >= ? AND pi.item_date < ? "
        "  AND pi.status='scheduled' AND tp.status!='archived' "
        "ORDER BY pi.item_date DESC LIMIT 5",
        (uid, week_ago, today)).fetchall()

    recent_training = db.execute(
        'SELECT date, exercise, actual_sets, actual_reps, actual_weight, outcome '
        'FROM training_log WHERE user_id = ? ORDER BY date DESC, id DESC LIMIT 10',
        (uid,)
    ).fetchall()

    recent_cardio = db.execute(
        'SELECT date, activity, duration_min, distance_mi, avg_hr FROM cardio_log '
        'WHERE user_id = ? ORDER BY date DESC LIMIT 5',
        (uid,)
    ).fetchall()

    has_plan_version = _has_plan_version(db, uid)

    weather = _get_weather(db)

    # Cardio sessions in the last 7 days with no conditions log entry
    unconditioned_cardio = db.execute(
        '''SELECT cl.id, cl.date, cl.activity, cl.activity_name, cl.duration_min
           FROM cardio_log cl
           LEFT JOIN conditions_log cond ON cond.cardio_log_id = cl.id
           WHERE cl.user_id = ? AND cl.date >= ? AND cond.id IS NULL
           ORDER BY cl.date DESC''',
        (uid, week_ago)
    ).fetchall()

    # Clothing recommendations for upcoming outdoor sessions
    clothing_recs = []
    try:
        from coaching import get_clothing_context
        active_plan = db.execute(
            "SELECT id FROM training_plans WHERE user_id = ? AND status != 'archived' "
            "ORDER BY start_date DESC LIMIT 1",
            (uid,)
        ).fetchone()
        if active_plan:
            today_str = date.today().isoformat()
            trip = db.execute(
                "SELECT pt.city FROM plan_travel pt "
                "JOIN training_plans tp ON tp.id = pt.plan_id "
                "WHERE tp.user_id=? AND pt.start_date<=? AND pt.end_date>=? "
                "  AND pt.city!='' LIMIT 1",
                (uid, today_str, today_str)
            ).fetchone()
            city = trip['city'] if trip else ''
            if not city:
                home = db.execute(
                    "SELECT city FROM locale_profiles WHERE preferred AND user_id=? LIMIT 1",
                    (uid,)
                ).fetchone()
                city = home['city'] if home and home['city'] else ''
            clothing_recs = get_clothing_context(db, active_plan['id'], city)
    except Exception:
        pass

    return render_template('dashboard.html', stats=stats,
                           recent_training=recent_training,
                           recent_cardio=recent_cardio,
                           today_workouts=today_workouts,
                           tomorrow_workouts=tomorrow_workouts,
                           missed_workouts=missed_workouts,
                           weather=weather,
                           today=today,
                           clothing_recs=clothing_recs,
                           unconditioned_cardio=unconditioned_cardio,
                           has_plan_version=has_plan_version)
