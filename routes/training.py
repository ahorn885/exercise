from flask import Blueprint, render_template, request, redirect, url_for, flash, jsonify
from database import get_db
from calculations import calculate_outcome, calculate_1rm, calculate_volume, calculate_next_rx

bp = Blueprint('training', __name__)


@bp.route('/training')
def list_entries():
    db = get_db()
    date_filter = request.args.get('date', '')
    exercise_filter = request.args.get('exercise', '')

    query = 'SELECT * FROM training_log WHERE 1=1'
    params = []
    if date_filter:
        query += ' AND date = ?'
        params.append(date_filter)
    if exercise_filter:
        query += ' AND exercise LIKE ?'
        params.append(f'%{exercise_filter}%')
    query += ' ORDER BY date DESC, id DESC'

    entries = db.execute(query, params).fetchall()
    exercises = db.execute('SELECT DISTINCT exercise FROM current_rx ORDER BY exercise').fetchall()
    return render_template('training/list.html', entries=entries, exercises=exercises,
                           date_filter=date_filter, exercise_filter=exercise_filter)


@bp.route('/training/new', methods=['GET', 'POST'])
def new_entry():
    db = get_db()
    if request.method == 'POST':
        _save_entry(db, None)
        flash('Workout logged.', 'success')
        return redirect(url_for('training.list_entries'))
    exercises = db.execute('SELECT exercise, movement_pattern FROM current_rx ORDER BY exercise').fetchall()
    return render_template('training/form.html', entry=None, exercises=exercises)


@bp.route('/training/<int:entry_id>/edit', methods=['GET', 'POST'])
def edit_entry(entry_id):
    db = get_db()
    entry = db.execute('SELECT * FROM training_log WHERE id=?', (entry_id,)).fetchone()
    if not entry:
        flash('Entry not found.', 'danger')
        return redirect(url_for('training.list_entries'))
    if request.method == 'POST':
        _save_entry(db, entry_id)
        flash('Entry updated.', 'success')
        return redirect(url_for('training.list_entries'))
    exercises = db.execute('SELECT exercise, movement_pattern FROM current_rx ORDER BY exercise').fetchall()
    return render_template('training/form.html', entry=entry, exercises=exercises)


@bp.route('/training/<int:entry_id>/delete', methods=['POST'])
def delete_entry(entry_id):
    db = get_db()
    db.execute('DELETE FROM training_log WHERE id=?', (entry_id,))
    db.commit()
    flash('Entry deleted.', 'warning')
    return redirect(url_for('training.list_entries'))


@bp.route('/api/rx/<exercise>')
def get_rx(exercise):
    db = get_db()
    rx = db.execute('SELECT * FROM current_rx WHERE exercise=?', (exercise,)).fetchone()
    if rx:
        return jsonify(dict(rx))
    return jsonify({})


def _save_entry(db, entry_id):
    f = request.form
    date = f.get('date', '')
    exercise = f.get('exercise', '')

    rx = db.execute('SELECT movement_pattern, recovery_cost FROM current_rx WHERE exercise=?', (exercise,)).fetchone()
    movement_pattern = rx['movement_pattern'] if rx else None
    recovery_cost = rx['recovery_cost'] if rx else None

    def num(val, cast=float):
        try:
            return cast(val) if val else None
        except (ValueError, TypeError):
            return None

    target_sets = num(f.get('target_sets'), int)
    target_reps = num(f.get('target_reps'), int)
    target_weight = num(f.get('target_weight'))
    target_duration = num(f.get('target_duration'), int)
    actual_sets = num(f.get('actual_sets'), int)
    actual_reps = num(f.get('actual_reps'), int)
    actual_weight = num(f.get('actual_weight'))
    actual_duration = num(f.get('actual_duration'), int)
    rpe = num(f.get('rpe'))
    rest_sec = num(f.get('rest_sec'), int)

    outcome = calculate_outcome(target_sets, target_reps, target_duration,
                                actual_sets, actual_reps, actual_duration)
    est_1rm = calculate_1rm(actual_weight, actual_reps)
    volume = calculate_volume(actual_sets, actual_reps, actual_weight)

    body_wt_row = db.execute('SELECT weight_lbs FROM body_metrics ORDER BY date DESC LIMIT 1').fetchone()
    body_weight = body_wt_row['weight_lbs'] if body_wt_row else None

    nxt = calculate_next_rx(outcome, movement_pattern,
                            actual_sets, actual_reps, actual_weight, actual_duration)

    if entry_id:
        db.execute('''UPDATE training_log SET
            date=?, exercise=?, sub_group=?, recovery_cost=?,
            target_sets=?, target_reps=?, target_weight=?, target_duration=?,
            actual_sets=?, actual_reps=?, actual_weight=?, actual_duration=?,
            rpe=?, rest_sec=?, outcome=?, est_1rm=?, volume=?, body_weight=?,
            next_weight=?, next_sets=?, next_reps=?, notes=?
            WHERE id=?''',
            (date, exercise, movement_pattern, recovery_cost,
             target_sets, target_reps, target_weight, target_duration,
             actual_sets, actual_reps, actual_weight, actual_duration,
             rpe, rest_sec, outcome, est_1rm, volume, body_weight,
             nxt['next_weight'], nxt['next_sets'], nxt['next_reps'],
             f.get('notes', ''), entry_id))
    else:
        db.execute('''INSERT INTO training_log
            (date, exercise, sub_group, recovery_cost,
             target_sets, target_reps, target_weight, target_duration,
             actual_sets, actual_reps, actual_weight, actual_duration,
             rpe, rest_sec, outcome, est_1rm, volume, body_weight,
             next_weight, next_sets, next_reps, notes)
            VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)''',
            (date, exercise, movement_pattern, recovery_cost,
             target_sets, target_reps, target_weight, target_duration,
             actual_sets, actual_reps, actual_weight, actual_duration,
             rpe, rest_sec, outcome, est_1rm, volume, body_weight,
             nxt['next_weight'], nxt['next_sets'], nxt['next_reps'],
             f.get('notes', '')))

    # Update Current Rx with latest result
    if outcome and exercise:
        db.execute('''UPDATE current_rx SET
            current_sets=?, current_reps=?, current_weight=?, current_duration=?,
            last_performed=?, last_outcome=?, rx_source='From Training Log'
            WHERE exercise=?''',
            (actual_sets, actual_reps, actual_weight, actual_duration,
             date, outcome, exercise))

    db.commit()
