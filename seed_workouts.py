#!/usr/bin/env python3
"""Seed historical workout data (training log + cardio log) into the database.

Usage:
    set DATABASE_URL=postgresql://...   (Windows CMD, use ^& to escape &)
    python seed_workouts.py
"""
import os
import psycopg2

DATABASE_URL = os.environ.get('DATABASE_URL')
if not DATABASE_URL:
    raise SystemExit("ERROR: Set DATABASE_URL environment variable first.")

conn = psycopg2.connect(DATABASE_URL)
cur = conn.cursor()

# ---------------------------------------------------------------------------
# TRAINING LOG
# Columns: date, exercise, actual_sets, actual_reps, actual_weight (lbs),
#          actual_duration (seconds), rpe, notes
# ---------------------------------------------------------------------------
TRAINING = [
    # ── Pre-plan baseline: Sat Mar 7, 2026 ─────────────────────────────────
    ('2026-03-07', 'KB Halo',                        2,  50, 25.0, None, None, 'Each direction. Pre-plan baseline.'),
    ('2026-03-07', 'KB Side Swing',                  1,  50, 25.0, None, None, 'Per side.'),
    ('2026-03-07', 'KB High Pull',                   4,  25, 25.0, None, None, None),
    ('2026-03-07', 'Kettlebell Swing (Two-Hand)',     2,  50, 25.0, None, None, None),
    ('2026-03-07', 'KB Tricep Overhead Extension',   7,  15, 25.0, None, None, None),
    ('2026-03-07', 'KB Row',                         2,  50, 25.0, None, None, None),
    ('2026-03-07', 'KB Cross-Body Curl',             4,  15, 25.0, None, None, '2-handed, per side.'),
    ('2026-03-07', 'KB Overhead Press',              3,  15, 25.0, None, None, None),

    # ── Pre-plan baseline: Sun Mar 8, 2026 ─────────────────────────────────
    ('2026-03-08', 'KB High Full-Body Pull',         4,  15, 25.0, None, None, None),
    ('2026-03-08', 'KB Side Swing',                  4,  15, 30.0, None, None, 'Per side.'),
    ('2026-03-08', 'KB 1-Handed High Pull',          4,  15, 10.0, None, None, 'Per side.'),
    ('2026-03-08', 'Kettlebell Swing (Two-Hand)',     4,  15, 30.0, None, None, None),
    ('2026-03-08', 'KB Tricep Overhead Extension',   4,  10, 10.0, None, None, '1-handed, per side.'),
    ('2026-03-08', 'KB Row',                         4,  15, 30.0, None, None, '1-handed.'),
    ('2026-03-08', 'KB Cross-Body Curl',             4,  12, 30.0, None, None, 'Per side.'),
    ('2026-03-08', 'KB Overhead Press',              4,  15, 15.0, None, None, '1-handed, per side.'),

    # ── Pre-plan baseline: Wed Mar 11, 2026 ────────────────────────────────
    ('2026-03-11', 'DB Press',                       4,  15, 30.0, None, None, None),
    ('2026-03-11', 'Deep Lunge',                     4,   5, 25.0, None, None, 'Per side.'),
    ('2026-03-11', 'DB Overhead Press',              4,   8, 25.0, None, None, '1-handed, per side.'),

    # ── Sat Apr 4 — AM Strength (Partner Home) ─────────────────────────────
    ('2026-04-04', 'Wide-Grip Pull-Up',              3,   6, None, None,  8.0, None),
    ('2026-04-04', 'Dead Hang',                      3, None, None,  40,  5.0, None),
    ('2026-04-04', 'Banded Row',                     3,  15, None, None,  3.0, None),
    ('2026-04-04', 'Pike Push-Up',                   3,  12, None, None,  9.0, None),
    ('2026-04-04', 'Fist Push-Up',                   3,  15, None, None,  8.0, None),
    ('2026-04-04', 'Dip',                            3,  12, None, None,  7.0, None),
    ('2026-04-04', 'Hollow Hold',                    3, None, None,  30,  7.0, None),
    ('2026-04-04', 'Hanging Knee Raise',             3,  15, None, None,  5.0, None),
    ('2026-04-04', 'Bicycle Crunch',                 3,  20, None, None,  7.0, None),
    ('2026-04-04', 'Bird Dog',                       3,  10, None, None,  4.0, None),

    # ── Wed Apr 8 — Core B: Paddle Core (Hotel Nashville) ──────────────────
    ('2026-04-08', 'Russian Twist (Feet Elevated)',  3,  20, 12.0, None, None, '12 lb med ball (14 lb unavailable).'),
    ('2026-04-08', 'Pallof Press',                   3,  15, 15.0, None, None, 'Cable, per side.'),
    ('2026-04-08', 'Cable Woodchop (High-to-Low)',   3,  12, 15.0, None, None, 'Per side.'),
    ('2026-04-08', 'Hanging Knee Raise',             3,  15, None, None, None, 'Smith machine bar.'),
    ('2026-04-08', 'Bicycle Crunch',                 3,  25, None, None, None, None),
    ('2026-04-08', 'V-Sit Hold',                     3, None, None,  30, None, None),

    # ── Wed Apr 8 — Paddle Sim Strength (Tue makeup) ───────────────────────
    ('2026-04-08', 'Pull-Up',                        4,   7, None, None, None,
     'Smith machine assisted. Significant form breakdown. '
     'Sets 1-2: breaks after reps 4,5,6. Set 3: breaks at 2,3,5. Set 4: breaks at 3,5. Long rests.'),
    ('2026-04-08', 'Lat Pulldown',                   3,   8, 120.0, None, None,
     'Vertical traction machine. Too heavy — got 6, 8, 10 reps. Planned 3×12.'),
    ('2026-04-08', 'Single-Arm DB Row (Staggered)',  4,  10, 50.0, None, None,
     'Reps: 6, 8, 12, 12. Planned 4×12.'),
    ('2026-04-08', 'Seated Cable Row',               3,  15, 73.0, None, None,
     'Ramped: 15×50, 15×80, 15×90 lb. Weight = avg.'),
    ('2026-04-08', 'Dead Hang',                      4, None, None,  24, None,
     'Grip fatigued. Times: 35s, 20s, 24s, 18s. Planned 4×35s.'),
    ('2026-04-08', 'Face Pull',                      3,  20, 20.0, None, None,
     'Ramped: 20×15, 20×20, 20×25 lb. Weight = avg.'),

    # ── Sun Apr 12 — Bodyweight Lower Circuit (Home) ───────────────────────
    ('2026-04-12', 'Air Squat',                      2,  20, None, None, None, 'Bodyweight.'),
    ('2026-04-12', 'Walking Lunge',                  2,  10, None, None, None, 'Per leg, bodyweight.'),
    ('2026-04-12', 'Single-Leg Deadlift',            2,   8, None, None, None, 'Per leg, bodyweight.'),
    ('2026-04-12', 'Glute Bridge / Hip Thrust',      2,  15, None, None, None, 'Bodyweight.'),
    ('2026-04-12', 'Lateral Lunge',                  2,   8, None, None, None, 'Per side, bodyweight.'),
    ('2026-04-12', 'Single-Leg Calf Raise',          2,  15, None, None, None, 'Per leg, bodyweight.'),
]

# ---------------------------------------------------------------------------
# CARDIO LOG
# Columns: date, activity, activity_name, duration_min, distance_mi,
#          avg_speed (mph), avg_hr, avg_pace (text), avg_power (watts), notes
# ---------------------------------------------------------------------------
CARDIO = [
    # date, activity, activity_name, duration_min, distance_mi, avg_speed, avg_hr, avg_pace, avg_power, notes
    ('2026-04-04', 'Road Cycling', 'PM Road Bike',
     96.0, 22.5, 14.0, 119, None, None,
     'Gravel bike on road. Partner home.'),

    ('2026-04-06', 'Treadmill', 'Easy Run — Hotel Nashville',
     40.5, None, None, 151, '11:32', None,
     'HR elevated for easy effort — possible travel, hotel heat, dehydration.'),

    ('2026-04-06', 'Mobility', 'Mobility Session',
     15.0, None, None, None, None, None,
     'Abbreviated from planned 25 min.'),

    ('2026-04-07', 'Cycling (Indoor)', 'Peloton Bike — Nashville',
     75.0, 30.0, None, None, None, None,
     'Peloton distance inflated vs outdoor — do not compare directly.'),

    ('2026-04-08', 'Treadmill', 'Treadmill Run + Incline Walk',
     65.0, None, None, None, None, None,
     '50 min @ 5.5 mph, then 15 min @ 15% incline / 2.5 mph. Demo floor 4 hrs before session.'),

    ('2026-04-11', 'Cycling (Indoor)', 'Cycling Trainer',
     45.0, None, None, None, None, None,
     'Shortened from planned 75 min. Kids weekend.'),

    ('2026-04-12', 'Kayak Erg', 'Kayak Ergometer',
     30.0, None, None, None, None, None,
     None),

    ('2026-04-12', 'Cycling (Indoor)', 'Cycling Trainer',
     75.0, 19.87, 15.9, None, None, 115,
     None),
]

# ---------------------------------------------------------------------------
# Insert training log
# ---------------------------------------------------------------------------
training_sql = """
    INSERT INTO training_log
        (date, exercise, actual_sets, actual_reps, actual_weight,
         actual_duration, rpe, notes)
    VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
"""
cur.executemany(training_sql, TRAINING)
print(f"Inserted {len(TRAINING)} training log entries.")

# ---------------------------------------------------------------------------
# Insert cardio log
# ---------------------------------------------------------------------------
cardio_sql = """
    INSERT INTO cardio_log
        (date, activity, activity_name, duration_min, distance_mi,
         avg_speed, avg_hr, avg_pace, avg_power, notes)
    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
"""
cur.executemany(cardio_sql, CARDIO)
print(f"Inserted {len(CARDIO)} cardio log entries.")

conn.commit()
cur.close()
conn.close()
print("Done!")
