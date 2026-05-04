"""
Claude API coaching integration.
Sport-adaptive system prompt (base + per-sport module), extended context,
and plan generation/review via the Anthropic API.

Set ANTHROPIC_API_KEY in the environment. Optionally set CLAUDE_MODEL to override
the default (claude-opus-4-7).
"""
import json
import os
from datetime import date, timedelta

import anthropic
import requests

# ── Base system prompt (generic, always included) ─────────────────────────────

_BASE_PROMPT = """You are an expert endurance sports coach. You have deep knowledge of the athlete's training framework, current situation, and preferences. Apply this knowledge precisely when generating or adjusting plans.

---

# Coaching Framework

## Target Race
Race details are provided per plan generation request. Apply the periodization structure below relative to the race date provided.

## Periodization
Phases are relative to weeks-until-race-day. Compute actual dates from the race date and plan start date provided in the request.

| Phase | Weeks out | Focus | Peak Vol |
|-------|-----------|-------|----------|
| 1 Base | 15–12 | Aerobic foundation, movement patterns | ~18 hrs |
| 2 Build | 11–8 | Volume increase, sport-specific work, strength up | ~26 hrs |
| 3 Peak | 7–4 | Max load, race simulation | ~33 hrs |
| 4 Taper | 3–2 | Volume -35→50%, maintain intensity | ~14→10 hrs |
| Race | 1 | Sharpening, travel, race | ~6 hrs + race |

Cutback weeks: every 4th week of training — reduce volume ~30%, no deep fatigue.

## Progression Rules
- Compounds (squat, DL, row): +5 lb per progression
- Rotation/accessories: +2.5 lb per progression
- Bodyweight: +reps; Plyometrics: +sets
- If RPE > target by 2+ consistently: hold weight
- Variety is critical — never repeat identical sessions week to week

## Substitution Rules

### Injury Substitutions
Active injuries and required modifications are provided per request from the training database. Always apply them strictly.

### Hotel Gym Substitutions
Barbell → Dumbbell: Back squat→Goblet squat, DL→DB RDL, Barbell row→Single-arm DB row
KB → DB: KB swing→DB swing (goblet grip), TGU→DB get-up
Cardio: Road bike→Stationary bike, Trail run→Treadmill with incline variation, Kayak→Band pull simulation
Hiking: Treadmill 10-15% incline with weighted vest, extend duration

### General Principles
1. Match movement pattern (push for push, pull for pull, hinge for hinge)
2. Match or exceed volume — if load drops, add reps or sets
3. Preserve intent — grip endurance work shouldn't be subbed with push exercises
4. When in doubt: bodyweight circuits at high rep counts beats skipping

---

# Nutrition Guidelines

## Session Fueling
- <60 min: water only
- 60-90 min: 30-40g carbs/hr, 400-500ml fluid/hr
- 90+ min: 50-60g carbs/hr, 500-600ml fluid/hr, 500mg Na/hr
- 3+ hrs: add BCAAs; tart cherry 30ml post-session

## Daily Supplements
Creatine 5g (morning), Omega-3 2-3g, Vitamin D3 2000 IU, Magnesium Glycinate 400mg (pre-bed), Multivitamin.

## Calorie & Macro Targets
Targets are provided dynamically per request in the Nutrition Context block, adjusted for the athlete's current body metrics, composition goal, and race philosophy. Apply them exactly as specified there.

---

# Equipment & Terrain
Available equipment and outdoor terrain options are provided per request based on the current locale. Use them to select appropriate exercises and substitute where needed.

---

# Athlete Signals (use when present in the request context)

The training context block may include these signals. Use them to inform plan generation and review decisions:

- **deload_flags**: Exercises where `sessions_since_progress >= 5`. Treat as a recommendation to drop weight ~10% on the next prescription for that exercise and reset the plateau.
- **recent_dispositions**: Audit trail of swap / completion decisions on past plan items (last 30 days). When the athlete consistently swaps a workout type, factor that into upcoming selection. The `reason` field, when present, captures the athlete's words.
- **wellness_summary**: Aggregated wellness signals (resting HR, stress, body battery, respiration) with short-term trends. Rising resting HR or falling body battery over the recent window is a recovery flag — bias toward easier sessions or rest.
- **coaching_preferences**: Durable athlete preferences captured from chat / reviews / natural-log / workout notes. Honour permanent preferences strictly. Non-permanent preferences are advisory."""


# ── Sport-specific modules (one selected per call) ────────────────────────────

_AR_MODULE = """
---

# Adventure Racing — Sport-Specific Framework

## Weekly Structure
- Monday: Rest (mandatory)
- 2 disciplines/day when possible (avoid kayak + MTB same day)
- Saturday: Long hike (scales: 4→5→6→cutback→5.5→6.5→7→cutback→7→7→7.5→8→cutback→6→4.5→3→2→race hrs)
- Road bike acceptable MTB substitute in training
- Partner home: limit hikes <2 hrs; prioritize cycling (1st) or running (2nd)

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
- Peak compound targets (Phase 3): Squat ~205, DL ~235, Weighted pull-up +40 lb, Row ~135

## Core Circuits (rotate for variety)
- A (General): Plank, dead bug, mountain climber, hollow body, bird-dog, superman
- B (Paddle): Russian twist, Pallof press, wood chop, hanging knee raise, bicycle crunch, V-sit
- C (Climbing): L-sit, hanging knee raise, ab wheel, side plank w/ hip abduction, compression tuck

## Brick Sessions (Phase 2+)
- Bike→Run, Bike→Paddle, Bike→Run→Paddle (Phase 3 mega-bricks)
- Always time transitions — target <5 min"""

_TRIATHLON_MODULE = """
---

# Triathlon — Sport-Specific Framework

## Weekly Structure
- One full rest day per week (or active recovery)
- Swim 2-3×/week; Bike 2-3×/week; Run 3-4×/week
- Brick sessions (Bike→Run) 1-2×/week in Build and Peak phases
- Long bike Saturday; long run Sunday (or separated by 1 day)

## Volume Balance by Phase
| Phase | Swim | Bike | Run |
|-------|------|------|-----|
| Base | 30% | 40% | 30% |
| Build | 25% | 45% | 30% |
| Peak | 20% | 45% | 35% |
| Taper | 20% | 40% | 40% |

## Swim Progressions
- Base: technique sets, drills, 200-400m repeats
- Build: 400-800m repeats, threshold sets, open-water simulation
- Peak: race-pace sets, sighting practice, full-distance simulation

## Brick Sessions
- Bike→Run only (no Run→Bike)
- Transition practice: aim for <2 min T2
- Early Build: 60-90 min bike + 15-30 min run
- Peak: race-distance bike + 20-45 min run

## Strength
- Hip flexors, glutes, core for run economy; shoulder stability for swim power
- Avoid heavy leg loading <72 hrs before long bike/run"""

_MARATHON_MODULE = """
---

# Marathon / Road Running — Sport-Specific Framework

## Weekly Structure
- One full rest day per week
- Long run Saturday or Sunday (the week's cornerstone, 25-35% of weekly mileage)
- Easy runs fill remaining days with 1-2 quality sessions (tempo or interval)
- Never schedule hard efforts back to back

## Long Run Structure
- Base: easy pace (conversation pace), 20-25% of weekly mileage
- Build: last 20-30% at marathon goal pace
- Peak: race simulation segments, 30-35% of mileage
- Taper: 40-50% reduction; last long run 2-3 weeks before race

## Pace Zones
| Zone | Name | Effort |
|------|------|--------|
| Z1 | Recovery | 65-70% max HR |
| Z2 | Easy / Aerobic | 70-75% max HR, conversational |
| Z3 | Tempo / Threshold | 80-85% max HR, comfortably hard |
| Z4 | VO2max | 90-95% max HR, hard |
| Z5 | Speed | >95% max HR, all-out |

## Strength
- Hip/glute: single-leg deadlifts, step-ups, hip thrusts, clamshells
- Calf: single-leg raises, eccentric loading
- 2 sessions/week in Base; reduce to 1 in Peak and Taper"""

_ULTRA_MODULE = """
---

# Ultra / Trail Running — Sport-Specific Framework

## Weekly Structure
- One full rest day per week
- Back-to-back long runs on weekends (Saturday + Sunday) in Build and Peak phases
- Time-on-feet is the primary metric — pace is secondary
- Include vert-matched training if course has significant elevation

## Long Run Structure
- Base: single long effort 3-4 hrs, easy effort
- Build: back-to-back Saturday (4-6 hrs) + Sunday (2-3 hrs) to simulate fatigue
- Peak: back-to-back with race-specific vert; include aid station simulation
- Taper: 40-50% reduction; last back-to-back 3 weeks out

## Aid Station Simulation
- Practice eating and drinking while moving
- Train with race-day nutrition (gels, real food, drop bags)
- At least 2 runs with full vest and race-day gear

## Strength
- Eccentric quad loading (downhill demands); hip/glute stability; ankle proprioception
- Core endurance for multi-hour efforts"""

_GENERIC_MODULE = """
---

# Endurance Training — General Framework

## Weekly Structure
- One full rest day per week
- Primary discipline sessions 3-4×/week
- Strength or cross-training 1-2×/week
- Long session on weekend: 25-35% of weekly training volume
- Easy days genuinely easy; hard days genuinely hard

## Strength
- Compound movements (squat, hinge, push, pull) 2×/week in Base; reduce to 1 in Peak/Taper
- Core work year-round: planks, carries, rotation

## Core Circuits (rotate for variety)
- A (Stability): Plank, dead bug, bird-dog, side plank, hollow body
- B (Power): Pallof press, wood chop, Russian twist, ab wheel"""


def _detect_sport_module(disciplines: str) -> str:
    """Return the sport-specific system prompt module for the given race disciplines."""
    d = disciplines.lower()
    ar_kw = {'climb', 'paddle', 'kayak', 'canoe', 'raft', 'nav', 'orienteer', 'rappel', 'abseil', 'packraft'}
    if any(k in d for k in ar_kw):
        return _AR_MODULE
    if any(k in d for k in {'triathlon', 'ironman', 'duathlon'}):
        return _TRIATHLON_MODULE
    if 'swim' in d and ('bike' in d or 'cycl' in d) and 'run' in d:
        return _TRIATHLON_MODULE
    if 'ultra' in d or 'trail run' in d:
        return _ULTRA_MODULE
    if 'marathon' in d or ('run' in d and not any(k in d for k in {'bike', 'cycl', 'swim', 'paddle'})):
        return _MARATHON_MODULE
    if disciplines.strip():
        return _GENERIC_MODULE
    return _AR_MODULE  # default for backward compat


def _get_plan_sport_module(db, plan_id: int) -> str:
    """Detect sport module from a stored plan's name and description."""
    try:
        plan = db.execute(
            'SELECT name, description FROM training_plans WHERE id=?', (plan_id,)
        ).fetchone()
        if plan:
            return _detect_sport_module((plan['name'] or '') + ' ' + (plan['description'] or ''))
    except Exception:
        pass
    return _AR_MODULE


# ── Context gathering ─────────────────────────────────────────────────────────

def get_coaching_context(db, plan_id=None, lookback_days=14, locale='home'):
    """Gather all training context for Claude. Returns a dict."""
    ctx = {'today': date.today().isoformat(), 'locale': locale}

    # Equipment and terrain available at current locale
    equipment_rows = db.execute(
        '''SELECT ei.tag, ei.label, ei.category
           FROM locale_equipment le
           JOIN equipment_items ei ON ei.id = le.equipment_id
           WHERE le.locale = ?
           ORDER BY ei.category, ei.label''',
        (locale,)
    ).fetchall()
    ctx['available_equipment'] = [dict(r) for r in equipment_rows]

    locale_profile = db.execute(
        'SELECT notes, city FROM locale_profiles WHERE locale = ?', (locale,)
    ).fetchone()
    ctx['locale_notes'] = locale_profile['notes'] if locale_profile and locale_profile['notes'] else ''
    ctx['locale_city'] = locale_profile['city'] if locale_profile and locale_profile['city'] else ''

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

    # Current Rx — all exercises with per-exercise success data and inventory metadata
    rx = db.execute(
        '''SELECT cr.exercise, cr.current_sets, cr.current_reps, cr.current_weight,
                  cr.next_sets, cr.next_reps, cr.next_weight,
                  cr.last_performed, cr.last_outcome, cr.consecutive_failures,
                  cr.sessions_since_progress,
                  ei.skills_ar_carryover, ei.recovery_cost,
                  ei.movement_pattern, ei.where_available, ei.discipline
           FROM current_rx cr
           LEFT JOIN exercise_inventory ei ON ei.id = cr.exercise_id
           ORDER BY cr.last_performed DESC'''
    ).fetchall()
    ctx['current_rx'] = [dict(r) for r in rx]
    ctx['deload_flags'] = [
        {'exercise': r['exercise'],
         'sessions_since_progress': r['sessions_since_progress']}
        for r in rx
        if (r['sessions_since_progress'] or 0) >= 5
    ]

    # Raw training and cardio always look back 90 days regardless of tier lookback
    log_cutoff = (date.today() - timedelta(days=90)).isoformat()

    training = db.execute(
        '''SELECT date, exercise, actual_sets, actual_reps, actual_weight,
                  rpe, outcome, notes
           FROM training_log
           WHERE date >= ?
           ORDER BY date DESC
           LIMIT 150''',
        (log_cutoff,)
    ).fetchall()
    ctx['recent_training'] = [dict(t) for t in training]

    # Recent cardio — 90 days, including Garmin performance fields
    cardio = db.execute(
        '''SELECT date, activity, activity_name, duration_min, distance_mi,
                  avg_hr, avg_pace, avg_power, norm_power,
                  aerobic_te, anaerobic_te, max_hr, elev_gain_ft, notes
           FROM cardio_log
           WHERE date >= ?
           ORDER BY date DESC
           LIMIT 75''',
        (log_cutoff,)
    ).fetchall()
    ctx['recent_cardio'] = [dict(c) for c in cardio]

    # Body metrics — last 4 entries for trend visibility
    metrics_rows = db.execute(
        'SELECT date, weight_lbs, body_fat_pct, vo2_max, resting_hr FROM body_metrics '
        'ORDER BY date DESC LIMIT 4'
    ).fetchall()
    ctx['body_metrics'] = [dict(m) for m in metrics_rows]

    # Training modalities
    try:
        modalities = db.execute(
            '''SELECT activity, category, primary_benefits, equipment_needed,
                      where_available, ar_carryover
               FROM training_modalities ORDER BY activity'''
        ).fetchall()
        ctx['training_modalities'] = [dict(m) for m in modalities]
    except Exception:
        ctx['training_modalities'] = []

    # Prior plans — last 90 days ("what we tried last block")
    try:
        prior_plans = db.execute(
            '''SELECT tp.id, tp.name, tp.sport_focus, tp.start_date, tp.end_date,
                      COUNT(CASE WHEN pi.status = 'completed' THEN 1 END) as completed,
                      COUNT(CASE WHEN pi.status = 'skipped' THEN 1 END) as skipped,
                      COUNT(CASE WHEN pi.status = 'swapped' THEN 1 END) as swapped,
                      COUNT(pi.id) as total_scheduled
               FROM training_plans tp
               LEFT JOIN plan_items pi ON pi.plan_id = tp.id
               WHERE date(tp.start_date) >= date('now', '-90 days')
                 AND (? IS NULL OR tp.id != ?)
               GROUP BY tp.id
               ORDER BY tp.start_date DESC''',
            (plan_id, plan_id)
        ).fetchall()
        prior = []
        for p in prior_plans:
            row = dict(p)
            sample = db.execute(
                'SELECT DISTINCT workout_name FROM plan_items WHERE plan_id=? LIMIT 10',
                (p['id'],)
            ).fetchall()
            row['sample_workouts'] = [w['workout_name'] for w in sample]
            prior.append(row)
        ctx['recent_plans'] = prior
    except Exception:
        ctx['recent_plans'] = []

    # Plan health if plan_id given
    if plan_id:
        try:
            from routes.plans import _plan_health
            ctx['plan_health'] = _plan_health(db, plan_id)
        except Exception:
            pass

    # Coaching preferences (permanent notes, avoid lists, etc.)
    try:
        prefs = db.execute(
            'SELECT category, content, permanent FROM coaching_preferences ORDER BY created_at ASC'
        ).fetchall()
        ctx['coaching_preferences'] = [dict(p) for p in prefs]
    except Exception:
        ctx['coaching_preferences'] = []

    # Recent plan-item dispositions (swap / completed audit trail, last 30 days)
    disp_cutoff = (date.today() - timedelta(days=30)).isoformat()
    try:
        disp = db.execute(
            '''SELECT pid.disposition, pid.reason, pid.log_type, pid.log_id,
                      pid.created_at,
                      pi.id as plan_item_id, pi.item_date as planned_date,
                      pi.workout_name as planned_workout, pi.sport_type as planned_sport
               FROM plan_item_disposition pid
               JOIN plan_items pi ON pi.id = pid.plan_item_id
               WHERE date(pid.created_at) >= ?
               ORDER BY pid.created_at DESC
               LIMIT 50''',
            (disp_cutoff,)
        ).fetchall()
        ctx['recent_dispositions'] = [dict(d) for d in disp]
    except Exception:
        ctx['recent_dispositions'] = []

    # Wellness summary — aggregate trends for the lookback window
    try:
        ctx['wellness_summary'] = get_wellness_summary(db, lookback_days=lookback_days)
    except Exception:
        ctx['wellness_summary'] = {}

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
      "intensity": "easy|moderate|hard|very_hard",
      "calorie_target": "e.g. 3400-3800",
      "macro_carb_pct": integer,
      "macro_protein_pct": integer,
      "macro_fat_pct": integer,
      "session_fueling": "string_or_null — specific intra/post session fueling protocol, null if session <60 min"
    }
  ]
}
Use the nutrition guidelines from your framework to set calorie and macro values for each day.
Apply the nutrition goal specified in the request (deficit/surplus/maintain/performance).
Carb + protein + fat percentages must sum to 100.
Skip rest days (Monday is always rest — omit it). Include every other day."""


def _get_client():
    key = os.environ.get('ANTHROPIC_API_KEY')
    if not key:
        raise RuntimeError('ANTHROPIC_API_KEY environment variable not set.')
    return anthropic.Anthropic(api_key=key)


def _model():
    return os.environ.get('CLAUDE_MODEL', 'claude-opus-4-7')


def _cached_system(sport_module: str = '') -> list:
    text = _BASE_PROMPT + ('\n' + sport_module if sport_module else '')
    return [{'type': 'text', 'text': text, 'cache_control': {'type': 'ephemeral', 'ttl': '1h'}}]


def _parse_json_response(text):
    """Strip markdown fences if present and parse JSON."""
    t = text.strip()
    if t.startswith('```'):
        t = t.split('```', 1)[1]
        if t.startswith('json'):
            t = t[4:]
        t = t.rsplit('```', 1)[0]
    return json.loads(t.strip())


_NUTRITION_GOAL_GUIDANCE = {
    'maintain':     'Maintain current body weight and composition. Use standard calorie targets from the nutrition guidelines.',
    'lose_fat':     'Reduce body fat. Apply a ~15% calorie deficit to the standard targets. Keep protein high to preserve muscle. Reduce carbs first, not protein or fat.',
    'build_muscle': 'Build muscle with a slight caloric surplus (~+10%). Increase protein to the high end of targets. Prioritize carbs around training sessions.',
    'performance':  'Maximize race performance. Prioritize carbohydrate availability. Do not restrict calories. Fuel all sessions aggressively, especially long and hard days.',
}

_PHILOSOPHY_ADDENDA = {
    'Just Finish': (
        'Conservative approach — prioritize injury prevention, consistency, and completing the race comfortably. '
        'Minimize high-intensity work. Use a comfortable, extended taper. Never sacrifice recovery for extra volume.'
    ),
    'Have Fun': (
        'Balanced training — enjoy variety, keep sessions engaging, no aggressive overreach. '
        'Include activities the athlete enjoys. Allow flexibility. Moderate taper.'
    ),
    'Compete': (
        'Structured periodization targeting a solid competitive performance. '
        'Include race-specific intensity blocks. Apply proper peak and taper. Balance stress and recovery.'
    ),
    'Win / Podium': (
        'Maximal periodization targeting podium performance. High-intensity blocks, VO2max work, '
        'aggressive taper, performance over comfort. Every session has a purpose.'
    ),
}


def _build_nutrition_context(body_metrics: list, nutrition_goal: str, race_philosophy: str) -> str:
    """Build a dynamic nutrition context block from current body metrics and goals."""
    goal_text = {
        'maintain':     'Maintain current body weight and composition. Match calorie intake to training load.',
        'lose_fat':     'Reduce body fat. Apply ~15% deficit on rest/easy days; hit full targets on hard/long days. Keep protein high, reduce carbs first.',
        'build_muscle': 'Build muscle with ~10% surplus. High protein. Prioritize carbs around training sessions.',
        'performance':  'Maximize performance. Prioritize carbohydrate availability. No calorie restriction. Fuel all sessions aggressively.',
    }.get(nutrition_goal, 'Maintain current body weight and composition.')

    philosophy_note = {
        'Just Finish':   'Conservative fueling — sustainable levels, no aggressive manipulation.',
        'Have Fun':      'Balanced fueling — no strict deficits or surpluses.',
        'Compete':       'Performance fueling — match targets precisely to training load.',
        'Win / Podium':  'Elite fueling — aggressive carb loading on hard days, no restriction during training.',
    }.get(race_philosophy, '')

    lines = [
        '## Nutrition Context',
        '',
        f'Goal: {nutrition_goal} — {goal_text}',
    ]
    if philosophy_note:
        lines.append(f'Philosophy ({race_philosophy}): {philosophy_note}')
    lines.append('')

    if body_metrics:
        latest = body_metrics[0]
        if latest.get('weight_lbs'):
            lines.append(f'Current weight: {latest["weight_lbs"]} lbs')
        if latest.get('body_fat_pct'):
            lines.append(f'Current body fat: {latest["body_fat_pct"]}%')
        if latest.get('vo2_max'):
            lines.append(f'VO2 max: {latest["vo2_max"]}')
        if len(body_metrics) > 1:
            oldest = body_metrics[-1]
            if latest.get('weight_lbs') and oldest.get('weight_lbs'):
                delta = latest['weight_lbs'] - oldest['weight_lbs']
                lines.append(f'Weight trend ({oldest["date"]} → {latest["date"]}): {"↓" if delta < 0 else "↑"} {abs(delta):.1f} lbs')
            if latest.get('body_fat_pct') and oldest.get('body_fat_pct'):
                bf_delta = latest['body_fat_pct'] - oldest['body_fat_pct']
                lines.append(f'Body fat trend: {"↓" if bf_delta < 0 else "↑"} {abs(bf_delta):.1f}%')
        lines.append('')

    lines += [
        'Day-type calorie targets (adjust per goal above):',
        '| Day Type | Calories | Carb | Protein | Fat |',
        '|----------|----------|------|---------|-----|',
        '| Rest | 2800–2900 | 45% | 29% | 24% |',
        '| Moderate (<90 min) | 3000–3200 | 54% | 25% | 21% |',
        '| Hard (2 sessions or >90 min) | 3400–3800 | 58% | 22% | 20% |',
        '| Heavy (bricks, >3 hrs) | 3900–4500 | 62% | 19% | 19% |',
        '| Long effort (5+ hrs) | 4700–6200 | 64% | 17% | 19% |',
    ]
    return '\n'.join(lines)


def generate_plan(db, start_date: str, weeks: int = 4, notes: str = '',
                  race_name: str = '', race_date: str = '', race_location: str = '',
                  race_disciplines: str = '', race_duration: str = '',
                  race_website: str = '', race_type: str = '',
                  race_goals: str = '',
                  locale: str = 'home',
                  nutrition_goal: str = 'maintain',
                  travel_schedule: list = None,
                  weekly_hours: float = 10.0,
                  rest_days=None,
                  race_philosophy: str = 'Compete',
                  experience_level: str = 'Intermediate') -> tuple:
    """
    Generate a new training plan block.
    Returns (plan_dict, usage) where plan_dict matches _create_plan_from_dict schema.
    """
    client = _get_client()
    ctx = get_coaching_context(db, locale=locale)

    sport_module = _detect_sport_module(race_disciplines)

    if rest_days is None:
        rest_days = ['Monday']
    elif isinstance(rest_days, str):
        rest_days = [d.strip() for d in rest_days.split(',') if d.strip()]
    rest_days_str = ', '.join(rest_days) if rest_days else 'Monday'

    goals_block = f'\n## Event Day Goals\n{race_goals}\n' if race_goals and race_goals.strip() else ''

    race_section = f"""## Target Event
- Event: {race_name or 'Not specified'}
- Type: {race_type or 'Not specified'}
- Date: {race_date or 'Not specified'}
- Location: {race_location or 'Not specified'}
- Disciplines: {race_disciplines or 'Not specified'}
- Expected duration: {race_duration or 'Not specified'}
- Website: {race_website or 'Not specified'}{goals_block}"""

    philosophy_addendum = _PHILOSOPHY_ADDENDA.get(race_philosophy, _PHILOSOPHY_ADDENDA['Compete'])
    training_params = f"""## Training Parameters
- Weekly training hours available: {weekly_hours}h
- Rest day(s): {rest_days_str}
- Race philosophy: {race_philosophy} — {philosophy_addendum}
- Athlete experience level: {experience_level}"""

    nutrition_section = _build_nutrition_context(ctx.get('body_metrics', []), nutrition_goal, race_philosophy)

    travel_section = ''
    if travel_schedule:
        lines = ['## Locale Updates (adapt equipment and workout selection for these date ranges)']
        for t in travel_schedule:
            loc = t.get('locale', 'hotel')
            city = t.get('city', '')
            city_str = f' ({city})' if city else ''
            indoor = ' — INDOOR ONLY (no outdoor activities)' if t.get('indoor_only') else ''
            lines.append(f"- {t.get('start_date')} → {t.get('end_date')}: {loc.title()}{city_str}{indoor}")
        travel_section = '\n'.join(lines) + '\n'

    user_msg = f"""Generate a {weeks}-week training plan block starting {start_date}.

{race_section}

{training_params}

{nutrition_section}

{travel_section}Determine the correct training phase based on start date vs race date above.
Apply the periodization structure, weekly layout preferences, and variety rules from your coaching framework.
Honour the preferred rest day and weekly hours target above.
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
        system=_cached_system(sport_module),
        messages=[{'role': 'user', 'content': user_msg}]
    ) as stream:
        response = stream.get_final_message()

    text = next((b.text for b in response.content if b.type == 'text'), '')
    plan = _parse_json_response(text)
    return plan, response.usage


def get_clothing_context(db, plan_id: int, city: str, days_ahead: int = 7) -> list:
    """
    Return clothing context for upcoming outdoor sessions in the next `days_ahead` days.
    Fetches a weather forecast from wttr.in and matches against conditions_log history.
    """
    today = date.today()
    today_str = today.isoformat()
    end_str = (today + timedelta(days=days_ahead)).isoformat()

    sessions = db.execute(
        '''SELECT id, item_date, sport_type, workout_name
           FROM plan_items
           WHERE plan_id=? AND sport_type != 'strength_training'
             AND status='scheduled' AND item_date BETWEEN ? AND ?
           ORDER BY item_date ASC''',
        (plan_id, today_str, end_str)
    ).fetchall()

    if not sessions:
        return []

    forecast_by_date = {}
    if city:
        try:
            resp = requests.get(f'https://wttr.in/{city}?format=j1', timeout=5)
            for day in resp.json().get('weather', []):
                d = day.get('date', '')
                hourly = day.get('hourly', [])
                desc = hourly[4].get('weatherDesc', [{}])[0].get('value', '') if len(hourly) > 4 else ''
                forecast_by_date[d] = {
                    'max_temp_f': int(day.get('maxtempF', 0)),
                    'min_temp_f': int(day.get('mintempF', 0)),
                    'avg_temp_f': (int(day.get('maxtempF', 0)) + int(day.get('mintempF', 0))) // 2,
                    'description': desc,
                }
        except Exception:
            pass

    recs = []
    for s in sessions:
        forecast = forecast_by_date.get(s['item_date'])
        rec = {
            'date': s['item_date'],
            'workout_name': s['workout_name'],
            'sport_type': s['sport_type'],
            'forecast': forecast,
            'similar_past_conditions': [],
        }
        if forecast:
            avg_temp = forecast['avg_temp_f']
            try:
                past = db.execute(
                    '''SELECT headwear, face_neck, upper_shell, upper_mid_layer,
                              upper_base_layer, lower_outer, lower_under, gloves,
                              arm_warmers, socks, footwear, comfort, comfort_notes,
                              temp_f, conditions, date
                       FROM conditions_log
                       WHERE temp_f BETWEEN ? AND ?
                       ORDER BY comfort DESC, date DESC LIMIT 5''',
                    (avg_temp - 10, avg_temp + 10)
                ).fetchall()
                rec['similar_past_conditions'] = [dict(p) for p in past]
            except Exception:
                pass
        recs.append(rec)
    return recs


def _get_performance_delta(db, plan_id: int, lookback_days: int) -> list:
    """Return planned-vs-actual comparison for completed sessions in the lookback window."""
    cutoff = (date.today() - timedelta(days=lookback_days)).isoformat()
    rows = db.execute(
        '''SELECT pi.id, pi.item_date, pi.workout_name, pi.sport_type, pi.intensity,
                  pi.target_duration_min, pi.target_distance_mi, pi.status,
                  SUM(tl.actual_sets) as actual_sets,
                  AVG(tl.rpe) as avg_rpe,
                  GROUP_CONCAT(tl.outcome) as outcomes,
                  cl.duration_min as actual_cardio_min,
                  cl.distance_mi as actual_cardio_mi,
                  cl.avg_hr, cl.aerobic_te
           FROM plan_items pi
           LEFT JOIN training_log tl ON tl.plan_item_id = pi.id
           LEFT JOIN cardio_log cl ON cl.plan_item_id = pi.id
           WHERE pi.plan_id = ? AND pi.item_date >= ?
             AND pi.status IN ('completed', 'skipped')
           GROUP BY pi.id
           ORDER BY pi.item_date ASC''',
        (plan_id, cutoff)
    ).fetchall()

    result = []
    for r in rows:
        row = dict(r)
        flag = 'on_plan'
        if r['status'] == 'skipped':
            flag = 'skipped'
        elif r['avg_rpe'] and r['avg_rpe'] > 8.5:
            flag = 'below_plan'
        elif r['outcomes'] and r['outcomes'].count('REDUCE') > r['outcomes'].count('PROGRESS'):
            flag = 'below_plan'
        elif r['target_duration_min'] and r['actual_cardio_min']:
            if r['actual_cardio_min'] < r['target_duration_min'] * 0.8:
                flag = 'below_plan'
        row['performance_flag'] = flag
        result.append(row)
    return result


def run_review(db, plan_id: int, tier: int, notes: str = '', locale: str = 'home',
               race_goals: str = '', intensity_direction: str = '') -> tuple:
    """
    Run a tier 1/2/3 coaching review.

    Tier 1 (session check): returns list of patch dicts
    Tier 2 (weekly): returns list of patch dicts
    Tier 3 (next block): returns new plan dict

    Returns (result, usage).
    """
    client = _get_client()
    lookback = {1: 7, 2: 14, 3: 30}.get(tier, 14)
    ctx = get_coaching_context(db, plan_id=plan_id, lookback_days=lookback, locale=locale)
    sport_module = _get_plan_sport_module(db, plan_id)
    city = ctx.get('locale_city', '')

    if tier == 3:
        plan = db.execute(
            'SELECT end_date FROM training_plans WHERE id=?', (plan_id,)
        ).fetchone()
        next_start = plan['end_date'] if plan else date.today().isoformat()

        instructions = f"""TIER 3 — Next Block Generation.
The current plan is nearly complete (≤7 sessions remain).
Generate a new 4-week plan block starting the day after {next_start}.
Use the full training history below as context for progressive overload and volume scaling.

{_PLAN_SCHEMA_INSTRUCTIONS}"""
        max_tokens = 8000
        delta_section = ''
    elif tier == 2:
        delta = _get_performance_delta(db, plan_id, lookback)
        below = [d for d in delta if d['performance_flag'] == 'below_plan']
        delta_section = f'\n## Performance Delta (planned vs. actual)\n{json.dumps(delta, indent=2, default=str)}\n'
        if below:
            delta_section += f'\nNOTE: {len(below)} of {len(delta)} recent sessions are below plan. Prioritize adjusting volume/intensity downward.\n'

        # Also include full remaining scheduled items so model sees the plan shape
        upcoming = db.execute(
            '''SELECT id, item_date, workout_name, sport_type, intensity,
                      target_duration_min, target_distance_mi
               FROM plan_items WHERE plan_id=? AND status='scheduled'
               ORDER BY item_date ASC''',
            (plan_id,)
        ).fetchall()
        delta_section += f'\n## Full Remaining Plan\n{json.dumps([dict(u) for u in upcoming], indent=2, default=str)}\n'

        clothing = get_clothing_context(db, plan_id, city)
        clothing_section = (
            f'\n## Upcoming Session Clothing Context (next 7 days)\n{json.dumps(clothing, indent=2, default=str)}\n'
            if clothing else ''
        )

        instructions = """TIER 2 — Weekly Review.
Analyze the last 2 weeks of training and the performance delta above. Adjust upcoming scheduled workouts as needed.
If clothing context is provided, include gear recommendations in the session notes for outdoor sessions.

Return ONLY a JSON array of patch operations (no markdown, no explanation):
[{"item_id": <integer plan_item_id>, "description": "...", "intensity": "...", "target_duration_min": ..., "notes": "..."}]

Only include fields that actually need changing. Return [] if no adjustments are needed.
The item_id values come from plan_health.upcoming_items or the Full Remaining Plan above."""
        max_tokens = 3000
        delta_section += clothing_section
    else:
        delta = _get_performance_delta(db, plan_id, lookback)
        below = [d for d in delta if d['performance_flag'] == 'below_plan']
        delta_section = f'\n## Performance Delta (planned vs. actual)\n{json.dumps(delta, indent=2, default=str)}\n'
        if below:
            delta_section += f'\nNOTE: {len(below)} of {len(delta)} recent sessions are below plan. Consider reducing intensity or volume on next sessions.\n'

        clothing = get_clothing_context(db, plan_id, city)
        if clothing:
            delta_section += f'\n## Upcoming Session Clothing Context (next 7 days)\n{json.dumps(clothing, indent=2, default=str)}\n'

        instructions = """TIER 1 — Session Check.
Review the most recent completed workout and performance delta above. Adjust the next 1-2 scheduled sessions if RPE trends, fatigue, or missed sessions warrant it.
If clothing context is provided, include gear recommendations in the session notes for outdoor sessions.

Return ONLY a JSON array of patch operations (no markdown, no explanation):
[{"item_id": <integer plan_item_id>, "description": "...", "intensity": "...", "notes": "..."}]

Only include fields that actually need changing. Return [] if no adjustments needed."""
        max_tokens = 2000

    goals_block = f'\n## Event Day Goals\n{race_goals}\n' if race_goals and race_goals.strip() else ''
    intensity_block = (
        f'\n## Intensity Adjustment Applied\nThe athlete reported the plan feels {intensity_direction}. '
        f'All remaining sessions have been shifted {"down" if intensity_direction == "too_hard" else "up"} one intensity level. '
        f'Factor this into your review.\n'
    ) if intensity_direction in ('too_hard', 'too_easy') else ''

    user_msg = f"""## Coaching Review — Tier {tier}

{instructions}
{delta_section}{goals_block}{intensity_block}
## Training Context
{json.dumps(ctx, indent=2, default=str)}

## Coach Notes
{notes or 'None'}"""

    with client.messages.stream(
        model=_model(),
        max_tokens=max_tokens,
        system=_cached_system(sport_module),
        messages=[{'role': 'user', 'content': user_msg}]
    ) as stream:
        response = stream.get_final_message()

    text = next((b.text for b in response.content if b.type == 'text'), '')
    result = _parse_json_response(text)
    return result, response.usage


_CHAT_RESPONSE_SCHEMA = """Respond ONLY with a JSON object (no markdown fences):
{
  "message": "Your conversational reply to the athlete",
  "preferences_to_save": [
    {"category": "avoid_exercise|prefer_exercise|nutrition|training|general", "content": "...", "permanent": true}
  ],
  "plan_patches": [
    {"item_id": <int>, "workout_name": "...", "description": "...", "intensity": "easy|moderate|hard|very_hard", "target_duration_min": <num>, "notes": "..."}
  ],
  "confirm_required": false
}

Rules:
- preferences_to_save: only include if the athlete expressed a lasting preference (avoid exercise, nutrition preference, training style, etc.). permanent=true for "never again" statements, false for temporary notes.
- plan_patches: only include if an immediate plan change is clearly warranted. Set confirm_required=true if the change is significant (multiple sessions, big intensity jump).
- item_id values come from plan_health.upcoming_items in the context. Only patch upcoming scheduled items.
- Keep message conversational and brief. Confirm what you're storing/changing.
- If nothing to store or patch, return empty arrays."""


def chat_with_coach(db, plan_id: int, message: str, history: list, locale: str = 'home') -> tuple:
    """
    Process a conversational message. Returns (response_dict, usage).

    response_dict keys: message, preferences_to_save, plan_patches, confirm_required
    history: list of {'role': 'user'|'assistant', 'content': str}
    """
    client = _get_client()
    ctx = get_coaching_context(db, plan_id=plan_id, lookback_days=14, locale=locale)
    sport_module = _get_plan_sport_module(db, plan_id)
    system_msg = _cached_system(sport_module)

    context_block = f"""## Current Training Context
{json.dumps(ctx, indent=2, default=str)}

## Response Format
{_CHAT_RESPONSE_SCHEMA}"""

    messages = []
    for turn in history[-10:]:
        messages.append({'role': turn['role'], 'content': turn['content']})
    messages.append({'role': 'user', 'content': f"{message}\n\n---\n{context_block}"})

    with client.messages.stream(
        model=_model(),
        max_tokens=2000,
        system=system_msg,
        messages=messages,
    ) as stream:
        response = stream.get_final_message()

    text = next((b.text for b in response.content if b.type == 'text'), '')
    result = _parse_json_response(text)
    return result, response.usage


# ── Feedback capture + preference normalization ───────────────────────────────

_FEEDBACK_EXTRACT_PROMPT = """You extract durable coaching preferences from athlete feedback. Be conservative — most feedback is just performance commentary, not a preference.

Return ONLY a JSON object (no markdown):
{"preferences": [{"category": "...", "content": "...", "permanent": true}]}

Categories: avoid_exercise, prefer_exercise, nutrition, training, scheduling, equipment, general

Rules:
- Only extract preferences the athlete clearly wants applied to FUTURE sessions
- "permanent": true for "never again", "always", "I hate", "I don't want"; false for one-off temporary notes
- Skip pure performance commentary ("felt strong", "slow today", "knee tight"), session ratings, weather observations, and one-time facts
- Skip questions, plan-edit requests, and clarifications
- One feedback may yield zero, one, or several preferences
- Phrase content as a directive a coach would file ("Burpees excluded at user request")
- Source context: {source}

Return {"preferences": []} if nothing durable is expressed."""


def extract_preferences(raw_text: str, source: str = 'unknown') -> list:
    """
    Run a Claude pass to extract durable preferences from free-text feedback.
    Returns list of {category, content, permanent} dicts. Empty on no signal,
    parse failure, or empty input. Uses Haiku for cost.
    """
    text = (raw_text or '').strip()
    if len(text) < 8:
        return []
    try:
        client = _get_client()
    except RuntimeError:
        return []
    prompt = _FEEDBACK_EXTRACT_PROMPT.replace('{source}', source) + f'\n\nFeedback:\n"""\n{text}\n"""'
    try:
        msg = client.messages.create(
            model='claude-haiku-4-5-20251001',
            max_tokens=512,
            messages=[{'role': 'user', 'content': prompt}],
        )
        body = next((b.text for b in msg.content if b.type == 'text'), '{}')
        parsed = _parse_json_response(body)
    except Exception:
        return []
    prefs = parsed.get('preferences', []) if isinstance(parsed, dict) else []
    out = []
    for p in prefs:
        if not isinstance(p, dict):
            continue
        content = (p.get('content') or '').strip()
        if not content:
            continue
        out.append({
            'category': (p.get('category') or 'general').strip() or 'general',
            'content': content,
            'permanent': bool(p.get('permanent', True)),
        })
    return out


def capture_feedback(db, source: str, raw_content: str, source_ref_id=None) -> int:
    """
    Insert raw feedback into feedback_log. Returns the new feedback_log id, or 0
    if the content is empty. Caller is responsible for db.commit().
    """
    text = (raw_content or '').strip()
    if not text:
        return 0
    cur = db.execute(
        'INSERT INTO feedback_log (source, source_ref_id, raw_content) VALUES (?,?,?)',
        (source, source_ref_id, text)
    )
    return cur.lastrowid


def save_preferences_from_feedback(db, fb_id: int, prefs: list) -> int:
    """
    Persist normalized preferences with a back-link to their source feedback row.
    Returns the count actually inserted. Caller is responsible for db.commit().
    """
    if not fb_id or not prefs:
        return 0
    n = 0
    for p in prefs:
        content = (p.get('content') or '').strip()
        if not content:
            continue
        db.execute(
            'INSERT INTO coaching_preferences (category, content, permanent, source_feedback_id) '
            'VALUES (?,?,?,?)',
            (p.get('category', 'general'), content,
             1 if p.get('permanent', True) else 0, fb_id)
        )
        n += 1
    return n


def capture_and_normalize_feedback(db, source: str, raw_content: str,
                                    source_ref_id=None) -> tuple:
    """
    Full pipeline: capture raw text, run extract pass, write preferences with
    source_feedback_id back-link. Returns (fb_id, prefs_saved). Skips on empty
    input or extraction failure. Caller is responsible for db.commit().
    """
    fb_id = capture_feedback(db, source, raw_content, source_ref_id)
    if not fb_id:
        return (0, 0)
    prefs = extract_preferences(raw_content, source)
    saved = save_preferences_from_feedback(db, fb_id, prefs)
    return (fb_id, saved)


# ── Wellness summary for coaching context ─────────────────────────────────────

def get_wellness_summary(db, lookback_days: int = 14) -> dict:
    """
    Aggregate recent wellness signals from wellness_log into trend-friendly
    numbers a coach can reason about. Returns {} if no data in window.
    """
    cutoff = (date.today() - timedelta(days=lookback_days)).isoformat()
    try:
        rows = db.execute(
            '''SELECT date,
                      MIN(CASE WHEN heart_rate > 30 THEN heart_rate END) AS resting_hr_proxy,
                      AVG(CASE WHEN stress_level >= 0 THEN stress_level END) AS avg_stress,
                      AVG(body_battery) AS avg_body_battery,
                      MAX(body_battery) AS max_body_battery,
                      MIN(body_battery) AS min_body_battery,
                      AVG(CASE WHEN respiration_rate > 0 THEN respiration_rate END) AS avg_respiration,
                      SUM(steps) AS total_steps
                 FROM wellness_log
                WHERE date >= ?
             GROUP BY date
             ORDER BY date DESC''',
            (cutoff,)
        ).fetchall()
    except Exception:
        return {}

    days = [dict(r) for r in rows]
    if not days:
        return {}

    def _avg(key):
        vals = [d[key] for d in days if d.get(key) is not None]
        return round(sum(vals) / len(vals), 1) if vals else None

    def _trend(key):
        # Compare latest 3 days vs prior 3 days within the window
        recent = [d[key] for d in days[:3] if d.get(key) is not None]
        prior = [d[key] for d in days[3:6] if d.get(key) is not None]
        if not recent or not prior:
            return None
        delta = (sum(recent) / len(recent)) - (sum(prior) / len(prior))
        return round(delta, 1)

    return {
        'lookback_days': lookback_days,
        'days_with_data': len(days),
        'avg_resting_hr': _avg('resting_hr_proxy'),
        'resting_hr_trend': _trend('resting_hr_proxy'),
        'avg_stress': _avg('avg_stress'),
        'stress_trend': _trend('avg_stress'),
        'avg_body_battery': _avg('avg_body_battery'),
        'body_battery_trend': _trend('avg_body_battery'),
        'avg_respiration': _avg('avg_respiration'),
        'avg_daily_steps': _avg('total_steps'),
        'latest_date': days[0]['date'],
    }
