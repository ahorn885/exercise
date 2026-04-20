import json
from datetime import date, timedelta

from flask import Blueprint, render_template, request, redirect, url_for, flash, jsonify
from database import get_db

bp = Blueprint('coaching', __name__, url_prefix='/coaching')


@bp.route('/context')
def context():
    """JSON endpoint — returns full coaching context for the active plan."""
    db = get_db()
    plan_id = request.args.get('plan_id', type=int)
    lookback = request.args.get('lookback_days', 14, type=int)
    from coaching import get_coaching_context
    ctx = get_coaching_context(db, plan_id=plan_id, lookback_days=lookback)
    return jsonify(ctx)


LOCALES = ['home', 'hotel', 'partner', 'airport']


@bp.route('/generate', methods=['GET', 'POST'])
def generate():
    db = get_db()
    plans = db.execute(
        'SELECT id, name, end_date FROM training_plans ORDER BY start_date DESC'
    ).fetchall()

    if request.method == 'POST':
        start_date = request.form.get('start_date', '').strip()
        weeks = int(request.form.get('weeks', 4))
        notes = request.form.get('notes', '').strip()
        race_name = request.form.get('race_name', '').strip()
        race_date = request.form.get('race_date', '').strip()
        race_location = request.form.get('race_location', '').strip()
        race_disciplines = request.form.get('race_disciplines', '').strip()
        race_duration = request.form.get('race_duration', '').strip()
        race_website = request.form.get('race_website', '').strip()
        locale = request.form.get('locale', 'home')
        if locale not in LOCALES:
            locale = 'home'
        nutrition_goal = request.form.get('nutrition_goal', 'maintain')
        try:
            travel_schedule = json.loads(request.form.get('travel_schedule', '[]'))
            if not isinstance(travel_schedule, list):
                travel_schedule = []
        except (json.JSONDecodeError, ValueError):
            travel_schedule = []

        if not start_date:
            flash('Start date is required.', 'danger')
            return redirect(url_for('coaching.generate'))

        if not _check_api_key():
            flash('ANTHROPIC_API_KEY is not configured. Set it in your environment.', 'danger')
            return redirect(url_for('coaching.generate'))

        try:
            from coaching import generate_plan
            from routes.plans import _create_plan_from_dict
            plan_data, usage = generate_plan(
                db, start_date, weeks=weeks, notes=notes,
                race_name=race_name, race_date=race_date, race_location=race_location,
                race_disciplines=race_disciplines, race_duration=race_duration,
                race_website=race_website, locale=locale,
                nutrition_goal=nutrition_goal,
                travel_schedule=travel_schedule,
            )
            plan_id = _create_plan_from_dict(db, plan_data)
            for trip in travel_schedule:
                s = trip.get('start_date', '')
                e = trip.get('end_date', '')
                if s and e:
                    db.execute(
                        'INSERT INTO plan_travel (plan_id, start_date, end_date, locale, city) VALUES (?,?,?,?,?)',
                        (plan_id, s, e, trip.get('locale', 'hotel'), trip.get('city', ''))
                    )
            db.commit()
            _log_usage(usage, 'generate')
            flash(
                f'Plan "{plan_data["name"]}" generated with {len(plan_data.get("workouts", []))} workouts. '
                f'({usage.output_tokens} output tokens)',
                'success'
            )
            return redirect(url_for('plans.view_plan', plan_id=plan_id))
        except json.JSONDecodeError as e:
            flash(f'Claude returned invalid JSON: {e}', 'danger')
        except Exception as e:
            flash(f'Generation failed: {e}', 'danger')

    # Suggest a start date: day after most recent plan ends, or today
    suggested_start = date.today().isoformat()
    if plans:
        latest_end = plans[0]['end_date']
        if latest_end:
            try:
                suggested_start = (date.fromisoformat(latest_end) + timedelta(days=1)).isoformat()
            except ValueError:
                pass

    return render_template('coaching/generate.html',
                           plans=plans,
                           suggested_start=suggested_start,
                           locales=LOCALES,
                           api_configured=_check_api_key())


@bp.route('/review/<int:plan_id>', methods=['GET', 'POST'])
def review(plan_id):
    db = get_db()
    plan = db.execute('SELECT * FROM training_plans WHERE id=?', (plan_id,)).fetchone()
    if not plan:
        flash('Plan not found.', 'danger')
        return redirect(url_for('plans.list_plans'))

    from routes.plans import _plan_health
    health = _plan_health(db, plan_id)

    if request.method == 'POST':
        tier = int(request.form.get('tier', 1))
        notes = request.form.get('notes', '').strip()
        locale = request.form.get('locale', 'home')
        if locale not in LOCALES:
            locale = 'home'

        if not _check_api_key():
            flash('ANTHROPIC_API_KEY is not configured.', 'danger')
            return redirect(url_for('coaching.review', plan_id=plan_id))

        try:
            from coaching import run_review
            result, usage = run_review(db, plan_id, tier, notes=notes, locale=locale)
            _log_usage(usage, f'review_t{tier}')

            if tier == 3:
                # result is a new plan dict
                from routes.plans import _create_plan_from_dict
                new_plan_id = _create_plan_from_dict(db, result)
                db.execute(
                    'INSERT INTO plan_reviews (plan_id, tier, sessions_reviewed, notes) VALUES (?,?,?,?)',
                    (plan_id, tier, health['sessions_since_tier1'],
                     f'Tier 3 review — new plan {new_plan_id} generated. {notes}')
                )
                db.commit()
                flash(
                    f'Next block generated: "{result.get("name")}" '
                    f'({len(result.get("workouts", []))} workouts, {usage.output_tokens} tokens).',
                    'success'
                )
                return redirect(url_for('plans.view_plan', plan_id=new_plan_id))

            else:
                # result is a list of patch dicts
                patches = result if isinstance(result, list) else []
                applied = 0
                for patch in patches:
                    item_id = patch.pop('item_id', None)
                    if not item_id or not patch:
                        continue
                    allowed = {'description', 'intensity', 'target_duration_min',
                               'target_distance_mi', 'notes', 'workout_name',
                               'calorie_target', 'macro_carb_pct', 'macro_protein_pct',
                               'macro_fat_pct', 'session_fueling'}
                    updates = {k: v for k, v in patch.items() if k in allowed}
                    if updates:
                        set_clause = ', '.join(f'{k}=?' for k in updates)
                        db.execute(
                            f'UPDATE plan_items SET {set_clause} WHERE id=? AND plan_id=?',
                            list(updates.values()) + [item_id, plan_id]
                        )
                        applied += 1

                db.execute(
                    'INSERT INTO plan_reviews (plan_id, tier, sessions_reviewed, notes) VALUES (?,?,?,?)',
                    (plan_id, tier, health['sessions_since_tier1'],
                     f'Tier {tier} review — {applied} items patched. {notes}')
                )
                db.commit()
                flash(
                    f'Tier {tier} review complete — {applied} workouts updated '
                    f'({usage.output_tokens} tokens).',
                    'success'
                )
                return redirect(url_for('plans.view_plan', plan_id=plan_id))

        except json.JSONDecodeError as e:
            flash(f'Claude returned invalid JSON: {e}', 'danger')
        except Exception as e:
            flash(f'Review failed: {e}', 'danger')

    return render_template('coaching/review.html', plan=plan, health=health,
                           locales=LOCALES,
                           api_configured=_check_api_key())


@bp.route('/api/generate', methods=['POST'])
def api_generate():
    """Headless plan generation for remote control."""
    if not _check_api_key():
        return jsonify({'ok': False, 'error': 'ANTHROPIC_API_KEY not configured'}), 500
    data = request.get_json(silent=True) or {}
    start_date = data.get('start_date', date.today().isoformat())
    weeks = int(data.get('weeks', 4))
    notes = data.get('notes', '')
    race_name = data.get('race_name', '')
    race_date = data.get('race_date', '')
    race_location = data.get('race_location', '')
    race_disciplines = data.get('race_disciplines', '')
    race_duration = data.get('race_duration', '')
    race_website = data.get('race_website', '')
    try:
        db = get_db()
        from coaching import generate_plan
        from routes.plans import _create_plan_from_dict
        plan_data, usage = generate_plan(
            db, start_date, weeks=weeks, notes=notes,
            race_name=race_name, race_date=race_date, race_location=race_location,
            race_disciplines=race_disciplines, race_duration=race_duration,
            race_website=race_website,
        )
        plan_id = _create_plan_from_dict(db, plan_data)
        db.commit()
        return jsonify({
            'ok': True,
            'plan_id': plan_id,
            'name': plan_data.get('name'),
            'workouts': len(plan_data.get('workouts', [])),
            'tokens': {'input': usage.input_tokens, 'output': usage.output_tokens,
                       'cache_read': usage.cache_read_input_tokens,
                       'cache_write': usage.cache_creation_input_tokens},
        })
    except Exception as e:
        return jsonify({'ok': False, 'error': str(e)}), 500


@bp.route('/api/review', methods=['POST'])
def api_review():
    """Headless plan review for remote control."""
    if not _check_api_key():
        return jsonify({'ok': False, 'error': 'ANTHROPIC_API_KEY not configured'}), 500
    data = request.get_json(silent=True) or {}
    plan_id = data.get('plan_id')
    tier = int(data.get('tier', 1))
    notes = data.get('notes', '')
    if not plan_id:
        return jsonify({'ok': False, 'error': 'plan_id required'}), 400
    try:
        db = get_db()
        from coaching import run_review
        from routes.plans import _plan_health
        result, usage = run_review(db, plan_id, tier, notes=notes)
        health = _plan_health(db, plan_id)

        if tier == 3:
            from routes.plans import _create_plan_from_dict
            new_plan_id = _create_plan_from_dict(db, result)
            db.execute(
                'INSERT INTO plan_reviews (plan_id, tier, sessions_reviewed, notes) VALUES (?,?,?,?)',
                (plan_id, tier, health['sessions_since_tier1'], notes)
            )
            db.commit()
            return jsonify({'ok': True, 'tier': 3, 'new_plan_id': new_plan_id,
                            'name': result.get('name'),
                            'tokens': {'output': usage.output_tokens}})
        else:
            patches = result if isinstance(result, list) else []
            applied = 0
            for patch in patches:
                item_id = patch.pop('item_id', None)
                if not item_id or not patch:
                    continue
                allowed = {'description', 'intensity', 'target_duration_min',
                           'target_distance_mi', 'notes', 'workout_name'}
                updates = {k: v for k, v in patch.items() if k in allowed}
                if updates:
                    set_clause = ', '.join(f'{k}=?' for k in updates)
                    db.execute(
                        f'UPDATE plan_items SET {set_clause} WHERE id=? AND plan_id=?',
                        list(updates.values()) + [item_id, plan_id]
                    )
                    applied += 1
            db.execute(
                'INSERT INTO plan_reviews (plan_id, tier, sessions_reviewed, notes) VALUES (?,?,?,?)',
                (plan_id, tier, health['sessions_since_tier1'], notes)
            )
            db.commit()
            return jsonify({'ok': True, 'tier': tier, 'patches_applied': applied,
                            'tokens': {'output': usage.output_tokens}})
    except Exception as e:
        return jsonify({'ok': False, 'error': str(e)}), 500


def _check_api_key():
    return bool(os.environ.get('ANTHROPIC_API_KEY'))


@bp.route('/chat/<int:plan_id>', methods=['GET', 'POST'])
def chat(plan_id):
    db = get_db()
    plan = db.execute('SELECT * FROM training_plans WHERE id=?', (plan_id,)).fetchone()
    if not plan:
        return jsonify({'ok': False, 'error': 'Plan not found'}), 404

    if request.method == 'GET':
        rows = db.execute(
            'SELECT role, content, actions_json, created_at FROM coaching_chat WHERE plan_id=? ORDER BY created_at ASC',
            (plan_id,)
        ).fetchall()
        return jsonify([dict(r) for r in rows])

    data = request.get_json(silent=True) or {}
    message = data.get('message', '').strip()
    locale = data.get('locale', 'home')
    if not message:
        return jsonify({'ok': False, 'error': 'message required'}), 400
    if not _check_api_key():
        return jsonify({'ok': False, 'error': 'ANTHROPIC_API_KEY not configured'}), 500

    history = [{'role': r['role'], 'content': r['content']} for r in db.execute(
        'SELECT role, content FROM coaching_chat WHERE plan_id=? ORDER BY created_at ASC',
        (plan_id,)
    ).fetchall()]

    try:
        from coaching import chat_with_coach
        result, usage = chat_with_coach(db, plan_id, message, history, locale=locale)
        _log_usage(usage, 'chat')

        db.execute(
            'INSERT INTO coaching_chat (plan_id, role, content) VALUES (?,?,?)',
            (plan_id, 'user', message)
        )

        for pref in result.get('preferences_to_save', []):
            db.execute(
                'INSERT INTO coaching_preferences (category, content, permanent) VALUES (?,?,?)',
                (pref.get('category', 'general'), pref['content'], 1 if pref.get('permanent', True) else 0)
            )

        patches_applied = 0
        if not result.get('confirm_required', False):
            allowed = {'description', 'intensity', 'target_duration_min', 'target_distance_mi', 'notes', 'workout_name',
                       'calorie_target', 'macro_carb_pct', 'macro_protein_pct', 'macro_fat_pct', 'session_fueling'}
            for patch in result.get('plan_patches', []):
                item_id = patch.get('item_id')
                updates = {k: v for k, v in patch.items() if k in allowed and v is not None}
                if item_id and updates:
                    set_clause = ', '.join(f'{k}=?' for k in updates)
                    db.execute(
                        f'UPDATE plan_items SET {set_clause} WHERE id=? AND plan_id=?',
                        list(updates.values()) + [item_id, plan_id]
                    )
                    patches_applied += 1

        import json as _json
        db.execute(
            'INSERT INTO coaching_chat (plan_id, role, content, actions_json) VALUES (?,?,?,?)',
            (plan_id, 'assistant', result.get('message', ''), _json.dumps({
                'preferences_saved': len(result.get('preferences_to_save', [])),
                'patches_applied': patches_applied,
                'confirm_required': result.get('confirm_required', False),
                'pending_patches': result.get('plan_patches', []) if result.get('confirm_required') else [],
            }))
        )
        db.commit()

        return jsonify({
            'ok': True,
            'message': result.get('message', ''),
            'preferences_saved': len(result.get('preferences_to_save', [])),
            'patches_applied': patches_applied,
            'confirm_required': result.get('confirm_required', False),
            'pending_patches': result.get('plan_patches', []) if result.get('confirm_required') else [],
        })
    except Exception as e:
        return jsonify({'ok': False, 'error': str(e)}), 500


@bp.route('/preferences', methods=['GET'])
def preferences():
    db = get_db()
    rows = db.execute(
        'SELECT id, category, content, permanent, created_at FROM coaching_preferences ORDER BY created_at DESC'
    ).fetchall()
    return jsonify([dict(r) for r in rows])


@bp.route('/preferences/<int:pref_id>/delete', methods=['POST'])
def delete_preference(pref_id):
    db = get_db()
    db.execute('DELETE FROM coaching_preferences WHERE id=?', (pref_id,))
    db.commit()
    return jsonify({'ok': True})


def _log_usage(usage, label):
    print(f'[coaching:{label}] in={usage.input_tokens} out={usage.output_tokens} '
          f'cache_read={usage.cache_read_input_tokens} '
          f'cache_write={usage.cache_creation_input_tokens}')


import os
