import json
from flask import Blueprint, render_template, request, redirect, url_for, flash
from database import get_db

bp = Blueprint('plans', __name__, url_prefix='/plans')


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

        workouts = data.get('workouts', [])
        if not data.get('name'):
            flash('Plan JSON must include a "name" field.', 'danger')
            return redirect(url_for('plans.import_plan'))

        db = get_db()
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
        db.commit()
        flash(f'Plan "{data["name"]}" imported with {len(workouts)} workouts.', 'success')
        return redirect(url_for('plans.view_plan', plan_id=plan_id))

    return render_template('plans/import.html')


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
    # Group items by ISO week
    from itertools import groupby
    from datetime import date as date_type
    def week_key(item):
        try:
            d = date_type.fromisoformat(item['item_date'])
            return d.isocalendar()[:2]  # (year, week)
        except Exception:
            return (0, 0)
    weeks = {}
    for item in items:
        key = week_key(item)
        weeks.setdefault(key, []).append(item)
    total = len(items)
    completed = sum(1 for i in items if i['status'] == 'completed')
    return render_template('plans/view.html', plan=plan, weeks=weeks,
                           total=total, completed=completed)


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
    # Check if already pushed to Garmin
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
