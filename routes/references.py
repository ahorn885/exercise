from flask import Blueprint, render_template, request
from database import get_db
import locations
from routes.auth import current_user_id
from routes.locales import athlete_locale_choices
from layer0_catalog import strength_catalog

bp = Blueprint('references', __name__)


@bp.route('/exercises')
def exercises():
    db = get_db()
    uid = current_user_id()
    locale_choices = athlete_locale_choices(db, uid)
    valid_slugs = {c['slug'] for c in locale_choices}
    locale_filter = [s for s in request.args.getlist('locale') if s in valid_slugs]

    # Single canonical catalog: layer0 strength exercises (the v1
    # exercise_inventory table is retired). Ordered by movement-pattern group
    # then name; where_available is derived from required equipment.
    rows = sorted(strength_catalog(db),
                  key=lambda r: ((r['movement_pattern'] or ''), (r['exercise'] or '')))

    profiles_active = {}
    equipment_counts = {}

    if locale_filter:
        placeholders = ','.join('?' * len(locale_filter))

        # Profile metadata (notes, updated_at) for display banner
        for p in db.execute(
            f'SELECT * FROM locale_profiles WHERE locale IN ({placeholders}) AND user_id = ?',
            list(locale_filter) + [uid]
        ).fetchall():
            profiles_active[p['locale']] = p

        # Per-locale equipment counts via the authoritative resolver (layer0
        # canonical names). Track 1 retired the legacy locale_equipment join;
        # the exercise-availability *filter* below is the public int-id
        # vocabulary (exercise_equipment) which can't be matched against the
        # canonical pool until the catalog migrates to layer0 (Track 3) — so
        # only the where_available bucket filter applies until then.
        for loc in locale_filter:
            equipment_counts[loc] = len(locations.locale_effective_tags(db, uid, loc))

    if locale_filter:
        # Map each selected athlete-slug → Layer 0 where_available bucket via
        # the choice list (legacy slug == bucket; custom locales come via
        # CATEGORY_TO_WHERE_AVAILABLE_BUCKET — outdoor_park resolves to '' and
        # contributes nothing, matching no exercises until the park-tags
        # follow-up lands).
        selected_buckets = {c['bucket'] for c in locale_choices
                            if c['slug'] in locale_filter and c['bucket']}
        rows = [
            r for r in rows
            if selected_buckets & set((r['where_available'] or '').split(','))
        ]

    return render_template('references/exercises.html', rows=rows,
                           locale_filter=locale_filter, locales=locale_choices,
                           profiles_active=profiles_active,
                           equipment_counts=equipment_counts)


@bp.route('/rx/setup/<exercise>', methods=['GET'])
def rx_setup(exercise):
    """Redirect to rx edit for setup."""
    from flask import redirect, url_for
    db = get_db()
    row = db.execute(
        'SELECT id FROM current_rx WHERE exercise=? AND user_id=?',
        (exercise, current_user_id())
    ).fetchone()
    if row:
        return redirect(url_for('rx.edit_entry', entry_id=row['id']))
    return redirect(url_for('rx.list_entries'))
