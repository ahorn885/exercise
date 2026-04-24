import os
import time

import requests
from flask import Blueprint, render_template
from database import get_db
from datetime import date, timedelta

bp = Blueprint('dashboard', __name__)

_weather_cache = {}


def _get_weather(db):
    today = date.today().isoformat()
    ts_now = time.time()

    loc = ''
    trip = db.execute(
        "SELECT city FROM plan_travel WHERE start_date<=? AND end_date>=? AND city!='' LIMIT 1",
        (today, today)).fetchone()
    if trip:
        loc = trip['city']
    else:
        home = db.execute("SELECT city FROM locale_profiles WHERE locale='home' LIMIT 1").fetchone()
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
    today = date.today().isoformat()
    tomorrow = (date.today() + timedelta(days=1)).isoformat()
    week_ago = (date.today() - timedelta(days=7)).isoformat()

    stats = {
        'training_total': db.execute('SELECT COUNT(*) FROM training_log').fetchone()[0],
        'cardio_total': db.execute('SELECT COUNT(*) FROM cardio_log').fetchone()[0],
        'active_injuries': db.execute("SELECT COUNT(*) FROM injury_log WHERE status='Active'").fetchone()[0],
        'exercises_progress': db.execute("SELECT COUNT(*) FROM current_rx WHERE last_outcome='PROGRESS ↑'").fetchone()[0],
        'latest_weight': None,
    }

    wt = db.execute('SELECT weight_lbs, date FROM body_metrics ORDER BY date DESC LIMIT 1').fetchone()
    if wt:
        stats['latest_weight'] = wt['weight_lbs']
        stats['weight_date'] = wt['date']

    today_workouts = db.execute(
        "SELECT pi.*, tp.name as plan_name FROM plan_items pi "
        "JOIN training_plans tp ON tp.id = pi.plan_id "
        "WHERE pi.item_date=? AND pi.status='scheduled' AND tp.status!='archived'",
        (today,)).fetchall()

    tomorrow_workouts = db.execute(
        "SELECT pi.*, tp.name as plan_name FROM plan_items pi "
        "JOIN training_plans tp ON tp.id = pi.plan_id "
        "WHERE pi.item_date=? AND pi.status='scheduled' AND tp.status!='archived'",
        (tomorrow,)).fetchall()

    missed_workouts = db.execute(
        "SELECT pi.*, tp.name as plan_name FROM plan_items pi "
        "JOIN training_plans tp ON tp.id = pi.plan_id "
        "WHERE pi.item_date >= ? AND pi.item_date < ? AND pi.status='scheduled' AND tp.status!='archived' "
        "ORDER BY pi.item_date DESC LIMIT 5",
        (week_ago, today)).fetchall()

    recent_training = db.execute(
        'SELECT date, exercise, actual_sets, actual_reps, actual_weight, outcome FROM training_log ORDER BY date DESC, id DESC LIMIT 10'
    ).fetchall()

    recent_cardio = db.execute(
        'SELECT date, activity, duration_min, distance_mi, avg_hr FROM cardio_log ORDER BY date DESC LIMIT 5'
    ).fetchall()

    weather = _get_weather(db)

    return render_template('dashboard.html', stats=stats,
                           recent_training=recent_training,
                           recent_cardio=recent_cardio,
                           today_workouts=today_workouts,
                           tomorrow_workouts=tomorrow_workouts,
                           missed_workouts=missed_workouts,
                           weather=weather,
                           today=today)
