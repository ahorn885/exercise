"""Auto-match logged activities to scheduled plan items.

Replaces the basic _find_plan_match / _sports_compatible / _compute_compliance
helpers that lived in routes/garmin.py with a single scoring matcher used by
both manual FIT upload and Garmin sync.

Match flow (per Andy's 2026-05 rules):
  Tier 1 — same day, fuzzy match on duration + distance.
  Tier 2 — nearby days (-2 / +1), same scoring.
  Tier 3 — no match: caller asks the user (handled by routes/garmin.py).

Scoring is forgiving on purpose: a strength session that bailed early or
swapped one exercise should still match its planned slot.

Disposition writes are handled by `record_disposition()` so the same path
captures auto-matches, user-confirmed swaps, and manual overrides.
"""

from datetime import date, timedelta


# Activity name (FIT-parsed display) → plan sport_type category
_ACTIVITY_TO_PLAN_SPORT = {
    'Running': 'running',
    'Trail Running': 'running',
    'Treadmill': 'running',
    'Road Cycling': 'cycling',
    'Mountain Biking': 'cycling',
    'Gravel Cycling': 'cycling',
    'Indoor Bike Trainer': 'cycling',
    'Hiking': 'hiking',
    'Swimming Pool': 'swimming',
    'Swimming Open': 'swimming',
    'Yoga': 'yoga',
    'Rowing Ergometer': 'rowing',
    'Kayaking': 'paddling',
}

# Plan sport_type aliases — interchangeable values for matching.
_SPORT_ALIASES = {
    'running':           {'run', 'trail run', 'trail_run', 'treadmill', 'track', 'jog'},
    'cycling':           {'bike', 'biking', 'cycle', 'mtb', 'road bike', 'gravel', 'ride'},
    'strength_training': {'strength', 'weights', 'gym', 'lifting', 'strength training', 'training'},
    'hiking':            {'hike', 'trail hike', 'walking', 'walk'},
    'swimming':          {'swim', 'pool', 'open water'},
    'paddling':          {'paddle', 'kayaking', 'rowing'},
    'yoga':              {'flexibility', 'mobility'},
}

# Sport groups that are interchangeable for plan matching — a hike FIT
# should match a "walk" plan item, etc.
_SPORT_GROUPS = [
    {'running'},
    {'cycling'},
    {'hiking'},
    {'swimming'},
    {'paddling'},
    {'strength_training'},
    {'yoga'},
]


# Score thresholds
SCORE_AUTO_MATCH = 0.5    # ≥ this score → auto-attach silently
SCORE_SPORT_ONLY = 0.6    # baseline when sport matches but no metrics to compare


def normalize_sport(sport_or_activity):
    """Map any sport / activity string to a normalized plan sport_type."""
    if not sport_or_activity:
        return None
    s = str(sport_or_activity).strip()
    if not s:
        return None
    if s in _ACTIVITY_TO_PLAN_SPORT:
        return _ACTIVITY_TO_PLAN_SPORT[s]
    sl = s.lower().replace(' ', '_')
    if sl in _SPORT_ALIASES:
        return sl
    for plan_sport, aliases in _SPORT_ALIASES.items():
        if sl == plan_sport or sl in aliases:
            return plan_sport
        if any(alias in sl for alias in aliases):
            return plan_sport
    return sl


def sport_compatible(activity_sport, plan_sport):
    """True if a logged activity's sport matches a plan item's sport_type."""
    a = normalize_sport(activity_sport)
    p = normalize_sport(plan_sport)
    if not a or not p:
        return False
    if a == p:
        return True
    for group in _SPORT_GROUPS:
        if a in group and p in group:
            return True
    return False


def _activity_sport(activity):
    """Pull whatever sport-ish field is present on the activity dict."""
    return (
        activity.get('_plan_sport_type')
        or activity.get('sport_type')
        or activity.get('activity')
    )


def _scaled_score(ratio):
    """Map an actual/target ratio to a 0–1 closeness score in [0.5, 1.5]."""
    if 0.5 <= ratio <= 1.5:
        return max(0.0, 1.0 - abs(1.0 - ratio))
    return 0.0


def score_match(activity, plan_item):
    """Return a 0.0–1.0 score for how well `activity` matches `plan_item`.

    0.0 = sport mismatch or duration/distance fall outside ±50%.
    Higher = closer match on duration and distance.
    `SCORE_SPORT_ONLY` if sport matches but no metric targets exist on the plan.
    """
    if not sport_compatible(_activity_sport(activity), plan_item['sport_type']):
        return 0.0

    target_dur = plan_item['target_duration_min']
    target_dist = plan_item['target_distance_mi']
    actual_dur = activity.get('duration_min')
    actual_dist = activity.get('distance_mi')

    parts = []
    if target_dur and actual_dur:
        s = _scaled_score(actual_dur / target_dur)
        if s == 0.0:
            return 0.0  # outside acceptable window — hard reject
        parts.append(s)
    if target_dist and actual_dist:
        s = _scaled_score(actual_dist / target_dist)
        if s == 0.0:
            return 0.0
        parts.append(s)

    if not parts:
        # Sport matches but plan has no metrics to compare against (typical of
        # strength_training or unstructured plan items). Moderate confidence.
        return SCORE_SPORT_ONLY

    return sum(parts) / len(parts)


def find_best_match(db, activity, min_score=SCORE_AUTO_MATCH):
    """Find the best-scoring scheduled plan_items row for an activity.

    Searches Tier 1 (same day) first, then Tier 2 (-2 / +1 days). Returns the
    same-day match if one passes `min_score`, even if a later-day item scores
    higher — same-day always wins ties.

    Returns dict {'plan_item': Row, 'score': float, 'day_offset': int} or None.
    Caller decides what to do with sub-threshold matches (typically: ask user).
    """
    activity_date = activity.get('date')
    if not activity_date:
        return None
    try:
        base_date = date.fromisoformat(activity_date)
    except (ValueError, TypeError):
        return None

    # Search same day first — if anything matches there, we don't bother with
    # neighbouring days. Real-world: people record what they do on the day,
    # not on the day before/after.
    for offset in (0, -1, 1, -2):
        target = (base_date + timedelta(days=offset)).isoformat()
        items = db.execute(
            '''SELECT pi.*, tp.name as plan_name
               FROM plan_items pi
               JOIN training_plans tp ON tp.id = pi.plan_id
               WHERE pi.item_date=? AND pi.status='scheduled'
                 AND tp.status != 'archived' ''',
            (target,)
        ).fetchall()

        best_for_day = None
        for item in items:
            score = score_match(activity, item)
            if score < min_score:
                continue
            if best_for_day is None or score > best_for_day['score']:
                best_for_day = {'plan_item': item, 'score': score, 'day_offset': offset}

        if best_for_day:
            return best_for_day

    return None


def candidate_plan_items(db, activity_date, days_back=2, days_forward=1):
    """Return plan_items in the matching window — used by the ask-user prompt.

    No score filter; the user picks. Useful for the "instead of / in addition
    to" dropdowns when the auto-matcher came up empty.
    """
    if not activity_date:
        return []
    try:
        base_date = date.fromisoformat(activity_date)
    except (ValueError, TypeError):
        return []
    items = []
    for offset in range(-days_back, days_forward + 1):
        target = (base_date + timedelta(days=offset)).isoformat()
        rows = db.execute(
            '''SELECT pi.*, tp.name as plan_name, ? as day_offset
               FROM plan_items pi
               JOIN training_plans tp ON tp.id = pi.plan_id
               WHERE pi.item_date=? AND pi.status='scheduled'
                 AND tp.status != 'archived'
               ORDER BY pi.id''',
            (offset, target)
        ).fetchall()
        items.extend(rows)
    return items


def record_disposition(db, plan_item_id, log_type, log_id, disposition, reason=None):
    """Insert a plan_item_disposition row.

    `disposition` is one of:
      'completed'    — activity fulfills the plan item (auto-match or user pick).
      'swapped_for'  — user did this instead of the planned item; planned item
                       is marked 'swapped' (not 'completed').

    'in_addition_to' is intentionally NOT a disposition — those activities are
    standalone logs with plan_item_id=NULL and the planned item stays
    'scheduled'. The user-prompt option exists as friendly framing but doesn't
    create a relationship in the DB.
    """
    if disposition not in ('completed', 'swapped_for'):
        raise ValueError(f'unknown disposition: {disposition}')
    db.execute(
        '''INSERT INTO plan_item_disposition
             (plan_item_id, log_type, log_id, disposition, reason)
           VALUES (?, ?, ?, ?, ?)''',
        (plan_item_id, log_type, log_id, disposition, reason)
    )
    if disposition == 'completed':
        db.execute(
            "UPDATE plan_items SET status='completed' WHERE id=? AND status='scheduled'",
            (plan_item_id,)
        )
    else:  # swapped_for
        db.execute(
            "UPDATE plan_items SET status='swapped' WHERE id=? AND status='scheduled'",
            (plan_item_id,)
        )


def compute_compliance(activity, plan_item):
    """Return per-target compliance percentages and a label.

    Kept compatible with the previous _compute_compliance shape so existing
    sync_preview rendering doesn't have to change.
    """
    result = {'duration_pct': None, 'distance_pct': None, 'label': 'no_target'}
    if not plan_item:
        result['label'] = 'unmatched'
        return result
    target_dur = plan_item['target_duration_min']
    actual_dur = activity.get('duration_min')
    if target_dur and actual_dur:
        result['duration_pct'] = round(actual_dur / target_dur * 100)
    target_dist = plan_item['target_distance_mi']
    actual_dist = activity.get('distance_mi')
    if target_dist and actual_dist:
        result['distance_pct'] = round(actual_dist / target_dist * 100)
    primary = result['duration_pct'] if result['duration_pct'] is not None else result['distance_pct']
    if primary is None:
        result['label'] = 'no_target'
    elif 80 <= primary <= 130:
        result['label'] = 'on_plan'
    elif primary < 80:
        result['label'] = 'short'
    else:
        result['label'] = 'over'
    return result
