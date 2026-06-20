"""Athlete profile helpers (Session 4).

The profile is a tiny per-user table seeded by the user themselves on
`/profile`. It feeds into the coaching context so plan generation /
review have the athlete's age, target event, weekly hours, and training
window without the user typing them into the generate form each time.

Allowed fields are pinned here so route POSTs can't write arbitrary
columns. New fields added in future sessions go in this list and the
`athlete_profile` schema in init_db.py simultaneously.
"""

from typing import Optional


PROFILE_FIELDS = (
    'date_of_birth',
    'sex',
    'height_cm',
    'primary_sport',
    # #469 — athlete-facing unit toggle (`imperial` / `metric`). Storage is
    # always kg; this flag drives the UI/entry boundary + rx prescription
    # display. See `units.py` for the conversion helpers.
    'unit_preference',
    # `target_event_name` + `target_event_date` retired from the form per
    # D-66 Layer 3B Scope A; columns dropped from athlete_profile in Scope B
    # (init_db.py migrations). `training_window` retired in D-73 Phase 1.2A
    # — superseded by `daily_availability_windows` (D-61 / PR12).
    'weekly_hours_target',
    'notes',
    # v5 §A.2 prefill-eligible baselines (PR6 D-51 column foundation).
    # Self-report at onboarding today; provider extractors land in PR7
    # (D2a) and write to athlete_profile_field_provenance.
    'body_weight_kg',
    'hrmax_bpm',
    'lactate_threshold_hr_bpm',
    'vo2max',
    'cycling_ftp_w',
    # v5 §G capacity toggle (PR12 D-61; trimmed FormRefresh Slice C
    # 2026-05-25). Per-day windows live in the `daily_availability_windows`
    # table. `doubles_feasible` gates second-window entry. The long-session
    # day + rest days are no longer stored — they're inferred from the
    # windows (longest enabled window = long session; disabled days = rest).
    'doubles_feasible',
    # Slice 2b.2b (§5.1.1 / D11) — session-count ceiling controls.
    # `two_a_day_preference` drives the Peak sessions/day density;
    # `peak_sessions_max` is the optional advanced override (NULL = derive
    # from the preference). Distinct from `doubles_feasible` (which gates
    # second-window *scheduling*): this is the *desired* training density.
    'two_a_day_preference',
    'peak_sessions_max',
    # D-73 Phase 1.2A (D-51 §3.3) — §C training history scalars. All
    # self-report at onboarding today; `previous_coaching` closed enum
    # (`self` / `online_plan` / `coach` / `none`). Free-text columns
    # (`longest_event_completed`, `training_consistency_cause`) tolerate
    # any string and the Layer 1 builder parses at read time.
    'years_structured_training',
    'peak_weekly_volume_hrs',
    'peak_weekly_volume_year',
    'longest_event_completed',
    'training_consistency_disrupted_weeks',
    'training_consistency_cause',
    'previous_coaching',
    # D-73 Phase 1.2A (D-51 §3.6) — §F testing-baseline gap fields. The
    # three `_source` companions encode how the existing prefill-eligible
    # baseline was obtained (closed enum: `measured` / `estimated_tanaka`
    # / `provider_<X>` for hrmax_source; analogous shapes for the others).
    # Not prefill-eligible themselves (they describe prefill provenance).
    'running_threshold_pace_sec_per_km',
    'running_threshold_test_date',
    'css_swim_sec_per_100m',
    'css_test_date',
    'cycling_ftp_test_date',
    'hrmax_source',
    'lt_method',
    'vo2max_source',
    # D-73 Phase 1.2A (D-51 §3.8) — §H no-event-mode plan parameters.
    # `plan_duration_weeks_no_event` enum (8/12/16/20/24); NULL when the
    # athlete has a target race_events row. `non_event_goal_type` closed
    # enum (`endurance` / `general_fitness` / `strength` / `mixed`).
    'plan_duration_weeks_no_event',
    'non_event_goal_type',
    # D-73 Phase 1.2A (D-51 §3.9) — §I lifestyle & recovery. Sleep-
    # deprivation pair stored regardless of §H race duration (Andy
    # 2026-05-19; athlete can edit any time, no write-path conditional).
    # `dietary_pattern` + `fueling_format_preference` are comma-separated
    # closed-enum tokens. `caffeine_race_day_strategy` is conditional in
    # the UI (NULL when `caffeine_tolerance='none'`) but storage is
    # unconstrained.
    'work_stress_level',
    'dietary_pattern',
    'supplement_protocol_notes',
    'caffeine_tolerance',
    'caffeine_daily_mg_estimate',
    'caffeine_race_day_strategy',
    'altitude_acclimatization_history',
    'altitude_max_exposure_m',
    'altitude_exposure_count',
    'fueling_format_preference',
    'gi_triggers_known',
    'salt_electrolyte_tolerance',
    'sleep_deprivation_max_hrs_continuous_awake',
    'sleep_deprivation_strategy_notes',
    # #304 — self-reported Layer-4 convenience fields. `experience_level` is a
    # closed self-select band (EXPERIENCE_LEVEL_CHOICES); `coaching_voice_
    # preferences` is free text rendered into the synthesizer's athlete context.
    'experience_level',
    'coaching_voice_preferences',
)

# #304 — self-select athlete experience band. Mirrors the
# `Layer1Payload.experience_level` Literal the Layer 4 prompts read.
EXPERIENCE_LEVEL_CHOICES = (
    'novice', 'developing', 'intermediate', 'advanced', 'elite',
)

# Subset of PROFILE_FIELDS that v5 §A.2.1 marks as provider-prefill-eligible.
# routes/profile.py:edit() writes athlete_profile_field_provenance rows
# scoped to this tuple on save (source='self_report' for PR6; D2 PRs
# add the manual_override flip when an athlete edits a prefilled value).
PREFILL_ELIGIBLE_FIELDS = (
    'body_weight_kg',
    'hrmax_bpm',
    'lactate_threshold_hr_bpm',
    'vo2max',
    'cycling_ftp_w',
)

# v5 §G day tokens. Sunday=0 mirrors the daily_availability_windows
# storage convention (matches §7.1 schema comment: 0=Sunday, 6=Saturday).
DAY_TOKENS = ('sun', 'mon', 'tue', 'wed', 'thu', 'fri', 'sat')
DAY_LABELS = ('Sunday', 'Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday')

# §G Doubles Feasible enum. The third value ('no') disables second-window
# entry in the form; 'occasionally' surfaces second windows but plan-gen
# treats them as discretionary per D-61 §3.3.
DOUBLES_FEASIBLE_CHOICES = ('regularly', 'occasionally', 'no')

# Slice 2b.2b §G two-a-day preference enum — the friendly primary control
# for the Peak session-count ceiling. Order is ascending density; mirrors
# `layer4.session_grid._TWO_A_DAY_DENSITY` keys (never 1.0× / occasionally
# 1.5× / regularly 1.85× sessions per available day at Peak).
TWO_A_DAY_CHOICES = ('never', 'occasionally', 'regularly')

# D-73 Phase 2.2 (Athlete_Onboarding_Data_Spec_v5.md §B.1.1) — injury_log
# closed enums. injury_type drives Layer 2D §5.3.6 accommodation-modality
# dispatch (V1_DEFAULT_ACCOMMODATIONS keyed on (injury_type, severity)).
# 'Other / uncertain' is the conservative fallback per §B.1.1; rows entered
# before this column landed default to NULL and Layer 2D treats NULL as
# the fallback bucket.
KNOWN_INJURY_TYPES = (
    'Acute soft tissue (strain / sprain / tear)',
    'Tendinopathy / overuse',
    'Joint (mechanical) — non-surgical',
    'Joint (mechanical) — surgical',
    'Bone (fracture / contusion) — non-stress',
    'Bone — stress fracture',
    'Skin / surface (burn / abrasion / laceration)',
    'Nerve',
    'Inflammatory (bursitis / fasciitis)',
    'Post-surgical',
    'Other / uncertain',
)

# D-73 Phase 2.2 (Athlete_Onboarding_Data_Spec_v5.md §B.1) — injury_log.severity
# 6-value enum per Layer2D_Spec.md §5.3.4 (severity → verdict mapping). Replaces
# legacy INTEGER (1-5) numeric scale. Acute/Post-surgical map to EXCLUDE;
# Recovering/Chronic-Managed/Structural-Permanent map to ACCOMMODATE;
# Resolved maps to CLEAN (defensive — resolved injuries shouldn't reach
# current_injuries partition).
KNOWN_INJURY_SEVERITIES = (
    'Acute',
    'Recovering',
    'Chronic-Managed',
    'Post-surgical',
    'Structural-Permanent',
    'Resolved',
)

# D-73 §I.2 nutrition & fueling capture vocab. Closed enums per
# Layer1_D51_Design_v1.md §3.9; storage stays unconstrained (the Layer 1/2E
# builders parse permissively) but the profile form constrains entry to these
# tokens. `dietary_pattern` + `fueling_format_preference` are multi-select
# (stored comma-separated). The `fueling_format` token set follows the
# Layer2E §I.2 format vocabulary (no enum was committed to a Layer 1 spec).
DIETARY_PATTERN_CHOICES = (
    'omnivore', 'vegetarian', 'vegan', 'pescatarian', 'paleo', 'keto',
    'gluten_free', 'low_fodmap', 'other',
)
FUELING_FORMAT_CHOICES = (
    'gel', 'chew', 'drink_mix', 'sports_drink', 'bar', 'real_food',
)
CAFFEINE_TOLERANCE_CHOICES = ('none', 'low', 'moderate', 'high')
CAFFEINE_RACE_DAY_STRATEGY_CHOICES = (
    'caffeine_loading', 'taper', 'maintain', 'avoid',
)
SALT_ELECTROLYTE_TOLERANCE_CHOICES = ('low', 'moderate', 'high')

# D-73 Phase 2.2 (Athlete_Onboarding_Data_Spec_v5.md §B.3) — injury_log
# movement_constraints multi-select. Maps to exercise DB col 9 keyword
# patterns; Layer 2D §5.3.3 substring-matches the per-constraint keyword
# bundle against layer0.exercises.injury_flags_text.
KNOWN_MOVEMENT_CONSTRAINTS = (
    'Pain with loading',
    'Pain with impact',
    'Pain above specific joint angle',
    'Pain on descent / eccentric',
    'Pain on rotation',
    'Pain with grip / sustained hold',
    'Pain with overhead movement',
    'Instability',
    'Reduced ROM',
    'Pain at high volume only',
)

# D-73 Phase 2.2 (Athlete_Onboarding_Data_Spec_v5.md §B.1) — injury_log.side.
# Layer 2D v1 doesn't filter on side (Layer2D_Spec.md §10 edge case;
# contraindicated_parts has no side dimension — tracked as 2D-7 future).
# Side is no longer captured by a dedicated form field; it's derived from
# the body_part prefix ('Left Wrist' → 'Left') at save time. Layer 2D still
# reads InjuryRecord.side for downstream Layer 4 / UI rendering.
KNOWN_INJURY_SIDES = ('Left', 'Right', 'Both', 'N/A')

# Which movement constraints plausibly apply to each body part. Keyed on the
# side-less canonical body part (the injury form's body_part values double
# Left/Right — strip the prefix before lookup). Drives the injury form's
# swap-on-change filtering so only relevant constraints render. Values MUST
# be a subset of KNOWN_MOVEMENT_CONSTRAINTS.
_MC = {c: c for c in KNOWN_MOVEMENT_CONSTRAINTS}
BODY_PART_CONSTRAINTS = {
    'Hand':       [_MC['Pain with loading'], _MC['Pain above specific joint angle'], _MC['Pain with grip / sustained hold'], _MC['Instability'], _MC['Reduced ROM'], _MC['Pain at high volume only']],
    'Wrist':      [_MC['Pain with loading'], _MC['Pain above specific joint angle'], _MC['Pain with grip / sustained hold'], _MC['Instability'], _MC['Reduced ROM'], _MC['Pain at high volume only']],
    'Elbow':      [_MC['Pain with loading'], _MC['Pain above specific joint angle'], _MC['Pain with grip / sustained hold'], _MC['Pain with overhead movement'], _MC['Instability'], _MC['Reduced ROM'], _MC['Pain at high volume only']],
    'Shoulder':   [_MC['Pain with loading'], _MC['Pain above specific joint angle'], _MC['Pain on rotation'], _MC['Pain with overhead movement'], _MC['Instability'], _MC['Reduced ROM'], _MC['Pain at high volume only']],
    'Knee':       [_MC['Pain with loading'], _MC['Pain with impact'], _MC['Pain above specific joint angle'], _MC['Pain on descent / eccentric'], _MC['Instability'], _MC['Reduced ROM'], _MC['Pain at high volume only']],
    'Ankle':      [_MC['Pain with loading'], _MC['Pain with impact'], _MC['Pain above specific joint angle'], _MC['Pain on descent / eccentric'], _MC['Pain on rotation'], _MC['Instability'], _MC['Reduced ROM'], _MC['Pain at high volume only']],
    'Foot':       [_MC['Pain with loading'], _MC['Pain with impact'], _MC['Pain above specific joint angle'], _MC['Reduced ROM'], _MC['Pain at high volume only']],
    'Hip':        [_MC['Pain with loading'], _MC['Pain with impact'], _MC['Pain above specific joint angle'], _MC['Pain on descent / eccentric'], _MC['Pain on rotation'], _MC['Instability'], _MC['Reduced ROM'], _MC['Pain at high volume only']],
    'Hamstring':  [_MC['Pain with loading'], _MC['Pain above specific joint angle'], _MC['Pain on descent / eccentric'], _MC['Pain at high volume only']],
    'Quad':       [_MC['Pain with loading'], _MC['Pain above specific joint angle'], _MC['Pain on descent / eccentric'], _MC['Pain at high volume only']],
    'Glute':      [_MC['Pain with loading'], _MC['Pain on descent / eccentric'], _MC['Pain on rotation'], _MC['Pain at high volume only']],
    'Calf':       [_MC['Pain with loading'], _MC['Pain with impact'], _MC['Pain on descent / eccentric'], _MC['Pain at high volume only']],
    'Shin':       [_MC['Pain with loading'], _MC['Pain with impact'], _MC['Pain at high volume only']],
    'Achilles':   [_MC['Pain with loading'], _MC['Pain with impact'], _MC['Pain on descent / eccentric'], _MC['Pain at high volume only']],
    'Groin':      [_MC['Pain with loading'], _MC['Pain above specific joint angle'], _MC['Pain on rotation'], _MC['Pain at high volume only']],
    'Abdomen':    [_MC['Pain with loading'], _MC['Pain on rotation'], _MC['Pain at high volume only']],
    'Chest':      [_MC['Pain with loading'], _MC['Pain with overhead movement'], _MC['Pain at high volume only']],
    'Rib':        [_MC['Pain with loading'], _MC['Pain on rotation'], _MC['Pain at high volume only']],
    'Lower Back': [_MC['Pain with loading'], _MC['Pain with impact'], _MC['Pain above specific joint angle'], _MC['Pain on rotation'], _MC['Pain at high volume only']],
    'Upper Back': [_MC['Pain with loading'], _MC['Pain above specific joint angle'], _MC['Pain on rotation'], _MC['Pain with overhead movement'], _MC['Pain at high volume only']],
    'Neck':       [_MC['Pain above specific joint angle'], _MC['Pain on rotation'], _MC['Pain with overhead movement'], _MC['Reduced ROM'], _MC['Pain at high volume only']],
}
del _MC

# D-73 Phase 1.2B (D-51 §3.2a) — health_conditions_log.system_category closed
# enum per v5 §B.4.1.
KNOWN_SYSTEM_CATEGORIES = (
    'cardiac',
    'respiratory',
    'metabolic',
    'neurological',
    'gi_immune',
    'musculoskeletal',
    'endocrine',
    'other',
)

# health_conditions_log.status — parallel to injury_log.status precedent.
HEALTH_CONDITION_STATUSES = ('Active', 'Resolved', 'Inactive')

# D-73 Phase 1.2B (D-51 §3.2b) — medications_log.medication_class closed enum
# per v5 §B. Training-relevant only (not a general pharmacy code); 'other'
# absorbs everything that doesn't move the training-impact needle.
KNOWN_MEDICATION_CLASSES = (
    'beta_blocker',
    'diuretic',
    'nsaid_chronic',
    'hrt',
    'ssri',
    'stimulant_adhd',
    'corticosteroid_chronic',
    'anticoagulant',
    # D-21 — added so the supplement_vocabulary contraindication tokens
    # `rx:thyroid_medication` (iron absorption) + `rx:pde5_inhibitor`
    # (nitrate/beetroot hypotension interaction) have a §B class to match.
    'thyroid_medication',
    'pde5_inhibitor',
    'other',
)

# D-73 Phase 1.2B (D-51 §3.3) — athlete_secondary_sports.experience_tier
# closed enum per v5 §C row 2.
EXPERIENCE_TIERS = ('under_1yr', '1_to_3yr', '3plus_yr')

# D-73 Phase 1.2B (D-51 §3.3) — recent_race_results.source mirrors the
# athlete_profile_field_provenance.source shape but per-row (record-shaped
# data). 'provider_<X>' values are appended when provider race-data
# extractors land (none today); the constant grows alongside them.
RACE_RESULT_SOURCES = ('self_report',)

# D-73 Phase 1.2B (D-51 §3.12) — athlete_network_links.relationship_types
# is a comma-separated subset of this closed enum per v5 §L.
KNOWN_RELATIONSHIP_TYPES = (
    'training_partner',
    'race_teammate',
    'coach',
    'family',
    'pacer',
    'crew',
)

# D-73 Phase 1.2B (D-51 §3.12) — linked_partner_consents.consent_scope
# per v5 §L Account Config 4 (Privacy and Linked-Partner Sharing). Athlete-
# controlled sharing granularity; 'none' is the explicit no-share state
# (distinct from "row absent" which means no consent ever granted).
LINKED_PARTNER_CONSENT_SCOPES = ('none', 'activity_summaries', 'full_plan_access')

# D-73 Phase 1.2C (D-51 §3.4) — per-discipline §D closed-enum write-path
# constants. Each is paired with a discipline_baseline_<discipline> column
# in init_db.py _PG_MIGRATIONS. Multi-select fields (trail_experience_terrain,
# bike_types_available, paddle_craft_types, ski_disciplines) store comma-
# separated subsets validated against the constant tuple. rock_climbing_*_grade
# stay free-text multi-system per Layer 4 Step 4a (not enumerated).

# §D.1 — discipline_baseline_running.trail_experience_terrain (multi-select).
TRAIL_EXPERIENCE_TERRAINS = ('moderate', 'technical', 'mountain', 'moorland')

# §D.2 — discipline_baseline_cycling.mtb_skill.
MTB_SKILL_LEVELS = ('beginner', 'intermediate', 'advanced')

# §D.2b — discipline_baseline_cycling.bike_types_available (multi-select).
# 2c.2b (#540): enumerated so the craft picker + write path stay in lockstep
# with the layer0.craft_discipline_aliases keys (the X1b.3b craft-substitution
# path — owned craft → discipline). Slugs == EQUIPMENT_CATEGORIES['Cycling
# Equipment'] tags. Previously left free-text (design wave §3.4).
# WS-I (#586, 2026-06-13): cycling_trainer dropped — a trainer/erg is fixed gear,
# not a mobile vessel, so it is EQUIPMENT (gym profile), not a craft. Craft =
# mobile, athlete-owned vessels only. Its craft_discipline_aliases rows retire in
# the same change (etl/migrations/layer0/0004_*).
# #622 (2026-06-16): tt_bike added — the time-trial / triathlon bike is a mobile
# vessel (aliases to D-007 Time-Trial Cycling), relocated out of the equipment
# vocabulary into the craft store (etl/migrations/layer0/0007_*).
BIKE_TYPES = ('road_bike', 'mountain_bike', 'gravel_bike', 'tt_bike')

# §D.3 — discipline_baseline_swimming.ow_experience.
OW_EXPERIENCE_LEVELS = ('none', 'limited', 'experienced')

# §D.4 — discipline_baseline_paddling.paddle_craft_types (multi-select).
# Vocabulary V4 §4: 'surfski' pruned (enum-only vessel, never tracked to a
# discipline). Hard-removed per build decision — any pre-existing athlete row
# storing 'surfski' must be migrated (it will otherwise fail enum validation).
# #622 (2026-06-16): 'sup' (Stand-up Paddleboard, aliases to D-032) + 'raft'
# (Paddle Rafting, aliases to D-019) added — both mobile vessels relocated out of
# the equipment vocabulary into the craft store (etl/migrations/layer0/0007_*).
PADDLE_CRAFT_TYPES = ('kayak', 'canoe', 'packraft', 'sup', 'raft')

# Display labels for the owned-craft pickers (bike + paddle, 2c.2b). Slugs are
# the stored + aliased keys; labels are presentation-only.
CRAFT_LABELS = {
    'road_bike': 'Road bike',
    'mountain_bike': 'Mountain bike',
    'gravel_bike': 'Gravel bike',
    'tt_bike': 'TT / triathlon bike',
    'kayak': 'Kayak',
    'canoe': 'Canoe',
    'packraft': 'Packraft',
    'sup': 'Stand-up paddleboard',
    'raft': 'Raft',
}

# §D.5 — discipline_baseline_skiing.ski_disciplines (multi-select).
SKI_DISCIPLINES = ('classic_xc', 'skate_xc', 'skimo')

# §D.6 — discipline_baseline_navigation.experience_level.
NAVIGATION_EXPERIENCE_LEVELS = ('none', 'map_only', 'map_compass', 'expert')


def get_daily_availability_windows(db, user_id):
    """Return per-day windows for `user_id` as a list of 7 dicts (Sun..Sat).

    Each entry has shape::

        {'day_of_week': 0..6, 'day_token': 'sun'..'sat',
         'day_label': 'Sunday'..'Saturday',
         'primary': {'enabled': bool, 'window_start': 'HH:MM'|None,
                     'window_duration_min': int|None},
         'secondary': {...same keys...} | None}

    Days with no stored rows fall back to enabled=False everywhere — the
    form renders them as unchecked rows. `secondary` is None when no
    second-window row exists (athlete didn't enable doubles for that day).

    Reads from `daily_availability_windows`. PG-only table per
    `_PG_MIGRATIONS`; on SQLite dev the SELECT returns no rows and every
    day reads as disabled.
    """
    if user_id is None:
        return [_empty_day(i) for i in range(7)]

    rows = []
    try:
        rows = db.execute(
            'SELECT day_of_week, window_index, enabled, window_start, '
            'window_duration_min FROM daily_availability_windows '
            'WHERE user_id = ?',
            (user_id,),
        ).fetchall()
    except Exception:
        # Transient DB hiccup — return all-disabled rather than crash the
        # onboarding form render.
        rows = []

    by_day_idx = {(r['day_of_week'], r['window_index']): r for r in rows}
    out = []
    for dow in range(7):
        primary_row = by_day_idx.get((dow, 0))
        secondary_row = by_day_idx.get((dow, 1))
        out.append({
            'day_of_week': dow,
            'day_token': DAY_TOKENS[dow],
            'day_label': DAY_LABELS[dow],
            'primary': _window_dict(primary_row),
            'secondary': _window_dict(secondary_row) if secondary_row else None,
        })
    return out


def _empty_day(dow):
    return {
        'day_of_week': dow,
        'day_token': DAY_TOKENS[dow],
        'day_label': DAY_LABELS[dow],
        'primary': {'enabled': False, 'window_start': None, 'window_duration_min': None},
        'secondary': None,
    }


def _window_dict(row):
    if row is None:
        return {'enabled': False, 'window_start': None, 'window_duration_min': None}
    start = row['window_start']
    # PG returns datetime.time; SQLite returns whatever string came in.
    # Template renders HH:MM either way.
    if start is not None and hasattr(start, 'strftime'):
        start = start.strftime('%H:%M')
    elif isinstance(start, str) and len(start) >= 5:
        start = start[:5]
    return {
        'enabled': bool(row['enabled']),
        'window_start': start,
        'window_duration_min': row['window_duration_min'],
    }


def upsert_daily_availability_windows(db, user_id, windows):
    """Replace this user's per-day windows with `windows`.

    `windows` is a list of 7 dicts (one per day-of-week, Sun..Sat) shaped
    like the output of `get_daily_availability_windows`. For each day,
    the primary row is always present; the secondary row exists only
    when the day's secondary dict carries `enabled=True`.

    Strategy: DELETE-then-INSERT scoped to user_id. The table's
    UNIQUE(user_id, day_of_week, window_index) makes upserting per-row
    workable, but the form submits the full week every time so wipe-
    then-insert is cleaner and idempotent.

    Caller is responsible for db.commit().
    """
    if user_id is None:
        raise ValueError('user_id required')

    db.execute(
        'DELETE FROM daily_availability_windows WHERE user_id = ?',
        (user_id,),
    )
    for day in windows:
        dow = day['day_of_week']
        for idx, key in ((0, 'primary'), (1, 'secondary')):
            w = day.get(key)
            if w is None:
                continue
            if idx == 1 and not w.get('enabled'):
                # Don't materialise disabled secondary rows; absence is
                # the canonical signal that the athlete didn't enable a
                # second window for this day.
                continue
            enabled = bool(w.get('enabled'))
            start = w.get('window_start') if enabled else None
            dur = w.get('window_duration_min') if enabled else None
            db.execute(
                'INSERT INTO daily_availability_windows '
                '(user_id, day_of_week, window_index, enabled, '
                ' window_start, window_duration_min) '
                'VALUES (?, ?, ?, ?, ?, ?)',
                (user_id, dow, idx, enabled, start, dur),
            )


def get_athlete_profile(db, user_id) -> Optional[dict]:
    """Return the profile row for `user_id` as a dict, or None if missing."""
    if user_id is None:
        return None
    row = db.execute(
        f"SELECT user_id, {', '.join(PROFILE_FIELDS)}, updated_at "
        "FROM athlete_profile WHERE user_id = ?",
        (user_id,)
    ).fetchone()
    return dict(row) if row else None


def upsert_athlete_profile(db, user_id, **fields) -> dict:
    """Insert-or-update the profile for `user_id`. Unknown keys are
    silently dropped — caller can pass a request.form-shaped dict
    without sanitising. Returns the resulting row as a dict.

    Caller is responsible for db.commit().
    """
    if user_id is None:
        raise ValueError('user_id required')

    clean = {k: fields[k] for k in PROFILE_FIELDS if k in fields}
    if db.execute(
        'SELECT 1 FROM athlete_profile WHERE user_id = ?', (user_id,)
    ).fetchone():
        if clean:
            assigns = ', '.join(f'{k}=?' for k in clean)
            db.execute(
                f'UPDATE athlete_profile SET {assigns}, updated_at = NOW() '
                f'WHERE user_id = ?',
                list(clean.values()) + [user_id]
            )
    else:
        cols = ['user_id'] + list(clean.keys())
        vals = [user_id] + list(clean.values())
        placeholders = ', '.join(['?'] * len(cols))
        db.execute(
            f'INSERT INTO athlete_profile ({", ".join(cols)}) '
            f'VALUES ({placeholders})',
            vals
        )

    return get_athlete_profile(db, user_id) or {}
