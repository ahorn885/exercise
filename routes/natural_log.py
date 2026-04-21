"""Natural language workout logging — interprets free-text descriptions via Claude."""
import json
import os
from datetime import date, timedelta

from flask import Blueprint, render_template, request, jsonify
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
- Strength sessions: tell the user to use the Session Logger instead; do not create a "strength" entry

## Date rules
- Default to today unless the user says "yesterday", "last night", "this morning" etc.
- "This morning" / "earlier today" = today
- "Yesterday" / "last night" = yesterday
- Use ISO format YYYY-MM-DD

Today: {today}
"""


def _check_api_key():
    return bool(os.environ.get('ANTHROPIC_API_KEY'))


def _load_scheduled(db):
    """Today's and yesterday's scheduled plan items for plan-linking context."""
    today = date.today().isoformat()
    yesterday = (date.today() - timedelta(days=1)).isoformat()
    rows = db.execute(
        '''SELECT pi.id, pi.item_date, pi.sport_type, pi.workout_name, pi.description,
                  pi.target_duration_min, pi.target_distance_mi, pi.intensity,
                  tp.name as plan_name
           FROM plan_items pi
           JOIN training_plans tp ON tp.id = pi.plan_id
           WHERE pi.status = 'scheduled' AND pi.item_date IN (?, ?)
             AND tp.status != 'archived'
           ORDER BY pi.item_date DESC''',
        (today, yesterday)
    ).fetchall()
    return [dict(r) for r in rows]


def _build_system(scheduled):
    today = date.today().isoformat()
    text = _SYSTEM.replace('{today}', today)
    if scheduled:
        lines = ['\n\n## Scheduled workouts (today / yesterday) — use for plan matching']
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
    system_text = _build_system(scheduled)

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
            saved.append({'type': 'cardio', 'id': cur.lastrowid,
                          'redirect': '/cardio'})

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

    db.commit()
    return jsonify({'ok': True, 'saved': saved})
