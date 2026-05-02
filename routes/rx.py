from flask import Blueprint, render_template, request, redirect, url_for, flash
from database import get_db
from calculations import project_next_from_current

bp = Blueprint('rx', __name__)


@bp.route('/rx')
def list_entries():
    db = get_db()
    discipline = request.args.get('discipline', '')
    status = request.args.get('status', '')
    locale_filter = request.args.get('locale', '')

    query = '''SELECT cr.*, ei.video_reference, ei.where_available,
                      ei.recovery_cost as ei_recovery_cost,
                      ei.suggested_volume as ei_suggested_volume
               FROM current_rx cr
               LEFT JOIN exercise_inventory ei ON ei.exercise = cr.exercise
               WHERE 1=1'''
    params = []
    if discipline:
        query += ' AND cr.discipline=?'
        params.append(discipline)
    if status:
        query += ' AND cr.last_outcome LIKE ?'
        params.append(f'%{status}%')
    if locale_filter:
        query += ' AND ei.where_available LIKE ?'
        params.append(f'%{locale_filter}%')
    query += ' ORDER BY cr.discipline, cr.exercise'
    entries = db.execute(query, params).fetchall()

    # Exercises in inventory but with no current_rx entry
    inv_query = '''SELECT ei.* FROM exercise_inventory ei
                   WHERE NOT EXISTS (SELECT 1 FROM current_rx cr WHERE cr.exercise = ei.exercise)'''
    inv_params = []
    if locale_filter:
        inv_query += ' AND ei.where_available LIKE ?'
        inv_params.append(f'%{locale_filter}%')
    inv_query += ' ORDER BY ei.discipline, ei.exercise'
    inventory_only = db.execute(inv_query, inv_params).fetchall()

    locales = db.execute('SELECT locale FROM locale_profiles ORDER BY locale').fetchall()

    return render_template('rx/list.html', entries=entries,
                           inventory_only=inventory_only,
                           discipline=discipline, status=status,
                           locale_filter=locale_filter, locales=locales)


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
        cur_sets = num(f.get('current_sets'), int)
        cur_reps = num(f.get('current_reps'), int)
        cur_weight = num(f.get('current_weight'))
        cur_duration = num(f.get('current_duration'), int)
        weight_increment = num(f.get('weight_increment'))

        # Re-derive next_* from the manually-edited current_*. Without this,
        # the prescription stays stale at whatever was last computed from a
        # logged session, which contradicts "any update to current should
        # also be used to calculate next."
        nxt = project_next_from_current(
            cur_sets, cur_reps, cur_weight, cur_duration,
            entry['movement_pattern'], weight_increment=weight_increment,
        )

        db.execute('''UPDATE current_rx SET
            current_sets=?, current_reps=?, current_weight=?, current_duration=?,
            inventory_sugg_volume=?, weight_increment=?, consecutive_failures=?,
            next_sets=?, next_reps=?, next_weight=?, next_duration=?,
            rx_source=? WHERE id=?''',
            (cur_sets, cur_reps, cur_weight, cur_duration,
             f.get('inventory_sugg_volume'), weight_increment,
             0 if f.get('reset_failures') else num(f.get('consecutive_failures'), int),
             nxt['next_sets'], nxt['next_reps'], nxt['next_weight'], nxt['next_duration'],
             'Manual override', entry_id))
        db.commit()
        flash('Rx updated.', 'success')
        return redirect(url_for('rx.list_entries'))
    return render_template('rx/form.html', entry=entry)
