"""Initialize the PostgreSQL database — schema + idempotent migrations + seeds."""
import os

from athlete import BIKE_TYPES, PADDLE_CRAFT_TYPES
from provider_value_map_seed import STRENGTH_NAME_TO_EX_ID, provider_value_map_rows

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
        exercise TEXT NOT NULL,
        movement_pattern TEXT,
        current_sets INTEGER, current_reps INTEGER,
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
    CREATE TABLE IF NOT EXISTS provider_value_map (
        provider           TEXT NOT NULL,
        data_type          TEXT NOT NULL,
        direction          TEXT NOT NULL,
        source_value       TEXT NOT NULL,
        canonical_kind     TEXT NOT NULL,
        canonical_value    TEXT,
        match_kind         TEXT NOT NULL,
        confidence         REAL NOT NULL DEFAULT 1.0,
        no_canonical_match BOOLEAN NOT NULL DEFAULT FALSE,
        notes              TEXT,
        PRIMARY KEY (provider, data_type, direction, source_value)
    );
    -- Generic raw-passthrough store (record-don't-drop, all buckets). Created in
    -- Slice 1. First writers (bucket-3 raw + the indoor-machine flag) land in
    -- Slice 2 per ProviderTranslation_StorageSchema_681_BuildDesign §3.3/§7.
    CREATE TABLE IF NOT EXISTS provider_raw_record (
        id            SERIAL PRIMARY KEY,
        user_id       INTEGER REFERENCES users(id),
        provider      TEXT NOT NULL,
        data_type     TEXT NOT NULL,
        external_id   TEXT,
        observed_at   TIMESTAMP,
        raw_payload   JSONB,
        bucket        SMALLINT,
        canonical_ref TEXT,
        fetched_at    TIMESTAMP DEFAULT NOW(),
        UNIQUE (user_id, provider, data_type, external_id)
    );
    -- #681 Wave 3b outbound: idempotent push ledger (translation spec §4.4 /
    -- StorageSchema design §3.3). First writer = the TrainingPeaks push
    -- (Slice 2), where pushed_payload_hash drives upsert-on-change vs no-op.
    -- Zwift is a file download with no external id, so it does not write here.
    CREATE TABLE IF NOT EXISTS provider_outbound_ref (
        id                  SERIAL PRIMARY KEY,
        user_id             INTEGER REFERENCES users(id),
        provider            TEXT NOT NULL,
        session_id          TEXT,
        external_id         TEXT,
        tier                SMALLINT,
        pushed_payload_hash TEXT,
        status              TEXT,
        created_at          TIMESTAMP DEFAULT NOW(),
        updated_at          TIMESTAMP DEFAULT NOW(),
        UNIQUE (user_id, provider, session_id)
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
    CREATE TABLE IF NOT EXISTS equipment_items (
        id       SERIAL PRIMARY KEY,
        tag      TEXT NOT NULL UNIQUE,
        label    TEXT NOT NULL,
        category TEXT NOT NULL
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
        exercise_ex_id         TEXT NOT NULL,
        substitute_ex_id       TEXT,
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
# Each user gets their own copy so rx_engine has something to UPSERT against on
# their first logged session, and so /rx isn't blank before they've logged.
# Catalog unification (Slice C): the exercise list is sourced from the single
# canonical layer0 strength catalog (the retired v1 EXERCISES seed is gone), the
# same EX-id keyed catalog the /rx page, plan-gen, and rx_engine already read.


def _layer0_strength_seed_rows(executor):
    """`(exercise_name, movement_pattern, ex_id)` tuples for the current_rx
    bootstrap, read from the active layer0 strength catalog.

    Reuses the same strength-type filter + progression-pattern collapse as
    `layer0_catalog.strength_catalog` so the seed list matches what /rx renders.
    Works for both seed callers: a raw psycopg2 cursor (init_postgres — `execute`
    returns None + yields tuples) and the app's db wrapper (routes/auth.py —
    `execute` returns a RealDict cursor). Raises if the layer0 schema is
    absent/empty — callers treat the seed as best-effort."""
    from layer0_catalog import _is_strength_type
    from layer0_progression import progression_pattern
    res = executor.execute(
        "SELECT exercise_id, exercise_name, exercise_type, movement_patterns "
        "FROM layer0.exercises WHERE superseded_at IS NULL ORDER BY exercise_name"
    )
    fetched = res.fetchall() if res is not None else executor.fetchall()
    rows = []
    for r in fetched:
        if isinstance(r, (tuple, list)):
            ex_id, name, exercise_type, patterns = r
        else:  # RealDict row from the app db wrapper
            ex_id, name = r['exercise_id'], r['exercise_name']
            exercise_type, patterns = r['exercise_type'], r['movement_patterns']
        if not _is_strength_type(exercise_type):
            continue
        rows.append((name, progression_pattern(list(patterns or [])), ex_id))
    return rows


def _seed_current_rx_for_user(executor, user_id, seed_rows):
    """INSERT seeded "Needs initial setup" current_rx rows for a single user from
    `seed_rows` (the layer0 strength catalog). Idempotent and de-duping: the
    `NOT EXISTS` guard skips any layer0 exercise the user already has by EX-id
    (so an existing user whose rows still carry v1 short names is not given a
    second, layer0-named copy of the same lift), and `ON CONFLICT (user_id,
    exercise)` guards the name key. A brand-new user (empty current_rx) gets the
    full catalog."""
    executor.executemany(
        '''INSERT INTO current_rx
               (exercise, movement_pattern, layer0_exercise_id, rx_source, user_id)
           SELECT %s, %s, %s, 'Needs initial setup', %s
           WHERE NOT EXISTS (
               SELECT 1 FROM current_rx c
               WHERE c.user_id = %s AND c.layer0_exercise_id = %s)
           ON CONFLICT (user_id, exercise) DO NOTHING''',
        [(name, mp, ex_id, user_id, user_id, ex_id)
         for (name, mp, ex_id) in seed_rows]
    )


# ── Recommended purchases — shared catalog ───────────────────────────────────
#
# Each entry binds to an equipment_items.tag (so "exercises impacted" can be
# derived live from the layer0 catalog via equipment_tag_layer0) and carries
# cost ranges + priority + a short rationale tailored to the AR / endurance profile.
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

    # Step 3 — drop the 9 equipment_items rows themselves. (The retired
    # exercise_equipment join that once referenced these tags is gone — the
    # catalog is layer0 now — so there is no FK to violate.)
    cur.execute("""
        DELETE FROM equipment_items
        WHERE tag = ANY(%s)
    """, (retired_tags,))


# #884 slice 3 — craft-slug allowlists for the athlete_gear backfill (in the
# migration tail below). Only known craft slugs migrate from the discipline-
# baseline CSVs into the unified gear store, so a stale/pruned slug (e.g. the
# legacy 'surfski', athlete.py §D.4) can't leak in as an unknown gear_id. Source:
# the closed craft enums = the bike/paddle half of the §5.5 gear_id keyspace
# (athlete_gear_repo.GEAR_REGISTRY).
_GEAR_BACKFILL_BIKE_IN = ", ".join(f"'{s}'" for s in BIKE_TYPES)
_GEAR_BACKFILL_PADDLE_IN = ", ".join(f"'{s}'" for s in PADDLE_CRAFT_TYPES)

_PG_MIGRATIONS = [
    "ALTER TABLE cardio_log ADD COLUMN IF NOT EXISTS stride_length_m REAL",
    "ALTER TABLE cardio_log ADD COLUMN IF NOT EXISTS vert_oscillation_cm REAL",
    "ALTER TABLE cardio_log ADD COLUMN IF NOT EXISTS vert_ratio_pct REAL",
    "ALTER TABLE cardio_log ADD COLUMN IF NOT EXISTS gct_ms REAL",
    "ALTER TABLE cardio_log ADD COLUMN IF NOT EXISTS gct_balance TEXT",
    "ALTER TABLE current_rx ADD COLUMN IF NOT EXISTS consecutive_failures INTEGER DEFAULT 0",
    "ALTER TABLE current_rx ADD COLUMN IF NOT EXISTS weight_increment REAL",
    "ALTER TABLE current_rx ADD COLUMN IF NOT EXISTS next_sets INTEGER",
    "ALTER TABLE current_rx ADD COLUMN IF NOT EXISTS next_reps INTEGER",
    "ALTER TABLE current_rx ADD COLUMN IF NOT EXISTS next_weight REAL",
    "CREATE TABLE IF NOT EXISTS locale_profiles (locale TEXT PRIMARY KEY, equipment TEXT DEFAULT '', notes TEXT DEFAULT '', updated_at TIMESTAMP DEFAULT NOW())",
    "CREATE TABLE IF NOT EXISTS equipment_items (id SERIAL PRIMARY KEY, tag TEXT NOT NULL UNIQUE, label TEXT NOT NULL, category TEXT NOT NULL)",
    "CREATE TABLE IF NOT EXISTS locale_equipment (locale TEXT NOT NULL REFERENCES locale_profiles(locale), equipment_id INTEGER NOT NULL REFERENCES equipment_items(id), PRIMARY KEY (locale, equipment_id))",
    "CREATE TABLE IF NOT EXISTS injury_exercise_modifications (id SERIAL PRIMARY KEY, injury_id INTEGER NOT NULL REFERENCES injury_log(id), exercise_ex_id TEXT NOT NULL, substitute_ex_id TEXT, modification_type TEXT NOT NULL DEFAULT 'modify', modification_notes TEXT, created_at TIMESTAMP DEFAULT NOW())",
    "ALTER TABLE cardio_log ADD COLUMN IF NOT EXISTS plan_item_id INTEGER REFERENCES plan_items(id)",
    "ALTER TABLE training_log ADD COLUMN IF NOT EXISTS plan_item_id INTEGER REFERENCES plan_items(id)",
    "ALTER TABLE conditions_log ADD COLUMN IF NOT EXISTS cardio_log_id INTEGER REFERENCES cardio_log(id)",
    # #430 Slice C (C3) — drop the public exercise_inventory.id FK from the
    # per-user rx tables. The columns are vestigial after C2 (no reads, no
    # writes; the rx path keys off layer0_exercise_id). DROP cascades the FK
    # constraint. Idempotent via IF EXISTS.
    "ALTER TABLE training_log DROP COLUMN IF EXISTS exercise_id",
    "ALTER TABLE current_rx DROP COLUMN IF EXISTS exercise_id",
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
    "CREATE TABLE IF NOT EXISTS training_sessions (id SERIAL PRIMARY KEY, date TEXT NOT NULL, notes TEXT, plan_item_id INTEGER REFERENCES plan_items(id), created_at TIMESTAMP DEFAULT NOW())",
    "CREATE TABLE IF NOT EXISTS training_log_sets (id SERIAL PRIMARY KEY, training_log_id INTEGER NOT NULL REFERENCES training_log(id) ON DELETE CASCADE, set_number INTEGER NOT NULL, reps INTEGER, weight_kg REAL, duration_sec INTEGER)",
    "ALTER TABLE training_log ADD COLUMN IF NOT EXISTS session_id INTEGER REFERENCES training_sessions(id)",
    "CREATE INDEX IF NOT EXISTS idx_tl_session ON training_log(session_id)",
    "CREATE INDEX IF NOT EXISTS idx_tls_log ON training_log_sets(training_log_id)",
    "CREATE INDEX IF NOT EXISTS idx_ts_date ON training_sessions(date)",
    "CREATE TABLE IF NOT EXISTS clothing_options (id SERIAL PRIMARY KEY, category TEXT NOT NULL, value TEXT NOT NULL, UNIQUE(category, value))",
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
    # #251 — email verification tokens. Single-use, time-limited. `email` is
    # captured at issue time so a token can't verify a *different* address the
    # athlete later switched to (consume checks it still matches users.email).
    """CREATE TABLE IF NOT EXISTS email_verifications (
        token TEXT PRIMARY KEY,
        user_id INTEGER NOT NULL REFERENCES users(id),
        email TEXT NOT NULL,
        created_at TIMESTAMP NOT NULL DEFAULT NOW(),
        expires_at TIMESTAMP NOT NULL,
        used_at TIMESTAMP
    )""",
    "CREATE INDEX IF NOT EXISTS email_verifications_user_id_idx ON email_verifications(user_id)",
    # #274 — admin invite tokens. An admin issues an invite to an email; the
    # link lets that address register even when ALLOW_REGISTRATION is off, and
    # registering through it marks the email verified (the token was delivered
    # to that inbox and presented back — same proof as the verify link).
    # Single-use, time-limited; accepted_user_id ties it to the created account.
    """CREATE TABLE IF NOT EXISTS user_invites (
        token TEXT PRIMARY KEY,
        email TEXT NOT NULL,
        created_by INTEGER NOT NULL REFERENCES users(id),
        created_at TIMESTAMP NOT NULL DEFAULT NOW(),
        expires_at TIMESTAMP NOT NULL,
        accepted_at TIMESTAMP,
        accepted_user_id INTEGER REFERENCES users(id)
    )""",
    "CREATE INDEX IF NOT EXISTS user_invites_pending_idx ON user_invites(created_at DESC) WHERE accepted_at IS NULL",
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
    # TOTP two-factor auth (#265). One row per user, scoped by PK. The row's
    # presence + `confirmed_at` encode the enrollment state machine (see
    # `mfa.py`): absent = off, confirmed_at NULL = enrollment pending,
    # confirmed_at set = active. `secret` is the base32 TOTP seed. Stored
    # plaintext like the api_tokens hash design note: this is a friends-only
    # install and the secret is only as sensitive as the DB it lives in (a DB
    # compromise already exposes password hashes); a future hardening pass can
    # wrap it with the `cryptography` Fernet key already in requirements.
    """CREATE TABLE IF NOT EXISTS user_totp (
        user_id INTEGER PRIMARY KEY REFERENCES users(id),
        secret TEXT NOT NULL,
        created_at TIMESTAMP NOT NULL DEFAULT NOW(),
        confirmed_at TIMESTAMP
    )""",
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
    # Slice 3 (#681 §4): provider-neutral rename — this table now holds
    # device-derived daily wellness for ANY provider (Garmin populates it today;
    # Polar/COROS land their raw daily wellness in provider_raw_record, promoted
    # here in a later multi-source wave). Idempotent: rename only when the legacy
    # table exists and the new name doesn't; carry the explicit index name across
    # too so we don't leave a duplicate. A fresh DB skips this and the CREATE
    # below builds the table under its new name directly.
    """DO $$
    BEGIN
      IF to_regclass('public.garmin_daily_metrics') IS NOT NULL
         AND to_regclass('public.daily_wellness_metrics') IS NULL THEN
        ALTER TABLE garmin_daily_metrics RENAME TO daily_wellness_metrics;
        ALTER INDEX IF EXISTS garmin_daily_metrics_user_date_idx
              RENAME TO daily_wellness_metrics_user_date_idx;
      END IF;
    END $$""",
    """CREATE TABLE IF NOT EXISTS daily_wellness_metrics (
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
        sleep_stress_above_resting_pct INTEGER,
        sleep_onset_latency_sec INTEGER,
        sleep_stage_raw_min_json TEXT,
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
    "CREATE INDEX IF NOT EXISTS daily_wellness_metrics_user_date_idx ON daily_wellness_metrics(user_id, date)",
    # Backfill columns for environments where daily_wellness_metrics was created
    # by an earlier migration (#460 / #463). IF NOT EXISTS keeps these
    # idempotent across re-runs.
    "ALTER TABLE daily_wellness_metrics ADD COLUMN IF NOT EXISTS resting_metabolic_rate INTEGER",
    "ALTER TABLE daily_wellness_metrics ADD COLUMN IF NOT EXISTS resting_hr INTEGER",
    "ALTER TABLE daily_wellness_metrics ADD COLUMN IF NOT EXISTS resting_hr_7day_avg INTEGER",
    "ALTER TABLE daily_wellness_metrics ADD COLUMN IF NOT EXISTS sleep_duration_sub_score INTEGER",
    "ALTER TABLE daily_wellness_metrics ADD COLUMN IF NOT EXISTS hrv_highest_5min_ms REAL",
    "ALTER TABLE daily_wellness_metrics ADD COLUMN IF NOT EXISTS heat_acclimation_pct INTEGER",
    "ALTER TABLE daily_wellness_metrics ADD COLUMN IF NOT EXISTS acute_training_load INTEGER",
    "ALTER TABLE daily_wellness_metrics ADD COLUMN IF NOT EXISTS restless_moments INTEGER",
    "ALTER TABLE daily_wellness_metrics ADD COLUMN IF NOT EXISTS floors_climbed INTEGER",
    "ALTER TABLE daily_wellness_metrics ADD COLUMN IF NOT EXISTS floors_descended INTEGER",
    "ALTER TABLE daily_wellness_metrics ADD COLUMN IF NOT EXISTS intensity_minutes INTEGER",
    # PR #489 — new mappings decoded from May 28 + May 30 reference data:
    # sleep_deep_min via [346] field_9 (already in the table create above
    # but Phase B environments may pre-date it), sleep_stress_avg derived
    # from [346] field_15 ÷ sample_count, sleep_wake_count from [382] field_2.
    "ALTER TABLE daily_wellness_metrics ADD COLUMN IF NOT EXISTS sleep_stress_avg REAL",
    "ALTER TABLE daily_wellness_metrics ADD COLUMN IF NOT EXISTS sleep_wake_count INTEGER",
    # `[346]` sub-score contributors (#283) — all 4 positions locked Jun 10
    # 2026 against 6 reference nights (Sep 8 2025 was the disambiguator).
    # field_5 = Light, field_7 = REM, field_8 = Stress, field_10 = Awake.
    "ALTER TABLE daily_wellness_metrics ADD COLUMN IF NOT EXISTS sleep_light_sub_score INTEGER",
    "ALTER TABLE daily_wellness_metrics ADD COLUMN IF NOT EXISTS sleep_rem_sub_score INTEGER",
    "ALTER TABLE daily_wellness_metrics ADD COLUMN IF NOT EXISTS sleep_stress_sub_score INTEGER",
    "ALTER TABLE daily_wellness_metrics ADD COLUMN IF NOT EXISTS sleep_awake_sub_score INTEGER",
    # `[384] field_18` best-guess = % of overnight stress samples above
    # Garmin's "resting" threshold (>25 on the 0-100 scale). Fits 6
    # reference nights within rounding. Not Connect-visible directly.
    "ALTER TABLE daily_wellness_metrics ADD COLUMN IF NOT EXISTS sleep_stress_above_resting_pct INTEGER",
    # `[384] field_3` = sleep_onset_latency_sec — Connect's "Time to fall
    # asleep" (#524). Absent on perfect-onset nights (Garmin omits zero).
    "ALTER TABLE daily_wellness_metrics ADD COLUMN IF NOT EXISTS sleep_onset_latency_sec INTEGER",
    # Raw `[275]` per-stage minute tally as JSON `{code: minutes}` (#524) —
    # 1=Unmeasurable, 2=Light, 3=Deep, 4=REM. Feeds the raw-vs-smoothed
    # "stage smoothing" chart: smoothed (Connect) minus this raw tally.
    "ALTER TABLE daily_wellness_metrics ADD COLUMN IF NOT EXISTS sleep_stage_raw_min_json TEXT",
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
        error TEXT,
        dead_lettered_at TIMESTAMP
    )""",
    "CREATE INDEX IF NOT EXISTS idx_webhook_events_lookup ON webhook_events (provider, provider_user_id, entity_id, event_type)",
    "CREATE INDEX IF NOT EXISTS idx_webhook_events_pending ON webhook_events (received_at) WHERE processed_at IS NULL",
    # #250: dead-letter column for failed deliveries that aged past their retry
    # window. ALTER keeps existing deployments in sync (CREATE only fires on a
    # fresh DB). The partial index backs the dead-letter path / prune sweep
    # (routes/webhook_maintenance.py).
    "ALTER TABLE webhook_events ADD COLUMN IF NOT EXISTS dead_lettered_at TIMESTAMP",
    "CREATE INDEX IF NOT EXISTS idx_webhook_events_dead_letter ON webhook_events (received_at) WHERE dead_lettered_at IS NOT NULL",
    # Slice 3 (#681 §4): the per-provider Polar wellness tables are retired.
    # Polar sleep / nightly-recharge / cardio-load now record into the canonical
    # provider_raw_record (record-don't-drop, provider-tagged), and continuous HR
    # into wellness_log. Empty in prod (zero-row gate verified 2026-06-19), so
    # the drops are clean. DROP IF EXISTS keeps this idempotent across deploys.
    "DROP TABLE IF EXISTS polar_sleep",
    "DROP TABLE IF EXISTS polar_nightly_recharge",
    "DROP TABLE IF EXISTS polar_cardio_load",
    "DROP TABLE IF EXISTS polar_continuous_hr_samples",
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
    # Slice 3 (#681 §4): COROS daily-summary now records into provider_raw_record
    # and per-sample HR into wellness_log; the per-provider tables are retired
    # (empty in prod — zero-row gate verified 2026-06-19). coros_plans below is
    # the plan-PUSH table and is unaffected.
    "DROP TABLE IF EXISTS coros_daily_summary",
    "DROP TABLE IF EXISTS coros_hrv_samples",
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
    # Strava manual-archive upload dedup/source tag (#757 follow-up — manual
    # multi-service upload). Bulk export carries original device files; tagged
    # `strava-file:<hash>` so Layer-3A reads source='strava'.
    "ALTER TABLE cardio_log ADD COLUMN IF NOT EXISTS strava_activity_id TEXT",
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
    # #971 Slice 2 — crowd-sourced gym/hotel photos. Each photo attaches to a
    # shared gym_profiles row (so every inheritor sees it, matching the
    # equipment-sharing model), uploaded by one athlete, stored in Vercel Blob
    # (`blob_url` = the public URL, `blob_pathname` = the store key for delete).
    # `status` gates peer visibility: a photo is `pending` until an admin
    # approves it (the same review step #971 Slice 3 added for equipment
    # corrections); the uploader sees their own pending photos, peers don't.
    # Rejected photos are deleted outright (row + blob), so only 'pending' /
    # 'approved' ever persist. ON DELETE CASCADE: photos vanish with the profile.
    """CREATE TABLE IF NOT EXISTS gym_profile_photos (
        id SERIAL PRIMARY KEY,
        gym_profile_id INTEGER NOT NULL REFERENCES gym_profiles(id) ON DELETE CASCADE,
        uploaded_by_user_id INTEGER REFERENCES users(id),
        blob_url TEXT NOT NULL,
        blob_pathname TEXT,
        content_type TEXT,
        status TEXT NOT NULL DEFAULT 'pending' CHECK (status IN ('pending', 'approved')),
        created_at TIMESTAMP DEFAULT NOW(),
        reviewed_by_user_id INTEGER REFERENCES users(id),
        reviewed_at TIMESTAMP
    )""",
    "CREATE INDEX IF NOT EXISTS gym_profile_photos_profile_idx ON gym_profile_photos (gym_profile_id, status)",
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
    # #681 (B) — Strava live ingest dedup. The #765 groundwork added the
    # strava_activity_id column; this is the idempotency guard the live webhook
    # ingest needs (mirrors the coros/polar/wahoo partial-unique pattern).
    "CREATE UNIQUE INDEX IF NOT EXISTS cardio_log_strava_activity_uidx ON cardio_log (user_id, strava_activity_id) WHERE strava_activity_id IS NOT NULL",
    # #681 (B) — RWGPS live ingest dedup (the rwgps_trip_id column already exists).
    "CREATE UNIQUE INDEX IF NOT EXISTS cardio_log_rwgps_trip_uidx ON cardio_log (user_id, rwgps_trip_id) WHERE rwgps_trip_id IS NOT NULL",
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
    # #826 — science-provenance backbone. These tables reference `plan_versions`
    # (created just above), so they live here in the migration list rather than
    # `PG_SCHEMA` (which runs before the migration list). `evidence_sources` is
    # the canonical, referenceable store of the external, credible research /
    # training-science a plan decision rests on — the prose that used to live as
    # free text in `training_methods.source` / `training_modalities`. Constrained
    # to three credible kinds (study | guideline | expert_coach): there is
    # deliberately no generic "internal/heuristic" kind — a decision that can't
    # cite one of these is a curation gap (`evidence_curation_flags`), not a 4th
    # kind. `is_baseline` marks the house-methodology sources every plan rests on
    # (the per-`plan_version` "whys" for v1); `status` + `superseded_by_id` give a
    # clean supersede/version model the #451 "your plan may change" delta job can
    # diff against.
    """CREATE TABLE IF NOT EXISTS evidence_sources (
        id SERIAL PRIMARY KEY,
        slug TEXT NOT NULL UNIQUE,
        kind TEXT NOT NULL CHECK (kind IN ('study', 'guideline', 'expert_coach')),
        title TEXT NOT NULL,
        summary TEXT,
        citation TEXT,
        url TEXT,
        status TEXT NOT NULL DEFAULT 'active' CHECK (status IN ('active', 'superseded')),
        superseded_by_id INTEGER REFERENCES evidence_sources(id),
        is_baseline BOOLEAN NOT NULL DEFAULT FALSE,
        as_of DATE,
        created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
    )""",
    "CREATE INDEX IF NOT EXISTS evidence_sources_baseline_idx ON evidence_sources (is_baseline, status)",
    # Link curated `training_methods` rows to a canonical source (forward-looking:
    # the table is unseeded today, so this migrates the free-text `source` model
    # toward the referenceable store as rows land).
    "ALTER TABLE training_methods ADD COLUMN IF NOT EXISTS evidence_source_id INTEGER REFERENCES evidence_sources(id)",
    # The persisted provenance link. Per-`plan_version` grain for v1 (one set of
    # "whys" per plan as a whole); the per-phase/session locator column is the
    # documented follow-up. Race-week briefs + race-day plans are always tied to a
    # `plan_version`, so they reuse these links (single table, no brief-scoped
    # variant). Superseding/adding an `evidence_sources` row joins straight back
    # here to find affected plans (the #451 backbone).
    """CREATE TABLE IF NOT EXISTS plan_version_evidence (
        plan_version_id BIGINT NOT NULL REFERENCES plan_versions(id) ON DELETE CASCADE,
        evidence_source_id INTEGER NOT NULL REFERENCES evidence_sources(id),
        created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
        PRIMARY KEY (plan_version_id, evidence_source_id)
    )""",
    "CREATE INDEX IF NOT EXISTS plan_version_evidence_source_idx ON plan_version_evidence (evidence_source_id)",
    # Curation-gap intake. When a decision wants to cite research but no matching
    # `evidence_sources` row exists, we flag it here (the decision still stands,
    # unattributed) rather than dropping it silently or hard-failing the plan. An
    # operator triages open flags in the admin view and either creates the missing
    # source (resolve) or dismisses the gap.
    """CREATE TABLE IF NOT EXISTS evidence_curation_flags (
        id SERIAL PRIMARY KEY,
        plan_version_id BIGINT REFERENCES plan_versions(id) ON DELETE CASCADE,
        raised_by_layer TEXT,
        context_text TEXT NOT NULL,
        cited_token TEXT,
        occurrences INTEGER NOT NULL DEFAULT 1,
        status TEXT NOT NULL DEFAULT 'open' CHECK (status IN ('open', 'resolved', 'dismissed')),
        resolved_by_evidence_source_id INTEGER REFERENCES evidence_sources(id),
        created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
        resolved_at TIMESTAMPTZ
    )""",
    "CREATE INDEX IF NOT EXISTS evidence_curation_flags_status_idx ON evidence_curation_flags (status, created_at DESC)",
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
    # numeric kg (the structured complement to the free-text race notes).
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
    # #257 — v3 onboarding refinement (Section I audit). All self-report bands,
    # nullable, no backfill. `sweat_rate_level` splits the v2 salt/electrolyte
    # conflation (V3-I-4): salt drives sodium, sweat-rate drives fluid in 2E.
    "ALTER TABLE athlete_profile ADD COLUMN IF NOT EXISTS sweat_rate_level TEXT",
    "ALTER TABLE athlete_profile ADD COLUMN IF NOT EXISTS daily_hydration_baseline TEXT",
    "ALTER TABLE athlete_profile ADD COLUMN IF NOT EXISTS sleep_consistency TEXT",
    "ALTER TABLE athlete_profile ADD COLUMN IF NOT EXISTS body_weight_trend TEXT",
    # 2E-6 §I.1 — structured supplement capture. Promotes the free-text
    # `athlete_profile.supplement_protocol_notes` to per-supplement records that
    # soft-reference `layer0.supplement_vocabulary.supplement_id` (no hard FK —
    # the vocab lives in a different schema and is ETL-owned). `canonical_name` +
    # `category` are denormalized so the profile + Layer 1 read without a
    # cross-schema join. The Layer 2E supplement_integration de-stub (the
    # recommendation + contraindication engine) consumes these next.
    """CREATE TABLE IF NOT EXISTS athlete_supplements (
        id SERIAL PRIMARY KEY,
        user_id INTEGER NOT NULL REFERENCES users(id),
        supplement_id TEXT NOT NULL,
        canonical_name TEXT NOT NULL,
        category TEXT,
        dose TEXT,
        frequency TEXT,
        timing TEXT,
        notes TEXT,
        created_at TIMESTAMP NOT NULL DEFAULT NOW()
    )""",
    "CREATE INDEX IF NOT EXISTS athlete_supplements_user_id_idx ON athlete_supplements(user_id)",
    # 2E-6 §I.1 — frequency/timing moved from free text to closed vocabs
    # (athlete_supplements_repo.SUPPLEMENT_FREQUENCIES/TIMINGS). frequency is a
    # new structured axis; add it idempotently for DBs that already created the
    # table from this PR's first commit (the CREATE above only fires on fresh).
    "ALTER TABLE athlete_supplements ADD COLUMN IF NOT EXISTS frequency TEXT",
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
        session_index_in_day SMALLINT NOT NULL CHECK (session_index_in_day IN (0, 1, 2)),
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
    # Layer 5A nutrition synthesis — deterministic per-day + plan-level nutrition
    # computed AFTER a plan reaches `ready` (zero-LLM advisory tier; see
    # `layer5/`). One row per plan_version holds the whole `PlanNutrition`
    # bundle (top-level baseline + per-day targets + race-day fueling) as JSONB.
    # UNIQUE (plan_version_id) makes the write an idempotent upsert so a
    # regenerate overwrites in place. `energy_model` is denormalized so a future
    # model-version bump can find + recompute stale artifacts. ON DELETE CASCADE
    # mirrors plan_sessions: the artifact is meaningless without its plan.
    # WRITE-ONLY / advisory — never an input to any Layer 4 cache key.
    """CREATE TABLE IF NOT EXISTS plan_nutrition (
        id BIGSERIAL PRIMARY KEY,
        plan_version_id BIGINT NOT NULL REFERENCES plan_versions(id) ON DELETE CASCADE,
        user_id INTEGER NOT NULL REFERENCES users(id),
        energy_model TEXT NOT NULL,
        payload_json JSONB NOT NULL,
        generated_at TIMESTAMPTZ NOT NULL,
        created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
        updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
        UNIQUE (plan_version_id)
    )""",
    "CREATE INDEX IF NOT EXISTS plan_nutrition_user_version_idx ON plan_nutrition (user_id, plan_version_id)",
    # Layer 5A nutrition INPUTS snapshot — the slice of the Layer 2E payload (+
    # body weight + event dates) that the deterministic nutrition stage consumes,
    # captured at plan-generation time. `orchestrate_plan_create` computes the
    # 2E payload inside its upstream cone and discards it; stashing it here (best-
    # effort, riding the generation transaction) lets the post-`ready` stage AND
    # the manual regenerate action rebuild nutrition without re-running the cone,
    # and pins the inputs to exactly what the plan was built on (no drift).
    # One row per plan_version; UNIQUE for idempotent overwrite. ON DELETE CASCADE.
    """CREATE TABLE IF NOT EXISTS plan_nutrition_inputs (
        id BIGSERIAL PRIMARY KEY,
        plan_version_id BIGINT NOT NULL REFERENCES plan_versions(id) ON DELETE CASCADE,
        user_id INTEGER NOT NULL REFERENCES users(id),
        payload_json JSONB NOT NULL,
        created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
        updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
        UNIQUE (plan_version_id)
    )""",
    "CREATE INDEX IF NOT EXISTS plan_nutrition_inputs_user_version_idx ON plan_nutrition_inputs (user_id, plan_version_id)",
    # Layer 5B conditions synthesis — deterministic per-day clothing/conditions
    # advisory computed AFTER a plan reaches `ready` (zero-LLM advisory tier; see
    # `layer5/conditions_*`). One row per plan_version holds the whole
    # `PlanConditions` bundle (per-day thermal band + clothing/kit + flags,
    # derived from climate normals at each session's locale) as JSONB.
    # UNIQUE (plan_version_id) makes the write an idempotent upsert so a
    # regenerate overwrites in place. `model` is denormalized so a future
    # model-version bump can find + recompute stale artifacts. ON DELETE CASCADE
    # mirrors plan_nutrition: the artifact is meaningless without its plan.
    # WRITE-ONLY / advisory — never an input to any Layer 4 cache key.
    """CREATE TABLE IF NOT EXISTS plan_conditions (
        id BIGSERIAL PRIMARY KEY,
        plan_version_id BIGINT NOT NULL REFERENCES plan_versions(id) ON DELETE CASCADE,
        user_id INTEGER NOT NULL REFERENCES users(id),
        model TEXT NOT NULL,
        payload_json JSONB NOT NULL,
        generated_at TIMESTAMPTZ NOT NULL,
        created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
        updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
        UNIQUE (plan_version_id)
    )""",
    "CREATE INDEX IF NOT EXISTS plan_conditions_user_version_idx ON plan_conditions (user_id, plan_version_id)",
    # #732 slice 2 — race_week_briefs. Storage home for the structured Layer 4
    # race-week-brief output (the `RaceWeekBrief` + optional multi-day `RacePlan`
    # from a `Layer4Payload`). The Taper-session OVERRIDES are mutated back into
    # `plan_sessions` in place (per-day pointer + ON CONFLICT upsert under the
    # athlete's active plan version, #732 slice 2 ratified decision); this table
    # is the home for the brief/race_plan payloads that have no equivalent in
    # plan_sessions. One row per plan_version; UNIQUE (plan_version_id) makes a
    # re-fired brief an idempotent overwrite in place, matching the in-place
    # mutation model. event_date + race_format are denormalized for queryability
    # (e.g. "show the brief for the upcoming race"). ON DELETE CASCADE mirrors
    # plan_nutrition: the brief is meaningless without its plan version.
    """CREATE TABLE IF NOT EXISTS race_week_briefs (
        id BIGSERIAL PRIMARY KEY,
        plan_version_id BIGINT NOT NULL REFERENCES plan_versions(id) ON DELETE CASCADE,
        user_id INTEGER NOT NULL REFERENCES users(id),
        event_date DATE NOT NULL,
        race_format TEXT NOT NULL,
        brief_json JSONB NOT NULL,
        race_plan_json JSONB,
        generated_at TIMESTAMPTZ NOT NULL,
        created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
        updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
        UNIQUE (plan_version_id)
    )""",
    "CREATE INDEX IF NOT EXISTS race_week_briefs_user_version_idx ON race_week_briefs (user_id, plan_version_id)",
    # #732 slice 4 — race_week_brief_log. One row per race-week-brief generation
    # ATTEMPT (success or failure), mirroring plan_refresh_log (D-64 §7.1). The
    # race_week_briefs table only holds successful artifacts; this log is the
    # observability surface — it records failures (which never reach
    # race_week_briefs, since a failed attempt doesn't commit the brief) with
    # their failure_reason, plus the per-attempt cost telemetry the orchestrator
    # returns on the Layer4Payload (duration_ms / input+output tokens /
    # llm_call_count). plan_version_id is nullable: a success row stamps the
    # active version the brief attached to; a failure row stamps the originating
    # plan view's version when known, else NULL.
    """CREATE TABLE IF NOT EXISTS race_week_brief_log (
        id BIGSERIAL PRIMARY KEY,
        user_id INTEGER NOT NULL REFERENCES users(id),
        triggered_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
        plan_version_id BIGINT REFERENCES plan_versions(id),
        days_to_event INTEGER,
        duration_ms INTEGER,
        input_tokens INTEGER,
        output_tokens INTEGER,
        llm_call_count INTEGER,
        success BOOLEAN NOT NULL,
        failure_reason TEXT,
        created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
    )""",
    "CREATE INDEX IF NOT EXISTS race_week_brief_log_user_triggered_idx ON race_week_brief_log (user_id, triggered_at DESC)",
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
    # #1056 — snapshot the athlete-facing plan name at creation so adding a new
    # target race later doesn't rename existing plans (reads fall back to the
    # derived name when NULL, e.g. rows created before this column).
    "ALTER TABLE plan_versions ADD COLUMN IF NOT EXISTS display_name TEXT",
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
    # User-facing lifecycle: a manual "archive" stamp, set when the athlete
    # shelves a plan they did NOT finish — they quit it, or a refresh
    # superseded it — but want it kept for reference. Independent of
    # `completed_at` (which implies the plan was completed): an archived plan
    # drops off the active Plan list into its Archived section, no completion
    # implied. The list buckets a non-NULL `archived_at` row into Archived
    # ahead of the scope-date buckets.
    "ALTER TABLE plan_versions ADD COLUMN IF NOT EXISTS archived_at TIMESTAMPTZ",
    # #208 — async/resumable plan-refresh. A refresh row is allocated
    # `generating` and driven by the same cron/poller as plan-create, so the
    # background pass must re-derive the refresh inputs from the row (the
    # original request is long gone). `created_via` already encodes the tier
    # (`plan_refresh_t{1,2,3}`); these carry the rest: the athlete's typed note
    # (re-parsed each pass), the parent plan version, the D-63 ad-hoc
    # attribution, and whether the frequency cap was overridden — everything
    # `_write_refresh_log` needs at completion.
    "ALTER TABLE plan_versions ADD COLUMN IF NOT EXISTS refresh_nl_text TEXT",
    "ALTER TABLE plan_versions ADD COLUMN IF NOT EXISTS refresh_parent_version_id BIGINT REFERENCES plan_versions(id)",
    "ALTER TABLE plan_versions ADD COLUMN IF NOT EXISTS refresh_triggered_by_ad_hoc_id BIGINT",
    "ALTER TABLE plan_versions ADD COLUMN IF NOT EXISTS refresh_cap_overridden BOOLEAN NOT NULL DEFAULT FALSE",
    # The NL parse is done ONCE at request time and frozen here, NOT re-run per
    # background pass: a non-deterministic re-parse would drift parsed_intent →
    # drift the plan_refresh cache key → non-convergence (the #202 class of bug).
    "ALTER TABLE plan_versions ADD COLUMN IF NOT EXISTS refresh_parsed_intent_json TEXT",
    "ALTER TABLE plan_versions ADD COLUMN IF NOT EXISTS refresh_used_degraded BOOLEAN NOT NULL DEFAULT FALSE",
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
    # #698 recovery-slot DB alignment (plan #75 persist failure, 2026-06-19). #698
    # made recovery sessions ADDITIVE — a day may carry ≤2 training (cardio/
    # strength) PLUS ≤1 recovery, so `session_index_in_day` legitimately reaches 2
    # (the 3rd slot). The model (payload.py `Field(ge=0, le=2)`), the prompt schema
    # (per_phase.py `maximum: 2`) and the day invariant (`_check_two_per_day`) were
    # all widened, but this DB CHECK stayed `IN (0,1)` — so any plan whose
    # deterministic recovery placement used the 3rd slot passed every in-memory
    # gate then died at INSERT with a CheckViolation, discarding the WHOLE plan
    # (all blocks). Realign the deployed constraint with the shipped contract.
    # Drop-then-add is idempotent; (0,1,2) is a superset so existing rows satisfy
    # it. (single_session / plan_refresh keep index ≤1 — they emit no recovery.)
    """DO $$
    BEGIN
        ALTER TABLE plan_sessions DROP CONSTRAINT IF EXISTS plan_sessions_session_index_in_day_check;
        ALTER TABLE plan_sessions ADD CONSTRAINT plan_sessions_session_index_in_day_check
            CHECK (session_index_in_day IN (0, 1, 2));
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
    # #582 — purge the auto-created legacy enum slot rows (home/hotel/partner/
    # airport) the retired LOCALES force-render left behind in locale_profiles.
    # Now that the list is driven purely off real rows, these bare slots are the
    # reason the legacy locations still render in prod — the code retirement
    # removed the force-render but nothing cleaned up the rows the old
    # auto-create-on-save seeded. Scope is deliberately tight so genuine athlete
    # data survives untouched: only a categoryless slot with no geocoding
    # (mapbox_id/lat), no linked gym, that is NOT the preferred home, has no
    # manual-entry address, no athlete-set name/notes/terrain, and no
    # equipment/toggle overrides is removed. Dependent override rows cascade;
    # event-window references (event_locale_id) SET NULL. Idempotent.
    """
    DELETE FROM locale_profiles lp
     WHERE lp.locale IN ('home', 'hotel', 'partner', 'airport')
       AND lp.category IS NULL
       AND lp.mapbox_id IS NULL
       AND lp.lat IS NULL
       AND lp.gym_profile_id IS NULL
       AND lp.place_payload IS NULL
       AND COALESCE(lp.manual_entry, FALSE) = FALSE
       AND COALESCE(lp.preferred, FALSE) = FALSE
       AND COALESCE(lp.locale_name, '') = ''
       AND COALESCE(lp.notes, '') = ''
       AND COALESCE(array_length(lp.locale_terrain_ids, 1), 0) = 0
       AND NOT EXISTS (SELECT 1 FROM locale_equipment_overrides o
                        WHERE o.user_id = lp.user_id AND o.locale = lp.locale)
       AND NOT EXISTS (SELECT 1 FROM locale_toggle_overrides t
                        WHERE t.user_id = lp.user_id AND t.locale = lp.locale)
    """,
    # #941 — retire the free-text `city` column. Weather / clothing resolution
    # moved off the typed city onto the Mapbox-anchored `lat`/`lng` already
    # captured on every geocoded locale (away event-window destination wins,
    # else preferred home). The typed city was the source of the wrong-location
    # bug: travel locales left it blank and the away window silently fell
    # through to home weather. Manual-entry addresses now ride in `place_payload`
    # (Mapbox-feature shape) so the list/form still render them.
    #
    # Backfill first (idempotent, runs before the DROP): a manual-entry row's
    # only address was its typed `city`; lift it into `place_payload` so the
    # address still renders after the column is gone. Guarded on the column
    # existing so a cold start that never had `city` skips it cleanly.
    """DO $$
    BEGIN
        IF EXISTS (
            SELECT 1 FROM information_schema.columns
            WHERE table_name = 'locale_profiles' AND column_name = 'city'
        ) THEN
            UPDATE locale_profiles
               SET place_payload = json_build_object(
                       'properties', json_build_object('full_address', city)
                   )::text
             WHERE manual_entry = TRUE
               AND COALESCE(city, '') <> ''
               AND (place_payload IS NULL OR place_payload = '');
        END IF;
    END $$;""",
    "ALTER TABLE locale_profiles DROP COLUMN IF EXISTS city",
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
    # Slice 2b.2b — athlete-facing session-grid unit fields. Nullable; NULL =
    # "unset", so the Layer 4 session grid falls back to its spec defaults
    # (two_a_day_preference -> 'occasionally', peak_sessions_max -> 10). The
    # enum/range are enforced at the app layer (onboarding + routes/profile.py),
    # matching the sibling text columns (sex, doubles_feasible) that carry no
    # DB CHECK.
    "ALTER TABLE athlete_profile ADD COLUMN IF NOT EXISTS two_a_day_preference TEXT",
    "ALTER TABLE athlete_profile ADD COLUMN IF NOT EXISTS peak_sessions_max INTEGER",
    # Event Windows Slice 1 (#581 WS-H) — athlete-declared date-bounded windows
    # where the training environment differs from the default home cluster.
    # Slice 1 = two SUBTRACTIVE override types: 'indoor_only' (home cluster minus
    # outdoor terrain) and 'locale_unavailable' (home cluster minus one locale,
    # named in unavailable_locale). Slice 2 adds the 'away' override_type +
    # away_locale (the destination locale_profiles slug, used as the cluster
    # ANCHOR — plan-gen resolves the away days against the destination's own
    # radius cluster, same logic as home). Athlete-scoped (F1). No DB CHECK per
    # the project convention — override_type / locale / date constraints are
    # enforced in athlete_event_windows_repo.py (mirrors the no-CHECK sibling
    # columns sex, doubles_feasible).
    "CREATE TABLE IF NOT EXISTS athlete_event_windows (id SERIAL PRIMARY KEY, user_id INTEGER NOT NULL REFERENCES users(id), start_date DATE NOT NULL, end_date DATE NOT NULL, override_type TEXT NOT NULL, unavailable_locale TEXT, away_locale TEXT, notes TEXT DEFAULT '', created_at TIMESTAMP DEFAULT NOW())",
    "CREATE INDEX IF NOT EXISTS idx_aew_user ON athlete_event_windows(user_id)",
    # Event Windows Slice 2 (#581 WS-H) — away_locale on the pre-existing table.
    "ALTER TABLE athlete_event_windows ADD COLUMN IF NOT EXISTS away_locale TEXT",
    # Event Windows Slice 6 (#593) — VOLUME windows. override_type gains
    # 'reduced_volume' (retained capacity fraction = volume_pct, 0<pct<1) and
    # 'no_training' (zeroed day, no column); volume_pct is NULL on every other
    # type. Closed-enum + range re-asserted in athlete_event_windows_repo.py.
    "ALTER TABLE athlete_event_windows ADD COLUMN IF NOT EXISTS volume_pct NUMERIC",
    # Event Windows per-day volume (#889) — volume_by_date: a JSON object
    # {ISO date: retained fraction} layering per-DATE levels onto a reduced_volume
    # window, so one reduced travel day inside a longer window doesn't scale the
    # rest. Stored as TEXT (json.dumps, driver-agnostic — mirrors the brought_craft
    # CSV pattern); NULL → the window-wide volume_pct applies to every covered day
    # (the pre-#889 behaviour). Dates/range validated in athlete_event_windows_repo.
    "ALTER TABLE athlete_event_windows ADD COLUMN IF NOT EXISTS volume_by_date TEXT",
    # Event Windows per-date restrictions (#237) — restrictions_by_date: a JSON
    # object {ISO date: {locale_lock, indoor_only}} layering per-DAY constraints
    # onto ANY window type, which the Layer 4 validator's D-67-aware branches
    # (session_locale_not_in_cluster, indoor_only) already enforce. Stored as
    # TEXT (json.dumps, driver-agnostic — mirrors volume_by_date); NULL → no
    # per-date restrictions. Shapes/range validated in athlete_event_windows_repo.
    # Originally also carried discipline_exclusions + max_total_minutes; both
    # dropped (Andy, 2026-06-30) — disciplines are governed by gear/terrain
    # availability rules, and volume_by_date's per-day percentage already
    # supersedes a minutes cap. A legacy row with those keys stored is read fine
    # (ignored at parse time); no migration needed.
    "ALTER TABLE athlete_event_windows ADD COLUMN IF NOT EXISTS restrictions_by_date TEXT",
    # #335 Phase 2b — key the strength-rx path off the layer0 EX-id (the single
    # source of truth the synthesizer emits on StrengthExercise.exercise_id)
    # instead of the exercise NAME, which never matched the layer0 qualified
    # names ("Back Squat (Barbell)" vs logged "Back Squat"). TEXT soft-reference
    # to layer0.exercises.exercise_id — no cross-schema FK (matches the layer0
    # soft-ref convention; layer0 is ETL-versioned). Populated by the curated
    # name->EX-id backfill (D2); read by rx_engine.current_rx_by_layer0_id().
    "ALTER TABLE current_rx ADD COLUMN IF NOT EXISTS layer0_exercise_id TEXT",
    "CREATE INDEX IF NOT EXISTS idx_current_rx_user_layer0 ON current_rx(user_id, layer0_exercise_id)",
    # #335 Phase 2b backfill — curated name->layer0 EX-id map (fuzzy + Andy's
    # HITL review, 2026-06-16). Name-keyed (not user-scoped): the mapping is a
    # general fact, so any user who logged this exact name resolves to the same
    # EX-id. Idempotent (`layer0_exercise_id IS NULL` guard). The map lives in
    # `layer0_progression.NAME_TO_EX_ID` (single source — also read by the
    # rx_engine write path, #430 Slice C); generated here so the two never drift.
    # The 4 names that needed NEW layer0 exercises (barbell row, plain biceps
    # curl, sit-up, KB halo) map to EX246-EX249 from layer0 migration
    # 0011_add_strength_rx_exercises.sql (Trigger #2, Andy-ratified 2026-06-16).
    # #679 (2026-06-17): extend the backfill to the full strength alias map,
    # now the consolidated `provider_value_map_seed.STRENGTH_NAME_TO_EX_ID`
    # (#681 §4 — coarse/manual canon + Garmin-FIT specifics + Andy's logged
    # vocabulary, incl. the 40 new exercises minted in layer0 0012-0016).
    # Heals existing current_rx rows to
    # their EX-id immediately rather than only on next log. Same single source as
    # the resolver write path (provider_strength_resolve._alias_map). Idempotent
    # (`layer0_exercise_id IS NULL` guard). The #694-culled names are intentionally
    # absent from the alias map, so they are not resolved here — the cull below
    # removes their rows outright (Andy: respect the cull, 2026-06-17).
    *[
        f"UPDATE current_rx SET layer0_exercise_id='{ex_id}' "
        f"WHERE exercise='{name}' AND layer0_exercise_id IS NULL"
        for name, ex_id in STRENGTH_NAME_TO_EX_ID.items()
    ],
    # ── Catalog unification (Slice B2): injury_exercise_modifications keys off
    # layer0 EX-ids (TEXT exercise_ex_id / substitute_ex_id). These ADD COLUMNs
    # are idempotent and retained for prod DBs created before the TEXT columns
    # existed; the Slice B2 backfill (which read the v1 catalog) and the legacy
    # int exercise_id / substitute_exercise_id columns are dropped in the Slice C
    # table-drop tail below. Fresh DBs get the TEXT shape straight from PG_SCHEMA.
    "ALTER TABLE injury_exercise_modifications ADD COLUMN IF NOT EXISTS exercise_ex_id TEXT",
    "ALTER TABLE injury_exercise_modifications ADD COLUMN IF NOT EXISTS substitute_ex_id TEXT",
    # The #694 cull (five mis-classified v1 'Novel' rows) is retired with its
    # tables: exercise_inventory + exercise_equipment are dropped in the Slice C
    # tail below, and the v1 EXERCISES/EXERCISE_EQUIPMENT seeds no longer exist,
    # so the culled names cannot re-seed. The culled names are absent from the
    # layer0 strength catalog, so the layer0-sourced current_rx seed never
    # re-introduces them either.
    # #681 §4 Slice 2 (cardio fidelity) — the fine layer0 discipline id of a
    # completed cardio activity (matrix-v2 §1 option C: store the fine D-id where
    # one exists, derive coarse `_plan_sport_type` via DISCIPLINE_TO_PLAN_SPORT in
    # provider_cardio_resolve). Additive + nullable; raw `activity`/typeKey stays
    # (record-don't-drop). Populated by the provider cardio-ingest repoint
    # (Slice 2b); NULL on existing rows + manual/unmapped activities.
    "ALTER TABLE cardio_log ADD COLUMN IF NOT EXISTS discipline_id TEXT",
    # #304 — self-reported Layer-4 convenience fields that the Layer 4 prompt
    # builders already read but the Layer 1 builder previously hardcoded to NULL.
    # `experience_level` is a closed self-select band; `coaching_voice_
    # preferences` is free text. Additive + nullable.
    "ALTER TABLE athlete_profile ADD COLUMN IF NOT EXISTS experience_level TEXT",
    "ALTER TABLE athlete_profile ADD COLUMN IF NOT EXISTS coaching_voice_preferences TEXT",
    # #787 / #304 PR B — retire the legacy v1 plan_travel table. Its three city
    # read-sites moved to athlete_event_windows (away windows) + locale_profiles
    # (preferred-home city); the v1 coaching-review writer + form were removed.
    # Empty in prod at drop time (0 rows). DROP IF EXISTS is idempotent.
    "DROP TABLE IF EXISTS plan_travel",
    # ── #438 — drop the free-text `mandatory_gear_text` race-event field ──────
    # Required kit is captured structurally by the route-locale equipment model
    # (race_route_locale_equipment) + the locale equipment overrides; the
    # free-text paste-from-race-director duplicate drove no consumer that the
    # structured surface doesn't serve better. The race-week brief no longer
    # reads it (kit_manifest now synthesizes from route-locale equipment + the
    # merged race notes). DROP IF EXISTS is idempotent + no-op on a fresh DB
    # (the column was removed from CREATE TABLE in the same change).
    "ALTER TABLE race_events DROP COLUMN IF EXISTS mandatory_gear_text",
    # ── #439 — merge `race_rules_summary` into `notes` (single free-text field) ─
    # The race-edit form split "Race rules summary" and "Notes" into two adjacent
    # textareas. The brief reader only rendered race_rules_summary, so anything
    # the athlete typed into Notes never reached the synthesizer (the #306/#338
    # root: rules captured but never read). The two columns fold into the
    # surviving `notes` field (the more general name — rules + context + portage),
    # and the brief now renders `notes` in full. Guarded DO block so the fold +
    # column drop run exactly once: when race_rules_summary still exists, prepend
    # its content to notes (blank-line separated; either side may be NULL/empty),
    # then drop the column. No-op on a fresh DB (column already absent from
    # CREATE TABLE) and on re-run (column already dropped).
    """DO $$
    BEGIN
        IF EXISTS (
            SELECT 1 FROM information_schema.columns
            WHERE table_name = 'race_events' AND column_name = 'race_rules_summary'
        ) THEN
            UPDATE race_events
               SET notes = NULLIF(
                       btrim(
                           COALESCE(race_rules_summary, '')
                           || CASE
                                WHEN COALESCE(race_rules_summary, '') <> ''
                                     AND COALESCE(notes, '') <> ''
                                THEN E'\\n\\n'
                                ELSE ''
                              END
                           || COALESCE(notes, ''),
                           E'\\n'
                       ),
                       ''
                   )
             WHERE COALESCE(race_rules_summary, '') <> '';
            ALTER TABLE race_events DROP COLUMN race_rules_summary;
        END IF;
    END $$;""",
    # coach_notes merge — consolidate the two free-text athlete→coach fields
    # (`notes` + `coaching_voice_preferences`) into one canonical `coach_notes`
    # column, and retire the never-captured `previous_coaching` enum. The two
    # legacy fields said the same thing to the coach; the synthesizer now reads
    # a single field. Backfill concatenates both legacy values (blank-safe,
    # double-newline separated) into `coach_notes` before the drops. Guarded on
    # column existence so it's a clean no-op on fresh DBs and on re-runs.
    "ALTER TABLE athlete_profile ADD COLUMN IF NOT EXISTS coach_notes TEXT",
    """DO $$
    BEGIN
        IF EXISTS (SELECT 1 FROM information_schema.columns
                   WHERE table_name='athlete_profile' AND column_name='notes')
           AND EXISTS (SELECT 1 FROM information_schema.columns
                       WHERE table_name='athlete_profile'
                         AND column_name='coaching_voice_preferences') THEN
            UPDATE athlete_profile
               SET coach_notes = NULLIF(
                       BTRIM(CONCAT_WS(
                           E'\\n\\n',
                           NULLIF(BTRIM(notes), ''),
                           NULLIF(BTRIM(coaching_voice_preferences), '')
                       )),
                       ''
                   )
             WHERE coach_notes IS NULL;
        END IF;
    END $$;""",
    "ALTER TABLE athlete_profile DROP COLUMN IF EXISTS notes",
    "ALTER TABLE athlete_profile DROP COLUMN IF EXISTS coaching_voice_preferences",
    "ALTER TABLE athlete_profile DROP COLUMN IF EXISTS previous_coaching",
    # ── OAuth sign-in / connect-first identity ────────────────────────────
    # Per Onboarding_OAuth_Signin_Design_v1 §5 (#251). provider_identity is
    # the DURABLE "sign in with <provider>" login link — deliberately separate
    # from provider_auth (the revocable sync credential). It must survive a
    # sync disconnect, which nulls provider_auth.provider_user_id
    # (routes/provider_auth.disconnect), so login can't ride on that column.
    # UNIQUE (provider, provider_user_id) enforces one provider account → at
    # most one AIDSTATION account — the invariant provider_auth can't, since
    # its provider_user_id is non-unique. Garmin is intentionally NOT a
    # sign-in provider (no OAuth; API paused) — no reserved row needed, the
    # table is open-vocab on `provider`.
    """CREATE TABLE IF NOT EXISTS provider_identity (
        id SERIAL PRIMARY KEY,
        user_id INTEGER NOT NULL REFERENCES users(id),
        provider TEXT NOT NULL,
        provider_user_id TEXT NOT NULL,
        email_at_link TEXT,
        linked_at TIMESTAMP NOT NULL DEFAULT NOW(),
        last_login_at TIMESTAMP,
        UNIQUE (provider, provider_user_id),
        UNIQUE (user_id, provider)
    )""",
    "CREATE INDEX IF NOT EXISTS provider_identity_user_idx ON provider_identity (user_id)",
    # Passwordless-capable accounts: a "sign in with <provider>" account has
    # no password. routes/auth._check_password already fails closed on an
    # empty/NULL hash, so a passwordless row simply can't authenticate via the
    # password form (design decision #2). DROP NOT NULL is a no-op on re-run.
    "ALTER TABLE users ALTER COLUMN password_hash DROP NOT NULL",
    # Provider-offered emails are unverified-by-us. This flag stays FALSE for
    # provider-seeded + legacy rows until a verify flow ships; it gates the
    # no-silent-merge-on-email rule (design decision #5).
    "ALTER TABLE users ADD COLUMN IF NOT EXISTS email_verified BOOLEAN DEFAULT FALSE",
    # Plan-lifecycle notifications (#259/#260) — email + in-app badge when plan
    # generation reaches a terminal status (`ready`/`failed`) in
    # `_advance_plan_generation`. Both the progress-screen poller AND the
    # every-minute cron drive that transition, so the notification is fired
    # under an ATOMIC claim on `notified_at`: the first writer to flip it from
    # NULL to NOW() wins and sends the one email; a racing second pass matches 0
    # rows and no-ops. This is the double-send guard the issue calls for — keyed
    # on the row, not a per-process flag, so it holds across the poller/cron
    # race. `notification_seen_at` is the in-app dismissal stamp: the dashboard
    # badge shows rows with `notified_at` set AND `notification_seen_at` NULL, so
    # gating on `notified_at IS NOT NULL` keeps legacy `ready`-by-default rows
    # (which never went through the notification path) from suddenly badging.
    # Both nullable; the claim/read SQL (plan_notifications.py) tolerates their
    # absence so the code is deploy-safe even before this column lands.
    "ALTER TABLE plan_versions ADD COLUMN IF NOT EXISTS notified_at TIMESTAMPTZ",
    "ALTER TABLE plan_versions ADD COLUMN IF NOT EXISTS notification_seen_at TIMESTAMPTZ",
    # Partial index backing the dashboard badge read (the unseen-notification
    # SELECT is user-scoped + filtered to the small set of fired-but-unseen
    # rows); keeps the per-render context cost negligible like `active_nudges`.
    "CREATE INDEX IF NOT EXISTS plan_versions_unseen_notification_idx "
    "ON plan_versions (user_id) "
    "WHERE notified_at IS NOT NULL AND notification_seen_at IS NULL",
    # ── Notification delivery preferences (#963) ─────────────────────────
    # Per-(user × notification_type × channel) opt-in overrides behind the §22
    # settings matrix. Registry (`notification_prefs.py`) owns the defaults; a
    # row here is a user's deviation from one. Absent row ⇒ resolve to default,
    # so a new user needs no seeding. `channel` includes 'push' even though it's
    # undeliverable until a native app ships — the preference is stored now and
    # delivery lands later (#963 scope: "wire the preference now, deliver
    # later"). Composite PK is the upsert conflict target
    # (notification_preferences_repo.set_pref). PG-only — SQLite dev has no such
    # table; the repo's hot-path reads fail open to defaults so its absence is
    # deploy-safe.
    """CREATE TABLE IF NOT EXISTS notification_preferences (
        user_id INTEGER NOT NULL REFERENCES users(id),
        notification_type TEXT NOT NULL,
        channel TEXT NOT NULL,
        enabled BOOLEAN NOT NULL DEFAULT TRUE,
        updated_at TIMESTAMP NOT NULL DEFAULT NOW(),
        PRIMARY KEY (user_id, notification_type, channel)
    )""",
    # Read/unread state for the §21 notifications feed (#963). Orthogonal to
    # `dismissed_at` (dismiss = resolved/archived; read = merely seen): an
    # undismissed nudge can be unread (read_at NULL) or read. Nullable; legacy
    # rows read as unread until stamped. The feed's "Mark read"/"Mark all read"
    # actions and unread styling key off it.
    "ALTER TABLE account_nudges ADD COLUMN IF NOT EXISTS read_at TIMESTAMP",
    # ── Layer 3D HITL gate (#213, Slice 1) ───────────────────────────────
    # The 3D gate aggregates the human-review items the upstream nodes already
    # emit (2A/2D/2E/3B) and parks a plan at `needs_review` instead of advancing
    # to Layer 4 synthesis when the gate is non-green. `hitl_gate` persists the
    # whole `Layer3DGate` (items + resolutions + gate_status + evaluated_against)
    # as one JSONB blob — read/written whole, no per-item querying at v1 scale
    # (Layer3D_Spec §10). Nullable; a plan with no gate state (legacy / clean
    # athlete) reads NULL. The accessor (plan_sessions_repo) tolerates absence so
    # the code is deploy-safe even before this column lands.
    "ALTER TABLE plan_versions ADD COLUMN IF NOT EXISTS hitl_gate JSONB",
    # Add the `needs_review` value to the generation_status CHECK. Drop-then-add
    # is idempotent; the new set is a superset so existing rows still satisfy it
    # (same pattern as the layer4_cache entry_point + plan_sessions index_in_day
    # realignments above). A plan that hits a non-green 3D gate parks at
    # `needs_review` rather than `generating`.
    """DO $$
    BEGIN
        ALTER TABLE plan_versions DROP CONSTRAINT IF EXISTS plan_versions_generation_status_chk;
        ALTER TABLE plan_versions ADD CONSTRAINT plan_versions_generation_status_chk
            CHECK (generation_status IN ('generating', 'ready', 'failed', 'needs_review'));
    END $$;""",
    # ── Catalog unification (Slice C): drop the retired v1 catalog ────────────
    # Every production read now keys off the single canonical layer0 catalog —
    # /rx (layer0_catalog.strength_catalog), purchases (equipment_tag_layer0),
    # injuries (exercise_ex_id → layer0), and rx_engine (layer0 EX-id). The v1
    # exercise_inventory + exercise_equipment tables and the vestigial FK columns
    # are dropped here; layer0 is the sole catalog. FK-safe order: drop the child
    # table + the FK columns that reference exercise_inventory before the parent.
    # Idempotent via IF EXISTS; on a fresh DB PG_SCHEMA never created these, so
    # each statement is a harmless no-op.
    "ALTER TABLE injury_exercise_modifications DROP COLUMN IF EXISTS exercise_id",
    "ALTER TABLE injury_exercise_modifications DROP COLUMN IF EXISTS substitute_exercise_id",
    "ALTER TABLE current_rx DROP COLUMN IF EXISTS discipline",
    "ALTER TABLE current_rx DROP COLUMN IF EXISTS type",
    "ALTER TABLE current_rx DROP COLUMN IF EXISTS inventory_sugg_volume",
    "DROP TABLE IF EXISTS exercise_equipment",
    "DROP TABLE IF EXISTS exercise_inventory",
    # ── #196 Phase 3 (cross-source activity dedup + merge) — Slice 1 schema ────
    # One real-world activity reaching us via N connected providers (e.g. a Wahoo
    # ride auto-forwarded to Strava) lands as N cardio_log rows. Slice 1 lays the
    # substrate for cross-source clustering + canonical merge WITHOUT any matching
    # logic (Slice 2), canonical materialization (Slice 3), or consumer repoint
    # (Slice 4). Storage shape B (Andy 2026-06-22, Trigger-#3 DDL ratification):
    # a real activity_clusters table + cardio_log.cluster_id FK — not a flag on
    # cardio_log.
    #   - started_at: a comparable UTC start instant — the fingerprint input —
    #     populated at ingest by routes/garmin.py:_bulk_insert_cardio. DISTINCT
    #     from the existing start_time TEXT (D-56 race/time-of-day display, local
    #     HH:MM:SS paired with the TEXT date); this is a true UTC TIMESTAMP.
    #   - activity_clusters: one row per real-world activity, carrying the
    #     fingerprint anchor (coarse sport_class + started_at + duration/distance
    #     — match on the coarse class, not the fine discipline_id, per the kickoff
    #     §6 gut-check). EMPTY until Slice 2's clusterer — its immediate first
    #     writer — populates it; the FK below stays NULL until then.
    # canonical_activity + per-field provenance land in Slice 3 with their first
    # writer (materialization), not created speculatively here.
    "ALTER TABLE cardio_log ADD COLUMN IF NOT EXISTS started_at TIMESTAMP",
    """CREATE TABLE IF NOT EXISTS activity_clusters (
        id           SERIAL PRIMARY KEY,
        user_id      INTEGER NOT NULL REFERENCES users(id),
        sport_class  TEXT NOT NULL,
        started_at   TIMESTAMP,
        duration_min REAL,
        distance_mi  REAL,
        created_at   TIMESTAMP DEFAULT NOW(),
        updated_at   TIMESTAMP DEFAULT NOW()
    )""",
    "CREATE INDEX IF NOT EXISTS activity_clusters_user_start_idx ON activity_clusters (user_id, started_at)",
    "ALTER TABLE cardio_log ADD COLUMN IF NOT EXISTS cluster_id INTEGER REFERENCES activity_clusters(id)",
    "CREATE INDEX IF NOT EXISTS cardio_log_cluster_idx ON cardio_log (cluster_id) WHERE cluster_id IS NOT NULL",
    # #892 — heal race_events.framework_sport values that drifted from the
    # canonical `sport_discipline_bridge` vocabulary only by case / surrounding
    # whitespace. The retired free-text "sport override" let these through, and
    # an unmatched value made the discipline grid resolve to empty ("not
    # included in disciplines" / only "Race-wide"). CONSERVATIVE on purpose:
    # only remaps when the normalized forms are identical, so a genuinely
    # different label (e.g. "Adventure Race" vs "Adventure Racing", or a
    # discipline-level name like "Trail Running" that maps to several framework
    # sports) is left for the athlete to re-pick via the #885 structured select
    # — auto-guessing the sport there would silently mis-plan their training.
    # The union-render + flagged select keep those races' disciplines visible
    # meanwhile. DO block guards on the bridge table existing so a fresh DB
    # (pre-ETL load) doesn't error here; mirrors the terrain_gap_rules
    # precedent above. Idempotent: a second run finds nothing left to normalize.
    "DO $$ "
    "BEGIN "
    "  IF EXISTS ("
    "    SELECT 1 FROM information_schema.tables "
    "    WHERE table_schema='layer0' AND table_name='sport_discipline_bridge'"
    "  ) THEN "
    "    UPDATE race_events re "
    "    SET framework_sport = canon.framework_sport "
    "    FROM ("
    "      SELECT DISTINCT framework_sport "
    "        FROM layer0.sport_discipline_bridge "
    "       WHERE superseded_at IS NULL AND framework_sport IS NOT NULL"
    "    ) canon "
    "    WHERE re.framework_sport IS NOT NULL "
    "      AND re.framework_sport <> canon.framework_sport "
    "      AND lower(btrim(re.framework_sport)) = lower(btrim(canon.framework_sport)); "
    "  END IF; "
    "END $$;",
    # ── #196 Phase 3 (cross-source activity dedup + merge) — Slice 3 schema ────
    # Completeness scoring + canonical materialization. Slice 2 groups the N
    # cardio_log rows of one real-world activity (a Wahoo ride auto-forwarded to
    # Strava) into one activity_clusters row; THIS slice merges each cluster into a
    # single best-of record. Storage shape B (Andy 2026-06-23, Trigger-#3 DDL
    # ratification): a separate canonical_activity row per cluster — NOT a flag or
    # in-place gap-fill on cardio_log — plus per-field provenance mirroring the
    # athlete_profile_field_provenance pattern.
    #   - canonical_activity: the merged "one clean ride". Mirrors cardio_log's
    #     mergeable metric columns so Slice 4 consumers read it almost identically
    #     to a cardio_log row. One row per cluster (UNIQUE cluster_id = the upsert
    #     key); primary_cardio_log_id = the copy that won the weighted-completeness
    #     score ("richest data wins", Andy 2026-06-23); the metric columns are the
    #     best-of (primary's value, gap-filled from the higher-scoring secondaries).
    #     Written by routes/garmin.py:materialize_canonical_activity, re-run on
    #     every cluster member add (a late Strava/RWGPS arrival re-merges).
    #   - canonical_activity_field_provenance: which source supplied each merged
    #     field ("power from Wahoo, HR from Garmin"). UNIQUE (cluster_id, field_name);
    #     replaced wholesale on each re-materialization. A source='manual_override'
    #     slot is reserved (mirrors athlete_profile_field_provenance) but no cardio
    #     manual-edit path writes it yet — deferred, not built this slice.
    """CREATE TABLE IF NOT EXISTS canonical_activity (
        id                    SERIAL PRIMARY KEY,
        user_id               INTEGER NOT NULL REFERENCES users(id),
        cluster_id            INTEGER NOT NULL UNIQUE REFERENCES activity_clusters(id),
        primary_cardio_log_id INTEGER REFERENCES cardio_log(id),
        completeness_score    REAL,
        date          TEXT, activity TEXT, activity_name TEXT, discipline_id TEXT,
        started_at    TIMESTAMP,
        duration_min  REAL, moving_time_min REAL, distance_mi REAL, avg_pace TEXT, avg_speed REAL,
        avg_hr INTEGER, max_hr INTEGER, calories INTEGER,
        elev_gain_ft REAL, elev_loss_ft REAL, avg_cadence INTEGER, max_cadence INTEGER,
        avg_power INTEGER, max_power INTEGER, norm_power INTEGER,
        aerobic_te REAL, anaerobic_te REAL, swolf INTEGER, active_lengths INTEGER,
        stride_length_m REAL, vert_oscillation_cm REAL, vert_ratio_pct REAL,
        gct_ms REAL, gct_balance TEXT,
        created_at TIMESTAMP DEFAULT NOW(),
        updated_at TIMESTAMP DEFAULT NOW()
    )""",
    "CREATE INDEX IF NOT EXISTS canonical_activity_user_idx ON canonical_activity (user_id)",
    """CREATE TABLE IF NOT EXISTS canonical_activity_field_provenance (
        id                   SERIAL PRIMARY KEY,
        cluster_id           INTEGER NOT NULL REFERENCES activity_clusters(id),
        field_name           TEXT NOT NULL,
        source_cardio_log_id INTEGER REFERENCES cardio_log(id),
        source_provider      TEXT,
        last_updated_at      TIMESTAMP NOT NULL DEFAULT NOW(),
        UNIQUE (cluster_id, field_name)
    )""",
    "CREATE INDEX IF NOT EXISTS cafp_cluster_idx ON canonical_activity_field_provenance (cluster_id)",
    # ── #196 Phase 3 Slice 4 — the shared deduplicated activity feed ──────────
    # One real-world activity reaching us via N connected providers lands as N
    # cardio_log rows (Slice 1/2 group them into a cluster; Slice 3 merges each
    # cluster into one best-of canonical_activity row). This view is the single
    # read surface the "count the ride once" consumers select from instead of
    # cardio_log (Andy 2026-06-23: "build it once, shared"). It returns each real
    # activity EXACTLY once:
    #   • clustered rows  → one row per cluster = canonical_activity's merged
    #     metrics, carrying the cluster's PRIMARY cardio_log row's identity/notes/
    #     created_at + per-provider ids (so source-tagging still resolves to the
    #     richest copy's device), and plan_item_id from whichever member is
    #     plan-matched (robust to which copy the matcher linked).
    #   • unclustered rows → raw cardio_log rows with cluster_id IS NULL
    #     (pre-Slice-2 rows + NULL-started_at rows that are never clustered).
    # The two branches partition cleanly: a cardio_log row is either in a cluster
    # (and represented by its canonical row) or has cluster_id IS NULL, and
    # canonical_activity holds exactly one row per cluster — so UNION ALL counts
    # every activity once with no overlap. Column order is identical across both
    # branches (UNION ALL is positional); keep them in lockstep on any edit.
    # Invariant: materialize_canonical_activity always sets primary_cardio_log_id
    # to a live member id, so the clustered branch's INNER JOIN never drops a row.
    # Additive / idempotent (CREATE OR REPLACE) / public-schema → auto-applies on
    # each Vercel deploy; no Neon apply owed. Raw cardio_log stays the read for
    # the literal activity-LOG/CRUD pages and the per-provider coverage/HRmax
    # counts (which intentionally need the un-merged rows).
    """CREATE OR REPLACE VIEW canonical_cardio_feed AS
        SELECT
            cl.id,
            ca.user_id,
            ca.cluster_id,
            ca.date, ca.activity, ca.activity_name, ca.discipline_id, ca.started_at,
            ca.duration_min, ca.moving_time_min, ca.distance_mi, ca.avg_pace, ca.avg_speed,
            ca.avg_hr, ca.max_hr, ca.calories, ca.elev_gain_ft, ca.elev_loss_ft,
            ca.avg_cadence, ca.max_cadence, ca.avg_power, ca.max_power, ca.norm_power,
            ca.aerobic_te, ca.anaerobic_te, ca.swolf, ca.active_lengths,
            ca.stride_length_m, ca.vert_oscillation_cm, ca.vert_ratio_pct, ca.gct_ms, ca.gct_balance,
            (SELECT m.plan_item_id FROM cardio_log m
              WHERE m.cluster_id = ca.cluster_id AND m.plan_item_id IS NOT NULL
              ORDER BY m.id LIMIT 1) AS plan_item_id,
            cl.notes, cl.created_at,
            cl.garmin_activity_id, cl.polar_exercise_id, cl.wahoo_workout_id,
            cl.coros_label_id, cl.strava_activity_id, cl.rwgps_trip_id
        FROM canonical_activity ca
        JOIN cardio_log cl ON cl.id = ca.primary_cardio_log_id
        UNION ALL
        SELECT
            cl.id,
            cl.user_id,
            cl.cluster_id,
            cl.date, cl.activity, cl.activity_name, cl.discipline_id, cl.started_at,
            cl.duration_min, cl.moving_time_min, cl.distance_mi, cl.avg_pace, cl.avg_speed,
            cl.avg_hr, cl.max_hr, cl.calories, cl.elev_gain_ft, cl.elev_loss_ft,
            cl.avg_cadence, cl.max_cadence, cl.avg_power, cl.max_power, cl.norm_power,
            cl.aerobic_te, cl.anaerobic_te, cl.swolf, cl.active_lengths,
            cl.stride_length_m, cl.vert_oscillation_cm, cl.vert_ratio_pct, cl.gct_ms, cl.gct_balance,
            cl.plan_item_id,
            cl.notes, cl.created_at,
            cl.garmin_activity_id, cl.polar_exercise_id, cl.wahoo_workout_id,
            cl.coros_label_id, cl.strava_activity_id, cl.rwgps_trip_id
        FROM cardio_log cl
        WHERE cl.cluster_id IS NULL""",
    # ── #884 slice 3 — unified athlete gear/craft store ──────────────────────
    # The public-schema store for owned gear/craft (design v3 §5.1/§5.2). Merges
    # the two craft families (bikes/boats, the discipline_baseline CSV columns)
    # with the owned gear toggles (ski/climbing/etc., previously storeless).
    # Read/written by athlete_gear_repo. STAGING: created + backfilled here, but
    # nothing reads it yet — the cascade cuts over in slice 4, capture is slice 6
    # (so the old craft path stays authoritative until then). `group_kind` is
    # stored denormalized so reads route without a catalog join; `access` ∈
    # {own, access}. created_at mirrors the sibling athlete_* audit convention.
    "CREATE TABLE IF NOT EXISTS athlete_gear ("
    "user_id INTEGER NOT NULL REFERENCES users(id), gear_id TEXT NOT NULL, "
    "group_kind TEXT NOT NULL, access TEXT NOT NULL DEFAULT 'own', "
    "created_at TIMESTAMP DEFAULT NOW(), PRIMARY KEY (user_id, gear_id))",
    "CREATE INDEX IF NOT EXISTS idx_athlete_gear_user ON athlete_gear(user_id)",
    # Per-locale availability — the gear analogue of athlete_craft_locale (a
    # standing "this gear is kept at this locale"). gear_id replaces craft_slug.
    "CREATE TABLE IF NOT EXISTS athlete_gear_locale ("
    "user_id INTEGER NOT NULL REFERENCES users(id), gear_id TEXT NOT NULL, "
    "locale TEXT NOT NULL, created_at TIMESTAMP DEFAULT NOW(), "
    "PRIMARY KEY (user_id, gear_id, locale))",
    "CREATE INDEX IF NOT EXISTS idx_agl_user ON athlete_gear_locale(user_id)",
    # The brought-gear set on an away window — the gear analogue of brought_craft
    # (CSV of gear_id slugs; written by the away capture in slice 5).
    "ALTER TABLE athlete_event_windows ADD COLUMN IF NOT EXISTS brought_gear TEXT",
    # Backfill (design v3 §11). Idempotent — ON CONFLICT DO NOTHING re-seeds
    # nothing on re-deploy and self-heals craft additions; removals don't
    # propagate, which is harmless while the new store is unread (slices 3→4).
    # Each owned bike/paddle craft CSV token explodes into one athlete_gear row,
    # filtered to the known craft slugs (no stale-slug leak), group_kind by family.
    f"INSERT INTO athlete_gear (user_id, gear_id, group_kind, access) "
    f"SELECT dbc.user_id, btrim(g.slug), 'bike', 'own' "
    f"FROM discipline_baseline_cycling dbc "
    f"CROSS JOIN LATERAL unnest(string_to_array(dbc.bike_types_available, ',')) AS g(slug) "
    f"WHERE btrim(g.slug) IN ({_GEAR_BACKFILL_BIKE_IN}) "
    f"ON CONFLICT (user_id, gear_id) DO NOTHING",
    f"INSERT INTO athlete_gear (user_id, gear_id, group_kind, access) "
    f"SELECT dbp.user_id, btrim(g.slug), 'paddle', 'own' "
    f"FROM discipline_baseline_paddling dbp "
    f"CROSS JOIN LATERAL unnest(string_to_array(dbp.paddle_craft_types, ',')) AS g(slug) "
    f"WHERE btrim(g.slug) IN ({_GEAR_BACKFILL_PADDLE_IN}) "
    f"ON CONFLICT (user_id, gear_id) DO NOTHING",
    # ── #196 Phase 2 — the canonical daily-wellness layer ─────────────────────
    # The daily-metrics analog of Phase 3's canonical_activity: one best-of row
    # per (user, date), materialized on ingest by canonical_wellness.py:
    # materialize_canonical_wellness. Replaces the coalesce-at-reader merge that
    # lived only in layer3a (so all consumers share one wellness read surface).
    #   - The 3 genuinely-multi-source fields (sleep_hours / hrv_rmssd_ms /
    #     resting_hr — every device measures the same quantity) are merged
    #     field-by-field, freshest-non-null with a garmin>whoop>oura>polar>coros
    #     tiebreak, and carry a *_source provenance column ("HRV from Garmin,
    #     sleep from Whoop").
    #   - The widened context fields (hrv/rhr baselines, sleep_score,
    #     training_readiness, vo2max, acute_training_load) are Garmin-origin today
    #     and carry NO source column: provenance is only meaningful where a merge
    #     chose between sources. "Readiness"/"load" are deliberately NOT coalesced
    #     across providers — Garmin training_readiness, Whoop recovery, Polar ANS
    #     charge are different quantities; merging them would average unlike units.
    # Additive / idempotent / public-schema → auto-applies on each Vercel deploy;
    # no Neon apply owed. Design: designs/CanonicalDailyWellness_196_Phase2_Design_v1.md
    """CREATE TABLE IF NOT EXISTS canonical_daily_wellness (
        id                       SERIAL PRIMARY KEY,
        user_id                  INTEGER NOT NULL REFERENCES users(id),
        date                     TEXT NOT NULL,
        total_sleep_hours        DOUBLE PRECISION, total_sleep_hours_source TEXT,
        hrv_rmssd_ms             DOUBLE PRECISION, hrv_rmssd_ms_source      TEXT,
        resting_hr               INTEGER, resting_hr_source        TEXT,
        hrv_7d_avg_ms            DOUBLE PRECISION,
        resting_hr_7day_avg      INTEGER,
        sleep_score              INTEGER,
        training_readiness       INTEGER,
        vo2max_running           DOUBLE PRECISION,
        vo2max_cycling           DOUBLE PRECISION,
        acute_training_load      INTEGER,
        created_at TIMESTAMP NOT NULL DEFAULT NOW(),
        updated_at TIMESTAMP NOT NULL DEFAULT NOW(),
        UNIQUE (user_id, date)
    )""",
    "CREATE INDEX IF NOT EXISTS canonical_daily_wellness_user_date_idx ON canonical_daily_wellness (user_id, date)",
    # Slice 2.3 (#196): the 3A wellness reader now reads these merged floats back
    # out of canonical and folds them into the 3A bundle hash (integration_bundle_hash),
    # which serializes exact double-precision repr. REAL (single precision) would
    # round-trip e.g. 54.7 -> 54.70000076293945 and drift the cache key vs the
    # retired inline-coalesce path, so widen to DOUBLE PRECISION (lossless; the
    # table is empty in prod so the rewrite is trivial). Idempotent on re-deploy.
    "ALTER TABLE canonical_daily_wellness ALTER COLUMN total_sleep_hours TYPE DOUBLE PRECISION",
    "ALTER TABLE canonical_daily_wellness ALTER COLUMN hrv_rmssd_ms      TYPE DOUBLE PRECISION",
    "ALTER TABLE canonical_daily_wellness ALTER COLUMN hrv_7d_avg_ms     TYPE DOUBLE PRECISION",
    "ALTER TABLE canonical_daily_wellness ALTER COLUMN vo2max_running    TYPE DOUBLE PRECISION",
    "ALTER TABLE canonical_daily_wellness ALTER COLUMN vo2max_cycling    TYPE DOUBLE PRECISION",
    # #884 slice 4b (taxonomy normalization, Andy 2026-06-29) — rename the live
    # gear group_kind 'climbing' -> 'climb' to match GEAR_REGISTRY + the modality
    # vocab. The denormalized group_kind on captured climbing_gear rows must track
    # GEAR_REGISTRY, else replace_owned_gear_for_kinds (which DELETEs by kind) and
    # get_owned_gear_toggles (which filters by _GEAR_TOGGLE_KINDS) would orphan a
    # stale 'climbing' row. Pairs with layer0 migration 0027 (gear_discipline_aliases).
    # Idempotent (matches only the old value); public-schema → auto-applies on deploy.
    "UPDATE athlete_gear SET group_kind = 'climb' WHERE group_kind = 'climbing'",
    # ── user_source_preferences (#196 Phase 5, Track B — slice B1) ───────────
    # Optional per-athlete HARD PIN over the canonical merge's automatic pick:
    # one preferred provider per domain ('wellness' | 'cardio'). When a pin is
    # set and the pinned provider has a value/copy it wins; otherwise the
    # most-complete merge applies (Andy 2026-06-29 — single pin per domain;
    # per-metric/field pins deferred). PK (user_id, domain) → at most one pin per
    # domain; absence = "no pin → automatic merge". Substrate only this slice —
    # consumers wire in B2 (wellness coalesce) / B3 (cardio merge) / B4 (picker).
    # Additive / idempotent / public-schema → auto-applies on deploy; no Neon
    # apply owed. Design: designs/CanonicalSourcePrecedence_196_Phase5_Design_v1.md
    """CREATE TABLE IF NOT EXISTS user_source_preferences (
        user_id            INTEGER NOT NULL REFERENCES users(id),
        domain             TEXT NOT NULL,
        preferred_provider TEXT NOT NULL,
        created_at TIMESTAMP NOT NULL DEFAULT NOW(),
        updated_at TIMESTAMP NOT NULL DEFAULT NOW(),
        PRIMARY KEY (user_id, domain)
    )""",
    # ── #954 — merge "Notes for the coach" into Coach Memory; retire coach_notes ─
    # The free-text `coach_notes` field (Athlete profile tab) and Coach Memory
    # (`coaching_preferences`) said the same thing to the synthesizer — both were
    # rendered into every Layer 4 surface. Consolidate onto the single Coach
    # Memory surface: migrate each athlete's non-empty `coach_notes` into one
    # durable preference (category 'general', permanent, manually-sourced —
    # source_feedback_id NULL, exactly like a hand-added pref) so the content is
    # preserved and still reaches the coach, then drop the column and its Layer 1
    # / Layer 4 plumbing. Guarded on the column's existence: the backfill runs
    # exactly once (the DROP that follows is the idempotency latch), and both are
    # clean no-ops on a fresh DB (column never added) and on re-deploy.
    """DO $$
    BEGIN
        IF EXISTS (SELECT 1 FROM information_schema.columns
                   WHERE table_name='athlete_profile' AND column_name='coach_notes') THEN
            INSERT INTO coaching_preferences
                       (user_id, category, content, permanent, source_feedback_id)
            SELECT user_id, 'general', BTRIM(coach_notes), 1, NULL
              FROM athlete_profile
             WHERE NULLIF(BTRIM(coach_notes), '') IS NOT NULL;
        END IF;
    END $$;""",
    "ALTER TABLE athlete_profile DROP COLUMN IF EXISTS coach_notes",
    # #255 — system_category canonical retag (8 → 11). Remap existing
    # health_conditions_log rows off the retired slugs so they keep matching the
    # canonical enum + the Layer 2E supplement screen. endocrine/metabolic fold
    # into endocrine_metabolic; gi_immune maps to gi (the GI-distress reading the
    # curated v3 list led with — an athlete whose condition was actually an
    # autoimmune one can re-pick immune_autoimmune in the editor). Idempotent: a
    # no-op once no legacy slugs remain.
    """UPDATE health_conditions_log
          SET system_category = CASE system_category
              WHEN 'metabolic'  THEN 'endocrine_metabolic'
              WHEN 'endocrine'  THEN 'endocrine_metabolic'
              WHEN 'gi_immune'  THEN 'gi'
              ELSE system_category END
        WHERE system_category IN ('metabolic', 'endocrine', 'gi_immune')""",
    # #255 — body-part half. The injury picker is now side-less canonical with a
    # dedicated `side` field; existing rows encoded the side in the body_part
    # string ('Left Wrist'). Strip the leading Left/Right (the side already lives
    # in injury_log.side, derived at the old save path) and align the back labels
    # to canonical casing. Idempotent: the predicates exclude already-migrated
    # rows.
    "UPDATE injury_log SET body_part = regexp_replace(body_part, '^(Left|Right) ', '') WHERE body_part ~ '^(Left|Right) '",
    "UPDATE injury_log SET body_part = 'Lower back' WHERE body_part = 'Lower Back'",
    "UPDATE injury_log SET body_part = 'Upper back' WHERE body_part = 'Upper Back'",
    # ── Recurring time-of-day notification schedules (#964) ───────────────
    # The *when* for the recurring-send notification family (supplement AM/PM,
    # next-day-workouts preview, daily log ping) — orthogonal to the
    # notification_preferences *whether* matrix. One row per (user, schedule_type)
    # holding the local send hour; the hourly cron (scan_scheduled_sends) fires a
    # feed nudge when the user's local hour matches and re-stamps last_sent_on for
    # once-per-day dedup. `schedule_type` == the account_nudges `nudge_type` it
    # fires, so the cron's fire action is an identity mapping. PG-only (mirrors
    # notification_preferences); SQLite dev has no such table and the repo's reads
    # fail open. Composite PK is the upsert conflict target.
    """CREATE TABLE IF NOT EXISTS notification_schedules (
        user_id       INTEGER  NOT NULL REFERENCES users(id),
        schedule_type TEXT     NOT NULL,
        send_hour     SMALLINT NOT NULL,
        enabled       BOOLEAN  NOT NULL DEFAULT TRUE,
        last_sent_on  DATE,
        updated_at    TIMESTAMP NOT NULL DEFAULT NOW(),
        PRIMARY KEY (user_id, schedule_type)
    )""",
    # Per-user IANA timezone (e.g. 'America/Chicago'), captured on the schedule
    # settings page. Localizes the send hour (NOW() AT TIME ZONE timezone in the
    # cron). NULL ⇒ schedules never fire (fail-safe — can't localize the clock
    # without it). Nullable so existing users need no backfill.
    "ALTER TABLE users ADD COLUMN IF NOT EXISTS timezone TEXT",
    # ── upcoming_conditions (#289 Layer-5 producer / #964 conditions advisory) ──
    # Live near-term forecast for each upcoming TRAINING day, per user. Refreshed
    # daily by the producer cron (/cron/conditions/refresh) and pruned as days
    # pass. Distinct from plan_conditions (climate normals baked per plan_version
    # as opaque JSONB) — this is the plain, (user, date)-queryable signal the
    # conditions-advisory reconcile fires on. temp_*_c are DOUBLE PRECISION (avoid
    # the REAL round-trip drift fixed in #196 Slice 2.3); precip_prob_pct is
    # 0–100. Canonical °C (Open-Meteo native); any rendering uses the units
    # toggle. Public-schema, so it auto-applies on each Vercel deploy (no
    # layer0-apply). PG-only; SQLite dev never reaches the cron that writes it.
    """CREATE TABLE IF NOT EXISTS upcoming_conditions (
        user_id         INTEGER  NOT NULL REFERENCES users(id),
        forecast_date   DATE     NOT NULL,
        locale_id       TEXT,
        temp_max_c      DOUBLE PRECISION,
        temp_min_c      DOUBLE PRECISION,
        precip_prob_pct SMALLINT,
        refreshed_at    TIMESTAMPTZ NOT NULL DEFAULT NOW(),
        PRIMARY KEY (user_id, forecast_date)
    )""",
    # #254 / D-17 slice B — sport SUB-format capture (two-column model, D1′).
    # `framework_sport` stays the top-level bridge key; this new column holds the
    # athlete's chosen full PLA sub-format name for the five sub-format-parent
    # sports (NULL = the orchestrator composes the parent's curated default from
    # layer0.sport_sub_format_map at the Layer 2A boundary). Public-schema, so it
    # auto-applies on each Vercel deploy. IF NOT EXISTS keeps it re-run safe.
    "ALTER TABLE race_events ADD COLUMN IF NOT EXISTS sport_sub_format TEXT NULL",
    # D5 one-time backfill — set the parent's is_default sub-format on existing
    # rows whose framework_sport is one of the five parents and whose
    # sport_sub_format is still NULL, so legacy/pre-capture target events compose
    # to a real PLA sport_name (no silent NULL bands) before the capture UI
    # (slice B2) ships. Guarded on the Layer-0 table existing (it lands via the
    # gated layer0-apply, not this public migration list) so a DB without it is a
    # clean no-op; idempotent (the NULL predicate excludes already-backfilled
    # rows). Athlete intent wins — rows that already carry a sport_sub_format are
    # never overwritten, even if the Layer-0 default later moves.
    """DO $$
    BEGIN
        IF to_regclass('layer0.sport_sub_format_map') IS NOT NULL THEN
            UPDATE race_events re
               SET sport_sub_format = m.sub_format_sport
              FROM layer0.sport_sub_format_map m
             WHERE re.sport_sub_format IS NULL
               AND m.parent_sport = re.framework_sport
               AND m.is_default = TRUE
               AND m.superseded_at IS NULL;
        END IF;
    END $$;""",
    # #884 slice 6c — brought_craft column DROP (the tail of the 6c-1 brought-
    # gear read+write cutover). The EventWindow attribute, repo read, and write
    # path all moved to brought_gear in 6c-1; that deploy ran the
    # brought_craft→brought_gear backfill (now removed above) one final time, so
    # brought_gear is authoritative and the legacy column can be retired. Public-
    # schema → auto-applies on each Vercel deploy. IF EXISTS keeps it re-run safe
    # and a clean no-op on a fresh DB that never created brought_craft.
    "ALTER TABLE athlete_event_windows DROP COLUMN IF EXISTS brought_craft",
    # #884 slice 6c-3 — retire the legacy athlete_craft_locale table (the (b)
    # standing-gear surface from Event Windows slice 4). Slice 5's away overlay
    # moved the live write+read path onto athlete_gear_locale
    # (replace_gear_locale / load_gear_locales); the only remaining reader was the
    # craft_locale→gear_locale backfill above (now removed), which ran one final
    # time on every deploy since slice 5, so gear_locale is authoritative. CASCADE
    # drops the orphaned index; IF EXISTS keeps it re-run safe and a clean no-op on
    # a fresh DB that never created the table. Public-schema → auto-applies on each
    # Vercel deploy.
    "DROP TABLE IF EXISTS athlete_craft_locale CASCADE",
    # Phase 0 (#246/#394/#223) — health_screening. AIDSTATION Health Screening
    # Spec v2: one current-state row per user. `flags` is the structured PAR-Q+
    # taxonomy (§4/§5); `details` is the optional per-flag free text, stored only
    # under explicit opt-in (`details_optin`, §7.2) — sensitive health data. The
    # acknowledgment + annual-reassessment timestamps (§9) are DB-authoritative
    # (NOW() / NOW()+365d on each save). Acknowledgment-only / non-blocking: flags
    # are coaching context, never a plan-gen gate (§2.3). Append-only acknowledgment
    # history (§8.3 liability defense) is a follow-up; this row is current state.
    """CREATE TABLE IF NOT EXISTS health_screening (
        user_id INTEGER PRIMARY KEY REFERENCES users(id),
        screening_version TEXT NOT NULL DEFAULT 'v1',
        flags JSONB NOT NULL DEFAULT '[]'::jsonb,
        details JSONB NOT NULL DEFAULT '{}'::jsonb,
        details_optin BOOLEAN NOT NULL DEFAULT FALSE,
        acknowledged BOOLEAN NOT NULL DEFAULT FALSE,
        acknowledged_at TIMESTAMP,
        last_assessed_at TIMESTAMP,
        reassessment_due_at TIMESTAMP,
        created_at TIMESTAMP DEFAULT NOW(),
        updated_at TIMESTAMP DEFAULT NOW()
    )""",
    # #272 — SMS / WhatsApp invites, in addition to email. An invite now
    # carries a `channel` ('email' | 'sms' | 'whatsapp') and is delivered to
    # either `email` or the new `phone` column depending on it — so `email`
    # drops its NOT NULL (a phone-channel invite has no email until the
    # athlete enters one at registration). Existing rows are all
    # channel='email' with email already set, so the column default needs no
    # backfill.
    "ALTER TABLE user_invites ALTER COLUMN email DROP NOT NULL",
    "ALTER TABLE user_invites ADD COLUMN IF NOT EXISTS phone TEXT",
    "ALTER TABLE user_invites ADD COLUMN IF NOT EXISTS channel TEXT NOT NULL DEFAULT 'email' "
    "CHECK (channel IN ('email', 'sms', 'whatsapp'))",
    # #418 — persist a plan's Layer-4 `notable_observations` so the operator
    # inspect page can surface them (previously read by nothing but the
    # now-removed `shape_override` validator). One JSONB blob written once at
    # generation-ready time; nullable so pre-migration/legacy rows read NULL.
    "ALTER TABLE plan_versions ADD COLUMN IF NOT EXISTS generation_observations JSONB",
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

# Progression / regression logic lives in calculations.py (weight increments
# from actual_weight, rep increments from PROGRESSION_RULES, +5s on time work,
# and the consecutive_failures regression after 3 REDUCE outcomes).
#
# The v1 EXERCISES + EXERCISE_EQUIPMENT seed constants were retired with the
# exercise_inventory / exercise_equipment tables (catalog unification, Slice
# C). The single canonical catalog is layer0.exercises: the /rx page reads it
# via layer0_catalog, the current_rx bootstrap seeds from it
# (_layer0_strength_seed_rows), and purchases derives impacted-exercise counts
# from it via equipment_tag_layer0.


# #826 — the curated science-provenance sources now live in the canonical
# `evidence_catalog` module (shared with the Layer 3 prompts so cited slugs
# always exist in the store). Re-exported here for back-compat with callers
# /tests that referenced this name.
from evidence_catalog import seed_rows as _evidence_seed_rows
EVIDENCE_SOURCE_SEEDS = _evidence_seed_rows()


def init_postgres():
    import psycopg2
    conn = psycopg2.connect(DATABASE_URL)
    cur = conn.cursor()
    # Each schema statement commits on its own. Previously the whole block ran
    # in one uncommitted transaction with no per-statement guard, so a single
    # bad fragment aborted the ENTIRE init (silently, caught by app.py) — which
    # is exactly what a ';' inside a SQL comment did: the naive split(';') broke
    # the comment mid-line into a non-statement fragment, a syntax error that
    # blocked every schema/migration change from Slice 1 on (#681 §4 prod
    # incident, 2026-06-19). IF NOT EXISTS makes each statement safe to re-run.
    for stmt in [s.strip() for s in PG_SCHEMA.split(';') if s.strip()]:
        try:
            cur.execute(stmt)
            conn.commit()
        except Exception as e:
            conn.rollback()
            print(f"[init_db] schema stmt failed (skipped): {e!r} :: {stmt[:100]!r}")  # Rule #15
    # Run migrations for columns added after initial deploy. Callable migrations
    # receive `cur`; string migrations are executed directly. Each migration
    # runs in its own transaction so a failure (e.g. SET NOT NULL on a column
    # that still has NULLs pre-bootstrap) doesn't abort the whole batch.
    # Advisory lock serialises concurrent Lambda cold-starts so they don't
    # race on ALTER TABLE (lock contention caused silent migration drops that
    # produced UndefinedColumn 500s on the first request after a deploy).
    # Lock is session-scoped: released automatically when the connection closes.
    cur.execute("SELECT pg_advisory_lock(7361925174)")
    conn.commit()
    for stmt in _PG_MIGRATIONS:
        try:
            if callable(stmt):
                stmt(cur)
            else:
                cur.execute(stmt)
            conn.commit()
        except Exception as e:
            conn.rollback()
            print(f"[init_db] migration failed (skipped): {e!r} :: {(stmt if isinstance(stmt, str) else repr(stmt))[:120]!r}")  # Rule #15
    # Seed current_rx for user 1 only — pre-bootstrap, the table stays empty
    # (NOT NULL on user_id post-2D would reject NULL inserts anyway). Andy's
    # rows are seeded inline by routes/auth.py:register on first-user bootstrap.
    # The seed list now comes from the canonical layer0 strength catalog (Slice
    # C). Best-effort + isolated: a missing/empty layer0 schema (e.g. a bare DB
    # built before the ETL has run) must not abort the rest of init.
    cur.execute('SELECT 1 FROM users WHERE id = 1')
    if cur.fetchone():
        try:
            _seed_current_rx_for_user(cur, 1, _layer0_strength_seed_rows(cur))
            conn.commit()
        except Exception as e:
            conn.rollback()
            print(f"[init_db] current_rx seed skipped: {e!r}")  # Rule #15
    # Seed steps run AFTER the migration loop. Each is wrapped in its own
    # try/commit/except-rollback so one failing seed can't abort the tail of
    # init (and get swallowed by app.py's broad "DB init skipped" catch) the way
    # the unguarded schema loop did pre-#742. The migration loop above has
    # already committed per-statement, so a seed failure here can only lose that
    # one seed's data — never the schema. Mirrors the migration loop's guard
    # (#747 residual hardening).
    #
    # Seed provider_value_map (#681 §4) from the consolidated seed module. The
    # table is the runtime-canonical store; the seed module is its git authoring
    # source, so ON CONFLICT DO UPDATE re-syncs the table to the seed each deploy.
    try:
        _pvm_rows = list(provider_value_map_rows())
        cur.executemany(
            '''INSERT INTO provider_value_map
               (provider, data_type, direction, source_value, canonical_kind,
                canonical_value, match_kind, confidence, no_canonical_match, notes)
               VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
               ON CONFLICT (provider, data_type, direction, source_value)
               DO UPDATE SET canonical_kind=EXCLUDED.canonical_kind,
                             canonical_value=EXCLUDED.canonical_value,
                             match_kind=EXCLUDED.match_kind,
                             confidence=EXCLUDED.confidence,
                             no_canonical_match=EXCLUDED.no_canonical_match,
                             notes=EXCLUDED.notes''',
            _pvm_rows
        )
        conn.commit()
        print(f"[init_db] seeded provider_value_map: {len(_pvm_rows)} rows")  # Rule #15
    except Exception as e:
        conn.rollback()
        print(f"[init_db] provider_value_map seed skipped: {e!r}")  # Rule #15
    # #826 — seed the curated science-provenance sources from the canonical
    # catalog (`evidence_catalog`), the same module the Layer 3 prompts cite
    # from, so every citable slug exists in the store. ON CONFLICT (slug) DO
    # UPDATE re-syncs the table to the catalog each deploy (mirrors
    # provider_value_map). `evidence_sources` is created in the migration list
    # above, so the table is guaranteed present here. Rows carry per-row
    # is_baseline (baseline sources auto-link to every plan; the rest are
    # cited selectively by Layer 3).
    try:
        cur.executemany(
            '''INSERT INTO evidence_sources
               (slug, kind, title, summary, citation, url, is_baseline)
               VALUES (%s, %s, %s, %s, %s, %s, %s)
               ON CONFLICT (slug) DO UPDATE SET
                   kind=EXCLUDED.kind, title=EXCLUDED.title, summary=EXCLUDED.summary,
                   citation=EXCLUDED.citation, url=EXCLUDED.url,
                   is_baseline=EXCLUDED.is_baseline''',
            EVIDENCE_SOURCE_SEEDS,
        )
        conn.commit()
        print(f"[init_db] seeded evidence_sources: "  # Rule #15
              f"{len(EVIDENCE_SOURCE_SEEDS)} rows")
    except Exception as e:
        conn.rollback()
        print(f"[init_db] evidence_sources seed skipped: {e!r}")  # Rule #15
    # Phase 1 — Seed equipment_items catalog (idempotent), then Phase 2 — build
    # the tag→id lookup, then Phase 2b — seed the shared purchase_recommendations
    # catalog. These three steps are interdependent (the purchase-rec seed needs
    # the tag→id map), so they share one guard: any failure rolls back the whole
    # equipment seed group rather than leaving a half-seeded catalog.
    try:
        for category_name, items in EQUIPMENT_CATEGORIES:
            for tag, label in items:
                cur.execute(
                    'INSERT INTO equipment_items (tag, label, category) VALUES (%s, %s, %s) '
                    'ON CONFLICT (tag) DO NOTHING',
                    (tag, label, category_name)
                )
        cur.execute('SELECT id, tag FROM equipment_items')
        tag_to_id = {row[1]: row[0] for row in cur.fetchall()}
        _seed_purchase_recommendations(cur, tag_to_id)
        conn.commit()
        print("[init_db] seeded equipment_items + purchase_recommendations")  # Rule #15
    except Exception as e:
        conn.rollback()
        print(f"[init_db] equipment/purchase seed skipped: {e!r}")  # Rule #15
    # Phase 3 — (removed) the exercise_equipment join seed retired with the v1
    # catalog (Slice C): exercise↔equipment now lives in layer0
    # (layer0.exercises.equipment_required); purchases counts impacted exercises
    # via equipment_tag_layer0 against that canonical catalog.
    # Phase 4 — (removed) the legacy locale_profiles.equipment → locale_equipment
    # backfill retired with Track 1: the locale_equipment table is dropped and
    # every locale now stores equipment as layer0 canonical names in
    # gym_profiles + locale_equipment_overrides.
    # Phase 5 — (removed) the public exercise_id FK backfill on current_rx /
    # training_log retired with #430 Slice C (C3): those columns are dropped;
    # the rx path keys off layer0_exercise_id.
    # clothing_options is now per-user (Session 3) — values accumulate as
    # the user types into the conditions form. No global seed.
    conn.commit()
    cur.close()
    conn.close()
    print('Postgres database initialized.')


if __name__ == '__main__':
    init_postgres()
