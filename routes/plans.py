import json
import os
from datetime import datetime, timedelta
from itertools import groupby
from datetime import date as date_type

import io
import re
import zipfile

from flask import Blueprint, render_template, request, redirect, url_for, flash, jsonify, Response
from database import get_db
from routes.auth import current_user_id

bp = Blueprint('plans', __name__, url_prefix='/plans')


def _coerce_date(value):
    """Best-effort coerce a DB value to a `date` for bucketing.

    psycopg returns DATE columns as `datetime.date` already; this also accepts
    ISO strings (the render harness's fake cursor returns canned string dates)
    and returns None for anything unparseable so a bad value just falls through
    to the Active bucket rather than 500-ing the page."""
    if value is None or isinstance(value, date_type):
        return value
    try:
        return date_type.fromisoformat(str(value)[:10])
    except ValueError:
        return None


DAILY_SUPPLEMENTS = [
    'Creatine 5g (morning)',
    'Omega-3 2–3g',
    'Vitamin D3 2000 IU',
    'Magnesium Glycinate 400mg (pre-bed)',
    'Multivitamin',
]

_NUTRITION_PROFILES = {
    'rest':      {'cal': '2800–2900', 'carb': 45, 'protein': 29, 'fat': 24, 'fueling': None},
    'moderate':  {'cal': '3000–3200', 'carb': 54, 'protein': 25, 'fat': 21,
                  'fueling': '30–40g carbs/hr · 400–500ml fluid/hr (if 60–90 min)'},
    'hard':      {'cal': '3400–3800', 'carb': 58, 'protein': 22, 'fat': 20,
                  'fueling': '50–60g carbs/hr · 500mg Na/hr · 500–600ml fluid/hr'},
    'heavy':     {'cal': '3900–4500', 'carb': 62, 'protein': 19, 'fat': 19,
                  'fueling': '50–60g carbs/hr · 500mg Na/hr · BCAAs · Tart cherry 30ml post'},
    'long_hike': {'cal': '4700–6200', 'carb': 64, 'protein': 17, 'fat': 19,
                  'fueling': '50–60g carbs/hr · 500mg Na/hr · BCAAs · Tart cherry 30ml post'},
}


def _workout_nutrition(sport_type, intensity, duration_min):
    """Return nutrition profile dict for a workout."""
    duration_min = duration_min or 0
    if sport_type == 'hiking' and duration_min >= 300:
        key = 'long_hike'
    elif sport_type == 'hiking' and duration_min >= 180:
        key = 'heavy'
    elif intensity == 'very_hard' or duration_min > 180:
        key = 'heavy'
    elif intensity == 'hard' or duration_min >= 90:
        key = 'hard'
    elif intensity in ('easy', 'moderate'):
        key = 'moderate'
    else:
        key = 'rest'
    return _NUTRITION_PROFILES[key]


def _create_plan_from_dict(db, data):
    """Insert a training plan from a dict. Returns plan_id."""
    uid = current_user_id()
    workouts = data.get('workouts', [])
    raw = json.dumps(data)
    cur = db.execute(
        '''INSERT INTO training_plans
           (name, description, sport_focus, start_date, end_date, source_json, user_id)
           VALUES (?,?,?,?,?,?,?) RETURNING id''',
        (data['name'], data.get('description'), data.get('sport_focus'),
         data.get('start_date'), data.get('end_date'), raw, uid)
    )
    plan_id = cur.lastrowid
    for w in workouts:
        garmin_json = w.get('garmin_workout_json')
        garmin_str = json.dumps(garmin_json) if garmin_json else None
        db.execute(
            '''INSERT INTO plan_items
               (plan_id, item_date, sport_type, workout_name, description,
                target_duration_min, target_distance_mi, intensity, garmin_workout_json,
                calorie_target, macro_carb_pct, macro_protein_pct, macro_fat_pct, session_fueling,
                user_id)
               VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)''',
            (plan_id, w.get('date'), w.get('sport_type', ''),
             w.get('workout_name', ''), w.get('description'),
             w.get('target_duration_min'), w.get('target_distance_mi'),
             w.get('intensity'), garmin_str,
             w.get('calorie_target'), w.get('macro_carb_pct'),
             w.get('macro_protein_pct'), w.get('macro_fat_pct'),
             w.get('session_fueling'), uid)
        )
    return plan_id


def _plan_health(db, plan_id):
    """Compute plan review health status for the three-tier incremental pattern."""
    uid = current_user_id()
    plan = db.execute(
        'SELECT created_at FROM training_plans WHERE id=? AND user_id=?',
        (plan_id, uid)
    ).fetchone()
    plan_created = plan['created_at'] if plan else '1970-01-01'

    # plan_reviews is parent-JOIN scoped via training_plans
    last_t1 = db.execute(
        '''SELECT pr.sessions_reviewed FROM plan_reviews pr
           JOIN training_plans tp ON tp.id = pr.plan_id
           WHERE pr.plan_id=? AND tp.user_id=? AND pr.tier=1
           ORDER BY pr.created_at DESC LIMIT 1''',
        (plan_id, uid)
    ).fetchone()
    last_t2 = db.execute(
        '''SELECT pr.created_at FROM plan_reviews pr
           JOIN training_plans tp ON tp.id = pr.plan_id
           WHERE pr.plan_id=? AND tp.user_id=? AND pr.tier=2
           ORDER BY pr.created_at DESC LIMIT 1''',
        (plan_id, uid)
    ).fetchone()

    current_completed = db.execute(
        "SELECT COUNT(*) FROM plan_items WHERE plan_id=? AND user_id=? AND status='completed'",
        (plan_id, uid)
    ).fetchone()[0]

    sessions_since_t1 = current_completed - (last_t1['sessions_reviewed'] if last_t1 else 0)

    # Use plan creation date as baseline if never reviewed at tier 2
    baseline_t2 = last_t2['created_at'] if last_t2 else plan_created
    try:
        baseline_dt = datetime.fromisoformat(baseline_t2.split('.')[0])
        days_since_t2 = (datetime.now() - baseline_dt).days
    except Exception:
        days_since_t2 = 0

    scheduled_remaining = db.execute(
        "SELECT COUNT(*) FROM plan_items WHERE plan_id=? AND user_id=? AND status='scheduled'",
        (plan_id, uid)
    ).fetchone()[0]

    tier1_due = sessions_since_t1 > 0
    tier2_due = days_since_t2 >= 7 or sessions_since_t1 >= 5
    tier3_due = 0 < scheduled_remaining <= 7

    recent = db.execute(
        '''SELECT item_date, workout_name, sport_type, status, notes
           FROM plan_items WHERE plan_id=? AND user_id=? AND status IN ('completed','skipped')
           ORDER BY item_date DESC LIMIT 5''',
        (plan_id, uid)
    ).fetchall()

    upcoming = db.execute(
        '''SELECT item_date, workout_name, sport_type, intensity, target_duration_min
           FROM plan_items WHERE plan_id=? AND user_id=? AND status='scheduled'
           ORDER BY item_date ASC LIMIT 7''',
        (plan_id, uid)
    ).fetchall()

    # Compliance data for recently completed items linked to cardio_log
    compliance_rows = db.execute(
        '''SELECT pi.item_date, pi.workout_name,
                  pi.target_duration_min, pi.target_distance_mi,
                  cl.duration_min as actual_duration_min,
                  cl.distance_mi as actual_distance_mi,
                  cl.activity_name as garmin_activity_name,
                  cl.avg_hr, cl.garmin_activity_id
           FROM plan_items pi
           JOIN cardio_log cl ON cl.plan_item_id = pi.id
           WHERE pi.plan_id = ? AND pi.user_id = ? AND pi.status = 'completed'
           ORDER BY pi.item_date DESC LIMIT 10''',
        (plan_id, uid)
    ).fetchall()

    compliance = []
    for cr in compliance_rows:
        dur_pct = None
        dist_pct = None
        if cr['target_duration_min'] and cr['actual_duration_min']:
            dur_pct = round(cr['actual_duration_min'] / cr['target_duration_min'] * 100)
        if cr['target_distance_mi'] and cr['actual_distance_mi']:
            dist_pct = round(cr['actual_distance_mi'] / cr['target_distance_mi'] * 100)
        compliance.append({
            'item_date': cr['item_date'],
            'workout_name': cr['workout_name'],
            'garmin_activity': cr['garmin_activity_name'],
            'duration_pct': dur_pct,
            'distance_pct': dist_pct,
            'avg_hr': cr['avg_hr'],
        })

    return {
        'plan_id': plan_id,
        'sessions_since_tier1': sessions_since_t1,
        'days_since_tier2': days_since_t2,
        'scheduled_remaining': scheduled_remaining,
        'tier1_due': tier1_due,
        'tier2_due': tier2_due,
        'tier3_due': tier3_due,
        'recent_sessions': [dict(r) for r in recent],
        'upcoming_items': [dict(u) for u in upcoming],
        'compliance': compliance,
    }


@bp.route('/')
def list_plans():
    db = get_db()
    all_plans = db.execute(
        '''SELECT p.*, COUNT(i.id) as item_count,
                  SUM(CASE WHEN i.status = 'completed' THEN 1 ELSE 0 END) as completed_count
           FROM training_plans p
           LEFT JOIN plan_items i ON i.plan_id = p.id
           WHERE p.user_id = ?
           GROUP BY p.id
           ORDER BY p.start_date DESC''',
        (current_user_id(),)
    ).fetchall()
    plans = [p for p in all_plans if p['status'] != 'archived']
    archived = [p for p in all_plans if p['status'] == 'archived']

    # AI-generated plans live in the separate `plan_versions` model (written by
    # the Layer 4 generator in routes/plan_create.py), NOT in `training_plans`.
    # Without this they were unreachable from the Plan screen — a successfully
    # generated plan only existed at its direct /plans/v2/<id> URL — so the list
    # looked empty even after generating plans. Surface the live generations
    # (still generating, or ready and not-yet-superseded) here. Failed
    # generations are intentionally NOT listed — they're a dead end the athlete
    # re-runs, not a plan to act on.
    gen_rows = db.execute(
        '''SELECT pv.id, pv.created_at, pv.created_via, pv.scope_start_date,
                  pv.scope_end_date, pv.pattern, pv.generation_status,
                  pv.completed_at,
                  COUNT(s.id) AS session_count
           FROM plan_versions pv
           LEFT JOIN plan_sessions s ON s.plan_version_id = pv.id
           WHERE pv.user_id = ?
             AND pv.generation_status IN ('ready', 'generating')
             AND pv.superseded_at IS NULL
           GROUP BY pv.id
           ORDER BY pv.scope_start_date ASC, pv.created_at ASC''',
        (current_user_id(),)
    ).fetchall()

    # Bucket the ready plans by their scope dates against today: a plan whose
    # scope hasn't started is Upcoming, one whose scope is live is Active, one
    # whose scope has ended (or that the athlete manually marked complete) is
    # Completed. Bucketing in Python — not SQL — keeps it testable through the
    # render harness's fake cursor (which returns canned rows, ignoring the SQL).
    today = date_type.today()
    gen_generating, gen_upcoming, gen_active, gen_completed = [], [], [], []
    for r in gen_rows:
        if r['generation_status'] == 'generating':
            gen_generating.append(r)
            continue
        start = _coerce_date(r['scope_start_date'])
        end = _coerce_date(r['scope_end_date'])
        if r['completed_at'] is not None:
            gen_completed.append(r)
        elif end is not None and end < today:
            gen_completed.append(r)
        elif start is not None and start > today:
            gen_upcoming.append(r)
        else:
            gen_active.append(r)

    return render_template(
        'plans/list.html', plans=plans, archived=archived,
        gen_generating=gen_generating, gen_upcoming=gen_upcoming,
        gen_active=gen_active, gen_completed=gen_completed)


@bp.route('/import', methods=['GET', 'POST'])
def import_plan():
    if request.method == 'POST':
        raw = request.form.get('plan_json', '').strip()
        if not raw:
            flash('No JSON provided.', 'warning')
            return redirect(url_for('plans.import_plan'))
        try:
            data = json.loads(raw)
        except json.JSONDecodeError as e:
            flash(f'Invalid JSON: {e}', 'danger')
            return redirect(url_for('plans.import_plan'))
        if not data.get('name'):
            flash('Plan JSON must include a "name" field.', 'danger')
            return redirect(url_for('plans.import_plan'))
        db = get_db()
        plan_id = _create_plan_from_dict(db, data)
        db.commit()
        workouts = data.get('workouts', [])
        flash(f'Plan "{data["name"]}" imported with {len(workouts)} workouts.', 'success')
        return redirect(url_for('plans.view_plan', plan_id=plan_id))
    return render_template('plans/import.html')


@bp.route('/api/import', methods=['POST'])
def api_import_plan():
    data = request.get_json(silent=True)
    if not data or not data.get('name'):
        return jsonify({'ok': False, 'error': 'JSON body with "name" field required'}), 400
    db = get_db()
    plan_id = _create_plan_from_dict(db, data)
    db.commit()
    return jsonify({'ok': True, 'plan_id': plan_id})


@bp.route('/api/review', methods=['POST'])
def api_plan_review():
    data = request.get_json(silent=True) or {}
    plan_id = data.get('plan_id')
    tier = data.get('tier')
    if not plan_id or tier not in (1, 2, 3):
        return jsonify({'ok': False, 'error': 'plan_id and tier (1, 2, or 3) required'}), 400
    db = get_db()
    uid = current_user_id()
    # Verify plan ownership before writing a review for it
    if not db.execute(
        'SELECT 1 FROM training_plans WHERE id=? AND user_id=?', (plan_id, uid)
    ).fetchone():
        return jsonify({'ok': False, 'error': 'Plan not found'}), 404
    completed = db.execute(
        "SELECT COUNT(*) FROM plan_items WHERE plan_id=? AND user_id=? AND status='completed'",
        (plan_id, uid)
    ).fetchone()[0]
    db.execute(
        'INSERT INTO plan_reviews (plan_id, tier, sessions_reviewed, notes) VALUES (?,?,?,?)',
        (plan_id, tier, completed, data.get('notes', ''))
    )
    db.commit()
    return jsonify({'ok': True})


@bp.route('/items/<int:item_id>', methods=['PATCH'])
def api_patch_plan_item(item_id):
    data = request.get_json(silent=True) or {}
    allowed = {'description', 'intensity', 'target_duration_min', 'target_distance_mi',
               'notes', 'workout_name'}
    updates = {k: v for k, v in data.items() if k in allowed}
    if not updates:
        return jsonify({'ok': False, 'error': 'No valid fields to update'}), 400
    db = get_db()
    set_clause = ', '.join(f'{k}=?' for k in updates)
    values = list(updates.values()) + [item_id, current_user_id()]
    db.execute(f'UPDATE plan_items SET {set_clause} WHERE id=? AND user_id=?', values)
    db.commit()
    return jsonify({'ok': True})


# Sport types where target_duration_min isn't the primary load axis. The
# duration_scale bulk action reaches these via a description note instead
# (the actual load is the sets/reps/weight prescribed in the description,
# which we can't reliably parse + rewrite).
_LOAD_NOTE_SPORTS = {'strength_training'}

# Intensity ladder for the intensity_step bulk action. Same ordering as the
# existing Tier 2 review's "too hard" / "too easy" toggle in routes/coaching.py.
_INTENSITY_LADDER = ['easy', 'moderate', 'hard', 'very_hard']

# Marker that wraps the load-scale note we append to strength descriptions.
# Idempotent re-application: a re-run with a different multiplier replaces
# the existing note rather than stacking. Anchored at end of string so it
# always sits at the bottom of the description.
_LOAD_NOTE_RE = re.compile(
    r'\n*\[Load scaled to \d+% — (?:reduce|increase) weights ~\d+% from prescribed\]\s*$'
)


def _build_load_note(mult: float) -> str:
    """Render the load-scale note appended to strength descriptions."""
    pct = round(mult * 100)
    if mult < 1:
        delta = round((1 - mult) * 100)
        return f'\n\n[Load scaled to {pct}% — reduce weights ~{delta}% from prescribed]'
    if mult > 1:
        delta = round((mult - 1) * 100)
        return f'\n\n[Load scaled to {pct}% — increase weights ~{delta}% from prescribed]'
    # mult == 1.0 → no note (caller should not invoke for a no-op multiplier)
    return ''


def _apply_load_note(description: str | None, mult: float) -> str:
    """Replace any existing load note (idempotent) and append the new one."""
    base = _LOAD_NOTE_RE.sub('', description or '').rstrip()
    note = _build_load_note(mult)
    return (base + note) if note else base


@bp.route('/<int:plan_id>/items/bulk', methods=['POST'])
def api_bulk_edit_items(plan_id):
    """Apply a single mechanical action to a set of scheduled plan items.

    JSON body:
      {
        "item_ids": [int, ...],
        "action":   "shift_date" | "intensity_step" | "duration_scale" | "mark_skipped",
        "value":    action-dependent (see below)
      }

    action / value pairs:
      shift_date       value: int (days, can be negative)
      intensity_step   value: "down" | "up"
      duration_scale   value: float (multiplier, e.g. 0.7 / 0.85 / 1.15 / 1.3)
      mark_skipped     value: ignored

    Only operates on items where status='scheduled' AND the parent plan is
    owned by the current user. Returns counts of updated / skipped items.
    """
    from datetime import date as date_type, timedelta as _td
    data = request.get_json(silent=True) or {}
    item_ids = data.get('item_ids') or []
    action = data.get('action')
    value = data.get('value')

    if not isinstance(item_ids, list) or not all(isinstance(i, int) for i in item_ids):
        return jsonify({'ok': False, 'error': 'item_ids must be a list of integers'}), 400
    if not item_ids:
        return jsonify({'ok': False, 'error': 'No items selected'}), 400
    if action not in ('shift_date', 'intensity_step', 'duration_scale', 'mark_skipped'):
        return jsonify({'ok': False, 'error': f'Unknown action: {action!r}'}), 400

    db = get_db()
    uid = current_user_id()
    if not db.execute(
        'SELECT 1 FROM training_plans WHERE id=? AND user_id=?', (plan_id, uid)
    ).fetchone():
        return jsonify({'ok': False, 'error': 'Plan not found'}), 404

    # Pull the scoped, scheduled items in one query — anything missing from
    # this set is silently skipped (covers cross-user IDs, cross-plan IDs,
    # already-completed/skipped items).
    placeholders = ','.join('?' * len(item_ids))
    rows = db.execute(
        f'''SELECT id, item_date, sport_type, intensity,
                   target_duration_min, description, status
            FROM plan_items
            WHERE id IN ({placeholders})
              AND plan_id = ? AND user_id = ? AND status = 'scheduled' ''',
        list(item_ids) + [plan_id, uid]
    ).fetchall()
    eligible = {r['id']: r for r in rows}
    not_eligible_count = len(item_ids) - len(eligible)

    updated = 0
    skipped_reason = None

    if action == 'shift_date':
        try:
            delta_days = int(value)
        except (TypeError, ValueError):
            return jsonify({'ok': False, 'error': 'shift_date value must be an int'}), 400
        if delta_days == 0:
            return jsonify({'ok': True, 'updated': 0, 'skipped': not_eligible_count})
        for r in rows:
            try:
                d = date_type.fromisoformat(r['item_date'])
            except (ValueError, TypeError):
                continue
            new_date = (d + _td(days=delta_days)).isoformat()
            db.execute(
                'UPDATE plan_items SET item_date=? WHERE id=? AND user_id=?',
                (new_date, r['id'], uid)
            )
            updated += 1

    elif action == 'intensity_step':
        if value not in ('down', 'up'):
            return jsonify({'ok': False, 'error': "intensity_step value must be 'down' or 'up'"}), 400
        direction = -1 if value == 'down' else 1
        skipped_unknown = 0
        for r in rows:
            cur = (r['intensity'] or '').strip().lower()
            try:
                idx = _INTENSITY_LADDER.index(cur)
            except ValueError:
                # Unknown intensity (NULL or non-standard) — leave alone
                skipped_unknown += 1
                continue
            new_idx = max(0, min(len(_INTENSITY_LADDER) - 1, idx + direction))
            if new_idx == idx:
                continue  # already at the rail; no change
            new_intensity = _INTENSITY_LADDER[new_idx]
            db.execute(
                'UPDATE plan_items SET intensity=? WHERE id=? AND user_id=?',
                (new_intensity, r['id'], uid)
            )
            updated += 1
        if skipped_unknown:
            skipped_reason = f'{skipped_unknown} item(s) had no intensity set'

    elif action == 'duration_scale':
        try:
            mult = float(value)
        except (TypeError, ValueError):
            return jsonify({'ok': False, 'error': 'duration_scale value must be a number'}), 400
        if mult <= 0:
            return jsonify({'ok': False, 'error': 'duration_scale value must be > 0'}), 400
        if mult == 1.0:
            return jsonify({'ok': True, 'updated': 0, 'skipped': not_eligible_count})
        load_noted = 0
        skipped_no_duration = 0
        for r in rows:
            if r['sport_type'] in _LOAD_NOTE_SPORTS:
                # Strength: append a load-scale note to description instead
                # of touching duration. The athlete reads the note and
                # adjusts their working weights on the fly.
                new_description = _apply_load_note(r['description'], mult)
                db.execute(
                    'UPDATE plan_items SET description=? WHERE id=? AND user_id=?',
                    (new_description, r['id'], uid)
                )
                load_noted += 1
                updated += 1
                continue
            if not r['target_duration_min']:
                skipped_no_duration += 1
                continue
            new_duration = max(1, int(round(r['target_duration_min'] * mult)))
            db.execute(
                'UPDATE plan_items SET target_duration_min=? WHERE id=? AND user_id=?',
                (new_duration, r['id'], uid)
            )
            updated += 1
        bits = []
        if load_noted:
            bits.append(f'{load_noted} strength item(s) annotated with load-scale note')
        if skipped_no_duration:
            bits.append(f'{skipped_no_duration} item(s) skipped (no duration set)')
        if bits:
            skipped_reason = '; '.join(bits)

    else:  # mark_skipped
        for r in rows:
            db.execute(
                "UPDATE plan_items SET status='skipped' WHERE id=? AND user_id=?",
                (r['id'], uid)
            )
            updated += 1

    db.commit()
    return jsonify({
        'ok': True,
        'updated': updated,
        'skipped': not_eligible_count,
        'reason': skipped_reason,
    })


@bp.route('/<int:plan_id>/health')
def plan_health(plan_id):
    db = get_db()
    if not db.execute(
        'SELECT id FROM training_plans WHERE id=? AND user_id=?',
        (plan_id, current_user_id())
    ).fetchone():
        return jsonify({'error': 'Plan not found'}), 404
    return jsonify(_plan_health(db, plan_id))


@bp.route('/<int:plan_id>/archive', methods=['POST'])
def archive_plan(plan_id):
    db = get_db()
    db.execute(
        "UPDATE training_plans SET status='archived' WHERE id=? AND user_id=?",
        (plan_id, current_user_id())
    )
    db.commit()
    flash('Plan archived.', 'secondary')
    return redirect(url_for('plans.list_plans'))


@bp.route('/<int:plan_id>/unarchive', methods=['POST'])
def unarchive_plan(plan_id):
    db = get_db()
    db.execute(
        "UPDATE training_plans SET status='active' WHERE id=? AND user_id=?",
        (plan_id, current_user_id())
    )
    db.commit()
    flash('Plan restored to active.', 'success')
    return redirect(url_for('plans.view_plan', plan_id=plan_id))


@bp.route('/<int:plan_id>/delete', methods=['POST'])
def delete_plan(plan_id):
    db = get_db()
    uid = current_user_id()
    # Verify plan ownership before deleting child rows that lack user_id
    if not db.execute(
        'SELECT 1 FROM training_plans WHERE id=? AND user_id=?', (plan_id, uid)
    ).fetchone():
        if request.is_json or request.headers.get('Accept') == 'application/json':
            return jsonify({'ok': False, 'error': 'Plan not found'}), 404
        flash('Plan not found.', 'danger')
        return redirect(url_for('plans.list_plans'))
    db.execute('DELETE FROM plan_reviews WHERE plan_id=?', (plan_id,))
    db.execute('DELETE FROM coaching_chat WHERE plan_id=? AND user_id=?', (plan_id, uid))
    db.execute('DELETE FROM plan_items WHERE plan_id=? AND user_id=?', (plan_id, uid))
    db.execute('DELETE FROM training_plans WHERE id=? AND user_id=?', (plan_id, uid))
    db.commit()
    if request.is_json or request.headers.get('Accept') == 'application/json':
        return jsonify({'ok': True})
    flash('Plan deleted.', 'warning')
    return redirect(url_for('plans.list_plans'))


def _build_week_grid(items):
    """Group plan_items into Mon–Sun week grids for the week-view calendar.

    Returns a chronological list of weeks; each week is {label, range, days}
    where `days` is exactly 7 cells (Mon..Sun), each
    {dow, date, iso, is_today, items}. Original Row objects are preserved.
    Items with an unparseable date are skipped (matching the legacy (0,0)
    sentinel behavior)."""
    buckets = {}
    for it in items:
        try:
            d = date_type.fromisoformat(it['item_date'])
        except Exception:
            continue
        buckets.setdefault(d.isocalendar()[:2], []).append((d, it))
    today = date_type.today()
    grid = []
    for idx, key in enumerate(sorted(buckets), start=1):
        pairs = buckets[key]
        monday = pairs[0][0] - timedelta(days=pairs[0][0].weekday())
        days = []
        for off in range(7):
            dd = monday + timedelta(days=off)
            days.append({
                'dow': dd.strftime('%a'),
                'date': dd.strftime('%b ') + str(dd.day),
                'iso': dd.isoformat(),
                'is_today': dd == today,
                'workouts': [it for (d, it) in pairs if d == dd],
            })
        sunday = monday + timedelta(days=6)
        grid.append({
            'label': 'Week %d' % idx,
            'range': '%s %d – %s %d' % (monday.strftime('%b'), monday.day,
                                        sunday.strftime('%b'), sunday.day),
            'days': days,
        })
    return grid


@bp.route('/<int:plan_id>')
def view_plan(plan_id):
    db = get_db()
    uid = current_user_id()
    plan = db.execute(
        'SELECT * FROM training_plans WHERE id = ? AND user_id = ?',
        (plan_id, uid)
    ).fetchone()
    if not plan:
        flash('Plan not found.', 'danger')
        return redirect(url_for('plans.list_plans'))
    items = db.execute(
        'SELECT * FROM plan_items WHERE plan_id = ? AND user_id = ? ORDER BY item_date ASC',
        (plan_id, uid)
    ).fetchall()

    weeks_view = _build_week_grid(items)

    total = len(items)
    completed = sum(1 for i in items if i['status'] == 'completed')

    active_mods = db.execute(
        '''SELECT iem.modification_type, iem.modification_notes,
                  il.body_part, il.status,
                  ei.exercise as exercise_name,
                  ei_sub.exercise as substitute_name
           FROM injury_exercise_modifications iem
           JOIN injury_log il ON il.id = iem.injury_id
           JOIN exercise_inventory ei ON ei.id = iem.exercise_id
           LEFT JOIN exercise_inventory ei_sub ON ei_sub.id = iem.substitute_exercise_id
           WHERE il.user_id = ? AND il.status IN ('Active', 'Managing')
           ORDER BY il.status, il.body_part, ei.exercise''',
        (uid,)
    ).fetchall()

    affected_exercises = {m['exercise_name'] for m in active_mods}
    health = _plan_health(db, plan_id)

    api_configured = bool(os.environ.get('ANTHROPIC_API_KEY'))

    days_to_race = None
    if plan['end_date']:
        try:
            race_date = date_type.fromisoformat(plan['end_date'])
            days_to_race = (race_date - date_type.today()).days
        except Exception:
            pass

    clothing_recs = []
    try:
        from coaching import get_clothing_context
        today_str = date_type.today().isoformat()
        # plan_travel is parent-JOIN scoped via training_plans
        trip = db.execute(
            '''SELECT pt.city FROM plan_travel pt
               JOIN training_plans tp ON tp.id = pt.plan_id
               WHERE pt.plan_id=? AND tp.user_id=?
                 AND pt.start_date<=? AND pt.end_date>=? AND pt.city!='' LIMIT 1''',
            (plan_id, uid, today_str, today_str)
        ).fetchone()
        city = trip['city'] if trip else ''
        if not city:
            # Track 1 — home city via the preferred-flagged locale (replaces
            # the hardcoded locale='home').
            home = db.execute(
                "SELECT city FROM locale_profiles WHERE preferred AND user_id=? LIMIT 1",
                (uid,)
            ).fetchone()
            city = home['city'] if home and home['city'] else ''
        clothing_recs = get_clothing_context(db, plan_id, city)
    except Exception:
        pass

    return render_template('plans/view.html', plan=plan, weeks_view=weeks_view,
                           total=total, completed=completed,
                           active_mods=active_mods,
                           affected_exercises=affected_exercises,
                           health=health,
                           workout_nutrition=_workout_nutrition,
                           daily_supplements=DAILY_SUPPLEMENTS,
                           api_configured=api_configured,
                           days_to_race=days_to_race,
                           clothing_recs=clothing_recs)


@bp.route('/<int:plan_id>/item/<int:item_id>')
def view_item(plan_id, item_id):
    db = get_db()
    uid = current_user_id()
    item = db.execute(
        'SELECT * FROM plan_items WHERE id = ? AND plan_id = ? AND user_id = ?',
        (item_id, plan_id, uid)
    ).fetchone()
    if not item:
        flash('Item not found.', 'danger')
        return redirect(url_for('plans.view_plan', plan_id=plan_id))
    nutrition = _workout_nutrition(item['sport_type'], item['intensity'],
                                   item['target_duration_min'])
    return render_template('plans/item.html', plan_id=plan_id, item=item,
                           nutrition=nutrition)


@bp.route('/<int:plan_id>/item/<int:item_id>/complete', methods=['POST'])
def complete_item(plan_id, item_id):
    db = get_db()
    notes = request.form.get('notes', '')
    db.execute(
        "UPDATE plan_items SET status = 'completed', notes = ? "
        "WHERE id = ? AND plan_id = ? AND user_id = ?",
        (notes, item_id, plan_id, current_user_id())
    )
    db.commit()
    flash('Workout marked as completed.', 'success')
    return redirect(url_for('plans.view_plan', plan_id=plan_id))


@bp.route('/<int:plan_id>/item/<int:item_id>/skip', methods=['POST'])
def skip_item(plan_id, item_id):
    db = get_db()
    notes = request.form.get('notes', '')
    db.execute(
        "UPDATE plan_items SET status = 'skipped', notes = ? "
        "WHERE id = ? AND plan_id = ? AND user_id = ?",
        (notes, item_id, plan_id, current_user_id())
    )
    db.commit()
    flash('Workout marked as skipped.', 'warning')
    return redirect(url_for('plans.view_plan', plan_id=plan_id))


@bp.route('/<int:plan_id>/item/<int:item_id>/push-to-garmin', methods=['POST'])
def push_to_garmin(plan_id, item_id):
    db = get_db()
    uid = current_user_id()
    item = db.execute(
        'SELECT * FROM plan_items WHERE id = ? AND plan_id = ? AND user_id = ?',
        (item_id, plan_id, uid)
    ).fetchone()
    if not item:
        flash('Item not found.', 'danger')
        return redirect(url_for('plans.view_plan', plan_id=plan_id))
    if not item['garmin_workout_json']:
        flash('No Garmin workout JSON attached to this plan item.', 'warning')
        return redirect(url_for('plans.view_item', plan_id=plan_id, item_id=item_id))
    try:
        from garmin_connect import upload_workout, schedule_workout
        workout_json = json.loads(item['garmin_workout_json'])
        workout_id = upload_workout(db, workout_json)
        if item['item_date']:
            schedule_workout(db, workout_id, item['item_date'])
        db.execute(
            '''INSERT INTO garmin_workouts
               (plan_item_id, garmin_workout_id, workout_name, sport_type, scheduled_date, user_id)
               VALUES (?,?,?,?,?,?)''',
            (item_id, workout_id, item['workout_name'],
             item['sport_type'], item['item_date'], uid)
        )
        db.commit()
        flash(f'Workout uploaded to Garmin Connect (ID: {workout_id}).', 'success')
    except Exception as e:
        flash(f'Garmin upload failed: {e}', 'danger')
    return redirect(url_for('plans.view_item', plan_id=plan_id, item_id=item_id))


def _safe_filename(text: str, max_len: int = 40) -> str:
    return re.sub(r'[^\w\-]+', '_', text or 'workout').strip('_')[:max_len]


@bp.route('/<int:plan_id>/item/<int:item_id>/workout.fit')
def download_item_fit(plan_id, item_id):
    """Download a single workout as a Garmin FIT file."""
    from fit_workout_generator import generate_workout_fit

    db = get_db()
    item = db.execute(
        'SELECT * FROM plan_items WHERE id=? AND plan_id=? AND user_id=?',
        (item_id, plan_id, current_user_id())
    ).fetchone()
    if not item:
        flash('Item not found.', 'danger')
        return redirect(url_for('plans.view_plan', plan_id=plan_id))

    try:
        fit_bytes = generate_workout_fit(dict(item))
    except Exception as e:
        flash(f'Could not generate FIT file: {e}', 'danger')
        return redirect(url_for('plans.view_item', plan_id=plan_id, item_id=item_id))

    filename = f"{item['item_date']}_{_safe_filename(item['workout_name'])}.fit"
    return Response(
        fit_bytes,
        mimetype='application/octet-stream',
        headers={'Content-Disposition': f'attachment; filename="{filename}"'},
    )


@bp.route('/<int:plan_id>/workouts.zip')
def download_plan_fits(plan_id):
    """Download all scheduled workouts in a plan as a ZIP of FIT files."""
    from fit_workout_generator import generate_workout_fit

    db = get_db()
    uid = current_user_id()
    plan = db.execute(
        'SELECT name FROM training_plans WHERE id=? AND user_id=?', (plan_id, uid)
    ).fetchone()
    if not plan:
        flash('Plan not found.', 'danger')
        return redirect(url_for('plans.list_plans'))

    items = db.execute(
        "SELECT * FROM plan_items WHERE plan_id=? AND user_id=? AND status='scheduled' "
        "ORDER BY item_date ASC",
        (plan_id, uid)
    ).fetchall()

    buf = io.BytesIO()
    with zipfile.ZipFile(buf, 'w', zipfile.ZIP_DEFLATED) as zf:
        for item in items:
            try:
                fit_bytes = generate_workout_fit(dict(item))
            except Exception:
                continue
            name = f"{item['item_date']}_{_safe_filename(item['workout_name'])}.fit"
            zf.writestr(name, fit_bytes)

    zip_filename = f"{_safe_filename(plan['name'], 30)}_workouts.zip"
    return Response(
        buf.getvalue(),
        mimetype='application/zip',
        headers={'Content-Disposition': f'attachment; filename="{zip_filename}"'},
    )
