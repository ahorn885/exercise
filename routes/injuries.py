import json

from flask import Blueprint, render_template, request, redirect, url_for, flash
from database import get_db
from routes.auth import current_user_id
from athlete import (
    KNOWN_INJURY_TYPES,
    KNOWN_INJURY_SEVERITIES,
    KNOWN_MOVEMENT_CONSTRAINTS,
    BODY_PART_CONSTRAINTS,
)

bp = Blueprint('injuries', __name__)

STATUSES = ['Active', 'Managing', 'Resolved']
BODY_PARTS = [
    'Left Hand', 'Right Hand',
    'Left Wrist', 'Right Wrist',
    'Left Elbow', 'Right Elbow',
    'Left Shoulder', 'Right Shoulder',
    'Left Knee', 'Right Knee',
    'Left Ankle', 'Right Ankle',
    'Left Foot', 'Right Foot',
    'Left Hip', 'Right Hip',
    'Left Hamstring', 'Right Hamstring',
    'Left Quad', 'Right Quad',
    'Groin',
    'Abdomen',
    'Lower Back', 'Upper Back',
    'Neck',
]

MOD_TYPES = [
    ('avoid',       'Avoid — skip entirely'),
    ('substitute',  'Substitute — replace with another exercise'),
    ('reduce_load', 'Reduce Load — same exercise, lower intensity'),
    ('modify',      'Modify — same exercise with adjustments'),
]


@bp.route('/injuries')
def list_entries():
    db = get_db()
    status_filter = request.args.get('status', '')
    body_part_filter = request.args.get('body_part', '')

    uid = current_user_id()
    query = "SELECT * FROM injury_log WHERE user_id = ?"
    params = [uid]
    if status_filter:
        query += ' AND status=?'
        params.append(status_filter)
    if body_part_filter:
        query += ' AND body_part LIKE ?'
        params.append(f'%{body_part_filter}%')
    query += " ORDER BY CASE status WHEN 'Active' THEN 0 WHEN 'Managing' THEN 1 ELSE 2 END, start_date DESC"
    entries = db.execute(query, params).fetchall()

    # Load all modifications grouped by injury_id (parent-JOIN scoped via injury_log)
    mod_rows = db.execute(
        '''SELECT iem.*, ei.exercise as exercise_name,
                  ei_sub.exercise as substitute_name
           FROM injury_exercise_modifications iem
           JOIN injury_log il ON il.id = iem.injury_id
           JOIN exercise_inventory ei ON ei.id = iem.exercise_id
           LEFT JOIN exercise_inventory ei_sub ON ei_sub.id = iem.substitute_exercise_id
           WHERE il.user_id = ?
           ORDER BY iem.injury_id, iem.id''',
        (uid,)
    ).fetchall()
    modifications = {}
    for m in mod_rows:
        modifications.setdefault(m['injury_id'], []).append(m)

    exercises = db.execute(
        'SELECT id, exercise, discipline, movement_pattern FROM exercise_inventory ORDER BY discipline, exercise'
    ).fetchall()

    return render_template('injuries/list.html', entries=entries,
                           modifications=modifications, exercises=exercises,
                           mod_types=MOD_TYPES,
                           status_filter=status_filter, body_part_filter=body_part_filter,
                           statuses=STATUSES)


@bp.route('/injuries/new', methods=['GET', 'POST'])
def new_entry():
    db = get_db()
    if request.method == 'POST':
        _save(db, None)
        flash('Injury logged.', 'success')
        return redirect(url_for('injuries.list_entries'))
    return render_template('injuries/form.html', entry=None,
                           statuses=STATUSES, body_parts=BODY_PARTS,
                           injury_types=KNOWN_INJURY_TYPES,
                           severities=KNOWN_INJURY_SEVERITIES,
                           movement_constraints=KNOWN_MOVEMENT_CONSTRAINTS,
                           body_part_constraints=BODY_PART_CONSTRAINTS,
                           entry_movement_constraints=[])


@bp.route('/injuries/<int:entry_id>/edit', methods=['GET', 'POST'])
def edit_entry(entry_id):
    db = get_db()
    entry = db.execute(
        'SELECT * FROM injury_log WHERE id=? AND user_id=?',
        (entry_id, current_user_id())
    ).fetchone()
    if not entry:
        flash('Entry not found.', 'danger')
        return redirect(url_for('injuries.list_entries'))
    if request.method == 'POST':
        _save(db, entry_id)
        flash('Entry updated.', 'success')
        return redirect(url_for('injuries.list_entries'))
    # movement_constraints is JSONB on read — psycopg2 returns the parsed
    # list, but SQLite (legacy compatibility layer) returns the raw JSON
    # string. Normalize for the template's `in` membership checks.
    raw_mc = entry['movement_constraints'] if entry and 'movement_constraints' in entry.keys() else None
    if isinstance(raw_mc, str):
        try:
            raw_mc = json.loads(raw_mc)
        except (json.JSONDecodeError, TypeError):
            raw_mc = []
    entry_mc = raw_mc or []
    return render_template('injuries/form.html', entry=entry,
                           statuses=STATUSES, body_parts=BODY_PARTS,
                           injury_types=KNOWN_INJURY_TYPES,
                           severities=KNOWN_INJURY_SEVERITIES,
                           movement_constraints=KNOWN_MOVEMENT_CONSTRAINTS,
                           body_part_constraints=BODY_PART_CONSTRAINTS,
                           entry_movement_constraints=entry_mc)


@bp.route('/injuries/<int:entry_id>/delete', methods=['POST'])
def delete_entry(entry_id):
    db = get_db()
    uid = current_user_id()
    # Verify ownership before clearing the parent-JOIN scoped child
    if not db.execute(
        'SELECT 1 FROM injury_log WHERE id=? AND user_id=?', (entry_id, uid)
    ).fetchone():
        flash('Entry not found.', 'danger')
        return redirect(url_for('injuries.list_entries'))
    db.execute('DELETE FROM injury_exercise_modifications WHERE injury_id=?', (entry_id,))
    db.execute('DELETE FROM injury_log WHERE id=? AND user_id=?', (entry_id, uid))
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

    # Verify the parent injury belongs to the current user
    if not db.execute(
        'SELECT 1 FROM injury_log WHERE id=? AND user_id=?',
        (entry_id, current_user_id())
    ).fetchone():
        flash('Injury not found.', 'danger')
        return redirect(url_for('injuries.list_entries'))

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
    # Parent-JOIN scope: ensure the injury belongs to the user before deleting
    if not db.execute(
        'SELECT 1 FROM injury_log WHERE id=? AND user_id=?',
        (entry_id, current_user_id())
    ).fetchone():
        return redirect(url_for('injuries.list_entries'))
    db.execute(
        'DELETE FROM injury_exercise_modifications WHERE id=? AND injury_id=?',
        (mod_id, entry_id)
    )
    db.commit()
    return redirect(url_for('injuries.list_entries') + f'#injury-{entry_id}')


def _save(db, entry_id):
    f = request.form
    uid = current_user_id()
    # Closed-enum reads — silently coerce out-of-enum values to NULL rather
    # than fail the save; the UI's <select> shapes guarantee in-enum input
    # under normal use. Empty-string ("—" placeholder selection) also maps
    # to NULL.
    def enum_or_none(value, allowed):
        return value if value in allowed else None
    severity = enum_or_none(f.get('severity'), KNOWN_INJURY_SEVERITIES)
    injury_type = enum_or_none(f.get('injury_type'), KNOWN_INJURY_TYPES)
    # Side is derived from the body_part prefix ('Left Wrist' → 'Left')
    # rather than a dedicated form field; side-less parts default to 'N/A'.
    body_part = f.get('body_part') or ''
    if body_part.startswith('Left '):
        side = 'Left'
    elif body_part.startswith('Right '):
        side = 'Right'
    else:
        side = 'N/A'
    mc_raw = f.getlist('movement_constraints')
    mc = [c for c in mc_raw if c in KNOWN_MOVEMENT_CONSTRAINTS]
    mc_json = json.dumps(mc)
    vals = (
        f.get('start_date'), f.get('body_part'), f.get('description'),
        severity, injury_type, side, mc_json, f.get('modifications_needed'),
        f.get('status'), f.get('resolved_date') or None,
    )
    if entry_id:
        db.execute(
            '''UPDATE injury_log SET start_date=?,body_part=?,description=?,
               severity=?,injury_type=?,side=?,movement_constraints=?,
               modifications_needed=?,status=?,resolved_date=?
               WHERE id=? AND user_id=?''',
            vals + (entry_id, uid),
        )
    else:
        db.execute(
            '''INSERT INTO injury_log
               (start_date,body_part,description,severity,injury_type,side,
                movement_constraints,modifications_needed,status,resolved_date,
                user_id)
               VALUES (?,?,?,?,?,?,?,?,?,?,?)''',
            vals + (uid,),
        )
    db.commit()
