from flask import Blueprint, render_template, request, redirect, url_for, flash, session as flask_session
from database import get_db

bp = Blueprint('garmin', __name__, url_prefix='/garmin')


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
