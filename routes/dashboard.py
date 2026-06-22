import os
import time

import requests
from flask import Blueprint, render_template
from database import get_db
from datetime import date, timedelta
from routes.auth import current_user_id
from plan_sessions_repo import (
    load_active_plan_version_for_date,
    load_scheduled_sessions_for_window,
)
from plan_naming import target_race_name, generated_plan_name
from athlete_event_windows_repo import resolve_weather_city

bp = Blueprint('dashboard', __name__)

_weather_cache = {}


def _v2_plan_names(db, user_id: int, sessions) -> dict:
    """Map each v2 session's `plan_version_id` to its derived display name
    (#620), so the dashboard's plan reference matches the plans list + header.
    One target-race read for the batch; the per-plan week suffix comes from each
    version's scope dates. Returns {} when there are no v2 sessions (the common
    new-user case) so we skip the queries entirely."""
    ids = {s.plan_version_id for s in sessions}
    if not ids:
        return {}
    race_name = target_race_name(db, user_id)
    placeholders = ','.join('?' * len(ids))
    rows = db.execute(
        f"SELECT id, scope_start_date, scope_end_date FROM plan_versions "
        f"WHERE id IN ({placeholders}) AND user_id = ?",
        list(ids) + [user_id],
    ).fetchall()
    return {
        r['id']: generated_plan_name(
            race_name, r['scope_start_date'], r['scope_end_date'])
        for r in rows
    }


def _v2_session_card(session, plan_name=None) -> dict:
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
        # Mirror the daily view's "Rest — <reason>" (plan_create/view.html) so
        # an explicit rest session surfaces its reason on the home card too,
        # not just a bare "Rest" (#888).
        name = 'Rest'
        reason = getattr(session, 'rest_reason', None)
        if reason:
            name += f" — {reason.replace('_', ' ').capitalize()}"
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
        'plan_name': plan_name or 'Training plan',
        'item_date': item_date.isoformat() if hasattr(item_date, 'isoformat')
        else item_date,
    }


def _rest_day_card(plan_version_id: int, plan_name: str | None, d: date) -> dict:
    """Synthesize the Today/Tomorrow card for a scheduled REST day — a date that
    sits inside an active plan's scope but carries no session row.

    The v2 generator encodes ordinary rest days as the ABSENCE of a session
    (per_phase `=== Schedule ===` — "Disabled days are rest days"), so without
    this the home card falls through to the "No session scheduled" empty state
    on a rest day even though the plan's daily view renders that same day as an
    explicit rest day (#888). Same card shape as `_v2_session_card` (rest branch)
    so both flow through one template; `sport_type == 'rest'` lets the template
    render it as a recovery day rather than a sport line.
    """
    return {
        'is_v2': True,
        'plan_version_id': plan_version_id,
        'workout_name': 'Rest',
        'sport_type': 'rest',
        'target_duration_min': None,
        'intensity': None,
        'locale_name': None,
        'plan_name': plan_name or 'Training plan',
        'item_date': d.isoformat(),
    }


def _fill_rest_days(
    db, user_id: int, *, today_d, tomorrow_d, today_workouts, tomorrow_workouts
):
    """Fill an empty Today/Tomorrow with an explicit REST card when the date
    still falls inside an active plan's scope (#888).

    The v2 generator encodes ordinary rest days as the ABSENCE of a session, so
    an otherwise-empty day that an active plan still covers is a rest day — the
    plan's daily view already renders it as one (gap-fill in
    `plan_create._plan_days_with_rest_gaps`); this brings the home card in line
    rather than leaving it on the "No session scheduled / no plan" empty state.

    Only fires per day when that day has NO legacy or v2 session, and only
    against an active plan covering the date, so a genuine no-plan day still
    reads as "no session". Returns the (today, tomorrow) lists, filled in place.
    """
    if today_workouts and tomorrow_workouts:
        return today_workouts, tomorrow_workouts
    race_name = target_race_name(db, user_id)
    if not today_workouts:
        pv = load_active_plan_version_for_date(db, user_id, today_d)
        if pv is not None:
            today_workouts = [_rest_day_card(
                pv['id'],
                generated_plan_name(
                    race_name, pv['scope_start_date'], pv['scope_end_date']),
                today_d,
            )]
    if not tomorrow_workouts:
        pv = load_active_plan_version_for_date(db, user_id, tomorrow_d)
        if pv is not None:
            tomorrow_workouts = [_rest_day_card(
                pv['id'],
                generated_plan_name(
                    race_name, pv['scope_start_date'], pv['scope_end_date']),
                tomorrow_d,
            )]
    return today_workouts, tomorrow_workouts


def _supplement_summary(db, user_id: int, today_sessions, today_d) -> dict | None:
    """Standard + today's Daily supplement recommendations for the home page (#621).

    Resolves the plan version scheduled today (or the athlete's latest version),
    loads its Layer 5A `PlanNutrition`, and returns the standing ("always take")
    list plus today's effort/event-based list. Best-effort — any miss (no plan,
    no nutrition artifact yet, today outside scope) returns None / empty so the
    card simply omits rather than breaking the dashboard.
    """
    try:
        from plan_nutrition_repo import load_plan_nutrition_by_version

        pv_id = None
        if today_sessions:
            pv_id = today_sessions[0].plan_version_id
        else:
            row = db.execute(
                "SELECT id FROM plan_versions WHERE user_id = ? "
                "ORDER BY id DESC LIMIT 1",
                (user_id,),
            ).fetchone()
            pv_id = row["id"] if row else None
        if pv_id is None:
            return None

        nutrition = load_plan_nutrition_by_version(db, pv_id)
        if nutrition is None or not nutrition.standing_supplements:
            return None

        today_recs = []
        for day in nutrition.days:
            if day.date == today_d:
                today_recs = day.supplement_recs
                break
        return {
            'standard': nutrition.standing_supplements,
            'daily': today_recs,
        }
    except Exception:
        return None


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
    ts_now = time.time()
    uid = current_user_id()

    loc = resolve_weather_city(db, uid, date.today())
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
    today_v2 = load_scheduled_sessions_for_window(db, uid, start=today_d, end=today_d)
    tomorrow_v2 = load_scheduled_sessions_for_window(
        db, uid, start=tomorrow_d, end=tomorrow_d
    )
    v2_names = _v2_plan_names(db, uid, today_v2 + tomorrow_v2)
    today_workouts = list(today_workouts) + [
        _v2_session_card(s, v2_names.get(s.plan_version_id)) for s in today_v2
    ]
    tomorrow_workouts = list(tomorrow_workouts) + [
        _v2_session_card(s, v2_names.get(s.plan_version_id)) for s in tomorrow_v2
    ]
    today_workouts, tomorrow_workouts = _fill_rest_days(
        db, uid,
        today_d=today_d, tomorrow_d=tomorrow_d,
        today_workouts=today_workouts, tomorrow_workouts=tomorrow_workouts,
    )

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

    # #259/#260 — in-app plan-ready/plan-failed badge. Best-effort: any read
    # fault degrades to an empty list so the dashboard renders rather than 500s
    # (mirrors the `active_nudges` context processor in app.py).
    try:
        from plan_notifications import get_unseen_plan_notifications
        plan_notifications = get_unseen_plan_notifications(db, uid)
    except Exception as e:  # noqa: BLE001 — badge must never break the dashboard
        print(f'dashboard: get_unseen_plan_notifications failed: {e}')
        plan_notifications = []

    supplement_summary = _supplement_summary(db, uid, today_v2, today_d)

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
            city = resolve_weather_city(db, uid, date.today())
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
                           supplement_summary=supplement_summary,
                           plan_notifications=plan_notifications,
                           has_plan_version=has_plan_version)
