from flask import Blueprint, render_template, request, redirect, url_for, flash
from database import get_db
from init_db import EQUIPMENT_CATEGORIES

bp = Blueprint('locales', __name__)

LOCALES = ['home', 'hotel', 'partner', 'airport']

# Flat set of all valid tag keys for input validation
ALL_TAGS = {tag for _, items in EQUIPMENT_CATEGORIES for tag, _ in items}


@bp.route('/locales')
def list_profiles():
    db = get_db()
    profiles = {r['locale']: r for r in db.execute('SELECT * FROM locale_profiles').fetchall()}
    tags_by_locale = {}
    for row in db.execute(
        '''SELECT le.locale, ei.tag, ei.label
           FROM locale_equipment le JOIN equipment_items ei ON ei.id = le.equipment_id
           ORDER BY le.locale, ei.category, ei.label'''
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
        flash('Unknown locale.', 'danger')
        return redirect(url_for('locales.list_profiles'))
    db = get_db()
    if request.method == 'POST':
        selected_tags = [t for t in request.form.getlist('equipment') if t in ALL_TAGS]
        notes = request.form.get('notes', '').strip()
        # Resolve tags to equipment_ids
        if selected_tags:
            placeholders = ','.join('?' * len(selected_tags))
            eq_rows = db.execute(
                f'SELECT id, tag FROM equipment_items WHERE tag IN ({placeholders})',
                selected_tags
            ).fetchall()
            tag_to_id = {r['tag']: r['id'] for r in eq_rows}
        else:
            tag_to_id = {}
        # Replace locale_equipment rows atomically
        db.execute('DELETE FROM locale_equipment WHERE locale = ?', (locale,))
        for tag in selected_tags:
            eq_id = tag_to_id.get(tag)
            if eq_id:
                db.execute(
                    'INSERT INTO locale_equipment (locale, equipment_id) VALUES (?, ?)',
                    (locale, eq_id)
                )
        # UPSERT locale_profiles for notes/updated_at only (equipment column intentionally omitted)
        db.execute(
            '''INSERT INTO locale_profiles (locale, notes, updated_at)
               VALUES (?, ?, datetime('now'))
               ON CONFLICT(locale) DO UPDATE SET
                 notes=excluded.notes,
                 updated_at=excluded.updated_at''',
            (locale, notes)
        )
        db.commit()
        flash(f'{locale.title()} profile saved ({len(selected_tags)} items).', 'success')
        return redirect(url_for('locales.list_profiles'))
    # GET — load active equipment from locale_equipment
    profile = db.execute('SELECT * FROM locale_profiles WHERE locale=?', (locale,)).fetchone()
    active_rows = db.execute(
        '''SELECT ei.tag FROM locale_equipment le
           JOIN equipment_items ei ON ei.id = le.equipment_id
           WHERE le.locale = ?''',
        (locale,)
    ).fetchall()
    active = {row['tag'] for row in active_rows}
    return render_template('locales/form.html', locale=locale,
                           equipment_categories=EQUIPMENT_CATEGORIES,
                           active=active,
                           notes=profile['notes'] if profile else '')
