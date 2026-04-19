from datetime import date, timedelta

from flask import Blueprint, render_template, request, redirect, url_for, flash, jsonify, session as flask_session
from database import get_db

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
           WHERE pi.status = 'scheduled'
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
        inserted = 0
        for row in rows:
            row['notes'] = request.form.get('notes') or row.get('notes')
            db.execute(
                '''INSERT INTO training_log
                   (date, exercise, actual_sets, actual_reps, actual_weight,
                    actual_duration, plan_item_id, notes)
                   VALUES (?,?,?,?,?,?,?,?)''',
                (row.get('date'), row.get('exercise'),
                 row.get('actual_sets'), row.get('actual_reps'),
                 row.get('actual_weight'), row.get('actual_duration'),
                 plan_item_id, row.get('notes'))
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
            for row in rows:
                db.execute(
                    '''INSERT INTO training_log
                       (date, exercise, actual_sets, actual_reps, actual_weight,
                        actual_duration, garmin_activity_id, plan_item_id, notes)
                       VALUES (?,?,?,?,?,?,?,?,?)''',
                    (row.get('date'), row.get('exercise'),
                     row.get('actual_sets'), row.get('actual_reps'),
                     row.get('actual_weight'), row.get('actual_duration'),
                     gid, plan_item_id, notes)
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
