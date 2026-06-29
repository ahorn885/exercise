import json

from flask import Blueprint, render_template, request, redirect, url_for, flash
from database import get_db
from routes.auth import current_user_id
from athlete import (
    KNOWN_INJURY_TYPES,
    KNOWN_INJURY_SEVERITIES,
    KNOWN_INJURY_SIDES,
    KNOWN_MOVEMENT_CONSTRAINTS,
    BODY_PART_CONSTRAINTS,
)
from layer0_catalog import strength_catalog

bp = Blueprint('injuries', __name__)

STATUSES = ['Active', 'Managing', 'Resolved']
# #255 — the body-part picker is now the side-less canonical vocab
# (`layer0.body_parts.canonical_name`), grouped by region for the <optgroup>
# select; side is captured by a separate field. Keys mirror BODY_PART_CONSTRAINTS.
BODY_PART_GROUPS = [
    ('Head / Neck',  ['Neck', 'Jaw', 'Trapezius']),
    ('Shoulder',     ['Shoulder', 'Rotator cuff', 'AC joint', 'Shoulder blade',
                      'Collarbone']),
    ('Arm',          ['Elbow', 'Forearm', 'Wrist', 'Hand', 'Biceps', 'Triceps',
                      'Fingers', 'Thumb', 'Finger pulley', 'DIP joint',
                      'CMC joint']),
    ('Back',         ['Upper back', 'Lower back', 'Spine (general)', 'SI joint',
                      'Sciatica']),
    ('Hip',          ['Hip', 'Groin', 'Hip flexor', 'Glute',
                      'Hip crest (iliac crest)', 'TFL']),
    ('Upper leg',    ['Quad', 'Hamstring', 'IT band']),
    ('Knee',         ['Knee', 'Kneecap', 'Meniscus', 'ACL', 'PCL', 'MCL', 'LCL']),
    ('Lower leg',    ['Calf', 'Soleus', 'Shin', 'Achilles', 'Peroneal']),
    ('Foot / Ankle', ['Ankle', 'Plantar fascia', 'Foot', 'Toes']),
    ('Trunk',        ['Rib', 'Chest']),
]

MOD_TYPES = [
    ('avoid',       'Avoid — skip entirely'),
    ('substitute',  'Substitute — replace with another exercise'),
    ('reduce_load', 'Reduce Load — same exercise, lower intensity'),
    ('modify',      'Modify — same exercise with adjustments'),
]


def _after_save_redirect():
    """Where to land after a create/edit/delete. The injury log is surfaced on
    the profile Health tab (#886); when an action is launched from there the
    form/list carries `return=profile`, so we bounce back to it (anchored at
    the injuries card) instead of the standalone log. Fixed endpoints only —
    no user-supplied URL, so no open-redirect surface."""
    if request.values.get('return') == 'profile':
        return redirect(url_for('profile.edit', tab='health') + '#injuries')
    return redirect(url_for('injuries.list_entries'))


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
        '''SELECT iem.*, lx.exercise_name AS exercise_name,
                  lx_sub.exercise_name AS substitute_name
           FROM injury_exercise_modifications iem
           JOIN injury_log il ON il.id = iem.injury_id
           LEFT JOIN layer0.exercises lx
                  ON lx.exercise_id = iem.exercise_ex_id AND lx.superseded_at IS NULL
           LEFT JOIN layer0.exercises lx_sub
                  ON lx_sub.exercise_id = iem.substitute_ex_id AND lx_sub.superseded_at IS NULL
           WHERE il.user_id = ?
           ORDER BY iem.injury_id, iem.id''',
        (uid,)
    ).fetchall()
    modifications = {}
    for m in mod_rows:
        modifications.setdefault(m['injury_id'], []).append(m)

    # Exercise picker for the modification form: the single canonical layer0
    # catalog, keyed by EX-id (the value the form posts + we store).
    exercises = sorted(strength_catalog(db),
                       key=lambda r: ((r['movement_pattern'] or ''), (r['exercise'] or '')))

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
        return _after_save_redirect()
    return render_template('injuries/form.html', entry=None,
                           statuses=STATUSES, body_part_groups=BODY_PART_GROUPS,
                           sides=KNOWN_INJURY_SIDES,
                           injury_types=KNOWN_INJURY_TYPES,
                           severities=KNOWN_INJURY_SEVERITIES,
                           movement_constraints=KNOWN_MOVEMENT_CONSTRAINTS,
                           body_part_constraints=BODY_PART_CONSTRAINTS,
                           entry_movement_constraints=[],
                           return_to=request.args.get('return'))


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
        return _after_save_redirect()
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
                           statuses=STATUSES, body_part_groups=BODY_PART_GROUPS,
                           sides=KNOWN_INJURY_SIDES,
                           injury_types=KNOWN_INJURY_TYPES,
                           severities=KNOWN_INJURY_SEVERITIES,
                           movement_constraints=KNOWN_MOVEMENT_CONSTRAINTS,
                           body_part_constraints=BODY_PART_CONSTRAINTS,
                           entry_movement_constraints=entry_mc,
                           return_to=request.args.get('return'))


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
    return _after_save_redirect()


@bp.route('/injuries/<int:entry_id>/modifications/add', methods=['POST'])
def add_modification(entry_id):
    db = get_db()
    # The picker now posts layer0 EX-ids (the single canonical catalog), stored
    # directly in exercise_ex_id / substitute_ex_id.
    exercise_ex_id = (request.form.get('exercise_id') or '').strip()
    substitute_ex_id = (request.form.get('substitute_exercise_id') or '').strip() or None
    mod_type = request.form.get('modification_type', 'modify')
    notes = request.form.get('modification_notes', '').strip()

    if not exercise_ex_id:
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
           (injury_id, exercise_ex_id, substitute_ex_id, modification_type, modification_notes)
           VALUES (?, ?, ?, ?, ?)''',
        (entry_id, exercise_ex_id, substitute_ex_id, mod_type, notes or None)
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
    # Side is its own form field now (#255 — the body_part picker is side-less
    # canonical); out-of-enum / missing values coerce to 'N/A'.
    side = f.get('side') if f.get('side') in KNOWN_INJURY_SIDES else 'N/A'
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
