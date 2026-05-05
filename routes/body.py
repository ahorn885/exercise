import os
from flask import Blueprint, render_template, request, redirect, url_for, flash
from database import get_db
from routes.auth import current_user_id

_IS_PG = bool(os.environ.get('DATABASE_URL'))

bp = Blueprint('body', __name__)


@bp.route('/body')
def list_entries():
    db = get_db()
    entries = db.execute(
        'SELECT * FROM body_metrics WHERE user_id = ? ORDER BY date DESC',
        (current_user_id(),)
    ).fetchall()
    return render_template('body/list.html', entries=entries)


@bp.route('/body/new', methods=['GET', 'POST'])
def new_entry():
    db = get_db()
    if request.method == 'POST':
        _save(db, None)
        flash('Body metrics logged.', 'success')
        return redirect(url_for('body.list_entries'))
    return render_template('body/form.html', entry=None)


@bp.route('/body/<int:entry_id>/edit', methods=['GET', 'POST'])
def edit_entry(entry_id):
    db = get_db()
    entry = db.execute(
        'SELECT * FROM body_metrics WHERE id=? AND user_id=?',
        (entry_id, current_user_id())
    ).fetchone()
    if not entry:
        flash('Entry not found.', 'danger')
        return redirect(url_for('body.list_entries'))
    if request.method == 'POST':
        _save(db, entry_id)
        flash('Entry updated.', 'success')
        return redirect(url_for('body.list_entries'))
    return render_template('body/form.html', entry=entry)


@bp.route('/body/<int:entry_id>/delete', methods=['POST'])
def delete_entry(entry_id):
    db = get_db()
    db.execute(
        'DELETE FROM body_metrics WHERE id=? AND user_id=?',
        (entry_id, current_user_id())
    )
    db.commit()
    flash('Entry deleted.', 'warning')
    return redirect(url_for('body.list_entries'))


def _save(db, entry_id):
    f = request.form
    uid = current_user_id()
    def num(v, cast=float):
        try: return cast(v) if v else None
        except: return None
    vals = (f.get('date'), num(f.get('weight_lbs')), num(f.get('body_fat_pct')),
            num(f.get('vo2_max')), num(f.get('resting_hr'), int), f.get('notes'))
    if entry_id:
        db.execute('UPDATE body_metrics SET date=?,weight_lbs=?,body_fat_pct=?,vo2_max=?,resting_hr=?,notes=? '
                   'WHERE id=? AND user_id=?',
                   vals + (entry_id, uid))
    else:
        if _IS_PG:
            db.execute('''INSERT INTO body_metrics (date,weight_lbs,body_fat_pct,vo2_max,resting_hr,notes,user_id)
                VALUES (?,?,?,?,?,?,?)
                ON CONFLICT (date) DO UPDATE SET
                weight_lbs=EXCLUDED.weight_lbs, body_fat_pct=EXCLUDED.body_fat_pct,
                vo2_max=EXCLUDED.vo2_max, resting_hr=EXCLUDED.resting_hr, notes=EXCLUDED.notes''', vals + (uid,))
        else:
            db.execute('INSERT OR REPLACE INTO body_metrics (date,weight_lbs,body_fat_pct,vo2_max,resting_hr,notes,user_id) VALUES (?,?,?,?,?,?,?)', vals + (uid,))
    db.commit()
