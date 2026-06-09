from flask import Blueprint, render_template, request, redirect, url_for, flash
from database import get_db
from routes.auth import current_user_id
from athlete import get_athlete_profile
from units import (
    normalize_unit_preference, display_weight, entered_weight_to_kg,
    weight_unit_label,
)

bp = Blueprint('body', __name__)


def _unit_pref(db, uid):
    profile = get_athlete_profile(db, uid) or {}
    return normalize_unit_preference(profile.get('unit_preference'))


def _decorate_entries(entries, unit_pref):
    """Return entries with `weight_display` (in athlete's unit) + the unit label."""
    out = []
    for e in entries:
        row = dict(e)
        row['weight_display'] = display_weight(row.get('weight_kg'), unit_pref)
        out.append(row)
    return out


@bp.route('/body')
def list_entries():
    db = get_db()
    uid = current_user_id()
    rows = db.execute(
        'SELECT * FROM body_metrics WHERE user_id = ? ORDER BY date DESC',
        (uid,)
    ).fetchall()
    unit_pref = _unit_pref(db, uid)
    return render_template(
        'body/list.html',
        entries=_decorate_entries(rows, unit_pref),
        weight_unit_label=weight_unit_label(unit_pref),
    )


@bp.route('/body/new', methods=['GET', 'POST'])
def new_entry():
    db = get_db()
    uid = current_user_id()
    if request.method == 'POST':
        _save(db, None)
        flash('Body metrics logged.', 'success')
        return redirect(url_for('body.list_entries'))
    unit_pref = _unit_pref(db, uid)
    return render_template(
        'body/form.html', entry=None,
        weight_unit_label=weight_unit_label(unit_pref),
    )


@bp.route('/body/<int:entry_id>/edit', methods=['GET', 'POST'])
def edit_entry(entry_id):
    db = get_db()
    uid = current_user_id()
    entry = db.execute(
        'SELECT * FROM body_metrics WHERE id=? AND user_id=?',
        (entry_id, uid)
    ).fetchone()
    if not entry:
        flash('Entry not found.', 'danger')
        return redirect(url_for('body.list_entries'))
    if request.method == 'POST':
        _save(db, entry_id)
        flash('Entry updated.', 'success')
        return redirect(url_for('body.list_entries'))
    unit_pref = _unit_pref(db, uid)
    entry_dict = dict(entry)
    entry_dict['weight_display'] = display_weight(entry_dict.get('weight_kg'), unit_pref)
    return render_template(
        'body/form.html', entry=entry_dict,
        weight_unit_label=weight_unit_label(unit_pref),
    )


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
    # #469 — accept weight in the athlete's display unit and convert to kg
    # canonical at the boundary.
    unit_pref = _unit_pref(db, uid)
    weight_kg = entered_weight_to_kg(num(f.get('weight')), unit_pref)
    vals = (f.get('date'), weight_kg, num(f.get('body_fat_pct')),
            num(f.get('vo2_max')), num(f.get('resting_hr'), int), f.get('notes'))
    if entry_id:
        db.execute('UPDATE body_metrics SET date=?,weight_kg=?,body_fat_pct=?,vo2_max=?,resting_hr=?,notes=? '
                   'WHERE id=? AND user_id=?',
                   vals + (entry_id, uid))
    else:
        db.execute('''INSERT INTO body_metrics (date,weight_kg,body_fat_pct,vo2_max,resting_hr,notes,user_id)
            VALUES (?,?,?,?,?,?,?)
            ON CONFLICT (user_id, date) DO UPDATE SET
            weight_kg=EXCLUDED.weight_kg, body_fat_pct=EXCLUDED.body_fat_pct,
            vo2_max=EXCLUDED.vo2_max, resting_hr=EXCLUDED.resting_hr, notes=EXCLUDED.notes''', vals + (uid,))
    db.commit()
