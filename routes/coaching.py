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
        race_date = request.form.get('race_date', '').strip()

        # Weeks: numeric or "until_race" (compute from start → race date)
        weeks_raw = request.form.get('weeks', '4')
        if weeks_raw == 'until_race' and start_date and race_date:
            try:
                from datetime import date as _date
                delta = _date.fromisoformat(race_date) - _date.fromisoformat(start_date)
                weeks = max(1, delta.days // 7)
            except ValueError:
                weeks = 4
        else:
            try:
                weeks = int(weeks_raw)
            except (ValueError, TypeError):
                weeks = 4

        notes = request.form.get('notes', '').strip()
        race_name = request.form.get('race_name', '').strip()
        race_type = request.form.get('race_type', '').strip()
        race_location = request.form.get('race_location', '').strip()
        # Disciplines: collected as multi-select checkboxes, joined to string
        disciplines_list = request.form.getlist('disciplines')
        race_disciplines = ', '.join(disciplines_list) if disciplines_list else request.form.get('race_disciplines', '').strip()
        race_duration = request.form.get('race_duration', '').strip()
        race_website = request.form.get('race_website', '').strip()
        # Build race_goals from structured fields
        goal_finish = request.form.get('goal_finish_time', '').strip()
        goal_splits = request.form.get('goal_splits', '').strip()
        goal_checkpoints = request.form.get('goal_checkpoints', '').strip()
        race_goals_parts = []
        if goal_finish:
            race_goals_parts.append(f'Goal finish time: {goal_finish}')
        if goal_splits:
            race_goals_parts.append(f'Splits / pacing strategy:\n{goal_splits}')
        if goal_checkpoints:
            race_goals_parts.append(f'Checkpoint / Aid Station / TA goals:\n{goal_checkpoints}')
        race_goals = '\n\n'.join(race_goals_parts)
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
        try:
            weekly_hours = float(request.form.get('weekly_hours', 10))
        except (ValueError, TypeError):
            weekly_hours = 10.0
        rest_days = request.form.getlist('rest_days') or ['Monday']
        race_philosophy = request.form.get('race_philosophy', 'Compete')
        experience_level = request.form.get('experience_level', 'Intermediate')

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
                race_website=race_website, race_type=race_type, race_goals=race_goals,
                locale=locale, nutrition_goal=nutrition_goal,
                travel_schedule=travel_schedule,
                weekly_hours=weekly_hours,
                rest_days=rest_days,
                race_philosophy=race_philosophy,
                experience_level=experience_level,
            )
            plan_id = _create_plan_from_dict(db, plan_data)
            if race_goals:
                db.execute('UPDATE training_plans SET race_goals=? WHERE id=?', (race_goals, plan_id))
            for trip in travel_schedule:
                s = trip.get('start_date', '')
                e = trip.get('end_date', '')
                if s and e:
                    db.execute(
                        'INSERT INTO plan_travel (plan_id, start_date, end_date, locale, city, indoor_only) VALUES (?,?,?,?,?,?)',
                        (plan_id, s, e, trip.get('locale', 'hotel'), trip.get('city', ''),
                         1 if trip.get('indoor_only') else 0)
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

        # ── Pre-review actions (applied before the AI call) ──────────────────

        # 1. Locale updates
        try:
            locale_updates = json.loads(request.form.get('locale_updates', '[]'))
            if not isinstance(locale_updates, list):
                locale_updates = []
        except (json.JSONDecodeError, ValueError):
            locale_updates = []
        for trip in locale_updates:
            s = trip.get('start_date', '')
            e = trip.get('end_date', '')
            if s and e:
                db.execute(
                    'INSERT INTO plan_travel (plan_id, start_date, end_date, locale, city, indoor_only) VALUES (?,?,?,?,?,?)',
                    (plan_id, s, e, trip.get('locale', 'hotel'), trip.get('city', ''),
                     1 if trip.get('indoor_only') else 0)
                )

        # 2. Intensity adjustment — bulk-shift all remaining scheduled sessions
        difficulty = request.form.get('difficulty_feedback', 'just_right')
        adjust_intensity = bool(request.form.get('adjust_intensity'))
        intensity_direction = ''
        intensity_shifted = 0
        if adjust_intensity and difficulty in ('too_hard', 'too_easy'):
            intensity_direction = difficulty
            if difficulty == 'too_hard':
                sql = """UPDATE plan_items SET intensity = CASE intensity
                    WHEN 'very_hard' THEN 'hard'
                    WHEN 'hard' THEN 'moderate'
                    WHEN 'moderate' THEN 'easy'
                    ELSE intensity END
                    WHERE plan_id=? AND status='scheduled'"""
            else:
                sql = """UPDATE plan_items SET intensity = CASE intensity
                    WHEN 'easy' THEN 'moderate'
                    WHEN 'moderate' THEN 'hard'
                    WHEN 'hard' THEN 'very_hard'
                    ELSE intensity END
                    WHERE plan_id=? AND status='scheduled'"""
            db.execute(sql, (plan_id,))
            intensity_shifted = db.execute(
                "SELECT changes()"
            ).fetchone()[0]

        # 3. Race goals update
        race_goals_changed = bool(request.form.get('race_goals_changed'))
        current_race_goals = plan['race_goals'] if 'race_goals' in plan.keys() else ''
        if race_goals_changed:
            updated_goals = request.form.get('updated_race_goals', '').strip()
            if updated_goals:
                db.execute('UPDATE training_plans SET race_goals=? WHERE id=?', (updated_goals, plan_id))
                current_race_goals = updated_goals

        if not _check_api_key():
            flash('ANTHROPIC_API_KEY is not configured.', 'danger')
            return redirect(url_for('coaching.review', plan_id=plan_id))

        try:
            from coaching import run_review, capture_and_normalize_feedback
            # Capture review notes into the feedback pipeline before the AI call
            # so any extracted preferences are visible to run_review's context.
            if notes:
                capture_and_normalize_feedback(db, 'plan_review', notes, source_ref_id=plan_id)
                db.commit()
            result, usage = run_review(
                db, plan_id, tier, notes=notes, locale=locale,
                race_goals=current_race_goals, intensity_direction=intensity_direction,
            )
            _log_usage(usage, f'review_t{tier}')

            if tier == 3:
                from routes.plans import _create_plan_from_dict
                new_plan_id = _create_plan_from_dict(db, result)
                # Carry race_goals forward to the new plan
                if current_race_goals:
                    db.execute('UPDATE training_plans SET race_goals=? WHERE id=?',
                               (current_race_goals, new_plan_id))
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

                review_summary = f'Tier {tier} review — {applied} items patched'
                if intensity_shifted:
                    review_summary += f', intensity shifted {intensity_direction.replace("_", " ")} ({intensity_shifted} sessions)'
                if race_goals_changed:
                    review_summary += ', race goals updated'
                db.execute(
                    'INSERT INTO plan_reviews (plan_id, tier, sessions_reviewed, notes) VALUES (?,?,?,?)',
                    (plan_id, tier, health['sessions_since_tier1'], f'{review_summary}. {notes}')
                )
                db.commit()
                flash(
                    f'Tier {tier} review complete — {applied} workouts updated'
                    + (f', intensity shifted {intensity_direction.replace("_", " ")}' if intensity_shifted else '')
                    + f' ({usage.output_tokens} tokens).',
                    'success'
                )
                return redirect(url_for('plans.view_plan', plan_id=plan_id))

        except json.JSONDecodeError as e:
            flash(f'Claude returned invalid JSON: {e}', 'danger')
        except Exception as e:
            flash(f'Review failed: {e}', 'danger')

    current_race_goals = plan['race_goals'] if 'race_goals' in plan.keys() else ''
    return render_template('coaching/review.html', plan=plan, health=health,
                           locales=LOCALES, current_race_goals=current_race_goals,
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
    race_type = data.get('race_type', '')
    race_location = data.get('race_location', '')
    race_disciplines = data.get('race_disciplines', '')
    race_duration = data.get('race_duration', '')
    race_website = data.get('race_website', '')
    weekly_hours = float(data.get('weekly_hours', 10))
    rest_days = data.get('rest_days', ['Monday'])
    if isinstance(rest_days, str):
        rest_days = [rest_days]
    race_philosophy = data.get('race_philosophy', 'Compete')
    experience_level = data.get('experience_level', 'Intermediate')
    try:
        db = get_db()
        from coaching import generate_plan
        from routes.plans import _create_plan_from_dict
        plan_data, usage = generate_plan(
            db, start_date, weeks=weeks, notes=notes,
            race_name=race_name, race_date=race_date, race_location=race_location,
            race_disciplines=race_disciplines, race_duration=race_duration,
            race_website=race_website, race_type=race_type,
            weekly_hours=weekly_hours, rest_days=rest_days,
            race_philosophy=race_philosophy, experience_level=experience_level,
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


@bp.route('/clarify', methods=['POST'])
def clarify():
    """
    Lightweight pre-flight check: given free-form coach notes, decide whether
    clarifying questions are needed before running plan generation or review.
    Returns {needs_clarification: bool, questions: [str]}.
    """
    if not _check_api_key():
        return jsonify({'needs_clarification': False, 'questions': []})

    data = request.get_json(silent=True) or {}
    notes = (data.get('notes') or '').strip()
    context = data.get('context', 'coaching')  # 'generate' | 'review' | 'coaching'

    # Skip clarification for empty or very short clear inputs
    if len(notes) < 8:
        return jsonify({'needs_clarification': False, 'questions': []})

    context_desc = {
        'generate': 'generating a new multi-week training plan',
        'review': 'running a coaching review to adjust an existing training plan',
    }.get(context, 'providing coaching input')

    prompt = f"""A user is {context_desc}. They wrote this in the coach notes field:

"{notes}"

Your job: decide if this input has important ambiguities that would meaningfully affect the coaching output. If so, return up to 3 short, specific clarifying questions. If the input is clear enough to act on (even if brief), return no questions.

Only ask questions when the answer would change the plan or review in a concrete way. Do NOT ask for information the coach can reasonably infer or that doesn't affect the output.

Respond ONLY with a JSON object (no markdown):
{{"questions": ["question 1", "question 2"]}}

Return an empty array if no clarification is needed."""

    try:
        import anthropic
        client = anthropic.Anthropic(api_key=os.environ.get('ANTHROPIC_API_KEY'))
        msg = client.messages.create(
            model='claude-haiku-4-5-20251001',
            max_tokens=256,
            messages=[{'role': 'user', 'content': prompt}]
        )
        text = next((b.text for b in msg.content if b.type == 'text'), '{}')
        import json as _json
        parsed = _json.loads(text)
        questions = [q for q in parsed.get('questions', []) if isinstance(q, str) and q.strip()]
        return jsonify({'needs_clarification': bool(questions), 'questions': questions})
    except Exception:
        # On any error, silently skip clarification rather than blocking the user
        return jsonify({'needs_clarification': False, 'questions': []})


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
        from coaching import chat_with_coach, capture_feedback, save_preferences_from_feedback
        result, usage = chat_with_coach(db, plan_id, message, history, locale=locale)
        _log_usage(usage, 'chat')

        db.execute(
            'INSERT INTO coaching_chat (plan_id, role, content) VALUES (?,?,?)',
            (plan_id, 'user', message)
        )

        # Route the chat-extracted preferences through the feedback_log pipeline
        # so each pref carries provenance back to the user's raw message.
        fb_id = capture_feedback(db, 'chat', message, source_ref_id=plan_id)
        save_preferences_from_feedback(db, fb_id, result.get('preferences_to_save', []))

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
