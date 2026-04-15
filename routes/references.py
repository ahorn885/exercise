from collections import defaultdict
from flask import Blueprint, render_template, request
from database import get_db
from routes.locales import LOCALES

bp = Blueprint('references', __name__)


def _exercise_available(exercise_id, ex_eq_map, profile_equipment_ids):
    """Return True if the exercise requires no equipment, or any option_group is fully covered.

    ex_eq_map: {exercise_id: [(equipment_id, option_group), ...]}
    option_group rows sharing the same group number are all required (AND);
    the exercise is available if ANY group is fully satisfied (OR).
    """
    reqs = ex_eq_map.get(exercise_id)
    if not reqs:
        return True  # bodyweight / no equipment rows
    groups = defaultdict(set)
    for eq_id, grp in reqs:
        groups[grp].add(eq_id)
    return any(grp_ids.issubset(profile_equipment_ids) for grp_ids in groups.values())


@bp.route('/exercises')
def exercises():
    db = get_db()
    locale_filter = request.args.getlist('locale')

    rows = db.execute('SELECT * FROM exercise_inventory ORDER BY discipline, exercise').fetchall()

    profiles_active = {}
    profile_equipment_ids = set()
    ex_eq_map = {}
    equipment_counts = {}

    if locale_filter:
        placeholders = ','.join('?' * len(locale_filter))

        # Profile metadata (notes, updated_at) for display banner
        for p in db.execute(
            f'SELECT * FROM locale_profiles WHERE locale IN ({placeholders})', locale_filter
        ).fetchall():
            profiles_active[p['locale']] = p

        # Union of equipment_ids across all selected locales
        for row in db.execute(
            f'SELECT DISTINCT equipment_id FROM locale_equipment WHERE locale IN ({placeholders})',
            locale_filter
        ).fetchall():
            profile_equipment_ids.add(row['equipment_id'])

        # Per-locale item counts for display
        for row in db.execute(
            f'SELECT locale, COUNT(*) as cnt FROM locale_equipment '
            f'WHERE locale IN ({placeholders}) GROUP BY locale',
            locale_filter
        ).fetchall():
            equipment_counts[row['locale']] = row['cnt']

        # Load full exercise_equipment map for availability check
        for row in db.execute(
            'SELECT exercise_id, equipment_id, option_group FROM exercise_equipment'
        ).fetchall():
            ex_eq_map.setdefault(row['exercise_id'], []).append(
                (row['equipment_id'], row['option_group'])
            )

    if locale_filter:
        filtered = []
        for r in rows:
            # Must be tagged for at least one selected locale
            ex_locales = set((r['where_available'] or '').split(','))
            if not any(loc in ex_locales for loc in locale_filter):
                continue
            # If any selected locale has a saved profile, apply equipment filter
            if profiles_active and not _exercise_available(r['id'], ex_eq_map, profile_equipment_ids):
                continue
            filtered.append(r)
        rows = filtered

    return render_template('references/exercises.html', rows=rows,
                           locale_filter=locale_filter, locales=LOCALES,
                           profiles_active=profiles_active,
                           equipment_counts=equipment_counts)


@bp.route('/rx/setup/<exercise>', methods=['GET'])
def rx_setup(exercise):
    """Redirect to rx edit for setup."""
    from flask import redirect, url_for
    db = get_db()
    row = db.execute('SELECT id FROM current_rx WHERE exercise=?', (exercise,)).fetchone()
    if row:
        return redirect(url_for('rx.edit_entry', entry_id=row['id']))
    return redirect(url_for('rx.list_entries'))
