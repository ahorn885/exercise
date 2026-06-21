"""Recommended purchases — shared catalog + per-user wanted/owned/passed state.

The catalog (`purchase_recommendations`) is seeded by init_db on cold start
and updated via UPSERT on slug, so cost/copy edits propagate without
disturbing per-user state. Per-user state lives in
`user_purchase_recommendations` keyed on (user_id, purchase_id).

Each recommendation is bound to an `equipment_items.tag`; "exercises this
unlocks" is derived live from the canonical layer0 catalog (count active
`layer0.exercises` whose `equipment_required` carries the token the tag maps to,
via `equipment_tag_layer0`) rather than the retired `exercise_equipment` join.
Items the user already owns in any locale (via `locale_equipment`) get a
hint badge — the explicit status toggle is independent so the user can
override (e.g. mark something "passed" even if a stray instance shows up
in a hotel-gym locale).
"""
from flask import Blueprint, render_template, request, redirect, url_for, flash
from database import get_db
from routes.auth import current_user_id
from layer0_progression import progression_pattern
from equipment_tag_layer0 import (
    layer0_token_for_tag, layer0_equipment_exercise_counts,
)

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

    # Track 1 — the "you already have this" hint sourced int equipment_ids from
    # the legacy locale_equipment table, now retired for the layer0
    # canonical-name store. The public purchase catalog (exercise_equipment /
    # equipment_items) is still int-id keyed, so the hint can't be matched
    # against the canonical pool until the catalog migrates to layer0 (Track 3).
    # Degraded to off until then (approved 2026-06-05); the explicit
    # owned/wanted/passed status below is unaffected.
    owned_equipment_ids = set()

    # Impacted-exercise counts from the single canonical catalog: count active
    # layer0 exercises whose equipment_required carries the token a
    # recommendation's equipment (tag) maps to. Cardio/craft/generically-modelled
    # equipment has no layer0 token → 0 (matches the pre-unification reality).
    l0_counts = layer0_equipment_exercise_counts(db)

    grouped = {'high': [], 'medium': [], 'low': []}
    counts_by_status = {'wanted': 0, 'owned': 0, 'passed': 0, 'none': 0}
    for r in rows:
        d = dict(r)
        token = layer0_token_for_tag(d.get('equipment_tag'))
        d['impacted_count'] = l0_counts.get(token, 0) if token else 0
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

    # The exercises this equipment unlocks, from the canonical layer0 catalog:
    # active exercises whose equipment_required carries the mapped token.
    impacted = []
    token = layer0_token_for_tag(pr['equipment_tag'])
    if token:
        raw = db.execute(
            '''SELECT exercise_id, exercise_name, exercise_type, movement_patterns
               FROM layer0.exercises
               WHERE superseded_at IS NULL AND ? = ANY(equipment_required)
               ORDER BY exercise_name''',
            (token,)
        ).fetchall()
        impacted = [
            {'exercise': r['exercise_name'], 'exercise_type': r['exercise_type'],
             'movement_pattern': progression_pattern(list(r['movement_patterns'] or []))}
            for r in raw
        ]

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
