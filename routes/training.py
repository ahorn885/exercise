import io

from flask import Blueprint, render_template, request, redirect, url_for, flash, jsonify, send_file
from database import get_db
from calculations import calculate_1rm, calculate_volume
from rx_engine import apply_session_outcome
from fit_workout_generator import generate_activity_fit

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

    # Fetch per-set data for entries that have it
    log_ids = [e['id'] for e in entries]
    sets_by_log = {}
    if log_ids:
        placeholders = ','.join('?' * len(log_ids))
        set_rows = db.execute(
            f'SELECT * FROM training_log_sets WHERE training_log_id IN ({placeholders}) ORDER BY training_log_id, set_number',
            log_ids
        ).fetchall()
        for s in set_rows:
            sets_by_log.setdefault(s['training_log_id'], []).append(s)

    return render_template('training/list.html', entries=entries, exercises=exercises,
                           date_filter=date_filter, exercise_filter=exercise_filter,
                           sets_by_log=sets_by_log)


@bp.route('/training/new', methods=['GET'])
def new_entry():
    db = get_db()
    exercises = db.execute('SELECT exercise, movement_pattern FROM current_rx ORDER BY exercise').fetchall()
    exercises_json = [{'exercise': e['exercise'], 'movement_pattern': e['movement_pattern']} for e in exercises]
    plan_items = _load_plan_items(db)
    return render_template('training/session_form.html', exercises=exercises,
                           exercises_json=exercises_json, plan_items=plan_items)


@bp.route('/training/session', methods=['POST'])
def save_session():
    data = request.get_json()
    if not data:
        return jsonify({'ok': False, 'error': 'No data'}), 400
    db = get_db()

    date = data.get('date', '')
    plan_item_id = data.get('plan_item_id') or None
    session_notes = data.get('notes', '')

    cur = db.execute(
        'INSERT INTO training_sessions (date, notes, plan_item_id) VALUES (?, ?, ?)',
        (date, session_notes, plan_item_id)
    )
    session_id = cur.lastrowid

    body_wt_row = db.execute('SELECT weight_lbs FROM body_metrics ORDER BY date DESC LIMIT 1').fetchone()
    body_weight = body_wt_row['weight_lbs'] if body_wt_row else None

    for ex_data in data.get('exercises', []):
        exercise = ex_data.get('exercise', '').strip()
        if not exercise:
            continue

        sets = ex_data.get('sets', [])
        target_sets = ex_data.get('target_sets')
        target_reps = ex_data.get('target_reps')
        target_weight = ex_data.get('target_weight')
        target_duration = ex_data.get('target_duration')
        rpe = ex_data.get('rpe')
        rest_sec = ex_data.get('rest_sec')
        notes = ex_data.get('notes', '')

        # Snapshot for the training_log row (history). actual_* describes what
        # they did this session; next_* and current_rx live downstream of the
        # rx_engine.
        actual_sets = len(sets)
        last_reps = sets[-1].get('reps') if sets else None
        all_weights = [s.get('weight_lbs') or 0 for s in sets]
        max_weight = max(all_weights) if all_weights else None
        if max_weight == 0:
            max_weight = None
        last_duration = sets[-1].get('duration_sec') if sets else None
        volume = sum((s.get('reps') or 0) * (s.get('weight_lbs') or 0) for s in sets) or None
        if volume == 0:
            volume = None
        all_1rms = [calculate_1rm(s.get('weight_lbs'), s.get('reps')) or 0 for s in sets]
        est_1rm = max(all_1rms) if all_1rms else None
        if est_1rm == 0:
            est_1rm = None

        rx = apply_session_outcome(
            db, exercise, date, sets,
            target_sets=target_sets, target_reps=target_reps,
            target_weight=target_weight, target_duration=target_duration,
            rx_source='From Training Log',
        )

        log_cur = db.execute(
            '''INSERT INTO training_log
               (date, exercise, exercise_id, sub_group, recovery_cost, session_id,
                target_sets, target_reps, target_weight, target_duration,
                actual_sets, actual_reps, actual_weight, actual_duration,
                rpe, rest_sec, outcome, est_1rm, volume, body_weight,
                next_weight, next_sets, next_reps, next_duration, plan_item_id, notes)
               VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)''',
            (date, exercise, rx['exercise_id'], rx['movement_pattern'], None, session_id,
             target_sets, target_reps, target_weight, target_duration,
             actual_sets, last_reps, max_weight, last_duration,
             rpe, rest_sec, rx['outcome'], est_1rm, volume, body_weight,
             rx['next_weight'], rx['next_sets'], rx['next_reps'], rx['next_duration'],
             plan_item_id, notes)
        )
        log_id = log_cur.lastrowid

        for s in sets:
            db.execute(
                'INSERT INTO training_log_sets (training_log_id, set_number, reps, weight_lbs, duration_sec) VALUES (?,?,?,?,?)',
                (log_id, s.get('set_number', 0), s.get('reps'), s.get('weight_lbs'), s.get('duration_sec'))
            )

    if plan_item_id:
        db.execute(
            "UPDATE plan_items SET status='completed' WHERE id=? AND status='scheduled'",
            (plan_item_id,)
        )

    db.commit()
    return jsonify({'ok': True, 'session_id': session_id})


@bp.route('/training/session/<int:session_id>/activity-fit')
def session_activity_fit(session_id):
    db = get_db()
    sess = db.execute('SELECT * FROM training_sessions WHERE id=?', (session_id,)).fetchone()
    if not sess:
        flash('Session not found.', 'danger')
        return redirect(url_for('training.list_entries'))
    duration_min = None
    if sess['plan_item_id']:
        pi = db.execute(
            'SELECT target_duration_min FROM plan_items WHERE id=?', (sess['plan_item_id'],)
        ).fetchone()
        if pi and pi['target_duration_min']:
            duration_min = pi['target_duration_min']
    entry = {
        'activity': 'strength_training',
        'date': sess['date'],
        'duration_min': duration_min,
    }
    fit_bytes = generate_activity_fit(entry)
    filename = f"strength_{sess['date']}.fit"
    return send_file(
        io.BytesIO(fit_bytes),
        as_attachment=True,
        download_name=filename,
        mimetype='application/octet-stream',
    )


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
    plan_items = _load_plan_items(db)
    return render_template('training/form.html', entry=entry, exercises=exercises,
                           plan_items=plan_items)


@bp.route('/training/<int:entry_id>/delete', methods=['POST'])
def delete_entry(entry_id):
    db = get_db()
    db.execute('DELETE FROM training_log WHERE id=?', (entry_id,))
    db.commit()
    flash('Entry deleted.', 'warning')
    return redirect(url_for('training.list_entries'))


def _load_plan_items(db):
    """Return upcoming scheduled plan items for the plan item selector."""
    return db.execute(
        '''SELECT pi.id, pi.item_date, pi.workout_name, pi.sport_type,
                  tp.name as plan_name
           FROM plan_items pi
           JOIN training_plans tp ON tp.id = pi.plan_id
           WHERE pi.status = 'scheduled'
           ORDER BY pi.item_date ASC
           LIMIT 60'''
    ).fetchall()


@bp.route('/api/rx/<exercise>')
def get_rx(exercise):
    db = get_db()
    rx = db.execute('SELECT * FROM current_rx WHERE exercise=?', (exercise,)).fetchone()
    result = dict(rx) if rx else {}
    # Include active injury modifications so the training form can warn the user
    mods = db.execute(
        '''SELECT iem.id, iem.modification_type, iem.modification_notes,
                  il.body_part, il.status,
                  ei_sub.exercise as substitute_name
           FROM injury_exercise_modifications iem
           JOIN injury_log il ON il.id = iem.injury_id
           JOIN exercise_inventory ei ON ei.id = iem.exercise_id
           LEFT JOIN exercise_inventory ei_sub ON ei_sub.id = iem.substitute_exercise_id
           WHERE ei.exercise = ? AND il.status IN (\'Active\', \'Managing\')''',
        (exercise,)
    ).fetchall()
    result['injury_mods'] = [dict(m) for m in mods]
    return jsonify(result)


def _save_entry(db, entry_id):
    f = request.form

    def num(val, cast=float):
        try:
            return cast(val) if val else None
        except (ValueError, TypeError):
            return None

    date = f.get('date', '')
    exercise = f.get('exercise', '')
    plan_item_id = num(f.get('plan_item_id'), int)
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

    # Synthesize per-set data from the aggregate form so the same engine
    # decides outcome / Family A / Family B. The aggregate form treats every
    # set as identical, which matches the original calculate_outcome() shape.
    n = actual_sets or 1
    synthesized_sets = [
        {'reps': actual_reps, 'weight_lbs': actual_weight, 'duration_sec': actual_duration}
        for _ in range(n)
    ]

    est_1rm = calculate_1rm(actual_weight, actual_reps)
    volume = calculate_volume(actual_sets, actual_reps, actual_weight)

    body_wt_row = db.execute('SELECT weight_lbs FROM body_metrics ORDER BY date DESC LIMIT 1').fetchone()
    body_weight = body_wt_row['weight_lbs'] if body_wt_row else None

    rx = apply_session_outcome(
        db, exercise, date, synthesized_sets,
        target_sets=target_sets, target_reps=target_reps,
        target_weight=target_weight, target_duration=target_duration,
        rx_source='From Training Log',
    )

    if entry_id:
        db.execute('''UPDATE training_log SET
            date=?, exercise=?, exercise_id=?, sub_group=?, recovery_cost=?,
            target_sets=?, target_reps=?, target_weight=?, target_duration=?,
            actual_sets=?, actual_reps=?, actual_weight=?, actual_duration=?,
            rpe=?, rest_sec=?, outcome=?, est_1rm=?, volume=?, body_weight=?,
            next_weight=?, next_sets=?, next_reps=?, next_duration=?, plan_item_id=?, notes=?
            WHERE id=?''',
            (date, exercise, rx['exercise_id'], rx['movement_pattern'], None,
             target_sets, target_reps, target_weight, target_duration,
             actual_sets, actual_reps, actual_weight, actual_duration,
             rpe, rest_sec, rx['outcome'], est_1rm, volume, body_weight,
             rx['next_weight'], rx['next_sets'], rx['next_reps'], rx['next_duration'],
             plan_item_id, f.get('notes', ''), entry_id))
    else:
        db.execute('''INSERT INTO training_log
            (date, exercise, exercise_id, sub_group, recovery_cost,
             target_sets, target_reps, target_weight, target_duration,
             actual_sets, actual_reps, actual_weight, actual_duration,
             rpe, rest_sec, outcome, est_1rm, volume, body_weight,
             next_weight, next_sets, next_reps, next_duration, plan_item_id, notes)
            VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)''',
            (date, exercise, rx['exercise_id'], rx['movement_pattern'], None,
             target_sets, target_reps, target_weight, target_duration,
             actual_sets, actual_reps, actual_weight, actual_duration,
             rpe, rest_sec, rx['outcome'], est_1rm, volume, body_weight,
             rx['next_weight'], rx['next_sets'], rx['next_reps'], rx['next_duration'],
             plan_item_id, f.get('notes', '')))

    if plan_item_id:
        db.execute(
            "UPDATE plan_items SET status='completed' WHERE id=? AND status='scheduled'",
            (plan_item_id,)
        )

    db.commit()
