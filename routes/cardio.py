from flask import Blueprint, render_template, request, redirect, url_for, flash
from database import get_db

bp = Blueprint('cardio', __name__)

ACTIVITIES = [
    'Running', 'Treadmill', 'Trail Running', 'Hiking', 'Stair Climbing',
    'Road Cycling', 'Mountain Biking', 'Gravel Cycling', 'Indoor Bike Trainer',
    'Kayaking', 'Pack Rafting', 'Kayak Ergometer', 'Rowing Ergometer',
    'Swimming (Pool)', 'Swimming (Open)', 'Yoga'
]


@bp.route('/cardio')
def list_entries():
    db = get_db()
    entries = db.execute(
        'SELECT * FROM cardio_log ORDER BY date DESC, id DESC'
    ).fetchall()
    return render_template('cardio/list.html', entries=entries)


@bp.route('/cardio/new', methods=['GET', 'POST'])
def new_entry():
    db = get_db()
    if request.method == 'POST':
        _save(db, None)
        flash('Cardio session logged.', 'success')
        return redirect(url_for('cardio.list_entries'))
    return render_template('cardio/form.html', entry=None, activities=ACTIVITIES)


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
    return render_template('cardio/form.html', entry=entry, activities=ACTIVITIES)


@bp.route('/cardio/<int:entry_id>/delete', methods=['POST'])
def delete_entry(entry_id):
    db = get_db()
    db.execute('DELETE FROM cardio_log WHERE id=?', (entry_id,))
    db.commit()
    flash('Entry deleted.', 'warning')
    return redirect(url_for('cardio.list_entries'))


def _save(db, entry_id):
    f = request.form

    def num(v, cast=float):
        try:
            return cast(v) if v else None
        except (ValueError, TypeError):
            return None

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
        f.get('notes')
    )

    if entry_id:
        db.execute('''UPDATE cardio_log SET
            date=?, activity=?, activity_name=?, duration_min=?, moving_time_min=?,
            distance_mi=?, avg_pace=?, avg_speed=?, avg_hr=?, max_hr=?, calories=?,
            elev_gain_ft=?, elev_loss_ft=?, avg_cadence=?, max_cadence=?,
            avg_power=?, max_power=?, norm_power=?, aerobic_te=?, anaerobic_te=?,
            swolf=?, active_lengths=?, notes=? WHERE id=?''',
            vals + (entry_id,))
    else:
        db.execute('''INSERT INTO cardio_log
            (date, activity, activity_name, duration_min, moving_time_min,
             distance_mi, avg_pace, avg_speed, avg_hr, max_hr, calories,
             elev_gain_ft, elev_loss_ft, avg_cadence, max_cadence,
             avg_power, max_power, norm_power, aerobic_te, anaerobic_te,
             swolf, active_lengths, notes)
            VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)''', vals)
    db.commit()
