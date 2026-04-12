from flask import Blueprint, render_template, request, redirect, url_for, flash
from database import get_db

bp = Blueprint('conditions', __name__)

WIND_DIRS = ['N', 'NE', 'E', 'SE', 'S', 'SW', 'W', 'NW', 'Calm', 'Variable']
CONDITIONS = ['Sunny', 'Partly Cloudy', 'Overcast', 'Light Rain', 'Heavy Rain',
              'Snow', 'Sleet/Mix', 'Fog', 'Windy', 'Humid']


@bp.route('/conditions')
def list_entries():
    db = get_db()
    entries = db.execute('SELECT * FROM conditions_log ORDER BY date DESC').fetchall()
    return render_template('conditions/list.html', entries=entries)


@bp.route('/conditions/new', methods=['GET', 'POST'])
def new_entry():
    db = get_db()
    if request.method == 'POST':
        _save(db, None)
        flash('Conditions logged.', 'success')
        return redirect(url_for('conditions.list_entries'))
    return render_template('conditions/form.html', entry=None,
                           wind_dirs=WIND_DIRS, conditions_opts=CONDITIONS)


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
    return render_template('conditions/form.html', entry=entry,
                           wind_dirs=WIND_DIRS, conditions_opts=CONDITIONS)


@bp.route('/conditions/<int:entry_id>/delete', methods=['POST'])
def delete_entry(entry_id):
    db = get_db()
    db.execute('DELETE FROM conditions_log WHERE id=?', (entry_id,))
    db.commit()
    flash('Entry deleted.', 'warning')
    return redirect(url_for('conditions.list_entries'))


def _save(db, entry_id):
    f = request.form
    def num(v, cast=float):
        try: return cast(v) if v else None
        except: return None
    vals = (
        f.get('date'), f.get('activity'),
        num(f.get('temp_f')), num(f.get('feels_like_f')), num(f.get('wind_mph')),
        f.get('wind_dir'), f.get('conditions'),
        f.get('headwear'), f.get('face_neck'), f.get('upper_shell'),
        f.get('upper_mid_layer'), f.get('upper_base_layer'),
        f.get('lower_outer'), f.get('lower_under'), f.get('gloves'),
        f.get('arm_warmers'), f.get('socks'), f.get('footwear'),
        num(f.get('comfort'), int), f.get('comfort_notes')
    )
    if entry_id:
        db.execute('''UPDATE conditions_log SET date=?,activity=?,temp_f=?,feels_like_f=?,
            wind_mph=?,wind_dir=?,conditions=?,headwear=?,face_neck=?,upper_shell=?,
            upper_mid_layer=?,upper_base_layer=?,lower_outer=?,lower_under=?,gloves=?,
            arm_warmers=?,socks=?,footwear=?,comfort=?,comfort_notes=? WHERE id=?''',
            vals + (entry_id,))
    else:
        db.execute('''INSERT INTO conditions_log
            (date,activity,temp_f,feels_like_f,wind_mph,wind_dir,conditions,headwear,
             face_neck,upper_shell,upper_mid_layer,upper_base_layer,lower_outer,lower_under,
             gloves,arm_warmers,socks,footwear,comfort,comfort_notes)
            VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)''', vals)
    db.commit()
