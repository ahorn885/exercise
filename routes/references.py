from flask import Blueprint, render_template, request
from database import get_db

bp = Blueprint('references', __name__)

LOCALES = ['home', 'hotel', 'partner', 'airport']


@bp.route('/exercises')
def exercises():
    db = get_db()
    locale_filter = request.args.getlist('locale')  # list of checked locales

    rows = db.execute('SELECT * FROM exercise_inventory ORDER BY discipline, exercise').fetchall()

    if locale_filter:
        # Keep rows that have ALL selected locales
        rows = [r for r in rows
                if all(loc in (r['where_available'] or '').split(',') for loc in locale_filter)]

    return render_template('references/exercises.html', rows=rows,
                           locale_filter=locale_filter, locales=LOCALES)


@bp.route('/rx/setup/<exercise>', methods=['GET'])
def rx_setup(exercise):
    """Redirect to rx edit for setup."""
    from flask import redirect, url_for
    db = get_db()
    row = db.execute('SELECT id FROM current_rx WHERE exercise=?', (exercise,)).fetchone()
    if row:
        return redirect(url_for('rx.edit_entry', entry_id=row['id']))
    return redirect(url_for('rx.list_entries'))
