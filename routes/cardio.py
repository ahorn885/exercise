import io

from flask import Blueprint, render_template, request, redirect, url_for, flash, send_file
from database import get_db
from fit_workout_generator import generate_activity_fit

bp = Blueprint('cardio', __name__)

ACTIVITIES = [
    'Running', 'Treadmill', 'Trail Running', 'Hiking', 'Stair Climbing',
    'Road Cycling', 'Mountain Biking', 'Gravel Cycling', 'Indoor Bike Trainer',
    'Kayaking', 'Pack Rafting', 'Kayak Ergometer', 'Rowing Ergometer',
    'Swimming Pool', 'Swimming Open', 'Yoga'
]


@bp.route('/cardio')
def list_entries():
    db = get_db()
    date_filter = request.args.get('date', '')
    activity_filter = request.args.get('activity', '')

    query = 'SELECT * FROM cardio_log WHERE 1=1'
    params = []
    if date_filter:
        query += ' AND date=?'
        params.append(date_filter)
    if activity_filter:
        query += ' AND activity LIKE ?'
        params.append(f'%{activity_filter}%')
    query += ' ORDER BY date DESC, id DESC'

    entries = db.execute(query, params).fetchall()
    activities = db.execute('SELECT DISTINCT activity FROM cardio_log ORDER BY activity').fetchall()
    return render_template('cardio/list.html', entries=entries,
                           date_filter=date_filter, activity_filter=activity_filter,
                           activities=activities)


@bp.route('/cardio/new', methods=['GET', 'POST'])
def new_entry():
    db = get_db()
    if request.method == 'POST':
        new_id = _save(db, None)
        flash('Cardio session logged.', 'success')
        if new_id:
            return redirect(url_for('conditions.new_entry', cardio_log_id=new_id))
        return redirect(url_for('cardio.list_entries'))
    plan_items = _load_plan_items(db)
    return render_template('cardio/form.html', entry=None, activities=ACTIVITIES,
                           plan_items=plan_items)


@bp.route('/cardio/<int:entry_id>/edit', methods=['GET', 'POST'])
def edit_entry(entry_id):
    db = get_db()
    entry = db.execute('SELECT * FROM cardio_log WHERE id=?', (entry_id,)).fetchone()
    if not entry:
        flash('Entry not found.', 'danger')
        return redirect(url_for('cardio.list_entries'))
    if request.method == 'POST':
        _save(db, entry_id)
        flash('Entry updated.', 'success')
        return redirect(url_for('cardio.list_entries'))
    plan_items = _load_plan_items(db)
    return render_template('cardio/form.html', entry=entry, activities=ACTIVITIES,
                           plan_items=plan_items)


@bp.route('/cardio/<int:entry_id>/activity-fit')
def activity_fit(entry_id):
    db = get_db()
    entry = db.execute('SELECT * FROM cardio_log WHERE id=?', (entry_id,)).fetchone()
    if not entry:
        flash('Entry not found.', 'danger')
        return redirect(url_for('cardio.list_entries'))
    fit_bytes = generate_activity_fit(dict(entry))
    activity_slug = (entry['activity'] or 'activity').lower().replace(' ', '_')
    filename = f"activity_{entry['date']}_{activity_slug}.fit"
    return send_file(
        io.BytesIO(fit_bytes),
        as_attachment=True,
        download_name=filename,
        mimetype='application/octet-stream',
    )


@bp.route('/cardio/<int:entry_id>/delete', methods=['POST'])
def delete_entry(entry_id):
    db = get_db()
    db.execute('DELETE FROM cardio_log WHERE id=?', (entry_id,))
    db.commit()
    flash('Entry deleted.', 'warning')
    return redirect(url_for('cardio.list_entries'))


def _load_plan_items(db):
    """Return upcoming/recent plan items for the plan item selector."""
    return db.execute(
        '''SELECT pi.id, pi.item_date, pi.workout_name, pi.sport_type,
                  tp.name as plan_name
           FROM plan_items pi
           JOIN training_plans tp ON tp.id = pi.plan_id
           WHERE pi.status = 'scheduled'
           ORDER BY pi.item_date ASC
           LIMIT 60'''
    ).fetchall()


def _save(db, entry_id):
    f = request.form

    def num(v, cast=float):
        try:
            return cast(v) if v else None
        except (ValueError, TypeError):
            return None

    plan_item_id = num(f.get('plan_item_id'), int)

    vals = (
        f.get('date'), f.get('activity'), f.get('activity_name'),
        num(f.get('duration_min')), num(f.get('moving_time_min')),
        num(f.get('distance_mi')), f.get('avg_pace'),
        num(f.get('avg_speed')), num(f.get('avg_hr'), int),
        num(f.get('max_hr'), int), num(f.get('calories'), int),
        num(f.get('elev_gain_ft')), num(f.get('elev_loss_ft')),
        num(f.get('avg_cadence'), int), num(f.get('max_cadence'), int),
        num(f.get('avg_power'), int), num(f.get('max_power'), int),
        num(f.get('norm_power'), int),
        num(f.get('aerobic_te')), num(f.get('anaerobic_te')),
        num(f.get('swolf'), int), num(f.get('active_lengths'), int),
        plan_item_id, f.get('notes')
    )

    new_id = None
    if entry_id:
        # Running dynamics columns are read-only (FIT-imported); don't overwrite them
        db.execute('''UPDATE cardio_log SET
            date=?, activity=?, activity_name=?, duration_min=?, moving_time_min=?,
            distance_mi=?, avg_pace=?, avg_speed=?, avg_hr=?, max_hr=?, calories=?,
            elev_gain_ft=?, elev_loss_ft=?, avg_cadence=?, max_cadence=?,
            avg_power=?, max_power=?, norm_power=?, aerobic_te=?, anaerobic_te=?,
            swolf=?, active_lengths=?, plan_item_id=?, notes=? WHERE id=?''',
            vals + (entry_id,))
    else:
        cur = db.execute('''INSERT INTO cardio_log
            (date, activity, activity_name, duration_min, moving_time_min,
             distance_mi, avg_pace, avg_speed, avg_hr, max_hr, calories,
             elev_gain_ft, elev_loss_ft, avg_cadence, max_cadence,
             avg_power, max_power, norm_power, aerobic_te, anaerobic_te,
             swolf, active_lengths, plan_item_id, notes)
            VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)''', vals)
        new_id = cur.lastrowid

    if plan_item_id:
        db.execute(
            "UPDATE plan_items SET status='completed' WHERE id=? AND status='scheduled'",
            (plan_item_id,)
        )

    cardio_notes = (f.get('notes') or '').strip()
    if cardio_notes:
        from coaching import capture_and_normalize_feedback
        ref_id = entry_id or new_id
        capture_and_normalize_feedback(db, 'workout_note_cardio', cardio_notes,
                                       source_ref_id=ref_id)

    db.commit()
    return new_id
