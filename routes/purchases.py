"""Recommended purchases — shared catalog + per-user wanted/owned/passed state.

The catalog (`purchase_recommendations`) is seeded by init_db on cold start
and updated via UPSERT on slug, so cost/copy edits propagate without
disturbing per-user state. Per-user state lives in
`user_purchase_recommendations` keyed on (user_id, purchase_id).

Each recommendation is bound to an `equipment_items.tag` so "exercises this
unlocks" is derived live from `exercise_equipment` rather than stored.
Items the user already owns in any locale (via `locale_equipment`) get a
hint badge — the explicit status toggle is independent so the user can
override (e.g. mark something "passed" even if a stray instance shows up
in a hotel-gym locale).
"""
from flask import Blueprint, render_template, request, redirect, url_for, flash
from database import get_db
from routes.auth import current_user_id

bp = Blueprint('purchases', __name__)

VALID_STATUSES = {'wanted', 'owned', 'passed'}
PRIORITY_ORDER = {'high': 0, 'medium': 1, 'low': 2}


@bp.route('/purchases')
def list_purchases():
    db = get_db()
    uid = current_user_id()

    # One pass over the catalog joined with per-user state. LEFT JOIN keeps
    # rows the user hasn't touched (status NULL).
    rows = db.execute(
        '''SELECT pr.id, pr.slug, pr.label, pr.equipment_id,
                  pr.est_cost_low, pr.est_cost_high, pr.priority, pr.rationale,
                  pr.sort_order, ei.tag AS equipment_tag, ei.label AS equipment_label,
                  upr.status, upr.user_notes
           FROM purchase_recommendations pr
           LEFT JOIN equipment_items ei ON ei.id = pr.equipment_id
           LEFT JOIN user_purchase_recommendations upr
             ON upr.purchase_id = pr.id AND upr.user_id = ?
           WHERE pr.active = 1
           ORDER BY pr.sort_order, pr.id''',
        (uid,)
    ).fetchall()

    # Set of equipment_ids this user owns somewhere (any locale). Drives
    # the "you already have this" hint independent of explicit status.
    owned_equipment_ids = {
        r['equipment_id'] for r in db.execute(
            'SELECT DISTINCT equipment_id FROM locale_equipment WHERE user_id = ?',
            (uid,)
        ).fetchall()
    }

    # Impacted-exercise counts in one query, then attach per row.
    impact_counts = {
        r['equipment_id']: r['cnt'] for r in db.execute(
            '''SELECT equipment_id, COUNT(DISTINCT exercise_id) AS cnt
               FROM exercise_equipment
               GROUP BY equipment_id'''
        ).fetchall()
    }

    grouped = {'high': [], 'medium': [], 'low': []}
    counts_by_status = {'wanted': 0, 'owned': 0, 'passed': 0, 'none': 0}
    for r in rows:
        d = dict(r)
        d['impacted_count'] = impact_counts.get(d['equipment_id'], 0)
        d['in_locale'] = d['equipment_id'] in owned_equipment_ids
        status = d['status'] or 'none'
        counts_by_status[status] = counts_by_status.get(status, 0) + 1
        bucket = d['priority'] if d['priority'] in grouped else 'medium'
        grouped[bucket].append(d)

    return render_template('purchases/list.html',
                           grouped=grouped,
                           counts_by_status=counts_by_status,
                           valid_statuses=sorted(VALID_STATUSES))


@bp.route('/purchases/<int:purchase_id>')
def detail(purchase_id):
    """Show the exercises a single recommendation unlocks, plus state."""
    db = get_db()
    uid = current_user_id()
    pr = db.execute(
        '''SELECT pr.*, ei.tag AS equipment_tag, ei.label AS equipment_label,
                  upr.status, upr.user_notes
           FROM purchase_recommendations pr
           LEFT JOIN equipment_items ei ON ei.id = pr.equipment_id
           LEFT JOIN user_purchase_recommendations upr
             ON upr.purchase_id = pr.id AND upr.user_id = ?
           WHERE pr.id = ?''',
        (uid, purchase_id)
    ).fetchone()
    if not pr or not pr['active']:
        flash('Recommendation not found.', 'danger')
        return redirect(url_for('purchases.list_purchases'))

    impacted = []
    if pr['equipment_id']:
        impacted = db.execute(
            '''SELECT DISTINCT ei.id, ei.exercise, ei.discipline, ei.movement_pattern
               FROM exercise_equipment ee
               JOIN exercise_inventory ei ON ei.id = ee.exercise_id
               WHERE ee.equipment_id = ?
               ORDER BY ei.discipline, ei.exercise''',
            (pr['equipment_id'],)
        ).fetchall()

    return render_template('purchases/detail.html', pr=dict(pr), impacted=impacted,
                           valid_statuses=sorted(VALID_STATUSES))


@bp.route('/purchases/<int:purchase_id>/status', methods=['POST'])
def set_status(purchase_id):
    db = get_db()
    uid = current_user_id()

    # Confirm the recommendation exists and is active before writing.
    pr = db.execute(
        'SELECT id FROM purchase_recommendations WHERE id = ? AND active = 1',
        (purchase_id,)
    ).fetchone()
    if not pr:
        flash('Recommendation not found.', 'danger')
        return redirect(url_for('purchases.list_purchases'))

    raw = (request.form.get('status') or '').strip()
    notes = (request.form.get('user_notes') or '').strip() or None

    if raw == '' or raw == 'clear':
        # Clear = revert to "no opinion yet"
        db.execute(
            'DELETE FROM user_purchase_recommendations '
            'WHERE user_id = ? AND purchase_id = ?',
            (uid, purchase_id)
        )
    elif raw in VALID_STATUSES:
        # UPSERT — both backends support ON CONFLICT.
        db.execute(
            '''INSERT INTO user_purchase_recommendations
               (user_id, purchase_id, status, user_notes)
               VALUES (?,?,?,?)
               ON CONFLICT(user_id, purchase_id) DO UPDATE SET
                 status=excluded.status, user_notes=excluded.user_notes,
                 updated_at=CURRENT_TIMESTAMP''',
            (uid, purchase_id, raw, notes)
        )
    else:
        flash('Unknown status.', 'danger')
        return redirect(url_for('purchases.list_purchases'))

    db.commit()
    # Honour the redirect form field so detail-page submits return there.
    target = request.form.get('redirect_to')
    if target == 'detail':
        return redirect(url_for('purchases.detail', purchase_id=purchase_id))
    return redirect(url_for('purchases.list_purchases'))
