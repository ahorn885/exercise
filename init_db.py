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
    CREATE TABLE IF NOT EXISTS training_log (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        date TEXT NOT NULL, exercise TEXT NOT NULL,
        sub_group TEXT, recovery_cost TEXT,
        target_sets INTEGER, target_reps INTEGER, target_weight REAL, target_duration INTEGER,
        actual_sets INTEGER, actual_reps INTEGER, actual_weight REAL, actual_duration INTEGER,
        rpe REAL, rest_sec INTEGER, outcome TEXT, est_1rm REAL, volume REAL,
        body_weight REAL, next_weight REAL, next_sets INTEGER, next_reps INTEGER,
        progression_level TEXT, notes TEXT,
        created_at TEXT DEFAULT (datetime('now'))
    );
    CREATE TABLE IF NOT EXISTS current_rx (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        exercise TEXT NOT NULL UNIQUE, discipline TEXT, type TEXT, movement_pattern TEXT,
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
    CREATE INDEX IF NOT EXISTS idx_tl_date ON training_log(date);
    CREATE INDEX IF NOT EXISTS idx_tl_exercise ON training_log(exercise);
    CREATE INDEX IF NOT EXISTS idx_cl_date ON cardio_log(date);
    CREATE INDEX IF NOT EXISTS idx_bm_date ON body_metrics(date);
    CREATE INDEX IF NOT EXISTS idx_pi_plan ON plan_items(plan_id);
    CREATE INDEX IF NOT EXISTS idx_pi_date ON plan_items(item_date);
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
    CREATE TABLE IF NOT EXISTS training_log (
        id SERIAL PRIMARY KEY,
        date TEXT NOT NULL, exercise TEXT NOT NULL,
        sub_group TEXT, recovery_cost TEXT,
        target_sets INTEGER, target_reps INTEGER, target_weight REAL, target_duration INTEGER,
        actual_sets INTEGER, actual_reps INTEGER, actual_weight REAL, actual_duration INTEGER,
        rpe REAL, rest_sec INTEGER, outcome TEXT, est_1rm REAL, volume REAL,
        body_weight REAL, next_weight REAL, next_sets INTEGER, next_reps INTEGER,
        progression_level TEXT, notes TEXT,
        created_at TIMESTAMP DEFAULT NOW()
    );
    CREATE TABLE IF NOT EXISTS current_rx (
        id SERIAL PRIMARY KEY,
        exercise TEXT NOT NULL UNIQUE, discipline TEXT, type TEXT, movement_pattern TEXT,
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
    CREATE INDEX IF NOT EXISTS idx_tl_date ON training_log(date);
    CREATE INDEX IF NOT EXISTS idx_tl_exercise ON training_log(exercise);
    CREATE INDEX IF NOT EXISTS idx_cl_date ON cardio_log(date);
    CREATE INDEX IF NOT EXISTS idx_bm_date ON body_metrics(date);
    CREATE INDEX IF NOT EXISTS idx_pi_plan ON plan_items(plan_id);
    CREATE INDEX IF NOT EXISTS idx_pi_date ON plan_items(item_date);
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
    conn.commit()
    conn.close()
    print(f'SQLite database initialized at {SQLITE_PATH}')


if __name__ == '__main__':
    if DATABASE_URL:
        init_postgres()
    else:
        init_sqlite()
