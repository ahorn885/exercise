"""Initialize the PostgreSQL database — schema + idempotent migrations + seeds."""
import os

DATABASE_URL = os.environ.get('DATABASE_URL')

PG_SCHEMA = '''
    CREATE TABLE IF NOT EXISTS users (
        id SERIAL PRIMARY KEY,
        username TEXT NOT NULL UNIQUE,
        email TEXT UNIQUE,
        password_hash TEXT NOT NULL,
        display_name TEXT,
        created_at TIMESTAMP DEFAULT NOW(),
        last_login TIMESTAMP
    );
    CREATE TABLE IF NOT EXISTS athlete_profile (
        user_id INTEGER PRIMARY KEY REFERENCES users(id),
        date_of_birth TEXT,
        sex TEXT,
        height_cm REAL,
        primary_sport TEXT,
        weekly_hours_target REAL,
        notes TEXT,
        body_weight_kg REAL,
        hrmax_bpm INTEGER,
        lactate_threshold_hr_bpm INTEGER,
        vo2max REAL,
        cycling_ftp_w INTEGER,
        doubles_feasible TEXT,
        unit_preference TEXT NOT NULL DEFAULT 'imperial',
        updated_at TIMESTAMP DEFAULT NOW()
    );
    CREATE TABLE IF NOT EXISTS exercise_inventory (
        id SERIAL PRIMARY KEY,
        exercise TEXT NOT NULL UNIQUE,
        type TEXT, discipline TEXT, equipment TEXT, muscles_worked TEXT,
        skills_ar_carryover TEXT, where_available TEXT, source TEXT,
        suggested_volume TEXT, substitution_group TEXT, recovery_cost TEXT,
        movement_pattern TEXT, session_placement TEXT, form_cue TEXT, video_reference TEXT,
        weight_increment REAL
    );
    CREATE TABLE IF NOT EXISTS training_plans (
        id SERIAL PRIMARY KEY,
        user_id INTEGER REFERENCES users(id),
        name TEXT NOT NULL,
        description TEXT,
        sport_focus TEXT,
        start_date TEXT,
        end_date TEXT,
        status TEXT DEFAULT 'active',
        source_json TEXT,
        created_at TIMESTAMP DEFAULT NOW()
    );
    CREATE TABLE IF NOT EXISTS plan_items (
        id SERIAL PRIMARY KEY,
        user_id INTEGER REFERENCES users(id),
        plan_id INTEGER NOT NULL REFERENCES training_plans(id),
        item_date TEXT NOT NULL,
        sport_type TEXT NOT NULL,
        workout_name TEXT NOT NULL,
        description TEXT,
        target_duration_min REAL,
        target_distance_mi REAL,
        intensity TEXT,
        garmin_workout_json TEXT,
        status TEXT DEFAULT 'scheduled',
        notes TEXT,
        calorie_target TEXT,
        macro_carb_pct INTEGER,
        macro_protein_pct INTEGER,
        macro_fat_pct INTEGER,
        session_fueling TEXT,
        created_at TIMESTAMP DEFAULT NOW()
    );
    CREATE TABLE IF NOT EXISTS training_sessions (
        id SERIAL PRIMARY KEY,
        user_id INTEGER REFERENCES users(id),
        date TEXT NOT NULL,
        notes TEXT,
        plan_item_id INTEGER REFERENCES plan_items(id),
        created_at TIMESTAMP DEFAULT NOW()
    );
    CREATE TABLE IF NOT EXISTS training_log (
        id SERIAL PRIMARY KEY,
        user_id INTEGER REFERENCES users(id),
        date TEXT NOT NULL, exercise TEXT NOT NULL,
        exercise_id INTEGER REFERENCES exercise_inventory(id),
        sub_group TEXT, recovery_cost TEXT,
        target_sets INTEGER, target_reps INTEGER, target_weight REAL, target_duration INTEGER,
        actual_sets INTEGER, actual_reps INTEGER, actual_weight REAL, actual_duration INTEGER,
        rpe REAL, rest_sec INTEGER, outcome TEXT, est_1rm REAL, volume REAL,
        body_weight REAL, next_weight REAL, next_sets INTEGER, next_reps INTEGER,
        progression_level TEXT, notes TEXT,
        garmin_activity_id TEXT,
        plan_item_id INTEGER REFERENCES plan_items(id),
        session_id INTEGER REFERENCES training_sessions(id),
        created_at TIMESTAMP DEFAULT NOW()
    );
    CREATE TABLE IF NOT EXISTS training_log_sets (
        id SERIAL PRIMARY KEY,
        user_id INTEGER REFERENCES users(id),
        training_log_id INTEGER NOT NULL REFERENCES training_log(id) ON DELETE CASCADE,
        set_number INTEGER NOT NULL,
        reps INTEGER,
        weight_kg REAL,
        duration_sec INTEGER
    );
    CREATE TABLE IF NOT EXISTS current_rx (
        id SERIAL PRIMARY KEY,
        user_id INTEGER REFERENCES users(id),
        exercise TEXT NOT NULL, exercise_id INTEGER REFERENCES exercise_inventory(id),
        discipline TEXT, type TEXT, movement_pattern TEXT,
        inventory_sugg_volume TEXT, current_sets INTEGER, current_reps INTEGER,
        current_weight REAL, current_duration INTEGER, last_performed TEXT,
        last_outcome TEXT, consecutive_failures INTEGER DEFAULT 0, rx_source TEXT,
        weight_increment REAL,
        next_sets INTEGER, next_reps INTEGER, next_weight REAL,
        UNIQUE(user_id, exercise)
    );
    CREATE TABLE IF NOT EXISTS cardio_log (
        id SERIAL PRIMARY KEY,
        user_id INTEGER REFERENCES users(id),
        date TEXT NOT NULL, activity TEXT NOT NULL, activity_name TEXT,
        duration_min REAL, moving_time_min REAL, distance_mi REAL, avg_pace TEXT,
        avg_speed REAL, avg_hr INTEGER, max_hr INTEGER, calories INTEGER,
        elev_gain_ft REAL, elev_loss_ft REAL, avg_cadence INTEGER, max_cadence INTEGER,
        avg_power INTEGER, max_power INTEGER, norm_power INTEGER,
        aerobic_te REAL, anaerobic_te REAL, swolf INTEGER, active_lengths INTEGER,
        stride_length_m REAL, vert_oscillation_cm REAL, vert_ratio_pct REAL,
        gct_ms REAL, gct_balance TEXT,
        garmin_activity_id TEXT,
        plan_item_id INTEGER REFERENCES plan_items(id),
        notes TEXT, created_at TIMESTAMP DEFAULT NOW()
    );
    CREATE TABLE IF NOT EXISTS body_metrics (
        id SERIAL PRIMARY KEY,
        user_id INTEGER REFERENCES users(id),
        date TEXT NOT NULL, weight_kg REAL, body_fat_pct REAL,
        vo2_max REAL, resting_hr INTEGER, notes TEXT,
        created_at TIMESTAMP DEFAULT NOW(),
        UNIQUE(user_id, date)
    );
    CREATE TABLE IF NOT EXISTS conditions_log (
        id SERIAL PRIMARY KEY,
        user_id INTEGER REFERENCES users(id),
        date TEXT NOT NULL, activity TEXT, temp_f REAL, feels_like_f REAL,
        wind_mph REAL, wind_dir TEXT, conditions TEXT,
        headwear TEXT, face_neck TEXT, upper_shell TEXT, upper_mid_layer TEXT,
        upper_base_layer TEXT, lower_outer TEXT, lower_under TEXT,
        gloves TEXT, arm_warmers TEXT, socks TEXT, footwear TEXT,
        comfort INTEGER, comfort_notes TEXT,
        cardio_log_id INTEGER REFERENCES cardio_log(id),
        created_at TIMESTAMP DEFAULT NOW()
    );
    CREATE TABLE IF NOT EXISTS injury_log (
        id SERIAL PRIMARY KEY,
        user_id INTEGER REFERENCES users(id),
        start_date TEXT NOT NULL, body_part TEXT NOT NULL, description TEXT,
        severity INTEGER, modifications_needed TEXT, status TEXT DEFAULT 'Active',
        resolved_date TEXT, created_at TIMESTAMP DEFAULT NOW()
    );
    CREATE TABLE IF NOT EXISTS training_modalities (
        id SERIAL PRIMARY KEY,
        activity TEXT NOT NULL UNIQUE, category TEXT, primary_benefits TEXT,
        equipment_needed TEXT, where_available TEXT, ar_carryover TEXT
    );
    CREATE TABLE IF NOT EXISTS training_methods (
        id SERIAL PRIMARY KEY,
        method TEXT NOT NULL, description TEXT, apply_to TEXT, source TEXT
    );
    CREATE TABLE IF NOT EXISTS plan_reviews (
        id SERIAL PRIMARY KEY,
        plan_id INTEGER NOT NULL REFERENCES training_plans(id),
        tier INTEGER NOT NULL,
        sessions_reviewed INTEGER DEFAULT 0,
        notes TEXT,
        created_at TIMESTAMP DEFAULT NOW()
    );
    CREATE TABLE IF NOT EXISTS feedback_log (
        id SERIAL PRIMARY KEY,
        user_id INTEGER REFERENCES users(id),
        source TEXT NOT NULL,
        source_ref_id INTEGER,
        raw_content TEXT NOT NULL,
        captured_at TIMESTAMP DEFAULT NOW()
    );
    CREATE TABLE IF NOT EXISTS coaching_preferences (
        id SERIAL PRIMARY KEY,
        user_id INTEGER REFERENCES users(id),
        category TEXT NOT NULL DEFAULT 'general',
        content TEXT NOT NULL,
        permanent INTEGER NOT NULL DEFAULT 1,
        source_feedback_id INTEGER REFERENCES feedback_log(id),
        created_at TIMESTAMP DEFAULT NOW()
    );
    CREATE TABLE IF NOT EXISTS coaching_chat (
        id SERIAL PRIMARY KEY,
        user_id INTEGER REFERENCES users(id),
        plan_id INTEGER REFERENCES training_plans(id),
        role TEXT NOT NULL,
        content TEXT NOT NULL,
        actions_json TEXT,
        created_at TIMESTAMP DEFAULT NOW()
    );
    CREATE TABLE IF NOT EXISTS garmin_auth (
        id SERIAL PRIMARY KEY,
        user_id INTEGER REFERENCES users(id),
        garmin_username TEXT,
        garth_session TEXT,
        created_at TIMESTAMP DEFAULT NOW(),
        updated_at TIMESTAMP DEFAULT NOW()
    );
    CREATE TABLE IF NOT EXISTS garmin_workouts (
        id SERIAL PRIMARY KEY,
        user_id INTEGER REFERENCES users(id),
        plan_item_id INTEGER REFERENCES plan_items(id),
        garmin_workout_id TEXT NOT NULL,
        workout_name TEXT,
        sport_type TEXT,
        scheduled_date TEXT,
        status TEXT DEFAULT 'active',
        created_at TIMESTAMP DEFAULT NOW()
    );
    CREATE TABLE IF NOT EXISTS locale_profiles (
        user_id INTEGER NOT NULL REFERENCES users(id),
        locale TEXT NOT NULL,
        equipment TEXT DEFAULT '',
        notes TEXT DEFAULT '',
        city TEXT DEFAULT '',
        updated_at TIMESTAMP DEFAULT NOW(),
        PRIMARY KEY (user_id, locale)
    );
    CREATE TABLE IF NOT EXISTS plan_travel (
        id SERIAL PRIMARY KEY,
        plan_id INTEGER NOT NULL REFERENCES training_plans(id),
        start_date TEXT NOT NULL,
        end_date TEXT NOT NULL,
        locale TEXT NOT NULL,
        city TEXT DEFAULT '',
        notes TEXT DEFAULT '',
        created_at TIMESTAMP DEFAULT NOW()
    );
    CREATE TABLE IF NOT EXISTS equipment_items (
        id       SERIAL PRIMARY KEY,
        tag      TEXT NOT NULL UNIQUE,
        label    TEXT NOT NULL,
        category TEXT NOT NULL
    );
    CREATE TABLE IF NOT EXISTS exercise_equipment (
        exercise_id  INTEGER NOT NULL REFERENCES exercise_inventory(id),
        equipment_id INTEGER NOT NULL REFERENCES equipment_items(id),
        option_group INTEGER NOT NULL DEFAULT 1,
        PRIMARY KEY (exercise_id, equipment_id)
    );
    CREATE TABLE IF NOT EXISTS locale_equipment (
        user_id      INTEGER NOT NULL REFERENCES users(id),
        locale       TEXT NOT NULL,
        equipment_id INTEGER NOT NULL REFERENCES equipment_items(id),
        PRIMARY KEY (user_id, locale, equipment_id),
        FOREIGN KEY (user_id, locale) REFERENCES locale_profiles(user_id, locale)
    );
    CREATE TABLE IF NOT EXISTS injury_exercise_modifications (
        id                     SERIAL PRIMARY KEY,
        injury_id              INTEGER NOT NULL REFERENCES injury_log(id),
        exercise_id            INTEGER NOT NULL REFERENCES exercise_inventory(id),
        substitute_exercise_id INTEGER REFERENCES exercise_inventory(id),
        modification_type      TEXT NOT NULL DEFAULT 'modify',
        modification_notes     TEXT,
        created_at             TIMESTAMP DEFAULT NOW()
    );
    CREATE INDEX IF NOT EXISTS idx_tl_date ON training_log(date);
    CREATE INDEX IF NOT EXISTS idx_tl_exercise ON training_log(exercise);
    CREATE INDEX IF NOT EXISTS idx_cl_date ON cardio_log(date);
    CREATE INDEX IF NOT EXISTS idx_bm_date ON body_metrics(date);
    CREATE INDEX IF NOT EXISTS idx_pi_plan ON plan_items(plan_id);
    CREATE INDEX IF NOT EXISTS idx_pi_date ON plan_items(item_date);
    CREATE TABLE IF NOT EXISTS clothing_options (
        id       SERIAL PRIMARY KEY,
        user_id  INTEGER NOT NULL REFERENCES users(id),
        category TEXT NOT NULL,
        value    TEXT NOT NULL,
        UNIQUE(user_id, category, value)
    );
    CREATE TABLE IF NOT EXISTS wellness_log (
        id             SERIAL PRIMARY KEY,
        user_id        INTEGER REFERENCES users(id),
        date           TEXT NOT NULL,
        timestamp_ms   BIGINT NOT NULL,
        heart_rate     INTEGER,
        stress_level   INTEGER,
        body_battery   INTEGER,
        respiration_rate REAL,
        steps          INTEGER,
        active_calories INTEGER,
        active_time_s  REAL,
        distance_m     REAL,
        activity_type  INTEGER,
        source         TEXT DEFAULT 'wellness_fit',
        UNIQUE(user_id, timestamp_ms)
    );
    CREATE INDEX IF NOT EXISTS idx_wl_date ON wellness_log(date);
    CREATE TABLE IF NOT EXISTS purchase_recommendations (
        id            SERIAL PRIMARY KEY,
        slug          TEXT NOT NULL UNIQUE,
        label         TEXT NOT NULL,
        equipment_id  INTEGER REFERENCES equipment_items(id),
        est_cost_low  INTEGER,
        est_cost_high INTEGER,
        priority      TEXT NOT NULL DEFAULT 'medium',
        rationale     TEXT,
        sort_order    INTEGER NOT NULL DEFAULT 0,
        active        INTEGER NOT NULL DEFAULT 1
    );
    CREATE TABLE IF NOT EXISTS user_purchase_recommendations (
        user_id     INTEGER NOT NULL REFERENCES users(id),
        purchase_id INTEGER NOT NULL REFERENCES purchase_recommendations(id),
        status      TEXT NOT NULL,
        user_notes  TEXT,
        updated_at  TIMESTAMP DEFAULT NOW(),
        PRIMARY KEY (user_id, purchase_id)
    );
'''


# ── current_rx seed — one set of "Needs initial setup" rows per user ──────────
# Each user gets their own copy so rx_engine has something to UPSERT against
# on their first logged session. The composite UNIQUE(user_id, exercise) lets
# us seed the same exercise list for every user without collisions.
# routes/auth.py:register calls this for the first-user bootstrap so Andy
# doesn't have to wait for a cold start.

def _seed_current_rx_for_user(executor, user_id):
    """INSERT seeded current_rx rows for a single user. Idempotent — relies on
    the composite UNIQUE(user_id, exercise) to skip rows that already exist."""
    executor.executemany(
        '''INSERT INTO current_rx (exercise, discipline, type, movement_pattern,
           inventory_sugg_volume, rx_source, user_id)
           VALUES (%s, %s, %s, %s, %s, 'Needs initial setup', %s)
           ON CONFLICT (user_id, exercise) DO NOTHING''',
        [tuple(e[:5]) + (user_id,) for e in EXERCISES]
    )


# ── Recommended purchases — shared catalog ───────────────────────────────────
#
# Each entry binds to an equipment_items.tag (so "exercises impacted" can be
# derived live from the exercise_equipment join) and carries cost ranges +
# priority + a short rationale tailored to the AR / endurance profile.
# Idempotency is keyed on `slug` — entries can be added or have their copy
# tweaked over time without disturbing per-user state in
# user_purchase_recommendations.
#
# Cost ranges are USD whole dollars (street price, new). Priority defaults:
#   high   — foundational; most home gyms benefit from this
#   medium — strong returns, but second-tier (or has a workable substitute)
#   low    — specialty / situational
PURCHASE_RECOMMENDATIONS = [
    # slug, label, equipment_tag, cost_low, cost_high, priority, rationale, sort
    ('adjustable_dumbbells', 'Adjustable Dumbbells (5–50 lb pair)', 'dumbbells',
     300, 700, 'high',
     'Single biggest unlock for a home gym — dozens of exercises (presses, rows, '
     'lunges, RDLs, carries, accessories) collapse onto one footprint. '
     'PowerBlock or Bowflex SelectTech land in this range.', 10),
    ('pull_up_bar', 'Doorway / Wall-Mount Pull-Up Bar', 'pull_up_bar',
     30, 120, 'high',
     'Most homes have no pulling-pattern equipment — this fixes it for under '
     '$50. Wall-mount is more rigid; doorway is non-permanent.', 20),
    ('kettlebell_pair', 'Kettlebells (one heavy + one moderate)', 'kettlebell',
     80, 250, 'high',
     'Swings, goblet squats, suitcase carries, Turkish get-ups, snatches — '
     'one tool covers explosive hip-hinge work and grip endurance.', 30),
    ('resistance_bands', 'Resistance Band Set (light to heavy)', 'resistance_bands',
     30, 80, 'high',
     'Warm-ups, pull-aparts, banded face-pulls, hip-mobility work, assisted '
     'pull-ups, travel kit. Cheap; high utility.', 40),
    ('foam_roller', 'High-Density Foam Roller', 'foam_roller',
     20, 60, 'high',
     'Daily recovery tool. Pairs with a lacrosse ball for trigger-point work. '
     'Cheap and there is no good substitute.', 50),

    ('squat_rack', 'Power Rack / Squat Stand', 'squat_rack',
     350, 900, 'medium',
     'Unlocks heavy barbell squats and bench safely without a spotter. Only '
     'worth it if you already own (or plan to buy) a barbell + plates.', 110),
    ('barbell_plates', 'Olympic Barbell + Plate Set (300+ lb)', 'barbell',
     400, 900, 'medium',
     'Required for heavy compound lifts (squat, deadlift, bench). Pair with a '
     'rack for safety. The single biggest leg-strength multiplier.', 120),
    ('bench_adjustable', 'Adjustable / Incline Bench', 'bench_adjustable',
     150, 400, 'medium',
     'Required for bench press, incline DB press, single-arm rows, split-stance '
     'work. Adjustable is worth the upcharge over flat-only.', 130),
    ('plyo_box', 'Stackable Plyo Box (12/18/24 in)', 'plyo_box',
     90, 200, 'medium',
     'Box jumps, step-ups, depth drops, elevated push-ups. Stackable saves '
     'space and gives you 3 heights in one footprint.', 140),
    ('weighted_vest', 'Adjustable Weighted Vest (20–40 lb)', 'weighted_vest',
     80, 200, 'medium',
     'Loaded carries and ruck training translate directly to AR pack-carrying '
     'demands. Also makes bodyweight pull-ups / push-ups progressively '
     'harder without buying more equipment.', 150),
    ('trx', 'TRX / Suspension Trainer', 'trx',
     100, 200, 'medium',
     'Bodyweight rows, anti-rotation work, atomic push-ups. Especially useful '
     'for hotel-room training where no rack is available.', 160),
    ('hangboard', 'Hangboard (climbing fingerboard)', 'hangboard',
     30, 150, 'medium',
     'Grip endurance for paddling, climbing transitions, and rope work in AR. '
     'Mounts above a doorway pull-up bar.', 170),

    ('sandbag', 'Sandbag (filled, 40–80 lb)', 'sandbag',
     50, 180, 'low',
     'Odd-object carries are the single most AR-specific strength stimulus — '
     'irregular load, awkward grip, replicates carrying gear or a teammate.', 210),
    ('rings', 'Gymnastic Rings', 'rings',
     30, 80, 'low',
     'Advanced bodyweight pulling, dips, and shoulder-stability work. Pairs '
     'with the pull-up bar — minimal incremental cost, high ceiling.', 220),
    ('jump_rope', 'Speed Jump Rope', 'jump_rope',
     15, 40, 'low',
     'Calf / ankle prep, footwork, conditioning warm-up. Trivial cost. Good '
     'for hotel-room bursts when an erg is unavailable.', 230),
    ('ab_wheel', 'Ab Wheel', 'ab_wheel',
     15, 40, 'low',
     'Anti-extension core work that hits harder than planks. Cheap; one of '
     'the best ROI accessories.', 240),
    ('slam_ball', 'Slam Ball (20–40 lb)', 'slam_ball',
     40, 120, 'low',
     'Power output without ballistic shoulder load. Floor slams, rotational '
     'throws — useful for paddle-stroke power transfer.', 250),
    ('rowing_erg', 'Rowing Erg (Concept2)', 'rowing_erg',
     900, 1100, 'low',
     'Premium pulling-pattern aerobic work and the closest land-based proxy '
     'for paddle endurance. Big-ticket; only worth it once foundational gear '
     'is in place.', 260),
]


def _seed_purchase_recommendations(executor, tag_to_id):
    """Seed the shared purchase_recommendations catalog. Idempotent —
    UPSERT on slug so copy/cost edits propagate to existing rows on every
    cold start, while purchase_id stays stable for any user state already
    referencing it. Caller supplies the equipment_items tag→id map (already
    built upstream during equipment seeding)."""
    sql = (
        'INSERT INTO purchase_recommendations '
        '(slug, label, equipment_id, est_cost_low, est_cost_high, '
        ' priority, rationale, sort_order, active) '
        'VALUES (%s,%s,%s,%s,%s,%s,%s,%s,1) '
        'ON CONFLICT (slug) DO UPDATE SET '
        '  label=EXCLUDED.label, equipment_id=EXCLUDED.equipment_id, '
        '  est_cost_low=EXCLUDED.est_cost_low, '
        '  est_cost_high=EXCLUDED.est_cost_high, '
        '  priority=EXCLUDED.priority, rationale=EXCLUDED.rationale, '
        '  sort_order=EXCLUDED.sort_order, active=1'
    )
    for slug, label, eq_tag, lo, hi, prio, rationale, sort in PURCHASE_RECOMMENDATIONS:
        eq_id = tag_to_id.get(eq_tag)
        executor.execute(sql, (slug, label, eq_id, lo, hi, prio, rationale, sort))


# Bucket C sub-item (g) — see _PG_MIGRATIONS tail entry for the rationale.
# SURFACE-only mapping: terrain rows describe the physical surface;
# modality (foot/bike/paddle) is captured discipline-side + equipment-side.
# open_water_paddle uses the conservative {TRN-009} mapping (Flat Water);
# athlete can add Moving/Whitewater/Ocean explicitly on next edit.
_OUTDOOR_TERRAIN_TAG_TO_TRN_IDS: dict[str, list[str]] = {
    "trail_running":     ["TRN-002", "TRN-003"],   # Groomed + Technical singletrack
    "road_running":      ["TRN-001"],              # Road / Paved
    "road_cycling":      ["TRN-001"],              # same paved surface (modality discipline-side)
    "mtb_trails":        ["TRN-002", "TRN-003"],   # same dirt singletrack (modality discipline-side)
    "gravel_routes":     ["TRN-020"],              # NEW gravel row (Bucket C (g))
    "pool_swim":         ["TRN-008"],              # Pool
    "open_water_swim":   ["TRN-009", "TRN-010"],   # Flat Water + Ocean / Tidal
    "open_water_paddle": ["TRN-009"],              # conservative: Flat Water only
    "hills":             ["TRN-004"],              # Hill / Rolling (not Mountain/Alpine)
}


def _retire_outdoor_terrain_equipment_tags(cur):
    """Bucket C (g) — translate locale_equipment + locale_equipment_overrides
    picks for the 9 retired "Outdoor & Terrain" equipment tags into
    locale_profiles.locale_terrain_ids, then delete the source rows and the
    equipment_items rows themselves.

    Fully idempotent: re-running after a successful pass is a no-op (the
    retired tag rows no longer exist in equipment_items, so the JOIN
    filters everything out; the UPDATE matches zero locales and the
    DELETEs are also no-ops). Safe on fresh deploys where the tags never
    existed in the first place.
    """
    retired_tags = list(_OUTDOOR_TERRAIN_TAG_TO_TRN_IDS.keys())

    # Build a SQL VALUES clause mapping tag → TRN-xxx array so the
    # translation can happen in a single set-based UPDATE rather than
    # row-by-row. Quoting is safe — keys are fixed constants in this module.
    mapping_rows = ",\n        ".join(
        "('{tag}', ARRAY[{trns}]::TEXT[])".format(
            tag=tag,
            trns=", ".join(f"'{tid}'" for tid in trns),
        )
        for tag, trns in _OUTDOOR_TERRAIN_TAG_TO_TRN_IDS.items()
    )

    # Step 1a — translate locale_equipment (private locales): for each
    # (user_id, locale) with at least one retired tag, UNION the mapped
    # TRN-xxx ids into locale_terrain_ids, deduped, preserving existing.
    cur.execute(f"""
        WITH tag_mapping(tag, trns) AS (
            VALUES {mapping_rows}
        ),
        translated AS (
            SELECT
                le.user_id,
                le.locale,
                ARRAY_AGG(DISTINCT trn) AS mapped_trns
            FROM locale_equipment le
            JOIN equipment_items ei ON ei.id = le.equipment_id
            JOIN tag_mapping tm ON tm.tag = ei.tag
            CROSS JOIN LATERAL unnest(tm.trns) AS trn
            GROUP BY le.user_id, le.locale
        )
        UPDATE locale_profiles lp
        SET locale_terrain_ids = ARRAY(
            SELECT DISTINCT t
            FROM unnest(lp.locale_terrain_ids || tr.mapped_trns) AS t
        )
        FROM translated tr
        WHERE lp.user_id = tr.user_id AND lp.locale = tr.locale
    """)

    # Step 1b — translate locale_equipment_overrides (shared-profile
    # locales): only action='add' overrides translate to terrain picks
    # (action='remove' was a no-op against shared baseline which is also
    # being retired). equipment_tag is the direct string, no JOIN needed.
    cur.execute(f"""
        WITH tag_mapping(tag, trns) AS (
            VALUES {mapping_rows}
        ),
        translated AS (
            SELECT
                leo.user_id,
                leo.locale,
                ARRAY_AGG(DISTINCT trn) AS mapped_trns
            FROM locale_equipment_overrides leo
            JOIN tag_mapping tm ON tm.tag = leo.equipment_tag
            CROSS JOIN LATERAL unnest(tm.trns) AS trn
            WHERE leo.action = 'add'
            GROUP BY leo.user_id, leo.locale
        )
        UPDATE locale_profiles lp
        SET locale_terrain_ids = ARRAY(
            SELECT DISTINCT t
            FROM unnest(lp.locale_terrain_ids || tr.mapped_trns) AS t
        )
        FROM translated tr
        WHERE lp.user_id = tr.user_id AND lp.locale = tr.locale
    """)

    # Step 2a — drop the per-locale picks pointing at the retired tags.
    cur.execute("""
        DELETE FROM locale_equipment
        WHERE equipment_id IN (
            SELECT id FROM equipment_items WHERE tag = ANY(%s)
        )
    """, (retired_tags,))

    # Step 2b — drop both add and remove overrides for the retired tags
    # (remove against a non-existent baseline is moot).
    cur.execute("""
        DELETE FROM locale_equipment_overrides
        WHERE equipment_tag = ANY(%s)
    """, (retired_tags,))

    # Step 3 — drop the 9 equipment_items rows themselves. No
    # exercise_equipment FK risk: none of the EXERCISE_EQUIPMENT seed
    # entries reference any of these 9 tags (verified at slice scoping).
    cur.execute("""
        DELETE FROM equipment_items
        WHERE tag = ANY(%s)
    """, (retired_tags,))


_PG_MIGRATIONS = [
    "ALTER TABLE cardio_log ADD COLUMN IF NOT EXISTS stride_length_m REAL",
    "ALTER TABLE cardio_log ADD COLUMN IF NOT EXISTS vert_oscillation_cm REAL",
    "ALTER TABLE cardio_log ADD COLUMN IF NOT EXISTS vert_ratio_pct REAL",
    "ALTER TABLE cardio_log ADD COLUMN IF NOT EXISTS gct_ms REAL",
    "ALTER TABLE cardio_log ADD COLUMN IF NOT EXISTS gct_balance TEXT",
    "ALTER TABLE exercise_inventory ADD COLUMN IF NOT EXISTS weight_increment REAL",
    "ALTER TABLE current_rx ADD COLUMN IF NOT EXISTS consecutive_failures INTEGER DEFAULT 0",
    "ALTER TABLE current_rx ADD COLUMN IF NOT EXISTS weight_increment REAL",
    "ALTER TABLE current_rx ADD COLUMN IF NOT EXISTS next_sets INTEGER",
    "ALTER TABLE current_rx ADD COLUMN IF NOT EXISTS next_reps INTEGER",
    "ALTER TABLE current_rx ADD COLUMN IF NOT EXISTS next_weight REAL",
    "CREATE TABLE IF NOT EXISTS locale_profiles (locale TEXT PRIMARY KEY, equipment TEXT DEFAULT '', notes TEXT DEFAULT '', updated_at TIMESTAMP DEFAULT NOW())",
    "CREATE TABLE IF NOT EXISTS equipment_items (id SERIAL PRIMARY KEY, tag TEXT NOT NULL UNIQUE, label TEXT NOT NULL, category TEXT NOT NULL)",
    "CREATE TABLE IF NOT EXISTS exercise_equipment (exercise_id INTEGER NOT NULL REFERENCES exercise_inventory(id), equipment_id INTEGER NOT NULL REFERENCES equipment_items(id), option_group INTEGER NOT NULL DEFAULT 1, PRIMARY KEY (exercise_id, equipment_id))",
    "CREATE TABLE IF NOT EXISTS locale_equipment (locale TEXT NOT NULL REFERENCES locale_profiles(locale), equipment_id INTEGER NOT NULL REFERENCES equipment_items(id), PRIMARY KEY (locale, equipment_id))",
    "CREATE TABLE IF NOT EXISTS injury_exercise_modifications (id SERIAL PRIMARY KEY, injury_id INTEGER NOT NULL REFERENCES injury_log(id), exercise_id INTEGER NOT NULL REFERENCES exercise_inventory(id), substitute_exercise_id INTEGER REFERENCES exercise_inventory(id), modification_type TEXT NOT NULL DEFAULT 'modify', modification_notes TEXT, created_at TIMESTAMP DEFAULT NOW())",
    "ALTER TABLE cardio_log ADD COLUMN IF NOT EXISTS plan_item_id INTEGER REFERENCES plan_items(id)",
    "ALTER TABLE training_log ADD COLUMN IF NOT EXISTS plan_item_id INTEGER REFERENCES plan_items(id)",
    "ALTER TABLE conditions_log ADD COLUMN IF NOT EXISTS cardio_log_id INTEGER REFERENCES cardio_log(id)",
    "ALTER TABLE training_log ADD COLUMN IF NOT EXISTS exercise_id INTEGER REFERENCES exercise_inventory(id)",
    "UPDATE training_log SET exercise_id = ei.id FROM exercise_inventory ei WHERE ei.exercise = training_log.exercise AND training_log.exercise_id IS NULL",
    "ALTER TABLE current_rx ADD COLUMN IF NOT EXISTS exercise_id INTEGER REFERENCES exercise_inventory(id)",
    "UPDATE current_rx SET exercise_id = ei.id FROM exercise_inventory ei WHERE ei.exercise = current_rx.exercise AND current_rx.exercise_id IS NULL",
    "ALTER TABLE locale_equipment ADD CONSTRAINT IF NOT EXISTS locale_equipment_locale_fk FOREIGN KEY (locale) REFERENCES locale_profiles(locale)",
    "CREATE TABLE IF NOT EXISTS plan_reviews (id SERIAL PRIMARY KEY, plan_id INTEGER NOT NULL REFERENCES training_plans(id), tier INTEGER NOT NULL, sessions_reviewed INTEGER DEFAULT 0, notes TEXT, created_at TIMESTAMP DEFAULT NOW())",
    "ALTER TABLE cardio_log ADD COLUMN IF NOT EXISTS garmin_activity_id TEXT",
    "ALTER TABLE training_log ADD COLUMN IF NOT EXISTS garmin_activity_id TEXT",
    "CREATE TABLE IF NOT EXISTS coaching_preferences (id SERIAL PRIMARY KEY, category TEXT NOT NULL DEFAULT 'general', content TEXT NOT NULL, permanent INTEGER NOT NULL DEFAULT 1, created_at TIMESTAMP DEFAULT NOW())",
    "CREATE TABLE IF NOT EXISTS coaching_chat (id SERIAL PRIMARY KEY, plan_id INTEGER REFERENCES training_plans(id), role TEXT NOT NULL, content TEXT NOT NULL, actions_json TEXT, created_at TIMESTAMP DEFAULT NOW())",
    "ALTER TABLE plan_items ADD COLUMN IF NOT EXISTS calorie_target TEXT",
    "ALTER TABLE plan_items ADD COLUMN IF NOT EXISTS macro_carb_pct INTEGER",
    "ALTER TABLE plan_items ADD COLUMN IF NOT EXISTS macro_protein_pct INTEGER",
    "ALTER TABLE plan_items ADD COLUMN IF NOT EXISTS macro_fat_pct INTEGER",
    "ALTER TABLE plan_items ADD COLUMN IF NOT EXISTS session_fueling TEXT",
    "ALTER TABLE locale_profiles ADD COLUMN IF NOT EXISTS city TEXT DEFAULT ''",
    "CREATE TABLE IF NOT EXISTS plan_travel (id SERIAL PRIMARY KEY, plan_id INTEGER NOT NULL REFERENCES training_plans(id), start_date TEXT NOT NULL, end_date TEXT NOT NULL, locale TEXT NOT NULL, city TEXT DEFAULT '', notes TEXT DEFAULT '', created_at TIMESTAMP DEFAULT NOW())",
    "CREATE TABLE IF NOT EXISTS training_sessions (id SERIAL PRIMARY KEY, date TEXT NOT NULL, notes TEXT, plan_item_id INTEGER REFERENCES plan_items(id), created_at TIMESTAMP DEFAULT NOW())",
    "CREATE TABLE IF NOT EXISTS training_log_sets (id SERIAL PRIMARY KEY, training_log_id INTEGER NOT NULL REFERENCES training_log(id) ON DELETE CASCADE, set_number INTEGER NOT NULL, reps INTEGER, weight_kg REAL, duration_sec INTEGER)",
    "ALTER TABLE training_log ADD COLUMN IF NOT EXISTS session_id INTEGER REFERENCES training_sessions(id)",
    "CREATE INDEX IF NOT EXISTS idx_tl_session ON training_log(session_id)",
    "CREATE INDEX IF NOT EXISTS idx_tls_log ON training_log_sets(training_log_id)",
    "CREATE INDEX IF NOT EXISTS idx_ts_date ON training_sessions(date)",
    "CREATE TABLE IF NOT EXISTS clothing_options (id SERIAL PRIMARY KEY, category TEXT NOT NULL, value TEXT NOT NULL, UNIQUE(category, value))",
    "ALTER TABLE plan_travel ADD COLUMN IF NOT EXISTS indoor_only INTEGER DEFAULT 0",
    "ALTER TABLE training_plans ADD COLUMN IF NOT EXISTS race_goals TEXT DEFAULT ''",
    "CREATE TABLE IF NOT EXISTS wellness_log (id SERIAL PRIMARY KEY, date TEXT NOT NULL, timestamp_ms BIGINT NOT NULL, heart_rate INTEGER, stress_level INTEGER, body_battery INTEGER, respiration_rate REAL, steps INTEGER, active_calories INTEGER, active_time_s REAL, distance_m REAL, activity_type INTEGER, source TEXT DEFAULT 'wellness_fit', UNIQUE(timestamp_ms))",
    "CREATE INDEX IF NOT EXISTS idx_wl_date ON wellness_log(date)",
    "ALTER TABLE current_rx ADD COLUMN IF NOT EXISTS next_duration INTEGER",
    "ALTER TABLE training_log ADD COLUMN IF NOT EXISTS next_duration INTEGER",
    "ALTER TABLE current_rx ADD COLUMN IF NOT EXISTS sessions_since_progress INTEGER DEFAULT 0",
    "CREATE TABLE IF NOT EXISTS plan_item_disposition (id SERIAL PRIMARY KEY, plan_item_id INTEGER NOT NULL REFERENCES plan_items(id), log_type TEXT NOT NULL, log_id INTEGER NOT NULL, disposition TEXT NOT NULL, reason TEXT, created_at TIMESTAMP DEFAULT NOW())",
    "CREATE INDEX IF NOT EXISTS idx_pid_plan ON plan_item_disposition(plan_item_id)",
    "CREATE INDEX IF NOT EXISTS idx_pid_log ON plan_item_disposition(log_type, log_id)",
    "CREATE TABLE IF NOT EXISTS feedback_log (id SERIAL PRIMARY KEY, source TEXT NOT NULL, source_ref_id INTEGER, raw_content TEXT NOT NULL, captured_at TIMESTAMP DEFAULT NOW())",
    "CREATE INDEX IF NOT EXISTS idx_fb_captured ON feedback_log(captured_at)",
    "ALTER TABLE coaching_preferences ADD COLUMN IF NOT EXISTS source_feedback_id INTEGER REFERENCES feedback_log(id)",
    "CREATE TABLE IF NOT EXISTS users (id SERIAL PRIMARY KEY, username TEXT NOT NULL UNIQUE, email TEXT UNIQUE, password_hash TEXT NOT NULL, display_name TEXT, created_at TIMESTAMP DEFAULT NOW(), last_login TIMESTAMP)",
    # Session 2A — drop dead tables (no live consumers)
    "DROP TABLE IF EXISTS equipment_matrix",
    "DROP TABLE IF EXISTS recommended_purchases",
    # Session 2A — add user_id columns to per-user tables. NULLABLE for now;
    # query scoping ships in Session 2B/C, NOT NULL constraint lands in 2D.
    "ALTER TABLE training_sessions ADD COLUMN IF NOT EXISTS user_id INTEGER REFERENCES users(id)",
    "ALTER TABLE training_log ADD COLUMN IF NOT EXISTS user_id INTEGER REFERENCES users(id)",
    "ALTER TABLE training_log_sets ADD COLUMN IF NOT EXISTS user_id INTEGER REFERENCES users(id)",
    "ALTER TABLE current_rx ADD COLUMN IF NOT EXISTS user_id INTEGER REFERENCES users(id)",
    "ALTER TABLE cardio_log ADD COLUMN IF NOT EXISTS user_id INTEGER REFERENCES users(id)",
    "ALTER TABLE body_metrics ADD COLUMN IF NOT EXISTS user_id INTEGER REFERENCES users(id)",
    "ALTER TABLE conditions_log ADD COLUMN IF NOT EXISTS user_id INTEGER REFERENCES users(id)",
    "ALTER TABLE injury_log ADD COLUMN IF NOT EXISTS user_id INTEGER REFERENCES users(id)",
    "ALTER TABLE training_plans ADD COLUMN IF NOT EXISTS user_id INTEGER REFERENCES users(id)",
    "ALTER TABLE plan_items ADD COLUMN IF NOT EXISTS user_id INTEGER REFERENCES users(id)",
    "ALTER TABLE plan_item_disposition ADD COLUMN IF NOT EXISTS user_id INTEGER REFERENCES users(id)",
    "ALTER TABLE feedback_log ADD COLUMN IF NOT EXISTS user_id INTEGER REFERENCES users(id)",
    "ALTER TABLE coaching_preferences ADD COLUMN IF NOT EXISTS user_id INTEGER REFERENCES users(id)",
    "ALTER TABLE coaching_chat ADD COLUMN IF NOT EXISTS user_id INTEGER REFERENCES users(id)",
    "ALTER TABLE garmin_auth ADD COLUMN IF NOT EXISTS user_id INTEGER REFERENCES users(id)",
    "ALTER TABLE garmin_workouts ADD COLUMN IF NOT EXISTS user_id INTEGER REFERENCES users(id)",
    "ALTER TABLE locale_profiles ADD COLUMN IF NOT EXISTS user_id INTEGER REFERENCES users(id)",
    "ALTER TABLE wellness_log ADD COLUMN IF NOT EXISTS user_id INTEGER REFERENCES users(id)",
    # Backfill parent tables — guarded by user-1 existence.
    "UPDATE training_sessions   SET user_id = 1 WHERE user_id IS NULL AND EXISTS (SELECT 1 FROM users WHERE id = 1)",
    "UPDATE training_log        SET user_id = 1 WHERE user_id IS NULL AND EXISTS (SELECT 1 FROM users WHERE id = 1)",
    "UPDATE current_rx          SET user_id = 1 WHERE user_id IS NULL AND EXISTS (SELECT 1 FROM users WHERE id = 1)",
    "UPDATE cardio_log          SET user_id = 1 WHERE user_id IS NULL AND EXISTS (SELECT 1 FROM users WHERE id = 1)",
    "UPDATE body_metrics        SET user_id = 1 WHERE user_id IS NULL AND EXISTS (SELECT 1 FROM users WHERE id = 1)",
    "UPDATE conditions_log      SET user_id = 1 WHERE user_id IS NULL AND EXISTS (SELECT 1 FROM users WHERE id = 1)",
    "UPDATE injury_log          SET user_id = 1 WHERE user_id IS NULL AND EXISTS (SELECT 1 FROM users WHERE id = 1)",
    "UPDATE training_plans      SET user_id = 1 WHERE user_id IS NULL AND EXISTS (SELECT 1 FROM users WHERE id = 1)",
    "UPDATE feedback_log        SET user_id = 1 WHERE user_id IS NULL AND EXISTS (SELECT 1 FROM users WHERE id = 1)",
    "UPDATE coaching_preferences SET user_id = 1 WHERE user_id IS NULL AND EXISTS (SELECT 1 FROM users WHERE id = 1)",
    "UPDATE garmin_auth         SET user_id = 1 WHERE user_id IS NULL AND EXISTS (SELECT 1 FROM users WHERE id = 1)",
    "UPDATE garmin_workouts     SET user_id = 1 WHERE user_id IS NULL AND EXISTS (SELECT 1 FROM users WHERE id = 1)",
    "UPDATE locale_profiles     SET user_id = 1 WHERE user_id IS NULL AND EXISTS (SELECT 1 FROM users WHERE id = 1)",
    "UPDATE wellness_log        SET user_id = 1 WHERE user_id IS NULL AND EXISTS (SELECT 1 FROM users WHERE id = 1)",
    # Denormalized children — pull from parent.
    "UPDATE plan_items SET user_id = tp.user_id FROM training_plans tp WHERE tp.id = plan_items.plan_id AND plan_items.user_id IS NULL",
    "UPDATE plan_item_disposition SET user_id = pi.user_id FROM plan_items pi WHERE pi.id = plan_item_disposition.plan_item_id AND plan_item_disposition.user_id IS NULL",
    "UPDATE coaching_chat SET user_id = tp.user_id FROM training_plans tp WHERE tp.id = coaching_chat.plan_id AND coaching_chat.user_id IS NULL",
    "UPDATE training_log_sets SET user_id = tl.user_id FROM training_log tl WHERE tl.id = training_log_sets.training_log_id AND training_log_sets.user_id IS NULL",
    # Composite indexes for the date-filtered hot queries.
    "CREATE INDEX IF NOT EXISTS idx_tl_user_date ON training_log(user_id, date)",
    "CREATE INDEX IF NOT EXISTS idx_cl_user_date ON cardio_log(user_id, date)",
    "CREATE INDEX IF NOT EXISTS idx_bm_user_date ON body_metrics(user_id, date)",
    "CREATE INDEX IF NOT EXISTS idx_cond_user_date ON conditions_log(user_id, date)",
    "CREATE INDEX IF NOT EXISTS idx_ts_user_date ON training_sessions(user_id, date)",
    "CREATE INDEX IF NOT EXISTS idx_wl_user_date ON wellness_log(user_id, date)",
    "CREATE INDEX IF NOT EXISTS idx_pi_user_date ON plan_items(user_id, item_date)",
    # Session 2D — composite UNIQUE replacements. Drop the legacy single-col
    # constraint (auto-named <table>_<col>_key by Postgres) and add the
    # composite. Wrapped in DO blocks so the ADD is idempotent across cold
    # starts. The runner's try/except still catches anything unexpected.
    "ALTER TABLE current_rx DROP CONSTRAINT IF EXISTS current_rx_exercise_key",
    """DO $$ BEGIN
        IF NOT EXISTS (SELECT 1 FROM pg_constraint WHERE conname = 'current_rx_user_id_exercise_key') THEN
            ALTER TABLE current_rx ADD CONSTRAINT current_rx_user_id_exercise_key UNIQUE (user_id, exercise);
        END IF;
       END $$""",
    "ALTER TABLE body_metrics DROP CONSTRAINT IF EXISTS body_metrics_date_key",
    """DO $$ BEGIN
        IF NOT EXISTS (SELECT 1 FROM pg_constraint WHERE conname = 'body_metrics_user_id_date_key') THEN
            ALTER TABLE body_metrics ADD CONSTRAINT body_metrics_user_id_date_key UNIQUE (user_id, date);
        END IF;
       END $$""",
    "ALTER TABLE wellness_log DROP CONSTRAINT IF EXISTS wellness_log_timestamp_ms_key",
    """DO $$ BEGIN
        IF NOT EXISTS (SELECT 1 FROM pg_constraint WHERE conname = 'wellness_log_user_id_timestamp_ms_key') THEN
            ALTER TABLE wellness_log ADD CONSTRAINT wellness_log_user_id_timestamp_ms_key UNIQUE (user_id, timestamp_ms);
        END IF;
       END $$""",
    # Session 2D — NOT NULL on user_id columns. SET NOT NULL is idempotent on
    # already-NOT-NULL columns. Will fail until the per-table backfill above
    # runs to completion (the migration runner catches the failure and the
    # next cold start retries — eventually consistent on Andy's bootstrap).
    "ALTER TABLE training_sessions   ALTER COLUMN user_id SET NOT NULL",
    "ALTER TABLE training_log        ALTER COLUMN user_id SET NOT NULL",
    "ALTER TABLE training_log_sets   ALTER COLUMN user_id SET NOT NULL",
    "ALTER TABLE current_rx          ALTER COLUMN user_id SET NOT NULL",
    "ALTER TABLE cardio_log          ALTER COLUMN user_id SET NOT NULL",
    "ALTER TABLE body_metrics        ALTER COLUMN user_id SET NOT NULL",
    "ALTER TABLE conditions_log      ALTER COLUMN user_id SET NOT NULL",
    "ALTER TABLE injury_log          ALTER COLUMN user_id SET NOT NULL",
    "ALTER TABLE training_plans      ALTER COLUMN user_id SET NOT NULL",
    "ALTER TABLE plan_items          ALTER COLUMN user_id SET NOT NULL",
    "ALTER TABLE plan_item_disposition ALTER COLUMN user_id SET NOT NULL",
    "ALTER TABLE feedback_log        ALTER COLUMN user_id SET NOT NULL",
    "ALTER TABLE coaching_preferences ALTER COLUMN user_id SET NOT NULL",
    "ALTER TABLE coaching_chat       ALTER COLUMN user_id SET NOT NULL",
    "ALTER TABLE garmin_auth         ALTER COLUMN user_id SET NOT NULL",
    "ALTER TABLE garmin_workouts     ALTER COLUMN user_id SET NOT NULL",
    "ALTER TABLE locale_profiles     ALTER COLUMN user_id SET NOT NULL",
    "ALTER TABLE wellness_log        ALTER COLUMN user_id SET NOT NULL",
    # Session 3 — clothing_options per-user
    "ALTER TABLE clothing_options ADD COLUMN IF NOT EXISTS user_id INTEGER REFERENCES users(id)",
    "UPDATE clothing_options SET user_id = 1 WHERE user_id IS NULL AND EXISTS (SELECT 1 FROM users WHERE id = 1)",
    "ALTER TABLE clothing_options DROP CONSTRAINT IF EXISTS clothing_options_category_value_key",
    """DO $$ BEGIN
        IF NOT EXISTS (SELECT 1 FROM pg_constraint WHERE conname = 'clothing_options_user_id_category_value_key') THEN
            ALTER TABLE clothing_options ADD CONSTRAINT clothing_options_user_id_category_value_key UNIQUE (user_id, category, value);
        END IF;
       END $$""",
    "DELETE FROM clothing_options WHERE user_id IS NULL",
    "ALTER TABLE clothing_options ALTER COLUMN user_id SET NOT NULL",
    # Session 3 — locale_equipment gain user_id (denormalized from parent)
    "ALTER TABLE locale_equipment ADD COLUMN IF NOT EXISTS user_id INTEGER REFERENCES users(id)",
    """UPDATE locale_equipment SET user_id = lp.user_id
       FROM locale_profiles lp WHERE lp.locale = locale_equipment.locale
       AND locale_equipment.user_id IS NULL""",
    # Session 3 — locale_profiles PK becomes composite (user_id, locale).
    # Drop dependent FKs first, swap PK, then re-create FKs.
    "ALTER TABLE locale_equipment DROP CONSTRAINT IF EXISTS locale_equipment_locale_fkey",
    "ALTER TABLE locale_equipment DROP CONSTRAINT IF EXISTS locale_equipment_locale_fk",
    "ALTER TABLE locale_profiles DROP CONSTRAINT IF EXISTS locale_profiles_pkey",
    """DO $$ BEGIN
        IF NOT EXISTS (SELECT 1 FROM pg_constraint WHERE conname = 'locale_profiles_pkey') THEN
            ALTER TABLE locale_profiles ADD CONSTRAINT locale_profiles_pkey PRIMARY KEY (user_id, locale);
        END IF;
       END $$""",
    # locale_equipment composite PK + composite FK
    "ALTER TABLE locale_equipment DROP CONSTRAINT IF EXISTS locale_equipment_pkey",
    """DO $$ BEGIN
        IF NOT EXISTS (SELECT 1 FROM pg_constraint WHERE conname = 'locale_equipment_pkey') THEN
            ALTER TABLE locale_equipment ADD CONSTRAINT locale_equipment_pkey PRIMARY KEY (user_id, locale, equipment_id);
        END IF;
       END $$""",
    """DO $$ BEGIN
        IF NOT EXISTS (SELECT 1 FROM pg_constraint WHERE conname = 'locale_equipment_user_locale_fkey') THEN
            ALTER TABLE locale_equipment ADD CONSTRAINT locale_equipment_user_locale_fkey
              FOREIGN KEY (user_id, locale) REFERENCES locale_profiles(user_id, locale);
        END IF;
       END $$""",
    "ALTER TABLE locale_equipment ALTER COLUMN user_id SET NOT NULL",
    # Session 4 — athlete profile.
    """CREATE TABLE IF NOT EXISTS athlete_profile (
        user_id INTEGER PRIMARY KEY REFERENCES users(id),
        date_of_birth TEXT, sex TEXT, height_cm REAL,
        primary_sport TEXT,
        weekly_hours_target REAL, notes TEXT,
        body_weight_kg REAL, hrmax_bpm INTEGER,
        lactate_threshold_hr_bpm INTEGER, vo2max REAL, cycling_ftp_w INTEGER,
        doubles_feasible TEXT,
        updated_at TIMESTAMP DEFAULT NOW()
    )""",
    # Session 5 — recommended-purchases rebuild.
    """CREATE TABLE IF NOT EXISTS purchase_recommendations (
        id SERIAL PRIMARY KEY,
        slug TEXT NOT NULL UNIQUE, label TEXT NOT NULL,
        equipment_id INTEGER REFERENCES equipment_items(id),
        est_cost_low INTEGER, est_cost_high INTEGER,
        priority TEXT NOT NULL DEFAULT 'medium',
        rationale TEXT, sort_order INTEGER NOT NULL DEFAULT 0,
        active INTEGER NOT NULL DEFAULT 1
    )""",
    """CREATE TABLE IF NOT EXISTS user_purchase_recommendations (
        user_id INTEGER NOT NULL REFERENCES users(id),
        purchase_id INTEGER NOT NULL REFERENCES purchase_recommendations(id),
        status TEXT NOT NULL, user_notes TEXT,
        updated_at TIMESTAMP DEFAULT NOW(),
        PRIMARY KEY (user_id, purchase_id)
    )""",
    # Session 6 — password reset tokens. Single-use, time-limited.
    """CREATE TABLE IF NOT EXISTS password_resets (
        token TEXT PRIMARY KEY,
        user_id INTEGER NOT NULL REFERENCES users(id),
        created_at TIMESTAMP NOT NULL DEFAULT NOW(),
        expires_at TIMESTAMP NOT NULL,
        used_at TIMESTAMP
    )""",
    "CREATE INDEX IF NOT EXISTS password_resets_user_id_idx ON password_resets(user_id)",
    # Admin action audit log. See SQLite migration above for rationale.
    """CREATE TABLE IF NOT EXISTS admin_audit (
        id SERIAL PRIMARY KEY,
        actor_user_id INTEGER REFERENCES users(id),
        action TEXT NOT NULL,
        target_user_id INTEGER,
        target_username TEXT,
        details TEXT,
        created_at TIMESTAMP NOT NULL DEFAULT NOW()
    )""",
    "CREATE INDEX IF NOT EXISTS admin_audit_created_at_idx ON admin_audit(created_at DESC)",
    # Per-user API tokens. See SQLite migration above for rationale.
    """CREATE TABLE IF NOT EXISTS api_tokens (
        id SERIAL PRIMARY KEY,
        user_id INTEGER NOT NULL REFERENCES users(id),
        name TEXT NOT NULL,
        token_hash TEXT NOT NULL UNIQUE,
        created_at TIMESTAMP NOT NULL DEFAULT NOW(),
        last_used_at TIMESTAMP,
        revoked_at TIMESTAMP,
        expires_at TIMESTAMP
    )""",
    "CREATE INDEX IF NOT EXISTS api_tokens_user_id_idx ON api_tokens(user_id)",
    # `expires_at` was added after initial deploy.
    "ALTER TABLE api_tokens ADD COLUMN IF NOT EXISTS expires_at TIMESTAMP",
    # Per-day wellness self-report. See SQLite migration above for rationale.
    """CREATE TABLE IF NOT EXISTS wellness_self_report (
        id SERIAL PRIMARY KEY,
        user_id INTEGER NOT NULL REFERENCES users(id),
        date TEXT NOT NULL,
        sleep_hours REAL,
        sleep_quality INTEGER,
        energy INTEGER,
        soreness INTEGER,
        mood INTEGER,
        notes TEXT,
        created_at TIMESTAMP NOT NULL DEFAULT NOW(),
        updated_at TIMESTAMP NOT NULL DEFAULT NOW(),
        UNIQUE(user_id, date)
    )""",
    "CREATE INDEX IF NOT EXISTS wellness_self_report_user_date_idx ON wellness_self_report(user_id, date)",
    # #283 Phase B — Garmin daily-derived metrics from _METRICS.fit /
    # _SLEEP_DATA.fit / _HRV_STATUS.fit. One row per (user, date); each FIT
    # file UPSERTs the columns it owns (sleep_score may arrive from any of
    # the three sources, HRV from _HRV_STATUS only, etc.) so files can land
    # in any order without clobbering each other. `hrv_samples_json` carries
    # the overnight per-period series for the wellness chart's HRV card.
    # Columns left nullable cover metrics whose FIT field mapping isn't
    # locked yet (sleep stages, training readiness, VO2max, SpO2) — they'll
    # populate as the parser's TODO mappings are resolved.
    """CREATE TABLE IF NOT EXISTS garmin_daily_metrics (
        id SERIAL PRIMARY KEY,
        user_id INTEGER NOT NULL REFERENCES users(id),
        date TEXT NOT NULL,
        sleep_score INTEGER,
        sleep_start_ms BIGINT,
        sleep_end_ms BIGINT,
        sleep_awake_min INTEGER,
        sleep_avg_respiration REAL,
        sleep_contributors_json TEXT,
        sleep_light_sub_score INTEGER,
        sleep_rem_sub_score INTEGER,
        sleep_stress_sub_score INTEGER,
        sleep_awake_sub_score INTEGER,
        sleep_deep_min INTEGER,
        sleep_light_min INTEGER,
        sleep_rem_min INTEGER,
        sleep_stress_avg REAL,
        sleep_wake_count INTEGER,
        hrv_overnight_avg_ms REAL,
        hrv_7d_avg_ms REAL,
        hrv_samples_json TEXT,
        training_readiness INTEGER,
        vo2max_running REAL,
        vo2max_cycling REAL,
        spo2_avg INTEGER,
        spo2_low INTEGER,
        resting_metabolic_rate INTEGER,
        resting_hr INTEGER,
        resting_hr_7day_avg INTEGER,
        sleep_duration_sub_score INTEGER,
        hrv_highest_5min_ms REAL,
        heat_acclimation_pct INTEGER,
        acute_training_load INTEGER,
        created_at TIMESTAMP NOT NULL DEFAULT NOW(),
        updated_at TIMESTAMP NOT NULL DEFAULT NOW(),
        UNIQUE(user_id, date)
    )""",
    "CREATE INDEX IF NOT EXISTS garmin_daily_metrics_user_date_idx ON garmin_daily_metrics(user_id, date)",
    # Backfill columns for environments where garmin_daily_metrics was created
    # by an earlier migration (#460 / #463). IF NOT EXISTS keeps these
    # idempotent across re-runs.
    "ALTER TABLE garmin_daily_metrics ADD COLUMN IF NOT EXISTS resting_metabolic_rate INTEGER",
    "ALTER TABLE garmin_daily_metrics ADD COLUMN IF NOT EXISTS resting_hr INTEGER",
    "ALTER TABLE garmin_daily_metrics ADD COLUMN IF NOT EXISTS resting_hr_7day_avg INTEGER",
    "ALTER TABLE garmin_daily_metrics ADD COLUMN IF NOT EXISTS sleep_duration_sub_score INTEGER",
    "ALTER TABLE garmin_daily_metrics ADD COLUMN IF NOT EXISTS hrv_highest_5min_ms REAL",
    "ALTER TABLE garmin_daily_metrics ADD COLUMN IF NOT EXISTS heat_acclimation_pct INTEGER",
    "ALTER TABLE garmin_daily_metrics ADD COLUMN IF NOT EXISTS acute_training_load INTEGER",
    "ALTER TABLE garmin_daily_metrics ADD COLUMN IF NOT EXISTS restless_moments INTEGER",
    "ALTER TABLE garmin_daily_metrics ADD COLUMN IF NOT EXISTS floors_climbed INTEGER",
    "ALTER TABLE garmin_daily_metrics ADD COLUMN IF NOT EXISTS floors_descended INTEGER",
    "ALTER TABLE garmin_daily_metrics ADD COLUMN IF NOT EXISTS intensity_minutes INTEGER",
    # PR #489 — new mappings decoded from May 28 + May 30 reference data:
    # sleep_deep_min via [346] field_9 (already in the table create above
    # but Phase B environments may pre-date it), sleep_stress_avg derived
    # from [346] field_15 ÷ sample_count, sleep_wake_count from [382] field_2.
    "ALTER TABLE garmin_daily_metrics ADD COLUMN IF NOT EXISTS sleep_stress_avg REAL",
    "ALTER TABLE garmin_daily_metrics ADD COLUMN IF NOT EXISTS sleep_wake_count INTEGER",
    # `[346]` sub-score contributors (#283) — all 4 positions locked Jun 10
    # 2026 against 6 reference nights (Sep 8 2025 was the disambiguator).
    # field_5 = Light, field_7 = REM, field_8 = Stress, field_10 = Awake.
    "ALTER TABLE garmin_daily_metrics ADD COLUMN IF NOT EXISTS sleep_light_sub_score INTEGER",
    "ALTER TABLE garmin_daily_metrics ADD COLUMN IF NOT EXISTS sleep_rem_sub_score INTEGER",
    "ALTER TABLE garmin_daily_metrics ADD COLUMN IF NOT EXISTS sleep_stress_sub_score INTEGER",
    "ALTER TABLE garmin_daily_metrics ADD COLUMN IF NOT EXISTS sleep_awake_sub_score INTEGER",
    # D-50 Phase 1 — provider integration tables. Mirrors the SQLite block
    # above with PG-native types (SERIAL, TIMESTAMP DEFAULT NOW(), BIGINT,
    # BOOLEAN). Per Athlete_Data_Integration_Spec v3 §4–§6. Garmin paused
    # (D-55); no per-provider Garmin table here. Per spec §4.2, `payload`
    # stays TEXT (not JSONB) for dispatch-logic portability.
    """CREATE TABLE IF NOT EXISTS provider_auth (
        id SERIAL PRIMARY KEY,
        user_id INTEGER NOT NULL REFERENCES users(id),
        provider TEXT NOT NULL,
        access_token TEXT,
        refresh_token TEXT,
        token_expires_at TIMESTAMP,
        session_blob TEXT,
        provider_user_id TEXT,
        scopes TEXT,
        webhook_token TEXT,
        status TEXT,
        registered_at TIMESTAMP,
        created_at TIMESTAMP DEFAULT NOW(),
        updated_at TIMESTAMP DEFAULT NOW(),
        UNIQUE (user_id, provider)
    )""",
    "CREATE INDEX IF NOT EXISTS provider_auth_status_idx ON provider_auth (status) WHERE status IN ('error', 'pending_backfill')",
    """CREATE TABLE IF NOT EXISTS webhook_events (
        id SERIAL PRIMARY KEY,
        provider TEXT NOT NULL,
        event_type TEXT,
        provider_user_id TEXT,
        entity_id TEXT,
        user_id INTEGER REFERENCES users(id),
        payload TEXT,
        signature_ok BOOLEAN,
        received_at TIMESTAMP DEFAULT NOW(),
        processed_at TIMESTAMP,
        error TEXT
    )""",
    "CREATE INDEX IF NOT EXISTS idx_webhook_events_lookup ON webhook_events (provider, provider_user_id, entity_id, event_type)",
    "CREATE INDEX IF NOT EXISTS idx_webhook_events_pending ON webhook_events (received_at) WHERE processed_at IS NULL",
    """CREATE TABLE IF NOT EXISTS polar_sleep (
        id SERIAL PRIMARY KEY,
        user_id INTEGER NOT NULL REFERENCES users(id),
        date TEXT NOT NULL,
        sleep_start_time TIMESTAMP,
        sleep_end_time TIMESTAMP,
        total_sleep_min INTEGER,
        continuity REAL,
        light_sleep_min INTEGER,
        deep_sleep_min INTEGER,
        rem_sleep_min INTEGER,
        unknown_sleep_min INTEGER,
        stages_json TEXT,
        raw_payload TEXT,
        fetched_at TIMESTAMP DEFAULT NOW(),
        UNIQUE (user_id, date)
    )""",
    """CREATE TABLE IF NOT EXISTS polar_nightly_recharge (
        id SERIAL PRIMARY KEY,
        user_id INTEGER NOT NULL REFERENCES users(id),
        date TEXT NOT NULL,
        ans_charge INTEGER,
        ans_charge_status TEXT,
        hrv_rmssd_ms REAL,
        breathing_rate REAL,
        recovery_indicator TEXT,
        raw_payload TEXT,
        fetched_at TIMESTAMP DEFAULT NOW(),
        UNIQUE (user_id, date)
    )""",
    """CREATE TABLE IF NOT EXISTS polar_cardio_load (
        id SERIAL PRIMARY KEY,
        user_id INTEGER NOT NULL REFERENCES users(id),
        date TEXT NOT NULL,
        daily_load REAL,
        acute_load REAL,
        chronic_load REAL,
        cardio_load_status TEXT,
        strain REAL,
        raw_payload TEXT,
        fetched_at TIMESTAMP DEFAULT NOW(),
        UNIQUE (user_id, date)
    )""",
    """CREATE TABLE IF NOT EXISTS polar_continuous_hr_samples (
        id SERIAL PRIMARY KEY,
        user_id INTEGER NOT NULL REFERENCES users(id),
        timestamp_ms BIGINT NOT NULL,
        heart_rate INTEGER,
        UNIQUE (user_id, timestamp_ms)
    )""",
    "CREATE INDEX IF NOT EXISTS idx_polar_hr_user_time ON polar_continuous_hr_samples (user_id, timestamp_ms)",
    """CREATE TABLE IF NOT EXISTS wahoo_plans (
        id SERIAL PRIMARY KEY,
        user_id INTEGER NOT NULL REFERENCES users(id),
        plan_item_id INTEGER REFERENCES plan_items(id),
        wahoo_plan_id TEXT,
        wahoo_workout_id TEXT,
        external_id TEXT,
        provider_updated_at TIMESTAMP,
        status TEXT,
        push_payload TEXT,
        created_at TIMESTAMP DEFAULT NOW(),
        updated_at TIMESTAMP DEFAULT NOW()
    )""",
    "CREATE INDEX IF NOT EXISTS idx_wahoo_plans_plan_item ON wahoo_plans (plan_item_id)",
    """CREATE TABLE IF NOT EXISTS coros_daily_summary (
        id SERIAL PRIMARY KEY,
        user_id INTEGER NOT NULL REFERENCES users(id),
        happen_day TEXT NOT NULL,
        rhr INTEGER,
        calories INTEGER,
        steps INTEGER,
        ppg_hrv INTEGER,
        sleep_avg_hr INTEGER,
        sleep_start_ms BIGINT,
        sleep_end_ms BIGINT,
        raw_payload TEXT,
        fetched_at TIMESTAMP DEFAULT NOW(),
        UNIQUE (user_id, happen_day)
    )""",
    """CREATE TABLE IF NOT EXISTS coros_hrv_samples (
        id SERIAL PRIMARY KEY,
        user_id INTEGER NOT NULL REFERENCES users(id),
        timestamp_s BIGINT NOT NULL,
        hrv INTEGER,
        hr INTEGER,
        UNIQUE (user_id, timestamp_s)
    )""",
    """CREATE TABLE IF NOT EXISTS coros_plans (
        id SERIAL PRIMARY KEY,
        user_id INTEGER NOT NULL REFERENCES users(id),
        plan_item_id INTEGER REFERENCES plan_items(id),
        coros_label_id TEXT,
        push_payload TEXT,
        status TEXT,
        created_at TIMESTAMP DEFAULT NOW(),
        updated_at TIMESTAMP DEFAULT NOW()
    )""",
    "CREATE INDEX IF NOT EXISTS idx_coros_plans_plan_item ON coros_plans (plan_item_id)",
    # D-50 §6 — foreign-id columns on existing app tables for provider dedup.
    "ALTER TABLE cardio_log ADD COLUMN IF NOT EXISTS polar_exercise_id TEXT",
    "ALTER TABLE cardio_log ADD COLUMN IF NOT EXISTS wahoo_workout_id TEXT",
    "ALTER TABLE cardio_log ADD COLUMN IF NOT EXISTS coros_label_id TEXT",
    "ALTER TABLE cardio_log ADD COLUMN IF NOT EXISTS rwgps_trip_id TEXT",
    "ALTER TABLE training_log ADD COLUMN IF NOT EXISTS polar_exercise_id TEXT",
    "ALTER TABLE training_log ADD COLUMN IF NOT EXISTS wahoo_workout_id TEXT",
    "ALTER TABLE training_log ADD COLUMN IF NOT EXISTS coros_label_id TEXT",
    # D-58 §7 — provider-sourced prefill provenance + 14-day connect-provider
    # nudge. PG-only per Athlete_Data_Integration_Spec_v4 §2.5 (SQLite frozen).
    # `field_name` is free-text TEXT here; the canonical KNOWN_PROFILE_FIELDS
    # registry + insert validation lands with the prefill UI PR (Open Item #17).
    """CREATE TABLE IF NOT EXISTS athlete_profile_field_provenance (
        id SERIAL PRIMARY KEY,
        user_id INTEGER NOT NULL REFERENCES users(id),
        field_name TEXT NOT NULL,
        source TEXT NOT NULL,
        source_provider_id INTEGER REFERENCES provider_auth(id),
        source_synced_at TIMESTAMP,
        last_updated_at TIMESTAMP NOT NULL DEFAULT NOW(),
        UNIQUE (user_id, field_name)
    )""",
    "CREATE INDEX IF NOT EXISTS apfp_user_idx ON athlete_profile_field_provenance (user_id)",
    "CREATE INDEX IF NOT EXISTS apfp_user_source_idx ON athlete_profile_field_provenance (user_id, source) WHERE source = 'manual_override'",
    """CREATE TABLE IF NOT EXISTS account_nudges (
        id SERIAL PRIMARY KEY,
        user_id INTEGER NOT NULL REFERENCES users(id),
        nudge_type TEXT NOT NULL,
        created_at TIMESTAMP NOT NULL DEFAULT NOW(),
        displayed_at TIMESTAMP,
        dismissed_at TIMESTAMP,
        UNIQUE (user_id, nudge_type)
    )""",
    # v5 Account Config 3 — disclosure acknowledgment records. One row per
    # acknowledgment event. The `oauth_scope_<provider>` rows are written
    # by routes/provider_auth.py:record_oauth_scope_ack at OAuth callback
    # success (D-58 §7.3 / v5 Account Config 3). Re-acknowledgment writes a
    # new row; query MAX(acknowledged_at) per (user_id, disclosure_id) to
    # find current state.
    """CREATE TABLE IF NOT EXISTS disclosure_acknowledgments (
        id SERIAL PRIMARY KEY,
        user_id INTEGER NOT NULL REFERENCES users(id),
        disclosure_id TEXT NOT NULL,
        version_id TEXT,
        scopes_granted TEXT,
        delivery_method TEXT NOT NULL DEFAULT 'in_app',
        acknowledged_at TIMESTAMP NOT NULL DEFAULT NOW()
    )""",
    "CREATE INDEX IF NOT EXISTS disclosure_acks_user_idx ON disclosure_acknowledgments (user_id, disclosure_id, acknowledged_at DESC)",
    # D-59 §9 — `locale_profiles` columns for Mapbox-anchored place lookup +
    # chain detection. `locale_name` is the athlete-supplied display label
    # (replaces the v1 hardcoded `locale` enum at the UX layer; the column
    # itself coexists). `chain_id` is a FK-style pointer to chain_registry.py
    # GYM_CHAINS[].chain_id; `chain_name` is the denormalized canonical name.
    # `category` is set by chain detection and refined by D-60 design.
    # `manual_entry=TRUE` rows skip Mapbox; coords + chain stay NULL.
    "ALTER TABLE locale_profiles ADD COLUMN IF NOT EXISTS locale_name TEXT",
    "ALTER TABLE locale_profiles ADD COLUMN IF NOT EXISTS mapbox_id TEXT",
    "ALTER TABLE locale_profiles ADD COLUMN IF NOT EXISTS lat DOUBLE PRECISION",
    "ALTER TABLE locale_profiles ADD COLUMN IF NOT EXISTS lng DOUBLE PRECISION",
    "ALTER TABLE locale_profiles ADD COLUMN IF NOT EXISTS chain_id TEXT",
    "ALTER TABLE locale_profiles ADD COLUMN IF NOT EXISTS chain_name TEXT",
    "ALTER TABLE locale_profiles ADD COLUMN IF NOT EXISTS category TEXT",
    "ALTER TABLE locale_profiles ADD COLUMN IF NOT EXISTS manual_entry BOOLEAN DEFAULT FALSE",
    "ALTER TABLE locale_profiles ADD COLUMN IF NOT EXISTS place_payload TEXT",
    "ALTER TABLE locale_profiles ADD COLUMN IF NOT EXISTS place_fetched_at TIMESTAMP",
    # D-60 §5 — shared gym profiles + per-athlete overrides. JSON columns
    # (equipment, toggles, disputed_items) are written whole on each save;
    # see §5.1 rationale for not normalising. `private=TRUE` rows are
    # visible only to created_by_user_id (when an athlete has sharing
    # disabled at locale creation time).
    """CREATE TABLE IF NOT EXISTS gym_profiles (
        id SERIAL PRIMARY KEY,
        mapbox_id TEXT UNIQUE,
        address_fingerprint TEXT,
        display_name TEXT,
        category TEXT NOT NULL,
        equipment TEXT,
        toggles TEXT,
        disputed_items TEXT,
        private BOOLEAN DEFAULT FALSE,
        created_by_user_id INTEGER REFERENCES users(id),
        created_at TIMESTAMP DEFAULT NOW(),
        last_confirmed_by INTEGER REFERENCES users(id),
        last_confirmed_at TIMESTAMP DEFAULT NOW(),
        contribution_count INTEGER DEFAULT 1
    )""",
    "CREATE INDEX IF NOT EXISTS gym_profiles_mapbox_idx ON gym_profiles (mapbox_id) WHERE mapbox_id IS NOT NULL",
    "CREATE INDEX IF NOT EXISTS gym_profiles_address_idx ON gym_profiles (address_fingerprint) WHERE address_fingerprint IS NOT NULL",
    # PR2's original D-60 batch declared these tables with
    # `locale_id INTEGER NOT NULL REFERENCES locale_profiles(id)`, but
    # locale_profiles' PK is composite (user_id, locale) — there is no `id`
    # column. PG rejects the inline FK; the migration runner's try/except
    # swallows the error, so the tables never actually got created in
    # production. PR11 corrects the shape: `locale TEXT` keyed against the
    # composite PK via a composite FK. ON DELETE CASCADE so per-athlete
    # overrides go away when a locale row is deleted.
    """CREATE TABLE IF NOT EXISTS locale_equipment_overrides (
        id SERIAL PRIMARY KEY,
        user_id INTEGER NOT NULL REFERENCES users(id),
        locale TEXT NOT NULL,
        equipment_tag TEXT NOT NULL,
        action TEXT NOT NULL CHECK (action IN ('add', 'remove')),
        created_at TIMESTAMP DEFAULT NOW(),
        UNIQUE (user_id, locale, equipment_tag, action),
        FOREIGN KEY (user_id, locale) REFERENCES locale_profiles(user_id, locale) ON DELETE CASCADE
    )""",
    "CREATE INDEX IF NOT EXISTS leo_user_locale_idx ON locale_equipment_overrides (user_id, locale)",
    """CREATE TABLE IF NOT EXISTS locale_toggle_overrides (
        id SERIAL PRIMARY KEY,
        user_id INTEGER NOT NULL REFERENCES users(id),
        locale TEXT NOT NULL,
        toggle_name TEXT NOT NULL,
        value BOOLEAN NOT NULL,
        created_at TIMESTAMP DEFAULT NOW(),
        UNIQUE (user_id, locale, toggle_name),
        FOREIGN KEY (user_id, locale) REFERENCES locale_profiles(user_id, locale) ON DELETE CASCADE
    )""",
    # Idempotent fix-up: if a prior boot somehow created either table with
    # the broken `locale_id INTEGER` shape (e.g. partial-DDL state from a
    # PG version that accepted the inline FK as deferred), bring it to the
    # correct shape. No-op on clean deploys.
    """DO $$ BEGIN
        IF EXISTS (
            SELECT 1 FROM information_schema.columns
            WHERE table_name='locale_equipment_overrides' AND column_name='locale_id'
        ) THEN
            ALTER TABLE locale_equipment_overrides
                DROP CONSTRAINT IF EXISTS locale_equipment_overrides_locale_id_fkey;
            IF NOT EXISTS (
                SELECT 1 FROM information_schema.columns
                WHERE table_name='locale_equipment_overrides' AND column_name='locale'
            ) THEN
                ALTER TABLE locale_equipment_overrides ADD COLUMN locale TEXT;
            END IF;
            ALTER TABLE locale_equipment_overrides DROP COLUMN locale_id;
        END IF;
        IF EXISTS (
            SELECT 1 FROM information_schema.columns
            WHERE table_name='locale_toggle_overrides' AND column_name='locale_id'
        ) THEN
            ALTER TABLE locale_toggle_overrides
                DROP CONSTRAINT IF EXISTS locale_toggle_overrides_locale_id_fkey;
            IF NOT EXISTS (
                SELECT 1 FROM information_schema.columns
                WHERE table_name='locale_toggle_overrides' AND column_name='locale'
            ) THEN
                ALTER TABLE locale_toggle_overrides ADD COLUMN locale TEXT;
            END IF;
            ALTER TABLE locale_toggle_overrides DROP COLUMN locale_id;
        END IF;
    END $$""",
    "ALTER TABLE locale_profiles ADD COLUMN IF NOT EXISTS gym_profile_id INTEGER REFERENCES gym_profiles(id)",
    "ALTER TABLE locale_profiles ADD COLUMN IF NOT EXISTS sharing_opt_out BOOLEAN DEFAULT FALSE",
    # D-61 §7 — per-day availability windows. Primary-window rows (window_index=0)
    # exist for every athlete × 7 days at onboarding completion; secondary-window
    # rows (window_index=1) only when athlete picked Doubles Feasible ≠ No.
    # CHECK constraint pairs enabled with start/duration so disabled rows can't
    # carry stale values. `preferred` on locale_profiles flags an athlete's
    # default locale; no uniqueness — §4.3 semantics.
    """CREATE TABLE IF NOT EXISTS daily_availability_windows (
        id SERIAL PRIMARY KEY,
        user_id INTEGER NOT NULL REFERENCES users(id),
        day_of_week SMALLINT NOT NULL,
        window_index SMALLINT NOT NULL DEFAULT 0,
        enabled BOOLEAN NOT NULL DEFAULT FALSE,
        window_start TIME,
        window_duration_min INTEGER,
        updated_at TIMESTAMP DEFAULT NOW(),
        UNIQUE (user_id, day_of_week, window_index),
        CHECK (window_index IN (0, 1)),
        CHECK (
            (enabled = FALSE AND window_start IS NULL AND window_duration_min IS NULL)
            OR (enabled = TRUE AND window_start IS NOT NULL AND window_duration_min IS NOT NULL)
        ),
        CONSTRAINT daily_availability_windows_duration_bound
            CHECK (window_duration_min IS NULL OR window_duration_min BETWEEN 30 AND 720)
    )""",
    "CREATE INDEX IF NOT EXISTS daw_user_day_idx ON daily_availability_windows (user_id, day_of_week)",
    "ALTER TABLE locale_profiles ADD COLUMN IF NOT EXISTS preferred BOOLEAN DEFAULT FALSE",
    # PR3 follow-up to D-50 §6 — partial UNIQUE indexes on the provider dedup
    # columns so webhook ingest can use ON CONFLICT instead of the defensive
    # SELECT-then-INSERT-or-UPDATE pattern coros_ingest currently uses. NULL
    # rows excluded so manual cardio_log entries (pre-provider-sync) don't
    # collide with each other.
    "CREATE UNIQUE INDEX IF NOT EXISTS cardio_log_polar_exercise_uidx ON cardio_log (user_id, polar_exercise_id) WHERE polar_exercise_id IS NOT NULL",
    "CREATE UNIQUE INDEX IF NOT EXISTS cardio_log_coros_label_uidx ON cardio_log (user_id, coros_label_id) WHERE coros_label_id IS NOT NULL",
    "CREATE UNIQUE INDEX IF NOT EXISTS cardio_log_wahoo_workout_uidx ON cardio_log (user_id, wahoo_workout_id) WHERE wahoo_workout_id IS NOT NULL",
    # PR6 (D-51) — v5 §A.2 prefill-eligible baselines added to athlete_profile.
    # Self-report at onboarding today; provider extractors (D2a/PR7) will
    # populate via athlete_profile_field_provenance once registry + UI ship.
    "ALTER TABLE athlete_profile ADD COLUMN IF NOT EXISTS body_weight_kg REAL",
    "ALTER TABLE athlete_profile ADD COLUMN IF NOT EXISTS hrmax_bpm INTEGER",
    "ALTER TABLE athlete_profile ADD COLUMN IF NOT EXISTS lactate_threshold_hr_bpm INTEGER",
    "ALTER TABLE athlete_profile ADD COLUMN IF NOT EXISTS vo2max REAL",
    "ALTER TABLE athlete_profile ADD COLUMN IF NOT EXISTS cycling_ftp_w INTEGER",
    # PR12 (D-61) — §G capacity. Per-day windows live in
    # `daily_availability_windows`; `doubles_feasible` ('regularly'/
    # 'occasionally'/'no') gates second-window entry.
    "ALTER TABLE athlete_profile ADD COLUMN IF NOT EXISTS doubles_feasible TEXT",
    # FormRefresh Slice C (2026-05-25) — drop the standalone Long Session
    # (available / days / max_hr) + Preferred Rest Day inputs. The long
    # session is now the longest enabled daily window (window cap raised
    # 360→720 min, below) and rest days are the disabled days — both derived
    # from `daily_availability_windows`, not asked. DROP IF EXISTS is
    # idempotent + no-op on a fresh DB (these are no longer created above);
    # reversible via re-add in git.
    "ALTER TABLE athlete_profile DROP COLUMN IF EXISTS long_session_available",
    "ALTER TABLE athlete_profile DROP COLUMN IF EXISTS long_session_days",
    "ALTER TABLE athlete_profile DROP COLUMN IF EXISTS long_session_max_hr",
    "ALTER TABLE athlete_profile DROP COLUMN IF EXISTS preferred_rest_days",
    # FormRefresh Slice C — raise the daily-window duration ceiling 360→720
    # min (6→12 h) so the longest enabled window can carry an expedition-
    # length long session (the dropped long_session_max_hr enum topped out at
    # "8+"). Fresh DBs get the named 720 bound from the CREATE above; this
    # migrates a deployed table whose inline CHECK still pins 360. The
    # enabled/window-pairing CHECK also references window_duration_min, so the
    # old bound is matched by its "360" literal (which that pairing CHECK does
    # not contain) to avoid dropping it. Idempotent: after the bump no
    # constraint matches "360" and the named 720 bound already exists.
    """DO $$
    DECLARE c text;
    BEGIN
        FOR c IN
            SELECT conname FROM pg_constraint
            WHERE conrelid = 'daily_availability_windows'::regclass
              AND contype = 'c'
              AND pg_get_constraintdef(oid) LIKE '%360%'
        LOOP
            EXECUTE format('ALTER TABLE daily_availability_windows DROP CONSTRAINT %I', c);
        END LOOP;
        IF NOT EXISTS (
            SELECT 1 FROM pg_constraint
            WHERE conrelid = 'daily_availability_windows'::regclass
              AND conname = 'daily_availability_windows_duration_bound'
        ) THEN
            ALTER TABLE daily_availability_windows
                ADD CONSTRAINT daily_availability_windows_duration_bound
                CHECK (window_duration_min IS NULL OR window_duration_min BETWEEN 30 AND 720);
        END IF;
    END $$;""",
    # Layer 4 §7.11 — plan_versions table (lifts D-64 §7.2 stub). Each
    # plan_session carries a plan_version_id FK; the per-day version pointer
    # per D-64 §6.3 picks the most-recent-version row per date when
    # surfacing the plan. superseded_at + superseded_by_version_id are
    # denormalized convenience for revert UX.
    """CREATE TABLE IF NOT EXISTS plan_versions (
        id BIGSERIAL PRIMARY KEY,
        user_id INTEGER NOT NULL REFERENCES users(id),
        created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
        created_via TEXT NOT NULL CHECK (created_via IN ('plan_create', 'plan_refresh_t1', 'plan_refresh_t2', 'plan_refresh_t3', 'single_session_synthesize')),
        scope_start_date DATE NOT NULL,
        scope_end_date DATE NOT NULL,
        pattern CHAR(1) NOT NULL CHECK (pattern IN ('A', 'B')),
        superseded_at TIMESTAMPTZ,
        superseded_by_version_id BIGINT REFERENCES plan_versions(id),
        notes JSONB
    )""",
    "CREATE INDEX IF NOT EXISTS plan_versions_user_created_idx ON plan_versions (user_id, created_at DESC)",
    "CREATE INDEX IF NOT EXISTS plan_versions_user_scope_idx ON plan_versions (user_id, scope_start_date, scope_end_date)",
    # Layer 4 Step 5 cache layer — `layer4_cache` table per `Layer4_Spec.md`
    # §9. Stores per-entry-point cache rows (phase_idx = -1) and per-phase
    # Pattern A rows (phase_idx >= 0). cache_key is a sha256 hex digest from
    # the per-entry formula in §9.1 (or the chained phase-key formula in
    # §9.2). plan_version_id + suggestion_id are NOT stored on the row;
    # they're rebound from the calling orchestrator on hit per §9.4.
    # Composite PK (cache_key, phase_idx) lets a single call cache its
    # top-level entry alongside per-phase entries without collision.
    """CREATE TABLE IF NOT EXISTS layer4_cache (
        cache_key TEXT NOT NULL,
        phase_idx INTEGER NOT NULL DEFAULT -1,
        user_id INTEGER NOT NULL REFERENCES users(id),
        entry_point TEXT NOT NULL CHECK (entry_point IN ('plan_create', 'plan_refresh', 'single_session_synthesize', 'race_week_brief', 'llm_layer3a_athlete_state', 'llm_layer3b_goal_timeline_viability', 'nl_parser_parse_intent')),
        phase_name TEXT,
        payload_json JSONB NOT NULL,
        created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
        last_hit_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
        hit_count INTEGER NOT NULL DEFAULT 0,
        PRIMARY KEY (cache_key, phase_idx),
        CHECK ((phase_idx = -1 AND phase_name IS NULL) OR (phase_idx >= 0 AND phase_name IS NOT NULL))
    )""",
    "CREATE INDEX IF NOT EXISTS layer4_cache_user_entry_idx ON layer4_cache (user_id, entry_point)",
    "CREATE INDEX IF NOT EXISTS layer4_cache_user_created_idx ON layer4_cache (user_id, created_at DESC)",
    "CREATE INDEX IF NOT EXISTS layer4_cache_entry_point_idx ON layer4_cache (entry_point)",
    # D-66 race-event data model (`Race_Events_D66_Design_v1.md` §3 + §10).
    # locale_profiles gains a surrogate `id BIGSERIAL` column so race_events
    # can FK against it (`event_locale_id BIGINT REFERENCES locale_profiles(id)
    # ON DELETE SET NULL`). The composite PK (user_id, locale) stays — D-60's
    # locale_equipment_overrides + locale_toggle_overrides keep using the
    # composite FK pair. Adding the column on an existing table backfills
    # each row with a unique nextval() automatically.
    "ALTER TABLE locale_profiles ADD COLUMN IF NOT EXISTS id BIGSERIAL",
    "CREATE UNIQUE INDEX IF NOT EXISTS locale_profiles_id_uidx ON locale_profiles (id)",
    """CREATE TABLE IF NOT EXISTS race_events (
        id BIGSERIAL PRIMARY KEY,
        user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
        name TEXT NOT NULL,
        event_date DATE NOT NULL,
        race_format TEXT NOT NULL CHECK (race_format IN ('single_day', 'continuous_multi_day', 'stage_race')),
        distance_km NUMERIC NULL,
        total_elevation_gain_m NUMERIC NULL,
        race_rules_summary TEXT NULL,
        mandatory_gear_text TEXT NULL,
        event_locale_id BIGINT NULL REFERENCES locale_profiles(id) ON DELETE SET NULL,
        is_target_event BOOLEAN NOT NULL DEFAULT FALSE,
        notes TEXT NULL,
        etl_version_set JSONB NOT NULL DEFAULT '{}'::jsonb,
        created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
        updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
    )""",
    # Partial UNIQUE index enforces "at most one target race per athlete"
    # per D-66 §3.1 + Decision 5; gaps allowed (no target = no row matches).
    "CREATE UNIQUE INDEX IF NOT EXISTS race_events_user_target_uidx ON race_events (user_id) WHERE is_target_event = TRUE",
    "CREATE INDEX IF NOT EXISTS race_events_user_date_idx ON race_events (user_id, event_date)",
    # Phase 5.1 form-refresh A (2026-05-20) — closes Layer2B_Spec.md §12
    # Open Item 2B-3 for the race-event edit path. race_terrain stores the
    # athlete-entered breakdown as JSONB ([{terrain_id: 'TRN-xxx',
    # pct_of_race: float}, ...]); whole-list read at orchestrator time, no
    # independent queries. Adds idempotently; default empty array preserves
    # the prior row shape for existing data.
    "ALTER TABLE race_events ADD COLUMN IF NOT EXISTS race_terrain JSONB NOT NULL DEFAULT '[]'::jsonb",
    # FormRefresh A2 (2026-05-25) — drop the `aid_stations` count column.
    # Race-day aid logistics are carried structurally by the
    # `race_route_locales` graph (role='aid_station' anchors); the integer
    # count had a single consumer — Layer 2E HITL gate 5 (anaphylaxis ×
    # aid exposure) — which was removed in the same slice (the project
    # never intended to capture/plan for that scenario). DROP IF EXISTS is
    # idempotent + no-op on a fresh DB (the column only ever existed via
    # the prior ALTER add, never in CREATE TABLE).
    "ALTER TABLE race_events DROP COLUMN IF EXISTS aid_stations",
    # D-73 Phase 5.2 walkthrough #1 + #2a (2026-05-21) — Mapbox-anchored race
    # location columns + race_url. The legacy `event_locale_id BIGINT FK to
    # locale_profiles(id)` semantic (athlete's own saved travel locale slot)
    # was wrong for race events — a race finish is at a specific real-world
    # place (city/state/POI), not at one of the athlete's home/hotel/partner
    # locales. The 5 new columns mirror the shape of `locale_profiles`'
    # Mapbox-anchored row (mapbox_id + name + place_name + lat + lng). The
    # legacy column stays nullable for backward-compat; new code uses the
    # Mapbox columns and clears the legacy FK on update. `race_url` carries
    # the race-director site URL — currently athlete-typed; future Trigger #2
    # LLM site-parse slice will pre-fill rules/equipment/terrain from the
    # URL.
    "ALTER TABLE race_events ADD COLUMN IF NOT EXISTS event_locale_name TEXT NULL",
    "ALTER TABLE race_events ADD COLUMN IF NOT EXISTS event_locale_mapbox_id TEXT NULL",
    "ALTER TABLE race_events ADD COLUMN IF NOT EXISTS event_locale_place_name TEXT NULL",
    "ALTER TABLE race_events ADD COLUMN IF NOT EXISTS event_locale_lat NUMERIC(9,6) NULL",
    "ALTER TABLE race_events ADD COLUMN IF NOT EXISTS event_locale_lng NUMERIC(9,6) NULL",
    "ALTER TABLE race_events ADD COLUMN IF NOT EXISTS race_url TEXT NULL",
    # D-73 Phase 5.2 Bucket E.(b) (2026-05-23) — race-level framework_sport
    # override. Layer 2A's discipline classifier keys on framework_sport
    # via `layer0.sport_discipline_bridge`; pre-walkthrough the value was
    # always sourced from `athlete_profile.primary_sport`. New column lets
    # an athlete whose primary sport differs from the target race
    # (e.g. trail runner doing one Adventure Racing race) classify the
    # race correctly without churning their profile. Orchestrator falls
    # back to primary_sport when this is NULL.
    "ALTER TABLE race_events ADD COLUMN IF NOT EXISTS framework_sport TEXT NULL",
    # D-73 Phase 5.2 Bucket E.(b)-B2 + E.(c)-C1 (2026-05-24) — per-race
    # discipline filter override. When set, Layer 2A's classifier post-
    # filters the bridge-derived discipline list to just these IDs
    # (preserves bridge SELECT for inclusion-reason rationale; just narrows
    # the output). NULL = use full bridge defaults (pre-B2 behavior).
    # Auto-cleared on framework_sport change (orphan cleanup) so the
    # selection always reflects the current sport's valid set.
    "ALTER TABLE race_events ADD COLUMN IF NOT EXISTS included_discipline_ids TEXT[] NULL",
    # FormRefresh A1 (2026-05-25) — magnitude axis. `estimated_duration_hr`
    # is the athlete-entered expected finish/cutoff time in hours; the
    # orchestrator prefers it over the coarse `_DURATION_HR_BY_RACE_FORMAT`
    # fallback when building Layer 2E's TargetEvent (which requires
    # estimated_duration_hr > 0). `primary_metric` records whether the
    # athlete defines this race by distance (e.g. 100km ultra) or duration
    # (e.g. 24h rogaine, multi-day expedition) — drives which input the
    # form emphasizes + lets the race-week brief phrase the event
    # correctly. Both nullable so legacy rows survive without backfill;
    # the duration CHECK rejects non-positive values (payload Field(gt=0)
    # is the typed backstop).
    "ALTER TABLE race_events ADD COLUMN IF NOT EXISTS estimated_duration_hr NUMERIC NULL CHECK (estimated_duration_hr IS NULL OR estimated_duration_hr > 0)",
    "ALTER TABLE race_events ADD COLUMN IF NOT EXISTS primary_metric TEXT NULL CHECK (primary_metric IS NULL OR primary_metric IN ('distance', 'duration'))",
    # §H.2 goal-context capture (2026-05-26) — close the Layer 3B deployed-shape
    # gap. 3B's event-mode viability reasoning + HITL triggers
    # (3B.first_time_competitive_goal) read the athlete's goal fields, but the
    # deployed race_events row never stored them — the cached wrapper hardcoded
    # goal_outcome='Finish', so every athlete was treated as a finisher
    # regardless of ambition. These 4 scalar columns let the athlete state
    # their actual goal; the orchestrator threads them into the Layer 3B call.
    # All nullable so legacy rows survive without backfill; the goal_outcome
    # CHECK mirrors layer3b.builder._VALID_GOAL_OUTCOMES, and pack-weight is a
    # numeric kg alongside the free-text mandatory_gear_text.
    "ALTER TABLE race_events ADD COLUMN IF NOT EXISTS goal_outcome TEXT NULL CHECK (goal_outcome IS NULL OR goal_outcome IN ('Finish', 'Compete mid-pack', 'Podium'))",
    "ALTER TABLE race_events ADD COLUMN IF NOT EXISTS first_time_at_distance BOOLEAN NULL",
    "ALTER TABLE race_events ADD COLUMN IF NOT EXISTS time_goal TEXT NULL",
    "ALTER TABLE race_events ADD COLUMN IF NOT EXISTS race_pack_weight_kg NUMERIC NULL CHECK (race_pack_weight_kg IS NULL OR race_pack_weight_kg >= 0)",
    # §H.2 goal-context Slice 2 (2026-05-26) — structured `previous_attempts`,
    # the remaining half of the §H.2 capture. JSONB list of
    # `[{outcome, dnf_cause}, ...]` (shape mirrors `race_terrain`); whole-list
    # read at orchestrator time, no independent queries. Feeds Layer 3B's
    # event-mode goal block + unblocks the `3B.dnf_recurrence_risk` HITL flag
    # (fires when a DNF entry's recovery window — keyed on `dnf_cause` via
    # layer3b.builder._DNF_RECOVERY_WINDOW_WEEKS — exceeds time_to_event_weeks).
    # Idempotent add; default empty array preserves the prior row shape.
    "ALTER TABLE race_events ADD COLUMN IF NOT EXISTS previous_attempts JSONB NOT NULL DEFAULT '[]'::jsonb",
    # FormRefresh A1 (2026-05-25) — race_format taxonomy collapse. The
    # original 4-value enum conflated structure with sport/discipline
    # (`expedition_ar` = AR sport; `multi_day_ultra` = ultrarunning sport).
    # The reconciled axis is purely STRUCTURAL: single_day /
    # continuous_multi_day / stage_race. Sport lives on `framework_sport`,
    # disciplines on Layer 2A, terrain on `race_terrain` — none of which
    # ever sourced from race_format (the orchestrator derives
    # framework_sport from the column or primary_sport, never the format),
    # so the collapse is information-preserving and needs no framework_sport
    # backfill. `expedition_ar` + `multi_day_ultra` both fold into
    # `continuous_multi_day`. Order is load-bearing + idempotent on re-run:
    # (1) DROP the old inline CHECK (auto-named `race_events_race_format_check`
    # on the deployed table) so the remap UPDATE can write the new value;
    # (2) remap rows (no-op after first run — no old values remain);
    # (3) re-ADD the named CHECK with the 3-value set. DROP IF EXISTS each
    # run keeps the ADD collision-free (Postgres has no ADD CONSTRAINT IF
    # NOT EXISTS).
    "ALTER TABLE race_events DROP CONSTRAINT IF EXISTS race_events_race_format_check",
    "UPDATE race_events SET race_format = 'continuous_multi_day' WHERE race_format IN ('expedition_ar', 'multi_day_ultra')",
    "ALTER TABLE race_events ADD CONSTRAINT race_events_race_format_check CHECK (race_format IN ('single_day', 'continuous_multi_day', 'stage_race'))",
    # Phase 5.1 form-refresh C (2026-05-20) — closes Layer2B_Spec.md §12
    # Open Item 2B-2 (§J Locale terrain access controlled vocabulary) +
    # the orchestrator's last `locale_terrain_ids=[]` forward-pointer
    # from the Phase 5.1 vertical slice. TEXT[] of canonical TRN-xxx ids;
    # whole-list read at orchestrator time via the home-locale row, no
    # independent queries. Default `'{}'` preserves the prior row shape
    # for existing data and lets athletes who haven't yet captured
    # terrain still load their locale edit form.
    "ALTER TABLE locale_profiles ADD COLUMN IF NOT EXISTS locale_terrain_ids TEXT[] NOT NULL DEFAULT '{}'",
    """CREATE TABLE IF NOT EXISTS race_route_locales (
        id BIGSERIAL PRIMARY KEY,
        race_event_id BIGINT NOT NULL REFERENCES race_events(id) ON DELETE CASCADE,
        role TEXT NOT NULL CHECK (role IN ('start', 'transition_area', 'aid_station', 'drop_bag_point', 'bivvy', 'finish', 'other')),
        sequence_idx INTEGER NOT NULL,
        name TEXT NOT NULL,
        mile_marker NUMERIC NULL,
        lat NUMERIC NULL,
        lng NUMERIC NULL,
        mapbox_id TEXT NULL,
        notes TEXT NULL,
        created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
        updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
        UNIQUE (race_event_id, sequence_idx)
    )""",
    "CREATE INDEX IF NOT EXISTS race_route_locales_race_seq_idx ON race_route_locales (race_event_id, sequence_idx)",
    """CREATE TABLE IF NOT EXISTS race_route_locale_equipment (
        id BIGSERIAL PRIMARY KEY,
        race_route_locale_id BIGINT NOT NULL REFERENCES race_route_locales(id) ON DELETE CASCADE,
        equipment_name TEXT NOT NULL,
        quantity_text TEXT NULL,
        notes TEXT NULL,
        created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
        updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
    )""",
    "CREATE INDEX IF NOT EXISTS race_route_locale_equipment_locale_idx ON race_route_locale_equipment (race_route_locale_id)",
    # D-66 Layer 3B Scope B — drop the legacy athlete_profile.target_event_*
    # columns. The one-time backfill that lived here previously (INSERT INTO
    # race_events SELECT FROM athlete_profile WHERE target_event_name IS NOT
    # NULL ...) ran on every init since the D-66 DB foundation PR and is now
    # retired: Scope A write-froze the columns from the athlete-facing surface
    # so no row can arrive with a non-migrated value, and `DROP COLUMN IF
    # EXISTS` is idempotent for the columns themselves.
    "ALTER TABLE athlete_profile DROP COLUMN IF EXISTS target_event_name",
    "ALTER TABLE athlete_profile DROP COLUMN IF EXISTS target_event_date",
    # D-73 Phase 1.2A (D-51 §3.3) — §C training history scalars on athlete_profile.
    # All nullable; existing rows survive without backfill. PROFILE_FIELDS in
    # athlete.py gains matching entries so the upsert helper can write them.
    "ALTER TABLE athlete_profile ADD COLUMN IF NOT EXISTS years_structured_training INTEGER",
    "ALTER TABLE athlete_profile ADD COLUMN IF NOT EXISTS peak_weekly_volume_hrs REAL",
    "ALTER TABLE athlete_profile ADD COLUMN IF NOT EXISTS peak_weekly_volume_year INTEGER",
    "ALTER TABLE athlete_profile ADD COLUMN IF NOT EXISTS longest_event_completed TEXT",
    "ALTER TABLE athlete_profile ADD COLUMN IF NOT EXISTS training_consistency_disrupted_weeks SMALLINT",
    "ALTER TABLE athlete_profile ADD COLUMN IF NOT EXISTS training_consistency_cause TEXT",
    "ALTER TABLE athlete_profile ADD COLUMN IF NOT EXISTS previous_coaching TEXT",
    # D-73 Phase 1.2A (D-51 §3.6) — §F testing-baseline gap fields + source
    # companions for the five existing prefill-eligible baselines.
    "ALTER TABLE athlete_profile ADD COLUMN IF NOT EXISTS running_threshold_pace_sec_per_km INTEGER",
    "ALTER TABLE athlete_profile ADD COLUMN IF NOT EXISTS running_threshold_test_date DATE",
    "ALTER TABLE athlete_profile ADD COLUMN IF NOT EXISTS css_swim_sec_per_100m INTEGER",
    "ALTER TABLE athlete_profile ADD COLUMN IF NOT EXISTS css_test_date DATE",
    "ALTER TABLE athlete_profile ADD COLUMN IF NOT EXISTS cycling_ftp_test_date DATE",
    "ALTER TABLE athlete_profile ADD COLUMN IF NOT EXISTS hrmax_source TEXT",
    "ALTER TABLE athlete_profile ADD COLUMN IF NOT EXISTS lt_method TEXT",
    "ALTER TABLE athlete_profile ADD COLUMN IF NOT EXISTS vo2max_source TEXT",
    # D-73 Phase 1.2A (D-51 §3.8) — §H no-event-mode plan parameters. NULL
    # when athlete is in event mode (race_events.is_target_event=TRUE exists).
    "ALTER TABLE athlete_profile ADD COLUMN IF NOT EXISTS plan_duration_weeks_no_event SMALLINT",
    "ALTER TABLE athlete_profile ADD COLUMN IF NOT EXISTS non_event_goal_type TEXT",
    # D-73 Phase 1.2A (D-51 §3.9) — §I lifestyle & recovery. Andy 2026-05-19:
    # sleep-deprivation fields store regardless of §H race duration (no
    # write-path conditional gate; athlete edits any time).
    "ALTER TABLE athlete_profile ADD COLUMN IF NOT EXISTS work_stress_level TEXT",
    "ALTER TABLE athlete_profile ADD COLUMN IF NOT EXISTS dietary_pattern TEXT",
    "ALTER TABLE athlete_profile ADD COLUMN IF NOT EXISTS supplement_protocol_notes TEXT",
    "ALTER TABLE athlete_profile ADD COLUMN IF NOT EXISTS caffeine_tolerance TEXT",
    "ALTER TABLE athlete_profile ADD COLUMN IF NOT EXISTS caffeine_daily_mg_estimate SMALLINT",
    "ALTER TABLE athlete_profile ADD COLUMN IF NOT EXISTS caffeine_race_day_strategy TEXT",
    "ALTER TABLE athlete_profile ADD COLUMN IF NOT EXISTS altitude_acclimatization_history BOOLEAN",
    "ALTER TABLE athlete_profile ADD COLUMN IF NOT EXISTS altitude_max_exposure_m INTEGER",
    "ALTER TABLE athlete_profile ADD COLUMN IF NOT EXISTS altitude_exposure_count SMALLINT",
    "ALTER TABLE athlete_profile ADD COLUMN IF NOT EXISTS fueling_format_preference TEXT",
    "ALTER TABLE athlete_profile ADD COLUMN IF NOT EXISTS gi_triggers_known TEXT",
    "ALTER TABLE athlete_profile ADD COLUMN IF NOT EXISTS salt_electrolyte_tolerance TEXT",
    "ALTER TABLE athlete_profile ADD COLUMN IF NOT EXISTS sleep_deprivation_max_hrs_continuous_awake SMALLINT",
    "ALTER TABLE athlete_profile ADD COLUMN IF NOT EXISTS sleep_deprivation_strategy_notes TEXT",
    # D-73 Phase 1.2A (D-51 §3.5) — strength_benchmarks 1:1 sub-table.
    # PK = user_id so each athlete has at most one row; populated lazily when
    # the athlete enters benchmarks. Right/left split on side-plank, single-leg
    # squat, and grip strength per v5 §E asymmetry signal.
    """CREATE TABLE IF NOT EXISTS strength_benchmarks (
        user_id INTEGER PRIMARY KEY REFERENCES users(id),
        front_plank_sec INTEGER,
        dead_bug_max_reps INTEGER,
        side_plank_left_sec INTEGER,
        side_plank_right_sec INTEGER,
        pushup_max_reps INTEGER,
        bodyweight_squat_max_reps INTEGER,
        single_leg_squat_left_max_reps INTEGER,
        single_leg_squat_right_max_reps INTEGER,
        pullup_max_reps INTEGER,
        dead_hang_sec INTEGER,
        grip_strength_left_kg REAL,
        grip_strength_right_kg REAL,
        last_tested_at DATE,
        updated_at TIMESTAMP DEFAULT NOW()
    )""",
    # D-56 — cardio_log race + time-of-day fields. Folded into D-73 Phase 1.2A
    # per Andy 2026-05-19; hard-blocker for Phase 3 Layer 3A (race-result filter
    # per v5 §C row 7 + Night Running detection per §D.1). DEFAULT FALSE on
    # is_race so existing rows are non-race by default; start_time is TEXT
    # (HH:MM:SS) since cardio_log.date is TEXT and the pair is read together.
    "ALTER TABLE cardio_log ADD COLUMN IF NOT EXISTS is_race BOOLEAN DEFAULT FALSE",
    "ALTER TABLE cardio_log ADD COLUMN IF NOT EXISTS start_time TEXT",
    # D-73 Phase 1.2A — drop legacy athlete_profile.training_window. Superseded
    # by daily_availability_windows (D-61 / PR12). UI surface retired in the
    # same session: routes/profile.py form handler + templates/profile/edit.html
    # select field removed. D-66 Scope B DROP COLUMN IF EXISTS precedent.
    "ALTER TABLE athlete_profile DROP COLUMN IF EXISTS training_window",
    # D-73 Phase 1.2B (D-51 §3.2a) — health_conditions_log multi-row table
    # parallel to injury_log. system_category closed enum lives in
    # athlete.KNOWN_SYSTEM_CATEGORIES; status enum (Active/Resolved/Inactive)
    # mirrors injury_log precedent. severity 1-5 per v5 §B.4 substructure.
    # §3.1 (disclosure_acknowledgments) intentionally NOT touched this
    # session — D-58/PR1 already shipped the table with disclosure_id /
    # version_id / scopes_granted columns (live readers per PR1 + PR10);
    # design wave §3.1 was written ahead of state verification (same
    # pattern as the §3.7 daily_availability_windows drift caught in 1.2A).
    """CREATE TABLE IF NOT EXISTS health_conditions_log (
        id SERIAL PRIMARY KEY,
        user_id INTEGER NOT NULL REFERENCES users(id),
        system_category TEXT NOT NULL,
        condition_name TEXT NOT NULL,
        severity INTEGER,
        notes TEXT,
        status TEXT NOT NULL DEFAULT 'Active',
        start_date DATE,
        resolved_date DATE,
        created_at TIMESTAMP DEFAULT NOW(),
        updated_at TIMESTAMP DEFAULT NOW()
    )""",
    "CREATE INDEX IF NOT EXISTS health_conditions_log_user_status_idx ON health_conditions_log (user_id, status)",
    "CREATE INDEX IF NOT EXISTS health_conditions_log_user_created_idx ON health_conditions_log (user_id, created_at DESC)",
    # D-73 Phase 1.2B (D-51 §3.2b) — medications_log. medication_class closed
    # enum lives in athlete.KNOWN_MEDICATION_CLASSES (training-relevant only
    # per v5 §B; not a general pharmacy code). stopped_at IS NULL = currently
    # taking; the partial index serves the active-medications Layer 3A query.
    """CREATE TABLE IF NOT EXISTS medications_log (
        id SERIAL PRIMARY KEY,
        user_id INTEGER NOT NULL REFERENCES users(id),
        medication_class TEXT NOT NULL,
        medication_name TEXT,
        started_at DATE,
        stopped_at DATE,
        notes TEXT,
        created_at TIMESTAMP DEFAULT NOW()
    )""",
    "CREATE INDEX IF NOT EXISTS medications_log_user_class_active_idx ON medications_log (user_id, medication_class) WHERE stopped_at IS NULL",
    # food_allergies (D-73 Phase 1.2B) was dropped as dead code: the table
    # had no write path (never populated), the Layer 1 → 2E plumbing that
    # loaded it was never consumed downstream, and the §B.4.2 'gi_immune'
    # auto-populate rule it was meant to trigger was never implemented.
    # DROP IF EXISTS is idempotent + no-op on a fresh DB.
    "DROP TABLE IF EXISTS food_allergies",
    # D-73 Phase 1.2B (D-51 §3.3) — §C multi-row companions. athlete_secondary
    # _sports.sport_slug FK-validated in application code against the 18-sport
    # Sports_Framework_v10.xlsx (no closed-enum DB constraint; the framework
    # ships via Layer 0 catalog). athlete_discipline_weighting.weight_pct
    # invariant (per-user sum across rows = 100) is application-enforced —
    # intermediate states during multi-row edits are valid so no CHECK.
    """CREATE TABLE IF NOT EXISTS athlete_secondary_sports (
        id SERIAL PRIMARY KEY,
        user_id INTEGER NOT NULL REFERENCES users(id),
        sport_slug TEXT NOT NULL,
        experience_tier TEXT NOT NULL,
        created_at TIMESTAMP DEFAULT NOW(),
        UNIQUE (user_id, sport_slug)
    )""",
    """CREATE TABLE IF NOT EXISTS athlete_discipline_weighting (
        id SERIAL PRIMARY KEY,
        user_id INTEGER NOT NULL REFERENCES users(id),
        discipline_slug TEXT NOT NULL,
        weight_pct SMALLINT NOT NULL,
        updated_at TIMESTAMP DEFAULT NOW(),
        UNIQUE (user_id, discipline_slug)
    )""",
    # D-73 Phase 1.2B (D-51 §3.3) — recent_race_results. source mirrors
    # athlete_profile_field_provenance.source shape per-row (record-shaped
    # data; not per-field). D-56 cardio_log.is_race=TRUE is the long-term
    # source — Layer 1 builder cross-references both for §C row 7 reads.
    """CREATE TABLE IF NOT EXISTS recent_race_results (
        id SERIAL PRIMARY KEY,
        user_id INTEGER NOT NULL REFERENCES users(id),
        event_name TEXT NOT NULL,
        event_date DATE NOT NULL,
        distance_km REAL,
        finish_time_seconds INTEGER,
        result_notes TEXT,
        source TEXT NOT NULL DEFAULT 'self_report',
        created_at TIMESTAMP DEFAULT NOW()
    )""",
    "CREATE INDEX IF NOT EXISTS recent_race_results_user_date_idx ON recent_race_results (user_id, event_date DESC)",
    # D-73 Phase 1.2B (D-51 §3.3) — pack_load_history. One row per pack-weight
    # tier the athlete currently trains at; session_count_4wk + longest_session
    # _hrs are trailing-window summaries the athlete updates as training
    # progresses. terrain_type is free-text (no closed enum; v5 §C.1 leaves
    # this open-ended). Layer 3B Scope C consumer per the expedition-AR
    # context-bundle precedent.
    """CREATE TABLE IF NOT EXISTS pack_load_history (
        id SERIAL PRIMARY KEY,
        user_id INTEGER NOT NULL REFERENCES users(id),
        pack_weight_kg REAL NOT NULL,
        session_count_4wk INTEGER,
        longest_session_hrs REAL,
        terrain_type TEXT,
        notes TEXT,
        created_at TIMESTAMP DEFAULT NOW()
    )""",
    # D-73 Phase 1.2B (D-51 §3.12) — athlete_network_links. linked_account
    # _user_id NULL means external partner (not an AIDSTATION user); non-NULL
    # triggers the §A.1 linked-partner-data-sharing disclosure (paired with
    # the linked_partner_consents row below). relationship_types is a comma-
    # separated subset of KNOWN_RELATIONSHIP_TYPES. race_event_id ON DELETE
    # SET NULL preserves the link when the linked race is removed (per v5
    # §L: Race Teammate conditional). race_events.id is BIGSERIAL so the FK
    # column is BIGINT to match.
    """CREATE TABLE IF NOT EXISTS athlete_network_links (
        id SERIAL PRIMARY KEY,
        user_id INTEGER NOT NULL REFERENCES users(id),
        partner_name TEXT NOT NULL,
        linked_account_user_id INTEGER REFERENCES users(id),
        relationship_types TEXT NOT NULL,
        partner_specific_rules TEXT,
        race_event_id BIGINT REFERENCES race_events(id) ON DELETE SET NULL,
        discipline_focus_on_team TEXT,
        created_at TIMESTAMP DEFAULT NOW(),
        updated_at TIMESTAMP DEFAULT NOW()
    )""",
    "CREATE INDEX IF NOT EXISTS athlete_network_links_user_idx ON athlete_network_links (user_id)",
    "CREATE INDEX IF NOT EXISTS athlete_network_links_linked_idx ON athlete_network_links (linked_account_user_id) WHERE linked_account_user_id IS NOT NULL",
    # D-73 Phase 1.2B (D-51 §3.12) — linked_partner_consents (folded in per
    # Andy 2026-05-19; design wave §6 Q5 default was defer). Athlete-owned
    # consent grant tied to a specific athlete_network_links row; revoked_at
    # IS NULL = currently granted. Per v5 §L Account Config 4 the scope is
    # athlete-controlled (none / activity_summaries / full_plan_access);
    # closed enum in athlete.LINKED_PARTNER_CONSENT_SCOPES. ON DELETE
    # CASCADE on the link FK is intentional — removing the network link
    # invalidates any consent granted against it.
    """CREATE TABLE IF NOT EXISTS linked_partner_consents (
        id SERIAL PRIMARY KEY,
        user_id INTEGER NOT NULL REFERENCES users(id),
        link_id INTEGER NOT NULL REFERENCES athlete_network_links(id) ON DELETE CASCADE,
        consent_scope TEXT NOT NULL,
        granted_at TIMESTAMP NOT NULL DEFAULT NOW(),
        revoked_at TIMESTAMP
    )""",
    "CREATE INDEX IF NOT EXISTS linked_partner_consents_active_idx ON linked_partner_consents (user_id, link_id) WHERE revoked_at IS NULL",
    # D-73 Phase 1.2C (D-51 §3.4) — per-discipline §D 1:1 baseline sub-tables.
    # PK = user_id so each athlete has at most one row per discipline; rows
    # exist for the disciplines the athlete trains and nullable columns for
    # the fields not yet entered (per v5 §D "every field is nullable; null
    # means 'not asked.'"). updated_at follows the 1.2A strength_benchmarks
    # precedent for the 1:1 sub-table audit shape. Closed-enum write-path
    # validation lives in athlete.py (TRAIL_EXPERIENCE_TERRAINS,
    # MTB_SKILL_LEVELS, OW_EXPERIENCE_LEVELS, PADDLE_CRAFT_TYPES,
    # SKI_DISCIPLINES, NAVIGATION_EXPERIENCE_LEVELS); rock_climbing_*_grade
    # is free-text (multi-system: Yosemite Decimal / French Sport / UIAA per
    # Layer 4 Step 4a precedent). bike_types_available is comma-separated
    # against EQUIPMENT_CATEGORIES['Cycling Equipment'] slugs (no separate
    # constant; design wave §3.4 left the closed-enum subset unspecified).
    """CREATE TABLE IF NOT EXISTS discipline_baseline_running (
        user_id INTEGER PRIMARY KEY REFERENCES users(id),
        easy_run_pace_sec_per_km INTEGER,
        vertical_gain_weekly_m REAL,
        vertical_gain_peak_session_m REAL,
        trail_experience_terrain TEXT,
        downhill_adaptation BOOLEAN,
        downhill_sessions_3mo INTEGER,
        night_running BOOLEAN,
        gut_training_g_per_hr_cho SMALLINT,
        gut_training_issues TEXT,
        updated_at TIMESTAMP DEFAULT NOW()
    )""",
    """CREATE TABLE IF NOT EXISTS discipline_baseline_cycling (
        user_id INTEGER PRIMARY KEY REFERENCES users(id),
        bike_types_available TEXT,
        mtb_skill TEXT,
        longest_ride_distance_km REAL,
        longest_ride_hrs REAL,
        saddle_endurance_hrs REAL,
        aero_endurance_min INTEGER,
        updated_at TIMESTAMP DEFAULT NOW()
    )""",
    """CREATE TABLE IF NOT EXISTS discipline_baseline_swimming (
        user_id INTEGER PRIMARY KEY REFERENCES users(id),
        pool_100m_pace_sec INTEGER,
        ow_experience TEXT,
        wetsuit_experience BOOLEAN,
        cold_water_experience BOOLEAN,
        ow_feeding_experience BOOLEAN,
        weekly_swim_volume_km REAL,
        updated_at TIMESTAMP DEFAULT NOW()
    )""",
    """CREATE TABLE IF NOT EXISTS discipline_baseline_paddling (
        user_id INTEGER PRIMARY KEY REFERENCES users(id),
        longest_paddle_km REAL,
        longest_paddle_hrs REAL,
        paddle_craft_types TEXT,
        updated_at TIMESTAMP DEFAULT NOW()
    )""",
    """CREATE TABLE IF NOT EXISTS discipline_baseline_skiing (
        user_id INTEGER PRIMARY KEY REFERENCES users(id),
        ski_disciplines TEXT,
        weekly_ski_volume_hrs REAL,
        updated_at TIMESTAMP DEFAULT NOW()
    )""",
    """CREATE TABLE IF NOT EXISTS discipline_baseline_navigation (
        user_id INTEGER PRIMARY KEY REFERENCES users(id),
        experience_level TEXT,
        night_nav_experience BOOLEAN,
        updated_at TIMESTAMP DEFAULT NOW()
    )""",
    """CREATE TABLE IF NOT EXISTS discipline_baseline_technical (
        user_id INTEGER PRIMARY KEY REFERENCES users(id),
        rock_climbing_outdoor_grade TEXT,
        rock_climbing_indoor_grade TEXT,
        abseiling_experience BOOLEAN,
        updated_at TIMESTAMP DEFAULT NOW()
    )""",
    # D-73 Phase 2.2 (Layer2D_Spec.md §3 / Athlete_Onboarding_Data_Spec_v5.md
    # §B.1) — injury_log gains the §B.1.1 / §B.3 structured fields Layer 2D
    # dispatches on. severity flips INTEGER (1-5) → TEXT (6-enum); injury_type,
    # side, movement_constraints added. Existing rows are test data per
    # Andy 2026-05-19 ("test only, can be lost") — wiped before the type
    # change so the INTEGER→TEXT swap doesn't need a cast. Closed-enum
    # constants in athlete.py (KNOWN_INJURY_TYPES, KNOWN_INJURY_SEVERITIES,
    # KNOWN_MOVEMENT_CONSTRAINTS, KNOWN_INJURY_SIDES); pydantic mirrors in
    # layer4/context.py InjuryRecord. Idempotent: the DELETE runs once
    # (subsequent runs are no-op against the new TEXT column shape since
    # only the new write path inserts rows after migration; the type-check
    # guard prevents the DELETE+DROP+ADD cycle from re-firing).
    lambda cur: (
        cur.execute(
            "SELECT data_type FROM information_schema.columns "
            "WHERE table_name='injury_log' AND column_name='severity'"
        ),
        (lambda dt: (
            cur.execute("DELETE FROM injury_log"),
            cur.execute("ALTER TABLE injury_log DROP COLUMN severity"),
            cur.execute("ALTER TABLE injury_log ADD COLUMN severity TEXT"),
        ) if dt and dt[0] == 'integer' else None)(cur.fetchone()),
    ),
    "ALTER TABLE injury_log ADD COLUMN IF NOT EXISTS injury_type TEXT",
    "ALTER TABLE injury_log ADD COLUMN IF NOT EXISTS side TEXT NOT NULL DEFAULT 'N/A'",
    "ALTER TABLE injury_log ADD COLUMN IF NOT EXISTS movement_constraints JSONB",
    # D-73 Phase 2.3 (Layer2B_Spec.md §7) — reclassify deployed
    # `layer0.terrain_gap_rules.gap_severity='partial'` rows to the
    # spec-canonical 4-band enum {critical, high, medium, low} keyed on
    # `proxy_fidelity` (>= 0.70 low; 0.50-0.69 medium; 0.40-0.49 high;
    # < 0.40 critical). 11 deployed rows reclassified; the 1 unbridgeable
    # row (TRN-013 → NULL) is left untouched. Idempotent: WHERE filter
    # on `gap_severity = 'partial'` no-ops after first run. DO block
    # guards on table existence so a fresh DB without the populate script
    # (etl/sources/populate_terrain_gap_rules.sql) doesn't error here.
    "DO $$ "
    "BEGIN "
    "  IF EXISTS ("
    "    SELECT 1 FROM information_schema.tables "
    "    WHERE table_schema='layer0' AND table_name='terrain_gap_rules'"
    "  ) THEN "
    "    UPDATE layer0.terrain_gap_rules "
    "    SET gap_severity = CASE "
    "      WHEN proxy_fidelity >= 0.70 THEN 'low' "
    "      WHEN proxy_fidelity >= 0.50 THEN 'medium' "
    "      WHEN proxy_fidelity >= 0.40 THEN 'high' "
    "      ELSE 'critical' "
    "    END "
    "    WHERE gap_severity = 'partial' AND superseded_at IS NULL; "
    "  END IF; "
    "END $$;",
    # Phase 5.2 caller-side substrate (2026-05-20) — `plan_sessions` table
    # per Layer 4 §7.11 natural-key reference + §7.12 schema-level rules.
    # Each row stores one `PlanSession` from a `Layer4Payload.sessions` list
    # as JSONB; the natural key `(plan_version_id, date, session_index_in_day)`
    # is UNIQUE-constrained (no two sessions on the same slot under the same
    # plan version). user_id is denormalized for fast (user_id, date) lookups
    # bypassing the plan_versions join. Per-day version pointer per D-64 §6.3
    # is implemented by DISTINCT ON (date, session_index_in_day) ORDER BY
    # plan_version_id DESC at read time. payload_json carries the full
    # PlanSession.model_dump(mode='json'); v1 stores the whole structure
    # rather than denormalizing 17+ columns (denormalize when plan-view
    # queries become load-bearing).
    """CREATE TABLE IF NOT EXISTS plan_sessions (
        id BIGSERIAL PRIMARY KEY,
        plan_version_id BIGINT NOT NULL REFERENCES plan_versions(id) ON DELETE CASCADE,
        user_id INTEGER NOT NULL REFERENCES users(id),
        session_id TEXT NOT NULL,
        date DATE NOT NULL,
        session_index_in_day SMALLINT NOT NULL CHECK (session_index_in_day IN (0, 1)),
        payload_json JSONB NOT NULL,
        created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
        UNIQUE (plan_version_id, date, session_index_in_day)
    )""",
    "CREATE INDEX IF NOT EXISTS plan_sessions_user_date_idx ON plan_sessions (user_id, date)",
    "CREATE INDEX IF NOT EXISTS plan_sessions_user_version_idx ON plan_sessions (user_id, plan_version_id)",
    # #321 plan-gen observability — durable per-block progress snapshot. Layer 4
    # synthesizes plans block-by-block across multiple resumable passes; accepted
    # blocks live in `layer4_cache` (TTL-managed), but nothing is queryable as
    # first-class plan data until the whole plan flips `ready` (all-at-once
    # `plan_sessions` write). This table is snapshotted from the cache once per
    # pass (`plan_sessions_repo.snapshot_progress_blocks`, called from
    # `_advance_plan_generation`) so an in-flight/failed plan's partial progress
    # is durable + inspectable (admin view). Keyed by (plan_version_id, phase_idx)
    # — phase_idx is the global week-block index. WRITE-ONLY side effect: this
    # table is NEVER an input to any Layer 4 cache key (the #199/#202/#294
    # determinism rule). sessions_json / synthesis_metadata_json are copied
    # verbatim from the cached block payload.
    """CREATE TABLE IF NOT EXISTS plan_progress_blocks (
        id BIGSERIAL PRIMARY KEY,
        plan_version_id BIGINT NOT NULL REFERENCES plan_versions(id) ON DELETE CASCADE,
        user_id INTEGER NOT NULL REFERENCES users(id),
        phase_idx INTEGER NOT NULL,
        phase_name TEXT NOT NULL,
        sessions_json JSONB NOT NULL,
        synthesis_metadata_json JSONB,
        snapshot_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
        UNIQUE (plan_version_id, phase_idx)
    )""",
    "CREATE INDEX IF NOT EXISTS plan_progress_blocks_user_version_idx ON plan_progress_blocks (user_id, plan_version_id)",
    # D-63 §5.3 — ad_hoc_workout_suggestions. Holds generated-but-not-yet-
    # logged single-session synthesizer outputs. request_payload carries the
    # SingleSessionRequest; generated_session carries the single PlanSession
    # from Layer4Payload.sessions[0]. status lifecycle: suggested → logged /
    # discarded / regenerated (§5.5). regenerated_into_id chains successive
    # regenerations; the original row stays for telemetry per D-63 §5.5.
    # Logged-into-* columns + cardio_log/training_log is_ad_hoc extensions
    # land with the log-this slice (paired with D-64 caller-side T1 hook).
    """CREATE TABLE IF NOT EXISTS ad_hoc_workout_suggestions (
        id BIGSERIAL PRIMARY KEY,
        user_id INTEGER NOT NULL REFERENCES users(id),
        requested_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
        request_payload JSONB NOT NULL,
        generated_session JSONB,
        status TEXT NOT NULL DEFAULT 'suggested'
            CHECK (status IN ('suggested', 'logged', 'discarded', 'regenerated')),
        logged_into_table TEXT,
        logged_into_id BIGINT,
        discarded_at TIMESTAMPTZ,
        regenerated_into_id BIGINT REFERENCES ad_hoc_workout_suggestions(id),
        token_cost_estimate INTEGER,
        created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
    )""",
    "CREATE INDEX IF NOT EXISTS ad_hoc_workout_suggestions_user_status_idx ON ad_hoc_workout_suggestions (user_id, status, requested_at DESC)",
    # D-64 §7.1 — plan_refresh_log. One row per refresh attempt (success or
    # failure). Written inside the same transaction as the orchestrator +
    # persist_layer4_sessions per D-64 §6.2 atomic-write semantics; on
    # parser/orchestrator failure the row still lands with success=FALSE +
    # failure_reason populated. parsed_intent carries the full ParsedIntent
    # JSONB (or the degraded `_default_parsed_intent()` payload when the
    # parser errored). layers_run is a TEXT[] of layer labels actually
    # executed downstream (orchestrator-side telemetry; v1 routes record
    # the static tier default since the orchestrator does not currently
    # expose per-cascade layer telemetry). Frequency-cap fields per D-64
    # §8 deferred — caps are a follow-on per the runtime session scope.
    """CREATE TABLE IF NOT EXISTS plan_refresh_log (
        id BIGSERIAL PRIMARY KEY,
        user_id INTEGER NOT NULL REFERENCES users(id),
        triggered_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
        tier TEXT NOT NULL CHECK (tier IN ('T1', 'T2', 'T3')),
        nl_text TEXT,
        parsed_intent JSONB,
        layers_run TEXT[] NOT NULL DEFAULT '{}',
        scope_start_date DATE NOT NULL,
        scope_end_date DATE NOT NULL,
        plan_version_id_before BIGINT REFERENCES plan_versions(id),
        plan_version_id_after BIGINT REFERENCES plan_versions(id),
        duration_ms INTEGER,
        sessions_changed INTEGER,
        success BOOLEAN NOT NULL,
        failure_reason TEXT,
        created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
    )""",
    "CREATE INDEX IF NOT EXISTS plan_refresh_log_user_triggered_idx ON plan_refresh_log (user_id, triggered_at DESC)",
    # D-63 §5.1 — cardio_log ad-hoc workout extensions. Lets the [Log this
    # workout] button on the on-demand workout result view persist the
    # generated cardio session as a real log row tied back to the source
    # ad_hoc_workout_suggestions row. Partial index on (user_id, is_ad_hoc)
    # keeps the ad-hoc subset cheap to query while keeping the index small.
    "ALTER TABLE cardio_log ADD COLUMN IF NOT EXISTS is_ad_hoc BOOLEAN NOT NULL DEFAULT FALSE",
    "ALTER TABLE cardio_log ADD COLUMN IF NOT EXISTS ad_hoc_request_payload JSONB",
    "ALTER TABLE cardio_log ADD COLUMN IF NOT EXISTS ad_hoc_suggestion_id BIGINT REFERENCES ad_hoc_workout_suggestions(id)",
    "CREATE INDEX IF NOT EXISTS cardio_log_ad_hoc_idx ON cardio_log (user_id, is_ad_hoc) WHERE is_ad_hoc = TRUE",
    # D-63 §5.2 — training_log ad-hoc workout extensions (mirror of §5.1).
    "ALTER TABLE training_log ADD COLUMN IF NOT EXISTS is_ad_hoc BOOLEAN NOT NULL DEFAULT FALSE",
    "ALTER TABLE training_log ADD COLUMN IF NOT EXISTS ad_hoc_request_payload JSONB",
    "ALTER TABLE training_log ADD COLUMN IF NOT EXISTS ad_hoc_suggestion_id BIGINT REFERENCES ad_hoc_workout_suggestions(id)",
    "CREATE INDEX IF NOT EXISTS training_log_ad_hoc_idx ON training_log (user_id, is_ad_hoc) WHERE is_ad_hoc = TRUE",
    # D-63 §5.4 — plan_refresh_log linkage to the originating ad-hoc workout
    # suggestion when a T1 refresh is triggered by the post-log T1 hook.
    # Backfills as NULL for refreshes that did not flow through the
    # log-this slice (existing rows + manual /plans/v2/refresh visits).
    "ALTER TABLE plan_refresh_log ADD COLUMN IF NOT EXISTS triggered_by_ad_hoc_id BIGINT REFERENCES ad_hoc_workout_suggestions(id)",
    # D-63 §3.5 — t1_hook_telemetry. One row per [No, thanks] dismissal of
    # the post-log T1 plan-check hook. Decoupled from ad_hoc_workout_
    # suggestions so we can extend with additional hook event types (e.g.,
    # partial-dismiss, deferred-refresh) without schema churn on the
    # suggestions table.
    """CREATE TABLE IF NOT EXISTS t1_hook_telemetry (
        id BIGSERIAL PRIMARY KEY,
        user_id INTEGER NOT NULL REFERENCES users(id),
        suggestion_id BIGINT NOT NULL REFERENCES ad_hoc_workout_suggestions(id),
        dismissed_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
        created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
    )""",
    "CREATE INDEX IF NOT EXISTS t1_hook_telemetry_user_dismissed_idx ON t1_hook_telemetry (user_id, dismissed_at DESC)",
    # D-64 §8 — frequency-cap override telemetry on plan_refresh_log. Set
    # TRUE on the row when the route's own cap-check returned exceeded AND
    # the form arrived with cap_override=1 (athlete clicked [Refresh
    # anyway] in the modal-confirm). Stale forms / direct-curls with
    # cap_override=1 against an under-cap window still land FALSE — the
    # column reflects "athlete confirmed the cost gate," not "request
    # contained an override field."
    "ALTER TABLE plan_refresh_log ADD COLUMN IF NOT EXISTS cap_overridden BOOLEAN NOT NULL DEFAULT FALSE",
    # D-73 Phase 5.2 Bucket C sub-item (g) — retire the 9 display-only
    # "Outdoor & Terrain" equipment tags in favour of the canonical
    # locale_terrain_ids grid as the single "what's accessible from this
    # location" surface. Callable defined above; performs translation +
    # delete in 5 SQL steps. Fully idempotent across re-runs and clean
    # deploys.
    _retire_outdoor_terrain_equipment_tags,
    # D-73 Phase 5.2 Bucket C sub-item (l) — athlete-side skill-capability
    # toggle states. Mirror of locale_toggle_overrides shape minus the
    # locale axis (skills are athlete-grain not athlete-locale-grain).
    # Default state of every toggle is OFF; an athlete row is inserted
    # only when they explicitly enable a skill (athlete-side capture
    # surface deferred to a follow-on slice — mirrors the gear-toggle
    # status quo where the orchestrator passes cluster_gear_toggle_states={}).
    """CREATE TABLE IF NOT EXISTS athlete_skill_toggles (
        id SERIAL PRIMARY KEY,
        user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
        toggle_name TEXT NOT NULL,
        enabled BOOLEAN NOT NULL DEFAULT FALSE,
        created_at TIMESTAMP DEFAULT NOW(),
        updated_at TIMESTAMP DEFAULT NOW(),
        UNIQUE (user_id, toggle_name)
    )""",
    "CREATE INDEX IF NOT EXISTS ast_user_idx ON athlete_skill_toggles (user_id)",
    # Un-ship the race-craft-aware scoring slice — drop the column so
    # deployed DBs shed it cleanly. Approved destructive drop (no users;
    # backward-compat not needed).
    "ALTER TABLE race_events DROP COLUMN IF EXISTS race_modality_hints",
    # Async plan-create (2026-05-26) — plan generation runs step-by-step,
    # resuming from the layer4_cache, so a generating row needs a lifecycle
    # flag the progress screen polls. Existing rows default to 'ready' (their
    # sessions already landed); only plan_create's async path sets
    # 'generating'. generation_error carries the user-facing failure copy.
    "ALTER TABLE plan_versions ADD COLUMN IF NOT EXISTS generation_status TEXT NOT NULL DEFAULT 'ready'",
    "ALTER TABLE plan_versions ADD COLUMN IF NOT EXISTS generation_error TEXT",
    """DO $$
    BEGIN
        IF NOT EXISTS (
            SELECT 1 FROM pg_constraint
            WHERE conrelid = 'plan_versions'::regclass
              AND conname = 'plan_versions_generation_status_chk'
        ) THEN
            ALTER TABLE plan_versions
                ADD CONSTRAINT plan_versions_generation_status_chk
                CHECK (generation_status IN ('generating', 'ready', 'failed'));
        END IF;
    END $$;""",
    # D-77 progress-based backstop (2026-05-27) — the per-week-block decomposition
    # (Layer4_Spec §5.2/§9.2) makes each unit fit the 300s ceiling; a generation
    # that caches ZERO new blocks for too long has a unit that genuinely can't
    # fit. `generation_units_cached` records the latest observed block count
    # (telemetry: how far generation has gotten). The stall TRIP is wall-clock
    # (`_generation_stalled` in routes/plan_create.py: no block cached within
    # `_STALL_WALLCLOCK_S`, on the DB clock) rather than a per-call counter — the
    # cron + poller both advance the row and a call-count trip false-killed plans
    # before the first block could cache. `generation_stall_passes` is retained
    # (now unused) to avoid a drop migration. Both default 0 (correct for
    # in-flight + legacy rows).
    "ALTER TABLE plan_versions ADD COLUMN IF NOT EXISTS generation_units_cached INTEGER NOT NULL DEFAULT 0",
    "ALTER TABLE plan_versions ADD COLUMN IF NOT EXISTS generation_stall_passes INTEGER NOT NULL DEFAULT 0",
    # Log-visibility (#47 follow-up, 2026-05-31): the full Python traceback on a
    # terminal `failed`, surfaced by the token-gated `/admin/plan/<id>/diag`
    # JSON endpoint so an operator/agent can read the real fault WITHOUT the app
    # login — `generation_error` only carries the user-facing copy, and the
    # Vercel runtime-log MCP truncates the traceback (see CLAUDE.md Rule #14).
    # Nullable; the persist (routes/plan_create.py::_mark_plan_failed) is
    # best-effort so the code is deploy-safe even before this column lands.
    "ALTER TABLE plan_versions ADD COLUMN IF NOT EXISTS generation_traceback TEXT",
    # D-77 advance-claim TTL (#350 follow-up, 2026-06-04): the per-plan advance
    # lock is a TTL stamp here, NOT a session pg_advisory_lock. The advisory lock
    # leaked on a hard SIGKILL — a 504-killed pass never ran its `finally`
    # release, and on Neon's transaction pooler the lock survived on the parked
    # backend, so every later advance no-op'd until recycle, starving the plan
    # until the stall backstop failed it (pv=56). A TTL stamp lapses on its own,
    # so a killed claim self-heals. Nullable; the claim/release SQL is
    # deploy-safe only AFTER this column lands (apply before deploying).
    "ALTER TABLE plan_versions ADD COLUMN IF NOT EXISTS advance_lock_until TIMESTAMPTZ",
    # User-facing lifecycle: a manual "mark complete" stamp, set when the athlete
    # retires a plan (e.g. they cancelled it, or it was superseded by a refresh
    # and they want it filed away) regardless of its scope dates. The Plan list
    # buckets ready plans by scope dates into Upcoming / Active / Completed; a
    # non-NULL `completed_at` forces a plan into Completed no matter the dates.
    "ALTER TABLE plan_versions ADD COLUMN IF NOT EXISTS completed_at TIMESTAMPTZ",
    # layer4_cache entry_point drift fix (2026-05-26) — the Layer 3A/3B
    # cached wrappers (2026-05-20) + the NL-parser cache (2026-05-21) write
    # entry_point values the original 4-value CHECK rejected, so every 3A/3B
    # cache write raised CheckViolation, surfacing as an uncaught 500 in plan
    # generation (the cached wrappers reuse the generic CacheBackend storage
    # but were never added to the table constraint). Realign the deployed
    # constraint with cache.VALID_ENTRY_POINTS. Drop-then-add is idempotent;
    # the new set is a superset so existing rows still satisfy it.
    """DO $$
    BEGIN
        ALTER TABLE layer4_cache DROP CONSTRAINT IF EXISTS layer4_cache_entry_point_check;
        ALTER TABLE layer4_cache ADD CONSTRAINT layer4_cache_entry_point_check
            CHECK (entry_point IN ('plan_create', 'plan_refresh', 'single_session_synthesize', 'race_week_brief', 'llm_layer3a_athlete_state', 'llm_layer3b_goal_timeline_viability', 'nl_parser_parse_intent'));
    END $$;""",
    # ── Locations Consolidation (Track 1) ────────────────────────────────
    # Home is `locale_profiles.preferred`; this partial unique index backstops
    # the app-logic "exactly one home per athlete" invariant (§3.3 / §10).
    "CREATE UNIQUE INDEX IF NOT EXISTS locale_profiles_one_home_idx "
    "ON locale_profiles (user_id) WHERE preferred",
    # Drop the legacy equipment model now that every locale uses gym_profiles +
    # overrides on the layer0 canonical vocabulary (§3.2). Idempotent; runs
    # after the unified read/write path ships. Nothing FKs onto locale_equipment
    # (race_route_locale_equipment is a separate table).
    "DROP TABLE IF EXISTS locale_equipment",
    "ALTER TABLE locale_profiles DROP COLUMN IF EXISTS equipment",
    # ── Vercel Log Drain sink (issue #350) ───────────────────────────────
    # Hard-kill backstop the plan-diag endpoint structurally can't be: a
    # gateway 504 / OOM kills the lambda before any `except` runs, so
    # generation_traceback stays NULL. A Vercel Log Drain POSTs runtime
    # stdout/stderr (+ the proxy request log carrying the 504) to
    # /admin/logs/drain; we persist each entry verbatim and query it past the
    # login wall via /admin/logs (routes/logs.py). `raw` is TEXT JSON like the
    # webhook_events sink — full fidelity, no truncation. log_id is UNIQUE so
    # the ingest ON CONFLICT dedups drain retries.
    """CREATE TABLE IF NOT EXISTS vercel_logs (
        id SERIAL PRIMARY KEY,
        log_id TEXT UNIQUE,
        ts TIMESTAMP,
        source TEXT,
        log_type TEXT,
        level TEXT,
        deployment_id TEXT,
        request_id TEXT,
        status_code INTEGER,
        method TEXT,
        path TEXT,
        message TEXT,
        raw TEXT NOT NULL,
        received_at TIMESTAMP DEFAULT NOW()
    )""",
    "CREATE INDEX IF NOT EXISTS idx_vercel_logs_ts ON vercel_logs (ts DESC)",
    "CREATE INDEX IF NOT EXISTS idx_vercel_logs_status ON vercel_logs (status_code) WHERE status_code >= 400",
    "CREATE INDEX IF NOT EXISTS idx_vercel_logs_request ON vercel_logs (request_id)",
    # ── #469 — athlete unit preference + canonical-kg weight migration ────
    # New profile field; defaults to imperial so historical user 1 reads as
    # lb-display until they pick otherwise.
    "ALTER TABLE athlete_profile ADD COLUMN IF NOT EXISTS unit_preference TEXT NOT NULL DEFAULT 'imperial'",
    # Reconcile the known mis-entry: user 1's body_weight_kg=161 was a
    # pounds value typed into the kg-labeled field (surfaced during plan #60
    # triage; ~73 kg ≈ 161 lb). Guarded on the exact mis-entry value so
    # re-runs after a real edit are no-ops.
    "UPDATE athlete_profile SET body_weight_kg = ROUND((161 * 0.45359237)::numeric, 2) "
    "  WHERE user_id = 1 AND body_weight_kg = 161",
    # body_metrics: rename weight_lbs → weight_kg + convert existing rows.
    # The two-step rename pattern (add new, convert, drop old) survives a
    # partial migration: weight_kg appears first, then values land, then
    # the old column drops. Idempotent via IF (NOT) EXISTS.
    "ALTER TABLE body_metrics ADD COLUMN IF NOT EXISTS weight_kg REAL",
    "UPDATE body_metrics SET weight_kg = ROUND((weight_lbs * 0.45359237)::numeric, 3)::real "
    "  WHERE weight_kg IS NULL AND weight_lbs IS NOT NULL",
    "ALTER TABLE body_metrics DROP COLUMN IF EXISTS weight_lbs",
    # training_log_sets: same pattern.
    "ALTER TABLE training_log_sets ADD COLUMN IF NOT EXISTS weight_kg REAL",
    "UPDATE training_log_sets SET weight_kg = ROUND((weight_lbs * 0.45359237)::numeric, 3)::real "
    "  WHERE weight_kg IS NULL AND weight_lbs IS NOT NULL",
    "ALTER TABLE training_log_sets DROP COLUMN IF EXISTS weight_lbs",
    # current_rx: column names are unit-agnostic (current_weight / next_weight),
    # so we convert in place rather than rename. The `_kg_converted` flag
    # column makes this idempotent — flipped to TRUE after first conversion,
    # checked before a second pass would double-convert.
    "ALTER TABLE current_rx ADD COLUMN IF NOT EXISTS weight_kg_converted BOOLEAN NOT NULL DEFAULT FALSE",
    "UPDATE current_rx SET current_weight = ROUND((current_weight * 0.45359237)::numeric, 3)::real, "
    "  next_weight = ROUND((next_weight * 0.45359237)::numeric, 3)::real, "
    "  weight_increment = ROUND((weight_increment * 0.45359237)::numeric, 3)::real, "
    "  weight_kg_converted = TRUE "
    "  WHERE NOT weight_kg_converted",
    # training_log: target_weight / actual_weight / next_weight / body_weight
    # all in lbs historically; convert once.
    "ALTER TABLE training_log ADD COLUMN IF NOT EXISTS weight_kg_converted BOOLEAN NOT NULL DEFAULT FALSE",
    "UPDATE training_log SET target_weight = ROUND((target_weight * 0.45359237)::numeric, 3)::real, "
    "  actual_weight = ROUND((actual_weight * 0.45359237)::numeric, 3)::real, "
    "  next_weight = ROUND((next_weight * 0.45359237)::numeric, 3)::real, "
    "  body_weight = ROUND((body_weight * 0.45359237)::numeric, 3)::real, "
    "  weight_kg_converted = TRUE "
    "  WHERE NOT weight_kg_converted",
    # exercise_inventory.weight_increment is the prescribed bump size in lbs
    # historically; convert to kg so the rx engine works in canonical units.
    "ALTER TABLE exercise_inventory ADD COLUMN IF NOT EXISTS weight_increment_kg_converted BOOLEAN NOT NULL DEFAULT FALSE",
    "UPDATE exercise_inventory SET weight_increment = ROUND((weight_increment * 0.45359237)::numeric, 3)::real, "
    "  weight_increment_kg_converted = TRUE "
    "  WHERE NOT weight_increment_kg_converted",
]

_CLOTHING_SEEDS = [
    ('headwear', 'Nothing'), ('headwear', 'Buff'), ('headwear', 'Ear Band'),
    ('headwear', 'Baseball Cap'), ('headwear', 'Brim Hat'), ('headwear', 'Wool Beanie'),
    ('headwear', 'Fleece Beanie'), ('headwear', 'Balaclava'),
    ('face_neck', 'Nothing'), ('face_neck', 'Buff'), ('face_neck', 'Balaclava'),
    ('upper_base_layer', 'Nothing'), ('upper_base_layer', 'Short Sleeve'),
    ('upper_base_layer', 'Long Sleeve Technical'), ('upper_base_layer', 'Merino Long Sleeve'),
    ('upper_mid_layer', 'Nothing'), ('upper_mid_layer', 'Fleece Pullover'),
    ('upper_mid_layer', 'Fleece Vest'), ('upper_mid_layer', 'Down Vest'),
    ('upper_mid_layer', 'Lightweight Puffy'),
    ('upper_shell', 'Nothing'), ('upper_shell', 'Wind Shell'),
    ('upper_shell', 'Softshell Jacket'), ('upper_shell', 'Rain Jacket'),
    ('upper_shell', 'Hardshell'),
    ('lower_under', 'Nothing'), ('lower_under', 'Shorts'), ('lower_under', 'Bib Shorts'),
    ('lower_under', 'Tights'), ('lower_under', 'Thermal Tights'),
    ('lower_outer', 'Nothing'), ('lower_outer', 'Wind Pants'),
    ('lower_outer', 'Softshell Pants'), ('lower_outer', 'Rain Pants'),
    ('gloves', 'Nothing'), ('gloves', 'Liner Gloves'), ('gloves', 'Lightweight Gloves'),
    ('gloves', 'Waterproof Gloves'), ('gloves', 'Heavy Mitts'),
    ('arm_warmers', 'Nothing'), ('arm_warmers', 'Arm Warmers'),
    ('socks', 'Regular Socks'), ('socks', 'Wool Socks'),
    ('socks', 'Waterproof Socks'), ('socks', 'Compression Socks'),
    ('footwear', 'Trail Runners'), ('footwear', 'Road Running Shoes'),
    ('footwear', 'Hiking Boots'), ('footwear', 'Waterproof Hiking Boots'),
    ('footwear', 'Cycling Shoes'), ('footwear', 'Neoprene Booties'),
    ('footwear', 'Gym Shoes'),
]

# Equipment catalog — single source of truth for seeding equipment_items and the locale profile UI.
# Imported by routes/locales.py; defined here so init_db.py can seed without importing routes.
EQUIPMENT_CATEGORIES = [
    ('Free Weights', [
        ('barbell',      'Barbell (Olympic)'),
        ('ez_bar',       'EZ Curl Bar'),
        ('tricep_bar',   'Tricep Bar (W-bar)'),
        ('hex_bar',      'Hex / Trap Bar'),
        ('dumbbells',    'Dumbbells'),
        ('kettlebell',   'Kettlebell'),
        ('sandbag',      'Sandbag'),
        ('med_ball',     'Med Ball'),
        ('slam_ball',    'Slam Ball'),
    ]),
    ('Racks & Benches', [
        ('squat_rack',       'Squat Rack / Power Cage'),
        ('smith_machine',    'Smith Machine'),
        ('bench_flat',       'Flat Bench'),
        ('bench_adjustable', 'Adjustable / Incline Bench'),
        ('ghd',              'GHD / Hyperextension Bench'),
        ('preacher_bench',   'Preacher Curl Bench'),
    ]),
    ('Bars & Bodyweight Rigs', [
        ('pull_up_bar', 'Pull-Up Bar'),
        ('dip_bars',    'Dip Bars / Parallel Bars'),
        ('rings',       'Gymnastic Rings'),
    ]),
    ('Leg Machines', [
        ('leg_press',          'Leg Press'),
        ('hack_squat',         'Hack Squat Machine'),
        ('leg_extension',      'Leg Extension Machine'),
        ('leg_curl',           'Leg Curl Machine'),
        ('calf_raise_machine', 'Calf Raise Machine'),
    ]),
    ('Upper Body Machines', [
        ('cable_machine',          'Cable Machine / Crossover'),
        ('lat_pulldown',           'Lat Pulldown Machine'),
        ('seated_row_machine',     'Seated Row Machine'),
        ('pec_deck',               'Pec Deck / Chest Fly Machine'),
        ('shoulder_press_machine', 'Shoulder Press Machine'),
        ('assisted_pullup',        'Assisted Pull-Up / Dip Machine'),
    ]),
    ('Cardio', [
        ('treadmill',       'Treadmill'),
        ('elliptical',      'Elliptical / Cross Trainer'),
        ('stationary_bike', 'Stationary Bike (Upright)'),
        ('recumbent_bike',  'Recumbent Bike'),
        ('spin_bike',       'Spin Bike / Peloton'),
        ('stair_climber',   'Stair Climber / StepMill'),
        ('rowing_erg',      'Rowing Erg (Concept2)'),
        ('kayak_erg',       'Kayak Ergometer'),
        ('air_bike',        'Air Bike / Assault Bike'),
        ('ski_erg',         'SkiErg'),
    ]),
    ('Functional & Conditioning', [
        ('sled',             'Sled'),
        ('battle_ropes',     'Battle Ropes'),
        ('plyo_box',         'Plyo Box'),
        ('resistance_bands', 'Resistance Bands'),
        ('trx',              'TRX / Suspension Trainer'),
        ('weighted_vest',    'Weighted Vest'),
        ('jump_rope',        'Jump Rope'),
    ]),
    ('Accessories', [
        ('stability_ball', 'Stability Ball'),
        ('bosu',           'BOSU Ball'),
        ('ab_wheel',       'Ab Wheel'),
        ('foam_roller',    'Foam Roller'),
        ('grip_trainer',   'Grip Trainer (squeeze)'),
        ('rice_bucket',    'Rice Bucket'),
        ('lacrosse_ball',  'Lacrosse Ball / Massage Ball'),
    ]),
    ('Specialty', [
        ('hangboard',     'Hangboard'),
        ('treadwall',     'Treadwall'),
        ('climbing_wall', 'Climbing Wall / Bouldering'),
    ]),
    ('Cycling Equipment', [
        ('road_bike',       'Road Bike'),
        ('mountain_bike',   'Mountain Bike (MTB)'),
        ('gravel_bike',     'Gravel Bike'),
        ('cycling_trainer', 'Cycling Trainer / Smart Trainer'),
    ]),
    ('Paddling Equipment', [
        ('kayak',    'Kayak'),
        ('packraft', 'Packraft'),
        ('canoe',    'Canoe'),
    ]),
    # D-73 Phase 5.2 Bucket C sub-item (g) 2026-05-24 — the "Outdoor &
    # Terrain" equipment category retired here in favour of the
    # `locale_terrain_ids` canonical grid as the single "what's accessible
    # from this location" surface on the locale-edit form. The 9 retired
    # tags (trail_running / road_running / road_cycling / mtb_trails /
    # gravel_routes / open_water_paddle / open_water_swim / pool_swim /
    # hills) translate to TRN-xxx picks via _OUTDOOR_TERRAIN_TAG_TO_TRN_IDS
    # at boot via the _retire_outdoor_terrain_equipment_tags migration.
    # Cycling / paddling GEAR (road_bike / mountain_bike / gravel_bike /
    # kayak / packraft / canoe) UNCHANGED — those are real equipment, not
    # venue markers.
]

# Volume rationale for endurance athletes (cyclists, trail runners, kayakers):
#   Strength training is supplemental — recovery cost must be managed alongside endurance work.
#   2-3 sets per exercise is the evidence-based ceiling; 3 sets is the default here.
#   2 sets is appropriate for novel/accessory work with higher recovery cost.
#   Rep ranges: 6-8 for heavy compounds (strength emphasis), 8-12 for medium compounds,
#               12-20 for accessories and isolation; max reps for bodyweight skills.
#   Total weekly sets per movement pattern (10+) matters more than per-session count.
#
# Progression logic (see calculations.py for implementation):
#   Weight increment is computed at workout time from actual_weight:
#     actual_weight < 15 lb  → 2.5 lb increment  (light KB/DB; micro-plate scale)
#     actual_weight >= 15 lb → 5.0 lb increment   (standard KB/DB or barbell)
#   Bodyweight exercises (no weight): rep increment from PROGRESSION_RULES.
#   Time-based: +5 sec per PROGRESS session.
#   The weight_increment column in exercise_inventory stores an override if needed.
#
# Regression logic:
#   REDUCE outcome (< 75% completion) increments a consecutive_failures counter.
#   REPEAT (75–99%) freezes the counter — no progress, no regression.
#   PROGRESS resets the counter to 0.
#   After 3 consecutive REDUCE outcomes, weight/duration decreases by one step.
#
# Equipment required per exercise — used to filter exercises against locale profiles.
# Tag syntax: 'a,b' = needs a AND b; 'a|b' = needs a OR b; '' = bodyweight (no restriction).
# Tags must match keys in EQUIPMENT_CATEGORIES (defined in routes/locales.py).
EXERCISE_EQUIPMENT = {
    # Bike — Staple
    'Back Squat':                        'barbell,squat_rack',
    'Front Squat':                       'barbell,squat_rack',
    'Goblet Squat':                      'kettlebell|dumbbells',
    'Romanian Deadlift':                 'barbell|dumbbells',
    'Glute Bridge / Hip Thrust':         '',
    'Barbell Hip Thrust':                'barbell,bench_flat',
    'Push-Up':                           '',
    'Dip':                               'dip_bars',
    'Plank':                             '',
    'Side Plank':                        '',
    'Pallof Press':                      'cable_machine|resistance_bands',
    'Mountain Climbers':                 '',
    'Single-Leg Calf Raise':             '',
    'Box Jump':                          'plyo_box',
    'Pedal Stance Deadlift':             'barbell|hex_bar',
    # Bike — Novel
    'Asymmetric Stab. Ball Push-Up':     'stability_ball',
    'TRX Mtn Climber / Unstable Bar':    'trx',
    'Side Plank + Banded Leg Raise':     'resistance_bands',
    'Isometric Lunge Hold':              '',
    'Elevated Reverse Lunge':            'bench_flat',
    'Renegade Row (Plank + DB Row)':     'dumbbells',
    # Foot — Staple
    'Weighted Box Step-Up':              'plyo_box,dumbbells',
    'Bulgarian Split Squat':             'bench_flat',
    'Nordic Hamstring Curl':             '',
    'Walking Lunge':                     '',
    'Single-Leg Deadlift':               'dumbbells|kettlebell|barbell',
    'Pull-Up':                           'pull_up_bar',
    'Single-Leg Glute Bridge':           '',
    'Dead Bug':                          '',
    'Bird Dog':                          '',
    'Glute Kickback (Banded)':           'resistance_bands',
    'Fire Hydrant (Banded)':             'resistance_bands',
    'Clamshell (Banded)':                'resistance_bands',
    'Oblique Press (Contralateral)':     '',
    'Copenhagen Plank':                  'bench_flat',
    'Step-Down (Eccentric)':             'bench_flat',
    'Good Morning':                      'barbell|dumbbells',
    'Back Extension / Rev. Hyper':       'ghd',
    'Banded Pull-Through':               'resistance_bands',
    'Kettlebell Swing (Two-Hand)':       'kettlebell',
    'Single-Arm KB Swing':               'kettlebell',
    'KB Clean & Press':                  'kettlebell',
    'KB Snatch':                         'kettlebell',
    'Farmer Carry':                      'dumbbells|kettlebell',
    'Suitcase Carry':                    'dumbbells|kettlebell',
    'Rack Carry':                        'dumbbells|kettlebell',
    'Overhead Carry':                    'dumbbells|kettlebell',
    'Bear Crawl':                        '',
    'Sled Push':                         'sled',
    'Sled Pull (Hand-Over-Hand)':        'sled',
    'Lunge to Rotation (Slam Ball/DB)':  'slam_ball|med_ball|dumbbells',
    # Foot — Novel
    'Hillbounding':                      '',
    '4-Side Box Step-Up/Off':            'plyo_box',
    '1,000 Step-Up Challenge':           'weighted_vest',
    'Single-Leg Stance Eyes Closed':     '',
    'Towel Pull-Up':                     'pull_up_bar',
    'Hanging Leg Raise in Boots':        'pull_up_bar',
    'Side Split Lunges (Deep)':          '',
    'Rapid Calf Raises':                 '',
    'Weighted Treadmill Incline Walk':   'treadmill',
    # Water — Staple
    'Seated Cable Row':                  'cable_machine',
    'Bent-Over Barbell Row':             'barbell',
    'Lat Pulldown':                      'lat_pulldown',
    'Straight-Arm Lat Pulldown':         'lat_pulldown',
    'Dumbbell Chest Press':              'dumbbells,bench_flat',
    'Plank with Rotation':               '',
    'Forearm Wrist Curls':               'dumbbells|barbell|ez_bar',
    'Deadlift (Standard)':               'barbell|hex_bar',
    'Face Pull':                         'cable_machine|resistance_bands',
    'Band Pull-Apart':                   'resistance_bands',
    'KB Sumo Deadlift':                  'kettlebell',
    'Battle Ropes':                      'battle_ropes',
    # Water — Novel
    'Half-Kneeling 1-Arm Cable Row':     'cable_machine',
    'Cable Woodchop (High-to-Low)':      'cable_machine',
    'Cable Woodchop (Low-to-High)':      'cable_machine',
    'Med Ball Wall Throws (Rotational)': 'med_ball',
    'KB Swing on Inverted BOSU':         'kettlebell,bosu',
    'Russian Twist (Feet Elevated)':     'dumbbells|med_ball',
    'Single-Arm DB Row (Staggered)':     'dumbbells',
    'Med Ball Torso Rotation (Seated)':  'med_ball',
    'High-Rep Strength Endurance Sets':  '',
    # Cross — Staple
    'KB Halo':                           'kettlebell',
    'Push Press':                        'barbell|dumbbells|kettlebell',
    'Sumo Deadlift High Pull':           'barbell|dumbbells|kettlebell',
    'KB Windmill':                       'kettlebell',
    'Turkish Get-Up':                    'kettlebell|dumbbells',
    'Sandbag / Pack Carry (Bear Hug)':   'sandbag',
    'Ab Wheel Rollout':                  'ab_wheel',
    'Hanging Knee Raise':                'pull_up_bar',
    'Wall Sit':                          '',
    'Seated Glute Squeeze (Isometric)':  '',
    # Cross — Novel
    'Sandbag Get-Up':                    'sandbag',
    'Pistol Squat':                      '',
    'Hangboard Max Hangs':               'hangboard',
    '7/3 Repeaters (Hangboard)':         'hangboard',
    'Front Lever Progression':           'pull_up_bar|rings',
    'Rice Bucket':                       'rice_bucket',
    'L-Sit Pull-Up':                     'pull_up_bar|rings',
    'Treadwall Intervals':               'treadwall',
    'Nasal-Breathing-Only Climbing':     'climbing_wall|treadwall',
    'Stability Ball Seated Shoulder Press': 'stability_ball,dumbbells',
    'Stability Ball Single-Arm DB Press':   'stability_ball,dumbbells',
    'Stability Ball Hamstring Curl':        'stability_ball',
    # Mobility — no equipment needed
    'Standing Hip Flexor Stretch':       '',
    'Standing Figure-4 Stretch':         '',
    'Wall Calf Stretch':                 '',
    'Wall Chest / Doorway Stretch':      '',
}

# where_available locale codes (comma-separated when multiple apply):
#   home     = user's home gym (barbell, KB, DB, bands, pull-up bar)
#   hotel    = hotel room / hotel gym (bodyweight; floor space available)
#   partner  = partner's home (bodyweight / minimal equipment assumed)
#   airport  = airport / transit (standing or seated; no floor exercises)
# Blank = gym-only or requires equipment not at any listed locale.

EXERCISES = [
    # (exercise, discipline, type, movement_pattern, suggested_volume, where_available)
    ('Back Squat',                        'Bike',  'Staple', 'Squat',        '3x6-8',             'home'),
    ('Front Squat',                       'Bike',  'Staple', 'Squat',        '3x6-8',             'home'),
    ('Goblet Squat',                      'Bike',  'Staple', 'Squat',        '3x8-12',            'home'),
    ('Romanian Deadlift',                 'Bike',  'Staple', 'Hinge',        '3x8-10',            'home'),
    ('Glute Bridge / Hip Thrust',         'Bike',  'Staple', 'Hinge',        '3x12-15',           'home,hotel,partner'),
    ('Barbell Hip Thrust',                'Bike',  'Staple', 'Hinge',        '3x8-10',            'home'),
    ('Push-Up',                           'Bike',  'Staple', 'Push',         '3x15-20',           'home,hotel,partner'),
    ('Dip',                               'Bike',  'Staple', 'Push',         '3x8-12',            'home'),
    ('Plank',                             'Bike',  'Staple', 'Core',         '3x30-60s',          'home,hotel,partner'),
    ('Side Plank',                        'Bike',  'Staple', 'Core',         '3x30s ea',          'home,hotel,partner'),
    ('Pallof Press',                      'Bike',  'Staple', 'Core',         '3x10 ea',           'home'),
    ('Mountain Climbers',                 'Bike',  'Staple', 'Core',         '3x30s',             'home,hotel,partner'),
    ('Single-Leg Calf Raise',             'Bike',  'Staple', 'Squat',        '3x15 ea',           'home,hotel,partner,airport'),
    ('Box Jump',                          'Bike',  'Staple', 'Plyo',         '3x5-8',             'home'),
    ('Pedal Stance Deadlift',             'Bike',  'Novel',  'Hinge',        '2-3x5-10',          'home'),
    ('Asymmetric Stab. Ball Push-Up',     'Bike',  'Novel',  'Push',         '3x10',              'home'),
    ('TRX Mtn Climber / Unstable Bar',    'Bike',  'Novel',  'Core',         '3x20',              'home'),
    ('Side Plank + Banded Leg Raise',     'Bike',  'Novel',  'Core',         '3x10 ea',           'home'),
    ('Isometric Lunge Hold',              'Bike',  'Novel',  'Lunge',        '2-3x30-90s',        'home,hotel,partner,airport'),
    ('Elevated Reverse Lunge',            'Bike',  'Novel',  'Lunge',        '3x8-10 ea',         'home,hotel,partner'),
    ('Renegade Row (Plank + DB Row)',      'Bike',  'Novel',  'Pull',         '3x8 ea',            'home'),
    ('Weighted Box Step-Up',              'Foot',  'Staple', 'Lunge',        '3x10 ea',           'home'),
    ('Bulgarian Split Squat',             'Foot',  'Staple', 'Lunge',        '3x8-10 ea',         'home,hotel,partner'),
    ('Nordic Hamstring Curl',             'Foot',  'Staple', 'Hinge',        '3x4-6, 2x/wk',     'home,hotel,partner'),
    ('Walking Lunge',                     'Foot',  'Staple', 'Lunge',        '3x12 ea',           'home,hotel,partner'),
    ('Single-Leg Deadlift',               'Foot',  'Staple', 'Hinge',        '3x8-10 ea',         'home,hotel,partner'),
    ('Pull-Up',                           'Foot',  'Staple', 'Pull',         '3x max',            'home'),
    ('Single-Leg Glute Bridge',           'Foot',  'Staple', 'Hinge',        '3x20 ea',           'home,hotel,partner'),
    ('Dead Bug',                          'Foot',  'Staple', 'Core',         '3x60s',             'home,hotel,partner'),
    ('Bird Dog',                          'Foot',  'Staple', 'Core',         '3x10 ea',           'home,hotel,partner'),
    ('Glute Kickback (Banded)',            'Foot',  'Staple', 'Hinge',        '3x20 ea',           'home'),
    ('Fire Hydrant (Banded)',              'Foot',  'Staple', 'Core',         '3x15 ea',           'home'),
    ('Clamshell (Banded)',                'Foot',  'Staple', 'Core',         '3x15 ea',           'home'),
    ('Oblique Press (Contralateral)',      'Foot',  'Staple', 'Core',         '3x60s alt.',        'home,hotel,partner'),
    ('Copenhagen Plank',                  'Foot',  'Staple', 'Core',         '3x15-30s ea',       'home,hotel,partner'),
    ('Step-Down (Eccentric)',              'Foot',  'Staple', 'Squat',        '3x10 ea',           'home,hotel,partner'),
    ('Good Morning',                      'Foot',  'Staple', 'Hinge',        '3x8-10',            'home,hotel,partner'),
    ('Back Extension / Rev. Hyper',       'Foot',  'Staple', 'Hinge',        '3x12-15',           'home'),
    ('Banded Pull-Through',               'Foot',  'Staple', 'Hinge',        '3x12-15',           'home'),
    ('Kettlebell Swing (Two-Hand)',        'Foot',  'Staple', 'Hinge',        '3-5x10-15',         'home'),
    ('Single-Arm KB Swing',               'Foot',  'Staple', 'Hinge',        '3x10 ea',           'home'),
    ('KB Clean & Press',                  'Foot',  'Staple', 'Push',         '3x6-8 ea',          'home'),
    ('KB Snatch',                         'Foot',  'Staple', 'Hinge',        '3x5-8 ea',          'home'),
    ('Farmer Carry',                      'Foot',  'Staple', 'Carry',        '3-4x40-60m',        'home'),
    ('Suitcase Carry',                    'Foot',  'Staple', 'Carry',        '3x40-60m ea',       'home'),
    ('Rack Carry',                        'Foot',  'Staple', 'Carry',        '3x40-60m',          'home'),
    ('Overhead Carry',                    'Foot',  'Staple', 'Carry',        '3x30-40m ea',       'home'),
    ('Bear Crawl',                        'Foot',  'Staple', 'Core',         '3x20-30m',          'home,hotel,partner'),
    ('Sled Push',                         'Foot',  'Staple', 'Squat',        '4-6x30-40m',        ''),
    ('Sled Pull (Hand-Over-Hand)',         'Foot',  'Staple', 'Pull',         '4-6x20-30m',        ''),
    ('Lunge to Rotation (Slam Ball/DB)',   'Foot',  'Staple', 'Lunge',        '3x8-10 ea',         'home'),
    ('Hillbounding',                      'Foot',  'Novel',  'Plyo',         '6-10x30s',          ''),
    ('4-Side Box Step-Up/Off',            'Foot',  'Novel',  'Lunge',        'Build to 4 circuits','home'),
    ('1,000 Step-Up Challenge',           'Foot',  'Novel',  'Lunge',        'Build to 1000 w/25lb','home'),
    ('Single-Leg Stance Eyes Closed',     'Foot',  'Novel',  'Balance',      '3x30s ea, daily',   'home,hotel,partner,airport'),
    ('Towel Pull-Up',                     'Foot',  'Novel',  'Pull',         '3x max',            'home'),
    ('Hanging Leg Raise in Boots',        'Foot',  'Novel',  'Core',         '3x8-12',            'home'),
    ('Side Split Lunges (Deep)',           'Foot',  'Novel',  'Squat',        '3x8 ea',            'home,hotel,partner,airport'),
    ('Rapid Calf Raises',                 'Foot',  'Novel',  'Plyo',         '3x30s',             'home,hotel,partner,airport'),
    ('Weighted Treadmill Incline Walk',   'Foot',  'Novel',  'Locomotion',   '30-60 min Z2-3',    ''),
    ('Seated Cable Row',                  'Water', 'Staple', 'Pull',         '3x10-12',           ''),
    ('Bent-Over Barbell Row',             'Water', 'Staple', 'Pull',         '3x6-8',             'home'),
    ('Lat Pulldown',                      'Water', 'Staple', 'Pull',         '3x10-12',           ''),
    ('Straight-Arm Lat Pulldown',         'Water', 'Staple', 'Pull',         '3x12-15',           ''),
    ('Dumbbell Chest Press',              'Water', 'Staple', 'Push',         '3x10-12',           'home'),
    ('Plank with Rotation',               'Water', 'Staple', 'Core',         '3x10 ea',           'home,hotel,partner'),
    ('Forearm Wrist Curls',               'Water', 'Staple', 'Pull',         '3x15-20',           'home'),
    ('Deadlift (Standard)',               'Water', 'Staple', 'Hinge',        '3x6-8',             'home'),
    ('Face Pull',                         'Water', 'Staple', 'Pull',         '3x15-20',           'home'),
    ('Band Pull-Apart',                   'Water', 'Staple', 'Pull',         '3x15-20',           'home'),
    ('KB Sumo Deadlift',                  'Water', 'Staple', 'Hinge',        '3x8-10',            'home'),
    ('Battle Ropes',                      'Water', 'Staple', 'Conditioning', '3-6x30s on/off',    ''),
    ('Half-Kneeling 1-Arm Cable Row',     'Water', 'Novel',  'Pull',         '3x8-10 ea',         ''),
    ('Cable Woodchop (High-to-Low)',       'Water', 'Novel',  'Rotation',     '3x10-12 ea',        ''),
    ('Cable Woodchop (Low-to-High)',       'Water', 'Novel',  'Rotation',     '3x10-12 ea',        ''),
    ('Med Ball Wall Throws (Rotational)', 'Water', 'Novel',  'Rotation',     '3x10 ea',           ''),
    ('KB Swing on Inverted BOSU',         'Water', 'Novel',  'Hinge',        '3x10-12',           'home'),
    ('Russian Twist (Feet Elevated)',      'Water', 'Novel',  'Rotation',     '3x20',              'home,hotel,partner'),
    ('Single-Arm DB Row (Staggered)',      'Water', 'Novel',  'Pull',         '3x8-10 ea',         'home'),
    ('Med Ball Torso Rotation (Seated)',   'Water', 'Novel',  'Rotation',     '3x15 ea',           ''),
    ('High-Rep Strength Endurance Sets',  'Water', 'Novel',  'Various',      '3-5x12-20',         ''),
    ('KB Halo',                           'Cross', 'Staple', 'Core',         '2-3x8 ea dir.',     'home'),
    ('Push Press',                        'Cross', 'Staple', 'Push',         '3x5-8',             'home'),
    ('Sumo Deadlift High Pull',           'Cross', 'Staple', 'Pull',         '3x6-8',             'home'),
    ('KB Windmill',                       'Cross', 'Staple', 'Core',         '3x5-8 ea',          'home'),
    ('Turkish Get-Up',                    'Cross', 'Staple', 'Core',         '3x3-5 ea',          'home'),
    ('Sandbag / Pack Carry (Bear Hug)',    'Cross', 'Staple', 'Carry',        '3x40-60m',          'home'),
    ('Ab Wheel Rollout',                  'Cross', 'Staple', 'Core',         '3x8-12',            'home'),
    ('Hanging Knee Raise',                'Cross', 'Staple', 'Core',         '3x10-15',           'home'),
    ('Sandbag Get-Up',                    'Cross', 'Novel',  'Core',         '5 reps per side',   'home'),
    ('Pistol Squat',                      'Cross', 'Novel',  'Squat',        '3x5-8 ea',          'home,hotel,partner,airport'),
    ('Hangboard Max Hangs',               'Cross', 'Novel',  'Grip',         '3-5x7-10s',         'home'),
    ('7/3 Repeaters (Hangboard)',         'Cross', 'Novel',  'Grip',         '3-5 sets to fail',  'home'),
    ('Front Lever Progression',           'Cross', 'Novel',  'Pull',         '3x5-10s holds',     'home'),
    ('Rice Bucket',                       'Cross', 'Novel',  'Grip',         '3-5 min daily',     'home'),
    ('L-Sit Pull-Up',                     'Cross', 'Novel',  'Pull',         '3x max',            'home'),
    ('Treadwall Intervals',               'Cross', 'Novel',  'Conditioning', '6x30s on/off',      ''),
    ('Nasal-Breathing-Only Climbing',     'Cross', 'Novel',  'Various',      '15-30 min cont.',   ''),
    ('Stability Ball Seated Shoulder Press','Water','Novel', 'Push',         '3x8-10',            'home'),
    ('Stability Ball Single-Arm DB Press','Cross', 'Novel',  'Push',         '3x8-10 ea',         'home'),
    ('Stability Ball Hamstring Curl',     'Foot',  'Novel',  'Hinge',        '3x10-12',           'home'),
    ('Wall Sit',                          'Cross', 'Staple', 'Squat',        '3x30-90s',          'home,hotel,partner,airport'),
    ('Seated Glute Squeeze (Isometric)',   'Cross', 'Staple', 'Hinge',        '5x10s squeeze',     'home,hotel,partner,airport'),
    ('Standing Hip Flexor Stretch',       'Foot',  'Staple', 'Mobility',     '2-3x30-60s each',   'home,hotel,partner,airport'),
    ('Standing Figure-4 Stretch',         'Foot',  'Staple', 'Mobility',     '2-3x30-60s each',   'home,hotel,partner,airport'),
    ('Wall Calf Stretch',                 'Foot',  'Staple', 'Mobility',     '2x30s each leg',    'home,hotel,partner,airport'),
    ('Wall Chest / Doorway Stretch',      'Water', 'Staple', 'Mobility',     '2-3x30s each',      'home,hotel,partner,airport'),
]


def init_postgres():
    import psycopg2
    conn = psycopg2.connect(DATABASE_URL)
    cur = conn.cursor()
    for stmt in [s.strip() for s in PG_SCHEMA.split(';') if s.strip()]:
        cur.execute(stmt)
    # Run migrations for columns added after initial deploy. Callable migrations
    # receive `cur`; string migrations are executed directly. Each migration
    # runs in its own transaction so a failure (e.g. SET NOT NULL on a column
    # that still has NULLs pre-bootstrap) doesn't abort the whole batch.
    for stmt in _PG_MIGRATIONS:
        try:
            if callable(stmt):
                stmt(cur)
            else:
                cur.execute(stmt)
            conn.commit()
        except Exception:
            conn.rollback()
    # Seed current_rx for user 1 only — pre-bootstrap, the table stays empty
    # (NOT NULL on user_id post-2D would reject NULL inserts anyway). Andy's
    # rows are seeded inline by routes/auth.py:register on first-user bootstrap.
    cur.execute('SELECT 1 FROM users WHERE id = 1')
    if cur.fetchone():
        _seed_current_rx_for_user(cur, 1)
    # Seed exercise_inventory
    cur.executemany(
        '''INSERT INTO exercise_inventory
           (exercise, discipline, type, movement_pattern, suggested_volume, where_available)
           VALUES (%s, %s, %s, %s, %s, %s)
           ON CONFLICT (exercise) DO NOTHING''',
        EXERCISES
    )
    # Seed exercise equipment tags (always update — safe to re-run)
    for exercise, tags in EXERCISE_EQUIPMENT.items():
        cur.execute(
            'UPDATE exercise_inventory SET equipment=%s WHERE exercise=%s',
            (tags, exercise)
        )
    # Phase 1 — Seed equipment_items catalog (idempotent)
    for category_name, items in EQUIPMENT_CATEGORIES:
        for tag, label in items:
            cur.execute(
                'INSERT INTO equipment_items (tag, label, category) VALUES (%s, %s, %s) '
                'ON CONFLICT (tag) DO NOTHING',
                (tag, label, category_name)
            )
    # Phase 2 — Build lookup dicts
    cur.execute('SELECT id, tag FROM equipment_items')
    tag_to_id = {row[1]: row[0] for row in cur.fetchall()}
    cur.execute('SELECT id, exercise FROM exercise_inventory')
    ex_to_id  = {row[1]: row[0] for row in cur.fetchall()}
    # Phase 2b — Seed shared purchase_recommendations catalog (UPSERT on slug)
    _seed_purchase_recommendations(cur, tag_to_id)
    # Phase 3 — Seed exercise_equipment (idempotent)
    for exercise_name, tag_str in EXERCISE_EQUIPMENT.items():
        ex_id = ex_to_id.get(exercise_name)
        if ex_id is None or not tag_str:
            continue
        for group_num, group in enumerate(tag_str.split('|'), start=1):
            for tag in [t.strip() for t in group.split(',') if t.strip()]:
                eq_id = tag_to_id.get(tag)
                if eq_id:
                    cur.execute(
                        'INSERT INTO exercise_equipment '
                        '(exercise_id, equipment_id, option_group) VALUES (%s, %s, %s) '
                        'ON CONFLICT DO NOTHING',
                        (ex_id, eq_id, group_num)
                    )
    # Phase 4 — (removed) the legacy locale_profiles.equipment → locale_equipment
    # backfill retired with Track 1: the locale_equipment table is dropped and
    # every locale now stores equipment as layer0 canonical names in
    # gym_profiles + locale_equipment_overrides.
    # Phase 5 — Backfill exercise_id FKs (runs after seeding so exercise_inventory is populated)
    cur.execute('''UPDATE current_rx SET exercise_id = ei.id
        FROM exercise_inventory ei WHERE ei.exercise = current_rx.exercise
        AND current_rx.exercise_id IS NULL''')
    cur.execute('''UPDATE training_log SET exercise_id = ei.id
        FROM exercise_inventory ei WHERE ei.exercise = training_log.exercise
        AND training_log.exercise_id IS NULL''')
    # clothing_options is now per-user (Session 3) — values accumulate as
    # the user types into the conditions form. No global seed.
    conn.commit()
    cur.close()
    conn.close()
    print('Postgres database initialized.')


if __name__ == '__main__':
    init_postgres()
