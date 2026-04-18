from flask import Blueprint, render_template, request, redirect, url_for, flash
from database import get_db

bp = Blueprint('injuries', __name__)

STATUSES = ['Active', 'Managing', 'Resolved']
BODY_PARTS = ['Left Wrist', 'Right Wrist', 'Left Knee', 'Right Knee', 'Left Ankle',
              'Right Ankle', 'Left Hip', 'Right Hip', 'Lower Back', 'Upper Back',
              'Left Shoulder', 'Right Shoulder', 'Neck', 'Left Hamstring',
              'Right Hamstring', 'Left Quad', 'Right Quad', 'Other']

MOD_TYPES = [
    ('avoid',       'Avoid — skip entirely'),
    ('substitute',  'Substitute — replace with another exercise'),
    ('reduce_load', 'Reduce Load — same exercise, lower intensity'),
    ('modify',      'Modify — same exercise with adjustments'),
]


@bp.route('/injuries')
def list_entries():
    db = get_db()
    entries = db.execute(
        "SELECT * FROM injury_log ORDER BY CASE status WHEN 'Active' THEN 0 WHEN 'Managing' THEN 1 ELSE 2 END, start_date DESC"
    ).fetchall()

    # Load all modifications grouped by injury_id
    mod_rows = db.execute(
        '''SELECT iem.*, ei.exercise as exercise_name,
                  ei_sub.exercise as substitute_name
           FROM injury_exercise_modifications iem
           JOIN exercise_inventory ei ON ei.id = iem.exercise_id
           LEFT JOIN exercise_inventory ei_sub ON ei_sub.id = iem.substitute_exercise_id
           ORDER BY iem.injury_id, iem.id'''
    ).fetchall()
    modifications = {}
    for m in mod_rows:
        modifications.setdefault(m['injury_id'], []).append(m)

    exercises = db.execute(
        'SELECT id, exercise, discipline, movement_pattern FROM exercise_inventory ORDER BY discipline, exercise'
    ).fetchall()

    return render_template('injuries/list.html', entries=entries,
                           modifications=modifications, exercises=exercises,
                           mod_types=MOD_TYPES)


@bp.route('/injuries/new', methods=['GET', 'POST'])
def new_entry():
    db = get_db()
    if request.method == 'POST':
        _save(db, None)
        flash('Injury logged.', 'success')
        return redirect(url_for('injuries.list_entries'))
    return render_template('injuries/form.html', entry=None,
                           statuses=STATUSES, body_parts=BODY_PARTS)


@bp.route('/injuries/<int:entry_id>/edit', methods=['GET', 'POST'])
def edit_entry(entry_id):
    db = get_db()
    entry = db.execute('SELECT * FROM injury_log WHERE id=?', (entry_id,)).fetchone()
    if not entry:
        flash('Entry not found.', 'danger')
        return redirect(url_for('injuries.list_entries'))
    if request.method == 'POST':
        _save(db, entry_id)
        flash('Entry updated.', 'success')
        return redirect(url_for('injuries.list_entries'))
    return render_template('injuries/form.html', entry=entry,
                           statuses=STATUSES, body_parts=BODY_PARTS)


@bp.route('/injuries/<int:entry_id>/delete', methods=['POST'])
def delete_entry(entry_id):
    db = get_db()
    db.execute('DELETE FROM injury_exercise_modifications WHERE injury_id=?', (entry_id,))
    db.execute('DELETE FROM injury_log WHERE id=?', (entry_id,))
    db.commit()
    flash('Entry deleted.', 'warning')
    return redirect(url_for('injuries.list_entries'))


@bp.route('/injuries/<int:entry_id>/modifications/add', methods=['POST'])
def add_modification(entry_id):
    db = get_db()
    exercise_id = request.form.get('exercise_id', type=int)
    substitute_id = request.form.get('substitute_exercise_id', type=int) or None
    mod_type = request.form.get('modification_type', 'modify')
    notes = request.form.get('modification_notes', '').strip()

    if not exercise_id:
        flash('Select an exercise to modify.', 'warning')
        return redirect(url_for('injuries.list_entries') + f'#injury-{entry_id}')

    valid_types = {t for t, _ in MOD_TYPES}
    if mod_type not in valid_types:
        mod_type = 'modify'

    db.execute(
        '''INSERT INTO injury_exercise_modifications
           (injury_id, exercise_id, substitute_exercise_id, modification_type, modification_notes)
           VALUES (?, ?, ?, ?, ?)''',
        (entry_id, exercise_id, substitute_id, mod_type, notes or None)
    )
    db.commit()
    flash('Exercise modification saved.', 'success')
    return redirect(url_for('injuries.list_entries') + f'#injury-{entry_id}')


@bp.route('/injuries/<int:entry_id>/modifications/<int:mod_id>/delete', methods=['POST'])
def delete_modification(entry_id, mod_id):
    db = get_db()
    db.execute(
        'DELETE FROM injury_exercise_modifications WHERE id=? AND injury_id=?',
        (mod_id, entry_id)
    )
    db.commit()
    return redirect(url_for('injuries.list_entries') + f'#injury-{entry_id}')


def _save(db, entry_id):
    f = request.form
    def num(v, cast=int):
        try: return cast(v) if v else None
        except: return None
    vals = (
        f.get('start_date'), f.get('body_part'), f.get('description'),
        num(f.get('severity')), f.get('modifications_needed'),
        f.get('status'), f.get('resolved_date') or None
    )
    if entry_id:
        db.execute('''UPDATE injury_log SET start_date=?,body_part=?,description=?,
            severity=?,modifications_needed=?,status=?,resolved_date=? WHERE id=?''',
            vals + (entry_id,))
    else:
        db.execute('''INSERT INTO injury_log
            (start_date,body_part,description,severity,modifications_needed,status,resolved_date)
            VALUES (?,?,?,?,?,?,?)''', vals)
    db.commit()
