import json
from datetime import datetime
from itertools import groupby
from datetime import date as date_type

from flask import Blueprint, render_template, request, redirect, url_for, flash, jsonify
from database import get_db

bp = Blueprint('plans', __name__, url_prefix='/plans')


def _calorie_target(sport_type, intensity, duration_min):
    """Return a calorie range string for a workout based on type/intensity/duration."""
    duration_min = duration_min or 0
    if sport_type == 'hiking' and duration_min >= 300:
        return '4700–6200'
    if sport_type == 'hiking' and duration_min >= 180:
        return '3900–4500'
    if intensity == 'very_hard' or duration_min > 180:
        return '3900–4500'
    if intensity == 'hard' or duration_min >= 90:
        return '3400–3800'
    if intensity in ('easy', 'moderate'):
        return '3000–3200'
    return '2800–2900'


def _create_plan_from_dict(db, data):
    """Insert a training plan from a dict. Returns plan_id."""
    workouts = data.get('workouts', [])
    raw = json.dumps(data)
    cur = db.execute(
        '''INSERT INTO training_plans
           (name, description, sport_focus, start_date, end_date, source_json)
           VALUES (?,?,?,?,?,?)''',
        (data['name'], data.get('description'), data.get('sport_focus'),
         data.get('start_date'), data.get('end_date'), raw)
    )
    plan_id = cur.lastrowid
    for w in workouts:
        garmin_json = w.get('garmin_workout_json')
        garmin_str = json.dumps(garmin_json) if garmin_json else None
        db.execute(
            '''INSERT INTO plan_items
               (plan_id, item_date, sport_type, workout_name, description,
                target_duration_min, target_distance_mi, intensity, garmin_workout_json)
               VALUES (?,?,?,?,?,?,?,?,?)''',
            (plan_id, w.get('date'), w.get('sport_type', ''),
             w.get('workout_name', ''), w.get('description'),
             w.get('target_duration_min'), w.get('target_distance_mi'),
             w.get('intensity'), garmin_str)
        )
    return plan_id


def _plan_health(db, plan_id):
    """Compute plan review health status for the three-tier incremental pattern."""
    plan = db.execute('SELECT created_at FROM training_plans WHERE id=?', (plan_id,)).fetchone()
    plan_created = plan['created_at'] if plan else '1970-01-01'

    last_t1 = db.execute(
        'SELECT sessions_reviewed FROM plan_reviews WHERE plan_id=? AND tier=1 ORDER BY created_at DESC LIMIT 1',
        (plan_id,)
    ).fetchone()
    last_t2 = db.execute(
        'SELECT created_at FROM plan_reviews WHERE plan_id=? AND tier=2 ORDER BY created_at DESC LIMIT 1',
        (plan_id,)
    ).fetchone()

    current_completed = db.execute(
        "SELECT COUNT(*) FROM plan_items WHERE plan_id=? AND status='completed'",
        (plan_id,)
    ).fetchone()[0]

    sessions_since_t1 = current_completed - (last_t1['sessions_reviewed'] if last_t1 else 0)

    # Use plan creation date as baseline if never reviewed at tier 2
    baseline_t2 = last_t2['created_at'] if last_t2 else plan_created
    try:
        baseline_dt = datetime.fromisoformat(baseline_t2.split('.')[0])
        days_since_t2 = (datetime.now() - baseline_dt).days
    except Exception:
        days_since_t2 = 0

    scheduled_remaining = db.execute(
        "SELECT COUNT(*) FROM plan_items WHERE plan_id=? AND status='scheduled'",
        (plan_id,)
    ).fetchone()[0]

    tier1_due = sessions_since_t1 > 0
    tier2_due = days_since_t2 >= 7 or sessions_since_t1 >= 5
    tier3_due = 0 < scheduled_remaining <= 7

    recent = db.execute(
        '''SELECT item_date, workout_name, sport_type, status, notes
           FROM plan_items WHERE plan_id=? AND status IN ('completed','skipped')
           ORDER BY item_date DESC LIMIT 5''',
        (plan_id,)
    ).fetchall()

    upcoming = db.execute(
        '''SELECT item_date, workout_name, sport_type, intensity, target_duration_min
           FROM plan_items WHERE plan_id=? AND status='scheduled'
           ORDER BY item_date ASC LIMIT 7''',
        (plan_id,)
    ).fetchall()

    # Compliance data for recently completed items linked to cardio_log
    compliance_rows = db.execute(
        '''SELECT pi.item_date, pi.workout_name,
                  pi.target_duration_min, pi.target_distance_mi,
                  cl.duration_min as actual_duration_min,
                  cl.distance_mi as actual_distance_mi,
                  cl.activity_name as garmin_activity_name,
                  cl.avg_hr, cl.garmin_activity_id
           FROM plan_items pi
           JOIN cardio_log cl ON cl.plan_item_id = pi.id
           WHERE pi.plan_id = ? AND pi.status = 'completed'
           ORDER BY pi.item_date DESC LIMIT 10''',
        (plan_id,)
    ).fetchall()

    compliance = []
    for cr in compliance_rows:
        dur_pct = None
        dist_pct = None
        if cr['target_duration_min'] and cr['actual_duration_min']:
            dur_pct = round(cr['actual_duration_min'] / cr['target_duration_min'] * 100)
        if cr['target_distance_mi'] and cr['actual_distance_mi']:
            dist_pct = round(cr['actual_distance_mi'] / cr['target_distance_mi'] * 100)
        compliance.append({
            'item_date': cr['item_date'],
            'workout_name': cr['workout_name'],
            'garmin_activity': cr['garmin_activity_name'],
            'duration_pct': dur_pct,
            'distance_pct': dist_pct,
            'avg_hr': cr['avg_hr'],
        })

    return {
        'plan_id': plan_id,
        'sessions_since_tier1': sessions_since_t1,
        'days_since_tier2': days_since_t2,
        'scheduled_remaining': scheduled_remaining,
        'tier1_due': tier1_due,
        'tier2_due': tier2_due,
        'tier3_due': tier3_due,
        'recent_sessions': [dict(r) for r in recent],
        'upcoming_items': [dict(u) for u in upcoming],
        'compliance': compliance,
    }


@bp.route('/')
def list_plans():
    db = get_db()
    plans = db.execute(
        '''SELECT p.*, COUNT(i.id) as item_count,
                  SUM(CASE WHEN i.status = 'completed' THEN 1 ELSE 0 END) as completed_count
           FROM training_plans p
           LEFT JOIN plan_items i ON i.plan_id = p.id
           GROUP BY p.id
           ORDER BY p.start_date DESC'''
    ).fetchall()
    return render_template('plans/list.html', plans=plans)


@bp.route('/import', methods=['GET', 'POST'])
def import_plan():
    if request.method == 'POST':
        raw = request.form.get('plan_json', '').strip()
        if not raw:
            flash('No JSON provided.', 'warning')
            return redirect(url_for('plans.import_plan'))
        try:
            data = json.loads(raw)
        except json.JSONDecodeError as e:
            flash(f'Invalid JSON: {e}', 'danger')
            return redirect(url_for('plans.import_plan'))
        if not data.get('name'):
            flash('Plan JSON must include a "name" field.', 'danger')
            return redirect(url_for('plans.import_plan'))
        db = get_db()
        plan_id = _create_plan_from_dict(db, data)
        db.commit()
        workouts = data.get('workouts', [])
        flash(f'Plan "{data["name"]}" imported with {len(workouts)} workouts.', 'success')
        return redirect(url_for('plans.view_plan', plan_id=plan_id))
    return render_template('plans/import.html')


@bp.route('/api/import', methods=['POST'])
def api_import_plan():
    data = request.get_json(silent=True)
    if not data or not data.get('name'):
        return jsonify({'ok': False, 'error': 'JSON body with "name" field required'}), 400
    db = get_db()
    plan_id = _create_plan_from_dict(db, data)
    db.commit()
    return jsonify({'ok': True, 'plan_id': plan_id})


@bp.route('/api/review', methods=['POST'])
def api_plan_review():
    data = request.get_json(silent=True) or {}
    plan_id = data.get('plan_id')
    tier = data.get('tier')
    if not plan_id or tier not in (1, 2, 3):
        return jsonify({'ok': False, 'error': 'plan_id and tier (1, 2, or 3) required'}), 400
    db = get_db()
    completed = db.execute(
        "SELECT COUNT(*) FROM plan_items WHERE plan_id=? AND status='completed'",
        (plan_id,)
    ).fetchone()[0]
    db.execute(
        'INSERT INTO plan_reviews (plan_id, tier, sessions_reviewed, notes) VALUES (?,?,?,?)',
        (plan_id, tier, completed, data.get('notes', ''))
    )
    db.commit()
    return jsonify({'ok': True})


@bp.route('/items/<int:item_id>', methods=['PATCH'])
def api_patch_plan_item(item_id):
    data = request.get_json(silent=True) or {}
    allowed = {'description', 'intensity', 'target_duration_min', 'target_distance_mi',
               'notes', 'workout_name'}
    updates = {k: v for k, v in data.items() if k in allowed}
    if not updates:
        return jsonify({'ok': False, 'error': 'No valid fields to update'}), 400
    db = get_db()
    set_clause = ', '.join(f'{k}=?' for k in updates)
    values = list(updates.values()) + [item_id]
    db.execute(f'UPDATE plan_items SET {set_clause} WHERE id=?', values)
    db.commit()
    return jsonify({'ok': True})


@bp.route('/<int:plan_id>/health')
def plan_health(plan_id):
    db = get_db()
    if not db.execute('SELECT id FROM training_plans WHERE id=?', (plan_id,)).fetchone():
        return jsonify({'error': 'Plan not found'}), 404
    return jsonify(_plan_health(db, plan_id))


@bp.route('/<int:plan_id>/delete', methods=['POST'])
def delete_plan(plan_id):
    db = get_db()
    db.execute('DELETE FROM plan_reviews WHERE plan_id=?', (plan_id,))
    db.execute('DELETE FROM plan_items WHERE plan_id=?', (plan_id,))
    db.execute('DELETE FROM training_plans WHERE id=?', (plan_id,))
    db.commit()
    if request.is_json or request.headers.get('Accept') == 'application/json':
        return jsonify({'ok': True})
    flash('Plan deleted.', 'warning')
    return redirect(url_for('plans.list_plans'))


@bp.route('/<int:plan_id>')
def view_plan(plan_id):
    db = get_db()
    plan = db.execute('SELECT * FROM training_plans WHERE id = ?', (plan_id,)).fetchone()
    if not plan:
        flash('Plan not found.', 'danger')
        return redirect(url_for('plans.list_plans'))
    items = db.execute(
        'SELECT * FROM plan_items WHERE plan_id = ? ORDER BY item_date ASC',
        (plan_id,)
    ).fetchall()

    def week_key(item):
        try:
            d = date_type.fromisoformat(item['item_date'])
            return d.isocalendar()[:2]
        except Exception:
            return (0, 0)

    weeks = {}
    for item in items:
        key = week_key(item)
        weeks.setdefault(key, []).append(item)

    total = len(items)
    completed = sum(1 for i in items if i['status'] == 'completed')

    active_mods = db.execute(
        '''SELECT iem.modification_type, iem.modification_notes,
                  il.body_part, il.status,
                  ei.exercise as exercise_name,
                  ei_sub.exercise as substitute_name
           FROM injury_exercise_modifications iem
           JOIN injury_log il ON il.id = iem.injury_id
           JOIN exercise_inventory ei ON ei.id = iem.exercise_id
           LEFT JOIN exercise_inventory ei_sub ON ei_sub.id = iem.substitute_exercise_id
           WHERE il.status IN ('Active', 'Managing')
           ORDER BY il.status, il.body_part, ei.exercise'''
    ).fetchall()

    affected_exercises = {m['exercise_name'] for m in active_mods}
    health = _plan_health(db, plan_id)

    return render_template('plans/view.html', plan=plan, weeks=weeks,
                           total=total, completed=completed,
                           active_mods=active_mods,
                           affected_exercises=affected_exercises,
                           health=health,
                           calorie_target=_calorie_target)


@bp.route('/<int:plan_id>/item/<int:item_id>')
def view_item(plan_id, item_id):
    db = get_db()
    item = db.execute(
        'SELECT * FROM plan_items WHERE id = ? AND plan_id = ?', (item_id, plan_id)
    ).fetchone()
    if not item:
        flash('Item not found.', 'danger')
        return redirect(url_for('plans.view_plan', plan_id=plan_id))
    garmin_workout = None
    if item['garmin_workout_json']:
        try:
            garmin_workout = json.loads(item['garmin_workout_json'])
        except Exception:
            pass
    gw = db.execute(
        'SELECT * FROM garmin_workouts WHERE plan_item_id = ? AND status = "active"',
        (item_id,)
    ).fetchone()
    try:
        from garmin_connect import get_auth_status
        auth_status = get_auth_status(db)
    except Exception:
        auth_status = {'authenticated': False, 'username': None}
    return render_template('plans/item.html', plan_id=plan_id, item=item,
                           garmin_workout=garmin_workout, gw=gw,
                           auth_status=auth_status)


@bp.route('/<int:plan_id>/item/<int:item_id>/complete', methods=['POST'])
def complete_item(plan_id, item_id):
    db = get_db()
    notes = request.form.get('notes', '')
    db.execute(
        "UPDATE plan_items SET status = 'completed', notes = ? WHERE id = ? AND plan_id = ?",
        (notes, item_id, plan_id)
    )
    db.commit()
    flash('Workout marked as completed.', 'success')
    return redirect(url_for('plans.view_plan', plan_id=plan_id))


@bp.route('/<int:plan_id>/item/<int:item_id>/skip', methods=['POST'])
def skip_item(plan_id, item_id):
    db = get_db()
    notes = request.form.get('notes', '')
    db.execute(
        "UPDATE plan_items SET status = 'skipped', notes = ? WHERE id = ? AND plan_id = ?",
        (notes, item_id, plan_id)
    )
    db.commit()
    flash('Workout marked as skipped.', 'warning')
    return redirect(url_for('plans.view_plan', plan_id=plan_id))


@bp.route('/<int:plan_id>/item/<int:item_id>/push-to-garmin', methods=['POST'])
def push_to_garmin(plan_id, item_id):
    db = get_db()
    item = db.execute(
        'SELECT * FROM plan_items WHERE id = ? AND plan_id = ?', (item_id, plan_id)
    ).fetchone()
    if not item:
        flash('Item not found.', 'danger')
        return redirect(url_for('plans.view_plan', plan_id=plan_id))
    if not item['garmin_workout_json']:
        flash('No Garmin workout JSON attached to this plan item.', 'warning')
        return redirect(url_for('plans.view_item', plan_id=plan_id, item_id=item_id))
    try:
        from garmin_connect import upload_workout, schedule_workout
        workout_json = json.loads(item['garmin_workout_json'])
        workout_id = upload_workout(db, workout_json)
        if item['item_date']:
            schedule_workout(db, workout_id, item['item_date'])
        db.execute(
            '''INSERT INTO garmin_workouts
               (plan_item_id, garmin_workout_id, workout_name, sport_type, scheduled_date)
               VALUES (?,?,?,?,?)''',
            (item_id, workout_id, item['workout_name'],
             item['sport_type'], item['item_date'])
        )
        db.commit()
        flash(f'Workout uploaded to Garmin Connect (ID: {workout_id}).', 'success')
    except Exception as e:
        flash(f'Garmin upload failed: {e}', 'danger')
    return redirect(url_for('plans.view_item', plan_id=plan_id, item_id=item_id))
