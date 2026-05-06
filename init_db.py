"""Initialize the database — supports both SQLite (local) and Postgres (production)."""
import os
import sqlite3

from database import sqlite_path

DATABASE_URL = os.environ.get('DATABASE_URL')
SQLITE_PATH = sqlite_path()

SQLITE_SCHEMA = '''
    CREATE TABLE IF NOT EXISTS users (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        username TEXT NOT NULL UNIQUE,
        email TEXT UNIQUE,
        password_hash TEXT NOT NULL,
        display_name TEXT,
        created_at TEXT DEFAULT (datetime('now')),
        last_login TEXT
    );
    CREATE TABLE IF NOT EXISTS athlete_profile (
        user_id INTEGER PRIMARY KEY REFERENCES users(id),
        date_of_birth TEXT,
        sex TEXT,
        height_cm REAL,
        primary_sport TEXT,
        target_event_name TEXT,
        target_event_date TEXT,
        weekly_hours_target REAL,
        training_window TEXT,
        notes TEXT,
        updated_at TEXT DEFAULT (datetime('now'))
    );
    CREATE TABLE IF NOT EXISTS exercise_inventory (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        exercise TEXT NOT NULL UNIQUE,
        type TEXT, discipline TEXT, equipment TEXT, muscles_worked TEXT,
        skills_ar_carryover TEXT, where_available TEXT, source TEXT,
        suggested_volume TEXT, substitution_group TEXT, recovery_cost TEXT,
        movement_pattern TEXT, session_placement TEXT, form_cue TEXT, video_reference TEXT,
        weight_increment REAL
    );
    CREATE TABLE IF NOT EXISTS training_sessions (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER REFERENCES users(id),
        date TEXT NOT NULL,
        notes TEXT,
        plan_item_id INTEGER REFERENCES plan_items(id),
        created_at TEXT DEFAULT (datetime('now'))
    );
    CREATE TABLE IF NOT EXISTS training_log (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
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
        created_at TEXT DEFAULT (datetime('now'))
    );
    CREATE TABLE IF NOT EXISTS training_log_sets (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER REFERENCES users(id),
        training_log_id INTEGER NOT NULL REFERENCES training_log(id) ON DELETE CASCADE,
        set_number INTEGER NOT NULL,
        reps INTEGER,
        weight_lbs REAL,
        duration_sec INTEGER
    );
    CREATE TABLE IF NOT EXISTS current_rx (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
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
        id INTEGER PRIMARY KEY AUTOINCREMENT,
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
        notes TEXT, created_at TEXT DEFAULT (datetime('now'))
    );
    CREATE TABLE IF NOT EXISTS body_metrics (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER REFERENCES users(id),
        date TEXT NOT NULL, weight_lbs REAL, body_fat_pct REAL,
        vo2_max REAL, resting_hr INTEGER, notes TEXT,
        created_at TEXT DEFAULT (datetime('now')),
        UNIQUE(user_id, date)
    );
    CREATE TABLE IF NOT EXISTS conditions_log (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER REFERENCES users(id),
        date TEXT NOT NULL, activity TEXT, temp_f REAL, feels_like_f REAL,
        wind_mph REAL, wind_dir TEXT, conditions TEXT,
        headwear TEXT, face_neck TEXT, upper_shell TEXT, upper_mid_layer TEXT,
        upper_base_layer TEXT, lower_outer TEXT, lower_under TEXT,
        gloves TEXT, arm_warmers TEXT, socks TEXT, footwear TEXT,
        comfort INTEGER, comfort_notes TEXT,
        cardio_log_id INTEGER REFERENCES cardio_log(id),
        created_at TEXT DEFAULT (datetime('now'))
    );
    CREATE TABLE IF NOT EXISTS injury_log (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER REFERENCES users(id),
        start_date TEXT NOT NULL, body_part TEXT NOT NULL, description TEXT,
        severity INTEGER, modifications_needed TEXT, status TEXT DEFAULT 'Active',
        resolved_date TEXT, created_at TEXT DEFAULT (datetime('now'))
    );
    CREATE TABLE IF NOT EXISTS training_modalities (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        activity TEXT NOT NULL UNIQUE, category TEXT, primary_benefits TEXT,
        equipment_needed TEXT, where_available TEXT, ar_carryover TEXT
    );
    CREATE TABLE IF NOT EXISTS training_methods (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        method TEXT NOT NULL, description TEXT, apply_to TEXT, source TEXT
    );
    CREATE TABLE IF NOT EXISTS training_plans (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER REFERENCES users(id),
        name TEXT NOT NULL,
        description TEXT,
        sport_focus TEXT,
        start_date TEXT,
        end_date TEXT,
        status TEXT DEFAULT 'active',
        source_json TEXT,
        created_at TEXT DEFAULT (datetime('now'))
    );
    CREATE TABLE IF NOT EXISTS plan_items (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
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
        created_at TEXT DEFAULT (datetime('now'))
    );
    CREATE TABLE IF NOT EXISTS plan_reviews (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        plan_id INTEGER NOT NULL REFERENCES training_plans(id),
        tier INTEGER NOT NULL,
        sessions_reviewed INTEGER DEFAULT 0,
        notes TEXT,
        created_at TEXT DEFAULT (datetime('now'))
    );
    CREATE TABLE IF NOT EXISTS feedback_log (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER REFERENCES users(id),
        source TEXT NOT NULL,
        source_ref_id INTEGER,
        raw_content TEXT NOT NULL,
        captured_at TEXT DEFAULT (datetime('now'))
    );
    CREATE TABLE IF NOT EXISTS coaching_preferences (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER REFERENCES users(id),
        category TEXT NOT NULL DEFAULT 'general',
        content TEXT NOT NULL,
        permanent INTEGER NOT NULL DEFAULT 1,
        source_feedback_id INTEGER REFERENCES feedback_log(id),
        created_at TEXT DEFAULT (datetime('now'))
    );
    CREATE TABLE IF NOT EXISTS coaching_chat (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER REFERENCES users(id),
        plan_id INTEGER REFERENCES training_plans(id),
        role TEXT NOT NULL,
        content TEXT NOT NULL,
        actions_json TEXT,
        created_at TEXT DEFAULT (datetime('now'))
    );
    CREATE TABLE IF NOT EXISTS garmin_auth (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER REFERENCES users(id),
        garmin_username TEXT,
        garth_session TEXT,
        created_at TEXT DEFAULT (datetime('now')),
        updated_at TEXT DEFAULT (datetime('now'))
    );
    CREATE TABLE IF NOT EXISTS garmin_workouts (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER REFERENCES users(id),
        plan_item_id INTEGER REFERENCES plan_items(id),
        garmin_workout_id TEXT NOT NULL,
        workout_name TEXT,
        sport_type TEXT,
        scheduled_date TEXT,
        status TEXT DEFAULT 'active',
        created_at TEXT DEFAULT (datetime('now'))
    );
    CREATE TABLE IF NOT EXISTS locale_profiles (
        user_id INTEGER NOT NULL REFERENCES users(id),
        locale TEXT NOT NULL,
        equipment TEXT DEFAULT '',
        notes TEXT DEFAULT '',
        city TEXT DEFAULT '',
        updated_at TEXT DEFAULT (datetime('now')),
        PRIMARY KEY (user_id, locale)
    );
    CREATE TABLE IF NOT EXISTS plan_travel (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        plan_id INTEGER NOT NULL REFERENCES training_plans(id),
        start_date TEXT NOT NULL,
        end_date TEXT NOT NULL,
        locale TEXT NOT NULL,
        city TEXT DEFAULT '',
        notes TEXT DEFAULT '',
        created_at TEXT DEFAULT (datetime('now'))
    );
    CREATE TABLE IF NOT EXISTS equipment_items (
        id       INTEGER PRIMARY KEY AUTOINCREMENT,
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
        id                     INTEGER PRIMARY KEY AUTOINCREMENT,
        injury_id              INTEGER NOT NULL REFERENCES injury_log(id),
        exercise_id            INTEGER NOT NULL REFERENCES exercise_inventory(id),
        substitute_exercise_id INTEGER REFERENCES exercise_inventory(id),
        modification_type      TEXT NOT NULL DEFAULT 'modify',
        modification_notes     TEXT,
        created_at             TEXT DEFAULT (datetime('now'))
    );
    CREATE INDEX IF NOT EXISTS idx_tl_date ON training_log(date);
    CREATE INDEX IF NOT EXISTS idx_tl_exercise ON training_log(exercise);
    CREATE INDEX IF NOT EXISTS idx_cl_date ON cardio_log(date);
    CREATE INDEX IF NOT EXISTS idx_bm_date ON body_metrics(date);
    CREATE INDEX IF NOT EXISTS idx_pi_plan ON plan_items(plan_id);
    CREATE INDEX IF NOT EXISTS idx_pi_date ON plan_items(item_date);
    CREATE TABLE IF NOT EXISTS clothing_options (
        id       INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id  INTEGER NOT NULL REFERENCES users(id),
        category TEXT NOT NULL,
        value    TEXT NOT NULL,
        UNIQUE(user_id, category, value)
    );
    CREATE TABLE IF NOT EXISTS wellness_log (
        id             INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id        INTEGER REFERENCES users(id),
        date           TEXT NOT NULL,
        timestamp_ms   INTEGER NOT NULL,
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
        id           INTEGER PRIMARY KEY AUTOINCREMENT,
        slug         TEXT NOT NULL UNIQUE,
        label        TEXT NOT NULL,
        equipment_id INTEGER REFERENCES equipment_items(id),
        est_cost_low INTEGER,
        est_cost_high INTEGER,
        priority     TEXT NOT NULL DEFAULT 'medium',
        rationale    TEXT,
        sort_order   INTEGER NOT NULL DEFAULT 0,
        active       INTEGER NOT NULL DEFAULT 1
    );
    CREATE TABLE IF NOT EXISTS user_purchase_recommendations (
        user_id     INTEGER NOT NULL REFERENCES users(id),
        purchase_id INTEGER NOT NULL REFERENCES purchase_recommendations(id),
        status      TEXT NOT NULL,
        user_notes  TEXT,
        updated_at  TEXT DEFAULT (datetime('now')),
        PRIMARY KEY (user_id, purchase_id)
    );
'''

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
        target_event_name TEXT,
        target_event_date TEXT,
        weekly_hours_target REAL,
        training_window TEXT,
        notes TEXT,
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
        weight_lbs REAL,
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
        date TEXT NOT NULL, weight_lbs REAL, body_fat_pct REAL,
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


# ── Session 2D — composite-UNIQUE rebuild helpers (SQLite) ────────────────────
#
# SQLite can't ALTER a constraint in place. The Session 2D contract is to
# move three single-column UNIQUEs to composite (user_id, X) so each user
# can independently own a row — current_rx.exercise, body_metrics.date,
# wellness_log.timestamp_ms.
#
# These helpers detect via sqlite_master.sql whether the new constraint is
# already present. If so, no-op. Otherwise rebuild the table by copying rows
# forward into a new table with the desired shape and renaming.

def _rebuild_table_if_legacy_unique(conn, table, new_create_sql, new_constraint_substr):
    """Rebuild `table` by copy-into-new-and-rename if the existing schema
    doesn't already contain `new_constraint_substr`. Idempotent."""
    row = conn.execute(
        "SELECT sql FROM sqlite_master WHERE type='table' AND name=?", (table,)
    ).fetchone()
    if not row or row[0] is None:
        return  # Table doesn't exist; CREATE TABLE in the schema uses the new shape.
    if new_constraint_substr in row[0]:
        return  # Already rebuilt.

    # Pull the existing column list so the INSERT-into-new is column-explicit
    # (defensive against column-order mismatches between old and new shapes).
    cols = [r[1] for r in conn.execute(f'PRAGMA table_info({table})').fetchall()]
    col_list = ', '.join(cols)

    conn.commit()  # flush any pending implicit-tx state
    conn.execute('PRAGMA foreign_keys = OFF')
    try:
        conn.execute(f'DROP TABLE IF EXISTS {table}__rebuild_tmp')
        # Build the new table under a temporary name so we can rename atomically.
        # The caller's `new_create_sql` references `<table>` literally; rewrite the
        # first occurrence to the temp name. Triggered FKs / indexes are NOT copied
        # here — none currently apply to the three rebuild targets.
        conn.execute(new_create_sql.replace(table, f'{table}__rebuild_tmp', 1))
        conn.execute(
            f'INSERT INTO {table}__rebuild_tmp ({col_list}) SELECT {col_list} FROM {table}'
        )
        conn.execute(f'DROP TABLE {table}')
        conn.execute(f'ALTER TABLE {table}__rebuild_tmp RENAME TO {table}')
        conn.commit()
    finally:
        conn.execute('PRAGMA foreign_keys = ON')


def _migrate_current_rx_unique(conn):
    _rebuild_table_if_legacy_unique(
        conn, 'current_rx',
        '''CREATE TABLE current_rx (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER REFERENCES users(id),
            exercise TEXT NOT NULL,
            exercise_id INTEGER REFERENCES exercise_inventory(id),
            discipline TEXT, type TEXT, movement_pattern TEXT,
            inventory_sugg_volume TEXT, current_sets INTEGER, current_reps INTEGER,
            current_weight REAL, current_duration INTEGER, last_performed TEXT,
            last_outcome TEXT, consecutive_failures INTEGER DEFAULT 0, rx_source TEXT,
            weight_increment REAL,
            next_sets INTEGER, next_reps INTEGER, next_weight REAL,
            next_duration INTEGER, sessions_since_progress INTEGER DEFAULT 0,
            UNIQUE(user_id, exercise)
        )''',
        'UNIQUE(user_id, exercise)',
    )


def _migrate_body_metrics_unique(conn):
    _rebuild_table_if_legacy_unique(
        conn, 'body_metrics',
        '''CREATE TABLE body_metrics (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER REFERENCES users(id),
            date TEXT NOT NULL, weight_lbs REAL, body_fat_pct REAL,
            vo2_max REAL, resting_hr INTEGER, notes TEXT,
            created_at TEXT DEFAULT (datetime('now')),
            UNIQUE(user_id, date)
        )''',
        'UNIQUE(user_id, date)',
    )


def _migrate_wellness_log_unique(conn):
    _rebuild_table_if_legacy_unique(
        conn, 'wellness_log',
        '''CREATE TABLE wellness_log (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER REFERENCES users(id),
            date TEXT NOT NULL, timestamp_ms INTEGER NOT NULL,
            heart_rate INTEGER, stress_level INTEGER, body_battery INTEGER,
            respiration_rate REAL, steps INTEGER, active_calories INTEGER,
            active_time_s REAL, distance_m REAL, activity_type INTEGER,
            source TEXT DEFAULT 'wellness_fit',
            UNIQUE(user_id, timestamp_ms)
        )''',
        'UNIQUE(user_id, timestamp_ms)',
    )


# ── Session 3 — clothing_options + locale_profiles per-user (SQLite) ──────────
#
# Three connected rebuilds:
#   - clothing_options: drop the global seed list; new shape is (user_id,
#     category, value) UNIQUE, NOT NULL on user_id. Existing rows on a
#     populated DB belong to Andy → backfill user_id=1 during rebuild.
#   - locale_profiles: PK becomes composite (user_id, locale). Existing
#     rows have user_id from 2A (NULLABLE) — coerce to user_id=1 on
#     rebuild; drop any orphan NULL rows (none expected post-2A backfill).
#   - locale_equipment: gain user_id, composite FK, composite PK. Backfill
#     user_id from the parent locale_profiles row.
#
# Order matters because of FKs. PRAGMA foreign_keys=OFF is held across
# all three rebuilds.

def _migrate_session3_locale_clothing(conn):
    """Per-user clothing_options + composite-PK locale_profiles +
    user-scoped locale_equipment. Idempotent — checks each table's schema
    via sqlite_master before rebuilding."""

    def _has_new_shape(table, sentinel):
        row = conn.execute(
            "SELECT sql FROM sqlite_master WHERE type='table' AND name=?", (table,)
        ).fetchone()
        return bool(row and row[0] and sentinel in row[0])

    needs_clothing = not _has_new_shape('clothing_options', 'UNIQUE(user_id, category, value)')
    needs_locale_profiles = not _has_new_shape('locale_profiles', 'PRIMARY KEY (user_id, locale)')
    needs_locale_equipment = not _has_new_shape('locale_equipment', 'PRIMARY KEY (user_id, locale, equipment_id)')

    if not (needs_clothing or needs_locale_profiles or needs_locale_equipment):
        return

    conn.commit()
    conn.execute('PRAGMA foreign_keys = OFF')
    try:
        if needs_clothing and conn.execute(
            "SELECT 1 FROM sqlite_master WHERE type='table' AND name='clothing_options'"
        ).fetchone():
            conn.execute('DROP TABLE IF EXISTS clothing_options__rebuild_tmp')
            conn.execute('''CREATE TABLE clothing_options__rebuild_tmp (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL REFERENCES users(id),
                category TEXT NOT NULL,
                value TEXT NOT NULL,
                UNIQUE(user_id, category, value)
            )''')
            # Existing rows belong to Andy if user 1 exists. Otherwise drop
            # them — fresh installs start empty per the per-user design.
            if conn.execute('SELECT 1 FROM users WHERE id = 1').fetchone():
                conn.execute(
                    'INSERT OR IGNORE INTO clothing_options__rebuild_tmp (category, value, user_id) '
                    'SELECT category, value, 1 FROM clothing_options'
                )
            conn.execute('DROP TABLE clothing_options')
            conn.execute('ALTER TABLE clothing_options__rebuild_tmp RENAME TO clothing_options')

        if needs_locale_profiles and conn.execute(
            "SELECT 1 FROM sqlite_master WHERE type='table' AND name='locale_profiles'"
        ).fetchone():
            conn.execute('DROP TABLE IF EXISTS locale_profiles__rebuild_tmp')
            conn.execute('''CREATE TABLE locale_profiles__rebuild_tmp (
                user_id INTEGER NOT NULL REFERENCES users(id),
                locale TEXT NOT NULL,
                equipment TEXT DEFAULT '',
                notes TEXT DEFAULT '',
                city TEXT DEFAULT '',
                updated_at TEXT DEFAULT (datetime('now')),
                PRIMARY KEY (user_id, locale)
            )''')
            # Coerce any rows with NULL user_id to user 1 (legacy backfill
            # from 2A should have caught them, but defend against partial
            # state). Drop NULL rows entirely if user 1 doesn't exist.
            cols_pre = [r[1] for r in conn.execute('PRAGMA table_info(locale_profiles)').fetchall()]
            shared_cols = [c for c in cols_pre
                           if c in ('user_id', 'locale', 'equipment', 'notes',
                                    'city', 'updated_at')]
            select_list = ', '.join(
                'COALESCE(user_id, 1) AS user_id' if c == 'user_id' else c
                for c in shared_cols
            )
            insert_list = ', '.join(shared_cols)
            if conn.execute('SELECT 1 FROM users WHERE id = 1').fetchone():
                conn.execute(
                    f'INSERT OR IGNORE INTO locale_profiles__rebuild_tmp ({insert_list}) '
                    f'SELECT {select_list} FROM locale_profiles'
                )
            else:
                conn.execute(
                    f'INSERT OR IGNORE INTO locale_profiles__rebuild_tmp ({insert_list}) '
                    f'SELECT {select_list} FROM locale_profiles WHERE user_id IS NOT NULL'
                )
            conn.execute('DROP TABLE locale_profiles')
            conn.execute('ALTER TABLE locale_profiles__rebuild_tmp RENAME TO locale_profiles')

        if needs_locale_equipment and conn.execute(
            "SELECT 1 FROM sqlite_master WHERE type='table' AND name='locale_equipment'"
        ).fetchone():
            conn.execute('DROP TABLE IF EXISTS locale_equipment__rebuild_tmp')
            conn.execute('''CREATE TABLE locale_equipment__rebuild_tmp (
                user_id INTEGER NOT NULL REFERENCES users(id),
                locale TEXT NOT NULL,
                equipment_id INTEGER NOT NULL REFERENCES equipment_items(id),
                PRIMARY KEY (user_id, locale, equipment_id),
                FOREIGN KEY (user_id, locale) REFERENCES locale_profiles(user_id, locale)
            )''')
            # Backfill user_id by joining to the (now rebuilt) locale_profiles
            # table — every locale value in legacy locale_equipment matches
            # exactly one rebuilt locale_profiles row.
            conn.execute(
                'INSERT OR IGNORE INTO locale_equipment__rebuild_tmp '
                '(user_id, locale, equipment_id) '
                'SELECT lp.user_id, le.locale, le.equipment_id '
                'FROM locale_equipment le '
                'JOIN locale_profiles lp ON lp.locale = le.locale'
            )
            conn.execute('DROP TABLE locale_equipment')
            conn.execute('ALTER TABLE locale_equipment__rebuild_tmp RENAME TO locale_equipment')

        conn.commit()
    finally:
        conn.execute('PRAGMA foreign_keys = ON')


# ── Per-user seed (current_rx) ────────────────────────────────────────────────
#
# Each user gets their own copy of the seeded "Needs initial setup" rows so
# rx_engine has something to UPSERT against on their first logged session.
# The composite UNIQUE(user_id, exercise) lets us seed the same exercise list
# for every user without collisions. routes/auth.py:register calls this for
# the first-user bootstrap so Andy doesn't have to wait for a cold start.

def _seed_current_rx_for_user(executor, user_id, is_postgres=False):
    """INSERT seeded current_rx rows for a single user. Idempotent — relies on
    the composite UNIQUE(user_id, exercise) to skip rows that already exist."""
    if is_postgres:
        executor.executemany(
            '''INSERT INTO current_rx (exercise, discipline, type, movement_pattern,
               inventory_sugg_volume, rx_source, user_id)
               VALUES (%s, %s, %s, %s, %s, 'Needs initial setup', %s)
               ON CONFLICT (user_id, exercise) DO NOTHING''',
            [tuple(e[:5]) + (user_id,) for e in EXERCISES]
        )
    else:
        executor.executemany(
            '''INSERT OR IGNORE INTO current_rx
               (exercise, discipline, type, movement_pattern, inventory_sugg_volume,
                rx_source, user_id)
               VALUES (?, ?, ?, ?, ?, 'Needs initial setup', ?)''',
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


def _seed_purchase_recommendations(executor, tag_to_id, is_postgres=False):
    """Seed the shared purchase_recommendations catalog. Idempotent —
    UPSERT on slug so copy/cost edits propagate to existing rows on every
    cold start, while purchase_id stays stable for any user state already
    referencing it. Caller supplies the equipment_items tag→id map (already
    built upstream during equipment seeding)."""
    if is_postgres:
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
    else:
        sql = (
            'INSERT INTO purchase_recommendations '
            '(slug, label, equipment_id, est_cost_low, est_cost_high, '
            ' priority, rationale, sort_order, active) '
            'VALUES (?,?,?,?,?,?,?,?,1) '
            'ON CONFLICT(slug) DO UPDATE SET '
            '  label=excluded.label, equipment_id=excluded.equipment_id, '
            '  est_cost_low=excluded.est_cost_low, '
            '  est_cost_high=excluded.est_cost_high, '
            '  priority=excluded.priority, rationale=excluded.rationale, '
            '  sort_order=excluded.sort_order, active=1'
        )
    for slug, label, eq_tag, lo, hi, prio, rationale, sort in PURCHASE_RECOMMENDATIONS:
        eq_id = tag_to_id.get(eq_tag)
        executor.execute(sql, (slug, label, eq_id, lo, hi, prio, rationale, sort))


# Migrations for existing databases — add columns that may not exist yet
_SQLITE_MIGRATIONS = [
    "ALTER TABLE cardio_log ADD COLUMN stride_length_m REAL",
    "ALTER TABLE cardio_log ADD COLUMN vert_oscillation_cm REAL",
    "ALTER TABLE cardio_log ADD COLUMN vert_ratio_pct REAL",
    "ALTER TABLE cardio_log ADD COLUMN gct_ms REAL",
    "ALTER TABLE cardio_log ADD COLUMN gct_balance TEXT",
    "ALTER TABLE exercise_inventory ADD COLUMN weight_increment REAL",
    "ALTER TABLE current_rx ADD COLUMN consecutive_failures INTEGER DEFAULT 0",
    "ALTER TABLE current_rx ADD COLUMN weight_increment REAL",
    "ALTER TABLE current_rx ADD COLUMN next_sets INTEGER",
    "ALTER TABLE current_rx ADD COLUMN next_reps INTEGER",
    "ALTER TABLE current_rx ADD COLUMN next_weight REAL",
    "CREATE TABLE IF NOT EXISTS locale_profiles (locale TEXT PRIMARY KEY, equipment TEXT DEFAULT '', notes TEXT DEFAULT '', updated_at TEXT DEFAULT (datetime('now')))",
    "CREATE TABLE IF NOT EXISTS equipment_items (id INTEGER PRIMARY KEY AUTOINCREMENT, tag TEXT NOT NULL UNIQUE, label TEXT NOT NULL, category TEXT NOT NULL)",
    "CREATE TABLE IF NOT EXISTS exercise_equipment (exercise_id INTEGER NOT NULL REFERENCES exercise_inventory(id), equipment_id INTEGER NOT NULL REFERENCES equipment_items(id), option_group INTEGER NOT NULL DEFAULT 1, PRIMARY KEY (exercise_id, equipment_id))",
    "CREATE TABLE IF NOT EXISTS locale_equipment (locale TEXT NOT NULL REFERENCES locale_profiles(locale), equipment_id INTEGER NOT NULL REFERENCES equipment_items(id), PRIMARY KEY (locale, equipment_id))",
    "CREATE TABLE IF NOT EXISTS injury_exercise_modifications (id INTEGER PRIMARY KEY AUTOINCREMENT, injury_id INTEGER NOT NULL REFERENCES injury_log(id), exercise_id INTEGER NOT NULL REFERENCES exercise_inventory(id), substitute_exercise_id INTEGER REFERENCES exercise_inventory(id), modification_type TEXT NOT NULL DEFAULT 'modify', modification_notes TEXT, created_at TEXT DEFAULT (datetime('now')))",
    "ALTER TABLE cardio_log ADD COLUMN plan_item_id INTEGER REFERENCES plan_items(id)",
    "ALTER TABLE training_log ADD COLUMN plan_item_id INTEGER REFERENCES plan_items(id)",
    "ALTER TABLE conditions_log ADD COLUMN cardio_log_id INTEGER REFERENCES cardio_log(id)",
    "ALTER TABLE training_log ADD COLUMN exercise_id INTEGER REFERENCES exercise_inventory(id)",
    "UPDATE training_log SET exercise_id = (SELECT id FROM exercise_inventory WHERE exercise = training_log.exercise)",
    "ALTER TABLE current_rx ADD COLUMN exercise_id INTEGER REFERENCES exercise_inventory(id)",
    "UPDATE current_rx SET exercise_id = (SELECT id FROM exercise_inventory WHERE exercise = current_rx.exercise)",
    "CREATE TABLE IF NOT EXISTS plan_reviews (id INTEGER PRIMARY KEY AUTOINCREMENT, plan_id INTEGER NOT NULL REFERENCES training_plans(id), tier INTEGER NOT NULL, sessions_reviewed INTEGER DEFAULT 0, notes TEXT, created_at TEXT DEFAULT (datetime('now')))",
    "ALTER TABLE cardio_log ADD COLUMN garmin_activity_id TEXT",
    "ALTER TABLE training_log ADD COLUMN garmin_activity_id TEXT",
    "CREATE TABLE IF NOT EXISTS coaching_preferences (id INTEGER PRIMARY KEY AUTOINCREMENT, category TEXT NOT NULL DEFAULT 'general', content TEXT NOT NULL, permanent INTEGER NOT NULL DEFAULT 1, created_at TEXT DEFAULT (datetime('now')))",
    "CREATE TABLE IF NOT EXISTS coaching_chat (id INTEGER PRIMARY KEY AUTOINCREMENT, plan_id INTEGER REFERENCES training_plans(id), role TEXT NOT NULL, content TEXT NOT NULL, actions_json TEXT, created_at TEXT DEFAULT (datetime('now')))",
    "ALTER TABLE plan_items ADD COLUMN calorie_target TEXT",
    "ALTER TABLE plan_items ADD COLUMN macro_carb_pct INTEGER",
    "ALTER TABLE plan_items ADD COLUMN macro_protein_pct INTEGER",
    "ALTER TABLE plan_items ADD COLUMN macro_fat_pct INTEGER",
    "ALTER TABLE plan_items ADD COLUMN session_fueling TEXT",
    "ALTER TABLE locale_profiles ADD COLUMN city TEXT DEFAULT ''",
    "CREATE TABLE IF NOT EXISTS plan_travel (id INTEGER PRIMARY KEY AUTOINCREMENT, plan_id INTEGER NOT NULL REFERENCES training_plans(id), start_date TEXT NOT NULL, end_date TEXT NOT NULL, locale TEXT NOT NULL, city TEXT DEFAULT '', notes TEXT DEFAULT '', created_at TEXT DEFAULT (datetime('now')))",
    "CREATE TABLE IF NOT EXISTS training_sessions (id INTEGER PRIMARY KEY AUTOINCREMENT, date TEXT NOT NULL, notes TEXT, plan_item_id INTEGER REFERENCES plan_items(id), created_at TEXT DEFAULT (datetime('now')))",
    "CREATE TABLE IF NOT EXISTS training_log_sets (id INTEGER PRIMARY KEY AUTOINCREMENT, training_log_id INTEGER NOT NULL REFERENCES training_log(id) ON DELETE CASCADE, set_number INTEGER NOT NULL, reps INTEGER, weight_lbs REAL, duration_sec INTEGER)",
    "ALTER TABLE training_log ADD COLUMN session_id INTEGER REFERENCES training_sessions(id)",
    "CREATE INDEX IF NOT EXISTS idx_tl_session ON training_log(session_id)",
    "CREATE INDEX IF NOT EXISTS idx_tls_log ON training_log_sets(training_log_id)",
    "CREATE INDEX IF NOT EXISTS idx_ts_date ON training_sessions(date)",
    "CREATE TABLE IF NOT EXISTS clothing_options (id INTEGER PRIMARY KEY AUTOINCREMENT, category TEXT NOT NULL, value TEXT NOT NULL, UNIQUE(category, value))",
    "ALTER TABLE plan_travel ADD COLUMN indoor_only INTEGER DEFAULT 0",
    "ALTER TABLE training_plans ADD COLUMN race_goals TEXT DEFAULT ''",
    "CREATE TABLE IF NOT EXISTS wellness_log (id INTEGER PRIMARY KEY AUTOINCREMENT, date TEXT NOT NULL, timestamp_ms INTEGER NOT NULL, heart_rate INTEGER, stress_level INTEGER, body_battery INTEGER, respiration_rate REAL, steps INTEGER, active_calories INTEGER, active_time_s REAL, distance_m REAL, activity_type INTEGER, source TEXT DEFAULT 'wellness_fit', UNIQUE(timestamp_ms))",
    "CREATE INDEX IF NOT EXISTS idx_wl_date ON wellness_log(date)",
    "ALTER TABLE current_rx ADD COLUMN next_duration INTEGER",
    "ALTER TABLE training_log ADD COLUMN next_duration INTEGER",
    "ALTER TABLE current_rx ADD COLUMN sessions_since_progress INTEGER DEFAULT 0",
    "CREATE TABLE IF NOT EXISTS plan_item_disposition (id INTEGER PRIMARY KEY AUTOINCREMENT, plan_item_id INTEGER NOT NULL REFERENCES plan_items(id), log_type TEXT NOT NULL, log_id INTEGER NOT NULL, disposition TEXT NOT NULL, reason TEXT, created_at TEXT DEFAULT (datetime('now')))",
    "CREATE INDEX IF NOT EXISTS idx_pid_plan ON plan_item_disposition(plan_item_id)",
    "CREATE INDEX IF NOT EXISTS idx_pid_log ON plan_item_disposition(log_type, log_id)",
    "CREATE TABLE IF NOT EXISTS feedback_log (id INTEGER PRIMARY KEY AUTOINCREMENT, source TEXT NOT NULL, source_ref_id INTEGER, raw_content TEXT NOT NULL, captured_at TEXT DEFAULT (datetime('now')))",
    "CREATE INDEX IF NOT EXISTS idx_fb_captured ON feedback_log(captured_at)",
    "ALTER TABLE coaching_preferences ADD COLUMN source_feedback_id INTEGER REFERENCES feedback_log(id)",
    "CREATE TABLE IF NOT EXISTS users (id INTEGER PRIMARY KEY AUTOINCREMENT, username TEXT NOT NULL UNIQUE, email TEXT UNIQUE, password_hash TEXT NOT NULL, display_name TEXT, created_at TEXT DEFAULT (datetime('now')), last_login TEXT)",
    # Session 2A — drop dead tables (no live consumers)
    "DROP TABLE IF EXISTS equipment_matrix",
    "DROP TABLE IF EXISTS recommended_purchases",
    # Session 2A — add user_id columns to per-user tables. NULLABLE for now;
    # query scoping ships in Session 2B/C, NOT NULL constraint lands in 2D.
    # Backfill UPDATEs are guarded by EXISTS so they're harmless if user 1
    # hasn't been registered yet (fresh-install or pre-bootstrap upgrade).
    "ALTER TABLE training_sessions ADD COLUMN user_id INTEGER REFERENCES users(id)",
    "ALTER TABLE training_log ADD COLUMN user_id INTEGER REFERENCES users(id)",
    "ALTER TABLE training_log_sets ADD COLUMN user_id INTEGER REFERENCES users(id)",
    "ALTER TABLE current_rx ADD COLUMN user_id INTEGER REFERENCES users(id)",
    "ALTER TABLE cardio_log ADD COLUMN user_id INTEGER REFERENCES users(id)",
    "ALTER TABLE body_metrics ADD COLUMN user_id INTEGER REFERENCES users(id)",
    "ALTER TABLE conditions_log ADD COLUMN user_id INTEGER REFERENCES users(id)",
    "ALTER TABLE injury_log ADD COLUMN user_id INTEGER REFERENCES users(id)",
    "ALTER TABLE training_plans ADD COLUMN user_id INTEGER REFERENCES users(id)",
    "ALTER TABLE plan_items ADD COLUMN user_id INTEGER REFERENCES users(id)",
    "ALTER TABLE plan_item_disposition ADD COLUMN user_id INTEGER REFERENCES users(id)",
    "ALTER TABLE feedback_log ADD COLUMN user_id INTEGER REFERENCES users(id)",
    "ALTER TABLE coaching_preferences ADD COLUMN user_id INTEGER REFERENCES users(id)",
    "ALTER TABLE coaching_chat ADD COLUMN user_id INTEGER REFERENCES users(id)",
    "ALTER TABLE garmin_auth ADD COLUMN user_id INTEGER REFERENCES users(id)",
    "ALTER TABLE garmin_workouts ADD COLUMN user_id INTEGER REFERENCES users(id)",
    "ALTER TABLE locale_profiles ADD COLUMN user_id INTEGER REFERENCES users(id)",
    "ALTER TABLE wellness_log ADD COLUMN user_id INTEGER REFERENCES users(id)",
    # Backfill parent tables — guarded by user-1 existence so the migration is
    # safe to run before the first user has registered.
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
    # Denormalized children — pull from parent (after parent backfill above).
    "UPDATE plan_items SET user_id = (SELECT user_id FROM training_plans WHERE training_plans.id = plan_items.plan_id) WHERE user_id IS NULL",
    "UPDATE plan_item_disposition SET user_id = (SELECT user_id FROM plan_items WHERE plan_items.id = plan_item_disposition.plan_item_id) WHERE user_id IS NULL",
    "UPDATE coaching_chat SET user_id = (SELECT user_id FROM training_plans WHERE training_plans.id = coaching_chat.plan_id) WHERE user_id IS NULL",
    "UPDATE training_log_sets SET user_id = (SELECT user_id FROM training_log WHERE training_log.id = training_log_sets.training_log_id) WHERE user_id IS NULL",
    # Composite indexes for the date-filtered hot queries.
    "CREATE INDEX IF NOT EXISTS idx_tl_user_date ON training_log(user_id, date)",
    "CREATE INDEX IF NOT EXISTS idx_cl_user_date ON cardio_log(user_id, date)",
    "CREATE INDEX IF NOT EXISTS idx_bm_user_date ON body_metrics(user_id, date)",
    "CREATE INDEX IF NOT EXISTS idx_cond_user_date ON conditions_log(user_id, date)",
    "CREATE INDEX IF NOT EXISTS idx_ts_user_date ON training_sessions(user_id, date)",
    "CREATE INDEX IF NOT EXISTS idx_wl_user_date ON wellness_log(user_id, date)",
    "CREATE INDEX IF NOT EXISTS idx_pi_user_date ON plan_items(user_id, item_date)",
    # Session 2D — composite UNIQUE replacements. SQLite can't ALTER a constraint;
    # callable migrations rebuild the table only if the new constraint isn't
    # already present. Each is idempotent.
    _migrate_current_rx_unique,
    _migrate_body_metrics_unique,
    _migrate_wellness_log_unique,
    # Session 3 — clothing_options per-user + locale_profiles composite PK +
    # locale_equipment user-scoping. All three rebuilds happen atomically
    # under a single PRAGMA foreign_keys=OFF window.
    _migrate_session3_locale_clothing,
    # Session 4 — athlete profile.
    """CREATE TABLE IF NOT EXISTS athlete_profile (
        user_id INTEGER PRIMARY KEY REFERENCES users(id),
        date_of_birth TEXT, sex TEXT, height_cm REAL,
        primary_sport TEXT, target_event_name TEXT, target_event_date TEXT,
        weekly_hours_target REAL, training_window TEXT, notes TEXT,
        updated_at TEXT DEFAULT (datetime('now'))
    )""",
    # Session 5 — recommended-purchases rebuild. Shared catalog +
    # per-user state. CREATE IF NOT EXISTS is idempotent on existing DBs;
    # the catalog is then seeded by _seed_purchase_recommendations on every
    # cold start (idempotent via UNIQUE(slug)).
    """CREATE TABLE IF NOT EXISTS purchase_recommendations (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
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
        updated_at TEXT DEFAULT (datetime('now')),
        PRIMARY KEY (user_id, purchase_id)
    )""",
    # Session 6 — password reset tokens. Single-use, time-limited.
    """CREATE TABLE IF NOT EXISTS password_resets (
        token TEXT PRIMARY KEY,
        user_id INTEGER NOT NULL REFERENCES users(id),
        created_at TEXT NOT NULL DEFAULT (datetime('now')),
        expires_at TEXT NOT NULL,
        used_at TEXT
    )""",
    "CREATE INDEX IF NOT EXISTS password_resets_user_id_idx ON password_resets(user_id)",
    # Admin action audit log. Written by routes/admin.py whenever the
    # admin (user_id=1) takes a destructive action, so post-hoc we can
    # answer "who deleted whom, and when?". actor_user_id can be NULL if
    # the actor row was itself deleted later. target_user_id is plain
    # INTEGER (no FK) so the row survives target deletion.
    """CREATE TABLE IF NOT EXISTS admin_audit (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        actor_user_id INTEGER REFERENCES users(id),
        action TEXT NOT NULL,
        target_user_id INTEGER,
        target_username TEXT,
        details TEXT,
        created_at TEXT NOT NULL DEFAULT (datetime('now'))
    )""",
    "CREATE INDEX IF NOT EXISTS admin_audit_created_at_idx ON admin_audit(created_at DESC)",
]

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
    "CREATE TABLE IF NOT EXISTS training_log_sets (id SERIAL PRIMARY KEY, training_log_id INTEGER NOT NULL REFERENCES training_log(id) ON DELETE CASCADE, set_number INTEGER NOT NULL, reps INTEGER, weight_lbs REAL, duration_sec INTEGER)",
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
        primary_sport TEXT, target_event_name TEXT, target_event_date TEXT,
        weekly_hours_target REAL, training_window TEXT, notes TEXT,
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
    ('Outdoor & Terrain', [
        ('trail_running',       'Trail Running (singletrack / dirt)'),
        ('road_running',        'Road Running (pavement)'),
        ('road_cycling',        'Road Cycling'),
        ('mtb_trails',          'Mountain Bike Trails (MTB)'),
        ('gravel_routes',       'Gravel / Mixed-Terrain Cycling'),
        ('open_water_paddle',   'Open Water Paddling (lake / river)'),
        ('open_water_swim',     'Open Water Swimming'),
        ('pool_swim',           'Pool Swimming'),
        ('hills',               'Hills / Significant Elevation Gain'),
    ]),
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
        _seed_current_rx_for_user(cur, 1, is_postgres=True)
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
    _seed_purchase_recommendations(cur, tag_to_id, is_postgres=True)
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
    # Phase 4 — Migrate locale_profiles.equipment → locale_equipment (idempotent).
    # locale_equipment now carries user_id directly (Session 3 composite PK).
    cur.execute('SELECT user_id, locale, equipment FROM locale_profiles')
    for row in cur.fetchall():
        if row[0] is None:
            continue  # Skip pre-bootstrap NULLs (cleaned up by Session 3 rebuild migration).
        for tag in (row[2] or '').split(','):
            tag = tag.strip()
            if tag:
                eq_id = tag_to_id.get(tag)
                if eq_id:
                    cur.execute(
                        'INSERT INTO locale_equipment (user_id, locale, equipment_id) '
                        'VALUES (%s, %s, %s) ON CONFLICT DO NOTHING',
                        (row[0], row[1], eq_id)
                    )
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


def init_sqlite():
    os.makedirs(os.path.dirname(SQLITE_PATH), exist_ok=True)
    conn = sqlite3.connect(SQLITE_PATH)
    conn.executescript(SQLITE_SCHEMA)
    # Run migrations for columns added after initial deploy. Callable migrations
    # (Session 2D rebuilds) receive `conn`; string migrations are executed
    # directly. try/except swallows any single-statement failure so the rest
    # of the batch continues — matches the pre-2D pattern.
    for stmt in _SQLITE_MIGRATIONS:
        try:
            if callable(stmt):
                stmt(conn)
            else:
                conn.execute(stmt)
        except Exception:
            pass
    # Seed current_rx for user 1 only — pre-bootstrap, the table stays empty.
    # Andy's rows are seeded inline by routes/auth.py:register on first-user
    # bootstrap so /rx isn't blank between registration and the next cold start.
    if conn.execute('SELECT 1 FROM users WHERE id = 1').fetchone():
        _seed_current_rx_for_user(conn, 1, is_postgres=False)
    # Seed exercise_inventory
    conn.executemany(
        '''INSERT OR IGNORE INTO exercise_inventory
           (exercise, discipline, type, movement_pattern, suggested_volume, where_available)
           VALUES (?, ?, ?, ?, ?, ?)''',
        EXERCISES
    )
    # Seed exercise equipment tags (always update — safe to re-run)
    for exercise, tags in EXERCISE_EQUIPMENT.items():
        conn.execute(
            'UPDATE exercise_inventory SET equipment=? WHERE exercise=?',
            (tags, exercise)
        )
    # Phase 1 — Seed equipment_items catalog (idempotent)
    for category_name, items in EQUIPMENT_CATEGORIES:
        for tag, label in items:
            conn.execute(
                'INSERT OR IGNORE INTO equipment_items (tag, label, category) VALUES (?, ?, ?)',
                (tag, label, category_name)
            )
    # Phase 2 — Build lookup dicts (index-based access; no row_factory set here)
    tag_to_id = {row[1]: row[0] for row in conn.execute('SELECT id, tag FROM equipment_items').fetchall()}
    ex_to_id  = {row[1]: row[0] for row in conn.execute('SELECT id, exercise FROM exercise_inventory').fetchall()}
    # Phase 2b — Seed shared purchase_recommendations catalog (UPSERT on slug)
    _seed_purchase_recommendations(conn, tag_to_id, is_postgres=False)
    # Phase 3 — Seed exercise_equipment (idempotent)
    for exercise_name, tag_str in EXERCISE_EQUIPMENT.items():
        ex_id = ex_to_id.get(exercise_name)
        if ex_id is None or not tag_str:
            continue
        for group_num, group in enumerate(tag_str.split('|'), start=1):
            for tag in [t.strip() for t in group.split(',') if t.strip()]:
                eq_id = tag_to_id.get(tag)
                if eq_id:
                    conn.execute(
                        'INSERT OR IGNORE INTO exercise_equipment '
                        '(exercise_id, equipment_id, option_group) VALUES (?, ?, ?)',
                        (ex_id, eq_id, group_num)
                    )
    # Phase 4 — Migrate locale_profiles.equipment → locale_equipment (idempotent).
    # locale_equipment now carries user_id directly (Session 3 composite PK).
    for row in conn.execute(
        'SELECT user_id, locale, equipment FROM locale_profiles'
    ).fetchall():
        if row[0] is None:
            continue  # Skip pre-bootstrap NULLs.
        for tag in (row[2] or '').split(','):
            tag = tag.strip()
            if tag:
                eq_id = tag_to_id.get(tag)
                if eq_id:
                    conn.execute(
                        'INSERT OR IGNORE INTO locale_equipment '
                        '(user_id, locale, equipment_id) VALUES (?, ?, ?)',
                        (row[0], row[1], eq_id)
                    )
    # Phase 5 — Backfill exercise_id FKs (runs after seeding so exercise_inventory is populated)
    conn.execute('''UPDATE current_rx SET exercise_id =
        (SELECT id FROM exercise_inventory WHERE exercise = current_rx.exercise)
        WHERE exercise_id IS NULL''')
    conn.execute('''UPDATE training_log SET exercise_id =
        (SELECT id FROM exercise_inventory WHERE exercise = training_log.exercise)
        WHERE exercise_id IS NULL''')
    # clothing_options is now per-user (Session 3) — values accumulate as
    # the user types into the conditions form. No global seed.
    conn.commit()
    conn.close()
    print(f'SQLite database initialized at {SQLITE_PATH}')


if __name__ == '__main__':
    if DATABASE_URL:
        init_postgres()
    else:
        init_sqlite()
