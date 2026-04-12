from flask import Blueprint, render_template, request, redirect, url_for, flash
from database import get_db

bp = Blueprint('injuries', __name__)

STATUSES = ['Active', 'Managing', 'Resolved']
BODY_PARTS = ['Left Wrist', 'Right Wrist', 'Left Knee', 'Right Knee', 'Left Ankle',
              'Right Ankle', 'Left Hip', 'Right Hip', 'Lower Back', 'Upper Back',
              'Left Shoulder', 'Right Shoulder', 'Neck', 'Left Hamstring',
              'Right Hamstring', 'Left Quad', 'Right Quad', 'Other']


@bp.route('/injuries')
def list_entries():
    db = get_db()
    entries = db.execute(
        "SELECT * FROM injury_log ORDER BY CASE status WHEN 'Active' THEN 0 WHEN 'Managing' THEN 1 ELSE 2 END, start_date DESC"
    ).fetchall()
    return render_template('injuries/list.html', entries=entries)


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
    db.execute('DELETE FROM injury_log WHERE id=?', (entry_id,))
    db.commit()
    flash('Entry deleted.', 'warning')
    return redirect(url_for('injuries.list_entries'))


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
