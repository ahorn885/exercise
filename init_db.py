"""Initialize the database — supports both SQLite (local) and Postgres (production)."""
import os
import sqlite3

DATABASE_URL = os.environ.get('DATABASE_URL')
SQLITE_PATH = os.path.join(os.path.dirname(__file__), 'instance', 'training.db')

SQLITE_SCHEMA = '''
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
        date TEXT NOT NULL,
        notes TEXT,
        plan_item_id INTEGER REFERENCES plan_items(id),
        created_at TEXT DEFAULT (datetime('now'))
    );
    CREATE TABLE IF NOT EXISTS training_log (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
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
        training_log_id INTEGER NOT NULL REFERENCES training_log(id) ON DELETE CASCADE,
        set_number INTEGER NOT NULL,
        reps INTEGER,
        weight_lbs REAL,
        duration_sec INTEGER
    );
    CREATE TABLE IF NOT EXISTS current_rx (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        exercise TEXT NOT NULL UNIQUE, exercise_id INTEGER REFERENCES exercise_inventory(id),
        discipline TEXT, type TEXT, movement_pattern TEXT,
        inventory_sugg_volume TEXT, current_sets INTEGER, current_reps INTEGER,
        current_weight REAL, current_duration INTEGER, last_performed TEXT,
        last_outcome TEXT, consecutive_failures INTEGER DEFAULT 0, rx_source TEXT,
        weight_increment REAL,
        next_sets INTEGER, next_reps INTEGER, next_weight REAL
    );
    CREATE TABLE IF NOT EXISTS cardio_log (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
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
        date TEXT NOT NULL UNIQUE, weight_lbs REAL, body_fat_pct REAL,
        vo2_max REAL, resting_hr INTEGER, notes TEXT,
        created_at TEXT DEFAULT (datetime('now'))
    );
    CREATE TABLE IF NOT EXISTS conditions_log (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
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
        start_date TEXT NOT NULL, body_part TEXT NOT NULL, description TEXT,
        severity INTEGER, modifications_needed TEXT, status TEXT DEFAULT 'Active',
        resolved_date TEXT, created_at TEXT DEFAULT (datetime('now'))
    );
    CREATE TABLE IF NOT EXISTS training_modalities (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        activity TEXT NOT NULL UNIQUE, category TEXT, primary_benefits TEXT,
        equipment_needed TEXT, where_available TEXT, ar_carryover TEXT
    );
    CREATE TABLE IF NOT EXISTS equipment_matrix (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        equipment TEXT NOT NULL UNIQUE,
        home TEXT DEFAULT '—', hotel_travel TEXT DEFAULT '—',
        commercial_gym TEXT DEFAULT '—', climbing_gym TEXT DEFAULT '—',
        outdoors TEXT DEFAULT '—', partner_home TEXT DEFAULT '—',
        airport_public TEXT DEFAULT '—'
    );
    CREATE TABLE IF NOT EXISTS training_methods (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        method TEXT NOT NULL, description TEXT, apply_to TEXT, source TEXT
    );
    CREATE TABLE IF NOT EXISTS recommended_purchases (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        item TEXT NOT NULL, est_cost TEXT, what_it_unlocks TEXT,
        exercises_impacted TEXT, priority TEXT
    );
    CREATE TABLE IF NOT EXISTS training_plans (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
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
        source TEXT NOT NULL,
        source_ref_id INTEGER,
        raw_content TEXT NOT NULL,
        captured_at TEXT DEFAULT (datetime('now'))
    );
    CREATE TABLE IF NOT EXISTS coaching_preferences (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        category TEXT NOT NULL DEFAULT 'general',
        content TEXT NOT NULL,
        permanent INTEGER NOT NULL DEFAULT 1,
        source_feedback_id INTEGER REFERENCES feedback_log(id),
        created_at TEXT DEFAULT (datetime('now'))
    );
    CREATE TABLE IF NOT EXISTS coaching_chat (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        plan_id INTEGER REFERENCES training_plans(id),
        role TEXT NOT NULL,
        content TEXT NOT NULL,
        actions_json TEXT,
        created_at TEXT DEFAULT (datetime('now'))
    );
    CREATE TABLE IF NOT EXISTS garmin_auth (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        garmin_username TEXT,
        garth_session TEXT,
        created_at TEXT DEFAULT (datetime('now')),
        updated_at TEXT DEFAULT (datetime('now'))
    );
    CREATE TABLE IF NOT EXISTS garmin_workouts (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        plan_item_id INTEGER REFERENCES plan_items(id),
        garmin_workout_id TEXT NOT NULL,
        workout_name TEXT,
        sport_type TEXT,
        scheduled_date TEXT,
        status TEXT DEFAULT 'active',
        created_at TEXT DEFAULT (datetime('now'))
    );
    CREATE TABLE IF NOT EXISTS locale_profiles (
        locale TEXT PRIMARY KEY,
        equipment TEXT DEFAULT '',
        notes TEXT DEFAULT '',
        city TEXT DEFAULT '',
        updated_at TEXT DEFAULT (datetime('now'))
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
        locale       TEXT NOT NULL REFERENCES locale_profiles(locale),
        equipment_id INTEGER NOT NULL REFERENCES equipment_items(id),
        PRIMARY KEY (locale, equipment_id)
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
        category TEXT NOT NULL,
        value    TEXT NOT NULL,
        UNIQUE(category, value)
    );
    CREATE TABLE IF NOT EXISTS wellness_log (
        id             INTEGER PRIMARY KEY AUTOINCREMENT,
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
        UNIQUE(timestamp_ms)
    );
    CREATE INDEX IF NOT EXISTS idx_wl_date ON wellness_log(date);
'''

PG_SCHEMA = '''
    CREATE TABLE IF NOT EXISTS exercise_inventory (
        id SERIAL PRIMARY KEY,
        exercise TEXT NOT NULL UNIQUE,
        type TEXT, discipline TEXT, equipment TEXT, muscles_worked TEXT,
        skills_ar_carryover TEXT, where_available TEXT, source TEXT,
        suggested_volume TEXT, substitution_group TEXT, recovery_cost TEXT,
        movement_pattern TEXT, session_placement TEXT, form_cue TEXT, video_reference TEXT,
        weight_increment REAL
    );
    CREATE TABLE IF NOT EXISTS training_sessions (
        id SERIAL PRIMARY KEY,
        date TEXT NOT NULL,
        notes TEXT,
        plan_item_id INTEGER REFERENCES plan_items(id),
        created_at TIMESTAMP DEFAULT NOW()
    );
    CREATE TABLE IF NOT EXISTS training_log (
        id SERIAL PRIMARY KEY,
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
        training_log_id INTEGER NOT NULL REFERENCES training_log(id) ON DELETE CASCADE,
        set_number INTEGER NOT NULL,
        reps INTEGER,
        weight_lbs REAL,
        duration_sec INTEGER
    );
    CREATE TABLE IF NOT EXISTS current_rx (
        id SERIAL PRIMARY KEY,
        exercise TEXT NOT NULL UNIQUE, exercise_id INTEGER REFERENCES exercise_inventory(id),
        discipline TEXT, type TEXT, movement_pattern TEXT,
        inventory_sugg_volume TEXT, current_sets INTEGER, current_reps INTEGER,
        current_weight REAL, current_duration INTEGER, last_performed TEXT,
        last_outcome TEXT, consecutive_failures INTEGER DEFAULT 0, rx_source TEXT,
        weight_increment REAL,
        next_sets INTEGER, next_reps INTEGER, next_weight REAL
    );
    CREATE TABLE IF NOT EXISTS cardio_log (
        id SERIAL PRIMARY KEY,
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
        date TEXT NOT NULL UNIQUE, weight_lbs REAL, body_fat_pct REAL,
        vo2_max REAL, resting_hr INTEGER, notes TEXT,
        created_at TIMESTAMP DEFAULT NOW()
    );
    CREATE TABLE IF NOT EXISTS conditions_log (
        id SERIAL PRIMARY KEY,
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
        start_date TEXT NOT NULL, body_part TEXT NOT NULL, description TEXT,
        severity INTEGER, modifications_needed TEXT, status TEXT DEFAULT 'Active',
        resolved_date TEXT, created_at TIMESTAMP DEFAULT NOW()
    );
    CREATE TABLE IF NOT EXISTS training_modalities (
        id SERIAL PRIMARY KEY,
        activity TEXT NOT NULL UNIQUE, category TEXT, primary_benefits TEXT,
        equipment_needed TEXT, where_available TEXT, ar_carryover TEXT
    );
    CREATE TABLE IF NOT EXISTS equipment_matrix (
        id SERIAL PRIMARY KEY,
        equipment TEXT NOT NULL UNIQUE,
        home TEXT DEFAULT '—', hotel_travel TEXT DEFAULT '—',
        commercial_gym TEXT DEFAULT '—', climbing_gym TEXT DEFAULT '—',
        outdoors TEXT DEFAULT '—', partner_home TEXT DEFAULT '—',
        airport_public TEXT DEFAULT '—'
    );
    CREATE TABLE IF NOT EXISTS training_methods (
        id SERIAL PRIMARY KEY,
        method TEXT NOT NULL, description TEXT, apply_to TEXT, source TEXT
    );
    CREATE TABLE IF NOT EXISTS recommended_purchases (
        id SERIAL PRIMARY KEY,
        item TEXT NOT NULL, est_cost TEXT, what_it_unlocks TEXT,
        exercises_impacted TEXT, priority TEXT
    );
    CREATE TABLE IF NOT EXISTS training_plans (
        id SERIAL PRIMARY KEY,
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
        source TEXT NOT NULL,
        source_ref_id INTEGER,
        raw_content TEXT NOT NULL,
        captured_at TIMESTAMP DEFAULT NOW()
    );
    CREATE TABLE IF NOT EXISTS coaching_preferences (
        id SERIAL PRIMARY KEY,
        category TEXT NOT NULL DEFAULT 'general',
        content TEXT NOT NULL,
        permanent INTEGER NOT NULL DEFAULT 1,
        source_feedback_id INTEGER REFERENCES feedback_log(id),
        created_at TIMESTAMP DEFAULT NOW()
    );
    CREATE TABLE IF NOT EXISTS coaching_chat (
        id SERIAL PRIMARY KEY,
        plan_id INTEGER REFERENCES training_plans(id),
        role TEXT NOT NULL,
        content TEXT NOT NULL,
        actions_json TEXT,
        created_at TIMESTAMP DEFAULT NOW()
    );
    CREATE TABLE IF NOT EXISTS garmin_auth (
        id SERIAL PRIMARY KEY,
        garmin_username TEXT,
        garth_session TEXT,
        created_at TIMESTAMP DEFAULT NOW(),
        updated_at TIMESTAMP DEFAULT NOW()
    );
    CREATE TABLE IF NOT EXISTS garmin_workouts (
        id SERIAL PRIMARY KEY,
        plan_item_id INTEGER REFERENCES plan_items(id),
        garmin_workout_id TEXT NOT NULL,
        workout_name TEXT,
        sport_type TEXT,
        scheduled_date TEXT,
        status TEXT DEFAULT 'active',
        created_at TIMESTAMP DEFAULT NOW()
    );
    CREATE TABLE IF NOT EXISTS locale_profiles (
        locale TEXT PRIMARY KEY,
        equipment TEXT DEFAULT '',
        notes TEXT DEFAULT '',
        city TEXT DEFAULT '',
        updated_at TIMESTAMP DEFAULT NOW()
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
        locale       TEXT NOT NULL REFERENCES locale_profiles(locale),
        equipment_id INTEGER NOT NULL REFERENCES equipment_items(id),
        PRIMARY KEY (locale, equipment_id)
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
        category TEXT NOT NULL,
        value    TEXT NOT NULL,
        UNIQUE(category, value)
    );
    CREATE TABLE IF NOT EXISTS wellness_log (
        id             SERIAL PRIMARY KEY,
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
        UNIQUE(timestamp_ms)
    );
    CREATE INDEX IF NOT EXISTS idx_wl_date ON wellness_log(date);
'''

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
    # Run migrations for columns added after initial deploy
    for stmt in _PG_MIGRATIONS:
        try:
            cur.execute(stmt)
        except Exception:
            conn.rollback()
    # Seed current_rx (5 columns — slice away where_available)
    cur.executemany(
        '''INSERT INTO current_rx (exercise, discipline, type, movement_pattern,
           inventory_sugg_volume, rx_source)
           VALUES (%s, %s, %s, %s, %s, 'Needs initial setup')
           ON CONFLICT (exercise) DO NOTHING''',
        [e[:5] for e in EXERCISES]
    )
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
    # Phase 4 — Migrate locale_profiles.equipment → locale_equipment (idempotent)
    cur.execute('SELECT locale, equipment FROM locale_profiles')
    for row in cur.fetchall():
        for tag in (row[1] or '').split(','):
            tag = tag.strip()
            if tag:
                eq_id = tag_to_id.get(tag)
                if eq_id:
                    cur.execute(
                        'INSERT INTO locale_equipment (locale, equipment_id) VALUES (%s, %s) '
                        'ON CONFLICT DO NOTHING',
                        (row[0], eq_id)
                    )
    # Phase 5 — Backfill exercise_id FKs (runs after seeding so exercise_inventory is populated)
    cur.execute('''UPDATE current_rx SET exercise_id = ei.id
        FROM exercise_inventory ei WHERE ei.exercise = current_rx.exercise
        AND current_rx.exercise_id IS NULL''')
    cur.execute('''UPDATE training_log SET exercise_id = ei.id
        FROM exercise_inventory ei WHERE ei.exercise = training_log.exercise
        AND training_log.exercise_id IS NULL''')
    # Seed clothing_options
    for category, value in _CLOTHING_SEEDS:
        cur.execute(
            'INSERT INTO clothing_options (category, value) VALUES (%s, %s) ON CONFLICT DO NOTHING',
            (category, value)
        )
    conn.commit()
    cur.close()
    conn.close()
    print('Postgres database initialized.')


def init_sqlite():
    os.makedirs(os.path.dirname(SQLITE_PATH), exist_ok=True)
    conn = sqlite3.connect(SQLITE_PATH)
    conn.executescript(SQLITE_SCHEMA)
    # Run migrations for columns added after initial deploy
    for stmt in _SQLITE_MIGRATIONS:
        try:
            conn.execute(stmt)
        except Exception:
            pass
    # Seed current_rx (5 columns — slice away where_available)
    conn.executemany(
        '''INSERT OR IGNORE INTO current_rx
           (exercise, discipline, type, movement_pattern, inventory_sugg_volume, rx_source)
           VALUES (?, ?, ?, ?, ?, 'Needs initial setup')''',
        [e[:5] for e in EXERCISES]
    )
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
    # Phase 4 — Migrate locale_profiles.equipment → locale_equipment (idempotent)
    for row in conn.execute('SELECT locale, equipment FROM locale_profiles').fetchall():
        for tag in (row[1] or '').split(','):
            tag = tag.strip()
            if tag:
                eq_id = tag_to_id.get(tag)
                if eq_id:
                    conn.execute(
                        'INSERT OR IGNORE INTO locale_equipment (locale, equipment_id) VALUES (?, ?)',
                        (row[0], eq_id)
                    )
    # Phase 5 — Backfill exercise_id FKs (runs after seeding so exercise_inventory is populated)
    conn.execute('''UPDATE current_rx SET exercise_id =
        (SELECT id FROM exercise_inventory WHERE exercise = current_rx.exercise)
        WHERE exercise_id IS NULL''')
    conn.execute('''UPDATE training_log SET exercise_id =
        (SELECT id FROM exercise_inventory WHERE exercise = training_log.exercise)
        WHERE exercise_id IS NULL''')
    # Seed clothing_options
    conn.executemany(
        'INSERT OR IGNORE INTO clothing_options (category, value) VALUES (?, ?)',
        _CLOTHING_SEEDS
    )
    conn.commit()
    conn.close()
    print(f'SQLite database initialized at {SQLITE_PATH}')


if __name__ == '__main__':
    if DATABASE_URL:
        init_postgres()
    else:
        init_sqlite()
