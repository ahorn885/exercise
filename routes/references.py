from flask import Blueprint, render_template, request
from database import get_db
from routes.locales import LOCALES

bp = Blueprint('references', __name__)


def _equipment_available(exercise_equipment, profile_equipment_set):
    """Return True if the exercise's equipment requirement is satisfied by the profile.

    Empty requirement → always True (bodyweight / no restriction).
    '|' separates alternatives (OR); ',' separates co-requirements within an alternative (AND).
    Example: 'barbell,squat_rack|smith_machine' → (barbell AND squat_rack) OR smith_machine.
    """
    if not exercise_equipment:
        return True
    for alternative in exercise_equipment.split('|'):
        required = [t.strip() for t in alternative.split(',') if t.strip()]
        if all(t in profile_equipment_set for t in required):
            return True
    return False


@bp.route('/exercises')
def exercises():
    db = get_db()
    locale_filter = request.args.getlist('locale')

    rows = db.execute('SELECT * FROM exercise_inventory ORDER BY discipline, exercise').fetchall()

    # Load saved equipment profiles for any selected locales
    profiles_active = {}
    profile_equipment = set()
    if locale_filter:
        placeholders = ','.join('?' * len(locale_filter))
        profile_rows = db.execute(
            f'SELECT * FROM locale_profiles WHERE locale IN ({placeholders})',
            locale_filter
        ).fetchall()
        for p in profile_rows:
            profiles_active[p['locale']] = p
            for tag in (p['equipment'] or '').split(','):
                if tag:
                    profile_equipment.add(tag)

    if locale_filter:
        filtered = []
        for r in rows:
            # Must be tagged for at least one selected locale
            ex_locales = set((r['where_available'] or '').split(','))
            if not any(loc in ex_locales for loc in locale_filter):
                continue
            # If any selected locale has a saved profile, apply equipment filter
            if profiles_active and not _equipment_available(r['equipment'], profile_equipment):
                continue
            filtered.append(r)
        rows = filtered

    return render_template('references/exercises.html', rows=rows,
                           locale_filter=locale_filter, locales=LOCALES,
                           profiles_active=profiles_active)


@bp.route('/rx/setup/<exercise>', methods=['GET'])
def rx_setup(exercise):
    """Redirect to rx edit for setup."""
    from flask import redirect, url_for
    db = get_db()
    row = db.execute('SELECT id FROM current_rx WHERE exercise=?', (exercise,)).fetchone()
    if row:
        return redirect(url_for('rx.edit_entry', entry_id=row['id']))
    return redirect(url_for('rx.list_entries'))
