from flask import Blueprint, render_template
from database import get_db

bp = Blueprint('references', __name__)


@bp.route('/exercises')
def exercises():
    db = get_db()
    rows = db.execute('SELECT * FROM exercise_inventory ORDER BY discipline, exercise').fetchall()
    return render_template('references/exercises.html', rows=rows)


@bp.route('/rx/setup/<exercise>', methods=['GET'])
def rx_setup(exercise):
    """Redirect to rx edit for setup."""
    from flask import redirect, url_for
    db = get_db()
    row = db.execute('SELECT id FROM current_rx WHERE exercise=?', (exercise,)).fetchone()
    if row:
        return redirect(url_for('rx.edit_entry', entry_id=row['id']))
    return redirect(url_for('rx.list_entries'))
