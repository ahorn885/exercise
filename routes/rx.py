from flask import Blueprint, render_template, request, redirect, url_for, flash
from database import get_db

bp = Blueprint('rx', __name__)


@bp.route('/rx')
def list_entries():
    db = get_db()
    discipline = request.args.get('discipline', '')
    status = request.args.get('status', '')

    query = 'SELECT * FROM current_rx WHERE 1=1'
    params = []
    if discipline:
        query += ' AND discipline=?'
        params.append(discipline)
    if status:
        query += " AND last_outcome LIKE ?"
        params.append(f'%{status}%')
    query += ' ORDER BY discipline, exercise'

    entries = db.execute(query, params).fetchall()
    return render_template('rx/list.html', entries=entries,
                           discipline=discipline, status=status)


@bp.route('/rx/<int:entry_id>/edit', methods=['GET', 'POST'])
def edit_entry(entry_id):
    db = get_db()
    entry = db.execute('SELECT * FROM current_rx WHERE id=?', (entry_id,)).fetchone()
    if not entry:
        flash('Entry not found.', 'danger')
        return redirect(url_for('rx.list_entries'))
    if request.method == 'POST':
        f = request.form
        def num(v, cast=float):
            try: return cast(v) if v else None
            except: return None
        db.execute('''UPDATE current_rx SET
            current_sets=?, current_reps=?, current_weight=?, current_duration=?,
            inventory_sugg_volume=?, rx_source=? WHERE id=?''',
            (num(f.get('current_sets'), int), num(f.get('current_reps'), int),
             num(f.get('current_weight')), num(f.get('current_duration'), int),
             f.get('inventory_sugg_volume'), 'Manual override', entry_id))
        db.commit()
        flash('Rx updated.', 'success')
        return redirect(url_for('rx.list_entries'))
    return render_template('rx/form.html', entry=entry)
