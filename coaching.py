"""
Claude API coaching integration.
Embeds ar-coaching, ar-nutrition, and ar-substitution skill content as a cached
system prompt, then generates or adjusts training plans via the Anthropic API.

Set ANTHROPIC_API_KEY in the environment. Optionally set CLAUDE_MODEL to override
the default (claude-opus-4-7).
"""
import json
import os
from datetime import date, timedelta

import anthropic

# ── Embedded skill content (static — cached with 1h TTL) ─────────────────────

_SYSTEM_PROMPT = """You are an expert adventure racing coach for Andy. You have deep knowledge of his training framework, current situation, and preferences. Apply this knowledge precisely when generating or adjusting plans.

---

# AR Coaching Framework

## Target Race
Race details are provided per plan generation request. Apply the periodization structure below relative to the race date provided.

## Periodization
Phases are relative to weeks-until-race-day. Compute actual dates from the race date and plan start date provided in the request.

| Phase | Weeks out | Focus | Peak Vol |
|-------|-----------|-------|----------|
| 1 Base | 15–12 | Aerobic foundation, movement patterns | ~18 hrs |
| 2 Build | 11–8 | Volume increase, bricks, strength up | ~26 hrs |
| 3 Peak | 7–4 | Max load, bricks, race simulation | ~33 hrs |
| 4 Taper | 3–2 | Volume -35→50%, maintain intensity | ~14→10 hrs |
| Race | 1 | Sharpening, travel, race | ~6 hrs + race |

Cutback weeks: every 4th week of training — reduce volume ~30%, no deep fatigue.

## Weekly Structure
- Monday: Rest (mandatory)
- 2 disciplines/day when possible (avoid kayak + MTB same day)
- Saturday: Long hike (scales: 4→5→6→cutback→5.5→6.5→7→cutback→7→7→7.5→8→cutback→6→4.5→3→2→race hrs)
- Road bike acceptable MTB substitute in training
- Partner home: limit hikes <2 hrs; prioritize cycling (1st) or running (2nd)
- Variety is critical — never repeat identical sessions week to week

## Progression Rules
- Compounds (squat, DL, row): +5 lb per progression
- Rotation/accessories: +2.5 lb per progression
- Bodyweight: +reps; Plyometrics: +sets
- If RPE > target by 2+ consistently: hold weight
- Peak compound targets (Phase 3): Squat ~205, DL ~235, Weighted pull-up +40 lb, Row ~135

## Climbing Progression Ladder
Grip-dominant only — NO wrist-loaded moves.
| Phase | Dead Hang | Lock-Off | One-Arm Assist | Extras |
|-------|-----------|----------|----------------|--------|
| 1 | 4-5×30-40s | 4×10-12s @90° | 3×15s/arm | Eccentrics, grip trainer, reverse wrist curl |
| 2 | 5×40-45s | 5×12-15s | 4×20-25s/arm | Explosive pull-ups, campus pulls |
| 3 | 5-6×50-55s | Circuit 90°/120°/175° | 5×25-35s/arm | Abseiling sim, double-hand bar locks |
| 4 | 3-4×35-40s | 3×10s | 3×20s/arm | Maintenance only |
Antagonist work every climbing session: push-ups + reverse wrist curls.

## Strength Programming
- Home gym: Olympic bar, KBs, DBs, bands, grip trainers
- Always include: farmer's carries, Turkish get-ups, KB swings
- Single-leg work every lower session
- Area is flat — use treadmill incline, trainer elevation, step-ups for simulation

## Core Circuits (rotate for variety)
- A (General): Plank, dead bug, mountain climber, hollow body, bird-dog, superman
- B (Paddle): Russian twist, Pallof press, wood chop, hanging knee raise, bicycle crunch, V-sit
- C (Climbing): L-sit, hanging knee raise, ab wheel, side plank w/ hip abduction, compression tuck

## Brick Sessions (Phase 2+)
- Bike→Run, Bike→Paddle, Bike→Run→Paddle (Phase 3 mega-bricks)
- Always time transitions — target <5 min

---

# Nutrition Guidelines

## Calorie Targets by Day Type
| Day Type | Calories | Carb | Protein | Fat |
|----------|----------|------|---------|-----|
| Rest | 2800–2900 | 45% | 29% | 24% |
| Moderate (<90 min) | 3000–3200 | 54% | 25% | 21% |
| Hard (2 sessions or >90 min) | 3400–3800 | 58% | 22% | 20% |
| Heavy (bricks, >3 hrs) | 3900–4500 | 62% | 19% | 19% |
| Long hike (5+ hrs) | 4700–6200 | 64% | 17% | 19% |

## Daily Supplements
Creatine 5g (morning), Omega-3 2-3g, Vitamin D3 2000 IU, Magnesium Glycinate 400mg (pre-bed), Multivitamin.

## Session Fueling
- <60 min: water only
- 60-90 min: 30-40g carbs/hr, 400-500ml fluid/hr
- 90+ min: 50-60g carbs/hr, 500-600ml fluid/hr, 500mg Na/hr
- 3+ hrs: add BCAAs; tart cherry 30ml post-session

---

# Substitution Rules

## Active Injury: Left Wrist
Pain/weakness with wrist extension. Hard rules:
- NO standard push-ups (flat palm) — use fist/knuckle push-ups only
- NO front squats with clean grip — use goblet or cross-arm
- NO barbell curls with wrist extension — use hammer or neutral-grip curls
- Climbing: grip-dominant moves OK; wrist-loaded moves NOT OK
- Reverse wrist curls allowed at light weight (10 lb) — therapeutic

## Hotel Gym Substitutions
Barbell → Dumbbell: Back squat→Goblet squat, DL→DB RDL, Barbell row→Single-arm DB row
KB → DB: KB swing→DB swing (goblet grip), TGU→DB get-up
Cardio: Road bike→Stationary bike, Trail run→Treadmill with incline variation, Kayak→Band pull simulation
Hiking: Treadmill 10-15% incline with weighted vest, extend duration

## General Principles
1. Match movement pattern (push for push, pull for pull, hinge for hinge)
2. Match or exceed volume — if load drops, add reps or sets
3. Preserve intent — grip endurance work shouldn't be subbed with push exercises
4. When in doubt: bodyweight circuits at high rep counts beats skipping

---

# Equipment Available
Road bike, mountain bike, cycling trainer, treadmill, kayak, paddling ergometer, home gym (Olympic weights, KBs, DBs, grip trainers, bands). Multiple outdoor trails (MTB, hike, run), rivers/lakes, road routes.
"""


# ── Context gathering ─────────────────────────────────────────────────────────

def get_coaching_context(db, plan_id=None, lookback_days=14):
    """Gather all training context for Claude. Returns a dict."""
    ctx = {'today': date.today().isoformat()}

    # Active injuries
    injuries = db.execute(
        "SELECT start_date, body_part, description, severity, status FROM injury_log "
        "WHERE status IN ('Active','Managing') ORDER BY start_date DESC"
    ).fetchall()
    ctx['active_injuries'] = [dict(i) for i in injuries]

    # Injury modifications
    try:
        mods = db.execute(
            '''SELECT iem.modification_type, iem.modification_notes,
                      il.body_part, ei.exercise as exercise_name,
                      ei_sub.exercise as substitute_name
               FROM injury_exercise_modifications iem
               JOIN injury_log il ON il.id = iem.injury_id
               JOIN exercise_inventory ei ON ei.id = iem.exercise_id
               LEFT JOIN exercise_inventory ei_sub ON ei_sub.id = iem.substitute_exercise_id
               WHERE il.status IN ('Active','Managing')'''
        ).fetchall()
        ctx['injury_modifications'] = [dict(m) for m in mods]
    except Exception:
        ctx['injury_modifications'] = []

    # Current Rx (top 25 by last performed)
    rx = db.execute(
        '''SELECT exercise, current_sets, current_reps, current_weight,
                  next_sets, next_reps, next_weight, last_performed, last_outcome
           FROM current_rx
           ORDER BY last_performed DESC
           LIMIT 25'''
    ).fetchall()
    ctx['current_rx'] = [dict(r) for r in rx]

    # Recent training log
    cutoff = (date.today() - timedelta(days=lookback_days)).isoformat()
    training = db.execute(
        '''SELECT date, exercise, actual_sets, actual_reps, actual_weight,
                  rpe, outcome, notes
           FROM training_log
           WHERE date >= ?
           ORDER BY date DESC
           LIMIT 60''',
        (cutoff,)
    ).fetchall()
    ctx['recent_training'] = [dict(t) for t in training]

    # Recent cardio
    cardio = db.execute(
        '''SELECT date, activity, activity_name, duration_min, distance_mi,
                  avg_hr, avg_pace, avg_power, notes
           FROM cardio_log
           WHERE date >= ?
           ORDER BY date DESC
           LIMIT 25''',
        (cutoff,)
    ).fetchall()
    ctx['recent_cardio'] = [dict(c) for c in cardio]

    # Latest body metrics
    metrics = db.execute(
        'SELECT date, weight_lbs, body_fat_pct, vo2_max, resting_hr FROM body_metrics '
        'ORDER BY date DESC LIMIT 1'
    ).fetchone()
    ctx['body_metrics'] = dict(metrics) if metrics else {}

    # Plan health if plan_id given
    if plan_id:
        try:
            from routes.plans import _plan_health
            ctx['plan_health'] = _plan_health(db, plan_id)
        except Exception:
            pass

    return ctx


# ── Claude API calls ──────────────────────────────────────────────────────────

_PLAN_SCHEMA_INSTRUCTIONS = """Return ONLY a JSON object (no markdown fences, no explanation) matching exactly:
{
  "name": "string",
  "description": "string",
  "sport_focus": "hybrid",
  "start_date": "YYYY-MM-DD",
  "end_date": "YYYY-MM-DD",
  "workouts": [
    {
      "date": "YYYY-MM-DD",
      "sport_type": "running|cycling|strength_training|hiking|swimming|walking",
      "workout_name": "string",
      "description": "Full workout details including exercises, sets, reps, weights, durations. Be specific.",
      "target_duration_min": number_or_null,
      "target_distance_mi": number_or_null,
      "intensity": "easy|moderate|hard|very_hard"
    }
  ]
}
Skip rest days (Monday is always rest — omit it). Include every other day."""


def _get_client():
    key = os.environ.get('ANTHROPIC_API_KEY')
    if not key:
        raise RuntimeError('ANTHROPIC_API_KEY environment variable not set.')
    return anthropic.Anthropic(api_key=key)


def _model():
    return os.environ.get('CLAUDE_MODEL', 'claude-opus-4-7')


def _cached_system():
    return [{'type': 'text', 'text': _SYSTEM_PROMPT,
             'cache_control': {'type': 'ephemeral', 'ttl': '1h'}}]


def _parse_json_response(text):
    """Strip markdown fences if present and parse JSON."""
    t = text.strip()
    if t.startswith('```'):
        t = t.split('```', 1)[1]
        if t.startswith('json'):
            t = t[4:]
        t = t.rsplit('```', 1)[0]
    return json.loads(t.strip())


def generate_plan(db, start_date: str, weeks: int = 4, notes: str = '',
                  race_name: str = '', race_date: str = '', race_location: str = '',
                  race_disciplines: str = '', race_duration: str = '',
                  race_website: str = '') -> tuple:
    """
    Generate a new training plan block.
    Returns (plan_dict, usage) where plan_dict matches _create_plan_from_dict schema.
    """
    client = _get_client()
    ctx = get_coaching_context(db)

    race_section = f"""## Target Race
- Event: {race_name or 'Not specified'}
- Date: {race_date or 'Not specified'}
- Location: {race_location or 'Not specified'}
- Disciplines: {race_disciplines or 'Not specified'}
- Expected duration: {race_duration or 'Not specified'}
- Website: {race_website or 'Not specified'}"""

    user_msg = f"""Generate a {weeks}-week training plan block starting {start_date}.

{race_section}

Determine the correct training phase based on start date vs race date above.
Apply the periodization structure, weekly layout preferences, climbing ladder, and variety rules from your coaching framework.
Tailor discipline emphasis to the race disciplines listed above.

## Current Training Context
{json.dumps(ctx, indent=2, default=str)}

## Coach Notes
{notes or 'None'}

## Output
{_PLAN_SCHEMA_INSTRUCTIONS}"""

    with client.messages.stream(
        model=_model(),
        max_tokens=16000,
        system=_cached_system(),
        messages=[{'role': 'user', 'content': user_msg}]
    ) as stream:
        response = stream.get_final_message()

    text = next((b.text for b in response.content if b.type == 'text'), '')
    plan = _parse_json_response(text)
    return plan, response.usage


def run_review(db, plan_id: int, tier: int, notes: str = '') -> tuple:
    """
    Run a tier 1/2/3 coaching review.

    Tier 1 (session check): returns list of patch dicts
    Tier 2 (weekly): returns list of patch dicts
    Tier 3 (next block): returns new plan dict

    Returns (result, usage).
    """
    client = _get_client()
    lookback = {1: 7, 2: 14, 3: 30}.get(tier, 14)
    ctx = get_coaching_context(db, plan_id=plan_id, lookback_days=lookback)

    if tier == 3:
        # Get current plan end date for next block start
        from database import get_db
        plan = get_db().execute(
            'SELECT end_date FROM training_plans WHERE id=?', (plan_id,)
        ).fetchone()
        next_start = plan['end_date'] if plan else date.today().isoformat()

        instructions = f"""TIER 3 — Next Block Generation.
The current plan is nearly complete (≤7 sessions remain).
Generate a new 4-week plan block starting the day after {next_start}.
Use the full training history below as context for progressive overload and volume scaling.

{_PLAN_SCHEMA_INSTRUCTIONS}"""
        max_tokens = 8000
    elif tier == 2:
        instructions = """TIER 2 — Weekly Review.
Analyze the last 2 weeks of training. Adjust upcoming scheduled workouts as needed.

Return ONLY a JSON array of patch operations (no markdown, no explanation):
[{"item_id": <integer plan_item_id>, "description": "...", "intensity": "...", "target_duration_min": ..., "notes": "..."}]

Only include fields that actually need changing. Return [] if no adjustments are needed.
The item_id values come from plan_health.upcoming_items in the context below."""
        max_tokens = 3000
    else:
        instructions = """TIER 1 — Session Check.
Review the most recent completed workout and adjust the next 1-2 scheduled sessions if RPE trends, fatigue, or missed sessions warrant it.

Return ONLY a JSON array of patch operations (no markdown, no explanation):
[{"item_id": <integer plan_item_id>, "description": "...", "intensity": "...", "notes": "..."}]

Only include fields that actually need changing. Return [] if no adjustments needed."""
        max_tokens = 2000

    user_msg = f"""## Coaching Review — Tier {tier}

{instructions}

## Training Context
{json.dumps(ctx, indent=2, default=str)}

## Coach Notes
{notes or 'None'}"""

    with client.messages.stream(
        model=_model(),
        max_tokens=max_tokens,
        system=_cached_system(),
        messages=[{'role': 'user', 'content': user_msg}]
    ) as stream:
        response = stream.get_final_message()

    text = next((b.text for b in response.content if b.type == 'text'), '')
    result = _parse_json_response(text)
    return result, response.usage
