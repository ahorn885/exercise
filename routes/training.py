import io

from flask import Blueprint, render_template, request, redirect, url_for, flash, jsonify, send_file
from database import get_db
from calculations import calculate_1rm, calculate_volume
from rx_engine import apply_session_outcome
from fit_workout_generator import generate_activity_fit
from routes.auth import current_user_id

bp = Blueprint('training', __name__)


_MODALITIES = ('strength', 'cardio')


@bp.route('/training')
def list_entries():
    """Federated workouts feed — one row per session (strength + cardio).

    The sidebar 'Workouts' item lives here. URL stays /training for back-compat
    with edit/delete redirects. Strength rows aggregate by `training_sessions`
    (one row per session, not per exercise) — a single multi-exercise workout
    is now one row. Pre-migration training_log rows with NULL session_id are
    excluded; they must be deleted on Neon before re-importing.
    """
    db = get_db()
    uid = current_user_id()
    date_filter = request.args.get('date', '')
    modality_filter = request.args.get('modality', '').strip().lower()
    if modality_filter not in _MODALITIES:
        modality_filter = ''  # 'all'

    sessions: list = []
    cardio_rows: list = []

    if modality_filter in ('', 'strength'):
        q = ('SELECT id, date, notes, plan_item_id FROM training_sessions '
             'WHERE user_id = ?')
        params: list = [uid]
        if date_filter:
            q += ' AND date = ?'
            params.append(date_filter)
        q += ' ORDER BY date DESC, id DESC'
        sessions = db.execute(q, params).fetchall()

    if modality_filter in ('', 'cardio'):
        q = 'SELECT * FROM cardio_log WHERE user_id = ?'
        params = [uid]
        if date_filter:
            q += ' AND date = ?'
            params.append(date_filter)
        q += ' ORDER BY date DESC, id DESC'
        cardio_rows = db.execute(q, params).fetchall()

    # Per-session training_log aggregation. One query for all sessions on the
    # page; group in Python so the SQL stays DB-agnostic.
    logs_by_session: dict = {}
    if sessions:
        session_ids = [s['id'] for s in sessions]
        placeholders = ','.join('?' * len(session_ids))
        log_rows = db.execute(
            f'SELECT id, session_id, exercise, volume FROM training_log '
            f'WHERE session_id IN ({placeholders}) AND user_id = ? '
            f'ORDER BY session_id, id',
            session_ids + [uid]
        ).fetchall()
        for r in log_rows:
            logs_by_session.setdefault(r['session_id'], []).append(r)

    # Build entries — one row per session.
    entries: list = []
    for s in sessions:
        logs = logs_by_session.get(s['id'], [])
        if not logs:
            continue  # defensive: empty session
        entries.append({
            'modality': 'strength',
            'id': s['id'],
            'date': s['date'],
            'exercise_count': len(logs),
            'exercises_summary': ', '.join(l['exercise'] for l in logs),
            'total_volume': sum((l['volume'] or 0) for l in logs),
        })
    for r in cardio_rows:
        d = dict(r)
        d['modality'] = 'cardio'
        entries.append(d)
    entries.sort(key=lambda e: (str(e['date']), e['id']), reverse=True)

    return render_template('training/list.html', entries=entries,
                           date_filter=date_filter, modality_filter=modality_filter)


@bp.route('/training/session/<int:session_id>')
def session_detail(session_id):
    """Read-focused detail page for one strength session — the click-through
    target from the Workouts feed. Shows every exercise in the session with
    per-set chips, the session's outcome rollup, and links to per-exercise
    edit / FIT download / session-level delete."""
    db = get_db()
    uid = current_user_id()
    session = db.execute(
        'SELECT * FROM training_sessions WHERE id = ? AND user_id = ?',
        (session_id, uid)
    ).fetchone()
    if not session:
        flash('Session not found.', 'danger')
        return redirect(url_for('training.list_entries'))
    logs = db.execute(
        'SELECT * FROM training_log WHERE session_id = ? AND user_id = ? '
        'ORDER BY id',
        (session_id, uid)
    ).fetchall()
    sets_by_log: dict = {}
    if logs:
        log_ids = [l['id'] for l in logs]
        placeholders = ','.join('?' * len(log_ids))
        set_rows = db.execute(
            f'SELECT * FROM training_log_sets '
            f'WHERE training_log_id IN ({placeholders}) AND user_id = ? '
            f'ORDER BY training_log_id, set_number',
            log_ids + [uid]
        ).fetchall()
        for s in set_rows:
            sets_by_log.setdefault(s['training_log_id'], []).append(s)
    plan_item = None
    if session['plan_item_id']:
        plan_item = db.execute(
            'SELECT pi.id, pi.item_date, pi.workout_name, pi.sport_type, '
            '       p.name AS plan_name '
            'FROM plan_items pi LEFT JOIN training_plans p ON p.id = pi.plan_id '
            'WHERE pi.id = ? AND pi.user_id = ?',
            (session['plan_item_id'], uid)
        ).fetchone()
    # #469 — decorate kg-canonical weights with display values + unit label
    # so the detail page renders in the athlete's chosen unit.
    from units import normalize_unit_preference, display_weight, weight_unit_label
    from athlete import get_athlete_profile
    profile = get_athlete_profile(db, uid) or {}
    unit_pref = normalize_unit_preference(profile.get('unit_preference'))
    wt_label = weight_unit_label(unit_pref)

    def _fmt_wt(v):
        d = display_weight(v, unit_pref)
        if d is None:
            return None
        return round(d, 1)

    logs_view = []
    for log in logs:
        row = dict(log)
        row['target_weight_display'] = _fmt_wt(row.get('target_weight'))
        row['actual_weight_display'] = _fmt_wt(row.get('actual_weight'))
        row['next_weight_display'] = _fmt_wt(row.get('next_weight'))
        logs_view.append(row)

    sets_view: dict = {}
    for log_id, rows in sets_by_log.items():
        sets_view[log_id] = []
        for s in rows:
            srow = dict(s)
            srow['weight_display'] = _fmt_wt(srow.get('weight_kg'))
            sets_view[log_id].append(srow)

    return render_template('training/session_detail.html',
                           session=session, logs=logs_view, sets_by_log=sets_view,
                           plan_item=plan_item, weight_unit_label=wt_label)


@bp.route('/training/session/<int:session_id>/delete', methods=['POST'])
def session_delete(session_id):
    """Delete an entire strength session. Cascade removes its training_log
    rows + per-set rows via the ON DELETE CASCADE chain. Used from the feed's
    Delete button and from the session detail page."""
    db = get_db()
    uid = current_user_id()
    session = db.execute(
        'SELECT id FROM training_sessions WHERE id = ? AND user_id = ?',
        (session_id, uid)
    ).fetchone()
    if not session:
        flash('Session not found.', 'danger')
        return redirect(url_for('training.list_entries'))
    db.execute(
        'DELETE FROM training_log WHERE session_id = ? AND user_id = ?',
        (session_id, uid)
    )
    db.execute(
        'DELETE FROM training_sessions WHERE id = ? AND user_id = ?',
        (session_id, uid)
    )
    db.commit()
    flash('Session deleted.', 'success')
    return redirect(url_for('training.list_entries'))


@bp.route('/training/new', methods=['GET'])
def new_entry():
    db = get_db()
    uid = current_user_id()
    exercises = db.execute(
        'SELECT exercise, movement_pattern FROM current_rx WHERE user_id = ? ORDER BY exercise',
        (uid,)
    ).fetchall()
    exercises_json = [{'exercise': e['exercise'], 'movement_pattern': e['movement_pattern']} for e in exercises]
    plan_items = _load_plan_items(db)
    from units import normalize_unit_preference, weight_unit_label
    from athlete import get_athlete_profile
    profile = get_athlete_profile(db, uid) or {}
    unit_pref = normalize_unit_preference(profile.get('unit_preference'))
    return render_template('training/session_form.html', exercises=exercises,
                           exercises_json=exercises_json, plan_items=plan_items,
                           weight_unit_label=weight_unit_label(unit_pref))


@bp.route('/training/session', methods=['POST'])
def save_session():
    data = request.get_json()
    if not data:
        return jsonify({'ok': False, 'error': 'No data'}), 400
    db = get_db()

    date = data.get('date', '')
    plan_item_id = data.get('plan_item_id') or None
    session_notes = data.get('notes', '')

    uid = current_user_id()
    cur = db.execute(
        'INSERT INTO training_sessions (date, notes, plan_item_id, user_id) VALUES (?, ?, ?, ?) RETURNING id',
        (date, session_notes, plan_item_id, uid)
    )
    session_id = cur.lastrowid

    body_wt_row = db.execute(
        'SELECT weight_kg FROM body_metrics WHERE user_id = ? '
        'ORDER BY date DESC LIMIT 1',
        (uid,)
    ).fetchone()
    body_weight = body_wt_row['weight_kg'] if body_wt_row else None

    # #469 — JS posts set weights in the athlete's display unit (form label
    # matches their `unit_preference`). Convert to canonical kg once here so
    # the rest of this handler + the rx_engine see kg only.
    from units import normalize_unit_preference, entered_weight_to_kg
    from athlete import get_athlete_profile
    _profile = get_athlete_profile(db, uid) or {}
    _unit_pref = normalize_unit_preference(_profile.get('unit_preference'))

    def _set_weight_kg(s):
        return entered_weight_to_kg(s.get('weight'), _unit_pref)

    for ex_data in data.get('exercises', []):
        exercise = ex_data.get('exercise', '').strip()
        if not exercise:
            continue

        raw_sets = ex_data.get('sets', [])
        # Sets carry canonical-kg `weight_kg` once converted. The rx_engine
        # + calculations modules both work in kg now.
        sets = []
        for s in raw_sets:
            sets.append({
                'set_number': s.get('set_number', 0),
                'reps': s.get('reps'),
                'weight_kg': _set_weight_kg(s),
                'duration_sec': s.get('duration_sec'),
            })
        target_sets = ex_data.get('target_sets')
        target_reps = ex_data.get('target_reps')
        # target_weight comes back from the rx API in kg (canonical) — no
        # conversion needed.
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
        all_weights = [s.get('weight_kg') or 0 for s in sets]
        max_weight = max(all_weights) if all_weights else None
        if max_weight == 0:
            max_weight = None
        last_duration = sets[-1].get('duration_sec') if sets else None
        volume = sum((s.get('reps') or 0) * (s.get('weight_kg') or 0) for s in sets) or None
        if volume == 0:
            volume = None
        all_1rms = [calculate_1rm(s.get('weight_kg'), s.get('reps')) or 0 for s in sets]
        est_1rm = max(all_1rms) if all_1rms else None
        if est_1rm == 0:
            est_1rm = None

        rx = apply_session_outcome(
            db, exercise, date, sets,
            target_sets=target_sets, target_reps=target_reps,
            target_weight=target_weight, target_duration=target_duration,
            rx_source='From Training Log', user_id=uid,
        )

        log_cur = db.execute(
            '''INSERT INTO training_log
               (date, exercise, exercise_id, sub_group, recovery_cost, session_id,
                target_sets, target_reps, target_weight, target_duration,
                actual_sets, actual_reps, actual_weight, actual_duration,
                rpe, rest_sec, outcome, est_1rm, volume, body_weight,
                next_weight, next_sets, next_reps, next_duration, plan_item_id, notes, user_id)
               VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?) RETURNING id''',
            (date, exercise, rx['exercise_id'], rx['movement_pattern'], None, session_id,
             target_sets, target_reps, target_weight, target_duration,
             actual_sets, last_reps, max_weight, last_duration,
             rpe, rest_sec, rx['outcome'], est_1rm, volume, body_weight,
             rx['next_weight'], rx['next_sets'], rx['next_reps'], rx['next_duration'],
             plan_item_id, notes, uid)
        )
        log_id = log_cur.lastrowid

        for s in sets:
            db.execute(
                'INSERT INTO training_log_sets (training_log_id, set_number, reps, weight_kg, duration_sec, user_id) VALUES (?,?,?,?,?,?)',
                (log_id, s.get('set_number', 0), s.get('reps'), s.get('weight_kg'), s.get('duration_sec'), uid)
            )

    if plan_item_id:
        db.execute(
            "UPDATE plan_items SET status='completed' "
            "WHERE id=? AND user_id=? AND status='scheduled'",
            (plan_item_id, uid)
        )

    if session_notes:
        from coaching import capture_and_normalize_feedback
        capture_and_normalize_feedback(db, 'workout_note_strength', session_notes,
                                       source_ref_id=session_id, user_id=uid)

    db.commit()
    return jsonify({'ok': True, 'session_id': session_id})


@bp.route('/training/session/<int:session_id>/activity-fit')
def session_activity_fit(session_id):
    db = get_db()
    uid = current_user_id()
    sess = db.execute(
        'SELECT * FROM training_sessions WHERE id=? AND user_id=?',
        (session_id, uid)
    ).fetchone()
    if not sess:
        flash('Session not found.', 'danger')
        return redirect(url_for('training.list_entries'))
    duration_min = None
    if sess['plan_item_id']:
        pi = db.execute(
            'SELECT target_duration_min FROM plan_items WHERE id=? AND user_id=?',
            (sess['plan_item_id'], uid)
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
    uid = current_user_id()
    entry = db.execute(
        'SELECT * FROM training_log WHERE id=? AND user_id=?', (entry_id, uid)
    ).fetchone()
    if not entry:
        flash('Entry not found.', 'danger')
        return redirect(url_for('training.list_entries'))
    if request.method == 'POST':
        _save_entry(db, entry_id)
        flash('Entry updated.', 'success')
        return redirect(url_for('training.list_entries'))
    exercises = db.execute(
        'SELECT exercise, movement_pattern FROM current_rx WHERE user_id = ? ORDER BY exercise',
        (uid,)
    ).fetchall()
    plan_items = _load_plan_items(db)
    # #469 — convert canonical-kg weights to the athlete's display unit so
    # the legacy form prefills cleanly.
    from units import normalize_unit_preference, display_weight, weight_unit_label
    from athlete import get_athlete_profile
    profile = get_athlete_profile(db, uid) or {}
    unit_pref = normalize_unit_preference(profile.get('unit_preference'))
    entry_dict = dict(entry)
    for col in ('target_weight', 'actual_weight'):
        v = display_weight(entry_dict.get(col), unit_pref)
        entry_dict[col] = round(v, 1) if v is not None else None
    return render_template('training/form.html', entry=entry_dict, exercises=exercises,
                           plan_items=plan_items,
                           weight_unit_label=weight_unit_label(unit_pref))


@bp.route('/training/<int:entry_id>/delete', methods=['POST'])
def delete_entry(entry_id):
    db = get_db()
    db.execute(
        'DELETE FROM training_log WHERE id=? AND user_id=?',
        (entry_id, current_user_id())
    )
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
           WHERE tp.user_id = ? AND pi.status = 'scheduled'
           ORDER BY pi.item_date ASC
           LIMIT 60''',
        (current_user_id(),)
    ).fetchall()


@bp.route('/api/rx/<exercise>')
def get_rx(exercise):
    db = get_db()
    uid = current_user_id()
    rx = db.execute(
        'SELECT * FROM current_rx WHERE exercise=? AND user_id=?', (exercise, uid)
    ).fetchone()
    result = dict(rx) if rx else {}
    # Include active injury modifications (parent-JOIN scoped via injury_log)
    mods = db.execute(
        '''SELECT iem.id, iem.modification_type, iem.modification_notes,
                  il.body_part, il.status,
                  ei_sub.exercise as substitute_name
           FROM injury_exercise_modifications iem
           JOIN injury_log il ON il.id = iem.injury_id
           JOIN exercise_inventory ei ON ei.id = iem.exercise_id
           LEFT JOIN exercise_inventory ei_sub ON ei_sub.id = iem.substitute_exercise_id
           WHERE ei.exercise = ? AND il.user_id = ?
             AND il.status IN (\'Active\', \'Managing\')''',
        (exercise, uid)
    ).fetchall()
    result['injury_mods'] = [dict(m) for m in mods]
    # #469 — surface display-unit values + label so the session-form JS can
    # render rx targets in the athlete's chosen unit without re-fetching the
    # profile. Storage stays canonical kg in current_weight/next_weight.
    from units import normalize_unit_preference, display_weight, weight_unit_label
    from athlete import get_athlete_profile
    profile = get_athlete_profile(db, uid) or {}
    unit_pref = normalize_unit_preference(profile.get('unit_preference'))
    result['weight_unit_label'] = weight_unit_label(unit_pref)
    if rx is not None:
        cur_d = display_weight(result.get('current_weight'), unit_pref)
        nxt_d = display_weight(result.get('next_weight'), unit_pref)
        result['current_weight_display'] = round(cur_d, 1) if cur_d is not None else None
        result['next_weight_display'] = round(nxt_d, 1) if nxt_d is not None else None
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

    # #469 — target_weight + actual_weight both arrive in the athlete's
    # display unit (form labels match `unit_preference`). Convert once here
    # so rx_engine + 1RM/volume calculations see kg only.
    uid = current_user_id()
    from units import normalize_unit_preference, entered_weight_to_kg
    from athlete import get_athlete_profile
    _profile = get_athlete_profile(db, uid) or {}
    _unit_pref = normalize_unit_preference(_profile.get('unit_preference'))
    target_weight = entered_weight_to_kg(target_weight, _unit_pref)
    actual_weight = entered_weight_to_kg(actual_weight, _unit_pref)

    # Synthesize per-set data from the aggregate form so the same engine
    # decides outcome / Family A / Family B. The aggregate form treats every
    # set as identical, which matches the original calculate_outcome() shape.
    n = actual_sets or 1
    synthesized_sets = [
        {'reps': actual_reps, 'weight_kg': actual_weight, 'duration_sec': actual_duration}
        for _ in range(n)
    ]

    est_1rm = calculate_1rm(actual_weight, actual_reps)
    volume = calculate_volume(actual_sets, actual_reps, actual_weight)

    body_wt_row = db.execute(
        'SELECT weight_kg FROM body_metrics WHERE user_id = ? '
        'ORDER BY date DESC LIMIT 1',
        (uid,)
    ).fetchone()
    body_weight = body_wt_row['weight_kg'] if body_wt_row else None

    rx = apply_session_outcome(
        db, exercise, date, synthesized_sets,
        target_sets=target_sets, target_reps=target_reps,
        target_weight=target_weight, target_duration=target_duration,
        rx_source='From Training Log', user_id=uid,
    )

    if entry_id:
        db.execute('''UPDATE training_log SET
            date=?, exercise=?, exercise_id=?, sub_group=?, recovery_cost=?,
            target_sets=?, target_reps=?, target_weight=?, target_duration=?,
            actual_sets=?, actual_reps=?, actual_weight=?, actual_duration=?,
            rpe=?, rest_sec=?, outcome=?, est_1rm=?, volume=?, body_weight=?,
            next_weight=?, next_sets=?, next_reps=?, next_duration=?, plan_item_id=?, notes=?
            WHERE id=? AND user_id=?''',
            (date, exercise, rx['exercise_id'], rx['movement_pattern'], None,
             target_sets, target_reps, target_weight, target_duration,
             actual_sets, actual_reps, actual_weight, actual_duration,
             rpe, rest_sec, rx['outcome'], est_1rm, volume, body_weight,
             rx['next_weight'], rx['next_sets'], rx['next_reps'], rx['next_duration'],
             plan_item_id, f.get('notes', ''), entry_id, uid))
    else:
        db.execute('''INSERT INTO training_log
            (date, exercise, exercise_id, sub_group, recovery_cost,
             target_sets, target_reps, target_weight, target_duration,
             actual_sets, actual_reps, actual_weight, actual_duration,
             rpe, rest_sec, outcome, est_1rm, volume, body_weight,
             next_weight, next_sets, next_reps, next_duration, plan_item_id, notes, user_id)
            VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)''',
            (date, exercise, rx['exercise_id'], rx['movement_pattern'], None,
             target_sets, target_reps, target_weight, target_duration,
             actual_sets, actual_reps, actual_weight, actual_duration,
             rpe, rest_sec, rx['outcome'], est_1rm, volume, body_weight,
             rx['next_weight'], rx['next_sets'], rx['next_reps'], rx['next_duration'],
             plan_item_id, f.get('notes', ''), uid))

    if plan_item_id:
        db.execute(
            "UPDATE plan_items SET status='completed' "
            "WHERE id=? AND user_id=? AND status='scheduled'",
            (plan_item_id, uid)
        )

    db.commit()
