from flask import Blueprint, render_template, request, redirect, url_for, flash
from database import get_db
from init_db import EQUIPMENT_CATEGORIES
from routes.auth import current_user_id

bp = Blueprint('locales', __name__)

LOCALES = ['home', 'hotel', 'partner', 'airport']

# Flat set of all valid tag keys for input validation
ALL_TAGS = {tag for _, items in EQUIPMENT_CATEGORIES for tag, _ in items}


@bp.route('/locales')
def list_profiles():
    db = get_db()
    uid = current_user_id()
    # locale_profiles is parent-scoped; locale_equipment is parent-JOIN scoped
    # via locale_profiles. Session 3 makes the locale PK composite (user_id, locale)
    # so users can have independent locales — until then, the global PK means a
    # user 2 can't claim a locale name user 1 already owns.
    profiles = {
        r['locale']: r for r in db.execute(
            'SELECT * FROM locale_profiles WHERE user_id = ?', (uid,)
        ).fetchall()
    }
    tags_by_locale = {}
    for row in db.execute(
        '''SELECT le.locale, ei.tag, ei.label
           FROM locale_equipment le
           JOIN equipment_items ei ON ei.id = le.equipment_id
           WHERE le.user_id = ?
           ORDER BY le.locale, ei.category, ei.label''',
        (uid,)
    ).fetchall():
        tags_by_locale.setdefault(row['locale'], []).append(
            {'tag': row['tag'], 'label': row['label']}
        )
    counts = {loc: len(items) for loc, items in tags_by_locale.items()}
    return render_template('locales/list.html', locales=LOCALES, profiles=profiles,
                           equipment_categories=EQUIPMENT_CATEGORIES,
                           tags_by_locale=tags_by_locale, counts=counts)


@bp.route('/locales/<locale>/edit', methods=['GET', 'POST'])
def edit_profile(locale):
    if locale not in LOCALES:
        flash('Unknown location.', 'danger')
        return redirect(url_for('locales.list_profiles'))
    db = get_db()
    uid = current_user_id()
    if request.method == 'POST':
        selected_tags = [t for t in request.form.getlist('equipment') if t in ALL_TAGS]
        notes = request.form.get('notes', '').strip()
        city = request.form.get('city', '').strip()
        # Resolve tags to equipment_ids (shared catalog)
        if selected_tags:
            placeholders = ','.join('?' * len(selected_tags))
            eq_rows = db.execute(
                f'SELECT id, tag FROM equipment_items WHERE tag IN ({placeholders})',
                selected_tags
            ).fetchall()
            tag_to_id = {r['tag']: r['id'] for r in eq_rows}
        else:
            tag_to_id = {}
        # Upsert locale_profiles first — locale_equipment has an FK on this
        # table. PK is composite (user_id, locale) since Session 3.
        # CURRENT_TIMESTAMP is portable; datetime('now') is SQLite-only and
        # blew up the UPSERT on Postgres. ON CONFLICT works on both backends.
        db.execute(
            '''INSERT INTO locale_profiles (user_id, locale, notes, city, updated_at)
               VALUES (?, ?, ?, ?, CURRENT_TIMESTAMP)
               ON CONFLICT(user_id, locale) DO UPDATE SET
                 notes=excluded.notes,
                 city=excluded.city,
                 updated_at=excluded.updated_at''',
            (uid, locale, notes, city)
        )
        # Replace locale_equipment rows atomically (scoped per-user)
        db.execute(
            'DELETE FROM locale_equipment WHERE user_id = ? AND locale = ?',
            (uid, locale)
        )
        for tag in selected_tags:
            eq_id = tag_to_id.get(tag)
            if eq_id:
                db.execute(
                    'INSERT INTO locale_equipment (user_id, locale, equipment_id) VALUES (?, ?, ?)',
                    (uid, locale, eq_id)
                )
        db.commit()
        flash(f'{locale.title()} profile saved ({len(selected_tags)} items).', 'success')
        return redirect(url_for('locales.list_profiles'))
    # GET — load active equipment from locale_equipment (parent-JOIN scoped)
    profile = db.execute(
        'SELECT * FROM locale_profiles WHERE locale=? AND user_id=?',
        (locale, uid)
    ).fetchone()
    active_rows = db.execute(
        '''SELECT ei.tag FROM locale_equipment le
           JOIN equipment_items ei ON ei.id = le.equipment_id
           WHERE le.user_id = ? AND le.locale = ?''',
        (uid, locale)
    ).fetchall()
    active = {row['tag'] for row in active_rows}
    return render_template('locales/form.html', locale=locale,
                           equipment_categories=EQUIPMENT_CATEGORIES,
                           active=active,
                           notes=profile['notes'] if profile else '',
                           city=profile['city'] if profile and profile['city'] else '')
