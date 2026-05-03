"""Natural language workout logging — interprets free-text descriptions via Claude."""
import json
import os
from datetime import date, timedelta

from flask import Blueprint, render_template, request, jsonify, url_for
from database import get_db

bp = Blueprint('natural_log', __name__, url_prefix='/log-natural')

# ── Cardio activities the app supports ───────────────────────────────────────
CARDIO_ACTIVITIES = [
    'Running', 'Trail Running', 'Road Cycling', 'Mountain Biking', 'Gravel Cycling',
    'Indoor Bike Trainer', 'Hiking', 'Backpacking', 'Kayaking', 'Pack Rafting',
    'Kayak Ergometer', 'Rowing Ergometer', 'Swimming', 'Open Water Swimming',
    'Nordic Ski', 'Snowshoe', 'Walk', 'Elliptical', 'Stair Climber',
    'Treadmill', 'Climbing',
]

# ── System prompt (cached) ────────────────────────────────────────────────────
_SYSTEM = """\
You are a workout logging assistant for Andy's adventure racing training app.
Your job: interpret natural-language workout descriptions, extract structured data,
and ask targeted clarifying questions only when critical information is missing.

## Response format — always return valid JSON, nothing else

### When you need more information:
{"type": "clarify", "question": "Your single clarifying question here"}

### When you have enough to log:
{
  "type": "ready",
  "summary": "One-sentence confirmation of what will be logged",
  "entries": [...],
  "plan_match": null
}

## Entry schemas

Cardio entry:
{
  "log_type": "cardio",
  "activity": "<activity name>",
  "date": "YYYY-MM-DD",
  "duration_min": <number or null>,
  "distance_mi": <number or null>,
  "avg_pace": "<M:SS per mile string or null>",
  "avg_speed": <mph number or null>,
  "avg_hr": <bpm integer or null>,
  "max_hr": <bpm integer or null>,
  "elev_gain_ft": <feet integer or null>,
  "calories": <integer or null>,
  "avg_power": <watts integer or null>,
  "norm_power": <watts integer or null>,
  "aerobic_te": <0.0-5.0 or null>,
  "notes": ""
}

Body metrics entry:
{
  "log_type": "body",
  "date": "YYYY-MM-DD",
  "weight_lbs": <number or null>,
  "body_fat_pct": <number or null>,
  "resting_hr": <integer or null>,
  "vo2_max": <number or null>,
  "notes": ""
}

Strength session entry (one entry per session, may contain many exercises):
{
  "log_type": "strength",
  "date": "YYYY-MM-DD",
  "exercises": [
    {
      "exercise": "<must match a name from the strength exercise list below — pick closest>",
      "sets": [
        {"reps": <int or null>, "weight_lbs": <number or null>, "duration_sec": <int or null>}
      ],
      "rpe": <0.0-10.0 or null>,
      "notes": ""
    }
  ],
  "notes": ""
}

## Valid activity values (pick the closest match):
Running, Trail Running, Road Cycling, Mountain Biking, Gravel Cycling,
Indoor Bike Trainer, Hiking, Backpacking, Kayaking, Pack Rafting,
Kayak Ergometer, Rowing Ergometer, Swimming, Open Water Swimming,
Nordic Ski, Snowshoe, Walk, Elliptical, Stair Climber, Treadmill, Climbing

## Plan match (when scheduled workouts are provided below):
If the described workout clearly matches a scheduled plan item, populate:
{"plan_item_id": <id>, "workout_name": "<name>", "confidence": "high|medium", "reason": "<brief reason>"}
Otherwise set plan_match to null.

## Clarifying question rules
- Ask ONE question at a time, never multiple
- Ask for duration if completely unknown for a cardio entry
- Ask to disambiguate activity type if genuinely unclear (e.g. "a ride" — road or mountain?)
- Ask about plan linking only if you see a plausible match but can't be certain
- Do NOT ask about optional fields (HR, elevation, power, calories) — leave them null
- If duration was given in any form (time range, "about X", etc.) that's enough — estimate it
- Strength: build a single "strength" entry with exercises[] for the session. If the user
  gives a shorthand like "3x5 @ 185", expand it to 3 sets of {reps:5, weight_lbs:185}.
  If an exercise name doesn't match the list closely, ask which exercise they mean.

## Date rules
- Default to today unless the user says "yesterday", "last night", "this morning" etc.
- "This morning" / "earlier today" = today
- "Yesterday" / "last night" = yesterday
- Use ISO format YYYY-MM-DD

Today: {today}
"""


def _check_api_key():
    return bool(os.environ.get('ANTHROPIC_API_KEY'))


def _load_strength_exercises(db):
    """Names of strength exercises Andy currently uses, for prompt-side matching."""
    rows = db.execute(
        'SELECT exercise FROM current_rx ORDER BY exercise'
    ).fetchall()
    return [r['exercise'] for r in rows if r['exercise']]


def _load_scheduled(db):
    """Scheduled plan items from the past 7 days for plan-linking context."""
    today = date.today().isoformat()
    week_ago = (date.today() - timedelta(days=7)).isoformat()
    rows = db.execute(
        '''SELECT pi.id, pi.item_date, pi.sport_type, pi.workout_name, pi.description,
                  pi.target_duration_min, pi.target_distance_mi, pi.intensity,
                  tp.name as plan_name
           FROM plan_items pi
           JOIN training_plans tp ON tp.id = pi.plan_id
           WHERE pi.status = 'scheduled' AND pi.item_date BETWEEN ? AND ?
             AND tp.status != 'archived'
           ORDER BY pi.item_date DESC''',
        (week_ago, today)
    ).fetchall()
    return [dict(r) for r in rows]


def _build_system(scheduled, strength_exercises=None):
    today = date.today().isoformat()
    text = _SYSTEM.replace('{today}', today)
    if strength_exercises:
        text += '\n\n## Strength exercise list (match closest by name)\n'
        text += ', '.join(strength_exercises)
    if scheduled:
        lines = ['\n\n## Scheduled workouts (past 7 days) — use for plan matching']
        for s in scheduled:
            dur = f" {int(s['target_duration_min'])} min" if s.get('target_duration_min') else ''
            dist = f" / {s['target_distance_mi']} mi" if s.get('target_distance_mi') else ''
            lines.append(
                f"- ID {s['id']}: {s['item_date']} — {s['workout_name']}"
                f" ({s['sport_type']}){dur}{dist} — Plan: {s['plan_name']}"
            )
            if s.get('description'):
                lines.append(f"  Description: {s['description'][:200]}")
        text += '\n'.join(lines)
    return text


def _parse_json(text):
    t = text.strip()
    if t.startswith('```'):
        t = t.split('```', 1)[1]
        if t.startswith('json'):
            t = t[4:]
        t = t.rsplit('```', 1)[0]
    return json.loads(t.strip())


@bp.route('/')
def index():
    db = get_db()
    scheduled = _load_scheduled(db)
    return render_template('natural_log/index.html',
                           api_configured=_check_api_key(),
                           scheduled=scheduled,
                           today=date.today().isoformat())


@bp.route('/parse', methods=['POST'])
def parse():
    if not _check_api_key():
        return jsonify({'ok': False, 'error': 'ANTHROPIC_API_KEY not configured'}), 500

    data = request.get_json(silent=True) or {}
    message = data.get('message', '').strip()
    history = data.get('history', [])   # [{role, content}, ...]

    if not message:
        return jsonify({'ok': False, 'error': 'message required'}), 400

    db = get_db()
    scheduled = _load_scheduled(db)
    strength = _load_strength_exercises(db)
    system_text = _build_system(scheduled, strength)

    messages = [{'role': t['role'], 'content': t['content']} for t in history]
    messages.append({'role': 'user', 'content': message})

    try:
        import anthropic as _anthropic
        client = _anthropic.Anthropic(api_key=os.environ['ANTHROPIC_API_KEY'])
        model = os.environ.get('CLAUDE_MODEL', 'claude-opus-4-7')

        with client.messages.stream(
            model=model,
            max_tokens=1024,
            system=[{'type': 'text', 'text': system_text,
                     'cache_control': {'type': 'ephemeral', 'ttl': '1h'}}],
            messages=messages,
        ) as stream:
            reply = stream.get_final_message()

        text = reply.content[0].text.strip()
        parsed = _parse_json(text)

        return jsonify({
            'ok': True,
            'type': parsed.get('type'),
            'question': parsed.get('question'),
            'summary': parsed.get('summary'),
            'entries': parsed.get('entries', []),
            'plan_match': parsed.get('plan_match'),
        })
    except json.JSONDecodeError as e:
        return jsonify({'ok': False, 'error': f'Model returned invalid JSON: {e}'}), 500
    except Exception as e:
        return jsonify({'ok': False, 'error': str(e)}), 500


@bp.route('/save', methods=['POST'])
def save():
    data = request.get_json(silent=True) or {}
    entries = data.get('entries', [])
    plan_match = data.get('plan_match')
    history = data.get('history', [])

    db = get_db()
    saved = []

    for entry in entries:
        log_type = entry.get('log_type')

        if log_type == 'cardio':
            plan_item_id = plan_match.get('plan_item_id') if plan_match else None
            cur = db.execute(
                '''INSERT INTO cardio_log
                   (date, activity, duration_min, distance_mi, avg_pace, avg_speed,
                    avg_hr, max_hr, elev_gain_ft, calories, avg_power, norm_power,
                    aerobic_te, notes, plan_item_id)
                   VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)''',
                (
                    entry.get('date', date.today().isoformat()),
                    entry.get('activity', ''),
                    entry.get('duration_min'),
                    entry.get('distance_mi'),
                    entry.get('avg_pace'),
                    entry.get('avg_speed'),
                    entry.get('avg_hr'),
                    entry.get('max_hr'),
                    entry.get('elev_gain_ft'),
                    entry.get('calories'),
                    entry.get('avg_power'),
                    entry.get('norm_power'),
                    entry.get('aerobic_te'),
                    entry.get('notes', ''),
                    plan_item_id,
                )
            )
            new_id = cur.lastrowid
            saved.append({
                'type': 'cardio',
                'id': new_id,
                'redirect': '/cardio',
                'fit_url': url_for('cardio.activity_fit', entry_id=new_id),
            })

        elif log_type == 'strength':
            session_date = entry.get('date', date.today().isoformat())
            session_notes = entry.get('notes', '')
            plan_item_id = plan_match.get('plan_item_id') if plan_match else None

            cur = db.execute(
                'INSERT INTO training_sessions (date, notes, plan_item_id) VALUES (?, ?, ?)',
                (session_date, session_notes, plan_item_id)
            )
            session_id = cur.lastrowid

            body_wt_row = db.execute(
                'SELECT weight_lbs FROM body_metrics ORDER BY date DESC LIMIT 1'
            ).fetchone()
            body_weight = body_wt_row['weight_lbs'] if body_wt_row else None

            for ex_data in entry.get('exercises', []):
                exercise = (ex_data.get('exercise') or '').strip()
                if not exercise:
                    continue
                sets = ex_data.get('sets') or []

                ei = db.execute(
                    'SELECT id FROM exercise_inventory WHERE exercise=?', (exercise,)
                ).fetchone()
                exercise_id = ei['id'] if ei else None
                rx = db.execute(
                    'SELECT movement_pattern FROM current_rx WHERE exercise=?', (exercise,)
                ).fetchone()
                movement_pattern = rx['movement_pattern'] if rx else None

                actual_sets = len(sets)
                last_reps = sets[-1].get('reps') if sets else None
                weights = [s.get('weight_lbs') or 0 for s in sets]
                max_weight = max(weights) if weights and max(weights) > 0 else None
                last_duration = sets[-1].get('duration_sec') if sets else None
                volume = sum((s.get('reps') or 0) * (s.get('weight_lbs') or 0) for s in sets) or None

                log_cur = db.execute(
                    '''INSERT INTO training_log
                       (date, exercise, exercise_id, sub_group, session_id,
                        actual_sets, actual_reps, actual_weight, actual_duration,
                        rpe, volume, body_weight, plan_item_id, notes)
                       VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)''',
                    (session_date, exercise, exercise_id, movement_pattern, session_id,
                     actual_sets, last_reps, max_weight, last_duration,
                     ex_data.get('rpe'), volume, body_weight,
                     plan_item_id, ex_data.get('notes', ''))
                )
                log_id = log_cur.lastrowid

                for i, s in enumerate(sets, start=1):
                    db.execute(
                        '''INSERT INTO training_log_sets
                           (training_log_id, set_number, reps, weight_lbs, duration_sec)
                           VALUES (?,?,?,?,?)''',
                        (log_id, s.get('set_number') or i,
                         s.get('reps'), s.get('weight_lbs'), s.get('duration_sec'))
                    )

            saved.append({'type': 'strength', 'id': session_id, 'redirect': '/training'})

        elif log_type == 'body':
            db.execute(
                '''INSERT OR REPLACE INTO body_metrics
                   (date, weight_lbs, body_fat_pct, resting_hr, vo2_max, notes)
                   VALUES (?,?,?,?,?,?)''',
                (
                    entry.get('date', date.today().isoformat()),
                    entry.get('weight_lbs'),
                    entry.get('body_fat_pct'),
                    entry.get('resting_hr'),
                    entry.get('vo2_max'),
                    entry.get('notes', ''),
                )
            )
            saved.append({'type': 'body', 'redirect': '/body'})

    if plan_match and plan_match.get('plan_item_id') and saved:
        db.execute(
            "UPDATE plan_items SET status='completed' WHERE id=? AND status='scheduled'",
            (plan_match['plan_item_id'],)
        )

    # Capture the user's natural-language messages as feedback so any durable
    # preferences ("never log a swim again", "always treat 8.5 RPE as hard")
    # get normalized into coaching_preferences with provenance.
    user_text = '\n'.join(
        (t.get('content') or '').strip()
        for t in history
        if isinstance(t, dict) and t.get('role') == 'user' and (t.get('content') or '').strip()
    )
    if user_text and saved:
        from coaching import capture_and_normalize_feedback
        first_id = next((s.get('id') for s in saved if s.get('id')), None)
        capture_and_normalize_feedback(db, 'natural_log', user_text, source_ref_id=first_id)

    db.commit()
    return jsonify({'ok': True, 'saved': saved})
