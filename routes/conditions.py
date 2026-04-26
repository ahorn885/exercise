from flask import Blueprint, render_template, request, redirect, url_for, flash
from database import get_db

bp = Blueprint('conditions', __name__)

WIND_DIRS = ['N', 'NE', 'E', 'SE', 'S', 'SW', 'W', 'NW', 'Calm', 'Variable']
CONDITION_ACTIVITIES = [
    'Running', 'Treadmill', 'Trail Running', 'Hiking', 'Stair Climbing',
    'Road Cycling', 'Mountain Biking', 'Gravel Cycling', 'Indoor Bike Trainer',
    'Kayaking', 'Pack Rafting', 'Kayak Ergometer', 'Rowing Ergometer',
    'Swimming Pool', 'Swimming Open', 'Yoga', 'Strength Training', 'Other',
]
WEATHER_CONDITIONS = ['Sunny', 'Partly Cloudy', 'Overcast', 'Light Rain', 'Heavy Rain',
                      'Snow', 'Sleet/Mix', 'Fog', 'Windy', 'Humid']
CLOTHING_FIELDS = [
    ('headwear', 'Headwear'),
    ('face_neck', 'Face/Neck'),
    ('upper_shell', 'Upper Shell'),
    ('upper_mid_layer', 'Upper Mid'),
    ('upper_base_layer', 'Upper Base'),
    ('lower_outer', 'Lower Outer'),
    ('lower_under', 'Lower Under'),
    ('gloves', 'Gloves'),
    ('arm_warmers', 'Arm Warmers'),
    ('socks', 'Socks'),
    ('footwear', 'Footwear'),
]

INDOOR_ACTIVITIES = {'Treadmill', 'Indoor Bike Trainer', 'Kayak Ergometer',
                     'Rowing Ergometer', 'Swimming Pool', 'Yoga', 'Strength Training'}


@bp.route('/conditions')
def list_entries():
    db = get_db()
    date_filter = request.args.get('date', '')
    activity_filter = request.args.get('activity', '')

    query = 'SELECT * FROM conditions_log WHERE 1=1'
    params = []
    if date_filter:
        query += ' AND date=?'
        params.append(date_filter)
    if activity_filter:
        query += ' AND activity LIKE ?'
        params.append(f'%{activity_filter}%')
    query += ' ORDER BY date DESC'

    entries = db.execute(query, params).fetchall()
    return render_template('conditions/list.html', entries=entries,
                           date_filter=date_filter, activity_filter=activity_filter)


@bp.route('/conditions/new', methods=['GET', 'POST'])
def new_entry():
    db = get_db()
    if request.method == 'POST':
        _save(db, None)
        flash('Conditions logged.', 'success')
        return redirect(url_for('conditions.list_entries'))
    cardio_sessions = _load_cardio_sessions(db)
    clothing_options = _load_clothing_options(db)
    # Pre-fill from a specific cardio session if provided
    prefill = None
    cardio_log_id = request.args.get('cardio_log_id', type=int)
    if cardio_log_id:
        row = db.execute(
            'SELECT id, date, activity FROM cardio_log WHERE id=?', (cardio_log_id,)
        ).fetchone()
        if row:
            prefill = {'cardio_log_id': row['id'], 'date': row['date'], 'activity': row['activity']}
    return render_template('conditions/form.html', entry=None, prefill=prefill,
                           wind_dirs=WIND_DIRS, conditions_opts=WEATHER_CONDITIONS,
                           activities=CONDITION_ACTIVITIES, clothing_options=clothing_options,
                           clothing_fields=CLOTHING_FIELDS, indoor_activities=INDOOR_ACTIVITIES,
                           cardio_sessions=cardio_sessions)


@bp.route('/conditions/<int:entry_id>/edit', methods=['GET', 'POST'])
def edit_entry(entry_id):
    db = get_db()
    entry = db.execute('SELECT * FROM conditions_log WHERE id=?', (entry_id,)).fetchone()
    if not entry:
        flash('Entry not found.', 'danger')
        return redirect(url_for('conditions.list_entries'))
    if request.method == 'POST':
        _save(db, entry_id)
        flash('Entry updated.', 'success')
        return redirect(url_for('conditions.list_entries'))
    cardio_sessions = _load_cardio_sessions(db)
    clothing_options = _load_clothing_options(db)
    return render_template('conditions/form.html', entry=entry, prefill=None,
                           wind_dirs=WIND_DIRS, conditions_opts=WEATHER_CONDITIONS,
                           activities=CONDITION_ACTIVITIES, clothing_options=clothing_options,
                           clothing_fields=CLOTHING_FIELDS, indoor_activities=INDOOR_ACTIVITIES,
                           cardio_sessions=cardio_sessions)


@bp.route('/conditions/<int:entry_id>/delete', methods=['POST'])
def delete_entry(entry_id):
    db = get_db()
    db.execute('DELETE FROM conditions_log WHERE id=?', (entry_id,))
    db.commit()
    flash('Entry deleted.', 'warning')
    return redirect(url_for('conditions.list_entries'))


def _load_cardio_sessions(db):
    return db.execute(
        '''SELECT id, date, activity, activity_name
           FROM cardio_log
           ORDER BY date DESC, id DESC
           LIMIT 60'''
    ).fetchall()


def _load_clothing_options(db):
    """Return {category: [value, ...]} dict from clothing_options table."""
    rows = db.execute('SELECT category, value FROM clothing_options ORDER BY category, value').fetchall()
    opts = {}
    for row in rows:
        opts.setdefault(row['category'], []).append(row['value'])
    return opts


def _save(db, entry_id):
    f = request.form

    def num(v, cast=float):
        try:
            return cast(v) if v else None
        except (ValueError, TypeError):
            return None

    is_indoor = bool(f.get('is_indoor'))
    cardio_log_id = num(f.get('cardio_log_id'), int)

    # For indoor sessions, clear outdoor-only fields
    wind_mph = None if is_indoor else num(f.get('wind_mph'))
    wind_dir = None if is_indoor else f.get('wind_dir') or None
    conditions = None if is_indoor else f.get('conditions') or None

    # Auto-persist any new clothing values typed by the user
    clothing_vals = {}
    for field, _label in CLOTHING_FIELDS:
        val = f.get(field) or None
        clothing_vals[field] = val
        if val:
            try:
                db.execute(
                    'INSERT OR IGNORE INTO clothing_options (category, value) VALUES (?, ?)',
                    (field, val)
                )
            except Exception:
                pass

    vals = (
        f.get('date'), f.get('activity'),
        num(f.get('temp_f')), num(f.get('feels_like_f')),
        wind_mph, wind_dir, conditions,
        clothing_vals['headwear'], clothing_vals['face_neck'],
        clothing_vals['upper_shell'], clothing_vals['upper_mid_layer'],
        clothing_vals['upper_base_layer'], clothing_vals['lower_outer'],
        clothing_vals['lower_under'], clothing_vals['gloves'],
        clothing_vals['arm_warmers'], clothing_vals['socks'], clothing_vals['footwear'],
        num(f.get('comfort'), int), f.get('comfort_notes') or None, cardio_log_id
    )

    if entry_id:
        db.execute('''UPDATE conditions_log SET date=?,activity=?,temp_f=?,feels_like_f=?,
            wind_mph=?,wind_dir=?,conditions=?,headwear=?,face_neck=?,upper_shell=?,
            upper_mid_layer=?,upper_base_layer=?,lower_outer=?,lower_under=?,gloves=?,
            arm_warmers=?,socks=?,footwear=?,comfort=?,comfort_notes=?,cardio_log_id=?
            WHERE id=?''',
            vals + (entry_id,))
    else:
        db.execute('''INSERT INTO conditions_log
            (date,activity,temp_f,feels_like_f,wind_mph,wind_dir,conditions,headwear,
             face_neck,upper_shell,upper_mid_layer,upper_base_layer,lower_outer,lower_under,
             gloves,arm_warmers,socks,footwear,comfort,comfort_notes,cardio_log_id)
            VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)''', vals)

    db.commit()
