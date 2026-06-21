from flask import Blueprint, render_template, request, redirect, url_for, flash
from database import get_db
from calculations import project_next_from_current, compute_deload_baseline
from rx_engine import DELOAD_THRESHOLD
from routes.auth import current_user_id
from units import (
    normalize_unit_preference, display_weight, entered_weight_to_kg,
    weight_unit_label,
)
from athlete import get_athlete_profile
from layer0_catalog import strength_catalog_by_exid

bp = Blueprint('rx', __name__)

# The per-user seed (init_db._seed_current_rx_for_user) stamps brand-new rows
# with this rx_source and every dimension NULL — the single "genuinely
# unconfigured" sentinel. A logged session ('From Training Log'), a manual edit
# ('Manual override'), or a deload ('Auto-deload') all overwrite rx_source and
# fill at least one dimension.
SEED_RX_SOURCE = 'Needs initial setup'

# The prescription dimensions that make a row a real capacity record.
_RX_DIMENSIONS = ('current_sets', 'current_reps', 'current_weight', 'current_duration')


def _unit_pref(db, uid):
    profile = get_athlete_profile(db, uid) or {}
    return normalize_unit_preference(profile.get('unit_preference'))


def _decorate_entry(entry, unit_pref):
    row = dict(entry)
    for col in ('current_weight', 'next_weight', 'weight_increment'):
        v = display_weight(row.get(col), unit_pref)
        row[col + '_display'] = round(v, 1) if v is not None else None
    # #693 — "needs setup" must reflect whether the exercise has been set up at
    # all (a capacity record from a logged session, a manual edit, or a deload),
    # not merely whether current_sets is populated. Keying off current_sets alone
    # mislabeled capacity/edited rows that carry only a weight or duration as
    # "needs setup". Reserve the label for a still-pristine seed row.
    row['needs_setup'] = (
        (row.get('rx_source') or SEED_RX_SOURCE) == SEED_RX_SOURCE
        and not any(row.get(col) for col in _RX_DIMENSIONS)
    )
    return row


@bp.route('/rx')
def list_entries():
    db = get_db()
    uid = current_user_id()
    pattern = request.args.get('pattern', '')
    status = request.args.get('status', '')
    locale_filter = request.args.get('locale', '')

    # Single canonical catalog: layer0, keyed by EX-id (the id current_rx and
    # plan-gen both carry). Replaces the v1 `exercise_inventory` display read +
    # the #814 name↔EX-id bridge — one source of truth, no name drift. Display
    # is organized by the layer0-native movement-pattern group + exercise_type;
    # the v1 `discipline` (a cardio concept) / `type` (Staple/Novel) /
    # `suggested_volume` are dropped, and `where_available` is derived from gear.
    cat_by_exid = strength_catalog_by_exid(db)

    # current_rx rows for this user. The status filter keys off cr alone; the
    # pattern and locale filters are applied AFTER enrichment, since a row's
    # movement-pattern group + where_available come from its layer0 catalog row.
    query = 'SELECT * FROM current_rx WHERE user_id = ?'
    params = [uid]
    if status:
        query += ' AND last_outcome LIKE ?'
        params.append(f'%{status}%')
    rows = db.execute(query, params).fetchall()

    def _enrich(row):
        e = dict(row)
        cat = cat_by_exid.get(e.get('layer0_exercise_id'))
        if cat:
            e['exercise_type'] = cat['exercise_type']
            e['movement_pattern'] = e.get('movement_pattern') or cat['movement_pattern']
            e['where_available'] = cat['where_available']
        else:
            # bucket-3 / un-resolved row: no layer0 home, keep its stored values.
            e['exercise_type'] = None
            e['where_available'] = None
        return e

    entries = [_enrich(r) for r in rows]
    if pattern:
        entries = [e for e in entries if e.get('movement_pattern') == pattern]
    if locale_filter:
        entries = [e for e in entries
                   if locale_filter in (e.get('where_available') or '')]
    entries.sort(key=lambda e: ((e.get('movement_pattern') or ''), (e.get('exercise') or '')))

    # Browse: layer0 strength exercises with no current Rx for this user,
    # excluded by EX-id (a prescribed lift never double-lists here).
    prescribed_exids = {r['layer0_exercise_id'] for r in rows if r['layer0_exercise_id']}
    inventory_only = [
        c for c in cat_by_exid.values()
        if c['layer0_exercise_id'] not in prescribed_exids
    ]
    if locale_filter:
        inventory_only = [c for c in inventory_only
                          if locale_filter in (c['where_available'] or '')]
    inventory_only.sort(key=lambda c: ((c['movement_pattern'] or ''), (c['exercise'] or '')))
    # Distinct movement-pattern groups present, for the filter dropdown.
    patterns = sorted({c['movement_pattern'] for c in cat_by_exid.values() if c['movement_pattern']})

    locales = db.execute(
        'SELECT locale FROM locale_profiles WHERE user_id = ? ORDER BY locale',
        (uid,)
    ).fetchall()

    deload_pending = [
        e for e in entries
        if (e['sessions_since_progress'] or 0) >= DELOAD_THRESHOLD
    ]

    unit_pref = _unit_pref(db, uid)
    entries_view = [_decorate_entry(e, unit_pref) for e in entries]
    deload_pending_view = [_decorate_entry(e, unit_pref) for e in deload_pending]

    return render_template('rx/list.html', entries=entries_view,
                           inventory_only=inventory_only,
                           pattern=pattern, patterns=patterns, status=status,
                           locale_filter=locale_filter, locales=locales,
                           deload_pending=deload_pending_view,
                           deload_threshold=DELOAD_THRESHOLD,
                           weight_unit_label=weight_unit_label(unit_pref))


@bp.route('/rx/<int:entry_id>/deload', methods=['POST'])
def deload_entry(entry_id):
    """One-click 10% deload: drop the primary baseline dimension, re-project
    next_*, and reset both plateau and failure counters."""
    db = get_db()
    uid = current_user_id()
    entry = db.execute(
        'SELECT * FROM current_rx WHERE id=? AND user_id=?', (entry_id, uid)
    ).fetchone()
    if not entry:
        flash('Entry not found.', 'danger')
        return redirect(url_for('rx.list_entries'))

    deloaded = compute_deload_baseline(
        entry['current_sets'], entry['current_reps'],
        entry['current_weight'], entry['current_duration'],
        entry['movement_pattern'],
        weight_increment=entry['weight_increment'],
    )
    nxt = project_next_from_current(
        deloaded['sets'], deloaded['reps'], deloaded['weight'], deloaded['duration'],
        entry['movement_pattern'], weight_increment=entry['weight_increment'],
    )

    db.execute('''UPDATE current_rx SET
        current_sets=?, current_reps=?, current_weight=?, current_duration=?,
        next_sets=?, next_reps=?, next_weight=?, next_duration=?,
        consecutive_failures=0, sessions_since_progress=0,
        rx_source=?
        WHERE id=? AND user_id=?''',
        (deloaded['sets'], deloaded['reps'], deloaded['weight'], deloaded['duration'],
         nxt['next_sets'], nxt['next_reps'], nxt['next_weight'], nxt['next_duration'],
         'Auto-deload', entry_id, uid))
    db.commit()

    # Build a human-readable note about what changed. Storage is canonical
    # kg; the flash renders in the athlete's display unit.
    from units import format_weight as _fmt_wt
    _unit = _unit_pref(db, uid)
    if entry['current_weight'] and deloaded['weight'] != entry['current_weight']:
        delta = f"{_fmt_wt(entry['current_weight'], _unit)} → {_fmt_wt(deloaded['weight'], _unit)}"
    elif entry['current_duration'] and deloaded['duration'] != entry['current_duration']:
        delta = f"{entry['current_duration']} → {deloaded['duration']} sec"
    elif entry['current_reps'] and deloaded['reps'] != entry['current_reps']:
        delta = f"{entry['current_reps']} → {deloaded['reps']} reps"
    elif entry['current_sets'] and deloaded['sets'] != entry['current_sets']:
        delta = f"{entry['current_sets']} → {deloaded['sets']} sets"
    else:
        delta = 'no change applied'
    flash(f"{entry['exercise']} deloaded ({delta}). Plateau counter reset.", 'success')
    return redirect(url_for('rx.list_entries'))


@bp.route('/rx/<int:entry_id>/edit', methods=['GET', 'POST'])
def edit_entry(entry_id):
    db = get_db()
    uid = current_user_id()
    entry = db.execute(
        'SELECT * FROM current_rx WHERE id=? AND user_id=?', (entry_id, uid)
    ).fetchone()
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
        # #469 — weight inputs arrive in the athlete's display unit; convert
        # to canonical kg before storing.
        unit_pref = _unit_pref(db, uid)
        cur_weight = entered_weight_to_kg(num(f.get('current_weight')), unit_pref)
        cur_duration = num(f.get('current_duration'), int)
        weight_increment = entered_weight_to_kg(num(f.get('weight_increment')), unit_pref)

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
            sessions_since_progress=?,
            next_sets=?, next_reps=?, next_weight=?, next_duration=?,
            rx_source=? WHERE id=? AND user_id=?''',
            (cur_sets, cur_reps, cur_weight, cur_duration,
             f.get('inventory_sugg_volume'), weight_increment,
             0 if f.get('reset_failures') else num(f.get('consecutive_failures'), int),
             0 if f.get('reset_plateau') else (entry['sessions_since_progress'] or 0),
             nxt['next_sets'], nxt['next_reps'], nxt['next_weight'], nxt['next_duration'],
             'Manual override', entry_id, uid))
        db.commit()
        flash('Rx updated.', 'success')
        return redirect(url_for('rx.list_entries'))
    unit_pref = _unit_pref(db, uid)
    return render_template('rx/form.html',
                           entry=_decorate_entry(entry, unit_pref),
                           weight_unit_label=weight_unit_label(unit_pref))
