import json
import os
import tempfile
import uuid
from datetime import date, timedelta

from flask import Blueprint, render_template, request, redirect, url_for, flash, jsonify, session as flask_session
from database import get_db
from calculations import calculate_outcome_from_sets, calculate_1rm, calculate_next_rx

bp = Blueprint('garmin', __name__, url_prefix='/garmin')


# ── Plan-matching helpers ─────────────────────────────────────────────────────

# Plan sport_type aliases — values that mean the same category as each key
_SPORT_ALIASES = {
    'running':          {'run', 'trail run', 'trail_run', 'treadmill', 'track', 'jog'},
    'cycling':          {'bike', 'biking', 'cycle', 'mtb', 'road bike', 'gravel'},
    'strength_training': {'strength', 'weights', 'gym', 'lifting', 'strength training'},
    'hiking':           {'hike', 'trail hike'},
    'swimming':         {'swim', 'pool', 'open water'},
    'walking':          {'walk'},
}


def _sports_compatible(garmin_plan_sport: str, plan_sport_type: str) -> bool:
    """Return True if a Garmin activity sport matches a plan item's sport_type."""
    g = garmin_plan_sport.lower().strip()
    p = (plan_sport_type or '').lower().strip()
    if g == p or g in p or p in g:
        return True
    aliases = _SPORT_ALIASES.get(g, set())
    return p in aliases or any(alias in p for alias in aliases)


def _find_plan_match(db, activity_date: str, plan_sport_type: str):
    """Return the best matching scheduled plan_items row, or None."""
    if not plan_sport_type:
        return None
    for offset in (0, 1, -1):
        try:
            target = (date.fromisoformat(activity_date) + timedelta(days=offset)).isoformat()
        except (ValueError, TypeError):
            continue
        items = db.execute(
            "SELECT * FROM plan_items WHERE item_date=? AND status='scheduled'",
            (target,)
        ).fetchall()
        sport_match = next(
            (i for i in items if _sports_compatible(plan_sport_type, i['sport_type'])),
            None
        )
        if sport_match:
            return sport_match
        # Same-day fallback: if only one item that day, match regardless of sport
        if offset == 0 and len(items) == 1:
            return items[0]
    return None


def _compute_compliance(activity: dict, plan_item) -> dict:
    """Return compliance percentages and a label for actual vs planned workout."""
    result = {'duration_pct': None, 'distance_pct': None, 'label': 'no_target'}
    if not plan_item:
        result['label'] = 'unmatched'
        return result
    target_dur = plan_item['target_duration_min']
    actual_dur = activity.get('duration_min')
    if target_dur and actual_dur:
        result['duration_pct'] = round(actual_dur / target_dur * 100)
    target_dist = plan_item['target_distance_mi']
    actual_dist = activity.get('distance_mi')
    if target_dist and actual_dist:
        result['distance_pct'] = round(actual_dist / target_dist * 100)
    primary = result['duration_pct'] if result['duration_pct'] is not None else result['distance_pct']
    if primary is None:
        result['label'] = 'no_target'
    elif primary >= 80 and primary <= 130:
        result['label'] = 'on_plan'
    elif primary < 80:
        result['label'] = 'short'
    else:
        result['label'] = 'over'
    return result


@bp.route('/debug-fit', methods=['GET', 'POST'])
def debug_fit():
    dump = None
    if request.method == 'POST':
        f = request.files.get('fit_file')
        if not f or not f.filename:
            flash('No file selected.', 'warning')
            return redirect(url_for('garmin.debug_fit'))
        try:
            raw = f.read()
            fname = f.filename.lower()
            if fname.endswith('.zip'):
                import zipfile, io
                with zipfile.ZipFile(io.BytesIO(raw)) as zf:
                    fit_names = [n for n in zf.namelist() if n.lower().endswith('.fit')]
                    if not fit_names:
                        flash('No .fit file found inside the zip.', 'danger')
                        return redirect(url_for('garmin.debug_fit'))
                    raw = zf.read(fit_names[0])
            from garmin_fit_parser import _dump_fit
            dump = _dump_fit(raw)
        except Exception as e:
            flash(f'Error: {e}', 'danger')
    return render_template('garmin/debug_fit.html', dump=dump)


@bp.route('/')
def dashboard():
    db = get_db()
    recent_cardio = db.execute(
        "SELECT * FROM cardio_log ORDER BY date DESC LIMIT 10"
    ).fetchall()
    try:
        from garmin_connect import get_auth_status
        auth_status = get_auth_status(db)
    except Exception:
        auth_status = {'authenticated': False, 'username': None}
    return render_template('garmin/dashboard.html', recent_cardio=recent_cardio,
                           auth_status=auth_status)


@bp.route('/import', methods=['GET', 'POST'])
def import_fit():
    if request.method == 'POST':
        if 'fit_file' not in request.files or request.files['fit_file'].filename == '':
            flash('No file selected.', 'warning')
            return redirect(url_for('garmin.import_fit'))
        fit_file = request.files['fit_file']
        fname = fit_file.filename.lower()
        if not (fname.endswith('.fit') or fname.endswith('.zip')):
            flash('File must be a .fit or .zip file.', 'danger')
            return redirect(url_for('garmin.import_fit'))
        try:
            raw = fit_file.read()
            if fname.endswith('.zip'):
                import zipfile, io
                with zipfile.ZipFile(io.BytesIO(raw)) as zf:
                    fit_names = [n for n in zf.namelist() if n.lower().endswith('.fit')]
                    if not fit_names:
                        flash('No .fit file found inside the zip.', 'danger')
                        return redirect(url_for('garmin.import_fit'))
                    raw = zf.read(fit_names[0])
            from garmin_fit_parser import parse_fit
            result = parse_fit(raw)
            flask_session['fit_import'] = result
            flask_session['fit_name_override'] = request.form.get('activity_name', '')
            flask_session['fit_notes'] = request.form.get('notes', '')
            return redirect(url_for('garmin.import_preview'))
        except Exception as e:
            flash(f'Error parsing FIT file: {e}', 'danger')
            return redirect(url_for('garmin.import_fit'))
    return render_template('garmin/import.html')


@bp.route('/import/preview')
def import_preview():
    result = flask_session.get('fit_import')
    if not result:
        flash('No FIT data in session. Please upload a file.', 'warning')
        return redirect(url_for('garmin.import_fit'))
    db = get_db()
    plan_items = db.execute(
        '''SELECT pi.id, pi.item_date, pi.workout_name, pi.sport_type,
                  tp.name as plan_name
           FROM plan_items pi
           JOIN training_plans tp ON tp.id = pi.plan_id
           WHERE pi.status = 'scheduled' AND tp.status != 'archived'
           ORDER BY pi.item_date ASC
           LIMIT 60'''
    ).fetchall()
    return render_template('garmin/import_preview.html', result=result,
                           name_override=flask_session.get('fit_name_override', ''),
                           notes=flask_session.get('fit_notes', ''),
                           plan_items=plan_items)


@bp.route('/import/confirm', methods=['POST'])
def import_confirm():
    result = flask_session.get('fit_import')
    if not result:
        flash('Session expired. Please re-upload the file.', 'warning')
        return redirect(url_for('garmin.import_fit'))

    db = get_db()
    log_type = result.get('log_type')

    def _num_int(v):
        try:
            return int(v) if v else None
        except (ValueError, TypeError):
            return None

    if log_type == 'cardio':
        data = result['data']
        data['activity_name'] = request.form.get('activity_name') or data.get('activity_name')
        data['notes'] = request.form.get('notes') or data.get('notes')
        data['activity'] = request.form.get('activity') or data.get('activity', 'Running')
        plan_item_id = _num_int(request.form.get('plan_item_id'))
        db.execute(
            '''INSERT INTO cardio_log
               (date, activity, activity_name, duration_min, moving_time_min,
                distance_mi, avg_pace, avg_speed, avg_hr, max_hr, calories,
                elev_gain_ft, elev_loss_ft, avg_cadence, max_cadence,
                avg_power, max_power, norm_power, aerobic_te, anaerobic_te,
                swolf, active_lengths,
                stride_length_m, vert_oscillation_cm, vert_ratio_pct,
                gct_ms, gct_balance, plan_item_id, notes)
               VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)''',
            (data.get('date'), data.get('activity'), data.get('activity_name'),
             data.get('duration_min'), data.get('moving_time_min'),
             data.get('distance_mi'), data.get('avg_pace'), data.get('avg_speed'),
             data.get('avg_hr'), data.get('max_hr'), data.get('calories'),
             data.get('elev_gain_ft'), data.get('elev_loss_ft'),
             data.get('avg_cadence'), data.get('max_cadence'),
             data.get('avg_power'), data.get('max_power'), data.get('norm_power'),
             data.get('aerobic_te'), data.get('anaerobic_te'),
             data.get('swolf'), data.get('active_lengths'),
             data.get('stride_length_m'), data.get('vert_oscillation_cm'),
             data.get('vert_ratio_pct'), data.get('gct_ms'), data.get('gct_balance'),
             plan_item_id, data.get('notes'))
        )
        if plan_item_id:
            db.execute(
                "UPDATE plan_items SET status='completed' WHERE id=? AND status='scheduled'",
                (plan_item_id,)
            )
        db.commit()
        flask_session.pop('fit_import', None)
        flash('Activity imported into Cardio Log.', 'success')
        return redirect(url_for('cardio.list_entries'))

    elif log_type == 'strength':
        rows = result['data']
        plan_item_id = _num_int(request.form.get('plan_item_id'))
        global_notes = request.form.get('notes') or ''

        session_date = rows[0]['date'] if rows else date.today().isoformat()
        sess_cur = db.execute(
            'INSERT INTO training_sessions (date, notes, plan_item_id) VALUES (?,?,?)',
            (session_date, global_notes or None, plan_item_id)
        )
        session_id = sess_cur.lastrowid

        body_wt_row = db.execute('SELECT weight_lbs FROM body_metrics ORDER BY date DESC LIMIT 1').fetchone()
        body_weight = body_wt_row['weight_lbs'] if body_wt_row else None

        inserted = 0
        for row in rows:
            exercise = row.get('exercise', '')
            sets = row.get('sets', [])

            rx = db.execute(
                'SELECT movement_pattern, weight_increment, consecutive_failures FROM current_rx WHERE exercise=?',
                (exercise,)
            ).fetchone()
            movement_pattern = rx['movement_pattern'] if rx else None
            weight_increment = rx['weight_increment'] if rx else None
            consecutive_failures = (rx['consecutive_failures'] or 0) if rx else 0

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

            outcome = calculate_outcome_from_sets(None, None, None, None, sets)
            nxt = calculate_next_rx(outcome, movement_pattern,
                                    actual_sets, last_reps, max_weight, last_duration,
                                    weight_increment=weight_increment,
                                    consecutive_failures=consecutive_failures)

            log_cur = db.execute(
                '''INSERT INTO training_log
                   (date, exercise, sub_group, session_id,
                    actual_sets, actual_reps, actual_weight, actual_duration,
                    outcome, est_1rm, volume, body_weight,
                    next_weight, next_sets, next_reps, plan_item_id, notes)
                   VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)''',
                (row.get('date'), exercise, movement_pattern, session_id,
                 actual_sets, last_reps, max_weight, last_duration,
                 outcome, est_1rm, volume, body_weight,
                 nxt['next_weight'], nxt['next_sets'], nxt['next_reps'],
                 plan_item_id, global_notes or None)
            )
            log_id = log_cur.lastrowid

            for i, s in enumerate(sets, 1):
                db.execute(
                    'INSERT INTO training_log_sets (training_log_id, set_number, reps, weight_lbs, duration_sec) VALUES (?,?,?,?,?)',
                    (log_id, i, s.get('reps'), s.get('weight_lbs'), s.get('duration_sec'))
                )

            if outcome and exercise:
                db.execute(
                    '''UPDATE current_rx SET
                       current_sets=?, current_reps=?, current_weight=?, current_duration=?,
                       last_performed=?, last_outcome=?, consecutive_failures=?,
                       next_sets=?, next_reps=?, next_weight=?,
                       rx_source='From FIT Import'
                       WHERE exercise=?''',
                    (actual_sets, last_reps, max_weight, last_duration,
                     row.get('date'), outcome, nxt['consecutive_failures'],
                     nxt['next_sets'], nxt['next_reps'], nxt['next_weight'], exercise)
                )
            inserted += 1

        if plan_item_id:
            db.execute(
                "UPDATE plan_items SET status='completed' WHERE id=? AND status='scheduled'",
                (plan_item_id,)
            )
        db.commit()
        flask_session.pop('fit_import', None)
        flash(f'Strength workout imported: {inserted} exercise entries added.', 'success')
        return redirect(url_for('training.list_entries'))

    flash('Unknown activity type.', 'danger')
    return redirect(url_for('garmin.import_fit'))


def _already_imported(db, gid: str) -> bool:
    """Return True if this Garmin activity ID is already in cardio_log or training_log."""
    return (
        db.execute('SELECT id FROM cardio_log WHERE garmin_activity_id=?', (gid,)).fetchone()
        is not None
        or db.execute('SELECT id FROM training_log WHERE garmin_activity_id=?', (gid,)).fetchone()
        is not None
    )


def _import_activity(db, act: dict, plan_item, compliance: dict) -> dict:
    """Insert one activity into the correct log table. Does NOT commit.

    Returns {'ok': bool, 'log_type': str, 'rows': int, 'error': str|None}
    """
    gid = act.get('garmin_activity_id', '')
    plan_item_id = plan_item['id'] if plan_item else None
    is_strength = act.get('_plan_sport_type') == 'strength_training'

    notes_parts = []
    if plan_item:
        notes_parts.append(f"Auto-matched: \"{plan_item['workout_name']}\"")
        if compliance.get('duration_pct') is not None:
            notes_parts.append(f"Duration {compliance['duration_pct']}% of target")
        if compliance.get('distance_pct') is not None:
            notes_parts.append(f"Distance {compliance['distance_pct']}% of target")
    notes = '. '.join(notes_parts) or None

    if is_strength:
        try:
            from garmin_connect import download_activity_fit
            from garmin_fit_parser import parse_fit
            fit_bytes = download_activity_fit(db, gid)
            parsed = parse_fit(fit_bytes)
        except Exception as e:
            return {'ok': False, 'log_type': 'strength', 'rows': 0, 'error': str(e)}

        rows = parsed.get('data', []) if parsed.get('log_type') == 'strength' else []
        if rows:
            session_date = rows[0]['date'] if rows else date.today().isoformat()
            sess_cur = db.execute(
                'INSERT INTO training_sessions (date, notes, plan_item_id) VALUES (?,?,?)',
                (session_date, notes, plan_item_id)
            )
            session_id = sess_cur.lastrowid

            body_wt_row = db.execute('SELECT weight_lbs FROM body_metrics ORDER BY date DESC LIMIT 1').fetchone()
            body_weight = body_wt_row['weight_lbs'] if body_wt_row else None

            for row in rows:
                exercise = row.get('exercise', '')
                sets = row.get('sets', [])

                rx = db.execute(
                    'SELECT movement_pattern, weight_increment, consecutive_failures FROM current_rx WHERE exercise=?',
                    (exercise,)
                ).fetchone()
                movement_pattern = rx['movement_pattern'] if rx else None
                weight_increment = rx['weight_increment'] if rx else None
                consecutive_failures = (rx['consecutive_failures'] or 0) if rx else 0

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

                outcome = calculate_outcome_from_sets(None, None, None, None, sets)
                nxt = calculate_next_rx(outcome, movement_pattern,
                                        actual_sets, last_reps, max_weight, last_duration,
                                        weight_increment=weight_increment,
                                        consecutive_failures=consecutive_failures)

                log_cur = db.execute(
                    '''INSERT INTO training_log
                       (date, exercise, sub_group, session_id,
                        actual_sets, actual_reps, actual_weight, actual_duration,
                        outcome, est_1rm, volume, body_weight,
                        next_weight, next_sets, next_reps,
                        garmin_activity_id, plan_item_id, notes)
                       VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)''',
                    (row.get('date'), exercise, movement_pattern, session_id,
                     actual_sets, last_reps, max_weight, last_duration,
                     outcome, est_1rm, volume, body_weight,
                     nxt['next_weight'], nxt['next_sets'], nxt['next_reps'],
                     gid, plan_item_id, notes)
                )
                log_id = log_cur.lastrowid

                for i, s in enumerate(sets, 1):
                    db.execute(
                        'INSERT INTO training_log_sets (training_log_id, set_number, reps, weight_lbs, duration_sec) VALUES (?,?,?,?,?)',
                        (log_id, i, s.get('reps'), s.get('weight_lbs'), s.get('duration_sec'))
                    )

                if outcome and exercise:
                    db.execute(
                        '''UPDATE current_rx SET
                           current_sets=?, current_reps=?, current_weight=?, current_duration=?,
                           last_performed=?, last_outcome=?, consecutive_failures=?,
                           next_sets=?, next_reps=?, next_weight=?,
                           rx_source='From FIT Import'
                           WHERE exercise=?''',
                        (actual_sets, last_reps, max_weight, last_duration,
                         row.get('date'), outcome, nxt['consecutive_failures'],
                         nxt['next_sets'], nxt['next_reps'], nxt['next_weight'], exercise)
                    )

            if plan_item_id:
                db.execute(
                    "UPDATE plan_items SET status='completed' WHERE id=? AND status='scheduled'",
                    (plan_item_id,)
                )
            return {'ok': True, 'log_type': 'strength', 'rows': len(rows), 'error': None}
        # FIT didn't yield strength data — fall through to cardio insert

    db.execute(
        '''INSERT INTO cardio_log
           (date, activity, activity_name, duration_min, moving_time_min,
            distance_mi, avg_pace, avg_speed, avg_hr, max_hr, calories,
            elev_gain_ft, elev_loss_ft, avg_cadence,
            avg_power, max_power, norm_power, aerobic_te, anaerobic_te,
            garmin_activity_id, plan_item_id, notes)
           VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)''',
        (act.get('date'), act.get('activity'), act.get('activity_name'),
         act.get('duration_min'), act.get('moving_time_min'),
         act.get('distance_mi'), act.get('avg_pace'), act.get('avg_speed'),
         act.get('avg_hr'), act.get('max_hr'), act.get('calories'),
         act.get('elev_gain_ft'), act.get('elev_loss_ft'), act.get('avg_cadence'),
         act.get('avg_power'), act.get('max_power'), act.get('norm_power'),
         act.get('aerobic_te'), act.get('anaerobic_te'),
         gid, plan_item_id, notes)
    )
    if plan_item_id:
        db.execute(
            "UPDATE plan_items SET status='completed' WHERE id=? AND status='scheduled'",
            (plan_item_id,)
        )
    return {'ok': True, 'log_type': 'cardio', 'rows': 1, 'error': None}


def _build_preview(db, raw_activities: list) -> list:
    """Turn raw Garmin API activity list into a preview list for the template or API."""
    from garmin_connect import normalize_activity
    preview = []
    for a in raw_activities:
        norm = normalize_activity(a)
        gid = norm.get('garmin_activity_id', '')
        already = _already_imported(db, gid)
        plan_item = _find_plan_match(db, norm['date'], norm.get('_plan_sport_type', ''))
        compliance = _compute_compliance(norm, plan_item)
        preview.append({
            'activity': norm,
            'already_imported': already,
            'plan_item': dict(plan_item) if plan_item else None,
            'compliance': compliance,
        })
    return preview


@bp.route('/sync', methods=['GET', 'POST'])
def sync():
    db = get_db()
    try:
        from garmin_connect import get_auth_status
        auth_status = get_auth_status(db)
    except Exception:
        auth_status = {'authenticated': False, 'username': None}

    if not auth_status['authenticated']:
        flash('Please authenticate with Garmin Connect first.', 'warning')
        return redirect(url_for('garmin.auth'))

    default_start = (date.today() - timedelta(days=7)).isoformat()
    default_end = date.today().isoformat()

    if request.method == 'POST':
        start_date = request.form.get('start_date') or default_start
        end_date = request.form.get('end_date') or default_end
        try:
            from garmin_connect import fetch_activities
            raw = fetch_activities(db, start_date, end_date)
        except Exception as e:
            flash(f'Failed to fetch from Garmin Connect: {e}', 'danger')
            return redirect(url_for('garmin.sync'))

        preview = _build_preview(db, raw)
        flask_session['garmin_sync_preview'] = preview
        return render_template('garmin/sync_preview.html', preview=preview,
                               start_date=start_date, end_date=end_date)

    return render_template('garmin/sync.html', auth_status=auth_status,
                           default_start=default_start, default_end=default_end)


@bp.route('/sync/confirm', methods=['POST'])
def sync_confirm():
    preview = flask_session.get('garmin_sync_preview', [])
    if not preview:
        flash('Session expired — please fetch again.', 'warning')
        return redirect(url_for('garmin.sync'))

    selected = set(request.form.getlist('selected_ids'))
    db = get_db()
    imported = matched = errors = 0

    for item in preview:
        gid = item['activity'].get('garmin_activity_id', '')
        if gid not in selected or item['already_imported']:
            continue
        result = _import_activity(db, item['activity'], item.get('plan_item'), item.get('compliance', {}))
        if result['ok']:
            imported += result['rows']
            if item.get('plan_item'):
                matched += 1
        else:
            errors += 1
            flash(f"Error importing {item['activity'].get('activity_name')}: {result['error']}", 'warning')

    db.commit()
    flask_session.pop('garmin_sync_preview', None)
    msg = f'{imported} activit{"y" if imported == 1 else "ies"} imported'
    if matched:
        msg += f', {matched} matched to plan items'
    if errors:
        msg += f', {errors} error(s)'
    flash(msg + '.', 'success')
    return redirect(url_for('garmin.dashboard'))


@bp.route('/api/sync', methods=['POST'])
def api_sync():
    """Headless sync endpoint for Claude Desktop remote triggering.

    POST JSON: {"start_date": "YYYY-MM-DD", "end_date": "YYYY-MM-DD"}
    Returns import summary with per-activity results.
    """
    data = request.get_json(silent=True) or {}
    start_date = data.get('start_date', (date.today() - timedelta(days=7)).isoformat())
    end_date = data.get('end_date', date.today().isoformat())

    db = get_db()
    try:
        from garmin_connect import get_auth_status, fetch_activities
        if not get_auth_status(db)['authenticated']:
            return jsonify({'ok': False, 'error': 'Not authenticated with Garmin Connect'}), 401
        raw = fetch_activities(db, start_date, end_date)
    except Exception as e:
        return jsonify({'ok': False, 'error': str(e)}), 500

    preview = _build_preview(db, raw)
    imported = matched = skipped = 0
    activity_log = []

    for item in preview:
        act = item['activity']
        name = act.get('activity_name') or act.get('activity')
        if item['already_imported']:
            skipped += 1
            activity_log.append({'name': name, 'date': act['date'], 'status': 'already_imported'})
            continue
        result = _import_activity(db, act, item.get('plan_item'), item.get('compliance', {}))
        if result['ok']:
            imported += result['rows']
            if item.get('plan_item'):
                matched += 1
            activity_log.append({
                'name': name,
                'date': act['date'],
                'log_type': result['log_type'],
                'plan_match': item['plan_item']['workout_name'] if item.get('plan_item') else None,
                'compliance': item['compliance'].get('label'),
                'status': 'imported',
            })
        else:
            activity_log.append({'name': name, 'date': act['date'], 'status': 'error', 'error': result['error']})

    db.commit()
    return jsonify({
        'ok': True,
        'date_range': {'start': start_date, 'end': end_date},
        'imported': imported,
        'matched': matched,
        'skipped': skipped,
        'activities': activity_log,
    })


@bp.route('/auth')
def auth():
    try:
        from garmin_connect import get_auth_status
        status = get_auth_status(get_db())
    except Exception:
        status = {'authenticated': False, 'username': None}
    return render_template('garmin/auth.html', status=status)


@bp.route('/auth/login', methods=['POST'])
def auth_login():
    email = request.form.get('email', '').strip()
    password = request.form.get('password', '').strip()
    mfa_code = request.form.get('mfa_code', '').strip() or None
    if not email or not password:
        flash('Email and password are required.', 'danger')
        return redirect(url_for('garmin.auth'))
    try:
        from garmin_connect import login
        login(get_db(), email, password, mfa_code)
        flash('Successfully authenticated with Garmin Connect.', 'success')
    except Exception as e:
        flash(f'Authentication failed: {e}', 'danger')
    return redirect(url_for('garmin.auth'))


@bp.route('/auth/import-cookies', methods=['POST'])
def auth_import_cookies():
    import json
    cookie_string = request.form.get('cookie_string', '').strip()
    if not cookie_string:
        flash('No cookie string provided.', 'danger')
        return redirect(url_for('garmin.auth'))
    session_data = json.dumps({'type': 'browser_cookie', 'cookie': cookie_string})
    db = get_db()
    existing = db.execute('SELECT id FROM garmin_auth LIMIT 1').fetchone()
    if existing:
        db.execute(
            "UPDATE garmin_auth SET garth_session=?, garmin_username=?, updated_at=datetime('now') WHERE id=?",
            (session_data, '', existing[0])
        )
    else:
        db.execute(
            'INSERT INTO garmin_auth (garth_session, garmin_username) VALUES (?,?)',
            (session_data, '')
        )
    db.commit()
    flash('Browser session cookies saved. Testing connection on the sync page.', 'success')
    return redirect(url_for('garmin.auth'))


@bp.route('/import-wellness', methods=['GET', 'POST'])
def import_wellness():
    if request.method == 'GET':
        return render_template('garmin/import_wellness.html', preview=None)

    f = request.files.get('fit_file')
    if not f or not f.filename:
        flash('No file selected.', 'warning')
        return redirect(url_for('garmin.import_wellness'))

    fname = f.filename.lower()
    if not (fname.endswith('.fit') or fname.endswith('.zip')):
        flash('File must be a .fit or .zip file.', 'danger')
        return redirect(url_for('garmin.import_wellness'))

    try:
        raw = f.read()
        if fname.endswith('.zip'):
            import zipfile, io
            with zipfile.ZipFile(io.BytesIO(raw)) as zf:
                fit_names = [n for n in zf.namelist() if n.lower().endswith('.fit')]
                if not fit_names:
                    flash('No .fit file found inside the zip.', 'danger')
                    return redirect(url_for('garmin.import_wellness'))
                raw = zf.read(fit_names[0])

        from garmin_fit_parser import parse_wellness_fit
        rows = parse_wellness_fit(raw)

        if not rows:
            flash('No wellness data found in this FIT file. Make sure it\'s a wellness/monitoring file, not an activity file.', 'warning')
            return redirect(url_for('garmin.import_wellness'))

        # Write parsed rows to a temp file — avoids cookie session size limits
        tmp_path = os.path.join(tempfile.gettempdir(), f'wellness_{uuid.uuid4().hex}.json')
        with open(tmp_path, 'w') as fh:
            json.dump(rows, fh)
        flask_session['wellness_tmp'] = tmp_path

        # Build preview summary
        dates = sorted({r['date'] for r in rows if r['date']})
        counts = {
            'total': len(rows),
            'heart_rate': sum(1 for r in rows if r.get('heart_rate')),
            'stress_level': sum(1 for r in rows if r.get('stress_level')),
            'body_battery': sum(1 for r in rows if r.get('body_battery')),
            'respiration_rate': sum(1 for r in rows if r.get('respiration_rate')),
            'steps': sum(1 for r in rows if r.get('steps')),
        }
        preview = {
            'date_min': dates[0] if dates else '?',
            'date_max': dates[-1] if dates else '?',
            'date_count': len(dates),
            'counts': counts,
            'sample': rows[:8],
        }
        return render_template('garmin/import_wellness.html', preview=preview)

    except Exception as e:
        flash(f'Error parsing wellness FIT file: {e}', 'danger')
        return redirect(url_for('garmin.import_wellness'))


@bp.route('/import-wellness/confirm', methods=['POST'])
def import_wellness_confirm():
    tmp_path = flask_session.get('wellness_tmp')
    if not tmp_path or not os.path.exists(tmp_path):
        flash('Session expired or data missing. Please re-upload the file.', 'warning')
        return redirect(url_for('garmin.import_wellness'))

    try:
        with open(tmp_path) as fh:
            rows = json.load(fh)
    except Exception:
        flash('Could not read parsed data. Please re-upload.', 'danger')
        return redirect(url_for('garmin.import_wellness'))
    finally:
        try:
            os.remove(tmp_path)
        except OSError:
            pass
        flask_session.pop('wellness_tmp', None)

    db = get_db()
    inserted = skipped = 0

    for row in rows:
        try:
            cur = db.execute(
                '''INSERT OR IGNORE INTO wellness_log
                   (date, timestamp_ms, heart_rate, stress_level, body_battery,
                    respiration_rate, steps, active_calories, active_time_s,
                    distance_m, activity_type)
                   VALUES (?,?,?,?,?,?,?,?,?,?,?)''',
                (row.get('date'), row.get('timestamp_ms'), row.get('heart_rate'),
                 row.get('stress_level'), row.get('body_battery'),
                 row.get('respiration_rate'), row.get('steps'),
                 row.get('active_calories'), row.get('active_time_s'),
                 row.get('distance_m'), row.get('activity_type'))
            )
            if cur.rowcount:
                inserted += 1
            else:
                skipped += 1
        except Exception:
            skipped += 1

    db.commit()

    msg = f'{inserted} wellness records imported'
    if skipped:
        msg += f', {skipped} already existed (skipped)'
    flash(msg + '.', 'success')
    return redirect(url_for('garmin.wellness_log'))


@bp.route('/wellness')
def wellness_log():
    db = get_db()
    date_filter = request.args.get('date', '')

    # Default to most recent date if none selected, so the chart has something to draw
    if not date_filter:
        latest = db.execute(
            'SELECT date FROM wellness_log ORDER BY date DESC LIMIT 1'
        ).fetchone()
        if latest:
            date_filter = latest['date']

    query = 'SELECT * FROM wellness_log'
    params = []
    if date_filter:
        query += ' WHERE date = ?'
        params.append(date_filter)
    query += ' ORDER BY timestamp_ms DESC LIMIT 2000'
    rows = db.execute(query, params).fetchall()

    # Chart data: ASC by time, only for the single selected day. Each series
    # carries its own x to skip nulls cleanly in Chart.js.
    chart_data = None
    if date_filter and rows:
        asc = sorted([dict(r) for r in rows], key=lambda r: r['timestamp_ms'])
        def series(field):
            return [{'x': r['timestamp_ms'], 'y': r[field]}
                    for r in asc if r.get(field) is not None]
        chart_data = {
            'date': date_filter,
            'heart_rate':       series('heart_rate'),
            'stress_level':     series('stress_level'),
            'body_battery':     series('body_battery'),
            'respiration_rate': series('respiration_rate'),
        }

    # Distinct dates for the date picker
    dates = db.execute(
        'SELECT DISTINCT date FROM wellness_log ORDER BY date DESC LIMIT 60'
    ).fetchall()

    return render_template('garmin/wellness_log.html', rows=rows,
                           dates=dates, date_filter=date_filter,
                           chart_data=chart_data)


@bp.route('/auth/import-tokens', methods=['POST'])
def auth_import_tokens():
    import json
    raw = request.form.get('token_json', '').strip()
    if not raw:
        flash('No token JSON provided.', 'danger')
        return redirect(url_for('garmin.auth'))
    try:
        token_data = json.loads(raw)
    except json.JSONDecodeError as e:
        flash(f'Invalid JSON: {e}', 'danger')
        return redirect(url_for('garmin.auth'))
    try:
        from garmin_connect import _save_session_to_db, _write_session_to_tmp, GARTH_TMP
        import garth, os
        _write_session_to_tmp(json.dumps(token_data))
        garth.resume(GARTH_TMP)
        username = getattr(garth.client, 'username', '')
        db = get_db()
        existing = db.execute('SELECT id FROM garmin_auth LIMIT 1').fetchone()
        session_json = json.dumps(token_data)
        if existing:
            db.execute(
                "UPDATE garmin_auth SET garth_session=?, garmin_username=?, updated_at=datetime('now') WHERE id=?",
                (session_json, username, existing[0])
            )
        else:
            db.execute(
                'INSERT INTO garmin_auth (garth_session, garmin_username) VALUES (?,?)',
                (session_json, username)
            )
        db.commit()
        flash(f'Tokens imported successfully{" for " + username if username else ""}.', 'success')
    except Exception as e:
        flash(f'Token import failed: {e}', 'danger')
    return redirect(url_for('garmin.auth'))
